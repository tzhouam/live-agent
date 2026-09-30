# Lip-sync measurements (evidence for review lipsync2), all measured locally 2026-09-30 / 10-01

## Method zero on real, presumably synchronous speech (Wikimedia Commons, Wikitongues; 480p transcodes, first 300 s)
| clip | licence | offset (ms) | 95% CI main lobe | runs | speech (s) | peak corr |
|---|---|---|---|---|---|---|
| Jesse speaking English (Wikitongues and AfroCrowd) | CC BY-SA 4.0 | 79.0 | [71.1, 85.6] | 40 | 256.4 | 0.164 |
| Leena speaking English (Wikitongues and AfroCrowd) | CC BY-SA 4.0 | -52.1 | [-63.0, -41.4] | 38 | 225.5 | 0.214 |
| WIKITONGUES- Chengxi speaking Hanghzounese | CC BY-SA 4.0 | -166.6 | [-183.8, -148.0] | 18 | 107.4 | 0.264 |
| WIKITONGUES- Orsolya speaking Hungarian | CC BY 3.0 | -78.7 | [-97.3, -56.2] | 9 | 89.5 | 0.232 |
| WIKITONGUES- Tao speaking Yunnan Mandarin with Thai and Taiwanese accent | CC BY-SA 4.0 | -104.1 | [-113.7, -95.1] | 12 | 117.0 | 0.273 |

Median -78.7 ms, range -166.6..+79.0 ms: by this method real speech shows the jaw opening ahead of the level peaks by
about 50-100 ms, with a per-recording spread of about +-90 ms (each source's own capture offset and speaking style;
the sources' sync is not independently known).

## Model output (TaoMate-H3, two GPUs, merge off), after the edge fix and 10 s run pieces
| recording | speech (s) | runs | offset (ms) | 95% CI main lobe | 95% CI unrestricted | main-lobe share | peak corr |
|---|---|---|---|---|---|---|---|
| sess-aea89030eebf (330 s lesson, 2026-09-30) | 84.9 | 31 | -44.8 | [-64.9, -30.1] | [-69.4, 333.3] | 0.923 | 0.161 |
| sess-1ff5d1bb12c0 (2026-09-29) | 38.4 | 15 | -37.9 | [-69.8, -14.5] | [-333.3, 203.7] | 0.712 | 0.123 |

Self-checks (audio delayed by N frames): aea N=+2 -127.7 ms (delta -82.9), N=-2 +37.0 (delta +81.8); 1ff5 N=+2 -120.0, N=-2 +47.5.
Conclusion used: the model's offset lies inside the spread of real speech measured the same way, so there is no basis for a
server-side shift; the method cannot certify absolute sync better than that spread.

## Server media paths: tests/test_av_alignment.py (recording and wire format, 34/34/34/17 shape) and tests/test_fmp4.py

## Page clock: scripts/lipsync_page_check.py on the live stack (8200 demo, real H.264), 2026-10-01
- playback offset +0 ms: {"paints": 603, "chunks": 9, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- injected: getOutputTimestamp 250 ms: {"paints": 301, "media_minus_context_ms": -233.3, "expected_ms": -233.3, "ok": true}
- injected: fallback base+output latency: {"paints": 300, "media_minus_context_ms": -25.3, "expected_ms": -25.3, "ok": true}
- offset change 0 -> +300 ms: {"paints": 361, "max_gap_near_switch_ms": 22.7, "wrong_index": 0, "ok": true}
- stop on a new comment: {"stops": 1, "paints_after": 200, "stale_after_stop": 0, "ok": true}
- reconnect: {"renders_per_refresh": 1.0, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [114.4, 114.1, 114.1, 114.0, 113.9, 114.0], "expected_ms": 103.3, "ok": true}
- phone_no_horizontal_scroll: true
- page_errors: []

Same checks pass on the CPU mock server (calibration 113.6-113.8 ms; offset change max gap 17.2 ms).
