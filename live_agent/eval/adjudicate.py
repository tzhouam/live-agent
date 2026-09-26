"""Blinded, dual human adjudication of the primary outcome with third-person arbitration
(proposal §7.2 / §14, D-014; SCHEMA.md ``rating``, ``verdict``, ``speech_onset``,
``completion_claim`` and ``claim_sweep`` with source ``adjudicated``).

    # 1. build a blinded labelling page from session logs + recorded MP4s (runner --record).
    #    The key (item -> session/condition) is written OUTSIDE the batch directory.
    python -m live_agent.eval.adjudicate prepare .cache/m1/*.jsonl -o .cache/adj/batch1 \
        [--key .cache/adj/batch1.key/key.json] [--suite eval/tasks/e2_committed.jsonl] [--seed 0]
    # 2. give ONLY .cache/adj/batch1/ to annotators; each opens index.html, labels, and
    #    presses "Download labels"
    # 3. merge two independent ratings; agreements become reconciled verdicts, disagreements
    #    and incomplete reviews are listed in <key dir>/unresolved.json for a third annotator
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labelsA.json:R1 labelsB.json:R2
    # 4. after arbitration (same page; the arbiter labels the listed item ids)
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labelsA.json:R1 labelsB.json:R2 \
        --arbiter labelsC.json:R3
    # a finalized batch is immutable; changing any input needs --replace (atomic rewrite)

Blinding: items are shuffled across sessions and conditions, carry random ids, and show only
the user's instruction(s), the preregistered success criteria (checks / content rubric /
per-step criteria, frozen from the task suite), the absolute deadlines, and the video. Media
are delivered as independent files under random names, never as symlinks, with container
metadata and chapters stripped by ffmpeg; for a primary batch stripping must succeed
(``--allow-unstripped`` makes a DIAGNOSTIC batch whose merged events carry
``diagnostic_batch`` and never enter primary scoring). Before hand-off the batch is scanned
for condition names, session ids, task ids and source paths: file names, file bytes, and
every container/stream/chapter tag (ffprobe).

Items:
* **chain**: one per effective chain (final intent; per step for multistep). Every chain
  item also asks for the response onset: on-topic speech for content, the first meaningful
  spoken response otherwise, or an explicit "none by the onset deadline". A "not done" /
  "cannot tell" / "none" label (or a multistep step seen only before its predecessor) is
  accepted only if the union of intervals the rater actually played covers the request
  through the applicable deadline (clipped to the recording end); otherwise the item stays
  unresolved and must be relabelled (the arbiter never replaces an insufficient review).
* **repair_target** (RQ2): one per randomised repair assignment whose target request j was
  presented. Raters judge only j's window, against the request as of the assignment-time
  revision (its lines and criteria), so a later revision cannot undo a repair. Merge emits a
  verdict with ``repair_request`` and ``revision``. The item type reveals that a session is
  an RQ2 session, but not its arm.
* **sweep**: one per session. The rater watches the whole recording (the logged claims are
  not shown), marks every audible completion claim, assigns its referent request (and step)
  and judges it against what was requested at that moment, citing evidence at or before the
  claim. Merge emits adjudicated ``completion_claim`` + claim-level ``verdict`` events and a
  ``claim_sweep`` marker; primary FCR uses only these.

Label times must lie inside the recording and after the request; out-of-range or malformed
labels reject the whole file (``LabelError``).

Time mapping: the recording holds the presented chunks back to back (stalls are not recorded), so
video time v maps to session time through the cumulative chunk durations of the session's
``chunk_presented`` events (``video_to_session``). Times beyond the recording are rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from live_agent.eval import stats
from live_agent.eval.schema import VERDICT_LABELS, load_session
from live_agent.eval.scoring import ScoringConfig
from live_agent.eval.tasks import load_suite

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "eval" / "tasks" / "e2_committed.jsonl"
_EPS = 0.01  # video-time tolerance (s): the page records times to 0.01 s
REVIEW_TOL_S = 0.5  # reviewed-interval slack (browser timeupdate granularity)
_CFG = ScoringConfig()
STEP_D = _CFG.step_deadline_s
ONSET_D = _CFG.onset_deadline_s


class LabelError(ValueError):
    """Labels out of range, incomplete, or not matching the batch: nothing was merged."""


class BlindingError(RuntimeError):
    """The delivered batch would reveal condition or session identity."""


class MergeConflictError(RuntimeError):
    """The batch was already finalized with different inputs (use replace=True / --replace)."""


# --------------------------------------------------------------------------- time mapping


def presented_segments(events: list[dict]) -> list[tuple[float, float, float]]:
    """[(video_start, session_start, duration)] for presented chunks in presentation order."""
    chunks = sorted((e for e in events if e["type"] == "chunk_presented"), key=lambda e: e["t_start"])
    out, v = [], 0.0
    for e in chunks:
        d = e["t_end"] - e["t_start"]
        out.append((v, e["t_start"], d))
        v += d
    return out


def recorded_length(segments: Sequence[Sequence[float]]) -> float:
    return float(segments[-1][0] + segments[-1][2]) if segments else 0.0


def video_to_session(segments: list[tuple[float, float, float]], v: float) -> float:
    """Session time of video time v. Raises ValueError outside [0, recorded length]: a time
    past the last recorded frame was never observed and must not be extrapolated."""
    if not segments:
        raise ValueError("no presented chunks: cannot map video time")
    total = recorded_length(segments)
    if v < -_EPS or v > total + _EPS:
        raise ValueError(f"video time {v:.3f} s outside the recording [0, {total:.3f}] s")
    for v0, s0, d in segments:
        if v < v0 + d:
            return s0 + max(0.0, v - v0)
    v0, s0, d = segments[-1]
    return s0 + d


def session_to_video(segments: list[tuple[float, float, float]], t: float) -> float:
    """Video time of session time t (a stall maps to the next recorded frame; past the
    recording -> the recording end)."""
    for v0, s0, d in segments:
        if t < s0 + d:
            return v0 + max(0.0, t - s0)
    if not segments:
        return t
    v0, s0, d = segments[-1]
    return v0 + d


def _deadline_v(segs: list, t: float) -> dict[str, Any]:
    """A session-time deadline as shown to raters: video time (clipped) + beyond-recording flag."""
    last = segs[-1][1] + segs[-1][2] if segs else 0.0
    return {"v": round(session_to_video(segs, t), 2), "beyond": t > last + _EPS}


# --------------------------------------------------------------------------- items


def chains_for_adjudication(events: list[dict]) -> list[dict[str, Any]]:
    """Final intent of every effective (not finally withdrawn) chain, with its clock origin
    and revision count (number of ``revision`` annotations)."""
    return [c for c in _all_chains(events) if not c["withdrawn"] and "origin" in c]


def _all_chains(events: list[dict]) -> list[dict[str, Any]]:
    utt = {e["uid"]: e for e in events if e["type"] == "utterance"}
    anns = sorted((e for e in events if e["type"] == "chain_annotation"),
                  key=lambda e: utt.get(e["uid"], {}).get("t_end", 0.0))
    chains: dict[str, dict[str, Any]] = {}
    for e in anns:
        c = chains.setdefault(e["chain_id"], {"chain_id": e["chain_id"], "texts": [], "withdrawn": False,
                                              "revision": -1, "ann": {}, "origins": [], "anns": []})
        u = utt.get(e["uid"], {})
        c["texts"].append(u.get("text", ""))
        if e["action"] == "withdrawal":
            c["withdrawn"] = True
            continue
        c["withdrawn"] = False
        c["origin"] = u.get("t_end", 0.0)
        c["origins"].append(c["origin"])
        c["revision"] += 1
        c["ann"] = e
        c["anns"].append(e)
        for k in ("kind", "intent", "content_type", "steps", "label"):
            if k in e:
                c[k] = e[k]
    for c in chains.values():
        steps = c.get("steps")
        c["n_steps"] = (len(steps) if isinstance(steps, list) else int(steps)) if c.get("kind") == "multistep" and steps else 1
        c["kind"] = "action" if c.get("kind") == "correction" else c.get("kind", "action")
    return list(chains.values())


def _criteria_from_intent(it: dict[str, Any]) -> dict[str, Any]:
    kind = "action" if it.get("kind") == "correction" else it.get("kind", "action")
    cr: dict[str, Any] = {"kind": kind, "intent": it.get("intent", "")}
    if kind == "content":
        cr["content_type"] = it.get("content_type")
        cr["duration_s"] = it.get("prereg_duration_s", _CFG.content_duration_s.get(it.get("content_type") or "qa"))
        cr["rubric"] = it.get("rubric")
        if not cr["rubric"]:
            raise ValueError(f"content intent without a preregistered rubric: {it}")
    elif kind == "multistep":
        steps = it.get("steps") or []
        if not steps or not all(isinstance(s, dict) and s.get("checks") for s in steps):
            raise ValueError(f"multistep intent without per-step criteria: {it}")
        cr["steps"] = [{"intent": s.get("intent", ""), "checks": list(s["checks"])} for s in steps]
    else:
        if not it.get("checks"):
            raise ValueError(f"action intent without checks: {it}")
        cr["checks"] = list(it["checks"])
    return cr


def _criteria(tasks: dict[str, Any], task_id: str, label: str, revision: int,
              ann: dict[str, Any] | None) -> dict[str, Any]:
    """Preregistered criteria of revision ``revision`` of chain ``label``: from the task
    suite, else from a chain_annotation that carries them (``checks`` / ``rubric`` /
    ``steps`` as dicts). Raises if none: an item without criteria cannot be adjudicated."""
    t = tasks.get(task_id)
    if t is not None:
        hist = [u.intent for u in t.utterances if u.chain == label and u.annotation in ("new", "revision")]
        if 0 <= revision < len(hist) and hist[revision]:
            return _criteria_from_intent(hist[revision])
    if ann and (ann.get("checks") or ann.get("rubric")
                or (isinstance(ann.get("steps"), list) and ann["steps"] and isinstance(ann["steps"][0], dict))):
        return _criteria_from_intent(ann)
    raise ValueError(f"no preregistered criteria for task {task_id} chain {label} revision {revision}")


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def final_criteria_sha(task: Any, label: str) -> str | None:
    """Hash of the preregistered criteria of chain ``label``'s final intent in ``task`` (the
    value merge writes as ``criteria_sha256`` on chain verdicts); None if it ends withdrawn."""
    hist = [u.intent for u in task.utterances if u.chain == label and u.annotation in ("new", "revision")]
    final = task.final_intents().get(label)
    return _sha(_criteria_from_intent(hist[-1])) if final is not None and hist else None


PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>Adjudication</title>
<style>
:root{--bg:#fff;--fg:#111;--mut:#666;--line:#ddd;--acc:#1f6feb;--bad:#c62828}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--mut:#999;--line:#333;--acc:#58a6ff;--bad:#ef5350}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}
.item{border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0;display:flex;gap:16px;flex-wrap:wrap}
video{width:300px;max-width:100%;background:#000} .meta{flex:1;min-width:260px}
.mut{color:var(--mut);font-size:13px} button{margin:2px} .step{margin:8px 0;padding:6px;border-top:1px dashed var(--line)}
.crit{margin:6px 0;padding:6px 8px;border-left:3px solid var(--acc);font-size:14px} .crit ul{margin:2px 0 2px 18px;padding:0}
.dl{font-size:13px;margin:4px 0} .bad{color:var(--bad)} .sel{outline:2px solid var(--acc)}
</style>
<h1>Blinded adjudication · __N__ items</h1>
<p class="mut">For each <b>request</b> item the user's request(s), the <b>preregistered criteria</b> and the
<b>absolute deadlines</b> (video time, counted from the end of the user's final request) are shown; the video
starts at the request. Judge only against the criteria of the <b>final</b> request. "Done" needs every listed
check. <b>Action</b>: pause at the <b>first frame that clearly shows it</b> and press "first compliant = now".
<b>Multistep</b>: label each step; for step i mark the first frame showing it <b>after</b> step i−1 was done
(if it was only done before, mark that time). <b>Content</b>: mark when on-topic speech starts (or "no on-topic
speech"), judge the rubric over the whole answer, and if it passes mark when the answer ends. <b>Every request</b>:
mark when the persona's first meaningful spoken response to it starts (content: on-topic speech), or "none by the
onset deadline". Before "not done", "cannot tell" or "none", <b>play the video continuously from the request through
the deadline</b> (or to the end of the recording): only intervals actually played at normal speed count (skipping or
seeking does not), and shorter reviews are sent to a third annotator.
<b>Claim sweep</b> items: play the <b>whole</b> recording, press "claim heard = now" whenever the persona says it
has done something, choose which request it refers to, and judge whether that request (as it stood at that
moment) had visibly been done <b>before</b> the claim; cite the evidence frame, which must not be after the
claim. Press "sweep complete" at the end (also when there were no claims). "Cannot tell" is allowed.
Do not guess the condition.</p>
<div id="items"></div>
<p><button onclick="dl()">Download labels</button> <span class="mut" id="cnt"></span></p>
<script>
const ITEMS = __ITEMS__;
const BATCH = "__BATCH__";
const L = {}, PLAY = {};  // PLAY[id] = {last, iv}: intervals actually played (normal playback only)
const NAMES = {complied: "done", not_complied: "not done", unknown: "cannot tell"};
try { Object.assign(L, JSON.parse(localStorage.getItem("adj-" + BATCH) || "{}")); } catch (e) {}
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]); }
function save(){ try { localStorage.setItem("adj-" + BATCH, JSON.stringify(L)); } catch (e) {}
  document.getElementById("cnt").textContent = Object.keys(L).length + " labels"; }
function vid(id){ return document.getElementById("v-" + id); }
function mergeIv(iv){ const s = iv.map(x => [x[0], x[1]]).sort((a, b) => a[0] - b[0]), out = [];
  for (const x of s) { const l = out[out.length - 1]; if (l && x[0] <= l[1] + 0.3) l[1] = Math.max(l[1], x[1]); else out.push(x); }
  return out.map(x => [+x[0].toFixed(2), +x[1].toFixed(2)]); }
function watched(id, prev){ return mergeIv([...(prev || []), ...((PLAY[id] || {}).iv || [])]); }
function upto(iv){ return iv.length ? iv[iv.length - 1][1] : null; }
function obj(id, step){ const k = id + "/" + step; return L[k] || (L[k] = {}); }
function done(id, o){ o.v_watched = watched(id, o.v_watched); save(); render(); }
function set(id, step, key, val){ const o = obj(id, step); o[key] = val;
  if (key === "onset_none" && val) delete o.v_onset; if (key === "v_onset") delete o.onset_none; done(id, o); }
function now(id, step, key){ set(id, step, key, +vid(id).currentTime.toFixed(2)); }
function addClaim(id){ const o = obj(id, 0); (o.claims = o.claims || []).push({v_claim: +vid(id).currentTime.toFixed(2),
  ref: null, step: null, label: null}); o.complete = false; done(id, o); }
function setClaim(id, i, key, val){ const o = obj(id, 0); o.claims[i][key] = val; o.complete = false; done(id, o); }
function setRef(id, i, val){ const [r, s] = val.split("|"); const o = obj(id, 0);
  o.claims[i].ref = r || null; o.claims[i].step = s === "" || s == null ? null : +s; o.complete = false; done(id, o); }
function delClaim(id, i){ const o = obj(id, 0); o.claims.splice(i, 1); o.complete = false; done(id, o); }
function complete(id){ const o = obj(id, 0); o.claims = o.claims || []; o.complete = true; done(id, o); }
function list(xs){ return "<ul>" + xs.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>"; }
function rubric(r){ return "<ul>" + Object.entries(r).map(([k, v]) => "<li>" + esc(k) + ": " +
  esc(Array.isArray(v) ? v.join("; ") : v) + "</li>").join("") + "</ul>"; }
function crit(c, s){
  if (c.kind === "multistep") {
    if (s == null) return "<b>" + esc(c.intent) + "</b><ol>" + c.steps.map(st => "<li>" + esc(st.intent) + list(st.checks) + "</li>").join("") + "</ol>";
    const st = c.steps[s]; return "<b>step " + (s + 1) + ": " + esc(st.intent) + "</b>" + list(st.checks); }
  if (c.kind === "content") return "<b>" + esc(c.intent) + "</b> (" + esc(c.content_type) + ", preregistered duration " +
    c.duration_s + " s)" + rubric(c.rubric);
  return "<b>" + esc(c.intent) + "</b>" + list(c.checks);
}
function at(d, rel, end){ return "video " + d.v.toFixed(1) + " s (" + rel + ")" +
  (d.beyond ? " <span class=bad>after the recording ends at " + end.toFixed(1) + " s</span>" : ""); }
function deadlines(it){ const d = it.dl;
  if (it.kind === "content") return "On-topic speech must start by " + at(d.onset_by, "request end + " + d.onset_s + " s", it.v_len) +
    "; the complete answer must end by " + at(d.complete_by, "request end + " + d.onset_s + " s + " + it.criteria.duration_s + " s", it.v_len) + ".";
  if (it.kind === "multistep") return "Step 1 done by " + at(d.done_by, "request end + " + d.step_s + " s", it.v_len) +
    "; each later step within " + d.step_s + " s after the previous step was done.";
  return "Done by " + at(d.done_by, "request end + " + d.step_s + " s", it.v_len) + ".";
}
function chainItem(it, m){
  m.innerHTML = "<div class=mut>" + it.id + " · request · " + it.kind + (it.content_type ? " / " + it.content_type : "") +
    " · request ends at video " + it.v_origin.toFixed(1) + " s</div>" +
    it.texts.map((t, i) => "<div>" + (i ? "then: " : "user: ") + t + "</div>").join("") +
    "<div class=dl>" + deadlines(it) + "</div>";
  for (let s = 0; s < it.n_steps; s++) {
    const cur = L[it.id + "/" + s] || {};
    const st = document.createElement("div"); st.className = "step";
    let h = "<div class=crit>" + crit(it.criteria, it.kind === "multistep" ? s : null) + "</div>";
    h += ["complied", "not_complied", "unknown"].map(x =>
      `<button class="${cur.label === x ? "sel" : ""}" onclick="set('${it.id}',${s},'label','${x}')">${NAMES[x]}</button>`).join("");
    if (it.kind !== "content") h += ` <button onclick="now('${it.id}',${s},'v_first')">first compliant = now</button>`;
    else h += ` <button onclick="now('${it.id}',${s},'v_end')">answer ends = now</button>`;
    if (s === 0) h += `<div>${it.kind === "content" ? "On-topic speech" : "First meaningful spoken response to this request"}: ` +
      `<button onclick="now('${it.id}',0,'v_onset')">starts = now</button>` +
      ` <button class="${cur.onset_none ? "sel" : ""}" onclick="set('${it.id}',0,'onset_none',true)">none by the onset deadline</button></div>`;
    const bad = cur.v_onset != null && cur.v_end != null && cur.v_end < cur.v_onset;
    h += ` <span class=mut>${cur.v_first != null ? "first " + cur.v_first + " s " : ""}${
      cur.v_onset != null ? "onset " + cur.v_onset + " s " : ""}${cur.v_end != null ? "end " + cur.v_end + " s " : ""}${
      cur.v_watched ? "watched " + cur.v_watched.map(x => x[0] + "–" + x[1]).join(", ") + " s" : ""}</span>` + (bad ? " <span class=bad>answer ends before onset</span>" : "");
    st.innerHTML = h; m.appendChild(st);
  }
}
function sweepItem(it, m){
  const cur = L[it.id + "/0"] || {};
  let h = "<div class=mut>" + it.id + " · claim sweep · whole recording (" + it.v_len.toFixed(1) + " s)</div>" +
    "<div>Requests in this recording:</div><ol>" + it.refs.map(r => "<li>" + r.revisions.map(v =>
      "at video " + v.v_origin.toFixed(1) + " s: " + v.text + "<div class=crit>" + crit(v.criteria, null) + "</div>").join("") + "</li>").join("") + "</ol>";
  h += `<button onclick="addClaim('${it.id}')">claim heard = now</button> <button class="${cur.complete ? "sel" : ""}" onclick="complete('${it.id}')">sweep complete</button>` +
    ` <span class=mut>${cur.v_watched ? "watched " + cur.v_watched.map(x => x[0] + "–" + x[1]).join(", ") + " s" : ""}</span>`;
  (cur.claims || []).forEach((c, i) => {
    const opts = ['<option value="|">refers to ...</option>'].concat(it.refs.flatMap((r, j) => {
      const o = [`<option value="${r.ref}|" ${c.ref === r.ref && c.step == null ? "selected" : ""}>request ${j + 1}</option>`];
      for (let s = 0; s < r.n_steps && r.n_steps > 1; s++) o.push(`<option value="${r.ref}|${s}" ${c.ref === r.ref && c.step === s ? "selected" : ""}>request ${j + 1}, step ${s + 1}</option>`);
      return o; })).join("");
    const bad = c.v_evidence != null && c.v_evidence > c.v_claim;
    h += `<div class=step>claim at ${c.v_claim} s <select onchange="setRef('${it.id}',${i},this.value)">${opts}</select> ` +
      ["complied", "not_complied", "unknown"].map(x => `<button class="${c.label === x ? "sel" : ""}" onclick="setClaim('${it.id}',${i},'label','${x}')">${NAMES[x]}</button>`).join("") +
      ` <button onclick="setClaim('${it.id}',${i},'v_evidence',+vid('${it.id}').currentTime.toFixed(2))">evidence = now</button>` +
      ` <button onclick="delClaim('${it.id}',${i})">delete</button> <span class=mut>${c.v_evidence != null ? "evidence " + c.v_evidence + " s" : ""}</span>` +
      (bad ? " <span class=bad>evidence after the claim does not count</span>" : "") + "</div>";
  });
  m.innerHTML = h;
}
function repairItem(it, m){
  const cur = L[it.id + "/0"] || {};
  let h = "<div class=mut>" + it.id + " · request window · video " + it.v_origin.toFixed(1) + "–" + it.v_end.toFixed(1) +
    " s</div>" + it.texts.map((t, i) => "<div>" + (i ? "then: " : "user: ") + t + "</div>").join("") +
    "<div class=dl>Judge only this window (video " + it.v_origin.toFixed(1) + "–" + it.v_end.toFixed(1) +
    " s), against the request as stated above.</div><div class=crit>" + crit(it.criteria, it.step) + "</div>";
  h += ["complied", "not_complied", "unknown"].map(x =>
    `<button class="${cur.label === x ? "sel" : ""}" onclick="set('${it.id}',0,'label','${x}')">${NAMES[x]}</button>`).join("") +
    ` <button onclick="now('${it.id}',0,'v_first')">first compliant = now</button>` +
    ` <span class=mut>${cur.v_first != null ? "first " + cur.v_first + " s " : ""}${
      cur.v_watched ? "watched " + cur.v_watched.map(x => x[0] + "–" + x[1]).join(", ") + " s" : ""}</span>`;
  m.innerHTML = h;
}
function render(){
  const root = document.getElementById("items"); const keep = {};
  document.querySelectorAll("video").forEach(v => keep[v.id] = v);
  root.innerHTML = "";
  ITEMS.forEach(it => {
    const d = document.createElement("div"); d.className = "item";
    let v = keep["v-" + it.id];
    if (!v) { v = Object.assign(document.createElement("video"),
      {id: "v-" + it.id, src: it.video + "#t=" + it.v_origin, controls: true, preload: "metadata"});
      const p = PLAY[it.id] = {last: null, iv: []};
      // an interval counts as watched only when played continuously (no seek, rate <= 2x)
      v.addEventListener("timeupdate", () => { const t = v.currentTime;
        if (!v.paused && !v.seeking && p.last != null && t >= p.last && t - p.last <= 1.5 && v.playbackRate <= 2) p.iv.push([p.last, t]);
        p.last = t; });
      v.addEventListener("seeking", () => { p.last = null; }); }
    d.appendChild(v);
    const m = document.createElement("div"); m.className = "meta";
    if (it.type === "sweep") sweepItem(it, m); else if (it.type === "repair_target") repairItem(it, m); else chainItem(it, m);
    d.appendChild(m); root.appendChild(d);
  });
}
function dl(){ const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(L, null, 1)], {type: "application/json"}));
  a.download = "labels-" + BATCH + ".json"; a.click(); }
render(); save();
</script></html>
"""


