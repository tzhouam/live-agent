# Related Work: Synthesis and Comparison Matrix

*Deliverable for goal.md §3. Research date: 2026-09-25. Revision: see git log.*

This document synthesizes the literature for the live-agent proposal. Four detailed notes support it; each
contains per-system entries, URLs, dates and verification method:

- `docs/notes/lit_video_avatars.md`: streaming video, world models, controllable generation, avatars, joint audio-video.
- `docs/notes/lit_agents_control_latency.md`: live and duplex agents, livestream agents, closed-loop control, orchestration, AV sync.
- `docs/notes/lit_memory_eval.md`: long-term memory, personalization, safety and deletion, evaluation.
- `docs/notes/reference_agent_and_minimax_h3.md`: the reference Twitch agent and MiniMax H3.

The backbone itself is analysed in `docs/backbone_verification.md`.

**Evidence labels used throughout.**
- **[cited]**: a number or claim quoted from the named primary source (paper, official repo, model card).
- **[vendor]**: a product or blog claim with no reproducible artifact.
- **[abstract-level]**: read only at abstract or HTML-summary level.
- **[local-code]**: verified in the vLLM-Omni checkout at commit `7b4dc76`.
- **[unverified]**: could not be confirmed.

We measured no latency or quality numbers locally in this phase. Every arXiv entry in `docs/references.bib` was
resolved through the arXiv export API on 2026-09-25. Many 2026 items are unreviewed preprints and are treated as
provisional.

---

## 1. Executive synthesis

### 1.1 Does real-time video generation alone suffice for a stateful live agent? (Testing the working hypothesis)

We examined the hypothesis rather than assuming it. The evidence is **mixed** and points to a narrower statement.

**Evidence that a streaming generator alone is insufficient:**

- **Generator state is short-horizon and not addressable as memory.**
  - LingBot-World 2.0 in vLLM-Omni keeps an attention sink (the first 3 chunks) plus a rolling window (the last
    3 chunks) of KV, about 2.25 s at 16 fps [local-code: `pipeline.py:748-782`; checkpoint config `sink_size=9`,
    `sliding_window_num_frames=18`].
  - Its authors state that regions leaving the window are "regenerated rather than recalled" [cited: gao2026lingbotworld2].
  - WorldTrace reports that KV caches become unaddressable beyond the training horizon [cited, preprint: wu2026worldtrace].
  - Long context is also not reliable memory even for LLMs:
    - Lost in the Middle shows position sensitivity.
    - In NoLiMa, GPT-4o drops from 99.3% to 69.7% at 32K.
    - In LongMemEval, long-context LLMs drop 30–60% and ChatGPT memory drops 37%
      [cited: liu2023lostmiddle, modarressi2025nolima, wu2024longmemeval].
- **The control surface is narrow.**
  - The public vLLM-Omni streaming path for LingBot accepts only structural SE(3) camera interactions mid-session.
    A prompt interaction is rejected with `interaction_failed` [local-code: `diffusion/interaction/registry.py:25-27`,
    `coordinator.py:59-65`].
  - Most real-time world models control camera or ego-motion only. Matrix-Game 2.0 removes text input entirely
    [cited: he2025matrixgame2].
- **Even the backbone's authors add an external reasoner.** LingBot-World 2.0 ships a VLM "Director" and a "Pilot"
  agent outside the generator. We found no quantitative evaluation of whether the proposed events are valid or rendered
  [abstract-level: gao2026lingbotworld2].

**Counter-evidence: some video systems do integrate reasoning.**

- End-to-end duplex audio-visual models embed an LLM "thinker" in the generation stack:
  - X-Streamer: 8K-token dialogue context ≈ 10 min, 256×256, 25 FPS on 2×A100 [cited: xie2025xstreamer].
  - Wan-Streamer v0.1: 192p, ≈200 ms model-side, ≈550 ms total including an assumed 350 ms network [cited: huang2026wanstreamer].
  - LPM 1.0: text motion prompts, 5,000+ motion descriptors [cited, weights not released: zeng2026lpm].
- Genie 3 supports "promptable world events" [vendor: deepmind2025genie3].

So "video models lack reasoning" is **false as a blanket claim**.

**Refined hypothesis carried into the proposal.** The generator's internal state (KV cache or context window) is
insufficient for three things:
1. **cross-session, correctable, provenance-tracked memory**;
2. **verifiable compliance with instructions**, i.e. what was rendered as opposed to what the LM says it did;
3. **control that is honest about the generator's actual affordances**.

