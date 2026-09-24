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

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/research_proposal.md =====
# Capability-Grounded Closed-Loop Control for a Real-Time, Personalized Live Agent

**Research proposal: live-agent project, Phase 1**

*Draft v1.0-rc, 2026-09-25. Review status is in §14 and `docs/codex_reviews.md`.*

**Evidence conventions.** Every quantitative statement carries one of these labels:
- **[cited]**: from a named primary source.
- **[vendor]**: from product or marketing material.
- **[local-code]**: verified in upstream vLLM-Omni `main` at commit `7b4dc76` (2026-09-24), cloned at `external/vllm-omni`.
- **[derived]**: our arithmetic from cited or code-level quantities.
- **[target]**: a proposed goal, not a result.
- **[estimate]**: our judgement.

**No experiment, measurement or user study has been run in this phase.** Supporting detail:
- `docs/related_work.md`: literature synthesis and comparison matrices.
- `docs/backbone_verification.md`: code-level backbone audit.
- `docs/decision_log.md`: decisions, alternatives and evidence.
- `docs/figures/`: editable Mermaid sources with rendered SVGs.

---

## Abstract

Real-time video generators can now stream minutes of controllable video. A live *agent* built on one must do more
than stream: it must follow instructions that are corrected and interrupted mid-stream, remember a user across
sessions, keep a consistent persona, and turn decisions into controls the generator can actually execute. The
backbone the project requires is LingBot-World 2.0 served by vLLM-Omni. In the pinned vLLM-Omni code:
- the public streaming path accepts only SE(3) camera interactions mid-session;
- it keeps a short sink-plus-window KV state;
- it produces no audio.

This is a camera-controlled world model, not a talking avatar [local-code].

We propose a **capability-grounded closed-loop controller** built from four parts:
1. A time-aligned behavior intermediate representation (IR).
2. A compiler that maps the IR only onto *empirically calibrated* generator affordances.
3. A deadline-bounded monitor that judges compliance on the frames the user actually sees.
4. A provenance-typed, scope-separated memory service.

The persona is rendered as a **dual-shot live persona**: a lip-synced avatar close-up from an external audio-driven
model, plus a LingBot-World "world shot" of the same persona. The controller switches between the two shots.

The central scientific question is whether calibrated affordances plus online visual verification raise *observable*
instruction compliance, and make failure reporting honest, at an acceptable latency cost. Three comparison
controllers isolate the effect:
- a prompt-only open-loop controller;
- a capability-aware open-loop controller;
- a verifier without calibrated affordances.

We also contribute a measurement protocol for **wall-clock time-to-visible-compliance (TVC)**, and a memory
evaluation that measures false memories and cross-scope leakage across modalities.

Milestone M0 is a short (≈1 week) hardware and backbone characterization. It gates every latency target, because all
real-time evidence for this backbone comes from upstream H200 multi-GPU stacks. Our local GPUs report as
"NVIDIA L20X" and their identity is unresolved.

---

## 1. Motivation and problem definition

### 1.1 Motivation

A live persona is a *closed-loop* system. The user speaks, the agent decides, the generator renders, the user sees
the result and reacts, often before the agent's previous plan has finished rendering. Three facts make this hard:

1. **Rendering has latency and granularity, and the transport adds queueing.**
   - LingBot-World applies a control at the next autoregressive (AR) chunk boundary. Each chunk is 12 frames
     (9 for the first) [local-code: `pipeline.py:2186-2197`].
   - A chunk already in generation cannot be redirected. `session.stop` cancels the whole rollout.
   - The WS server sends each chunk as soon as it is produced, with no pacing to playback
     [local-code: `serving_video_output_stream.py:148-155`; no pacing logic found]. When generation runs faster
     than playback, undisplayed video accumulates at the client. That backlog is exactly what stale plans and
     mis-anchored corrections come from.
2. **The generator's affordances are narrow and stochastic.**
   - Mid-session, the public path accepts camera SE(3) interactions only [local-code: `registry.py:25-27`].
   - The LingBot-World 2.0 paper realizes character actions through chunk-wise text prompts [cited: gao2026lingbotworld2].
     The streaming server does not expose that path, and whether the prompts reliably produce the actions is unverified.
   - A language model that "decides to wave" and says so can therefore easily be wrong about what the user sees.
3. **The generator's state is not a memory.**
   - The KV cache keeps an attention sink (the first 3 chunks) and a rolling window (the most recent 3 chunks,
     about 2.25 s at 16 fps) [local-code].
   - The authors say that regions leaving the window are "regenerated rather than recalled" [cited].
   - Long LLM contexts are unreliable memories as well [cited: wu2024longmemeval, modarressi2025nolima].

### 1.2 Working hypothesis, refined

The owner's starting hypothesis is that "real-time video generation alone is insufficient for reliable, stateful
agent behavior". The literature supports a narrower version:
- **Counter-evidence (§2):** unified audio-visual models such as X-Streamer, Wan-Streamer and LPM 1.0 *do* embed
  reasoning.
- **What remains missing:** none of the systems we reviewed demonstrates correctable cross-session memory together
  with verified visible compliance.

We therefore test **H-core**:

> Without an external state layer (any persistent store or controller outside the model's weights, KV cache and
> context window), neither generator KV state nor a thinker's dialogue context provides three things:
> (a) user-correctable and deletable cross-session memory with provenance;
> (b) verified visible compliance with instructions;
> (c) control restricted to affordances the generator can actually render.

The operational test is in §7.4. A system without an external layer that passes it refutes H-core for that system.

### 1.3 Target scenario (focused demo)

**The dual-shot live persona "companion host"** (decision D-005).

**Persona and shots.** A single fictional persona, with a reference image and a canon profile curated by the
project, appears in two shots:
- **Presenter shot.** A lip-synced close-up rendered by an external audio-driven avatar model from the persona
  reference image and the TTS audio.
- **World shot.** LingBot-World renders the same persona, from the same reference image and prompt, in a scene
  seen from a third-person view.
  - **Committed:** viewpoint control, i.e. camera turns, moves and stops, through the verified SE(3) camera interface.
  - **Conditional:** character locomotion ("walk toward the lake", "walk slower") and scene or character events.
    Camera motion is not character control [local-code]. These behaviours are prompt-conditioned and depend on
    extension C1 and on E1 calibration showing measurable success.

A **shot track** in the controller cuts between the two at chunk boundaries, as a broadcast director would.

**Mode 1 (primary acceptance scenario): private 1:1 session.** A user talks to the persona by voice. Typical requests:
- "Turn left… no, the other way!" A correction and interruption. Committed (camera).
- "Look around slowly, I like calm views." A preference that should persist and is realised as camera speed.
  Committed.
- "What did I tell you about my sister?" Episodic recall. Committed.
- "Forget that." Deletion. Committed.
- "Show me the lake village again, the one from last time." Cross-session visual memory by restarting from a stored
  frame. The restart has a visible seam.
- "Walk to the lake" / "make it snow." Conditional on C1 and E1.

**First demo, defined as a measured configuration.** The first demo is whatever M0 qualifies as real-time. Its
fallback is the presenter shot plus pre-rendered world clips; the reference agent appears to use a similar clip
regime, but that is unverified. Live world events, sessions longer than the validated length, and restarts are
**gated extensions**. They enter the demo only after their measurements pass.

**Mode 2 (second evaluation scenario): private test livestream.**
- Chat messages come from scripted test accounts.
- Viewers vote on destinations and ask the persona questions.
- Some messages attempt memory poisoning.
- Private memories must never surface.
- **No public broadcast in this phase.**

**Out of scope.** General-purpose assistance, tool use beyond memory, multi-user concurrency on one generator,
and commercial use. The LingBot weights are CC BY-NC-SA 4.0 [cited].

### 1.4 Problem definition

Notation:
- The user issues time-stamped instructions $u_t$.
- The agent emits a behavior program $\pi$: time-aligned actions on tracks {speech, shot, camera, scene-event,
  character-event}.
- The generator realises a control $c$ with success probability $p_c$ and a time-to-effect distribution $F_c$. Both
  are unknown a priori.
- The user perceives the displayed stream $v_{\le \tau}$ at presentation time $\tau$.

For each instruction, the agent should maximise *observable compliance*: a judge applied to the displayed frames
agrees that the instruction was executed within a deadline $D$. It should minimise TVC and false claims of completion,
while keeping memory correct, scoped and deletable. The main difficulty is that $p_c$ and $F_c$ are properties of a
stochastic generator, not of a game engine.

---

## 2. Related work and research gap

The full synthesis and comparison matrices are in `docs/related_work.md`. We summarize the points that shape
the design.

**Streaming video and world models.** The distill-to-causal recipe is now standard: CausVid → Self Forcing →
Causal Forcing, with rolling KV and attention sinks. A 1.3B model runs at about 16–21 FPS at 480p on one H100
[cited: huang2025selfforcing, yang2025longlive].

For 14B models:
- LingBot-World 2.0 in vLLM-Omni reaches ≈549 ms per 12-frame chunk on 4×H200 with the PR #7749 stack
  [cited, upstream PR].
- On one GPU in eager mode it takes ≈3.24 s per chunk [cited].

Mid-stream text control exists in LongLive (KV re-cache), Echo-Forcing and Genie 3 ("promptable events", [vendor]).
Most real-time world models control only the camera or ego-motion; Matrix-Game 2.0 removes text input entirely.
Character behaviour inside world models is still nascent (LingBot-World 2.0 actions, HelloWorld, ReactiveGWM).

**Avatars.** Audio-driven streaming avatars run in real time:
- LiveAvatar: 45 FPS on 5×H800.
- SoulX-FlashTalk: 32 FPS on 8×H800.
- SoulX-FlashHead Lite: 96 FPS on an RTX 4090.
- Ditto and LivePortrait: single-GPU real-time.

All figures are [cited]. These avatars lip-sync but do not control the scene. Unified duplex audio-video models trade
resolution for integration: X-Streamer runs at 256², Wan-Streamer at 192p. Joint audio-video models are offline and
clip-length (MiniMax H3: 4–15 s) [cited].

**Agents and orchestration.** The front/back "fast talker / slow thinker" split is standard (GPT-Live-1, Dispider,
JoyAI-VL-Interaction); we reuse it and do not claim it. Voice cascades achieve about 1.3 s round trips
[vendor: pipecat2026primer]. Interruption handling is weak even for speech alone: no system passes more than 50% on
EchoChain [cited]. PACE shows that aligning context with actual *playback* fixes mis-anchored interruptions in audio
[cited: wang2026pace].

**Control over generators.** Prior art:
- SayCan grounds plans in measured affordances.
- Inner Monologue replans from closed-loop feedback.
- VISTA and SPIRAL refine video with VLM critics, offline or iteratively.
- LingBot-World 2.0 ships a VLM Director and Pilot, with no reported evaluation of whether their events are valid.

Latency-related measures exist:
- WorldMark: response latency counted in generated frames.
- ABot-World-0: wall-clock time until the first frame is *available*, with no compliance check.

**Memory.**
- Storage mechanisms are mature: MemGPT, Generative Agents, Mem0, Zep/Graphiti.
- Correction, forgetting and deletion are weak:
  - MemoryAgentBench selective forgetting scores at most 28%.
  - K-Bench finds 22–86% leakage after "deletion".
- Memory poisoning is demonstrated by MINJA and MPBench.
- Multi-principal scoping is unsolved (GateMem).

All [cited].

**Gap.** We found no system or benchmark that closes the loop for a *stochastic streaming generator*: calibrated
affordances, deadline-bounded verification on *displayed* frames, and honest failure reporting, evaluated together with
cross-session memory and persona consistency. §3 states which parts are scientific contributions.

---

## 3. Contributions: science vs. engineering

**Scientific contributions (to be tested):**
- **S1 (central).** Capability-grounded closed-loop control for a stochastic streaming generator, with three parts:
  - a capability manifest calibrated from measured success rates, time-to-effect distributions and side effects;
  - a compiler that maps the IR only onto supported affordances, and degrades or declines the rest;
  - a deadline-bounded monitor on displayed frames.

  The claim is the measured effect of this *combination* on observable compliance and false-claim rates,
  isolated by ablation against SayCan-, Inner-Monologue- and open-loop-style controllers.
- **S2 (measurement).** A wall-clock TVC protocol for chunked AR generators:
  - it decomposes latency into queueing, generation, transport, playback backlog and visual inertia;
  - it treats instructions that never comply as censored observations;
  - it separates TVC from generated-frame response latency (WorldMark) and frame availability (ABot-World-0).
- **S3 (evaluation).** Memory for a live persona:
  - typed by provenance (user-asserted, agent-inferred, agent-generated, viewer-claimed, system-observed);
  - separated by scope (private, public, canon);
  - evaluated for false memories, correction and deletion propagation, and leakage across speech, on-screen text and
    generated visuals.

  The mechanisms are borrowed (§2). The contribution is the live, multimodal evaluation.

**Engineering integration (necessary, not claimed as research):**
Engineering items are labelled I1–I4 to keep them distinct from experiments E1–E6.
- **I1.** vLLM-Omni extensions C1–C3: a prompt-interaction path on the stepwise LingBot pipeline, WS reset and session
  extension, and server-side chunk timestamps.
- **I2.** Client presentation timestamps and a bounded look-ahead gate (C4).
- **I3.** Dual-shot rendering with a shared persona reference and a shared presentation timeline (C5, C6).
- **I4.** Voice pipeline (VAD, ASR, turn-taking, streaming TTS) built from existing frameworks.

**Longer-term research (not needed for the first demo):** a character-centric live world model that conditions
LingBot-World on speech audio and behavior tokens (A3, §5.1). It requires training and is not claimed here.

---

## 4. Research questions and falsifiable hypotheses

The success thresholds are in §8. All thresholds are **[target]**.

| RQ | Question | Hypothesis | Falsified if |
|---|---|---|---|
| RQ1 | Does capability-grounded closed-loop control improve *observable* compliance over open-loop LLM control? A1 and A2 share memory, renderers and the same generator control substrate (camera, plus C1 prompts where built); only the controller differs | **H1a:** A2 has higher *instruction-level success* than A1. Refusals and degradations count as failures; conditional OCR is reported alongside. **H1b:** A2 has a lower false-completion-claim rate (FCR) than A1. **H1c:** each component (manifest, verifier) contributes: A2 > A2−verify and A2 > A2−manifest | The 95% CI of the paired difference A2−A1 in instruction-level success includes 0 or is negative. FCR does not fall. The ablations show no drop |
| RQ2 | What determines wall-clock TVC for a chunked AR world model, and can control policy reduce it? | **H2a:** camera TVC is predicted within ±1 chunk period by the §6.4 model ($A+W+G+\delta+Q+I$, regime U or G), given measured $T$ and queue depths. **H2b:** prompt-driven events have additional visual inertia $I \ge 1$ chunk. **H2c:** bounded look-ahead (≤ 1 chunk) improves TVC deadline success and median over unpaced streaming, at a cost in stall rate that we measure | The model mispredicts the median by more than 1 chunk. Inertia is ≈ 0. Pacing improves neither deadline success nor median |
| RQ3 | Does provenance-typed, scope-separated memory reduce false memories and leakage without hurting recall? | **H3a:** a lower false-user-fact rate than (i) full-history context and (ii) Mem0-style untyped extraction, at non-inferior recall (margin 5 pp). **H3b:** cross-scope leak rate below 1% vs baselines > 0. **H3c:** after deletion, multi-channel leak rate below 5% | The rates are not lower, or recall is inferior beyond the margin |
| RQ4 | Is a world model needed for this experience? This tests the owner's hypothesis in both directions | A0 and A2 share the same LLMs, memory service, TTS and avatar renderer; only the world shot and its controller differ. **H4a:** on scene-grounded tasks (viewpoint, visual recall, events where qualified), A2 beats A0 on task success. **H4b:** on talk-only tasks, A0 is non-inferior to A2 on MOS | H4a: no difference. H4b rejected: A0 worse. Either outcome is informative |
| RQ5 | Does anchoring interaction state to *displayed* frames improve handling of corrections after interruptions? | **H5:** display-aligned context raises referent-resolution accuracy on video-referent corrections ("no, the *other* path") over generation-aligned context | No improvement (CI includes 0) |
| RQ6 | Can the persona remain consistent across shots and over long sessions? | **H6:** persona identity similarity between the presenter and world shots, and over 30 min, stays above a threshold calibrated on the reference image (§8) | Similarity drops below the threshold in more than 20% of windows |

RQ1 and RQ2 are primary; RQ3–RQ6 are secondary. We report all outcomes, including null results.

---

## 5. Candidate architectures and selection

### 5.1 Candidates

Figure: `docs/figures/fig4_candidate_architectures.mmd`.

