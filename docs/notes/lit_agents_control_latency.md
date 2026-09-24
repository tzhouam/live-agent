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

## 2. Comparison matrix (most relevant systems)

Legend:
- **Mem:** long-term memory (—: none stated).
- **Ctrl:** control interface exposed.
- **Lat:** reported latency (source; HW if stated).
- **Open:** code/weights availability.

| System | Type | I/O | Duplex / barge-in | Mem | Ctrl | Lat (reported) | Open | Date | Relevance |
|---|---|---|---|---|---|---|---|---|---|
| Moshi (Kyutai) | E2E speech LM | speech↔speech+text | full duplex (2 streams, inner monologue) | context only | persona via prompt/fine-tune | 160 ms theoretical; ~200 ms practical on L4 | code Apache-2.0; weights released | 2024-09-17 | Duplex front-end baseline |
| dGSLM | textless dialogue LM | 2-channel audio | full duplex (dual tower) | — | none | n/a | Meta release | 2022-03-30 | Foundational |
| SyncLLM | time-synced Llama-3-8B | speech | full duplex; tested with up to 240 ms simulated latency | — | — | — | paper | 2024-09-23 | Time-sync mechanism |
| LSLM | listen-while-speaking | speech | interruption detection (fusion) | — | — | n/s | paper | 2024-08-05 | Interruption modelling |
| Freeze-Omni | frozen-LLM S2S | speech | duplex via state prediction | — | — | "low latency" (numbers [unverified]) | code on GitHub | 2024-11-01 | Keep LLM frozen |
| Qwen2.5-Omni | Thinker–Talker | text/img/audio/video → text+speech | streaming | — | text prompt | n/s in abstract | 7B weights | 2025-03-26 | Omni front-end |
| Qwen3-Omni | MoE Thinker–Talker | same | streaming | — | text prompt, tools | 234 ms theoretical first packet (cold start) | Apache-2.0 repo | 2025-09-22 | Omni front-end |
| Qwen3.5-Omni | Hybrid-attention MoE | same | streaming | — | — | n/s | [unverified] | 2026-04-17 | Latest Qwen omni |
| MiniCPM-o 4.5 | 9B omni duplex | see/listen/speak | full duplex, proactive | — | — | runs on edge devices with <12 GB RAM | Apache-2.0 repo | 2026-04-30 | Open duplex video-aware front-end |
| GLM-4-Voice | E2E speech | speech | streaming, turn-based | — | voice style instructions | n/s | 9B open | 2024-12-03 | Baseline |
| VITA-1.5 / VITA-Audio | vision+speech MLLM | video/speech | near-real-time | — | — | VITA-Audio: faster first audio via MCTP | open | 2025-01-03 / 2025-05-06 | Baseline |
| Step-Audio / StepAudio 3 Realtime | speech LLM | speech | SA3-RT: full duplex, "think-while-speaking" | — | tools, role-play | n/s | Step-Audio-Chat open; SA3-RT [unverified] | 2025-02-17 / 2026-09-12 | Think-while-speaking |
| Kimi-Audio | audio foundation | audio | streaming detokenizer | — | — | n/s | open | 2025-04-25 | Baseline |
| OpenAI GPT-Realtime-2 / 2.1 | API S2S | audio(+text) | barge-in | session | tools, reasoning effort | "p95 latency −25%" (2.1) [vendor claim] | API | 2026-05 / 2026-07 | Commercial baseline |
| OpenAI GPT-Live-1 | API duplex front-end | audio/text only (no image/video) | full duplex | "longer sessions" | delegates reasoning/tools to backend | $0.05/min; FDB +30 pp vs 2.1 [vendor claim] | API | 2026-09-10 | Validates front/back split |
| Gemini Live API (3.8 Live) | API | text/img/audio/video in (video as JPEG ≤1 FPS) | barge-in, proactive audio always on | compression, resumption | async function calling default | n/s | API | 2026-09 | Video-aware front-end; 1 FPS vision |
| Tavus CVI (Phoenix-4, Sparrow, Raven) | cascaded video-call agent | video↔video | turn-taking model | Persona layer | persona config, swappable LLM | "sub-600 ms" end-to-end [vendor claim, secondary] | API | Phoenix-4: 2026-02-18 | Closest commercial analogue |
| Pipecat | framework | any | VAD + Smart Turn + interruption | app-level | pipeline graph | 1,293 ms typical breakdown (primer) | BSD-2 | 2023-12 → | Orchestration base |
| LiveKit Agents + Turn Detector v1 | framework | any | audio EOT model | app-level | — | 9.9% false-cutoff at 300 ms [vendor claim] | Apache-2.0; model license | 2026-06-17 (v1) | Turn detection |
| VideoLLM-online (LIVE) | streaming VideoLLM | video→text | decides when to speak | KV context | — | real-time (see paper) | code/model released | 2024-06-17 | Streaming perception |
| Dispider | async perception/decision/reaction | video→text | proactive | memory in perception | — | async | paper/code | 2025-01-06 | Decoupling pattern |
| StreamBridge | offline→streaming adapter | video→text | proactive gating model | memory buffer | — | — | NeurIPS 2025 | 2025-05-08 | Adapter pattern |
| StreamingVLM | infinite-stream VLM | video→text | — | attention-sink KV | — | up to 8 FPS on 1×H100 | MIT-han-lab code | 2025-10-10 | Online verifier candidate |
| JoyAI-VL-Interaction | 8B VL interaction + system | video/audio→speech | decides each second: silent / respond / delegate | pluggable memory | background brain | n/s | fully open | 2026-06-10 | Open front/back system |
| Wan-Streamer v0.1 | E2E AV duplex foundation | AV↔AV | full duplex incl. interruption | — | — | ~200 ms model-side; ~550 ms total incl. 350 ms network; 160 ms units at 25 fps | [unverified] | 2026-06-23 | E2E alternative to cascade |
| TalkingMachines (Character.AI) | audio-driven AR DiT avatar | audio→video | via audio LLM | — | audio | real-time (DiT/VAE on separate devices) | paper | 2025-06-03 | Avatar path |
| JoyStreamer-Flash (JD) | AR-diffusion avatar | audio→video | — | cache reset for unbounded length | audio (+text in JoyStreamer) | 16 FPS, 1 GPU, 1.3B | [unverified] | 2025-12-12 | E-commerce production lineage |
| TaoMate (Taobao) | joint AV digital human | text→AV | — | "persistent A/V memory" + visual anchor | prompt segments | n/s in abstract | project page | 2026-07-27 | Long-form identity |
| Vorch-Streamer | text→AV streaming | text→AV | — | bounded causal context | LM-predicted 25 Hz speech-plan tokens | 27.12 FPS | project page | 2026-08-06 | LM plans speech progression |
| LingBot-World 2.0 | AR world model + agentic harness | text+camera/actions→video | — | "does not truly remember" (authors) | WASD/IJKL + per-chunk text; VLM Director proposes events | 720p@60fps claim (distilled); SGLang example 832×480 at 25 FPS on 8 GPUs | open 14B (+1.3B) | 2026-07-08 | **Target backbone** |
| Zing-0.5 | world model | keys+text→video | — | — | joint action+text, text events mid-stream | 24 FPS at 832×480, 4-step | weights + SGLang serving | 2026-09-15 | Alternative with text events |
| SIMA 2 (+Genie 3) | Gemini embodied agent | pixels→kbd/mouse | — | — | language/sketch/emoji goals | n/s | closed | 2025-12-04 | LLM agent acting inside a generated world |
| Neuro-sama | AI VTuber | chat/voice→LLM→TTS→rig | yes (live) | undisclosed | Twitch chat, games | "low latency" | closed | 2022-12-19 debut | Livestream reference |
| LiveThinking (Taobao) | distilled reasoning for live commerce | text | — | — | — | sub-second; 30× compute cut; GMV lift | paper | 2025-10-09 | Latency-aware reasoning |
| PACE | middleware | voice | playback-aligned context | — | — | GCM accuracy 25.0→96.3% | [unverified] | 2026-08-07 | **Key idea for C1** |

