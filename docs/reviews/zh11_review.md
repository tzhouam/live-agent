**zh10: RESOLVED.** §5.4 starts the correction clock when the last required frame has been presented and assigns the correction to the first request whose prompt lock can accept it. §4, §7.2, and §8 consistently refer to that earliest eligible request.

1. **major — The primary success deadline remains undefined for most E2 tasks.** §1.3 requires compliance by \(D\), and §7.2 censors failures at \(D\), but §8 gives a 15-second deadline only for action TVC. Content, multistep, and changing-intent tasks have no specified \(D\) or clock origin. Define these before evaluation, identically for A1 and A2; otherwise RQ1’s primary success rate is not reproducible.

2. **minor — Use actual presentation timestamps in §5.4’s calculation.** \(E=V_k+(c+1)\Delta\) assumes equal, uninterrupted block durations, while §1.1 lists unequal blocks and §1.2 allows slower playback. The stated definition of \(E\) is correct; the formula and worked example should be marked illustrative or replaced with measured last-frame times.

**Verdict: not ready** until finding 1 is fixed.