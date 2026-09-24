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
