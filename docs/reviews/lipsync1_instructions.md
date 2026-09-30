# Codex review: lip sync on the demo page and its measurement (uncommitted change on top of 1da3243)

Context: a real-time digital-teacher demo. A video model (TaoMate-H3 on vLLM-Omni) streams 5 s requests as chunks of
34/34/34/17 frames at 24 fps with 32 kHz audio; the server decodes them and sends each chunk to the browser as one
H.264 segment + PCM. The page (inlined diff of `live_agent/server/static/index.html`) schedules each chunk's PCM on an
AudioContext (`start = max(currentTime + 0.05, playhead)`, `end = start + n_frames / fps`) and draws frames on a canvas
from requestAnimationFrame, choosing frame `floor((t - start) / (end - start) * n)`. The owner asked that "the
teacher's mouth should be aligned with the audio"; an earlier change (D-037) switched `t` from `currentTime` to the
heard time (`getOutputTimestamp`). This change:
1. Page: `t = heardTime() + refreshS - avOffsetMs / 1000` (one display refresh because a canvas drawn now appears at
   the next vsync; a per-viewer offset "画面延后", -300..+300 ms in localStorage, for devices that report too little
   output delay, e.g. Bluetooth); a calibration test (six 1 kHz beeps on the audio clock, a white flash drawn on the
   media clock); a chunk leaves the draw queue only when `t >= end` even if its audio ended (onended ack) first;
   test hooks `window.__avTrace` / `window.__avFlashLog`; the render loop is started once (`startRender`).
2. `tools/av_sync.py`: measures lip sync of a recording from MediaPipe jawOpen vs the audio level (voiced runs,
   high-passed, cross-correlation +-8 frames, parabolic peak, bootstrap CI over runs for the main lobe).
3. `scripts/lipsync_page_check.py`: headless checks of the page clock; `tests/test_av_alignment.py`: flash/click
   alignment through the session recorder and the page wire format.
Measurements are in `docs/reviews/lipsync1_results.md`. Conclusion drawn: the model's lips lead the voice by ~45 ms
(CI about -65..-30 ms), inside perceptual tolerance, so no server-side shift; the page compensates output and display
delay and offers the manual offset for devices that misreport.

Please find correctness bugs and weak conclusions, most severe first. Focus on:
- the clock math: getOutputTimestamp semantics (contextTime/performanceTime), the sign and size of the refresh
  compensation, the offset sign ("画面延后" positive must delay the picture), interaction with `start`/`end`, the
  chunk_start / chunk_end acks and the `painted` QC evidence sent to the server, background tabs (rAF stops), stop /
  barge-in (`stopAll`), reconnects, the calibration beeps vs a live stream (same output gain, push-to-talk ducking);
- whether the queue-filter change can leak chunks or draw a stale chunk over a newer one;
- the measurement method: is jawOpen vs level correlation a valid lip-sync estimate, is the sign convention right,
  is the main-lobe bootstrap CI honest, are the self-checks sufficient, and is "no server-side shift" justified;
- the tests and check script: can they pass while the behaviour is wrong?
For each finding: file:line or function, a concrete failure scenario, severity (high/medium/low), and a fix. Skip style.
