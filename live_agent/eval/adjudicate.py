"""Blinded human adjudication of the primary outcome (proposal §14; SCHEMA.md `verdict`, source
`adjudicated`).

    # 1. build a blinded labelling page from session logs + recorded MP4s (runner --record)
    python -m live_agent.eval.adjudicate prepare .cache/m1/*.jsonl -o .cache/adj/batch1 [--seed 0]
    # 2. open .cache/adj/batch1/index.html in a browser, label, press "Download labels"
    # 3. merge the labels back into the logs as adjudicated verdicts
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labels.json --annotator A1

Blinding: items are shuffled across sessions and conditions, carry random ids, and show only the
user's instruction(s) and the video; the item -> session key stays in ``key.json``.

Time mapping: the recording holds the presented chunks back to back (stalls are not recorded), so
video time v maps to session time through the cumulative chunk durations of the session's
``chunk_presented`` events (``video_to_session``).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import secrets
import shutil
from pathlib import Path
from typing import Any

from live_agent.eval.schema import load_session


def presented_segments(events: list[dict]) -> list[tuple[float, float, float]]:
    """[(video_start, session_start, duration)] for presented chunks in presentation order."""
    chunks = sorted((e for e in events if e["type"] == "chunk_presented"), key=lambda e: e["t_start"])
    out, v = [], 0.0
    for e in chunks:
        d = e["t_end"] - e["t_start"]
        out.append((v, e["t_start"], d))
        v += d
    return out


def video_to_session(segments: list[tuple[float, float, float]], v: float) -> float:
    for v0, s0, d in segments:
        if v < v0 + d:
            return s0 + max(0.0, v - v0)
    if not segments:
        return v
    v0, s0, d = segments[-1]
    return s0 + (v - v0)


def session_to_video(segments: list[tuple[float, float, float]], t: float) -> float:
    for v0, s0, d in segments:
        if t < s0 + d:
            return v0 + max(0.0, t - s0)
    if not segments:
        return t
    v0, s0, d = segments[-1]
    return v0 + d


def chains_for_adjudication(events: list[dict]) -> list[dict[str, Any]]:
    """Final intent of every effective (not finally withdrawn) chain, with its clock origin."""
    utt = {e["uid"]: e for e in events if e["type"] == "utterance"}
    chains: dict[str, dict[str, Any]] = {}
    for e in events:
        if e["type"] != "chain_annotation":
            continue
        c = chains.setdefault(e["chain_id"], {"chain_id": e["chain_id"], "texts": [], "withdrawn": False})
        u = utt.get(e["uid"], {})
        c["texts"].append(u.get("text", ""))
        if e["action"] == "withdrawal":
            c["withdrawn"] = True
            continue
        c["withdrawn"] = False
        c["origin"] = u.get("t_end", 0.0)
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


PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>Adjudication</title>
<style>
:root{{--bg:#fff;--fg:#111;--mut:#666;--line:#ddd;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--line:#333;--acc:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
.item{{border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0;display:flex;gap:16px;flex-wrap:wrap}}
video{{width:300px;max-width:100%;background:#000}} .meta{{flex:1;min-width:260px}}
.mut{{color:var(--mut);font-size:13px}} button{{margin:2px}} .step{{margin:8px 0;padding:6px;border-top:1px dashed var(--line)}}
.sel{{outline:2px solid var(--acc)}}
</style>
<h1>Blinded adjudication · {n} items</h1>
<p class="mut">For each item: the user's request(s) are shown; the video starts at the request. Decide whether the
persona <b>visibly</b> did the <b>final</b> requested thing. When it did, pause at the <b>first frame that clearly
shows it</b> and press "first compliant = now". For content items, mark the time the answer ends. "Cannot tell" is
allowed. Do not guess the condition.</p>
<div id="items"></div>
<p><button onclick="dl()">Download labels</button> <span class="mut" id="cnt"></span></p>
<script>
const ITEMS = {items};
const L = {{}};
try {{ Object.assign(L, JSON.parse(localStorage.getItem("adj-{batch}") || "{{}}")); }} catch (e) {{}}
function save(){{ try {{ localStorage.setItem("adj-{batch}", JSON.stringify(L)); }} catch (e) {{}}
  document.getElementById("cnt").textContent = Object.keys(L).length + " step labels"; }}
function set(id, step, key, val){{ const k = id + "/" + step; L[k] = Object.assign(L[k] || {{}}, {{[key]: val}}); save(); render(); }}
function now(id, step, key){{ set(id, step, key, +document.getElementById("v-" + id).currentTime.toFixed(2)); }}
function render(){{
  const root = document.getElementById("items"); const keep = {{}};
  document.querySelectorAll("video").forEach(v => keep[v.id] = v);
  root.innerHTML = "";
  ITEMS.forEach(it => {{
    const d = document.createElement("div"); d.className = "item";
    const v = keep["v-" + it.id] || Object.assign(document.createElement("video"),
      {{id: "v-" + it.id, src: it.video + "#t=" + it.v_origin, controls: true, preload: "metadata"}});
    d.appendChild(v);
    const m = document.createElement("div"); m.className = "meta";
    m.innerHTML = "<div class=mut>" + it.id + " · " + it.kind + (it.content_type ? " / " + it.content_type : "") +
      " · request at video " + it.v_origin.toFixed(1) + " s</div>" +
      it.texts.map((t, i) => "<div>" + (i ? "then: " : "user: ") + t + "</div>").join("");
    for (let s = 0; s < it.n_steps; s++) {{
      const k = it.id + "/" + s, cur = L[k] || {{}};
      const st = document.createElement("div"); st.className = "step";
      const lab = it.n_steps > 1 ? "step " + (s + 1) + ": " : "";
      st.innerHTML = lab + ["complied", "not_complied", "unknown"].map(x =>
        `<button class="${{cur.label === x ? "sel" : ""}}" onclick="set('${{it.id}}',${{s}},'label','${{x}}')">${{
          {{complied: "done", not_complied: "not done", unknown: "cannot tell"}}[x]}}</button>`).join("") +
        ` <button onclick="now('${{it.id}}',${{s}},'v_first')">first compliant = now</button>` +
        (it.kind === "content" ? ` <button onclick="now('${{it.id}}',${{s}},'v_end')">answer ends = now</button>` : "") +
        ` <span class=mut>${{cur.v_first != null ? "first " + cur.v_first + " s " : ""}}${{cur.v_end != null ? "end " + cur.v_end + " s" : ""}}</span>`;
      m.appendChild(st);
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


def prepare(logs: list[Path], out: Path, seed: int = 0) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    items, key = [], {}
    for log in logs:
        s = load_session(log)
        video = log.with_suffix(".mp4")
        if not video.exists():
            print(f"skip {log.name}: no recording {video.name}")
            continue
        segs = presented_segments(s.events)
        media = out / "media" / f"{secrets.token_hex(4)}.mp4"  # random name: the file name would unblind
        media.parent.mkdir(exist_ok=True)
        try:
            media.symlink_to(video.resolve())
        except OSError:
            shutil.copyfile(video, media)
        for c in chains_for_adjudication(s.events):
            iid = secrets.token_hex(3)
            items.append({"id": iid, "video": os.path.relpath(media, out), "kind": c["kind"],
                          "content_type": c.get("content_type"), "texts": [html.escape(t) for t in c["texts"]],
                          "n_steps": c["n_steps"], "v_origin": round(session_to_video(segs, c["origin"]), 2)})
            key[iid] = {"log": str(log.resolve()), "chain_id": c["chain_id"], "segments": segs, "kind": c["kind"]}
    random.Random(seed).shuffle(items)
    batch = out.name
    (out / "index.html").write_text(PAGE.format(n=len(items), items=json.dumps(items, ensure_ascii=False),
                                                batch=batch), encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    return out / "index.html"


def merge(batch_dir: Path, labels_path: Path, annotator: str) -> dict[str, int]:
    key = json.loads((batch_dir / "key.json").read_text(encoding="utf-8"))
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    per_log: dict[str, list[dict]] = {}
    for k, lab in labels.items():
        iid, step = k.split("/")
        if iid not in key or "label" not in lab:
            continue
        info = key[iid]
        segs = [tuple(x) for x in info["segments"]]
        ev: dict[str, Any] = {"type": "verdict", "source": "adjudicated", "label": lab["label"],
                              "chain_id": info["chain_id"], "annotator": annotator}
        if int(step) or info["kind"] == "multistep":
            ev["step"] = int(step)
        if lab.get("v_first") is not None:
            ev["t_first_compliant"] = video_to_session(segs, float(lab["v_first"]))
        if lab.get("v_end") is not None:
            ev["t_evidence"] = video_to_session(segs, float(lab["v_end"]))
        elif "t_first_compliant" in ev:
            ev["t_evidence"] = ev["t_first_compliant"]
        per_log.setdefault(info["log"], []).append(ev)
    counts = {}
    for log, evs in per_log.items():
        with open(log, "a", encoding="utf-8") as f:
            for ev in evs:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        counts[Path(log).name] = len(evs)
    return counts


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("logs", nargs="+", type=Path)
    a.add_argument("-o", "--out", type=Path, required=True)
    a.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("merge")
    b.add_argument("batch_dir", type=Path)
    b.add_argument("labels", type=Path)
    b.add_argument("--annotator", required=True)
    args = p.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.logs, args.out, args.seed))
    else:
        print(merge(args.batch_dir, args.labels, args.annotator))


if __name__ == "__main__":
    main()
