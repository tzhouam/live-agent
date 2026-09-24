# Literature review: long-term memory, personalization, and evaluation for a real-time personalized live agent

Scope: areas 4 (memory and personalization) and 6 (evaluation) of the live-agent proposal. The target system is an interactive digital persona that streams generated video and speech, follows instructions, reasons, and keeps useful long-term memory across sessions. It serves two settings: 1:1 personalized sessions and public livestreams, so private and public memory must be kept apart.

Compiled 2026-09-25. BibTeX: `bib_memory_eval.bib`. Citation keys appear in brackets, e.g. [packer2023memgpt].

## 0. How this was verified (read first)

- **arXiv metadata** (title, authors, first-posted date, and the comment field giving the venue) was pulled programmatically from the arXiv API for every arXiv item, 105 papers in total. Titles, dates, and author lists in the bib file come from that API. They were not typed from memory.
- **Numbers** are quoted only from one of these sources: (i) the paper's own abstract (API), (ii) the paper's HTML or PDF, which I read or grepped (marked *[paper]*), or (iii) a primary vendor page (marked *[vendor]*). Vendor numbers are self-reported and have **not** been independently reproduced.
- **Venues** come from the arXiv comment field or a Crossref DOI lookup. Items without a venue are **preprints**. Many 2026 items are recent unreviewed preprints and should be treated as provisional (marked *[preprint-2026]*).
- **Not directly verified:** the OpenAI blog pages returned HTTP 403, so their dates come from secondary reporting and are marked. The GDPR Art. 17 page fetch failed, so the legal summary below is from general knowledge; the text should be re-checked against EUR-Lex before any legal claim goes in the proposal. The Gemini "Personal Intelligence" date comes from secondary reports (Bloomberg, TechCrunch).
- **Metadata oddity:** arXiv 2608.00009 (AgentMemBench) and 2608.02613 (MemArena) show a "published" date earlier than their ID month. Cite them with care; they are not used for any key claim.

---

## 1. Executive synthesis

### 1.1 What existing memory systems solve

1. **Storage beyond the context window is solved as engineering.** Four designs are established:
   - OS-style tiers: MemGPT/Letta [packer2023memgpt].
   - Memory streams with reflection: Generative Agents [park2023generativeagents].
   - Extract-then-reconcile pipelines with ADD/UPDATE/DELETE/NOOP: Mem0 [chhikara2025mem0], learned in Memory-R1 [yan2025memoryr1].
   - Graphs: Zep/Graphiti with bi-temporal validity [rasmussen2025zep], HippoRAG 1/2 [gutierrez2024hipporag; gutierrez2025hipporag2], and A-MEM Zettelkasten links [xu2025amem].

   All of these beat naive truncation on conversational QA.
2. **Simple baselines are competitive, and the benchmarks are partly saturated.**
   - On LoCoMo, a **full-context** baseline (72.90% J) beat Mem0 (66.88%) and Mem0^g (68.44%) in Mem0's own paper *[paper]*.
   - Letta reports 74.0% on LoCoMo by storing history in files and letting a gpt-4o-mini agent grep them *[vendor]*.
   - Zep and Mem0 publicly disputed each other's LoCoMo setups *[vendor]*.
   - MemoryArena (ICML 2026) shows that agents near saturation on LoCoMo "perform poorly" once memory has to drive later actions [he2026memoryarena].
   - **Implication:** LoCoMo accuracy alone cannot be the headline result for the proposal.
3. **Cost and latency are now first-class concerns.**
   - Mem0 reports 91% lower p95 latency than full context: 1.44 s vs 17.12 s *[paper]*.
   - LightMem (ICLR 2026) moves consolidation to "sleep-time" offline updates [fang2025lightmem].
   - The serving-cost benchmark "Total Recall at What Cost?" finds that no system wins on both accuracy (21–54%) and cost, and that break-even against full transcript "never" arrives within 400 turns for the most expensive system [pollertlam2026totalrecall] *[preprint-2026]*.
   - Commercial assistants run consolidation in the background: ChatGPT "Dreaming" (June 2026, secondary reporting); LangMem "subconscious" background extraction.

### 1.2 What remains open

1. **Updates, corrections, and forgetting are the weakest competency across benchmarks.**
   - MemoryAgentBench: selective-forgetting multi-hop is capped at about 28% for every method [hu2025memoryagentbench] *[paper]*.
   - GroupMemBench: knowledge-update accuracy is 27.1% for the best system [yang2026groupmembench].
   - Memora introduces FAMA to penalize reuse of invalidated memories and finds that such reuse is frequent [uddin2026memora].
   - HaluMem: hallucinations are generated and accumulated in the extraction and update stages, not only at answer time [chen2025halumem].
