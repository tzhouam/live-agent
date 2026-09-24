# Codex Review Log (GPT-6 Sol)

Auditable record of the mandatory independent reviews (goal.md §7). Raw
artifacts for each run are in `docs/reviews/<tag>_{instructions,prompt,review,events,meta}`.

## Reviewer setup (verified 2026-09-25)

| Item | Value | Evidence |
|---|---|---|
| Tool | Codex CLI `codex-cli 0.156.0` (`/home/zhoutaichang/.local/bin/codex`) | `codex --version` |
| Model requested | `gpt-6-sol` (`-m gpt-6-sol`; also the default in `~/.codex/config.toml`) | command line in each `*_meta.txt` |
| Model actually used | `gpt-6-sol`, provider `openai` | `"model":"gpt-6-sol"` in each session rollout (`~/.codex/sessions/2026/09/25/rollout-*.jsonl`; path recorded in `*_meta.txt`) |
| Available models (cache) | gpt-6-astra, gpt-6-sol, gpt-6-luna, gpt-5.6-*, gpt-5.5, … | `~/.codex/models_cache.json` |
| Codex MCP server | Failed to connect in the Claude Code session (`CONNECTION_CLOSED`). The CLI is used instead | session environment notice |
| Sandbox | The `bwrap` sandbox cannot start: `/proc/sys/user/max_user_namespaces = 0` ("No space left on device"). Running Codex unsandboxed was denied by the Claude Code permission policy. **Mitigation:** run `-s read-only` and inline all evidence through `tools/codex_review.sh`. **Limitation:** the reviewer can check only what is inlined, not browse the repo itself | cp1 attempt 1 output; `unshare` test |

## Summary table

| CP | Tag | Date (UTC) | Reviewed revision | Model (rollout) | Findings | Status |
|---|---|---|---|---|---|---|
| 1 | cp1_attempt1 | 2026-09-24T17:29Z | ef3a0f3 | gpt-6-sol | 6 provisional (reviewer could not read files) | Superseded by cp1 |
| 1 | cp1 | 2026-09-24T17:36Z | ef3a0f3 (+ inlined files) | gpt-6-sol | 7 (1 blocking, 5 major, 1 minor) | Resolved in d68466e. Blocking item #1 is carried into CP3 |
| 2 | cp2 | see `cp2_meta.txt` | 7cce79f | gpt-6-sol | 10 (2 blocking, 7 major, 1 minor) | Resolved in 8eb4d33. Re-reviewed as part of CP3 |
| 3 | cp3 | see `cp3_meta.txt` | ecbb880 | gpt-6-sol | 15 (2 blocking, 12 major, 1 minor) | Resolved in c085745. Re-reviewed as part of CP4 |

## Checkpoint 1 — project understanding, requirements, assumptions

**Attempt 1 (invalid).** The reviewer's shell sandbox failed on every file read,
so it reviewed only the prompt text. Its output is kept as
`docs/reviews/cp1_attempt1_review_sandbox_failed.md` but is not counted as a
review of the artifacts.

**Attempt 2 (`cp1`).** The inlined files were goal.md, docs/PROJECT.md v0.1,
CLAUDE.md, AGENTS.md, and AGENT.md, plus the author's initial observations.

| # | Sev. | Issue (abridged) | Disposition | Resolution |
|---|---|---|---|---|
| 1 | blocking | The demo may exceed what the backbone can control. The recipe shows only public camera control: no gestures, expressions, speech, or public mid-session prompt switching | **Accepted** | The backbone is being verified at code level (`docs/backbone_verification.md`). The demo scenario will be chosen after a control→observable-behavior table exists (goal §4/§5). Carried into CP3 for re-review |
| 2 | major | Acceptance scenario and "real-time" are undefined | **Accepted** | PROJECT.md Q3: 1:1 private user is the first acceptance scenario and livestream is the second (D-001). Q6: targets are set in the proposal |
| 3 | major | Feasibility assumptions are stated too confidently (GPU inventory vs. capacity; H3 provenance) | **Accepted** | A1 split into inventory (observed) and capacity (open). Q4 added for H3 provenance/license |
| 4 | major | The hypothesis has no competing account | **Accepted** | Q5: a simple LLM+TTS+talking-head pipeline is carried as a competing baseline that the evaluation can favor |
| 5 | major | The "single source of truth" drops binding requirements from goal.md | **Accepted** | goal.md now takes precedence. A requirement→deliverable checklist was added to PROJECT.md |
| 6 | major | The review log lacks a reproducible evidence trail | **Accepted** | `tools/codex_review.sh` records the prompt with its sha256, output, events, rollout path and model, repo and vLLM-Omni SHAs, dirty state, and exit code. PROJECT.md was updated |
| 7 | minor | CLAUDE.md dropped "where supported" for speech. AGENT.md precedence could override goal.md | **Accepted** | Both fixed |

