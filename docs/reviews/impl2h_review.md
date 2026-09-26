1. **RESOLVED** — `report.py::_check_pairs` checks the registered pair set.
2. **RESOLVED** — `scoring.py::_score_chain` requires observation through the later multistep window before an order failure.
3. **PARTIAL (major)** — `scoring.py::score_session` bypasses onset adjudication for skipped and refused effective chains. An audible refusal can be recorded as no TFMR event. Require an adjudicated onset decision for these chains while retaining their failure outcome.
4. **RESOLVED** — `adjudicate.py::_reconcile_sweep` matches claims one-to-one.
5. **RESOLVED** — `memory/store.py::_confirmation_binds` checks the proposition’s subject and polarity.
6. **RESOLVED** — `memory/store.py::_physical_purge` and `verify_erased` cover persistent journals and raw-file residue.
7. **RESOLVED** — Repair-target adjudication retains the assignment-time revision.
8. **RESOLVED** — `scoring.py::rq2_audit` uses `t_evidence` for eligibility.
9. **RESOLVED** — `scoring.py::_repair` checks full target presentation before success; `report.py::repair_comparison` refuses an unobserved primary row.
10. **RESOLVED** — `runner.py::_main` labels injected-input runs; `report.py::build_report` refuses them as primary E2.
11. **PARTIAL (major)** — `runner.py::convert` maps verdicts by the served utterance, but `gt_revision` still looks up the director chain’s *last* ground-truth chain. If the director merges two ground-truth chains, the first chain loses its revision binding and its RQ2 point fails audit. Compute the ground-truth chain and revision from the same served utterance UID for every event.
12. **RESOLVED** — `adjudicate.py::merge` requires two sufficient primary reviews before accepting a verdict or claim sweep.
13. **RESOLVED** — `memory/store.py::ingest_user_utterance` rejects viewer events outside authenticated public mode.
14. **NEW (major)** — `adjudicate.py::_review_need` and `_repair_to_session`: a positive label needs no watched interval. Two raters can seek to an action frame or an answer’s end, mark “done,” and produce an accepted first-compliance time or content-rubric pass without reviewing the preceding response. Require continuous review from the request to the marked first frame, and through the answer for content.
15. **NEW (major)** — `adjudicate.py::merge` and `scoring.py::score_session`: separate batches can append primary verdicts and claim sweeps for the same session. A later positive verdict can turn an earlier negative chain into success, while repeated swept claims change FCR. Reject duplicate primary adjudications and sweeps per session, with an explicit replacement path.
16. **NEW (major)** — `report.py::expected_pairs` and `pair_problems`: pairing checks `(task, seed, label)` only. If A1 omits a scripted revision while A2 includes it, both pass the pair check although they are scored against different final intents and deadlines. Validate each condition’s annotation sequence and final criteria against the registered task before paired inference.

not ready