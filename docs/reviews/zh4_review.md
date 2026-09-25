### zh3 item check

| Item | Status | Evidence in v2.3 |
|---|---|---|
| Carried zh2 #1 | RESOLVED | §5.4 includes the presentation slot, KV dependency, and immediate locking. |
| Carried zh2 #2 | RESOLVED | §5.4 includes the full correction chain and places no cap on request \(j\). |
| Carried zh2 #3 | RESOLVED | §5.3 shows the compiled H3 prompt and limits its speech guarantees. |
| Carried zh2 #4 | RESOLVED | §7.3 has four memory arms and full listening review of probe audio. |
| Carried zh2 #5 | PARTIALLY | Seven arms are present, but one comparison remains confounded (finding 1). |
| Carried zh2 #6 | RESOLVED | §5.2 specifies per-axis updates, canon-preserving arms, and a frozen evaluation policy. |
| Carried zh2 #7 | RESOLVED | §2.1 identifies VQQA’s local CogVideoX evaluation. |
| Carried zh1 #9 | RESOLVED | The abstract lists state beyond KV and marks 0.68× as derived. |
| zh3 #3 | PARTIALLY | M1 now owns qualification, but §8 still requires an M0 measurement that §6.4 says M0 cannot make (finding 2). |
| zh3 #4 | RESOLVED | §5.3 states the speech limits, proposed check, and fallback. |
| zh3 #7 | RESOLVED | A0 is restored in §5.1 and RQ6. |
| zh3 #8 | RESOLVED | §1.2 defines turn-taking, admission control, and waiting-time measurement. |
| zh3 #9 | RESOLVED | The separate 17.29 s benchmark, derived 0.68× figure, and VQQA generator are identified. |

### Findings

1. **Major — RQ4 attribution remains confounded.** In §7.4, arm 4 gets targeted textual correction, while arm 5 gets randomly inserted restatements. Matching frequency does not isolate the ledger’s effect. Apply the same drift detector, correction rule, and timing to both arms, changing only ledger access.

2. **Major — The qualification measurements conflict.** §6.4 says M0 cannot measure end-to-end \(\Lambda\), yet §8 conditions TVC and TFMR targets on “M0 measured \(\Lambda \le 3\) s.” Also, §7.0 asks M0 to measure teacher–student co-resident memory on a released path that runs them sequentially. Move the \(\Lambda\) condition to M1 and specify a separate co-residency harness or measure it after T2.

3. **Major — The full demo has no realtime requalification gate.** §9 puts the speech chain and A2 controller in M2, after M1’s client playback soak test. §1.2 uses M1 qualification for the first live-agent demo, but those later components can change latency and contention. Requalify the assembled system after M2, or limit the M1 realtime claim to the generator and playback path.

4. **Minor — Clarify the RQ3 criterion and labels.** §8’s “LTX only descriptive” should specify *cross-backbone* comparison; §4 proposes an inferential within-LTX granularity test. Mark the `1–3` question and clip counts in §§5.2–5.5 as targets. The title and §12 still say v2.0 while the revision note says v2.3.

**Verdict: not ready.** No new blocking issue, but finding 3 is a new major issue and the two partial resolutions remain material.