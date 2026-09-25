"""M0/M1 validation of the streaming TaoMate-H3 adapter (T1 + T2 + T3).

Runs ``TaoMateH3Generator`` inside a canhazgpu reservation, submits prompts one at a time
(mid-session), receives chunks incrementally and records the single timeline
(lock -> teacher -> student -> first chunk -> done) per request.

Submission policy (default ``--policy mixed``):
* requests 0..P-1 are *pipelined*: request k+1 is locked when request k's first chunk
  arrives (just-in-time locking while k plays), which exposes queueing and throughput;
* the last ``--idle`` requests are locked only after the previous request finished, which
  measures the unloaded lock->first-chunk lead Lambda_idle = teacher + student first chunk.

Outputs (under ``--out``, default .cache/m0/stream/<tag>-<time>/): results.json, the
concatenated session MP4 (native 24 fps video + 32 kHz stereo audio) and worker logs.

Example::

    gpu run --gpu-ids 0,1,2,3,4,5 --timeout 1h --note "live-agent M0: streaming validation" -- \
      .venvs/taomate-h3/bin/python scripts/m0/validate_streaming.py --tag s6_ded
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from live_agent.generator.taomate_h3 import TaoMateH3Generator  # noqa: E402
from live_agent.types import now  # noqa: E402

FFMPEG = "/usr/bin/ffmpeg"  # has libx264 on this host (/usr/local/bin/ffmpeg does not)
REQUEST_SECONDS = 119 / 24


def _git_head(path: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True,
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def write_mp4(path: Path, video: np.ndarray, audio: np.ndarray, fps: int = 24) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        pcm = Path(tmp) / "a.f32le"
        pcm.write_bytes(np.ascontiguousarray(audio, dtype=np.float32).tobytes())
        h, w = video.shape[1:3]
        cmd = [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", f"{w}x{h}",
               "-r", str(fps), "-i", "pipe:0", "-f", "f32le", "-ar", "32000", "-ac", "2", "-i", str(pcm),
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(path)]
        subprocess.run(cmd, input=np.ascontiguousarray(video).tobytes(), check=True)


def snr_db(reference: np.ndarray, test: np.ndarray) -> float:
    n = min(len(reference), len(test))
    ref, tst = reference[:n].astype(np.float64), test[:n].astype(np.float64)
    noise = np.sum((ref - tst) ** 2)
    return float("inf") if noise == 0 else float(10 * np.log10(np.sum(ref ** 2) / noise))


async def run(args: argparse.Namespace) -> dict:
    prompts = json.loads(args.prompts.read_text())["prompts"]
    if args.requests:
        prompts = prompts[: args.requests]
    out = args.out
    gen = TaoMateH3Generator(
        student_devices=args.student_devices,
        teacher_devices=args.teacher_devices,
        colocate_teacher=args.colocate,
        lookahead=not args.sequential,
        return_latents=args.return_latents,
        warmup_prompt=None if args.no_warmup else prompts[0],
        log_dir=out / "logs",
        seed=args.seed,
    )
    t_start = now()
    await gen.start()
    t_ready = now()
    chunks = []
    first_chunk_seen: dict[int, asyncio.Event] = {k: asyncio.Event() for k in range(len(prompts))}
    done_seen: dict[int, asyncio.Event] = {k: asyncio.Event() for k in range(len(prompts))}

    async def consume():
        async for chunk in gen.chunks():
            chunks.append(chunk)
            if chunk.chunk_index == 0:
                first_chunk_seen[chunk.request_index].set()
            if chunk.chunk_index == 3:
                done_seen[chunk.request_index].set()
            if len(chunks) == 4 * len(prompts):
                return

    consumer = asyncio.create_task(consume())
    idle_from = len(prompts) - args.idle
    lock_policy = []
    for k, prompt in enumerate(prompts):
        if k > 0:
            if k >= idle_from:
                await done_seen[k - 1].wait()
                while gen.timings[k - 1].t_done is None:
                    await asyncio.sleep(0.01)
                await asyncio.sleep(args.idle_gap)
                lock_policy.append("idle")
            else:
                await first_chunk_seen[k - 1].wait()
                lock_policy.append("pipelined")
        else:
            lock_policy.append("first")
        await gen.submit(k, prompt)
    await asyncio.wait_for(consumer, timeout=args.timeout)
    while any(t.t_done is None for t in gen.timings):
        await asyncio.sleep(0.05)
    full_audio = await gen.full_audio()
    flushed = await gen.flush()
    worker_info = {role: {k: v for k, v in info.get("ready", {}).items() if k != "type"}
                   for role, info in gen.worker_info.items()}
    await gen.close()

    # ---------------------------------------------------------------- per-request timeline
    rows = []
    for timing, policy in zip(gen.timings, lock_policy):
        k = timing.request_index
        extras = gen.request_extras.get(k, {})
        req_chunks = [c for c in chunks if c.request_index == k]
        rows.append({
            "request_index": k,
            "lock_policy": policy,
            "t_lock_mono": timing.t_lock,
            "t_done_mono": timing.t_done,
            "lock_to_teacher_start_s": timing.t_teacher_start - timing.t_lock,
            "teacher_s": timing.teacher_s,
            "teacher_text_s": extras.get("teacher_text_s"),
            "teacher_done_to_student_start_s": timing.t_student_start - timing.t_teacher_done,
            "student_start_to_first_chunk_s": timing.t_first_chunk - timing.t_student_start,
            "lock_to_first_chunk_s": timing.lead_s,
            "student_request_s": timing.t_done - timing.t_student_start,
            "lock_to_done_s": timing.t_done - timing.t_lock,
            "chunk_frames": [c.n_frames for c in req_chunks],
            "chunk_ready_since_student_start_s": [round(c.t_ready - timing.t_student_start, 3) for c in req_chunks],
            "chunk_denoise_s": [round(c.meta["t_denoised"] - c.meta["t_phase_start"], 3) for c in req_chunks],
            "chunk_decode_s": [round(c.meta["t_decoded"] - c.meta["t_denoised"], 3) for c in req_chunks],
            "chunk_transport_s": [round(c.t_ready - c.meta["t_decoded"], 3) for c in req_chunks],
            "audio_teacher_exact_match": extras.get("audio_teacher_exact_match"),
            "student_peak_allocated_gib": extras.get("student_peak_allocated_gib"),
            "teacher_peak_allocated_gib": extras.get("teacher_peak_allocated_gib"),
        })

    # ---------------------------------------------------------------- playback simulation
    # Playback of chunk j starts at t0 + B + frame_start/24. The smallest startup buffer B
    # with no stall is max_j(t_ready_j - t0 - frame_start_j/24), t0 = first chunk arrival.
    t0 = chunks[0].t_ready
    slack = [c.t_ready - t0 - c.meta["frame_start"] / 24 for c in chunks]
    pipelined = [r for r in rows if r["lock_policy"] in ("first", "pipelined")]

    # ---------------------------------------------------------------- media + audio parity
    video = np.concatenate([c.video for c in chunks], axis=0)
    audio = np.concatenate([c.audio for c in chunks], axis=0)
    mp4 = out / "session.mp4"
    write_mp4(mp4, video, audio)
    reference = full_audio["audio"]
    streamed_end = len(audio)
    audio_parity = {
        "streamed_samples": int(streamed_end),
        "reference_samples": int(len(reference)),
        "snr_db_vs_one_shot_decode": snr_db(reference[:streamed_end], audio),
        "max_abs_diff": float(np.max(np.abs(reference[:streamed_end] - audio))),
    }

    summary = {
        "requests": len(rows),
        "start_to_ready_s": t_ready - t_start,
        "warmup_s": gen.warmup_s,
        "mean_student_request_s_pipelined": statistics.mean(r["student_request_s"] for r in pipelined[1:] or pipelined),
        "mean_teacher_s": statistics.mean(r["teacher_s"] for r in rows),
        "request_media_s": REQUEST_SECONDS,
        "mean_lock_to_first_chunk_s_pipelined": statistics.mean(r["lock_to_first_chunk_s"] for r in pipelined[1:] or pipelined),
        "lock_to_first_chunk_s_idle": [r["lock_to_first_chunk_s"] for r in rows if r["lock_policy"] == "idle"],
        "min_startup_buffer_no_stall_s": max(slack),
        "all_audio_teacher_exact_match": all(r["audio_teacher_exact_match"] for r in rows),
        "frames": int(video.shape[0]),
        "flushed_frames": None if flushed.get("video") is None else int(len(flushed["video"])),
    }
    summary["real_time"] = summary["mean_student_request_s_pipelined"] < REQUEST_SECONDS
    result = {
        "meta": {
            "tag": args.tag, "date": time.strftime("%Y-%m-%d %H:%M:%S %z"),
            "live_agent_head": _git_head(REPO), "taomate_h3_head": _git_head(REPO / "external" / "TaoMate-H3"),
            "student_devices": gen.student_devices, "teacher_devices": gen.teacher_devices,
            "lookahead": not args.sequential, "resolution": f"{gen.info.width}x{gen.info.height}",
            "prompts": str(args.prompts), "argv": sys.argv,
        },
        "worker_ready": worker_info,
        "warmup": {"s": gen.warmup_s},
        "summary": summary,
        "audio_parity": audio_parity,
        "requests": rows,
        "playback_slack_s": [round(s, 3) for s in slack],
        "mp4": str(mp4),
    }
    if args.return_latents:
        import pickle

        with open(out / "latents_and_teacher.pkl", "wb") as handle:
            pickle.dump({k: {"latents": e.get("latents"), "teacher_blob": e.get("teacher_blob")}
                         for k, e in gen.request_extras.items()}, handle)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--prompts", type=Path, default=REPO / "scripts" / "m0" / "prompts_session_40s.json")
    parser.add_argument("--requests", type=int, default=0)
    parser.add_argument("--idle", type=int, default=2, help="last N requests locked after the previous finished")
    parser.add_argument("--idle-gap", type=float, default=0.5)
    parser.add_argument("--student-devices")
    parser.add_argument("--teacher-devices")
    parser.add_argument("--colocate", action="store_true")
    parser.add_argument("--sequential", action="store_true", help="disable teacher lookahead")
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--return-latents", action="store_true")
    parser.add_argument("--seed", type=int, default=8301)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    args.out = args.out or REPO / ".cache" / "m0" / "stream" / f"{args.tag}-{time.strftime('%Y%m%dT%H%M%S')}"
    args.out.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(run(args))
    (args.out / "results.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result["summary"], indent=2))
    print(json.dumps(result["audio_parity"], indent=2))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
