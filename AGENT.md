# AGENT.md — live-agent

This file exists for tools that read `AGENT.md`. It carries no separate rules.

- Project specification (single source of truth): [`docs/PROJECT.md`](docs/PROJECT.md)
- Rules for agents and reviewers (Codex / GPT-6 Sol): [`AGENTS.md`](AGENTS.md)
- Claude Code rules: [`CLAUDE.md`](CLAUDE.md)
- Original brief: [`goal.md`](goal.md)

`goal.md` sets the requirements, and `docs/PROJECT.md` records their current interpretation.
If any of these files disagree, log the conflict in `docs/decision_log.md` and fix it. Do not silently pick one.


## Agent operating rules

These owner instructions apply to subsequent work units.

- The main window orchestrates only: it plans, delegates, integrates, checks evidence and reports. Workers execute according to this project's ownership rules.
- Before each coherent core work unit, record in its plan or handoff: the objective or observed blocker, minimal necessary change, meaningful verification, and completion/stop condition.
- Before core action, discuss decisions, design, code approach, task/data selection, tests, experiments and analysis in English with actual Claude Code Opus 5.5 (`claude-opus-5-5`). Verify the returned model identity; do not substitute another model or claim an exchange that did not happen.
- The Opus discussion must cut unnecessary infrastructure, abstractions, duplicated tests and irrelevant work. Keep work only if it changes the answer to the current question or prevents a concrete defect, integrity failure or privacy breach; otherwise defer it.
- Project ownership prevails; this section does not change who executes. Where technical work, including design and independent review, is reserved to a named specialist, Opus reviews only necessity, scope and coordination. The technical plan stays specialist-owned, and reserved code is not shared for Opus technical review.
- Review per work unit, not per shell command. Routine execution within the reviewed plan needs no repeated approval. Substantive changes to scope, method, task selection or verification strategy require a brief replan and renewed Opus discussion before execution.
- Discuss completed results with Opus and accept work on actual evidence. Report offline tests separately from real execution; stop when the completion condition is met.
- Share only necessary sanitized inputs with external reviewers. Keep credentials, owner-private backend identity, private notes, frozen artifacts and project-specific guards protected. Do not reintroduce removed local token/context/length caps.
- If Opus is unavailable, report it and do not proceed with the affected core action without owner direction. Never impersonate a review or silently bypass it.