Remaining disagreements: none.

## Checkpoint 2 — literature synthesis, capability claims, research gap

Tag `cp2`. Reviewed revision 7cce79f. Inlined: related_work.md, backbone_verification.md, the synthesis
sections of the three literature notes, and the reference-agent note. The reviewer followed some primary-source
links (arXiv) on its own.

| # | Sev. | Issue (abridged) | Disposition | Resolution (8eb4d33) and evidence |
|---|---|---|---|---|
| 1 | blocking | G1/TVC overclaims novelty: WorldMark already measures response latency | **Accepted after verification.** Claude read the WorldMark HTML: its latency is counted in *generated-video frames* until motion reaches half the reference speed. A targeted search also found ABot-World-0 (arXiv 2607.19191), which reports *wall-clock action-to-first-frame* time, i.e. when a frame becomes available, with no compliance check | TVC redefined as wall-clock time from instruction arrival to *displayed, judged-compliant* content, with censored failures. Downgraded to a measurement protocol supporting contribution 1. G1 rewritten with both neighbours |
| 2 | blocking | The explorer/voice-over demo undershoots the "digital persona" goal | **Accepted** | Dual-shot live persona (D-005): a lip-synced avatar close-up plus a LingBot world shot of the same persona, with cross-shot coherence measured. Compositing is an ablation |
| 3 | major | "Camera-only" is a code-read conclusion; an ack is not compliance; a real WS prompt test is needed | **Accepted** | Scope stated in backbone_verification.md (CP2 clarifications). A real WS prompt attempt was added to M0 |
| 4 | major | Latency labels are loose (549 ms stack; derived 0.6–1.15 s is not TVC; Wan-Streamer's network is assumed; D vs external avatar; rewind class) | **Accepted** | All relabelled. Rewind/snapshot → "C/D, feasibility unknown". D is limited to native LingBot conditioning |
| 5 | major | The falsification test is loose, and "internal state" mixes generator KV with thinker context | **Accepted** | H-core restated with the two kinds of state separated, a definition of "external state layer", an operational test and a refutation condition |
| 6 | major | Contribution 1's prior art is understated (SayCan, Inner Monologue); "offline only" is too broad | **Accepted after verification.** Claude ran a targeted search (2026-09-25). SPIRAL's critic is iterative/offline; the agentic-visual-generation survey (2609.06758) does not cover runtime verification of streaming generators. Bib entries were added through the arXiv API | Contribution 1 repositioned as a specific combination, with four required comparison arms. G2 reworded to "not found for streaming generators" |
| 7 | major | Novelty varies across G4–G10 (PACE, provenance, WBench) | **Accepted** | Contributions 3–5 downgraded or scoped to their evaluation novelty. G10 now says "no single benchmark found". WBench cited |
| 8 | major | Interruption and TVC need operational definitions; cancel ≠ redirect | **Accepted** | G5 rewritten (cancel exists; redirecting an in-flight chunk does not). The TVC timestamp list and censoring are defined. VLM judges are validated against blinded human labels (proposal §8) |
| 9 | major | Material neighbours were missing from the synthesis (WBench, WorldMark, VideoFDB, MIDAS, StreamingVLM, MemoryArena, LiViBench) | **Accepted** | Added to the matrices and gaps |
| 10 | minor | Matrix fields incomplete (URLs, control interface, latency in §2.4); KV wording; tea observation | **Accepted** | Direct arXiv links in every row. §2.4 rebuilt with control-interface and latency columns ("not stated" per cell). KV sink and window described separately. The tea observation stays a single unaligned sample |

Remaining disagreements: none. The reviewer also noted it could not re-read the pinned checkout. This is an
inherent limitation of inline review (D-002). CP3 inlines the relevant code excerpts.

## Checkpoint 3 — architectures, integration, memory, latency

Tag `cp3`. Reviewed revision ecbb880 (proposal v0.9). Inlined: the proposal, backbone_verification, decision_log,
the 4 figure sources, the vLLM-Omni streaming API doc, the realtime design doc, and **real code excerpts with line
numbers** (`docs/reviews/cp3_ev_code_excerpts.md`) from registry.py, coordinator.py,
serving_video_output_stream.py, pipeline.py and the deploy yaml. CP3 also re-reviewed the CP2 revisions (dual-shot
design, TVC repositioning) and raised no objection to them.

| # | Sev. | Issue (abridged) | Disposition | Resolution (c085745) |
|---|---|---|---|---|
| 1 | blocking | A1's "free-form prompts" cannot execute (prompt handler not registered) | **Accepted** | Shared generator substrate (D-009): S-cam, plus S-prompt only through C1 once it passes M1 tests; without C1, prompt changes are session restarts for both A1 and A2 |
| 2 | blocking | The backlog gate has no mechanism; `session.ping` is not flow control | **Accepted.** Claude had independently confirmed `serving_video_output_stream.py:17,79-88,311` before the review arrived | C4 redefined as a server generation gate (feasibility checked in M1), with skip-to-latest and rate adaptation as fallbacks. M0 measures queue depths and transport backpressure (D-010) |
| 3 | major | C1 is more than registration; stepwise `invalidate=True` safety is unverified | **Accepted** | C1 spec: encode at the boundary, session state, per-rank K/V rebuild under Ulysses head sharding, transition policy, tests. Re-sized to medium |
| 4 | major | Evidence labels (documented / code-read / executed) are conflated | **Accepted** | §6.1 distinguishes the three. M0 WS contract test added |
| 5 | major | Camera commands ≠ "walk slower" / "walk to the lake" | **Accepted** | Demo scoped to committed camera/viewpoint control and a visible host. Locomotion and events are conditional (D-012) |
| 6 | major | Architecture comparison confounded (memory and renderer differ); alternatives missing; A3(b) needs no training | **Accepted** | Shared substrate. Table of feasibility alternatives: SGLang server, tick path, clip scheduling, compositing, different backbone. A3 split into (a) training and (b) none if weights exist |
| 7 | major | IR camera contract undefined; Fig. 2 cancellation inconsistent | **Accepted. While verifying, Claude found an error the reviewer did not name**: `target` poses are *absolute relative to the session origin* (`camera.py:44,107,341-352`), not relative | Contract: frame, units, velocity held until replaced (explicit stop), absolute targets from a compiler pose estimate (D-011). Golden IR→WS example (JSON and quaternions validated). A single cancellation rule; Fig. 2 fixed |
| 8 | major | Monitor underspecified: sparse-flow scale ambiguity, VLM latency ≠ throughput | **Accepted** | Rotation plus translation *direction* only, abstention rules, K=4 frames per chunk, verdict deadline, repair eligibility reported |
| 9 | major | Quarantine leaks: quotations and echoes of persona claims | **Accepted** | Claim-type classification, echo lineage against the generated-event log with confirmation, paraphrase `derived_from`. Probes added to E3 |
| 10 | major | Scope holes through derived media and persona history | **Accepted** | `source_scopes` on every derived artifact. Private-session persona utterances are private. Public sessions start only from canon/public frames. Fresh-public-session probe added |
| 11 | major | Deletion vs append-only log undefined | **Accepted** | Erasure physically deletes records, cascades to 6 artifact classes, keeps a content-free tombstone ledger and bounded backup retention, and is verified after a flush and restart |
| 12 | major | TVC budget mixes paced and unpaced timing; p95 sums invalid | **Accepted** | Regime U (unbounded growth) vs regime G ($W \sim U(0,P)$, $L \cdot P$). Figures are labelled column sums, not quantiles, and will be replaced by a simulation from M0 measurements. 2-GPU/12 fps recomputed |
| 13 | major | Avatar delay omitted from the speech path; ack ≠ presentation | **Accepted** | Shared presentation timeline. Separate first-speech targets for world-shot and presenter-shot starts. Narration aligned to presentation |
| 14 | major | The first-demo boundary and GPU budget are optimistic; C2/C5 under-sized | **Accepted** | First demo = M0-qualified configuration with a presenter-plus-clips fallback. C2 medium–large; C5 seam acknowledged. GPU estimate labelled optimistic; full-machine slots booked |
| 15 | minor | Denominators and censoring | **Accepted** | Instruction-level success is primary (refusals count as failures). Conditional OCR and refusal rate reported. Unconditional p95 only if censoring ≤ 5%, otherwise restricted mean and deadline success |

Remaining disagreements: none.
