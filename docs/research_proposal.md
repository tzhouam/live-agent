# Capability-Grounded Closed-Loop Control for a Real-Time, Personalized Live Agent

**Research proposal: live-agent project, Phase 1**

*Draft v0.9, 2026-09-25. Review status is in §14 and `docs/codex_reviews.md`.*

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

Milestone M0 is a one-day hardware and backbone characterization. It gates every latency target, because all
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
- **World shot.** LingBot-World renders the same persona, from the same reference image, in a scene: third-person
  view, walking, looking around. The camera follows instructions, and scene or character events are added once the
  prompt-interaction extension exists (§6.3).

A **shot track** in the controller cuts between the two at chunk boundaries, as a broadcast director would.

**Mode 1 (primary acceptance scenario): private 1:1 session.** A user talks to the persona by voice. Typical requests:
- "Show me the lake village again, the one from last time." This is cross-session visual memory.
- "Walk slower, I like the calm pace." A preference that should persist.
- "Turn left… no, the other way!" A correction and interruption.
- "What did I tell you about my sister?" Episodic recall.
- "Forget that." Deletion.

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
- **E1.** A prompt-interaction path on vLLM-Omni's stepwise LingBot pipeline (registry and text K/V refresh), plus WS
  reset and session extension, and server-side chunk timestamps.
- **E2.** Client presentation timestamps and a bounded look-ahead playback policy.
- **E3.** Dual-shot rendering with a shared persona reference and an audio master clock.
- **E4.** Voice pipeline (VAD, ASR, turn-taking, streaming TTS) built from existing frameworks.

**Longer-term research (not needed for the first demo):** a character-centric live world model that conditions
LingBot-World on speech audio and behavior tokens (A3, §5.1). It requires training and is not claimed here.

---

## 4. Research questions and falsifiable hypotheses

The success thresholds are in §8. All thresholds are **[target]**.

| RQ | Question | Hypothesis | Falsified if |
|---|---|---|---|
| RQ1 | Does capability-grounded closed-loop control improve *observable* compliance over open-loop LLM control? | **H1a:** A2 has a higher observed compliance rate (OCR) than A1 on the task suite. **H1b:** A2 has a lower false-completion-claim rate (FCR) than A1. **H1c:** each component (manifest, verifier) contributes: A2 > A2−verify and A2 > A2−manifest | The 95% CI of the paired difference A2−A1 in OCR includes 0 or is negative. FCR does not fall. The ablations show no drop |
| RQ2 | What determines wall-clock TVC for a chunked AR world model, and can control policy reduce it? | **H2a:** camera TVC is predicted within ±1 chunk period by $W+T+\delta+Q+I$ (§6.4) given measured $T$ and backlog $Q$. **H2b:** prompt-driven events have additional visual inertia $I \ge 1$ chunk. **H2c:** bounded look-ahead (≤ 1 chunk) reduces TVC p95 relative to unpaced streaming, at a cost in stall rate that we measure | The model mispredicts the median by more than 1 chunk. Inertia is ≈ 0. Pacing does not reduce p95 |
| RQ3 | Does provenance-typed, scope-separated memory reduce false memories and leakage without hurting recall? | **H3a:** a lower false-user-fact rate than (i) full-history context and (ii) Mem0-style untyped extraction, at non-inferior recall (margin 5 pp). **H3b:** cross-scope leak rate below 1% vs baselines > 0. **H3c:** after deletion, multi-channel leak rate below 5% | The rates are not lower, or recall is inferior beyond the margin |
| RQ4 | Is a world model needed for this experience? This tests the owner's hypothesis in both directions | **H4a:** on scene-grounded tasks (navigation, scene events, visual recall), A2 beats A0 (no world model) on task success. **H4b:** on talk-only tasks, A0 is non-inferior to A2 on MOS | H4a: no difference. H4b rejected: A0 worse. Either outcome is informative |
| RQ5 | Does anchoring interaction state to *displayed* frames improve handling of corrections after interruptions? | **H5:** display-aligned context raises referent-resolution accuracy on video-referent corrections ("no, the *other* path") over generation-aligned context | No improvement (CI includes 0) |
| RQ6 | Can the persona remain consistent across shots and over long sessions? | **H6:** persona identity similarity between the presenter and world shots, and over 30 min, stays above a threshold calibrated on the reference image (§8) | Similarity drops below the threshold in more than 20% of windows |