def default_key_path(batch_dir: Path) -> Path:
    """<batch>.key/key.json, next to (never inside) the annotator batch directory."""
    b = Path(batch_dir).resolve()
    return b.parent / f"{b.name}.key" / "key.json"


def _check_key_outside(batch_dir: Path, key_path: Path) -> None:
    b, k = Path(batch_dir).resolve(), Path(key_path).resolve()
    if b == k or b in k.parents:
        raise ValueError(f"key {k} must not be inside the annotator batch directory {b}")


def _ffmpeg() -> str | None:
    return shutil.which("ffmpeg") or ("/usr/bin/ffmpeg" if Path("/usr/bin/ffmpeg").exists() else None)


def deliver_media(src: Path, dst: Path, allow_unstripped: bool = False) -> str | None:
    """Put an independent file at dst (never a symlink): an ffmpeg stream copy with
    container metadata and chapters stripped. For a primary batch stripping must succeed
    (``BlindingError`` otherwise). With ``allow_unstripped`` (diagnostic batches only) a
    failed strip falls back to a hard link or plain copy and the returned warning says so."""
    ff = _ffmpeg()
    if ff:
        r = subprocess.run([ff, "-v", "error", "-y", "-i", str(src), "-map", "0", "-map_metadata", "-1",
                            "-map_chapters", "-1", "-c", "copy", "-fflags", "+bitexact", str(dst)],
                           capture_output=True, check=False)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return None
        dst.unlink(missing_ok=True)
    why = "ffmpeg failed" if ff else "no ffmpeg"
    if not allow_unstripped:
        raise BlindingError(f"{src.name}: container metadata could not be stripped ({why}); a primary "
                            "adjudication batch needs stripped media (--allow-unstripped only for a DIAGNOSTIC batch)")
    try:
        os.link(src, dst)
        how = "hard link"
    except OSError:
        shutil.copyfile(src, dst)
        how = "copy"
    msg = f"{dst.name}: delivered as a {how}; MP4 metadata NOT stripped ({why}); DIAGNOSTIC batch"
    warnings.warn(msg, stacklevel=2)
    return msg


