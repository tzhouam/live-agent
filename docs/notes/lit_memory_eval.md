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

## 3. Comparison matrix A: memory systems

Legend: *[paper]* = number read in the paper; *[abs]* = from the abstract; *[vendor]* = vendor page or README.

| System (date) | Memory mechanism | Write / update policy | Forgetting / conflict | Reported results (as cited) | Code | Key limitation for live persona |
|---|---|---|---|---|---|---|
| **MemGPT / Letta** [packer2023memgpt] (2023-10) | OS-style: main context (system, working context, FIFO) plus recall and archival storage; LLM self-edits memory via function calls | agent-initiated, in-loop (hot path) | eviction and summarization of FIFO; no explicit truth maintenance | DMR (MSC-based): GPT-4 Turbo 35.3% → 93.4% with MemGPT; GPT-4 32.1% → 92.5% *[paper]* | yes (Letta, research.memgpt.ai) | self-editing adds LLM calls per turn; DMR is easy (Zep 94.8%) |
| **Generative Agents** [park2023generativeagents] (2023-04; UIST 2023) | memory stream of NL observations; retrieval = recency (decay 0.995) + importance (LLM 1–10) + relevance; reflections when summed importance > 150 *[paper]* | write everything; reflect periodically | none (recency decay affects retrieval only) | TrueSkill believability: full 29.89 vs no-memory/planning/reflection 21.21; d = 8.16; 100 Prolific evaluators *[paper]* | yes | reports "hallucinated embellishments" *[paper]*; costly |
| **MemoryBank / SiliconFriend** [zhong2023memorybank] (2023-05; AAAI 2024) | conversation logs, event summaries, user portrait | continuous | Ebbinghaus R = e^(−t/S); S starts at 1, +1 and t reset on recall *[paper]* | qualitative plus 15 simulated users, 194 probing questions *[paper]* | yes | decay is heuristic; "exploratory and highly simplified" (authors) |
| **Reflexion** [shinn2023reflexion] (2023-03; NeurIPS 2023) | verbal self-reflection in an episodic buffer across trials | after task feedback | n/a | HumanEval pass@1 91% vs GPT-4 80% *[abs]* | yes | task-learning memory, not user memory |
| **Mem0 / Mem0^g** [chhikara2025mem0] (2025-04) | LLM extraction (summary + last 10 messages) → compare with top-10 similar memories → ADD/UPDATE/DELETE/NOOP; graph variant *[paper]* | per message pair, synchronous extraction | DELETE on contradiction (LLM-judged) | LoCoMo J: Mem0 66.88±0.15, Mem0^g 68.44±0.17, full-context 72.90±0.19, OpenAI 52.90, Zep 65.99 (10 runs, GPT-4o-mini, adversarial category excluded); p95 1.44 s vs 17.12 s *[paper]*. README (Apr 2026 algorithm): LoCoMo 92.5, LongMemEval 94.4, BEAM-1M 64.1, BEAM-10M 48.6 *[vendor]* | Apache-2.0 | LLM-judged deletes can hallucinate; vendor numbers not reproduced; Zep disputes setup |
| **Zep / Graphiti** [rasmussen2025zep] (2025-01) | temporal KG; bi-temporal (event vs ingestion time), validity intervals, edge invalidation that keeps history *[vendor repo]* | episodic ingestion → entity/edge extraction | contradictions invalidate old edges; history kept | DMR 94.8% vs MemGPT 93.4%; LongMemEval up to +18.5% accuracy, −90% latency *[abs]*; corrected LoCoMo 75.14±0.17 *[vendor]* | Graphiti Apache-2.0 | keeping history conflicts with erasure; graph extraction cost |
| **LangMem** (LangChain docs) | semantic (collections/profiles), episodic, procedural | "hot path" (conscious) vs "background" (subconscious) formation | delete/invalidate or update/consolidate | none quantitative on docs page | yes | framework, not evaluated |
| **HippoRAG / HippoRAG 2** [gutierrez2024hipporag; gutierrez2025hipporag2] (2024-05 NeurIPS 2024; 2025-02 ICML 2025) | KG + Personalized PageRank ("hippocampal index") | offline indexing | n/a | up to +20% multi-hop QA; single-step 10–30× cheaper, 6–13× faster than IRCoT *[abs]*; HippoRAG 2 +7% associative memory *[abs]* | yes | document memory; no user or temporal semantics |
| **MemoRAG** [qian2024memorag] (2024-09; WebConf 2025) | light long-range model builds global memory (KV compression) → clues → retrieval | offline over corpus | n/a | "superior" on long-context tasks *[abs]* | yes | corpus QA, not dialogue |
| **A-MEM** [xu2025amem] (2025-02; NeurIPS 2025) | Zettelkasten notes (content, time, keywords, tags, context, embedding, links); memory evolution rewrites old notes | on each add | evolution may overwrite context (risk) | LoCoMo multi-hop F1 45.85 vs MemGPT 25.52 (GPT-4o-mini); ~1.2k vs ~16.9k tokens per op *[paper]* | yes | rewriting old notes can drift or hallucinate |
| **MemoryOS** [kang2025memoryos] (2025-05) | short / mid / long-term personal memory; FIFO and segmented pages | hierarchical promotion | heat-based (per paper) | LoCoMo +49.11% F1, +46.18% BLEU-1 over baselines (GPT-4o-mini) *[abs]* | yes | F1/BLEU on LoCoMo only |
| **MemOS** [li2025memos] (2025-07) | "MemCube" unifying plaintext, activation (KV), and parameter memory with lifecycle | scheduled | lifecycle/governance | see paper | yes | complex; cross-substrate deletion not shown |
| **MIRIX** [wang2025mirix] (2025-07) | six types (Core, Episodic, Semantic, Procedural, Resource, Knowledge Vault) with multi-agent managers; multimodal (screenshots) | per-type agents | per-type | ScreenshotVQA +35% vs RAG with −99.9% storage; LoCoMo 85.4% *[abs]* | yes (app) | multi-agent cost; privacy only as local storage |
| **Memory-R1** [yan2025memoryr1] (2025-08) | RL-trained Memory Manager (ADD/UPDATE/DELETE/NOOP) + Answer Agent (PPO/GRPO) | learned | learned DELETE | beats baselines on LoCoMo, MSC, LongMemEval with 152 training QA pairs, 3B–14B *[abs]* | – | reward is QA outcome; no provenance or safety reward |
| **MemAgent** [yu2025memagent] (2025-07; ICLR 2026 oral) | fixed-size memory overwritten while reading segments; RL (DAPO extension) | overwrite | implicit | 8K context trained on 32K → 3.5M QA with <5% loss; >95% on 512K RULER *[abs]* | yes | long-document reading, not cross-session user memory |
| **LightMem** [fang2025lightmem] (2025-10; ICLR 2026) | Atkinson–Shiffrin: sensory filter → topic short-term → long-term with **sleep-time** offline update | offline consolidation | – | LongMemEval/LoCoMo: up to +7.7% / +29.3% accuracy; up to 38× / 20.9× fewer tokens *[abs]* | yes | good template for latency-bounded writes |
| **MemMachine** [wang2026memmachine] (2026-04) *[preprint-2026]* | ground-truth-preserving episodic store + profile; contextualized retrieval | store raw episodes (less lossy extraction) | – | LoCoMo 0.9169 (gpt-4.1-mini); LongMemEval_S 93.0% *[abs]*; ~80% fewer input tokens than Mem0 | open-source | vendor-affiliated; LoCoMo saturation |
| **Commercial: ChatGPT memory** | "saved memories" + "reference chat history" (Apr 10 2025, secondary); "Dreaming" background synthesis (rollout from 2026-06-04, secondary) | background | user can view/edit; temporary chat | LongMemEval: ChatGPT memory −37% vs offline reading [wu2024longmemeval] *[paper]* | closed | SpAIware showed persistent injection (2024) |
| **Commercial: Claude memory** | project-scoped memories, viewable/editable summary; Incognito chat; import/export | background | user edit | launch 2025-09-11 (Team/Enterprise); 2025-10-23 Pro/Max *[vendor]* | closed | project scoping is a useful analogue for public/private |
| **Commercial: Gemini** | "personal context" from past chats + Temporary Chat (2025-08, secondary); "Personal Intelligence" connected apps (2026-01-14 beta, secondary) | background | temporary chats kept up to 72 h (secondary) | – | closed | cross-app data raises scoping stakes |

