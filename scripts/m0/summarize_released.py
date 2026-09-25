"""Summarize M0 released-path profiling runs (events.jsonl, result.json, nvidia_smi.csv).

Usage: python scripts/m0/summarize_released.py .cache/m0/runs/r4_480p_rep*  [--json out.json]
Prints one Markdown table per run and a mean/min/max table across runs. All values are
*measured locally* (wall-clock seconds between synchronized hook timestamps).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def _pairs(events: list[dict], name: str, role: str) -> list[tuple[dict, float]]:
    """Match NAME.start/NAME.end events (rank 0) in order; return (start_event, seconds)."""

    starts = [e for e in events if e["event"] == f"{name}.start" and e["role"] == role and e["rank"] == 0]
    ends = [e for e in events if e["event"] == f"{name}.end" and e["role"] == role and e["rank"] == 0]
    return [(s, e["t"] - s["t"]) for s, e in zip(starts, ends)]


def summarize(run: Path) -> dict:
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    meta = json.loads((run / "meta.json").read_text())
    out: dict = {"run": run.name, "devices": meta.get("devices"), "date": meta.get("date")}
    t = lambda role, ev: next(e["t"] for e in events if e["role"] == role and e["event"] == ev and e["rank"] == 0)  # noqa: E731

    # teacher stage
    out["teacher_process_s"] = meta["stages"]["teacher_process"]["end"] - meta["stages"]["teacher_process"]["start"]
    out["teacher_model_load_s"] = _pairs(events, "pipeline_load", "teacher")[0][1]
    out["teacher_text_encode_s"] = [round(s, 3) for _, s in _pairs(events, "text_encode", "teacher")]
    out["teacher_text_offload_s"] = _pairs(events, "text_offload", "teacher")[0][1]
    out["teacher_request_s"] = [round(s, 3) for _, s in _pairs(events, "teacher_request", "teacher")]

    # worker stage
    out["worker_process_s"] = meta["stages"]["worker_process"]["end"] - meta["stages"]["worker_process"]["start"]
    out["student_runtime_init_s"] = _pairs(events, "runtime_init", "worker")[0][1]
    out["student_model_load_s"] = _pairs(events, "pipeline_load", "worker")[0][1]
    out["student_lora_load_s"] = _pairs(events, "lora_load", "worker")[0][1]
    out["student_text_encode_s"] = [round(s, 3) for _, s in _pairs(events, "text_encode", "worker")]
    out["student_text_offload_s"] = _pairs(events, "text_offload", "worker")[0][1]
    out["student_request_s"] = [round(s, 3) for _, s in _pairs(events, "student_request", "worker")]

    phases: dict[int, list] = defaultdict(list)
    denoise = [e for e in events if e["role"] == "worker" and e["event"].startswith("phase_")]
    starts = [e for e in denoise if e["event"] == "phase_denoise.start"]
    for start in starts:
        k, p = start["request_index"], start["phase"]
        end = next(e for e in denoise if e["event"] == "phase_denoise.end" and e["request_index"] == k and e["phase"] == p)
        commit = next(e for e in denoise if e["event"] == "phase_commit.end" and e["request_index"] == k and e["phase"] == p)
        phases[k].append({
            "phase": p,
            "denoise_s": round(end["t"] - start["t"], 3),
            "commit_s": round(commit["t"] - end["t"], 3),
            "chunk_s": round(commit["t"] - start["t"], 3),
        })
    out["student_chunks"] = {k: v for k, v in sorted(phases.items())}
    request_start = {s["request_index"]: s["t"] for s, _ in _pairs(events, "student_request", "worker")}
    out["first_final_chunk_latent_s"] = round(
        next(e["t"] for e in denoise if e["event"] == "phase_denoise.end" and e["request_index"] == 0 and e["phase"] == 0)
        - request_start[0], 3)

    pub = dict((name, _pairs(events, name, "worker")) for name in (
        "publish", "video_decode_and_encode", "video_vae_decode", "h264_encode_video",
        "audio_vae_decode", "final_validate"))
    out["publish_s"] = pub["publish"][0][1]
    out["video_vae_decode_s"] = pub["video_vae_decode"][0][1]
    out["video_vae_load_and_setup_s"] = pub["video_vae_decode"][0][0]["t"] - pub["video_decode_and_encode"][0][0]["t"]
    out["h264_encode_video_s"] = pub["h264_encode_video"][0][1]
    out["audio_vae_decode_s"] = pub["audio_vae_decode"][0][1]
    muxes = [s for e, s in _pairs(events, "ffmpeg", "worker") if e.get("kind") == "mux"]
    out["mux_s"] = muxes[0] if muxes else None
    out["final_validate_s"] = pub["final_validate"][0][1]

    result = json.loads((run / "output" / "result.json").read_text())
    perf = result["performance"]
    out["dit_cuda_s"] = perf["dit"]["cuda_seconds"]
    out["dit_noisy_calls"] = perf["dit"]["noisy_calls"]
    out["dit_clean_calls"] = perf["dit"]["clean_kv_calls"]
    out["dit_peak_allocated_gib"] = perf["dit"]["peak_allocated_bytes"] / 2**30
    out["worker_peak_allocated_gib"] = perf["peak_memory_allocated_bytes"] / 2**30
    out["worker_peak_reserved_gib"] = perf["peak_memory_reserved_bytes"] / 2**30
    out["video_vae_active_cuda_s"] = perf.get("video_vae_active_cuda_seconds")
    out["teacher_peak_allocated_gib"] = max(
        e["peak_allocated_gib"] for e in events if e["role"] == "teacher" and e["event"] == "memory")

    smi = (run / "nvidia_smi.csv")
    if smi.exists():
        peak: dict[str, float] = defaultdict(float)
        for line in smi.read_text().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[2].replace(".", "").isdigit():
                peak[parts[1]] = max(peak[parts[1]], float(parts[2]) / 1024)
        out["nvidia_smi_peak_used_gib"] = {k: round(v, 1) for k, v in sorted(peak.items())}
    out["_t0_worker_request0"] = t("worker", "student_request.start")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rows = [summarize(run) for run in args.runs if (run / "output" / "result.json").exists()]
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2) + "\n")
    scalar = [k for k, v in rows[0].items() if isinstance(v, (int, float)) and not k.startswith("_")]
    print("| metric | " + " | ".join(r["run"] for r in rows) + " | mean |")
    print("|---|" + "---|" * (len(rows) + 1))
    for key in scalar:
        values = [r[key] for r in rows if r.get(key) is not None]
        print(f"| {key} | " + " | ".join(f"{r[key]:.3f}" if r.get(key) is not None else "-" for r in rows)
              + f" | {statistics.mean(values):.3f} |")
    for key in ("teacher_text_encode_s", "teacher_request_s", "student_text_encode_s", "student_request_s",
                "nvidia_smi_peak_used_gib"):
        print(f"| {key} | " + " | ".join(str(r.get(key)) for r in rows) + " | |")
    print()
    for r in rows:
        print(f"{r['run']} per-chunk (request: [denoise_s, commit_s]):",
              {k: [(c["denoise_s"], c["commit_s"]) for c in v] for k, v in r["student_chunks"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
