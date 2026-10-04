# Omni port collision repair — 2026-10-02

This targets split2's new major finding. The launcher now validates and normalizes the Omni port along
with service ports, constructs the full planned listener set (frontend, backend, enabled helpers, Omni),
and rejects duplicates before frontend startup or any GPU invocation. Free-port probes follow that
configuration check.

**Measured locally:** `python3 -m pytest tests/test_launcher.py` passes **11 tests**. The test uses an
executable fake `gpu` and a vLLM executable stub with an isolated absent API-key file. Cases include
Omni/helper collisions (with optional image helper), leading-zero Omni/service collisions, invalid
ports, full/packed helper/service collisions, and unique ports reaching the fake GPU boundary. Failure
cases assert no GPU command invocation and no frontend startup. The unique-port case verifies the
normalized Omni argument, expected fake failure and frontend cleanup. No actual GPU/model is started.

`bash -n scripts/run_live.sh` and `git diff --check` pass. Existing full CPU suite, backend/media tests,
28 frontend tests and Chromium checks are recorded in `split1_results.md`. GPU runtime is still
unverified for this refactor. Numeric test counts/outcomes are measured locally; ports and version
numbers are interface/configuration values.

Final review identified a minor Bash integer-overflow edge case. The launcher now strips leading zeros
and bounds decimal length before arithmetic; the exact oversized input is rejected before any start.
The final `python3 -m pytest tests/test_launcher.py` result is **12 passed (measured locally)**.

The actual CPU `demo` stack was also rechecked after the planned-listener repair: proxied health,
frontend page delivery and SIGTERM cleanup succeeded, with both service listeners closed. The final
integer-length guard preserves ordinary valid ports; the unique-port fake-boundary case passes with it.