2. **Deleting a memory record does not mean the information is forgotten.**
   - K-Bench: when the secret sits in the prompt or retrieval store, TOFU- and MUSE-style metrics report no leak, yet deployed agents leak on 22–86% of queries [yu2026kbench] *[preprint-2026]*.
   - Execution-state unlearning: deleting the plaintext memory "leaves leakage unchanged", because summaries, plans, and KV caches derived from the fact persist [yao2026executionunlearning] *[preprint-2026]*.
   - GateMem: no method achieves strong utility, access control, and reliable forgetting at the same time in shared-memory settings [ren2026gatemem] *[preprint-2026]*.
   - This bears directly on GDPR-style erasure requests and on public/private separation.
3. **Persistent memory is an attack surface.**
   - Documented attacks: PoisonedRAG [zou2024poisonedrag], AgentPoison [chen2024agentpoison], MINJA (query-only injection) [dong2025minja], MPBench [dash2026mpbench], and the SpAIware demonstration against ChatGPT memory (2024; Rehberger; secondary sources).
   - In a public livestream, **any viewer is a potential writer** to memory, so provenance-gated writes are mandatory.
   - CAPTURE shows that recency- and provenance-only rules cannot fully separate genuine preference drift from poisoning [hossain2026capture] *[preprint-2026]*.
4. **Long context is not reliable memory.**
   - Lost in the Middle [liu2023lostmiddle] shows U-shaped position sensitivity.
   - RULER: only about half of the models claiming ≥32K context hold up at 32K [hsieh2024ruler].
   - NoLiMa: at 32K, 11 of 13 models drop below 50% of their short-context baseline, and GPT-4o falls from 99.3% to 69.7% [modarressi2025nolima].
   - LongMemEval: 30–60% drops for long-context LLMs relative to oracle evidence, and commercial ChatGPT memory drops 37% [wu2024longmemeval] *[paper]*.
   - BEAM (up to 10M tokens): 1M-context LLMs struggle as dialogues lengthen [tavakoli2025beam].
5. **Visual world-state memory is a different problem from user memory.** Video world-model memory (WorldMem, Context-as-Memory, VMem, RELIC, Matrix-Game 3.0, Genie 3) is about **scene and entity consistency on revisits**. It uses camera-pose-indexed frame retrieval, surfels, point clouds, or compressed KV tokens. It carries no semantics of user facts, consent, or provenance.
   - The generated-video "memory" in a KV cache is itself fragile: WorldTrace shows that KV caches become unaddressable beyond the training horizon because of RoPE offsets [wu2026worldtrace].
   - R2M-Bench shows that naive revisit similarity is confounded by slow motion [gu2026r2mbench].
   - For a talking persona, the relevant visual memory is **identity and appearance consistency**: character-addressable memory such as SlotMem [liu2026slotmem], and Live Avatar's >10,000 s drift-free streaming claim [huang2025liveavatar]. Scene revisits matter less.

### 1.3 Open problems specific to a live multimodal persona

These are the proposal's research opportunities.

- **P1. Write policy under a latency budget.** Decide what is written synchronously in the hot path and what goes to asynchronous consolidation. The trade-off: the hot path is fresh but adds latency; background consolidation is cheap but stale. LangMem documents this trade-off qualitatively; LightMem and "Dreaming" push work offline. No benchmark measures **time-to-availability** of a memory, meaning the turns or seconds between an utterance and its retrievability, jointly with speech and video latency.
- **P2. Epistemic status of memories.** Separate *user-asserted facts*, *agent-inferred beliefs* (e.g., "user seems to like jazz"), *agent-generated events* (what the persona said, showed, or promised on stream), and *third-party or viewer claims*.
  - Generative Agents already documented "hallucinated embellishments" in memory [park2023generativeagents] *[paper]*.
  - HaluMem, MemSyco-Bench [xiang2026memsycobench], and OP-Bench [hu2026opbench] measure extraction hallucination, memory-induced sycophancy, and over-personalization.
  - No benchmark tests whether a system can *answer "who said this, when, and how sure are we?"* for every memory.
- **P3. Public/private scoping.** Keep 1:1 memories out of public streams, keep viewer A's data away from viewer B, and keep the persona's own canon apart from both.
  - GateMem (multi-principal access control plus deletion) and GroupMemBench (per-speaker belief tracking) are the closest existing benchmarks. Neither covers a broadcast setting in which the audience is partly anonymous and adversarial.
  - Commercial analogues: Claude project-scoped memory plus Incognito (2025-09-11); Gemini Temporary Chat (2025-08); ChatGPT temporary chat.
