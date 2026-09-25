**Zh6 finding: RESOLVED.** §1.2 and §6.4 now agree: E2 and E5 proceed under the near-real-time service rule if the M2 whole-system test fails, and their results carry that label.

1. **major — RQ3 still assumes a fixed request cadence.** §4 says H3a tests TVC against the §6.4 model, which assumes locks every 5 seconds. The turn-based fallback has no such cadence, yet §7.2 still assigns RQ3 to E2. Make H3a conditional on real-time qualification, or specify a separate prediction and analysis for fallback runs.

2. **major — fallback skips need an outcome rule.** §1.2 records pending instructions displaced by newer ones as “skipped,” while §7.2 scores only the final intent. Under admission control, that can conceal instructions the system dropped because it was overloaded. Distinguish explicit user withdrawal from capacity-driven skips, and report the latter by condition with a defined denominator.

**Verdict: not ready.** No remaining blocking issue found in the inlined text.