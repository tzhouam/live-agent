You are GPT-6 Sol acting as the INDEPENDENT REVIEWER for the "live-agent" research project. Checkpoint 1 of 4: project understanding, requirements, and assumptions. Reviewed revision: git commit ef3a0f3 (files inlined below). Do not edit any files.

Additional initial observations by the author (Claude), for you to challenge:
- Upstream vLLM-Omni main cloned read-only at external/vllm-omni, commit 7b4dc7633bde (2026-09-24). Its recipe recipes/Robbyant/LingBot-World-2.0.md states: only checkpoint robbyant/lingbot-world-v2-14b-causal-fast-diffusers is supported (CC BY-NC-SA, non-commercial); 4 DMD steps; validated on H200/B200 at 480x832; public realtime path is `WS /v1/realtime/video` (stepwise, one request per rollout, one fMP4 chunk per AR block of 3 latent frames = 12 raw frames); mid-session control is structural SE3 camera (`session.interaction`, target/velocity modes); prompt switching is validated in the (deprecated) tick path; max_num_seqs=1, single replica; stateful streaming VAE decode not implemented (seams possible). A detailed code-level analysis is in progress.
- Hardware: 8x NVIDIA L20X (~140 GB each), shared, scheduled via canhazgpu (no guaranteed allocation).
- A local copy of "MiniMax H3" is at /data/zhoutaichang/worldmodel/MiniMax-H3/FL2VA (subfolders transformer, video_vae, audio_vae, processor with camera .npy files) — possibly a joint audio+video model with camera conditioning. Unverified; provenance and license unknown.
- Codex CLI 0.156.0; `codex exec -m gpt-6-sol` verified via the session rollout recording "model":"gpt-6-sol". The Codex MCP server failed to connect; the CLI is used. The shell sandbox cannot start on this host, so material is inlined.
- A prior attempt of this checkpoint failed because the reviewer could not read files; its provisional findings were: (a) test the working hypothesis against competing approaches rather than selecting an architecture early; (b) define an explicit acceptance scenario and measurable "real-time"; (c) model/hardware feasibility unverified; (d) record full audit metadata per review. You may confirm, refine, or reject these.

Critique:
1. Does docs/PROJECT.md faithfully capture goal.md? List any requirement missed, weakened, or distorted.
2. Are the assumptions / open questions the right ones? Which material assumptions are missing?
3. Is the instruction-file structure (single spec + thin pointers) sound and consistent?
4. Is the review procedure auditable enough?
5. Early risks or framing errors to fix before literature and architecture work (working hypothesis framing; demo scoping; the fact that LingBot-World is a camera-controlled world model rather than an avatar model).
Output a numbered list of findings, each tagged blocking/major/minor with a concrete suggested fix. Be concise.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: goal.md =====
# Project Goal: A Real-Time, Personalized Live Agent with Reasoning and Long-Term Memory

You are the lead research scientist and systems architect for this project.

This directory is the workspace for developing a demo of a real-time, personalized live agent: an interactive digital persona that can engage with users through live video and, where supported, speech; follow user instructions; reason about ongoing interactions; and maintain useful long-term memories across sessions.

Your immediate assignment is to produce an evidence-grounded academic research proposal and establish the project’s persistent documentation. Do not jump directly into a full implementation.

## 1. Project Motivation and Scope

The central research question is:

**How can we combine real-time video generation with reasoning, instruction following, and persistent memory to create a coherent, controllable, personalized live agent?**

Our starting hypothesis is that real-time video generation alone is insufficient for reliable, stateful agent behavior. Investigate this hypothesis rather than asserting that all existing video generation models lack reasoning.

We want more than a chatbot connected to a video generator. The proposed system should connect user intent, reasoning, memory, and observable audiovisual behavior in a continuous interaction loop.

The desired capabilities include:
- Following instructions during an ongoing interaction, including corrections, interruptions, and changing goals.
- Remembering relevant user preferences, facts, and prior interactions across sessions.
- Maintaining a consistent persona and coherent visual, conversational, and behavioral state.
- Translating decisions into controls that the underlying generation model can actually execute.
- Remaining responsive while reasoning, retrieving memories, and generating continuous output.