- **P4. Verifiable correction and forgetting.** After "forget X" or "actually I moved to Berlin", all derived artifacts must reflect the change: summaries, profile, graph edges, persona self-narrative, cached prompts or KV, and even generated visual content.
  - Execution-state unlearning [yao2026executionunlearning] and agentic unlearning [wang2026agenticunlearning] give formal starting points.
  - Graphiti's bi-temporal invalidation keeps a history of the fact. For erasure that history must be purged too; for correction it should be kept. That tension is not resolved in the literature.
- **P5. Multimodal and streaming memory.** Mem-Gallery [bei2026memgallery], H2HMem [zhu2026h2hmem], and MIRIX (screenshots) [wang2025mirix] start to cover images, but none is livestream-native with real-time chat, audio, and generated video. LiViBench [wang2026livibench] covers *understanding* of livestream video and comments, not memory.
- **P6. Consistency of the persona itself.** This has three layers: textual persona consistency (DNLI, PICon, InCharacter), visual identity (ArcFace similarity over long streams), and voice identity. All three must hold across sessions and must stay consistent with what the persona *remembers having done*.

### 1.4 Benchmarks to reuse and what must be built (summary; details in §5)

- **Reuse as-is (component level):**
  - Memory: LongMemEval_S/M; LoCoMo only with caveats and alongside a full-context baseline; MemoryAgentBench (selective forgetting); PersonaMem and PrefEval (personalization); HaluMem (hallucination); OP-Bench and MemSyco-Bench (over-personalization and sycophancy).
  - Spoken interaction: Full-Duplex-Bench v1/v1.5/v2 and Talking Turns.
  - Instruction following: Multi-IF and MT-Bench-101.
  - Persona: InCharacter, CharacterEval/RoleBench, PICon, DNLI.
  - Video: VBench/VBench-2.0 subsets (human fidelity), ArcFace identity similarity, LSE-C/LSE-D, FVD, and RotErr/TransErr where camera control is used.
- **Adapt:** GateMem and GroupMemBench for scoping; Memora/FAMA and MemOps for lifecycle correctness; K-Bench-style multi-channel leak probes for deletion.
- **Must build:** a **live-persona memory benchmark** with:
  - (a) mixed 1:1 and broadcast sessions with multiple principals and anonymous viewers;
  - (b) gold provenance labels (user-asserted / inferred / agent-generated / third-party);
  - (c) scripted corrections, erasure requests, and poisoning attempts from viewers;
  - (d) cross-channel leak probes over text, speech transcript, on-screen text, and visual content;
  - (e) latency-coupled metrics: memory time-to-availability, and turn latency with memory on vs off;
  - (f) a longitudinal human study with MOS, SUS, Godspeed, and social presence, pre-registered and with bootstrap CIs.

---

## 2. Conceptual distinctions to state explicitly in the proposal

| Memory type | Substrate | Lifetime | Examples | What "correct" means |
|---|---|---|---|---|
| **Working/context memory** | prompt tokens, KV cache | one call / one stream | LLM context; RELIC compressed latent tokens in KV; WorldTrace | available and addressable; *not* a store of record |
| **User episodic memory** | raw turns/episodes with timestamps | cross-session | Generative Agents memory stream, MemMachine episodes, LongMemEval "session decomposition" | faithful to what happened, time-stamped, attributable |
| **User semantic memory / profile** | extracted facts, profiles, graphs | cross-session, mutable | Mem0 facts, Zep/Graphiti bi-temporal edges, MemoryOS long-term persona, LangMem profiles | current and correct after updates; provenance kept |
| **Procedural/reflective memory** | lessons, instructions | cross-session | Reflexion episodic buffer, LangMem procedural, MIRIX procedural | improves behavior; no leakage of private details |
| **Parametric memory** | weights (fine-tune/LoRA) | long | MemoryBank-tuned SiliconFriend; MemOS parameter memory | hard to delete (unlearning: SISA, TOFU, K-Bench) |
| **Visual world-state memory** | frames+poses, surfels, point clouds, latent memory tokens | one generated world/stream | WorldMem, Context-as-Memory, VMem, Spatia, Genie 3 | revisit consistency (PSNR/LPIPS/rFID on revisits, MBench, R2M-Bench) |
| **Persona identity memory (visual/voice)** | reference images, identity embeddings, slot memory | persona lifetime | SlotMem, Live Avatar long-horizon strategies | ArcFace similarity stable over time; voice similarity |

CoALA [sumers2023coala] provides the working/episodic/semantic/procedural vocabulary. The episodic-memory position paper [pink2025episodicmemory] argues for five properties of episodic memory for LLM agents. The TMLR 2026 survey [huang2026memorysurvey2] organizes memory by substrate, cognitive mechanism, and subject: user-centric vs agent-centric.

---
