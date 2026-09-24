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

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/related_work.md =====
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

===== FILE: docs/backbone_verification.md =====
# Backbone Verification: LingBot-World 2.0 in vLLM-Omni

> Deliverable for goal.md §4. It is based on the audit in `docs/notes/backbone_lingbot_world_vllm_omni.md`
> (reproduced below), with the independent checks Claude made on 2026-09-25 listed first.
> Inspected implementation: upstream `vllm-project/vllm-omni` `main` @ `7b4dc7633bde8642f0c05f77bd018751541df404`
> (2026-09-24), a read-only clone at `external/vllm-omni`. No GPU job was run, so **every latency number here is
> upstream-reported (class B) or derived**, never measured locally.

## Independent spot-checks (Claude, 2026-09-25)

| Claim from the audit | Check | Result |
|---|---|---|
| LingBot registers only the `camera` interaction modality | Read `vllm_omni/diffusion/interaction/registry.py:17-28` | Confirmed: `"LingBotWorldCausalDMDPipeline": {"camera": SE3DeltaCameraHandler}`. Only the Helios pipelines register `prompt` |
| An unsupported modality fails | Read `vllm_omni/diffusion/interaction/coordinator.py:59-65,107` | Confirmed: `get_handler` raises `ValueError("interaction modality ... is not supported")`. `enqueue_parts` resolves all handlers before enqueueing |
| The WS server returns `interaction_failed` | Read `vllm_omni/entrypoints/openai/serving_video_output_stream.py:461-477` | Confirmed: an exception from `submit_interaction_async` sends `code="interaction_failed"`. The ValueError propagating through `submit_interaction_async` to this handler was **not executed** |
| The upstream benchmark sends prompt updates | `benchmarks/lingbot_world/benchmark_lingbot_world_realtime.py:199-200` fires `workload.prompt_updates` | Confirmed that the code exists. It contradicts the registry. Unexecuted |
| Recipe facts (checkpoint, license, 480x832, `max_num_seqs=1`, single replica, no stateful streaming VAE in the tick example) | Read `recipes/Robbyant/LingBot-World-2.0.md` in full | Confirmed |
| Local GPU identity | `nvidia-smi --query-gpu=name,compute_cap,memory.total,power.limit` and `nvidia-smi -q` | NVML reports **"NVIDIA L20X", architecture "Ada Lovelace", compute capability 8.9**, device ID 0x26BA10DE, **143,771 MiB, 700 W**. The memory and power figures match an H200 SXM, and an upstream PR author says "L20X" is an H200 BIOS mislabel. The architecture and compute capability do not match H200 (9.0). **Identity unresolved.** It matters because kernel selection (FA3, FP8 paths) depends on the reported capability |
| Prior local runs of LingBot v2 on this hardware | Read-only look at `/data/zhoutaichang/feature/lingbot-world-v2-quality/logs/*.log` (official `generate.py`, 2026-09-11) | Those runs report `FA2 False FA3 False` (an SDPA fallback) and end in tracebacks. **No usable timing.** This is evidence that the software stack on this machine is not turnkey |

**Smallest experiment that resolves the latency question (M0 in the proposal):**
`gpu run --gpus 1 --timeout 1h --note "live-agent M0" -- vllm serve robbyant/lingbot-world-v2-14b-causal-fast-diffusers --omni --deploy-config vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`,
then `benchmarks/lingbot_world/benchmark_lingbot_world_realtime.py --num-chunks 16`. Repeat with 4 GPUs and
`benchmarks/lingbot_world/configs/usp4_compiled.yaml`. In the same reservation, record `torch.cuda.get_device_capability()`.

---


- Audit date: 2026-09-25. Read-only: no GPU jobs were run and no weights were downloaded.
- Repo: `/data/zhoutaichang/live-agent/external/vllm-omni`, upstream `main` @ `7b4dc7633bde8642f0c05f77bd018751541df404` (2026-09-24).
  All `path:line` references below are relative to this checkout and this commit.
- Classes: **A** = present in the code I inspected (read, not executed, unless noted). **B** = reported upstream
  (paper, model card, or PR body) but not checked locally. **C** = needs engineering work. **D** = needs new training or research.
- Where a finding comes only from reading the code and I did not run anything, it is marked *(code-read, not executed)*.

---

## 0. TL;DR for the live-agent proposal

LingBot-World 2.0 in vLLM-Omni is an **image-conditioned, camera-controlled world model**. It streams fragmented-MP4
chunks of 12 frames (9 for the first chunk) at 480x832. The only control you can change mid-session over the
public WebSocket is **structural SE(3) camera motion**.

- **Mid-session text prompt changes do not work on the public stepwise path.** The interaction registry registers
  only `camera` for `LingBotWorldCausalDMDPipeline` (`vllm_omni/diffusion/interaction/registry.py:25-27`). A
  `session.interaction` that carries `event.prompt` reaches `InteractionCoordinator.get_handler("prompt")`, which
  raises (`vllm_omni/diffusion/interaction/coordinator.py:59-65`). The WS server then answers with
  `interaction_failed` (`serving_video_output_stream.py:466-477`). Prompt switching exists only on the deprecated
  in-process "tick" path, and that path outputs latents only (`pipeline.py:1531-1535`).
- There is **no character, avatar, body, face, or lip control and no audio**. Upstream says character actions
  (attacking, archery, spell-casting) come from *chunk-wise text prompts* (arXiv 2607.07534). The vLLM-Omni stepwise
  server cannot express those today because it has no prompt interaction for this pipeline.
- **Memory is a sink plus a rolling window**, not long-term memory. The checkpoint config has `sink_size=9` and
  `sliding_window_num_frames=18` latent frames. That is the first 3 chunks plus the most recent 3 chunks
  (~36 px frames ≈ 2.25 s at 16 fps). The paper itself says regions that leave the window are "regenerated rather
  than recalled".