## 4. Comparison matrix B: benchmarks and metrics

| Benchmark (date, venue) | What it measures | Scale / data | Headline finding (as cited) | Avail. | Reuse for live persona? |
|---|---|---|---|---|---|
| **MSC** [xu2021msc] (2021; ACL 2022) | multi-session human–human chat with persona recall | 5 sessions per episode (as used in MemGPT) | retrieval and summarize-recall beat encoder-decoder *[abs]* | ParlAI | historical baseline; DMR is saturated |
| **DuLeMon** [xu2022dulemon] (2022; Findings ACL 2022) | Chinese long-term persona memory for user **and** bot | – | PLATO-LTM improves consistency and engagingness *[abs]* | yes | tracks both parties' personas, which fits a persona |
| **LoCoMo** [maharana2024locomo] (2024; ACL 2024) | QA (single-hop, multi-hop, temporal, open-domain, adversarial), event summarization, multimodal dialogue | paper: 50 convs, ~300 turns, ~9.2K tokens, up to 35 sessions; 7,512 QA *[paper]*; public eval commonly 10 convs (per Mem0) | human F1 87.9 vs GPT-3.5-16K 37.8 *[paper]* | CC BY-NC 4.0 | use only with a full-context baseline; known label issues (Zep blog); near saturation |
| **LongMemEval** [wu2024longmemeval] (2024-10; ICLR 2025) | extraction, multi-session reasoning, temporal reasoning, **knowledge update**, **abstention** | 500 Qs; S ≈ 115K tokens; M ≈ 500 sessions / ~1.5M tokens *[paper]* | long-context −30–60%; ChatGPT −37%, Coze −64% *[paper]* | GitHub | **reuse (primary text-memory benchmark)** |
| **PerLTQA** [du2024perltqa] (2024-02) | semantic vs episodic personal memory QA | 8,593 Qs, 30 characters *[abs]* | BERT classifiers beat LLMs at memory classification | yes | memory-type classification |
| **MemBench** [tan2025membench] (2025-06; Findings ACL 2025) | factual vs reflective memory; participation vs observation; effectiveness, efficiency, capacity | – | – | GitHub | the "observation" mode fits a streamer watching chat |
| **MemoryAgentBench** [hu2025memoryagentbench] (2025-07) | accurate retrieval, test-time learning, long-range understanding, **selective forgetting** (FactConsolidation) | incremental multi-turn | SF multi-hop ≤ 28% for all methods *[paper]* | GitHub + HF | **reuse for correction/forgetting** |
| **PersonaMem** [jiang2025personamem] (2025-04; COLM 2025) | dynamic user profiling, preference evolution | 180+ users, up to 60 sessions, 15 tasks | frontier models ≈ 50% *[abs]* | GitHub | **reuse (personalization)** |
| **PrefEval** [zhao2025prefeval] (2025-02; ICLR 2025 oral) | explicit and implicit preference following up to 100K tokens | 3,000 preference–query pairs, 20 topics | zero-shot preference following < 10% at 10 turns (~3K tokens) *[abs]* | yes | **reuse** |
| **BEAM** [tavakoli2025beam] (2025-10) | long-term memory up to 10M tokens | 100 convs, 2,000 Qs *[abs]* | 1M-context LLMs struggle as dialogues lengthen | – | stress test for scale |
| **HaluMem** [chen2025halumem] (2025-11) | operation-level hallucination: extraction, update, QA | ~15K memory points, 3.5K Qs; 1.5K–2.6K turns, >1M tokens *[abs]* | hallucinations accumulate at extraction and update | – | **reuse (hallucinated memories)** |
| **Memora / FAMA** [uddin2026memora] (2026-04; Findings ACL 2026) | remembering, reasoning, recommending; penalizes obsolete memory | weeks-to-months conversations | frequent reuse of invalid memories *[abs]* | – | **adapt metric (FAMA)** |
| **MemOps** [hao2026memops] (2026-07) *[preprint-2026]* | lifecycle ops (remember, forget, update, reflect) with gold traces | – | final-answer accuracy hides operation failures | – | **adapt: operation-level scoring** |
| **MemoryArena** [he2026memoryarena] (2026-02; ICML 2026) | memory driving later actions across sessions | web, planning, search, reasoning | LoCoMo-saturated agents fail here *[abs]* | yes | partial (agentic tasks) |
| **AMemGym** [cheng2026amemgym] (2026-03; ICLR 2026) | on-policy interactive memory eval with simulated users and state evolution | – | gaps in RAG, long-context, and agentic memory | – | **reuse the method (on-policy simulator)** |
| **GroupMemBench** [yang2026groupmembench] (2026-05) *[preprint-2026]* | multi-party memory, speaker-grounded beliefs | – | best 46.0% avg; knowledge update 27.1% *[abs]* | – | **adapt for livestream chat** |
| **GateMem** [ren2026gatemem] (2026-06) *[preprint-2026]* | multi-principal utility, access control, forgetting after deletion | 4 domains | no method strong on all three *[abs]* | GitHub | **adapt for public/private** |
| **OP-Bench** [hu2026opbench] (2026-01) | over-personalization: irrelevance, repetition, sycophancy | 1,700 instances | widespread once memory is added | – | **reuse** |
| **MemSyco-Bench** [xiang2026memsycobench] (2026-07) | memory-induced sycophancy; scope; conflict with evidence | 5 tasks | – | GitHub | **reuse** |
| **Mem-Gallery** [bei2026memgallery] / **H2HMem** [zhu2026h2hmem] / **CloneMem** [hu2026clonemem] (2026) | multimodal long-term conversational memory / multi-party multimodal / life-trace AI clones | – | current systems struggle | partly | adapt (multimodal, clone persona) |
| **MPBench** [dash2026mpbench] (2026-06) *[preprint-2026]* | memory poisoning via 4 write channels; 6 attack classes | – | aggressive writers are more exploitable; prompt-injection defenses do not cover this | – | **reuse (security)** |
| **K-Bench** [yu2026kbench] (2026-09) *[preprint-2026]* | unlearning leak across 6 agent channels | – | 22–86% leak where TOFU/MUSE show none *[abs]* | – | **adapt for deletion verification** |
| **TOFU** [maini2024tofu] (2024-01) | parametric unlearning | 200 fictitious authors × 20 QA | no baseline unlearns effectively *[abs]* | yes | only if parametric personalization is used |
| **Lost in the Middle / RULER / NoLiMa** (2023–2025) | long-context usage | – | see §1.2 | yes | evidence that long context ≠ memory |
| **DNLI** [welleck2018dnli] (ACL 2019); PersonaChat [zhang2018personachat] (ACL 2018) | persona consistency as NLI | – | – | yes | automatic contradiction metric |
| **CharacterEval** [tu2024charactereval] (2024-01) | Chinese role-play, 13 metrics / 4 dimensions | 1,785 dialogues, 77 characters *[abs]* | – | GitHub | persona quality (zh) |
| **RoleBench / RoleLLM** [wang2023rolellm] (2023-10) | role-play speaking style and knowledge | 100 roles, 168,093 samples *[abs]* | – | GitHub | persona quality (en/zh) |
| **InCharacter** [wang2023incharacter] (2023-10; ACL 2024) | personality fidelity via psychological-scale interviews | 32 characters, 14 scales | up to 80.7% accuracy *[abs]* | yes | persona personality consistency |
| **PICon** [kim2026picon] (2026-03) | interrogation: internal, external, retest consistency | 7 agent groups vs 63 humans | agents fail to meet the human baseline *[abs]* | yes | **reuse for long-session persona drift** |
| Persona RL metrics [abdulhai2025personarl] (2025-10) | prompt-to-line, line-to-line, Q&A consistency | – | −55% inconsistency with multi-turn RL *[abs]* | – | metric definitions |
| **Multi-IF** [he2024multiif] (2024-10) | multi-turn multilingual instruction following | 4,501 convs × 3 turns, 8 languages | o1-preview 0.877 → 0.707 from turn 1 to 3 *[abs]* | yes | **reuse** |
| **MT-Bench-101** [bai2024mtbench101] (2024-02; ACL 2024) | 13 multi-turn tasks, 3-tier taxonomy | 4,208 turns, 1,388 dialogues | – | GitHub | **reuse** |
| **Full-Duplex-Bench** v1 / v1.5 / v2 / v3 [lin2025fullduplexbench; lin2025fdbv15; lin2025fdbv2; lin2026fdbv3] (2025–2026) | pause handling, backchannel, turn-taking, interruption; overlap; multi-turn with an automated examiner (correction, entity tracking); tool use under disfluency | – | v3: GPT-Realtime Pass@1 0.600; cascaded latency 10.12 s *[abs]* | GitHub | **reuse (speech interaction)**; v2 "correction" and "entity tracking" are memory-adjacent |
| **Talking Turns** [arora2025talkingturns] (2025-03; ICLR 2025) | turn-taking judged by a supervised model; user study | Switchboard-based | systems rarely backchannel and interrupt aggressively *[abs]* | promised | **reuse** |
| **VBench / VBench-2.0** [huang2023vbench; zheng2025vbench2] (CVPR 2024; 2025) | 16 dimensions (incl. subject consistency, flicker); 2.0: human fidelity, controllability, physics, commonsense, creativity | – | – | yes | subset (subject consistency, human fidelity) |
| **WorldScore** [duan2025worldscore] (ICCV 2025) | world generation: controllability, quality, dynamics along camera trajectories | 3,000 examples, 19 models | – | yes | only if the persona has navigable scenes |
| **MBench** [zhang2026mbench], **R2M-Bench** [gu2026r2mbench], **WorldRoamBench** [xu2026worldroambench] (2026) | memory of video world models: entity, environment, causal consistency; relative revisit memory (MemoryGain, NMR; ρ = 0.547 with humans); long-horizon stability | – | none of 10+ models satisfies all dimensions (WorldRoamBench) *[abs]* | partly | visual-memory eval if scenes persist |
| **FVD** [unterthiner2018fvd] | distributional video quality | – | – | yes | coarse quality; not per-identity |
| **ArcFace** [deng2018arcface] | face-identity embedding; cosine similarity to reference | – | – | yes | **identity drift over long streams** |
| **RotErr / TransErr** (CameraCtrl) [he2024cameractrl] | camera-pose error from COLMAP; RotErr = Σ arccos((tr(R_gen R_gtᵀ) − 1)/2); TransErr = Σ‖T_gt − T_gen‖²; scale aligned on first two frames; 1,000 RealEstate10K videos *[paper]* | – | – | yes | only for camera-controlled output |
| **LSE-C / LSE-D** (SyncNet [chung2016syncnet]; Wav2Lip [prajwal2020wav2lip]) | audio-visual sync confidence and distance | – | – | yes | **reuse for talking head** |
| **UX: MOS (ITU-T P.800), SUS [brooke1996sus], Godspeed [bartneck2009godspeed], social presence [biocca2003socialpresence]** | perceived quality, usability, anthropomorphism/likeability/intelligence, co-presence | – | – | instruments | **reuse in human study** |
| **Statistics: error bars [miller2024errorbars], LLM-judge bias [zheng2023llmjudge], IRR [hallgren2012interrater], pre-registration [nosek2018preregistration]** | clustered SEs, paired tests, power; judge biases; κ/ICC; prereg | – | GPT-4 judge agreement > 80%, matching human–human agreement [zheng2023llmjudge] *[abs]* | – | **adopt** |