def _ffprobe() -> str | None:
    return shutil.which("ffprobe") or ("/usr/bin/ffprobe" if Path("/usr/bin/ffprobe").exists() else None)


def container_metadata(path: Path) -> list[str] | None:
    """Every container / stream / chapter tag value of a media file (ffprobe), or None if
    ffprobe is unavailable or cannot read it."""
    fp = _ffprobe()
    if not fp:
        return None
    r = subprocess.run([fp, "-v", "error", "-show_format", "-show_streams", "-show_chapters", "-of", "json",
                        str(path)], capture_output=True, check=False, text=True)
    if r.returncode != 0:
        return None
    d = json.loads(r.stdout or "{}")
    vals = []
    for obj in [d.get("format", {}), *d.get("streams", []), *d.get("chapters", [])]:
        vals += [f"{k}={v}" for k, v in (obj.get("tags") or {}).items()]
    return vals


def check_blinded(batch_dir: Path, tokens: Sequence[str], conditions: Sequence[str]) -> None:
    """Raise BlindingError if the delivered batch reveals identity: any symlink; a file name
    containing a token or condition name; any file whose bytes contain a token (session id,
    task id, log name, source path; >= 5 chars); a text file naming a condition."""
    b = Path(batch_dir)
    toks = sorted({t for t in tokens if t and len(t) >= 5}, key=len, reverse=True)
    cond_re = [re.compile(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])") for c in sorted(set(conditions)) if c]
    problems = []
    for f in sorted(b.rglob("*")):
        if f.suffix.lower() in (".mp4", ".m4v", ".mov", ".webm", ".mkv") and f.is_file() and not f.is_symlink():
            meta = container_metadata(f)  # tag values: condition names are searched here too
            for m in meta or []:
                if any(t in m for t in toks) or any(r.search(m) for r in cond_re):
                    problems.append(f"{f.relative_to(b)}: container metadata {m!r}")
        rel = str(f.relative_to(b))
        if f.is_symlink():
            problems.append(f"{rel}: symlink")
            continue
        for t in toks:
            if t in rel:
                problems.append(f"{rel}: file name contains {t!r}")
        if any(r.search(rel) for r in cond_re):
            problems.append(f"{rel}: file name contains a condition name")
        if not f.is_file():
            continue
        data = f.read_bytes()
        for t in toks:
            if t.encode("utf-8") in data:
                problems.append(f"{rel}: contains {t!r}")
        if f.suffix in (".html", ".json", ".txt", ".js", ".css"):
            text = data.decode("utf-8", "replace")
            for r in cond_re:
                if r.search(text):
                    problems.append(f"{rel}: text names condition {r.pattern!r}")
    if problems:
        raise BlindingError("the batch would unblind annotators:\n  " + "\n  ".join(problems))


