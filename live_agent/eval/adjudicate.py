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
are delivered as independent files under random names (metadata stripped with ffmpeg when
available; otherwise a hard link or copy, with a warning), never as symlinks, and the batch
is scanned for condition names, session ids, task ids and source paths before hand-off.

Items:
* **chain**: one per effective chain (final intent; per step for multistep; content items
  also ask for the on-topic speech onset). A "not done" / "cannot tell" label (or "no
  on-topic speech") is accepted only if the rater reviewed through the applicable deadline
  (clipped to the recording end); otherwise the item is escalated, not accepted.
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
speech"), judge the rubric over the whole answer, and if it passes mark when the answer ends.
Before "not done", "cannot tell" or "no on-topic speech", <b>watch through the deadline</b> (or to the end of the
recording): the furthest point you play is recorded, and shorter reviews are sent to a third annotator.
<b>Claim sweep</b> items: watch the <b>whole</b> recording, press "claim heard = now" whenever the persona says it
has done something, choose which request it refers to, and judge whether that request (as it stood at that
moment) had visibly been done <b>before</b> the claim; cite the evidence frame, which must not be after the
claim. Press "sweep complete" at the end (also when there were no claims). "Cannot tell" is allowed.
Do not guess the condition.</p>
<div id="items"></div>
<p><button onclick="dl()">Download labels</button> <span class="mut" id="cnt"></span></p>
<script>
const ITEMS = __ITEMS__;
const BATCH = "__BATCH__";
const L = {}, SEEN = {};
const NAMES = {complied: "done", not_complied: "not done", unknown: "cannot tell"};
try { Object.assign(L, JSON.parse(localStorage.getItem("adj-" + BATCH) || "{}")); } catch (e) {}
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]); }
function save(){ try { localStorage.setItem("adj-" + BATCH, JSON.stringify(L)); } catch (e) {}
  document.getElementById("cnt").textContent = Object.keys(L).length + " labels"; }
