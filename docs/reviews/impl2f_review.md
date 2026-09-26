1. **RESOLVED — round-4 #1 (blocking), `report.py::_check_pairs`.** It now checks both conditions against the registered task, seed, and chain set, including keys missing from both.

2. **RESOLVED — round-4 #2 (major), `scoring.py::_score_chain`; `adjudicate.py::_review_need`.** An early multistep occurrence needs review through its later eligible window before an order failure is accepted.

3. **RESOLVED — round-4 #3 (major), `adjudicate.py::_to_session` and `merge`; `scoring.py::_adjudication_gap`.** Effective chains require an explicit response-onset decision.

4. **RESOLVED — round-4 #4 (major), `adjudicate.py::_reconcile_sweep`.** Claim matching is one-to-one across raters and the arbiter.

5. **PARTIAL — round-4 #5 (major), `memory/store.py::_confirmation_binds`.** Requiring subject, predicate, and value cues fixes the cited bare-value case, but cues can come from different clauses. “我住在北京，我妹妹住在上海” can confirm a pending “my sister lives in Beijing” fact. Match a structured proposition within one clause, or require an affirmative answer to its linked question.

6. **RESOLVED — round-4 #6 (major), `memory/store.py::_physical_purge` and `verify_erased`.** Persistent journals are removed during purge, and record-ID erasure checks captured record text in the raw files before acknowledgement.

7. **NEW — major, `scoring.py::score_session` and `_repair`; `adjudicate.py::prepare`.** RQ2 scores repairs using only verdicts for the chain’s *final* revision, while adjudication prepares only that final intent. If a repair visibly succeeds and the user later revises the chain, the earlier repair can be counted as a failure. Prepare blinded items for each randomized repair target under its assignment-time revision, and score that point against those verdicts.

8. **NEW — major, `scoring.py::rq2_audit` and `_vtime`.** Eligibility is defined at evidence time, but a runner judge verdict has `chunk: 0`, causing `_vtime` to return the first chunk’s start instead of `t_evidence`. A withdrawal or revision during the request can therefore change whether a failure point is audited or assigned. Use `t_evidence` for negative-verdict eligibility.

9. **NEW — major, `report.py::repair_comparison`.** It issues a row labelled “primary” while excluding randomized points whose target request was not fully observed. If unfinished targets occur more often in one arm, the comparison is a selected-subset estimate. Require reruns before the primary RQ2 comparison, and keep an explicitly labelled missing-data sensitivity analysis.

10. **NEW — major, `runner.py::run_task` and `report.py::build_report`.** The live-stack runner sends task text directly to `on_user_utterance`, bypassing the proposal’s TTS → VAD/ASR input path; the reporter can nevertheless issue a primary E2 decision from these `generator_path` logs after adjudication. This omits recognition errors and input-path delay from the measured contrast. Route pilot instructions through the actual audio path, or prevent generator-path logs from receiving an end-to-end E2 primary decision.

**Verdict: not ready.**