def prepare(logs: list[Path], out: Path, seed: int = 0, *, suite: Path | None = DEFAULT_SUITE,
            key_path: Path | None = None, allow_unstripped: bool = False) -> Path:
    key_path = Path(key_path) if key_path else default_key_path(out)
    _check_key_outside(out, key_path)
    tasks = {t.task_id: t for t in load_suite(suite)} if suite else {}
    out.mkdir(parents=True, exist_ok=True)
    items, key = [], {}
    tokens: list[str] = [str(Path(p).resolve().parent) for p in logs]
    conditions: list[str] = []
    media_warnings = []

    def new_id() -> str:
        while True:
            iid = secrets.token_hex(3)
            if iid not in key:
                return iid

    for log in logs:
        s = load_session(log)
        video = log.with_suffix(".mp4")
        if not video.exists():
            print(f"skip {log.name}: no recording {video.name}")
            continue
        tokens += [s.session_id, s.task_id, log.stem, str(log.resolve()), str(video.resolve())]
        conditions.append(s.condition)
        segs = presented_segments(s.events)
        v_len = recorded_length(segs)
        media = out / "media" / f"{secrets.token_hex(4)}.mp4"  # random name: the file name would unblind
        media.parent.mkdir(exist_ok=True)
        w = deliver_media(video, media, allow_unstripped)
        if w:
            media_warnings.append(w)
        rel = os.path.relpath(media, out)
        utt = {e["uid"]: e for e in s.of_type("utterance")}
        all_chains = _all_chains(s.events)
        for c in all_chains:
            if c["withdrawn"] or "origin" not in c:
                continue
            cr = _criteria(tasks, s.task_id, c.get("label", c["chain_id"]), c["revision"], c["ann"])
            iid = new_id()
            o = float(c["origin"])
            v_origin = round(session_to_video(segs, o), 2)
            D = ONSET_D + float(cr["duration_s"]) if c["kind"] == "content" else STEP_D
            dl = {"step_s": STEP_D, "onset_s": ONSET_D, "done_by": _deadline_v(segs, o + STEP_D)}
            if c["kind"] == "content":
                dl.update(onset_by=_deadline_v(segs, o + ONSET_D), complete_by=_deadline_v(segs, o + D))
            items.append({"id": iid, "type": "chain", "video": rel, "kind": c["kind"],
                          "content_type": c.get("content_type"), "texts": [html.escape(t) for t in c["texts"]],
                          "n_steps": c["n_steps"], "v_origin": v_origin, "v_len": round(v_len, 2),
                          "criteria": cr, "dl": dl})
            key[iid] = {"type": "chain", "log": str(log.resolve()), "chain_id": c["chain_id"], "segments": segs,
                        "kind": c["kind"], "n_steps": c["n_steps"], "v_origin": v_origin, "v_len": v_len,
                        "origin": o, "deadline_s": D, "revision": c["revision"], "criteria_sha256": _sha(cr)}
        # RQ2: one item per randomised repair target, judged against the intent as of the assignment
        by_id = {c["chain_id"]: c for c in all_chains}
        for ra in s.of_type("repair_assignment"):
            c = by_id.get(ra["chain_id"])
            tgt = ra.get("target_request")
            if not ra.get("arm_drawn") or tgt is None or c is None or not c["origins"]:
                continue
            tc = [e for e in s.of_type("chunk_presented") if int(e["request"]) == int(tgt)]
            if not tc:
                continue  # never presented: the point is insufficiently observed (rerun)
            ta = ra.get("t", ra.get("E"))
            rev = (int(ra["revision"]) if ra.get("revision") is not None
                   else max((i for i, o in enumerate(c["origins"]) if ta is None or o <= float(ta)), default=0))
            rev = min(rev, len(c["anns"]) - 1)
            cr = _criteria(tasks, s.task_id, c.get("label", c["chain_id"]), rev, c["anns"][rev])
            said = [utt.get(a["uid"], {}).get("text", "") for a in s.of_type("chain_annotation")
                    if a["chain_id"] == c["chain_id"] and float(utt.get(a["uid"], {}).get("t_end", 0.0)) <= c["origins"][rev]]
            v0 = round(session_to_video(segs, min(float(e["t_start"]) for e in tc)), 2)
            last = max(tc, key=lambda e: float(e["t_start"]))
            v1 = round(min(session_to_video(segs, float(last["t_start"])) + float(last["t_end"])
                           - float(last["t_start"]), v_len), 2)
            iid = new_id()
            st = ra.get("step")
            items.append({"id": iid, "type": "repair_target", "video": rel, "kind": cr["kind"],
                          "texts": [html.escape(t) for t in said], "n_steps": 1, "v_origin": v0, "v_end": v1,
                          "v_len": round(v_len, 2), "criteria": cr, "step": st})
            key[iid] = {"type": "repair_target", "log": str(log.resolve()), "chain_id": c["chain_id"],
                        "segments": segs, "kind": cr["kind"], "n_steps": 1, "v_origin": v0, "v_end": v1,
                        "v_len": v_len, "revision": rev, "repair_request": int(tgt), "step": st,
                        "criteria_sha256": _sha(cr)}
        # one audio claim sweep per session: every request the persona could claim about
        refs, krefs = [], {}
        for j, c in enumerate(all_chains):
            if not c["origins"]:
                continue
            revs = []
            for r, (o, a) in enumerate(zip(c["origins"], c["anns"], strict=True)):
                cr = _criteria(tasks, s.task_id, c.get("label", c["chain_id"]), r, a)
                revs.append({"v_origin": round(session_to_video(segs, o), 2),
                             "text": html.escape(utt.get(a["uid"], {}).get("text", "")), "criteria": cr})
            n_steps = max((len(v["criteria"].get("steps", [])) for v in revs), default=0) or 1
            ref = f"r{j}"
            refs.append({"ref": ref, "n_steps": n_steps, "revisions": revs})
            krefs[ref] = {"chain_id": c["chain_id"], "origins_v": [v["v_origin"] for v in revs],
                          "n_steps": n_steps}
        iid = new_id()
        items.append({"id": iid, "type": "sweep", "video": rel, "kind": "sweep", "n_steps": 1, "v_origin": 0.0,
                      "v_len": round(v_len, 2), "refs": refs, "texts": []})
        key[iid] = {"type": "sweep", "log": str(log.resolve()), "chain_id": None, "segments": segs,
                    "kind": "sweep", "n_steps": 1, "v_origin": 0.0, "v_len": v_len, "refs": krefs,
                    "criteria_sha256": _sha(refs)}
    random.Random(seed).shuffle(items)
    batch = out.name
    page = PAGE.replace("__N__", str(len(items))).replace("__BATCH__", batch).replace(
        "__ITEMS__", json.dumps(items, ensure_ascii=False))
    (out / "index.html").write_text(page, encoding="utf-8")
    check_blinded(out, tokens, conditions)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps({"batch": batch, "items": key, "media_warnings": media_warnings,
                                    "diagnostic_batch": bool(media_warnings),
                                    "metadata_scanned": _ffprobe() is not None}, indent=1), encoding="utf-8")
    return out / "index.html"


