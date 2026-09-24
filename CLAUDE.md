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
