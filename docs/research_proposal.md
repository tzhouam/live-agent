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

**Testability (CP4 finding 1).** Every system we can build here includes an external LLM controller, so a *strict*
test of H-core needs a system with no external layer at all. The only candidate is an end-to-end model of the A3(b)
class, run as-is. We run that test only if such weights become available. Otherwise H-core is examined through
**H-core-abl**: removing the persistent memory service, the capability manifest and the monitor from A2 (comparator
A1−mem, §7.4) causes the memory and compliance probes to fail. H-core-abl is weaker than H-core, and we report it
as such. The operational test is in §7.4.

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

**First demo, defined as a measured configuration.** The first demo uses a configuration that (i) passes M0
*throughput qualification* and then (ii) passes the *stream-stability acceptance* soak test (§6.4). Its
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
| RQ3 | Does provenance-typed, scope-separated memory reduce false memories and leakage without hurting recall? | **H3a:** a lower false-user-fact rate than (i) full-history context and (ii) Mem0-style untyped extraction, at non-inferior recall (margin 5 pp). **H3b:** for the **utterance channel** (the persona's response text and its TTS speech, checked on the response text and on an ASR transcript of the synthesized audio), the user-level cross-scope leak rate has a 95% upper bound below 1% (≥ 300 independent simulated users), while baselines leak (> 0). The visual channel is reported descriptively, with no threshold. **H3c:** after deletion, multi-channel leak rate below 5% | H3a: not lower, or recall inferior beyond the margin. H3b: any utterance-channel leak observed (the bound then exceeds 1%), or baselines do not leak either. H3c: post-deletion leak ≥ 5% |
| RQ4 | Is a world model needed for this experience? This tests the owner's hypothesis in both directions | A0 and A2 share the same LLMs, memory service, TTS and avatar renderer; only the world shot and its controller differ. A0 cannot perform scene tasks by construction, so it is **not** compared with A2 on scene-task success. The comparisons are: **H4a:** in mixed sessions, users prefer A2 over **A0+clips** (A0 plus pre-rendered world clips cut in by the same shot track: the clip-scheduling alternative) on overall MOS and on pairwise preference. **H4b:** on talk-only sessions, A0 is non-inferior to A2 on MOS, with a margin of 0.5 on a 5-point scale | H4a: no preference (CI includes 0). H4b: the lower CI bound falls below −0.5. Either outcome is informative |
| RQ5 | Does anchoring interaction state to *displayed* frames improve handling of corrections after interruptions? | **H5:** display-aligned context raises referent-resolution accuracy on video-referent corrections ("no, the *other* path") over generation-aligned context | No improvement (CI includes 0) |
| RQ6 | Can the persona remain consistent across shots and over long sessions? | **H6:** (i) within each shot, identity similarity to the reference stays above a per-shot threshold calibrated against human same/different judgments; (ii) across shots, human raters judge the two renderings to be the same person in ≥ 80% of sampled cut pairs; (iii) behavioural and scene-state probes stay consistent over 30 min | More than 20% of windows fall below threshold, or cross-shot agreement is below 80% |

RQ1 and RQ2 are primary; RQ3–RQ6 are secondary. We report all outcomes, including null results.

---

## 5. Candidate architectures and selection

### 5.1 Candidates

Figure: `docs/figures/fig4_candidate_architectures.mmd`.

**Shared substrate.** To avoid confounds (CP3 finding 6):
- **A0, A1 and A2** share the LLMs, ASR, TTS, avatar renderer and memory service. The exception is E3, where memory
  itself is the factor.
- **A1 and A2 only** also share the **generator control substrate**. A0 has no world generator.
- The generator control substrate is:
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
  1. **Server gate (C4):** the stepwise runner starts AR block $n+L+1$ only when the client acknowledges the
     **presentation start** (first displayed frame) of chunk $n$.
     - At that moment, chunk $n$ and the $L$ queued chunks $n+1..n+L$ cover $(L+1)P$ of playback.
     - A sustained stream needs two conditions:
       - **Throughput:** mean $T + \delta < P$. Otherwise any finite buffer eventually empties.
       - **Jitter tolerance:** individual $T + \delta \le (L+1)P$.
     - This needs a change in the engine or runner loop, and its feasibility is to be established in M1.
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
  - (v) generation work that references it, handled according to its state:
    - *unsent* IR items and prompts are dropped;
    - *sent* events cannot be withdrawn, so they are superseded by neutral controls;
    - if the erased item is in the active world-generator state (prompt, text K/V, or the scene being rendered), the
      **world session is ended and restarted** from a canon frame (C5). This is the only way the API lets us clear
      generator state;
    - media already *presented* cannot be un-presented;
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

**Regime G** (gated at presentation start with look-ahead $L$). It is stall-free if mean $T + \delta < P$
(throughput) **and** every $T + \delta \le (L+1)P$ (jitter).
- In steady state, a generation starts every $P$.
- An event waits for the next generation start: $W \approx U(0, P)$.
- The chunk it lands in, $n+L+1$, begins presentation $(L+1)P$ after that generation start.
- So TVC ≈ $A + U(0,P) + (L+1)P + I$.
- **Trade-off.**
  - $L = 0$ gives the lowest latency, but stalls whenever $T + \delta > P$, e.g. on jitter.
  - $L = 1$ tolerates jitter up to $2P$, but adds $P$ of latency.
  - Both are measured (H2c).

**Illustrative values in regime G** (4-GPU, upstream-reproduced $T = 0.549$ s, 16 fps, $P = 0.75$ s):

| Term | $L=0$ median-ish | $L=1$ median-ish | $L=1$ upper-ish | Basis |
|---|---|---|---|---|
| $A$ | 0.45 s | 0.45 s | 0.8 s | [target]; endpointing 200–300 ms [cited: pipecat2026primer] |
| $W$ | 0.375 s | 0.375 s | 0.71 s | $U(0, 0.75)$ [derived] |
| $(L+1)P$ | 0.75 s | 1.5 s | 1.5 s | [derived] |
| $I$ (camera) | 0.1 s | 0.1 s | 0.4 s | [estimate]; measured in E1 |
| **Camera TVC** | **≈1.7 s** | **≈2.4 s** | **≈3.4 s** | Column sums, **not quantiles**. Illustrative only |

**Two-stage qualification.**

*Stage 1 — M0 throughput qualification.* This selects *candidate* configurations.
- A configuration qualifies for $L$ only if both hold over ≥ 3 × 40 chunks, including warm-up outliers:
  - the **measured mean** $T + \delta$ is below $0.9P$ (throughput, with margin);
  - $T + \delta \le (L+1)P$ for ≥ 99% of chunks (jitter).
- A queue simulation driven by the measured cadence trace, with jitter and stalls, must also show a bounded backlog.

A 120-chunk M0 trace cannot establish a stall rate of one per 10 minutes, because at 16 fps even 1% late chunks
could mean about eight stalls in 10 minutes. Stage 1 therefore qualifies throughput only.

*Stage 2 — stream-stability acceptance (in M1).* A candidate configuration becomes "real-time" for the demo and
for E2/E4 only if:
- a live **soak test** of ≥ 3 × 30 min [target] with the chosen $L$ meets the §8 stream-stability target
  (≤ 1 stall per 10 min, with the observed rate and upper bound reported);
- the trace-driven simulation based on the soak-test cadence agrees with that result.

**2×H200-class** ($T \approx 0.89$ s [cited]):
- At 16 fps, $T > P = 0.75$ s, so the stream stalls.
- At 12 fps ($P = 1.0$ s), mean $T + \delta ≈ 0.94$ s. That fails the 0.9P throughput margin, so this configuration
  is marginal and qualifies only if measured cadence is better than reported.
  - If it qualifies with $L = 0$: TVC ≈ $A + U(0,1.0) + 1.0 + I$ ≈ 2.0 s median-ish.
  - With $L = 1$: ≈ 3.0 s.

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
  `benchmarks/lingbot_world/benchmark_lingbot_world_realtime.py`: 3 warm sessions × 40 chunks per configuration [target].
- Record `torch.cuda.get_device_capability()` and the attention backend.
- Run the WS contract test (§6.1). It includes one `session.interaction` with `event.prompt`, which settles the
  contradiction between the registry and the benchmark code.
- Measure generated, received, decoded and presented queue depths without pacing. Check whether transport
  backpressure pauses the engine.

**Outputs.**
- Cadence $T$ and TTFC, as p50/p95 with bootstrap CIs.
- Stall regime.
- Observed prompt-interaction behavior.

**Go/no-go rule.** Proceed to real-time world-shot experiments only in configurations that pass both stages of
§6.4: M0 throughput qualification, then the M1 stream-stability soak test. Otherwise report the regime and use the fallback
designs of §6.4.

### 7.1 E1: capability calibration (builds the manifest; RQ2)

**Controls.**
All counts in E1 are [target].
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

**Task suite.** Scripted tasks, each spoken by a TTS-simulated user from a fixed script, for reproducibility.
All counts are [target].
- **Committed subset: 80 tasks** (camera/viewpoint, shot cuts, speech):
  - 30 single-step instructions;
  - 25 multi-step instructions, for example "turn toward the lake, move forward, then stop and look left";
  - 25 interaction-dynamics tasks: a mid-execution correction, a goal change, a barge-in during speech, or a
    referent correction against displayed content (RQ5).
- **Conditional subset: 20 tasks** (scene and character events). It runs only if C1 and E1 qualify, and it is always
  analysed separately.

Task templates are adapted from EchoChain, Full-Duplex-Bench v2 and WBench [cited].

**Outcome judgement, independent of the online monitor (CP4 finding 2).**
- The primary outcome for the A2-vs-A1 contrast is **blinded human adjudication of every trial**:
  - 2 raters who do not see the condition, the IR, the ack or the monitor verdict;
  - a third rater resolves disagreements;
  - κ is reported.
- Ablation contrasts use an **offline evaluation judge** that differs from the online monitor. It is an ensemble of
  full-clip VLM judges plus the geometric estimator run offline at full frame rate. It is validated on a ≥ 20%
  human-labelled stratified sample of each condition, and κ is reported per condition to expose condition-dependent
  judge error.
- **Locked evaluation set.** Evaluation scenes, tasks, prompts, deadlines and compiler thresholds are frozen and
  pre-registered after E1 and the pilot. They are disjoint from calibration scenes and seeds.

**Outcome rules for each instruction.**

| Case | Instruction-level success | TVC |
|---|---|---|
| Compliant within $D$ | success | observed time |
| Refused or degraded by the compiler | failure | censored at $D$ |
| Superseded by the user before $D$ | excluded from success; counted in a separate "superseded" tally. The *final* intent is scored | final intent scored from its own utterance |
| Human raters answer "cannot tell" | failure in the primary analysis; excluded in a sensitivity analysis | censored at $D$ |
| Never compliant | failure | censored at $D$ |

**Conditions.**
- A1: prompt-only open loop.
- A2−verify: capability-aware open loop.
- A2−manifest: a verifier with an uncalibrated, "everything allowed" manifest.
- A2: full system.
- A2+unpaced: no look-ahead bound (RQ2c).
- A2−display-alignment: context aligned to generation (RQ5).

**Metrics.**
- **Instruction-level success.** The denominator is *all scored intents*: every instruction except intermediate
  intents that the user superseded before their deadline. For those, the *final* intent is scored instead. Refusals
  and degradations count as failures. The number of superseded intents is reported separately.
- **Refusal/degradation rate.**
- **OCR (conditional).** Among instructions that were executed, the fraction judged compliant within the deadline
  $D$ on displayed frames.
- Task success for multi-step tasks: all steps compliant, in order.
- **FCR** = (completion claims contradicted by the judge) / (completion claims made).
- **Claim coverage** = (completion claims made) / (instructions judged compliant). Reported alongside FCR, so that a
  system cannot lower its FCR simply by never claiming completion.
- TVC: deadline success, Kaplan–Meier median, and p95 only when identifiable (§8).
- Recovery time after a correction.
- Referent-resolution accuracy.

**Design and analysis.**
- Within-task paired design: each task × 5 seeds × each condition [target]. Tasks are the clustering unit.
- Mixed-effects logistic regression: condition as a fixed effect; task and seed as random effects.
- Paired bootstrap 95% CIs for differences.
- Holm correction across the primary contrasts (A2 vs A1 on instruction-level success and on FCR).

**Sample size and power [estimate]; tasks are clustered.**
- *Pilot.* Before any full run, a 60-trial pilot estimates the intra-task correlation (ICC). Power for the main runs is
  then computed by simulating the mixed model with that ICC.
- *Planning assumption.* ICC ≈ 0.3 with 5 seeds gives a design effect ≈ 2.2. We therefore plan **80 committed-subset
  tasks** × 5 seeds (400 trials per condition). This targets 80% power to detect a 12–15 pp difference in
  instruction-level success at α = 0.05.
- *FCR and ablations.* These are reported with task-clustered bootstrap CIs and are **not** individually powered. We
  state the minimum detectable effect from the pilot variance.

### 7.3 E3: memory (RQ3)

**(a) Component benchmarks.**
- LongMemEval_S: extraction, temporal reasoning, knowledge update, abstention.
- MemoryAgentBench, selective-forgetting split.
- A small GateMem-style scoping suite.

All are run on the memory service with a fixed LLM [cited benchmarks].

**(b) Live-persona memory protocol (new).**
- 20 simulated users × 6 sessions each [target], with scripted life facts, preferences, corrections and erasure requests.
- Persona-generated distractors: for example, the persona says "I love snow", which must not become a user fact.
- **Echo probes:**
  - the user repeats a persona invention as if it were about themselves;
  - the persona paraphrases a real user fact, and the user later refers back to it.
- **Fresh-public-session probe:** a Mode 2 session starts immediately after a private session.
- Mode 2 sessions with 10 scripted viewers [target]. 3 of them attempt MINJA-style poisoning and private-fact elicitation.
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

**Analysis.**
- Per-user clustered bootstrap CIs. Non-inferiority test on recall with a 5 pp margin.
- **Rare-event claims (CP4 finding 4).**
  - A "< 1%" leak claim needs a 95% upper bound below 1%. With zero leaks observed, that takes ≥ 300 independent
    opportunities (rule of three).
  - **Independence.** Opportunities from the same user are correlated, so the "< 1%" claim is made at the **user
    level**. It uses ≥ 300 independent simulated users [target]. Each user has one private session with planted
    facts, followed by a fresh public session. Simulated users are scripted and cheap at the memory+LLM level.
  - This user-level claim covers **only the utterance channel**: the persona's response text, plus an ASR transcript
    of its synthesized TTS audio. Both can be produced at scale without the world generator.
  - Two channels need the full rendering stack: **on-screen text** (OCR of the displayed stream) and **generated
    visuals**. They are tested on a smaller subset (≈ 30 users [target]). For them we report only the observed rate
    and a cluster-robust upper bound, and make **no** "< 1%" claim.
  - The main 20-user × 6-session protocol still yields within-user, longitudinal leak and deletion data, reported with
    clustered bootstrap CIs.

### 7.4 E4: long-horizon consistency and the H-core test (RQ6, H-core)

**Long sessions.** 10 sessions of 30 min each [target], in Mode 1 with scripted interaction.

**Metrics.**
- Persona identity:
  - presenter shot: face embedding (ArcFace [cited]) against the reference;
  - world shot: a person re-identification embedding.
  - These are **per-shot scores, never compared with each other**. Each shot's threshold is calibrated against
    human same/different judgments on a labelled sample.
  - Cross-shot identity uses **human 2AFC judgments** on sampled cut pairs.
- Behavioural and scene-state consistency: persona-canon probes; props and scene-state probes after cuts and
  restarts; consistency between what the persona says it did and what was displayed.
- Persona text consistency: DNLI/PICon-style contradiction probes [cited].
- Stream stability: stall rate, seam artefacts at chunk boundaries (the stateful streaming decoder is noted as partial
  in the recipe), and session-restart seams (C5).

**H-core test.**
- A2 and **A1−mem** each run through ≥ 3 sessions separated by restarts.
  - A1−mem is A1 with the memory service removed. **No state carries over between sessions**: each session starts
    with a fresh context, holding only the persona canon.
  - It removes the external *memory* layer, but it still has an external controller. It therefore tests H-core-abl,
    not strict H-core (§1.2).
- The same planted facts, corrections, deletions and visual-recall requests are used for both.
- **Strict H-core:** if an end-to-end system (A3b-class) becomes available with weights, it is run as-is, with no
  wrapper, through the same protocol. It refutes H-core if it meets the §8 memory and compliance thresholds.

### 7.5 E5: human evaluation (RQ4 and UX)

**Design.** Within-subject, counterbalanced. Pilot N = 12, then a main study with N = 24 if the pilot supports it
[estimate]. Sessions last 15 min per condition [target].

**Measures.**
- MOS for overall quality.
- SUS.
- Godspeed (anthropomorphism, likeability, perceived intelligence).
- Social presence.
- Perceived responsiveness.
- **Pairwise preference** (H4a): after each pair of conditions, a forced choice ("which would you rather talk to
  again?"), plus a strength rating.
- Task success on 5 scene-grounded and 5 talk-only tasks.

**Analysis.** Mixed models; Wilcoxon signed-rank for Likert items. For pairwise preference: a Bradley–Terry model
with participant random effects, plus an exact sign test for A2 vs A0+clips. We report effect sizes with CIs.

**Sample size [estimate].** For H4b non-inferiority (margin 0.5 MOS, assumed SD of paired differences 0.8, one-sided
α = 0.05, power 0.8), n ≈ 16. N = 24 therefore leaves room for drop-outs. The assumptions are re-estimated in the pilot.

Conditions: A0, A0+clips, A2. A1 is included only if session time allows.

**Governance.** Pre-registration before the main study [cited: nosek2018preregistration]. Informed consent. No
public broadcast.

### 7.6 E6: private livestream (Mode 2)

A closed test stream with scripted viewers, run for 2 h × 3 runs [target]. Metrics:
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
| Instruction-level success (primary for H1a) | Denominator = all scored intents (§7.2 outcome rules: user-superseded intermediate intents are replaced by their final intent). Refusals and degradations count as failures | A2 − A1 ≥ +10 pp, with the paired CI excluding 0 |
| OCR (conditional) | Among executed instructions, judged compliant on displayed frames within $D$ ($D$ = 5 s camera, 8 s events) | Reported with the refusal/degradation rate. Not used alone |
| FCR | (Completion claims contradicted by human adjudication) / (completion claims made). Always reported with claim coverage = claims / compliant instructions | A2 ≤ 5% and below A1, CI excluding 0 (H1b). Claim coverage for A2 ≥ 70% |
| Multi-step task success | All steps compliant, in order | Reported; A2 > A1 |
| TVC / time to first correctly conditioned visual response (TFCV), camera | From the user's end-of-utterance (VAD endpoint on the shared presentation timeline) to the first presented frame, in any shot, that human adjudication judges compliant. Failures are censored at $D$ = 5 s | Deadline success ≥ 90% within $D$. Kaplan–Meier median ≤ 2.5 s. The p95 is reported only if the KM curve reaches 0.95 before $D$ (deadline success ≥ 95%); otherwise the restricted mean time with horizon $D$ is reported |
| TVC (events, post-C1) | Same, for scene/character events | Deadline success within 8 s and median reported. Targets are set after E1 |
| Time to first speech | End of user utterance → first audible persona audio (fillers included), on the shared presentation timeline | World-shot start: p50 ≤ 0.8 s, p95 ≤ 1.5 s. Presenter-shot start: p50 ≤ 1.1 s, p95 ≤ 1.8 s |
| Time to first meaningful response (TFMR) | End of user utterance → start of the first presented audio segment whose transcript *addresses the request*. Fillers and backchannels are excluded; judged by two blinded raters against a rubric | p50 ≤ 1.5 s, p95 ≤ 2.5 s |
| End-to-end latency distribution | Per-instruction TFMR and TFCV, as p50/p95 over all instructions in E2 (censored per the TVC rule) | Reported by condition and configuration |
| Barge-in stop | User speech onset → persona audio stops | p95 ≤ 250 ms |
| Recovery after correction | Correction utterance → first compliant frame of the corrected intent | p50 ≤ TVC p50 + 1 chunk |
| Memory recall | Correct answers on planted-fact probes | Non-inferior to the best baseline (margin 5 pp) |
| False-user-fact rate | Stored or asserted user facts not stated by the user | ≤ 2% and below baselines |
| Post-deletion leak | Any channel reveals a deleted item | ≤ 5% (vs K-Bench-style baselines) |
| Cross-scope leak | Private item surfaces in Mode 2, or across users | Utterance channel (response text + ASR of TTS audio): 95% upper bound < 1% at the user level over ≥ 300 independent simulated users (0 leaks observed; rule of three). On-screen text (OCR) and generated visuals: observed rate plus a cluster-robust bound on ≈ 30 users, with no threshold claim |
| Identity consistency | Per shot: embedding similarity to the reference per 30 s window (face for the presenter; re-ID for the world shot). Thresholds are calibrated on human same/different labels. Cross-shot: human 2AFC on cut pairs | ≥ 80% of windows pass per shot; ≥ 80% cross-shot "same person" |
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
| **M1** (≈3 weeks) | C1–C4 extensions (upstream-able where possible); stream-stability soak test (§6.4, stage 2); avatar model bake-off (license, latency, identity); E1 calibration | Manifest v1 with CIs; judge validated (κ) |
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

GPT-6 Sol reviewed this proposal through Codex at all four mandatory checkpoints, with CP4 re-run in rounds.
`docs/codex_reviews.md` records every round, its verdict, each finding's disposition, and any open disagreements.