---

## 5. Per-item notes (grouped)

### 5.1 Foundational agent-memory architectures

- **MemGPT** (Packer et al., arXiv 2310.08560, 2023-10-12). https://arxiv.org/abs/2310.08560
  - Virtual context management with interrupts; the LLM moves data between main context and external recall/archival stores through function calls.
  - Evaluation: document analysis, and multi-session chat on MSC with the DMR task (an LLM-generated QA about sessions 1–5) and a conversation-opener task.
  - DMR numbers are in the matrix *[paper]*.
  - Limitations: DMR is narrow and near ceiling (Zep 94.8%). Self-editing costs extra LLM calls in the hot path.
  - Relevance: this is the conceptual template for a persona's "core memory" block, which would hold persona canon and user profile.
- **Generative Agents** (Park et al., 2304.03442, 2023-04-07; UIST 2023, DOI 10.1145/3586183.3606763).
  - Retrieval scoring and reflection trigger values are in the matrix *[paper]*.
  - Evaluation: "interviews" of 25 agents ranked by 100 human evaluators, aggregated with TrueSkill, with Kruskal–Wallis and Dunn post-hoc tests. This is a good model for the proposal's statistics.
  - The paper documents embellishment hallucinations.
  - Relevance: reflection is a consolidation mechanism, and the importance score is a write-priority signal.