RQ1 and RQ2 are primary; RQ3–RQ6 are secondary. We report all outcomes, including null results.

---

## 5. Candidate architectures and selection

### 5.1 Candidates

Figure: `docs/figures/fig4_candidate_architectures.mmd`.

- **A0: no world model (simple baseline).**
  - Pipeline: LLM with memory → streaming TTS → audio-driven avatar in front of a static background.
  - Tests whether the world model adds value at all (RQ4).
  - Generator candidates: SoulX-FlashHead, Ditto, LivePortrait (single-GPU classes); LiveAvatar for higher quality.
    One will be chosen in M1.
- **A1: open-loop direct coupling.**
  - A single LLM writes free-form prompts and camera commands to LingBot-World.
  - Memory is the chat history in context.
  - No manifest and no verification; the same dual-shot rendering as A2.
  - This is the "LLM connected to a video generator" baseline the brief warns against.
- **A2: capability-grounded closed-loop modular controller (proposed).** Figure 1: `fig1_architecture_A2.mmd`.
- **A3: tightly coupled.** Two routes:
  - (a) fine-tune LingBot-World with audio and behavior-token conditioning (a character-centric world model);
  - (b) adopt an end-to-end duplex audio-video model (Wan-Streamer-class).

  Under H-core, A3 still needs an external memory layer.

### 5.2 Comparison

All entries are **[estimate]** unless marked otherwise.

| Criterion | A0 | A1 | A2 | A3 |
|---|---|---|---|---|
| Lip-sync / face quality | High (dedicated avatar) | High on presenter shot; none on world shot | Same as A1 | Unknown; (b) is low resolution: 192p–256² [cited] |
| Scene / camera controllability | None | Camera only; prompts need E1 | Camera + calibrated events | Potentially highest; unproven |
| Observable compliance | n/a (scene) | Unverified | Measured and repaired | Unknown |
| Instruction-to-visual latency | Speech only | Chunk-bound; no backlog control | Chunk-bound + bounded backlog | Possibly lower (frame-wise) |
| Memory reliability | Depends on the memory layer | Context only (weak) | Typed and scoped | Needs an external layer |
| Engineering complexity | Low | Medium | High | Very high |
| Compute (single user) | 1–2 GPUs | Generator 4 GPUs (if H200-class) + avatar 1 + LLM/ASR/TTS 1 | Same as A1, + monitor ≈ 1 GPU | Training cluster |
| Training required | No | No | No (calibration only) | **Yes** |
| Demo feasibility (Phase 2) | High | High | Medium–high | Low |

**Selection.** A2 is the proposed system. A0 and A1 are required baselines. A3 is a longer-term extension: it is
justified only if S1 shows that affordance limits, not control, dominate compliance failures. No foundation-model
training is required for Phase 2.

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

Each IR item is a record:

```yaml
id: ir-0193                # unique; becomes vLLM-Omni event_id when compiled
plan_version: 12           # items from superseded plans are dropped (staleness)
track: camera              # speech | shot | camera | scene_event | character_event | memory_op
intent: "turn_left"        # symbolic intent from a closed vocabulary + free text
params: {yaw_deg: -60, transition_chunks: 1}
earliest_start: t_now      # wall-clock or relative to a speech segment id
deadline_s: 3.0            # when unobserved after this, the item counts as failed
priority: user_explicit    # user_explicit > plan_step > idle_behavior
supersedes: [ir-0191]      # latest-wins semantics for the same track
expect:                    # observable predicate for the monitor
  kind: camera_yaw_change
  sign: negative
  min_magnitude_deg: 20
fallback: [verbal_ack_failure]
provenance: {source_utterance: utt-551, speaker: user}
```

