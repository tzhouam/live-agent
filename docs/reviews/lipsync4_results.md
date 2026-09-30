# Page check during a live lesson (8200 demo, real H.264, teacher persona with boards), 2026-10-01 00:55
- playback offset +0 ms: {"paints": 604, "chunks": 9, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- injected: getOutputTimestamp 250 ms: {"paints": 300, "media_minus_context_ms": -233.3, "expected_ms": -233.3, "ok": true}
- injected: fallback base+output latency: {"paints": 300, "media_minus_context_ms": -25.3, "expected_ms": -25.3, "ok": true}
- offset change 0 -> +300 ms: {"paints": 515, "switch": {"k0": "16/3", "k1": "17/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "16/3", "reentered_ended_chunk": true, "max_gap_near_switch_ms": 17.9, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- offset change -300 -> +300 ms: {"paints": 276, "switch": {"k0": "17/3", "k1": "18/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "17/3", "reentered_ended_chunk": true, "max_gap_near_switch_ms": 19.2, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- offset change +300 -> -300 ms: {"paints": 331, "switch": {"k0": "18/3", "k1": "19/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "19/0", "reentered_ended_chunk": null, "max_gap_near_switch_ms": 21.3, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- stop on a new comment: {"stops": 1, "paints_after": 97, "stale_after_stop": 0, "ok": true}
- reconnect: {"renders_per_refresh": 1.0, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [112.9, 113.0, 113.0, 112.9, 112.8, 112.9], "expected_ms": 103.3, "ok": true}
- phone_no_horizontal_scroll: true
- page_errors: []

# After the round-4 fixes: live lesson (杠杆原理), --expect-boards, 2026-10-01 01:05
- playback offset +0 ms: {"paints": 604, "chunks": 9, "media_minus_heard_ms": 16.7, "expected_ms": 16.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset +200 ms: {"paints": 600, "chunks": 9, "media_minus_heard_ms": -183.3, "expected_ms": -183.3, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- playback offset -100 ms: {"paints": 601, "chunks": 9, "media_minus_heard_ms": 116.7, "expected_ms": 116.7, "wrong_index": 0, "skipped_frames": 0, "chunk_ends_shown": true, "ok": true}
- injected: getOutputTimestamp 250 ms: {"paints": 300, "media_minus_context_ms": -233.3, "expected_ms": -233.3, "ok": true}
- injected: fallback base+output latency: {"paints": 300, "media_minus_context_ms": -25.3, "expected_ms": -25.3, "ok": true}
- offset change 0 -> +300 ms: {"paints": 546, "switch": {"k0": "16/3", "k1": "17/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "16/3", "reentered_ended_chunk": true, "max_gap_near_switch_ms": 23.0, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- offset change -300 -> +300 ms: {"paints": 276, "switch": {"k0": "17/3", "k1": "18/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "17/3", "reentered_ended_chunk": true, "max_gap_near_switch_ms": 21.3, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- offset change +300 -> -300 ms: {"paints": 331, "switch": {"k0": "18/3", "k1": "19/0", "request_boundary": true, "prev_ended": true, "prev_kept": true, "lines_differ": true, "boards_differ": true}, "first_paint_after": "19/0", "reentered_ended_chunk": null, "max_gap_near_switch_ms": 18.2, "wrong_index": 0, "caption_not_on_screen_chunk": 0, "board_not_on_screen_chunk": 0, "ok": true}
- render errors: audio-clock chunk_end: {"chunk_end_while_failing": 3, "paints_after_restore": 91, "ok": true}
- stop on a new comment: {"stops": 1, "paints_after": 122, "stale_after_stop": 0, "ok": true}
- reconnect: {"renders_per_refresh": 1.01, "ok": true}
- calibration offset +120 ms: {"beeps": 6, "flashes": 6, "flash_minus_beep_ms": [115.3, 115.2, 115.1, 114.9, 115.0, 114.9], "expected_ms": 103.3, "ok": true}
- page_errors: []