Unified models improve responsiveness. Among the systems we reviewed, none provides these three properties. This
is falsifiable: an end-to-end system that met the memory and compliance criteria of §5 of the proposal without an
external state layer would refute it.

### 1.2 What existing work solves (reuse, do not re-invent)

| Problem | State of the art | Reuse for us |
|---|---|---|
| Bidirectional DiT → real-time causal streamer | CausVid → Self Forcing → Causal Forcing(++) recipe, rolling KV + attention sink (LongLive, Rolling Forcing). 1.3B @ 480p ≈16–21 FPS on 1×H100, ≈0.8 s first chunk [cited: huang2025selfforcing, yang2025longlive] | Already embodied in LingBot-World 2.0 causal-fast (4-step DMD) |
| Streaming serving with session state | vLLM-Omni AR-Diffusion sessions: `session_id` / `event_id` / `chunk_index`; paged KV; `WS /v1/realtime/video` with per-chunk `started/active/completed_event_ids` [local-code] | Direct integration point; event acks give runtime ground truth of *when* a control was applied |
| Mid-stream prompt switching | LongLive KV-recache; Echo-Forcing scene recall + decay; CausVid "dynamic prompting" [cited] | Design reference for the missing LingBot stepwise prompt path (engineering class C) |
| Real-time audio-driven talking avatars | LiveAvatar 45 FPS, TTFF 1.21 s, 5×H800, Apache-2.0; SoulX-FlashTalk 32 FPS, 0.87 s, 8×H800; Ditto; LivePortrait 12.8 ms/frame on RTX 4090 [cited] | Candidate for the no-world-model baseline and for an optional face path |
| Duplex speech and turn-taking | Moshi ≈200 ms on L4; Qwen3-Omni 234 ms theoretical first packet; LiveKit turn detector; Pipecat pipelines [cited / vendor] | Reuse the voice front-end and barge-in handling |
| Fast talker / slow thinker | GPT-Live-1 (front/back delegation), Dispider, JoyAI-VL-Interaction, ConvFill, LTS-VoiceAgent [cited / vendor] | Adopt as a pattern; **not** a contribution |
| LLM-as-director for video (offline) | VideoDirectorGPT, LVD, DirecT2V, Mora; offline generate→judge→refine (VISTA, VideoRepair); learned judges VideoScore2 [cited] | Judge models for evaluation; IR design inspiration |
| Memory storage beyond context | MemGPT/Letta tiers; Generative Agents memory stream + reflection; Mem0 ADD/UPDATE/DELETE; Zep/Graphiti bi-temporal KG; LightMem sleep-time consolidation [cited] | Reuse the storage and retrieval mechanics |
| Memory and interaction benchmarks | LongMemEval, MemoryAgentBench (selective forgetting), PersonaMem, PrefEval, HaluMem, Multi-IF, Full-Duplex-Bench v1–v3, EchoChain [cited] | Reuse for component-level evaluation |

### 1.3 What remains unresolved (gaps with evidence)