Treat personalized interaction and livestreaming as the initial use cases. Define a focused demo scenario rather than expanding into an unrestricted general-purpose assistant.

### Preferred video-generation foundation

Investigate **LingBot-World v2 / LingBot-World 2.0 in vLLM-Omni** as the preferred video-generation backbone.

Repository:
https://github.com/vllm-project/vllm-omni

Verify the exact model, checkpoint, implementation, supported controls, integration maturity, and hardware requirements. Do not assume that capabilities described in a paper are already implemented in the local checkout or available through the serving interface.

Do not silently replace this backbone with another model. Explain any feasibility gaps and justify proposed alternatives.

### Reference live agent

Study:
https://www.twitch.tv/sylar_nv

According to the project owner, this agent was built by a friend and is based purely on **MiniMax H3**. Treat that implementation detail as owner-provided information until independently verified.

Use the agent as a reference for the intended experience. Assess publicly observable behavior where accessible, but do not infer private implementation details from the stream alone.

Our ambition is to improve instruction following, controllability, and long-term memory. Do not presume the reference agent lacks these capabilities or claim an improvement before evaluation.

## 2. Inspect the Workspace and Establish Project Instructions

First inspect the existing directory, repository structure, relevant code, and any existing project instructions. Preserve unrelated content and uncommitted work.

Create or update:
- `CLAUDE.md`
- `AGENT.md`
- `AGENTS.md`

These files must clearly document the project’s purpose, current scope, intended capabilities, research standards, deliverables, and required Codex review process.

Keep them concise and consistent. Use shared documentation and cross-references to avoid contradictory copies of the project specification. Preserve useful existing instructions.

Record a provisional project understanding early, then update it after research and review. Distinguish confirmed requirements from assumptions and open questions.

## 3. Conduct a Broad, Critical Research Review

Research relevant academic papers, preprints, technical reports, engineering blogs, real products, and open-source software. Include foundational work and recent developments as of the research date.

Cover at least these areas:

1. Real-time and streaming video generation, interactive world models, and controllable generation.
2. Multimodal agents, live conversational systems, digital humans, and autonomous livestreaming agents.
3. Reasoning, planning, instruction following, and closed-loop control over generative models.
4. Long-term agent memory, personalization, episodic and semantic memory, retrieval, consolidation, correction, and forgetting.
5. Low-latency orchestration, asynchronous execution, interruption handling, and audiovisual synchronization.
6. Evaluation of interactive agents: task success, memory reliability, behavioral consistency, responsiveness, and user experience.

Prioritize primary sources for technical claims. Use blogs and products to understand practical engineering and user experience, while distinguishing marketing claims from reproducible evidence.

Build a related-work comparison matrix. For each important system, record its approach, relevant capabilities, memory mechanism, control interface, reported latency and hardware, code or model availability, limitations, and relevance to this project.

Record publication dates and source URLs. For repository evidence, record the inspected branch or commit and relevant file paths or symbols.

Do not produce only a bibliography. Synthesize what existing work solves, what remains unresolved, what can be reused, and where a defensible research contribution may exist. Do not claim novelty merely because several existing components are combined.

## 4. Verify the Backbone’s Actual Integration Surface

Inspect the relevant vLLM-Omni implementation and upstream model materials before recommending an architecture.

Determine:
- Which inputs and conditioning mechanisms are supported.
- Whether instructions or controls can change during an active session.
- How streaming chunks, scheduling, session state, and generation caches are managed.
- What can be interrupted, cancelled, reset, or resumed.
- Which controls affect camera motion, character behavior, scene content, or other observable outputs.
- Whether speech, audio generation, or lip synchronization requires additional components.
- What latency, memory, and compute evidence is available.

Identify concrete integration points and missing interfaces. Explicitly separate:
- Capabilities available in the inspected implementation.
- Capabilities reported upstream but not verified locally.
- Capabilities requiring engineering extensions.
- Capabilities requiring new training or research.

Do not assume that camera control implies character control, or that high generation FPS implies low instruction-to-response latency.

