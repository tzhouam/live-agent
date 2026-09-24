You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" project (AGENTS.md rules: read-only; numbered findings tagged blocking/major/minor with evidence or the settling check). Checkpoint 4 of 4: EXPERIMENTAL DESIGN AND THE COMPLETE FINAL PROPOSAL. Also re-review whether the CP3 resolutions recorded in docs/codex_reviews.md are actually reflected in the proposal (verify, don't trust the log).

Inlined: docs/research_proposal.md (v1.0-rc), docs/PROJECT.md, CLAUDE.md, AGENTS.md, AGENT.md, docs/decision_log.md, docs/codex_reviews.md, docs/related_work.md, and additional real code excerpts (camera handler target/velocity semantics; ping semantics) from vllm-omni @7b4dc76.

Please assess:
1. Experiments E0(M0)–E6: do they directly test the claimed benefits (H1–H6, H-core)? Baselines/ablations adequate (A0, A1, A1−mem, A2−verify, A2−manifest, A2+unpaced, A2−display-alignment; memory baselines)? Confounds (shared substrate), controls for backbone/hardware/resolution/workload, sample sizes and power reasoning, repeated trials, uncertainty reporting, censoring handling, judge validation, calibration/evaluation leakage.
2. Metrics and success criteria (§8): measurable, well-defined denominators, thresholds justified/labelled as targets? Any that cannot be measured with the described instrumentation?
3. Required evaluation items from the brief: instruction-following & multi-step success; recovery from interruptions/changing instructions; cross-session memory recall, factual precision, correction, forgetting; persona and visual-state consistency over extended interactions; time to first meaningful response AND time to first correctly conditioned visual response; end-to-end p50/p95 latency, streaming stability, compute cost. Is each covered?
4. Labelling discipline: any number presented as a result without [cited]/[derived]/[target]/[estimate]? Any fabricated-sounding claim?
5. Is the scientific contribution clearly separated from engineering integration? Is the proposal self-contained (could a reviewer understand it without the supporting docs)?
6. Consistency: do PROJECT.md, CLAUDE.md, AGENTS.md, AGENT.md, decision_log and the proposal agree? Is the Codex review status accurately reported?
7. CP3 resolution check: list any CP3 finding that is NOT adequately resolved in the text.
Give an overall verdict: ready / ready with minor fixes / not ready. Be concise and concrete.