- **MemoryBank** (Zhong et al., 2305.10250; AAAI 2024).
  - The Ebbinghaus decay details are in the matrix.
  - Relevance: it is the canonical "forgetting-curve" citation. The authors call it simplified, and it provides **no user-controlled or compliance-grade forgetting**.
- **Reflexion** (Shinn et al., 2303.11366; NeurIPS 2023). An episodic buffer of self-critiques. It illustrates agent-generated memories that must be kept separate from user facts.
- **CoALA** (Sumers et al., 2309.02427; TMLR). A framework of working, episodic, semantic, and procedural memory plus an internal/external action space. Use it as the proposal's taxonomy.
- **Episodic memory position paper** (Pink et al., 2502.06975, 2025-02). Names five properties of episodic memory and a roadmap.

### 5.2 Production and recent memory systems

- **Mem0** (Chhikara et al., 2504.19413, 2025-04-28; repo github.com/mem0ai/mem0, Apache-2.0).
  - Paper numbers are in the matrix. The evaluation ran 10 runs and reports mean ± 1 SD, which is good practice.
  - Controversy: Zep's blog (2025-05-06, modified 2026-06-03) argues that the Zep configuration was wrong. It says the evaluation used a single-user model for two speakers, timestamps were appended to messages, and searches ran sequentially. It also notes that LoCoMo's adversarial category lacks ground truth and that full-context scores about 73%.
  - The README now claims much higher numbers for an April 2026 algorithm *[vendor, unverified]*.
