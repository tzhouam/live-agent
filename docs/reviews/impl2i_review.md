### Round-7 findings

1. **RESOLVED** — Pairing checks use the registered expected set.
2. **RESOLVED** — Multistep order failures require observation through the later step’s window.
3. **RESOLVED** — Skipped and refused chains require an adjudicated onset decision.
4. **RESOLVED** — Swept claims are matched one-to-one.
5. **RESOLVED** — Confirmation checks subject and polarity.
6. **RESOLVED** — Physical purge and raw-file verification cover the identified journals and residue.
7. **RESOLVED** — Repair-target labels retain the assignment-time revision.
8. **RESOLVED** — RQ2 eligibility uses evidence time.
9. **RESOLVED** — Repair success requires full target presentation; unobserved targets block the primary row.
10. **RESOLVED** — Injected-input runs cannot receive a primary E2 decision.
11. **PARTIAL** — Verdicts and revisions now follow the served utterance UID, but `convert` still maps `SPEECH_ONSET` and `LOCK` through the director chain’s last ground-truth chain. Those fields are diagnostic.
12. **RESOLVED** — A verdict needs two sufficient primary reviews.
13. **RESOLVED** — Viewer events are rejected outside authenticated public mode.
14. **RESOLVED** — Positive labels require watched coverage up to the marked frame or answer end.
15. **RESOLVED** — Duplicate primary adjudications across batches are rejected, with an explicit replacement path.
16. **RESOLVED** — Paired inference checks the registered annotation sequence and final criteria.

### New findings

17. **Major — [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `observation_end`; [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `_load_ratings`.** A recording can end after 5 seconds of painted media while an `observation_end` event says 20 seconds. Raters can mark “not done” after watching the whole short recording because review coverage is clipped to its end; scoring then trusts the later event and counts a 15-second action failure as fully observed. **Fix:** validate `observation_end` against the last painted chunk, and reject or rerun negative labels whose deadline window lacks presented media.

18. **Major — [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `score_session`; [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `_load_ratings`.** A capacity-skipped chain whose recording ends 2 seconds after the request can receive an adjudicated “no onset” decision and enter TFMR as censored at 15 seconds. The chain’s failure outcome is valid, but its 15-second response window was not observed. Refusals have the same path. **Fix:** retain the failure outcome while requiring full onset-window observation for TFMR, or censor TFMR at the actual observation end and label the missing window.

19. **Major — [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `add_ledger`.** A noncanonical ledger entry accepts `derived_from=()` and a caller-selected public scope. If its text was composed from a private recall, the stored `source_scopes` contain only `public:<stream>`; public retrieval can expose it. **Fix:** require source lineage for learned ledger entries and derive their scope from those sources; reserve empty lineage for explicitly authenticated, operator-authored entries.

20. **Major — [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `_forget_db` and `forget`.** If database deletion succeeds but an external purge fails, retrying by the deleted record ID finds no record. The new report has no original content terms or affected sessions. A session-keyed recording or generator purge can then acknowledge an empty job while the original external copy survives. **Fix:** retain a retriable pending-erasure receipt until every required target acknowledges, and make retries resume that receipt rather than create a new empty erasure.

not ready