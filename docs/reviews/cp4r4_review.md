1. **Round-3 H3b scope — RESOLVED.** §4, §7.3 and §8 limit the <1% claim to text and speech at the user level; generated visuals have no threshold claim.
2. **Round-3 review-log wording — RESOLVED.** The log records the round-3 verdict and uses “Re-review → cp4r4” without claiming that round 4 has occurred.
3. **Round-3 qualification versus stall target — RESOLVED.** §6.4 makes M0 a candidate throughput gate and requires an M1 soak test against the stall target before calling a configuration real-time.

4. **Major — H3b’s text-channel test is not operationally consistent.** §7.3 defines text leakage as OCR of the *displayed stream*, but describes the ≥300-user test as cheap at the memory-and-LLM level and reserves world-generator testing for ≈30 users. Specify how displayed text is produced and checked for all ≥300 users, or narrow the statistical claim to an output channel actually tested at that scale.
5. **Minor — The RQ4 row in §4’s Markdown table spans raw line breaks.** Put the row on one line or use formatting that preserves all four columns.

**Verdict: not ready.** Resolve finding 4, then fix the RQ4 table.