**Speech.** Speech items carry TTS segment ids. A *narration policy* separates two kinds of statement:
- *Intentions* ("turning left") may be spoken immediately.
- *Completions* ("we're at the lake") may be spoken only after the monitor confirms them.

This rule targets false completion claims (FCR, H1b).

#### Capability manifest

For every control $c$ the backbone might execute, the manifest records the following. Examples of controls:
- camera velocity / target;
- scene prompt "it starts to snow";
- character prompt "the host waves".

| Field | Meaning | Source |
|---|---|---|
| `status` | A / B / C / D (§6) | backbone_verification.md |
| `interface` | exact WS payload template | local-code |
| `p_success` (+CI) | fraction judged compliant within D | calibration experiment E1 |
| `tvc_p50/p95` | time to visible compliance | E1 |
| `side_effects` | identity drift, scene reset, artefacts | E1 |
| `preconditions` | e.g. world shot active, persona visible | design |

**Compiler rules:**
- (i) reject an item if `status` ∉ {A, C-implemented};
- (ii) if `p_success` < θ, pick a cheaper equivalent or a verbal alternative;
- (iii) if the predicted TVC exceeds the item's deadline, tell the user it will take a moment, or degrade;
- (iv) map timing onto the next chunk boundary;
- (v) emit WS `session.interaction` messages with `event_id = IR id`.

#### Compliance monitor

The monitor runs on **displayed** frames, identified by client presentation timestamps.

**Camera items.** Relative camera motion is estimated between frames with a lightweight geometric estimator (sparse
flow → essential matrix) and compared with the commanded SE(3). Accuracy is validated offline against RotErr/TransErr
[cited: he2024cameractrl].

**Scene and character items.** A VLM judge answers a yes/no question on sampled frames of the chunks that follow.
Candidates: StreamingVLM, or a Qwen-VL-class model. Its cost is bounded by StreamingVLM's reported ≈8 FPS on
1×H100 [cited].

**Identity.** Embedding similarity to the persona reference is computed per shot.

**Verdicts.** Each item gets `complied`, `not_complied` or `unknown`, with a confidence. Verdicts update the planner
and, over time, the manifest (online calibration, with separate held-out evaluation).

**Judge validation.** The judges themselves are validated against blinded human labels (§8).

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

**Backlog and buffering (engineering E2).**
- The WS server does not pace generation [local-code].
- If generation period $T$ < playback period $P = 12/\text{fps}$, the client backlog grows by $P-T$ per chunk.
- Policy options:
  - *bounded look-ahead*: the client acknowledges presentation; the controller keeps at most $L$ undisplayed chunks by
    delaying `session.ping` progress, or, if needed, by a server-side gate (E1);
  - playback-rate matching.
- If $T > P$, the stream stalls. Mitigations: lower playback fps (for example 12 fps gives $P = 1.0$ s), a shot cut
  to the presenter, or more GPUs.
- M0 measures which regime applies on local hardware.

**Display-aligned state (RQ5).**
- The context seen by the responder and planner records which chunks were *presented* (from client timestamps),
  not which were generated.
- Corrections such as "no, the other one" are resolved against displayed content.

**Audio/video synchronization.**
- Audio is the master clock.
- Presenter shot: the avatar is driven by the TTS audio. Audio playback is delayed by the avatar pipeline latency to
  meet lip-sync tolerance. EBU R37 gives +40/−60 ms end-to-end, and ITU-R BT.1359 gives detectability at
  +45/−125 ms [cited].
- World shot: there are no lips to sync. Speech about an action is aligned with the chunk whose metadata shows the
  event started. Completion statements wait for the monitor (the narration policy).
- Shot cuts happen at chunk boundaries of the world stream.

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
- Only user-speaker turns feed fact extraction.
- The persona's own utterances and rendered events go to a **generated-event log** with `speaker=persona`. They are
  *never* promoted to user facts.
- Agent inferences ("the user seems to like jazz") become *candidate beliefs*. They are used only as hedged
  suggestions until the user confirms them.