**Shared substrate.** To avoid confounds (CP3 finding 6), A0, A1 and A2 use the *same* components:
- LLMs;
- ASR, TTS and avatar renderer;
- memory service, except in E3, where memory itself is the factor;
- **generator control substrate**:
  - S-cam: SE(3) camera interactions (class A);
  - S-prompt: mid-session prompts through C1 on the patched vLLM-Omni server, used only once C1 has passed its
    M1 tests.

Without C1, A1 and A2 can change the prompt only by restarting the session, and both pay the same cost for it.

- **A0: no world model (simple baseline).**
  - Pipeline: shared LLM and memory → TTS → audio-driven avatar in front of a static background.
  - Isolates the value of the world shot (RQ4).
  - Avatar candidates: SoulX-FlashHead, Ditto, LivePortrait (single-GPU classes); LiveAvatar for higher quality.
    One is chosen in M1.
- **A1: open-loop direct coupling.**
  - The shared LLM writes free-form camera commands (S-cam) and free-form prompts (S-prompt) straight to the generator.
  - No IR, no manifest, no verification, no narration policy.
  - This is the "LLM connected to a video generator" baseline the brief warns against.
- **A2: capability-grounded closed-loop modular controller (proposed).** Figure 1: `fig1_architecture_A2.mmd`.
- **A3: tightly coupled.** Two routes:
  - (a) fine-tune LingBot-World with audio and behavior-token conditioning. **Needs training.**
  - (b) adopt an existing end-to-end duplex audio-video model (Wan-Streamer-class). This needs **no** training if
    weights are released, but none were located [cited as unreleased/unverified].

  Under H-core, A3 still needs an external memory layer.

**Feasibility alternatives for the world shot.** These are evaluated as fallbacks, not as main arms.

| Alternative | What it buys | Cost / evidence |
|---|---|---|
| SGLang's LingBot-World 2.0 server | Mid-session prompt switching reported [cited: SGLang cookbook] | Different serving stack (8-GPU example); not the required vLLM-Omni integration. Used only if C1 fails, and justified in the decision log |
| vLLM-Omni deprecated tick path | Prompt switching and reset exist [local-code] | Latent output only; deprecated; needs decode and transport glue |
| Clip scheduling: pre-rendered or queued segments, reference-agent style | Robust quality, no real-time need | Large instruction latency (≈15–20 s in the one observed reference sample; single, unaligned) |
| Avatar composited into the world shot | One unified frame | Lighting, perspective and matting artefacts; tested as an ablation |
| A different world backbone for the world shot | May have better controls | Violates the preferred-backbone requirement unless justified. Recorded only as a contingency |

### 5.2 Comparison

All entries are **[estimate]** unless marked otherwise.

| Criterion | A0 | A1 | A2 | A3 |
|---|---|---|---|---|
| Lip-sync / face quality | High (dedicated avatar) | Same avatar on presenter shot; none on world shot | Same as A1 | Unknown; (b) is low resolution: 192p–256² [cited] |
| Scene / camera controllability | None | Camera; prompts only with C1 | Camera + calibrated events | Potentially highest; unproven |
| Observable compliance | n/a (scene) | Unverified | Measured and repaired | Unknown |
| Instruction-to-visual latency | Speech only | Chunk-bound; same substrate | Same substrate, plus backlog control | (b): ≈200 ms model-side claimed [cited] |
| Memory reliability | Shared service | Shared service (in RQ1) | Shared service | Needs an external layer |
| Engineering complexity | Low | Medium | High | (a) very high; (b) medium if weights exist |
| Compute (single user) | 1–2 GPUs | Generator 4 GPUs (if H200-class) + avatar 1 + LLM/ASR/TTS 1 | Same as A1, + monitor ≈ 1 GPU | (a) training cluster |
| Training required | No | No | No (calibration only) | (a) **Yes**; (b) no, if weights are released |
| Demo feasibility (Phase 2) | High | High | Medium–high | Low |

**Selection.** A2 is the proposed system. A0 and A1 are required baselines. A3(a) is a longer-term extension: it is
justified only if S1 shows that affordance limits, not control, dominate compliance failures. The demo needs no
foundation-model training, provided it is limited to the committed camera/viewpoint behaviours and the visible
host. **Reliable character behaviour may require training.** That is an open result of E1.

### 5.3 A2 components and interfaces

**Fast path (critical):**
- Streaming VAD/ASR with barge-in detection.
- A turn and interrupt manager.
- A *responder* LLM: small and fast, streaming, with a short horizon. It produces speech and simple IR actions.
- Streaming TTS.
- The avatar renderer, driven by the TTS audio.

**Deliberative path (asynchronous):**
- A *planner* LLM that maintains a goal stack, decomposes multi-step requests, and consumes monitor feedback.
- Memory retrieval with a latency budget.

**Control layer:**
- **Behavior IR** (below).
- **Capability manifest.**
- **Compiler.**
- **Chunk-boundary scheduler.** It owns `event_id`s, staleness and cancellation.

**Observation layer:**
- The event-ack reader: chunk metadata `started/active/completed_event_ids` [local-code].
- Client presentation timestamps.
- The compliance monitor.

**Memory service:** see §5.6.

#### Behavior IR (intermediate representation)

Each IR item is a record. Fields:

```yaml
id: ir-0193                # unique; becomes the vLLM-Omni event_id when compiled
plan_version: 12           # the planner's goal-stack version when the item was created
track: camera              # speech | shot | camera | scene_event | character_event | memory_op
intent: turn               # closed vocabulary (turn, move, stop, look_at, event:<name>, say, cut_to)
params: {...}              # track-specific; camera contract below
t_start: {anchor: next_boundary}   # or {anchor: speech_segment, id: seg-77, offset_s: 0.0}
deadline_s: 5.0            # measured from receipt of the instruction; after it, the item counts as not complied
priority: user_explicit    # user_explicit > plan_step > idle_behavior
expect: {...}              # observable predicate for the monitor (below)
fallback: [verbal_ack_failure]
provenance: {source_utterance: utt-551, speaker: user}
```

**Camera contract.** This follows the code and API doc: `SE3DeltaCameraHandler`, and
`docs/serving/streaming_video_output_api.md` [local-code, documented].
- **Frame.** LingBot/Unity camera frame: +X right, +Y up, +Z forward.
  - `target` poses are **absolute, relative to the session-start origin**. The handler interpolates from the current
    pose to that pose [local-code: `interaction/modality_handlers/camera.py:44,107,341-352`].
  - `velocity` is a per-frame SE(3) delta.
- **Units.** Translation in the model's native pose units, *not* metres; the key script moves 0.05 per latent
  frame [local-code: `actions.py:275-339`]. Rotation as a unit quaternion `[qx,qy,qz,qw]`.
- **`velocity` mode.** Held *until replaced* [local-code]. The API has no duration field, so a finite motion is
  compiled as two events: a velocity event, then a zero-velocity "stop" event aimed at the boundary after the intended
  number of chunks.
- **`target` mode.** Interpolated over `transition_chunks`. It snaps to the target and clears when the transition ends.
- **IR semantics are relative; the wire format is absolute.** The IR's `turn {yaw_deg: -60}` means "relative to the
  pose at application time". The compiler keeps a **pose estimate** $\hat{x}$, integrated from the session origin and
  every acknowledged event, and emits the absolute target $\hat{x}\cdot R_y(-60°)$ with
  `transition_chunks = ceil(|yaw| / yaw_rate_per_chunk)`. `yaw_rate_per_chunk` comes from the manifest (E1).
  $\hat{x}$ may drift from the handler's internal pose. The handler's committed pose is not echoed in the chunk
  metadata, so exposing it is added to extension C3.

**Supersession.** An event already sent cannot be withdrawn from the server queue; the API has no removal. A
newer event on the same track is sent instead. For `velocity`, the newest event holds from its application frame
onward. Events that arrive within the same chunk map to latent frames by arrival time [local-code: `types.py:108-129`,
per the audit]. For `target`, a new target replaces the interpolation from the current pose.

**Golden example: correction and stop.** Ids are illustrative. The current pose is taken to be the identity
(session origin), so absolute and relative targets coincide here.

| t (s) | Event | IR | WS message(s) |
|---|---|---|---|
| 0.00 | User: "look left" | `ir-1 turn yaw −60°, deadline 5 s` | `{"type":"session.interaction","interaction":{"event_id":"ir-1","event":{"multi_modal_data":{"camera":{"mode":"target","data":{"translation":[0,0,0],"rotation":[0,-0.5,0,0.866]}}}},"transition_chunks":2}}` |
| 0.9 | Chunk k metadata `started_event_ids:["ir-1"]` | ir-1 applied; **not yet complied** | – |
| 1.4 | User: "no, the other way!" (barge-in) | plan_version 13; `ir-2 turn to yaw +60°` (absolute), supersedes ir-1 | same shape, rotation `[0,0.5,0,0.866]`, `transition_chunks:3`. The handler interpolates from wherever ir-1 left the pose |
| 2.1 | Chunk k+1 still shows the ir-1 motion (in flight) | monitor: ir-1 superseded, its expectation dropped | – |
| 2.9 | Chunk k+2 `started_event_ids:["ir-2"]`; monitor sees positive yaw on displayed frames | ir-2 complied at TVC measured from t=1.4 | – |
| 3.5 | User: "stop" | `ir-3 stop` | `{"camera":{"mode":"velocity","data":{"translation":[0,0,0],"rotation":[0,0,0,1]}}}` |

**Cancellation rule.** This single rule replaces the earlier inconsistent wording in Figure 2.
- On a new `plan_version`, *unsent* items of older versions are dropped.
- *Sent* items can only be superseded by newer events.
- Their expectations are removed from the monitor.

#### Capability manifest

For every control $c$ the backbone might execute, the manifest records the following. Examples of controls:
- camera turn / move / stop;
- scene prompt "it starts to snow" (C1 only);
- character prompt "the host waves" (C1 only).

| Field | Meaning | Source |
|---|---|---|
| `status` | documented / code-read / executed-M0 / calibrated-E1, plus class A–D | backbone_verification.md, M0, E1 |
| `interface` | exact WS payload template | local-code |
| `p_success` (+CI) | fraction judged compliant within the deadline | E1 |
| `tvc_quantiles` | time to visible compliance, restricted mean, censoring rate | E1 |
| `side_effects` | identity drift, scene reset, artefacts | E1 |
| `preconditions` | e.g. world shot active, persona visible | design |

**Compiler rules:**
- (i) reject any item whose `status` is below `executed-M0`;
- (ii) if `p_success` < θ, pick an equivalent with higher success, or a verbal alternative;
- (iii) if the predicted deadline-success probability is too low, tell the user it will take a moment, or degrade;
- (iv) map timing onto the next chunk boundary;
- (v) emit WS messages with `event_id = IR id`.

Every rejection or degradation is logged. It counts **against** instruction-level success (§8).

#### Compliance monitor

**Inputs.** The monitor runs only on **displayed** frames, identified by client presentation timestamps (C4).

**Camera items.**
- Rotation is estimated between displayed frames from robust homography/essential-matrix fits on sparse features.
- Only the *direction* of translation is estimated. Monocular geometry does not recover scale.
- The monitor **abstains** (`unknown`) when inlier ratio or texture is too low, or when independently moving content
  dominates.
- The error rate is measured offline against RotErr/TransErr-style references [cited: he2024cameractrl] and against
  human labels.

**Scene and character items (C1 only).**
- A VLM judge, from the StreamingVLM or Qwen-VL class, answers a yes/no question about K = 4 frames sampled uniformly
  from each displayed chunk after the item was applied.
- It may abstain.
- The *verdict latency* (frames presented → verdict) is measured. Throughput figures such as StreamingVLM's ≈8 FPS
  on 1×H100 [cited] do not bound verdict latency.

**Identity.** Embedding similarity to the persona reference, per shot.

**Verdicts and repair.**
- Each item gets `complied`, `not_complied` or `unknown` within a *verdict deadline*: the item deadline minus the
  predicted repair TVC.
- An item is *repair-eligible* only if its verdict arrives before that point. We report the fraction of failures that
  were repairable in time.
- Verdicts feed the planner. The manifest is re-estimated only from calibration data, never from evaluation runs.

**Narration policy.**
- *Intentions* ("turning left") may be spoken immediately.
- *Completions* ("we're at the lake") may be spoken only after a `complied` verdict.

This targets FCR (H1b).

### 5.4 Critical path vs asynchronous work

| Operation | Path | Notes |
|---|---|---|
| VAD, endpointing, barge-in | **critical** | ≤ 300 ms endpoint target |
| Responder first token → TTS first packet → audio out | **critical** (speech) | Speech is never blocked on video |
| Avatar rendering from TTS audio | **critical** (presenter shot) | Adds avatar latency ahead of audio playback (sync, §5.5) |
| Compile + WS send of a camera or event item | **critical** (visual) | ≈ tens of ms [estimate] |
| Wait for chunk boundary, generation, mux, transport | **critical** (visual) | Set by the backbone; no control inside a chunk |
| Planner reasoning, multi-step decomposition | async | Results arrive as new IR versions |
| Memory retrieval | async with budget | A profile preloaded at session start is on the critical path at ≈0 ms. Deep retrieval runs async with a timeout |
| Memory writes (episodic append) | sync but cheap | Append-only log |
| Extraction and consolidation | async (sleep-time) | LightMem-style [cited] |
| Compliance monitor | async with deadline | Feeds repair; its judgments never gate speech |

### 5.5 Interruptions, stale plans, buffering and synchronization

**Barge-in.**
- Stop TTS and avatar output immediately [target ≤ 200 ms].
- Cancel all IR items with `plan_version` below the new version that have not yet been sent.
- Items already sent cannot be recalled; the scheduler sends *superseding* controls instead:
  - camera `velocity` → zero or the new velocity;
  - a `target` pose, which lerps over `transition_chunks` [local-code: camera handler].
- The chunk already in flight will still render the old intent. The responder may acknowledge this
  ("turning — one moment").

**Stale plans.** Every IR item carries `plan_version`. The scheduler drops superseded items at compile time. The
monitor ignores the expectations of superseded items.

**Backlog and buffering (engineering I2, C4).**
- The WS server sends every chunk as soon as it is produced; there is no playback timer
  [local-code: `serving_video_output_stream.py:148-155`].
- `session.ping` only refreshes the stall clock (`:17,79-88,311`). It is **not** a flow-control mechanism.
- If generation period $T$ < playback period $P = 12/\text{fps}$, the client backlog grows by $P - T$ per chunk.
  With $T = 0.549$ s [cited upstream] and 16 fps ($P = 0.75$ s) that is ≈0.20 s per chunk [derived], so a bounded
  backlog **requires** an effective gate.
- Whether WebSocket/TCP backpressure from a slow reader pauses the engine is **unverified**. It is an M0 check that
  compares generated, received, decoded and presented queue depths.
- Candidate mechanisms, in order of preference:
  1. **Server gate (C4):** the stepwise runner waits before starting AR block $n+L+1$ until the client acknowledges
     presentation of chunk $n$. This needs a change in the engine or runner loop, and its feasibility is to be
     established in M1.
  2. **Client skip-to-latest:** drop the undisplayed backlog when an instruction arrives. It is responsive, but the
     skipped content causes a visible jump.
  3. **Playback-rate adaptation:** a slight speed-up (≤ 1.1×) to drain the backlog.
- If $T > P$, the stream stalls. Mitigations: lower fps (12 fps gives $P = 1.0$ s), a cut to the presenter shot, or
  more GPUs. M0 determines the regime.

**Display-aligned state (RQ5).**
- The context seen by the responder and planner records which chunks were *presented* (from client timestamps),
  not which were generated.
- Corrections such as "no, the other one" are resolved against displayed content.

**Audio/video synchronization: a shared presentation timeline.**
- One client-side clock timestamps every presented TTS audio packet, avatar frame, world chunk and shot cut. All
  latency metrics are computed from this timeline.
- Audio is the master clock.
- **Presenter shot.** The avatar is driven by the TTS audio. Audio playback is delayed by the avatar pipeline latency
  $d_\text{av}$, so lip-sync stays within tolerance: EBU R37 gives +40/−60 ms end-to-end, and ITU-R BT.1359 gives
  detectability at +45/−125 ms [cited].
  - $d_\text{av}$ is **on the critical path** for first speech.
  - Mitigation: start each response on the currently displayed shot. If the world shot is on screen, audio can start
    without waiting for $d_\text{av}$, and the cut to the presenter happens once avatar frames are ready.
- **World shot.** There are no lips to sync.
  - An event ack shows only that a chunk was *generated* with the event. Narration about an action is aligned to the
    *presentation* time of that chunk, not to the ack.
  - Completion statements wait for a monitor verdict (the narration policy).
- **Cuts** happen at world-chunk presentation boundaries. The world stream keeps generating during presenter shots,
  so the generator's cost is paid continuously.

### 5.6 Long-term memory design

Figure 3: `docs/figures/fig3_memory_lifecycle.mmd`.