When access, hardware, or documentation is insufficient, state the limitation and specify the smallest experiment needed to resolve it.

## 5. Develop and Compare Candidate Architectures

Compare plausible alternatives before selecting a design. Consider a simple baseline, a modular reasoning-and-memory controller with a streaming generator, and a more tightly coupled approach where technically justified.

Do not treat any architecture as predetermined.

Address the following questions explicitly:

### Reasoning and control

How are user instructions converted into structured, time-aligned controls that the generator can execute?

Define the intermediate representation, component interfaces, persistent state, and feedback mechanism. Explain how the system detects and recovers when generated behavior does not match the requested action.

Distinguish “the language model says it followed the instruction” from observable compliance in the generated output.

### Real-time execution

Explain which operations lie on the critical path and which can run asynchronously.

Specify how the design handles interruptions, stale plans, queued output, revised instructions, buffering, and synchronization between speech and video.

Provide an end-to-end latency budget with explicit assumptions. Label numerical targets as proposed targets, not measured results.

### Long-term memory

Distinguish:
- Working context within an interaction.
- Persistent user facts and preferences.
- Episodic interaction history.
- Visual or world-state continuity.
- Model caches used for inference.

Explain memory writing, retrieval, consolidation, correction, deletion, provenance, and conflict resolution. Do not equate a larger context window or a KV cache with reliable long-term memory.

Address separation between private personal memories and public livestream content. Prevent generated or inferred events from being stored as confirmed facts about the user.

### Feasibility and trade-offs

Compare expected quality, latency, controllability, complexity, compute cost, and training requirements.

Separate a feasible first demo from longer-term research extensions. Avoid requiring foundation-model training unless the evidence shows it is necessary.

Include architecture and interaction-sequence diagrams with editable sources.

## 6. Produce an Academic Research Proposal

Write a substantive proposal suitable for technical and academic review, not a product pitch or a generic implementation checklist.

Include:
1. Title and abstract.
2. Motivation, target scenario, and problem definition.
3. Related work and research gap.
4. Research questions and falsifiable hypotheses.
5. Proposed method and system architecture.
6. Verified vLLM-Omni integration plan.
7. Experimental design, baselines, and ablations.
8. Evaluation metrics and success criteria.
9. Demo milestones, resource assumptions, and feasibility risks.
10. Limitations, privacy and safety considerations, and references.

Make the expected scientific contribution explicit and distinguish it from engineering integration.

### Evaluation requirements

Design experiments that test the claimed benefits directly. Include:
- Instruction-following and multi-step task success.
- Recovery from interruptions and changing instructions.
- Cross-session memory recall, factual precision, correction, and forgetting.
- Persona and visual-state consistency over extended interactions.
- Time to first meaningful response and time to first correctly conditioned visual response.
- End-to-end p50/p95 latency, streaming stability, and compute cost.

Propose appropriate baselines and ablations, such as removing persistent memory, removing planning, or removing output verification.

Control for backbone, hardware, resolution, and workload where possible. Describe sample sizes, repeated trials, and uncertainty reporting.

Use the Twitch agent as a quantitative baseline only when access and reproducibility support a fair comparison; otherwise, identify it as a qualitative reference.

Do not fabricate experiments, measurements, user-study findings, or expected improvements. Clearly label cited results, locally measured results, hypotheses, estimates, and proposed targets.

## 7. Mandatory Independent Review with GPT-6 Sol in Codex

Use **GPT-6 Sol through Codex** as an independent reviewer throughout the work, not merely at the end.

First inspect the available Codex integration and verify the actual model identifier and invocation mechanism. Do not assume that naming a model in a prompt selects it.

Require review at these checkpoints:
1. Project understanding, requirements, and assumptions.
2. Literature synthesis, capability claims, and proposed research gap.
3. Candidate architectures, model integration, memory design, and latency feasibility.
4. Experimental design and the complete final proposal.

Submit all material assumptions, interpretations, and design decisions for review. Give the reviewer the relevant evidence and ask it to challenge unsupported claims, overlooked alternatives, interface mismatches, feasibility assumptions, and weak evaluation designs.

