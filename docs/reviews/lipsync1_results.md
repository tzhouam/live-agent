# Lip-sync measurements (evidence for review lipsync1), all measured locally on 2026-09-30

## Model output (TaoMate-H3, two GPUs, merge off), tools/av_sync.py --signal jaw
| recording | speech (s) | runs | offset (ms, >0 picture late) | 95% CI (main lobe) | peak corr |
|---|---|---|---|---|---|
| sess-aea89030eebf (2026-09-30, 330 s lesson on the 8200 demo) | 84.9 | 31 | -45.2 | [-65.3, -30.0] | 0.118 |
| sess-1ff5d1bb12c0 (2026-09-29 two-GPU demo) | 38.4 | 15 | -42.6 | [-72.8, -20.6] | 0.094 |

Self-checks (audio delayed by N frames before measuring; the offset must drop by N frames):
- sess-aea89030eebf: N=0 -1.08 frames, N=+2 -3.01 (delta -1.93), N=-2 +0.93 (delta +2.01)
- sess-1ff5d1bb12c0: N=0 -1.02, N=+3 -3.86 (delta -2.84), N=-3 +2.09 (delta +3.11)
The inner-lip gap signal (landmarks 13/14 over eye distance) did not track the shifts (face ~70 px wide), so jawOpen is the default.
Earlier attempts that failed and why: motion-energy cells (head motion dominates, CI +-300 ms); fixed 5-10 s windows (muted no-line requests are digital silence, the jumps dominated; negative correlation at lag 0).
The USP4 BF16 recording sess-b61bbb5ad485 has only 23 s of speech in 1447 s (idle session), not measured.

## Server media paths (tests/test_av_alignment.py)
- Session recording (ffmpeg libx264 + AAC with edit list): flash vs click within 2 ms at 4 positions.
- Page wire format: each chunk's PCM covers exactly its frames, click at the flash frame's sample.
- fMP4 decoder from the vLLM-Omni stream: sample-accurate tone phase (tests/test_fmp4.py, existing).

## Page clock (scripts/lipsync_page_check.py, headless Chromium, 60 Hz rAF)
Live stack (8200 demo, real H.264 chunks), 12 s per offset:
- playback offset +0 ms: {"paints": 722, "chunks": 11, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 721, "chunks": 11, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 720, "chunks": 11, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [112.4, 112.3, 112.2, 112.1, 112.1, 112.2], "expected_ms": 103.3, "ok": true}
- phone_no_horizontal_scroll: true
- page_errors: []
CPU mock server: same checks pass (calibration flash onsets 110.3-110.5 ms for expected 103.3 + up to one refresh).