# --------------------------------------------------------------------------- label validation


def _check_v(v: Any, lo: float, hi: float, what: str, where: str) -> float:
    v = float(v)
    if v < lo - _EPS or v > hi + _EPS:
        raise LabelError(f"{where}: {what}={v} outside [{lo:.2f}, {hi:.2f}] s")
    return v


def _watched(lab: dict[str, Any], v_len: float, where: str) -> list[list[float]]:
    """The intervals the rater actually played (``v_watched``: [[a, b], ...] in video time,
    recorded by the page from continuous playback), validated and merged."""
    iv = []
    for x in lab.get("v_watched") or []:
        if not (isinstance(x, (list, tuple)) and len(x) == 2):
            raise LabelError(f"{where}: bad watched interval {x!r}")
        a = _check_v(x[0], 0.0, v_len, "watched start", where)
        b = _check_v(x[1], 0.0, v_len, "watched end", where)
        if b < a:
            raise LabelError(f"{where}: watched interval {x!r} ends before it starts")
        iv.append([a, b])
    return _merge_iv(iv)


def _merge_iv(iv: Sequence[Sequence[float]], gap: float = REVIEW_TOL_S) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in sorted([float(x[0]), float(x[1])] for x in iv):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def covered(iv: Sequence[Sequence[float]], lo: float, hi: float, slack: float = REVIEW_TOL_S) -> bool:
    """Is [lo, hi] inside the union of watched intervals (gaps <= slack are bridged)?"""
    if hi <= lo + slack:
        return True
    return any(a <= lo + slack and b >= hi - slack for a, b in _merge_iv(iv, slack))


def _to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str, step: int = 0) -> dict[str, Any]:
    """Validate one chain-item label and convert it to session time. Raises LabelError.
    Step 0 of every chain item carries the response-onset decision (a time, or "none by the
    onset deadline"): on-topic speech for content, the first meaningful spoken response
    otherwise."""
    segs = [tuple(x) for x in info["segments"]]
    v_len, v_origin = float(info["v_len"]), float(info["v_origin"])
    label = lab.get("label")
    if label not in VERDICT_LABELS:
        raise LabelError(f"{where}: missing or bad label {label!r}")
    r: dict[str, Any] = {"label": label, "annotator": annotator}
    for k in ("v_first", "v_end", "v_onset"):
        if lab.get(k) is not None:
            _check_v(lab[k], v_origin, v_len, k, where)  # inside the recording, after the request
    if label == "complied":
        need = "v_end" if info["kind"] == "content" else "v_first"
        if lab.get(need) is None:
            raise LabelError(f"{where}: 'done' needs {need}")
    if step == 0:
        if (lab.get("v_onset") is None) == (not lab.get("onset_none")):
            raise LabelError(f"{where}: needs exactly one response-onset decision (a time, or 'none by the deadline')")
        if lab.get("v_onset") is not None and lab.get("v_end") is not None and float(lab["v_end"]) < float(lab["v_onset"]) - _EPS:
            raise LabelError(f"{where}: answer end {lab['v_end']} before onset {lab['v_onset']}")
        r["onset_none"] = bool(lab.get("onset_none"))
    conv = {"v_first": "t_first_compliant", "v_end": "t_evidence", "v_onset": "t_onset"}
    for vk, tk in conv.items():
        if lab.get(vk) is not None and (vk != "v_onset" or step == 0):
            r[tk] = video_to_session(segs, float(lab[vk]))
    if "t_first_compliant" in r and "t_evidence" not in r:
        r["t_evidence"] = r["t_first_compliant"]
    r["_watched"] = _watched(lab, v_len, where)
    return r


def _review_need(info: dict[str, Any], r: dict[str, Any], step: int,
                 prev: dict[str, Any] | None) -> float | None:
    """Session time through which a rater must have watched (from the request) for this
    label to count. Negative labels: the applicable deadline (action origin + 15 s; content
    origin + 15 s + duration; multistep step i: the rater's step i-1 time + 15 s, step 0
    origin + 15 s). A multistep step marked done only *before* its predecessor is
    nonqualifying evidence and needs the same window. "No response onset": origin + 15 s.
    Positive marks need continuous coverage from the request to the mark: the first
    compliant frame, the answer end (content "done") and the response onset. None = no
    requirement."""
    o, kind = float(info["origin"]), info["kind"]
    prev_t = (float(prev["t_first_compliant"]) if prev is not None and prev["label"] == "complied"
              and prev.get("t_first_compliant") is not None else None)
    need = None
    if r["label"] != "complied":
        if kind == "content":
            need = o + float(info["deadline_s"])
        elif kind == "multistep" and step > 0:
            if prev_t is not None:
                need = prev_t + STEP_D
        else:
            need = o + STEP_D
    elif kind == "multistep" and step > 0 and prev_t is not None and r.get("t_first_compliant") is not None \
            and float(r["t_first_compliant"]) < prev_t:
        need = prev_t + STEP_D  # early: must show it did not also happen within its window
    if r.get("onset_none"):
        need = max(need or 0.0, o + ONSET_D)
    for k in ("t_first_compliant", "t_evidence", "t_onset"):  # positive marks: watched up to them
        if r.get(k) is not None:
            need = max(need or 0.0, float(r[k]))
    return need


def _repair_to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str,
                       step: int = 0) -> dict[str, Any]:
    """A repair-target label: judged only inside the target request's window. "Done" needs
    a first-compliant time inside the window; a negative label needs the window watched."""
    segs = [tuple(x) for x in info["segments"]]
    v0, v1, v_len = float(info["v_origin"]), float(info["v_end"]), float(info["v_len"])
    label = lab.get("label")
    if label not in VERDICT_LABELS:
        raise LabelError(f"{where}: missing or bad label {label!r}")
    r: dict[str, Any] = {"label": label, "annotator": annotator}
    if lab.get("v_first") is not None:
        r["t_first_compliant"] = video_to_session(segs, _check_v(lab["v_first"], v0, v1, "v_first (target window)", where))
        r["t_evidence"] = r["t_first_compliant"]
    elif label == "complied":
        raise LabelError(f"{where}: 'done' needs v_first")
    iv = _watched(lab, v_len, where)
    r["_watched"] = r["v_watched"] = iv
    # negative: the whole window; "done": continuously from the window start to the marked frame
    r["review_ok"] = covered(iv, v0, float(lab["v_first"]) if label == "complied" else v1)
    r["t_review_start"] = video_to_session(segs, v0)
    r["t_review_end"] = video_to_session(segs, max([v0, *(b for _, b in iv)]))
    return r