- Viewer chat in Mode 2 is written only to the public scope. It is rate-limited and sanitized, and tagged
  `viewer-claimed`.

**Retrieval.**
1. Filter by scope first, before any relevance scoring:
   - Mode 1 may read private:user, canon and the persona's own public history;
   - Mode 2 may read public:stream and canon, and never private.
2. Rank by relevance, recency and importance [cited: park2023generativeagents].
3. Every injected memory carries its provenance tag, so the LLM can hedge.

**Consolidation.** Runs asynchronously at "sleep time": session end, idle periods [cited: fang2025lightmem]. It
summarizes episodes, merges duplicates, and records `derived_from` links.

**Correction.** User-asserted facts use a bi-temporal update [cited: rasmussen2025zep]. The old value gets
`valid_to=now` and is kept for audit. An agent-inferred belief never overrides a user-asserted fact.

**Deletion.** An erasure request triggers a **cascade** along `derived_from` links:
- delete the fact and its episodic mentions;
- regenerate affected summaries;
- purge visual-state records that depict the item;
- flush cached prompts and LLM KV.

Each cascade is logged in a deletion ledger that records only the fact that a deletion happened, not its content.
This addresses the finding that "deletion ≠ forgetting" [cited: yao2026executionunlearning, yu2026kbench].

**Conflict resolution.** The order is: user-asserted (latest valid) > system-observed > agent-inferred >
viewer-claimed. Conflicts between user-asserted facts are raised to the user for confirmation.

**Provenance.** Every record keeps its source utterance or frame id, speaker, session, timestamp and extraction
model version.

**Public/private separation.** There are three physically separate stores: private per user, public per stream,
and canon. Mode 2 processes have no read credentials for private stores. Leak probes (§7.3) test this across speech,
on-screen text and generated visuals.

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

| ID | Extension | Why | Size [estimate] |
|---|---|---|---|
| C1 | Register `PromptInteractionHandler` for LingBot. Invalidate and rebuild text K/V when the prompt changes on the stepwise path (`_ar_text_caches(..., invalidate=True)`) | Scene and character events | small–medium; upstream-able |
| C2 | WS `session.reset` / `session.extend` (increase `total_chunks`) | Open-ended sessions; persona restart | medium |
| C3 | Server-side monotonic timestamps in chunk metadata | TVC decomposition | small |
| C4 | Client presentation-ack protocol and bounded look-ahead (server gate if needed) | Backlog control, display alignment | medium |
| C5 | Restart from a stored frame (`image_reference` = last displayed frame) with seam handling | Cross-session visual continuity | small (client-side) |
| C6 | External avatar path, shot switcher, audio master clock | Visible speaking persona | medium |

### 6.4 Latency model

This model is **[derived]**. Numerical values are **[target]** or upstream-conditional.

For one camera instruction arriving at wall-clock $t_0$:

$$\text{TVC} = \underbrace{A}_{\text{ASR+plan+compile}} + \underbrace{W}_{\sim U(0,T)} + \underbrace{T}_{\text{gen}} + \underbrace{\delta}_{\text{mux+net}} + \underbrace{Q}_{\text{playback backlog}} + \underbrace{I}_{\text{visual inertia}}$$

We do not add the judge detection delay: it is removed through the judge's localization of the onset frame.

**Illustrative budget.** This assumes the upstream PR #7749 figure $T=0.549$ s is reproduced locally, 16 fps playback
($P=0.75$ s) and look-ahead $L\le1$:

