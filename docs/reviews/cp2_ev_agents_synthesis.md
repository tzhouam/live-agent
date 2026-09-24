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