- **Performance on this machine class (reported by upstream PR authors, not measured by me):** on 4xH200 with
  Ulysses SP=4, compiled, 4 DMD steps, 480x832, the steady cadence is **~549 ms per 12-frame chunk**
  (≈21.9 frames/s produced) and time to first chunk (TTFC) is **~1.07 s** (PR #7749, 2026-09-24). On 2xH200 the
  cadence is ~892–896 ms per chunk. On 1 GPU, eager, it is ~3241 ms per chunk (PR #7645, older head).
- **Instruction-to-visible camera response is at least one chunk boundary away.** An event is applied at the next
  AR-block boundary, so the latency is about 1–2 chunk intervals plus transport and client buffer:
  ≈0.55–1.1 s on 4xH200 before buffering *(derived, not measured)*.

---

## 1. Checkpoints, pipeline classes, variants, hardware, parallelism

| Item | Value | Evidence |
|---|---|---|
| Supported checkpoint (only one) | `robbyant/lingbot-world-v2-14b-causal-fast-diffusers` | `recipes/Robbyant/LingBot-World-2.0.md:8,277`; `tests/e2e/online_serving/test_lingbot_world_v2_stepwise.py:33` |
| Pipeline class | `LingBotWorldCausalDMDPipeline` (nn.Module + SupportImageInput, SupportsStepExecution, InteractionMixin …) | `vllm_omni/diffusion/models/lingbot_world/pipeline.py:571-592` |
| Transformer class | `CausalLingBotWorldTransformer3DModel` | `.../lingbot_world/transformer.py:805-843` |
| Stage topology registration | `LINGBOT_WORLD_PIPELINE` (model_type `lingbot_world`, 1 diffusion stage, final output `video`, **no default deploy config**) | `vllm_omni/model_executor/models/lingbot_world/pipeline.py:1-37` |
| Pre/post-process hooks | `get_lingbot_world_pre_process_func`, `get_lingbot_world_post_process_func` | `vllm_omni/diffusion/registry.py:666,738`; `pipeline.py:395-568` |
| Variant supported | Only the **causal-fast (DMD-distilled)** variant, pinned to 4 steps with timesteps (1000, 750, 500, 250); any other step count is rejected | `pipeline.py:111`, `pipeline.py:1007-1014` |
| Variants not supported | causal-pretrain, bidirectional, 1.3B, Cache-DiT, TeaCache, SP other than Ulysses, PP/CFG/VAE-parallel, HSDP | `recipes/.../LingBot-World-2.0.md:277,290-292`; `pipeline.py:245-280` |
| Architecture (local checkpoint config) | 40 layers, 40 heads x 128, ffn 13824, in_ch 36 (= 16 noise + 4 mask + 16 image latents), out 16, patch (1,2,2), text_dim 4096 (UMT5), `sink_size 9`, `num_frames_per_block 3`, `sliding_window_num_frames 18`, `local_attn_size -1` | `/data/models/hub/models--robbyant--lingbot-world-v2-14b-causal-fast-diffusers/snapshots/59cccf49…/transformer/config.json` |
| Official README uses a different sink | Official `generate.py` example passes `--local_attn_size 18 --sink_size 6` (vs 9 in the diffusers config) | same snapshot `README.md` (Inference section). Consequence not verified. |
| Execution modes | (a) offline request mode (whole trajectory → MP4); (b) **stepwise streaming** (one request = whole rollout, 1 chunk per AR block); (c) deprecated "tick" mode (1 block per `generate()`, latent output) | `recipes/.../LingBot-World-2.0.md:17-32` |
| Deploy config for streaming | `vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`: 1 stage, `devices "0"`, `max_num_seqs 1`, `enforce_eager true`, `engine_backend ARDiffusionEngine`, `step_execution/streaming_output true`, `ar_diffusion_height 480`/`width 832`, `gpu_memory_fraction 0.6`, `warmup_cudagraph true` | `vllm_omni/deploy/lingbot_world_v2_stepwise.yaml:10-44` |
| Realtime topology | `benchmarks/lingbot_world/configs/usp4_compiled.yaml`: 4 GPUs, Ulysses SP=4, TP=1, `enforce_eager false` | `benchmarks/lingbot_world/README.md:47-69` |
| Parallelism accepted | pure Ulysses (`sequence_parallel_size == ulysses_degree`, ring=allgather=1, `ulysses_mode="strict"`, no a2a permute); TP=1/2 validated; online FP8 linears (experimental) | `pipeline.py:245-280`; recipe `:218-255,259-269` |
| Hardware validated (recipe) | NVIDIA H200 and B200; no AMD, Ascend, or Intel support is claimed | recipe `:11,292` |
| Resolution cap | `height*width <= 480*832`, divisible by 16; the served resolution must equal the load-time `ar_diffusion_height/width` | `pipeline.py:114,1000-1005,1880-1884` |
| Concurrency | `max_num_seqs` must be 1; a single replica only (no session-affine routing); KV spec `session_capacity=2` resident sessions | `docs/design/feature/realtime_ar_diffusion.md:161-176`; `pipeline.py:784` |
| License | Checkpoint: **CC BY-NC-SA 4.0 (non-commercial)**. vLLM-Omni integration: Apache-2.0 | recipe `:14-15`; local model card front-matter `license: cc-by-nc-sa-4.0` |

**Local weights (read-only listing, nothing downloaded):**

- `/data/models/hub/models--robbyant--lingbot-world-v2-14b-causal-fast-diffusers` is a complete snapshot
  `59cccf49…`, 81 GB (transformer 8 shards, UMT5 text encoder, Wan VAE).
- `/data/models/lingbot-world-v2-1.3b-causal-fast-diffusers` (18 GB) and `/data/models/lingbot-world-v2-1.3b-causal-fast`
  (6.4 GB). vLLM-Omni does not claim support for the 1.3B model.
- `/data/models/hub/models--robbyant--lingbot-world-fast-diffusers` (81 GB) is the v1 LingBot-World-Fast
  (Apache-2.0), which vLLM-Omni does not use.
- The `models--robbyant--lingbot-world-v2-14b-causal-fast` hub dir contains only refs (1.5 KB), not weights.
- Access: the shared `/data/models` belongs to the machine, not to `/data/zhoutaichang`. Confirm you may use it.

**Machine GPUs** (`nvidia-smi --query-gpu=name,memory.total`): 8 x "NVIDIA L20X", 143771 MiB each. PR #7749's author
says that on their node this NVML string is a BIOS mislabel of **H200**, and PR #7645 reports the same string. That
PR was probably measured on this machine or a sibling. **I have not verified which GPU these cards are.**

## 2. Inputs and conditioning (formats and where they are parsed)

| Input | Format | Where parsed |
|---|---|---|
| First frame (required) | Exactly one image: PIL, tensor `[3,H,W]`/`[1,3,H,W]`, or path, ≤ 4096x4096 source px. WS: `image_reference` (`http(s)` or `data:` URL) | `pipeline.py:403-429` (pre-process), `:922-930`, `:957-970`; WS `serving_video_output_stream.py:558-560,609-626` |
| Image usage | VAE-encoded **only at chunk 0**. Later blocks feed zero pixel frames to a stateful causal encoder, and once the encoder reaches a fixed point it stops running. You **cannot re-condition on a new image mid-session.** | `pipeline.py:1139-1181,1218-1232` |
| Text prompt | Non-empty string, UMT5, `max_sequence_length` must be exactly 512, LRU cache of 4 encodes; cross-attn K/V cached per session | `pipeline.py:115-119,917-918,1033-1039,1465-1508,1334-1376` |
| Negative prompt | Rejected on `session.interaction`; start-time negative prompt is passed through but LingBot is CFG-free (4-step DMD) *(code-read)* | `serving_video_output_stream.py:401-407,553-554` |
| Camera trajectory (offline / `action_path`) | Directory with `poses.npy` `[F,4,4]` (C2W) and `intrinsics.npy` `[F,4]` (fx,fy,cx,cy at an 832x480 reference), 1..4096 frames. Served only from a trusted root (`model_config.lingbot_action_root` / `VLLM_OMNI_LINGBOT_ACTION_ROOT`) | `camera.py:22,46-84,165-228`; `pipeline.py:489-519` |
| Camera action script (request-scoped) | `extra_params.camera_action_script`: list with one entry per chunk, each entry `[[keys],[keys],[keys]]` (3 latent frames), keys from `w a s d i j k l` | `actions.py:26-31,94-117`; `pipeline.py:479-487,1887-1891` |
| Keys → pose | Integrated in fp64: move 0.05 per latent frame, pitch 4°, yaw 6°, pitch clamp 85°, focal 500 px (the SGLang adapter constants) | `actions.py:275-339` |
| Mid-session camera (public) | `session.interaction` → `event.multi_modal_data.camera = {mode: "target"|"velocity", data: {translation:[x,y,z], rotation:[qx,qy,qz,qw]}}`, Unity frame (+X right, +Y up, +Z forward). `data.actions` (WASD) is rejected | `interaction/modality_handlers/camera.py:104-195,390-393`; `docs/serving/streaming_video_output_api.md:86-113` |
| Camera → model | Poses become first-relative framewise deltas, then a 6-ch Plücker embedding `[origin_xyz, dir_xyz]`, pixel-unshuffled x8 to the latent grid (`6*8*8` channels), then patch embed and per-layer `cam_injector` modulation | `camera.py:392-493`; `pipeline.py:537-543,1255-1332`; `transformer.py:587-614,905-924` |
| Tick-path controls (deprecated) | Opaque `ARDiffusionControlInput(track, schema, data)` with schemas `lingbot.camera_actions.v1` (3 frames of keys) / `lingbot.camera_trajectory.v1` | `pipeline.py:434-478`; recipe `:209-214` |
| Other | `flow_shift` (default 5.0), `seed`, `fps` (MP4 label only; the checkpoint declares no fps) | `pipeline.py:952-955`; `benchmarks/lingbot_world/README.md:90-111` |

## 3. Can prompt / camera / actions change mid-session?

| Control | Public stepwise WS path | Deprecated tick path | Evidence |
|---|---|---|---|
| Camera (SE3 target/velocity) | **Yes (A)**. Queued, then applied at the next chunk boundary. Velocity is held until replaced. Target lerps over `transition_chunks` (default 1). Events map to latent frames by arrival time within the chunk | Yes (keys or trajectory per tick) | `camera.py:197-359`; `diffusion_model_runner.py:1427-1431`; `pipeline.py:1998-2032` |
| Camera script + live interaction | **Mutually exclusive.** If `camera_action_script` or `action_path` was given, any live camera event raises | n/a | `pipeline.py:1956-1962,1985-1991` |
| Text prompt | **No (C).** `prompt` is not registered for LingBot, so `get_handler` raises and the server reports `interaction_failed`. The pipeline also encodes the prompt once in `prepare_encode` and calls `_ar_text_caches(..., invalidate=False)` for every chunk, so registering `PromptInteractionHandler` alone would not refresh cross-attn K/V *(code-read, not executed)* | **Yes (A, latent-only)**. `ar_diffusion_tick.prompt` is re-encoded (LRU-cached) and session text K/V is invalidated when the prompt key changes | `registry.py:17-28`; `coordinator.py:59-65,107`; `pipeline.py:1893-1897,1935,2053-2056`; tick: `pipeline.py:1437-1463,1538,1570-1574,1623-1628` |
| Upstream benchmark sends prompt updates | `benchmarks/lingbot_world/workload.py:145-165` builds `session.interaction` with `event.prompt`; by the analysis above this would fail for LingBot. **This contradicts the registry and has not been run.** | – | `benchmarks/lingbot_world/README.md:164-192` |
| Image / reference | No | No | `pipeline.py:1166-1172` |
| Character actions / events | **Not exposed.** Upstream implements them as chunk-wise captions (needs prompt switching). Space (jump) / P (glide) / U/O/F/G event keys from the paper are not in vLLM-Omni's key set | – | `actions.py:29`; arXiv 2607.07534 |

Is the prompt re-encoded per chunk? On the tick path, `encode_prompt` is called on every tick but hits the
4-entry cache, and text K/V is rebuilt only when the (prompt, len, dtype) key changes (`pipeline.py:1455-1463`).
On the stepwise path the prompt is encoded once per request (`pipeline.py:1893`).

## 4. Streaming mechanics

| Aspect | Value | Evidence |
|---|---|---|
| AR block | 3 latent frames; 4 DMD probe forwards + 1 clean-KV commit forward per block (last-step KV reuse is experimental and skips the commit) | `transformer.py:841`; `pipeline.py:2078-2153`; `dmd_block.py`; recipe `:56-74` |
| Pixel frames per chunk | Chunk 0 = 9 frames. Later chunks = 12 frames with the session-owned streaming Wan decoder. Without it, every chunk is 9 frames with seams | `pipeline.py:2186-2197,1806-1840` |
| num_frames constraint | `(num_frames-1) % 4 == 0` and latent frames % 3 == 0, i.e. `9 + 12k`. Chunks = `((num_frames-1)//4+1)//3` | `pipeline.py:1016-1031`; recipe `:49-54,152-154` |
| Session length | Fixed up front by `num_frames` in `session.start` (`total_chunks` at `pipeline.py:1886,1922`). There is **no API to extend** a session. No hard cap in code (`num_frames` ≤ int64; temporal RoPE extended on the fly `transformer.py:1091-1099`, PR #6838; KV metadata bounded PR #7498). Longest upstream-validated run in PRs: 40 chunks (477 frames) | `protocol/videos.py:162`; PR #7645 |
| KV cache | Runner-owned paged AR-Diffusion KV (`ar_diffusion_kv`, not the generic `paged_scheduler`); chunk-window eviction with protected sink | `experimental/ar_diffusion/kv_cache/config.py:34-61`, `manager.py:208-331,620`; `docs/design/feature/diffusion_paged_kv_cache.md:153-156,295` |
| Window | Sink 9 latent frames (first 3 chunks) + recent 9 latent frames (3 chunks). The key count grows until chunk 6 | `pipeline.py:748-782`; `benchmarks/lingbot_world/README.md:113-124` |
| Memory accounting | `required = scratch + pages + cross-attn + model-owned state` (condition, camera modulation, 2x encoder histories, streaming decoder ≈1801 MiB at 832x480 bf16). Upstream reports a two-session KV requirement of 57.1 GiB (PR #5491, H200) | `pipeline.py:85-92,794-800`; design doc `:111-159` |
| Scheduling | Stepwise: the scheduler groups a block's steps into one runner call (`supports_chunk_step_grouping`). Interactions are applied only at chunk boundaries | `pipeline.py:582-585`; `experimental/ar_diffusion/runner.py:346-430`; PR #7648 |
| Session state | `session_id == request_id` on the stepwise path. State: paged KV, text K/V, encoder cache, camera tail/pitch, streaming decoder cache | `pipeline.py:173-193,1936,2141-2177`; `runner.py:294-310` |

## 5. Interrupt, cancel, reset, resume

| Operation | Stepwise WS (public) | Tick / Python API | Evidence |
|---|---|---|---|
| Cancel | `session.stop` → `engine.abort(request_id)` → session done `stopped:true`. A client disconnect also aborts. Stall timeout 60 s, start timeout 10 s | – | `serving_video_output_stream.py:71-75,168-171,273-281,307-310` |
| KV release on cancel | Scheduler-finished/aborted request ids close the session KV | – | `runner.py:294-310` |
| Reset (restart at chunk 0) | **Not exposed** over WS (C) | `ARDiffusionSession.reset()` / `ARDiffusionSessionManager.reset_session()`; runner `reset_session`; `extra_args["reset"]` | `experimental/ar_diffusion/session.py:468-516,565-576`; `runner.py:49-58,228-234`; `pipeline.py:885-891` |
| Failure semantics | Forward exception → session KV released (fail-closed); no retry of the same chunk; tick sessions go to FAILED and need reset/close | same | `runner.py:258-292`; design doc `:80-109` |
| Resume / rewind / branch / checkpoint | **None** (C). No KV snapshot, rewind, or fork API | none | design doc non-goals `:211-222` |
| Eviction | LRU across resident sessions (capacity from memory, cap 2) | same | `runner.py:236-246` |
| Pause | None. The client can only stop pulling, which triggers the stall timeout | – | – |

## 6. What controls camera, what controls character, what controls scene

- **Camera / ego-viewpoint**: WASD/IJKL/SE3 only change the *camera trajectory* embedded as Plücker rays
  (`camera.py:425-493`). The code has no notion of a subject. The PR #7198 test prompt shows how a third-person
  character is produced *via text only* ("Third-person view from behind the officer … look-input is the only
  camera motion"), so any apparent character locomotion is the model's interpretation of camera motion plus the
  prompt. It is not a separate control.
- **Scene content**: Set by the first-frame image and the text prompt at start. On the public path it is fixed for
  the session, because the prompt cannot change (see §3).
- **Character / avatar / body / face / lips**: **No control of any kind** in the vLLM-Omni integration
  (verified: no such inputs in `_parse_request` `pipeline.py:893-1055`; the registry has only camera). Upstream
  (arXiv 2607.07534) claims character actions (combat, archery, spell-casting, shooting), jump/glide keys, and a
  "pilot agent" that plans character behavior. The actions go through **chunk-wise prompts**, and there is no
  identity or face control → B for game-style actions, **D for a persona avatar** (identity-preserving face, lip,
  and gesture control).

## 7. Audio

None. The pipeline outputs video frames and latents only (`pipeline.py:2159-2173`). The WS encoder produces an m4s
fMP4 video stream (`serving_video_output_stream.py:504-509`). No audio is mentioned in the LingBot-World or
LingBot-World 2.0 model cards, or in the upstream paper summaries I fetched. Speech and lip-sync would need a
separate TTS model plus a new audio-conditioned video model or adapter → **D**.

## 8. Latency, throughput, memory

All numbers below were **reported by upstream authors** in PR bodies or docs. **I measured none of them.**
The chunk length is 12 frames, and the RTF basis must be stated.

| Setup | TTFC | Steady per-chunk | Source (date) |
|---|---|---|---|
| 1 GPU ("L20X"=H200?), eager, stepwise WS | 2712–2726 ms | 3240.8–3241.8 ms (RTF@12 ≈ 3.24) | PR #7645 body (2026-09-21) |
| 4 GPU USP4 compiled, same PR head | 1541–1558 ms | 1354.9–1363.1 ms (RTF@12 ≈ 1.36; 0/33 chunks met 1 s) | PR #7645; README `benchmarks/lingbot_world/README.md:97-102` |
| 4xH200 USP4 after #7648 alone | – | 916–920 ms median (RTF@12 0.94) | PR #7648 (2026-09-21) |
| 4xH200 #7648 + #7651 (VAE width shard) | – | 721 ms median, p99 906 (RTF@16 0.99) | PR #7648 |
| 4xH200 latest main + decoder/RGB (+ FP8 selective, KV skip) | 1072–1082 ms | **548.68 ms** mean (chunks 6–38) | PR #7749 (2026-09-24) |
| 2xH200 full stack | – | ~892–896 ms | PR #7749 |
| Known issue | first chunk sometimes 5.5–7.5 s with contiguous KV gather default on | – | PR #7749 |
| SP scaling (81-frame offline request, H200) | – | AR-block GPU median 2397 / 1345 / 725 ms for SP1/2/4. Peak alloc 69.3/69.7/59.6 GiB | PR #6841 (2026-09-11) |
| Condition encode | 178 ms/block before the fixed point, which is reached by block 11 | `pipeline.py:1159-1161` |
| Streaming decoder state | ≈1801 MiB/session at 832x480 bf16 | `pipeline.py:85-92` |

**Upstream model claims (B):** 720p @ 60 fps for the distilled real-time variant, hour-level generation, "1.3B on a
single GPU" (arXiv 2607.07534 / model card). The paper summary I retrieved contains no hardware-specific FPS or
latency table. LingBot-World v1: "<1 s latency at 16 fps" (arXiv 2601.20540). **None of this is reproduced in
vLLM-Omni.** The best vLLM-Omni number is 480x832 at ≈22 produced frames/s on 4xH200.

**Derived instruction-to-visible latency (camera), not measured:**

- An event received during chunk N's generation is applied at the boundary after chunk N (`diffusion_model_runner.py:1427-1431`).
- Chunk N+1 then takes one interval T to generate, then the muxed bytes need about +45 ms (PR #7648 note).
- So latency ≈ (0..T) wait + T + delivery + client playback buffer. With T≈549 ms that is **≈0.6–1.15 s + buffer**
  (4xH200). With T≈3.24 s on 1 GPU it is **≈3.3–6.5 s**.
- Within a chunk, the event's arrival time selects the latent frame it starts at (`types.py:108-129`, `camera.py:265-278`).

## 9. Serving interface

- **Offline**: `Omni(...).generate(...)`, then `export_to_video` MP4 (`examples/offline_inference/diffusion/lingbot_world_v2.py:260-277`).
  Tick-mode in-process example writes latent `.pt` plus JSON per chunk
  (`examples/offline_inference/diffusion/lingbot_world_v2_realtime.py`; recipe `:76-110`).
- **Online**: `vllm serve robbyant/lingbot-world-v2-14b-causal-fast-diffusers --omni --deploy-config vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`
  (recipe `:121-134`); endpoint `WS /v1/realtime/video` (`api_server.py:1715`).
- **Protocol** (`serving_video_output_stream.py:1-27`; `docs/serving/streaming_video_output_api.md:32-50`):
  - Client → server: `session.start` {model, prompt, image_reference, width, height, num_frames, fps, seed, format:"m4s", extra_params{flow_shift, camera_action_script | action_path, video_codec_options}},
    `session.interaction` {interaction:{event_id, event:{prompt?, multi_modal_data?}, transition_chunks?}}, `session.ping`, `session.stop`.
  - Server → client: `video.start`; `video.chunk_metadata` {generation_chunk_index, num_frames, byte_length, started/active/completed_event_ids, transport_chunk_index} **followed by one binary fMP4 (m4s) frame**;
    `session.interaction.queued`; `session.pong`; `session.done`; `error`.
  - Only `m4s` is accepted. The default codec is `ultrafast`/`zerolatency` (`:257-261,500-509`).
- Deprecated tick transport is internal Python only (no HTTP).
- SGLang (external, B) offers a different WS API: `/v1/realtime_video/generate`, MessagePack, WebP/JPEG/raw frames,
  and prompt switching (SGLang cookbook). This is a possible alternative backend.

## 10. Integration points for an external controller (LLM planner) and what is missing

**Available (A):**

1. A controller can hold the WS and push SE3 `velocity`/`target` camera events with its own `event_id`s.
2. Per-chunk metadata echoes `started/active/completed_event_ids`, which gives closed-loop acknowledgement of when
   an instruction took effect.
3. `session.stop` for cancel.
4. `transition_chunks` for smoothing camera targets.
5. The Python-level `ARDiffusionSessionManager` for tick sessions, with prompt switching, reset, and close,
   latent output only.

**Missing:**

| Gap | Class | Smallest experiment to resolve |
|---|---|---|
| Mid-session prompt on stepwise path (register `prompt` handler + invalidate text K/V per chunk when the embed changes; embed lerp would need K/V rebuild per chunk) | C | On 1 GPU with the existing stepwise yaml: send one `session.interaction {event.prompt}` at chunk 3 of a 7-chunk session. Confirm `interaction_failed`. Then patch the registry to add `PromptInteractionHandler`, call `_ar_text_caches(state.prompt_embeds, invalidate=True)` when the prompt version changes, and check that chunk 4+ changes (CLIP-score vs both prompts). |
| Whether prompt switching causes character actions (per the paper's chunk-wise captions) with this checkpoint | B→D | Tick-path script (`lingbot_world_v2_realtime.py`) with a prompt event "the character swings a sword", decode latents offline, and inspect / VLM-judge. No server change is needed. |
| Session extension (open-ended length) / reset / rewind over WS | C | Add `session.reset` mapped to `runner.reset_session` and a "continue" that bumps `total_chunks`. Test that a 200-chunk session holds cadence and memory (log `torch.cuda.max_memory_allocated`). |
| Long-term memory beyond sink+window (revisit consistency, persona identity) | D | Loop-closure test: forward 10 chunks, backward 10 chunks, then compare the returned view to the original with LPIPS/DINO similarity. Expect a failure, as the paper admits. |
| Character / avatar / face / lip / gesture control | D | None possible without new conditioning. Probe the prompt-only persona with a talking-head prompt and measure identity drift (ArcFace cosine vs frame 0) over 40 chunks. |
| Audio / TTS / lip-sync | D | Out of scope for this backbone. Pair it with a separate audio-driven avatar model. |
| Reference-image re-conditioning mid-session (scene cut / new persona) | C/D | Engineering: close the session and start a new one with a new image (cost = TTFC ≈1.1 s on 4xH200). Research: inject a new condition into a running KV. |
| Resolution > 480x832 / 720p | C/D | The recipe restricts to ≤480x832 (`pipeline.py:1004-1005`). 720p would need a new `ar_diffusion_height/width` plus quality validation. The checkpoint's 720p ability is unverified. |
| Real-time on 1 GPU | C | Reproduce the benchmark: `gpu run --gpus 1 -- vllm serve … single_gpu_eager.yaml`, then `benchmark_lingbot_world_realtime.py --num-chunks 16`. The expected ~3.2 s/chunk means RTF > 3. Then try compile + FP8. |
| Verify reported 4-GPU cadence on this machine | B→A | `gpu run --gpus 4 --timeout 1h -- vllm serve … usp4_compiled.yaml` + benchmark `--num-chunks 40 --warmup-sessions 1 --sessions 3 --target-fps 12`. |
| Server-side per-chunk timestamps for instruction-to-pixel latency | C | Add a monotonic timestamp to the chunk metadata. Measure event-send → first chunk whose `started_event_ids` contains the event. |
| Multi-replica / multi-user | C | Needs session-affine routing (design doc `:170-172`). |

---

## Evidence table

| # | Claim | Evidence | Date | Class |
|---|---|---|---|---|
| 1 | Only `robbyant/lingbot-world-v2-14b-causal-fast-diffusers` is supported | `recipes/Robbyant/LingBot-World-2.0.md:8,277` | 2026-09-24 (HEAD) | A |
| 2 | Pipeline class `LingBotWorldCausalDMDPipeline`, 4 fixed DMD steps (1000/750/500/250) | `pipeline.py:111,571-592,1007-1014` | HEAD | A |
| 3 | LingBot-World v2 first landed in vLLM-Omni via tick sessions | PR #5491, merged 2026-08-16 (commit 3875f8ded) | 2026-08-16 | A |
| 4 | Stepwise streaming execution added | PR #6844, merged 2026-09-07 (5cd925631) | 2026-09-07 | A |
| 5 | Ulysses SP added; SP4 AR-block GPU median 725 ms (H200) | PR #6841, merged 2026-09-11 | 2026-09-11 | A (code) / B (numbers) |
| 6 | Camera SE3 interaction for streaming | PR #7198, merged 2026-09-20 (e36babd48) | 2026-09-20 | A |
| 7 | Interaction framework (prompt, then camera) refactor | PR #6294 (2026-09-07); midway prompt frontend PR #4652 (2026-07-27) | – | A |
| 8 | Registry: LingBot → `camera` only; Helios → `prompt` | `vllm_omni/diffusion/interaction/registry.py:17-28` | HEAD | A |
| 9 | Unsupported modality raises ValueError | `coordinator.py:59-65` | HEAD | A |
| 10 | Prompt event to LingBot on WS → `interaction_failed` | `serving_video_output_stream.py:461-477` + #8/#9 | HEAD | A (code-read, not executed) |
| 11 | Stepwise path encodes the prompt once and never invalidates text K/V | `pipeline.py:1893-1897,1935,2053-2056` | HEAD | A |
| 12 | Tick path supports prompt switching with K/V invalidation, latent output only | `pipeline.py:1437-1463,1531-1539` | HEAD | A |
| 13 | Image used only at chunk 0 | `pipeline.py:1166-1172,1218-1231` | HEAD | A |
| 14 | Keys WASD/IJKL only; 0.05 move, 4° pitch, 6° yaw | `actions.py:28-29,275-339` | HEAD | A |
| 15 | SE3 camera target/velocity semantics, applied at chunk boundary | `interaction/modality_handlers/camera.py:104-359`; `diffusion_model_runner.py:1427-1431` | HEAD | A |
| 16 | Camera script and live camera are mutually exclusive | `pipeline.py:1956-1962,1985-1991` | HEAD | A |
| 17 | Chunk = 3 latent frames = 12 px frames (9 for the first) | `pipeline.py:2186-2197`; `transformer.py:841` | HEAD | A |
| 18 | Sink 9 + window 18 latent frames | local `transformer/config.json`; `pipeline.py:748-782` | snapshot 59cccf49 | A |
| 19 | Official README uses `--sink_size 6 --local_attn_size 18` | local model card README | 2026-07-09 | B |
| 20 | Resolution ≤ 480x832, fixed at load | `pipeline.py:1004-1005,1880-1884`; yaml `:40-41` | HEAD | A |
| 21 | `max_num_seqs=1`, single replica, 2 resident sessions | design doc `:161-176`; `pipeline.py:784` | HEAD | A |
| 22 | WS cancel via `session.stop`/disconnect; no reset/rewind over WS | `serving_video_output_stream.py:168-171,307-310`; design doc `:211-222` | HEAD | A |
| 23 | Reset/close exist for tick sessions (Python) | `experimental/ar_diffusion/session.py:468-516`; `runner.py:228-234` | HEAD | A |
| 24 | Output = fMP4 (m4s) video chunks; no audio | `serving_video_output_stream.py:257-261,500-545`; `pipeline.py:2159-2173` | HEAD | A |
| 25 | 1-GPU eager ≈3241 ms/chunk; USP4 compiled ≈1359 ms/chunk (older head) | PR #7645 body; `benchmarks/lingbot_world/README.md:97-102` | 2026-09-21 | B (upstream-measured) |
| 26 | 4xH200 latest ≈549 ms/chunk, TTFC ≈1.07 s; 2xH200 ≈892–896 ms | PR #7749 body (ba3d48e1c) | 2026-09-24 | B (upstream-measured) |
| 27 | 4xH200 721 ms median with #7648+#7651 | PR #7648 body | 2026-09-21 | B |
| 28 | Two-session KV requirement 57.1 GiB (H200) | PR #5491 body | 2026-08-16 | B |
| 29 | "L20X" NVML string = H200 BIOS mislabel on the PR author's node | PR #7749 body; local `nvidia-smi` shows 8x L20X 143771 MiB | 2026-09-24 / 2026-09-25 | B (unverified here) |
| 30 | Streaming decoder ≈1801 MiB/session | `pipeline.py:85-92` | HEAD | A (comment-reported) |
| 31 | Paper: LingBot-World 2.0 "Infinite Worlds with Versatile Interactions", arXiv 2607.07534 v1 | https://arxiv.org/abs/2607.07534 | 2026-07-08 | B |
| 32 | Claims 720p@60fps distilled, hour-level horizon, 14B + 1.3B single-GPU | arXiv 2607.07534; local model card | 2026-07 | B |
| 33 | Character actions / events via chunk-wise prompts; Space jump, P glide; VLM Director/Pilot agents | arXiv 2607.07534 (HTML v1) | 2026-07-08 | B |
| 34 | Paper admits no true memory: revisited regions regenerated | arXiv 2607.07534 (HTML v1) | 2026-07-08 | B |
| 35 | v1 paper "Advancing Open-source World Models", arXiv 2601.20540; <1 s latency, 16 fps, minute-level | https://arxiv.org/abs/2601.20540; local v1 model card | 2026-01-28 | B |
| 36 | v1 checkpoints: base-cam, base-act, fast (Apache-2.0) | local `models--robbyant--lingbot-world-fast-diffusers` README | 2026-01-29 | B |
| 37 | v2 GitHub: robbyant/lingbot-world-v2, CC BY-NC-SA 4.0; 14B causal-fast/pretrain/bid, 1.3B causal-fast (2026-09-10) | https://github.com/robbyant/lingbot-world-v2 | 2026-09 | B |
| 38 | HF model `robbyant/lingbot-world-v2-14b-causal-fast-diffusers`, CC BY-NC-SA 4.0 | https://huggingface.co/robbyant/lingbot-world-v2-14b-causal-fast-diffusers ; local snapshot 59cccf49 | 2026-07-09 | A (weights present locally) |
| 39 | SGLang LingBot-World 2.0 cookbook: 8 GPU Ulysses-8, WS MessagePack, prompt switching | https://docs.sglang.io/cookbook/diffusion/LingBot-World/LingBot-World-2.0 | fetched 2026-09-25 | B |
| 40 | Upstream benchmark sends prompt updates although LingBot has no prompt handler | `benchmarks/lingbot_world/workload.py:145-165` vs `registry.py:25-27` | HEAD | C (inconsistency; unexecuted) |
| 41 | Persona avatar / face / lip / gesture control | none found | – | D |
| 42 | Audio / speech | none found | – | D |

## Capability classification summary

- **A (in code):**
  - image+text-conditioned start, 480x832
  - streamed fMP4 chunks over `WS /v1/realtime/video`
  - live SE3 camera (target/velocity)
  - request-scoped WASD/IJKL script
  - pose/intrinsics trajectory replay
  - sink+rolling-window paged KV
  - stop/abort, and event acknowledgement via chunk metadata
  - Ulysses SP, TP 1/2, online FP8
  - tick-path prompt switching, reset, and close (Python, latents only)
- **B (upstream-reported, not verified here):**
  - cadence numbers (≈549 ms/chunk on 4xH200, ≈3.2 s on 1 GPU)
  - 720p@60 fps, hour-level horizon
  - character actions via chunk-wise prompts; director/pilot agents
  - H200 identity of the local "L20X" cards
- **C (engineering):**
  - prompt interaction on the stepwise path (with text-K/V invalidation)
  - WS reset / extend / rewind / snapshot
  - image re-conditioning by session restart
  - multi-replica routing
  - per-chunk server timestamps
  - >480x832 resolution
- **D (training/research):**
  - persona avatar identity, face, lip-sync, gesture control
  - audio
  - long-term memory beyond the ~6-chunk window
  - reliable character-behavior control with this checkpoint

===== FILE: docs/reviews/cp2_ev_video_synthesis.md =====
# Literature review: real-time video generation, interactive world models, controllable generation, streaming avatars, joint audio-video

*Research note (supporting material, not authoritative). Compiled 2026-09-25.*
*Scope: areas (a) to (e) of the live-agent proposal. The LingBot-World 2.0 / vLLM-Omni backbone is covered in depth in
[`backbone_lingbot_world_vllm_omni.md`](backbone_lingbot_world_vllm_omni.md). MiniMax H3 as a reference agent is covered in
[`reference_agent_and_minimax_h3.md`](reference_agent_and_minimax_h3.md).*
*BibTeX: [`bib_video_avatars.bib`](bib_video_avatars.bib). Keys are given in brackets like `[yin2024causvid]`.*

**How to read the numbers.** Every speed, latency or hardware figure below is **cited**: copied from the paper abstract, paper body,
official README or vendor page named next to it. None was measured locally. Our hardware (8x L20X, see `docs/PROJECT.md` A1) is
different from the H100/H800/H200 setups most papers report, so no figure transfers directly. "Vendor claim" marks figures from
product pages or blogs that have no paper, code or independent benchmark behind them. "Unverified" marks items I could not confirm from a
primary source.

**Verification method.** All 103 arXiv IDs cited here were resolved through the arXiv export API (title, authors, v1 date) on
2026-09-25. Licenses were read from the GitHub license API or Hugging Face model-card metadata the same day. Performance details not in
the abstracts come from the arXiv HTML full text, where stated.

---

## 1. Synthesis

### 1.1 What is effectively solved (as of Sep 2026)

1. **Turning a bidirectional video DiT into a real-time causal streamer is now a standard recipe.** The recipe:
   (i) start from a bidirectional DiT, usually from the Wan2.1/2.2 family;
   (ii) initialize a causal (block- or frame-autoregressive) student, first via ODE-trajectory distillation (CausVid
   `[yin2024causvid]`), later via a causal teacher (Causal Forcing `[zhu2026causalforcing]`) or causal consistency distillation
   (Causal Forcing++ `[zhao2026causalforcingpp]`);
   (iii) close the train/test gap by training on the model's own rollouts with a distribution-matching (DMD) or adversarial loss
   (Self Forcing `[huang2025selfforcing]`, APT2/AAPT `[lin2025aapt]`, Self-Forcing++ `[cui2025selfforcingpp]`);
   (iv) run inference with a rolling KV cache plus an *attention sink* (LongLive `[yang2025longlive]`, Rolling Forcing `[liu2025rollingforcing]`).
   Several full-stack open recipes exist: minWM `[zhao2026minwm]`, SolarWM `[huang2026solarwm]`, AlayaWorld `[alayaworld2026alayaworld]`.
   *Cited envelope:* a 1.3B model at 480p reaches about 16 to 21 FPS on one H100, with about 0.8 s to the first chunk (Self Forcing, LongLive).
   An 8B model reaches 24 FPS at 736x416 on one H100 (AAPT). At 14B, real time needs multi-GPU pipelines. Helios `[yuan2026helios]`
   claims 14B at 19.5 FPS on one H100, but its code is not yet released.
2. **Minute- to hour-scale stability without collapse** is claimed by many systems. Examples: Self-Forcing++ (4 min 15 s), LongLive
   (240 s), LiveAvatar (>10,000 s), Visko Orbis (hour scale), LingBot-World 2.0 ("unbounded"). Most claims are demonstrated on
   curated prompts. Independent benchmarks disagree: WorldRoamBench `[xu2026worldroambench]` (10+ models) and WBench `[ying2026wbench]`
   (20 models) both report that *no* model is strong on action following, visual stability, physics and memory at the same time.
3. **Audio-driven talking avatars at real-time rates.** Lip-synced talking-head and upper-body streaming now runs at 25 to 45 FPS
   using multi-GPU 14B models:
   LiveAvatar `[huang2025liveavatar]` (45 FPS, TTFF 1.21 s, 5xH800);
   SoulX-FlashTalk `[shen2025soulxflashtalk]` (32 FPS, 0.87 s start-up, 8xH800);
   TalkingMachines `[low2025talkingmachines]` (18B, 512x512, 2 NFE, 1 to 2 H100 plus a VAE GPU).
   Small models run on a single consumer GPU:
   SoulX-FlashHead Lite (96 FPS, RTX 4090) `[yu2026soulxflashhead]`;
   AvatarForcing (34 ms/frame, 1.3B) `[cui2026avatarforcing]`;
   Ditto `[li2024ditto]`;
   LivePortrait (12.8 ms/frame, RTX 4090) `[guo2024liveportrait]`.
4. **Offline joint audio-video generation is solved at product quality.** Closed systems: Veo 3/3.1, Sora 2, Seedance 2.0, Wan 2.6.
   Open weights: LTX-2 `[hacohen2026ltx2]`, Ovi `[low2025ovi]`, MOVA `[openmoss2026mova]`, MiniMax H3 (about 33B tensor elements on
   Hugging Face), DreamX-Creator `[zhu2026dreamxcreator]`. All produce clips of at most about 15 to 20 s. None stream.

### 1.2 What remains unresolved (candidate research gaps)

| Gap | Evidence | Why it matters for a live agent |
|---|---|---|
| **G1. Instruction-to-visual latency is not measured.** | Papers report throughput (FPS) and time-to-first-frame. None of those reviewed reports how long it takes for a *mid-stream* text instruction ("wave", "it starts raining") to become visible and compliant. LongLive shows the trade-off qualitatively: keeping the whole KV cache "adapts to new prompts after a delay", and discarding it causes abrupt jumps. Echo-Forcing `[wu2026echoforcing]` names "delayed response to new prompts" as a failure mode but measures VBench scores. The lower bound is set by the chunk size (e.g. 3 latent frames ≈ 12 video frames ≈ 0.5 s at 24 FPS for Wan-VAE-based chunk AR; *estimate*) plus how long the cache keeps pulling toward the old prompt. | The core UX metric of a "live" persona. It is also a clean, defensible measurement contribution. |
| **G2. Character-level control inside world models is nascent.** | Most real-time world models control **camera or ego-motion only**: Matrix-Game 2.0/3.0, WorldPlay, GameCraft, Voyager, SolarWM. Matrix-Game 2.0 *removes* text input. Character or NPC control is emerging: LingBot-World 2.0 adds combat actions and text-driven events. AlayaWorld has combat and spell casting. HelloWorld `[ouyang2026helloworld]` has button-triggered wave/nod/greet toward the camera (not real-time). ReactiveGWM `[wang2026reactivegwm]` steers NPC strategy (Street Fighter only). WanToFight `[hu2026wantofight]` covers two-player combat. CustomX `[wang2025customx]` directs a character in natural language (not real-time). EchoWM `[zhang2026echowm]` learns third-person camera-character dynamics with audio. **None combines lip-synced speech and facial expression with scene-level world control.** | Our persona must speak, gesture and act *inside* a scene it can change. Today that requires two disjoint model families: avatar models for the face and world models for the scene. |
| **G3. The persona's long-horizon identity under large motion and scene change is untested.** | Avatar models keep identity with reference sinks and identity tokens (StreamAvatar Reference Sink + RAPR; X-Streamer global identity reference; LPM multi-granularity references). They do so mostly in static framing. World models measure *scene* memory (FOV retrieval, patch memory) and seldom subject identity. Matrix-Game 3.5 `[qian2026matrixgame35]` is the first to name a "static-dynamic disentangled" representation for subject identity. Vidu S2 reports degradation beyond 90 s with dance motion. | A persona that walks, turns and changes outfit must stay recognisable for hours. |
| **G4. The LLM's episodic memory is not linked to the visual state.** | Conversational memory lives in the LLM context (e.g. X-Streamer's Thinker: 8K tokens ≈ 10 min). Visual memory lives in KV caches or frame banks (WorldMem `[xiao2025worldmem]`, Context-as-Memory `[yu2025contextasmemory]`, WorldPlay, RAD `[chen2025rad]`, SSM world models `[po2025ssmworldmodel]`). No system writes "what the persona looked like, wore, held, or where it was" into long-term memory and re-injects it across sessions. The closest mechanism is Vidu S2's dynamic reference update `[zhang2026vidus2]`. | "Remember the red scarf I gave you yesterday" needs cross-session visual grounding. |
| **G5. End-to-end systems trade resolution for latency.** | Fully unified duplex models run at low resolution: X-Streamer at 256x256 on 2xA100; Wan-Streamer at 192p with about 200 ms model-side latency; MIDAS at 384x640. High-fidelity systems are cascaded (LLM, then TTS, then audio-driven video) and pay start-up latency of about 0.9 to 1.3 s. | We need a design point between these. For a research demo, a cascade plus a streaming video backbone is the realistic choice. |
| **G6. Streaming joint audio-video is only emerging.** | Hallo-Live `[li2026hallolive]` (distilled from Ovi; 20.38 FPS, 0.94 s, 2xH200). Starchild-1 (vendor claim). EchoWM (world plus audio; no speed figure). Wan-Streamer (192p). | Needed if speech and non-speech sound (laughing, footsteps, ambience) should come from the same model as the visuals. |
| **G7. Evaluation.** | There is no benchmark for *live agents* covering lip sync, instruction-compliance latency, identity drift over hours, cross-session memory recall and interruption handling together. The pieces exist: LPM-Bench (conversational performance), GenBench (LiveAvatar), HelloWorldBench (social actions), WBench and WorldRoamBench (world models). | A benchmark or protocol is itself a publishable contribution. |

### 1.3 What is reusable for our project

- **Backbone family alignment.** Wan `[teamwan2025wan]` is the shared base. LingBot-World 2.0 ships Wan-style checkpoints (its README's task name is `i2v-A14B`). Wan is also the
  base of most open avatar models: TalkingMachines (Wan2.1 I2V), MultiTalk and InfiniteTalk (Wan2.1), SoulX-FlashTalk (InfiniteTalk/Wan
  plus the Self-Forcing codebase), LiveAvatar (Wan2.2-S2V-14B), Wan-S2V, Wan-Animate. Audio-injection modules (L-RoPE audio binding in
  MultiTalk, LoRA audio injection in OmniAvatar, S2V audio blocks) are therefore *candidates* for porting onto a LingBot-World
  checkpoint. Porting feasibility is **unverified**. It depends on whether LingBot 2.0 kept the Wan block layout (see the backbone note).
- **Streaming and serving tricks with released code:**
  rolling KV cache plus attention sink (LongLive, Rolling Forcing; Apache-2.0 and Tencent license respectively);
  KV-recache on prompt switch (LongLive);
  training-free hierarchical memory with scene recall and difference-aware decay (Echo-Forcing);
  Timestep-forcing Pipeline Parallelism, one GPU per denoising step (LiveAvatar, Apache-2.0);
  DiT/VAE disaggregation on separate GPUs (TalkingMachines; also the "8+1 GPU" layout of Matrix-Game 3.0);
  camera-aware memory retrieval (Context-as-Memory, WorldPlay, Matrix-Game 3.x).
- **Instruction-to-behavior planners:** MLLM "director" blueprints (Kling-Avatar `[ding2025klingavatar]`, OmniHuman-1.5 `[jiang2025omnihuman15]`);
  "Visual Thought Plan" (Ex-Omni-2D `[zhang2026exomni2d]`);
  LLM tool calls injecting semantic motion control into a streaming animator (EchoAvatar `[chen2026echoavatar]`, 3D);
  pilot/director agent harness (LingBot-World 2.0);
  time-localized prompt attention masks for button-triggered actions (HelloWorld). The last is training-free and could localize a
  gesture instruction to a chunk window.
- **Data:** Sekai2 `[he2026sekai2]` (2,826 h with camera trajectories and revisits), SolarWM-Data (1.43M clips), MIDAS's 20k-hour
  dialogue set (not released), VividHead (782 h, FlashHead).

### 1.4 Where a defensible contribution may exist

1. **A character-centric live world model.** Condition a real-time world backbone such as LingBot-World 2.0 on (a) the persona's
   speech audio for lip sync and co-speech gesture, and (b) LLM-emitted discrete behavior tokens or text events that are
   time-localized to chunk windows. Keep camera/scene control. Differentiation: G2 says no published system unifies avatar-grade
   facial performance with world-model scene control. HelloWorld, ReactiveGWM and LingBot-2.0's action set are the nearest
   neighbours. Each covers one slice.
2. **Measure and reduce instruction-to-visual latency (G1).** Define "time-to-visible-compliance" (TVC): the time from instruction
   arrival until a VLM judge or an action classifier detects compliance. Report it next to FPS and TTFF. Then propose mechanisms and
   compare them against LongLive KV-recache and Echo-Forcing decay: partial cache re-encoding, prompt-conditioned sink tokens,
   frame-wise 1 to 2 step AR (Causal Forcing++ reports 50% lower first-frame latency than chunk-wise 4-step), or speculative
   pre-rendering of likely next behaviors. Cheap to run, easy to reproduce, and fills a clear gap.
3. **Episodic visual memory tied to agent memory (G3+G4).** Store persona and scene state snapshots (reference frames, identity
   embeddings, prop and outfit descriptors) as first-class memory items keyed by dialogue events. Re-inject them as dynamic references
   (Vidu-S2-style) or as KV "scene recall frames" (Echo-Forcing-style) when the LLM retrieves the event. Evaluate cross-session recall
   and identity drift over at least 1 h. This connects our memory workstream (`bib_memory_eval.bib`) to the video workstream.
4. **Live-agent benchmark/protocol (G7).** Combine LPM-Bench-style conversational metrics, WBench-style multi-turn interaction turns,
   TVC (item 2) and hour-scale identity drift (ArcFace similarity over time).

Risks to state honestly: our hardware is L20X, not H100/H800, so every cited real-time figure must be re-measured. LingBot-World 2.0
weights are **CC BY-NC-SA 4.0** (non-commercial, share-alike), which is acceptable for research but limits any product path. Tencent
Hunyuan licenses (HY-WorldPlay, GameCraft, Voyager, HunyuanVideo-Avatar) exclude the EU, UK and South Korea.

---


===== FILE: docs/reviews/cp2_ev_agents_synthesis.md =====
# Literature review: live agents, closed-loop control over generators, low-latency orchestration

Scope: research areas 2, 3 and 5 of `goal.md`:
- (2) multimodal and live conversational agents, digital humans, autonomous livestreaming agents
- (3) reasoning, planning, instruction following and closed-loop control over generative models
- (5) low-latency orchestration, asynchronous execution, interruption handling, audio-visual (AV) sync

Research date: 2026-09-25. Companion BibTeX: `bib_agents_control_latency.bib`.

## How to read this note

- **Sources.** arXiv IDs, titles, first authors and v1 dates were checked against the arXiv export API on 2026-09-25. Product facts come from vendor docs or blogs fetched on the same day. They are marked **[vendor claim]** because they are not independently reproducible.
- **Abstract-only.** Many 2026 preprints were read only at the abstract or HTML-summary level. These entries are marked **[abstract-level]**. Their numbers must be re-checked against the full paper before they appear in a proposal.
- **Unverified.** Anything we could not confirm from a primary source is marked **[unverified]**.
- **Hardware.** "HW n/s" means the source does not state the hardware.
- **Date quirk.** For 2608.24909 and 2609.17416, the arXiv API returned `published` dates that fall before the month in the ID. We record the API date as returned.

---

## 1. Executive synthesis

### 1.1 What is largely solved, or at least has strong baselines

1. **Full-duplex speech** is an established model class. Examples:
   - Moshi: theoretical latency 160 ms; practical latency about 200 ms on an L4 GPU.
   - Qwen3-Omni: theoretical cold-start first-packet latency 234 ms.
   - Also dGSLM, SyncLLM, LSLM, MiniCPM-o 4.5 and StepAudio 3 Realtime.

   Commercial APIs now separate a duplex "front" voice layer from a delegated "back" reasoner. OpenAI's GPT-Live-1 (GA 2026-09-10) is described as delegating reasoning and tools to a backend model. Gemini 3.8 Live makes async function calling the default.

2. **Cascaded voice pipelines have well-understood latency budgets.** The Pipecat community primer (June 2026 revision) itemises a typical round trip at about 1,293 ms:
   - STT plus endpointing: 300 ms
   - LLM time-to-first-byte (TTFB): 650 ms
   - TTS TTFB: 120 ms
   - Transport: the remainder

   The primer calls 1,500 ms voice-to-voice "an important target". Streaming TTS first-packet latency is now 150–220 ms (CosyVoice 2: 150 ms; Kyutai DSM-TTS: 220 ms). Audio-native end-of-turn models give a 9.9% false-cutoff rate at a 300 ms latency budget (LiveKit Turn Detector v1, **[vendor claim]**).

3. **Real-time audio-driven avatars and streaming video diffusion are feasible on 1–4 GPUs:**
   - JoyStreamer-Flash: 16 FPS on one GPU, 1.3B parameters.
   - Vorch-Streamer: 27.12 FPS text-to-audio-video.
   - StreamDiffusionV2: 58.28 FPS with a 14B model on 4×H100, first frame in 0.5 s.
   - LingBot-World 2.0: its report claims 720p at 60 fps from a distilled variant.
   - Wan-Streamer v0.1: end-to-end duplex audio-visual interaction with about 200 ms model-side latency and about 550 ms total, including an assumed 350 ms network round trip.

4. **Decoupled "fast talker / slow thinker" orchestration is the dominant pattern.** It appears in research and products alike:
   - Dispider, AgileThinker, ConvFill ("conversational infill")
   - LTS-VoiceAgent, DuplexOmni, JoyAI-VL-Interaction
   - StreamArena/StreamMind, Speculative Interaction Agents, GPT-Live-1

   A new system should reuse this pattern rather than claim it.

5. **"LLM as director" for offline video generation is well explored.** Examples: VideoDirectorGPT, LVD, DirecT2V, Mora, StoryAgent. So is offline generate→judge→refine: VideoRepair, VISTA, PhyT2V, VideoAgent, with VideoScore/VideoScore2 as learned judges.

### 1.2 What remains unresolved (evidence-backed gaps)

**G1. Interruption and state update are measurably poor, even in speech-only systems.**
- EchoChain: no system exceeds a 50% pass rate. Failure modes are "contextual inertia, interruption amnesia, objective displacement". Removing interruptions cuts failures by 40.2%.
- IHBench: open-weight models lag closed models on post-interruption recovery and degrade faster as conversations grow.
- OmniInteract: best interaction-aware F1 is 0.368 overall and 0.052 on multi-answer monitoring.
- Omni-DuplexEval: best model scores 39.6% overall and 20.0% on proactive reminders.

No comparable benchmark exists for interrupting and redirecting a streaming generated video persona.

**G2. The context model does not know what the user actually saw or heard.**
- PACE names this "generative context mis-anchoring": servers generate faster than clients play, so user interruptions get interpreted against content the user never heard. PACE raises referent-anchoring accuracy from 25.0% to 96.3% on its GCM-Bench.
- The Pipecat primer recommends the same audio-side fix: use word-level timestamps to rebuild "what the user actually heard".
- For generated video, the same problem applies to queued-but-undisplayed chunks. We found no work that aligns agent context with the displayed video frames.

**G3. Mapping language intent to controls the generator can execute is shallow.**
- Offline directors emit rich layouts (bounding boxes, per-frame prompts).
- Real-time world models expose only narrow controls. LingBot-World 2.0 in the SGLang cookbook exposes WASD/IJKL key states plus per-chunk text prompts. The vLLM-Omni local checkout passes camera/action controls through a model-specific reducer.
- LingBot-World 2.0 ships an "agentic harness": a VLM "Director" plus a "Pilot". By our reading of the paper's HTML **[abstract/HTML-level]**, it gives **no quantitative evaluation** of whether agent-proposed events are valid or actually rendered.

**G4. Nobody verifies observable compliance online.**
- VLM judges (VideoScore2, VISTA's critics, VideoRepair's MLLM questions) run offline over whole clips.
- World-model benchmarks (WorldMark, WorldRoamBench, iWorld-Bench) measure action following offline. WorldMark finds "the fastest responders are often the least stable". WorldRoamBench finds no model "reliably satisf[ies] all dimensions".
- No work closes the loop at runtime. Nothing checks, within a deadline, that a user instruction ("wave", "turn left", "make it rain") became visible and then acts on the result.

**G5. Interrupting in-flight video is unaddressed at the systems level.**
- In vLLM-Omni's experimental real-time AR-diffusion runtime, control and prompt events queue per session. They are applied at the next chunk ("tick") and acknowledged via `applied_event_ids` only after the chunk commits.
- A failed tick forces a session reset; there is no mid-chunk abort. Section 5 has the details.
- So interruption latency is bounded below by queued chunks plus one chunk's generation time plus transport. Nobody has characterised this trade-off (chunk size vs. responsiveness vs. quality) for a conversational persona.

**G6. Nonverbal full-duplex behaviour is missing from cascades.**
- VideoFDB (NVIDIA, 2026-05) reports "captioning collapse and visual-stream ignorance". It concludes that speech-to-avatar systems "architecturally cannot produce full-duplex nonverbal responses", i.e. listening behaviour while the user speaks.
- End-to-end models address this (Wan-Streamer, Beyond Monologue, MIDAS), but they are avatar-centric and not world-model-centric.

**G7. AV sync is a hard constraint for split pipelines.**
- Broadcast tolerances: EBU R37 says +40/−60 ms end-to-end. ITU-R BT.1359 detectability is +45/−125 ms (the acceptability limit is quoted as −185 or −190 ms by secondary sources; **[unverified]** against the ITU PDF).
- A world model that is not audio-conditioned (LingBot-World) cannot lip-sync by itself. A TTS stream and a camera/world video stream need explicit shared timestamps. Unless the persona is shown only at a distance, a separate audio-driven face path is also needed.

**G8. The reference agent class is not real-time generation.**
- Neuro-sama, the canonical AI VTuber, uses an LLM + TTS + Live2D/3D rig, not generated video (Wikipedia; creator statements).
- MiniMax H3, which the owner says the reference agent is built on, is described by MiniMax as a clip model: "up to 15 seconds at 2K". The blog mentions no live or streaming mode.
- A "purely MiniMax H3" live agent therefore probably relies on clip scheduling or pre-generation. This is **inference only**, not verified.

### 1.3 Reusable components (recommend reuse, do not re-invent)

| Need | Reuse candidates | Notes |
|---|---|---|
| Transport, WebRTC, VAD, barge-in, pipeline graph | Pipecat (BSD-2), LiveKit Agents (Apache-2.0) | Both have interruption handling and context truncation. LiveKit ships an open turn-detector checkpoint (v1-mini, CPU). |
| Voice front-end (duplex) | Moshi (Apache-2.0 code), MiniCPM-o 4.5, Qwen3-Omni (Apache-2.0), GPT-Live-1 / Gemini Live (API) | Choose by license/hardware. Open duplex models are weaker on reasoning; delegate reasoning. |
| Streaming TTS | CosyVoice 2/3, Kyutai DSM-TTS, Fish-Speech, MiniMax Speech (API) | 150–220 ms first packet reported. |
| Streaming video perception (monitor/verifier) | StreamingVLM (8 FPS on 1×H100), Dispider/StreamBridge patterns, JoyAI-VL-Interaction (open) | Candidate online compliance checker. |
| Video judge (offline eval) | VideoScore2, VBench-style metrics, WorldMark/WorldRoamBench adapters | For evaluation, not the runtime loop. |
| Generator serving | vLLM-Omni real-time AR-diffusion sessions (experimental), SGLang LingBot cookbook, StreamDiffusionV2 techniques, xDiT parallelism | Session and event-ID semantics already exist in vLLM-Omni. |
| Persona/memory pattern | Generative Agents memory stream (recency/importance/relevance + reflection); Voyager skill library | Area 4 covers memory in depth. |

### 1.4 Where a defensible research contribution could exist

These are hypotheses to test, not novelty claims. Combining Pipecat + an LLM + LingBot-World is engineering, not a research contribution. Each hypothesis below comes with a measurable claim.

**C1. Display-aligned state for generated video (extends PACE/G2 from audio to video).**
- Formalise the gap between the "committed", "generated-but-queued" and "displayed" video state.
- Route user corrections through a context anchored to *displayed* frames.
- Measure:
  - control-to-photon latency
  - stale-content exposure after interruption
  - referent-anchoring accuracy (e.g. "no, the *other* one")
- Compare queue-flush, chunk-boundary preemption and soft-transition policies on LingBot-World in vLLM-Omni.
- Novelty risk: PACE and the Pipecat primer cover audio. The video/world-model version plus the chunk-granularity trade-off looks open as of this search.

**C2. Online observable-compliance verification.**
- A runtime monitor (a streaming VLM) checks, within a deadline, whether each issued control produced its intended visible effect. It emits a compliance ledger keyed by `event_id` / `applied_event_ids`, and triggers bounded repair (re-prompt, alternate control, or a verbal acknowledgement of failure).
- Evaluate against offline VideoScore2 or human labels.
- Novelty risk: VISTA, VideoRepair and PhyT2V do offline refinement, and LingBot's Director is unevaluated. We found no *online, deadline-bounded* verifier for interactive world models.

**C3. An empirically calibrated capability model for intent-to-control grounding.**
- Measure which text events and camera/action combinations the generator actually renders reliably (success rate, latency to effect, side effects). Use this as a constraint set for the planner, like Voyager's skill library but for generator affordances.
- The planner then refuses, or offers an alternative, for instructions it predicts will fail.
- Novelty risk: moderate. Convai's "Prompt-to-Action" and NVIDIA ACE map intents to *game-engine* actions with known semantics. Doing this for a *stochastic generator* with measured affordances is less explored.

**C4. A benchmark for multi-turn, interrupting instructions to a video persona.**
- Combine the speech-side protocols (EchoChain, IHBench, Full-Duplex-Bench v2) with world-model action metrics (WorldMark per-axis direction accuracy and latency). Add corrections, goal changes and interruptions of in-flight actions.
- Every surveyed benchmark covers speech *or* video control, never both under interruption.

---


===== FILE: docs/reviews/cp2_ev_memory_synthesis.md =====
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

===== FILE: docs/notes/reference_agent_and_minimax_h3.md =====
# Reference live agent (twitch.tv/sylar_nv) and MiniMax H3: evidence notes

Compiled 2026-09-25 (local, UTC+8). Web accesses were made 2026-09-24 17:25–17:40 UTC.
This was a read-only pass: no repos were modified, no GPU jobs were run and no model weights
were loaded. Safetensors *headers* were parsed for tensor shapes only.

Status labels:
- **verified**: seen directly in a primary source (official page, API response, local file).
- **observed**: seen directly in public VOD media or chat replay. This is behaviour only; nothing
  about the implementation follows from it.
- **secondary**: reported by a third party and not checked against a primary source.
- **unverified**: an owner or hearsay claim with no public evidence found.

---

## Part 1: Reference live agent `sylar_nv`

### 1.1 Provenance claim
- The project owner says the agent was built by a friend and is "based purely on MiniMax H3".
  **Unverified.** Nothing public (channel description, panels, socials, titles) names the model or
  the builder. One chat-replay line from a viewer asks "你是啥模型" ("what model are you?"). The
  answer was not checked because it would need ASR of the audio.
- Some observations fit an H3-based video path but do not prove one:
  - The VOD source rendition is 960x544 at 24 fps. The upstream vLLM-Omni H3 recipe lists 960x544 at 24 fps as a native H3
    long-video shape, and H3 is fixed at 24 fps.
  - The earliest VOD thumbnails show a counter of the form "第 1698 段 · 13 秒" ("segment 1698 · 13 s").
    That fits sequential generation in clips of about 13 s. H3's default clip limit is 4–15 s.
  - Other 24 fps generators could produce the same features.

### 1.2 What was accessible and what was blocked

| Source | Result | Access time (UTC) |
|---|---|---|
| `https://www.twitch.tv/sylar_nv/about` (WebFetch) | Page shell only, content rendered by JS. No text extracted | 2026-09-24 ~17:30 |
| `https://www.twitch.tv/sylar_nv/videos` (WebFetch) | Page shell only, content rendered by JS | ~17:38 |
| Twitch public GQL `gql.twitch.tv/gql` with the public web Client-ID (curl, anonymous) | **Accessible**: user, VOD list, VOD chat replay, VOD playback token. `channel.socialMedias` failed with `IntegrityCheckFailed` | 17:30–17:33 |
| VOD HLS (`usher.ttvnw.net` → CloudFront `index-dvr.m3u8`, anonymous) | **Accessible**. 2 short excerpts (150 s + 80 s) downloaded from VOD 2881733191 for frame/audio inspection. Stored only in the session scratchpad, not in the repo | ~17:31–17:33 |
| twitchtracker.com/sylar_nv | HTTP 403 | ~17:36 |
| streamscharts.com/channels/sylar_nv | HTTP 403 | ~17:38 |
| sullygnome.com/channel/sylar_nv | HTTP 403 | ~17:38 |
| Web search `"sylar_nv" twitch` | No relevant hits. No media coverage, GitHub or X posts found | ~17:36 |
| Live stream | Offline at the time of access (`stream: null`) | 17:30 |

### 1.3 Public metadata (Twitch GQL, verified, 2026-09-24 17:30 UTC)
- login/display `sylar_nv`, user id `1542050203`. Account created **2026-09-18T19:19:12Z**.
- Followers: **4**. Not an affiliate or partner. Description: null. Panels: none. Stream title: empty.
  Category: none. Schedule: none. Clips: 0.
- Last broadcast id `316483758833` has `startedAt` 2026-09-23T10:31:30Z. The matching VOD 2881733191 has
  `createdAt` 07:34:48Z. The two timestamps disagree, and both are recorded here as returned.
- **43 archived VODs** (2026-09-18 → 2026-09-23), about **27.8 h** in total. Lengths range from 89 s to 17,572 s
  (about 4.9 h). View counts are 0–89. The top VOD is 2881733191 (10,597 s, 89 views).
  None of the VODs has a title or category.

### 1.4 Publicly observable behaviour (observed; VOD media plus chat replay)
Visual format changed over the week, based on VOD preview thumbnails:
- **Sep 18–19**: a science-explainer format voted on by chat. An overlay offers two questions, for example
  "!A 杯边水面为什么弯了?" ("!A why does the water surface curve at the cup's edge?") and
  "!B 冷杯子为什么会出汗?" ("!B why does a cold cup sweat?"), with vote counts and a segment counter "第 N 段 · 13 秒" ("segment N · 13 s").
  Chat replay shows the operator sending `!A`, `!B` and `!customized prompt`.
- **Sep 20**: one thumbnail shows a bearded man in a cap in a room, framed like a webcam.
- **Sep 21–23**: a persistent persona. A young woman in a green Hanfu-style robe sits reading at a desk in a
  classical Chinese study. The desk holds a teapot, pastries, an incense burner, a book labelled "CUDA" and
  a sketched portrait on the wall, with a lotus pond seen through the window.
  An overlay reads "互动指南 / 默认静读 · !ask 点播互动" ("Interaction guide / silent reading by default · !ask for on-request interaction"), with example commands
  (!ask 今天读到什么故事? / 给我讲讲 CUDA / 翻一页书 / 点点头 / 挥挥手 / 喝口茶 / 吃一口龙须酥; that is,
  what story did you read today? / tell me about CUDA / turn a page / nod / wave / have a sip of tea / eat a piece of dragon's-beard candy).

Behaviour seen in VOD 2881733191 (offsets are chat-replay `contentOffsetSeconds`):
- **Idle mode**: silent reading with small natural motions such as page turns and a steaming incense burner.
  Audio is near the ambient floor, about −52 dBFS RMS.
- **Responds to chat instructions**:
  - An operator message "喝口茶" ("have a sip of tea") at 5227 s was followed by a viewer's "!ask 喝口茶" at 5229 s.
    The persona is seen lifting a teacup and drinking at about 5244–5246 s, which is roughly **15–20 s** after
    the message. A second drink appears at about 5270 s.
  - Loud vocal audio (−15 to −12 dBFS) starts at about 5288 s. The candidate trigger is a viewer's "唱首歌吧"
    ("sing a song") at 5252 s, but the link to any one message was **not** confirmed because no ASR was run.
  - Within the 150 s talking excerpt (5380–5530 s), speech is nearly continuous, with 1–2 s pauses and lip
    motion consistent with speech.
- **Other requests seen in chat replay**:
  - Physical actions: close or open the window, stand up, wave, nod, cry, shake your head.
  - Content: tell a story, sing a (love / break-up / English) song, explain CUDA or RDMA.
  - Scene edits: change clothes, background or the view outside the window.
  - Identity questions: who are you, what model are you.
  - Some viewers posted inappropriate or sexualised requests. The system's handling of them was not
    examined.
  - A viewer remarked that the singing had become electronic ("上电音了").
  - Whether each request was honoured was **not** systematically checked.
- **Visual consistency**: identity, costume and set stay stable across a 150 s talking excerpt.
  One discontinuity was seen at about 5280–5288 s, where the background switches to a bookshelf, the framing
  changes and then the scene returns. This looks like a clip-boundary or scene-regeneration artefact, but the
  cause is unknown.
- **Memory of viewers**: no evidence either way. It would require ASR of the responses and repeat-visitor
  probes.
- **Audio/stream spec**: H.264 960x544 at 24 fps and AAC 48 kHz stereo. This is the Twitch transcode; the
  source quality was capped at FULL_HD for anonymous viewers.

### 1.5 What a fair quantitative comparison would need
1. **Recorded VODs with exact timing**: VOD download works anonymously today, but retention is limited
   (Twitch deletes archives after a few days for non-affiliates). Snapshot the VODs now. Align chat
   offsets to the video PTS with a known marker, because chat offsets and video time were not validated here.
2. **Controlled prompt script**: a fixed set of instructions (actions, Q&A, songs, scene edits, repeat-viewer
   memory probes, adversarial or unsafe requests), sent at scheduled times from a dedicated test account,
   ideally with the operator's consent.
3. **Operator cooperation**: confirm the model stack (e.g. whether it is really H3 alone; which TTS and LLM
   are used, if any), the hardware, the resolution and steps, and whether clips are pre-generated or queued.
   Without this, only black-box latency and quality can be compared.
4. **Metrics** that apply to both systems:
   - instruction-to-onset latency, measured with ASR and action detection on the video;
   - instruction success rate, judged by humans or a VLM;
   - lip-sync, measured with SyncNet-style scores;
   - identity drift over hours, measured with face-embedding similarity;
   - audio quality;
   - uptime and rate of stalls or discontinuities;
   - accuracy on viewer-memory probes.
5. **Ethics**: the operator's consent before publishing analysis of their stream, and viewer handles
   anonymised. This note records no viewer identities.

---

## Part 2: MiniMax H3

### 2.1 What it is (verified from official sources)
- MiniMax H3 is an **open-weight, omni-modal joint video and audio generation model**, a diffusion transformer.
  It is **not an LLM** and it is **not marketed as a world model**. MiniMax describes it as "a general-purpose,
  omni-modal generative system" that understands text, image, video and audio context and generates
  "video with native stereo audio at resolutions up to 2K and durations of up to 15 seconds".
- **Announced 2026-07-31** in the MiniMax blog post "MiniMax H3: An Open Model Breaking the Boundaries
  Between Tasks and Modalities". It is the successor to Hailuo 01 and Hailuo 02.
  - The weights were published to Hugging Face on about **2026-08-03**, according to secondary sources.
  - The HF API reports the repo `createdAt` as 2026-07-28T10:45Z and `lastModified` as 2026-08-13.
  - The HF API reports `gated: false`. The vLLM-Omni recipe says access approval is required, which conflicts.
- **License**: the "MiniMax H3 Community License Agreement". It is not OSI-approved.
  - The Applicable Territory **excludes the EU, UK, Republic of Korea and USA**.
  - Commercial products above **$20M yearly revenue** need a separate written authorization.
  - Commercial user interfaces must display "MiniMax H3".
  - Outputs may not be used to improve other AI models.
  - This is a relevant constraint for a US, EU, UK or Korean deployment of the proposal.
- **Size and architecture** (model card and GitHub README):
  - H3-Omni-Transformer: a 33B dense single-stream DiT (about 13B of it in AdaLN branches) with 3D MM-RoPE.
  - Text/multimodal encoder: Qwen3-VL-32B (layer-50 output).
  - VisualVAE: causal, 16x spatial and 4x temporal compression, 24 channels.
  - Stereo AudioVAE: 40 Hz latent rate.
- **Tasks**: T2VA (text), FL2VA (first/last keyframe), and Ref2VA (up to 9 images, 3 videos and 3 audios as
  references). There are two task-specific checkpoint partitions.
- **Output**: 24 fps, 4–15 s by default, a short side of 768 px (up to 2K via "In-context Regeneration";
  the 2K regenerator is reported not open-sourced, secondary source) and 32 kHz stereo audio.
  Aspect ratios are 21:9, 16:9, 4:3, 1:1, 3:4 and 9:16. The card lists 11 languages.
- **Streaming or real-time**: there is **no official claim** of streaming, real-time or camera control.
  Camera control exists only through third-party adapters (SolarWM, below).
- **Latency and hardware**: there are no official numbers. Community vLLM-Omni measurements, all offline and
  none real-time:
  - 4x H200, 1344x768, 124 frames (about 5.2 s), 50 steps: 85.5 s median.
  - 4x B300, FL2VA 209 frames at 1248x768: about 87 s.
  - 4x MI300X, 209 frames: about 267–287 s end to end.
  - 2x RTX 5090 with offload, 124 frames: 8 min 38 s.
  - About 134 GiB of BF16 per partition.
  - Few-step adapters exist: FastH3, a 4-step DMD2 student, and LightX2V Turbo LoRAs.

### 2.2 Local checkpoint inspection (verified, read-only)
Path: `/data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA/`

| Component | Local size (`du -sh`) | Evidence | Estimated params |
|---|---|---|---|
| transformer (`MiniMaxH3DiTModel`) | **4.9 G: only shard 1 of 13 present** | index `total_size` = 66,280,430,144 B. Config: hidden 5376, 50 layers, 56 heads × 128 (attention inner dim 7168), FFN 14336 (fc1 is 28672, gated), adaLN 2688→96768, 2 token-refiner layers, `text_dim` 5120, video latent 24, audio latent 32, patch (1,2,2) | Per block about 645.5M (adaLN 260M, qkv 116M, out 38.5M, MLP 231M), so 50 × 645.5M ≈ 32.3B, plus 0.77B refiner. That gives **≈33.1B**, consistent with 66.3 GB of mostly-bf16 weights and the card's "33B / 13B AdaLN" |
| video_vae (`AutoencoderKLLegacy`, remote code) | 9.8 G | fp32, 2.604B params (from the header). Causal 3D-conv encoder, 36-layer ViT decoder. `vae_ratio` 16, `vae_ratio_t` 4, `vae_clip_length` 17, 24 channels | ≈2.6B |
| audio_vae (DAC encoder + BigVGAN decoder) | 578 M | fp32, 0.151B params. Sample rate 32 kHz, 2 channels. Encoder rates 2·4·4·5·5 = 800, giving a **40 Hz** latent | ≈0.15B |
| processor / tokenizer | 11 M each | `Qwen3VLProcessor`, `Qwen2TokenizerFast` | – |
| text_encoder | **absent locally** | `model_index.json` names `MiniMaxH3Qwen3VLHFEncoder`, and `text_dim` 5120 fits Qwen3-VL-32B | ≈32–33B (not measured locally) |

`model_index.json`:
- `_class_name` is `MiniMaxH3Pipeline`.
- Partition `fl2va`, tasks `["t2va","fl2va"]`.
- Sigma shift scales: video 12.0, audio 3.0.

**The local FL2VA copy is incomplete.** 12 of the 13 DiT shards and the text encoder are missing, so this
directory cannot run inference as-is.

### 2.3 Inputs and outputs, as used locally (`/data/zhoutaichang/worldmodel/H3-Demo/`)
- Plan files: `h3-{control,final,speed,stream-30s,test}-plan.json`.
  - Each entry has `key`, `num_frames`, `fps: 24.0`, `caption`, `image`, `camera` and `prompt`, plus sha256 values.
  - Horizons are 240 frames (10 s), 720 frames (30 s) and 2880 frames (120 s).
- Inputs:
  - One keyframe, `cases/source.image.png`, 1344x768 RGB.
  - A text prompt, `cases/source.prompt.txt`, describing a forward walk beside a wheat field.
  - A camera track, `cases/*.camera.npy`: a **float64 array of shape `[N, 4, 4]`, one 4x4 pose per output frame**.
    - Frame 0 is `diag(-1,-1,1,1)`, and later frames carry metric translation.
    - The SolarWM recipe defines these as camera-to-world matrices in OpenCV axes with metric translation,
      rebased to frame 0, with the rebased translation kept under 20 m.
    - There is no audio input in these plans.
- Base H3 output: an MP4 with H.264 video at 24 fps and 32 kHz stereo AAC.
  SolarWM-H3 output: **video only**. The audio branch is fed encoded silence and its output is discarded.
- Frame grid:
  - 17n+5 video frames map to 5n+2 video latents; audio latents are at 40 Hz.
  - The VAE temporal clip is 17 frames.
  - The SolarWM Stage-2 chunk is 5 latent frames, i.e. 17 pixel frames, about 0.71 s at 24 fps.

### 2.4 Chunking and streaming support
- **Upstream vLLM-Omni main** (`/data/zhoutaichang/live-agent/external/vllm-omni`, commit `7b4dc7633`,
  2026-09-25) **already contains MiniMax-H3 support**: `vllm_omni/diffusion/models/minimax_h3/`, the `MiniMaxH3Pipeline`,
  and the recipe `recipes/MiniMaxAI/MiniMax-H3.md`. It includes:
  - a temporal-chunk VAE decode with a frames-only callback (`temporal_chunks.py`, `chunked_decode.py`; PR #7017);
  - streamed-video encoding on the worker (PR #7018) and streaming fMP4 output;
  - long-video latent continuation up to 300 s (`long_video=true`, `continuation.py`);
  - `audio_mode=lock_source`, which drives generation with a given soundtrack;
  - FastH3 (4-step) and Turbo LoRA adapters;
  - an AR-diffusion session with streaming VAE decode (PR #6533, generic).

  These are chunked or offline generation paths. None is documented as real-time.
- **SolarWM-H3 camera-controlled world-model integration**: **not in upstream main**. It exists only as
  **uncommitted working-tree changes** in `/data/zhoutaichang/worldmodel/vllm-omni`:
  - The branch is `feat/solarwm-h3-experimental`. HEAD is `e284d907` (2026-09-13), which is an
    upstream-main commit and an ancestor of `7b4dc76`, 273 commits behind it. The branch has no commits of its own.
  - Untracked files:
    - `vllm_omni/experimental/world_models/solarwm_h3/{camera,pipeline_solarwm_h3,sgf,weights}.py`
    - `vllm_omni/diffusion/models/minimax_h3/camera_prope.py`
    - `vllm_omni/model_extras/solarwm_h3.py`
    - `recipes/SolarWM/SolarWM-H3.md`
    - `tests/experimental/world_models/solarwm_h3/*`
  - Modified files: `minimax_h3_transformer.py` (+94 lines), `registry.py`, `model_metadata.py`,
    `model_extras/registry.py` and the docs.
  - Behaviour per the recipe:
    - Adapter weights: `junchaoh-cs/SolarWM-H3-33B`.
    - **Stage0.5** is a bidirectional adapter producing a fixed 158 frames with 29 Euler steps, run with TP=2.
    - **Stage2** is a causal "self-gradient-forcing" student. Each chunk is 5 latent frames (17 frames) from
      4 denoiser evaluations, with a KV cache over the last 5 chunks (about 31 GiB bf16). Any length N ≥ 22 poses
      is accepted, including the 2880-frame, 2-minute demo.
    - Validated on an L20X 140 GiB; Stage2 can run on 1 GPU.
    - The recipe states "Speed is not a goal of this integration".
    - The adapter is a rank-384 LoRA folded into the weights at load time.
  - Other related branches on origin: `codex-minimax-h3-vendor-callback`, `perf/minimax-h3-adaln-cache-offload`,
    `perf/minimax-h3-lossless-hot-path`.

### 2.5 Implications for the proposal (analysis, not evidence)
- H3 gives joint video, audio and speech with lip-synced stereo from a single 33B DiT. That is attractive for a
  persona, but it runs offline at tens of seconds or more per 5 s clip on 4 high-end GPUs. A live agent built
  on "pure H3" must therefore pre-generate or queue clips, or use few-step or causal students (FastH3,
  SGF-style chunking). The roughly 15–20 s action latency seen on sylar_nv fits such a design but does not confirm it.
- The license territory exclusion matters for deployment location.

---

## Evidence table

| Claim | Source | Access date | Status |
|---|---|---|---|
| sylar_nv is "based purely on MiniMax H3", built by the owner's friend | project owner (verbal) | 2026-09-25 | unverified |
| Channel created 2026-09-18T19:19Z, 4 followers, no description/panels/schedule, not affiliate | Twitch GQL `user(login:"sylar_nv")` | 2026-09-24 17:30 UTC | verified |
| 43 VODs, 2026-09-18 to 09-23, ≈27.8 h total, max 89 views | Twitch GQL `videos(first:100)` | 2026-09-24 17:31 UTC | verified |
| Offline at access time | Twitch GQL `stream: null` | 2026-09-24 17:30 UTC | verified |
| VOD rendition 960x544 at 24 fps, AAC 48 kHz stereo | usher master playlist + ffprobe, VOD 2881733191 | 2026-09-24 17:31 UTC | verified |
| Persona format (classical study, `!ask` overlay, idle reading) | VOD 2881733191 frames at 5220–5530 s; thumbnails of VODs 2879089351, 2880014406, 2880966445, 2881093241 | 2026-09-24 17:32 UTC | observed |
| Early A/B chat-vote explainer format with "第N段 · 13秒" counter | thumbnails of VODs 2877689483, 2878248559; chat replay `!A`/`!B` | 2026-09-24 17:34 UTC | observed |
| Performs requested tea-drinking about 15–20 s after the chat message | VOD 2881733191 chat offsets 5227/5229 vs frames at about 5244 s | 2026-09-24 17:33 UTC | observed (single sample; offset alignment unvalidated) |
| Continuous speech with lip motion during talking mode | VOD 2881733191, 5380–5530 s; audio RMS | 2026-09-24 17:31 UTC | observed (content not transcribed) |
| Viewer memory | – | – | gap (not assessable) |
| twitchtracker / streamscharts / sullygnome stats | respective URLs | 2026-09-24 17:36–17:38 UTC | blocked (HTTP 403) |
| No media coverage or socials found | WebSearch `"sylar_nv" twitch` | 2026-09-24 17:36 UTC | verified (absence in search) |
| H3 announced 2026-07-31; omni-modal video + native stereo audio, ≤15 s, 2K | https://www.minimax.io/blog/minimax-h3 | 2026-09-24 | verified |
| H3 is 33B DiT (~13B AdaLN), Qwen3-VL-32B encoder, VAE 16x/4x/24ch, AudioVAE 40 Hz; T2VA/FL2VA/Ref2VA; 24 fps, 4–15 s, 32 kHz stereo | https://huggingface.co/MiniMaxAI/MiniMax-H3 ; https://github.com/MiniMax-AI/MiniMax-H3 | 2026-09-24 | verified |
| HF repo createdAt 2026-07-28, lastModified 2026-08-13, gated false, license tag `minimax-h3-community-license-agreement` | https://huggingface.co/api/models/MiniMaxAI/MiniMax-H3 | 2026-09-24 | verified |
| Weights published about 2026-08-03 | https://aiweekly.co/alerts/minimax-posts-h3-a-33b-omni-modal-video-model-to-hugging-face ; MarkTechPost 2026-08-01 | 2026-09-24 | secondary |
| License excludes EU/UK/Korea/USA; >$20M revenue needs authorization; "MiniMax H3" attribution; no training other models on outputs | https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE | 2026-09-24 | verified |
| No official streaming/real-time/camera-control claim | H3 blog, model card, GitHub README | 2026-09-24 | verified (absence) |
| 2K regenerator / Context-IR not open-sourced | aiweekly (above) | 2026-09-24 | secondary |
| Local DiT ≈33.1B params (66.28 GB index; per-layer shapes) | `/data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA/transformer/{config.json,model.safetensors.index.json}` and shard-1 header | 2026-09-25 | verified (computed) |
| Local copy incomplete (1/13 DiT shards, no text_encoder) | `ls`/`du -sh` of the same dir | 2026-09-25 | verified |
| Video VAE 2.6B fp32; audio VAE 0.15B fp32, 32 kHz stereo, 40 Hz | `video_vae/source/config.json`, `audio_vae/{config.json,metadata.json}` + headers | 2026-09-25 | verified |
| Camera input = float64 `[N,4,4]` per-frame c2w; 24 fps; 240/720/2880 frames; 1344x768 keyframe | `/data/zhoutaichang/worldmodel/H3-Demo/{*.json,cases/}`; SolarWM recipe | 2026-09-25 | verified |
| H3 support + chunked decode/long-video continuation in upstream vLLM-Omni main 7b4dc76 | `/data/zhoutaichang/live-agent/external/vllm-omni/{vllm_omni/diffusion/models/minimax_h3/,recipes/MiniMaxAI/MiniMax-H3.md}` | 2026-09-25 | verified |
| Community H3 latencies (H200 85.5 s / B300 87 s / MI300X ~270 s / 2x5090 8m38s) | same recipe | 2026-09-25 | secondary (community measurements) |
| SolarWM-H3 integration only as uncommitted changes on `feat/solarwm-h3-experimental` (HEAD e284d907) | `git -C /data/zhoutaichang/worldmodel/vllm-omni status/log` | 2026-09-25 | verified |
| SolarWM paper (arXiv 2609.02886, 2026-09-02) builds on H3, Wan2.2, LTX-2.5 | https://arxiv.org/abs/2609.02886 | 2026-09-24 | verified |