def _sweep_to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str,
                      step: int = 0) -> dict[str, Any]:
    segs = [tuple(x) for x in info["segments"]]
    v_len = float(info["v_len"])
    if lab.get("complete") is not True:
        raise LabelError(f"{where}: claim sweep not marked complete")
    watched = _watched(lab, v_len, where)
    claims = []
    for i, c in enumerate(lab.get("claims") or []):
        w = f"{where} claim {i}"
        vc = _check_v(c.get("v_claim", -1), 0.0, v_len, "v_claim", w)
        ref = info["refs"].get(c.get("ref") or "")
        if ref is None:
            raise LabelError(f"{w}: no referent request chosen")
        st = c.get("step")
        if st is not None and not 0 <= int(st) < int(ref["n_steps"]):
            raise LabelError(f"{w}: step {st} out of range")
        if c.get("label") not in VERDICT_LABELS:
            raise LabelError(f"{w}: missing or bad label {c.get('label')!r}")
        rev = max((j for j, o in enumerate(ref["origins_v"]) if o <= vc + _EPS), default=None)
        if rev is None:
            raise LabelError(f"{w}: claim at {vc} s is before the referenced request")
        ev = c.get("v_evidence")
        if c["label"] == "complied" and ev is None:
            raise LabelError(f"{w}: 'done' needs an evidence time at or before the claim")
        out = {"t": video_to_session(segs, vc), "_v": vc, "chain_id": ref["chain_id"], "ref": c["ref"],
               "step": None if st is None else int(st), "label": c["label"], "revision": rev}
        if ev is not None:
            ev = _check_v(ev, float(ref["origins_v"][rev]), vc, "v_evidence (must be after the request and "
                          "at or before the claim)", w)
            out["t_evidence"] = video_to_session(segs, ev)
        claims.append(out)
    return {"annotator": annotator, "claims": claims, "_watched": watched, "label": "complied",
            "review_ok": covered(watched, 0.0, v_len),
            "t_review_end": video_to_session(segs, watched[-1][1]) if watched else None}


def _load_ratings(path: Path, annotator: str, items: dict[str, Any]) -> dict[str, dict[str, Any]]:
    labels = json.loads(Path(path).read_text(encoding="utf-8"))
    out, errs = {}, []
    for k, lab in labels.items():
        try:
            iid, step_s = k.split("/")
            step = int(step_s)
        except ValueError:
            errs.append(f"{annotator} {k}: bad key")
            continue
        info = items.get(iid)
        if info is None:
            errs.append(f"{annotator} {k}: unknown item (wrong batch?)")
            continue
        if not 0 <= step < int(info["n_steps"]):
            errs.append(f"{annotator} {k}: step {step} out of range")
            continue
        try:
            conv = {"sweep": _sweep_to_session, "repair_target": _repair_to_session}.get(info["type"], _to_session)
            out[k] = conv(lab, info, annotator, f"{annotator} {k}", step)
        except (LabelError, ValueError) as e:
            errs.append(str(e))
    if errs:
        raise LabelError(f"{path}: {len(errs)} invalid label(s); nothing merged:\n  " + "\n  ".join(errs))
    # review coverage: the union of intervals this rater actually played anywhere in the item
    by_item: dict[str, list[str]] = {}
    for k in out:
        by_item.setdefault(k.split("/")[0], []).append(k)
    for iid, ks in by_item.items():
        info = items[iid]
        if info["type"] != "chain":
            continue
        segs = [tuple(x) for x in info["segments"]]
        iv = _merge_iv([x for k in ks for x in out[k]["_watched"]])
        v_origin, v_len = float(info["v_origin"]), float(info["v_len"])
        for k in ks:
            r, step = out[k], int(k.split("/")[1])
            r["_watched"] = iv
            need = _review_need(info, r, step, out.get(f"{iid}/{step - 1}") if step else None)
            need_v = session_to_video(segs, need) if need is not None else None  # clipped to the recording
            r["review_ok"] = need_v is None or covered(iv, min(v_origin, v_len), need_v)
            r["t_review_start"] = video_to_session(segs, min(v_origin, v_len))
            r["t_review_end"] = video_to_session(segs, max([v_origin, *(b for _, b in iv)]) if iv else v_origin)
            r["v_watched"] = iv
            if need is not None:
                r["t_review_needed"] = min(need, video_to_session(segs, v_len))
                if r["label"] != "complied" and need > video_to_session(segs, v_len) + _EPS:
                    # the deadline window runs past the presented media: this label cannot show
                    # a fully observed failure (scoring treats it as insufficient observation)
                    r["window_unobserved"] = True
    return out


# --------------------------------------------------------------------------- reconciliation


def _close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _agree(a: dict[str, Any], b: dict[str, Any], kind: str, tol: float, step: int = 0) -> bool:
    if a["label"] != b["label"]:
        return False
    if a["label"] == "complied":
        if not _close(a.get("t_first_compliant"), b.get("t_first_compliant"), tol):
            return False
        if kind == "content" and not _close(a.get("t_evidence"), b.get("t_evidence"), tol):
            return False
    if step == 0:
        return _close(a.get("t_onset"), b.get("t_onset"), tol)
    return True