**Five distinct kinds of state (required separation).**

| Kind | Substrate | Lifetime | Writes | Reads | Not to be confused with |
|---|---|---|---|---|---|
| Working context | responder/planner prompt; recent turns; displayed-state summary | one session | every turn | every turn | long-term memory |
| Persistent user facts & preferences | semantic store: `(subject, predicate, value, provenance, valid_from, valid_to, scope, confidence, derived_from)` | cross-session | consolidation of *user-asserted* statements; explicit user confirmations | preloaded profile + retrieval | agent-inferred beliefs |
| Episodic history | append-only log of turns, instructions and outcomes, with timestamps and speakers | cross-session (retention policy) | synchronous append | retrieval by time, entity, similarity | summaries (derived) |
| Visual / world-state continuity | records of reference frames (last displayed world frame, persona reference), scene prompt, camera pose | cross-session | on session end and on user request ("remember this place") | when a new world session starts: `image_reference` = the stored frame [local-code: image-conditioned start] | generator KV |
| Model inference caches | LingBot paged KV (sink + window), text K/V, LLM KV cache | one generator/LLM session | automatic | automatic | **any** long-term memory |

**Write policy.**

*Claim typing.* Fact extraction reads only user-speaker turns, and it first classifies the **claim type** of each
statement:
- the user's own assertion ("my sister lives in Paris");
- a quotation of, or claim about, what the persona said ("you told me my sister lives in Paris");
- a question;
- a hypothetical or joke.

Only own assertions become candidate facts directly.

