## Round-8 findings in scope

1. **PARTIAL** — A1 closes fully presented chains, but a cut request can leave a chain open indefinitely (new finding 2).
2. **RESOLVED** — Worker rank PIDs are gathered for cleanup.
3. **RESOLVED** — The repeat arm retains the original action and line; the comparison still has a separate confound (new finding 3).
4. **RESOLVED** — A cut bridge can be issued again.
5. **RESOLVED** — Worker cancellation reaches state cleanup.
6. **RESOLVED** — Bounded runs drain pending QC.
7. **RESOLVED** — Verdicts are bound to revision and step.
8. **RESOLVED, scoped** — Multistep action gating exists; the online pilot excludes content chains.
9. **RESOLVED** — Erasure purges queued corrections.
10. **RESOLVED** — Barge-in changes the plan before its first await.
11. **RESOLVED** — Locking refreshes timing samples.
12. **RESOLVED** — `LOCK` records `retry_of`.
13. **RESOLVED, scoped** — Moderation and pre-play ASR limits are disclosed.
14. **RESOLVED** — The cited completion phrase is guarded.
15. **RESOLVED** — LLM and ASR work is outside the WebSocket receive loop.
16. **RESOLVED** — Displaced unexecuted chains produce capacity skips.
17. **RESOLVED on the stated prior evidence** — Primary scoring uses task annotations independently of the refusal heuristic.
18. **RESOLVED** — A1 supplies its own action phrase and spoken line.
19. **RESOLVED, scoped** — The action-chain pilot limit is explicit.
20. **RESOLVED** — `SessionView` filters chunks by generation epoch.
21. **PARTIAL** — Startup cleanup handles errors, but default warmup has no timeout (new finding 4).
22. **RESOLVED, scoped** — Client clock mapping exists; accuracy remains unmeasured.
23. **RESOLVED, scoped** — JPEG/PCM transport is disclosed and excluded from M1 qualification.
24. **RESOLVED on round-8 evidence** — The M0 claim is limited to short-run throughput. `docs/m0_measurements.md` was not inlined here, so its figures could not be re-audited.
25. **RESOLVED** — Old-plan segments remain ineligible pending a barge-in decision.
26. **RESOLVED** — The client-stamped utterance end is retained.
27. **RESOLVED** — The browser supplies a last-paint timestamp.
28. **RESOLVED** — Worker rank-PID gathering is present.
29. **RESOLVED** — Media is evicted after presentation and QC.
30. **RESOLVED** — Erasure and barge-in have separately owned lock gates.
31. **RESOLVED** — The repair offset of two is labelled as a mock-run observation.
32. **RESOLVED** — Erasure stops playback before storage deletion.
33. **RESOLVED** — Erasure discards the active recording.
34. **PARTIAL** — Late action verdicts cannot verify or repair, but a check timing out at the deadline can leave the chain open (new finding 1).
35. **RESOLVED** — An empty or unknown action intent receives a controlled refusal.
36. **RESOLVED, scoped** — The narration guard’s pattern-based limit is disclosed.
37. **RESOLVED** — The WebSocket handler watches fatal orchestrator termination.
38. **RESOLVED** — A new instruction drops the interrupted chain’s deferred completion remark.
39. **RESOLVED** — Typed instructions interrupt before LLM work.
40. **RESOLVED, scoped** — A claim in a cut chunk is now marked `audibility="uncertain"` when only audio energy was detected.
41. **RESOLVED** — Repair reserves the next actual unlocked opportunity.
42. **RESOLVED** — Shared-memory decode failure surfaces a fatal adapter error.
43. **RESOLVED** — Erasure invalidates and drains pending QC before redaction.
44. **RESOLVED** — The browser schedules decoded chunks in arrival order.
45. **RESOLVED** — `stop` awaits generator close despite cancellation.
46. **RESOLVED** — Action deadlines no longer truncate content replies.
47. **RESOLVED** — Inputs retain the epoch stamped when received.
48. **RESOLVED** — Action control resolves before the later speech check.
49. **RESOLVED** — A blocklist-withheld segment loses its checks and chain binding and is refused.

## New findings

1. **Major — [orchestrator.py: `_run_checks_inner`, `_one_check`](/data/zhoutaichang/live-agent/live_agent/orchestrator.py).** If an action judge times out at the step deadline, `_one_check` returns `UNKNOWN` with a verdict time just past the deadline. `_run_checks_inner` suppresses verification and repair, but calls `expire` only when the deadline had already passed *before* QC began. The chain can remain `OPEN`, with later multistep actions held forever. Expire the revision and step whenever action QC misses its deadline, including timeout and late-return paths.

2. **Major — [director.py: `on_interrupted`, `_resume_interrupted`, `on_request_presented`](/data/zhoutaichang/live-agent/live_agent/director/director.py).** An A1 request uses `action_text`, while `on_interrupted` saves only `intent`. If the user cuts that request and the ensuing utterance is chat, `_resume_interrupted` discards the saved segment because `intent` is empty. The dropped request also remains in `chain.requests`, so the chain cannot close as presented. This leaves an A1 chain open and exposes it to later responder decisions as unfinished. Preserve and resume A1’s action and line, and make dropped carrying requests either superseded for closure or terminal capacity skips.

3. **Major — [orchestrator.py: `_repair`](/data/zhoutaichang/live-agent/live_agent/orchestrator.py).** In the randomized RQ2 comparison, `REPEAT` resubmits the original spoken line, while `GRADIENT` submits an empty line. H3 generates audio and video together, so a difference in remedy success could result from removing speech rather than from the semantic correction. Keep the original line in both arms and vary only the correction text.

4. **Major — [taomate_h3.py: `_start`, `_warmup`](/data/zhoutaichang/live-agent/live_agent/generator/taomate_h3.py).** The default startup runs warmup after both workers report ready, but `start_timeout` covers only readiness. If a worker stalls during that first request without disconnecting, `_warmup` waits for four chunks indefinitely and `start` never reaches its cleanup path. Bound warmup with a timeout, surface a worker error, and close the partially started adapter.

No further blocking or major finding is established from the inlined prompt and capability descriptions. The prompt compiler and M0 measurement file themselves were not supplied for this round.

**Verdict: not ready.**