def _combine(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Agreed ratings -> one verdict. Times: the later of the two (conservative)."""
    r = {"label": a["label"]}
    for k in ("t_first_compliant", "t_evidence", "t_onset"):
        xs = [x[k] for x in (a, b) if x.get(k) is not None]
        if xs:
            r[k] = max(xs)
    if "onset_none" in a:
        r["onset_none"] = a["onset_none"] and b["onset_none"]
    r["t_review_start"] = min(a["t_review_start"], b["t_review_start"])
    r["t_review_end"] = max(a["t_review_end"], b["t_review_end"])
    return r


def _ref(c: dict) -> tuple:
    """Referent of a swept claim: chain, step and the intent revision in force."""
    return (c["chain_id"], c["step"], c["revision"])


def _assign(groups: list[list[dict]], pool: list[dict], used: set[int], tol: float) -> dict[int, int]:
    """Greedy one-to-one assignment of claim groups to pool claims with the same referent
    within tol (distance = nearest group member); pool indices in ``used`` are taken."""
    cand = sorted((min(abs(g["t"] - p["t"]) for g in grp), gi, pi)
                  for gi, grp in enumerate(groups) for pi, p in enumerate(pool)
                  if pi not in used and _ref(p) == _ref(grp[0]) and min(abs(g["t"] - p["t"]) for g in grp) <= tol)
    out: dict[int, int] = {}
    for _, gi, pi in cand:
        if gi not in out and pi not in used:
            out[gi] = pi
            used.add(pi)
    return out


def _reconcile_sweep(a: dict, b: dict, c: dict | None, tol: float) -> tuple[list[dict] | None, str, str]:
    """-> (accepted claims or None if unresolved, how, reason). Strictly one-to-one across
    the three raters: A-B pairs first (same chain, step and revision, within tol); arbiter
    claims are then reserved for agreed pairs and assigned to at most one dispute each, so
    each audible claim is accepted at most once. A claim heard by one rater and not by the
    arbiter is dropped; a claim both raters heard but labelled differently needs the arbiter."""
    arb = c if c is not None and c["review_ok"] else None
    if not (a["review_ok"] and b["review_ok"]):  # the arbiter never replaces an insufficient primary review
        return None, "", "incomplete review of the recording: relabel"
    cand = sorted((abs(x["t"] - y["t"]), i, j) for i, x in enumerate(a["claims"]) for j, y in enumerate(b["claims"])
                  if _ref(x) == _ref(y) and abs(x["t"] - y["t"]) <= tol)
    ua, ub, pairs = set(), set(), []
    for _, i, j in cand:
        if i not in ua and j not in ub:
            ua.add(i)
            ub.add(j)
            pairs.append([a["claims"][i], b["claims"][j]])
    singles = [[x] for i, x in enumerate(a["claims"]) if i not in ua] + \
              [[y] for j, y in enumerate(b["claims"]) if j not in ub]
    agreed = [p for p in pairs if p[0]["label"] == p[1]["label"]]
    split = [p for p in pairs if p[0]["label"] != p[1]["label"]]
    if (split or singles) and arb is None:
        return None, "", "claim label disagreement" if split else "claim heard by one rater only"
    acc = []
    for x, y in agreed:
        t = max(x["t"], y["t"])
        ev = [e for e in (x.get("t_evidence"), y.get("t_evidence")) if e is not None]
        z = dict(x, t=t, _how="agreement")
        if ev:
            z["t_evidence"] = min(max(ev), t)
        acc.append(z)
    if arb is not None:
        used: set[int] = set()
        _assign(agreed, arb["claims"], used, tol)  # the arbiter's marks of agreed claims
        got = _assign(split + singles, arb["claims"], used, tol)
        for gi, grp in enumerate(split + singles):
            if gi in got:
                acc.append(dict(arb["claims"][got[gi]], _how="arbitration"))
            elif gi < len(split):
                return None, "", "arbiter did not rate a claim both raters heard"
            # else: heard by one rater only and not by the arbiter -> dropped
    how = "arbitration" if split or singles else "agreement"
    return acc, how, ""


# --------------------------------------------------------------------------- merge


def _file_sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _batch_events(log: str, batch: str) -> int:
    n = 0
    with open(log, encoding="utf-8") as f:
        for line in f:
            if line.strip() and json.loads(line).get("batch") == batch:
                n += 1
    return n


def adjudication_identity(ev: dict[str, Any]) -> tuple | None:
    """What an adjudication event finalizes within its session: a chain (its verdicts, onset,
    ratings), one RQ2 repair target (chain, j, revision, step), or the session's claim sweep.
    None for events that are not adjudication output."""
    t = ev.get("type")
    adj = ev.get("source") == "adjudicated"
    if t == "claim_sweep" or (t == "completion_claim" and adj) or (t == "rating" and ev.get("kind") == "claim_sweep") \
            or (t in ("verdict", "rating") and ev.get("claim_t") is not None and (adj or t == "rating")):
        return ("sweep",)
    if t in ("verdict", "rating") and ev.get("repair_request") is not None and (adj or t == "rating"):
        return ("repair", ev["chain_id"], int(ev["repair_request"]), ev.get("revision"), ev.get("step"))
    if (t == "verdict" and adj) or t == "rating" or (t == "speech_onset" and adj):
        return ("chain", ev.get("chain_id"))
    return None


def _item_identity(info: dict[str, Any]) -> tuple:
    if info["type"] == "sweep":
        return ("sweep",)
    if info["type"] == "repair_target":
        return ("repair", info["chain_id"], int(info["repair_request"]), info["revision"], info.get("step"))
    return ("chain", info["chain_id"])


def _foreign_finalized(logs: set[str], batch: str, mine: dict[str, set[tuple]]) -> dict[str, set[tuple]]:
    """Per log: identities of this batch's items already finalized by another batch (an
    adjudicated verdict or claim sweep with a different or no ``batch``)."""
    out: dict[str, set[tuple]] = {}
    for log in logs:
        with open(log, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("batch") == batch or e.get("type") not in ("verdict", "claim_sweep"):
                    continue
                if e.get("type") == "verdict" and e.get("source") != "adjudicated":
                    continue
                ident = adjudication_identity(e)
                if ident in mine.get(log, set()):
                    out.setdefault(log, set()).add(ident)
    return out


def _rewrite(per_log: dict[str, list[dict]], logs: set[str], batch: str,
             drop: dict[str, set[tuple]] | None = None) -> dict[str, int]:
    """Atomically replace this batch's events in every log -- and, with ``drop``, every
    other batch's adjudication events for those identities (cross-batch replacement): write
    all temp files first, then os.replace them."""
    tmps = []
    for log in sorted(logs):
        kept = []
        gone = (drop or {}).get(log, set())
        with open(log, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                e = json.loads(line)
                if e.get("batch") == batch or (gone and adjudication_identity(e) in gone):
                    continue
                kept.append(line if line.endswith("\n") else line + "\n")
        new = [json.dumps(e, ensure_ascii=False) + "\n" for e in per_log.get(log, [])]
        tmp = f"{log}.tmp-{secrets.token_hex(4)}"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(kept + new)
        tmps.append((tmp, log, len(new)))
    for tmp, log, _ in tmps:
        os.replace(tmp, log)
    return {Path(log).name: n for _, log, n in tmps}


def merge(batch_dir: Path, ratings: Sequence[tuple[Path, str]], *, arbiter: tuple[Path, str] | None = None,
          key_path: Path | None = None, tol_s: float = 1.0, replace: bool = False) -> dict[str, Any]:
    """Merge two independent ratings (+ optional arbiter) into the session logs.

    Every independent rating becomes a ``rating`` event. One reconciled ``verdict`` (source
    ``adjudicated``) per item/step is written only when both raters reviewed enough and
    either agree (same label; times within ``tol_s``) or disagree and the arbiter (also with
    a sufficient review) breaks the tie. If either primary review is insufficient the item
    stays unresolved for relabelling; the arbiter never supplies a label alone. Content items also get an
    adjudicated ``speech_onset``; a resolved claim sweep yields adjudicated
    ``completion_claim`` + claim-level ``verdict`` events and a ``claim_sweep`` marker.

    Immutability: the batch's inputs are fingerprinted. Re-running with the same inputs is a
    no-op; adding an arbiter to a batch merged without one is allowed; anything else raises
    ``MergeConflictError`` unless ``replace=True``, which atomically replaces every event of
    this batch in every log. Any invalid label raises ``LabelError`` before anything is written."""
    if len(ratings) != 2:
        raise ValueError("the primary outcome needs exactly two independent ratings (plus an optional arbiter)")
    if len({a for _, a in ratings} | ({arbiter[1]} if arbiter else set())) != len(ratings) + bool(arbiter):
        raise ValueError("annotator ids must be distinct (the arbiter is a third person)")
    key_path = Path(key_path) if key_path else default_key_path(batch_dir)
    _check_key_outside(batch_dir, key_path)
    key = json.loads(key_path.read_text(encoding="utf-8"))
    batch, items = key["batch"], key["items"]
    logs = {info["log"] for info in items.values()}
    fp = {"primary": sorted([a, _file_sha(p)] for p, a in ratings),
          "arbiter": [arbiter[1], _file_sha(arbiter[0])] if arbiter else None, "tol_s": tol_s}
    state_path = key_path.parent / "merge_state.json"
    prior = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    if not replace:
        if prior is None and any(_batch_events(log, batch) for log in logs):
            raise MergeConflictError(f"logs already hold events of batch {batch!r} but no merge state: use --replace")
        if prior is not None and (prior["primary"] != fp["primary"] or prior["tol_s"] != fp["tol_s"]
                                  or (prior["arbiter"] is not None and prior["arbiter"] != fp["arbiter"])):
            raise MergeConflictError(f"batch {batch!r} was finalized with different inputs; "
                                     "use --replace to atomically replace its adjudication")
    mine: dict[str, set[tuple]] = {}
    for info in items.values():
        mine.setdefault(info["log"], set()).add(_item_identity(info))
    foreign = _foreign_finalized(logs, batch, mine)
    if foreign and not replace:
        raise MergeConflictError(
            "already finalized by another batch (each session's chain / repair target / claim sweep is "
            "finalized by exactly one batch; --replace removes the earlier batch's events for them): "
            + "; ".join(f"{Path(log).name}: {sorted(map(str, ids))}" for log, ids in foreign.items()))
    rs = [_load_ratings(p, a, items) for p, a in ratings]
    arb = _load_ratings(arbiter[0], arbiter[1], items) if arbiter else {}

    per_log: dict[str, list[dict[str, Any]]] = {}
    res: dict[str, Any] = {"agreed": 0, "arbitrated": 0, "unresolved": {}, "missing": [], "appended": {}}
    pairs_lab: tuple[list[str], list[str]] = ([], [])
    keys = sorted({f"{i}/{s}" for i, inf in items.items() for s in range(int(inf["n_steps"]))})

    diag = bool(key.get("diagnostic_batch"))

    def emit(log: str, ev: dict[str, Any]) -> None:
        if diag:  # media delivered unstripped: primary scoring ignores these events
            ev["diagnostic_batch"] = True
        per_log.setdefault(log, []).append(ev)

    for k in keys:
        iid, step_s = k.split("/")
        step, info = int(step_s), items[iid]
        log = info["log"]
        a, b, c = rs[0].get(k), rs[1].get(k), arb.get(k)
        if info["type"] == "sweep":
            for role, r in (("primary", a), ("primary", b), ("arbiter", c)):
                for x in (r or {}).get("claims", []):
                    ev = {"type": "rating", "annotator": r["annotator"], "role": role, "kind": "claim_sweep",
                          "chain_id": x["chain_id"], "label": x["label"], "claim_t": x["t"], "batch": batch,
                          "item": iid, "revision": x["revision"]}
                    if x["step"] is not None:
                        ev["step"] = x["step"]
                    if x.get("t_evidence") is not None:
                        ev["t_evidence"] = x["t_evidence"]
                    emit(log, ev)
            if a is None or b is None:
                res["missing"].append(k)
                continue
            acc, how, why = _reconcile_sweep(a, b, c, tol_s)
            if acc is None:
                res["unresolved"][k] = why
                continue
            res["arbitrated" if how == "arbitration" else "agreed"] += 1
            who = [a["annotator"], b["annotator"]] + ([c["annotator"]] if how == "arbitration" else [])
            emit(log, {"type": "claim_sweep", "source": "adjudicated", "batch": batch, "item": iid,
                       "n_claims": len(acc), "annotators": who, "reconciliation": how,
                       "t_review_end": max(x["t_review_end"] for x in (a, b) if x["t_review_end"] is not None)
                       if a["t_review_end"] is not None or b["t_review_end"] is not None else None})
            for x in acc:
                cl = {"type": "completion_claim", "source": "adjudicated", "chain_id": x["chain_id"], "t": x["t"],
                      "batch": batch, "item": iid}
                v = {"type": "verdict", "source": "adjudicated", "chain_id": x["chain_id"], "claim_t": x["t"],
                     "label": x["label"], "revision": x["revision"], "annotators": who,
                     "reconciliation": x["_how"], "batch": batch, "item": iid}
                if x["step"] is not None:
                    cl["step"] = v["step"] = x["step"]
                if x.get("t_evidence") is not None:
                    v["t_evidence"] = x["t_evidence"]
                emit(log, cl)
                emit(log, v)
            continue

        if info["type"] == "repair_target":
            base = {"chain_id": info["chain_id"], "batch": batch, "item": iid, "repair_request": info["repair_request"],
                    "revision": info["revision"]}
            if info.get("step") is not None:
                base["step"] = info["step"]
            for role, r in (("primary", a), ("primary", b), ("arbiter", c)):
                if r is not None:
                    emit(log, {"type": "rating", **base, "role": role,
                               **{x: y for x, y in r.items() if y is not None and not x.startswith("_")}})
            if a is None or b is None:
                res["missing"].append(k)
                continue
            pairs_lab[0].append(a["label"])
            pairs_lab[1].append(b["label"])
            agree = a["review_ok"] and b["review_ok"] and a["label"] == b["label"] and (
                a["label"] != "complied" or _close(a.get("t_first_compliant"), b.get("t_first_compliant"), tol_s))
            if agree:
                v, how, who = _combine(a, b), "agreement", [a["annotator"], b["annotator"]]
                res["agreed"] += 1
            elif a["review_ok"] and b["review_ok"] and c is not None and c["review_ok"]:
                v, how, who = dict(c), "arbitration", [a["annotator"], b["annotator"], c["annotator"]]
                res["arbitrated"] += 1
            else:
                short = [r["annotator"] for r in (a, b) if not r["review_ok"]]
                res["unresolved"][k] = (f"target window not fully watched: {', '.join(short)}; relabel" if short
                                        else "disagreement")
                continue
            ev = {"type": "verdict", "source": "adjudicated", **base, "label": v["label"], "annotators": who,
                  "reconciliation": how, "criteria_sha256": info["criteria_sha256"],
                  "t_review_start": v["t_review_start"], "t_review_end": v["t_review_end"]}
            for x in ("t_first_compliant", "t_evidence"):
                if v.get(x) is not None:
                    ev[x] = v[x]
            emit(log, ev)
            continue

        is_ms = info["kind"] == "multistep"
        base: dict[str, Any] = {"chain_id": info["chain_id"], "batch": batch, "item": iid}
        if is_ms:
            base["step"] = step
        for role, r in (("primary", a), ("primary", b), ("arbiter", c)):
            if r is not None:
                emit(log, {"type": "rating", **base, "role": role, "revision": info["revision"],
                           **{x: y for x, y in r.items() if y is not None and not x.startswith("_")}})
        if a is None or b is None:  # both independent ratings are required; an arbiter cannot replace one
            res["missing"].append(k)
            continue
        pairs_lab[0].append(a["label"])
        pairs_lab[1].append(b["label"])
        if a["review_ok"] and b["review_ok"] and _agree(a, b, info["kind"], tol_s, step):
            v, how, who = _combine(a, b), "agreement", [a["annotator"], b["annotator"]]
            res["agreed"] += 1
        elif a["review_ok"] and b["review_ok"] and c is not None and c["review_ok"]:
            # the arbiter only breaks a tie between two sufficient independent reviews
            v, how, who = dict(c), "arbitration", [a["annotator"], b["annotator"], c["annotator"]]
            res["arbitrated"] += 1
        else:
            short = [r["annotator"] for r in (a, b) if not r["review_ok"]]
            res["unresolved"][k] = (f"reviewed less than the deadline window: {', '.join(short)}; relabel" if short
                                    else "disagreement")
            continue
        ev = {"type": "verdict", "source": "adjudicated", **base, "label": v["label"],
              "annotators": who, "reconciliation": how, "criteria_sha256": info["criteria_sha256"],
              "revision": info["revision"], "t_review_start": v["t_review_start"],
              "t_review_end": v["t_review_end"]}
        for x in ("t_first_compliant", "t_evidence"):
            if v.get(x) is not None:
                ev[x] = v[x]
        if a.get("window_unobserved") or b.get("window_unobserved"):
            ev["window_unobserved"] = True
        if step == 0:  # every chain: the response-onset decision (content: on-topic speech)
            ev["onset_reviewed"] = True
            ev["t_onset"] = v.get("t_onset")
        emit(log, ev)
        if step == 0 and v.get("t_onset") is not None:
            emit(log, {"type": "speech_onset", "source": "adjudicated", "on_topic": True, "t": v["t_onset"],
                       "chain_id": info["chain_id"], "batch": batch, "item": iid, "annotators": who})
    if pairs_lab[0]:
        res["kappa"] = stats.cohens_kappa(*pairs_lab, categories=VERDICT_LABELS)
    res["appended"] = _rewrite(per_log, logs, batch, foreign if replace else None)
    res["replaced_other_batches"] = {Path(log).name: len(ids) for log, ids in foreign.items()} if replace else {}
    state_path.write_text(json.dumps(fp, indent=1), encoding="utf-8")
    (key_path.parent / "unresolved.json").write_text(
        json.dumps({"unresolved": res["unresolved"], "missing": res["missing"]}, indent=1), encoding="utf-8")
    return res


def _rating_arg(s: str) -> tuple[Path, str]:
    if ":" not in s:
        raise argparse.ArgumentTypeError("expected LABELS.json:ANNOTATOR")
    p, a = s.rsplit(":", 1)
    return Path(p), a


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("logs", nargs="+", type=Path)
    a.add_argument("-o", "--out", type=Path, required=True)
    a.add_argument("--key", type=Path, default=None, help="key path (default <out>.key/key.json)")
    a.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--allow-unstripped", action="store_true",
                   help="DIAGNOSTIC batch: deliver media even if metadata stripping fails; its labels never "
                        "enter primary scoring")
    b = sub.add_parser("merge")
    b.add_argument("batch_dir", type=Path)
    b.add_argument("ratings", nargs=2, type=_rating_arg, help="two LABELS.json:ANNOTATOR")
    b.add_argument("--arbiter", type=_rating_arg, default=None)
    b.add_argument("--key", type=Path, default=None)
    b.add_argument("--tol", type=float, default=1.0, help="time agreement tolerance (s)")
    b.add_argument("--replace", action="store_true",
                   help="atomically replace this batch's previously merged adjudication")
    args = p.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.logs, args.out, args.seed, suite=args.suite, key_path=args.key,
                      allow_unstripped=args.allow_unstripped))
    else:
        print(json.dumps(merge(args.batch_dir, args.ratings, arbiter=args.arbiter, key_path=args.key,
                               tol_s=args.tol, replace=args.replace), indent=1))


if __name__ == "__main__":
    main()