---

## 3. Per-system notes

### 3A. Multimodal and live conversational agents

#### Full-duplex and end-to-end speech models

**dGSLM (Nguyen et al.)**, arXiv 2203.16502, 2022-03-30; TACL 2023. https://arxiv.org/abs/2203.16502
- *Approach:* textless dual-tower transformer with cross-attention, trained on about 2,000 h of two-channel Fisher audio.
- *Capabilities:* generates overlaps, laughter and turn-taking.
- *Limitations:* weak semantics.
- *Relevance:* foundational proof that duplex timing can be learned from two-channel data.

**Moshi (Défossez et al., Kyutai)**, arXiv 2410.00037, 2024-09-17. https://arxiv.org/abs/2410.00037 · https://github.com/kyutai-labs/moshi
- *Approach:* a 7B temporal transformer models two audio streams (user and Moshi) plus "inner monologue" text. It uses the Mimi codec (80 ms frames).
- *Latency:* 160 ms theoretical (80 ms frame + 80 ms acoustic delay); practical latency "as low as 200ms on an L4 GPU" (README).
- *Memory:* context only.
- *Availability:* code Apache-2.0; the arXiv page lists CC BY-NC-SA for the paper.
- *Limitations:* small-LM reasoning; persona needs fine-tuning.
- *Relevance:* the duplex front-end baseline; the DSM framework (below) generalises it.

**SyncLLM (Veluri et al., Meta/UW)**, arXiv 2409.15594, 2024-09-23; EMNLP 2024. https://arxiv.org/abs/2409.15594
- *Approach:* adds time synchronisation to Llama-3-8B so the model runs against a real-world clock.
- *Data:* 212k h of synthetic plus 2k h of real dialogue.
- *Evaluation:* two-agent simulation with up to 240 ms network latency.
- *Relevance:* explicit clock-sync design, which matters when video chunks must also align.

**LSLM (Ma et al.)**, arXiv 2408.02622, 2024-08-05; AAAI. https://arxiv.org/abs/2408.02622
- *Approach:* listen-while-speaking with early, middle and late fusion; middle fusion is best.
- *Evaluation:* command-based and voice-based interruption.
- *Relevance:* an interruption-detection formulation.

**Freeze-Omni (Wang et al.)**, arXiv 2411.00774, 2024-11-01. https://arxiv.org/abs/2411.00774
- *Approach:* keeps the text LLM frozen and connects speech encoder/decoder with three-stage training, avoiding catastrophic forgetting.
- *Latency:* exact numbers **[unverified]**.
- *Relevance:* the frozen-LLM principle preserves reasoning and instruction following.

**Qwen2.5-Omni**, arXiv 2503.20215, 2025-03-26. https://arxiv.org/abs/2503.20215
- *Approach:* Thinker (LLM) plus Talker (dual-track AR speech) with TMRoPE time-aligned audio/video positions. 7B weights are on HF.