- **Zep / Graphiti** (Rasmussen et al., 2501.13956, 2025-01-20). Bi-temporal KG, edge invalidation, Apache-2.0 repo. Relevance: this is the best existing model of **provenance and time for facts**. It needs an erasure mode that purges history.
- **Letta filesystem study** (blog, 2025-08-12). Reports 74.0% on LoCoMo with gpt-4o-mini using file tools, vs Mem0^g 68.5% *[vendor]*. Relevance: a mandatory simple baseline.
- **LangMem** (LangChain docs; no date on page). Hot-path vs background memory formation; semantic, episodic, and procedural memory. Relevance: this vocabulary maps directly onto the latency-bounded write policy (P1).
- **A-MEM** (Xu et al., 2502.12110; NeurIPS 2025). Zettelkasten-style links and memory evolution. Risk: evolution rewrites past notes, which conflicts with provenance.
- **HippoRAG / HippoRAG 2** (Gutiérrez et al.; NeurIPS 2024 / ICML 2025). KG plus PPR, framed as non-parametric continual learning.
- **MemoRAG** (Qian et al.; WebConf 2025). Global memory built from compressed KV that emits clues for retrieval.
- **MemoryOS** (Kang et al., 2506.06326); **MemOS** (Li et al., 2507.03724). OS-style hierarchies. MemOS adds activation (KV) and parameter memory under one abstraction, which is the right abstraction for cross-substrate deletion, but deletion across substrates is not shown.
- **MIRIX** (Wang & Chen, 2507.07957). Six memory types and a multimodal screen-capture memory. The closest existing system to multimodal personal memory.
- **Memory-R1** (Yan et al., 2508.19828); **MemAgent** (Yu et al., 2507.02259; ICLR 2026 oral). RL-learned memory operations. Relevance: a write policy could be learned under a reward that includes latency and provenance correctness. That reward design is open.
- **LightMem** (Fang et al., 2510.18866; ICLR 2026). Sleep-time consolidation.
- **MemMachine** (Wang et al., 2604.04853, 2026-04) *[preprint-2026]*. Argues for keeping raw episodes to avoid lossy extraction, which is consistent with provenance needs.
- **Commercial systems.**
  - ChatGPT: saved memories plus chat-history reference (2025-04-10) and "Dreaming" background synthesis (from 2026-06-04). These dates come from secondary reporting because the OpenAI pages returned 403.
  - Claude: project-scoped memory, editable summary, and Incognito (2025-09-11), extended to Pro/Max (2025-10-23) *[vendor]*.
  - Gemini: personal context and Temporary Chat (2025-08-13, secondary), and Personal Intelligence connected apps (2026-01-14 beta; U.S. expansion 2026-03-17; secondary).
  - Relevance: user-facing controls (view, edit, temporary or incognito sessions, scoping) are now the **industry baseline** that a research system should match or exceed.