| # | Gap | Evidence | Relevance |
|---|---|---|---|
| G1 | **Instruction-to-visible-compliance latency is not measured.** Papers report FPS and time-to-first-frame, not how long a mid-stream instruction takes to become visibly and correctly rendered | LongLive and Echo-Forcing describe delayed prompt adaptation only qualitatively [cited]. WorldMark reports "the fastest responders are often the least stable" [abstract-level: xu2026worldmark] | Core UX property of a live agent. Directly measurable with vLLM-Omni event acks + a detector |
| G2 | **No online, deadline-bounded verification of observable compliance.** Verify-and-refine exists only offline | VISTA, VideoRepair, PhyT2V are offline; LingBot's Director/Pilot has no reported validity evaluation [cited / abstract-level] | Distinguishes "LM says it complied" from "the output complied" |
| G3 | **Language intent → executable generator control is shallow and unaware of what the generator can do.** Real-time generators expose narrow, model-specific controls | LingBot public path: camera-only [local-code]. SGLang LingBot: keys + per-chunk text [cited: SGLang cookbook]. Convai/ACE map intents to *game-engine* actions with known semantics [vendor] | Planner must know what a *stochastic generator* can reliably render |
| G4 | **Agent context is not aligned with what the user actually saw or heard.** Generated-but-unplayed content causes mis-anchoring | PACE (audio): referent anchoring 25.0% → 96.3% [cited: wang2026pace]. No video analogue found | Interruptions of queued video chunks ("no, the other one") |
| G5 | **Interrupting in-flight video is not characterized.** Controls apply only at chunk boundaries; a failed tick forces a reset; no mid-chunk abort | vLLM-Omni design doc and code [local-code: `docs/design/feature/realtime_ar_diffusion.md`]. Interruption is weak even in speech-only systems: EchoChain < 50% pass [cited: modi2026echochain] | Latency floor = queued chunks + one generation interval + transport |
| G6 | **Correction, forgetting and deletion are the weakest memory competencies.** Deleting a record ≠ forgetting | MemoryAgentBench selective forgetting ≤ 28% [cited]. K-Bench: 22–86% leak after "deletion" [preprint: yu2026kbench]. Execution-state unlearning: derived summaries, plans and caches persist [preprint: yao2026executionunlearning] | User corrections and erasure requests must propagate to derived artifacts |
| G7 | **Public/private separation and memory poisoning in broadcast settings are open.** | GateMem: no method is strong on utility + access control + forgetting at once [preprint: ren2026gatemem]. MINJA: query-only memory injection [cited: dong2025minja] | In a livestream every viewer is a potential writer |
| G8 | **Character-level control inside world models is nascent. No system combines avatar-grade speech/face performance with scene-level world control** | Camera-only: Matrix-Game 2/3, WorldPlay, SolarWM. Character slices: LingBot-World 2.0 actions via chunk prompts, HelloWorld social reactions (not real-time), ReactiveGWM NPC strategy [cited] | Our persona must speak *and* act in a scene. Today that takes two model families |
| G9 | **Visual state is not linked to agent episodic memory across sessions** | World-model memory (WorldMem, Context-as-Memory, WorldPlay) targets scene revisits within one rollout. Avatar identity uses reference sinks [cited] | "Remember the scarf you wore yesterday" needs cross-session visual grounding |
| G10 | **No benchmark covers a live generated-video persona end to end** (speech + video control under interruption + memory + identity drift) | Benchmarks cover speech *or* video *or* memory [cited: see §2.4] | A protocol or benchmark is itself a contribution |

### 1.4 Where a defensible research contribution may exist

Combining a voice pipeline, an LLM and LingBot-World is **engineering integration, not a research contribution**. The
candidate contributions below each come with a measurable claim and a novelty risk. They are hypotheses, not
established claims.

1. **Capability-grounded, closed-loop control of a stochastic streaming generator** (addresses G2 and G3).
   - An empirically calibrated *capability manifest* records, for each control, the success rate, the
     time-to-effect distribution and side effects, all measured.
   - A time-aligned behavior IR is compiled against the manifest.
   - An online, deadline-bounded compliance monitor turns event acks and observed frames into
     "complied / not complied / unknown".
   - Claim to test: compared with open-loop LLM→prompt control, this raises *observable* compliance and makes
     honest failure reporting possible, at a measured latency cost.
   - Novelty risk: moderate. Offline verify-refine and game-engine intent mapping exist; LingBot's Director exists but
     is unevaluated.
2. **Time-to-visible-compliance (TVC) as a first-class metric, and its decomposition for chunked AR generators**
   (addresses G1 and G5).
   - Define TVC and decompose it into queue wait, chunk generation, transport and buffer, then *visual inertia*
     (chunks until the rendered content actually changes).
   - Characterize how chunk size, KV window and control type affect it.
   - Novelty risk: low to moderate. The measurement and its decomposition appear new; mechanisms to reduce inertia
     overlap with LongLive and Echo-Forcing.
3. **Display-aligned interaction state for generated video** (addresses G4). Extends PACE from audio to video.
   Corrections are interpreted against displayed frames, not generated-but-queued ones. Novelty risk: moderate.
4. **Provenance-typed, scope-separated memory for a live persona** (addresses G6, G7 and G9).
   - Memories are typed as user-asserted, agent-inferred, agent-generated, viewer-claimed, or system-observed.
   - Scopes: private per user, public per stream, persona canon.
   - Deletion cascades to derived artifacts, including visual state records.
   - Claim to test: this reduces false-memory and cross-scope leakage rates at equal recall.
   - Novelty risk: moderate to high for the individual mechanisms; the live multimodal setting and the combined
     evaluation are less covered.
