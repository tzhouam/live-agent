"""Backend paths and command-line configuration, independent of frontend assets."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARD_IMAGES = ROOT / ".cache" / "board_images"
CURRICULUM = ROOT / "configs" / "curriculum"
STUDENT_SEEDS = ROOT / "configs" / "students"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live-agent API and streaming backend")
    p.add_argument("--config", default=str(ROOT / "configs" / "persona_hanfu"))
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3", "vllm_omni_h3"])
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--llm-api-key-env", default="LLM_API_KEY",
                   help="environment variable holding the responder's API key (hosted models)")
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--asr-url", default="http://127.0.0.1:8103/v1")
    p.add_argument("--asr-model", default="qwen3-asr")
    p.add_argument("--memory-db", default=str(ROOT / ".cache" / "memory.sqlite"))
    p.add_argument("--log-dir", default=str(ROOT / ".cache" / "sessions"))
    p.add_argument("--record", action="store_true", help="record each session's presented audio/video to <log-dir>/<session>.mp4")
    p.add_argument("--director-mode", default="closed_loop", choices=["closed_loop", "open_loop"])
    p.add_argument("--correction-mode", default="gradient", choices=["gradient", "repeat", "none"])
    p.add_argument("--lambda-prior", type=float, default=3.0)
    p.add_argument("--mock-judge-p", type=float, default=1.0, help="with --vlm-url mock: P(action judged done)")
    p.add_argument("--dev-allow-uncalibrated", action="store_true",
                   help="allow capabilities that were never executed (development only)")
    p.add_argument("--image-url", default="", help="board figure server (Qwen-Image via vLLM-Omni), empty: none")
    p.add_argument("--video-codec", default="auto", choices=["auto", "jpeg"],
                   help="auto: H.264 segments to pages that can decode them (WebCodecs), else JPEG frames")
    p.add_argument("--student", default="demo", help="student profile id for private sessions (the page may pick one)")
    p.add_argument("--students", default="", help="comma-separated profile ids the page may pick (default: only --student)")
    p.add_argument("--student-store", default=str(BOARD_IMAGES.parent / "students"), help="saved student profiles (personal data)")
    p.add_argument("--lesson-self-check", default="log", choices=["off", "log", "revise"],
                   help="judge every lesson section against the lesson-quality checklist: log only, or rewrite "
                        "a failing section once before it plays (sections after the first)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8201)
    # Generator options (--taomate-*, --omni-*) are parsed by the adapters (taomate_h3.py, vllm_omni_h3.py).
    args, rest = p.parse_known_args(argv)
    args.extra = rest
    return args