*Echo lineage.* Every candidate fact is compared, semantically, with the **generated-event log**, which holds
everything the persona said or showed.
- If the candidate matches earlier persona output, it is tagged `echo`. The user may be repeating a persona
  invention, so an echo needs explicit confirmation ("Just to check — is that something you're telling me about
  yourself?") before promotion.
- When the persona paraphrases a genuine user fact, the paraphrase is stored in the generated-event log with
  `derived_from` → the user's original. A later echo of it therefore resolves to the original and is not a new fact.

*Other sources.*
- The persona's own utterances and rendered events go only to the generated-event log (`speaker=persona`). They are
  never promoted to user facts.
- Agent inferences ("the user seems to like jazz") become *candidate beliefs*. They are used only as hedged
  suggestions until the user confirms them.
- Viewer chat in Mode 2 is written only to the public scope. It is rate-limited, sanitized and tagged `viewer-claimed`.

*Probes.* Both failure cases, a user repeating a persona invention and a persona paraphrasing a user fact, are
explicit probes in E3.

**Scope tags on derived artifacts.** Every artifact carries `source_scopes`, the union of the scopes of everything it
was derived from. This covers:
- summaries;
- persona utterances;
- visual-state frames;
- reference images;
- cached prompts.

Rules:
- A Mode 2 process may load only artifacts whose `source_scopes` ⊆ {public, canon}.
- The persona's utterances in a private session are **private-scoped**, so the "persona's public history" contains
  only what it said in public.
- A world frame captured in a private session is private. **A public world session may start only from a canon or
  public-derived frame.**

E3 includes a test that starts a fresh public session immediately after a private one.

**Retrieval.**
1. Filter on `source_scopes` first, before any relevance scoring:
   - Mode 1 reads private:user ∪ public ∪ canon;
   - Mode 2 reads public ∪ canon.
2. Rank by relevance, recency and importance [cited: park2023generativeagents].
3. Every injected memory carries its provenance and claim-type tags, so the LLM can hedge.
4. A session-start profile preload keeps the critical path at ≈ 0 ms. Deeper retrieval runs asynchronously with a
   timeout.

**Consolidation.** Runs asynchronously at "sleep time": session end, idle periods [cited: fang2025lightmem]. It
summarizes episodes, merges duplicates, and records `derived_from` links.

**Correction.**
- User-asserted facts use a bi-temporal update [cited: rasmussen2025zep]: the old value gets `valid_to=now` and is kept
  for audit.
- The correction also **invalidates every artifact derived from the old value**, followed through `derived_from`:
  summaries are regenerated; visual references and cached prompts are flushed.
- An agent-inferred belief never overrides a user-asserted fact.

**Deletion (erasure) semantics.**
- The episodic log is *append-only for normal operation*. Erasure is the one exception, and it **physically deletes**
  records. There is no soft delete for erasure.
- The erasure cascade covers:
  - (i) the fact and every episodic record that mentions it, plus their embeddings and index entries;
  - (ii) derived summaries, which are regenerated without the fact;
  - (iii) visual-state frames and reference images that depict it;
  - (iv) cached prompts and LLM KV, flushed by restarting the LLM session;
  - (v) in-flight IR items and queued prompts that reference it, which are cancelled;
  - (vi) private recordings of rendered media.
- A **tombstone ledger** keeps only (hashed id, timestamp, reason code), without the content, so that the deletion can
  be audited.
- Backups follow a bounded-retention policy (for example ≤ 7 days [target]), and erasure is re-applied on restore.
- Media already broadcast in Mode 2 cannot be recalled. This limitation is stated to users.
- **Verification:** after the cascade, a cache flush and a session restart, we query every store and probe every
  output channel (§7.3).

**Conflict resolution.** The order is: user-asserted (latest valid) > system-observed > agent-inferred >
viewer-claimed. `echo` facts do not count as user-asserted until confirmed. Conflicts between user-asserted facts are
raised to the user for confirmation.

**Provenance.** Every record keeps its source utterance or frame id, speaker, session, timestamp and extraction
model version.

**Public/private separation.** There are three physically separate stores: private per user, public per stream,
and canon.
- Mode 2 processes have no read credentials for private stores.
- `source_scopes` rules apply to every derived artifact, including media.
- Leak probes (§7.3) test the separation across speech, on-screen text and generated visuals, including a fresh
  public session started right after a private one.

### 5.7 Interaction sequence

Figure 2 (`fig2_sequence_interrupt.mmd`) walks through an instruction, a barge-in correction, superseding camera
control, event acknowledgement from chunk metadata, monitor verification, and the episodic write of the outcome.

---

## 6. Verified vLLM-Omni integration plan

Source: `docs/backbone_verification.md` (a code-level audit with path:line evidence and independent spot-checks).
Classes:
- **A**: in the inspected code.
- **B**: reported upstream, not verified.
- **C**: engineering extension.
- **D**: needs training or research.

### 6.1 What the backbone provides (A)

Evidence status is kept distinct for every item: **documented** (API/recipe docs), **code-read** (inspected source)
or **executed** (none yet). M0 includes a minimal **WS contract test** that exercises each item below once:
- `session.start` with `image_reference`;
- camera `target` and `velocity`;
- `transition_chunks`;
- the event-ack fields;
- `session.stop`;
- a `num_frames` that is not of the form 9+12k, which should be rejected;
- a prompt interaction, expected to fail.

Items then move to **executed**.

**Model and hardware.**
- Model: `robbyant/lingbot-world-v2-14b-causal-fast-diffusers`, pipeline `LingBotWorldCausalDMDPipeline`.
- 4 DMD steps. Resolution at most 480×832, fixed at load time.
- Weights are present locally in the shared `/data/models/hub`. Permission to use them is still to be confirmed.

**Serving.**
- `vllm serve … --omni --deploy-config vllm_omni/deploy/lingbot_world_v2_stepwise.yaml`.
- Endpoint `WS /v1/realtime/video`.
- `session.start` carries prompt, `image_reference`, `num_frames` and `extra_params`.
- Chunks arrive as `video.chunk_metadata` followed by a binary fMP4 chunk.

**Mid-session control.** `session.interaction` with `event.multi_modal_data.camera` in `target` or `velocity` mode,
applied at the next chunk boundary. The camera handler is `SE3DeltaCameraHandler`.

**Event acknowledgement.** Chunk metadata carries `started/active/completed_event_ids`.

**Lifecycle.**
- Cancel with `session.stop` or disconnect.
- Stall timeout 60 s; start timeout 10 s.

**Limits.**
- `max_num_seqs=1`, a single replica, at most 2 resident sessions.
- Session length fixed by `num_frames` at start: `9 + 12k` frames.

### 6.2 Reported upstream only (B)

- **Speed.** ≈549 ms/chunk and TTFC ≈1.07 s on 4×H200 with the PR #7749 stack; ≈892–896 ms on 2×H200; ≈3.24 s on
  1 GPU eager.
- **Paper claims.** 720p@60 fps and an hour-level horizon.
- **Character actions via chunk-wise prompts.**
- **Hardware identity.** An upstream author's statement that "L20X" is a mislabelled H200. Our `nvidia-smi` shows
  Ada / CC 8.9 / 143,771 MiB / 700 W, so the question is unresolved.

### 6.3 Engineering extensions needed (C)

| ID | Extension | Why | Size [estimate] / what makes it hard |
|---|---|---|---|
| C1 | Mid-session prompt on the stepwise path. (i) Register a prompt handler for LingBot. (ii) At the chunk boundary, encode the new prompt (UMT5, with an LRU cache) and store it in session state. (iii) Rebuild the cross-attention text K/V on every SP/TP rank; with Ulysses, text K/V is head-sharded. (iv) Define the transition: hard switch at the boundary, or a LongLive-style KV re-cache [cited: yang2025longlive]. The stepwise path currently calls `_ar_text_caches(..., invalidate=False)` (`pipeline.py:1935,2053-2056`). The tick path shows that invalidation works *there* (`pipeline.py:1437-1463`, per the audit); that it is safe for stepwise is **unverified** | Scene and character events | medium. Tests: the visual change is judged by a VLM; camera interaction is unaffected; parity on ranks 1/2/4 |
| C2 | WS `session.reset` / `session.extend`. Session length is fixed by `num_frames` at start, and state (sink KV, decoder) is sized then | Open-ended sessions | medium–large. Until it exists, sessions are started long enough, and rotated |
| C3 | Server-side monotonic timestamps and the handler's committed camera pose in chunk metadata | TVC decomposition; compiler pose tracking | small |
| C4 | Client presentation acks plus a server generation gate (bounded look-ahead $L$) | Backlog control, display alignment | medium–large. It changes the runner loop; feasibility is established in M1 |
| C5 | Restart from a stored frame (`image_reference` = last displayed frame). The KV and decoder state are **not** preserved | Cross-session visual continuity | small to build. **There will be a visible seam**, which is measured and not hidden |
| C6 | External avatar path, shot switcher, shared presentation timeline | Visible speaking persona | medium |

### 6.4 Latency model

This model is **[derived]**. Numbers are **illustrative, not predictions**. M0 measures the joint timestamp
distribution, and a simulation from those measurements replaces this table.

For a camera instruction whose end-of-utterance is at $t_0$:

$$\text{TVC} = A + W + G + \delta + Q + I$$

| Term | Meaning |
|---|---|
| $A$ | ASR endpoint + IR emission + compile/send |
| $W$ | wait until the next generation start that can include the event |
| $G$ | generation time of that chunk |
| $\delta$ | mux + network |
| $Q$ | time the chunk waits at the client behind already-generated, undisplayed chunks |
| $I$ | visual inertia: presented frames until the effect becomes judgeable |

Judge detection delay is excluded, because the judge localizes the onset frame.

**Regime U (unpaced, $T < P$).**
- $W \sim U(0, T)$ and $G = T$.
- $Q$ **grows without bound** at $(P - T)$ per chunk: ≈0.20 s per chunk for $T = 0.549$ s at 16 fps.
- TVC therefore increases over the session. This is the failure mode that C4 addresses.

**Regime G (gated with look-ahead $L$, $T + \delta \le P$).**
- Generation of chunk $n+L+1$ starts when chunk $n$ is presented.
- An event waits for the next generation start: $W \approx U(0, P)$.
- The chunk it lands in is presented about $L \cdot P$ after generation starts (the generation time is hidden behind
  playback when $T + \delta \le P$).
- So TVC ≈ $A + U(0, P) + L \cdot P + I$.

**Illustrative values in regime G** (4-GPU, upstream-reproduced $T = 0.549$ s, 16 fps, $L = 1$):

| Term | Median-ish | Upper-ish | Basis |
|---|---|---|---|
| $A$ | 0.45 s | 0.8 s | [target]; endpointing 200–300 ms [cited: pipecat2026primer] |
| $W$ | 0.375 s | 0.71 s | $U(0, 0.75)$ [derived] |
| $L \cdot P$ | 0.75 s | 0.75 s | [derived] |
| $I$ (camera) | 0.1 s | 0.4 s | [estimate]; measured in E1 |
| **Camera TVC** | **≈1.7 s** | **≈2.7 s** | Column sums, **not quantiles**. Illustrative only |

**2×H200-class** ($T \approx 0.89$ s [cited]):
- At 16 fps, $T > P = 0.75$ s, so the stream stalls.
- At 12 fps ($P = 1.0$ s): TVC ≈ $A + U(0, 1.0) + 1.0 + I$, i.e. ≈2.0 s median-ish, with the same caveats.

**1 GPU** ($T \approx 3.24$ s [cited]): no real-time world shot. Use the presenter shot plus pre-rolled world clips.

**Speech path (first audible response), from the shared timeline.**
- **Starting on the world shot:** endpoint 250 ms + responder TTFT 300 ms + TTS first packet 150 ms + network 50 ms
  ≈ **0.75 s** [target].
- **Starting on the presenter shot:** add $d_\text{av}$. With $d_\text{av} = 0.3$ s [target], that is ≈ **1.05 s**.
- Both are reported separately.

### 6.5 Capabilities that need new training or research (D)

- Native LingBot lip, face and audio conditioning.
- Reliable character-behavior control beyond what prompts provide.
- Memory beyond the sink and window inside the generator.
- Rewinding or snapshotting generator state: "C/D, feasibility unknown". It requires snapshotting the paged KV
  together with the encoder and decoder state.

None of these is required for the first demo.

---

## 7. Experimental design

All experiments hold these fixed across conditions unless the factor itself is under test:
- the backbone checkpoint (fixed snapshot `59cccf49…`);
- GPU type and count;
- 480×832 resolution and playback fps;
- LLM, ASR and TTS models and versions;
- seeds;
- scripted workloads.

Each run logs:
- all wall-clock timestamps (C3/C4);
- the WS event stream;
- displayed-frame hashes;
- IR items and verdicts.

### 7.0 M0: backbone and hardware characterization (gate)

**Procedure.**
- Under `gpu run --gpus {1,2,4} --timeout 2h --note "live-agent M0"`, serve the stepwise deploy config and run
  `benchmarks/lingbot_world/benchmark_lingbot_world_realtime.py`: 3 warm sessions × 40 chunks per configuration.
- Record `torch.cuda.get_device_capability()` and the attention backend.
- Run the WS contract test (§6.1). It includes one `session.interaction` with `event.prompt`, which settles the
  contradiction between the registry and the benchmark code.
- Measure generated, received, decoded and presented queue depths without pacing. Check whether transport
  backpressure pauses the engine.

**Outputs.**
- Cadence $T$ and TTFC, as p50/p95 with bootstrap CIs.
- Stall regime.
- Observed prompt-interaction behavior.

**Go/no-go rule.** Proceed to real-time world-shot experiments only in configurations where $T \le P$ at the chosen
fps. Otherwise report the regime and use the fallback designs of §6.4.

### 7.1 E1: capability calibration (builds the manifest; RQ2)

**Controls.**
- 8 camera primitives: forward, back, strafe, yaw ±, pitch ±, stop.
- 12 scene-event prompts, after C1.
- 8 character-event prompts, after C1.

**Scenes.** 5 scenes, each with the persona reference.

**Trials.** 30 trials per control × scene, with randomized issue time within a chunk. That is ≈ 4,200 trials if all 28 controls qualify. At about 5 s of generated video each, that is ≈ 6 h of 4-GPU generation, plus judge time [estimate].

**Labels.**
- Camera: the geometric estimator.
- Events: the VLM judge, plus blinded human labels on a 20% stratified sample.

**Outputs.**
- $p_\text{success}$ with Wilson CIs.
- TVC distribution, with Kaplan–Meier curves for censored non-compliance.
- Side effects: identity similarity drop, scene reset.

**Analysis.** Test H2a with a TVC model fit and H2b with inertia estimates. Calibration data and evaluation data are
**disjoint**: separate scenes and seeds.

### 7.2 E2: instruction following, multi-step tasks and interruptions (RQ1, RQ2c, RQ5)

**Task suite.** 60 scripted tasks, each spoken by a TTS-simulated user from a fixed script, for reproducibility.
- 20 single-step instructions.
- 20 multi-step instructions, for example "turn toward the lake, move forward, then stop and look left".
- The single-step and multi-step sets together are split into a **committed subset** (camera/viewpoint and shot
  cuts: 30 tasks) and a **conditional subset** (scene and character events: 10 tasks). The conditional subset runs
  only if C1 and E1 qualify, and it is always analysed separately.
- 20 interaction-dynamics tasks: a mid-execution correction, a goal change, a barge-in during speech, or a referent
  correction against displayed content (RQ5).

Task templates are adapted from EchoChain, Full-Duplex-Bench v2 and WBench [cited].

**Conditions.**
- A1: prompt-only open loop.
- A2−verify: capability-aware open loop.
- A2−manifest: a verifier with an uncalibrated, "everything allowed" manifest.
- A2: full system.
- A2+unpaced: no look-ahead bound (RQ2c).
- A2−display-alignment: context aligned to generation (RQ5).

**Metrics.**
- **Instruction-level success.** The denominator is *all* instructions, and refusals and degradations count as
  failures.
- **Refusal/degradation rate.**
- **OCR (conditional).** Among instructions that were executed, the fraction judged compliant within the deadline
  $D$ on displayed frames.
- Task success for multi-step tasks: all steps compliant, in order.
- FCR: the persona claimed completion, but the judge says not complied.
- TVC: deadline success, Kaplan–Meier median, and p95 only when identifiable (§8).
- Recovery time after a correction.
- Referent-resolution accuracy.

**Design and analysis.**
- Within-task paired design: each task × 5 seeds × each condition, giving 300 paired trials per condition.
- Mixed-effects logistic regression: condition as a fixed effect; task and seed as random effects.
- Paired bootstrap 95% CIs for differences.
- Holm correction across the primary contrasts (A2 vs A1 on instruction-level success and on FCR).

**Power [estimate].** Consider a true instruction-level success of 60% vs 75% with ≈ 20% discordant pairs. McNemar's test on 300 pairs then
has power > 0.9 at α = 0.05. We will re-estimate after a 60-trial pilot.

### 7.3 E3: memory (RQ3)

**(a) Component benchmarks.**
- LongMemEval_S: extraction, temporal reasoning, knowledge update, abstention.
- MemoryAgentBench, selective-forgetting split.
- A small GateMem-style scoping suite.

All are run on the memory service with a fixed LLM [cited benchmarks].

**(b) Live-persona memory protocol (new).**
- 20 simulated users × 6 sessions each, with scripted life facts, preferences, corrections and erasure requests.
- Persona-generated distractors: for example, the persona says "I love snow", which must not become a user fact.
- **Echo probes:**
  - the user repeats a persona invention as if it were about themselves;
  - the persona paraphrases a real user fact, and the user later refers back to it.
- **Fresh-public-session probe:** a Mode 2 session starts immediately after a private session.
- Mode 2 sessions with 10 scripted viewers. 3 of them attempt MINJA-style poisoning and private-fact elicitation.
- **Probes** after each session:
  - recall questions;
  - post-correction questions;
  - post-deletion questions;
  - **multi-channel leak probes**:
    - the speech transcript (ASR);
    - on-screen text (OCR of the displayed stream);
    - generated visuals, through a VLM check for depicted deleted items (e.g., "the red scarf").

**Conditions.**
- Full-history context (no memory service).
- Mem0-style untyped extraction [cited].
- The A2 memory without provenance typing.
- The A2 memory without scope separation.
- The full A2 memory.

**Metrics.**
- Recall accuracy.
- Precision / false-user-fact rate. This includes generated-event contamination: a persona utterance stored as a user
  fact.
- Correction propagation rate.
- Post-deletion leak rate per channel.
- Cross-scope leak rate.
- Poisoning success rate.
- Time-to-availability of a new memory.

**Analysis.** Per-user clustered bootstrap CIs. Non-inferiority test on recall with a 5 pp margin.

### 7.4 E4: long-horizon consistency and the H-core test (RQ6, H-core)

**Long sessions.** 10 sessions of 30 min each, in Mode 1 with scripted interaction.

**Metrics.**
- Persona identity similarity:
  - presenter shot: a face embedding (ArcFace [cited]) against the reference image;
  - world shot: a person re-identification embedding, because faces may not be visible;
  - cross-shot similarity.
- Persona text consistency: DNLI/PICon-style contradiction probes [cited].
- Stream stability: stall rate, seam artefacts at chunk boundaries (the stateful streaming decoder is noted as partial
  in the recipe), and session-restart seams (C5).

**H-core test.**
- A2 and **A1−mem** run through ≥ 3 sessions separated by restarts. A1−mem is A1 without the memory service: dialogue history only, in context, carried across restarts only as far as the context window allows. It is the "no external layer" variant.
- The same planted facts, corrections, deletions and visual-recall requests are used for both.
- If an end-to-end system (A3b-class) becomes available with weights, it is run in the same protocol.
- H-core is refuted for a system if it meets the §8 memory and compliance thresholds without an external layer.

### 7.5 E5: human evaluation (RQ4 and UX)

**Design.** Within-subject, counterbalanced. Pilot N = 12, then a main study with N = 24 if the pilot supports it
[estimate]. Conditions: A0, A1 and A2, with 15-min sessions per condition.

**Measures.**
- MOS for overall quality.
- SUS.
- Godspeed (anthropomorphism, likeability, perceived intelligence).
- Social presence.
- Perceived responsiveness.
- Task success on 5 scene-grounded and 5 talk-only tasks (RQ4).

**Analysis.** Mixed models; Wilcoxon signed-rank for Likert items. We report effect sizes with CIs.

**Governance.** Pre-registration before the main study [cited: nosek2018preregistration]. Informed consent. No
public broadcast.

### 7.6 E6: private livestream (Mode 2)

A closed test stream with scripted viewers, run for 2 h × 3 runs. Metrics:
- chat-response latency;
- instruction success on voted actions;
- poisoning and leak rates;
- stalls.

### 7.7 Reference agent

`twitch.tv/sylar_nv` is used as a **qualitative reference only**.

A quantitative comparison happens only if all of the following hold:
- VODs are archived;
- chat and video time are aligned;
- a scripted prompt set is sent from a test account;
- the operator consents.

If these hold, we apply the same black-box metrics to both systems: onset latency, instruction success, lip-sync,
identity drift and memory probes. We will state explicitly that the two systems differ in backbone and hardware and
are **not controlled**.

### 7.8 Uncertainty reporting (all experiments)

- Every metric is reported with a 95% CI: bootstrap, clustered by task, user or session.
- Compliance is always reported next to coverage: instruction-level success, refusal/degradation rate and conditional
  OCR. This way, declining hard instructions cannot inflate the results.
- Latency distributions are reported as p50/p95/p99 with ≥ 3 repeated runs per configuration.
- Censored TVC is analysed with survival curves.
- We report judge–human agreement (Cohen's κ) and judge runtime cost.
- All raw logs are released internally. No cherry-picking: every scripted task is reported.

---

## 8. Metrics and success criteria

All thresholds below are **[target]**. They are provisional until M0 and the E2 pilot.

| Metric | Definition | Success criterion |
|---|---|---|
| Instruction-level success (primary for H1a) | All instructions in the denominator. Refusals and degradations count as failures | A2 − A1 ≥ +10 pp, with the paired CI excluding 0 |
| OCR (conditional) | Among executed instructions, judged compliant on displayed frames within $D$ ($D$ = 5 s camera, 8 s events) | Reported with the refusal/degradation rate. Not used alone |
| FCR | Completion claims contradicted by the judge | A2 ≤ 5% and below A1, CI excluding 0 (H1b) |
| Multi-step task success | All steps compliant, in order | Reported; A2 > A1 |
| TVC (camera) | Wall-clock from instruction end-of-utterance to first judged-compliant *displayed* frame; failures censored | Deadline success ≥ 90% within 3.5 s. Median ≤ 2.0 s (Kaplan–Meier). An unconditional p95 is reported only if censoring ≤ 5%; otherwise the restricted mean time is reported |
| TVC (events, post-C1) | Same, for scene/character events | Deadline success within 8 s and median reported. Targets are set after E1 |
| Time to first speech | End of user utterance → first audible persona audio, on the shared presentation timeline | World-shot start: p50 ≤ 0.8 s, p95 ≤ 1.5 s. Presenter-shot start: p50 ≤ 1.1 s, p95 ≤ 1.8 s |
| Barge-in stop | User speech onset → persona audio stops | p95 ≤ 250 ms |
| Recovery after correction | Correction utterance → first compliant frame of the corrected intent | p50 ≤ TVC p50 + 1 chunk |
| Memory recall | Correct answers on planted-fact probes | Non-inferior to the best baseline (margin 5 pp) |
| False-user-fact rate | Stored or asserted user facts not stated by the user | ≤ 2% and below baselines |
| Post-deletion leak | Any channel reveals a deleted item | ≤ 5% (vs K-Bench-style baselines) |
| Cross-scope leak | Private item surfaces in Mode 2, or across users | < 1% (ideally 0 observed; report the upper CI) |
| Identity consistency | Embedding similarity to the reference (per shot, per 30 s window) | Above the threshold τ. τ is set as the 5th percentile of same-persona reference augmentations; ≥ 80% of windows pass |
| Lip-sync (presenter) | LSE-C / LSE-D (SyncNet) [cited]; A/V offset | Within ±45 ms offset; LSE comparable to the avatar model's published range |
| Stream stability | Stalls per 10 min; seam artefacts | ≤ 1 stall / 10 min on the qualified configuration |
| Judge validity | κ between VLM or geometric judge and blinded humans | κ ≥ 0.6. Otherwise human labels are primary |
| Compute | GPU-seconds per session-minute, per component | Reported (no threshold) |

---

## 9. Milestones, resources and feasibility risks

### 9.1 Milestones

Durations are **[estimate]**.

| Milestone | Content | Exit criterion |
|---|---|---|
| **M0** (≈1 week) | Hardware and backbone characterization (§7.0); weight-use permission; environment build | Measured $T$, TTFC and regime; prompt-interaction behavior observed |
| **M1** (≈3 weeks) | C1–C4 extensions (upstream-able where possible); avatar model bake-off (license, latency, identity); E1 calibration | Manifest v1 with CIs; judge validated (κ) |
| **M2** (≈3 weeks) | A0, A1, A2 controllers; memory service; voice pipeline; dual-shot renderer (C5, C6) | End-to-end Mode 1 demo on a scripted task |
| **M3** (≈3 weeks) | E2, E3, E4 | Primary RQ1/RQ2 results with CIs |
| **M4** (≈2 weeks) | E5 pilot, E6 private livestream, write-up | Proposal claims confirmed or refuted; report |

### 9.2 Resources

**GPUs.** All through `gpu` (canhazgpu) reservations with timeouts.
- Generator: 4 GPUs, if the local cards are H200-class (M0).
- Avatar: 1 GPU.
- LLM, ASR, TTS and monitor: 1–2 GPUs.

Total: about 6–7 of the 8 shared GPUs for one live session. This is an **optimistic reservation estimate** [estimate]:
- the world stream keeps generating during presenter shots;
- the monitor runs concurrently;
- the other users of the machine compete for the same GPUs.

**Availability is not guaranteed.** Live sessions and E2/E4 runs book scheduled slots for the full machine
(`gpu reserve --start … --end …`).

**Models.**
- LLMs: open-weight instruct models served locally. This keeps personal memory on premises. API models may be used
  only for ablations with synthetic data.
- ASR and TTS: open streaming models, e.g. the CosyVoice class [cited]. To be selected in M1.
- Avatar: one from the M1 bake-off.

**People.** 1–2 researchers [estimate]. Human-study participants must be recruited under the institution's rules.

### 9.3 Feasibility risks

| Risk | Likelihood [estimate] | Impact | Mitigation / fallback |
|---|---|---|---|
| Local GPUs are not H200-class, or kernels are unavailable (FA2/FA3 missing in a prior local run) | Medium | High: no real-time world shot | M0 gate. Lower fps (12). Presenter-centric demo with pre-rolled world segments. Report honestly |
| Prompt interaction (C1) does not produce character actions with this checkpoint | Medium–high | Medium: fewer event types | Manifest excludes them. Contribution S1 still holds for camera and scene events. Document as a finding |
| Identity drift of the persona in the world shot (image used only at chunk 0) | High | Medium | Session restart from stored frames (C5); shot grammar favours the presenter for close-ups; measure (RQ6) |
| Cross-shot incoherence (two renderers) | High | Medium | Shared reference image and prompt; cut timing at event boundaries; composite ablation; report |
| Unpaced backlog inflates TVC | High (by code-read) | High | C4 bounded look-ahead |
| VLM judge too slow or inaccurate for online use | Medium | High for S1 | Geometric judge for camera; smaller judges; sample frames; if κ < 0.6, verification is used only offline and S1 is re-scoped |
| Single session per generator (`max_num_seqs=1`, single replica) | Certain | Low for research | One live user at a time; Mode 2 is one stream |
| License (CC BY-NC-SA weights; avatar and H3 licenses) | Certain | Medium | Research-only use; license audit in M1 |
| GPU scheduling contention | Medium | Medium | Book slots; short `--timeout` runs |

---

## 10. Limitations

- **No local measurement yet.** Every latency figure is upstream-reported or derived, so targets may shift after M0.
- **Code-read, not executed.** The main backbone constraint (camera-only mid-session interaction) was established by
  reading code and has not been executed.
- **Simulated users.** Simulated users (TTS scripts) make E2/E3 reproducible but do not capture spontaneous speech.
  The human study is small.
- **Imperfect judges.** VLM and geometric judges are imperfect, and we bound their error with human labels.
- **The dual-shot design does not unify the persona.** It demonstrates a visible speaking persona and a controllable
  world persona. It does not show one model doing both, which is A3 and future work.
- **The reference agent is uncontrolled.** Its implementation is unverified, and it is not a controlled baseline.
- **Weak on the "reasoning" part of the question.** We evaluate instruction following and multi-step tasks, not
  general reasoning ability.

## 11. Privacy, safety and ethics

- **Consent and minimization.**
  - Private memories are stored only with explicit consent.
  - Retention periods are defined.
  - Users can view, correct and erase their memories. Erasure cascades to derived artifacts (§5.6).
  - GDPR Art. 17-style erasure is a design target. The legal text is to be checked against EUR-Lex before any
    compliance claim.
- **Separating public and private memory.**
  - Stores are physically separate.
  - Scopes are filtered at retrieval.
  - Mode 2 has no read path to private stores.
  - Multi-channel leak probes run as release gates.
- **Generated content is never a user fact.** Persona utterances and rendered events are quarantined in a
  generated-event log.
- **Memory poisoning and prompt injection from chat.** Viewer input is untrusted: rate-limited, sanitized, stored with
  its provenance tag, and never promoted to canon or to private scopes.
- **Disclosure and likeness.**
  - The persona is fictional and labelled as AI-generated in every stream.
  - No real person's likeness or voice is used without consent.
  - Moderation filters apply to viewer requests; the reference stream showed inappropriate requests.
- **Licenses.** Research use only, under CC BY-NC-SA 4.0 for the LingBot weights and the licenses of other models.
  The MiniMax H3 license excludes some territories [cited]. H3 is not part of the proposed stack.
- **Human studies.** Subject to institutional ethics approval. The pre-registered analysis plan is followed.

## 12. Expected outcomes

- Evidence for or against **H1** and **H-core**: when does closed-loop, capability-grounded control help, and what
  latency does it cost?
- A calibrated **capability manifest** for LingBot-World 2.0 on the local hardware, releasable as a dataset.
- A **TVC protocol** and measurements for a chunked AR world model.
- Upstream-able vLLM-Omni extensions: prompt interaction for LingBot stepwise, reset/extend, timestamps.
- A live-persona **memory evaluation** covering false memories, deletion and cross-modal leakage.

## 13. References

Full, verified BibTeX is in `docs/references.bib`; every arXiv entry was resolved through the arXiv API on
2026-09-25. Keys cited in this proposal:

- **Backbone:** gao2026lingbotworld2, robbyantteam2026lingbotworld.
- **Streaming video:** yin2024causvid, huang2025selfforcing, yang2025longlive, zhu2026causalforcing,
  zhao2026causalforcingpp, wu2026echoforcing, he2025matrixgame2, wang2026matrixgame3, sun2025worldplay,
  deepmind2025genie3, ouyang2026helloworld, huang2026solarwm, abotworld2026abotworld0.
- **Avatars and joint audio-video:** huang2025liveavatar, shen2025soulxflashtalk, li2024ditto, guo2024liveportrait,
  xie2025xstreamer, huang2026wanstreamer, zeng2026lpm, minimax2026h3blogvideo.
- **Agents and control:** defossez2024moshi, xu2025qwen3omni, pipecat2026primer, wang2026pace, modi2026echochain,
  ahn2022saycan, huang2022innermonologue, long2025vista, yang2026spiral, lin2023videodirectorgpt, xu2025streamingvlm,
  mazumdar2026videofdb.
- **Memory:** packer2023memgpt, park2023generativeagents, chhikara2025mem0, rasmussen2025zep, fang2025lightmem,
  wu2024longmemeval, hu2025memoryagentbench, ren2026gatemem, yu2026kbench, yao2026executionunlearning, dong2025minja,
  modarressi2025nolima.
- **Evaluation:** xu2026worldmark, ying2026wbench, he2026memoryarena, lin2025fullduplexbench, lin2025fdbv2,
  he2024cameractrl, deng2018arcface, chung2016syncnet, nosek2018preregistration.
- **Standards:** itu1998bt1359, ebuNDr37.

**Code evidence:** vLLM-Omni `7b4dc7633bde8642f0c05f77bd018751541df404`. Paths are listed in
`docs/backbone_verification.md`.

## 14. Review status

This proposal went through the mandatory GPT-6 Sol (Codex) checkpoints. See `docs/codex_reviews.md` for the model
verification, the findings and their resolutions.

===== FILE: docs/PROJECT.md =====
# Live Agent — Project Specification (single source of truth)

Status: **v1.0** (2026-09-25). Updated after the research phase and Codex checkpoints 1–3. v0.1 was the provisional
version; see `docs/codex_reviews.md` and the git history. **Precedence:** `goal.md` (the owner's brief) sets the
requirements. This file records our current interpretation of them and tracks
their status. If the two disagree, raise the conflict in `docs/decision_log.md`
for resolution; do not silently prefer either one. `CLAUDE.md`, `AGENTS.md` and
`AGENT.md` point here and must not restate the spec.

## Purpose

Research, then demo, a **real-time, personalized live agent**: a digital persona
that talks with users through live generated video (and speech where supported),
follows instructions during the interaction, reasons about it, and keeps useful
long-term memory across sessions.

Central research question: *How can we combine real-time video generation with
reasoning, instruction following, and persistent memory to create a coherent,
controllable, personalized live agent?*

Working hypothesis (to be tested, not asserted): real-time video generation
alone is insufficient for reliable, stateful agent behavior.

## Current phase and scope

- **Phase 1 (current): research and proposal only.** Deliverables are listed
  below. No foundation-model training, paid deployments, public broadcasts, or
  unrelated repository changes.
- Initial use cases: **personalized 1:1 interaction** and **livestreaming**.
  We target one focused demo scenario (defined in the proposal), not a
  general-purpose assistant.
- Preferred video backbone: **LingBot-World 2.0 in vLLM-Omni**
  (<https://github.com/vllm-project/vllm-omni>). It may not be silently
  replaced. Any feasibility gap and any alternative must be justified in
  `docs/decision_log.md`.
- Reference experience: <https://www.twitch.tv/sylar_nv> (owner-provided, not
  verified: built by a friend, "based purely on MiniMax H3"). It is a qualitative
  reference unless a fair quantitative comparison is possible.

## Intended capabilities

1. Follow instructions during a live interaction, including corrections,
   interruptions, and changing goals.
2. Remember relevant user preferences, facts, and prior interactions across
   sessions, with correction, deletion, and provenance.
3. Keep the persona and its visual, conversational, and behavioral state
   consistent.
4. Turn decisions into controls that the generator can actually execute, and
   check that the output complies.
5. Stay responsive while reasoning, retrieving memories, and streaming output.

## Requirements, assumptions, open questions

| ID | Item | Status |
|----|------|--------|
| R1 | Produce the deliverables listed below | Confirmed (goal.md §8) |
| R2 | Mandatory GPT-6 Sol review through Codex at 4 checkpoints, with an auditable log | Confirmed (goal.md §7) |
| R3 | Label every number as cited / measured locally / estimate / proposed target | Confirmed (goal.md §6) |
| R4 | Keep private user memory separate from public livestream content; never store generated or inferred events as confirmed user facts | Confirmed (goal.md §5) |
| A1 | Hardware *inventory*: 8× NVIDIA L20X (≈140 GB each), shared and scheduled through `gpu` (canhazgpu). Inventory is not guaranteed capacity: schedulable access, memory per job, and LingBot throughput on L20X are **unverified**. Upstream validated H200/B200 only | Inventory observed 2026-09-25 (`nvidia-smi`); capacity open |
| A2 | The reference agent's implementation ("MiniMax H3") | **Still unverified.** Public evidence is consistent with clip-based H3 generation (24 fps, ~13 s segments) but does not prove it. H3 is an offline joint audio-video clip model (4–15 s) with no streaming mode. The reference agent is qualitative only (`docs/related_work.md` §3) |
| A3 | Speech, audio and lip sync need components outside LingBot-World | **Confirmed (code-read):** no audio in the pipeline. Native LingBot lip, face and audio conditioning is class D. An external TTS plus audio-driven avatar is engineering (D-005) |
| Q1 | Mid-session prompt changes in LingBot-World 2.0? | **Answered (code-read, not yet executed):** the public stepwise WS path registers only `camera` (`registry.py:25-27`). A prompt interaction → `interaction_failed`. Prompt switching exists only on the deprecated tick path (latents only). Extension C1 is needed. M0 runs one real WS test |
| Q2 | Does camera control express character behavior? | **Answered: no.** Camera control is viewpoint only. Character actions are prompt-conditioned (paper, class B) and depend on C1 and E1 calibration (D-012) |
| Q3 | Audience | 1:1 private user first; private test livestream second; no public broadcast this phase (D-001) |
| Q4 | Local "MiniMax H3" copy | Incomplete: 1 of 13 DiT shards, no text encoder. MiniMax H3 Community License excludes some territories. **Not part of the proposed stack** |
| Q5 | Is a simpler pipeline enough? | Carried as baseline A0, with the same LLM, memory and avatar as A2 (D-004, D-009). RQ4 tests this in both directions |
| Q6 | "Real-time" targets | Defined as [target] values in proposal §8, gated by M0 measurement |
| Q7 | Local GPU identity ("L20X": Ada/CC 8.9 per NVML vs H200-like 143,771 MiB/700 W) | **Open.** Resolved in M0 (D-008) |
| Q8 | Permission to use the shared `/data/models` LingBot weights | **Open. Owner to confirm** |

## Current direction (summary; details in `docs/research_proposal.md`)

- **Demo:** a dual-shot live persona. A lip-synced avatar close-up plus a LingBot-World world shot. Committed
  control: camera/viewpoint. Conditional: prompt-driven events.
- **Central research claim:** capability-grounded closed-loop control (IR → calibrated capability manifest →
  compiler → deadline-bounded monitor on displayed frames). Measured with a wall-clock time-to-visible-compliance
  (TVC) protocol.
- **Memory:** typed by provenance and separated by scope (private/public/canon). Deletion cascades to derived
  artifacts.
- **Next step (Phase 2, needs owner go-ahead):** M0, the backbone and hardware characterization.

## Requirement → deliverable checklist (from goal.md)

| goal.md § | Requirement | Where addressed |
|---|---|---|
| §1 | Research question, hypothesis tested rather than asserted, focused demo scenario, preferred backbone not silently replaced, reference agent treated as qualitative | proposal §1–2, decision_log |
| §2 | Instruction files kept consistent. Provisional understanding recorded first, then updated | this file, CLAUDE/AGENTS/AGENT.md |
| §3 | Six research areas. Matrix fields: approach, capabilities, memory, control interface, latency/hardware, availability, limitations, relevance, date/URL. Synthesis of solved, open, reusable, and contribution | related_work.md |
| §4 | Backbone integration surface. Each capability classed as available / reported / needs engineering / needs research, with the smallest resolving experiment | backbone_verification.md, proposal §6 |
| §5 | ≥3 candidate architectures. IR/interfaces/state/feedback, critical path, interruption, latency budget, memory taxonomy and lifecycle, private/public separation, feasibility, diagrams | proposal §5, figures/ |
| §6 | Ten proposal sections. Contribution separated from engineering. Evaluation with baselines, ablations, controls, sample sizes, uncertainty. Every number labeled | research_proposal.md |
| §7 | GPT-6 Sol review at 4 checkpoints, logged and re-reviewed | codex_reviews.md, docs/reviews/ |
| §8 | Final consistency check and closing summary | end of phase |

## Deliverables (Phase 1)

| File | Content |
|------|---------|
| `docs/research_proposal.md` | Complete, self-contained academic proposal |
| `docs/related_work.md` | Evidence-backed synthesis and comparison matrix |
| `docs/backbone_verification.md` | Verified vLLM-Omni / LingBot-World integration surface |
| `docs/decision_log.md` | Decisions, alternatives, evidence, assumptions, open questions |
| `tools/codex_review.sh` | Runs a Codex review checkpoint with inlined evidence and audit metadata |
| `docs/codex_reviews.md` | Actual Codex review records and resolutions |
| `docs/references.bib` | Verified bibliography |
| `docs/figures/` | Editable diagrams (Mermaid `.mmd` sources) |
| `docs/notes/` | Raw research notes (supporting material, not authoritative) |

## Research standards

- Use primary sources for technical claims. Record URLs and dates. For code,
  record the repo, commit, and `path:line` or symbol.
- Keep separate: what the inspected code does, what is reported upstream but
  not verified here, what needs engineering, and what needs new training or research.
- Do not fabricate experiments, measurements, user studies, or expected gains.
- Do not claim novelty just because components are combined. Agreement between
  models is not verification.
- Camera control does not imply character control. High generation FPS does
  not imply low latency from instruction to visible response.

## Codex review process (mandatory)

- Reviewer: **GPT-6 Sol**, invoked as
  `codex exec -m gpt-6-sol -s read-only --skip-git-repo-check -o <out> - < prompt`
  from the repo root. After each run, verify the model in the session rollout
  (`~/.codex/sessions/.../rollout-*.jsonl`, field `"model":"gpt-6-sol"`).
  Naming a model inside a prompt does not select it.
- Checkpoints: (1) understanding/requirements/assumptions; (2) literature and
  research gap; (3) architectures, integration, memory, latency; (4) experiments
  and final proposal.
- The Codex shell sandbox cannot start on this host (user namespaces are
  disabled), and running unsandboxed is not permitted. Reviews therefore run
  through `tools/codex_review.sh <tag> <instructions> <files...>`, which puts
  every piece of evidence (files and code excerpts) inline in the prompt.
- For each checkpoint, record in `docs/reviews/<tag>_*`: the exact prompt and
  evidence bundle (with sha256), the reviewer output, the event stream, and
  metadata (repo HEAD and dirty state, vLLM-Omni commit, CLI version, requested
  model, model reported by the rollout, thread ID, exit code).
  `docs/codex_reviews.md` summarizes every finding with its disposition
  (accepted / partially accepted / rejected with evidence / open) and the
  revision that resolved it. Re-review material changes.
- If Codex is unavailable, record the exact blocker and mark the review
  **pending**. Never simulate or substitute a reviewer.

===== FILE: CLAUDE.md =====
# CLAUDE.md — live-agent

Project: research and demo a real-time, personalized live agent (live generated
video, plus speech where supported; instruction following, reasoning, long-term memory).

**The project specification lives in [`docs/PROJECT.md`](docs/PROJECT.md).** It covers
purpose, scope, capabilities, requirements, research standards, deliverables and
the mandatory Codex review process. Read it first. Do not restate it here, and edit
the spec there only. The original brief is [`goal.md`](goal.md). Do not edit it.

Claude-specific working rules:
- Current phase is research and proposal. Do not train, deploy, broadcast, or
  change repos outside this directory. `external/` holds read-only reference
  clones (git-ignored). Record the commit you inspected.
- Every GPU job goes through `gpu run ... --timeout ... --note ...` (see
  `/data/zhoutaichang/CLAUDE.md`). Never run GPU code as root.
- Git: local repo, author `tzhouam <tzhouam@connect.ust.hk>`. Do not push unless asked.
- Run Codex reviews with the exact command in `docs/PROJECT.md`, verify the
  model in the session rollout, and log results in `docs/codex_reviews.md`.
- Log material decisions in `docs/decision_log.md` when you make them.
- Label every number as *cited*, *measured locally*, *estimate*, or *proposed target*.

===== FILE: AGENTS.md =====
# AGENTS.md — live-agent

Instructions for Codex and other coding or review agents working in this directory.

**The project specification lives in [`docs/PROJECT.md`](docs/PROJECT.md)** (purpose,
scope, capabilities, research standards, deliverables, review process). Read
it first. The original brief is [`goal.md`](goal.md). `CLAUDE.md` adds Claude-specific rules.

When you are acting as the **independent reviewer** (GPT-6 Sol via `codex exec`):
- Work read-only. Do not edit files unless the prompt explicitly asks.
- Challenge unsupported claims, overlooked alternatives, interface mismatches
  with the inspected vLLM-Omni code, feasibility assumptions, and weak
  evaluation designs. Check claims against the cited sources or code paths
  (`external/vllm-omni` at the recorded commit), not against the author's summary.
- Give findings as a numbered list. Mark each one **blocking**, **major**,
  or **minor**, and give the evidence or the check that would settle it.
- Do not treat agreement with the author as verification.

When you are acting as a **contributor**: follow `docs/PROJECT.md`. Do not train,
deploy, or broadcast in the current phase. Label every number as cited,
measured, estimate, or target.

===== FILE: AGENT.md =====
# AGENT.md — live-agent

This file exists for tools that read `AGENT.md`. It carries no separate rules.

- Project specification (single source of truth): [`docs/PROJECT.md`](docs/PROJECT.md)
- Rules for agents and reviewers (Codex / GPT-6 Sol): [`AGENTS.md`](AGENTS.md)
- Claude Code rules: [`CLAUDE.md`](CLAUDE.md)
- Original brief: [`goal.md`](goal.md)

`goal.md` sets the requirements, and `docs/PROJECT.md` records their current interpretation.
If any of these files disagree, log the conflict in `docs/decision_log.md` and fix it. Do not silently pick one.

===== FILE: docs/decision_log.md =====
# Decision Log

Material decisions, the alternatives considered, the evidence, and the
assumptions they depend on. IDs are stable. Statuses are *provisional*, *adopted*,
*superseded*, or *open*.

| ID | Date | Decision | Alternatives | Evidence / rationale | Status |
|---|---|---|---|---|---|
| D-001 | 2026-09-25 | The first acceptance scenario is a **1:1 private user**. **Public livestream** is the second evaluation scenario, with separate memory scopes | Livestream first; both at once | CP1 finding 2. Memory and instruction-following claims are measurable only with a controlled user. Livestream adds unconsented third parties | provisional |
| D-002 | 2026-09-25 | Codex reviews run with `-s read-only` and all evidence inline | Unsandboxed Codex (denied by the permission policy); MCP Codex (server failed to connect) | `max_user_namespaces=0` means bwrap cannot start | adopted |
| D-003 | 2026-09-25 | Pin upstream vLLM-Omni `main` at `7b4dc76` (2026-09-24) as the inspected implementation, in a read-only clone at `external/vllm-omni` | Use one of the user's feature branches under /data/zhoutaichang | Upstream main is the public integration surface. Feature branches hold unrelated or uncommitted work | adopted |
| D-004 | 2026-09-25 | Carry a "no world model" baseline (LLM + TTS + talking-head avatar) through the evaluation | Evaluate only the LingBot-based design | CP1 finding 4 / goal §5 ("simple baseline") | adopted |
| D-005 | 2026-09-25 | Demo = **dual-shot live persona**: a lip-synced avatar close-up (external audio-driven model) plus a LingBot-World world shot of the same persona, chosen by a controller shot track. Voice-over-only explorer rejected | (a) Explorer with voice-over only; (b) avatar composited into the LingBot scene; (c) a native LingBot talking head | CP2 blocking finding 2. The backbone has no native lip, face or audio path (class D), and the owner's goal requires a visible persona. (b) is kept as an ablation | provisional |
| D-006 | 2026-09-25 | Central research claim = capability-grounded closed-loop control with deadline-bounded visual verification. TVC is its measurement protocol | TVC as the headline novelty; memory as the headline | CP2 findings 1 and 6. WorldMark and ABot-World-0 already measure related latencies; SayCan and Inner Monologue are prior art for affordances and feedback | provisional |
| D-007 | 2026-09-25 | No GPU benchmark in this phase. The smallest resolving experiment is specified as M0 | Run the vLLM-Omni LingBot benchmark now | The goal keeps this phase to research. The environment is not turnkey (earlier local run had no FlashAttention and ended in tracebacks). The weights sit in shared `/data/models`, and permission to use them should be confirmed | adopted |
| D-008 | 2026-09-25 | GPU identity recorded as unresolved: NVML "L20X"/Ada/CC 8.9 vs H200-like memory and power | Assume H200 (as an upstream PR says) | Direct `nvidia-smi -q` evidence conflicts with that PR's statement | adopted |
| D-009 | 2026-09-25 | A0, A1 and A2 share LLMs, renderers, memory service (except in E3) and the generator control substrate (S-cam, plus S-prompt through C1). Only the controller differs | Separate stacks per arm | CP3 finding 6: removes confounds for RQ1 and RQ4 | adopted |
| D-010 | 2026-09-25 | A bounded look-ahead gate (C4) is required for real-time TVC. `session.ping` is not flow control. Fallbacks: skip-to-latest, playback-rate adaptation | Rely on the client buffer | Code-read: `serving_video_output_stream.py:148-155` sends chunks as produced; ping only refreshes the stall clock (`:17,79-88,311`). Backlog grows ≈0.2 s/chunk at T=0.549 s and 16 fps [derived] | adopted |
| D-011 | 2026-09-25 | The IR is relative, the wire format is absolute. The compiler tracks a pose estimate and emits absolute `target` poses | Send relative targets | Code-read: `camera.py:44,107,341-352` — target poses are absolute relative to the session-start origin. The API doc's "absolute pose" wording agrees | adopted |
| D-012 | 2026-09-25 | The first demo commits only camera/viewpoint control and a visible host. Locomotion and scene/character events are conditional on C1 and E1 | Promise "walk to the lake" | CP3 finding 5: camera ≠ character; prompts need C1 | adopted |

## Open questions

See `docs/PROJECT.md` (A*/Q* table). Resolved questions move here with the evidence.

===== FILE: docs/codex_reviews.md =====
# Codex Review Log (GPT-6 Sol)

Auditable record of the mandatory independent reviews (goal.md §7). Raw
artifacts for each run are in `docs/reviews/<tag>_{instructions,prompt,review,events,meta}`.

## Reviewer setup (verified 2026-09-25)

| Item | Value | Evidence |
|---|---|---|
| Tool | Codex CLI `codex-cli 0.156.0` (`/home/zhoutaichang/.local/bin/codex`) | `codex --version` |
| Model requested | `gpt-6-sol` (`-m gpt-6-sol`; also the default in `~/.codex/config.toml`) | command line in each `*_meta.txt` |
| Model actually used | `gpt-6-sol`, provider `openai` | `"model":"gpt-6-sol"` in each session rollout (`~/.codex/sessions/2026/09/25/rollout-*.jsonl`; path recorded in `*_meta.txt`) |
| Available models (cache) | gpt-6-astra, gpt-6-sol, gpt-6-luna, gpt-5.6-*, gpt-5.5, … | `~/.codex/models_cache.json` |
| Codex MCP server | Failed to connect in the Claude Code session (`CONNECTION_CLOSED`). The CLI is used instead | session environment notice |
| Sandbox | The `bwrap` sandbox cannot start: `/proc/sys/user/max_user_namespaces = 0` ("No space left on device"). Running Codex unsandboxed was denied by the Claude Code permission policy. **Mitigation:** run `-s read-only` and inline all evidence through `tools/codex_review.sh`. **Limitation:** the reviewer can check only what is inlined, not browse the repo itself | cp1 attempt 1 output; `unshare` test |

## Summary table

| CP | Tag | Date (UTC) | Reviewed revision | Model (rollout) | Findings | Status |
|---|---|---|---|---|---|---|
| 1 | cp1_attempt1 | 2026-09-24T17:29Z | ef3a0f3 | gpt-6-sol | 6 provisional (reviewer could not read files) | Superseded by cp1 |
| 1 | cp1 | 2026-09-24T17:36Z | ef3a0f3 (+ inlined files) | gpt-6-sol | 7 (1 blocking, 5 major, 1 minor) | Resolved in d68466e. Blocking item #1 is carried into CP3 |
| 2 | cp2 | see `cp2_meta.txt` | 7cce79f | gpt-6-sol | 10 (2 blocking, 7 major, 1 minor) | Resolved in 8eb4d33. Re-reviewed as part of CP3 |
| 3 | cp3 | see `cp3_meta.txt` | ecbb880 | gpt-6-sol | 15 (2 blocking, 12 major, 1 minor) | Resolved in c085745. Re-reviewed as part of CP4 |

## Checkpoint 1 — project understanding, requirements, assumptions

**Attempt 1 (invalid).** The reviewer's shell sandbox failed on every file read,
so it reviewed only the prompt text. Its output is kept as
`docs/reviews/cp1_attempt1_review_sandbox_failed.md` but is not counted as a
review of the artifacts.

**Attempt 2 (`cp1`).** The inlined files were goal.md, docs/PROJECT.md v0.1,
CLAUDE.md, AGENTS.md, and AGENT.md, plus the author's initial observations.

| # | Sev. | Issue (abridged) | Disposition | Resolution |
|---|---|---|---|---|
| 1 | blocking | The demo may exceed what the backbone can control. The recipe shows only public camera control: no gestures, expressions, speech, or public mid-session prompt switching | **Accepted** | The backbone is being verified at code level (`docs/backbone_verification.md`). The demo scenario will be chosen after a control→observable-behavior table exists (goal §4/§5). Carried into CP3 for re-review |
| 2 | major | Acceptance scenario and "real-time" are undefined | **Accepted** | PROJECT.md Q3: 1:1 private user is the first acceptance scenario and livestream is the second (D-001). Q6: targets are set in the proposal |
| 3 | major | Feasibility assumptions are stated too confidently (GPU inventory vs. capacity; H3 provenance) | **Accepted** | A1 split into inventory (observed) and capacity (open). Q4 added for H3 provenance/license |
| 4 | major | The hypothesis has no competing account | **Accepted** | Q5: a simple LLM+TTS+talking-head pipeline is carried as a competing baseline that the evaluation can favor |
| 5 | major | The "single source of truth" drops binding requirements from goal.md | **Accepted** | goal.md now takes precedence. A requirement→deliverable checklist was added to PROJECT.md |
| 6 | major | The review log lacks a reproducible evidence trail | **Accepted** | `tools/codex_review.sh` records the prompt with its sha256, output, events, rollout path and model, repo and vLLM-Omni SHAs, dirty state, and exit code. PROJECT.md was updated |
| 7 | minor | CLAUDE.md dropped "where supported" for speech. AGENT.md precedence could override goal.md | **Accepted** | Both fixed |

Remaining disagreements: none.

## Checkpoint 2 — literature synthesis, capability claims, research gap

Tag `cp2`. Reviewed revision 7cce79f. Inlined: related_work.md, backbone_verification.md, the synthesis
sections of the three literature notes, and the reference-agent note. The reviewer followed some primary-source
links (arXiv) on its own.

| # | Sev. | Issue (abridged) | Disposition | Resolution (8eb4d33) and evidence |
|---|---|---|---|---|
| 1 | blocking | G1/TVC overclaims novelty: WorldMark already measures response latency | **Accepted after verification.** Claude read the WorldMark HTML: its latency is counted in *generated-video frames* until motion reaches half the reference speed. A targeted search also found ABot-World-0 (arXiv 2607.19191), which reports *wall-clock action-to-first-frame* time, i.e. when a frame becomes available, with no compliance check | TVC redefined as wall-clock time from instruction arrival to *displayed, judged-compliant* content, with censored failures. Downgraded to a measurement protocol supporting contribution 1. G1 rewritten with both neighbours |
| 2 | blocking | The explorer/voice-over demo undershoots the "digital persona" goal | **Accepted** | Dual-shot live persona (D-005): a lip-synced avatar close-up plus a LingBot world shot of the same persona, with cross-shot coherence measured. Compositing is an ablation |
| 3 | major | "Camera-only" is a code-read conclusion; an ack is not compliance; a real WS prompt test is needed | **Accepted** | Scope stated in backbone_verification.md (CP2 clarifications). A real WS prompt attempt was added to M0 |
| 4 | major | Latency labels are loose (549 ms stack; derived 0.6–1.15 s is not TVC; Wan-Streamer's network is assumed; D vs external avatar; rewind class) | **Accepted** | All relabelled. Rewind/snapshot → "C/D, feasibility unknown". D is limited to native LingBot conditioning |
| 5 | major | The falsification test is loose, and "internal state" mixes generator KV with thinker context | **Accepted** | H-core restated with the two kinds of state separated, a definition of "external state layer", an operational test and a refutation condition |
| 6 | major | Contribution 1's prior art is understated (SayCan, Inner Monologue); "offline only" is too broad | **Accepted after verification.** Claude ran a targeted search (2026-09-25). SPIRAL's critic is iterative/offline; the agentic-visual-generation survey (2609.06758) does not cover runtime verification of streaming generators. Bib entries were added through the arXiv API | Contribution 1 repositioned as a specific combination, with four required comparison arms. G2 reworded to "not found for streaming generators" |
| 7 | major | Novelty varies across G4–G10 (PACE, provenance, WBench) | **Accepted** | Contributions 3–5 downgraded or scoped to their evaluation novelty. G10 now says "no single benchmark found". WBench cited |
| 8 | major | Interruption and TVC need operational definitions; cancel ≠ redirect | **Accepted** | G5 rewritten (cancel exists; redirecting an in-flight chunk does not). The TVC timestamp list and censoring are defined. VLM judges are validated against blinded human labels (proposal §8) |
| 9 | major | Material neighbours were missing from the synthesis (WBench, WorldMark, VideoFDB, MIDAS, StreamingVLM, MemoryArena, LiViBench) | **Accepted** | Added to the matrices and gaps |
| 10 | minor | Matrix fields incomplete (URLs, control interface, latency in §2.4); KV wording; tea observation | **Accepted** | Direct arXiv links in every row. §2.4 rebuilt with control-interface and latency columns ("not stated" per cell). KV sink and window described separately. The tea observation stays a single unaligned sample |

Remaining disagreements: none. The reviewer also noted it could not re-read the pinned checkout. This is an
inherent limitation of inline review (D-002). CP3 inlines the relevant code excerpts.

## Checkpoint 3 — architectures, integration, memory, latency

Tag `cp3`. Reviewed revision ecbb880 (proposal v0.9). Inlined: the proposal, backbone_verification, decision_log,
the 4 figure sources, the vLLM-Omni streaming API doc, the realtime design doc, and **real code excerpts with line
numbers** (`docs/reviews/cp3_ev_code_excerpts.md`) from registry.py, coordinator.py,
serving_video_output_stream.py, pipeline.py and the deploy yaml. CP3 also re-reviewed the CP2 revisions (dual-shot
design, TVC repositioning) and raised no objection to them.

| # | Sev. | Issue (abridged) | Disposition | Resolution (c085745) |
|---|---|---|---|---|
| 1 | blocking | A1's "free-form prompts" cannot execute (prompt handler not registered) | **Accepted** | Shared generator substrate (D-009): S-cam, plus S-prompt only through C1 once it passes M1 tests; without C1, prompt changes are session restarts for both A1 and A2 |
| 2 | blocking | The backlog gate has no mechanism; `session.ping` is not flow control | **Accepted.** Claude had independently confirmed `serving_video_output_stream.py:17,79-88,311` before the review arrived | C4 redefined as a server generation gate (feasibility checked in M1), with skip-to-latest and rate adaptation as fallbacks. M0 measures queue depths and transport backpressure (D-010) |
| 3 | major | C1 is more than registration; stepwise `invalidate=True` safety is unverified | **Accepted** | C1 spec: encode at the boundary, session state, per-rank K/V rebuild under Ulysses head sharding, transition policy, tests. Re-sized to medium |
| 4 | major | Evidence labels (documented / code-read / executed) are conflated | **Accepted** | §6.1 distinguishes the three. M0 WS contract test added |
| 5 | major | Camera commands ≠ "walk slower" / "walk to the lake" | **Accepted** | Demo scoped to committed camera/viewpoint control and a visible host. Locomotion and events are conditional (D-012) |
| 6 | major | Architecture comparison confounded (memory and renderer differ); alternatives missing; A3(b) needs no training | **Accepted** | Shared substrate. Table of feasibility alternatives: SGLang server, tick path, clip scheduling, compositing, different backbone. A3 split into (a) training and (b) none if weights exist |
| 7 | major | IR camera contract undefined; Fig. 2 cancellation inconsistent | **Accepted. While verifying, Claude found an error the reviewer did not name**: `target` poses are *absolute relative to the session origin* (`camera.py:44,107,341-352`), not relative | Contract: frame, units, velocity held until replaced (explicit stop), absolute targets from a compiler pose estimate (D-011). Golden IR→WS example (JSON and quaternions validated). A single cancellation rule; Fig. 2 fixed |
| 8 | major | Monitor underspecified: sparse-flow scale ambiguity, VLM latency ≠ throughput | **Accepted** | Rotation plus translation *direction* only, abstention rules, K=4 frames per chunk, verdict deadline, repair eligibility reported |
| 9 | major | Quarantine leaks: quotations and echoes of persona claims | **Accepted** | Claim-type classification, echo lineage against the generated-event log with confirmation, paraphrase `derived_from`. Probes added to E3 |
| 10 | major | Scope holes through derived media and persona history | **Accepted** | `source_scopes` on every derived artifact. Private-session persona utterances are private. Public sessions start only from canon/public frames. Fresh-public-session probe added |
| 11 | major | Deletion vs append-only log undefined | **Accepted** | Erasure physically deletes records, cascades to 6 artifact classes, keeps a content-free tombstone ledger and bounded backup retention, and is verified after a flush and restart |
| 12 | major | TVC budget mixes paced and unpaced timing; p95 sums invalid | **Accepted** | Regime U (unbounded growth) vs regime G ($W \sim U(0,P)$, $L \cdot P$). Figures are labelled column sums, not quantiles, and will be replaced by a simulation from M0 measurements. 2-GPU/12 fps recomputed |
| 13 | major | Avatar delay omitted from the speech path; ack ≠ presentation | **Accepted** | Shared presentation timeline. Separate first-speech targets for world-shot and presenter-shot starts. Narration aligned to presentation |
| 14 | major | The first-demo boundary and GPU budget are optimistic; C2/C5 under-sized | **Accepted** | First demo = M0-qualified configuration with a presenter-plus-clips fallback. C2 medium–large; C5 seam acknowledged. GPU estimate labelled optimistic; full-machine slots booked |
| 15 | minor | Denominators and censoring | **Accepted** | Instruction-level success is primary (refusals count as failures). Conditional OCR and refusal rate reported. Unconditional p95 only if censoring ≤ 5%, otherwise restricted mean and deadline success |

Remaining disagreements: none.

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
  - LingBot-World 2.0 in vLLM-Omni retains two separate pieces of KV state: an attention sink holding the
    *first* 3 chunks of the session, and a rolling window holding the *most recent* 3 chunks (≈36 px frames,
    about 2.25 s at 16 fps). The sink is anchored at the session start; it is not contiguous with the window
    [local-code: `pipeline.py:748-782`; checkpoint config `sink_size=9`, `sliding_window_num_frames=18`].
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
  - Wan-Streamer v0.1: 192p, ≈200 ms model-side; the ≈550 ms total includes an *assumed* 350 ms network component, not a measured one [cited: huang2026wanstreamer].
  - LPM 1.0: text motion prompts, 5,000+ motion descriptors [cited, weights not released: zeng2026lpm].
- Genie 3 supports "promptable world events" [vendor: deepmind2025genie3].

So "video models lack reasoning" is **false as a blanket claim**.

**Refined hypothesis carried into the proposal (revised after CP2).** We separate two kinds of internal state:
(i) the *generator's* KV/latent cache, and (ii) the *dialogue context* of any LM "thinker" inside a unified model.

- **H-core:** without an explicit external state layer, neither kind of internal state provides:
  (a) cross-session memory that the user can **correct and delete**, with provenance;
  (b) **verified visible compliance** with instructions;
  (c) **control limited to affordances the generator can actually render**.
- An "external state layer" means any persistent store or controller outside the model's forward pass (weights,
  KV and context window).
- **Operational test** (proposal §7):
  - Horizon: ≥ 3 sessions separated by session restarts (a new generator session and a fresh context).
  - Probes: planted user facts, corrections, deletion requests and generated distractors.
  - Visible compliance: judged on displayed frames against the thresholds in proposal §8.
- **Refutation:** a system without an external state layer that meets the memory and compliance thresholds on this
  test refutes H-core for that system.
- Our survey's statement that no reviewed system provides (a)–(c) together is **a survey finding, not a proof of
  absence**.

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
| G1 | **Wall-clock time from instruction to displayed, compliant content is not reported.** Related measures exist but stop short: WorldMark's *response latency* counts **generated-video frames** until motion reaches half the reference speed after a command switch, including third-person splits [cited: xu2026worldmark, full text checked 2026-09-25]. ABot-World-0 reports **wall-clock action-to-first-frame** latency (1.2 s on 1×RTX 5090), defined as the time until the next chunk's first frame is *available*; it does not check whether that frame complies [cited: abotworld2026abotworld0]. LongLive and Echo-Forcing describe delayed prompt adaptation only qualitatively | Needed: a wall-clock measure from instruction arrival to *displayed and judged-compliant* content. It should span ASR, planning, queueing, generation, transport, buffering and visual inertia, and count never-complied cases as censored observations. This is a measurement-protocol contribution, not a new concept |
| G2 | **Deadline-bounded, runtime verification of observable compliance for *streaming generators* was not found.** A targeted search on 2026-09-25 found video critics that are offline or iterative: VISTA, VideoRepair, PhyT2V, and SPIRAL's VLM CriticAgent, which refines segments iteratively and feeds GRPO [cited: long2025vista, yang2026spiral]. Closed-loop *robotics* is prior art for feedback-driven replanning (Inner Monologue) and measured affordances (SayCan) [cited: huang2022innermonologue, ahn2022saycan]. LingBot's Director/Pilot has no reported validity evaluation | Distinguishes "the LM says it complied" from "the output complied" |
| G3 | **Language intent → executable generator control is shallow and unaware of what the generator can do.** Real-time generators expose narrow, model-specific controls | LingBot public path: camera-only [local-code]. SGLang LingBot: keys + per-chunk text [cited: SGLang cookbook]. Convai/ACE map intents to *game-engine* actions with known semantics [vendor] | Planner must know what a *stochastic generator* can reliably render |
| G4 | **Agent context is not aligned with what the user actually saw or heard.** Generated-but-unplayed content causes mis-anchoring | PACE (audio): referent anchoring 25.0% → 96.3% [cited: wang2026pace]. No video analogue found | Interruptions of queued video chunks ("no, the other one") |
| G5 | **Redirecting in-flight video while keeping the session is not characterized.** `session.stop` / request abort exist and *cancel* the rollout. Redirection is different: new controls apply only at the next chunk boundary, and a chunk already in flight cannot be changed. A failed tick forces a reset | vLLM-Omni design doc and code [local-code: `docs/design/feature/realtime_ar_diffusion.md`]. Interruption is weak even in speech-only systems: EchoChain < 50% pass [cited: modi2026echochain] | Latency floor = queued chunks + one generation interval + transport |
| G6 | **Correction, forgetting and deletion are the weakest memory competencies.** Deleting a record ≠ forgetting | MemoryAgentBench selective forgetting ≤ 28% [cited]. K-Bench: 22–86% leak after "deletion" [preprint: yu2026kbench]. Execution-state unlearning: derived summaries, plans and caches persist [preprint: yao2026executionunlearning] | User corrections and erasure requests must propagate to derived artifacts |
| G7 | **Public/private separation and memory poisoning in broadcast settings are open.** | GateMem: no method is strong on utility + access control + forgetting at once [preprint: ren2026gatemem]. MINJA: query-only memory injection [cited: dong2025minja] | In a livestream every viewer is a potential writer |
| G8 | **Character-level control inside world models is nascent. No system combines avatar-grade speech/face performance with scene-level world control** | Camera-only: Matrix-Game 2/3, WorldPlay, SolarWM. Character slices: LingBot-World 2.0 actions via chunk prompts, HelloWorld social reactions (not real-time), ReactiveGWM NPC strategy [cited] | Our persona must speak *and* act in a scene. Today that takes two model families |
| G9 | **Generated visual state is not linked to agent episodic memory across sessions** | World-model memory (WorldMem, Context-as-Memory, WorldPlay) targets scene revisits within one rollout. Avatar identity uses reference sinks. Multimodal *agent* memory stores images and screenshots the user provides, not the agent's own generated appearance: MIRIX [wang2025mirix], Mem-Gallery [bei2026memgallery], H2HMem [zhu2026h2hmem]. Vidu S2's dynamic references re-inject visuals within a session [cited: zhang2026vidus2] | "Remember the scarf you wore yesterday" needs cross-session visual grounding |
| G10 | **We found no single benchmark covering the whole combination** (speech + video control under interruption + cross-session memory + identity drift + wall-clock compliance latency) | Partial coverage exists. WBench: multi-turn subject actions, event editing, first- and third-person views, 22 metrics validated against humans [cited: ying2026wbench]. WorldMark: response dynamics. VideoFDB: full-duplex vision-speech agents [cited: mazumdar2026videofdb]. MemoryArena: memory that must drive later actions [cited: he2026memoryarena]. LiViBench: livestream understanding [cited: wang2026livibench]. Full-Duplex-Bench and EchoChain: speech interruption | The protocol should *reuse* these components. Only the integration and the wall-clock and memory probes are new |

### 1.4 Where a defensible research contribution may exist

Combining a voice pipeline, an LLM and LingBot-World is **engineering integration, not a research contribution**. The
candidate contributions below each come with a measurable claim and a novelty risk. They are hypotheses, not
established claims.

1. **Central candidate: capability-grounded, closed-loop control of a stochastic streaming generator under
   latency** (addresses G2 and G3).
   - **Prior art to position against:**
     - SayCan: language-model plans weighted by *measured affordances* [ahn2022saycan].
     - Inner Monologue: replanning driven by closed-loop feedback [huang2022innermonologue].
     - SPIRAL and VISTA: VLM critics used for offline or iterative refinement [yang2026spiral, long2025vista].
     - LingBot-World 2.0's Director/Pilot.
   - **Defensible claim — this specific combination:**
     - (i) affordances calibrated for a *stochastic generator*: per-control success rate, time-to-effect
       distribution and side effects;
     - (ii) visual verification with a *deadline*, on displayed frames, during streaming;
     - (iii) honest reporting of failures to the user, under the constraint that a chunk cannot be redirected mid-flight.
   - **Required comparisons:**
     - a prompt-only planner (open loop, no manifest);
     - a capability-aware open-loop planner (manifest, no verifier);
     - a verifier without calibrated affordances;
     - the full system.
2. **Measurement protocol: wall-clock time-to-visible-compliance (TVC)** (addresses G1 and G5). This supports
   contribution 1 and is not a standalone novelty claim.
   - **Definition:** time from instruction receipt to the first *displayed* frame that is independently judged compliant.
   - **Timestamps logged:** receipt, control acceptance, generation start, mux completion, client presentation,
     judged visible onset.
   - **Never-complied cases** are right-censored and reported as a failure rate, not dropped.
   - **Distinct from** WorldMark (generated-frame units, motion onset) and ABot-World-0 (availability, not compliance).
3. **Display-aligned interaction state for generated video** (addresses G4). This is a video adaptation of PACE
   [wang2026pace].
   - Its distinctive parts: client-reported presentation times, and tests in which a user refers to video content
     while interrupting.
   - Novelty: moderate. We treat it as secondary.
4. **Provenance-typed, scope-separated memory for a live persona** (addresses G6, G7 and G9).
   - The mechanisms come from Generative Agents, Zep/Graphiti, GateMem and execution-state unlearning.
   - The potentially new part is the **evaluation**: broadcast-setting leakage and poisoning measured *across
     modalities* (speech, on-screen content, generated visuals), plus correction and deletion that propagate to
     visual state records.
5. **Live-persona evaluation protocol** (addresses G10). It is assembled from WBench, WorldMark, Full-Duplex-Bench,
   LongMemEval, MemoryAgentBench and GateMem components. New elements: TVC and the cross-session and cross-modal probes.
6. *(Longer-term; needs training.)* **A character-centric live world model** (addresses G8).
   - Adds audio and behavior-token conditioning to LingBot-World.
   - This is an ambitious training direction and **not a near-term claim**.

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
| **LingBot-World 2.0 in vLLM-Omni** (integration PRs 2026-08-16 → 09-24; `7b4dc76`) | 14B causal-fast, 4-step DMD, chunk = 3 latent = 12 px frames (first chunk 9) | C (SE3 target/velocity) mid-stream on public WS. T only at start. Prompt switching only on the deprecated tick path (latents only) [local-code] | Sink 3 chunks + window 3 chunks; image used only at chunk 0 | Upstream-reported, specific stacks: ≈549 ms/chunk and TTFC ≈1.07 s on 4×H200 USP4 with the PR #7749 stack (compiled; streaming decoder; selective FP8 and KV-skip options, some experimental). ≈892–896 ms on 2×H200 (same PR). ≈3.24 s/chunk and TTFC ≈2.7 s on 1 GPU eager (PR #7645, older head). **Not measured locally** [cited: vLLM-Omni PRs #7749, #7645] | Code Apache-2.0; weights **CC BY-NC-SA 4.0**. Weights present locally | ≤480×832; `max_num_seqs=1`; single replica; fixed session length; no WS reset; no audio; no character control | **Required backbone.** Integration surface verified |
| LingBot-World 2.0 paper (2026-07-08; arXiv [2607.07534](https://arxiv.org/abs/2607.07534)) | Same family; causal pretraining + distillation | K, C, actions (attack, archery, spells) and text events via **chunk-wise prompts**; VLM Director/Pilot | "does not truly remember"; unbounded horizon claimed | 720p@60 fps claim (distilled) [cited, unreproduced in vLLM-Omni] | Repo `robbyant/lingbot-world-v2`; CC BY-NC-SA | Claims not reproduced in the integration | Shows the intended affordances. The gap between paper and serving is key |
| LingBot-World v1 (2026-01-28; [2601.20540](https://arxiv.org/abs/2601.20540)) | Wan-based world model | K, C | minute-level "long-term memory" claim | <1 s latency @16 fps [cited] | Apache-2.0 | Not used by vLLM-Omni | Predecessor |
| Self Forcing (2025-06-09; [2506.08009](https://arxiv.org/abs/2506.08009)) | Train on own rollouts (DMD), rolling KV | T (inherits) | rolling KV | ≈16 FPS H100, ≈0.8 s first latency, 480p [cited] | Apache-2.0 | 1.3B | Base recipe |
| LongLive (2025-09-26; [2509.22622](https://arxiv.org/abs/2509.22622)) | Frame sink + short window; KV-recache on prompt switch | **T mid-stream** | short window + sink | 20.7 FPS 1×H100; up to 240 s [cited] | Apache-2.0 | 1.3B; delay after switch shown qualitatively | Prompt-switch reference for G1 |
| Causal Forcing / ++ (2026-02-02; 2026-05-14) | Causal teacher / consistency distillation | inherits | – | ++: frame-wise 2-step, −50% first-frame latency vs chunk 4-step [cited] | Apache-2.0 | small models | Latency-reduction lever (needs retraining) |
| Echo-Forcing (2026-05-15; [2605.16003](https://arxiv.org/abs/2605.16003)) | Training-free hierarchical memory, scene recall, difference-aware decay | **T mid-stream** (smooth/hard cuts) | scene recall frames | bounded cache [cited] | code, no license | VBench-only eval | Recall + switch mechanism |
| Matrix-Game 2.0 (2025-08-18; [2508.13009](https://arxiv.org/abs/2508.13009)) | Real-time interactive world model | K; **text removed** | 6-frame KV; no memory (stated) | 25 FPS 352×640, 1×H100, 1.8B [cited] | MIT | ego-only | Shows camera ≠ character |
| Matrix-Game 3.0 (2026-04-10; [2604.08995](https://arxiv.org/abs/2604.08995)) | Camera-aware memory retrieval | K + mouse | memory retrieval by FOV | up to 40 FPS 720p, 5B, 8 DiT GPUs + 1 VAE GPU [cited] | Apache-2.0 | ego-only | Visual memory reference |
| WorldPlay / HY-World 1.5 (2025-12-16; [2512.14614](https://arxiv.org/abs/2512.14614)) | Reconstituted context memory | K + text-triggered events | ~30 s horizon (stated) | 720p 24 FPS 8×H800 [cited] | Tencent license (excludes EU/UK/KR) | license | Text events in a world model |
| Genie 3 (2025-08; blog) | Closed world model | K, C, **promptable events** | ~1 min visual memory | 720p 24 FPS [vendor] | closed | not accessible | Upper-bound reference |
| HelloWorld (2026-08-05; [2608.05070](https://arxiv.org/abs/2608.05070)) | Time-localized prompt attention masks | C + button → social reactions (wave, nod) | – | not stated | code (LTX-2 license) | not real-time | Training-free way to localize actions in time |
| SolarWM (2026-09-02; [2609.02886](https://arxiv.org/abs/2609.02886)) | Open recipe making Wan2.2, LTX-2.5 or MiniMax-H3 causal and real-time | C (metric camera) | trained on 5 s, rolls out to hours | "real-time" claimed [cited] | Apache-2.0 code + data | camera-only | Alternative backbone route (incl. H3 camera variant) |
| EchoWM (2026-08-24; [2608.23189](https://arxiv.org/abs/2608.23189)) | World model + audio (speech, sound) | 6-DoF + 3rd-person character | AR post-training | 720p; speed n/s [abstract-level] | not located | unreleased | Only world model we found that also generates audio |

### 2.2 Avatars, digital humans, and joint audio-video

| System (date; source) | Approach | Ctrl / beyond lip-sync | Identity / long horizon | Latency / HW (reported) | Avail. | Limitations | Relevance |
|---|---|---|---|---|---|---|---|
| LiveAvatar (2025-12-04; [2512.04677](https://arxiv.org/abs/2512.04677)) | Audio-driven 14B streaming (Wan2.2-S2V base), timestep-forcing pipeline parallelism | Au | >10,000 s drift-free claim | 45 FPS, TTFF 1.21 s, 5×H800 [cited] | Apache-2.0 | lip-sync only | Baseline A0 candidate |
| SoulX-FlashTalk (2025-12-29; [2512.23379](https://arxiv.org/abs/2512.23379)) | Streaming audio-driven avatar | Au | self-correction | 32 FPS, 0.87 s, 8×H800 [cited] | Apache-2.0 | 8 GPUs | Baseline candidate |
| Ditto (2024-11-29; [2411.19509](https://arxiv.org/abs/2411.19509)) / LivePortrait (2024-07-03; [2407.03168](https://arxiv.org/abs/2407.03168)) | Motion-space / keypoint talking head | Au + gaze/pose / retargeting | motion space | real-time; LivePortrait 12.8 ms/frame RTX 4090 [cited] | Apache-2.0 / MIT | head-only | **Cheap baseline A0** (single GPU) |
| TalkingMachines (2025-06-03; [2506.03099](https://arxiv.org/abs/2506.03099)) | Audio-driven AR DiT (Wan I2V) + audio LLM | Au | sparse causal attn | 512×512, 2 NFE, 1–2 H100 + VAE GPU [cited] | not released | – | Architecture reference |
| LPM 1.0 (2026-04-09; [2604.07823](https://arxiv.org/abs/2604.07823)) | Duplex performance model | Au + **text motion prompts**, 78 emotions | multi-granularity refs | "real-time" 480p [cited] | not released | closed | Closest to an instruction-driven persona |
| X-Streamer (2025-09-25; [2509.21574](https://arxiv.org/abs/2509.21574)) | Unified thinker + streaming AV | speech/text/video in | global identity ref; 8K ctx ≈10 min | 25 FPS 256×256 2×A100 [cited] | not released | low res; context-only memory | Counter-evidence for the hypothesis (§1.1) |
| Wan-Streamer v0.1 (2026-06-23; [2606.25041](https://arxiv.org/abs/2606.25041)) | E2E duplex AV foundation model | full duplex incl. interruptions | block-causal | ≈200 ms model-side; ≈550 ms total includes an *assumed* 350 ms network; 192p [cited] | [unverified] | 192p | E2E alternative (tightly coupled) |
| Hallo-Live (2026-04-26; [2604.23632](https://arxiv.org/abs/2604.23632)) | Streaming joint AV (from Ovi) | T → AV | – | 20.38 FPS, 0.94 s, 2×H200 [cited] | not located | – | Only streaming joint-AV with numbers |
| Vidu S2 (2026-09-10; [2609.11638](https://arxiv.org/abs/2609.11638)) | Interactive avatar with dynamic references | voice instructions, outfit/background swap | degrades > 90 s dance | 720p 25–42 FPS, HW n/s [cited] | demo only | closed | Dynamic reference = visual memory re-injection |
| **MiniMax H3** (2026-07-31; blog) | 33B joint video+audio DiT (Qwen3-VL-32B encoder) | T, first/last frame, refs; 32 kHz stereo audio | clip-level | offline: ≈85 s for 5.2 s clip on 4×H200 [cited: vLLM-Omni community] | Open weights, H3 Community License (excludes EU/UK/KR/US territories) | 4–15 s clips, no streaming | **Claimed basis of the reference agent** (unverified) |

### 2.3 Live agents, orchestration and control

| System (date; source) | Approach | Control interface | Memory | Latency / HW (reported) | Avail. | Limitations | Relevance |
|---|---|---|---|---|---|---|---|
| Moshi (2024-09-17; [2410.00037](https://arxiv.org/abs/2410.00037)) | Full-duplex speech-text LM | persona via prompt/fine-tune | context | ≈200 ms practical on L4 [cited] | Apache-2.0 code, weights | weak reasoning | Duplex front-end option |
| Qwen3-Omni (2025-09-22; [2509.17765](https://arxiv.org/abs/2509.17765)) | Thinker–Talker MoE | text prompt, tools | context | 234 ms theoretical first packet [cited] | Apache-2.0 | – | Omni front-end option |
| Pipecat / LiveKit Agents (2023– / 2026-06 turn detector) | Pipeline frameworks with VAD, turn detection, barge-in | pipeline graph | app-level | ≈1,293 ms typical cascade; 1,500 ms target [vendor: pipecat2026primer] | BSD-2 / Apache-2.0 | – | Reuse for orchestration |
| GPT-Live-1 / Gemini Live (2026-09) | Duplex front-end delegating to back-end reasoner | tools, async calls | session | [vendor] | API | closed | Validates the front/back split |
| Tavus CVI (Phoenix-4, 2026-02) | Cascaded video-call agent | persona config | "long-term memory module" | sub-600 ms [vendor, secondary] | API | closed | Closest commercial analogue |
| Neuro-sama (2022-12 debut) | LLM + TTS + Live2D/3D rig (not generated video) | chat, games | undisclosed | – | closed | – | Livestream reference class |
| PACE (2026-08-07; [2608.07631](https://arxiv.org/abs/2608.07631)) | Playback-aligned context for duplex voice | – | – | GCM accuracy 25.0→96.3% [cited] | [unverified] | audio only | Basis of contribution 3 |
| VideoDirectorGPT (2023-09-26; [2309.15091](https://arxiv.org/abs/2309.15091)), VISTA (2025-10-17; [2510.15831](https://arxiv.org/abs/2510.15831)) | LLM planning / offline generate-judge-refine | layouts, prompts | – | offline | code | offline | IR and verifier design reference |
| VideoFDB (2026-05-28; [2605.30256](https://arxiv.org/abs/2605.30256)) | Benchmark of full-duplex vision-speech agents | – | – | – | not stated | Reports that speech-to-avatar cascades "architecturally cannot produce full-duplex nonverbal responses" [cited] | Limits of a cascade (listening behavior) |
| MIDAS (2025-08; [2508.19320](https://arxiv.org/abs/2508.19320)) | LLM backbone + diffusion head for interactive digital humans | audio, pose, text conditions | context | 384×640, 480 ms chunks [cited] | not released | avatar-centric | Duplex visual behavior; tightly coupled alternative |
| StreamingVLM (2025-10-10; [2510.09608](https://arxiv.org/abs/2510.09608)) | Infinite-stream VLM with attention-sink KV | text query | streaming KV | up to 8 FPS on 1×H100 [cited] | MIT (code) | cost per verified chunk | Online compliance-monitor candidate. Sets monitor cost |
| EchoChain (2026-04-08; [2604.16456](https://arxiv.org/abs/2604.16456)) | Interruption benchmark (speech) | – | – | no system > 50% pass [cited] | – | speech only | Evaluation template |

### 2.4 Memory systems and evaluation

In the Latency/HW column, "not stated" means the source gives no figure. None of these was measured by us.

| System / benchmark (date; URL) | Approach / what it measures | Control interface | Write–update–forget | Latency / HW (reported) | Avail. | Limitation for us | Relevance |
|---|---|---|---|---|---|---|---|
| MemGPT/Letta (2023-10-12; [2310.08560](https://arxiv.org/abs/2310.08560)) | OS-style memory tiers | LLM function calls self-edit memory | agent-initiated, hot path | not stated (adds LLM calls per turn) | Apache-2.0 | DMR 93.4% (GPT-4 Turbo) [cited]; DMR is saturated | Storage tiers |
| Generative Agents (2023-04-07; [2304.03442](https://arxiv.org/abs/2304.03442)) | Memory stream scored by recency, importance and relevance; reflection | retrieval function in the agent loop | write everything; reflect periodically | not stated | code | documents "hallucinated embellishments" [cited] | Persona memory template; false-memory risk |
| Mem0 (2025-04-28; [2504.19413](https://arxiv.org/abs/2504.19413)) | Extract, then ADD/UPDATE/DELETE/NOOP | SDK/API add/search | synchronous extraction; LLM-judged delete | p95 1.44 s vs 17.12 s full context [cited] | Apache-2.0 | LoCoMo: the full-context baseline 72.90 beats Mem0 66.88 [cited] | Simple baselines must be reported |
| Zep/Graphiti (2025-01-20; [2501.13956](https://arxiv.org/abs/2501.13956)) | Bi-temporal knowledge graph; invalidation keeps history | API episodes and search | ingestion → edges | "−90% latency" on LongMemEval [cited, abstract] | Apache-2.0 | history conflicts with erasure | Provenance and time model |
| LightMem (2025-10-21; [2510.18866](https://arxiv.org/abs/2510.18866)) | Sensory filter → short-term → sleep-time long-term memory | library | offline consolidation | 38× / 20.9× fewer tokens [cited] | code | – | Write policy under a latency budget |
| LongMemEval (2024-10-14; [2410.10813](https://arxiv.org/abs/2410.10813); ICLR 2025) | Extraction, multi-session, temporal, knowledge-update, abstention | – (benchmark) | – | – | GitHub | text only | **Primary text-memory benchmark** |
| MemoryAgentBench (2025-07-07; [2507.05257](https://arxiv.org/abs/2507.05257)) | Retrieval, test-time learning, long-range, **selective forgetting** | – | – | – | GitHub | text only | Correction and forgetting (SF multi-hop ≤ 28%) |
| MemoryArena (2026-02; he2026memoryarena, ICML 2026) | Memory that must drive later actions | – | – | – | yes | agentic, not persona | Action-driving memory |
| GateMem (2026-06-17; [2606.18829](https://arxiv.org/abs/2606.18829)) | Multi-principal access control + deletion | – | – | – | GitHub | preprint | Public/private template |
| K-Bench (2026-09-11; [2609.12808](https://arxiv.org/abs/2609.12808)); Execution-state unlearning (2026-09-04; [2609.04875](https://arxiv.org/abs/2609.04875)) | Leakage after deletion across agent channels | – | – | – | not stated | preprints | Deletion verification (22–86% leak) |
| MINJA (2025-03-05; [2503.03704](https://arxiv.org/abs/2503.03704)) | Query-only memory injection attack | chat queries | – | – | not stated | – | Threat model for viewer poisoning |
| LiViBench (2026; wang2026livibench) | Understanding livestream video and comments | – | – | – | not stated | understanding, not memory | Livestream setting |
| WorldMem (2025-04-16; [2504.12369](https://arxiv.org/abs/2504.12369)), Context-as-Memory (2025-06-03; [2506.03141](https://arxiv.org/abs/2506.03141)) | Frame memory indexed by pose, for world revisits | camera pose | per rollout | not stated | code | scene memory, not user memory | Keep distinct from user memory |
| WBench (2026-05-25; [2605.25874](https://arxiv.org/abs/2605.25874)), WorldMark (2026-04-23; [2604.21686](https://arxiv.org/abs/2604.21686)) | World-model interaction: subject actions, event editing, perspectives; response latency in generated frames | – | – | – | yes | offline; no memory or speech | Reuse for the video-control part of the evaluation |
| Full-Duplex-Bench v1/v2 (2025-03-06; [2503.04721](https://arxiv.org/abs/2503.04721); 2025-10-09; [2510.07838](https://arxiv.org/abs/2510.07838)) | Pause, backchannel, turn-taking, interruption; multi-turn correction | – | – | – | GitHub | speech only | Voice evaluation |
| Multi-IF (2024-10-21; [2410.15553](https://arxiv.org/abs/2410.15553)) | Multi-turn instruction following | – | – | – | yes | text only | Instruction following (o1-preview drops 0.877 → 0.707 from turn 1 to 3) |

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

## 4. Implications for the proposal (revised after CP2)

1. **Backbone fit.** LingBot-World 2.0 is a camera-controlled *world* model, not an avatar model.
   - Verified mid-stream interaction: SE(3) camera only. This comes from reading the code; a prompt interaction
     sent over the WS has **not yet been executed**. Request-scoped camera scripts also exist.
   - Character actions need prompt switching on the streaming path (engineering class C). Whether prompts actually
     produce the actions with this checkpoint is class B.
   - *Native* LingBot lip, face and audio conditioning is class D. Showing a speaking persona through an **external**
     audio-driven avatar path is engineering, not class D.
2. **The persona must stay visible and recognizably speaking** (owner goal; CP2 blocking finding 2). An explorer with
   voice-over only is rejected as the primary demo. The proposal instead uses a **dual-shot live persona**:
   - a lip-synced close-up "presenter" shot from an external audio-driven avatar model;
   - a "world" shot in which LingBot-World renders the same persona in a controllable scene;
   - a shot track in the controller that switches between them at chunk boundaries (a broadcast-style grammar).

   Where the two renderings disagree (identity, costume, lighting, continuity), the protocol measures and reports it.
   Compositing the avatar into the LingBot scene is an alternative, evaluated as an ablation.
3. **The scientific contribution is not the integration.**
   - Central: capability-grounded closed-loop control with deadline-bounded visual verification (contribution 1).
   - Measurement protocol: wall-clock TVC.
   - Secondary: display-aligned state, and provenance- and scope-safe memory evaluated across modalities.
4. **Hardware risk is first-order.**
   - All real-time LingBot numbers come from specific H200 multi-GPU stacks.
   - Local cards report as "L20X" (Ada, CC 8.9, 143,771 MiB), and their identity is unresolved.
   - A prior local run had FlashAttention unavailable.
   - Milestone M0 must measure cadence, TTFC and a real WS prompt-interaction attempt before any latency target is
     treated as achievable.

===== FILE: docs/reviews/cp4_ev_code_excerpts.md =====
# Additional code excerpts, vllm-omni @ 7b4dc7633bde8642f0c05f77bd018751541df404

## vllm_omni/diffusion/interaction/modality_handlers/camera.py:40-50
```python
   40      """Canonical absolute camera pose used by the shared timeline.
   41  
   42      Coordinates follow Unity semantics: ``+X`` right, ``+Y`` up,
   43      ``+Z`` forward. Session start is the identity transform;
   44      ``target`` poses are relative to that origin.
   45      """
   46  
   47      translation: Vec3 = (0.0, 0.0, 0.0)
   48      rotation: Quat = _IDENTITY_QUAT
   49  
   50      @classmethod
```

## vllm_omni/diffusion/interaction/modality_handlers/camera.py:100-112
```python
  100      # Since a camera session is not lazily initialized, use this field to mark that a client enqueue is ever received.
  101      has_received_input: bool = False
  102  
  103  
  104  class SE3DeltaCameraHandler(InteractionHandler):
  105      """Generic camera timeline that samples absolute poses per frame.
  106  
  107      * ``mode=target``: lerp toward an absolute pose (relative to session start).
  108      * ``mode=velocity``: hold a structural SE3 delta until replaced.
  109  
  110      ``received_at`` is resolved on the media grid (``num_media_frames``/``fps``), then mapped onto latent steps.
  111      Later integration and ``last_absolute_poses`` aligns with ``num_latent_frames``.
  112      """
```

## vllm_omni/diffusion/interaction/modality_handlers/camera.py:255-360
```python
  255          fps: float,
  256          num_latent_frames: int,
  257          boundary_at: float,
  258      ) -> tuple[list[CameraPose], list[str], list[str], list[str]]:
  259          """Sample absolute poses for this chunk under target/velocity semantics."""
  260          num_media_frames = max(int(num_media_frames), 1)
  261          num_latent_frames = max(int(num_latent_frames), 1)
  262          pending = list(session.pending_events)
  263          session.pending_events.clear()
  264  
  265          by_latent: dict[int, list[QueuedCameraEvent]] = {}
  266          for event in pending:
  267              media_frame = resolve_event_frame_offset(
  268                  received_at=event.received_at,
  269                  previous_boundary_at=session.last_boundary_at,
  270                  num_frames=num_media_frames,
  271                  fps=fps,
  272              )
  273              latent_idx = _media_frame_to_latent(
  274                  media_frame,
  275                  num_media_frames=num_media_frames,
  276                  num_latent_frames=num_latent_frames,
  277              )
  278              by_latent.setdefault(latent_idx, []).append(event)
  279          for events in by_latent.values():
  280              events.sort(key=lambda item: item.received_at)
  281  
  282          started: list[str] = []
  283          completed: list[str] = []
  284          seen_completed: set[str] = set()
  285          poses: list[CameraPose] = []
  286  
  287          def _mark_completed(event_id: str) -> None:
  288              if event_id not in seen_completed:
  289                  seen_completed.add(event_id)
  290                  completed.append(event_id)
  291  
  292          for latent_idx in range(num_latent_frames):
  293              for event in by_latent.get(latent_idx, []):
  294                  started.append(event.event_id)
  295                  cancelled_id = self._activate_event(session, event)
  296                  if cancelled_id is not None:
  297                      _mark_completed(cancelled_id)
  298              just_completed = self._step_one_frame(session, num_latent_frames)
  299              poses.append(session.current_pose.clone())
  300              if just_completed is not None:
  301                  _mark_completed(just_completed)
  302  
  303          active: list[str] = []
  304          if session.active_event is not None:
  305              active.append(session.active_event.event_id)
  306  
  307          session.last_boundary_at = boundary_at
  308          return poses, started, active, completed
  309  
  310      def _activate_event(self, session: CameraSession, event: QueuedCameraEvent) -> str | None:
  311          """Activate ``event``, returning the event_id cancelled by this replacement if any."""
  312          cancelled_id: str | None = None
  313          if session.active_event is not None and session.active_event.event_id != event.event_id:
  314              cancelled_id = session.active_event.event_id
  315  
  316          event.elapsed_transition_chunks = 0.0
  317          event.elapsed_transition_frames = 0
  318          session.active_event = event
  319          if event.mode == "target":
  320              session.target_source = session.current_pose.clone()
  321          else:
  322              session.target_source = None
  323          return cancelled_id
  324  
  325      def _clear_active_target(self, session: CameraSession) -> str:
  326          """Snap to the target pose, clear the active target track, and return its event_id."""
  327          assert session.active_event is not None and session.active_event.mode == "target"
  328          event = session.active_event
  329          event_id = event.event_id
  330          session.current_pose = event.pose.clone()
  331          session.active_event = None
  332          session.target_source = None
  333          return event_id
  334  
  335      def _step_one_frame(self, session: CameraSession, total_num_frames_this_chunk: int) -> str | None:
  336          """Advance the active camera command by one frame."""
  337          event = session.active_event
  338          if event is None:
  339              return None
  340  
  341          if event.mode == "target":
  342              duration = event.transition_chunks
  343              source = session.target_source or session.current_pose
  344              target = event.pose
  345              if duration <= 0:
  346                  return self._clear_active_target(session)
  347  
  348              total_frames = max(1, int(round(duration * float(total_num_frames_this_chunk))))
  349              event.elapsed_transition_frames += 1
  350              event.elapsed_transition_chunks = event.elapsed_transition_frames / float(total_num_frames_this_chunk)
  351              alpha = min(1.0, event.elapsed_transition_frames / float(total_frames))
  352              session.current_pose = _lerp_pose(source, target, alpha)
  353              if event.elapsed_transition_frames >= total_frames:
  354                  return self._clear_active_target(session)
  355              return None
  356  
  357          # Velocity: apply the held structural SE3 delta once per frame.
  358          session.current_pose = _compose_pose(session.current_pose, event.pose)
  359          return None
  360  
```

## serving_video_output_stream.py:10-30 and 75-92 (ping semantics)
```python
   10              "interaction": {
   11                  "event_id": "...",
   12                  "event": {"prompt": "..."},
   13                  "transition_chunks": (optional, integer),
   14              },
   15          }
   16          {"type": "session.stop"}
   17          {"type": "session.ping"}  # optional; refreshes stall clock
   18  
   19      Server -> Client:
   20          {"type": "video.start", "request_id": "...", "config": {...}, "format": "m4s"}
   21          {"type": "video.chunk_metadata", ...}
   22          <binary frame: fragmented MP4 bytes>
   23          {"type": "session.interaction.queued", "request_id": "...", "event_id": "..."}
   24          {"type": "session.done", ...}
   25          {"type": "session.pong"}  # reply to session.ping
   26          {"type": "error", "message": "..."}
   27  """
   28  
   29  from __future__ import annotations
   30  
   75  _MAX_CONTROL_MESSAGE_SIZE = 128 * 1024
   76  
   77  
   78  class _SessionProgress:
   79      """Tracks last server-side progress for stall-timeout enforcement."""
   80  
   81      def __init__(self) -> None:
   82          self._last_at = time.monotonic()
   83  
   84      def touch(self) -> None:
   85          self._last_at = time.monotonic()
   86  
   87      def stalled_for(self, stall_timeout: float) -> bool:
   88          return time.monotonic() - self._last_at > stall_timeout
   89  
   90  
   91  class OmniStreamingVideoOutputHandler:
   92      """Handles `/v1/realtime/video` sessions for generated video output."""
```
