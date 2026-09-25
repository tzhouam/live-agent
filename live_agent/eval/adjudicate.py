"""Blinded, dual human adjudication of the primary outcome with third-person arbitration
(proposal §7.2 / §14, D-014; SCHEMA.md ``rating`` and ``verdict`` with source ``adjudicated``).

    # 1. build a blinded labelling page from session logs + recorded MP4s (runner --record).
    #    The key (item -> session/condition) is written OUTSIDE the batch directory.
    python -m live_agent.eval.adjudicate prepare .cache/m1/*.jsonl -o .cache/adj/batch1 \
        [--key .cache/adj/batch1.key/key.json] [--suite eval/tasks/e2_committed.jsonl] [--seed 0]
    # 2. give ONLY .cache/adj/batch1/ to annotators; each opens index.html, labels, and
    #    presses "Download labels"
    # 3. merge two independent ratings; agreements become reconciled verdicts, disagreements
    #    are listed in <key dir>/unresolved.json for a third annotator (arbiter)
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labelsA.json:R1 labelsB.json:R2
    # 4. after arbitration (same page; arbiter labels the listed item ids)
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labelsA.json:R1 labelsB.json:R2 \
        --arbiter labelsC.json:R3

Blinding: items are shuffled across sessions and conditions, carry random ids, and show only
the user's instruction(s), the preregistered success criteria (checks / content rubric /
per-step criteria, frozen from the task suite) and the video.

Items: one per effective chain (final intent; per step for multistep; content items also ask
for the on-topic speech onset), plus one per completion claim that the chain's final-intent
verdict cannot settle (claims on withdrawn chains, or heard before the final revision). Such a
claim is judged against what was requested when it was heard.

Every label records the reviewed interval (request start to the furthest point the
annotator played). Label times must lie inside the recording and inside the final-intent
interval (after the request); out-of-range or incomplete labels reject the whole file.

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
import secrets
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from live_agent.eval import stats
from live_agent.eval.schema import VERDICT_LABELS, load_session
from live_agent.eval.scoring import build_chains, claim_needs_direct_adjudication
from live_agent.eval.tasks import load_suite

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "eval" / "tasks" / "e2_committed.jsonl"
_EPS = 1e-3  # video-time tolerance (s)


class LabelError(ValueError):
    """Labels out of range, incomplete, or not matching the batch: nothing was merged."""


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
    for v0, s0, d in segments:
        if t < s0 + d:
            return v0 + max(0.0, t - s0)
    if not segments:
        return t
    v0, s0, d = segments[-1]
    return v0 + d


# --------------------------------------------------------------------------- items


def chains_for_adjudication(events: list[dict]) -> list[dict[str, Any]]:
    """Final intent of every effective (not finally withdrawn) chain, with its clock origin
    and revision count (number of ``revision`` annotations)."""
    utt = {e["uid"]: e for e in events if e["type"] == "utterance"}
    anns = sorted((e for e in events if e["type"] == "chain_annotation"),
                  key=lambda e: utt.get(e["uid"], {}).get("t_end", 0.0))
    chains: dict[str, dict[str, Any]] = {}
    for e in anns:
        c = chains.setdefault(e["chain_id"], {"chain_id": e["chain_id"], "texts": [], "withdrawn": False,
                                              "revision": -1, "ann": {}})
        u = utt.get(e["uid"], {})
        c["texts"].append(u.get("text", ""))
        if e["action"] == "withdrawal":
            c["withdrawn"] = True
            continue
        c["withdrawn"] = False
        c["origin"] = u.get("t_end", 0.0)
        c["revision"] += 1
        c["ann"] = e
        for k in ("kind", "intent", "content_type", "steps", "label"):
            if k in e:
                c[k] = e[k]
    out = []
    for c in chains.values():
        if c["withdrawn"] or "origin" not in c:
            continue
        steps = c.get("steps")
        c["n_steps"] = (len(steps) if isinstance(steps, list) else int(steps)) if c.get("kind") == "multistep" and steps else 1
        c["kind"] = "action" if c.get("kind") == "correction" else c.get("kind", "action")
        out.append(c)
    return out


def _criteria_from_intent(it: dict[str, Any]) -> dict[str, Any]:
    kind = "action" if it.get("kind") == "correction" else it.get("kind", "action")
    cr: dict[str, Any] = {"kind": kind, "intent": it.get("intent", "")}
    if kind == "content":
        from live_agent.eval.scoring import CONTENT_DURATION_S

        cr["content_type"] = it.get("content_type")
        cr["duration_s"] = it.get("prereg_duration_s", CONTENT_DURATION_S.get(it.get("content_type") or "qa"))
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
:root{{--bg:#fff;--fg:#111;--mut:#666;--line:#ddd;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--line:#333;--acc:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
.item{{border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0;display:flex;gap:16px;flex-wrap:wrap}}
video{{width:300px;max-width:100%;background:#000}} .meta{{flex:1;min-width:260px}}
.mut{{color:var(--mut);font-size:13px}} button{{margin:2px}} .step{{margin:8px 0;padding:6px;border-top:1px dashed var(--line)}}
.crit{{margin:6px 0;padding:6px 8px;border-left:3px solid var(--acc);font-size:14px}} .crit ul{{margin:2px 0 2px 18px;padding:0}}
.sel{{outline:2px solid var(--acc)}}
</style>
<h1>Blinded adjudication · {n} items</h1>
<p class="mut">For each item the user's request(s) and the <b>preregistered criteria</b> are shown; the video starts at
the request. Judge only against the criteria of the <b>final</b> request. "Done" needs every listed check.
<b>Action</b>: pause at the <b>first frame that clearly shows it</b> and press "first compliant = now".
<b>Multistep</b>: label each step; for step i mark the first frame showing it <b>after</b> step i−1 was done (if it was
only done before, mark that time). <b>Content</b>: mark when on-topic speech starts (or "no on-topic speech"), and
judge the rubric over the whole answer; if it passes, mark when the answer ends. <b>Claim</b> items: decide whether,
at the moment the persona claimed completion, what was requested at that time had visibly been done.
"Cannot tell" is allowed. Watch until you are sure: the furthest point you play is recorded as the reviewed
interval. Do not guess the condition.</p>
<div id="items"></div>
<p><button onclick="dl()">Download labels</button> <span class="mut" id="cnt"></span></p>
<script>
const ITEMS = {items};
const L = {{}}, SEEN = {{}};
try {{ Object.assign(L, JSON.parse(localStorage.getItem("adj-{batch}") || "{{}}")); }} catch (e) {{}}
function esc(s){{ return String(s).replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]); }}
function save(){{ try {{ localStorage.setItem("adj-{batch}", JSON.stringify(L)); }} catch (e) {{}}
  document.getElementById("cnt").textContent = Object.keys(L).length + " step labels"; }}
function seen(id){{ const v = document.getElementById("v-" + id); return Math.max(SEEN[id] || 0, v ? v.currentTime : 0); }}
function set(id, step, key, val){{ const k = id + "/" + step; const o = Object.assign(L[k] || {{}}, {{[key]: val}});
  if (key === "onset_none" && val) delete o.v_onset; if (key === "v_onset") delete o.onset_none;
  o.v_seen = +Math.max(o.v_seen || 0, seen(id)).toFixed(2); L[k] = o; save(); render(); }}
function now(id, step, key){{ set(id, step, key, +document.getElementById("v-" + id).currentTime.toFixed(2)); }}
function list(xs){{ return "<ul>" + xs.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>"; }}
function rubric(r){{ return "<ul>" + Object.entries(r).map(([k, v]) => "<li>" + esc(k) + ": " +
  esc(Array.isArray(v) ? v.join("; ") : v) + "</li>").join("") + "</ul>"; }}
function crit(c, s){{
  if (c.kind === "multistep") {{ const st = c.steps[s]; return "<b>step " + (s + 1) + ": " + esc(st.intent) + "</b>" + list(st.checks); }}
  if (c.kind === "content") return "<b>" + esc(c.intent) + "</b> (" + esc(c.content_type) + ", answer within " +
    c.duration_s + " s after onset)" + rubric(c.rubric);
  return "<b>" + esc(c.intent) + "</b>" + list(c.checks);
}}
function render(){{
  const root = document.getElementById("items"); const keep = {{}};
  document.querySelectorAll("video").forEach(v => keep[v.id] = v);
  root.innerHTML = "";
  ITEMS.forEach(it => {{
    const d = document.createElement("div"); d.className = "item";
    let v = keep["v-" + it.id];
    if (!v) {{ v = Object.assign(document.createElement("video"),
      {{id: "v-" + it.id, src: it.video + "#t=" + it.v_origin, controls: true, preload: "metadata"}});
      v.addEventListener("timeupdate", () => {{ SEEN[it.id] = Math.max(SEEN[it.id] || 0, v.currentTime); }}); }}
    d.appendChild(v);
    const m = document.createElement("div"); m.className = "meta";
    const head = it.type === "claim" ? "claim · persona said it was done at video " + it.v_claim.toFixed(1) + " s"
      : it.kind + (it.content_type ? " / " + it.content_type : "");
    m.innerHTML = "<div class=mut>" + it.id + " · " + head + " · request at video " + it.v_origin.toFixed(1) + " s</div>" +
      it.texts.map((t, i) => "<div>" + (i ? "then: " : "user: ") + t + "</div>").join("");
    for (let s = 0; s < it.n_steps; s++) {{
      const k = it.id + "/" + s, cur = L[k] || {{}};
      const st = document.createElement("div"); st.className = "step";
      const cs = it.type === "claim" && it.claim_step != null ? it.claim_step : s;
      let h = "<div class=crit>" + crit(it.criteria, cs) + "</div>";
      h += ["complied", "not_complied", "unknown"].map(x =>
        `<button class="${{cur.label === x ? "sel" : ""}}" onclick="set('${{it.id}}',${{s}},'label','${{x}}')">${{
          {{complied: "done", not_complied: "not done", unknown: "cannot tell"}}[x]}}</button>`).join("");
      if (it.type === "chain" && it.kind !== "content")
        h += ` <button onclick="now('${{it.id}}',${{s}},'v_first')">first compliant = now</button>`;
      if (it.type === "chain" && it.kind === "content")
        h += ` <button onclick="now('${{it.id}}',${{s}},'v_onset')">on-topic speech starts = now</button>` +
             ` <button class="${{cur.onset_none ? "sel" : ""}}" onclick="set('${{it.id}}',${{s}},'onset_none',true)">no on-topic speech</button>` +
             ` <button onclick="now('${{it.id}}',${{s}},'v_end')">answer ends = now</button>`;
      h += ` <span class=mut>${{cur.v_first != null ? "first " + cur.v_first + " s " : ""}}${{
        cur.v_onset != null ? "onset " + cur.v_onset + " s " : ""}}${{cur.v_end != null ? "end " + cur.v_end + " s " : ""}}${{
        cur.v_seen != null ? "reviewed to " + cur.v_seen + " s" : ""}}</span>`;
      st.innerHTML = h; m.appendChild(st);
    }}
    d.appendChild(m); root.appendChild(d);
  }});
}}
function dl(){{ const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(L, null, 1)], {{type: "application/json"}}));
  a.download = "labels-{batch}.json"; a.click(); }}
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


def prepare(logs: list[Path], out: Path, seed: int = 0, *, suite: Path | None = DEFAULT_SUITE,
            key_path: Path | None = None) -> Path:
    key_path = Path(key_path) if key_path else default_key_path(out)
    _check_key_outside(out, key_path)
    tasks = {t.task_id: t for t in load_suite(suite)} if suite else {}
    out.mkdir(parents=True, exist_ok=True)
    items, key = [], {}

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
        segs = presented_segments(s.events)
        v_len = recorded_length(segs)
        media = out / "media" / f"{secrets.token_hex(4)}.mp4"  # random name: the file name would unblind
        media.parent.mkdir(exist_ok=True)
        try:
            media.symlink_to(video.resolve())
        except OSError:
            shutil.copyfile(video, media)
        rel = os.path.relpath(media, out)
        for c in chains_for_adjudication(s.events):
            cr = _criteria(tasks, s.task_id, c.get("label", c["chain_id"]), c["revision"], c["ann"])
            iid = new_id()
            v_origin = round(session_to_video(segs, c["origin"]), 2)
            items.append({"id": iid, "type": "chain", "video": rel, "kind": c["kind"],
                          "content_type": c.get("content_type"), "texts": [html.escape(t) for t in c["texts"]],
                          "n_steps": c["n_steps"], "v_origin": v_origin, "criteria": cr})
            key[iid] = {"type": "chain", "log": str(log.resolve()), "chain_id": c["chain_id"], "segments": segs,
                        "kind": c["kind"], "n_steps": c["n_steps"], "v_origin": v_origin, "v_len": v_len,
                        "revision": c["revision"], "criteria_sha256": _sha(cr)}
        # claims the final-intent verdict cannot settle
        chains = build_chains(s)
        utt = {e["uid"]: e for e in s.of_type("utterance")}
        anns = s.of_type("chain_annotation")
        for cl in s.of_type("completion_claim"):
            ch = chains.get(cl["chain_id"])
            t = float(cl["t"])
            if ch is None or not claim_needs_direct_adjudication(ch, t):
                continue
            r = ch.revision_at(t)
            said = [a for a in anns if a["chain_id"] == ch.chain_id and float(utt[a["uid"]]["t_end"]) <= t]
            rev_ann = [a for a in said if a["action"] in ("new", "revision")]
            cr = _criteria(tasks, s.task_id, ch.label, r, rev_ann[-1] if rev_ann else None)
            iid = new_id()
            v_origin = round(session_to_video(segs, ch.origins[r]), 2)
            items.append({"id": iid, "type": "claim", "video": rel, "kind": cr["kind"],
                          "content_type": cr.get("content_type"),
                          "texts": [html.escape(utt[a["uid"]]["text"]) for a in said],
                          "n_steps": 1, "v_origin": v_origin, "v_claim": round(session_to_video(segs, t), 2),
                          "claim_step": cl.get("step"), "criteria": cr})
            key[iid] = {"type": "claim", "log": str(log.resolve()), "chain_id": ch.chain_id, "segments": segs,
                        "kind": cr["kind"], "n_steps": 1, "v_origin": v_origin, "v_len": v_len,
                        "revision": r, "claim_t": t, "claim_id": cl.get("claim_id"),
                        "claim_step": cl.get("step"), "criteria_sha256": _sha(cr)}
    random.Random(seed).shuffle(items)
    batch = out.name
    (out / "index.html").write_text(PAGE.format(n=len(items), items=json.dumps(items, ensure_ascii=False),
                                                batch=batch), encoding="utf-8")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps({"batch": batch, "items": key}, indent=1), encoding="utf-8")
    return out / "index.html"


# --------------------------------------------------------------------------- merge


def _to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str) -> dict[str, Any]:
    """Validate one label and convert it to session time. Raises LabelError."""
    segs = [tuple(x) for x in info["segments"]]
    v_len, v_origin = float(info["v_len"]), float(info["v_origin"])
    label = lab.get("label")
    if label not in VERDICT_LABELS:
        raise LabelError(f"{where}: missing or bad label {label!r}")
    r: dict[str, Any] = {"label": label, "annotator": annotator}
    for k in ("v_first", "v_end", "v_onset", "v_seen"):
        v = lab.get(k)
        if v is None:
            continue
        v = float(v)
        if v < -_EPS or v > v_len + _EPS:
            raise LabelError(f"{where}: {k}={v} outside the recording [0, {v_len:.2f}] s")
        if k != "v_seen" and v < v_origin - _EPS:
            raise LabelError(f"{where}: {k}={v} before the request (final intent starts at video {v_origin:.2f} s)")
    is_chain = info["type"] == "chain"
    if is_chain and label == "complied":
        need = "v_end" if info["kind"] == "content" else "v_first"
        if lab.get(need) is None:
            raise LabelError(f"{where}: 'done' needs {need}")
    if is_chain and info["kind"] == "content" and (lab.get("v_onset") is None) == (not lab.get("onset_none")):
        raise LabelError(f"{where}: content item needs exactly one of an onset time or 'no on-topic speech'")
    conv = {"v_first": "t_first_compliant", "v_end": "t_evidence", "v_onset": "t_onset"}
    for vk, tk in conv.items():
        if lab.get(vk) is not None:
            r[tk] = video_to_session(segs, float(lab[vk]))
    if "t_first_compliant" in r and "t_evidence" not in r:
        r["t_evidence"] = r["t_first_compliant"]
    if is_chain and info["kind"] == "content":
        r["onset_none"] = bool(lab.get("onset_none"))
    marks = [float(lab[k]) for k in ("v_first", "v_end", "v_onset") if lab.get(k) is not None]
    seen = max([v_origin, *marks, *([float(lab["v_seen"])] if lab.get("v_seen") is not None else [])])
    r["t_review_start"] = video_to_session(segs, min(v_origin, v_len))
    r["t_review_end"] = video_to_session(segs, min(seen, v_len))
    return r


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
            out[k] = _to_session(lab, info, annotator, f"{annotator} {k}")
        except (LabelError, ValueError) as e:
            errs.append(str(e))
    if errs:
        raise LabelError(f"{path}: {len(errs)} invalid label(s); nothing merged:\n  " + "\n  ".join(errs))
    return out


def _close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _agree(a: dict[str, Any], b: dict[str, Any], kind: str, is_chain: bool, tol: float) -> bool:
    if a["label"] != b["label"]:
        return False
    if is_chain and a["label"] == "complied":
        if not _close(a.get("t_first_compliant"), b.get("t_first_compliant"), tol):
            return False
        if kind == "content" and not _close(a.get("t_evidence"), b.get("t_evidence"), tol):
            return False
    if is_chain and kind == "content":
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


def _sig(ev: dict[str, Any]) -> tuple:
    return (ev["type"], ev.get("batch"), ev.get("item"), ev.get("step"), ev.get("annotator"))


def merge(batch_dir: Path, ratings: Sequence[tuple[Path, str]], *, arbiter: tuple[Path, str] | None = None,
          key_path: Path | None = None, tol_s: float = 1.0) -> dict[str, Any]:
    """Merge two independent ratings (+ optional arbiter) into the session logs.

    Appends every independent rating as a ``rating`` event, and one reconciled ``verdict``
    (source ``adjudicated``) per item/step only when the two raters agree (same label; times
    within ``tol_s``) or the arbiter labelled it. Content items also get an adjudicated
    ``speech_onset``. Unresolved and missing items are returned and written to
    ``unresolved.json`` next to the key. Idempotent per batch (re-running after arbitration
    appends only what is new). Any invalid label rejects the merge (``LabelError``)."""
    if len(ratings) != 2:
        raise ValueError("the primary outcome needs exactly two independent ratings (plus an optional arbiter)")
    if len({a for _, a in ratings} | ({arbiter[1]} if arbiter else set())) != len(ratings) + bool(arbiter):
        raise ValueError("annotator ids must be distinct (the arbiter is a third person)")
    key_path = Path(key_path) if key_path else default_key_path(batch_dir)
    _check_key_outside(batch_dir, key_path)
    key = json.loads(key_path.read_text(encoding="utf-8"))
    batch, items = key["batch"], key["items"]
    rs = [_load_ratings(p, a, items) for p, a in ratings]
    arb = _load_ratings(arbiter[0], arbiter[1], items) if arbiter else {}

    per_log: dict[str, list[dict[str, Any]]] = {}
    res: dict[str, Any] = {"agreed": 0, "arbitrated": 0, "unresolved": [], "missing": [], "appended": {}}
    pairs_lab: tuple[list[str], list[str]] = ([], [])
    keys = sorted(set(rs[0]) | set(rs[1]) | set(arb)
                  | {f"{i}/{s}" for i, inf in items.items() for s in range(int(inf["n_steps"]))})
    for k in keys:
        iid, step_s = k.split("/")
        step, info = int(step_s), items[iid]
        is_chain = info["type"] == "chain"
        base: dict[str, Any] = {"chain_id": info["chain_id"], "batch": batch, "item": iid, "step": step}
        a, b = rs[0].get(k), rs[1].get(k)
        for role, r in (("primary", a), ("primary", b), ("arbiter", arb.get(k))):
            if r is not None:
                ev = {"type": "rating", **base, "role": role, "revision": info["revision"],
                      **{x: y for x, y in r.items() if y is not None}}
                if not is_chain:
                    ev["claim_t"] = info["claim_t"]
                per_log.setdefault(info["log"], []).append(ev)
        if a is None or b is None:  # both independent ratings are required; an arbiter cannot replace one
            res["missing"].append(k)
            continue
        pairs_lab[0].append(a["label"])
        pairs_lab[1].append(b["label"])
        if _agree(a, b, info["kind"], is_chain, tol_s):
            v, how, who = _combine(a, b), "agreement", [a["annotator"], b["annotator"]]
            res["agreed"] += 1
        elif k in arb:
            v, how, who = dict(arb[k]), "arbitration", [a["annotator"], b["annotator"], arb[k]["annotator"]]
            res["arbitrated"] += 1
        else:
            res["unresolved"].append(k)
            continue
        ev = {"type": "verdict", "source": "adjudicated", **base, "label": v["label"],
              "annotators": who, "reconciliation": how, "criteria_sha256": info["criteria_sha256"],
              "t_review_start": v["t_review_start"], "t_review_end": v["t_review_end"]}
        for x in ("t_first_compliant", "t_evidence"):
            if v.get(x) is not None:
                ev[x] = v[x]
        if is_chain:
            ev["revision"] = info["revision"]
            if info["kind"] != "multistep":
                del ev["step"]
            if info["kind"] == "content":
                ev["onset_reviewed"] = True
                ev["t_onset"] = v.get("t_onset")
        else:
            ev["claim_t"] = info["claim_t"]
            del ev["step"]
            if info.get("claim_id") is not None:
                ev["claim_id"] = info["claim_id"]
        per_log.setdefault(info["log"], []).append(ev)
        if is_chain and info["kind"] == "content" and v.get("t_onset") is not None:
            per_log[info["log"]].append({"type": "speech_onset", "source": "adjudicated", "on_topic": True,
                                         "t": v["t_onset"], "chain_id": info["chain_id"], "batch": batch,
                                         "item": iid, "annotators": who})
    if pairs_lab[0]:
        res["kappa"] = stats.cohens_kappa(*pairs_lab, categories=VERDICT_LABELS)
    for log, evs in per_log.items():
        existing = set()
        with open(log, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    if e.get("batch") == batch:
                        existing.add(_sig(e))
        new = [e for e in evs if _sig(e) not in existing]
        with open(log, "a", encoding="utf-8") as f:
            for ev in new:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        res["appended"][Path(log).name] = len(new)
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
    args = p.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.logs, args.out, args.seed, suite=args.suite, key_path=args.key))
    else:
        print(json.dumps(merge(args.batch_dir, args.ratings, arbiter=args.arbiter, key_path=args.key,
                               tol_s=args.tol), indent=1))


if __name__ == "__main__":
    main()
