# Live Agent — Project Specification (single source of truth)

Status: **v0.2 provisional** (2026-09-25; revised after Codex checkpoint 1, see
`docs/codex_reviews.md`). **Precedence:** `goal.md` (the owner's brief) sets the
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
| A2 | The reference agent's implementation ("MiniMax H3") is unverified | Assumption |
| A3 | Speech (ASR/TTS) and lip sync probably need components outside LingBot-World | To verify (backbone note) |
| Q1 | Does LingBot-World 2.0 accept mid-session text/prompt changes, or only camera/action signals? | Open → backbone investigation |
| Q2 | Can a world model with camera/action control express character behavior (gestures, expressions)? | Open |
| Q3 | Audience: the first acceptance scenario is **one private user** (1:1). Public livestream with chat is a second evaluation scenario that reuses the same agent, with separate memory scopes | Decision D-001 (provisional) |
| Q4 | Provenance, license, and working inference path of the local "MiniMax H3" copy | Open → reference-agent note |
| Q5 | Is a simpler pipeline (LLM + TTS + talking-head avatar, with no world model) enough for the focused demo? It must be carried as a competing baseline | Open. The evaluation must be able to favor it |
| Q6 | Proposed "real-time" targets (time to first speech, time to first correctly conditioned visual, p50/p95) | Set in the proposal, labeled as targets |

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