| Term | p50 | p95 | Basis |
|---|---|---|---|
| A (endpoint + responder IR emit + compile) | 0.45 s | 0.8 s | [target]; endpointing 200–300 ms [cited: pipecat2026primer] |
| W | 0.27 s | 0.52 s | uniform over $T$ [derived] |
| T | 0.55 s | 0.60 s | [cited upstream; unmeasured locally] |
| δ | 0.1 s | 0.15 s | mux ≈ 45 ms [cited PR #7648] + LAN [estimate] |
| Q | 0.375 s | 0.75 s | half to one chunk backlog under $L\le1$ [derived] |
| I (camera) | 0.1 s | 0.4 s | [estimate]; measured in M0/E1 |
| **Camera TVC** | **≈1.8 s** | **≈3.2 s** | **[derived]**. Sums of p95 overstate the true p95. Illustrative only |

**Speech path (first audible response).**
- Endpoint 250 ms + responder TTFT 300 ms + TTS first packet 150 ms + network 50 ms ≈ **0.75 s p50 [target]**.
- p95 ≤ 1.5 s [target], following the 1.5 s cascade target of the Pipecat primer [vendor].
- Presenter-shot lip-sync adds the avatar latency, which must be ≤ 300 ms [target] or be hidden by delaying audio.

**Regimes.**
- **1 GPU:** $T \approx 3.24$ s > $P$ [cited]. Streaming stalls; the world shot cannot run in real time. Use a presenter
  shot with pre-rolled world clips, or wait for more GPUs.
- **2×H200-class:** $T \approx 0.89$ s > $P = 0.75$ s at 16 fps, but < $P = 1.0$ s at 12 fps. Real time is possible
  at 12 fps.

These regimes are why M0 gates the targets.

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
- Send one WS `session.interaction` with `event.prompt` to settle the contradiction between the registry and the
  benchmark code.
- Measure the growth of the client backlog without pacing.

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

**Trials.** 30 trials per control × scene, with randomized issue time within a chunk.

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
- 20 single-step instructions: camera or event.
- 20 multi-step instructions, for example "walk to the lake, then stop and look left".
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
- OCR: fraction of instructions judged compliant within the deadline $D$ on displayed frames.
- Task success for multi-step tasks: all steps compliant, in order.
- FCR: the persona claimed completion, but the judge says not complied.
- TVC p50/p95, including censored cases.
- Recovery time after a correction.
- Referent-resolution accuracy.

**Design and analysis.**
- Within-task paired design: each task × 5 seeds × each condition, giving 300 paired trials per condition.
- Mixed-effects logistic regression: condition as a fixed effect; task and seed as random effects.
- Paired bootstrap 95% CIs for differences.
- Holm correction across the primary contrasts (A2 vs A1 on OCR and on FCR).

**Power [estimate].** Consider a true OCR of 60% vs 75% with ≈ 20% discordant pairs. McNemar's test on 300 pairs then
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
- A2 and a "no external layer" variant of A1 run through ≥ 3 sessions separated by restarts.
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
- Latency distributions are reported as p50/p95/p99 with ≥ 3 repeated runs per configuration.
- Censored TVC is analysed with survival curves.
- We report judge–human agreement (Cohen's κ) and judge runtime cost.
- All raw logs are released internally. No cherry-picking: every scripted task is reported.

---

## 8. Metrics and success criteria

All thresholds below are **[target]**. They are provisional until M0 and the E2 pilot.

| Metric | Definition | Success criterion |
|---|---|---|
| OCR | Instructions judged compliant on displayed frames within deadline $D$ ($D$ = 5 s camera, 8 s events) | A2 − A1 ≥ +10 pp, with the paired CI excluding 0 (H1a) |
| FCR | Completion claims contradicted by the judge | A2 ≤ 5% and below A1, CI excluding 0 (H1b) |
| Multi-step task success | All steps compliant, in order | Reported; A2 > A1 |
| TVC (camera) | Wall-clock from instruction end-of-utterance to first judged-compliant *displayed* frame; failures censored | p50 ≤ 2.0 s, p95 ≤ 3.5 s on the M0-qualified configuration |
| TVC (events, post-C1) | Same, for scene/character events | p50 ≤ 3.5 s, p95 ≤ 6 s; compliance rate reported separately |
| Time to first speech | End of user utterance → first audible persona audio | p50 ≤ 0.8 s, p95 ≤ 1.5 s |
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

Total: about 6–7 of the 8 shared GPUs for one live session. **Availability is not guaranteed**; long experiments need
scheduled slots (`gpu reserve --start … --end …`).

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
