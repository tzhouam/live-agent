1. **RESOLVED — round-5 #1:** `report.py::_check_pairs` checks the registered pair set, including keys absent from both conditions.
2. **RESOLVED — round-5 #2:** Multistep order failures require review through the later eligible window.
3. **RESOLVED — round-5 #3:** Effective chains require an adjudicated response-onset decision.
4. **RESOLVED — round-5 #4:** Claim matching is one-to-one across raters and arbiter.
5. **PARTIAL — round-5 #5, major, `memory/store.py::_confirmation_binds`:** The cues now occur in one clause, but they do not establish the subject. “我妈妈住在北京” can confirm a pending fact that *I* live in Beijing: `我`, `住`, and `北京` all match. Parse the proposition’s subject and polarity, or require an affirmative answer to its linked question.
6. **RESOLVED — round-5 #6:** Purge removes persistent journals, and record-ID erasure checks captured text in raw files.
7. **RESOLVED — round-5 #7:** Repair targets are adjudicated and scored against the assignment-time revision.
8. **RESOLVED — round-5 #8:** RQ2 eligibility uses `t_evidence`.
9. **PARTIAL — round-5 #9, major, `scoring.py::_repair` and `report.py::repair_comparison`:** A target with one presented chunk can receive a `complied` label. `_repair` returns `success` before checking whether every target chunk was presented, so the primary RQ2 row includes that unfinished target while excluding unfinished failures. Require full target observation before accepting success or issuing the primary row.
10. **RESOLVED — round-5 #10:** The shipped runner labels text-injected runs `simulation` or `generator_path`; the report refuses them an end-to-end primary E2 decision.

11. **NEW — major, `runner.py::convert`:** If the director merges two ground-truth chains, `dchain_to_gt` retains the last chain. A refusal for the first instruction is then assigned to the second chain; `gt_revision` also loses the first chain’s revision, excluding its RQ2 point at audit. Map each event through the utterance and revision it served, and carry that binding on refusals.
12. **NEW — major, `adjudicate.py::merge` and `_reconcile_sweep`:** When either primary rater has insufficient review, a single sufficiently reviewed arbiter can supply the chain verdict or the entire claim sweep. The resulting primary label has only one complete independent assessment. Require two sufficiently reviewed independent labels for every accepted item; otherwise leave it unresolved for relabelling.
13. **NEW — blocking, `memory/store.py::ingest_user_utterance` (via `memory_bridge.py::on_user_utterance`):** A private session with a `stream_id` routes an utterance tagged `viewer:<id>` to `ingest_viewer_chat`, which writes its text into `public:<stream_id>` despite the session’s private mode. Reject viewer events outside authenticated public mode and derive the speaker role from that mode, not the utterance field.

not ready