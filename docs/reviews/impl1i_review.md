## Round-7 findings in scope

1. **RESOLVED** — A1 closes a chain only after every carrying request is presented.
2. **RESOLVED** — Both worker services call rank-PID gathering; shutdown uses those PIDs for the shared-memory sweep.
3. **RESOLVED** — The repeat arm retains the original action and line.
4. **RESOLVED** — A cut bridge can be issued again.
5. **RESOLVED** — Adapter cancellation reaches worker cleanup.
6. **RESOLVED** — Bounded runs drain pending QC.
7. **RESOLVED** — Verdicts remain bound to revision and step.
8. **RESOLVED, scoped** — Multistep action gating exists; the online-loop pilot excludes content chains.
9. **RESOLVED** — Purge redacts queued corrections.
10. **RESOLVED** — Barge-in changes the plan before its first await.
11. **RESOLVED** — Locking refreshes timing samples.
12. **RESOLVED** — `LOCK` records `retry_of`.
13. **RESOLVED, scoped** — Moderation and pre-play ASR limits are disclosed.
14. **RESOLVED** — The previously cited completion phrase is guarded.
15. **RESOLVED** — LLM and ASR work is outside the WebSocket receive loop.
16. **RESOLVED** — Displaced unexecuted chains produce capacity skips.
17. **RESOLVED on the stated prior evidence** — Primary scoring uses task annotations independently of the refusal heuristic.
18. **RESOLVED** — A1 supplies its own action phrase and spoken line.
19. **RESOLVED, scoped** — The action-chain pilot limit is explicit.
20. **RESOLVED** — `SessionView` filters chunks by generation epoch.
21. **RESOLVED** — Partial adapter startup and cancellation have cleanup paths.
22. **RESOLVED, scoped** — Client clock mapping exists; its accuracy is disclosed as unmeasured.
23. **RESOLVED, scoped** — JPEG/PCM transport is disclosed and excluded from M1 qualification.
24. **RESOLVED** — The supplied M0 table supports the documented short-run throughput claim and its qualification limits.
25. **RESOLVED** — Old-plan segments remain ineligible pending a barge-in decision.
26. **RESOLVED** — The client-stamped utterance end is retained.
27. **RESOLVED** — The browser supplies a measured last-paint timestamp.
28. **RESOLVED** — The worker code now shows rank-PID gathering for shutdown cleanup.
29. **RESOLVED** — Media is evicted after presentation and QC.
30. **RESOLVED** — Erasure and barge-in have separately owned lock gates.
31. **RESOLVED** — The repair offset of two is labelled as a mock-run observation.
32. **RESOLVED** — Erasure stops playback before storage deletion.
33. **RESOLVED** — Erasure discards the active recording.
34. **RESOLVED** — QC is capped at the action-step deadline, and late verdicts cannot trigger verification or repair.
35. **RESOLVED** — An unknown or empty action intent gets a controlled refusal line.
36. **RESOLVED, scoped** — The cited paraphrase is caught; the documented pattern-based guard does not claim complete coverage.
37. **RESOLVED** — The WebSocket handler watches fatal orchestrator termination.
38. **RESOLVED** — A new instruction drops the interrupted chain’s deferred completion remark.
39. **RESOLVED** — Typed instructions invoke interruption before LLM work.
40. **PARTIAL — major** — `orchestrator.py:_audible_before_cut` treats the first audio-energy onset as the onset of the scripted speech and any completion claim. A cut after a clink or other sound but before the words can still log the claim as heard. Preserve the played audio interval and verify speech or claim audibility within it; otherwise mark it uncertain.
41. **RESOLVED** — Repair reserves the next actual unlocked opportunity.
42. **RESOLVED** — Shared-memory decode failures discard payloads and surface a fatal adapter error.
43. **RESOLVED** — Erasure invalidates, cancels and drains pending QC before redaction.
44. **RESOLVED** — The browser schedules decoded chunks in arrival order.
45. **PARTIAL — major** — `orchestrator.py:stop` shields `gen.close()`, but cancellation during that await lets `stop` return while close continues in a background task. Session cleanup can then finish before worker shutdown does. Await the close task to completion despite cancellation, then re-raise cancellation.

## New blocking or major findings

46. **Major — `orchestrator.py:_chain_deadline, _run_checks_inner`; `director.py:expire`.** Content chains receive the default 15-second step deadline even though the proposal allows 15 seconds for speech onset **plus** up to 10 or 30 seconds for the complete answer. When a later content request finishes after 15 seconds, its speech check expires the chain and drops remaining queued segments, potentially truncating an otherwise timely explanation or song. Apply the registered content onset and completion deadlines separately; speech QC must not expire the reply at the onset deadline.

47. **Major — `server/app.py:handle_inputs`; `orchestrator.py:_on_user_utterance`.** The input epoch is captured only when a queued utterance starts director processing. If a second barge-in occurs while the first audio item is still queued or being transcribed, the first utterance can capture the *second* epoch, apply its stale plan, and lock a request before the newer utterance is handled. Stamp each input with its epoch when received, and discard superseded decisions using that stamp while still honoring erasure requests.

48. **Major — `orchestrator.py:_run_checks_inner`.** Action and speech checks run serially, and action verification waits for the speech check. An action verdict obtained before its 15-second deadline is discarded as a control transition if the following ASR check runs past that deadline. The next multistep action is then never released despite timely visual verification. Resolve action control from the timely action verdict independently of the post-presentation speech check.

49. **Major — `orchestrator.py:_audit`; `director.py:next_script`.** When the operator blocklist withholds an action or line, `_audit` blanks the script but leaves its action check and chain binding intact. A later positive visual verdict, including a false positive or action carried over from generator state, can mark the withheld request complied and queue “好了。” Treat an audit-withheld action as a refusal or failure and remove its stale checks before submission.

No additional blocking or major finding arises from the inlined M0 figures or prompt compiler. The M0 figures support short-run generator throughput only; the documented client and soak qualifications remain open.

**Verdict: not ready.**