**Qwen3-Omni**, arXiv 2509.17765, 2025-09-22. https://arxiv.org/abs/2509.17765 · https://github.com/QwenLM/Qwen3-Omni (Apache-2.0)
- *Approach:* MoE Thinker–Talker; a multi-codebook Talker plus a causal ConvNet replace block diffusion.
- *Latency:* 234 ms theoretical cold-start first-packet latency (model-side only, no network).

**Qwen3.5-Omni**, arXiv 2604.15804, 2026-04-17. https://arxiv.org/abs/2604.15804
- *Claims:* hybrid-attention MoE, 256k context, 10+ h of audio, 400 s of 720p video, and ARIA text–speech alignment.
- *Availability:* open weights **[unverified]**. **[abstract-level]**

**MiniCPM-o 4.5 (OpenBMB)**, arXiv 2604.27393, 2026-04-30. https://arxiv.org/abs/2604.27393
- *Approach:* "Omni-Flow" aligns all inputs and outputs on a shared time axis, giving full duplex (see, listen and speak at once) plus proactive comments/reminders.
- *Size and footprint:* 9B; edge deployment under 12 GB RAM.
- *Relevance:* an open, video-aware duplex front-end (repo: OpenBMB/MiniCPM-V/o, Apache-2.0). The predecessor MiniCPM-o 2.6 (early 2025) marketed "multimodal live streaming" (repo title).

**GLM-4-Voice (Zeng et al., Zhipu/Tsinghua)**, arXiv 2412.02612, 2024-12-03. https://arxiv.org/abs/2412.02612
- *Approach:* 12.5 Hz single-codebook tokenizer at 175 bps, continued pre-training from GLM-4-9B on 1T tokens.
- *Control:* instruction control of emotion, rate and dialect.

**VITA-1.5 (Fu et al.)**, arXiv 2501.01957, 2025-01-03 (NeurIPS 2025 spotlight). https://arxiv.org/abs/2501.01957
- End-to-end vision+speech without separate ASR/TTS. Exact latency numbers **[unverified]**.

**VITA-Audio (Long et al.)**, arXiv 2505.03739, 2025-05-06.
- MCTP module emits several audio tokens per forward pass to cut first-audio latency.

**Step-Audio (StepFun)**, arXiv 2502.11946, 2025-02-17. https://arxiv.org/abs/2502.11946
- 130B unified model; Step-Audio-Chat and TTS-3B are open.
- Instruction control of dialect, emotion and singing; tool calling and role-play.

**StepAudio 3 Realtime**, arXiv 2609.14005, 2026-09-12. https://arxiv.org/abs/2609.14005
- *Approach:* "listen-converse-think-act" loop with "Think-While-Speaking".
- *Reported scores:* 98.9 on the Artificial Analysis Full-Duplex Bench; 56.0% on τ-Voice.
- *Unknowns:* latency and hardware n/s in the abstract. License CC BY-NC-ND (paper). **[abstract-level]**

**Kimi-Audio (Moonshot)**, arXiv 2504.18425, 2025-04-25.
- 12.5 Hz tokenizer, continuous-in / discrete-out, chunk-wise streaming flow-matching detokenizer, 13M+ h of audio. Open-source.

**MiniMax-Speech**, arXiv 2505.07916, 2025-05-12. https://arxiv.org/abs/2505.07916
- *Approach:* AR transformer TTS with a learnable speaker encoder (zero-shot, no transcript needed) and Flow-VAE.
- *Claims:* 32 languages; top of the TTS Arena at the time **[vendor claim]**.
- *Relevance:* relevant because the reference agent is reportedly MiniMax-based.

**Sesame CSM**, blog "Crossing the uncanny valley of conversational voice", 2025-02-27. https://www.sesame.com/blog/crossing-the-uncanny-valley-of-voice
- *Approach:* split transformer (backbone predicts RVQ level 0; a small decoder predicts the rest). Sizes range from 1B/100M to 8B/300M.
- *Finding:* without context, listeners could not tell CSM from real speech; *with* conversational context they preferred real recordings.
- *Availability:* Apache-2.0 release plans. The 1B checkpoint release date is **[unverified]**.

#### Duplex, interruption and turn-taking evaluation

**Full-Duplex-Bench v1/v1.5/v2 (Lin et al.)**, arXiv 2503.04721 (2025-03-06) and 2510.07838 (2025-10-09). https://github.com/DanielLin94144/Full-Duplex-Bench
- *v1 measures:* pause handling, backchannel, smooth turn-taking and user interruption (takeover rate, JSD to human backchannel timing, latency).
- *v2:* multi-turn with an automated examiner over WebRTC/WebSocket.

**EchoChain (Modi et al.)**, arXiv 2604.16456, 2026-04-08. https://arxiv.org/abs/2604.16456
- *Measures:* state-update reasoning when the user interrupts mid-response.
- *Findings:* no system passes more than 50%; failure modes are contextual inertia, interruption amnesia and objective displacement; removing interruptions cuts failures by 40.2%. **[abstract-level]**
- *Relevance:* directly relevant to "corrections, interruptions, changing goals".

**IHBench (Salimi et al.)**, arXiv 2606.19595, 2026-06-17.
- *Measures:* post-interruption recovery in state-machine workflows, across six interruption types.
- *Findings:* closed models degrade about 3.3× more slowly with conversation length; open models are sensitive to audio vs text input. **[abstract-level]**