### 5.3 Long context vs memory

- **Lost in the Middle** (Liu et al., 2307.03172; TACL). Position-dependent degradation.
- **RULER** (Hsieh et al., 2404.06654; COLM 2024). Tested 17 models; only about half hold up at 32K.
- **NoLiMa** (Modarressi et al., 2502.05167; ICML 2025). Needles with no literal overlap; numbers are in §1.2.
- **Argument for the proposal:** a long context window or KV cache is a *working memory with no guarantees*. Durable, correctable, scoped memory needs an explicit store. The same holds on the video side: WorldTrace shows KV visual memory becomes unaddressable past the training horizon.

### 5.4 Safety: poisoning, injection, hallucinated memories, deletion

- **PoisonedRAG** (USENIX Sec 2025): five injected texts give 90% attack success.
- **AgentPoison** (2407.12784): >80% attack success at <0.1% poison rate *[abs]*.
- **MINJA** (2503.03704): query-only memory injection.
  - A follow-up [sunil2026poisondefense] cites MINJA as achieving >95% injection success and 70% attack success in idealized conditions, and finds realistic pre-existing memories reduce effectiveness *[abs]*.
- **SpAIware** (Rehberger, 2024; Embrace The Red / later journal version): persistent injection into ChatGPT memory. Sources are secondary; cite the ScienceDirect article only after checking it.
- **MPBench** [dash2026mpbench] and the **memory-security survey** [lin2026memsecuritysurvey] (EMNLP 2026). The survey proposes a lifecycle model (Write, Store, Retrieve, Execute, Share, Forget/Rollback) and argues that security must be "anchored in storage-time provenance, versioning, and policy-aware retention". This directly supports P2 and P3.
- **CAPTURE** [hossain2026capture]: poisoning success 11.5% while accepting 83.5% of genuine updates, rising to 24.7% under an adaptive attacker *[abs]*.
- **Hallucinated memories:** Generative Agents (embellishment), HaluMem (extraction and update stages), MemSyco-Bench (sycophancy), OP-Bench (over-personalization).
- **Deletion and unlearning:**
  - SISA machine unlearning [bourtoule2019machineunlearning] (S&P 2021).
  - TOFU [maini2024tofu].
  - Agentic unlearning (parameter–memory "backflow") [wang2026agenticunlearning].
  - K-Bench [yu2026kbench].
  - Execution-state unlearning [yao2026executionunlearning]: exact unlearning needs recomputing at least T − τ + 1 transitions; provenance-guided selective replay attains this *[abs]*.
  - GDPR Art. 17 (right to erasure) motivates verifiable deletion. Legal text was not re-fetched in this session.
  - Take-away: **the unit of deletion must be a provenance closure, not a row**.

