You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" research project (see AGENTS.md rules: read-only, challenge claims, numbered findings tagged blocking/major/minor). Checkpoint 2 of 4: LITERATURE SYNTHESIS, CAPABILITY CLAIMS, AND PROPOSED RESEARCH GAP. Reviewed revision: the git commit printed in the meta file (files inlined below).

Inlined: docs/related_work.md (the deliverable under review), docs/backbone_verification.md (code-level audit of LingBot-World 2.0 in vLLM-Omni @7b4dc76), and the synthesis sections of three supporting notes plus the reference-agent note.

Please scrutinize:
1. Capability claims: is any claim about LingBot-World / vLLM-Omni overstated or unsupported by the cited path:line evidence as quoted? Are A/B/C/D classifications sound? Is "camera-only mid-stream control on the public path" adequately supported? Are latency figures properly labelled as upstream-reported vs derived?
2. Hypothesis framing (§1.1): is the refined hypothesis fair to counter-evidence (X-Streamer, Wan-Streamer, LPM, Genie 3)? Is it falsifiable as stated?
3. Gaps G1–G10 and candidate contributions 1–6: which are weak, already solved by cited or well-known work, or merely engineering integration? Name specific prior work that might undercut novelty (e.g. for TVC metric, capability manifests / affordance models, online VLM verification, provenance-typed memory, PACE extension). Which is the strongest defensible contribution?
4. Missing areas or important systems/papers that a reviewer would expect (in any of the six areas: streaming video/world models; multimodal/livestream agents; reasoning/control over generators; memory; orchestration/latency/AV sync; evaluation).
5. The reference-agent treatment: is it appropriately cautious?
6. The comparison matrix: does it include the required fields (approach, capabilities, memory mechanism, control interface, latency+hardware, availability, limitations, relevance, date, URL)? Any row that looks factually suspicious?
7. The implication that the demo should use an "explorer persona with voice-over" rather than a talking head: is this justified, or is it scoping the problem to fit the backbone in a way that undermines the owner's goal of a "digital persona"? Suggest alternatives.
Be concrete and concise.
