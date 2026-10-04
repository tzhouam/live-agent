# Frontend/backend refactor validation — 2026-10-02

All counts and observed outcomes below are **measured locally** on the CPU mock stack. Port numbers
and HTTP status codes identify configuration/protocol values, not performance measurements.

- `python3 -m pytest`: **363 passed, 1 skipped**. The skipped test requires a real TaoMate GPU run.
  Existing FastAPI startup-handler and Torch deprecation warnings remain. A timestamp fallback regression
  was added after collection; `python3 -m pytest tests/test_backend_api.py` subsequently passed **5 tests**,
  including the new case before and after client clock synchronization.
- `npm --prefix frontend test`: **19 passed**. Includes browser API helper behavior and real local
  HTTP/WebSocket proxy tests: streaming delivery, binary order, both handshake head buffers, ranges,
  HTTP errors, stale-profile status propagation, client abort, static path/symlink containment and
  frontend shutdown with active WebSockets under SIGINT and SIGTERM.
- `python3 scripts/lipsync_page_check.py http://127.0.0.1:18210 --seconds 6 --warmup 2`: exit **0**, every
  check `ok: true`, no browser page errors. Separate mock backend on loopback port `18211`, memory disabled,
  isolated student/trace directories. Covers playback offsets, injected output latency, offset changes
  across request boundaries, render-error fallback, stop on a new comment, reconnect and calibration.
- Chromium profile/trace smoke check against the same frontend: profile loads, a versioned edit saves,
  stale version returns `409`, reset succeeds, and the empty trace page renders. No browser page errors.
  The student store was isolated from existing user profiles.
- `PORT=18220 BACKEND_PORT=18221 RECORD=0 READY_TIMEOUT=20 scripts/run_live.sh demo`: frontend and backend
  started separately, proxied `/api/health` returned `status: ok`, direct backend `/` returned `404`,
  Ctrl-C exited the launcher and stopped its children.
- `bash -n` for changed shell scripts and `git diff --check`: passed.

Inspection of the moved transport and WebSocket session function ASTs found their behavior unchanged.
A missing import of the server clock function was caught in the contributor review and restored before
browser validation. The previous `/traces` HTML renderer was replaced with `/api/traces` JSON plus a
frontend view; session video matching now excludes another session sharing its filename prefix.

These checks verify the separation and the local mock path. They do **not** measure generator throughput,
qualify the GPU stack, evaluate teaching quality or establish physical display/audio alignment. No training,
GPU reservation, deployment or public broadcast was performed for this refactor.

## Additional checks after the first review

- Final frontend code exercised in Chromium: live playback and a typed instruction, nonempty trace API,
  and terminating the frontend with an active browser session. All succeeded, no page errors.
- Launcher failure paths: an occupied backend port rejects before any frontend or GPU start; a sleeping
  fake backend reaches the readiness timeout, prints no ready message and cleans its frontend process.
  SIGTERM of the actual mock stack closes both listeners. No GPU reservations made.
- `PORT=08200 BACKEND_PORT=8200 scripts/run_live.sh full`: exit **2** before acquiring GPUs, with
  `PORT and BACKEND_PORT must be different`. Numeric normalization rejects equivalent port spellings.
- Profile polling regression (pre-existing before extraction): a pending clean-page refresh used to apply
  after the user began editing or after a newer profile loaded. Controlled-response tests now exercise
  the real script's name/exam edits, save, reload, student switch, overlapping polls and hidden-page guard.
  All **7** pass; removing the guard produces **6** failures, confirming that the tests detect the race.
- The launcher version guard accepts Node **18.2** or newer and rejects older versions, matching the
  frontend shutdown API requirement. These are runtime version identifiers.

Test counts, exit outcomes and browser observations here are **measured locally**. Contributor inspection
confirmed the GPU reservation marker is preserved in installed canhazgpu status output; actual GPU worker
shutdown remains untested. All local smoke-test services were stopped after validation.

## Review repairs

- Final `npm --prefix frontend test`: **28 passed** (measured locally).
- WebSocket orderly EOF now relies on `pipe`/`end` to drain writes instead of destroying the downstream
  socket. A deterministic controlled pending-write test holds binary output while observing upstream
  close; the previous implementation destroys the downstream with bytes still queued, and the fixed
  implementation delivers the pending bytes. The regression fails on the previous code and passes on
  the fix. Ordinary slow TCP runs did not reproduce truncation; the additional slow-client test verifies
  complete delivery of a **16 MiB** payload (measured test payload size), without assuming host TCP
  buffers always create observable backpressure.
- Package runtime and launcher guard both require Node **18.2** or newer. Equivalent decimal port
  spellings are normalized before collision checks.
