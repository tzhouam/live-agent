## Round-2 findings in scope

1. **RESOLVED** — `orchestrator.py:stop/_maybe_finish` drains pending QC before ending a bounded run.
2. **RESOLVED** — `director.py:on_verified` binds verdicts to the current revision and step.
3. **RESOLVED, scoped** — multistep action gating is present; the documented pilot scope excludes content chains.
4. **PARTIAL** — `orchestrator.py:_erase` fails closed and waits for worker reset, but retained `BlockScript.corrections` are not redacted; late stale media can also remain in shared memory.
5. **RESOLVED** — barge-in pauses locking and changes the plan before its first await.
6. **PARTIAL** — `timeline.py:effective_leads` separates teacher time from KV wait, but `orchestrator.py:_chunk_loop` can copy a timing before `REQUEST_DONE` supplies `t_done`; it never refreshes that sample.
7. **PARTIAL** — `director.py:_pop_segment` reserves the repair slot, but the `LOCK` event omits `retry_of`, so the log does not explicitly identify the request that carried it.
8. **RESOLVED, scoped** — the missing moderation gate and pre-play ASR are disclosed as open limits.
9. **PARTIAL** — the example completion phrase is caught and silent claims are suppressed, but `director.py:_claims_completion` misses ordinary claims such as “我把茶喝了”.
10. **RESOLVED** — the WebSocket receive loop remains available during ASR and LLM work.
11. **RESOLVED** — displaced unexecuted chains receive capacity-skip events.
12. **PARTIAL** — calibrated status is the default gate, but `director.py:_declined_request` creates a refusal chain only when its request regex matches *and* the LLM uses a recognized decline. Other misclassified action requests can disappear from the scoring denominator.
13. **RESOLVED** — A1 writes its action phrase and line without A2’s manifest or QC.
14. **RESOLVED, scoped** — the action-chain pilot limit is stated.
15. **RESOLVED** — `SessionView.chunks` filters reset epochs.
16. **RESOLVED** — partial startup cleanup and unconditional session-lock release are implemented; cancellation during adapter shutdown is a separate finding below.
17. **RESOLVED, scoped** — clock mapping is present and its accuracy remains unmeasured.
18. **RESOLVED, scoped** — JPEG/PCM transport is disclosed and excluded from M1 qualification.
19. **RESOLVED for wording** — the short-run throughput claim is qualified. `docs/m0_measurements.md` and raw measurements were not inlined, so its figures cannot be independently checked here.
20. **PARTIAL** — stale LLM decisions are discarded by epoch, but `orchestrator.py:on_user_utterance` still counts a discarded decision toward the post-interruption restart wait. An old queued segment can lock before the new utterance is processed.
21. **RESOLVED** — client-stamped utterance end is carried through ASR and the input queue.
22. **PARTIAL** — QC receives painted frames, but `on_presented/_run_checks` uses nominal chunk end as evidence time rather than the last painted frame’s time. This can misidentify the earliest correctable request.
23. **PARTIAL** — adapter prompts and queued output are cleared and both workers acknowledge reset; late stale shared-memory payloads are not cleaned up.
24. **RESOLVED** — decoded media is evicted after presentation and QC.

## New material findings

1. **Blocking — `director.py:_open_chains`, `orchestrator.py:_run_checks_inner`.** A1 never runs QC, and presentation never closes its action chains. Completed A1 instructions therefore remain “open” in every later responder prompt; a later request may be treated as a revision of a stale chain, changing the effective-intent denominator and confounding A2 versus A1. Close A1 chains when their planned segments have been presented, using a lifecycle rule independent of compliance judgment.

2. **Major — `taomate_h3.py:_on_message`, `taomate_worker/protocol.py:to_shm/from_shm`.** A worker can create a `/dev/shm` file for a chunk just before reset. If its message arrives afterward, `_on_message` rejects the stale session before `from_shm` unlinks the file. Repeated interruptions or erasures can retain private media and fill shared memory. Unlink payloads on every stale-message path, including error and shutdown paths.

3. **Major — `orchestrator.py:_repair`, `director.py:queue_retry`.** The RQ2 `REPEAT` arm queues an action with an empty spoken line; the original request contained that line. It therefore tests a changed audio teacher input and prompt, rather than repetition of the original instruction. Preserve the original action and line for the repeat arm, and log the actual retry prompt for both arms.

4. **Major — `ledger.py:bridging_note`, `orchestrator.py:_drop_unpresented`.** After a partial barge-in, the generator may continue from unseen action or speech. The ledger records only request numbers for this divergence; the next prompt uses a generic posture sentence and clears the marker before that bridge is presented. An unseen action can still influence later video without an explicit, auditable reconciliation. Record the generated but unpresented action and speech, retain the divergence until a bridge is presented, and measure the resulting seam—or reset the generator.

5. **Major — `taomate_h3.py:close`.** If shutdown is cancelled while awaiting `proc.wait`, cleanup exits before terminating workers or closing channels and the listener. Put bounded process termination and resource closure in cancellation-safe cleanup, then re-raise cancellation.

**Verdict: not ready.**