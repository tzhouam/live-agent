"""Re-judge saved E1 action clips offline with two judge configurations (no generation needed).

    python3 scripts/e1_rejudge.py --e1 .cache/e1 --out .cache/e1/rejudge.jsonl

v1 = K=4 state question (the pilot's judge); v2 = contrast mode (K=8 incl. first/last frame,
"did the action happen in this clip"). Neither is ground truth: agreement with human labels on
the saved clips decides which judge E1/E2 may use (proposal §14.2, 20% human sample).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_agent.capability import CapabilityManifest  # noqa: E402
from live_agent.llm import OpenAICompatLLM  # noqa: E402
from live_agent.qc.judge import VLMJudge  # noqa: E402
from live_agent.types import CheckQuestion, Chunk, now  # noqa: E402


async def main(args) -> None:
    manifest = CapabilityManifest.load(Path(args.config) / "capabilities.json")
    by_intent = {c.intent: c for c in manifest.caps.values()}
    vlm = OpenAICompatLLM(args.vlm_url, args.vlm_model)
    judges = {"v1": VLMJudge(vlm, k=4), "v2": VLMJudge(vlm, k=8, contrast=True)}
    trials = [json.loads(x) for x in open(Path(args.e1) / "trials.jsonl", encoding="utf-8")]
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in trials:
            if not r.get("clip"):
                continue
            video = np.load(r["clip"])["video"]
            ch = Chunk(0, 0, len(video), 24.0, video=video, audio=None, sample_rate=32000, t_ready=now())
            cap = by_intent[r["intent"]]
            out = {"intent": r["intent"], "trial": r["trial"], "clip": r["clip"]}
            for name, j in judges.items():
                text = cap.check_question if name == "v1" else f"{cap.check_question}（{cap.phrase}）"
                v = await j.judge(CheckQuestion("q", text), [ch], 0, 0.0)
                out[name] = v.label.value
                out[name + "_conf"] = v.confidence
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
            fh.flush()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--e1", default=".cache/e1")
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--out", default=".cache/e1/rejudge.jsonl")
    asyncio.run(main(p.parse_args()))