For each checkpoint:
- Obtain an independent critique.
- Address the critique with evidence or revisions.
- Record the issues raised, resulting changes, and remaining disagreements.
- Re-review material changes where necessary.

Maintain an auditable review log containing the actual model used, review date, reviewed artifact or revision, substantive feedback, and resolution status.

Cross-model agreement is not proof. Validate important claims against sources, inspected code, or experiments rather than treating consensus as verification.

If GPT-6 Sol or Codex is unavailable, document the exact blocker, continue the research, and mark the required review as pending. Do not simulate another model’s feedback, silently substitute a different reviewer, or claim full completion of this requirement.

## 8. Required Deliverables and Completion Criteria

Produce these artifacts, adapting supporting paths to existing repository conventions:

- `CLAUDE.md`, `AGENT.md`, and `AGENTS.md`: consistent project purpose and working instructions.
- `docs/research_proposal.md`: the complete academic proposal.
- `docs/related_work.md`: evidence-backed research synthesis and comparison matrix.
- `docs/decision_log.md`: material decisions, alternatives, evidence, assumptions, and unresolved questions.
- `docs/codex_reviews.md`: actual Codex review records and resolutions.
- `docs/references.bib`: verified bibliographic references.
- `docs/figures/`: editable architecture and interaction diagrams.

The proposal must be self-contained. Supporting documents should add detail, not hold essential explanations missing from the proposal.

Before finishing, check that major claims have evidence, proposed interfaces match verified capabilities, success criteria are measurable, instruction files agree, and the Codex review status is accurately reported.

Finish with a concise summary of the recommended direction, key evidence, strongest unresolved risks, review status, and files created or modified.

Proceed autonomously on non-blocking questions using clearly documented assumptions. Keep this phase focused on research, feasibility, and proposal development; do not start expensive training, paid deployments, public broadcasts, or unrelated repository changes.
===== FILE: docs/PROJECT.md =====
# Live Agent — Project Specification (single source of truth)

Status: **v0.1 provisional** (2026-09-25). Written before research and review, and
updated after each Codex checkpoint (see `docs/codex_reviews.md`). `CLAUDE.md`,
`AGENTS.md` and `AGENT.md` point here and must not restate this spec in their own words.
The original brief is `goal.md`.

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
| A1 | Local hardware is 8× NVIDIA L20X (≈140 GB each), scheduled through `gpu` (canhazgpu) | Observed 2026-09-25 (`nvidia-smi`) |
| A2 | The reference agent's implementation ("MiniMax H3") is unverified | Assumption |
| A3 | Speech (ASR/TTS) and lip sync probably need components outside LingBot-World | To verify (backbone note) |
| Q1 | Does LingBot-World 2.0 accept mid-session text/prompt changes, or only camera/action signals? | Open → backbone investigation |
| Q2 | Can a world model with camera/action control express character behavior (gestures, expressions)? | Open |
| Q3 | Is the demo audience one private user, a public chat, or both? | Assumed both, as separate modes |

## Deliverables (Phase 1)

| File | Content |
|------|---------|
| `docs/research_proposal.md` | Complete, self-contained academic proposal |
| `docs/related_work.md` | Evidence-backed synthesis and comparison matrix |
| `docs/backbone_verification.md` | Verified vLLM-Omni / LingBot-World integration surface |
| `docs/decision_log.md` | Decisions, alternatives, evidence, assumptions, open questions |
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
- For each checkpoint, log the date, model, reviewed git revision, issues,
  resolutions, and remaining disagreements in `docs/codex_reviews.md`. Raw
  reviewer output goes in `docs/reviews/`. Re-review material changes.
- If Codex is unavailable, record the exact blocker and mark the review
  **pending**. Never simulate or substitute a reviewer.

===== FILE: CLAUDE.md =====
# CLAUDE.md — live-agent

Project: research and demo a real-time, personalized live agent (live generated
video + speech, instruction following, reasoning, long-term memory).

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

If these files disagree, `docs/PROJECT.md` wins. Fix the others to match it.
