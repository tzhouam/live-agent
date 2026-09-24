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