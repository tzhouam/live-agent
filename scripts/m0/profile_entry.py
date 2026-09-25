"""torchrun entry that runs the *released* TaoMate-H3 stages with timing hooks.

Usage (launched by ``scripts/m0/profile_released.py``, one torchrun per stage)::

    torchrun ... scripts/m0/profile_entry.py teacher <taomate_h3.teacher worker args>
    torchrun ... scripts/m0/profile_entry.py worker  <taomate_h3.worker args>

The hooks only wrap functions of the read-only clone at runtime (no source edits).
Every hook calls ``torch.cuda.synchronize()`` at its boundaries so that wall-clock
timestamps bracket the GPU work; this adds a few host syncs per chunk (negligible
next to ~0.1-1 s forwards) but must be kept in mind when comparing with the README.

Events are appended as JSON lines to ``$M0_EVENT_LOG`` (rank 0 only, except the final
per-rank memory record). Timestamps: ``t`` = ``time.time()`` (epoch seconds).
"""

from __future__ import annotations

import atexit
import functools
import json
import os
import sys
import time
from pathlib import Path

ROLE = sys.argv[1]
ARGV = sys.argv[2:]
RANK = int(os.environ.get("RANK", "0"))
LOG = os.environ.get("M0_EVENT_LOG")
LATENT_DIR = os.environ.get("M0_LATENT_DIR")
_PHASE = {"request": -1, "phase": 0}
# Per-role/per-rank Triton JIT cache: concurrent ranks sharing ~/.triton on the CPFS home
# directory failed with "OSError: [Errno 116] Stale file handle" (first 4-GPU attempt).
os.environ["TRITON_CACHE_DIR"] = str(
    Path(__file__).resolve().parents[2] / ".cache" / "triton" / f"m0-{ROLE}-rank{RANK}"
)


def _emit(event: str, *, all_ranks: bool = False, **data) -> None:
    if LOG is None or (RANK != 0 and not all_ranks):
        return
    record = {"t": time.time(), "role": ROLE, "rank": RANK, "event": event, **data}
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _sync() -> None:
    import torch

    if torch.cuda.is_available() and torch.cuda.is_initialized():
        torch.cuda.synchronize()


def _wrap(owner, name: str, event: str, *, extra=None, after=None) -> None:
    original = getattr(owner, name)

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        info = extra(args, kwargs) if extra else {}
        _sync()
        _emit(event + ".start", **info)
        result = original(*args, **kwargs)
        _sync()
        _emit(event + ".end", **info)
        if after is not None:
            after(args, kwargs, result, info)
        return result

    setattr(owner, name, wrapper)


def _install_common() -> None:
    from taomate_h3.model import pipeline as pipeline_module

    counter = {"text": 0}

    def text_info(args, kwargs):
        counter["text"] += 1
        return {"index": counter["text"] - 1, "chars": len(kwargs.get("prompt", ""))}

    _wrap(pipeline_module.MiniMaxH3NativePipeline, "__init__", "pipeline_load")
    _wrap(pipeline_module.MiniMaxH3NativePipeline, "_encode_text", "text_encode", extra=text_info)
    _wrap(pipeline_module.MiniMaxH3NativePipeline, "_offload_text", "text_offload")


def _install_teacher() -> None:
    from taomate_h3 import teacher

    _wrap(
        teacher,
        "_generate_request",
        "teacher_request",
        extra=lambda a, k: {"request_index": int(k["request_index"])},
    )


def _install_worker() -> None:
    import torch

    from taomate_h3 import runner
    from taomate_h3.inference import acceleration, lora_checkpoint
    from taomate_h3.model import denoise, output
    from taomate_h3.model import pipeline as pipeline_module
    from taomate_h3.runtime import direct
    from taomate_h3.streaming import cache

    _wrap(direct.H3Runtime, "__init__", "runtime_init")
    _wrap(lora_checkpoint, "apply_h3_lora_checkpoint", "lora_load")
    _wrap(acceleration, "apply_direct_acceleration", "acceleration")
    _wrap(direct.H3Runtime, "precompute_text_prompts", "text_precompute")

    def request_info(args, kwargs):
        _PHASE["request"] += 1
        _PHASE["phase"] = 0
        return {"request_index": _PHASE["request"]}

    def save_latents(args, kwargs, result, info):
        if LATENT_DIR and RANK == 0:
            Path(LATENT_DIR).mkdir(parents=True, exist_ok=True)
            video, audio = result
            torch.save(
                {"video": video, "audio": audio},
                Path(LATENT_DIR) / f"request_{info['request_index']:02d}.pt",
            )

    _wrap(direct.H3Runtime, "generate_latents", "student_request", extra=request_info,
          after=save_latents)

    original_loop = denoise.minimax_h3_denoise_loop

    @functools.wraps(original_loop)
    def loop(*args, **kwargs):
        info = {"request_index": _PHASE["request"], "phase": _PHASE["phase"]}
        _sync()
        _emit("phase_denoise.start", **info)
        result = original_loop(*args, **kwargs)
        _sync()
        _emit("phase_denoise.end", **info)
        return result

    denoise.minimax_h3_denoise_loop = loop

    original_retain = cache.CleanAVKVCache.retain_sink_and_recent_commits

    @functools.wraps(original_retain)
    def retain(self, *args, **kwargs):
        result = original_retain(self, *args, **kwargs)
        _sync()
        _emit("phase_commit.end", request_index=_PHASE["request"], phase=_PHASE["phase"])
        _PHASE["phase"] += 1
        return result

    cache.CleanAVKVCache.retain_sink_and_recent_commits = retain

    _wrap(output.H3LatentDecoder, "decode_video", "video_vae_decode")
    _wrap(pipeline_module, "save_h3_video_mp4_from_rgb24_shards", "h264_encode_video")
    _wrap(pipeline_module, "save_h3_video_mp4", "h264_encode_video")
    _wrap(direct.H3Runtime, "decode_video_latents", "video_decode_and_encode")
    _wrap(direct.H3Runtime, "decode_audio_latents", "audio_vae_decode")
    _wrap(
        runner,
        "_run_media",
        "ffmpeg",
        extra=lambda a, k: {"kind": "strict_decode" if "null" in a[0] else "mux"},
    )
    _wrap(runner, "_validate_final", "final_validate")
    _wrap(runner, "_publish", "publish")


@atexit.register
def _memory_record() -> None:
    try:
        import torch

        if torch.cuda.is_available() and torch.cuda.is_initialized():
            _emit(
                "memory",
                all_ranks=True,
                device=torch.cuda.current_device(),
                peak_allocated_gib=torch.cuda.max_memory_allocated() / 2**30,
                peak_reserved_gib=torch.cuda.max_memory_reserved() / 2**30,
            )
    except Exception:  # pragma: no cover - best effort at exit
        pass


def main() -> int:
    _emit("process_start", argv=ARGV)
    _install_common()
    if ROLE == "teacher":
        _install_teacher()
        from taomate_h3.teacher import main as stage_main
    elif ROLE == "worker":
        _install_worker()
        from taomate_h3.worker import main as stage_main
    else:
        raise SystemExit(f"unknown role {ROLE}")
    code = stage_main(ARGV)
    _emit("process_end")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
