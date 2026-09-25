"""Human validation of the E1 judge (proposal §14.2: a stratified 20% sample is human-labelled).

    # 1. sample clips (stratified by capability), encode MP4s, write a blinded labelling page
    python3 scripts/e1_validate.py prepare --e1 .cache/e1 --frac 0.2 -o .cache/e1_val
    # 2. open .cache/e1_val/index.html, label every clip, "Download labels" -> labels.json
    # 3. judge-vs-human agreement per judge configuration (needs scripts/e1_rejudge.py output)
    python3 scripts/e1_validate.py agree --e1 .cache/e1 --val .cache/e1_val labels.json [labels2.json]

The page shows only the requested action and the clip; judge labels and trial ids stay in
``<out>.key.json`` (outside the page folder). A capability may become ``calibrated`` only after
the judge configuration used for it agrees with the human labels (reported here: accuracy,
Cohen's kappa, false-positive and false-negative counts).
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>E1 Validation</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#fff;--fg:#111;--mut:#666;--line:#ddd;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--line:#333;--acc:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
.item{{border:1px solid var(--line);border-radius:8px;padding:12px;margin:14px 0;display:flex;gap:16px;flex-wrap:wrap}}
video{{width:260px;max-width:100%;background:#000}} .sel{{outline:2px solid var(--acc)}} .mut{{color:var(--mut)}}
</style>
<h1>E1 clip validation · {n} clips</h1>
<p class="mut">Each clip is one 5-second request in which the persona was asked to do the action shown. Answer whether
the action <b>visibly happens in this clip</b> (a state that was already true from the start does not count).</p>
<div id="items"></div><p><button onclick="dl()">Download labels</button> <span id="cnt" class="mut"></span></p>
<script>
const ITEMS = {items}; const L = {{}};
try {{ Object.assign(L, JSON.parse(localStorage.getItem("e1val") || "{{}}")); }} catch (e) {{}}
function save(){{ try {{ localStorage.setItem("e1val", JSON.stringify(L)); }} catch (e) {{}}
  document.getElementById("cnt").textContent = Object.keys(L).length + " / " + ITEMS.length + " labelled"; }}
function set(id, v){{ L[id] = v; save(); render(); }}
function render(){{ const r = document.getElementById("items"); r.innerHTML = "";
  ITEMS.forEach(it => {{ const d = document.createElement("div"); d.className = "item";
    d.innerHTML = `<video src="${{it.video}}" controls preload="metadata"></video><div><div class=mut>${{it.id}}</div>
      <div>动作：${{it.action}}</div><div>${{["complied","not_complied","unknown"].map(x =>
      `<button class="${{L[it.id]===x?"sel":""}}" onclick="set('${{it.id}}','${{x}}')">${{{{complied:"做了",not_complied:"没做",unknown:"看不出"}}[x]}}</button>`).join("")}}</div></div>`;
    r.appendChild(d); }}); }}
function dl(){{ const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(L, null, 1)], {{type: "application/json"}}));
  a.download = "labels.json"; a.click(); }}
render(); save();
</script></html>
"""


def prepare(e1: Path, out: Path, frac: float, seed: int, ffmpeg: str) -> Path:
    trials = [json.loads(x) for x in open(e1 / "trials.jsonl", encoding="utf-8") if '"clip"' in x]
    caps = json.loads(Path("configs/persona_hanfu/capabilities.json").read_text(encoding="utf-8"))
    question = {c["intent"]: c["check_question"] for c in caps["capabilities"]}
    by_cap = defaultdict(list)
    for r in trials:
        by_cap[r["intent"]].append(r)
    rng = random.Random(seed)
    sample = []
    for cap, rs in sorted(by_cap.items()):
        n = max(1, round(frac * len(rs)))
        sample += rng.sample(rs, min(n, len(rs)))
    rng.shuffle(sample)
    (out / "media").mkdir(parents=True, exist_ok=True)
    items, key = [], {}
    for r in sample:
        iid = secrets.token_hex(3)
        mp4 = out / "media" / f"{secrets.token_hex(4)}.mp4"
        v = np.load(r["clip"])["video"]
        _, h, w, _ = v.shape
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                        "-r", "24", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)],
                       input=np.ascontiguousarray(v).tobytes(), check=True)
        items.append({"id": iid, "video": str(mp4.relative_to(out)), "action": question[r["intent"]]})
        key[iid] = {"intent": r["intent"], "trial": r["trial"], "clip": r["clip"]}
    (out / "index.html").write_text(PAGE.format(n=len(items), items=json.dumps(items, ensure_ascii=False)),
                                    encoding="utf-8")
    Path(str(out) + ".key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    return out / "index.html"


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    labels = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(x) / n) * (b.count(x) / n) for x in labels)
    return None if pe == 1 else (po - pe) / (1 - pe)


def agree(e1: Path, val: Path, label_files: list[Path]) -> dict:
    key = json.loads(Path(str(val) + ".key.json").read_text(encoding="utf-8"))
    judged = {(r["intent"], r["trial"]): r for r in map(json.loads, open(e1 / "rejudge.jsonl", encoding="utf-8"))}
    raters = [json.loads(p.read_text(encoding="utf-8")) for p in label_files]
    report: dict = {"n_items": len(key), "raters": len(raters)}
    if len(raters) == 2:
        common = [i for i in key if i in raters[0] and i in raters[1]]
        report["inter_rater_kappa"] = kappa([raters[0][i] for i in common], [raters[1][i] for i in common])
    # human reference: items where all raters agree on a definite label
    ref = {i: raters[0][i] for i in key
           if all(i in r for r in raters) and len({r[i] for r in raters}) == 1 and raters[0][i] != "unknown"}
    report["reference_items"] = len(ref)
    for judge in ("v1", "v2"):
        pairs = [(ref[i], judged[(key[i]["intent"], key[i]["trial"])][judge]) for i in ref
                 if (key[i]["intent"], key[i]["trial"]) in judged]
        h, j = [p[0] for p in pairs], [p[1] for p in pairs]
        report[judge] = {"n": len(pairs), "accuracy": (sum(x == y for x, y in pairs) / len(pairs)) if pairs else None,
                         "kappa": kappa(h, j),
                         "false_positive": sum(x == "not_complied" and y == "complied" for x, y in pairs),
                         "false_negative": sum(x == "complied" and y != "complied" for x, y in pairs)}
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--e1", type=Path, default=Path(".cache/e1"))
    a.add_argument("--frac", type=float, default=0.2)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--ffmpeg", default="/usr/bin/ffmpeg")
    a.add_argument("-o", "--out", type=Path, required=True)
    b = sub.add_parser("agree")
    b.add_argument("--e1", type=Path, default=Path(".cache/e1"))
    b.add_argument("--val", type=Path, required=True)
    b.add_argument("labels", nargs="+", type=Path)
    args = p.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.e1, args.out, args.frac, args.seed, args.ffmpeg))
    else:
        print(json.dumps(agree(args.e1, args.val, args.labels), indent=1))


if __name__ == "__main__":
    main()