5. **A live-persona evaluation protocol** (addresses G10). Novelty risk: low for the combination. It must be well
   constructed to count as a contribution.
6. *(Longer-term, needs training)* A **character-centric live world model**: audio and behavior-token conditioning
   added to LingBot-World (addresses G8). Highest potential, highest cost, and it depends on unverified portability
   of Wan-family audio modules.

---

## 2. Comparison matrix

Column key:
- **Ctrl**: C = camera/ego, K = keys, A = character actions, T = text/prompt, Au = audio.
- **Mid-stream**: can controls or prompts change during generation?
- **Latency/HW**: as reported by the source. None was measured by us.
- **Avail.**: code/weights availability and license.

Dates are v1 or first public release. URLs for arXiv items are `https://arxiv.org/abs/<id>`.

### 2.1 Video generation backbones and world models

| System (date; source) | Approach | Ctrl / mid-stream | Memory / consistency | Latency / HW (reported) | Avail. | Limitations | Relevance |
|---|---|---|---|---|---|---|---|
| **LingBot-World 2.0 in vLLM-Omni** (integration PRs 2026-08-16 → 09-24; `7b4dc76`) | 14B causal-fast, 4-step DMD, chunk = 3 latent = 12 px frames (first chunk 9) | C (SE3 target/velocity) mid-stream on public WS. T only at start. Prompt switching only on the deprecated tick path (latents only) [local-code] | Sink 3 chunks + window 3 chunks; image used only at chunk 0 | 4×H200 USP4: ≈549 ms/chunk, TTFC ≈1.07 s. 2×H200: ≈892–896 ms. 1 GPU eager: ≈3.24 s/chunk, TTFC ≈2.7 s [cited: vLLM-Omni PRs #7749, #7645] | Code Apache-2.0; weights **CC BY-NC-SA 4.0**. Weights present locally | ≤480×832; `max_num_seqs=1`; single replica; fixed session length; no WS reset; no audio; no character control | **Required backbone.** Integration surface verified |
| LingBot-World 2.0 paper (2026-07-08; arXiv 2607.07534) | Same family; causal pretraining + distillation | K, C, actions (attack, archery, spells) and text events via **chunk-wise prompts**; VLM Director/Pilot | "does not truly remember"; unbounded horizon claimed | 720p@60 fps claim (distilled) [cited, unreproduced in vLLM-Omni] | Repo `robbyant/lingbot-world-v2`; CC BY-NC-SA | Claims not reproduced in the integration | Shows the intended affordances. The gap between paper and serving is key |
| LingBot-World v1 (2026-01-28; 2601.20540) | Wan-based world model | K, C | minute-level "long-term memory" claim | <1 s latency @16 fps [cited] | Apache-2.0 | Not used by vLLM-Omni | Predecessor |
| Self Forcing (2025-06-09; 2506.08009) | Train on own rollouts (DMD), rolling KV | T (inherits) | rolling KV | ≈16 FPS H100, ≈0.8 s first latency, 480p [cited] | Apache-2.0 | 1.3B | Base recipe |
| LongLive (2025-09-26; 2509.22622) | Frame sink + short window; KV-recache on prompt switch | **T mid-stream** | short window + sink | 20.7 FPS 1×H100; up to 240 s [cited] | Apache-2.0 | 1.3B; delay after switch shown qualitatively | Prompt-switch reference for G1 |
| Causal Forcing / ++ (2026-02-02; 2026-05-14) | Causal teacher / consistency distillation | inherits | – | ++: frame-wise 2-step, −50% first-frame latency vs chunk 4-step [cited] | Apache-2.0 | small models | Latency-reduction lever (needs retraining) |
| Echo-Forcing (2026-05-15; 2605.16003) | Training-free hierarchical memory, scene recall, difference-aware decay | **T mid-stream** (smooth/hard cuts) | scene recall frames | bounded cache [cited] | code, no license | VBench-only eval | Recall + switch mechanism |
| Matrix-Game 2.0 (2025-08-18; 2508.13009) | Real-time interactive world model | K; **text removed** | 6-frame KV; no memory (stated) | 25 FPS 352×640, 1×H100, 1.8B [cited] | MIT | ego-only | Shows camera ≠ character |
| Matrix-Game 3.0 (2026-04-10; 2604.08995) | Camera-aware memory retrieval | K + mouse | memory retrieval by FOV | up to 40 FPS 720p, 5B, 8 DiT GPUs + 1 VAE GPU [cited] | Apache-2.0 | ego-only | Visual memory reference |
| WorldPlay / HY-World 1.5 (2025-12-16; 2512.14614) | Reconstituted context memory | K + text-triggered events | ~30 s horizon (stated) | 720p 24 FPS 8×H800 [cited] | Tencent license (excludes EU/UK/KR) | license | Text events in a world model |
| Genie 3 (2025-08; blog) | Closed world model | K, C, **promptable events** | ~1 min visual memory | 720p 24 FPS [vendor] | closed | not accessible | Upper-bound reference |
| HelloWorld (2026-08-05; 2608.05070) | Time-localized prompt attention masks | C + button → social reactions (wave, nod) | – | not stated | code (LTX-2 license) | not real-time | Training-free way to localize actions in time |
| SolarWM (2026-09-02; 2609.02886) | Open recipe making Wan2.2, LTX-2.5 or MiniMax-H3 causal and real-time | C (metric camera) | trained on 5 s, rolls out to hours | "real-time" claimed [cited] | Apache-2.0 code + data | camera-only | Alternative backbone route (incl. H3 camera variant) |
| EchoWM (2026-08-24; 2608.23189) | World model + audio (speech, sound) | 6-DoF + 3rd-person character | AR post-training | 720p; speed n/s [abstract-level] | not located | unreleased | Only world model we found that also generates audio |

### 2.2 Avatars, digital humans, and joint audio-video

| System (date; source) | Approach | Ctrl / beyond lip-sync | Identity / long horizon | Latency / HW (reported) | Avail. | Limitations | Relevance |
|---|---|---|---|---|---|---|---|
| LiveAvatar (2025-12-04; 2512.04677) | Audio-driven 14B streaming (Wan2.2-S2V base), timestep-forcing pipeline parallelism | Au | >10,000 s drift-free claim | 45 FPS, TTFF 1.21 s, 5×H800 [cited] | Apache-2.0 | lip-sync only | Baseline A0 candidate |
| SoulX-FlashTalk (2025-12-29; 2512.23379) | Streaming audio-driven avatar | Au | self-correction | 32 FPS, 0.87 s, 8×H800 [cited] | Apache-2.0 | 8 GPUs | Baseline candidate |
| Ditto (2024-11-29; 2411.19509) / LivePortrait (2024-07-03; 2407.03168) | Motion-space / keypoint talking head | Au + gaze/pose / retargeting | motion space | real-time; LivePortrait 12.8 ms/frame RTX 4090 [cited] | Apache-2.0 / MIT | head-only | **Cheap baseline A0** (single GPU) |
| TalkingMachines (2025-06-03; 2506.03099) | Audio-driven AR DiT (Wan I2V) + audio LLM | Au | sparse causal attn | 512×512, 2 NFE, 1–2 H100 + VAE GPU [cited] | not released | – | Architecture reference |
| LPM 1.0 (2026-04-09; 2604.07823) | Duplex performance model | Au + **text motion prompts**, 78 emotions | multi-granularity refs | "real-time" 480p [cited] | not released | closed | Closest to an instruction-driven persona |
| X-Streamer (2025-09-25; 2509.21574) | Unified thinker + streaming AV | speech/text/video in | global identity ref; 8K ctx ≈10 min | 25 FPS 256×256 2×A100 [cited] | not released | low res; context-only memory | Counter-evidence for the hypothesis (§1.1) |
| Wan-Streamer v0.1 (2026-06-23; 2606.25041) | E2E duplex AV foundation model | full duplex incl. interruptions | block-causal | ≈200 ms model, ≈550 ms total, 192p [cited] | [unverified] | 192p | E2E alternative (tightly coupled) |
| Hallo-Live (2026-04-26; 2604.23632) | Streaming joint AV (from Ovi) | T → AV | – | 20.38 FPS, 0.94 s, 2×H200 [cited] | not located | – | Only streaming joint-AV with numbers |
| Vidu S2 (2026-09-10; 2609.11638) | Interactive avatar with dynamic references | voice instructions, outfit/background swap | degrades > 90 s dance | 720p 25–42 FPS, HW n/s [cited] | demo only | closed | Dynamic reference = visual memory re-injection |
| **MiniMax H3** (2026-07-31; blog) | 33B joint video+audio DiT (Qwen3-VL-32B encoder) | T, first/last frame, refs; 32 kHz stereo audio | clip-level | offline: ≈85 s for 5.2 s clip on 4×H200 [cited: vLLM-Omni community] | Open weights, H3 Community License (excludes EU/UK/KR/US territories) | 4–15 s clips, no streaming | **Claimed basis of the reference agent** (unverified) |

### 2.3 Live agents, orchestration and control

| System (date; source) | Approach | Control interface | Memory | Latency / HW (reported) | Avail. | Limitations | Relevance |
|---|---|---|---|---|---|---|---|
| Moshi (2024-09-17; 2410.00037) | Full-duplex speech-text LM | persona via prompt/fine-tune | context | ≈200 ms practical on L4 [cited] | Apache-2.0 code, weights | weak reasoning | Duplex front-end option |
| Qwen3-Omni (2025-09-22; 2509.17765) | Thinker–Talker MoE | text prompt, tools | context | 234 ms theoretical first packet [cited] | Apache-2.0 | – | Omni front-end option |
| Pipecat / LiveKit Agents (2023– / 2026-06 turn detector) | Pipeline frameworks with VAD, turn detection, barge-in | pipeline graph | app-level | ≈1,293 ms typical cascade; 1,500 ms target [vendor: pipecat2026primer] | BSD-2 / Apache-2.0 | – | Reuse for orchestration |
| GPT-Live-1 / Gemini Live (2026-09) | Duplex front-end delegating to back-end reasoner | tools, async calls | session | [vendor] | API | closed | Validates the front/back split |
| Tavus CVI (Phoenix-4, 2026-02) | Cascaded video-call agent | persona config | "long-term memory module" | sub-600 ms [vendor, secondary] | API | closed | Closest commercial analogue |
| Neuro-sama (2022-12 debut) | LLM + TTS + Live2D/3D rig (not generated video) | chat, games | undisclosed | – | closed | – | Livestream reference class |
| PACE (2026-08-07; 2608.07631) | Playback-aligned context for duplex voice | – | – | GCM accuracy 25.0→96.3% [cited] | [unverified] | audio only | Basis of contribution 3 |
| VideoDirectorGPT (2023-09-26; 2309.15091), VISTA (2025-10-17; 2510.15831) | LLM planning / offline generate-judge-refine | layouts, prompts | – | offline | code | offline | IR and verifier design reference |
| EchoChain (2026-04-08; 2604.16456) | Interruption benchmark (speech) | – | – | no system > 50% pass [cited] | – | speech only | Evaluation template |

### 2.4 Memory systems and evaluation

| System / benchmark (date; source) | Mechanism / what it measures | Write–update–forget | Reported (as cited) | Avail. | Limitation for us | Relevance |
|---|---|---|---|---|---|---|
| MemGPT/Letta (2023-10-12; 2310.08560) | OS-style tiers, self-editing | agent-initiated, hot path | DMR 93.4% (GPT-4 Turbo) | Apache-2.0 | extra LLM calls per turn | Storage tiers |
| Generative Agents (2023-04-07; 2304.03442) | Memory stream: recency, importance, relevance; reflection | write-all, reflect | believability gain; documents hallucinated embellishments | code | cost; false memories | Persona memory template |
| Mem0 (2025-04-28; 2504.19413) | Extract → ADD/UPDATE/DELETE/NOOP | synchronous extraction | LoCoMo: full-context 72.90 > Mem0 66.88; p95 1.44 s vs 17.12 s | Apache-2.0 | LLM-judged deletes | Shows the need for simple baselines |
| Zep/Graphiti (2025-01-20; 2501.13956) | Bi-temporal KG, invalidation that keeps history | ingestion → edges | DMR 94.8% | Apache-2.0 | history vs erasure tension | Provenance and time model |
| LightMem (2025-10-21; 2510.18866) | Sleep-time offline consolidation | offline | up to +7.7% / +29.3% accuracy, 38× / 20.9× fewer tokens | code | – | Latency-bounded write policy |
| LongMemEval (2024-10-14; 2410.10813; ICLR 2025) | Extraction, multi-session, temporal, knowledge-update, abstention | – | long-context −30–60% | GitHub | text-only | **Primary text-memory benchmark** |
| MemoryAgentBench (2025-07-07; 2507.05257) | Incl. selective forgetting | – | SF multi-hop ≤ 28% | GitHub | – | Correction and forgetting |
| GateMem (2026-06-17; 2606.18829) | Multi-principal access control + deletion | – | no method strong on all three | GitHub | preprint | Public/private template |
| K-Bench (2026-09-11; 2609.12808) / Execution-state unlearning (2026-09-04; 2609.04875) | Leak after deletion across agent channels | – | 22–86% leak | – | preprints | Deletion verification |
| MINJA (2025-03-05; 2503.03704) | Query-only memory injection | – | high injection success [cited] | – | – | Viewer poisoning threat model |
| WorldMem (2025-04-16; 2504.12369), Context-as-Memory (2025-06-03; 2506.03141) | Pose-indexed frame memory for world revisits | per rollout | revisit consistency | code | scene, not user memory | Keep distinct from user memory |
| Full-Duplex-Bench v1/v2 (2025-03-06; 2025-10-09) | Pause, backchannel, turn-taking, interruption; multi-turn correction | – | – | GitHub | speech only | Voice evaluation |
| Multi-IF (2024-10-21; 2410.15553) | Multi-turn instruction following | – | o1-preview 0.877 → 0.707 turn 1→3 | yes | text only | Instruction-following eval |

---

## 3. Reference agent (qualitative)

Observed on `twitch.tv/sylar_nv`, evidence accessed 2026-09-24 17:25–17:40 UTC. Details and evidence table are in
`docs/notes/reference_agent_and_minimax_h3.md`.

**Channel.** Created 2026-09-18, 4 followers, 43 VODs (≈27.8 h) as of access time. No public description of the
implementation.

**Observed format.**
- From 2026-09-21 the channel shows a stable photoreal persona: a woman in a Hanfu-style robe reading in a classical
  study. An overlay advertises `!ask` commands: turn a page, nod, wave, sip tea, tell a story.
- It responds to chat requests. One observed tea-drinking response came ≈15–20 s after the request (a single sample;
  chat/video time alignment not validated).
- Near-continuous speech with lip motion.
- One visible scene discontinuity.
- Transcoded output 960×544 at 24 fps.
- Early streams showed a "segment N · 13 s" counter.

**Implementation.**
- "Based purely on MiniMax H3" is **owner-provided and unverified**.
- The 24 fps output and ~13 s segments fit H3's 4–15 s clip regime, but this is not proof.
- H3 is an offline clip model with no official streaming mode [cited: minimax2026h3blogvideo]. A live agent built on
  it probably schedules clips. This is inference, not verified.

**Use in this project.** A **qualitative reference** for the intended experience: persistent persona, chat-triggered
actions and speech. It is **not a quantitative baseline**. A fair comparison would need:
- archived VODs (they expire);
- chat-to-video time alignment;
- a scripted prompt set sent from a test account;
- the operator's cooperation and consent.

If those become available, the metrics in the proposal (TVC, instruction success, lip-sync, identity drift, memory
probes) are directly applicable.

---

## 4. Implications for the proposal

1. **Backbone fit.** LingBot-World 2.0 is a camera-controlled *world* model, not an avatar model.
   - Verified mid-stream control: camera only.
   - Character actions require prompt switching, which is engineering (class C) on the streaming path. Whether prompts
     actually produce the actions with this checkpoint is class B.
   - Lip-synced speech is class D.

   The demo scenario must therefore be chosen to fit verified affordances: a **third-person or first-person "explorer"
   persona with voice-over speech**, not a face-to-camera talking head. The talking-head experience is covered by
   baseline A0 (LLM + TTS + audio-driven avatar), which also tests whether a world model is needed at all.
2. **The scientific contribution is not the integration.** It is (a) capability-grounded closed-loop control with online
   verification; (b) the TVC metric and its characterization; (c) provenance- and scope-safe memory; (d) an evaluation
   protocol.
3. **Hardware risk is first-order.**
   - All real-time LingBot numbers come from H200 multi-GPU setups.
   - Local cards report as "L20X" (Ada, CC 8.9, 143,771 MiB). Their identity is unresolved.
   - A prior local run had FlashAttention unavailable.
   - Milestone M0 must measure before any latency target is treated as achievable.