### 5.5 Visual and world-state memory for video generation (distinct from user memory)

- **WorldMem** (Xiao et al., 2504.12369).
  - Memory bank of latent frames, a 5-D pose, and a timestamp.
  - Retrieval by field-of-view (FOV) overlap plus time; state-aware attention with Plücker and time embeddings.
  - Minecraft beyond context: PSNR 23.98 vs Diffusion Forcing 17.32 *[paper]*.
  - Stated limitations: occlusion defeats FOV retrieval, and memory grows linearly.
- **Context-as-Memory** (Yu et al.; SIGGRAPH Asia 2025): stored context frames concatenated to the input, with FOV-overlap retrieval.
- **VMem** (Li et al.; ICCV 2025): surfel-indexed view memory.
- **Video World Models with Long-term Spatial Memory** (Wu et al., 2506.05284).
- **Spatia** (point-cloud memory updated by SLAM).
- **GIM-World** (implicit memory tokens distilled from a geometry teacher).
- **RELIC** (14B model, compressed latent tokens in the KV cache, 16 FPS).
- **Matrix-Game 3.0** (camera-aware memory retrieval, up to 40 FPS real time, per the abstract).
- **Mixture of Contexts** (learned sparse attention routing, "minutes" of consistency).
- **FAR** (long-short context for frame-autoregressive video).
- **WorldTrace** (addressable compressed KV memory; LoopBench).
- **Genie 3** (DeepMind blog, 2025-08-05): 24 fps, 720p, consistency for "several minutes", visual memory "as far back as one minute ago". Consistency is emergent, with no explicit 3D. Limitations: interaction lasts a few minutes, and errors accumulate *[vendor]*.
- **Evaluation:** MBench, R2M-Bench, WorldRoamBench, WorldScore.
- **Identity-centric memory, most relevant to a persona:** SlotMem (character-addressable slot memory) and Live Avatar (14B streaming avatar, 45 FPS, TTFF 1.21 s on 5 H800 GPUs, >10,000 s without identity drift, per the abstract; introduces GenBench).
- **Distinction to state:** these memories hold *appearance and geometry for rendering consistency*. They have no notion of consent, truth, or audience. They are nevertheless a **privacy channel**: a private 1:1 detail rendered on screen, such as a user's photo shown as a prop, becomes public if the visual memory is reused in a livestream. Deletion must therefore reach visual memory banks too, which no work addresses.

### 5.6 Evaluation of interactive and memory agents

- **Datasets:** MSC, DuLeMon, LoCoMo, LongMemEval, PerLTQA, MemBench, MemoryAgentBench, PersonaMem, PrefEval, BEAM, HaluMem, Memora, MemOps, MemoryArena, AMemGym, GroupMemBench, GateMem, OP-Bench, MemSyco-Bench, Mem-Gallery, H2HMem, CloneMem, LOCOMO-Conv. Details are in matrix B.
- **LOCOMO-Conv** [chang2026locomoconv] (Findings EMNLP 2026) is notable: when users *don't ask* explicitly, retrieval gaps appear, and "silent grounding" occurs. A live persona must bring memory up proactively, which fits this setup.
- **Serving cost:** [pollertlam2026totalrecall].
- **Persona:** PersonaChat/DNLI (NLI-based contradiction), CharacterEval, RoleBench, InCharacter, PICon, and the persona-RL metrics.
- **Real-time spoken interaction:** Full-Duplex-Bench v1 through v3 and Talking Turns.
- **Video:** VBench/2.0, WorldScore, FVD, ArcFace similarity, RotErr/TransErr, LSE-C/D.
- **UX and statistics:** listed in matrix B.

---

## 6. Proposed evaluation plan (derived from the gaps)

**E1. Component memory accuracy (reuse).**
- Run LongMemEval_S/M, MemoryAgentBench (AR and SF), PersonaMem, PrefEval, and HaluMem.
- Always report full-context, filesystem (Letta-style), and RAG baselines next to the system.
- Report LoCoMo only as secondary, with its known issues stated.

