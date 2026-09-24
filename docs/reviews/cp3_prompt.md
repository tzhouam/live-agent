You are GPT-6 Sol, the INDEPENDENT REVIEWER for the "live-agent" project (AGENTS.md rules: read-only; numbered findings tagged blocking/major/minor, each with evidence or the check that would settle it). Checkpoint 3 of 4: CANDIDATE ARCHITECTURES, MODEL INTEGRATION, MEMORY DESIGN, LATENCY FEASIBILITY. This also re-reviews the CP2 revisions (dual-shot persona, TVC repositioning).

Inlined: docs/research_proposal.md (focus on §1.3, §3, §5, §6; §7-8 will be reviewed at CP4 but flag anything blocking), docs/backbone_verification.md, docs/decision_log.md, the four Mermaid figure sources, the vLLM-Omni streaming API doc and realtime design doc, and REAL code excerpts from vllm-omni @7b4dc76 with line numbers (cp3_ev_code_excerpts.md) — use these to check every interface claim.

Please challenge specifically:
1. Interface mismatches: does every control the proposal compiles to actually exist in the quoted code/docs (session.interaction camera target/velocity, transition_chunks, event acks started/active/completed_event_ids, session.stop, image_reference at start, num_frames 9+12k)? Is the claim that the WS server does not pace generation supported by serving_video_output_stream.py:148-155? Are C1-C6 extensions correctly sized/scoped (e.g., C1 text K/V refresh: is `_ar_text_caches(..., invalidate=True)` real per the excerpt)?
2. Architecture comparison: are A0-A3 fair; is anything overlooked (e.g., using SGLang's LingBot server which supports prompt switching; using the deprecated tick path; pre-rendered clip scheduling like the reference agent; avatar composited into world; switching backbone for the world shot)? Is the "no training needed" claim sound?
3. Behavior IR / manifest / compiler / monitor: are they well-defined enough to implement and to be falsifiable? Is the narration policy (intent now, completion only after verification) sound? Weaknesses in using a VLM judge online (latency, error), camera estimator from sparse flow at 480p?
4. Dual-shot persona: is it coherent? Identity consistency across two different generators, shot-switch timing at chunk boundaries, A/V sync with audio master clock, GPU budget (4+1+1-2 of 8 shared GPUs).
5. Memory design: are the five state kinds properly separated; write/retrieval/consolidation/correction/deletion/provenance/conflict rules coherent; does the generated-event quarantine actually prevent generated/inferred events becoming user facts (e.g., the user repeating a persona claim; the persona paraphrasing a user fact)? Public/private separation holes (e.g., visual state records reused across modes; persona's own public history leaking private info said in 1:1)?
6. Latency model & budget (§6.4): errors in the TVC decomposition, the backlog analysis (P=0.75 s at 16 fps, T=0.549 s), regimes for 1/2/4 GPUs, speech path targets, barge-in. Is "sums of p95 overstate" handled acceptably? Anything on the critical path mislabelled as async or vice versa?
7. Is the feasible first demo clearly separated from longer-term research?
Be concrete and concise.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/research_proposal.md =====
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

===== FILE: docs/backbone_verification.md =====
# Backbone Verification: LingBot-World 2.0 in vLLM-Omni

> Deliverable for goal.md §4. It is based on the audit in `docs/notes/backbone_lingbot_world_vllm_omni.md`
> (reproduced below), with the independent checks Claude made on 2026-09-25 listed first.
> Inspected implementation: upstream `vllm-project/vllm-omni` `main` @ `7b4dc7633bde8642f0c05f77bd018751541df404`
> (2026-09-24), a read-only clone at `external/vllm-omni`. No GPU job was run, so **every latency number here is
> upstream-reported (class B) or derived**, never measured locally.

## Clarifications after Codex CP2 (2026-09-25)

- **Scope of "camera-only".** This conclusion comes from reading the code, not from running it. It covers mid-session
  `session.interaction` messages on the public stepwise WS path. Other ways to steer the camera also exist:
  request-scoped `camera_action_script` / `action_path`, and prompt switching on the deprecated tick path (latent
  output). The upstream benchmark sends prompt updates, which contradicts the registry, so **one real WS prompt-update
  attempt is part of M0** before `interaction_failed` is treated as observed.
- **Event ack ≠ visible compliance.** The `started/active/completed_event_ids` fields in chunk metadata show when a
  control was *applied* to a chunk. They say nothing about whether the rendered content complies.
- **The "≈0.6–1.15 s" camera figure** in §0 and §8 below is a derived *earliest chunk-delivery estimate*. It is not
  time-to-visible-compliance, because it leaves out client playback queueing, the network and visual inertia. It also
  assumes the upstream PR #7749 stack on 4×H200 (compiled, streaming decoder, selective FP8, KV-skip; some options
  experimental).
- **Reclassifications.**
  - WS *rewind / snapshot / branch*: moved from C to "C/D, feasibility unknown". Snapshotting paged KV together with
    the streaming-decoder and encoder state has no existing design.
  - Class D now covers only **native** LingBot lip, face and audio conditioning. A speaking persona built from an
    external TTS plus an audio-driven avatar is engineering (C) *outside* the backbone.
- **Cancel vs redirect.** `session.stop` and disconnect cancel the rollout. What is missing is *redirecting* an
  in-flight chunk while keeping the session. A new control can only take effect at the next chunk boundary.

---

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

## Open questions

See `docs/PROJECT.md` (A*/Q* table). Resolved questions move here with the evidence.

===== FILE: docs/figures/fig1_architecture_A2.mmd =====
%% Fig. 1 — Proposed architecture A2: capability-grounded closed-loop controller, dual-shot persona
%% (LingBot-World world shot + external audio-driven avatar close-up).
%% Editable Mermaid source. Render: npx -y @mermaid-js/mermaid-cli -i fig1_architecture_A2.mmd -o fig1.svg
flowchart LR
  subgraph IN[Inputs]
    U[User mic / text<br/>1:1 session]
    C[Livestream chat<br/>public, untrusted]
  end

  subgraph FAST[Fast path - critical]
    VAD[VAD + streaming ASR<br/>barge-in detector]
    TD[Turn and interrupt manager]
    RESP[Responder LLM<br/>streaming, short horizon]
    TTS[Streaming TTS]
  end

  subgraph SLOW[Deliberative path - async]
    PLAN[Planner LLM<br/>goal stack, multi-step plans]
    MEMR[Memory retrieval<br/>scoped, provenance-typed]
  end

  subgraph CTRL[Control layer]
    IR[(Behavior IR<br/>time-aligned tracks:<br/>speech / shot / camera /<br/>scene-event / character-event)]
    MAN[[Capability manifest<br/>verified backbone controls]]
    COMP[Control compiler<br/>IR to executable controls<br/>+ reject / degrade]
    SCHED[Chunk-boundary scheduler<br/>event ids, cancellation, staleness]
  end

  subgraph GEN[vLLM-Omni server]
    WS[WS /v1/realtime/video<br/>session.start / interaction / stop]
    LB[LingBot-World 2.0 14B<br/>causal-fast, 4 DMD steps<br/>sink + rolling KV]
  end

  subgraph AV[Avatar path - external to backbone]
    AVA[Audio-driven avatar<br/>close-up, lip-sync<br/>same persona reference]
  end

  subgraph VERIFY[Observation and verification]
    ACK[Event ack from chunk metadata<br/>started / active / completed ids]
    MON[Compliance monitor<br/>pose estimator + VLM judge<br/>identity embedding]
  end

  subgraph MEM[Memory service]
    WM[Working context<br/>per session]
    EP[(Episodic log<br/>append-only, timestamped)]
    SEM[(Semantic profile<br/>user-asserted facts only)]
    GENV[(Agent-generated events<br/>quarantined, never user facts)]
    VIS[(Visual state records<br/>ref frames, persona look,<br/>world seeds)]
    CONS[Consolidator<br/>async, sleep-time]
  end

  OUT[Shot switcher + muxer<br/>audio = master clock<br/>bounded look-ahead buffer]
  VIEW[Viewer / stream]

  U --> VAD --> TD
  C --> TD
  TD -->|interrupt| SCHED
  TD --> RESP
  TD --> PLAN
  MEMR --> RESP
  MEMR --> PLAN
  RESP --> TTS --> OUT
  TTS --> AVA --> OUT
  SCHED -->|shot track| OUT
  RESP --> IR
  PLAN --> IR
  IR --> COMP
  MAN --> COMP
  COMP --> SCHED --> WS --> LB
  LB --> WS --> OUT --> VIEW
  WS --> ACK --> SCHED
  OUT -->|presentation timestamps| SCHED
  OUT --> MON --> SCHED
  MON --> PLAN
  TD --> EP
  RESP --> GENV
  MON --> VIS
  EP --> CONS --> SEM
  CONS --> VIS
  SEM --> MEMR
  EP --> MEMR
  VIS --> MEMR
  WM --- RESP

===== FILE: docs/figures/fig2_sequence_interrupt.mmd =====
%% Fig. 2 — Interaction sequence: instruction, interruption, revision, verification.
%% Times are illustrative placeholders, not measurements. T = chunk period (12 frames).
sequenceDiagram
  autonumber
  participant User
  participant ASR as VAD/ASR + Turn mgr
  participant R as Responder LLM
  participant P as Planner LLM
  participant M as Memory
  participant CC as Compiler + Scheduler
  participant G as vLLM-Omni LingBot (WS)
  participant V as Compliance monitor
  participant O as Muxer / Viewer

  User->>ASR: "Walk toward the lake"
  ASR->>R: final transcript (endpoint)
  par fast reply
    R->>O: TTS "Sure, heading to the lake" (first audio)
  and plan
    R->>P: intent(navigate, target=lake)
    P->>M: retrieve(user prefs: pace=slow) [scope=private]
    M-->>P: fact(pace=slow, provenance=user-asserted, t=session 2)
    P->>CC: IR: camera.velocity(z=+0.03) from t0, event e17
  end
  CC->>G: session.interaction {event_id:e17, camera velocity}
  G-->>CC: session.interaction.queued(e17)
  Note over G: applied at next chunk boundary (0..T wait) + T generation
  G->>O: chunk k (metadata started_event_ids=[e17]) + fMP4
  O->>V: frames of chunk k
  V-->>CC: observed forward motion ok (pose est.)
  User->>ASR: "No wait, turn left instead!" (barge-in)
  ASR->>R: interrupt
  R->>O: stop TTS, ack "Turning left"
  ASR->>CC: cancel pending events newer than current chunk
  CC->>G: session.interaction {event_id:e18, camera target yaw -60deg, transition_chunks:1}
  G->>O: chunk k+1 still reflects e17 (already in flight)
  G->>O: chunk k+2 started_event_ids=[e18]
  O->>V: frames k+2
  V-->>CC: yaw change observed? if not within 2 chunks -> re-issue / tell user
  CC->>M: episodic event (instruction revised, outcome=complied@k+2) [provenance=system-observed]

===== FILE: docs/figures/fig3_memory_lifecycle.mmd =====
%% Fig. 3 — Memory taxonomy and lifecycle with provenance and scope.
flowchart TB
  subgraph Sources
    UA[User utterance<br/>user-asserted]
    INF[LLM inference about user<br/>agent-inferred]
    GEN[What the persona said or showed<br/>agent-generated]
    VW[Viewer chat claim<br/>third-party, untrusted]
    OBS[Monitor observations of output<br/>system-observed]
  end
  subgraph Scopes
    PRIV[private:user_id]
    PUB[public:stream_id]
    CANON[persona canon<br/>curated, read-only at runtime]
  end
  UA -->|write sync: episodic| EP[(Episodic log)]
  INF -->|write: candidate only| CAND[(Candidate beliefs<br/>need confirmation)]
  GEN --> GLOG[(Generated-event log<br/>never promoted to user facts)]
  VW -->|rate-limited, sanitized| PUBLOG[(Public episodic)]
  OBS --> VISST[(Visual state records)]
  EP -->|async consolidation| SEMF[(Semantic facts<br/>value, provenance, time, scope, confidence)]
  CAND -->|user confirms| SEMF
  SEMF -->|correction: supersede, keep audit| SEMF
  SEMF -->|erasure: purge + derived artifacts| DEL[Deletion ledger<br/>cascade to summaries, caches,<br/>visual refs]
  PRIV -.isolation.- PUB
  SEMF --- PRIV
  PUBLOG --- PUB
  CANON --> RET[Retriever: scope filter FIRST, then relevance]
  SEMF --> RET
  EP --> RET
  PUBLOG --> RET
  VISST --> RET
  RET -->|public mode: private scope blocked| CTX[Prompt context]

===== FILE: docs/figures/fig4_candidate_architectures.mmd =====
%% Fig. 4 — Candidate architectures compared in the proposal (A0-A3).
flowchart TB
  subgraph A0[A0 - No world model baseline]
    a0u[User] --> a0l[LLM + memory] --> a0t[Streaming TTS] --> a0v[Audio-driven avatar<br/>static background]
  end
  subgraph A1[A1 - Open-loop direct coupling]
    a1u[User] --> a1l[LLM, chat history as memory] -->|free-form prompt / camera JSON| a1g[LingBot-World WS]
    a1l --> a1t[TTS + avatar close-up]
  end
  subgraph A2[A2 - Proposed: capability-grounded closed loop]
    a2u[User] --> a2f[Fast responder] --> a2t[TTS + avatar]
    a2u --> a2p[Planner] --> a2ir[Behavior IR] --> a2c[Compiler vs capability manifest] --> a2g[LingBot-World WS]
    a2g --> a2m[Compliance monitor on displayed frames] --> a2p
    a2mem[(Typed, scoped memory)] --> a2p
    a2mem --> a2f
  end
  subgraph A3[A3 - Tightly coupled, long-term]
    a3u[User] --> a3x[Unified model: LM + audio/behavior-conditioned<br/>world generator, trained end-to-end or adapter-tuned]
    a3x --> a3mem[(External memory still required per H-core)]
  end

===== FILE: docs/reviews/cp3_ev_streaming_api.md =====
# Streaming Video Output WebSocket API

Use `WS /v1/realtime/video` to receive fragmented MP4 chunks while a compatible
diffusion video model is generating. This endpoint streams generated video
output; it is unrelated to [`WS /v1/video/chat/stream`](video_stream_api.md),
which streams live video input into a conversational model.

## Quick Start

Start a model that supports step execution and enable diffusion streaming
output:

```bash
vllm serve BestWishYsh/Helios-Distilled --omni \
  --diffusion-streaming-output \
  --port 8091
```

Install the client dependency and run the provided client:

```bash
pip install av websockets

python examples/online_serving/streaming_video_generation/streaming_video_client.py \
  --host 127.0.0.1 \
  --port 8091 \
  --model BestWishYsh/Helios-Distilled \
  --prompt "A serene lakeside sunrise with mist over the water" \
  --output output.mp4
```

## Protocol

Control events are JSON text frames. Each `video.chunk_metadata` event is
immediately followed by one binary WebSocket frame containing fragmented MP4
bytes.

| Direction | Event or frame | Purpose |
| ----------- | ---------------- | --------- |
| Client to server | `session.start` | Starts generation with a prompt and video parameters |
| Server to client | `video.start` | Confirms the request ID, format, and accepted configuration |
| Server to client | `video.chunk_metadata` | Describes the next binary media frame |
| Server to client | Binary frame | Carries one fragmented MP4 chunk |
| Client to server | `session.interaction` | Queues an optional interaction (e.g., prompt. camera action) during generation |
| Server to client | `session.interaction.queued` | Confirms that an interaction was queued |
| Client to server | `session.ping` | Refreshes the stall clock |
| Server to client | `session.pong` | Acknowledges a ping |
| Client to server | `session.stop` | Cancels the active generation |
| Server to client | `session.done` | Reports completion or cancellation and the chunk count |
| Server to client | `error` | Reports validation, generation, or timeout failures |

Start a minimal session with:

```json
{
  "type": "session.start",
  "model": "BestWishYsh/Helios-Distilled",
  "prompt": "A serene lakeside sunrise",
  "format": "m4s",
  "width": 640,
  "height": 384,
  "fps": 16,
  "num_frames": 99
}
```

Only `m4s` output is currently accepted. Concatenate the binary frames in
receive order, then remux the fragmented stream if the target player requires
a progressive MP4 file.

## Mid-Generation Interaction

Models that implement interaction updates can change the active prompt:

```json
{
  "type": "session.interaction",
  "interaction": {
    "event_id": "sunlight-update",
    "event": {"prompt": "Sunlight breaks through the mist"},
    "transition_chunks": 2
  }
}
```

Models that register the camera modality (for example LingBot-World) also
accept structural SE3 payloads on `event.multi_modal_data.camera`. Coordinates
follow Unity semantics (`+X` right, `+Y` up, `+Z` forward; same as LingBot's
native camera frame). WASD key tokens are not admitted by the engine:

```json
{
  "type": "session.interaction",
  "interaction": {
    "event_id": "forward-1",
    "event": {
      "multi_modal_data": {
        "camera": {
          "mode": "velocity",
          "data": {
            "translation": [0.0, 0.0, 0.05],
            "rotation": [0.0, 0.0, 0.0, 1.0]
          }
        }
      }
    }
  }
}
```

`mode` is `target` (lerp to an absolute pose over `transition_chunks`) or
`velocity` (hold a per-frame SE3 delta until replaced). Prompt and camera may
be combined in one interaction event.

This feature is pipeline-dependent. An enabled endpoint does not imply that
the loaded model supports midway prompt or camera updates.

The default start timeout is 10 seconds and the server reports a stall after
about 60 seconds without generation progress or a `session.ping`. See the
[streaming video generation example](https://github.com/vllm-project/vllm-omni/tree/main/examples/online_serving/streaming_video_generation)
for prompt/camera-update scheduling and browser playback.

===== FILE: docs/reviews/cp3_ev_realtime_design.md =====
# Realtime AR-Diffusion sessions

> **Status:** experimental. This document describes the internal execution
> contract implemented under `vllm_omni.experimental.ar_diffusion`. It does not
> define a public HTTP or WebSocket schema.

## Scope

Realtime AR-Diffusion serves world models that generate one autoregressive
latent block per request while retaining model state across requests. The
generic runtime owns identity, event ordering, session lifecycle, routing, and
KV allocation. A model adapter owns model-specific controls and conditioning.

LingBot World v2 is the first single-KV-branch integration. DreamZero uses the
same runner capability with two logical CFG branches.

## Identities

Four identifiers have distinct lifetimes:

| Identifier | Lifetime | Owner | Contract |
| --- | --- | --- | --- |
| `session_id` | One persistent world | Session manager | Selects runner KV and model-owned state. |
| `event_id` | One control/prompt update | Transport adapter | Unique and monotonically increasing within a session, including across reset. |
| `chunk_index` | One committed AR block position | Session | Contiguous from zero; reset starts again at zero. |
| `request_id` | One chunk execution | Session | Correlates the tick with its returned metadata. |

`AsyncOmni` keeps its normal UUID-suffixed engine routing ID. The tick
`request_id` remains inside the immutable AR-Diffusion snapshot and the
standard output metadata, while caller-visible `OmniRequestOutput.request_id`
continues to use AsyncOmni's existing external-ID contract. Protocol identity
therefore does not require a private entrypoint override.

## Request lifecycle

1. `ARDiffusionSession.accept_event()` validates and queues an immutable
   `ARDiffusionSessionEvent`. Prompt and opaque control tracks may be updated in
   the same event.
2. `ARDiffusionSession.next_chunk()` serializes chunk execution and calls
   `_build_tick_locked()`. The resulting `ARDiffusionTickRequest` is a snapshot
   of the current prompt, reduced controls, ordered event IDs, and chunk index.
3. `ARDiffusionOmniTickConsumer.execute_tick()` copies the stage sampling
   parameters, stores the typed tick in
   `sampling_params.extra_args["ar_diffusion_tick"]`, constructs the normal Omni
   prompt through its `prompt_provider`, and invokes `AsyncOmni.generate()`.
4. `AsyncOmni` allocates its normal unique engine routing ID and submits one
   `OmniDiffusionRequest` through the orchestrator.
5. `ARDiffusionModelRunner._request_session()` parses the typed tick.
   `_get_or_create_session()` obtains runner-owned paged KV, and
   `bind_ar_diffusion_state()` exposes it to the pipeline only for the duration
   of `execute_model()`.
6. The model pipeline validates the tick and generates exactly one latent
   block. LingBot interprets camera controls in
   `LingBotCameraControlReducer` and
   `LingBotWorldCausalDMDPipeline.forward()`; the generic runtime does not parse
   camera or action schemas.
7. The pipeline returns one `DiffusionOutput` with the generated payload and an
   `ARDiffusionChunkMetadata` mapping under `metadata["ar_diffusion"]`.
   `AsyncOmni` exposes it as
   `OmniRequestOutput.multimodal_output["metadata"]["ar_diffusion"]`.
8. The consumer parses the standard envelope. The session commits its reducer
   state, prompt, controls, event IDs, and next chunk index only when returned
   metadata exactly equals the submitted tick snapshot.

The metadata envelope is:

```json
{
  "metadata": {
    "ar_diffusion": {
      "session_id": "world-7",
      "request_id": "ar-world-7-3-...",
      "chunk_index": 3,
      "applied_event_ids": [10, 11]
    }
  }
}
```

## Transaction and failure semantics

Accepted events are not acknowledged as applied until the model output and
metadata are validated. Reducer `prepare()` is speculative; reducer `commit()`
and the session snapshot form one logical commit. A model, metadata, or reducer
failure leaves the chunk index and queued events uncommitted and transitions the
session to `FAILED`.

After a tick failure, worker state is closed because a forward may have
partially modified or already released KV. The same chunk is not retried in
place. A caller must explicitly reset the session, starting again at chunk
zero, or close it.

Explicit close follows this state machine:

```text
ACTIVE or FAILED
       |
       v
    CLOSING ---- worker cleanup succeeds ----> CLOSED
       |
       +------- worker cleanup fails --------> CLEANUP_FAILED
                                                   |
                                                   +-- close retry --> CLOSING
```

`CLEANUP_FAILED` is a local tombstone. The session manager retains it, rejects
creation of the same `session_id`, and rejects reset. Only an idempotent close
retry that succeeds removes the session. Transport disconnect uses the same
path.

## KV ownership and capacity

`ARDiffusionKVCacheSpec` is the pipeline-owned immutable geometry contract. It
declares:

- TP-local self-attention geometry, AR block size, sink, and recent window;
- logical KV branches and their worker-local slots;
- fixed-length cross-attention caches;
- scratch tokens required by an uncommitted forward;
- persistent model-owned CUDA bytes per resident session; and
- the requested resident-session capacity.

The runner computes:

```text
required(capacity) =
    scratch
  + managed_self_attention_pages(capacity)
  + capacity * cross_attention_bytes_per_session
  + capacity * model_owned_state_bytes_per_session
```

`gpu_memory_fraction` is a soft expansion budget:

```text
configured_budget = available_device_bytes * gpu_memory_fraction
effective_budget = max(configured_budget, required(1))
```

If `required(1)` exceeds actual available device memory, initialization fails.
Otherwise the runner always admits one viable session and uses the configured
fraction to select additional resident sessions up to the model-declared cap.
All model-owned reservations are deducted before the paged self-attention pool
is allocated.

LingBot advances a session-owned causal Wan VAE encoder for each condition
block: the opening pixel frame is followed by four zero pixel frames per later
latent frame. It retains one current condition block, with separate committed
and in-flight encoder histories so a failed block cannot overwrite committed
context. The state reservation includes both encoder histories, derived from
the encoder's convolution input grids, and the streaming decoder cache. These
caches are released through the same close/reset hooks. Condition encoding
currently requires the unpatched, non-tiled Wan encoder path; the existing
decoder's tiling fallback remains independent. Real-weight GPU parity with a
full-horizon encode still requires validation because the pointwise posterior
projection now runs per block.

DreamZero reports the measured 603 MiB per-session Wan VAE causal-convolution
state.

## Concurrency and routing limits

The current runner executes one request at a time:

- `max_num_seqs` must be one;
- request batching and diffusion step execution are rejected;
- one AR block is generated per engine request; and
- an AR-Diffusion stage must have exactly one replica.

The single-replica restriction is intentional. Multi-replica support requires
session-affine routing so every tick, reset, and close reaches the worker that
owns the session. Random or round-robin routing is not correct.

Multiple resident sessions may share one runner. Capacity selection accounts
for all persistent pools, and the runner performs LRU eviction through the same
model lifecycle hook used by explicit close.

## Model boundary

The generic runtime transports controls as opaque
`ARDiffusionControlInput(track, schema, data)` values. Model adapters validate
and reduce those values. This keeps target/velocity, key state, pose,
intrinsics, and other model-specific conventions out of the session protocol.

For LingBot World v2:

- `lingbot_world/actions.py` parses key-state and trajectory controls;
- `lingbot_world/camera.py` loads or constructs camera trajectories and Plücker embeddings;
- `lingbot_world/transformer.py` implements checkpoint-compatible causal attention; and
- `lingbot_world/pipeline.py` constructs conditioning, owns small non-KV session state, and
  produces one block plus the standard metadata envelope.

## Ulysses sequence parallelism

LingBot supports pure Ulysses sequence parallelism for both direct and
AR-Diffusion execution. With Ulysses degree greater than one, hidden tokens,
camera features, token-expanded timestep modulation, and RoPE tables are sharded
together. Without SP, timestep modulation retains the frame-broadcast path.
Self-attention performs the sequence-to-head all-to-all before reading or writing
paged KV, while static text K/V uses the same local head shard. Text K/V shards
own compact storage; cross-attention exchanges query/output layouts to use these
shards. This retains the shared cache geometry and reduces text K/V storage at
the cost of two all-to-all calls per layer.

The output head projects local tokens before gathering the flow values. For
the 14B model this reduces the gathered width from 5120 to 64; frame modulation
uses each shard's global token offset, including shards that split a frame. Only
`ulysses_mode="strict"` is supported; `advanced_uaa`, Ring, and AllGather-KV modes
remain unsupported for this model.

## Non-goals

This contract does not currently provide:

- a public HTTP or WebSocket request schema (the structured-interaction
  frontend is tracked separately in
  [#5527](https://github.com/vllm-project/vllm-omni/pull/5527));
- camera/action semantics shared by every world model;
- session migration or replication across workers;
- retry of an ambiguous partially executed chunk;
- cross-stage KV transfer; or
- stateful streaming VAE decode.

Those features can be layered on top without adding LingBot-specific identity
or lifecycle fields to the generic runtime.

## Required regression coverage

CPU contract tests cover:

- separation of tick correlation IDs from internal engine routing IDs;
- event ordering, metadata equality, and reducer fail-closed commit;
- close/disconnect failure tombstones and cleanup retry;
- capacity one under the default fraction for shipped LingBot geometry;
- capacity expansion under a tuned fraction;
- DreamZero model-owned state accounting;
- runner session reuse, reset, close, LRU eviction, and forward cleanup; and
- LingBot model registration, imports, camera/action reduction, and one-block
  output metadata.

GPU validation must additionally exercise real model loading, action input,
prompt switching, rolling-window replacement, reset, close, finite output
latents, and exact metadata/request identity.

===== FILE: docs/reviews/cp3_ev_code_excerpts.md =====
# Code excerpts from vllm-omni @ 7b4dc7633bde8642f0c05f77bd018751541df404 (extracted by the author with sed -n; line numbers are real)

## vllm_omni/diffusion/interaction/registry.py:17-28
```python
   17  STRUCTURED_HANDLER_REGISTRY: dict[str, dict[str, type[InteractionHandler]]] = {
   18      # Pipeline class name -> modality -> handler class.
   19      "HeliosPipeline": {
   20          "prompt": PromptInteractionHandler,
   21      },
   22      "HeliosPyramidPipeline": {
   23          "prompt": PromptInteractionHandler,
   24      },
   25      "LingBotWorldCausalDMDPipeline": {
   26          "camera": SE3DeltaCameraHandler,
   27      },
   28  }
```

## vllm_omni/diffusion/interaction/coordinator.py:55-125
```python
   55      def needs_chunk_media(self) -> bool:
   56          """Whether any registered handler needs chunk media/latent counts + fps."""
   57          return any(handler.needs_chunk_media for handler in self._handlers.values())
   58  
   59      def get_handler(self, modality: str) -> InteractionHandler:
   60          handler = self._handlers.get(modality)
   61          if handler is None:
   62              raise ValueError(
   63                  f"interaction modality {modality!r} is not supported by pipeline {self.model_class_name!r}"
   64              )
   65          return handler
   66  
   67      def enqueue(
   68          self,
   69          state: StepRequestState,
   70          *,
   71          modality: str,
   72          event_id: str,
   73          received_at: float,
   74          payload: InteractionPayload,
   75          transition_chunks: int | None,
   76      ) -> None:
   77          """Fan out enqueue to handlers in stable order (prompt first)."""
   78          handler = self.get_handler(modality)
   79          handler.enqueue(
   80              state,
   81              event_id=event_id,
   82              received_at=received_at,
   83              payload=payload,
   84              transition_chunks=transition_chunks,
   85          )
   86  
   87      def enqueue_parts(
   88          self,
   89          state: StepRequestState,
   90          *,
   91          parts: list[tuple[str, InteractionPayload]],
   92          event_id: str,
   93          received_at: float,
   94          transition_chunks: int | None,
   95      ) -> None:
   96          """Ensure every modality is supported and every payload validates, then enqueue.
   97  
   98          Composite events must not partially mutate queues when a later track is
   99          unsupported or carries an invalid payload.
  100          """
  101          if not parts:
  102              raise ValueError("interaction event requires prompt and/or multi_modal_data")
  103  
  104          # Reconcile rank-local samples so USP/SP shards share one arrival time.
  105          received_at = synchronized_monotonic_time(received_at)
  106  
  107          handlers = [(self.get_handler(modality), payload) for modality, payload in parts]
  108          for handler, payload in handlers:
  109              handler.validate_payload(
  110                  state,
  111                  event_id=event_id,
  112                  payload=payload,
  113                  transition_chunks=transition_chunks,
  114              )
  115          for (modality, payload), (handler, _) in zip(parts, handlers, strict=True):
  116              del handler
  117              self.enqueue(
  118                  state,
  119                  modality=modality,
  120                  event_id=event_id,
  121                  received_at=received_at,
  122                  payload=payload,
  123                  transition_chunks=transition_chunks,
  124              )
  125  
```

## vllm_omni/entrypoints/openai/serving_video_output_stream.py:140-180
```python
  140                      websocket,
  141                      request_id,
  142                      stop_event,
  143                      send_lock,
  144                      progress,
  145                      interaction_payloads_by_id,
  146                  )
  147              )
  148              async for chunk, metadata in self._stream_video_bytes(request, request_id, output_format, progress):
  149                  if stop_event.is_set():
  150                      stopped = True
  151                      break
  152                  async with send_lock:
  153                      metadata["transport_chunk_index"] = chunks_sent
  154                      await websocket.send_json(metadata)
  155                      await websocket.send_bytes(chunk)
  156                  chunks_sent += 1
  157                  progress.touch()
  158  
  159              async with send_lock:
  160                  await websocket.send_json(
  161                      {
  162                          "type": "session.done",
  163                          "request_id": request_id,
  164                          "chunks": chunks_sent,
  165                          "stopped": stopped or stop_event.is_set(),
  166                      }
  167                  )
  168          except WebSocketDisconnect:
  169              logger.info("Streaming video output: client disconnected")
  170              if request_id is not None:
  171                  await self._abort_request(request_id)
  172          except Exception as e:
  173              if stop_event.is_set():
  174                  try:
  175                      async with send_lock:
  176                          await websocket.send_json(
  177                              {
  178                                  "type": "session.done",
  179                                  "request_id": request_id,
  180                                  "chunks": chunks_sent,
```

## vllm_omni/entrypoints/openai/serving_video_output_stream.py:455-480
```python
  455                  send_lock=send_lock,
  456              )
  457              return
  458  
  459          interaction_payloads_by_id[event_id] = normalized
  460  
  461          try:
  462              await self._engine_client.submit_interaction_async(
  463                  request_id,
  464                  interaction=normalized,
  465              )
  466          except Exception:
  467              logger.exception("Failed to apply interaction for request %s", request_id, exc_info=True)
  468              interaction_payloads_by_id.pop(event_id, None)
  469              await self._send_error(
  470                  websocket,
  471                  "Failed to apply interaction",
  472                  code="interaction_failed",
  473                  request_id=request_id,
  474                  event_id=event_id,
  475                  send_lock=send_lock,
  476              )
  477              return
  478  
  479          try:
  480              async with send_lock:
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:745-800
```python
  745          latent_height = self._ar_height // spatial
  746          latent_width = self._ar_width // spatial
  747          tokens_per_frame = (latent_height // patch_height) * (latent_width // patch_width)
  748          total_window_frames = (
  749              int(self.transformer.config.local_attn_size)
  750              if int(self.transformer.config.local_attn_size) != -1
  751              else int(self.transformer.config.sliding_window_num_frames)
  752          )
  753          sink_frames = int(self.transformer.config.sink_size)
  754          recent_window_frames = total_window_frames - sink_frames
  755          if recent_window_frames <= 0:
  756              raise ValueError("LingBot AR-Diffusion cache needs a positive recent window after reserving sink frames.")
  757          condition_latent_frames = int(self.transformer.config.num_frames_per_block)
  758          condition_channels = self.vae_scale_factor_temporal + int(self.transformer.config.out_channels)
  759          element_size = torch.empty((), dtype=self.transformer.dtype).element_size()
  760          condition_bytes_per_session = (
  761              condition_channels * condition_latent_frames * latent_height * latent_width * element_size
  762          )
  763          # Each layer retains scale and shift for the rank-local camera tokens
  764          # across all forwards of a block, including between scheduler calls.
  765          camera_tokens = tokens_per_frame * condition_latent_frames
  766          sp_size = int(self.od_config.parallel_config.ulysses_degree)
  767          camera_bytes_per_session = (
  768              2
  769              * int(self.transformer.config.num_layers)
  770              * ((camera_tokens + sp_size - 1) // sp_size)
  771              * int(self.transformer.config.num_attention_heads)
  772              * int(self.transformer.config.attention_head_dim)
  773              * element_size
  774          )
  775          return ARDiffusionKVCacheSpec(
  776              num_layers=int(self.transformer.config.num_layers),
  777              num_kv_heads=int(self.transformer.blocks[0].self_attn.num_sp_heads),
  778              head_size=int(self.transformer.config.attention_head_dim),
  779              tokens_per_frame=tokens_per_frame,
  780              frames_per_block=int(self.transformer.config.num_frames_per_block),
  781              window_frames=recent_window_frames,
  782              sink_frames=sink_frames,
  783              kv_branches=(ARDiffusionKVBranchSpec(self._AR_BRANCH, 0),),
  784              session_capacity=2,
  785              cross_attention=(
  786                  ARDiffusionCrossAttentionKVSpec(
  787                      self._AR_TEXT_CACHE,
  788                      _MAX_SEQUENCE_LENGTH,
  789                      # Cross-attention keeps every local head on every rank rather than sharding heads across
  790                      # the Ulysses group, so the text pool holds that many heads, not the self-attention share.
  791                      num_kv_heads=int(self.transformer.blocks[0].cross_attn.num_local_heads),
  792                  ),
  793              ),
  794              model_owned_state_bytes_per_session=(
  795                  condition_bytes_per_session
  796                  + camera_bytes_per_session
  797                  + 2 * self._condition_encoder_cache_bytes()  # Committed and in-flight histories.
  798                  + self._streaming_decode_bytes_per_session()
  799              ),
  800          )
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:1880-1940
```python
 1880          if (inputs.height, inputs.width) != (self._ar_height, self._ar_width):
 1881              raise ValueError(
 1882                  "LingBot AR-Diffusion request resolution must match the "
 1883                  f"fixed cache geometry {self._ar_height}x{self._ar_width}."
 1884              )
 1885          block_frames = int(self.transformer.config.num_frames_per_block)
 1886          total_chunks = inputs.num_latent_frames // block_frames
 1887          if inputs.camera_action_script is not None and len(inputs.camera_action_script) != total_chunks:
 1888              raise ValueError(
 1889                  "camera_action_script must contain one action list per generated chunk; "
 1890                  f"got {len(inputs.camera_action_script)} chunks for {total_chunks} requested chunks."
 1891              )
 1892          dtype = self.transformer.dtype
 1893          prompt_embeds = self.encode_prompt(
 1894              inputs.prompt,
 1895              max_sequence_length=inputs.max_sequence_length,
 1896              dtype=dtype,
 1897          )
 1898          camera_trajectory_cache = None
 1899          camera_embedding_cache = None
 1900          if inputs.camera_trajectory is not None:
 1901              available_frames = int(inputs.camera_trajectory.poses.shape[0])
 1902              if available_frames < inputs.num_frames:
 1903                  raise ValueError(
 1904                      "camera trajectory frames must be at least num_frames; "
 1905                      f"got camera_frames={available_frames}, num_frames={inputs.num_frames}."
 1906                  )
 1907              truncated = CameraTrajectory(
 1908                  poses=inputs.camera_trajectory.poses[: inputs.num_frames],
 1909                  intrinsics=inputs.camera_trajectory.intrinsics[: inputs.num_frames],
 1910              )
 1911              camera_trajectory_cache = interpolate_camera_trajectory(truncated, inputs.num_latent_frames)
 1912              # Embed the whole trajectory once, exactly as request mode does, and
 1913              # slice it per block in ``_prepare_next_chunk``. Embedding each chunk
 1914              # on its own would normalize that block's framewise translations by
 1915              # its own largest step, so a slow block would be conditioned as
 1916              # full-speed motion and drift from offline replay of the same path.
 1917              camera_embedding_cache, _ = self._prepare_camera(inputs, dtype=dtype)
 1918          state.prompt_embeds = prompt_embeds
 1919          state.chunk_index = 0
 1920          state.step_index = 0
 1921          state.step_in_chunk = 0
 1922          state.total_chunks = total_chunks
 1923          state.chunk_num_steps = len(LINGBOT_DMD_TIMESTEPS)
 1924          state.extra = {
 1925              "inputs": inputs,
 1926              "schedule": _build_shifted_flow_schedule(flow_shift=inputs.flow_shift),
 1927              "dtype": dtype,
 1928              "block_frames": block_frames,
 1929              "camera_pitch": 0.0,
 1930              "camera_tail": None,
 1931              "camera_action_script": inputs.camera_action_script,
 1932              "camera_trajectory_cache": camera_trajectory_cache,
 1933              "camera_embedding_cache": camera_embedding_cache,
 1934          }
 1935          self._ar_text_caches(prompt_embeds, invalidate=False)
 1936          self._ar_sessions[state.request_id] = _LingBotARSessionState()
 1937          return state
 1938  
 1939      def _prepare_next_chunk(self, state: StepRequestState) -> None:
 1940          extra = state.extra
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:1950-2060
```python
 1950              start_frame=start_frame,
 1951              session_state=session_state,
 1952              dtype=extra["dtype"],
 1953          )
 1954          previous = extra.get("camera_tail")
 1955  
 1956          if extra.get("camera_action_script") is not None:
 1957              if (
 1958                  (camera_session := state.interaction_sessions.get("camera"))
 1959                  and isinstance(camera_session, CameraSession)
 1960                  and camera_session.has_received_input
 1961              ):
 1962                  raise ValueError("Cannot use mid-generation camera interaction together with camera_action_script; ")
 1963              chunk_actions = extra["camera_action_script"][state.chunk_index]
 1964              action_trajectory, camera_pitch = integrate_lingbot_camera_actions(
 1965                  chunk_actions,
 1966                  width=inputs.width,
 1967                  height=inputs.height,
 1968                  initial_pose=(previous.poses[-1] if previous is not None else None),
 1969                  initial_pitch=float(extra.get("camera_pitch", 0.0)),
 1970              )
 1971              extra["camera_pitch"] = camera_pitch
 1972              media_frames = self._chunk_media_frame_count(state, block_frames=block_frames)
 1973              chunk_inputs = replace(
 1974                  inputs,
 1975                  camera_trajectory=action_trajectory,
 1976                  camera_actions=chunk_actions,
 1977                  num_frames=media_frames,
 1978                  num_latent_frames=block_frames,
 1979              )
 1980              camera, camera_tail = self._prepare_camera(
 1981                  chunk_inputs,
 1982                  dtype=extra["dtype"],
 1983                  previous=previous,
 1984              )
 1985          elif extra.get("camera_embedding_cache") is not None:
 1986              if (
 1987                  (camera_session := state.interaction_sessions.get("camera"))
 1988                  and isinstance(camera_session, CameraSession)
 1989                  and camera_session.has_received_input
 1990              ):
 1991                  raise ValueError("Cannot use mid-generation camera interaction together with camera_embedding_cache; ")
 1992              trajectory = extra["camera_trajectory_cache"]
 1993              camera = extra["camera_embedding_cache"][:, :, start_frame:stop_frame]
 1994              camera_tail = CameraTrajectory(
 1995                  poses=trajectory.poses[stop_frame - 1 : stop_frame].clone(),
 1996                  intrinsics=trajectory.intrinsics[stop_frame - 1 : stop_frame].clone(),
 1997              )
 1998          elif self._interaction_coordinator is not None and self._interaction_coordinator.has_modality("camera"):
 1999              # Poses come from the latest boundary apply: ``prepare_encode`` for
 2000              # chunk 0, the diffusion runner for later chunks. This method only
 2001              # digests them — it does not apply interactions itself.
 2002              camera_session = state.interaction_sessions.get("camera")
 2003              if not isinstance(camera_session, CameraSession) or camera_session.last_absolute_poses is None:
 2004                  raise RuntimeError(
 2005                      "LingBot camera interaction requires apply_interaction_at_chunk_boundary before prepare_next_chunk."
 2006                  )
 2007              absolute_poses = camera_session.last_absolute_poses
 2008              media_frames = self._chunk_media_frame_count(state, block_frames=block_frames)
 2009              num_latent_frames = block_frames
 2010              if int(absolute_poses.shape[0]) != num_latent_frames:
 2011                  raise ValueError(
 2012                      "camera interaction must produce exactly one pose per latent frame; "
 2013                      f"got {int(absolute_poses.shape[0])}, expected {num_latent_frames}."
 2014                  )
 2015              action_trajectory = camera_trajectory_from_absolute_pose(
 2016                  absolute_poses,
 2017                  width=inputs.width,
 2018                  height=inputs.height,
 2019              )
 2020              chunk_inputs = replace(
 2021                  inputs,
 2022                  camera_trajectory=action_trajectory,
 2023                  camera_actions=None,
 2024                  num_frames=media_frames,
 2025                  num_latent_frames=num_latent_frames,
 2026              )
 2027              camera, camera_tail = self._prepare_camera(
 2028                  chunk_inputs,
 2029                  dtype=extra["dtype"],
 2030                  previous=previous,
 2031                  latent_aligned=True,
 2032              )
 2033          else:
 2034              raise RuntimeError("LingBot step execution is missing a camera trajectory or action script.")
 2035          if camera.shape[2:] != condition.shape[2:]:
 2036              raise RuntimeError(
 2037                  "folded camera and image condition must share latent frame/height/width geometry; "
 2038                  f"got camera={tuple(camera.shape)}, condition={tuple(condition.shape)}."
 2039              )
 2040          generator = getattr(state.sampling, "generator", None)
 2041          if not isinstance(generator, torch.Generator):
 2042              raise ValueError("LingBot World requires the runner-provided torch.Generator.")
 2043          extra["condition"] = condition
 2044          extra["camera"] = camera
 2045          # One camera-modulation cache per block: the four probes and the
 2046          # commit below are separate scheduler steps, so the block runner
 2047          # cannot open the reuse window around them the way generate_block
 2048          # does around its own loop. Holding the cache here makes the window
 2049          # span exactly this block, per request.
 2050          extra["camera_cache"] = CameraModulationCache()
 2051          extra["camera_tail"] = camera_tail
 2052          extra["start_frame"] = start_frame
 2053          extra["ar_cross_attention"] = self._ar_text_caches(
 2054              cast(torch.Tensor, state.prompt_embeds),
 2055              invalidate=False,
 2056          )
 2057          state.latents = randn_tensor(
 2058              (
 2059                  1,
 2060                  self.transformer.config.out_channels,
```

## vllm_omni/diffusion/models/lingbot_world/pipeline.py:2180-2200
```python
 2180              stage_durations=self.stage_durations if hasattr(self, "stage_durations") else None,
 2181              chunk_index=completed_chunk_index,
 2182              total_chunks=state.total_chunks,
 2183              finished=state.request_denoise_completed,
 2184          )
 2185  
 2186      def _chunk_media_frame_count(self, state: StepRequestState, *, block_frames: int) -> int:
 2187          """Pixel frames this chunk will emit when decoded.
 2188  
 2189          Independent (non-streaming) decode restarts causal expansion every block,
 2190          so each chunk is ``(block_frames - 1) * temporal + 1`` frames.
 2191          Streaming decode expands only the session's opening latent to one frame and every later latent to the full
 2192          temporal factor, so chunk 0 matches the independent count and later chunks are ``block_frames * temporal``.
 2193          """
 2194          decode_state = self._streaming_decode_states.get(state.request_id)
 2195          if decode_state is not None and decode_state.started:
 2196              return block_frames * self.vae_scale_factor_temporal
 2197          return (block_frames - 1) * self.vae_scale_factor_temporal + 1
 2198  
 2199      def peek_chunk_media(self, state: StepRequestState) -> ChunkMediaSpec:
 2200          """Expose this chunk's decoded media extent and latent step count."""
```

## vllm_omni/deploy/lingbot_world_v2_stepwise.yaml:1-50
```python
    1  # LingBot-World 2.0 stepwise deploy: single diffusion stage for WS /v1/realtime/video.
    2  #
    3  # One AsyncOmni request is one rollout: prepare_encode runs once, then every
    4  # four DMD steps stream one AR block. Step execution keeps AR-Diffusion paged KV
    5  # on ARDiffusionModelRunner, so this stage must stay at max_num_seqs=1.
    6  #
    7  # The cache geometry is fixed at load time, so ar_diffusion_height/width must
    8  # match the height/width a client asks for.
    9  
   10  pipeline: lingbot_world
   11  async_chunk: false
   12  distributed_executor_backend: mp
   13  dtype: bfloat16
   14  
   15  stages:
   16    - stage_id: 0
   17      devices: "0"
   18      max_num_seqs: 1
   19      enforce_eager: true
   20      model_class_name: LingBotWorldCausalDMDPipeline
   21      # LingBot runs on the AR-Diffusion engine (engine-level paged KV cache).
   22      engine_backend: vllm_omni.experimental.ar_diffusion.engine.ARDiffusionEngine
   23      # One request, many streamed chunks. streaming_output implies step_execution,
   24      # but both are stated here so the topology is readable on its own.
   25      step_execution: true
   26      streaming_output: true
   27      # num_inference_steps is for the step scheduler, not the pipeline: it sizes a
   28      # request's step budget before the pipeline is reached, so a served request
   29      # does not have to carry it. The pipeline itself pins the causal-fast
   30      # checkpoint's four-step DMD schedule and rejects any other count.
   31      default_sampling_params:
   32        num_inference_steps: 4
   33        output_type: pil
   34        extra_args:
   35          flow_shift: 5.0
   36      model_config:
   37        # Multi-rank width sharding changes floating-point numerics at shard borders.
   38        # Set false for full-frame VAE decode while keeping DiT sequence parallelism.
   39        lingbot_vae_spatial_sharding: true
   40        ar_diffusion_height: 480
   41        ar_diffusion_width: 832
   42        ar_diffusion_kv_config:
   43          gpu_memory_fraction: 0.6
   44          warmup_cudagraph: true
```
