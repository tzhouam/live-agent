## Round-4 findings in scope

1. **PARTIAL** — `Director.on_request_presented` counts dropped A1 requests as presented, so a later segment can close a chain whose action was never shown.
2. **PARTIAL** — `TaoMateH3Generator._worker_pids` reads a top-level `pids` field, but `_on_message` stores worker data under `hello` and `ready`; the rank-PID shutdown sweep receives none.
3. **RESOLVED** — `Orchestrator._repair` retains the original action and line in the repeat arm.
4. **PARTIAL** — `StateLedger` names unseen action and speech and waits for the bridge request to finish, but a dropped bridge leaves `bridge_request` set and prevents another bridge.
5. **RESOLVED** — adapter cancellation reaches worker termination and resource closure.
6. **RESOLVED** — bounded runs wait for pending QC.
7. **RESOLVED** — verdicts are bound to revision and step.
8. **RESOLVED, scoped** — multistep action gating is present; content chains are excluded from the online-loop pilot claim.
9. **PARTIAL** — erasure redacts scripts and pending corrections, but `Director.purge` leaves erased text in a queued `Segment.correction`; purge that field too.
10. **RESOLVED** — barge-in changes the plan before its first await.
11. **RESOLVED** — lock timing refreshes generator samples.
12. **RESOLVED** — `LOCK` records `retry_of`.
13. **RESOLVED, scoped** — the moderation and pre-play ASR limits are disclosed.
14. **RESOLVED for the cited phrase** — the guard catches the previously reported completion wording.
15. **RESOLVED** — ASR and LLM work run outside the WebSocket receive loop.
16. **RESOLVED** — displaced unexecuted chains produce capacity skips.
17. **RESOLVED** — the primary denominator comes from task annotations, independently of the declined-request heuristic.
18. **RESOLVED** — A1 writes its action phrase and spoken line.
19. **RESOLVED, scoped** — the action-chain pilot limit is explicit.
20. **RESOLVED** — `SessionView.chunks` filters chunks from earlier epochs.
21. **RESOLVED** — partial-start and cancellation cleanup are present.
22. **RESOLVED, scoped** — client clock mapping exists; its accuracy remains unmeasured.
23. **RESOLVED, scoped** — JPEG/PCM transport is disclosed and excluded from M1 qualification.
24. **RESOLVED for wording** — the throughput claim is limited to short runs. The underlying `docs/m0_measurements.md` figures were not inlined, so I cannot verify them independently.
25. **RESOLVED** — old-plan segments remain ineligible while the post-barge-in decision is pending.
26. **RESOLVED** — the client-stamped utterance end is retained.
27. **PARTIAL** — `_evidence_time` searches the painted frames across chunks, but estimates the final frame’s time from its index and nominal duration rather than using a measured paint timestamp.
28. **PARTIAL** — reset drains old chunks, but preserves queued exceptions that can surface in a later session; the rank-PID sweep remains ineffective as in #2.
29. **RESOLVED** — media is evicted after presentation and QC.
30. **RESOLVED** — erasure and barge-in now own separate lock gates.
31. **RESOLVED** — the repair offset of two is labelled as the observed mock-run value.

## New findings

32. **Blocking — `orchestrator.py:_erase_locked`.** A typed forget request calls synchronous `memory.forget()` before stopping playback and dropping queued media. If deletion or `VACUUM` takes time, the browser can present buffered content containing the fact being erased. Stop playback and mark unpresented requests dropped before storage work; perform slow deletion off the event loop, then confirm generator reset.

33. **Major — `orchestrator.py:_erase_locked`.** When recording is enabled, the code unconditionally acknowledges `recordings` as failed and never deletes the recording. An erasure during a recorded E2 session leaves the erasure gate closed and the session unable to continue. Close and delete the recording and temporary media, verify removal, then acknowledge that target.

34. **Major — `orchestrator.py:_run_checks_inner`, `qc/judge.py:VLMJudge.judge`.** QC has no timeout or deadline check; `CheckQuestion.deadline_s` is unused. A stalled VLM or ASR call can indefinitely hold action verification, the next multistep action, repair, and completion of a bounded run. Bound checks by the chain’s remaining deadline, record missed or ineligible checks, and let the session progress.

35. **Major — `director.py:next_script`.** On capability degradation or refusal, `line = line or ...` retains an LLM acceptance such as “好，我挥挥手” while emitting no waving action. The user hears a promise instead of the required oral degradation or refusal. Replace the line with an explicit capability decision message and log that decision.

36. **Major — `director.py:_guard/_claims_completion`.** The regex does not catch completion claims such as “茶我喝光啦”. Such a line can be locked and spoken before any presented-content verdict, violating the completion policy. Restrict pre-verification action speech to controlled intent wording, with completion wording generated only from verified state.

37. **Major — `server/app.py:ws_endpoint`, `orchestrator.py:_guarded`.** A fatal generator-loop error sets `_stop`, but the WebSocket handler remains blocked in `ws.receive()`. The user gets a frozen session and the shared-generator session lock remains held until disconnect. Watch `orch.wait_done()` alongside receives, report the failure, and run cleanup immediately.

38. **Major — `director.py:on_verified/on_barge_in`.** If the user barges in after a request finishes presenting but before QC returns, `on_barge_in` removes existing completion remarks; late QC can then add a new “好了。” while the replacement decision is pending. That stale remark may play before the revised request, and the completed chain is no longer available as a revision target. Defer or suppress completion remarks during barge-in and resolve the pending user decision against the prior chain before releasing them.

The prompt compiler and `docs/m0_measurements.md` were not inlined, so their implementation and numerical claims remain unverified here.

**Verdict: not ready.**