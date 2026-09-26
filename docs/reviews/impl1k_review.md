Round-9 status:

- **#1 RESOLVED** — A check that times out at or returns after the action deadline now expires the step.
- **#2 RESOLVED** — An interrupted A1 request retains its action and line, and its dropped request is removed from the chain’s closure list.
- **#3 RESOLVED** — The repeat and gradient arms now carry the same spoken line.
- **#4 RESOLVED** — Warmup has a timeout, and startup failure closes the partial adapter.

New findings:

1. **Major — [orchestrator.py](/data/zhoutaichang/live-agent/live_agent/orchestrator.py), `_run_checks_inner`; [director.py](/data/zhoutaichang/live-agent/live_agent/director/director.py), `expire`.** If too few frames were painted, QC returns without a verdict. A timely `UNKNOWN` verdict also causes neither verification nor repair; `CorrectionMode.NONE` leaves a failed check similarly open. There is no later deadline transition, so a multistep chain can remain `OPEN` indefinitely and hold its next step. Schedule an independent step-deadline expiry, and make every abstention or no-repair path reach a terminal state by that deadline.

2. **Major — [director.py](/data/zhoutaichang/live-agent/live_agent/director/director.py), `on_verified`; [orchestrator.py](/data/zhoutaichang/live-agent/live_agent/orchestrator.py), `_repair`.** A user can give an unrelated new instruction after an old request finishes presenting but before its QC returns. The old chain is not capacity-skipped because it has no queued segment. A late positive verdict then puts its “好了。” ahead of the new instruction, delaying the new response; a negative verdict labels the already-presented old chain a *capacity skip*. Bind post-QC speech and retry decisions to the current instruction epoch. Record the old chain’s actual outcome without inserting speech ahead of the new plan or classifying executed work as skipped.

3. **Major — [director.py](/data/zhoutaichang/live-agent/live_agent/director/director.py), `purge`; [orchestrator.py](/data/zhoutaichang/live-agent/live_agent/orchestrator.py), `_on_user_utterance`, `_erase_locked`.** `purge` omits `interrupted` and `deferred` segments. If a forget decision becomes stale after a second barge-in, erasure is still honoured without applying the first decision; an interrupted A1 segment can retain the erased line while erasure reports controller purge complete. A later chat decision can resume that segment. Purge these stores before acknowledging `unsent_scripts`, and terminate or rebuild affected chains from clean state.

No additional major adapter finding is established from the inlined code. The prompt compiler, capability manifest implementation, and `docs/m0_measurements.md` were not inlined, so their claims cannot be independently re-audited here.

**Verdict: not ready.**