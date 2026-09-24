1. **Major — CP4 round 2 #4: PARTIALLY RESOLVED.** §7.3 and §8 limit the “<1%” cross-scope leak claim to text and speech over independent simulated users; the visual channel has no threshold claim. §4 H3b still states an unqualified “cross-scope leak rate below 1%.” Scope H3b and its falsification rule to text and speech.

2. **Minor — #5: RESOLVED.** §7.2 and §8 consistently score final intents and tally superseded intermediate intents separately.

3. **Minor — #6: RESOLVED.** §7.5 now measures pairwise preference and specifies its analysis, matching H4a.

4. **Minor — #7: RESOLVED.** §5.5 and §6.4 now distinguish sustained throughput from jitter tolerance; the 2-GPU, 12-fps case is correctly conditional on measurement.

5. **Minor — #9: PARTIALLY RESOLVED.** §14 no longer claims approval, and PROJECT.md reflects the review rounds. The log nevertheless says round 3 was “Re-reviewed” while it has no round-3 result. Record this verdict and change that retrospective wording.

6. **Minor — new substrate inconsistency: RESOLVED.** §5.1 and D-009 agree: A0 shares the LLM, memory, speech and avatar stack; only A1 and A2 share generator controls.

7. **Major — new qualification mismatch.** §6.4 allows up to 1% of chunks to exceed the gate’s jitter limit, yet §1.3 calls an M0-qualified configuration real-time and §8 targets at most one stall per 10 minutes. At 16 fps, 1% can mean roughly eight late chunks per 10 minutes. The 120-chunk M0 trace also cannot establish that stall target. Require the trace-driven check to meet the stated stall target, or distinguish M0 throughput qualification from stream-stability acceptance.

**Verdict: not ready.** Fix the H3b scope and the M0 qualification rule, then update the review log. PROJECT.md, CLAUDE.md, AGENTS.md, AGENT.md and the decision log otherwise agree with the proposal on the inspected points.