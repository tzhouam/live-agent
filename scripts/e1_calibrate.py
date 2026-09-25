"""E1 capability calibration (proposal §14.2).

For each capability: N trials. Each trial = a fresh generator session with one idle
request, then one request carrying the action (compiled exactly as the director would),
then one idle request (to observe late onset). The VLM judge answers the capability's
check question on the action request's frames (and the following request as a fallback).
Results: success rate with Wilson CI, onset request offset, per-trial records (JSONL),
and an updated manifest (status executed/calibrated). A 20% stratified sample of the
saved clips must be human-labelled before the manifest is used for E2 (judge validity).

Usage (TaoMate-H3 on GPUs; always through canhazgpu):
    gpu run --gpus 4 --timeout 4h --note "live-agent E1 calibration" -- \
        python3 scripts/e1_calibrate.py --generator taomate_h3 --trials 30 --out .cache/e1
    python3 scripts/e1_calibrate.py --generator mock --trials 5 --out .cache/e1_mock   # dry run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_agent.capability import CapabilityManifest, Status  # noqa: E402
from live_agent.eval.stats import wilson  # noqa: E402
from live_agent.ledger import StateLedger  # noqa: E402
from live_agent.prompt.h3_compiler import compile_prompt  # noqa: E402
from live_agent.types import BlockScript, CheckQuestion, now  # noqa: E402


async def collect(gen, n_requests: int):
    """Collect all chunks of the next n_requests requests."""
    out: dict[int, list] = {}
    agen = gen.chunks()
    while sum(1 for v in out.values() if len(v) == 4) < n_requests:
        ch = await agen.__anext__()
        out.setdefault(ch.request_index, []).append(ch)
    return out


async def run(args) -> None:
    cfg = Path(args.config)
    manifest = CapabilityManifest.load(cfg / "capabilities.json")
    ledger = StateLedger.from_config(cfg / "canon.json")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator
        from live_agent.qc.judge import MockJudge

        gen = MockGenerator(speed=20.0)
        judge = MockJudge(p_default=0.7)
    else:
        from live_agent.generator.taomate_h3 import TaoMateH3Generator
        from live_agent.llm import OpenAICompatLLM
        from live_agent.qc.judge import VLMJudge

        gen = TaoMateH3Generator.from_args(args)
        judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model), k=args.k)
    await gen.start()
    caps = [c for c in manifest.caps.values() if not args.only or c.intent in args.only]
    trials_path = out / "trials.jsonl"
    fh = open(trials_path, "a", encoding="utf-8")
    for cap in caps:
        results = []
        for trial in range(args.trials):
            await gen.reset()
            base = gen.next_request_index
            idle = BlockScript(base, 0, ledger.canon, action="she reads the open book quietly", transcript="")
            act = BlockScript(base + 1, 0, ledger.canon, action=cap.phrase, transcript="")
            tail = BlockScript(base + 2, 0, ledger.canon, action="she reads the open book quietly", transcript="")
            t0 = now()
            for s, first in ((idle, True), (act, False), (tail, False)):
                await gen.submit(s.request_index, compile_prompt(s, first_request=first))
            chunks = await collect(gen, 3)
            q = CheckQuestion("q", cap.check_question)
            v_act = await judge.judge(q, chunks[base + 1], base + 1, now())
            v_tail = await judge.judge(q, chunks[base + 2], base + 2, now())
            onset = 0 if v_act.label.value == "complied" else (1 if v_tail.label.value == "complied" else None)
            rec = {"cap_id": cap.cap_id, "intent": cap.intent, "trial": trial, "onset_offset": onset,
                   "label_action_request": v_act.label.value, "label_next_request": v_tail.label.value,
                   "conf": [v_act.confidence, v_tail.confidence], "wall_s": now() - t0}
            if args.save_clips and args.generator != "mock":
                clip = out / "clips" / f"{cap.intent}-t{trial}.npz"
                clip.parent.mkdir(exist_ok=True)
                np.savez_compressed(clip, video=np.concatenate([c.video for c in chunks[base + 1]]))
                rec["clip"] = str(clip)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(rec)
        k = sum(1 for r in results if r["onset_offset"] == 0)
        lo, hi = wilson(k, len(results))
        manifest.update_from_calibration(cap.cap_id, successes=k, trials=len(results), ci=(lo, hi),
                                         tvc_median_s=None)
        print(f"{cap.intent:14s} {k}/{len(results)} = {k/len(results):.2f} [{lo:.2f}, {hi:.2f}]", flush=True)
    fh.close()
    manifest.save(out / "capabilities.calibrated.json")
    await gen.close()
    print(f"wrote {out/'capabilities.calibrated.json'} (review + human-label a 20% sample before use)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--trials", type=int, default=30)
    p.add_argument("--only", nargs="*", default=None)
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--save-clips", action="store_true")
    p.add_argument("--out", default=".cache/e1")
    args, rest = p.parse_known_args()
    args.extra = rest
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