**PACE (Wang et al.)**, arXiv 2608.07631, 2026-08-07. https://arxiv.org/abs/2608.07631
- *Problem:* "generative context mis-anchoring" (see G2).
- *Approach:* middleware that removes unplayed assistant content from context after an interruption. It works with black-box speech models.
- *Results:* GCM-Bench (108 cases) accuracy rises from 25.0% to 96.3%; response quality preserved on Full-Duplex-Bench v1 (200 interruption samples). **[abstract-level]**
- *Relevance:* the direct precedent for C1.

**VideoFDB (Mazumdar et al., NVIDIA)**, arXiv 2605.30256, 2026-05-28.
- *Setup:* 237 real video-call clips, 11 nonverbal dynamics, rubric LM-as-judge.
- *Findings:* "captioning collapse", "visual-stream ignorance", and speech-to-avatar systems cannot produce full-duplex nonverbal responses. **[abstract-level]**

**OmniInteract (Lu et al.)**, arXiv 2605.26485, 2026-05-26.
- *Setup:* 250 videos, 1,430 time-grounded response slots, including interruption diagnostics.
- *Findings:* best IA-QTF1 is 0.368, and 0.052 on 1QnA. Offline reasoning ability does not transfer to online interaction.

**Omni-DuplexEval (He et al.)**, arXiv 2605.17360, 2026-05-17.
- *Setup:* 660 videos covering real-time description and proactive reminders.
- *Findings:* best model scores 39.6% overall and 20.0% on proactive reminders.

#### Commercial real-time APIs (all [vendor claim])