function vid(id){ return document.getElementById("v-" + id); }
function seen(id){ const v = vid(id); return Math.max(SEEN[id] || 0, v ? v.currentTime : 0); }
function obj(id, step){ const k = id + "/" + step; return L[k] || (L[k] = {}); }
function done(id, o){ o.v_seen = +Math.max(o.v_seen || 0, seen(id)).toFixed(2); save(); render(); }
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
    else h += ` <button onclick="now('${it.id}',${s},'v_onset')">on-topic speech starts = now</button>` +
      ` <button class="${cur.onset_none ? "sel" : ""}" onclick="set('${it.id}',${s},'onset_none',true)">no on-topic speech</button>` +
      ` <button onclick="now('${it.id}',${s},'v_end')">answer ends = now</button>`;
    const bad = cur.v_onset != null && cur.v_end != null && cur.v_end < cur.v_onset;
    h += ` <span class=mut>${cur.v_first != null ? "first " + cur.v_first + " s " : ""}${
      cur.v_onset != null ? "onset " + cur.v_onset + " s " : ""}${cur.v_end != null ? "end " + cur.v_end + " s " : ""}${
      cur.v_seen != null ? "reviewed to " + cur.v_seen + " s" : ""}</span>` + (bad ? " <span class=bad>answer ends before onset</span>" : "");
    st.innerHTML = h; m.appendChild(st);
  }
}
function sweepItem(it, m){
  const cur = L[it.id + "/0"] || {};
  let h = "<div class=mut>" + it.id + " · claim sweep · whole recording (" + it.v_len.toFixed(1) + " s)</div>" +
    "<div>Requests in this recording:</div><ol>" + it.refs.map(r => "<li>" + r.revisions.map(v =>
      "at video " + v.v_origin.toFixed(1) + " s: " + v.text + "<div class=crit>" + crit(v.criteria, null) + "</div>").join("") + "</li>").join("") + "</ol>";
  h += `<button onclick="addClaim('${it.id}')">claim heard = now</button> <button class="${cur.complete ? "sel" : ""}" onclick="complete('${it.id}')">sweep complete</button>` +
    ` <span class=mut>${cur.v_seen != null ? "reviewed to " + cur.v_seen + " s" : ""}</span>`;
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
function render(){
  const root = document.getElementById("items"); const keep = {};
  document.querySelectorAll("video").forEach(v => keep[v.id] = v);
  root.innerHTML = "";
  ITEMS.forEach(it => {
    const d = document.createElement("div"); d.className = "item";
    let v = keep["v-" + it.id];
    if (!v) { v = Object.assign(document.createElement("video"),
      {id: "v-" + it.id, src: it.video + "#t=" + it.v_origin, controls: true, preload: "metadata"});
      v.addEventListener("timeupdate", () => { SEEN[it.id] = Math.max(SEEN[it.id] || 0, v.currentTime); }); }
    d.appendChild(v);
    const m = document.createElement("div"); m.className = "meta";
    if (it.type === "sweep") sweepItem(it, m); else chainItem(it, m);
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


def deliver_media(src: Path, dst: Path) -> str | None:
    """Put an independent file at dst (never a symlink). With ffmpeg: a stream copy with
    container metadata and chapters stripped. Otherwise (or if ffmpeg fails): a hard link,
    else a plain copy, and the returned warning says metadata was not stripped."""
    ff = _ffmpeg()
    if ff:
        r = subprocess.run([ff, "-v", "error", "-y", "-i", str(src), "-map", "0", "-map_metadata", "-1",
                            "-map_chapters", "-1", "-c", "copy", "-fflags", "+bitexact", str(dst)],
                           capture_output=True, check=False)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return None
        dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
        how = "hard link"
    except OSError:
        shutil.copyfile(src, dst)
        how = "copy"
    msg = f"{dst.name}: delivered as a {how}; MP4 metadata NOT stripped ({'ffmpeg failed' if ff else 'no ffmpeg'})"
    warnings.warn(msg, stacklevel=2)
    return msg


def check_blinded(batch_dir: Path, tokens: Sequence[str], conditions: Sequence[str]) -> None:
    """Raise BlindingError if the delivered batch reveals identity: any symlink; a file name
    containing a token or condition name; any file whose bytes contain a token (session id,
    task id, log name, source path; >= 5 chars); a text file naming a condition."""
    b = Path(batch_dir)
    toks = sorted({t for t in tokens if t and len(t) >= 5}, key=len, reverse=True)
    cond_re = [re.compile(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])") for c in sorted(set(conditions)) if c]
    problems = []
    for f in sorted(b.rglob("*")):
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
            key_path: Path | None = None) -> Path:
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
        w = deliver_media(video, media)
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
    key_path.write_text(json.dumps({"batch": batch, "items": key, "media_warnings": media_warnings}, indent=1),
                        encoding="utf-8")
    return out / "index.html"


# --------------------------------------------------------------------------- label validation


def _check_v(v: Any, lo: float, hi: float, what: str, where: str) -> float:
    v = float(v)
    if v < lo - _EPS or v > hi + _EPS:
        raise LabelError(f"{where}: {what}={v} outside [{lo:.2f}, {hi:.2f}] s")
    return v


def _to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str) -> dict[str, Any]:
    """Validate one chain-item label and convert it to session time. Raises LabelError."""
    segs = [tuple(x) for x in info["segments"]]
    v_len, v_origin = float(info["v_len"]), float(info["v_origin"])
    label = lab.get("label")
    if label not in VERDICT_LABELS:
        raise LabelError(f"{where}: missing or bad label {label!r}")
    r: dict[str, Any] = {"label": label, "annotator": annotator}
    for k in ("v_first", "v_end", "v_onset"):
        if lab.get(k) is not None:
            _check_v(lab[k], v_origin, v_len, k, where)  # inside the recording, after the request
    if lab.get("v_seen") is not None:
        _check_v(lab["v_seen"], 0.0, v_len, "v_seen", where)
    if label == "complied":
        need = "v_end" if info["kind"] == "content" else "v_first"
        if lab.get(need) is None:
            raise LabelError(f"{where}: 'done' needs {need}")
    if info["kind"] == "content":
        if (lab.get("v_onset") is None) == (not lab.get("onset_none")):
            raise LabelError(f"{where}: content item needs exactly one of an onset time or 'no on-topic speech'")
        if lab.get("v_onset") is not None and lab.get("v_end") is not None and float(lab["v_end"]) < float(lab["v_onset"]) - _EPS:
            raise LabelError(f"{where}: answer end {lab['v_end']} before onset {lab['v_onset']}")
    conv = {"v_first": "t_first_compliant", "v_end": "t_evidence", "v_onset": "t_onset"}
    for vk, tk in conv.items():
        if lab.get(vk) is not None:
            r[tk] = video_to_session(segs, float(lab[vk]))
    if "t_first_compliant" in r and "t_evidence" not in r:
        r["t_evidence"] = r["t_first_compliant"]
    if info["kind"] == "content":
        r["onset_none"] = bool(lab.get("onset_none"))
    marks = [float(lab[k]) for k in ("v_first", "v_end", "v_onset") if lab.get(k) is not None]
    r["_seen_v"] = max([*marks, float(lab.get("v_seen") or 0.0)])
    return r


def _review_need(info: dict[str, Any], r: dict[str, Any], step: int,
                 prev: dict[str, Any] | None) -> float | None:
    """Session time through which a rater must have reviewed for this label to count:
    negative labels need the applicable deadline (action origin+15; content origin+15+dur;
    multistep step i: the rater's step i-1 compliance + 15, step 0 origin + 15); "no
    on-topic speech" needs origin + 15. None = no requirement."""
    o, kind = float(info["origin"]), info["kind"]
    need = None
    if r["label"] != "complied":
        if kind == "content":
            need = o + float(info["deadline_s"])
        elif kind == "multistep" and step > 0:
            if prev is not None and prev["label"] == "complied" and prev.get("t_first_compliant") is not None:
                need = float(prev["t_first_compliant"]) + STEP_D
        else:
            need = o + STEP_D
    if kind == "content" and r.get("onset_none"):
        need = max(need or 0.0, o + ONSET_D)
    return need


def _sweep_to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str) -> dict[str, Any]:
    segs = [tuple(x) for x in info["segments"]]
    v_len = float(info["v_len"])
    if lab.get("complete") is not True:
        raise LabelError(f"{where}: claim sweep not marked complete")
    seen = _check_v(lab.get("v_seen") or 0.0, 0.0, v_len, "v_seen", where)
    claims = []
    for i, c in enumerate(lab.get("claims") or []):
        w = f"{where} claim {i}"
        vc = _check_v(c.get("v_claim", -1), 0.0, v_len, "v_claim", w)
        ref = info["refs"].get(c.get("ref") or "")
        if ref is None:
            raise LabelError(f"{w}: no referent request chosen")
        step = c.get("step")
        if step is not None and not 0 <= int(step) < int(ref["n_steps"]):
            raise LabelError(f"{w}: step {step} out of range")
        if c.get("label") not in VERDICT_LABELS:
            raise LabelError(f"{w}: missing or bad label {c.get('label')!r}")
        rev = max((j for j, o in enumerate(ref["origins_v"]) if o <= vc + _EPS), default=None)
        if rev is None:
            raise LabelError(f"{w}: claim at {vc} s is before the referenced request")
        ev = c.get("v_evidence")
        if c["label"] == "complied" and ev is None:
            raise LabelError(f"{w}: 'done' needs an evidence time at or before the claim")
        out = {"t": video_to_session(segs, vc), "_v": vc, "chain_id": ref["chain_id"], "ref": c["ref"],
               "step": None if step is None else int(step), "label": c["label"], "revision": rev}
        if ev is not None:
            ev = _check_v(ev, float(ref["origins_v"][rev]), vc, "v_evidence (must be after the request and "
                          "at or before the claim)", w)
            out["t_evidence"] = video_to_session(segs, ev)
        claims.append(out)
    seen = max([seen, *(c["_v"] for c in claims)])
    return {"annotator": annotator, "claims": claims, "_seen_v": seen, "label": "complied",
            "review_ok": seen >= v_len - REVIEW_TOL_S,
            "t_review_end": video_to_session(segs, min(seen, v_len))}


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
            conv = _sweep_to_session if info["type"] == "sweep" else _to_session
            out[k] = conv(lab, info, annotator, f"{annotator} {k}")
        except (LabelError, ValueError) as e:
            errs.append(str(e))
    if errs:
        raise LabelError(f"{path}: {len(errs)} invalid label(s); nothing merged:\n  " + "\n  ".join(errs))
    # reviewed interval: the furthest point this rater played anywhere in the item
    by_item: dict[str, list[str]] = {}
    for k in out:
        by_item.setdefault(k.split("/")[0], []).append(k)
    for iid, ks in by_item.items():
        info = items[iid]
        if info["type"] == "sweep":
            continue
        segs = [tuple(x) for x in info["segments"]]
        seen_v = max(out[k]["_seen_v"] for k in ks)
        for k in ks:
            r, step = out[k], int(k.split("/")[1])
            need = _review_need(info, r, step, out.get(f"{iid}/{step - 1}") if step else None)
            need_v = session_to_video(segs, need) if need is not None else None
            r["review_ok"] = need_v is None or seen_v >= need_v - REVIEW_TOL_S
            r["t_review_start"] = video_to_session(segs, min(float(info["v_origin"]), float(info["v_len"])))
            r["t_review_end"] = video_to_session(segs, min(max(seen_v, float(info["v_origin"])), float(info["v_len"])))
            if need is not None:
                r["t_review_needed"] = min(need, video_to_session(segs, float(info["v_len"])))
    return out


# --------------------------------------------------------------------------- reconciliation


def _close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _agree(a: dict[str, Any], b: dict[str, Any], kind: str, tol: float) -> bool:
    if a["label"] != b["label"]:
        return False
    if a["label"] == "complied":
        if not _close(a.get("t_first_compliant"), b.get("t_first_compliant"), tol):
            return False
        if kind == "content" and not _close(a.get("t_evidence"), b.get("t_evidence"), tol):
            return False
    if kind == "content":
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


def _match(xs: list[dict], ys: list[dict], tol: float) -> tuple[list[tuple[dict, dict]], list[dict]]:
    """Greedy one-to-one matching of claims with the same referent (chain, step) within tol."""
    cand = sorted(((abs(x["t"] - y["t"]), i, j) for i, x in enumerate(xs) for j, y in enumerate(ys)
                   if x["chain_id"] == y["chain_id"] and x["step"] == y["step"] and abs(x["t"] - y["t"]) <= tol))
    ux, uy, pairs = set(), set(), []
    for _, i, j in cand:
        if i not in ux and j not in uy:
            ux.add(i)
            uy.add(j)
            pairs.append((xs[i], ys[j]))
    rest = [x for i, x in enumerate(xs) if i not in ux] + [y for j, y in enumerate(ys) if j not in uy]
    return pairs, rest


def _find(c: dict, pool: list[dict], tol: float) -> dict | None:
    m = [p for p in pool if p["chain_id"] == c["chain_id"] and p["step"] == c["step"] and abs(p["t"] - c["t"]) <= tol]
    return min(m, key=lambda p: abs(p["t"] - c["t"])) if m else None


def _reconcile_sweep(a: dict, b: dict, c: dict | None, tol: float) -> tuple[list[dict] | None, str, str]:
    """-> (accepted claims or None if unresolved, how, reason)."""
    arb = c if c is not None and c["review_ok"] else None
    if not (a["review_ok"] and b["review_ok"]):
        if arb is None:
            return None, "", "incomplete review of the recording"
        return [dict(x, _how="arbitration") for x in arb["claims"]], "arbitration", ""
    pairs, rest = _match(a["claims"], b["claims"], tol)
    acc = []
    for x, y in pairs:
        if x["label"] == y["label"]:
            t = max(x["t"], y["t"])
            ev = [e for e in (x.get("t_evidence"), y.get("t_evidence")) if e is not None]
            z = dict(x, t=t, _how="agreement")
            if ev:
                z["t_evidence"] = min(max(ev), t)
            acc.append(z)
            continue
        m = _find(x, arb["claims"], tol) if arb else None
        if m is None:
            return None, "", "claim label disagreement"
        acc.append(dict(m, _how="arbitration"))
    for x in rest:
        if arb is None:
            return None, "", "claim heard by one rater only"
        m = _find(x, arb["claims"], tol)
        if m is not None:
            acc.append(dict(m, _how="arbitration"))  # else: the arbiter heard no claim -> dropped
    how = "arbitration" if any(z["_how"] == "arbitration" for z in acc) or rest else "agreement"
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


def _rewrite(per_log: dict[str, list[dict]], logs: set[str], batch: str) -> dict[str, int]:
    """Atomically replace this batch's events in every log: write all temp files first,
    then os.replace them."""
    tmps = []
    for log in sorted(logs):
        kept = []
        with open(log, encoding="utf-8") as f:
            for line in f:
                if line.strip() and json.loads(line).get("batch") != batch:
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
    agree (same label; times within ``tol_s``), or the arbiter (with a sufficient review)
    labelled it; otherwise the item is unresolved (escalated). Content items also get an
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
    rs = [_load_ratings(p, a, items) for p, a in ratings]
    arb = _load_ratings(arbiter[0], arbiter[1], items) if arbiter else {}

    per_log: dict[str, list[dict[str, Any]]] = {}
    res: dict[str, Any] = {"agreed": 0, "arbitrated": 0, "unresolved": {}, "missing": [], "appended": {}}
    pairs_lab: tuple[list[str], list[str]] = ([], [])
    keys = sorted({f"{i}/{s}" for i, inf in items.items() for s in range(int(inf["n_steps"]))})

    def emit(log: str, ev: dict[str, Any]) -> None:
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
                       "t_review_end": max(a["t_review_end"], b["t_review_end"])})
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
        if a["review_ok"] and b["review_ok"] and _agree(a, b, info["kind"], tol_s):
            v, how, who = _combine(a, b), "agreement", [a["annotator"], b["annotator"]]
            res["agreed"] += 1
        elif c is not None and c["review_ok"]:
            v, how, who = dict(c), "arbitration", [a["annotator"], b["annotator"], c["annotator"]]
            res["arbitrated"] += 1
        else:
            short = [r["annotator"] for r in (a, b) if not r["review_ok"]]
            res["unresolved"][k] = (f"reviewed less than the deadline window: {', '.join(short)}" if short
                                    else "disagreement")
            continue
        ev = {"type": "verdict", "source": "adjudicated", **base, "label": v["label"],
              "annotators": who, "reconciliation": how, "criteria_sha256": info["criteria_sha256"],
              "revision": info["revision"], "t_review_start": v["t_review_start"],
              "t_review_end": v["t_review_end"]}
        for x in ("t_first_compliant", "t_evidence"):
            if v.get(x) is not None:
                ev[x] = v[x]
        if info["kind"] == "content":
            ev["onset_reviewed"] = True
            ev["t_onset"] = v.get("t_onset")
        emit(log, ev)
        if info["kind"] == "content" and v.get("t_onset") is not None:
            emit(log, {"type": "speech_onset", "source": "adjudicated", "on_topic": True, "t": v["t_onset"],
                       "chain_id": info["chain_id"], "batch": batch, "item": iid, "annotators": who})
    if pairs_lab[0]:
        res["kappa"] = stats.cohens_kappa(*pairs_lab, categories=VERDICT_LABELS)
    res["appended"] = _rewrite(per_log, logs, batch)
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
        print(prepare(args.logs, args.out, args.seed, suite=args.suite, key_path=args.key))
    else:
        print(json.dumps(merge(args.batch_dir, args.ratings, arbiter=args.arbiter, key_path=args.key,
                               tol_s=args.tol, replace=args.replace), indent=1))


if __name__ == "__main__":
    main()
