## Round-5 findings in scope

1. **RESOLVED** — A1 closes a chain only after every request carrying it was fully presented.
2. **PARTIAL** — `_worker_pids` now reads `hello` and `ready`, but the inlined worker protocol does not establish that every rank PID is sent; the GPU shutdown check remains pending.
3. **RESOLVED** — The repeat arm retains the original action and line.
4. **RESOLVED** — Dropping a bridge request clears `bridge_request`, allowing another bridge.
5. **RESOLVED** — Adapter cancellation reaches worker cleanup.
6. **RESOLVED** — Bounded runs drain pending QC.
7. **RESOLVED** — Verdicts remain bound to revision and step.
8. **RESOLVED, scoped** — Multistep action gating exists; the online-loop pilot excludes content chains.
9. **RESOLVED** — `Director.purge` redacts queued `Segment.correction`.
10. **RESOLVED** — Barge-in changes the plan before its first await.
11. **RESOLVED** — Locking refreshes generator timing samples.
12. **RESOLVED** — `LOCK` records `retry_of`.
13. **RESOLVED, scoped** — Moderation and pre-play ASR limits are disclosed.
14. **RESOLVED for the cited wording** — The reported completion phrase is guarded.
15. **RESOLVED** — LLM and ASR calls run outside the WebSocket receive loop.
16. **RESOLVED** — Displaced unexecuted chains produce capacity skips.
17. **RESOLVED on the prior review’s evidence** — Scoring uses task annotations independently of the refusal heuristic; evaluation files were not inlined again.
18. **RESOLVED** — A1 supplies its own action phrase and spoken line.
19. **RESOLVED, scoped** — The action-chain pilot limit is explicit.
20. **RESOLVED** — `SessionView` filters chunks by generation epoch.
21. **RESOLVED** — Partial startup and cancellation have cleanup paths.
22. **RESOLVED, scoped** — Client clock mapping exists; accuracy is disclosed as unmeasured.
23. **RESOLVED, scoped** — JPEG/PCM transport is disclosed and excluded from M1 qualification.
24. **PARTIAL** — The throughput claim is limited to short runs, but `docs/m0_measurements.md` was not inlined, so its figures cannot be independently checked.
25. **RESOLVED** — Old-plan segments remain ineligible while a barge-in decision is pending.
26. **RESOLVED** — The client-stamped utterance end is retained.
27. **PARTIAL** — `_evidence_time` accepts a measured last-paint timestamp, but still estimates it when absent; the browser code that supplies the timestamp was not inlined.
28. **PARTIAL** — Reset drains queued exceptions; the rank-PID shutdown sweep has the verification gap in #2.
29. **RESOLVED** — Media is evicted after presentation and QC.
30. **RESOLVED** — Erasure and barge-in use separately owned gates.
31. **RESOLVED** — The repair offset of two is labelled as a mock-run observation.
32. **RESOLVED** — `_erase_locked` stops playback before storage deletion.
33. **RESOLVED** — Erasure discards and verifies removal of an active recording.
34. **PARTIAL (major)** — `_run_checks_inner` has an eight-second timeout, but ignores `CheckQuestion.deadline_s` and the chain’s remaining deadline. A check begun near the 15-second limit can finish too late to drive timely repair or step release. Bound and log checks against the remaining deadline.
35. **PARTIAL (major)** — Manifest degradation replaces the LLM line, but `Director._apply_decision` still enqueues the original line when `_validate` refuses an unknown or empty action intent. For `intent="fly", line="好，我飞起来"`, it logs refusal while speaking acceptance. Replace that line with a controlled refusal.
36. **PARTIAL (major)** — Action-bearing lines receive an additional perfective check, but chat or content lines rely on `_COMPLETION` alone. A line such as “茶被我喝净了” can be spoken without verification and is not logged as a completion claim. Apply the completion policy to every unverified spoken line.
37. **RESOLVED** — The WebSocket handler watches orchestrator termination and cleans up a fatal session.
38. **PARTIAL (major)** — `on_verified` marks a chain `COMPLIED` before a pending barge-in decision. `decide` then omits it from open chains; a new decision can release its deferred “好了。” ahead of the replacement request, while a revision cannot merge into that chain. Keep the prior chain revision-eligible until the decision resolves, and discard its remark when superseded.

## New findings

39. **Major — `server/app.py:ws_endpoint`, `text` branch.** A typed instruction is queued without calling `orch.on_speech_start`. Typed corrections and forget requests therefore leave playback running during the responder call; an older buffered request can still be shown after the user interrupts. Invoke the interruption path when accepting a typed instruction, before queueing its LLM work.

40. **Major — `orchestrator.py:_drop_unpresented`, `ledger.py:bridging_note`.** Cutting a request after one or more chunks were shown marks its *whole* action and transcript as unseen. The next prompt can assert that S1 “did not say” a line whose audio was already heard. Track shown action and speech at chunk level, or reset when the unshown portion cannot be distinguished.

41. **Major — `timeline.py:earliest_correctable`.** It skips an unlocked request when its *planned* lock time is before `E+C`, even if backlog or a gate has delayed its actual lock until after the correction is ready. The repair then goes to `j+1` although `j` was the earliest usable request, invalidating the logged RQ2 assignment. Determine eligibility at the actual lock opportunity and reserve the first still-unlocked eligible request.

42. **Major — `taomate_h3.py:_on_message`, `P.CHUNK` path.** A missing or corrupt shared-memory payload makes `P.from_shm` raise inside an event-loop callback. No `WorkerError` reaches `chunks()`, the other payload may remain on disk, and playback can wait forever for the missing chunk. Catch decode failures, discard both payloads, and propagate a fatal adapter error.

The prompt compiler and `docs/m0_measurements.md` were not inlined, so their implementation and numerical claims remain unverified in this round.

**Verdict: not ready.**