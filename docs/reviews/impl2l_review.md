**Round-10 status**

- Carried #11 — **RESOLVED:** ambiguous director chains without a revision are left unmapped.
- #17 — **RESOLVED:** observation ends are capped by presented media.
- #18 — **RESOLVED:** TFMR can be censored at the observed end without changing a skip or refusal outcome.
- #19 — **RESOLVED:** learned ledger entries require source lineage.
- #20 — **RESOLVED:** the erasure receipt is created in the deletion transaction.
- New #1 — **RESOLVED:** sweep claims are matched by occurrence before referent and truth; three-way disputes remain unresolved.
- New #2 — **RESOLVED:** a pending batch manifest makes an interrupted replacement detectable.
- New #3 — **RESOLVED:** non-user speaker roles are rejected from user-fact ingestion.
- New #4 — **PARTIAL:** erasure selection covers the residue fields, but a restart can lose the terms needed for reselection.

**New findings**

1. **Major — `live_agent/eval/scoring.py`, `score_session`; `live_agent/eval/runner.py`, `convert`.** Refusals have no revision binding. If an old intent is refused after the user finishes a revision, the refusal’s timestamp is after the final clock origin, so refusal precedence marks the *final* chain failed even if that intent is adjudicated compliant. Emit the served revision on refusals and apply only refusals bound to the final revision; treat an unbound refusal on a revised chain as an adjudication gap.

2. **Major — `live_agent/eval/runner.py`, `run_task.send`.** The runner gives `Utterance` one endpoint timestamp, awaits `orch.on_user_utterance`, then records a later endpoint in the ground-truth log. A condition-dependent wait moves the scoring origin later; `--speed` amplifies the error and can turn a deadline miss into success. Capture the utterance endpoint once, before the orchestration await, and use it in both places.

3. **Major — `live_agent/memory/store.py`, `record_inference`.** An inference with `derived_from=[]` and `scope="public:<stream>"` is accepted even when it contains a private user fact. It is stored in public scope and can be returned by public retrieval with `include_pending=True`. Require source lineage for learned inferences, derive their scope from those sources, and reject a public write when provenance is incomplete.

4. **Major — `live_agent/memory/store.py`, `correct`.** Correction requires neither an authenticated confirming user turn nor an `own_assertion` source. Correcting a public `viewer_claim` creates a new public record labelled as a user `own_assertion`, giving it false provenance and higher conflict priority. Require an authenticated user episode tied to the owner and restrict this path to eligible user assertions; use a separate typed path for system corrections.

5. **Major — `live_agent/memory/store.py`, `_resume_report` / `recover_interrupted`.** After a restart, `_RECEIPT_CONTENT` is gone. A receipt with `memory_db` still pending resumes with no terms, texts or vectors; reselection does nothing, and ID-only verification can acknowledge the database while an unlinked term-bearing record survives. Keep such a receipt pending until the erasure query is restored or an exhaustive purge and content-aware verification can be performed.

**Verdict: not ready.**