**OpenAI Realtime API**
- *History (API changelog):* gpt-4o-realtime-preview (2024-10-01); GA with gpt-realtime (2025-08-28).
- *GPT-Realtime-2 (2026-05):* reasoning effort from minimal to xhigh, 128K context, "96.6% Big Bench Audio at xhigh". These figures come from secondary coverage **[unverified against primary]**. The changelog page rendering showed an ambiguous year; secondary sources say May 2026.
- *gpt-realtime-2.1 / 2.1-mini (2026-07):* improved interruption behaviour; p95 latency down by at least 25% (community announcement).
- *GPT-Live-1 (GA 2026-09-10; model page https://developers.openai.com/api/docs/models/gpt-live-1):*
  - full-duplex audio/text only (no image/video input)
  - "delegates both reasoning and tool invocation to a backend agent system"
  - `v1/live/sessions` endpoint only; $0.05/min
  - secondary coverage reports +30 pp on Full-Duplex-Bench vs 2.1
- *Relevance:* industry is converging on the front/back split. No video output.

**Gemini Live API** (https://ai.google.dev/gemini-api/docs/live, …/live-session, …/models/gemini-3.8-live)
- *Transport:* stateful WebSocket; WebRTC via LiveKit/Pipecat partners.
- *Input/interaction:* image/video input as JPEG ≤1 FPS; barge-in supported.
- *Session limits (without compression):* 15 min audio-only, 2 min audio+video; connection about 10 min. Context-window compression and resumption tokens (valid 2 h) extend sessions.
- *Gemini 3.8 Live (2026-09):* proactive audio permanently on; affective dialog removed; async function calling by default; "interleaved reasoning".
- *Relevance:* the 1 FPS vision cap limits its use as a fine-grained compliance verifier.

**MiniMax.** Speech API (MiniMax-Speech lineage). MiniMax H3 (blog 2026-07-31; https://www.minimax.io/blog/minimax-h3):
- open-weights omni video generation model
- up to 15 s at 2K
- no live/streaming mode mentioned
- weights promised "in the coming days" in the blog; an HF repo `MiniMaxAI/MiniMax-H3` exists (search result)

#### Streaming video understanding agents

**VideoLLM-online / LIVE (Chen et al.)**, arXiv 2406.11816, 2024-06-17 (CVPR 2024).
- Streaming EOS-style training objective decides when to speak; offline→streaming data conversion.
- Code, model and demo released.

**Dispider (Qian et al.)**, arXiv 2501.03218, 2025-01-06.
- Asynchronous perception, decision and reaction modules: the prototype "don't block perception while reasoning" design.

**StreamBridge (Wang et al., Apple)**, arXiv 2505.05467, 2025-05-08 (NeurIPS 2025).
- A memory buffer plus a lightweight activation/gating model turn an offline VideoLLM into a proactive streaming assistant.

**StreamingVLM (Xu et al., MIT Han Lab)**, arXiv 2510.09608, 2025-10-10 (ICLR 2026).
- Attention-sink plus recent-vision and recent-text KV cache.
- "Up to 8 FPS on a single NVIDIA H100"; code open.
- *Relevance:* a candidate online verifier.

**Video Streaming Thinking (VST)**, arXiv 2603.12262 (ECCV 2026).
- Reasons while watching, spreading reasoning latency over playback; 15.7× faster than Video-R1.

**Proact-VL**, arXiv 2603.03447 (ICML 2026).
- Proactive real-time companion for game commentary and guidance (Live Gaming Benchmark).
- *Relevance:* livestream commentary is close to our use case.

**JoyAI-VL-Interaction (JD)**, arXiv 2606.14777, 2026-06-10.
- 8B model that decides each second whether to stay silent, respond or delegate to a background model.
- Fully open, with a deployable system (pluggable ASR/TTS, memory, "background brain").
- Human raters preferred it over the Doubao and Gemini in-app video-call assistants **[authors' claim]**.

**StreamArena / StreamMind (Zhang et al.)**, arXiv 2608.05703, 2026-08-06.
- *Benchmark:* hour-scale (88.8 min average) interactive streaming; shows that last-4-frame baselines can match complex models on older benchmarks.
- *StreamMind:* frontend workers handle latency-critical interaction; backend workers asynchronously build persistent multimodal memory.

**DuplexOmni**, arXiv 2606.09186, 2026-06-08.
- An interaction layer and a pluggable thinking layer that run asynchronously and in parallel.

#### Video-call agents and frameworks

**Tavus CVI** (docs: https://docs.tavus.io/sections/conversational-video-interface/overview-cvi)
- *Pipeline:* Raven (perception) → Sparrow (turn-taking) → STT → LLM → TTS → Phoenix (real-time face); WebRTC via Daily.
- *Persona layer:* "PAL" / persona configuration.
- *Latency:* Phoenix-4 (2026-02-18) coverage claims "sub-600ms end-to-end latency" **[vendor claim via secondary coverage]**. Phoenix-4.5 is claimed at 134 ms audio→video **[vendor claim, unverified]**.
- *Relevance:* the closest commercial analogue of a cascaded video persona; no user-controllable world/camera.

**Pipecat** (https://github.com/pipecat-ai/pipecat, BSD-2; primer https://voiceaiandvoiceagents.com/, June 2026 revision)
- Frame-based pipeline with VAD, Smart Turn and interruption handling.
- Latency table and truncation practice: see sections 1.1 and 4.1.

**LiveKit Agents** (https://github.com/livekit/agents, Apache-2.0)
- *Turn detection:* the original text-based EOT model (Qwen2.5-0.5B distilled from 7B) was superseded by the audio-based Turn Detector v1 (2026-06-17). It has dual semantic and acoustic branches and 14 languages.
- *Accuracy claims:* 9.9% false-cutoff at 300 ms (vs 12.9% Deepgram Flux), and 4.5% at 600 ms. The eot-bench suite is Apache-2.0 **[vendor claim]**.

### 3B. Autonomous livestreaming agents, AI VTubers, embodied characters, digital humans

**Neuro-sama** (Vedal)
- *History:* began as an osu! bot in 2018; Twitch debut with LLM chat, TTS and a Live2D avatar on 2022-12-19. Evil Neuro followed on 2023-03-25, and a 3D model on 2025-11-15. Became the most-subscribed Twitch channel around January 2026 (Wikipedia; Dexerto).
- *Architecture:* public knowledge is limited. The creator has confirmed an LLM-based core but not the model or implementation. Community claims (OpenVoice TTS, faster-whisper STT) are **[unverified]**.
- *Behaviour:* output filtering replaces blocked text with "filtered".
- *Relevance:* the de facto livestream reference. Viewer research (arXiv 2509.10427, qualitative fandom study) finds attachment is sustained by a "consistent persona", unpredictability and collective events. This supports persona consistency and memory as core requirements.

**AI livestreaming research papers**

- **LiveThinking (Sun et al., Taobao Live)**, arXiv 2510.07685, 2025-10-09.
  - Distils a 670B teacher into a 30B-A3B MoE via rejection-sampling fine-tuning, then GRPO to shorten reasoning.
  - 30× cost reduction, sub-second responses, statistically significant GMV lift in deployment.
  - *Relevance:* shows production live commerce trades reasoning depth for latency.
- **DLIOS**, arXiv 2603.03060.
  - Douyin overlay system: danmaku quick-reaction engine (keyword routing to static speech or an LLM) and hot-swappable persona config.
  - Reports LLM→TTS segment P95 ≤ 2.1 s over a 36 h stress test.
  - An engineering case study: low-rigour but a concrete latency datapoint.
- **The Triadic Loop**, arXiv 2604.18850. Conceptual paper on streamer–AI co-host–audience alignment; introduces "strategic misalignment".
- We found **no paper titled "Towards AI livestreaming"**. Treat that phrase in the task list as unverified.

**E-commerce digital humans (industry; mostly [vendor claim])**
- **Baidu Huiboxing:** Luo Yonghao's digital-human livestream on 2025-06-15. Over 6 h, 13M+ views, reported GMV above ¥55M. The script was generated with ERNIE 4.5 Turbo; multi-avatar banter (TechNode 2025-06-17; CNBC 2025-06-19).
- **JD:** Richard Liu avatar stream in April 2024. JoyStreamer digital-human hosts reached more than 70,000 merchants (reported March 2026); "cost one-tenth" of human hosts **[vendor claim, secondary]**. Research lineage:
  - JoyStreamer (arXiv 2602.00702)
  - JoyStreamer-Flash (arXiv 2512.11423, 2025-12-12): 1.3B, 4-step causal AR diffusion, 16 FPS on a single GPU (GPU type n/s), unbounded length via cache-resetting RoPE.
- **Alibaba/Taobao:** TaoMate (arXiv 2607.24359, 2026-07-27) uses an immutable visual anchor plus fixed-capacity compressed A/V memory for long-form stable digital humans (stable over 1,000 s per summary). LiveThinking (above) also comes from Taobao Live.

**Streaming digital-human generation (research)**
- **TalkingMachines (Character.AI)**, arXiv 2506.03099: 18B audio-driven AR DiT; DiT and VAE disaggregated across devices.
- **MIDAS**, arXiv 2508.19320: LLM backbone with a diffusion head; audio, pose and text conditions; 64× compression autoencoder; about 20k h of dialogue data.
- **Wan-Streamer v0.1**, arXiv 2606.25041, 2026-06-23:
  - one transformer over interleaved video, audio and text tokens with block-causal attention; no separate VAD/ASR/TTS/animation modules
  - ~200 ms model-side, ~550 ms total including a 350 ms network round trip; 160 ms streaming units at 25 fps
  - weights **[unverified]**
  - the strongest end-to-end alternative to our cascade
- **Beyond Monologue**, arXiv 2604.10367: talking+listening avatar with dual-stream audio.
- **Vorch-Streamer**, arXiv 2608.05663: an external LM predicts 25 Hz speech-planning tokens to control speech progression; 27.12 FPS joint audio-video.
- **OmniMate**, arXiv 2607.23023: joint video, speech and SFX; a Generation Progress Controller for chunk completion.
- **Super Star**, arXiv 2608.24909 (ACM MM 2026): streaming speech plus online gesture generation with a self-evolving feedback loop.

**Game and embodied characters**
- **Generative Agents (Park et al.)**, arXiv 2304.03442, 2023-04-07 (UIST 2023).
  - Memory stream with retrieval scored on recency, importance and relevance; periodic reflection; planning.
  - *Relevance:* the persona and memory reference design.
- **Voyager (Wang et al.)**, arXiv 2305.16291, 2023-05-25.
  - Automatic curriculum, a skill library of executable code, and iterative prompting with environment feedback and self-verification. 3.3× more unique items than baselines.
  - *Relevance:* the template for C3 (a library of verified generator affordances).
- **SIMA 2 (Google DeepMind)**, arXiv 2512.04797, 2025-12-04.
  - Gemini-based agent acting through keyboard and mouse in 3D games; takes language, sketch and emoji instructions; self-improves with Gemini-generated tasks and rewards.
  - Demonstrated inside Genie 3 generated worlds (blog).
  - *Relevance:* the closest precedent for "an LLM agent acting inside a generated world", although there the agent is the *player*, not the persona.
- **NVIDIA ACE** (CES 2025 blog): "autonomous game characters" using on-device SLMs. PUBG Ally uses Mistral-Nemo-Minitron-8B-128k-instruct; inZOI "Smart Zoi". Perceive, plan, act **[vendor claim]**.
- **Inworld** (Runtime and TTS): orchestration with long-term memory, safety and knowledge features **[vendor claim]**.
- **Convai:** NPC "Prompt-to-Action". User prompts map to structured atomic actions executed by the game engine, with scene perception via camera or metadata **[vendor claim]**. The key contrast with our setting: the game engine *guarantees* action semantics, while a generative world model does not.

### 3C. Reasoning, planning and closed-loop control over generative models

**LLM as director (offline)**
- **VideoDirectorGPT (Lin et al.)**, arXiv 2309.15091, 2023-09-26. A GPT-4 planner produces a multi-scene "video plan" (scenes, entities, layouts, backgrounds, consistency groups); Layout2Vid executes it.
- **LVD (Lian et al.)**, arXiv 2309.17444 (ICLR 2024). An LLM produces dynamic scene layouts that guide video diffusion; code released.
- **DirecT2V (Hong et al.)**, arXiv 2305.14330. An LLM writes frame-level prompts for zero-shot T2V.
- **Mora (Yuan et al.)**, arXiv 2403.13248. Multi-agent Sora-like pipeline built from open modules.
- **StoryAgent (Hu et al.)**, arXiv 2411.04925. Story designer, storyboard, video creator and evaluator agents.
- *Common limitation:* offline, minutes per clip, with rich layout-level controls that real-time world models do not expose.

**LLM/VLM agents inside interactive world models**
- **LingBot-World 2.0 / "Infinite Worlds with Versatile Interactions" (Gao et al., Robbyant/Ant Group)**, arXiv 2607.07534, 2026-07-08. https://github.com/robbyant/lingbot-world-v2
  - *Model:* 14B causal model (plus a 1.3B single-GPU variant); controls are camera pose/actions plus per-chunk text for character actions and environment events.
  - *Speed:* a distilled real-time variant claims 720p at 60 fps (hardware "substantial", not specified in our reading).
  - *Agentic harness:* the Pilot plans and executes character behaviour; a VLM "Director" watches the current frame and proposes events such as weather or spawns.
  - *What is missing (per our HTML read):* the VLM is not named, no loop frequency is given, and there is no quantitative evaluation of agent validity. The authors state the model "does not truly remember the world it has generated".
  - *Predecessor:* LingBot-World v1, "Advancing Open-source World Models", arXiv 2601.20540.
  - *SGLang cookbook:* checkpoint `robbyant/lingbot-world-v2-14b-causal-fast-diffusers`; example of 8 GPUs, 832×480, target 25 FPS, 9 frames per chunk, 4 steps. At 25 FPS a 9-frame chunk is 360 ms of video, which bounds the control granularity (derived).
- **Zing-0.5**, arXiv 2609.17909, 2026-09-15. Joint keyboard and text control; text events applied "without restarting generation"; 24 FPS at 832×480; weights plus SGLang serving released; about $0.009 per stream-minute **[authors' claim]**.
- **SIMA 2 + Genie 3**: see 3B.
- **Agentic Video Generation: text to executable event graphs via tool-constrained LLM planning**, arXiv 2604.10383. Found in search; not read; **[unverified content]**.

**Generate → verify → refine (offline)**
- **Self-Refine**, arXiv 2303.17651. Generic iterative self-feedback.
- **VideoRepair (Lee et al.)**, arXiv 2411.15115. MLLM-generated evaluation questions detect misaligned regions; region-preserving local regeneration.
- **VISTA (Long et al., Google)**, arXiv 2510.15831 (CVPR 2026). Temporal plan, then a pairwise tournament, then critics (visual, audio, context), then prompt rewriting. Up to a 60% pairwise win rate.
- **PhyT2V**, arXiv 2412.00596 (CVPR 2025). LLM-guided iterative prompt refinement for physical plausibility; reports "2.3×" adherence.
- **VideoAgent (Soni et al.)**, arXiv 2410.10076. VLM feedback refines video plans for embodied control.
- **VideoScore**, arXiv 2406.15252 (EMNLP 2024; Spearman 77.1 with humans on VideoFeedback-test). **VideoScore2**, arXiv 2509.22799: three axes (visual, text alignment, physical/common-sense) with chain-of-thought rationales; SFT followed by GRPO.
- *Gap:* all of these run over complete clips, over seconds to minutes, not online.

**Instruction-following benchmarks (text)**
- **IFEval**, arXiv 2311.07911. Verifiable single-turn constraints.
- **FollowBench**, arXiv 2310.20410. Multi-level constraints (content, situation, style, format, example).
- **MT-Bench-101**, arXiv 2402.14762. 13 tasks across 4,208 turns.
- **Multi-IF**, arXiv 2410.15553. Three-turn multilingual IFEval extension (4,501 conversations).
- **MultiChallenge**, arXiv 2501.17399. Instruction retention, inference memory, versioned editing and self-coherence. All frontier models scored below 50% at release.
- *Relevance:* use these protocols to design turn-level compliance checks. They say nothing about *observable* audiovisual compliance.

**Video and world-model control-compliance benchmarks**
- **WorldMark**, arXiv 2604.21686. Per-model adapters map a standard WASD vocabulary. Measures direction accuracy and purity, response latency, stability and memory. Findings: "fastest responders are often the least stable"; the highest-quality model ranked last on translation accuracy and latency.
- **WorldRoamBench**, arXiv 2606.31672. Action, vision, physics and memory over 10–60 s sessions; "none reliably satisfies all dimensions".
- **iWorld-Bench**, arXiv 2605.03941 (ICML 2026). 14 models; trajectory following and memory.

### 3D. Low-latency orchestration

**Human turn-taking thresholds**
- **Stivers et al. 2009** (PNAS 106(26):10587–10592, doi:10.1073/pnas.0903616106), across 10 languages:
  - per-language modal response offset between 0 and +200 ms; overall mode 0 ms
  - overall mean 208 ms (Japanese mean 7 ms; Danish 469 ms)
  - figures via a secondary quotation of the paper; the PNAS page was blocked (403)
- **Levinson & Torreira 2015** (Front. Psychol. 6:731, doi:10.3389/fpsyg.2015.00731): gaps are about 200 ms while production latency exceeds 600 ms, so listeners must *predict* turn ends and plan in overlap.
- *Implication:* even Moshi-class systems (~200 ms) only just match human gaps. Cascades (~0.8–1.5 s) need fillers, backchannels or speculative starts (PredGen, ConvFill, LTS-VoiceAgent).

**Speculative and asynchronous pipelines**
- **PredGen**, arXiv 2506.15556. Speculates candidate responses while the user is still speaking; about 2× latency reduction in simulation.
- **Can Speech LLMs Think while Listening?**, arXiv 2510.07497 (Meta). Starts reasoning early, guided by an entropy-based "question completeness" signal; DPO gives a 70% latency reduction without accuracy loss.
- **ConvFill / Thinking While Speaking**, arXiv 2511.07397. A small talker (135M–1.7B) hides a frontier reasoner's latency by infilling its streamed knowledge; within 6.3% of reasoner accuracy; n=18 user study on an Apple M2; code open.
- **LTS-VoiceAgent**, arXiv 2601.19952. Semantic trigger plus a background thinker and foreground speaker; Pause-and-Repair benchmark.
- **Speculative Interaction Agents (Hooper et al., Berkeley)**, arXiv 2605.13360. Asynchronous I/O plus speculative tool calling: 1.3–1.7× faster (cloud), 1.6–2.2× (edge 3B models).
- **Never Stop Thinking (Li & Shi)**, arXiv 2609.17416. Interrupt-and-resume orchestrator; 19% overall latency cut; ReactiveBench. Warns that LLM judges reward *visible* reasoning, so use verifiable objectives. This caveat applies to our VLM-judge plans.
- **AgileThinker**, arXiv 2511.04898. Reactive and planning threads run together; Real-Time Reasoning Gym.

**Streaming TTS and STT**
- **CosyVoice 2**, arXiv 2412.10117. FSQ tokens, LLM backbone, chunk-aware causal flow matching; latency "as low as 150ms". **CosyVoice 3**, arXiv 2505.17589, focuses on in-the-wild robustness.
- **Fish-Speech**, arXiv 2411.01156. Dual-AR with GFSQ.
- **F5-TTS**, arXiv 2410.06885. Non-autoregressive flow matching, RTF 0.15. Not natively streaming.
- **Kyutai DSM**, arXiv 2509.08753. Delayed-streams modelling for both ASR and TTS. TTS first audio in 220 ms; STT delays of 0.5 s (1B en/fr) and 2.5 s (2.6B en). The Unmute demo combines DSM-ASR, DSM-TTS and Gemma 3.
- **MiniMax-Speech, Sesame CSM**: see 3A.

**Audio-visual synchronisation standards**
- **ITU-R BT.1359-1 (11/1998)**, "Relative timing of sound and vision for broadcasting": detectability +45 ms (audio leads) to −125 ms (audio lags). The acceptability threshold is commonly quoted as +90/−185 ms (Wikipedia and TV Tech quote slightly different lag values). **[primary PDF not read]**
- **EBU R37:** end-to-end +40/−60 ms; per stage +5/−15 ms.
- **ATSC IS-191 (2003):** +15/−45 ms.
- *Design target for our system:* keep generated-face-to-TTS skew within EBU R37. Carry a shared presentation timestamp from the TTS audio clock into video chunk scheduling. With WebRTC, lip sync is done at the receiver from RTP/RTCP timestamps, which assumes correct capture timestamps.

**Serving systems for streaming generation**
- **StreamDiffusion**, arXiv 2312.12491. Stream batch plus an I/O queue; 91.07 fps image-to-image on an RTX 4090.
- **StreamDiffusionV2**, arXiv 2511.07399. SLO-aware batching, sink-token rolling KV, motion-aware noise, pipeline parallelism over steps and layers. First frame in 0.5 s; 58.28 FPS (14B) and 64.52 FPS (1.3B) on 4×H100.
- **xDiT**, arXiv 2411.01738. Sequence parallelism, PipeFusion and CFG parallelism for DiTs.
- **FastVideo / Sliding Tile Attention**, arXiv 2502.04507. Cuts HunyuanVideo end-to-end time from 945 s to 501 s (training-free) or 268 s (fine-tuned). Offline speed, not streaming.
- **vLLM-Omni**, arXiv 2602.02204, 2026-02-02. Stage-graph, fully disaggregated serving for any-to-any models; up to 91.4% lower job completion time vs baselines **[authors' claim]**.
- **vLLM-Omni real-time AR-diffusion (local checkout @7b4dc76, 2026-09-24)**. Source: `external/vllm-omni/docs/design/feature/realtime_ar_diffusion.md`, status "experimental".
  - *Identifiers:* `session_id`, a monotonic `event_id` per control/prompt update, `chunk_index` and `request_id`.
  - *Tick lifecycle:* events are queued; `next_chunk()` snapshots prompt, controls and event IDs into a tick; one latent block is generated per tick. State commits only when the returned metadata matches the snapshot (`applied_event_ids`).
  - *Failure handling:* failure marks the session FAILED and requires an explicit reset.
  - *Scope:* the runtime "does not define a public HTTP or WebSocket schema". LingBot camera/action parsing lives in `lingbot_world/actions.py` and `LingBotCameraControlReducer`.
  - *Implications:* (i) `applied_event_ids` is a ready-made hook for a compliance ledger (C2); (ii) preemption granularity is one chunk; (iii) there is no documented mid-chunk cancel.

**WebRTC.** Both Pipecat (Daily) and LiveKit are WebRTC-based. Gemini Live is WebSocket-native with WebRTC through partners. Tavus uses Daily WebRTC.

---

## 4. Cross-cutting analysis for our design

### 4.1 Latency budget sketch (derived, to be measured)

| Stage | Plausible budget | Evidence |
|---|---|---|
| Endpointing / EOT | 200–300 ms | LiveKit v1 at 300 ms; primer VAD trigger 200 ms |
| Front-end first audio (duplex model or filler) | ~200–250 ms model-side | Moshi, Qwen3-Omni, Wan-Streamer |
| Reasoner TTFT (delegated) | ~650 ms typical | Pipecat primer table |
| TTS first packet | 120–220 ms | Primer, CosyVoice 2, Kyutai |
| Video control-to-photon | ≥ one chunk (e.g. 360 ms at 9 frames/25 FPS) + generation + transport | SGLang cookbook example; vLLM-Omni tick semantics |
| AV skew | within +40/−60 ms | EBU R37 |

**Conclusion.** The verbal acknowledgement ("okay, turning around") can land within about 300 ms, but the *visual* compliance lands later. The system should disclose this lag rather than hide it. This mismatch is the concrete research handle behind C1 and C2.

### 4.2 Interruption semantics we need, but no surveyed system specifies for video

1. **Truncate.** Drop generated-but-undisplayed video chunks and audio.
2. **Re-anchor.** Rebuild the agent context to what was displayed (PACE for video).
3. **Preempt.** Let the new event win at the next tick; decide whether to reset KV or continue with a transition prompt.
4. **Verify.** Watch the displayed stream for the requested effect within a deadline.
5. **Recover.** Fall back to an alternative control, or verbally acknowledge failure.

---

## 5. Items searched but not confirmed (do not cite without checking)

- "Towards AI livestreaming": no such paper found.
- Freeze-Omni and VITA-1.5 precise latency numbers.
- Neuro-sama implementation details: OpenVoice and faster-whisper claims come from community pages.
- GPT-Realtime-2 benchmark numbers: secondary sources only.
- Tavus sub-600 ms and 134 ms: secondary coverage and vendor blog titles only.
- ITU-R BT.1359 acceptability lag value (−185 vs −190 ms).
- Open-weight status: Wan-Streamer, Qwen3.5-Omni, StepAudio 3 Realtime, JoyStreamer-Flash.
- The GPU type behind JoyStreamer-Flash's 16 FPS.
- LingBot-World 2.0: the VLM used by the Director agent.
- The reference agent `twitch.tv/sylar_nv`: not indexed by search; implementation per owner only.
