## Round-2 finding status

1. **R1 #1 RESOLVED** — Primary scoring requires adjudicated verdicts; judge scoring is labelled diagnostic.
2. **R1 #2 RESOLVED** — Untimed negative verdicts can be merged and scored.
3. **R1 #3 RESOLVED** — Criteria are shown to raters; scripted speech onset cannot pass the primary content gate.
4. **R1 #4 PARTIAL** — `runner.convert` uses explicit judged chain IDs, but its director-to-task mapping can still conflate distinct chains.
5. **R1 #5 RESOLVED** — Primary FCR uses an adjudicated sweep of recorded audio.
6. **R1 #6 RESOLVED** — Capacity skips are emitted and take failure precedence.
7. **R1 #7 RESOLVED** — The default primary report rejects insufficient observation.
8. **R1 #8 PARTIAL** — Repair evidence time is logged, but the inlined code does not establish that eligible failure points were predefined or that every logged assignment was randomized.
9. **R1 #9 RESOLVED** — Holm families are fixed; FCR and coverage have task-clustered intervals.
10. **R1 #10 RESOLVED** — The runner requests the session view’s seed for its header.
11. **R1 #11 RESOLVED** — Media are delivered under random names, without symlinks, and checked for revealing identifiers.
12. **R1 #12 RESOLVED** — The bridge requires a fixed session mode at construction.
13. **R1 #13 PARTIAL** — Public lineage still depends on a caller’s unverified `complete` or `none` assertion.
14. **R1 #14 OPEN** — `MemoryStore.confirm` still activates a pending echo without a confirming user turn.
15. **R1 #15 PARTIAL** — The cascade and similarity sweep are present, with the cross-lingual limit documented; physical-file verification is still optional.
16. **R1 #16 RESOLVED** — Short runs are labelled diagnostics, not M1 qualification.
17. **R2 #1 RESOLVED** — Unobserved deadline windows block the default primary report.
18. **R2 #2 PARTIAL** — Negative-label review checks the furthest video position reached, not coverage of the intervening interval.
19. **R2 #3 PARTIAL** — Mode is fixed, but caller-asserted empty public lineage remains possible.
20. **R2 #4 RESOLVED** — Media delivery and the batch scan address path-based unblinding.
21. **R2 #5 RESOLVED** — Changed merge inputs conflict unless replacement is explicitly requested.
22. **R2 #6 RESOLVED** — Content deadlines use utterance end plus 15 seconds plus the registered duration; onset/end order is checked.
23. **R2 #7 PARTIAL** — Claim evidence must precede the claim, but full review still relies on the furthest-position check.
24. **R2 #8 PARTIAL** — Withdrawn chains retain repair assignments, but a target-request success can override withdrawal.
25. **R2 #9 RESOLVED** — Success curves are separated by kind and deadline, with failures retained in the denominator.
26. **R2 #10 RESOLVED** — Correction retirement and insertion run in one transaction.
27. **R2 #11 RESOLVED** — The throughput statement is limited to a short run; M1/M2 gates remain open.

## New material findings

1. **Blocking — `live_agent/eval/report.py`, `_paired` and `compare`.** A missing A1 task, seed, or chain is silently dropped from pairing, yet the report can still issue an H1a decision. With only one task cluster, bootstrap draws repeat that task and can even produce a zero p-value for a positive difference. **Fix:** require the preregistered pair set to be complete before a primary decision, reject duplicate pair keys, and suppress inferential decisions below a preregistered minimum number of independent tasks.

2. **Major — `live_agent/eval/scoring.py`, `_score_chain`; `live_agent/eval/adjudicate.py`, `_review_need`.** In a multistep task, step 2 seen only *before* step 1 causes immediate `order_fail`. A recording that ends just after step 1 can therefore be scored as a definite failure even though step 2 still has 15 seconds to occur; a positive early step-2 label needs no review through that later deadline. **Fix:** treat early step-2 compliance as nonqualifying evidence, require review through step 1’s compliance time plus 15 seconds, and mark shorter recordings insufficiently observed.

3. **Major — `live_agent/eval/adjudicate.py`, `prepare` and `merge`; `live_agent/eval/scoring.py`, `score_session`.** Raters mark on-topic speech onset only for content items. Action and multistep chains can have a meaningful spoken response, but primary TFMR records no adjudicated onset for them and censors them at 15 seconds. **Fix:** collect an adjudicated meaningful-response onset decision for every effective chain, including an explicit “none by deadline” decision.

4. **Major — `live_agent/eval/adjudicate.py`, `_reconcile_sweep`.** One arbiter claim can be reused to accept multiple unmatched claims from the primary raters. For example, two nearby one-rater marks and one arbiter mark produce two adjudicated completion claims for one audible statement, changing FCR’s denominator. Matching also omits the intent revision. **Fix:** reconcile claims one-to-one across all three raters, including referent revision, and emit each accepted audible claim once.

5. **Major — `live_agent/eval/scoring.py`, `_repair`.** `ok` is checked before `ch.withdrawn`. If a user withdraws after randomization but a previously locked target request later plays compliant content, RQ2 records a success although its stated primary rule counts post-assignment withdrawal as failure. **Fix:** apply the preregistered withdrawal rule before testing target-request success, using assignment, withdrawal, and compliance times.

6. **Major — `live_agent/memory/store.py`, `forget` and `verify_erased`.** The store acknowledges `memory_db` after a logical check with `raw_file=False`. If the SQLite database is in WAL mode, an older WAL frame can retain erased text after the rows disappear, while erasure is reported complete. **Fix:** flush and truncate the WAL or rebuild the database, then verify the relevant database and journal files before acknowledging physical erasure.

**Verdict: not ready.**