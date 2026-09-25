"""Summarize validate_streaming.py runs (results.json) into one Markdown table.

Usage: python scripts/m0/summarize_streaming.py .cache/m0/stream/s4_coloc_v3-* ...
Values are *measured locally*.

"period" = mean wall time between consecutive request completions over the pipelined
requests 0..P-1, i.e. the sustained production rate with the teacher included. Real time
requires period < 119/24 = 4.958 s (native media per request). Lock times of pipelined
requests are reconstructed from the policy: lock(k+1) = arrival of request k's first chunk.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def period_s(rows: list[dict]) -> float:
    pipe = [q for q in rows if q["lock_policy"] in ("first", "pipelined")]
    if pipe and pipe[0].get("t_done_mono") is not None:  # exact (runs after 05:47)
        return (pipe[-1]["t_done_mono"] - pipe[0]["t_done_mono"]) / (len(pipe) - 1)
    t_lock, t_done = 0.0, []
    for q in pipe:
        t_done.append(t_lock + q["lock_to_done_s"])
        t_lock += q["lock_to_first_chunk_s"]
    return (t_done[-1] - t_done[0]) / (len(t_done) - 1)


def main() -> int:
    print("| run | teacher lookahead | teacher s/request (mean) | student s/request (pipelined 1..5, mean / max) "
          "| period s/request | lock->first chunk s (pipelined 1..5) | Lambda_idle s (lock->first chunk, idle) "
          "| student start->first chunk s | idle chunk denoise / decode / transport s | min startup buffer s "
          "| audio == teacher | streamed-vs-one-shot audio SNR dB |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for run in map(Path, sys.argv[1:]):
        r = json.loads((run / "results.json").read_text())
        rows = r["requests"]
        pipe = [q for q in rows if q["lock_policy"] in ("first", "pipelined")]
        idle = [q for q in rows if q["lock_policy"] == "idle"]
        student = [q["student_request_s"] for q in pipe[1:]]
        mean_chunk = lambda key: statistics.mean(x for q in idle for x in q[key])  # noqa: E731
        print(
            f"| {run.name} | {r['meta']['lookahead']} "
            f"| {statistics.mean(q['teacher_s'] for q in rows):.2f} "
            f"| {statistics.mean(student):.2f} / {max(student):.2f} "
            f"| {period_s(rows):.2f} "
            f"| {statistics.mean(q['lock_to_first_chunk_s'] for q in pipe[1:]):.2f} "
            f"| {' , '.join(format(q['lock_to_first_chunk_s'], '.2f') for q in idle)} "
            f"| {statistics.mean(q['student_start_to_first_chunk_s'] for q in rows[1:]):.2f} "
            f"| {mean_chunk('chunk_denoise_s'):.2f} / {mean_chunk('chunk_decode_s'):.2f} / "
            f"{mean_chunk('chunk_transport_s'):.3f} "
            f"| {r['summary']['min_startup_buffer_no_stall_s']:.2f} "
            f"| {r['summary']['all_audio_teacher_exact_match']} "
            f"| {r['audio_parity']['snr_db_vs_one_shot_decode']:.1f} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
