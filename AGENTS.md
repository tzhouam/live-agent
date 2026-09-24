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