**E2. Lifecycle correctness (adapt).**
- Use FAMA (Memora) and MemOps-style operation traces.
- Report per operation: correction latency, meaning the number of turns until the updated fact is used everywhere, and stale-use rate.

**E3. Scoping and deletion (build, borrowing from GateMem and K-Bench).**
- Leak rate across channels: text reply, TTS transcript, on-screen captions, generated visuals (OCR/VLM probe), tool logs, summaries, and caches.
- Tested under (a) 1:1 → public cross-over probes, (b) viewer-to-viewer probes, and (c) post-erasure probes. Erasure is verified by comparing against a counterfactual replay, following execution-state unlearning.

**E4. Provenance fidelity (build).**
- For each retrieved memory, check whether the system correctly labels its source (user-asserted / inferred / agent-generated / third-party viewer) and its time.
- Metrics: provenance accuracy, plus "agent-generated-as-user-fact" confusion rate.

**E5. Robustness to viewer poisoning (reuse MPBench/MINJA-style attacks in the broadcast setting).** Report attack success rate together with the acceptance rate of genuine updates, which is the CAPTURE-style trade-off.

**E6. Real-time coupling (build).**
- Memory time-to-availability.
- Turn latency p50/p95 with memory on vs off.
- Full-Duplex-Bench v1.5/v2 metrics with memory enabled.
- Video frame-rate stability during memory writes.

**E7. Persona consistency over sessions (reuse and adapt).** PICon retest consistency, DNLI contradiction rate, InCharacter personality stability, ArcFace identity similarity to the reference over ≥1 h streams, voice-similarity drift, and LSE-C/D.

**E8. Human study.**
- Longitudinal: repeated sessions over ≥2 weeks. The design is inspired by CAPTURE's 40-user, 2–3-week replay and Generative Agents' ranking study.
- Measures: MOS for AV quality, SUS, Godspeed (anthropomorphism, likeability, perceived intelligence, perceived safety), social presence, and perceived creepiness or over-personalization (OP-Bench categories).
- Pre-register hypotheses and analysis [nosek2018preregistration].

**Statistics.**
- Repeated runs with mean ± SD as in Mem0 (10 runs).
- Question-clustered bootstrap CIs and paired differences [miller2024errorbars].
- Report LLM-judge agreement with humans on a subset (κ/ICC [hallgren2012interrater]) and control for the judge biases in [zheng2023llmjudge].
- Human rankings aggregated with TrueSkill or mixed-effects models; correction for multiple comparisons.

---

## 7. Most relevant 10 items for this proposal

1. **LongMemEval** [wu2024longmemeval]: primary text-memory benchmark; covers knowledge updates and abstention; documents the commercial memory gap.
2. **Mem0** [chhikara2025mem0] + the Zep critique + the Letta filesystem blog: the canonical extract/reconcile pipeline and the cautionary tale about benchmarks and baselines.
3. **Zep/Graphiti** [rasmussen2025zep]: bi-temporal provenance model; it conflicts with erasure.
4. **MemoryAgentBench** [hu2025memoryagentbench]: selective forgetting is the weakest competency (≤28% multi-hop).
5. **GateMem** [ren2026gatemem]: multi-principal access control plus deletion; the nearest template for public/private (preprint).
6. **Execution-state unlearning** [yao2026executionunlearning] + **K-Bench** [yu2026kbench]: deletion ≠ forgetting; provenance-closure replay (preprints).
7. **HaluMem** [chen2025halumem] + **Generative Agents** [park2023generativeagents]: hallucinated or embellished memories come from the write and update path.
8. **MPBench / MINJA / memory-security survey** [dash2026mpbench; dong2025minja; lin2026memsecuritysurvey]: viewer-writable memory is an attack surface; provenance must be anchored at storage time.
9. **LightMem** [fang2025lightmem] + **Total Recall at What Cost?** [pollertlam2026totalrecall]: latency- and cost-aware write and consolidation.
10. **Video memory: WorldMem / RELIC / WorldTrace / Live Avatar** [xiao2025worldmem; hong2025relic; wu2026worldtrace; huang2025liveavatar]: shows what visual memory is and is not, and why KV cache ≠ memory. Live Avatar is the closest real-time persona renderer.

## 8. Open verification to-dos

- Re-fetch the OpenAI memory and Dreaming pages from a browser and record exact dates and control semantics, including whether deleting a chat deletes derived memories.
- Fetch GDPR Art. 17 text from EUR-Lex.
- Obtain MSC and DuLeMon dataset statistics from the papers if they are needed in the proposal (not quoted here).
- Check the VMem and Context-as-Memory quantitative results if needed (not quoted here).
- Confirm venue status of 2026 preprints before submission.
