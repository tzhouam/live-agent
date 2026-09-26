## Round-6 findings in scope

1. **RESOLVED** — A1 closes chains after all carrying requests are presented.
2. **PARTIAL** — Rank-PID gathering has a helper, but the inlined worker code does not show the services calling it; the GPU shutdown sweep remains unverified.
3. **RESOLVED** — The repeat arm retains the original action and line.
4. **RESOLVED** — A cut bridge can be issued again.
5. **RESOLVED** — Adapter cancellation reaches worker cleanup.
6. **RESOLVED** — Bounded runs drain pending QC.
7. **RESOLVED** — Verdicts remain bound to revision and step.
8. **RESOLVED, scoped** — Multistep action gating exists; the online pilot excludes content chains.
9. **RESOLVED** — Purge redacts queued corrections.
10. **RESOLVED** — Barge-in changes the plan before its first await.
11. **RESOLVED** — Locking refreshes timing samples.
12. **RESOLVED** — `LOCK` records `retry_of`.
13. **RESOLVED, scoped** — Moderation and pre-play ASR limits are disclosed.
14. **RESOLVED** — The cited completion phrase is guarded.
15. **RESOLVED** — LLM and ASR work is outside the WebSocket receive loop.
16. **RESOLVED** — Displaced unexecuted chains produce capacity skips.
17. **RESOLVED on prior evidence** — Scoring uses task annotations independently of the refusal heuristic.
18. **RESOLVED** — A1 supplies its own action phrase and spoken line.
19. **RESOLVED, scoped** — The action-chain pilot limit is explicit.
20. **RESOLVED** — `SessionView` filters chunks by generation epoch.
21. **RESOLVED** — Partial adapter startup and cancellation have cleanup paths.
22. **RESOLVED, scoped** — Client clock mapping exists; its accuracy is disclosed as unmeasured.
23. **RESOLVED, scoped** — JPEG/PCM transport is disclosed and excluded from M1 qualification.
24. **PARTIAL** — The throughput claim is scoped to short runs, but `docs/m0_measurements.md` is absent from the inlined evidence, so its figures cannot be checked.
25. **RESOLVED** — Old-plan segments remain ineligible pending a barge-in decision.
26. **RESOLVED** — The client-stamped utterance end is retained.
27. **RESOLVED** — The browser supplies a measured last-paint timestamp.
28. **PARTIAL** — Queue draining is present; rank-PID shutdown verification has the gap in #2.
29. **RESOLVED** — Media is evicted after presentation and QC.
30. **RESOLVED** — Erasure and barge-in have separately owned gates.
31. **RESOLVED** — The repair offset of two is labelled as a mock-run observation.
32. **RESOLVED** — Erasure stops playback before storage deletion.
33. **RESOLVED** — Erasure discards the active recording.
34. **PARTIAL — major**, [`orchestrator.py:_qc_budget, _run_checks_inner`](/data/zhoutaichang/live-agent/live_agent/orchestrator.py): the budget still ignores `CheckQuestion.deadline_s` and grants at least one second after the chain deadline. A late verdict can mark a chain complied, release another step, or queue repair after its deadline. Cap checks at the applicable deadline and suppress late control transitions.
35. **RESOLVED** — An unknown or empty action intent now gets a controlled refusal line.
36. **PARTIAL — major**, [`director.py:_claims_completion`](/data/zhoutaichang/live-agent/live_agent/director/director.py): “茶被我饮尽了” is an unverified completion claim that matches neither regex and can be spoken. Apply a verified-claim policy beyond the current verb list, and test paraphrases.
37. **RESOLVED** — The WebSocket handler watches fatal orchestrator termination.
38. **PARTIAL — major**, [`director.py:apply, on_verified`](/data/zhoutaichang/live-agent/live_agent/director/director.py): a revision drops its deferred completion remark, but a *new* instruction can still cause the old chain’s deferred “好了。” to be queued ahead of it. Discard the interrupted remark when resolving the barge-in, including when the decision opens a new chain.
39. **RESOLVED** — Typed instructions invoke the interruption path before LLM work.
40. **PARTIAL — major**, [`orchestrator.py:_drop_unpresented`](/data/zhoutaichang/live-agent/live_agent/orchestrator.py) and [`ledger.py:bridging_note`](/data/zhoutaichang/live-agent/live_agent/ledger.py): a cut during the first chunk has no completed-chunk ack, so speech already heard can be labelled “not said”; an audible completion claim can also be discarded. Report partial presentation on stop, or treat the in-flight chunk as partly shown and preserve audible-claim evidence.
41. **RESOLVED** — Repair reserves the next actual unlocked opportunity rather than relying on its planned lock time.
42. **RESOLVED** — Shared-memory decode failures discard payloads and surface a fatal adapter error.

## New findings

43. **Blocking — [`orchestrator.py:_erase_locked, _run_checks_inner`](/data/zhoutaichang/live-agent/live_agent/orchestrator.py).** Erasure leaves QC for fully presented requests running. If a speech check is awaiting ASR, erasure can redact the log, then that check can append a `VERDICT` rationale containing the erased spoken value. Cancel and drain pre-erasure QC before redaction, invalidate its results, and prevent late writes from restoring erased content.

44. **Major — [`server/static/index.html:onMessage, schedule`](/data/zhoutaichang/live-agent/live_agent/server/static/index.html).** Each chunk schedules playback only after its asynchronous JPEG decodes finish. A later chunk can finish decoding first and play before an earlier chunk, breaking presentation order and the evidence timeline. Buffer decoded chunks and schedule only the next contiguous request/chunk.

45. **Major — [`orchestrator.py:stop`](/data/zhoutaichang/live-agent/live_agent/orchestrator.py).** Cancellation during its QC drain exits before task cancellation, generator close, and log close. A cancelled session can leave worker activity and an open log behind. Put cleanup in a cancellation-safe `finally` and re-raise cancellation after it completes.

The prompt compiler and `docs/m0_measurements.md` were not inlined; prompt fidelity and their numerical claims remain unverified here.

**Verdict: not ready.**