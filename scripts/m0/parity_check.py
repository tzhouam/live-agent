"""Compare a streaming-adapter run (validate_streaming.py --return-latents, prompts_10s) with a
released-path run (profile_released.py) on the same prompts/seed/resolution.

Checks: teacher milestones (states 3/6/9) and student output latents per request.
Usage: python scripts/m0/parity_check.py <stream_run_dir> <released_run_dir>
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import torch


def compare(a: torch.Tensor, b: torch.Tensor) -> dict:
    a, b = a.float(), b.float()
    diff = (a - b).abs()
    return {"shape": list(a.shape), "bitwise_equal": bool(torch.equal(a, b)),
            "max_abs": float(diff.max()), "mean_abs": float(diff.mean()),
            "rel_l2": float(diff.norm() / b.norm().clamp_min(1e-12))}


def main() -> int:
    stream, released = Path(sys.argv[1]), Path(sys.argv[2])
    data = pickle.load(open(stream / "latents_and_teacher.pkl", "rb"))
    report = {}
    for k in sorted(data):
        blob = pickle.loads(data[k]["teacher_blob"])
        ref_teacher = torch.load(released / "guidance" / f"request_{k:02d}.pt", weights_only=True)
        ref_latents = torch.load(released / "latents" / f"request_{k:02d}.pt", weights_only=True)
        report[k] = {
            "teacher_milestones": [compare(x, y) for x, y in zip(blob["milestones"], ref_teacher["milestones"])],
            "video_latents": compare(torch.from_numpy(data[k]["latents"]["video"]), ref_latents["video"]),
            "audio_latents": compare(torch.from_numpy(data[k]["latents"]["audio"]), ref_latents["audio"]),
        }
    text = json.dumps(report, indent=2)
    (stream / "parity.json").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
