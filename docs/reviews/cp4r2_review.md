**Checkpoint 4, round 2 — review of the supplied text**

1. **[blocking] CP4 #1 — RESOLVED.** §1.2 and §7.4 distinguish strict H-core from the weaker A1−mem ablation and specify a fresh context for each A1−mem session.
2. **[blocking] CP4 #2 — RESOLVED.** §7.2 makes blinded human adjudication the primary A2–A1 outcome and uses a separate, human-validated offline judge for ablations.
3. **[major] CP4 #3 — RESOLVED.** §8 defines TFMR and TFCV, including their start points, judgments and censoring.
4. **[major] CP4 #4 — PARTIALLY.** The pilot addresses task clustering. The proposed 360 leak probes come from only 20 users, however; the rule-of-three calculation assumes independent opportunities and does not establish a clustered 95% upper bound below 1% (§7.3, §8).
5. **[major] CP4 #5 — PARTIALLY.** FCR, claim coverage and TVC censoring are defined. §7.2 excludes user-superseded instructions from success, while §7.2 and §8 both say *all* instructions are in the denominator.
6. **[major] CP4 #6 — PARTIALLY.** The A0+clips comparison, non-inferiority margin and identity measures are specified. H4a requires pairwise preference, but §7.5 does not include a pairwise preference measure or analysis.
7. **[major] CP4 #7 — PARTIALLY.** The gate edge and latency accounting are now explicit. The claimed stall-free condition, \(T+\delta\le(L+1)P\), is insufficient for a sustained stream: if average generation time \(T>P\), an \(L=1\) buffer eventually empties even when that condition holds (§5.5, §6.4). §7.0’s \(T\le P\) gate implicitly recognizes this.
8. **[major] CP4 #8 — RESOLVED.** §5.6 distinguishes unsent work, sent controls, active generator state and already presented media.
9. **[minor] CP4 #9 — PARTIALLY.** D-001 and many count labels are fixed. §14 says the *final* CP4 round is recorded, while the supplied review log contains only the round-one result and says round two was re-reviewed without recording its findings or verdict.

**Additional major inconsistency:** §5.1 and D-009 say A0, A1 and A2 share the generator control substrate, but §5.1 defines A0 as having no world model. State that A1 and A2 share that substrate, while A0 shares the applicable LLM, memory, speech and avatar components. The instruction files otherwise agree on scope and read-only review rules; PROJECT.md’s status line is stale because it says it was updated after checkpoints 1–3.

**Verdict: not ready.** Resolve the clustered leak claim, success denominator, sustained gate criterion and missing H4a preference measure; correct the shared-substrate statement and record this round’s actual review status.