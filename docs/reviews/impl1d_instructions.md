You are the independent reviewer (Codex, GPT-6 Sol) for the live-agent project, Phase 2 checkpoint "impl1d" (round 3):
the **implementation of the A2 control path** against the Chinese proposal `docs/research_proposal_zh.md` v2.11
(inlined), plus the TaoMate-H3 generator adapter and its local measurements.

Review goals, in priority order:
1. **Correctness bugs** in the control path: the single timeline (lock → teacher → student → presented),
   just-in-time locking (P_{k+1} = V_k + R − Λ − σ), KV/order constraints, barge-in and erasure (drop unpresented,
   bridging, generator reset), deadlocks and races in the asyncio orchestration, QC → repair → earliest correctable
   request, "done" spoken only after verification, capability gating (emit/degrade/refuse), prompt compilation.
2. **Fidelity to the proposal:** anything the proposal specifies as mandatory for A2 that is missing, or behaves
   differently, or places where the implementation would make a later E2 result invalid (confounds between A1 and A2,
   leakage between the online judge and the primary outcome, mis-timed events).
3. **Adapter** (`taomate_h3.py`, `SessionView`): session isolation, request numbering, stale chunks, error paths,
   resource leaks on shutdown or cancellation.
4. **Honesty of claims** in `docs/implementation.md` and `docs/m0_measurements.md`: is each claim supported by the
   code and the numbers described, are the number labels right, and is anything overstated?

Output format: a numbered list of findings. For each: severity (blocking / major / minor), file and line or function,
the concrete failure scenario, and the fix. Then a one-line verdict: "ready for E1/E2 pilot", "ready after fixes",
or "not ready". Do not praise; do not restate the code. If you find nothing in a category, say so briefly.

This is round 3. Round-2 findings are in the inlined `docs/reviews/impl<N>c_review.md`; resolutions are summarised in
`docs/codex_reviews.md`. First give one line per round-2 finding in your scope (RESOLVED / PARTIAL / OPEN), then NEW
findings only if they are material (blocking or major). Accepted documented limits are fine when the docs narrow the
claim accordingly. End with the verdict line.
