You are the independent reviewer (Codex, GPT-6 Sol) for the live-agent project, Phase 2 checkpoint "impl2c" (round 2):
the **evaluation harness and the memory service** against the Chinese proposal `docs/research_proposal_zh.md`
v2.11 (inlined).

Review goals, in priority order:
1. **Scoring validity:** intent chains (new / revision / withdrawal), effective-chain denominator, deadline table D,
   outcome precedence, capacity skips and refusals as failures, FCR and claim coverage, Kaplan–Meier with censoring,
   Wilson / Clopper–Pearson / clustered bootstrap / Holm. Anything that would bias A2 vs A1 or let the online judge leak
   into the primary outcome.
2. **Runner and converter** (`runner.py`): the orchestrator → SCHEMA mapping (chains by utterance uid, time rescaling,
   verdict fields, speech onset, completion claims), paired seeding, the live-stack mode.
3. **Blinded adjudication** (`adjudicate.py`): blinding, time mapping, merge semantics.
4. **Memory:** provenance typing, scope filtering before ranking, echo detection, bi-temporal correction, erasure
   cascade and verify_erased. Any path where a private fact can reach a public scope or survive erasure.
5. **Honesty of claims** in `docs/implementation.md`.

Output format: a numbered list of findings. For each: severity (blocking / major / minor), file and function, the
concrete failure scenario, and the fix. Then a one-line verdict: "ready for E1/E2 pilot", "ready after fixes", or
"not ready". Do not praise; do not restate the code.

This is round 2. Round 1 findings and their resolutions are summarised in the inlined `docs/codex_reviews.md`
(section "Phase 2") and `docs/implementation.md` ("Known deviations"). First state for each round-1 finding in your
scope whether it is RESOLVED, PARTIAL or OPEN (one line each), then list any NEW findings in the same format.
Accepted documented limits are acceptable if the docs make the claim narrower accordingly.
