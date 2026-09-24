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

## Open questions

See `docs/PROJECT.md` (A*/Q* table). Resolved questions move here with the evidence.
