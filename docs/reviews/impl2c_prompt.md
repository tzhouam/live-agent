You are the independent reviewer (Codex, GPT-6 Sol) for the live-agent project, Phase 2 checkpoint "impl2c" (round 2):
the **evaluation harness and the memory service** against the Chinese proposal `docs/research_proposal_zh.md`
v2.11 (inlined).

Review goals, in priority order:
1. **Scoring validity:** intent chains (new / revision / withdrawal), effective-chain denominator, deadline table D,
   outcome precedence, capacity skips and refusals as failures, FCR and claim coverage, Kaplan–Meier with censoring,
   Wilson / Clopper–Pearson / clustered bootstrap / Holm. Anything that would bias A2 vs A1 or let the online judge leak
   into the primary outcome.
2. **Runner and converter** (`runner.py`): the orchestrator → SCHEMA mapping (chains by utterance uid, time rescaling,
   verdict fields, speech onset, completion claims), paired seeding, the live-stack mode.
3. **Blinded adjudication** (`adjudicate.py`): blinding, time mapping, merge semantics.
4. **Memory:** provenance typing, scope filtering before ranking, echo detection, bi-temporal correction, erasure
   cascade and verify_erased. Any path where a private fact can reach a public scope or survive erasure.
5. **Honesty of claims** in `docs/implementation.md`.

Output format: a numbered list of findings. For each: severity (blocking / major / minor), file and function, the
concrete failure scenario, and the fix. Then a one-line verdict: "ready for E1/E2 pilot", "ready after fixes", or
"not ready". Do not praise; do not restate the code.

This is round 2. Round 1 findings and their resolutions are summarised in the inlined `docs/codex_reviews.md`
(section "Phase 2") and `docs/implementation.md` ("Known deviations"). First state for each round-1 finding in your
scope whether it is RESOLVED, PARTIAL or OPEN (one line each), then list any NEW findings in the same format.
Accepted documented limits are acceptable if the docs make the claim narrower accordingly.

NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='.

===== FILE: docs/codex_reviews.md =====
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
| 2 | cp2 | see `cp2_meta.txt` | 7cce79f | gpt-6-sol | 10 (2 blocking, 7 major, 1 minor) | Resolved in 8eb4d33. CP3 re-reviewed it (no objections) |
| 3 | cp3 | see `cp3_meta.txt` | ecbb880 | gpt-6-sol | 15 (2 blocking, 12 major, 1 minor) | Resolved in c085745. The CP4 re-review found #11, #12 and #15 only partly resolved; fixed in d2e6a36 |
| 4 | cp4 | see `cp4_meta.txt` | b3435bb | gpt-6-sol | 9 (2 blocking, 6 major, 1 minor). Verdict: **not ready** | Addressed in d2e6a36. Re-review → cp4r2 (below) |
| 4 | cp4r2 | 2026-09-24T18:12Z | 3e99d08 | gpt-6-sol | 4 resolved, 5 partial, 1 new major. Verdict: **not ready** | Addressed in e3416a1. Re-review → cp4r3 (below) |
| 4 | cp4r3 | see `cp4r3_meta.txt` | 22c720f | gpt-6-sol | #5, #6, #7 and the substrate fix resolved. 2 major (H3b scope; M0 qualification vs stall target) + 1 minor (log wording). Verdict: **not ready** | Addressed in bacdb22. Re-review → cp4r4 (below) |
| 4 | cp4r4 | see `cp4r4_meta.txt` | 67d8801 | gpt-6-sol | All 3 round-3 items resolved. 1 major (H3b channel operationalization) + 1 minor (table row). Verdict: **not ready** | Addressed in 55016af. Re-review → cp4r5 (below) |
| 4 | cp4r5 | see `cp4r5_meta.txt` | df29f75 | gpt-6-sol | Round-4 items resolved. 2 minor. **Verdict: ready with minor fixes** (no blocking/major) | Both minor fixes applied in d822c32. Confirmation → cp4r6 (below) |
| 4 | cp4r6 | see `cp4r6_meta.txt` | 6f64d21 | gpt-6-sol | Both fixes verified; no regressions. **Final verdict: ready** | Closed |

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

## Checkpoint 4 — experimental design and complete proposal (round 1)

Tag `cp4`. Reviewed revision b3435bb (proposal v1.0-rc). Inlined: proposal, PROJECT.md, CLAUDE.md, AGENTS.md,
AGENT.md, decision_log, codex_reviews, related_work, and code excerpts (camera handler, ping semantics).
**Verdict: not ready.** The reviewer confirmed that most CP3 resolutions are reflected in the text.

| # | Sev. | Issue (abridged) | Disposition | Resolution (d2e6a36) |
|---|---|---|---|---|
| 1 | blocking | A1−mem does not test "no external layer": it has an external controller and carries history over | **Accepted** | Strict H-core is tested only against an unwrapped A3b-class system. Otherwise H-core-abl, which is explicitly weaker. A1−mem now carries no state across sessions (D-013) |
| 2 | blocking | The primary outcome is judged by the same kind of monitor the system acts on | **Accepted** | Blinded 2-rater human adjudication of every A2-vs-A1 trial. A separate offline evaluation judge for the ablations, with κ per condition. Evaluation set locked after E1 and the pilot (D-014) |
| 3 | major | Time to first *meaningful* response and time to first correctly conditioned visual response are undefined | **Accepted** | TFMR (fillers excluded, rubric, blinded raters) and TFCV (any shot, human-adjudicated, censored at D) defined on the shared timeline. End-to-end p50/p95 over all instructions |
| 4 | major | Power ignores task clustering; rare-leak claims are underpowered | **Accepted** | Pilot ICC → simulation power. 80 committed tasks × 5 seeds (design effect ≈ 2.2). "< 1%" leak claims need ≥ 360 opportunities with 0 leaks (rule of three) |
| 5 | major | FCR denominator, outcome rules and censoring are ambiguous (CP3 #15 partial) | **Accepted** | FCR = contradicted claims / claims, reported with claim coverage. Outcome-rule table (refused, superseded, cannot-tell, never). p95 only if KM reaches 0.95 before D; otherwise restricted mean with horizon D |
| 6 | major | A0 fails scene tasks by construction; H4b has no margin; cross-shot identity uses incomparable embeddings | **Accepted** | RQ4 compares A2 with **A0+clips** on MOS and preference. H4b margin 0.5 MOS (n≈16 needed; N=24 planned). Per-shot thresholds calibrated on human labels; cross-shot identity by human 2AFC; behavioural and scene-state probes added |
| 7 | major | Gate edge undefined; the T ≤ P rule ignores jitter (CP3 #12 partial) | **Accepted** | The gate fires at presentation *start* of chunk n; TVC ≈ A + U(0,P) + (L+1)P + I, with an L=0 vs L=1 trade-off. Qualification needs T+δ ≤ (L+1)P for ≥ 99% of measured chunks, plus a trace-driven queue simulation (D-015) |
| 8 | major | Erasure "cancels" work the API cannot cancel (CP3 #11 partial) | **Accepted** | Distinguishes unsent (dropped), sent (superseded), and live generator state (world session restarted from a canon frame). Presented media cannot be un-presented |
| 9 | minor | §14 claimed completion prematurely; D-001 wording; unlabelled design counts | **Accepted** | §14 reworded. D-001 now says "private test livestream". `[target]` labels added to design counts |

## Checkpoint 4 — round 2 (`cp4r2`)

Reviewed revision 3e99d08. Inlined: proposal, PROJECT.md, the 3 instruction files, decision_log, codex_reviews.
**Verdict: not ready.** CP4 #1, #2, #3 and #8 were RESOLVED. #4, #5, #6, #7 and #9 were PARTIALLY resolved.

| Item | Issue | Disposition | Resolution (e3416a1) |
|---|---|---|---|
| #4 | 360 leak probes from 20 users are not independent; the clustered bound is not < 1% | **Accepted** | The "< 1%" claim is now user-level over ≥ 300 independent simulated users, for text/speech channels. The visual channel gets a rate plus a cluster-robust bound, with no threshold claim |
| #5 | Superseded instructions are excluded while the text says "all instructions" | **Accepted** | Denominator is now "all scored intents" (superseded intermediate intents are replaced by their final intent), consistently in §7.2 and §8 |
| #6 | H4a needs pairwise preference, which §7.5 lacks | **Accepted** | Forced-choice pairwise preference added. Analysed with Bradley–Terry (participant random effects) and an exact sign test |
| #7 | $T+\delta \le (L+1)P$ is insufficient when mean $T > P$ | **Accepted** | Two conditions: throughput (mean $T+\delta < P$; qualification needs < 0.9P) and jitter ($T+\delta \le (L+1)P$ for ≥ 99% of chunks). The 2×H200 / 12 fps case is re-labelled marginal. The M0 go/no-go rule references this |
| #9 | §14 and the log did not record round 2; PROJECT.md status line stale | **Accepted** | This entry. §14 reworded. PROJECT.md status updated |
| new | "A0 shares the generator substrate" contradicts "A0 has no world model" | **Accepted** | §5.1 and D-009: A0 shares LLM, memory, speech and avatar; only A1 and A2 share the generator substrate |

## Checkpoint 4 — round 3 (`cp4r3`)

Reviewed revision 22c720f. Inlined: the same set as cp4r2. **Verdict: not ready.**

| Item | Issue | Disposition | Resolution (bacdb22) |
|---|---|---|---|
| r2#4 | H3b in §4 still states an unqualified "< 1%" | **Accepted** | H3b and its falsification rule are limited to text/speech channels at the user level; the visual channel is descriptive |
| r2#9 | The log said "re-reviewed" without recording a result | **Accepted** | Summary-table wording changed to "Re-review → <tag> (below)". This entry records the cp4r3 verdict |
| new | M0's 99%-jitter qualification conflicts with calling the configuration real-time and with the ≤ 1 stall/10 min target; 120 chunks cannot establish that target | **Accepted** | Two-stage qualification: M0 qualifies throughput (candidates only); an M1 soak test (≥ 3 × 30 min) plus a trace-driven simulation must meet the stall target before anything is called "real-time". §1.3, §6.4, §7.0 and §9.1 updated |

## Checkpoint 4 — round 4 (`cp4r4`)

Reviewed revision 67d8801. **Verdict: not ready.** All round-3 items were RESOLVED.

| Item | Issue | Disposition | Resolution (55016af) |
|---|---|---|---|
| 4 | H3b's "text channel" includes OCR of the displayed stream, which cannot be tested at the 300-user memory+LLM scale | **Accepted** | The statistical claim is limited to the **utterance channel** (response text + ASR of TTS audio), which can be produced at scale. On-screen OCR text and visuals are measured descriptively on ≈ 30 users |
| 5 | The RQ4 table row spans raw line breaks | **Accepted** | Row joined onto one line |

## Checkpoint 4 — round 5 (`cp4r5`)

Reviewed revision df29f75. **Verdict: ready with two minor fixes; no remaining blocking or major issue.**

| Item | Issue | Disposition | Resolution (d822c32) |
|---|---|---|---|
| 3 | The H3b falsification wording assumed exactly 300 users | **Accepted** | Falsification now depends on the exact one-sided Clopper–Pearson 95% upper bound (≥ 1%) |
| 4 | The log lacked a round-5 entry | **Accepted** | This entry |

## Checkpoint 4 — round 6 (`cp4r6`, confirmation)

Reviewed revision 6f64d21 (proposal and review log inlined). The reviewer verified the H3b fix and the round-5 log
entry and found no regression in §4, §7.3 or §8. **Final verdict: ready.**

After this verdict, the only change was the version label "v1.0-rc" → "v1.0". No content changed.

## Completion status of the review requirement (goal.md §7)

| Requirement | Status |
|---|---|
| Actual model verified (not just named in a prompt) | **Met.** Every run's session rollout records `"model":"gpt-6-sol"` (see each `*_meta.txt`) |
| Review at all 4 checkpoints | **Met.** CP1 (plus an invalid first attempt), CP2, CP3, CP4 in rounds 1–6 |
| Critique addressed with evidence or revisions; issues, changes and disagreements recorded | **Met.** Every finding has a disposition. No finding was rejected. Remaining disagreements: none |
| Material changes re-reviewed | **Met.** CP2 changes were re-reviewed in CP3, CP3 changes in CP4, and CP4 changes in rounds 2–6 |
| Limitation | Codex's shell sandbox cannot start on this host, and unsandboxed runs are not permitted. The reviewer therefore saw only inlined files and code excerpts and could not browse the repo on its own; it followed some public arXiv links. Agreement between models is not verification: the key backbone claims were checked independently against code (`docs/backbone_verification.md`, spot-checks) and against primary sources |

## 中文 v2.0/v2.1: owner-directed rewrite (TaoMate-H3 + Google agentic suite)

A material change (D-017), so it is re-reviewed from scratch.

### zh1: review of v2.0 (commit 63734a8)

Inlined: `research_proposal_zh.md`, `taomate_deep_dive.md`, `google_longform_agentic_suite.md`, `decision_log.md`,
and TaoMate-H3 code excerpts with line numbers (`zh1_ev_taomate_code.md`, @6b2f998). Model gpt-6-sol (rollout
verified). **Verdict: not ready.** Before the review, Claude independently checked three code claims: FA3-only
(`attention_hook.py:43-48`), teacher-audio overwrite (`runtime.py:339-359`), and sink + 2 recent (`cache.py:206-219`).

| # | Sev. | Issue (abridged) | Disposition | Resolution (v2.1) |
|---|---|---|---|---|
| 1 | blocking | The §6.4 latency is one request too low under D-015's L=1 gate | **Accepted** | Single timeline (lock → teacher → student → visible). The default gate is now L=0, with Λ ≤ R required (D-018). L=1 is the contrast, with its +R stated. Targets re-set and conditioned on measured Λ |
| 2 | blocking | A displayed failure cannot correct request k+2 under L=1 | **Accepted** | "Earliest correctable request" is defined from the timeline and reported as a distribution. The "within 2 requests" claim was removed |
| 3 | blocking | LTX 1 s control is unsupported (its demo changes the prompt per ~5 s window); H3 vs LTX confounds granularity | **Accepted** | The granularity test now happens only within LTX, after 1 s prompt changes are shown to work. H3 vs LTX is labelled a system comparison. The 2–3 s LTX claim was removed |
| 4 | major | Audio-teacher cost and scheduling are missing; README numbers exclude audio prep | **Accepted** | Throughput condition covers the full pipeline. M0 measures teacher and student co-resident (memory, contention) and runs 30 min continuously |
| 5 | major | "Re-anchoring" means nothing on T2AV without image conditioning | **Accepted** | Three executable interventions (textual correction, session reset, image re-anchoring only after FL2AV), compared with verbatim repetition |
| 6 | major | Interruption can leave the generator continuing from unseen content | **Accepted** | T8 rollback to the last presented chunk (feasibility in M1), else session reset or explicit bridging with measured discontinuity. Visual acknowledgement is measured separately from a meaningful reply |
| 7 | major | Experimental over-claims (RQ2 selection, RQ3 non-inferiority, RQ4 attribution, power) | **Accepted** | RQ2 randomized at a predefined failure point. RQ3 uses a 5 pp non-inferiority margin. RQ4 uses within-H3 ablations, with LTX descriptive only. Preregistered, simulation-based power; no pre-claimed effect size |
| 8 | major | Voice, spoken content and reasoning lack tests; "TTS" label wrong; leak check must cover generated audio | **Accepted** | Speech WER vs script, cross-session speaker identity (human), factual correctness, pre-generation script moderation, leak checks on generated audio (ASR + human spot audit) |
| 9 | minor | Source labels (SM90 from README; CC 8.9 is a local observation; 0.68× is DiT-only; state is not only KV; CANVAS is a storyboard; A²RD-only overhead); source vs new mechanisms | **Accepted** | 【本机观测】 label added; all corrected; paragraph separating source mechanisms from new ones added |

### zh2: re-review of v2.1 (commit dc72ab0)

> **Correction (added after zh3).** The "Resolution (v2.2)" column below was logged before the edits were verified. The v2.2 edit script aborted on one string mismatch, so **none of these resolutions were in the proposal when zh3 reviewed it** (text still v2.1). zh3 correctly reported them as NOT RESOLVED. They were applied and verified by grep in v2.3 (see zh3 below). This was a tooling/process error by the author, not a disagreement with the reviewer.

Model gpt-6-sol (rollout verified). zh1 status: #3, #5 and #6 RESOLVED; #1, #2, #4, #7, #8 and #9 PARTIALLY.
**Verdict: not ready.**

| # | Sev. | Issue | Disposition | Resolution (v2.2) |
|---|---|---|---|---|
| 1 | blocking | The latency model ignores that k+1 cannot present before k's 5 s slot ends, and the KV dependency on k | **Accepted** | ready = max(lock + G_a, done_k) + G_1 + δ; present = max(ready, V_k + R). Just-in-time locking (lock at V_k + R − Λ − σ) is adopted, with early lock and L=1 as contrasts. Targets recomputed (≈7 / 8.5 / 13.5 s illustrative medians) |
| 2 | major | The correction chain omits synthesis, compile, moderation and encode; the "k+2 cap" is wrong | **Accepted** | Chain C is defined in full; the correction enters the first request j with P_j ≥ visible + C, with no cap. The condition for reaching k+1 is stated |
| 3 | major | The H3 prompt contract is not demonstrated (a string per request, `<d>` tags; six-field format is LTX's); voice has no reference; generated speech is unchecked | **Accepted.** Claude read the real H3 format in `examples/prompts_60s.json` | A BlockScript → compiled H3 prompt example is added in the actual `integrated_multimodal_description`/`<d>` format. E1 tests exact spoken content and speaker identity. Generated speech is ASR-checked within σ before presentation, with the added delay measured |
| 4 | major | RQ5 has no matched untyped comparator; ASR spot audit cannot certify zero leaks | **Accepted** | Four memory arms with a matched retrieval budget. All ~900 probe-response audio clips are fully listened to by two raters; ASR sensitivity is validated |
| 5 | major | RQ4 arms confound ledger with correction or reset | **Accepted** | 7-arm factorial with matched prompt budget and reset frequency, including ledger-only and no-ledger controls |
| 6 | major | The bandit is not isolated or frozen; canon risk; the per-axis factorization was misdescribed | **Accepted** | Per-axis updates; canon-preserving arms; trained on separate pilot sessions and frozen during evaluation; a separate randomized ablation |
| 7 | minor | VQQA also runs CogVideoX-5B locally | **Accepted** | Corrected |
| zh1 #9 | residual | The abstract says rolling KV is the "only" state; 0.68× labelled as a citation | **Accepted** | Fixed ("main state" plus the other items; 0.68× is 【推导】) |

### zh3: round 3 (reviewed a revision where the v2.2 edits had silently failed to apply)

Model gpt-6-sol (rollout verified). **Verdict: not ready.** The carried-over findings (zh2 #1, #2 and #4–#7, zh1 #9)
were correct, because the text had not changed. New findings:

| # | Sev. | Issue | Disposition | Resolution (v2.3, verified by grep before commit) |
|---|---|---|---|---|
| carried | blocking/major | zh2 #1–#7 and zh1 #9 not present in the text | **Accepted** | All applied in v2.3: JIT lock with presentation slot + KV dependency; full correction chain C with no cap; compiled H3 prompt example in the real `integrated_multimodal_description`/`<d>` format; four memory comparators + full listening of ~900 probe clips; 7-arm factorial RQ4; per-axis, canon-preserving, frozen bandit; VQQA's local CogVideoX; state/label fixes |
| 3 | blocking | M0 cannot qualify end-to-end timing before T1–T3 exist (the released path precomputes all audio and writes one MP4 at the end) | **Accepted** | M0 is now per-component profiling only. End-to-end qualification (Λ, σ, throughput, jitter, 3 × 30 min soak) moves to M1, after T1–T3. §1.2 first demo requires M1 qualification |
| 4 | major | Speech guarantees overstated; pre-generation moderation cannot catch off-script speech | **Accepted** | "Guarantee scope" paragraph: WER and speaker tests in E1; ASR check of the generated audio inside σ before presentation (the teacher audio is ready at P+G_a), with added delay and false-block rate measured; otherwise the lack of a guarantee is stated |
| 7 | major | No interactive system-level baseline for the backbone decision | **Accepted** | A0 (LLM + streaming TTS + real-time audio-driven avatar, same memory) reinstated as the system baseline. RQ6 now compares A2 vs A0 in both directions |
| 8 | major | The near-real-time fallback lacks a stable service rule | **Accepted** | Turn-based mode, admission control (≤ 1 pending instruction, newer supersedes, skipped logged), optional slowed playback (≥ 20 fps); E2 measures wait growth |
| 9 | minor | Label and source scope | **Accepted** | 17.29 s marked as a separate benchmark; 0.68× 【推导】; VQQA local generator |

### zh4: round 4 (v2.3)

> **Correction (added after zh5).** The "Resolution (v2.4)" column below was logged before the edits were verified. The v2.4 edit script aborted on a mismatch in the §8 TVC row: that row still held v2.1 text, because v2.3 had never updated it. The chained shell command committed and ran zh5 anyway, so **zh5 reviewed unchanged text** and correctly reported NOT RESOLVED. **Process fix:** edits are now all-or-nothing scripts, run and grep-verified as a separate step, and logging and review happen only after verification. The resolutions were then applied for real and verified; see zh5 below.

Model gpt-6-sol (rollout verified). zh3 items: all RESOLVED except zh2 #5 and zh3 #3 (PARTIALLY). No new blocking
issue. **Verdict: not ready.**

| # | Sev. | Issue | Disposition | Resolution (v2.4) |
|---|---|---|---|---|
| 1 | major | RQ4 arm 5 (random restatement) vs arm 4 (targeted correction) differs by more than ledger access | **Accepted** | Arms 5 and 7 use the same drift detector, rule and timing; the correction or reset text comes from the static canon only. Arm 4 vs 5 and 6 vs 7 differ **only** in ledger access |
| 2 | major | §8 conditions on "M0-measured Λ", which M0 cannot measure; co-residency cannot be measured on the sequential released path | **Accepted** | Condition moved to M1. Co-residency is measured with a dedicated harness after T2, in M1 |
| 3 | major | No requalification after M2 adds the speech chain, controller, VLM and memory | **Accepted** | Three-step qualification: M0 profiling → M1 generator + playback → end-of-M2 whole-system soak. Only then "real-time live agent", and E2/E5 start. §1.2 and §9.1 updated |
| 4 | minor | RQ3 wording in §8; unlabelled counts; version labels | **Accepted** | Cross-backbone vs within-LTX made explicit; counts labelled 【目标】; title and §12 now v2.3 |

### zh5: round 5 (reviewed unchanged v2.3 text; see the correction above)

Model gpt-6-sol (rollout verified). It correctly reported zh4 #1–#4 NOT RESOLVED and raised no new issues.
**Verdict: not ready.** Resolution: the v2.4 edits were applied with an all-or-nothing script and verified by grep:
- the RQ4 arm-5/7 wording;
- the §8 TVC row: M1 condition, cross-backbone wording, TFMR, and a spoken-audio ASR check;
- the M0 co-residency sentence moved to M1;
- the three-step qualification, with whole-system requalification at the end of M2;
- the §1.2 first-demo gate;
- the M2 row;
- 【目标】 labels;
- v2.4 version labels.

Three residual "M0 measures end-to-end" references were also fixed (§1.1 table, §6.4 heading, §9.3 risk row).

### zh6: round 6 (verified v2.4, commit ee7c7d5)

Model gpt-6-sol (rollout verified). zh4 #1–#4 were all **RESOLVED**. One new major finding: the near-real-time fallback
promises E2 measurements, but E2 was gated on passing real-time requalification. **Verdict: not ready.**
**Resolution (v2.5, verified by grep):** if the end-of-M2 gate fails, E2/E5 still run under the near-real-time service
rule and are labelled "near-real-time". The RQ1/RQ2/RQ4/RQ5 contrasts stay valid (shared substrate). Latency results
are reported as measured, and no §8 real-time target is claimed. §1.2 and §6.4 are consistent.

### zh7: round 7 (v2.5, commit 71386aa)

Model gpt-6-sol (rollout verified). zh6 finding **RESOLVED**. Two new majors, with no blocking issue. **Verdict: not ready.**

| # | Sev. | Issue | Disposition | Resolution (v2.6, grep-verified) |
|---|---|---|---|---|
| 1 | major | RQ3's H3a assumes a fixed 5 s cadence that the turn-based fallback lacks | **Accepted** | H3a applies only when qualified. Fallback runs test a separate queueing model (A + admission wait + full request time + I) on measured queue timestamps |
| 2 | major | Capacity-driven skips hidden by final-intent scoring | **Accepted** | "Capacity skip" is separated from "user supersession". Capacity skips count as failures over all user instructions, and the skip rate is reported per condition |

### zh8: round 8 (v2.6, commit a91c9ee)

Model gpt-6-sol (rollout verified). zh7 #1 RESOLVED; zh7 #2 PARTIALLY: the primary denominator was ambiguous between
"all user instructions" and "final intent". No other blocking or major issue. **Verdict: not ready.**
**Resolution (v2.7, grep-verified).**
- The scoring unit is now the **intent chain**. User revisions and withdrawals merge into one chain, scored once on
  its final intent.
- The primary denominator is the number of intent chains.
- Withdrawn chains are excluded from the denominator and reported.
- Capacity-skipped chains stay in the denominator as failures.
- Updated consistently in RQ1 (§4), §7.2 (definition, rule table, metrics) and §8.

### zh9: round 9 (v2.7, commit 34e3637)

Model gpt-6-sol (rollout verified). zh8 is PARTIALLY resolved: "all chains" vs "withdrawn excluded" still conflicted.
No other blocking or major issue. **Verdict: not ready.**
**Resolution (v2.8, grep-verified).**
- An **effective intent chain** is defined once: a chain whose final intent was not withdrawn, including
  capacity-skipped chains.
- It is the primary denominator in §4, §7.2 and §8, and each chain is scored once.
- Withdrawn chains are reported separately.
- The capacity-skip rate is also over effective chains.

### zh10: round 10 (v2.8, commit b39d18a)

Model gpt-6-sol (rollout verified). zh9 **RESOLVED**. New major finding: the correction clock started at the block's
first frame, before the evidence had been shown. **Verdict: not ready.**
**Resolution (v2.9, grep-verified).** An evidence-complete time E is defined: E = V_k + (c+1)Δ for a full-block check,
or the time the last required frame is shown. The correction enters the first request with P_j ≥ E + C. The k+1
condition is (c+1)Δ + C ≤ R − Λ − σ. Worked example [derived]: with Λ + σ = 3.5 s, only block 0 with C ≤ 0.1 s can
reach k+1, so k+2 is the usual case.

### zh11: round 11 (v2.9, commit 715f92e)

Model gpt-6-sol (rollout verified). zh10 **RESOLVED**. There is 1 major finding: deadline D is undefined for content,
multi-step and changing-intent tasks. There is 1 minor finding: E assumes equal blocks. **Verdict: not ready.**
**Resolution (v2.10, grep-verified).**
- A preregistered D table, identical across conditions. The clock origin is the end of the user utterance that starts
  or last revises the chain.
  - Action/expression: 15 s.
  - Content: 15 s to begin an on-topic spoken reply; correctness is judged separately.
  - Multi-step: 15 s per step, counted from the previous step's compliance.
  - Correction: 15 s, restarted at the revising utterance.
- Near-real-time mode uses the same D.
- The E formula is marked illustrative; the analysis uses measured last-frame presentation timestamps.

### zh12: round 12 (v2.10, commit 9a9fbbf)

Model gpt-6-sol (rollout verified). zh11 #1 and #2 **RESOLVED**. There is 1 major finding: content-task success
required only an on-topic *start*. **Verdict: not ready.**
**Resolution (v2.11, grep-verified).** A content task succeeds only if **both** hold:
1. an on-topic spoken reply starts within 15 s;
2. the full reply finishes within 15 s plus a preregistered duration (Q&A ≤ 10 s, explanation ≤ 30 s, song ≤ 30 s)
   and satisfies a preregistered rubric: Q&A correct; explanation covers k specified points with no factual error;
   song recognizably sung with the specified lyrics/theme.

Onset success is reported separately and is not part of the primary outcome.

### zh13: round 13 (v2.11, commit f481809): **final verdict "ready"**

Model gpt-6-sol (rollout verified). zh12 **RESOLVED**. The whole-document pass found no remaining blocking or major
issue. **Verdict: ready.**

**Summary of the zh review series.**
- 13 rounds on the owner-directed rewrite. Every finding was accepted; none were rejected.
- Two process incidents: in zh3 and zh5, edits silently failed to apply before review. Both are recorded above, and
  the process was fixed (all-or-nothing edit scripts, grep verification before logging or review).
- Remaining disagreements: none.
- Limitation: the reviewer saw only inlined material. Key TaoMate-H3 code claims were independently spot-checked by
  Claude (FA3-only, teacher-audio overwrite, sink + 2 recent KV, prompt format).

## Phase 2: implementation reviews

### impl1 + impl2: round 1 (commit 8a2e5c4)

Model gpt-6-sol, verified in both rollouts. The review was split across two checkpoints:
- **impl1:** control path and generator adapter, 19 findings.
- **impl2:** evaluation harness and memory, 16 findings.

Both verdicts: **not ready**. Every finding was accepted; none were rejected. Fixed in commit fc23372 (145 tests pass):
- **Control path:**
  - QC runs once per request, only after all chunks have been presented; acks for dropped requests are ignored.
  - Verdicts and retries are bound to revision and step.
  - Multistep steps are released only after the previous step is verified.
  - Erasure quiesces locking, purges controller state, prompts and the log file, and requires acknowledgements from every purge target.
  - Barge-in is immediate in both clients.
  - Λ excludes the KV-dependency wait.
  - The repair cost C covers everything from E to a lockable correction, and the repair takes the reserved earliest correctable request.
  - A pre-generation script audit runs, and ASR is non-blocking.
  - Completion wording is guarded in code.
  - Claims are timed at the audio onset.
  - The WebSocket receive loop no longer blocks on the LLM or ASR.
  - Admission control produces capacity skips.
  - E2 gating requires calibrated capabilities, and unsupported actions produce logged refusals.
  - A1 is now "the LLM writes the prompt".
  - SessionView filters by epoch.
  - Loop tasks are supervised and startup cleanup is guarded.
  - Client audio-output timestamps are mapped to the server clock.
- **Evaluation and memory:**
  - Primary scoring and reporting use adjudicated verdicts only; judge scoring is available only as a labelled diagnostic.
  - Adjudication uses a two-rater reconciled merge with an arbiter, frozen criteria, the key kept outside the batch, and range checks.
  - Content onsets must be adjudicated.
  - Revision-bound verdicts and skips.
  - FCR covers every audible claim.
  - Observation windows are checked.
  - Holm families are fixed, and FCR and coverage get task-clustered CIs.
  - Memory write scope comes from the session, and lineage is required for procedures and persona lines.
  - Consolidation excludes stale records.
  - Confirmation needs a user turn.
  - Erasure fails closed.
- **Accepted as documented limits, not code:**
  - impl1 #14: no online checks for content and memory chains, and no drift detector, so the A2 pilot claim is restricted to action chains.
  - impl1 #8: pre-play ASR is not implemented.
  - impl1 #17 and #18: JPEG + PCM transport instead of fMP4, and the clock mapping is unmeasured.
  - impl2 #16, impl1 #19: the claims were reworded (generator-path diagnostic rather than M1 qualification; short-run throughput only).

See `docs/implementation.md` "Known deviations".

### impl1b + impl2b: round 2 (commit fc23372): **NOT RUN (reviewer authentication failure)**

Both calls to `tools/codex_review.sh` (2026-09-26) failed before producing a review. The error was `401 Unauthorized:
Incorrect API key provided`, after 5 reconnects (see `docs/reviews/impl1b_events.jsonl`). No review text exists, and
none is simulated here. The meta files' `rollout_models` line (gpt-6-sol) is from these threads' own rollouts: the
session was created with the requested model, but every model request was rejected, so it is not evidence of a review. Next step: the owner re-authenticates Codex (`codex login`), then round 2 is
re-run with the same prompts (`docs/reviews/impl{1,2}b_prompt.md`).

===== FILE: docs/reviews/impl2_review.md =====
1. **blocking — [report.py](/data/zhoutaichang/live-agent/live_agent/eval/report.py), `main`; [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `_pick_source`.** The default report silently falls back to online `judge` verdicts when a chain lacks adjudication. A2 has judge verdicts and A1 does not, so an incompletely adjudicated A2–A1 report can show an artificial A2 advantage. **Fix:** require adjudicated verdicts for every effective chain in the primary report; reject incomplete batches and make judge-only scoring an explicitly labelled diagnostic.

2. **blocking — [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `merge`; [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `_score_chain`.** Pressing “not done” or “cannot tell” without a time produces a verdict that makes `_compliance_time` raise, so an ordinary label can stop scoring. Merging two annotators also appends both as `adjudicated`; one `complied` label can win despite disagreement, with no third-person arbitration. **Fix:** record the reviewed interval for every label, score negative labels without a first-compliant time, retain independent ratings, and append only a reconciled verdict.

3. **blocking — [sim_user.py](/data/zhoutaichang/live-agent/live_agent/eval/sim_user.py), `run`; [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `prepare`; [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `convert`.** The adjudication page omits the preregistered content rubric and the descriptions of individual multistep actions. Meanwhile, `convert` marks the start of any presented request with a transcript as `on_topic=True`, without checking audible speech or its onset. A content chain can therefore satisfy its 15-second onset gate from a fabricated event, while raters lack the criteria for its completion gate. **Fix:** freeze the rubric and step criteria into the blinded item, and obtain on-topic speech onset from presented audio with a measured timestamp.

4. **major — [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `_score_chain`; [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `convert`.** Verdicts without a `revision` are accepted whenever their presentation time follows the final utterance endpoint. After “drink tea” is revised to “put the cup down,” an already locked tea request presented after the revision can count toward the final intent. The converter emits judge verdicts without revision numbers and copies each action verdict to *every* chain on the script. **Fix:** bind each verdict to its judged chain, step, and intent revision; reject mismatches rather than relying on time alone.

5. **major — [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `_claims` and `score_session`; [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `convert`.** Completion claims are timed at the request’s first presented chunk, not when the claim is heard. A chain-level compliance verdict can validate a claim about a different substep, and claims on chains later withdrawn disappear from FCR altogether. These cases can undercount or misclassify false claims. **Fix:** log the presented audio time and referent of each claim, adjudicate claims directly, and include every audible completion claim in the FCR denominator.

6. **major — [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `convert`.** No branch emits the schema’s `capacity_skip` event. A dropped, unrevised chain may still fail as `never`, but the capacity-skip rate becomes zero and conditional success treats that chain as served; a stray verdict can even override the missing skip. **Fix:** emit a skip with chain and revision identity from admission control, then apply skip precedence before verdict scoring.

7. **major — [scoring.py](/data/zhoutaichang/live-agent/live_agent/eval/scoring.py), `score_session`; [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `run_task`.** Missing compliance is censored at the nominal deadline without checking that presented media was observed through that deadline. A recording ending ten seconds after an action can be treated as a full 15-second failure; longer content and multistep deadlines have the same exposure problem. Early multistep failure is also stored as censoring for `time_to_success`, although it precludes completion. **Fix:** record the observation end per chain, rerun incomplete trials or censor at the actual end, and keep deterministic step failure separate from right censoring.

8. **blocking — [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `CONDITIONS` and `run_task`; [report.py](/data/zhoutaichang/live-agent/live_agent/eval/report.py), `repair_comparison`.** RQ2 assigns repair mode by whole condition (`A2` versus `A2-repeat`), rather than randomizing the predefined failure point. The report compares repair arms only when both occur within one condition, so this runner produces no specified RQ2 comparison. **Fix:** randomize each eligible, predefined failure point, log the assignment and earliest eligible request, and analyse by assigned arm.

9. **major — [report.py](/data/zhoutaichang/live-agent/live_agent/eval/report.py), `compare` and `condition_section`; [stats.py](/data/zhoutaichang/live-agent/live_agent/eval/stats.py), `cluster_bootstrap_diff`.** The Holm family is whatever `--compare` arguments the analyst supplies, so changing that list after inspection changes adjusted results. The displayed 95% paired intervals remain unadjusted; FCR and claim coverage receive only claim- or chain-level Wilson intervals despite task clustering. **Fix:** fix the comparison family before data collection, make significance decisions from the adjusted family, and report task-clustered uncertainty for those rates.

10. **major — [runner.py](/data/zhoutaichang/live-agent/live_agent/eval/runner.py), `live_factory`, `run_task`, and `_main`.** The live factory passes the paired seed to the orchestrator but does not show it being passed to `SessionView` or the TaoMate generator. Conditions run in blocks, leaving order and warm-up effects confounded with A1/A2. The “live” path sends text directly, uses `SimClient`, and writes `mode="simulation"` even for TaoMate runs. **Fix:** set and log the effective generator seed, counterbalance condition order, and distinguish generator-path trials from browser, TTS/ASR, and real-time qualification runs.

11. **major — [adjudicate.py](/data/zhoutaichang/live-agent/live_agent/eval/adjudicate.py), `prepare`, `video_to_session`, and `merge`.** `key.json`, which reveals condition and session, is placed in the annotator batch directory. Merge also accepts timestamps beyond the last recorded segment; `video_to_session` extrapolates them into session time, allowing an unobserved frame to become a timely compliance verdict. **Fix:** keep the key outside annotator access, validate labels against actual recorded frames and the final-intent interval, and reject out-of-range or incomplete timing.

12. **blocking — [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `_utterance_scope` and `add_procedure`; [memory_bridge.py](/data/zhoutaichang/live-agent/live_agent/memory_bridge.py), `on_user_utterance`.** A user utterance carrying `scope="canon"` or a public scope is accepted as such; its extracted fact can then be retrieved publicly. Separately, `add_procedure` defaults to canon and requires no parent IDs, so a procedure written from private experience can become public without a private source tag. **Fix:** derive write scope from the authenticated session, forbid user facts in canon, and require source lineage and a scope check for learned procedures.

13. **blocking — [memory_bridge.py](/data/zhoutaichang/live-agent/live_agent/memory_bridge.py), `on_persona_line`; [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `record_generated_event` and `add_record`.** The bridge records persona output without the IDs of memories that informed it. A public line or ledger artifact containing a private fact can consequently receive only a public `source_scopes` tag; retrieval’s correctly ordered scope filter cannot detect the missing lineage, and erasure cannot cascade through it. **Fix:** propagate source IDs from retrieval through scripts and generated artifacts, and reject public writes whenever any input has a private scope.

14. **major — [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `consolidate` and `confirm`.** Correction marks descendants stale, but `consolidate` still includes `generated_event` records regardless of status. A persona line repeating an old value can reintroduce that value into a fresh active summary after correction. Also, `confirm` turns an agent inference into an `own_assertion` user fact while retaining `speaker="agent"` and requiring no confirming utterance. **Fix:** exclude stale and invalidated sources from consolidation; create a new fact linked to explicit user confirmation, preserving the inference as provenance.

15. **blocking — [store.py](/data/zhoutaichang/live-agent/live_agent/memory/store.py), `forget` and `verify_erased`.** Erasure hooks are optional and their errors are collected while `forget` still returns; recordings or active generator and LLM state can survive a reported deletion. `verify_erased` searches a literal term mainly in records already tagged to the user, so it can return empty for paraphrased or wrongly untagged public artifacts and does not verify external caches or media. **Fix:** require acknowledgements from every applicable purge target before reporting completion, verify deleted IDs and descendants across stores, and fail closed on hook errors.

16. **major — [implementation.md](/data/zhoutaichang/live-agent/docs/implementation.md), “Verified so far.”** Calling the 12 short, server-host `SimClient` sessions an “M1 qualification run” can be read as qualification under proposal §6.4, which requires the client playback path and at least three 30-minute soak runs. The document later says those checks remain unverified. **Fix:** label this a short generator-path diagnostic and reserve “M1 qualification” for the specified completed gate.

**Verdict: not ready.**
===== FILE: docs/research_proposal_zh.md =====
# 在线智能体导演：基于 TaoMate-H3 的实时个性化直播数字人

**研究提案（中文版 v2.11，2026-09-25）**

*v2.11：已按 GPT-6 Sol 评审（zh1–zh12）修订。本版依据项目负责人的指示重写（决策 D-017）。生成底座由 LingBot-World 2.0 改为 TaoMate-H3，系统架构借鉴 Google 长视频智能体套件（Co-Director / CANVAS / A²RD / VQQA）。英文 v1.0（`docs/research_proposal.md`）保留为上一版。*

**证据标注。** 每个定量陈述都带一种标注：
- 【引用】：来自具名的一手资料。
- 【代码】：在已检出的源码中核实。只读，未执行。
- 【本机观测】：在本机上用只读命令观测到的结果，例如 `nvidia-smi`。
- 【推导】：基于引用或代码中的数值推算。
- 【目标】：提议的目标，不是结果。
- 【估计】：我们的判断。

**本阶段未运行任何实验、测量或用户研究。**

已检出的代码版本如下（均只读，位于 `external/`）：

| 仓库 | 提交 |
|---|---|
| TaoMate-H3 | `6b2f998` |
| TaoMate（LTX） | `136d890` |
| vLLM-Omni | `7b4dc76`；上游 `3bd5ac9` 仅做了检查 |

支撑材料：
- `docs/notes/taomate_deep_dive.md`
- `docs/notes/google_longform_agentic_suite.md`
- `docs/notes/taomate_h3_assessment.md`
- `docs/related_work.md`
- `docs/backbone_verification.md`（LingBot）

---

## 摘要

我们要构建一个可以直播的数字人。它需要做到：
- 用自己的声音和口型实时说话；
- 在对话中途接受纠正与打断；
- 跨会话记住用户；
- 在数十分钟乃至数小时内保持人设与场景一致。

**生成底座选用 TaoMate-H3。** 它是在 MiniMax H3 上训练的 3 步流式 LoRA，并附带运行时代码【引用】。它有三个优点：音视频在同一时间轴上生成，说话、表情、动作都能用文本提示逐块描述，且与负责人所述的参考主播同属 H3 家族。

**但代码核查发现四个限制，本提案的方法都要围绕它们设计：**
1. **控制粒度粗。** 控制粒度为 **5 秒一个请求**，每个请求内部分为 4 个块。
2. **状态极短。** 生成器的主要状态是「首块视频 sink + 最近 2 个块」的滚动 KV，另有位置偏移、首块归一化统计量与音频教师尾部。论文中的锚点与学习型记忆**不在** H3 代码里【代码】。
3. **语音是离线预算的。** 语音由基座 H3 的「教师」过程**预先**为整份脚本计算，然后覆盖流式模型的音频；运行时**不接受会话中途的新提示**【代码】。
4. **硬件要求高。** 发布的运行路径只接受 FlashAttention-3【代码】，README 要求 Hopper/SM90【引用】，而本机 GPU 报告为计算能力 8.9【本机观测】。在 8×H20 上，**仅 DiT 部分**的速度约为实时的 0.68 倍：10 秒视频用时 14.81 秒【引用】，0.68 倍由此换算【推导】。这个数字不含音频教师与编码。

**Google 的长视频套件为何可借鉴，又为何不能照搬。** 该套件表明：一致性来自包在生成器**外面**的智能体，包括分层导演、持久视觉锚点、分段自回归记忆和基于 VLM 问答的「语义梯度」修正。但这四个系统全部离线，可以反复重生成，每段开销可达数分钟【引用】。

**我们的研究问题是把这套结构「在线化」。** 在线后必须满足四个约束：
- 每个判断都要在截止时间内完成；
- 只能判定用户**实际看到**的画面；
- 已播出的内容不能重生成，修正只能**向前**作用于下一块；
- 用户随时可能打断。

**核心科学贡献：** 在线智能体导演。它由状态账本、校准过的能力清单和截止时间内的「前向语义梯度」修正组成，并通过对照实验衡量它在可观测指令遵循、长时一致性与响应时延上的收益与代价。工程集成不算贡献。

---

## 1. 动机、目标场景与问题定义

### 1.1 为什么「只接一个视频生成器」不够

| 事实 | 对直播智能体的含义 | 证据 |
|---|---|---|
| TaoMate-H3 每个请求 5 秒，分 4 块（首请求为 39/34/34/17 帧，之后共 119 帧），每块 3 步去噪 | 指令最快在下一个 5 秒请求边界生效 | 【代码】`config.py:23,80-134`；`streaming/geometry.py:173-200` |
| KV 只保留首块视频 sink 和最近 2 块音视频；音频历史每 60 秒丢弃。此外还携带位置偏移、首块颜色归一化统计量和音频教师的尾部 | 生成器没有长期的语义记忆。人设与场景一致性主要只能来自外部 | 【代码】`streaming/cache.py:206-219`；`config.py:29`；`streaming/runtime.py:451-462` |
| 音频由基座 H3 教师过程为整份脚本预算，再覆盖流式音频；文本编码器编码完所有提示后被移到 CPU | 语音内容必须提前一个请求写好。运行时不能中途换话题 | 【代码】`streaming/runtime.py:339-359,739-743`；`runner.py:293,299-323`；`cli.py:223-229` |
| 发布路径只接受 FlashAttention-3；权重与激活量化为 INT8（CUTLASS）。README 要求 SM90 | 本机 GPU 为计算能力 8.9，可能无法运行，需移植或换硬件 | 【代码】`streaming/attention_hook.py:43-48`、`cli.py:130-146`；【引用】README；【本机观测】`nvidia-smi` |
| 在 8×H20、480×864 上生成 10 秒：DiT 用时 14.81 秒【引用】（约 16.2 FPS，≈0.68× 实时【推导】），首帧可播 17.29 秒（来自单独的基准测试，不是发布的一次性输出路径），首个最终块 6.15 秒。**这几个数字都不含内部音频准备**，而且发布路径的输出要到最后才写出 | 仅看 DiT 就**不是实时**；完整流水线（教师 + 学生 + 编码）更慢：M0 分组件测，M1 在 T1–T3 完成后测端到端 | 【引用】TaoMate-H3 README / 模型卡 |

**工作假设（可证伪）。** 离开外部状态层与在线导演，仅靠流式生成器无法同时做到三件事：
- (a) 跨会话、可纠正、可删除、可溯源的用户记忆；
- (b) 经过验证的可见指令遵循；
- (c) 小时级的人设与场景一致性。

反例同样存在：X-Streamer、Wan-Streamer 等端到端模型内置了推理【引用】。因此我们只检验上述较窄的命题。检验方法见 §7.4。

### 1.2 目标场景：一对一陪伴主播 + 私有测试直播

**人设。** 一个虚构人设，比如「书房里的汉服读书人」，风格与参考主播相近。人设的**正典档案**由项目方整理，包括外貌、服饰、声音、场景和道具。

**模式 1：主验收场景，一对一私聊。** 用户语音输入。典型指令分四类：

| 类别 | 例子 |
|---|---|
| 动作 | 「喝口茶」「翻一页书」「挥挥手」 |
| 内容 | 「讲讲 CUDA」「唱首歌」 |
| 纠正与打断 | 「不对，换一首」「先停一下」 |
| 记忆 | 「我上次说我妹妹在哪？」「忘掉这件事」 |

**模式 2：第二评测场景，私有测试直播。** 脚本化的测试账号在弹幕里投票、提问，其中部分账号尝试投毒。**本阶段不做公开直播。**

**首个演示的范围。** 只包含 **M2 末整系统再认定**为实时的配置（§6.4）。M1 的认定只覆盖生成器与播放路径。

**未通过时的「近实时」服务规则。** 如果完整流水线的吞吐达不到每 5 秒一个请求（8×H20 上仅 DiT 就约 7.4 秒 / 请求【推导】），持续的对话会让队列无限增长，所以需要明确的规则：
- **话轮制：** 人设说完一段后进入「倾听」，用户说完才生成下一段。不维持连续的 5 秒节奏，等待时间如实显示。
- **准入控制：** 同时最多有 1 条未执行的指令。更新的指令取代旧指令，被取代的记为「**容量跳过**」。它与用户主动撤回或改口（「用户取代」）严格区分。
- **降速播放：** 可选，把播放帧率降到生成速率，但不低于 20 fps，并测量主观质量。
- 反应片段只用来掩饰短暂等待，**不**计入 TFMR。

E2 在持续交互下测量等待时间的增长与 TFMR。只有在 M2 末再认定未通过时，E2 才以「近实时」标签进行（见 §6.4）。

### 1.3 问题定义

- 用户在时间 $t$ 发出指令 $u_t$。
- 智能体为第 $k$ 个请求生成**块脚本** $s_k$。它包含动作、台词、外貌、场景、镜头和声音字段，与 TaoMate 的提示格式一致。
- 生成器以未知概率 $p_c$ 渲染出控制 $c$，从发出到生效的时间服从未知分布 $F_c$。
- 用户在呈现时刻 $\tau$ 看到并听到 $v_{\le\tau}$。

对每条指令，目标是三点：
- 最大化**可观测遵循**：独立评判在截止时间 $D$ 内、在呈现的画面与音频上判定为「已执行」；
- 最小化「指令到可见遵循时间」（TVC）与虚假完成声明；
- 同时保持记忆正确、作用域隔离、可删除，并保持长时一致性。

---

## 2. 相关工作与研究空白

完整矩阵见 `docs/related_work.md`。这里只列出决定本设计的要点。

### 2.1 Google 长视频智能体套件：可借鉴什么、在线后会失效什么

四个系统都**不训练，都不实时，都不交互**【引用】。其中三个是对冻结 API 模型（Gemini、Nano Banana、Veo）的提示编排；VQQA 还在本地通过 Diffusers 运行 CogVideoX-5B 作评估对象。

| 系统 | 机制（原文） | 关键数字【引用】 | 在线化后保留 | 在线化后失效 |
|---|---|---|---|---|
| [Co-Director](https://arxiv.org/abs/2604.24842) | 编排器 → 前期 → 制作 → 后期。UCB1 在「创意策略 3 × 叙事模式 3 × 美学原型 4」三个轴上选择组合，并用 Gemini 3 Pro 的**分因子**评分（每轴 0–100）**按轴分别**更新各轴取值，不是 36 个独立臂 | GenAd-Bench 平均 81.4（随机搜索 75.7，基础流水线 68.5，Veo 3.1 63.6）；换成标量奖励后产品保真度 −5.0 | 分层参数化的人设风格轴；分因子评审；**跨会话**的老虎机 | 一次「拉臂」就要完整跑一遍流水线；奖励在视频结束后才到 |
| [CANVAS](https://arxiv.org/abs/2604.13452) | 全局计划：角色外观状态、地点 id、带「持有者」字段的道具状态（JSON）。锚点记忆：角色规范锚点 + 最近锚点、地点背景锚点、道具锚点。检索规则分三种情况：连续、回到已知地点、新地点 | HardContinuityBench（仅 5 个故事）；去掉规范锚点后角色一致性 4.24 → 2.59 | 状态账本的字段设计；检索规则；**规范锚点永不覆盖** | 生成 N 个候选再选优——已播出的内容无法选；依赖未来剧本的规划 |
| [A²RD](https://arxiv.org/abs/2605.06924) | 分段「检索–合成–精修–更新」。每段记录文本状态：身份、身份变化、动作、空间三元组、镜头。另有全局参考与成功/失败提示库。外推与内插的切换由多模态大模型根据下一段剧情决定 | 1 分钟 VBench-Long：叙事 0.90（基线 0.75），角色 0.74（0.57）。10 分钟时角色/环境/物体一致 90.5/84.0/91.5%。每段额外开销 < 7.2 分钟 | 逐块文本状态；成功/失败提示库作为跨会话程序性记忆；「推进 vs 纠偏」策略（在线版改为三种可执行干预，§5.4） | 重生成和编辑；需要预知下一段；内插需要预定的终止帧 |
| [VQQA](https://arxiv.org/abs/2603.12310) | 问题生成：对齐问题 5–10 个、质量问题 8–10 个 → 问答 → 以低分问答对作「语义梯度」改写提示 → 全局 VLM 按**原始**提示选优 | T2V-CompBench +11.57，VBench2 +8.43；平均 1.245 轮，约 7.23 次 VLM 调用 | 编译时为每条指令生成可检验的问题；语义梯度作用于**下一块**的提示 | 迭代重生成与全局选优 |

**来源机制与我们的新机制要分开看。** 上表「原文」与「关键数字」两列是论文核实过的机制。「在线化后保留」一列是我们**新提出、尚未验证**的机制：跨会话老虎机、前向修正、文本状态账本。另外两点说明：
- CANVAS 的主要产出是**分镜关键帧**，只有附录中才把关键帧交给 Veo 生成约 1.5 分钟视频。
- 「每段数分钟」的开销专指 A²RD。
- Co-Director 的整条流水线拉臂与 VQQA 的候选选优为我们提供了灵感，但**不能**证明在线版本有效。

**空白。** 在我们的检索范围内，没有找到满足以下全部条件的系统：
- 在**截止时间内**判定用户**实际看到**的内容；
- 只做**向前**修正，不重生成；
- 容许用户中途打断；
- 能跨会话保持人设与用户记忆。

这是检索结论，不是「不存在」的证明。

### 2.2 TaoMate 的两个版本：论文 ≠ H3 代码

| | TaoMate（论文，LTX-2.3 初始化） | TaoMate-H3（负责人指定） |
|---|---|---|
| 参数量 | 22.1B（新增记忆模块 97.8M） | H3 约 33B DiT + rank-128 LoRA |
| 记忆 | 不可变视觉锚点 + 固定容量压缩音视频状态 + 分模态残差注意力【引用】；代码中每 4 层一个记忆注意力层【代码：TaoMate `learned_memory.py`】 | **没有**。只有 sink + 最近 2 块的滚动 KV，以及首块颜色重标定【代码】 |
| 块粒度 | 生成块 = 3 个潜帧 ≈ 1 秒，但交互演示**每约 5 秒窗口（5 块）才换一次提示**【代码：TaoMate `runtime.py:46-53`、`streaming_runtime.py:4927`】。1 秒级的提示控制**尚未证实** | 5 秒请求 = 4 块【代码】 |
| 速度 | 3 卡 35 FPS（卡型未说明）；单张 RTX PRO 5000 为 11.1 FPS【引用】 | 8×H20 约 16.2 FPS【引用】 |
| 交互 | 有演示：FastAPI + SSE、本地 Gemma 规划、文件队列、每窗口一个提示；**打断标志写入后从未被读取**【代码】 | 无服务端、无队列、无回调【代码】 |
| 注意力后端 | flex_attention / SDPA（可能可在 CC 8.9 上运行）【代码】 | 必须 FA3（SM90）【代码】 |
| 许可 | 代码 Apache-2.0；权重继承 LTX-2.3 与 Gemma 的许可 | MiniMax H3 社区许可：排除欧盟、英国、韩国、美国地区 |

**设计含义。** TaoMate-H3 是**主底座**（负责人指定）。TaoMate-LTX 只作为**系统级对照**：它与 H3 在骨干、规模、记忆、音频路径、运行时上都不同，所以两者的差异**不能**归因到任何单一因素。LingBot-World 2.0 降为**可选的世界镜头与对照**，其核查结论见 `docs/backbone_verification.md`。

### 2.3 其他相关方向（摘要）

- **流式视频与世界模型。** CausVid、Self Forcing、LongLive、Matrix-Game、LingBot-World。
- **实时数字人。** LiveAvatar、SoulX-FlashTalk、LPM 1.0、X-Streamer。
- **双工语音。** Moshi、Qwen3-Omni。
- **快说慢想的前后端分工。** 已是业界通用做法，我们复用，不作为贡献。
- **与播放对齐的上下文。** PACE（音频）。
- **长期记忆。** MemGPT、Mem0、Zep；其短板是纠错与遗忘：MemoryAgentBench 选择性遗忘 ≤ 28%，K-Bench 删除后仍泄漏 22–86%。

以上均为【引用】，详见 `related_work.md`。

---

## 3. 贡献：科学与工程分开

**科学贡献（待检验）：**

- **S1（核心）在线智能体导演。** 把 Co-Director / CANVAS / A²RD / VQQA 在截止时间、仅可前向修正、可被打断的约束下重新设计：
  - **状态账本**：CANVAS 的全局计划加上 A²RD 的逐块文本状态，用来合成每个块脚本；
  - **能力清单**：离线用 VQQA 式问答和 A²RD 评分细则校准，记录每类动作、表情、台词的实测成功率与生效时间；
  - **在线质检**：编译时生成可检验问题，由 VLM 在截止时间内对呈现内容作答；
  - **前向语义梯度**：失败时把低分问答写进**最早可接收修正的请求**的提示；
  - **推进 vs 纠偏**：检测到漂移时采取三种可执行干预之一（§5.4）。

  我们检验的是这个**组合**相对于开环提示与各消融版本的效果。
- **S2（测量）块粒度下的 TVC 协议。** 以挂钟时间衡量「指令 → 呈现且被判定遵循」的时间，在**同一条时间线**上逐项分解：提示锁定、音频教师、学生生成、编码传输、呈现、视觉惯性。从未遵循的样本按删失处理。粒度的影响只在**同一骨干内**比较（§4 RQ3）。
- **S3（评估）直播人设的类型化记忆。** 按来源区分用户断言、智能体推断、人设生成、观众声称、系统观测，按作用域区分私有、公开、正典。评估虚假记忆、纠错与删除的传播，以及跨语音、屏幕文字、生成画面的泄漏。

**工程集成（必要，但不算贡献）：**

| 编号 | 内容 |
|---|---|
| T1 | TaoMate-H3 **会话中途提示队列**：rank 0 队列广播，文本编码器常驻 GPU，删除「请求必须属于预编译提示列表」的校验（`base10_teacher.py:177`） |
| T2 | **音频教师前瞻一请求**：常驻加载基座 H3 的音频过程，比视频提前一个请求计算 |
| T3 | **逐块 fMP4 输出**，取代结尾一次性写 MP4（`runner.py:124-263`） |
| T4 | **FA3 → FA2/SDPA 移植**，以适配 CC 8.9（`attention_hook.py`、`model/layers.py`）；或改用 H20/H200 级机器 |
| T5 | 客户端呈现时间戳与播放积压控制 |
| T6 | 语音链路（VAD、ASR、话轮） |
| T7 | 可选：LingBot 世界镜头 |
| T8 | 打断回滚：按块快照 KV 与音频教师尾部，回滚到最后一个**已呈现**的块。可行性未知，M1 评估 |

**长期方向（需训练，不属首个演示）：**
- 把 TaoMate 论文的学习型锚点记忆移植到 H3；
- 缩短 H3 的请求粒度（重新蒸馏）；
- 音频教师的逐块化。

---

## 4. 研究问题与可证伪假设

阈值见 §8，均为【目标】。

| RQ | 假设 | 证伪条件 |
|---|---|---|
| **RQ1 在线导演（主）** | **H1a** 完整在线导演（A2）的**指令级成功率**高于开环（A1：LLM 直接写块提示）。以**有效意图链**（最终意图未被撤回，含被容量跳过的链）为分母，每条计分一次；拒绝、降级与容量跳过都算失败（§7.2）。**H1b** 虚假完成声明率更低。**H1c** 消融后下降：去掉清单、去掉质检、去掉前向修正、去掉账本，各自都会下降 | A2−A1 成对差的 95% CI 含 0 或为负；FCR 不降；消融无下降 |
| **RQ2 前向修正** | **H2** 在同一个、事先定义的失败点上，**随机分配**「前向语义梯度修正」或「重复原指令」，比较在**最早可接收修正的请求**（按 §5.4 时间线确定，并如实报告它是第几个请求）中的补救率 | 补救率差的 CI 含 0 |
| **RQ3 时延与粒度（主）** | **H3a** 通过实时认定时，在 H3 上用 §6.4 的单时间线模型（每 R 秒锁定一次）预测 TVC，中位数误差 ≤ 1 个请求周期。近实时运行没有固定节奏，改为检验**排队模型**：TVC ≈ A + 等待准入 + 完整请求处理时间 + I，并用实测的队列时间戳单独做预测与分析，中位数误差 ≤ 1 个请求处理时间。**H3b（有前提）** 先在 TaoMate-LTX 上证实可以逐块（约 1 秒）换提示，再在**同一骨干内**比较 1 秒与 5 秒提示粒度：细粒度的 TVC 中位数更低，且遵循率**非劣**（边际 5 pp，事先做功效计算）。H3 与 LTX 之间的比较只作系统级描述 | 预测误差 > 1 周期；逐块换提示不可行（报告为发现）；TVC 无差异，或遵循率劣于边际 |
| **RQ4 长时一致性** | **H4** 在 H3 **内部**做析因消融（§7.4 的 7 组，提示预算与重置频率匹配）：账本本身，以及它与纠偏、重置的组合，各自提升 30–60 分钟一致性。TaoMate-LTX 的学习型记忆只作描述性对照 | 仅账本与逐字重复无差异；各组合相对其无账本对照无差异 |
| **RQ5 记忆** | 类型化 + 隔离记忆的虚假用户事实率更低，召回非劣（边际 5 pp）。话语通道用户级跨域泄漏的精确（Clopper–Pearson）单侧 95% 上界 < 1%（≥ 300 名模拟用户）。删除后泄漏 < 5% | 未更低或召回劣于边际；上界 ≥ 1%；删除后泄漏 ≥ 5% |
| **RQ6 体验与底座价值** | 混合会话中比较 A2 与交互式语音 + 头像基线 A0：动作与表现类任务上 A2 更受偏好；纯对话任务上 A0 的 TFMR 更低，且 MOS 不劣（边际 0.5）。同时报告 A2 相对 B0 的交互价值与时延容忍度 | A2 对 A0 的偏好 CI 含 0；两个方向的结果都有信息量 |

主问题为 RQ1 与 RQ3。所有结果（包括零结果）都报告。

---

## 5. 方法与系统架构

### 5.1 候选架构比较

| | A0 语音 + 头像（交互式系统基线） | B0 预写脚本 | A1 开环直连 | **A2 在线导演（提出）** | A3 紧耦合（长期） |
|---|---|---|---|---|---|
| 做法 | LLM + 流式 TTS + 实时音频驱动头像（如 SoulX-FlashHead / Ditto 类，M1 选型），同一记忆服务 | TaoMate-H3 原生 JSON 脚本、固定循环，不交互 | LLM 根据对话直接写下一请求的提示 | 分层导演 + 状态账本 + 能力清单 + 在线质检 + 前向修正 + 类型化记忆 | 把学习型记忆移入 H3，重蒸馏为更细粒度，甚至端到端双工 |
| 交互 | 有（话轮级、低时延） | 无 | 有（5 秒粒度） | 有（5 秒粒度，另有即时反应层，§5.5） | 视训练而定 |
| 可观测遵循 | 仅限语音与头部 | – | 未验证 | 测量并修正 | 未知 |
| 训练 | 无 | 无 | 无 | 无（只需校准） | **需要** |
| 可行性【估计】 | 高 | 高 | 高 | 中高 | 低 |

**共享底座（去混杂）。** B0、A1、A2 使用同一 TaoMate-H3 运行时（含 T1–T3）、同一 LLM、ASR 与记忆服务。A1 与 A2 之间只有控制器不同，这一对比回答 RQ1。**A0** 是交互式的「语音 + 头像」系统基线（D-004 保留），用于端到端时延、语音、偏好与成本的系统级比较（RQ6）。它回答「在语音必须跟随 5 秒请求的前提下，TaoMate-H3 是否值得」。TaoMate-LTX 上的 A2 作为粒度与记忆的对照（RQ3、RQ4）。

### 5.2 A2 的五层结构

从上到下依次为：

1. **交互层（快路径）。**
   - VAD/ASR、话轮与打断管理；
   - **应答 LLM**：小而快，产出下一块的台词与动作意图。
2. **导演层（Co-Director 在线化）。**
   - 人设风格轴（策略、叙事模式、美学）在会话开始时固定，在会话内注入每个智能体；
   - **规划 LLM**（慢路径，异步）维护目标栈并拆解多步请求；
   - UCB1 老虎机只在**会话之间**更新。奖励由两部分组成：分因子 MLLM 评审，加上用户显式反馈。
     - 与 Co-Director 一样，奖励**按轴分别**更新三个轴。
     - 所有臂都**保持正典**：只影响表达方式（语气、节奏、景别），不改外貌与声音。
     - 老虎机只在单独的预试会话中训练；E2–E5 评估期间**冻结策略**。它的作用另做一个单独随机化的次要消融。
3. **连续性层（CANVAS + A²RD 在线化）。**
   - **状态账本**：人设外貌状态、地点 id、道具状态（含持有者）、逐块文本状态（身份、动作、空间三元组、镜头）；
   - **块脚本合成器**：把账本中不变的字段（外貌、场景、镜头、声音）**逐字复用**，只让动作与台词演进。这个约定来自 TaoMate（LTX）论文；H3 实际接受的是每个请求一个字符串，所以要经过编译（§5.3），写法与 H3 官方示例相同。
4. **生成层。**
   - TaoMate-H3 流式运行时，加上 T1 提示队列、T2 音频前瞻、T3 逐块输出；
   - 在这一层之上，**编译器**只下发能力清单中实测可靠的动作或表情描述，其余降级（比如改为口头回应）或婉拒。
5. **质检层（VQQA 在线化）。**
   - 编译时为每条指令生成 1–3 个【目标】可检验问题，例如「这一块中人物是否举杯喝茶？」；
   - 在线 VLM 在**呈现**后的截止时间内作答；
   - 失败时生成前向语义梯度（低分问答 → **最早可接收修正的请求**的提示中的修正）；
   - 检测到漂移时触发**纠偏**（定义见 §5.4）；
   - 离线部分：完整的 VQQA 与 A²RD 评分细则只用于校准能力清单，从不用于评估。

**记忆服务**贯穿各层（§5.6）。A²RD 的成功/失败提示库在其中作为跨会话的程序性记忆。

### 5.3 中间表示：块脚本（BlockScript）及其编译后的 H3 提示

块脚本是内部结构。编译器把它编译为 TaoMate-H3 实际接受的**每 5 秒一个字符串**【代码：`config.py:80-134`】，格式与官方示例相同：`integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`，台词写成内联的 `<d>[Chinese] …</d>`（示例文件 `examples/prompts_60s.json`）。

官方 60 秒示例中，每个 5 秒提示都会逐字复述「同一人物、同一服饰、同一场景、镜头与光照保持不变」，只让动作与台词变化。状态账本做的就是把这种写法**自动化、可审计**。

```yaml
# 块脚本（内部）
request_index: 42
plan_version: 17
canon:        # 取自正典与账本，逐字复用，不由 LLM 改写
  subject: "a young East Asian woman (S1) in a green hanfu, hair in a bun with a jade hairpin"
  scene: "classical study, lotus pond outside the window, teapot, pastries and incense burner on the desk"
  camera: "locked eye-level medium shot, soft key light, constant exposure"
  voice: "S1 uses the same gentle, medium-paced Mandarin voice"
evolving:
  action: "she puts the book down and lifts the teacup with both hands to take one sip"   # 须命中能力清单
  transcript: "好，我先喝口茶，再给你讲 CUDA。"
checks: ["人物是否捧起茶杯并喝茶？", "台词是否被完整、准确地说出？"]
provenance: {source_utterance: utt-551, speaker: user}
```

```text
# 编译后交给 TaoMate-H3 的提示（第 42 个请求）
integrated_multimodal_description: [Shot 1] Live-action portrait livestream, one uninterrupted five-second shot.
The same young East Asian woman (S1) in a green hanfu, hair in a bun with a jade hairpin, sits in the same classical
study; the lotus pond, teapot, pastries and incense burner remain unchanged. The locked eye-level medium shot,
soft key light and exposure remain constant. S1 uses the same gentle, medium-paced Mandarin voice. She puts the book
down and lifts the teacup with both hands to take one sip, then says once: <d>[Chinese] 好，我先喝口茶，再给你讲 CUDA。</d>
Her lips close. No other person or human voice appears. No captions or readable text appear anywhere in frame.

overall_soundscape: Clear dry Mandarin speech, quiet room tone, a soft porcelain clink as the cup is set down.

non_diegetic_music: N/A
```

**声音与台词的保证范围。** H3 没有声音参考输入，最终音频来自基座 H3 的纯音频教师【代码：`runtime.py:339-359,739-743`】。所以：
- 声音一致性只能靠文本描述与音频尾部延续；
- 「台词被逐字说出」不能事先保证，E1 要测：在换提示、换种子、会话重置之后，逐字准确率（WER）是多少，说话人是否一致；
- 进入生成前的内容审核只能拦住**脚本**，拦不住模型说出脚本以外的话；
- 在即时锁定的余量 σ 内，对**已生成**的请求音频做 ASR 复核，不合格就不播放该请求，改为反应片段加口头说明。这一步增加的时延与误拦率都单独计量。若 σ 内来不及复核，就如实声明「播放前不保证台词」。

**叙述策略。**
- **意图**可以立即说出，比如「好，我喝口茶」。
- **完成**（例如「刚才那首歌你喜欢吗」这类以「已发生」为前提的话）只有在质检判定遵循之后，才能出现在后续台词里。

### 5.4 关键时序、纠偏与打断

**单一时间线**（请求周期 R = 5 秒，每个请求依次经过以下事件）：
1. **锁定提示** $P_{k}$：块脚本 $s_k$ 定稿；之后到达的指令只能进入 $s_{k+1}$。
2. **音频教师** $A_k$：基座 H3 为 $s_k$ 计算音频里程碑，用时 $G_a$。
3. **学生生成**：从 $S_k$ 开始逐块生成，第一块用时 $G_1$；学生按步骤消费教师里程碑，所以教师必须提前完成，或者与学生并行且在各步骤到来前就绪。
4. **可见**：请求 $k$ 在 $V_k$ 开始呈现，4 个块依次可见。

**提前量** $\Lambda = G_a + G_1 + \delta$，即从锁定提示到第一块生成完毕、可以播放的时间。

**两个硬约束。**
1. **呈现时隙。** 请求 $k+1$ 最早只能在请求 $k$ 的 5 秒时隙结束后呈现，即 $V_{k+1} \ge V_k + R$。
2. **KV 依赖。** 学生生成 $k+1$ 需要 $k$ 的最终 KV 提交；发布代码按请求顺序执行【代码：`runner.py:299-323`】。

所以就绪时间 $\text{ready}_{k+1} = \max(P_{k+1} + G_a,\ \text{done}_k) + G_1 + \delta$，呈现时间 $V_{k+1} = \max(\text{ready}_{k+1},\ V_k + R)$。

**锁定策略：即时锁定（本版采用，记入 D-018）。**
- 在请求 $k$ 呈现期间**尽量晚**锁定 $k+1$：$P_{k+1} = V_k + R - \Lambda - \sigma$，其中 $\sigma$ 为安全余量，也用于生成语音的 ASR 复核。
- 前提有两条：$\text{done}_k \le P_{k+1} + G_a$，即上一请求的学生已完成；以及完整流水线吞吐 < R。
- 这样，锁定到呈现的时间只有 $\Lambda + \sigma$，而不是一整个 R。
- **对照策略：** 早锁定（在 $k$ 开始呈现时锁定 $k+1$）更抗抖动，但锁定到呈现要一个 R；L = 1 还要再加一个 R。

**最早可接收修正的请求。**
- 请求 $k$ 的第 $c$ 块（从 0 起算）在 $V_k + c\Delta$ 时**开始**呈现，$\Delta$ 为单块时长，约 1.4 秒。
- **证据完整时刻** $E$：检验所需的**最后一帧**实际呈现的时刻，取自客户端呈现时间戳。下面的 $E = V_k + (c+1)\Delta$ 假设各块等长、播放不间断，仅作示意；实际块长不等（首请求为 39/34/34/17 帧），且可能降速播放，所以分析一律使用**实测**的最后一帧呈现时间。
- 修正链条耗时 $C = v + $ 修正合成 $+$ 编译 $+$ 内容审核 $+$ 文本编码，其中 $v$ 为 VLM 判定时间。
- 修正进入**第一个满足** $P_j \ge E + C$ 的请求 $j$。$j$ 可以是 $k+1$、$k+2$ 或更晚，**不设上限**。
- 在即时锁定下，整块检验时进入 $k+1$ 的条件是 $(c+1)\Delta + C \le R - \Lambda - \sigma$。例如（示意，假设等长块）$\Lambda + \sigma = 3.5$ 秒时，只有第 0 块、且 $C \le 0.1$ 秒才可能进入 $k+1$【推导】，所以通常是 $k+2$。早锁定下，**不可能**进入 $k+1$。
- E2 实测并报告 $C$ 的各项、$j$ 的分布，以及错过或不具备修正资格的失败。

**纠偏：三种可执行的干预**，都要与「只逐字重复正典字段」对照：
1. **文本纠偏。** 针对漂移的属性加入明确的修正语句，例如「发簪为玉簪，不是金簪」。这是提示内容的**实质改变**，不同于逐字重复。
2. **会话重置。** 用正典文本新开一个生成会话，KV 与 sink 都重新建立。会有可见接缝，接缝需要测量。
3. **图像重锚定。** 仅在 FL2AV（参考帧版本）发布并验证后才有，届时从正典帧启动新会话。

在此之前，本提案不把前两种称为「图像锚定」。

**打断。**
- 客户端立即停止播放（**视觉确认**，目标 ≤ 250 ms），切到最后一个已呈现的帧或反应片段。视觉确认与**有意义的生成回应**分开计量。
- 生成端的问题：正在生成的请求仍可能提交 KV，并推进音频教师的尾部，导致后续内容依赖用户**从未看到**的动作和台词。
- 处置方式，按优先级：
  1. T8 回滚到最后一个已呈现的块（可行性在 M1 评估）；
  2. 会话重置（测量延迟与接缝）；
  3. 接受分叉：账本记录「已生成未呈现」的内容，下一个块脚本显式衔接，并如实计量这种不连续。

### 5.5 即时反应层（弥补 5 秒粒度）

语音由视频模型生成，所以对话延迟至少等于一个请求的延迟（§6.4）。我们引入两项缓解措施：

- **预渲染反应片段库。** 离线用同一底座、同一人设生成「点头倾听」「思考」「稍等」等 1–3 秒【目标】片段，由客户端在打断或等待时切入。它只提供**视觉确认**，不算有意义的回应。
  - 拼接处会有接缝，接缝需要测量；
  - 片段与实时流之间的身份一致性单独评估。
- **缩短请求。** 在 H3 上缩短请求需要重新蒸馏，属于长期方向。短期内，只有在 LTX 上**证实可以逐块换提示**之后，才能在该骨干内检验粒度的影响（RQ3）。

### 5.6 长期记忆设计

五类状态严格区分：

| 类别 | 载体 | 生命周期 | 不可混淆为 |
|---|---|---|---|
| 工作上下文 | 应答与规划提示、近期话轮、**已呈现**内容摘要 | 单次会话 | 长期记忆 |
| 持久用户事实与偏好 | 语义存储：主语、谓语、值、溯源、有效起止、作用域、置信度、derived_from | 跨会话 | 智能体推断 |
| 情景历史 | 只追加日志（时间戳、说话人） | 跨会话 | 摘要 |
| 人设与世界连续性（**状态账本**） | 正典锚点（永不覆盖）、最近状态、地点与道具状态、逐块文本状态；H3 的 FL2AV 发布后再加入参考帧 | 跨会话 | 生成器 KV |
| 模型推理缓存 | TaoMate-H3 的 sink + 最近 2 块 KV、位置偏移、首块归一化统计量、音频教师尾部、LLM KV | 单次生成器会话 | **任何**长期记忆 |

**写入。**
- 事实只从用户话轮抽取，并先判断句子属于哪一类：本人断言、转述人设的话、提问、假设或玩笑。
- 人设说过的话进入**生成事件日志**，永不升级为用户事实。
- 与人设旧输出语义匹配的候选标记为 `echo`，须经用户确认。
- 智能体推断只作为候选信念。
- 弹幕只写入公开作用域，标注 `viewer-claimed`，限速并清洗。

**作用域。**
- 所有派生物都带 `source_scopes` 标签：摘要、人设台词、账本条目、反应片段。
- 直播模式只加载 ⊆ {公开, 正典} 的内容。
- 私聊中人设说的话属于私有。
- 公开会话只能从正典锚点启动。

**纠正。** 双时态更新：旧值记下 `valid_to` 并保留审计。纠正沿 `derived_from` 让所有派生物失效。

**删除（擦除）。** 物理删除，并级联到以下对象：
- 嵌入与索引；
- 摘要（删除后重新生成）；
- 账本条目；
- 缓存提示与 LLM KV（通过重启会话清空）；
- 私有录像；
- 生成器状态：若被删内容仍在未发送的块脚本或当前生成状态中，丢弃未发送的块脚本，并从正典锚点重启生成会话。

已呈现的画面无法撤回。墓碑账本只记录哈希 id、时间和原因。

**冲突优先级。** 用户断言（最新有效）> 系统观测 > 智能体推断 > 观众声称。

---

## 6. 底座集成计划（依据代码核查）

### 6.1 已具备（代码中可见）【代码】

- 3 步去噪的流式 LoRA（rank 128，未合并，以 BF16 旁路存放）；
- 按请求提示（JSON 列表）；
- 滚动 KV，同一全局时间轴、不重置；
- 音视频同步输出；
- 并行方式为 TP2 × Ulysses4，支持 4 或 8 卡；
- 480p / 768p / 1088p。

### 6.2 仅上游报告【引用】

- TaoMate-H3 的速度数字（8×H20），**不含**内部音频准备，且输出到最后才写出；
- TaoMate 论文的 35 FPS、30 分钟以上连续生成、各项质量指标。项目主页与论文的数字不一致，例如 LipSync 5.773 与 5.918。
- 参考帧版本 FL2AV「10/15 前发布」，Ref2AV 待定。

### 6.3 需工程扩展（T1–T7，见 §3）

最小集成点：
- `runner.py:299-323`：取下一个提示的循环；
- `streaming/runtime.py:609-621`：每块输入的构建；
- `cli.py:223-229`：音频教师的预计算。

**vLLM-Omni 在 `7b4dc76` 与 `3bd5ac9` 两个版本上都**无法**直接承载 TaoMate-H3，原因有四：
- LoRA 加载器只认 Turbo 文件名与 PEFT 键；
- H3 模型没有跨请求的持久缓存；
- H3 没有实现实时 WebSocket 或流式会话接口；
- 现有的续写与分块解码都只在单个请求内工作【代码】。

**结论：** 短期直接在 TaoMate-H3 运行时上加队列，比移植到 vLLM-Omni 省事得多。移植到 vLLM-Omni 作为后续上游贡献。

### 6.4 时延模型【推导】（数值仅作示意，由 M1 实测替代）

沿用 §5.4 的单一时间线。$R$ = 5 秒；$\Lambda = G_a + G_1 + \delta$ 为锁定到可见的提前量；$A$ 为端点检测、应答 LLM 与编译的时间；$I$ 为视觉惯性。

锁定每隔 R 发生一次，指令要等 $U(0,R)$ 才赶上下一次锁定。锁定到呈现的时间取决于锁定策略（§5.4），且呈现不能早于上一请求的时隙结束：

| 策略 | TVC | 示意中位（$A = I = 0.5$ 秒） | 示意偏高 |
|---|---|---|---|
| **即时锁定（采用）** | $A + U(0,R) + \Lambda + \sigma + I$ | $\Lambda + \sigma = 3.5$ 秒时 ≈ **7 秒** | ≈ 9.5 秒 |
| 早锁定，L = 0 | $A + U(0,R) + R + I$ | ≈ **8.5 秒** | ≈ 11 秒 |
| 早锁定，L = 1 | $A + U(0,R) + 2R + I$ | ≈ **13.5 秒** | ≈ 16 秒 |

表中数值为各项相加的示意，**不是分位数**【推导·估计】。实现 T1–T3 之后，用实测时间戳重新计算，并做回放仿真。

**吞吐条件（完整流水线，不只是 DiT）。** 平均每个请求的（教师 + 学生 + 编码）时间要小于 R，并且两个模型同时常驻时显存与算力都够用。
- 8×H20 上仅 DiT 就要约 7.4 秒 / 请求【推导】，**不满足**。
- 教师的开销尚未测量：它要跑 9 次前向，且在发布路径中是预先完成的【代码】。
- 「教师与学生重叠执行」是新的工程（T2），能否满足 $\max(G, G_a)$ 形式的并行需要实测。

**TaoMate-LTX。** 其提示粒度同样约为 5 秒窗口【代码】，所以**不预设**它的 TVC 更低，只在 M0 中实测。

**三步资格（按实现顺序）。**
1. **M0：组件剖析**（不是资格认定）。在发布路径上分别测教师、学生、编码的耗时与显存。发布路径先准备全部音频，最后写一个 MP4【代码：`cli.py:219-229`、`runner.py:293-330`】，所以 M0 **无法**测端到端的 Λ 与呈现时间。
2. **M1：端到端资格。** T1–T3 完成后，在真实的客户端播放路径上测 Λ、σ、吞吐与抖动，并做 ≥ 3 × 30 分钟浸泡测试，卡顿 ≤ 1 次 / 10 分钟。这一步只认定「生成器 + 播放路径」的实时性。
3. **M2 末：整系统再认定。** 语音链路、A2 控制器、VLM 质检与记忆服务都会增加时延与 GPU 争用，所以装配完整系统后要再做一次同标准的浸泡测试。通过之后，才能宣称「实时直播智能体」，并以**实时**标签开展 E2 与 E5。**若未通过**，E2 与 E5 仍然进行，但改用 §1.2 的近实时服务规则（话轮制 + 准入控制），所有结果标注为「近实时」：
   - RQ1、RQ2、RQ4、RQ5 的对照仍然有效，因为 A1 与 A2 共享同一底座；
   - 时延类目标（TVC、TFMR）只报告实测值与等待时间的增长，**不**宣称达到 §8 的实时目标。

两阶段都通过后，才称为「实时」；否则按「近实时」如实标注。

### 6.5 需训练或研究

- 把学习型锚点记忆移植到 H3；
- 缩短请求粒度（重新蒸馏）；
- 音频教师的逐块化；
- 端到端双工。

首个演示不依赖这些。

---

## 7. 实验设计

**控制变量：**
- 底座检查点与 LoRA 版本；
- GPU 型号与数量；
- 分辨率 480×864；
- LLM、ASR、VLM 版本；
- 随机种子；
- 脚本化工作负载。

**记录项：**
- 全部挂钟时间戳；
- 块脚本与版本；
- 检验问题与判定；
- 呈现帧哈希。

### 7.0 M0：硬件与底座表征（门槛）

- 在 `gpu run` 预约中执行 `torch.cuda.get_device_capability()`，确认是否为 SM90。
- 在发布路径上，4 卡与 8 卡各跑 3 次 × 60 秒的 TaoMate-H3 生成【目标】，**分组件**剖析：音频教师、学生每块、VAE 解码、编码各自的耗时与显存。发布路径按顺序执行教师与学生，所以**两者同时常驻**的显存与争用在 T2 完成后、于 M1 用专门的测试程序测量。M0 的结果只用于估计 Λ，端到端资格在 M1 认定（§6.4）。
- 若本机 GPU 为 CC 8.9：先做 T4（FA2/SDPA 移植），并做与 FA3 输出的一致性检验（在另一台 H20/H200 上），再测速；否则申请 Hopper 机器。
- 在同一硬件上测 TaoMate-LTX 作为对照。

### 7.1 E1：能力校准（构建能力清单）

在 5 个场景 × 人设上，共 **40 个动作与表情描述**：喝茶、翻书、挥手、点头、起身、笑、皱眉等。另测台词类型（讲解、唱歌、问答）。每项 30 次试验【目标】。

**评判：**
- 离线 VQQA 式问答；
- A²RD 评分细则；
- 20% 分层抽样做人工双盲标注。

**产出：**
- 成功率（Wilson CI）；
- 生效时间分布（KM 曲线）；
- 副作用：身份漂移、口型失配。

**校准数据与评估数据互不相交。**

### 7.2 E2：指令遵循、多步任务、打断与纠正（RQ1、RQ2、RQ3）

**任务。** 80 个任务 × 5 个种子【目标】，由 TTS 模拟用户按脚本发出。分为三类：
- 单步动作或内容；
- 多步任务，如「先喝口茶，再翻到下一页，然后讲一段」；
- 交互动态：中途纠正、改目标、打断、针对呈现内容的指代纠正。

**条件：** B0、A1、A2、A2−清单、A2−质检、A2−前向修正、A2−账本，以及 TaoMate-LTX 上的 A2。

**主结局：** 对每次试验做**双人双盲人工裁定**，第三人仲裁，独立于在线质检。

**计分单位：意图链。** 用户的一条新指令开启一条意图链。之后用户对它的撤回或改口**并入同一条链**，按链的最终意图计分一次。与之无关的新指令开启新链。**有效意图链** = 最终意图未被用户撤回的意图链，包括被系统容量跳过的链。**主分母 = 有效意图链总数**，每条有效意图链恰好计分一次；用户撤回的链不在分母中，只单独报告数量。

**截止时间 D 与计时起点（事先注册，所有条件相同）【目标】。** 计时起点是开启该意图链、或最后一次改口的**用户话语结束时刻**（VAD 端点，在共享呈现时间线上）。

| 任务类型 | D | 判定内容 |
|---|---|---|
| 单步动作 / 表情 | 15 秒 | 首个被判定遵循的呈现帧 |
| 内容类（讲解、唱歌、问答） | **两项都满足才算成功**：(1) 15 秒内开始切题的语音回应；(2) 整段回应在「15 秒 + 预定时长」内完成，预定时长按任务事先注册（问答 ≤ 10 秒，讲解 ≤ 30 秒，唱歌 ≤ 30 秒），并满足事先注册的评分细则：问答答对；讲解覆盖指定的 k 个要点且无事实错误；唱歌唱出指定歌曲或主题的歌词段落且可辨认为歌唱 | 主结局要求 (1) 与 (2) 同时满足。「起始成功率」单独报告，不计入主结局 |
| 多步任务（n 步） | 每一步 15 秒，从上一步被判定遵循的时刻起算；总截止为 15n 秒 | 按顺序全部遵循才算成功 |
| 纠正 / 改口 | 从改口话语结束时重新计时，15 秒 | 按最终意图判定 |

近实时模式使用同样的 D，这样结果可以直接比较。超时即失败，并在 D 处删失。

**结果规则：**

| 情况 | 处理 |
|---|---|
| 拒绝或降级 | 计为失败 |
| 用户改口或撤回 | 并入同一意图链，按最终意图计分一次；撤回的链不计入分母，单独报告 |
| 容量跳过（系统因负载，按准入控制丢弃一条**未被用户改口**的意图链） | 该链属于有效意图链，**计为失败**。容量跳过率 = 被跳过的链数 / 有效意图链总数（不含撤回链），按条件单独报告 |
| 评判「无法判断」 | 主分析计为失败，另做敏感性分析 |
| 从未遵循 | 在截止时间 $D$ 处删失 |

**指标：**
- 指令级成功率（分母为有效意图链总数）；
- 容量跳过率与撤回链数；
- 拒绝与降级率；
- 条件遵循率；
- FCR = 被裁定为未完成的完成声明数 / 完成声明总数，同时报告声明覆盖率；
- 补救率（RQ2）；
- TVC（截止成功率、KM 中位数）；
- 首个有意义回应（TFMR）。

**功效与预注册。** 以任务为聚类单位，事先注册估计量。用预试得到的基线成功率、任务内相关（ICC）与多重比较校正（Holm）做仿真，确定样本量。本提案不预先声称可检出多大的差异。

**RQ2 设计。** 在事先定义的失败点上随机分配「前向修正」或「重复原指令」，避免按处理后的结果挑选样本。

**B0 的定位。** B0 主要检验「交互」对「固定循环」的价值，不承担其他结论。

### 7.3 E3：记忆（RQ5）

- **组件基准：** LongMemEval_S、MemoryAgentBench 选择性遗忘、GateMem 式作用域测试。
- **直播人设协议：** 20 用户 × 6 会话【目标】，覆盖以下情形：
  - 人设生成的干扰信息，例如人设说「我最爱喝龙井」；
  - echo 探针；
  - 纠正与删除；
  - 私聊后立刻开直播；
  - 弹幕投毒（MINJA 式）。
- **对照组（RQ5）：** 在相同工作负载与相同检索预算下比较四种记忆：
  - 全历史上下文；
  - Mem0 式无类型抽取；
  - 去掉作用域隔离的 A2 记忆；
  - 完整的 A2 记忆。
- **泄漏上界：** 在 **≥ 300 名独立模拟用户**上检验话语通道：块脚本的台词文本，以及**底座生成的语音**。
  - 所有对探针问题的**生成语音回答**都由两人完整听审（约 900 段），不依赖 ASR 抽检。
  - ASR 只用于其他场景的筛查，它的检出灵敏度用人工标注校验。
  - 精确上界 < 1% 要求**零**用户级泄漏。
  - 屏幕文字与生成画面只在约 30 名用户上做描述性统计。

### 7.4 E4：长时一致性与核心假设（RQ4）

- 在 H3 内部比较以下几组（提示长度预算与重置频率在组间匹配）：
  1. 纯脚本；
  2. 逐字重复正典字段；
  3. **仅账本**（账本驱动提示合成，不做纠偏）；
  4. 账本 + 文本纠偏；
  5. 无账本的文本纠偏：**同一个**漂移检测器、同一条纠偏规则、同一时机，只是纠偏文本只能取自静态正典档案，拿不到账本记录的当前状态；
  6. 账本 + 会话重置；
  7. 无账本的会话重置：由同一个漂移检测器在同样条件下触发，重置后的提示只来自静态正典档案。

  组 4 对 5、组 6 对 7 之间，**唯一的差别是能否读取账本**，由此把账本的作用与纠偏、重置本身分开。TaoMate-LTX 学习型记忆只作描述性对照。会话数按会话级精度计算确定（预试估计方差后，目标 ≥ 10 场 × 30–60 分钟【目标】）。
- 指标：
  - 人脸身份相似度，阈值用人工同一/不同标注校准；
  - **语音保真与内容**：生成语音的 ASR 转写相对台词的 WER；跨会话、跨重启的说话人一致性（嵌入 + 人工同一/不同判断）；讲解类内容的事实正确性（评分细则 + 人工）；
  - 服饰、场景、道具状态探针；
  - 声音一致性（说话人嵌入）；
  - 口型同步 LSE-C/D；
  - 接缝与卡顿。
- **核心假设的检验：** 在 ≥ 3 次【目标】会话重启之间（每次都是新上下文）检验记忆与遵循阈值。未包装的端到端系统若有权重，按原样参与；否则检验较弱的消融版本（A2 对去掉记忆服务的 A1），并如实标明其较弱。

### 7.5 E5：人工评估（RQ6）

- 被试内设计，平衡顺序。预试 N = 12，正式 N = 24【目标】。
- 条件：A0、B0、A2（A1 视时间而定）。
- 量表：MOS、SUS、Godspeed、社会临场感、时延容忍度、成对强制选择（Bradley–Terry 分析）。
- 流程：预注册；知情同意。

### 7.6 E6：私有测试直播

脚本化观众，2 小时 × 3 场【目标】。测量：
- 弹幕响应时延；
- 投票动作的成功率；
- 投毒与泄漏；
- 卡顿。

**参考主播 sylar_nv 仅作定性参照**，因为其实现未经证实（H3 片段拼接是推测）。只有满足下面全部条件，才做定量对比：VOD 已存档、弹幕与视频时间对齐、使用脚本化测试账号、运营者同意。即便如此，结论也标明为非受控对比。

### 7.7 不确定性报告

- 所有指标都给 95% CI（聚类 bootstrap），并报告 κ。
- 时延给出 p50/p95/p99，每项 ≥ 3 次重复。
- 删失数据用生存曲线分析。
- 遵循率始终与覆盖率一起报告。

---

## 8. 指标与成功标准（均为【目标】，M0 与预试后修订）

| 指标 | 成功标准 |
|---|---|
| 指令级成功率（H1a，主；分母为有效意图链总数，即最终意图未被撤回的链，含被容量跳过的链；拒绝、降级、容量跳过均计为失败） | A2 − A1 ≥ +10 pp，成对 CI 不含 0 |
| 虚假完成声明率 FCR | A2 ≤ 5% 且低于 A1；声明覆盖率 ≥ 70% |
| 前向修正补救率（H2） | 在最早可接收修正的请求中，补救率高于「重复原指令」，CI 不含 0；同时报告该请求是第几个 |
| TVC（动作类） | H3 使用即时锁定，且 **M1** 实测 Λ + σ ≤ 3.5 秒时：15 秒内截止成功率 ≥ 80%，KM 中位 ≤ 8 秒。Λ 更大或改用早锁定时，在 M1 后按回放仿真重设。H3 与 LTX 之间的**跨骨干**比较只作描述；LTX 内部的粒度检验见 RQ3 |
| 首个有意义回应 TFMR | 回应语音开始播放的时间：p50 ≤ 8 秒（前提同 TVC；由实测时间线计算） |
| 视觉确认（反应片段或停帧） | p95 ≤ 1 秒；与 TFMR 分开统计 |
| 语音保真 | 生成语音的 ASR-WER 相对台词 ≤ 10%；跨会话说话人一致性 ≥ 80%（人工判断） |
| 讲解正确性与安全 | 事实错误率与不安全内容率单独报告。块脚本进入生成前先审核；**已生成的语音**在呈现前于 σ 余量内做 ASR 复核，额外时延与误拦率单独计量 |
| 打断停止 | p95 ≤ 250 ms（客户端） |
| 身份一致性（30–60 分钟） | ≥ 80% 的窗口高于人工校准阈值；声音相似度同样标准 |
| 口型同步 | LSE-C/D 不劣于 H3 基座的发布水平 |
| 虚假用户事实率 | ≤ 2% 且低于基线 |
| 删除后泄漏 | ≤ 5% |
| 跨域泄漏（话语通道） | 精确上界 < 1%（≥ 300 名用户） |
| 流稳定性 | ≤ 1 次卡顿 / 10 分钟（通过实时资格的配置） |
| 评判有效性 | κ ≥ 0.6，否则以人工标注为主 |

---

## 9. 里程碑、资源与风险

### 9.1 里程碑（周期为【估计】）

| 里程碑 | 周期 | 内容 |
|---|---|---|
| M0 | ≈ 1 周 | 硬件确认；FA 移植可行性；H3 与 LTX 测速；权重使用许可 |
| M1 | ≈ 3 周 | T1–T3、T5；浸泡测试；E1 校准；质检评判验证 |
| M2 | ≈ 3 周 | A0/B0/A1/A2、账本、记忆服务、语音链路、反应片段库；**结束时对整系统再认定实时性** |
| M3 | ≈ 3 周 | E2–E4 |
| M4 | ≈ 2 周 | E5 预试、E6、撰写报告 |

### 9.2 资源

- **GPU：** H3 需要 4–8 卡，另需 1–2 卡跑 LLM、ASR、VLM。全部通过 canhazgpu 预约并设置超时。这是偏乐观的估计。
- **硬件前提：** 若本机确为 CC 8.9，要么完成 T4，要么使用 Hopper 机器。
- **模型：** 本地共享目录已有 MiniMax H3 快照（272 GB，含 FL2VA/Ref2VA 与文本编码器，完整性未校验）。TaoMate-H3 LoRA 与 TaoMate-LTX 权重需要下载，本阶段未下载。

### 9.3 主要风险

| 风险 | 可能性【估计】 | 对策 |
|---|---|---|
| FA3 无法在本机运行，或移植后精度下降 | 高 | M0 门槛；使用 Hopper 机器；以 TaoMate-LTX 兜底 |
| H3 吞吐达不到实时 | 高（按 H20 数据） | 近实时模式并如实标注；降分辨率；以 LTX 对照 |
| 5 秒粒度导致交互体验差 | 高 | 即时反应层；RQ3 量化；长期重新蒸馏 |
| 提示词无法稳定产生指定动作 | 中 | 能力清单排除；口头替代；作为研究发现报告 |
| 音频教师与中途提示冲突（音频按请求预算） | 中 | T2 前瞻一请求；指令延后一个请求生效并标注 |
| 打断后生成状态与呈现内容分叉 | 高 | T8 回滚 / 会话重置 / 显式衔接，并计量不连续 |
| 教师与学生同时常驻时显存或算力不足 | 中 | M1 在 T2 后实测；分卡部署；降分辨率 |
| 许可（H3 社区许可排除美、欧、英、韩地区） | 确定 | 仅作研究用途，部署地区须合规 |
| GPU 调度冲突 | 中 | 提前预约时段 |

---

## 10. 局限、隐私安全伦理

**局限：**
- 尚无本地测量；
- TaoMate-H3 的关键结论来自代码阅读，未执行；
- 5 秒粒度是底座的硬约束，本提案只做缓解与量化，不解决它；
- 模拟用户无法覆盖自发语音；
- 人评规模小；
- 参考主播不受控。

**隐私与安全：**
- 私有记忆仅在明确同意后存储；用户可查看、纠正、删除，删除会级联；
- 公开与私有物理隔离，泄漏探针作为发布门槛；
- 生成内容永不成为用户事实；
- 弹幕视为不可信输入；
- 人设为虚构，所有直播都标注 AI 生成；不使用真人肖像或声音；
- 对弹幕请求做内容审核（参考主播的弹幕中出现过不当请求）；
- 语音由底座生成，LLM 无法流式控制每个字，所以块脚本要在**进入生成前**审核，生成后再做 ASR 抽检；
- 遵守 MiniMax H3 社区许可与 LTX/Gemma 许可；
- 人评须通过伦理审查。

---

## 11. 参考文献（完整、经核实的 BibTeX 见 `docs/references.bib`）

- **Google 长视频套件：** google2026longformblog，song2026codirector，mondal2026canvas，long2026a2rd，song2026vqqa
- **TaoMate：** gan2026taomate；TaoMate-H3（[GitHub](https://github.com/TaoLiveAIGC/TaoMate-H3)，提交 `6b2f998`；[HF](https://huggingface.co/TaoLiveAIGC/TaoMate-H3)）；TaoMate 代码（提交 `136d890`）
- **MiniMax H3：** minimax2026h3blogvideo
- **LingBot 与流式视频：** gao2026lingbotworld2，yang2025longlive，huang2025selfforcing
- **数字人与双工：** huang2025liveavatar，xie2025xstreamer，huang2026wanstreamer，defossez2024moshi，wang2026pace
- **控制与验证：** ahn2022saycan，huang2022innermonologue，xu2026worldmark，abotworld2026abotworld0
- **记忆与评估：** wu2024longmemeval，hu2025memoryagentbench，ren2026gatemem，yu2026kbench，dong2025minja，ying2026wbench

## 12. 评审状态

本中文版（v2.0 → v2.11）属于重大架构变更。它提交 GPT-6 Sol（Codex）独立评审，记录见 `docs/codex_reviews.md` 的「中文 v2.0」一节。

===== FILE: docs/implementation.md =====
# Implementation (Phase 2)

Status: started 2026-09-26 on the owner's instruction (D-019). This document describes the implementation of
the proposal in `docs/research_proposal_zh.md` v2.11: the architecture as built, how to run it, and what is
verified. Every number is labelled *measured locally*, *cited*, *estimate* or *target*.

## Layout

| Path | Proposal § | What it is |
|---|---|---|
| `live_agent/types.py` | §9, §10 | Shared types: CanonProfile, BlockScript, IntentChain, Chunk, Verdict, TimelineEvent |
| `live_agent/prompt/h3_compiler.py` | §9 | BlockScript → TaoMate-H3 prompt string, in the official `integrated_multimodal_description` / `<d>` format. Canon fields are copied verbatim |
| `live_agent/capability.py` | §8.2 L4, §14.2 | Capability manifest. The compiler emits an action only when it is `executed`/`calibrated` and above the success threshold; otherwise it degrades or refuses (both logged as failures) |
| `live_agent/ledger.py` | §8.2 L3, §10.4 | State ledger (online CANVAS + A²RD): immutable canon, current state, per-request state, textual drift correction, bridging for unshown content |
| `live_agent/timeline.py` | §10, §11 | Single timeline, just-in-time locking (P_{k+1} = V_k + R − Λ − σ; Λ estimated online), earliest correctable request, latency model, JSONL event log |
| `live_agent/director/director.py` | §8.2 L1–2, §9 | Responder (LLM → intent chains + per-request segments), cancellation rule, narration policy ("done" is spoken only after verification), forward-repair queue, A1 open-loop mode |
| `live_agent/qc/judge.py` | §8.2 L5 | VLM judge on presented frames (K=4, may abstain), speech check (ASR character error rate), forward corrector ("semantic gradient"), mock judge |
| `live_agent/orchestrator.py` | §10–§12 | Lock loop, chunk streaming, presentation acks → QC → repair, barge-in (drop unpresented, bridge), erasure (memory cascade + generator reset) |
| `live_agent/memory/` | §12 | Typed, scoped SQLite memory: claim typing, echo detection, source-scope filtering before ranking, bi-temporal correction, erasure cascade with tombstones and `verify_erased` |
| `live_agent/memory_bridge.py` | §12 | Adapter from the memory service to the orchestrator |
| `live_agent/generator/base.py`, `mock.py` | §13 | Generator contract; CPU mock with the TaoMate-H3 chunk layout (39/34/34/17 frames, then 34/34/34/17) |
| `live_agent/generator/taomate_h3.py`, `taomate_worker/` | §13 (T1–T3) | TaoMate-H3 streaming adapter: mid-session prompt queue, audio-teacher lookahead, per-chunk output. Status is tracked in `docs/m0_measurements.md` |
| `live_agent/server/app.py`, `static/index.html` | — | FastAPI WebSocket server and browser client. JPEG frames + PCM16 per chunk; the client's AudioContext is the master clock; chunk start/end acks are stamped with server time |
| `live_agent/asr.py` | — | Qwen3-ASR client (vLLM transcription API) and audio decoding |
| `live_agent/eval/` | §7, §14, §15 | Evaluation: SCHEMA.md log format, scoring (intent chains, D table, outcome rules), stats (Wilson, Clopper–Pearson, KM, clustered bootstrap, Holm, κ, power), 30-task suite, simulated user, runner, report |
| `configs/persona_hanfu/` | §3 | Persona canon and capability manifest (24 actions covering the E2 suite; `documented` until E1 executes them) |
| `live_agent/generator/base.py` `SessionView` | — | One live session on a long-lived shared generator: reset per session, local request numbering, stale chunks dropped (D-022) |
| `live_agent/sim.py` `Recorder` | — | MP4 of the *presented* stream (background-thread encoding), used for adjudication and E1 clips |
| `live_agent/eval/adjudicate.py` | §14, D-014 | Blinded human adjudication: shuffled items, random ids and media names, key kept apart; labels merged back as `source: adjudicated` verdicts with video→session time mapping (D-024) |
| `scripts/e1_rejudge.py`, `scripts/e1_validate.py` | §14.2 | Offline re-judging of saved E1 clips (judge v1/v2); blinded stratified human-validation page and judge-vs-human agreement (accuracy, κ, FP/FN) |
| `scripts/e1_calibrate.py` | §14.2 | E1: idle → action → idle per trial; VLM judge; Wilson CI; clips for the 20% human sample. A judge-only pass marks capabilities `executed`, and only human-validated labels make them `calibrated` |
| `scripts/serve_models.sh` | — | vLLM servers for Qwen3-8B (8101), Qwen3-VL-8B (8102), Qwen3-ASR-1.7B (8103) on one GPU (isolated venv `.venvs/serve`, vLLM 0.28.0 + torch cu129) |

## Running

```bash
# helper models (one GPU; always through canhazgpu)
gpu run --gpus 1 --timeout 6h --note "live-agent helper models" -- scripts/serve_models.sh

# server with the mock generator (no video GPU needed)
python3 -m live_agent.server.app --generator mock --dev-allow-uncalibrated --port 8200
# server with TaoMate-H3 (student on 4 GPUs, teacher on 2; started once, shared across sessions)
gpu run --gpus 6 --timeout 4h --note "live-agent server" -- python3 -m live_agent.server.app --generator taomate_h3
# open http://127.0.0.1:8200 (tunnel the port if remote)

# E2 simulation on the mock stack (real LLM responder, mock judge)
python3 -m live_agent.eval.runner --conditions A1 A2 --seeds 0 --speed 4 --out .cache/e2
# E2 / M1 on the real stack (TaoMate-H3 + LLM responder + VLM judge), recording what was presented
gpu run --gpus 6 --timeout 1h --note "live-agent M1" -- env PYTHONPATH=. python3 -m live_agent.eval.runner \
    --generator taomate_h3 --conditions A2 A1 --out .cache/m1 --record [--allow-uncalibrated]
python3 -m live_agent.eval.report .cache/m1/*.jsonl --compare A2:A1 -o .cache/m1/report.md

# blinded adjudication of the primary outcome
python3 -m live_agent.eval.adjudicate --help   # prepare (criteria frozen from the suite; key kept in
                                               # <batch>.key/, outside the annotator's folder) and merge
                                               # (two raters + optional arbiter; only reconciled verdicts
                                               # are appended; unresolved items listed)
python3 -m live_agent.eval.report <logs> -o report.md              # primary: exits 2 if any chain/claim unadjudicated
python3 -m live_agent.eval.report <logs> --source judge -o diag.md # labelled DIAGNOSTIC

# E1 calibration
gpu run --gpus 6 --timeout 4h --note "live-agent E1" -- env PYTHONPATH=. python3 scripts/e1_calibrate.py \
    --generator taomate_h3 --trials 30 --save-clips --out .cache/e1

# tests (CPU)
python3 -m pytest
```

## Verified so far

- **GPU identity (measured locally, 2026-09-26):** `torch.cuda.get_device_capability()` = (9, 0), 132 SMs,
  139.8 GiB. Hopper, so FA3 is usable (D-020).
- **CPU test suite:** unit and end-to-end tests pass on the mock stack. They cover:
  - the prompt format;
  - JIT lock timing;
  - verified-then-claim ordering;
  - forward repair;
  - refusal of unsupported actions;
  - barge-in drop and bridging;
  - the open-loop baseline;
  - the memory rules;
  - the scoring rules;
  - statistics.
- **Deadlock classes found and fixed by tests:** barge-in or erasure dropping requests that the backlog guard
  was waiting on.

- **M0 (measured locally):** the TaoMate-H3 streaming adapter is real time at 480x864 on 4+2 GPUs. See
  `docs/m0_measurements.md` and D-021.
- **Generator-path diagnostic run (not M1 qualification; measured locally, 2026-09-26; `.cache/m1`, 12 sessions = 6 tasks × A2/A1, seed 0,
  real TaoMate-H3 + Qwen3-8B responder + Qwen3-VL-8B judge, pre-E1 manifest with `--allow-uncalibrated`):**
  - 29–52 chunks per session, **0 playback gaps > 50 ms** in all 12 sessions (after moving the recorder off
    the event loop; the first attempt showed ~0.1 s gaps per chunk caused by the synchronous recorder).
  - A2: every completion claim came after a judge `complied` verdict (0/5 contradicted by the judge). One
    forward repair (M01 step 1) succeeded on the retry, 2 requests after the failure.
  - Judge-sourced chain outcomes: A2 4/6 success (A01, A03, D01, D04), C01 "never" because content rubric
    verdicts come only from adjudication, M01 "never" because of a converter bug (verdicts lacked `step`;
    fixed afterwards, with a test). A1 has no online judge by design, so it scores 0 under judge-only
    scoring. **This is not an A2-vs-A1 result:** the primary outcome is blinded adjudication (D-014), n is
    tiny, and the manifest is not yet calibrated.
  - On-topic speech onset (TFMR) median ≈ 4.2 s in both conditions. The judge-sourced TVC for A2 actions
    uses the start of the verified request as the compliance time (the online judge gives no first
    compliant frame), so it is a lower bound.
  - Spot check (manual, one session): in A2-E2-A01 the persona reaches for the teacup and lifts it toward her
    mouth in the verified request.
- **Server path with TaoMate-H3 (measured locally, 2026-09-26; `scripts/server_check.sh`):** FastAPI/WebSocket server,
  generator started once, and a headless client (`scripts/ws_client_check.py`) that plays chunks, acks with a
  mapped client clock and types two instructions with barge-in. 60 s session, loopback network:
  - Instruction → on-topic speech onset: **2.2 s and 3.6 s**, measured as the audio-energy onset of the presented
    request. Before two fixes it was 10.8 s and 9.3 s:
    - after a barge-in, the timeline restarts, so the next request locks immediately instead of waiting for the
      dropped requests' slots;
    - the restart request waits up to 1.5 s for the in-flight responder decision instead of spending 5 s on a
      "listen" filler.
  - The action verdict arrives 7.7–8.2 s after the instruction (the full request is presented first, then the judge
    runs). The completion remark was heard 12.6 s after the instruction, after the verdict. A failed action got a
    forward correction in its reserved request. The speech check (ASR) returned CER 0.00 on most lines.
  - No playback gaps except the two barge-ins (the persona freezes until new content arrives: 2.6–3.5 s; the
    proposal's reaction-clip visual acknowledgement is not implemented).
  - Bugs found on this path and fixed:
    - ASR rejected 32 kHz WAV, so audio is now resampled to 16 kHz.
    - One failed check ended the session; failed checks now abstain.
    - The chunk header lacked the media duration.
    - The openai SDK's lazy imports stalled the event loop ~1.1 s on the first LLM call (found with a stack-sampling
      watchdog); the client is now warmed up at start-up. Ping RTT went from 1.0–1.8 s to 45–52 ms.
    - The judge's frame encoding moved off the event loop.
    - A chain whose request was cut by barge-in now counts as unexecuted (capacity skip, or resumed).
- **E2 dry run (simulation):** 54 sessions (A1/A2/A2-repeat × 6 tasks × 3 seeds, mock generator and judge,
  real LLM). The pipeline scores end to end. The repair offset j−k is always 2 with 5 s requests (the
  failure is known only after the full request is presented, and request k+1 is already locked), so most
  repaired chains finish after the 15 s action deadline. This is a structural property to report.

## Known deviations and scope limits (after Codex impl1/impl2)

- **Online checks cover action steps only.** Content and memory instructions get a speech (ASR) check but no
  online compliance question, so they cannot be forward-repaired; their outcomes come only from blinded
  adjudication. The drift detector and its three interventions (§10.4: textual correction, session reset,
  image re-anchoring) are not wired into the active path; only the textual bridging note after barge-in is.
  **The E2 pilot claim for A2's online loop is therefore restricted to action and multistep-action chains.**
- **Pre-play ASR of generated speech (§15) is not implemented.** ASR runs after presentation, off the event
  loop. The pre-generation script audit is implemented (erased terms, length).
- **Transport:** the browser path sends JPEG frames + PCM16 per chunk instead of the proposal's per-chunk fMP4
  (`Chunk.encoded` is unused). Presentation acks carry the client's audio-output time (performance clock via
  `getOutputTimestamp`), mapped to server time with the lowest-RTT ping; the accuracy of this mapping is
  not yet measured.
- **Generator-path runs are not M1 qualification.** The §6.4 gate needs the client playback path and at least
  three 30-minute soak runs. The runs in `.cache/m1` are short generator-path diagnostics.

## Not yet verified

- **E1:** a judge-only pilot ran (24 × 5 trials on TaoMate-H3, `docs/e1_pilot.md`). It showed the VLM judge failing
  in both directions, so every capability stays `executed`. Next: two raters label the stratified sample
  (`scripts/e1_validate.py`), then full E1 runs with the validated judge.
- **Primary outcome:** nothing has been adjudicated yet. The tool exists; annotators are needed.
- 30-min soak, 768p/1080p, 60 s+ sessions on the TaoMate path, and the browser playback path on a remote
  client (σ, jitter) are not yet measured. The M1 run used the simulated client on the server host.
- None of the simulation outputs are experimental results. The mock judge's success probability is an
  input, not a measurement.

===== FILE: live_agent/eval/SCHEMA.md =====
# E2 session-log schema (v1)

The orchestrator, simulated user, online judge and human adjudication tool all append to
one JSONL file per **session** (= one task × one seed × one condition). Scoring
(`live_agent/eval/scoring.py`) implements proposal v2.11 §7.2 (intent chains, deadline
table D, outcome rules) and §8 metrics. Validation lives in `live_agent/eval/schema.py`
(`SessionLogWriter`, `load_session`). Events may appear in any order; the loader sorts
them by time.

**Times:** all `t*` fields are seconds on the **shared presentation timeline** (the clock
the client uses to timestamp presented frames, `live_agent.types.now`). Do not use wall-clock time.

**Primary outcome (D-014):** blinded, dual human adjudication with third-person arbitration,
independent of the online monitor. Default scoring reads only reconciled `verdict`s with
`source: "adjudicated"` and adjudicated `speech_onset`s. Online-judge scoring is a
**diagnostic** (`ScoringConfig.diagnostic_config()`, `report --source judge`), and its report is
headed DIAGNOSTIC.

## Header (line 1)

```json
{"type": "session", "schema_version": 1, "session_id": "A2-E2-D04-s3",
 "condition": "A2", "task_id": "E2-D04", "seed": 3,
 "mode": "simulation|generator_path|browser", "generator_seed": 123, "backbone": "taomate-h3"}
```
Required: `session_id`, `condition`, `task_id`, `seed`. `mode`, if present, must be
`simulation`, `generator_path` or `browser`. Other keys are free-form metadata.

## Events

| type | required fields | optional fields | emitted by |
|---|---|---|---|
| `utterance` | `uid`, `speaker` (`user`/`persona`/`viewer:<id>`), `text`, `t_start`, `t_end` (VAD endpoint) | `barge_in` (bool) | sim user / ASR |
| `chain_annotation` | `uid` (of the utterance), `action` (`new`/`revision`/`withdrawal`), `chain_id` | `label` (task-local chain label for cross-condition pairing and for looking up the preregistered criteria, e.g. `c1`), `kind` (`action`/`content`/`multistep`; `correction` is treated as `action`), `intent`, `content_type` (`qa`/`explain`/`sing`), `prereg_duration_s`, `steps` (list or int), `checks`, `rubric` | sim user (script) or annotator |
| `lock` | `t`, `request` | `chain_ids`, `plan_version` | orchestrator (diagnostic; not needed for scoring) |
| `chunk_presented` | `request`, `chunk`, `t_start`, `t_end` | `frame_hash` | client presentation ack |
| `observation_end` | `t` (last presented media time of the session) | | runner |
| `verdict` | `source` (`adjudicated`/`human`/`judge`), `label` (`complied`/`not_complied`/`unknown`), and `chain_id` **or** `claim_id` | `revision`, `step` (multistep, 0-based), `request`, `chunk`, `t_first_compliant`, `t_evidence`, `t_review_start`, `t_review_end`, `claim_t` (claim-level verdict), `onset_reviewed`, `t_onset`, `annotators`, `reconciliation` (`agreement`/`arbitration`), `batch`, `item`, `criteria_sha256`, `qid` | judge / adjudication tool |
| `rating` | `annotator`, `chain_id`, `label` | `role` (`primary`/`arbiter`), `step`, `revision`, `claim_t`, the same time fields as a verdict, `onset_none`, `batch`, `item` | adjudication tool (one annotator's independent label; kept for agreement statistics, **never scored**) |
| `completion_claim` | `chain_id`, `t` | `step`, `claim_id`, `request`, `text` | orchestrator (persona says "done") |
| `refusal` | `chain_id`, `t` | `kind` (`refused` (default) / `degraded`), `reason` | compiler / safety filter |
| `capacity_skip` | `chain_id`, `t` | `revision`, `reason` | admission control |
| `speech_onset` | `t`, `on_topic` (`true`/`false`/`null`) | `source` (`script` (default) / `adjudicated` / `human`), `chain_id` (**required for the onset to count toward a chain**), `request` | runner (`script`) / adjudication tool (`adjudicated`) |
| `visual_ack` | `t`, `uid` (the utterance acknowledged) | `kind` (`reaction_clip`/`freeze`) | client |
| `playback_stop` | `t` | `reason` | client |
| `repair_assignment` | `chain_id`, `arm` (`forward_correction`/`repeat`), `failure_request` (k), `target_request` (j = earliest request with P_j ≥ E + C) | `step`, `E`, `C` | orchestrator (RQ2: arm randomised per eligible failure point, e.g. condition `A2-rq2`) |

## Contract the runner must satisfy

* **Judge verdicts** (`source: "judge"`) carry `revision` = the number of revisions of the
  chain's intent the judged request was planned under, and `step` for multistep. Each
  verdict is attached only to the chain the judged request served. Judge verdicts without
  `revision` are used only in diagnostic scoring.
* **`completion_claim.t`** is the presentation time of the chunk in which the claim line
  is heard (not the request start), with `step` when the claim is about one step. Claims
  are emitted for chains that are later withdrawn too.
* **`speech_onset`** from the runner has `source: "script"` and `on_topic: null`: the line
  was scripted for that chain and `t` is the energy-based audio onset in the presented
  chunk. Nobody has verified it is on topic, so it **never** passes the content onset
  gate or counts toward TFMR in primary scoring. Only `source: "adjudicated"` with
  `on_topic: true` does (diagnostic scoring also accepts `script` onsets as unverified).
* **`capacity_skip`** carries `chain_id`, `t` and `revision` when admission control
  displaces an open chain.
* **`observation_end`**: last presented media time of the session. Without it the scorer
  falls back to the end of the last `chunk_presented`.

## Time fields on verdicts

* `t_first_compliant`: presentation time of the **first frame judged compliant**. It defines
  TVC and the judged-compliance time of a multistep step. If it is missing, the scorer
  uses the `t_start` of `chunk_presented(request, chunk)`, then `t_evidence`. A
  `complied` verdict without any of these is malformed and stops scoring.
* `t_evidence`: presentation time of the **last** frame (or audio) needed for the verdict
  (E in §5.4). For content chains this is the **end of the response**, and it is the
  completion time.
* `not_complied` / `unknown` verdicts need no time. Without one they apply to the whole
  reviewed interval (`t_review_start`–`t_review_end`, recorded for every adjudicated label).
* **Revision binding:** a verdict with `revision` counts only if it equals the chain's final
  revision count. An adjudicated verdict without `revision` is taken to be on the final
  intent. A `complied` time earlier than the final clock origin is ignored.
* **Sources:** primary scoring uses `adjudicated` only. Diagnostic scoring uses the
  highest-preference source present per chain (`ScoringConfig.diagnostic_config(("human",
  "judge"))`, for example).

## Adjudication (`live_agent/eval/adjudicate.py`)

* `prepare` builds a blinded page (shuffled items, random ids, random media names) in the
  batch directory and writes the key (`item → log, chain, condition`) to
  `<batch>.key/key.json` or `--key`, **never inside the batch directory**.
* Items: one per effective chain (final intent; per step for multistep), plus one per
  completion claim the final-intent verdict cannot settle (a claim on a withdrawn chain,
  or one heard before the final revision), judged against what was requested when it was
  heard. Every item shows the preregistered criteria frozen from the task suite
  (`eval/tasks/e2_committed.jsonl`: action `checks`, content `rubric` and duration, each
  multistep step's `intent` and `checks`). An item without criteria is an error. Content
  items also ask for the on-topic speech onset (a time, or "no on-topic speech").
* `merge` takes **two** independent label files and an optional **arbiter** file. It
  validates every label (times inside the recording and not before the request; "done"
  needs its time; content needs an onset decision) and rejects the whole file on any
  error. It appends every label as a `rating` event. It appends one reconciled `verdict`
  per item/step only when the two raters agree (same label; times within `--tol`, default
  1 s; the later time is used) or the arbiter labelled it. It appends an adjudicated
  `speech_onset` when the reconciled onset has a time. Unresolved and missing items are
  written to `unresolved.json` next to the key. Re-running is idempotent per batch.

## Scoring rules (summary; all *proposed targets*, identical across conditions)

* **Chain.** `new` opens a chain. `revision` merges into it: the intent fields are
  replaced and the clock restarts at the revising utterance's `t_end`. `withdrawal`
  withdraws the chain, and a later `revision` reopens it. Each chain is scored once, on
  its final intent.
* **Effective chains** (proposal denominator) are all chains that do not end withdrawn.
  Capacity-skipped chains are included.
* **Precedence:** withdrawn → capacity-skipped (fail; the skip's `revision` must equal
  the final revision, or without `revision` it must be at or after the final origin) →
  refused/degraded (fail, at or after the final origin) → adjudication completeness →
  deadline rules → observation check.
* **Adjudication completeness (primary):** an attempted chain needs an adjudicated verdict
  bound to its final intent. Content also needs an onset decision (`onset_reviewed` or an
  adjudicated `speech_onset`). Multistep needs a verdict for every step up to the first
  one not done. Otherwise the outcome is `unadjudicated`, and the primary report refuses
  to run and lists the gaps. The same applies to claims that need claim-level adjudication.
* **Deadlines D:**
  * action: first judged-compliant frame ≤ 15 s;
  * content: adjudicated on-topic `speech_onset` ≤ 15 s **and** a `complied` rubric
    verdict with `t_evidence` ≤ 15 s + preregistered duration (qa 10, explain 30, sing 30,
    or `prereg_duration_s`);
  * multistep: step *i* complied ≤ 15 s after step *i−1*'s compliance (step 0: after the
    origin), with every step in order.
* **Observation:** a chain that did not succeed, whose failure rests on the *absence* of
  compliance up to a time later than `observation_end`, is `insufficient_observation`.
  It is excluded from the primary analysis, counted, and flagged for rerun.
* **Outcomes:** `success`, `late`, `never` (censored at D), `unknown` (a "cannot tell"
  verdict inside the window decided the failure: counted as a failure in the primary
  analysis and excluded in the sensitivity analysis), `onset_fail`, `rubric_fail`,
  `order_fail` (a step done only before its predecessor: a deterministic, competing
  failure, not censoring; left out of the time-to-success KM), `refused`, `degraded`,
  `capacity_skipped`, `withdrawn`, `unadjudicated`, `insufficient_observation`.
* **FCR** = false claims / all audible completion claims, **withdrawn chains included**. A
  claim is judged against the intent revision in force when it was heard. It is true only
  if a `complied` verdict bound to that revision, for the claimed `step` (or for every step
  when none is named), has its compliance time in [origin of that revision, `t` +
  `claim_grace_s` (default 0)]. A claim-level verdict (`claim_id`, or `chain_id` +
  `claim_t`) settles the claim directly, and `unknown` counts as false. **Claim coverage**
  is the share of primary chains with at least one claim; coverage among successful chains
  is also reported. Both get task-clustered bootstrap CIs.
* **Repair (RQ2):** the unit is the failure point (one `repair_assignment` each).
  Success means a `complied` verdict whose request (explicit `request`, else the presented
  chunk containing its compliance time) is `target_request`. The offset j−k is reported.
* **TVC** (action chains): first compliant frame − origin, censored at 15 s.
  **TFMR**: first accepted on-topic `speech_onset` − origin, censored at 15 s.
  **Visual-ack latency**: `visual_ack.t` minus the utterance's `t_end`, or its `t_start`
  for a barge-in.
  **Barge-in stop latency**: the first `playback_stop` at or after a barge-in
  utterance's `t_start`, minus that `t_start`.
* **Conditional success** = successes / served chains (primary chains that were not
  refused, degraded or skipped).
* **Comparisons** (`report.py`): preregistered families only. Primary: A2−A1 (H1a). H1c:
  A2 minus each of A2-noqc, A2-noledger, A2-nomanifest, A2-nocorrection. Holm is applied
  over the preregistered family size (a member not run counts as p = 1), with a decision
  column and a Bonferroni simultaneous CI. `--compare` only selects displayed rows. Pairs
  outside the families are exploratory: unadjusted, no decision.

## Minimal example

```jsonl
{"type":"session","schema_version":1,"session_id":"s1","condition":"A2","task_id":"E2-A01","seed":0,"mode":"simulation"}
{"type":"utterance","uid":"s1:u0","speaker":"user","text":"请喝口茶吧。","t_start":2.0,"t_end":3.1}
{"type":"chain_annotation","uid":"s1:u0","action":"new","chain_id":"s1:c1","label":"c1","kind":"action","intent":"端起茶杯喝一口茶"}
{"type":"visual_ack","t":3.5,"uid":"s1:u0"}
{"type":"chunk_presented","request":2,"chunk":0,"t_start":9.6,"t_end":11.0}
{"type":"verdict","chain_id":"s1:c1","source":"judge","label":"complied","revision":0,"request":2,"chunk":0,"t_evidence":11.0}
{"type":"completion_claim","chain_id":"s1:c1","t":12.0}
{"type":"observation_end","t":30.0}
{"type":"rating","annotator":"R1","role":"primary","chain_id":"s1:c1","label":"complied","t_first_compliant":9.8,"t_review_start":3.1,"t_review_end":20.0}
{"type":"rating","annotator":"R2","role":"primary","chain_id":"s1:c1","label":"complied","t_first_compliant":10.1,"t_review_start":3.1,"t_review_end":18.0}
{"type":"verdict","chain_id":"s1:c1","source":"adjudicated","label":"complied","revision":0,"t_first_compliant":10.1,"t_evidence":10.1,"annotators":["R1","R2"],"reconciliation":"agreement","t_review_start":3.1,"t_review_end":20.0}
```

===== FILE: live_agent/eval/schema.py =====
"""Session-log schema (JSONL) for E2 scoring. Human-readable spec: ``SCHEMA.md``.

One file = one session = one task x one seed x one condition. Line 1 is a ``session``
header; every other line is an event. All times are seconds on the shared presentation
timeline (the same clock as ``live_agent.types.now``), not wall-clock.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

# event type -> required fields (besides "type")
REQUIRED: dict[str, tuple[str, ...]] = {
    "session": ("session_id", "condition", "task_id", "seed"),
    "utterance": ("uid", "speaker", "text", "t_start", "t_end"),
    "chain_annotation": ("uid", "action", "chain_id"),
    "lock": ("t", "request"),
    "chunk_presented": ("request", "chunk", "t_start", "t_end"),
    "verdict": ("source", "label"),
    "completion_claim": ("chain_id", "t"),
    "refusal": ("chain_id", "t"),
    "capacity_skip": ("chain_id", "t"),
    "speech_onset": ("t", "on_topic"),
    "visual_ack": ("t", "uid"),
    "playback_stop": ("t",),
    "repair_assignment": ("chain_id", "arm", "failure_request", "target_request"),
    "observation_end": ("t",),
    # one annotator's raw, independent label (kept for agreement statistics; never scored)
    "rating": ("annotator", "chain_id", "label"),
}

ANNOTATION_ACTIONS = ("new", "revision", "withdrawal")
VERDICT_LABELS = ("complied", "not_complied", "unknown")
VERDICT_SOURCES = ("adjudicated", "human", "judge")
REFUSAL_KINDS = ("refused", "degraded")
REPAIR_ARMS = ("forward_correction", "repeat")
ONSET_SOURCES = ("script", "adjudicated", "human")
SESSION_MODES = ("simulation", "generator_path", "browser")


class SchemaError(ValueError):
    pass


@dataclass
class SessionLog:
    meta: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def session_id(self) -> str:
        return str(self.meta["session_id"])

    @property
    def condition(self) -> str:
        return str(self.meta["condition"])

    @property
    def task_id(self) -> str:
        return str(self.meta["task_id"])

    @property
    def seed(self) -> int:
        return int(self.meta["seed"])

    def of_type(self, *types: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["type"] in types]


def validate_event(ev: dict[str, Any]) -> None:
    typ = ev.get("type")
    if typ not in REQUIRED:
        raise SchemaError(f"unknown event type {typ!r}: {ev}")
    missing = [k for k in REQUIRED[typ] if k not in ev]
    if missing:
        raise SchemaError(f"{typ} event missing {missing}: {ev}")
    if typ == "chain_annotation" and ev["action"] not in ANNOTATION_ACTIONS:
        raise SchemaError(f"bad annotation action {ev['action']!r}")
    if typ == "verdict":
        if ev["label"] not in VERDICT_LABELS:
            raise SchemaError(f"bad verdict label {ev['label']!r}")
        if ev["source"] not in VERDICT_SOURCES:
            raise SchemaError(f"bad verdict source {ev['source']!r}")
        if "claim_id" not in ev and "chain_id" not in ev:
            raise SchemaError(f"verdict needs chain_id or claim_id: {ev}")
    if typ == "refusal" and ev.get("kind", "refused") not in REFUSAL_KINDS:
        raise SchemaError(f"bad refusal kind {ev.get('kind')!r}")
    if typ == "repair_assignment" and ev["arm"] not in REPAIR_ARMS:
        raise SchemaError(f"bad repair arm {ev['arm']!r}")
    if typ == "rating" and ev["label"] not in VERDICT_LABELS:
        raise SchemaError(f"bad rating label {ev['label']!r}")
    if typ == "speech_onset":
        if ev.get("source", "script") not in ONSET_SOURCES:
            raise SchemaError(f"bad speech_onset source {ev.get('source')!r}")
        if ev["on_topic"] not in (True, False, None):
            raise SchemaError(f"speech_onset on_topic must be true/false/null: {ev}")
    if typ == "session" and ev.get("mode") is not None and ev["mode"] not in SESSION_MODES:
        raise SchemaError(f"bad session mode {ev['mode']!r} (expected one of {SESSION_MODES})")


def _sort_key(ev: dict[str, Any]) -> float:
    for k in ("t", "t_end", "t_evidence", "t_start"):
        if k in ev and ev[k] is not None:
            return float(ev[k])
    return float("-inf")


def parse_session(records: Iterable[dict[str, Any]]) -> SessionLog:
    records = list(records)
    if not records or records[0].get("type") != "session":
        raise SchemaError("first record must be a 'session' header")
    meta = dict(records[0])
    validate_event(meta)
    events = []
    for ev in records[1:]:
        validate_event(ev)
        events.append(dict(ev))
    events.sort(key=_sort_key)  # stable: equal times keep file order
    return SessionLog(meta=meta, events=events)


def load_session(path: str | Path) -> SessionLog:
    with open(path, encoding="utf-8") as f:
        recs = [json.loads(line) for line in f if line.strip()]
    return parse_session(recs)


class SessionLogWriter:
    """Append-only JSONL writer; the orchestrator and the simulated user share one."""

    def __init__(self, path: str | Path, **meta: Any):
        self.path = Path(path)
        header = {"type": "session", "schema_version": SCHEMA_VERSION, **meta}
        validate_event(header)
        self._f = open(self.path, "w", encoding="utf-8")
        self.write(header)

    def write(self, ev: dict[str, Any]) -> None:
        validate_event(ev)
        self._f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> SessionLogWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

===== FILE: live_agent/eval/scoring.py =====
"""E2 scoring: intent chains, per-task deadlines, outcome rules (proposal v2.11 §7.2, §8).

Rules implemented (all *proposed targets*, preregistered, identical across conditions):

* Intent chain: opened by a ``new`` annotation; ``revision`` merges into the same chain,
  replaces its intent fields and restarts the clock; ``withdrawal`` withdraws it (a later
  revision re-opens it). Scored once, on the final intent.
* Clock origin: ``t_end`` (VAD endpoint) of the opening or latest revising utterance.
* Primary outcome = blinded, reconciled human adjudication (D-014). Default scoring uses
  ``adjudicated`` verdicts only; a chain the system attempted but that has no complete
  adjudication is ``unadjudicated`` and the primary report refuses to run. Online-judge
  scoring is a labelled diagnostic (``ScoringConfig.diagnostic_config()``).
* Verdicts are bound to the intent revision they judged (``revision``); a mismatch is
  ignored. Judge verdicts without ``revision`` are used only in diagnostic mode.
* Effective chains (proposal denominator): final intent not withdrawn; capacity-skipped
  chains are included and count as failures. Chains whose deadline window was not fully
  observed (``observation_end``) and that did not succeed inside it are
  ``insufficient_observation``: excluded from the primary analysis, counted, flagged for rerun.
* Deadlines D: action 15 s -> first judged-compliant presented frame; content: on-topic
  speech onset <= 15 s (adjudicated onset only in primary mode) AND complete response
  (rubric pass) <= 15 s + preregistered duration (qa 10, explain 30, sing 30); multistep:
  15 s per step measured from the previous step's judged-compliance time, all steps in
  order; correction = restart clock at revision.
* Outcomes: refused/degraded -> fail; capacity skip (of the final revision) -> fail (in
  denominator); withdrawn -> excluded, counted; "cannot tell" -> fail in primary, excluded
  in sensitivity analysis; never complied -> censored at D; order_fail -> a deterministic
  failure (competing event, not censoring).
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any

from live_agent.eval.schema import SessionLog
from live_agent.types import TaskKind

CONTENT_DURATION_S = {"qa": 10.0, "explain": 30.0, "sing": 30.0}  # proposed target (§7.2)
PRIMARY_SOURCES: tuple[str, ...] = ("adjudicated",)
_EPS = 1e-6


@dataclass(frozen=True)
class ScoringConfig:
    step_deadline_s: float = 15.0  # action / per multistep step / correction (proposed target)
    onset_deadline_s: float = 15.0  # content onset (proposed target)
    content_duration_s: dict[str, float] = field(default_factory=lambda: dict(CONTENT_DURATION_S))
    # Primary: adjudicated verdicts only. Anything else must be declared diagnostic.
    source_preference: tuple[str, ...] = PRIMARY_SOURCES
    # speech_onset sources accepted for the content onset gate / TFMR. "script" onsets
    # (on_topic null: the line was scripted, nobody verified it) only in diagnostic mode.
    onset_sources: tuple[str, ...] = PRIMARY_SOURCES
    diagnostic: bool = False
    claim_grace_s: float = 0.0  # compliance evidence may trail a claim by at most this
    tfmr_horizon_s: float = 15.0  # TFMR censoring horizon

    def __post_init__(self) -> None:
        if not self.diagnostic and (
            tuple(self.source_preference) != PRIMARY_SOURCES
            or tuple(self.onset_sources) != PRIMARY_SOURCES
        ):
            raise ValueError(
                "the primary outcome uses adjudicated verdicts and onsets only (D-014); "
                "other sources require diagnostic=True (see ScoringConfig.diagnostic_config())"
            )

    @classmethod
    def diagnostic_config(cls, sources: tuple[str, ...] = ("judge",), **kw: Any) -> ScoringConfig:
        """Diagnostic scoring (e.g. of the online judge): not a result. Scripted speech
        onsets are accepted as unverified."""
        return cls(source_preference=tuple(sources),
                   onset_sources=("adjudicated", "human", "script"), diagnostic=True, **kw)


class Outcome(str, enum.Enum):
    SUCCESS = "success"
    LATE = "late"  # complied, but after the deadline
    NEVER = "never"  # no compliant verdict: censored at D
    UNKNOWN = "unknown"  # "cannot tell" decided the failure
    ONSET_FAIL = "onset_fail"  # content: no on-topic speech onset within 15 s
    RUBRIC_FAIL = "rubric_fail"  # content: response judged not meeting rubric
    ORDER_FAIL = "order_fail"  # multistep: steps complied out of order (competing failure)
    REFUSED = "refused"
    DEGRADED = "degraded"
    CAPACITY_SKIPPED = "capacity_skipped"
    WITHDRAWN = "withdrawn"
    UNADJUDICATED = "unadjudicated"  # primary mode: adjudication missing (report rejects)
    INSUFFICIENT_OBSERVATION = "insufficient_observation"  # window not observed: rerun


NOT_PRIMARY = (Outcome.WITHDRAWN, Outcome.UNADJUDICATED, Outcome.INSUFFICIENT_OBSERVATION)


class IncompleteAdjudicationError(ValueError):
    """The primary analysis needs a reconciled adjudicated verdict for every chain and claim."""


# --------------------------------------------------------------------------- chains


@dataclass
class Chain:
    chain_id: str
    label: str  # task-local label used to pair chains across conditions
    kind: TaskKind
    opened_uid: str
    origins: list[float]  # clock origins in order: opening, then each revision
    intent: str = ""
    content_type: str | None = None
    prereg_duration_s: float | None = None
    n_steps: int = 1
    revisions: list[str] = field(default_factory=list)
    withdrawn: bool = False
    withdrawn_t: float | None = None

    @property
    def clock_origin(self) -> float:
        return self.origins[-1]

    def revision_at(self, t: float) -> int:
        """Index of the intent revision in force at time t (0 = the opening intent)."""
        r = 0
        for i, o in enumerate(self.origins):
            if o <= t:
                r = i
        return r

    def origin_at(self, t: float) -> float:
        """Clock origin in force at time t (for judging claims made before a revision)."""
        return self.origins[self.revision_at(t)]


def claim_needs_direct_adjudication(ch: Chain, t: float) -> bool:
    """A claim is settled by the chain's final-intent verdicts only when the chain ends
    effective and the claim was heard under the final intent; otherwise it needs its own
    (claim-level) adjudication against what was requested at claim time."""
    return ch.withdrawn or ch.revision_at(t) != len(ch.revisions)


def _kind(v: Any) -> TaskKind:
    k = TaskKind(v) if v is not None else TaskKind.ACTION
    return TaskKind.ACTION if k == TaskKind.CORRECTION else k


def _apply_intent(ch: Chain, ann: dict[str, Any]) -> None:
    if "kind" in ann:
        ch.kind = _kind(ann["kind"])
    if "intent" in ann:
        ch.intent = ann["intent"]
    if "content_type" in ann:
        ch.content_type = ann["content_type"]
    if "prereg_duration_s" in ann:
        ch.prereg_duration_s = ann["prereg_duration_s"]
    if "steps" in ann:
        ch.n_steps = len(ann["steps"]) if isinstance(ann["steps"], list) else int(ann["steps"])
    elif "kind" in ann and ch.kind != TaskKind.MULTISTEP:
        ch.n_steps = 1


def build_chains(session: SessionLog) -> dict[str, Chain]:
    utts = {e["uid"]: e for e in session.of_type("utterance")}
    anns = sorted(session.of_type("chain_annotation"), key=lambda a: utts[a["uid"]]["t_end"])
    chains: dict[str, Chain] = {}
    for a in anns:
        u = utts.get(a["uid"])
        if u is None:
            raise ValueError(f"annotation refers to unknown utterance {a['uid']}")
        cid = a["chain_id"]
        if a["action"] == "new":
            if cid in chains:
                raise ValueError(f"chain {cid} opened twice")
            ch = Chain(cid, a.get("label", cid), _kind(a.get("kind")), a["uid"], [float(u["t_end"])])
            _apply_intent(ch, a)
            chains[cid] = ch
            continue
        if cid not in chains:
            raise ValueError(f"{a['action']} of unknown chain {cid}")
        ch = chains[cid]
        if a["action"] == "revision":
            ch.revisions.append(a["uid"])
            ch.origins.append(float(u["t_end"]))
            ch.withdrawn, ch.withdrawn_t = False, None
            _apply_intent(ch, a)
        else:  # withdrawal
            ch.withdrawn, ch.withdrawn_t = True, float(u["t_end"])
    return chains


# --------------------------------------------------------------------------- outcomes


@dataclass
class ChainOutcome:
    session_id: str
    condition: str
    task_id: str
    seed: int
    chain_id: str
    label: str
    kind: str
    content_type: str | None
    outcome: Outcome
    clock_origin: float
    n_revisions: int
    deadline_s: float  # D for this chain
    time_to_success: float  # min(time, censor point); for KM (not meaningful for order_fail)
    success_event: bool
    competing_failure: bool = False  # order_fail: deterministic failure, not right-censoring
    tvc: float | None = None  # action chains: first judged-compliant frame - origin (censored at D)
    tvc_event: bool = False
    onset_s: float | None = None  # content: first on-topic speech onset - origin
    onset_ok: bool | None = None
    tfmr: float | None = None
    tfmr_event: bool = False
    steps_complied: int = 0
    n_claims: int = 0  # audible completion claims (all, incl. withdrawn chains)
    n_false_claims: int = 0
    n_claims_unadjudicated: int = 0  # primary mode: claims without a usable adjudication
    repairs: list[dict[str, Any]] = field(default_factory=list)  # one per RQ2 failure point
    missing: str = ""  # what adjudication is missing / why observation is insufficient

    @property
    def success(self) -> bool:
        return self.outcome == Outcome.SUCCESS

    @property
    def effective(self) -> bool:
        """Proposal definition: final intent not withdrawn."""
        return self.outcome != Outcome.WITHDRAWN

    @property
    def in_primary(self) -> bool:
        """Counted in the primary denominator (effective, adjudicated, observed)."""
        return self.outcome not in NOT_PRIMARY

    @property
    def served(self) -> bool:
        """Attempted by the system (not refused, degraded, or capacity-skipped)."""
        return self.in_primary and self.outcome not in (
            Outcome.REFUSED,
            Outcome.DEGRADED,
            Outcome.CAPACITY_SKIPPED,
        )


@dataclass
class SessionScore:
    session_id: str
    condition: str
    task_id: str
    seed: int
    chains: list[ChainOutcome]
    visual_ack_s: list[float]
    barge_in_stop_s: list[float]
    barge_ins_without_stop: int
    diagnostic: bool = False
    sources: tuple[str, ...] = PRIMARY_SOURCES
    observation_end: float | None = None


def _vtime(v: dict[str, Any], chunks: dict[tuple[int, int], dict[str, Any]]) -> float | None:
    """Presentation time of the first frame judged compliant (for a negative label: the
    evidence time if any, else None = the label covers its whole reviewed interval)."""
    if v.get("t_first_compliant") is not None:
        return float(v["t_first_compliant"])
    key = (v.get("request"), v.get("chunk"))
    if key in chunks:
        return float(chunks[key]["t_start"])
    if v.get("t_evidence") is not None:
        return float(v["t_evidence"])
    if v["label"] == "complied":
        raise ValueError(f"'complied' verdict without a compliance time: {v}")
    return None


def _t_end(v: dict[str, Any]) -> float | None:
    """Content completion time (end of the response) of a verdict."""
    if v.get("t_evidence") is not None:
        return float(v["t_evidence"])
    return v["_tc"]


def _pick_source(vs: list[dict[str, Any]], pref: tuple[str, ...]) -> list[dict[str, Any]]:
    for s in pref:
        sel = [v for v in vs if v["source"] == s]
        if sel:
            return sel
    return []


def _bound(v: dict[str, Any], rev: int, cfg: ScoringConfig) -> bool:
    """Is verdict v about intent revision ``rev``? Adjudicated/human verdicts without a
    ``revision`` are made on the final intent (the caller passes the final revision)."""
    if v.get("revision") is not None:
        return int(v["revision"]) == rev
    return v["source"] != "judge" or cfg.diagnostic  # unbound judge verdicts: diagnostic only


def _onset_accepted(e: dict[str, Any], cfg: ScoringConfig) -> bool:
    src = e.get("source", "script")  # legacy onsets without source were scripted, unverified
    if src not in cfg.onset_sources:
        return False
    if e.get("on_topic") is True:
        return True
    return cfg.diagnostic and src == "script" and e.get("on_topic") is None


def _content_deadline(ch: Chain, cfg: ScoringConfig) -> float:
    dur = ch.prereg_duration_s
    if dur is None:
        dur = cfg.content_duration_s[ch.content_type or "qa"]
    return cfg.onset_deadline_s + dur


def _adjudication_gap(ch: Chain, vs: list[dict[str, Any]], adj_onsets: list[dict[str, Any]]) -> str:
    """'' when the final intent is fully adjudicated, else what is missing."""
    if not vs:
        return "no adjudicated verdict for the final intent"
    if ch.kind == TaskKind.CONTENT:
        if not (any(v.get("onset_reviewed") for v in vs) or adj_onsets):
            return "content: speech onset not adjudicated"
        return ""
    if ch.kind == TaskKind.MULTISTEP:
        for i in range(ch.n_steps):
            sv = [v for v in vs if int(v.get("step", 0)) == i]
            if not sv:
                return f"multistep: step {i} not adjudicated"
            if not any(v["label"] == "complied" for v in sv):
                return ""  # later steps are moot
    return ""


def _score_chain(
    ch: Chain,
    vs: list[dict[str, Any]],
    onsets: list[dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[Outcome, dict[str, Any]]:
    """Deadline rules for a non-withdrawn, non-skipped, non-refused chain. ``vs`` are the
    verdicts bound to the final revision, each with ``_tc`` (None for untimed negatives).
    ``info['needs_until']`` = the session time through which absence of compliance had to
    be observed for a failure outcome to be certain."""
    o = ch.clock_origin
    vs = [v for v in vs if v["_tc"] is None or v["_tc"] >= o - _EPS]
    info: dict[str, Any] = {}
    D = cfg.step_deadline_s

    if ch.kind == TaskKind.CONTENT:
        D_c = _content_deadline(ch, cfg)
        info["deadline"] = D_c
        on = [float(e["t"]) - o for e in onsets if float(e["t"]) >= o]
        onset = min(on) if on else None
        info["onset_s"] = onset
        info["onset_ok"] = onset is not None and onset <= cfg.onset_deadline_s
        # rubric verdicts: t_evidence = presentation time of the end of the response
        done = sorted(_t_end(v) - o for v in vs if v["label"] == "complied")
        comp = done[0] if done else None
        info["t_complete"] = comp
        in_time = [v for v in vs if v["_tc"] is None or _t_end(v) - o <= D_c]
        if not info["onset_ok"]:
            if onset is None:
                info["needs_until"] = o + cfg.onset_deadline_s
            return Outcome.ONSET_FAIL, info
        if comp is not None and comp <= D_c:
            return Outcome.SUCCESS, info
        if comp is not None:
            return Outcome.LATE, info
        info["needs_until"] = o + D_c
        if any(v["label"] == "unknown" for v in in_time):
            return Outcome.UNKNOWN, info
        if any(v["label"] == "not_complied" for v in in_time):
            return Outcome.RUBRIC_FAIL, info
        return Outcome.NEVER, info

    # action (incl. corrections) and multistep: per-step 15 s from previous compliance
    n = ch.n_steps if ch.kind == TaskKind.MULTISTEP else 1
    prev = o
    done_steps = 0
    for i in range(n):
        step_vs = [v for v in vs if int(v.get("step", 0)) == i]
        ok = sorted(v["_tc"] for v in step_vs if v["label"] == "complied" and v["_tc"] >= prev - _EPS)
        info["deadline"] = prev - o + D  # censor point if we stop here
        if not ok:
            window = [v for v in step_vs if v["_tc"] is None or prev <= v["_tc"] <= prev + D]
            if any(v["label"] == "complied" and v["_tc"] < prev for v in step_vs):
                out = Outcome.ORDER_FAIL  # step done only before its predecessor: deterministic
            else:
                info["needs_until"] = prev + D
                out = Outcome.UNKNOWN if any(v["label"] == "unknown" for v in window) else Outcome.NEVER
            info["steps_complied"] = done_steps
            return out, info
        t_ok = ok[0]
        if i == 0 and n == 1:
            info["tvc"] = t_ok - o
        if t_ok - prev > D:
            info["steps_complied"] = done_steps
            info["t_late"] = t_ok - o
            return Outcome.LATE, info
        prev = t_ok
        done_steps += 1
    info["steps_complied"] = done_steps
    info["t_complete"] = prev - o
    info["deadline"] = D * n
    return Outcome.SUCCESS, info


def _claim_key(chain_id: str, t: float) -> tuple[str, float]:
    return (chain_id, round(float(t), 3))


def _claims(
    ch: Chain,
    claims: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    direct: dict[Any, list[dict[str, Any]]],
    chunks: dict[tuple[int, int], dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[int, int, int]:
    """Return (n_claims, n_false, n_unadjudicated) over every audible completion claim on
    the chain, withdrawn chains included. A claim is judged against the intent revision in
    force when it was heard: it is true only if a ``complied`` verdict bound to that
    revision (for the claimed step, or for every step when no step is named) has its
    compliance time in [origin of that revision, t_claim + grace]. A claim-level verdict
    (``claim_id``, or ``chain_id`` + ``claim_t``) settles the claim directly; ``unknown``
    counts as false. In primary mode a claim that needs claim-level adjudication (withdrawn
    chain, or heard before the final revision) and has none is unadjudicated."""
    n_false = n_unadj = 0
    n_rev = len(ch.revisions)
    has_chain_adj = any(v["source"] in cfg.source_preference for v in verdicts)
    for c in claims:
        t = float(c["t"])
        dv = direct.get(("id", c.get("claim_id"))) if c.get("claim_id") is not None else None
        dv = dv or direct.get(_claim_key(ch.chain_id, t))
        dv = _pick_source(dv or [], cfg.source_preference)
        if dv:
            n_false += int(dv[-1]["label"] != "complied")
            continue
        if not cfg.diagnostic and (claim_needs_direct_adjudication(ch, t) or not has_chain_adj):
            n_unadj += 1
            continue
        r = ch.revision_at(t)
        lo, hi = ch.origins[r], t + cfg.claim_grace_s
        steps = [int(c["step"])] if c.get("step") is not None else list(range(ch.n_steps))
        ok = True
        for s in steps:
            hit = False
            for v in verdicts:
                if v["label"] != "complied" or int(v.get("step", 0)) != s:
                    continue
                vr = v.get("revision")
                if vr is None and v["source"] != "judge":
                    vr = n_rev  # adjudicated on the final intent
                if vr is not None and int(vr) != r:
                    continue
                tc = _vtime(v, chunks)
                if tc is not None and lo - _EPS <= tc <= hi + _EPS:
                    hit = True
                    break
            ok = ok and hit
        n_false += int(not ok)
    return len(claims), n_false, n_unadj


def _request_at(t: float, chunks: dict[tuple[int, int], dict[str, Any]]) -> int | None:
    for (k, _), c in chunks.items():
        if float(c["t_start"]) - _EPS <= t < float(c["t_end"]):
            return k
    return None


def observation_end(session: SessionLog) -> float | None:
    """Last presented media time: the ``observation_end`` event, else the end of the last
    presented chunk, else None (hand-built logs without media: no check)."""
    ends = [float(e["t"]) for e in session.of_type("observation_end")]
    if ends:
        return max(ends)
    ch = [float(e["t_end"]) for e in session.of_type("chunk_presented")]
    return max(ch) if ch else None


def score_session(session: SessionLog, cfg: ScoringConfig | None = None) -> SessionScore:
    cfg = cfg or ScoringConfig()
    chains = build_chains(session)
    chunks = {(int(e["request"]), int(e["chunk"])): e for e in session.of_type("chunk_presented")}
    obs_end = observation_end(session)

    by_chain: dict[str, dict[str, list[dict[str, Any]]]] = {c: {} for c in chains}

    def put(cid: str | None, key: str, ev: dict[str, Any]) -> None:
        if cid in by_chain:
            by_chain[cid].setdefault(key, []).append(ev)

    direct: dict[Any, list[dict[str, Any]]] = {}
    for e in session.events:
        t = e["type"]
        if t == "verdict":
            if e.get("claim_id") is not None:
                direct.setdefault(("id", e["claim_id"]), []).append(e)
            elif e.get("claim_t") is not None:
                direct.setdefault(_claim_key(e["chain_id"], e["claim_t"]), []).append(e)
            else:
                put(e["chain_id"], "verdict", e)
        elif t in ("completion_claim", "refusal", "capacity_skip", "repair_assignment") or (
            t == "speech_onset" and e.get("chain_id") is not None
        ):
            put(e["chain_id"], t, e)

    out: list[ChainOutcome] = []
    for cid, ch in chains.items():
        ev = by_chain[cid]
        o = ch.clock_origin
        n_rev = len(ch.revisions)
        all_v = _pick_source(ev.get("verdict", []), cfg.source_preference)
        vs = [dict(v, _tc=_vtime(v, chunks)) for v in all_v if _bound(v, n_rev, cfg)]
        onsets = [e for e in ev.get("speech_onset", []) if _onset_accepted(e, cfg)]
        adj_onsets = [e for e in onsets if e.get("source") == "adjudicated" and float(e["t"]) >= o]
        skips = [
            e for e in ev.get("capacity_skip", [])
            if (int(e["revision"]) == n_rev if e.get("revision") is not None else e["t"] >= o)
        ]
        refusals = [e for e in ev.get("refusal", []) if e["t"] >= o]

        info: dict[str, Any] = {}
        missing = ""
        if ch.withdrawn:
            outcome = Outcome.WITHDRAWN
        elif skips:
            outcome = Outcome.CAPACITY_SKIPPED
        elif refusals:
            kinds = {e.get("kind", "refused") for e in refusals}
            outcome = Outcome.REFUSED if "refused" in kinds else Outcome.DEGRADED
        else:
            gap = "" if cfg.diagnostic else _adjudication_gap(ch, vs, adj_onsets)
            if gap:
                outcome, missing = Outcome.UNADJUDICATED, gap
            else:
                outcome, info = _score_chain(ch, vs, onsets, cfg)
                need = info.get("needs_until")
                if need is not None and obs_end is not None and need > obs_end + _EPS:
                    missing = f"observed to {obs_end:.2f} s, window needs {need:.2f} s ({outcome.value})"
                    outcome = Outcome.INSUFFICIENT_OBSERVATION

        if ch.kind == TaskKind.CONTENT:
            D = _content_deadline(ch, cfg)
        elif ch.kind == TaskKind.MULTISTEP:
            D = cfg.step_deadline_s * ch.n_steps
        else:
            D = cfg.step_deadline_s
        success = outcome == Outcome.SUCCESS
        if success:
            tts = float(info.get("t_complete", info.get("tvc", 0.0)))
        else:
            tts = float(info.get("deadline", D))  # censored where failure became certain

        rec = ChainOutcome(
            session_id=session.session_id,
            condition=session.condition,
            task_id=session.task_id,
            seed=session.seed,
            chain_id=cid,
            label=ch.label,
            kind=ch.kind.value,
            content_type=ch.content_type,
            outcome=outcome,
            clock_origin=o,
            n_revisions=n_rev,
            deadline_s=D,
            time_to_success=tts,
            success_event=success,
            competing_failure=outcome == Outcome.ORDER_FAIL,
            steps_complied=int(info.get("steps_complied", 0)),
            missing=missing,
        )
        if rec.in_primary and ch.kind == TaskKind.ACTION:
            if info.get("tvc") is not None and info["tvc"] <= D:
                rec.tvc, rec.tvc_event = info["tvc"], True
            else:
                rec.tvc, rec.tvc_event = D, False  # censored at D
        if rec.in_primary and ch.kind == TaskKind.CONTENT:
            rec.onset_s = info.get("onset_s")
            rec.onset_ok = bool(info.get("onset_ok", False))
        if rec.in_primary:
            on = [float(e["t"]) - o for e in onsets if float(e["t"]) >= o]
            first = min(on) if on else None
            if first is not None and first <= cfg.tfmr_horizon_s:
                rec.tfmr, rec.tfmr_event = first, True
            else:
                rec.tfmr, rec.tfmr_event = cfg.tfmr_horizon_s, False
        # every audible completion claim, withdrawn chains included
        rec.n_claims, rec.n_false_claims, rec.n_claims_unadjudicated = _claims(
            ch, ev.get("completion_claim", []), all_v, direct, chunks, cfg
        )
        for r in ev.get("repair_assignment", []):  # RQ2: one record per failure point
            tgt = int(r["target_request"]) if r.get("target_request") is not None else None
            step = r.get("step")

            def req(v: dict[str, Any]) -> int | None:
                if v.get("request") is not None:
                    return int(v["request"])
                return _request_at(v["_tc"], chunks) if v["_tc"] is not None else None

            rec.repairs.append({
                "arm": r["arm"],
                "failure_request": int(r["failure_request"]),
                "target_request": tgt,
                "step": step,
                "offset": (tgt - int(r["failure_request"])) if tgt is not None else None,
                "success": tgt is not None and any(
                    v["label"] == "complied" and req(v) == tgt
                    and (step is None or int(v.get("step", 0)) == int(step))
                    for v in vs
                ),
            })
        out.append(rec)

    # latencies
    utts = {e["uid"]: e for e in session.of_type("utterance")}
    acks = []
    for e in session.of_type("visual_ack"):
        u = utts.get(e["uid"])
        if u is None:
            continue
        ref = u["t_start"] if u.get("barge_in") else u["t_end"]
        acks.append(float(e["t"]) - float(ref))
    stops = sorted(float(e["t"]) for e in session.of_type("playback_stop"))
    barge, missing_stop = [], 0
    for u in utts.values():
        if not u.get("barge_in"):
            continue
        after = [s for s in stops if s >= float(u["t_start"])]
        if after:
            barge.append(after[0] - float(u["t_start"]))
        else:
            missing_stop += 1

    return SessionScore(
        session_id=session.session_id,
        condition=session.condition,
        task_id=session.task_id,
        seed=session.seed,
        chains=out,
        visual_ack_s=acks,
        barge_in_stop_s=barge,
        barge_ins_without_stop=missing_stop,
        diagnostic=cfg.diagnostic,
        sources=tuple(cfg.source_preference),
        observation_end=obs_end,
    )


def adjudication_gaps(sessions: list[SessionScore]) -> list[str]:
    """Human-readable list of what blocks the primary analysis (empty = complete)."""
    gaps = []
    for s in sessions:
        for c in s.chains:
            if c.outcome == Outcome.UNADJUDICATED:
                gaps.append(f"{s.session_id} {c.chain_id}: {c.missing}")
            if c.n_claims_unadjudicated:
                gaps.append(f"{s.session_id} {c.chain_id}: {c.n_claims_unadjudicated} completion "
                            "claim(s) need claim-level adjudication")
    return gaps


def require_complete(sessions: list[SessionScore]) -> None:
    """Raise unless every chain and claim needed by the primary analysis is adjudicated."""
    if any(s.diagnostic for s in sessions):
        return
    gaps = adjudication_gaps(sessions)
    if gaps:
        raise IncompleteAdjudicationError(
            f"{len(gaps)} adjudication gap(s); the primary report needs a reconciled "
            "adjudicated verdict for every effective chain and claim:\n  " + "\n  ".join(gaps)
        )


# --------------------------------------------------------------------------- aggregation


def _rate(k: int, n: int) -> float:
    return k / n if n else math.nan


def summarize(chains: list[ChainOutcome]) -> dict[str, Any]:
    """Point estimates for one condition (CIs are added in report.py). The primary
    denominator excludes withdrawn, unadjudicated and insufficiently observed chains (the
    last two are counted separately). FCR counts every claim, withdrawn chains included."""
    eff = [c for c in chains if c.in_primary]
    n = len(eff)
    succ = sum(c.success for c in eff)
    skipped = sum(c.outcome == Outcome.CAPACITY_SKIPPED for c in eff)
    refused = sum(c.outcome in (Outcome.REFUSED, Outcome.DEGRADED) for c in eff)
    unknown = sum(c.outcome == Outcome.UNKNOWN for c in eff)
    served = [c for c in eff if c.served]
    content = [c for c in eff if c.kind == TaskKind.CONTENT.value]
    claims = sum(c.n_claims - c.n_claims_unadjudicated for c in chains)
    false_claims = sum(c.n_false_claims for c in chains)
    reps = [r for c in eff for r in c.repairs]
    return {
        "n_effective": n,
        "n_success": succ,
        "success_rate": _rate(succ, n),
        "n_withdrawn": sum(c.outcome == Outcome.WITHDRAWN for c in chains),
        "n_insufficient_observation": sum(c.outcome == Outcome.INSUFFICIENT_OBSERVATION for c in chains),
        "n_unadjudicated": sum(c.outcome == Outcome.UNADJUDICATED for c in chains),
        "capacity_skip_rate": _rate(skipped, n),
        "n_capacity_skipped": skipped,
        "refusal_degradation_rate": _rate(refused, n),
        "n_refused_degraded": refused,
        "n_unknown": unknown,
        "success_rate_excl_unknown": _rate(succ, n - unknown),  # sensitivity analysis
        "conditional_success_rate": _rate(sum(c.success for c in served), len(served)),
        "n_served": len(served),
        "content_onset_rate": _rate(sum(bool(c.onset_ok) for c in content), len(content)),
        "n_content": len(content),
        "n_claims": claims,
        "n_false_claims": false_claims,
        "n_claims_unadjudicated": sum(c.n_claims_unadjudicated for c in chains),
        "fcr": _rate(false_claims, claims),
        "claim_coverage": _rate(sum(c.n_claims > 0 for c in eff), n),
        "claim_coverage_of_successes": _rate(
            sum(c.n_claims > 0 for c in eff if c.success), succ
        ),
        "repair": {
            arm: {
                "n": sum(r["arm"] == arm for r in reps),
                "k": sum(bool(r["success"]) for r in reps if r["arm"] == arm),
                "offsets": sorted(r["offset"] for r in reps if r["arm"] == arm and r["offset"] is not None),
            }
            for arm in sorted({r["arm"] for r in reps})
        },
        "outcomes": {o.value: sum(c.outcome == o for c in chains) for o in Outcome},
    }

===== FILE: live_agent/eval/stats.py =====
"""Statistics for E1-E6 (proposal v2.11 §7.7): binomial intervals, Kaplan-Meier with
right-censoring, clustered bootstrap (cluster = task), Holm, Cohen's kappa,
non-inferiority, and simulation-based power for a paired clustered binary outcome."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import optimize, stats

# --------------------------------------------------------------------------- binomial


def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Two-sided Wilson score interval."""
    if n == 0:
        return (math.nan, math.nan)
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return (float(lo), float(hi))


def wilson_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided upper Wilson bound at level ``conf``."""
    return wilson(k, n, 2 * conf - 1)[1]


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson interval."""
    if n == 0:
        return (math.nan, math.nan)
    a = 1 - conf
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return (lo, hi)


def clopper_pearson_upper(k: int, n: int, conf: float = 0.95) -> float:
    """Exact one-sided upper bound (RQ5 leakage: 0/300 -> 0.00994)."""
    if n == 0:
        return math.nan
    return 1.0 if k == n else float(stats.beta.ppf(conf, k + 1, n - k))


# --------------------------------------------------------------------------- Kaplan-Meier


@dataclass
class KMResult:
    times: np.ndarray  # distinct event times
    survival: np.ndarray  # S(t) just after each event time
    at_risk: np.ndarray
    events: np.ndarray
    greenwood_var: np.ndarray

    def s_at(self, t: float) -> float:
        idx = np.searchsorted(self.times, t, side="right") - 1
        return 1.0 if idx < 0 else float(self.survival[idx])

    @property
    def median(self) -> float | None:
        """Smallest t with S(t) <= 0.5; None if not reached (report as '> horizon')."""
        hit = np.nonzero(self.survival <= 0.5 + 1e-12)[0]
        return float(self.times[hit[0]]) if hit.size else None

    def quantile(self, q: float) -> float | None:
        """Time by which a fraction q has had the event (e.g. q=0.95 -> p95)."""
        hit = np.nonzero(1 - self.survival >= q - 1e-12)[0]
        return float(self.times[hit[0]]) if hit.size else None

    def rmst(self, horizon: float) -> float:
        """Restricted mean time to event: integral of S(t) over [0, horizon]."""
        grid = np.concatenate([[0.0], self.times[self.times < horizon], [horizon]])
        s = np.concatenate([[1.0], self.survival[self.times < horizon]])
        return float(np.sum(np.diff(grid) * s))


def kaplan_meier(times: Sequence[float], events: Sequence[bool | int]) -> KMResult:
    """Product-limit estimator; ties: events before censorings at the same time."""
    t = np.asarray(times, dtype=float)
    e = np.asarray(events, dtype=bool)
    if t.size == 0:
        z = np.zeros(0)
        return KMResult(z, z, z, z, z)
    ut = np.unique(t[e])
    s, var_sum = 1.0, 0.0
    surv, risk, ev, gw = [], [], [], []
    for u in ut:
        n = int(np.sum(t >= u))
        d = int(np.sum((t == u) & e))
        s *= 1 - d / n
        if n > d:
            var_sum += d / (n * (n - d))
        surv.append(s)
        risk.append(n)
        ev.append(d)
        gw.append(s * s * var_sum)
    return KMResult(ut, np.array(surv), np.array(risk), np.array(ev), np.array(gw))


# --------------------------------------------------------------------------- bootstrap


def _cluster_index(clusters: Sequence[Hashable]) -> tuple[np.ndarray, int]:
    labels = {c: i for i, c in enumerate(dict.fromkeys(clusters))}
    return np.array([labels[c] for c in clusters], dtype=int), len(labels)


def cluster_bootstrap_mean(
    x: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Percentile CI of a pooled mean, resampling whole clusters with replacement."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "boot": np.zeros(0)}
    idx, C = _cluster_index(clusters)
    sums = np.bincount(idx, weights=x, minlength=C)
    cnts = np.bincount(idx, minlength=C).astype(float)
    rng = np.random.default_rng(rng)
    draw = rng.integers(0, C, size=(n_boot, C))
    boot = sums[draw].sum(1) / cnts[draw].sum(1)
    a = (1 - conf) / 2
    return {
        "estimate": float(x.mean()),
        "lo": float(np.quantile(boot, a)),
        "hi": float(np.quantile(boot, 1 - a)),
        "boot": boot,
    }


def cluster_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Paired difference mean(a - b); units paired by position, clusters resampled whole.
    Also returns a two-sided bootstrap p-value (2 x the smaller tail mass at 0)."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    r = cluster_bootstrap_mean(d, clusters, n_boot=n_boot, conf=conf, rng=rng)
    boot = r["boot"]
    if boot.size:
        p = 2 * min(np.mean(boot <= 0), np.mean(boot >= 0))
        r["p_value"] = float(min(1.0, p))
    else:
        r["p_value"] = math.nan
    return r


def cluster_bootstrap_rate_diff(
    x: Sequence[float],
    in_a: Sequence[bool],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Unpaired difference mean(x | A) - mean(x | not A) with clusters resampled whole
    (e.g. RQ2 forward-correction vs repeat arms randomised within tasks)."""
    x = np.asarray(x, dtype=float)
    g = np.asarray(in_a, dtype=bool)
    idx, C = _cluster_index(clusters)
    sa = np.bincount(idx, weights=x * g, minlength=C)
    na = np.bincount(idx, weights=g.astype(float), minlength=C)
    sb = np.bincount(idx, weights=x * ~g, minlength=C)
    nb = np.bincount(idx, weights=(~g).astype(float), minlength=C)
    est = (x[g].mean() if g.any() else math.nan) - (x[~g].mean() if (~g).any() else math.nan)
    rng = np.random.default_rng(rng)
    draw = rng.integers(0, C, size=(n_boot, C))
    with np.errstate(divide="ignore", invalid="ignore"):
        boot = sa[draw].sum(1) / na[draw].sum(1) - sb[draw].sum(1) / nb[draw].sum(1)
    boot = boot[np.isfinite(boot)]
    a = (1 - conf) / 2
    if boot.size == 0:
        return {"estimate": float(est), "lo": math.nan, "hi": math.nan, "p_value": math.nan}
    p = min(1.0, 2 * min(np.mean(boot <= 0), np.mean(boot >= 0)))
    return {
        "estimate": float(est),
        "lo": float(np.quantile(boot, a)),
        "hi": float(np.quantile(boot, 1 - a)),
        "p_value": float(p),
    }


# --------------------------------------------------------------------------- multiplicity


def holm(pvalues: Sequence[float], alpha: float = 0.05, m: int | None = None) -> dict[str, list]:
    """Holm step-down; returns adjusted p-values and reject flags in input order.

    ``m`` is the preregistered family size. When fewer p-values are supplied (a family
    member was not run), the missing ones are treated as p = 1, i.e. the step-down still
    starts at alpha / m. ``m`` smaller than the number of p-values is an error."""
    p = np.asarray(pvalues, dtype=float)
    m = p.size if m is None else int(m)
    if m < p.size:
        raise ValueError(f"family size m={m} < number of p-values {p.size}")
    order = np.argsort(p)
    adj = np.empty(p.size)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return {"adjusted": adj.tolist(), "reject": (adj <= alpha).tolist()}


# --------------------------------------------------------------------------- agreement


def cohens_kappa(r1: Sequence[Hashable], r2: Sequence[Hashable], categories=None) -> float:
    if len(r1) != len(r2) or not r1:
        raise ValueError("ratings must be non-empty and equal length")
    cats = list(categories) if categories is not None else sorted(set(r1) | set(r2), key=str)
    ix = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    m = np.zeros((k, k))
    for a, b in zip(r1, r2):
        m[ix[a], ix[b]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = float(m.sum(1) @ m.sum(0)) / (n * n)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return float((po - pe) / (1 - pe))


# --------------------------------------------------------------------------- non-inferiority


def noninferiority(
    new: Sequence[float],
    ref: Sequence[float],
    clusters: Sequence[Hashable],
    margin: float,
    alpha: float = 0.025,
    n_boot: int = 4000,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, Any]:
    """One-sided non-inferiority of ``new`` vs ``ref`` (higher is better), paired units,
    clustered bootstrap. Non-inferior iff the one-sided (1 - alpha) lower bound of
    mean(new - ref) exceeds -margin. margin > 0, e.g. 0.05 for 5 pp (RQ3 H3b, RQ5)."""
    r = cluster_bootstrap_diff(new, ref, clusters, n_boot=n_boot, conf=1 - 2 * alpha, rng=rng)
    return {
        "estimate": r["estimate"],
        "lower": r["lo"],
        "margin": margin,
        "alpha": alpha,
        "noninferior": bool(r["lo"] > -margin),
    }


# --------------------------------------------------------------------------- power


def _latent_sigma(icc: float) -> float:
    """Logit-scale random-effect SD giving latent-variable ICC (residual var pi^2/3)."""
    if icc <= 0:
        return 0.0
    return math.sqrt(icc / (1 - icc) * math.pi**2 / 3)


_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(40)
_GH_W = _GH_W / _GH_W.sum()


def _intercept_for_marginal(p: float, sigma: float) -> float:
    """beta such that E[expit(beta + sigma Z)] = p, Z ~ N(0,1)."""
    if sigma == 0:
        return math.log(p / (1 - p))

    def f(b: float) -> float:
        return float(np.sum(_GH_W / (1 + np.exp(-(b + sigma * _GH_X))))) - p

    return float(optimize.brentq(f, -40, 40))


def simulate_power(
    baseline: float,
    effect: float,
    icc: float,
    n_tasks: int,
    n_seeds: int,
    alpha: float = 0.05,
    n_comparisons: int = 1,
    n_sims: int = 2000,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Power for a paired, task-clustered binary outcome (proposal §7.2 power analysis).

    Model: task random intercept u_t ~ N(0, sigma^2) on the logit scale, shared by both
    arms (pairing), sigma from the latent ICC; arm intercepts calibrated so the marginal
    success rates are ``baseline`` and ``baseline + effect``; each (task, seed, arm) trial
    is Bernoulli. Analysis: two-sided one-sample t-test on per-task mean differences
    (the cluster-level analogue of the clustered bootstrap) at alpha / n_comparisons
    (Holm's first, strictest step: conservative). Power counts only rejections in the
    direction of ``effect``."""
    p1 = baseline + effect
    if not (0 < baseline < 1 and 0 < p1 < 1):
        raise ValueError("baseline and baseline+effect must be in (0, 1)")
    if n_tasks < 2:
        raise ValueError("need >= 2 tasks")
    rng = np.random.default_rng(rng)
    sigma = _latent_sigma(icc)
    b0 = _intercept_for_marginal(baseline, sigma)
    b1 = _intercept_for_marginal(p1, sigma)
    u = rng.normal(0.0, sigma, size=(n_sims, n_tasks))
    y0 = rng.binomial(n_seeds, 1 / (1 + np.exp(-(b0 + u))))
    y1 = rng.binomial(n_seeds, 1 / (1 + np.exp(-(b1 + u))))
    d = (y1 - y0) / n_seeds
    mean = d.mean(1)
    sd = d.std(1, ddof=1)
    a = alpha / n_comparisons
    crit = stats.t.ppf(1 - a / 2, n_tasks - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = np.where(sd > 0, mean / (sd / math.sqrt(n_tasks)), np.sign(mean) * np.inf)
    sign = 1.0 if effect >= 0 else -1.0
    reject = (np.abs(tstat) > crit) & (np.sign(tstat) == sign)
    if effect == 0:
        reject = np.abs(tstat) > crit
    power = float(reject.mean())
    return {
        "power": power,
        "mc_se": math.sqrt(power * (1 - power) / n_sims),
        "alpha_per_test": a,
        "sigma_logit": sigma,
        "n_trials_per_arm": n_tasks * n_seeds,
    }


def min_tasks_for_power(
    target: float = 0.8,
    task_grid: Sequence[int] = (10, 20, 30, 40, 60, 80, 100, 120, 160),
    **kw: Any,
) -> dict[str, Any]:
    """Smallest task count in ``task_grid`` reaching ``target`` power (None if none)."""
    curve = {}
    for t in task_grid:
        curve[t] = simulate_power(n_tasks=t, **kw)["power"]
        if curve[t] >= target:
            return {"n_tasks": t, "curve": curve}
    return {"n_tasks": None, "curve": curve}


def percentiles(x: Sequence[float], qs: Sequence[float] = (50, 95, 99)) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {f"p{int(q)}": math.nan for q in qs}
    return {f"p{int(q)}": float(np.percentile(x, q)) for q in qs}


===== FILE: live_agent/eval/runner.py =====
"""E2 runner: execute scripted tasks against the live-agent stack and write SCHEMA.md logs.

Conditions (proposal §7.2): A1 open loop; A2 full; A2-noqc (no online checks);
A2-repeat (RQ2 contrast: repeat instead of forward correction); B0 (scripted, no input).

Time: all orchestrator times are monotonic seconds; with a sped-up mock stack they are
rescaled by ``speed`` so that deadlines (15 s ...) apply in *simulated* seconds.
Chains: the director's chains are mapped to the task's ground-truth chains through the
utterance uid that opened / revised them.

Usage:
    python -m live_agent.eval.runner --suite eval/tasks/e2_committed.jsonl \
        --conditions A1 A2 --seeds 0 1 --out .cache/e2 [--mock --speed 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import zlib
from pathlib import Path
from typing import Any

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.eval.schema import SessionLogWriter
from live_agent.eval.sim_user import SimulatedUser
from live_agent.eval.tasks import Task, load_suite
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.sim import SimClient
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import EventType, Utterance, now

CONDITIONS = {
    "A1": dict(mode=DirectorMode.OPEN_LOOP, qc=False, correction=CorrectionMode.NONE),
    "A2": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.GRADIENT),
    "A2-noqc": dict(mode=DirectorMode.CLOSED_LOOP, qc=False, correction=CorrectionMode.NONE),
    "A2-repeat": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.REPEAT),
    # RQ2: the repair arm is drawn per eligible failure point (seeded), logged per repair.
    "A2-rq2": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.RANDOMIZED),
}

CONTENT_DURATION_S = {"qa": 10.0, "explain": 30.0, "sing": 30.0}  # proposal §7 D table [proposed target]


def observation_horizon_s(task: Task) -> float:
    """How long after the last utterance media must be observed so every deadline D is covered."""
    d = 15.0
    for u in task.utterances:
        it = u.intent or {}
        kind = it.get("kind", task.kind)
        if kind == "multistep":
            steps = it.get("steps") or 1
            d = max(d, 15.0 * (len(steps) if isinstance(steps, list) else int(steps)))
        elif kind == "content":
            dur = it.get("prereg_duration_s") or CONTENT_DURATION_S.get(it.get("content_type", ""), 30.0)
            d = max(d, 15.0 + float(dur))
    return d + 5.0


def convert(orch: Orchestrator, user_events: list[dict], *, t0: float, speed: float) -> list[dict]:
    """Map orchestrator TimelineEvents + sim-user events into SCHEMA.md events."""
    ts = lambda t: (t - t0) * speed  # noqa: E731
    uid_to_chain = {e["uid"]: e["chain_id"] for e in user_events if e["type"] == "chain_annotation"}
    gt_uids: dict[str, list[str]] = {}  # GT chain -> uids of its new/revision utterances, in order
    for e in user_events:
        if e["type"] == "chain_annotation" and e["action"] in ("new", "revision"):
            gt_uids.setdefault(e["chain_id"], []).append(e["uid"])
    dchain_to_gt: dict[str, str] = {}
    dchain_uids: dict[str, list[str]] = {}
    for c in orch.director.chains.values():
        dchain_uids[c.chain_id] = [c.opened_by, *c.revisions]
        for uid in dchain_uids[c.chain_id]:
            if uid in uid_to_chain:
                dchain_to_gt[c.chain_id] = uid_to_chain[uid]

    def gt_revision(dchain: str, drev: int | None) -> int | None:
        """Director revision r -> GT revision index of the utterance that defined it."""
        uids = dchain_uids.get(dchain, [])
        gt = dchain_to_gt.get(dchain)
        if gt is None or drev is None or drev >= len(uids) or uids[drev] not in gt_uids.get(gt, []):
            return None
        return gt_uids[gt].index(uids[drev])

    out: list[dict[str, Any]] = []
    for e in user_events:  # already on the shared clock (monotonic) -> rescale
        e = dict(e)
        for k in ("t_start", "t_end", "t"):
            if k in e:
                e[k] = ts(e[k])
        out.append(e)
    for ev in orch.log.events:
        d, k = ev.data, ev.request_index
        script = orch.scripts.get(k) if k is not None else None
        dchains = script.chain_ids if script is not None else []
        if ev.type == EventType.LOCK and k is not None:
            out.append({"type": "lock", "t": ts(ev.t), "request": k,
                        "chain_ids": [dchain_to_gt[c] for c in dchains if c in dchain_to_gt],
                        "plan_version": d.get("plan_version")})
        elif ev.type == EventType.CHUNK_PRESENTED:
            out.append({"type": "chunk_presented", "request": k, "chunk": ev.chunk_index,
                        "t_start": ts(ev.t), "t_end": ts(d["t_end"])})
        elif ev.type == EventType.VERDICT and d.get("kind") == "action":
            for cid in d.get("chain_ids", dchains):  # only the chain the judged request served
                gt = dchain_to_gt.get(cid)
                if gt is None:
                    continue
                v = {"type": "verdict", "source": "judge", "label": d["label"], "chain_id": gt,
                     "request": k, "chunk": 0, "t_evidence": ts(d["t_evidence"]), "qid": d.get("qid")}
                rev = gt_revision(cid, d.get("revision"))
                if rev is not None:
                    v["revision"] = rev
                if d.get("step") is not None:  # multistep: the director's step index (action steps)
                    v["step"] = d["step"]
                out.append(v)
        elif ev.type == EventType.COMPLETION_CLAIM:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                c = {"type": "completion_claim", "chain_id": gt, "t": ts(ev.t), "request": k,
                     "text": d.get("text", "")}
                if d.get("step") is not None:
                    c["step"] = d["step"]
                out.append(c)
        elif ev.type == EventType.SPEECH_ONSET:
            for cid in d.get("chain_ids", []):
                gt = dchain_to_gt.get(cid)
                if gt:  # scripted for this chain; on-topic only a human can confirm
                    out.append({"type": "speech_onset", "t": ts(ev.t), "on_topic": None, "source": "script",
                                "onset_source": d.get("onset_source"), "chain_id": gt, "request": k})
        elif ev.type == EventType.REFUSAL:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "refusal", "chain_id": gt, "t": ts(ev.t),
                            "kind": "degraded" if d.get("degraded") else "refused", "reason": d.get("reason", "")})
        elif ev.type == EventType.CAPACITY_SKIP:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                sk = {"type": "capacity_skip", "chain_id": gt, "t": ts(ev.t)}
                rev = gt_revision(d["chain_id"], d.get("revision"))
                if rev is not None:
                    sk["revision"] = rev
                out.append(sk)
        elif ev.type == EventType.PLAYBACK_STOP:
            out.append({"type": "playback_stop", "t": ts(ev.t), "reason": "erasure" if d.get("erasure") else "barge_in"})
        elif ev.type == EventType.REPAIR:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                r = {"type": "repair_assignment", "chain_id": gt,
                     "arm": "forward_correction" if d.get("mode") == "gradient" else "repeat",
                     "failure_request": k, "target_request": d.get("earliest_correctable"),
                     "C": d.get("chain_cost_s")}
                if d.get("step") is not None:
                    r["step"] = d["step"]
                out.append(r)
        elif ev.type == EventType.OBSERVATION_END:
            out.append({"type": "observation_end", "t": ts(ev.t)})
    return out


async def run_task(task: Task, condition: str, seed: int, *, factory, speed: float, out_dir: Path,
                   mode: str = "simulation") -> Path:
    cfg = CONDITIONS[condition]
    # Per-(task, seed) RNG stream, identical across conditions (paired design), different across tasks.
    stream = zlib.crc32(f"{task.task_id}/{seed}".encode())
    orch, client = factory(cfg, stream)
    client.orchestrator = orch
    t0 = now()
    user_events: list[dict] = []

    async def send(text: str, meta: dict) -> dict:
        t_start = now()
        if meta.get("barge_in"):
            await orch.on_speech_start(t_start)
        await orch.on_user_utterance(Utterance(meta["uid"], "user", text, now()))
        return {"t_start": t_start, "t_end": now()}

    user = SimulatedUser(task, send, clock=now, sleep=lambda dt: asyncio.sleep(dt / speed),
                         session_id=f"{condition}-{task.task_id}-s{seed}", on_event=user_events.append)
    path = out_dir / f"{condition}-{task.task_id}-s{seed}.jsonl"
    if getattr(client, "recorder", None) is not None:
        client.recorder.path = path.with_suffix(".mp4")  # adjudication looks for <log>.mp4
    client.start()
    await orch.start()
    try:
        await user.run()
        # observe media until every deadline D of the task has passed (scorer checks observation_end)
        await asyncio.wait_for(orch._stop.wait(), timeout=observation_horizon_s(task) / speed)
    except asyncio.TimeoutError:
        pass
    finally:
        await orch.stop()
        client.close()
    if orch.error is not None:
        raise RuntimeError(f"{condition}/{task.task_id}: session failed: {orch.error}")
    header = dict(session_id=f"{condition}-{task.task_id}-s{seed}", condition=condition,
                  task_id=task.task_id, seed=seed, mode=mode, backbone=orch.gen.info.name)
    gseed = getattr(getattr(orch.gen, "backend", orch.gen), "seed", None)
    with SessionLogWriter(path, **header, **({"generator_seed": gseed} if gseed is not None else {})) as w:
        for ev in convert(orch, user_events, t0=t0, speed=speed):
            w.write(ev)
    return path


def schedule(tasks: list[Task], conditions: list[str], seeds: list[int]) -> list[tuple[Task, str, int]]:
    """Counterbalanced order: per (seed, task) the conditions run back to back, rotated so each
    condition appears in each position equally often (no condition-blocked warm-up/drift)."""
    out = []
    i = 0
    for seed in seeds:
        for t in tasks:
            rot = conditions[i % len(conditions):] + conditions[: i % len(conditions)]
            out += [(t, c, seed) for c in rot]
            i += 1
    return out


def mock_factory(config_dir: Path, *, speed: float, llm, p_default: float = 0.7):
    from live_agent.generator.mock import MockGenerator
    from live_agent.qc.judge import ForwardCorrector, MockJudge

    canon = json.loads((config_dir / "canon.json").read_text(encoding="utf-8"))

    def factory(cfg: dict, seed: int):
        manifest = CapabilityManifest.load(config_dir / "capabilities.json")
        manifest.min_status = Status.DOCUMENTED  # simulation: capabilities are not yet executed
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = MockGenerator(teacher_s=1.0, chunk_s=0.5, speed=speed, seed=seed)
        sched = LockScheduler(SchedulerConfig(request_s=5.0 / speed, sigma_s=0.5 / speed, delta_s=0.01,
                                              lambda_prior_s=3.0 / speed, time_scale=1.0 / speed))
        client = SimClient(speed=speed)
        orch = Orchestrator(gen, director, sched, client, judge=MockJudge(p_default=p_default, seed=seed),
                            corrector=ForwardCorrector(None), log=EventLog(),
                            cfg=OrchestratorConfig(correction_mode=cfg["correction"], qc_enabled=cfg["qc"],
                                                   seed=seed))
        return orch, client

    return factory


def live_factory(config_dir: Path, *, backend, llm, vlm, record_dir: Path | None = None,
                 allow_uncalibrated: bool = False):
    """Real stack: shared generator backend (e.g. TaoMate-H3; one session at a time through
    SessionView), LLM responder, VLM judge, LLM forward corrector. Real time (speed 1)."""
    from live_agent.generator.base import SessionView
    from live_agent.qc.judge import ForwardCorrector, VLMJudge
    from live_agent.sim import Recorder

    canon = json.loads((config_dir / "canon.json").read_text(encoding="utf-8"))
    counter = iter(range(10**9))

    def factory(cfg: dict, seed: int):
        manifest = CapabilityManifest.load(config_dir / "capabilities.json")
        # E2 gating needs human-validated E1 calibration; earlier runs are qualification only.
        manifest.min_status = Status.DOCUMENTED if allow_uncalibrated else Status.CALIBRATED
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = SessionView(backend, seed=seed)
        sched = LockScheduler(SchedulerConfig(request_s=backend.info.request_seconds))
        rec = Recorder(record_dir / f"session-{next(counter):03d}.mp4") if record_dir else None
        client = SimClient(speed=1.0, recorder=rec)
        orch = Orchestrator(gen, director, sched, client, judge=VLMJudge(vlm, k=8, contrast=True), corrector=ForwardCorrector(llm),
                            log=EventLog(), cfg=OrchestratorConfig(correction_mode=cfg["correction"],
                                                                   qc_enabled=cfg["qc"], seed=seed))
        return orch, client

    return factory


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default="eval/tasks/e2_committed.jsonl")
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--conditions", nargs="+", default=["A1", "A2"])
    p.add_argument("--seeds", nargs="+", type=int, default=[0])
    p.add_argument("--tasks", nargs="*", default=None)
    p.add_argument("--out", default=".cache/e2")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--p-default", type=float, default=0.7, help="mock judge success probability")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--allow-uncalibrated", action="store_true",
                   help="live stack: accept 'documented' capabilities (M1 qualification before E1)")
    p.add_argument("--record", action="store_true", help="save the presented stream as MP4 (live stack)")
    args, rest = p.parse_known_args()
    args.extra = rest
    asyncio.run(_main(args))


async def _main(args) -> None:
    from live_agent.llm import OpenAICompatLLM

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in load_suite(args.suite) if not args.tasks or t.task_id in args.tasks]
    llm = OpenAICompatLLM(args.llm_url, args.llm_model)
    await llm.warmup()
    backend = None
    if args.generator == "mock":
        speed = args.speed
        factory = mock_factory(Path(args.config), speed=speed, llm=llm, p_default=args.p_default)
    else:
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        speed = 1.0
        backend = TaoMateH3Generator.from_args(args)
        await backend.start()
        factory = live_factory(Path(args.config), backend=backend, llm=llm,
                               vlm=OpenAICompatLLM(args.vlm_url, args.vlm_model),
                               record_dir=out if args.record else None,
                               allow_uncalibrated=args.allow_uncalibrated)
    mode = "simulation" if backend is None else "generator_path"
    try:
        for t, cond, seed in schedule(tasks, args.conditions, args.seeds):
            path = await run_task(t, cond, seed, factory=factory, speed=speed, out_dir=out, mode=mode)
            print(path, flush=True)
    finally:
        if backend is not None:
            await backend.close()


if __name__ == "__main__":
    main()

===== FILE: live_agent/eval/adjudicate.py =====
"""Blinded, dual human adjudication of the primary outcome with third-person arbitration
(proposal §7.2 / §14, D-014; SCHEMA.md ``rating`` and ``verdict`` with source ``adjudicated``).

    # 1. build a blinded labelling page from session logs + recorded MP4s (runner --record).
    #    The key (item -> session/condition) is written OUTSIDE the batch directory.
    python -m live_agent.eval.adjudicate prepare .cache/m1/*.jsonl -o .cache/adj/batch1 \
        [--key .cache/adj/batch1.key/key.json] [--suite eval/tasks/e2_committed.jsonl] [--seed 0]
    # 2. give ONLY .cache/adj/batch1/ to annotators; each opens index.html, labels, and
    #    presses "Download labels"
    # 3. merge two independent ratings; agreements become reconciled verdicts, disagreements
    #    are listed in <key dir>/unresolved.json for a third annotator (arbiter)
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labelsA.json:R1 labelsB.json:R2
    # 4. after arbitration (same page; arbiter labels the listed item ids)
    python -m live_agent.eval.adjudicate merge .cache/adj/batch1 labelsA.json:R1 labelsB.json:R2 \
        --arbiter labelsC.json:R3

Blinding: items are shuffled across sessions and conditions, carry random ids, and show only
the user's instruction(s), the preregistered success criteria (checks / content rubric /
per-step criteria, frozen from the task suite) and the video.

Items: one per effective chain (final intent; per step for multistep; content items also ask
for the on-topic speech onset), plus one per completion claim that the chain's final-intent
verdict cannot settle (claims on withdrawn chains, or heard before the final revision). Such a
claim is judged against what was requested when it was heard.

Every label records the reviewed interval (request start to the furthest point the
annotator played). Label times must lie inside the recording and inside the final-intent
interval (after the request); out-of-range or incomplete labels reject the whole file.

Time mapping: the recording holds the presented chunks back to back (stalls are not recorded), so
video time v maps to session time through the cumulative chunk durations of the session's
``chunk_presented`` events (``video_to_session``). Times beyond the recording are rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import secrets
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from live_agent.eval import stats
from live_agent.eval.schema import VERDICT_LABELS, load_session
from live_agent.eval.scoring import build_chains, claim_needs_direct_adjudication
from live_agent.eval.tasks import load_suite

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = ROOT / "eval" / "tasks" / "e2_committed.jsonl"
_EPS = 1e-3  # video-time tolerance (s)


class LabelError(ValueError):
    """Labels out of range, incomplete, or not matching the batch: nothing was merged."""


# --------------------------------------------------------------------------- time mapping


def presented_segments(events: list[dict]) -> list[tuple[float, float, float]]:
    """[(video_start, session_start, duration)] for presented chunks in presentation order."""
    chunks = sorted((e for e in events if e["type"] == "chunk_presented"), key=lambda e: e["t_start"])
    out, v = [], 0.0
    for e in chunks:
        d = e["t_end"] - e["t_start"]
        out.append((v, e["t_start"], d))
        v += d
    return out


def recorded_length(segments: Sequence[Sequence[float]]) -> float:
    return float(segments[-1][0] + segments[-1][2]) if segments else 0.0


def video_to_session(segments: list[tuple[float, float, float]], v: float) -> float:
    """Session time of video time v. Raises ValueError outside [0, recorded length]: a time
    past the last recorded frame was never observed and must not be extrapolated."""
    if not segments:
        raise ValueError("no presented chunks: cannot map video time")
    total = recorded_length(segments)
    if v < -_EPS or v > total + _EPS:
        raise ValueError(f"video time {v:.3f} s outside the recording [0, {total:.3f}] s")
    for v0, s0, d in segments:
        if v < v0 + d:
            return s0 + max(0.0, v - v0)
    v0, s0, d = segments[-1]
    return s0 + d


def session_to_video(segments: list[tuple[float, float, float]], t: float) -> float:
    for v0, s0, d in segments:
        if t < s0 + d:
            return v0 + max(0.0, t - s0)
    if not segments:
        return t
    v0, s0, d = segments[-1]
    return v0 + d


# --------------------------------------------------------------------------- items


def chains_for_adjudication(events: list[dict]) -> list[dict[str, Any]]:
    """Final intent of every effective (not finally withdrawn) chain, with its clock origin
    and revision count (number of ``revision`` annotations)."""
    utt = {e["uid"]: e for e in events if e["type"] == "utterance"}
    anns = sorted((e for e in events if e["type"] == "chain_annotation"),
                  key=lambda e: utt.get(e["uid"], {}).get("t_end", 0.0))
    chains: dict[str, dict[str, Any]] = {}
    for e in anns:
        c = chains.setdefault(e["chain_id"], {"chain_id": e["chain_id"], "texts": [], "withdrawn": False,
                                              "revision": -1, "ann": {}})
        u = utt.get(e["uid"], {})
        c["texts"].append(u.get("text", ""))
        if e["action"] == "withdrawal":
            c["withdrawn"] = True
            continue
        c["withdrawn"] = False
        c["origin"] = u.get("t_end", 0.0)
        c["revision"] += 1
        c["ann"] = e
        for k in ("kind", "intent", "content_type", "steps", "label"):
            if k in e:
                c[k] = e[k]
    out = []
    for c in chains.values():
        if c["withdrawn"] or "origin" not in c:
            continue
        steps = c.get("steps")
        c["n_steps"] = (len(steps) if isinstance(steps, list) else int(steps)) if c.get("kind") == "multistep" and steps else 1
        c["kind"] = "action" if c.get("kind") == "correction" else c.get("kind", "action")
        out.append(c)
    return out


def _criteria_from_intent(it: dict[str, Any]) -> dict[str, Any]:
    kind = "action" if it.get("kind") == "correction" else it.get("kind", "action")
    cr: dict[str, Any] = {"kind": kind, "intent": it.get("intent", "")}
    if kind == "content":
        from live_agent.eval.scoring import CONTENT_DURATION_S

        cr["content_type"] = it.get("content_type")
        cr["duration_s"] = it.get("prereg_duration_s", CONTENT_DURATION_S.get(it.get("content_type") or "qa"))
        cr["rubric"] = it.get("rubric")
        if not cr["rubric"]:
            raise ValueError(f"content intent without a preregistered rubric: {it}")
    elif kind == "multistep":
        steps = it.get("steps") or []
        if not steps or not all(isinstance(s, dict) and s.get("checks") for s in steps):
            raise ValueError(f"multistep intent without per-step criteria: {it}")
        cr["steps"] = [{"intent": s.get("intent", ""), "checks": list(s["checks"])} for s in steps]
    else:
        if not it.get("checks"):
            raise ValueError(f"action intent without checks: {it}")
        cr["checks"] = list(it["checks"])
    return cr


def _criteria(tasks: dict[str, Any], task_id: str, label: str, revision: int,
              ann: dict[str, Any] | None) -> dict[str, Any]:
    """Preregistered criteria of revision ``revision`` of chain ``label``: from the task
    suite, else from a chain_annotation that carries them (``checks`` / ``rubric`` /
    ``steps`` as dicts). Raises if none: an item without criteria cannot be adjudicated."""
    t = tasks.get(task_id)
    if t is not None:
        hist = [u.intent for u in t.utterances if u.chain == label and u.annotation in ("new", "revision")]
        if 0 <= revision < len(hist) and hist[revision]:
            return _criteria_from_intent(hist[revision])
    if ann and (ann.get("checks") or ann.get("rubric")
                or (isinstance(ann.get("steps"), list) and ann["steps"] and isinstance(ann["steps"][0], dict))):
        return _criteria_from_intent(ann)
    raise ValueError(f"no preregistered criteria for task {task_id} chain {label} revision {revision}")


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


PAGE = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>Adjudication</title>
<style>
:root{{--bg:#fff;--fg:#111;--mut:#666;--line:#ddd;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--line:#333;--acc:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:980px;padding:16px}}
.item{{border:1px solid var(--line);border-radius:8px;padding:12px;margin:16px 0;display:flex;gap:16px;flex-wrap:wrap}}
video{{width:300px;max-width:100%;background:#000}} .meta{{flex:1;min-width:260px}}
.mut{{color:var(--mut);font-size:13px}} button{{margin:2px}} .step{{margin:8px 0;padding:6px;border-top:1px dashed var(--line)}}
.crit{{margin:6px 0;padding:6px 8px;border-left:3px solid var(--acc);font-size:14px}} .crit ul{{margin:2px 0 2px 18px;padding:0}}
.sel{{outline:2px solid var(--acc)}}
</style>
<h1>Blinded adjudication · {n} items</h1>
<p class="mut">For each item the user's request(s) and the <b>preregistered criteria</b> are shown; the video starts at
the request. Judge only against the criteria of the <b>final</b> request. "Done" needs every listed check.
<b>Action</b>: pause at the <b>first frame that clearly shows it</b> and press "first compliant = now".
<b>Multistep</b>: label each step; for step i mark the first frame showing it <b>after</b> step i−1 was done (if it was
only done before, mark that time). <b>Content</b>: mark when on-topic speech starts (or "no on-topic speech"), and
judge the rubric over the whole answer; if it passes, mark when the answer ends. <b>Claim</b> items: decide whether,
at the moment the persona claimed completion, what was requested at that time had visibly been done.
"Cannot tell" is allowed. Watch until you are sure: the furthest point you play is recorded as the reviewed
interval. Do not guess the condition.</p>
<div id="items"></div>
<p><button onclick="dl()">Download labels</button> <span class="mut" id="cnt"></span></p>
<script>
const ITEMS = {items};
const L = {{}}, SEEN = {{}};
try {{ Object.assign(L, JSON.parse(localStorage.getItem("adj-{batch}") || "{{}}")); }} catch (e) {{}}
function esc(s){{ return String(s).replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]); }}
function save(){{ try {{ localStorage.setItem("adj-{batch}", JSON.stringify(L)); }} catch (e) {{}}
  document.getElementById("cnt").textContent = Object.keys(L).length + " step labels"; }}
function seen(id){{ const v = document.getElementById("v-" + id); return Math.max(SEEN[id] || 0, v ? v.currentTime : 0); }}
function set(id, step, key, val){{ const k = id + "/" + step; const o = Object.assign(L[k] || {{}}, {{[key]: val}});
  if (key === "onset_none" && val) delete o.v_onset; if (key === "v_onset") delete o.onset_none;
  o.v_seen = +Math.max(o.v_seen || 0, seen(id)).toFixed(2); L[k] = o; save(); render(); }}
function now(id, step, key){{ set(id, step, key, +document.getElementById("v-" + id).currentTime.toFixed(2)); }}
function list(xs){{ return "<ul>" + xs.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>"; }}
function rubric(r){{ return "<ul>" + Object.entries(r).map(([k, v]) => "<li>" + esc(k) + ": " +
  esc(Array.isArray(v) ? v.join("; ") : v) + "</li>").join("") + "</ul>"; }}
function crit(c, s){{
  if (c.kind === "multistep") {{ const st = c.steps[s]; return "<b>step " + (s + 1) + ": " + esc(st.intent) + "</b>" + list(st.checks); }}
  if (c.kind === "content") return "<b>" + esc(c.intent) + "</b> (" + esc(c.content_type) + ", answer within " +
    c.duration_s + " s after onset)" + rubric(c.rubric);
  return "<b>" + esc(c.intent) + "</b>" + list(c.checks);
}}
function render(){{
  const root = document.getElementById("items"); const keep = {{}};
  document.querySelectorAll("video").forEach(v => keep[v.id] = v);
  root.innerHTML = "";
  ITEMS.forEach(it => {{
    const d = document.createElement("div"); d.className = "item";
    let v = keep["v-" + it.id];
    if (!v) {{ v = Object.assign(document.createElement("video"),
      {{id: "v-" + it.id, src: it.video + "#t=" + it.v_origin, controls: true, preload: "metadata"}});
      v.addEventListener("timeupdate", () => {{ SEEN[it.id] = Math.max(SEEN[it.id] || 0, v.currentTime); }}); }}
    d.appendChild(v);
    const m = document.createElement("div"); m.className = "meta";
    const head = it.type === "claim" ? "claim · persona said it was done at video " + it.v_claim.toFixed(1) + " s"
      : it.kind + (it.content_type ? " / " + it.content_type : "");
    m.innerHTML = "<div class=mut>" + it.id + " · " + head + " · request at video " + it.v_origin.toFixed(1) + " s</div>" +
      it.texts.map((t, i) => "<div>" + (i ? "then: " : "user: ") + t + "</div>").join("");
    for (let s = 0; s < it.n_steps; s++) {{
      const k = it.id + "/" + s, cur = L[k] || {{}};
      const st = document.createElement("div"); st.className = "step";
      const cs = it.type === "claim" && it.claim_step != null ? it.claim_step : s;
      let h = "<div class=crit>" + crit(it.criteria, cs) + "</div>";
      h += ["complied", "not_complied", "unknown"].map(x =>
        `<button class="${{cur.label === x ? "sel" : ""}}" onclick="set('${{it.id}}',${{s}},'label','${{x}}')">${{
          {{complied: "done", not_complied: "not done", unknown: "cannot tell"}}[x]}}</button>`).join("");
      if (it.type === "chain" && it.kind !== "content")
        h += ` <button onclick="now('${{it.id}}',${{s}},'v_first')">first compliant = now</button>`;
      if (it.type === "chain" && it.kind === "content")
        h += ` <button onclick="now('${{it.id}}',${{s}},'v_onset')">on-topic speech starts = now</button>` +
             ` <button class="${{cur.onset_none ? "sel" : ""}}" onclick="set('${{it.id}}',${{s}},'onset_none',true)">no on-topic speech</button>` +
             ` <button onclick="now('${{it.id}}',${{s}},'v_end')">answer ends = now</button>`;
      h += ` <span class=mut>${{cur.v_first != null ? "first " + cur.v_first + " s " : ""}}${{
        cur.v_onset != null ? "onset " + cur.v_onset + " s " : ""}}${{cur.v_end != null ? "end " + cur.v_end + " s " : ""}}${{
        cur.v_seen != null ? "reviewed to " + cur.v_seen + " s" : ""}}</span>`;
      st.innerHTML = h; m.appendChild(st);
    }}
    d.appendChild(m); root.appendChild(d);
  }});
}}
function dl(){{ const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(L, null, 1)], {{type: "application/json"}}));
  a.download = "labels-{batch}.json"; a.click(); }}
render(); save();
</script></html>
"""


def default_key_path(batch_dir: Path) -> Path:
    """<batch>.key/key.json, next to (never inside) the annotator batch directory."""
    b = Path(batch_dir).resolve()
    return b.parent / f"{b.name}.key" / "key.json"


def _check_key_outside(batch_dir: Path, key_path: Path) -> None:
    b, k = Path(batch_dir).resolve(), Path(key_path).resolve()
    if b == k or b in k.parents:
        raise ValueError(f"key {k} must not be inside the annotator batch directory {b}")


def prepare(logs: list[Path], out: Path, seed: int = 0, *, suite: Path | None = DEFAULT_SUITE,
            key_path: Path | None = None) -> Path:
    key_path = Path(key_path) if key_path else default_key_path(out)
    _check_key_outside(out, key_path)
    tasks = {t.task_id: t for t in load_suite(suite)} if suite else {}
    out.mkdir(parents=True, exist_ok=True)
    items, key = [], {}

    def new_id() -> str:
        while True:
            iid = secrets.token_hex(3)
            if iid not in key:
                return iid

    for log in logs:
        s = load_session(log)
        video = log.with_suffix(".mp4")
        if not video.exists():
            print(f"skip {log.name}: no recording {video.name}")
            continue
        segs = presented_segments(s.events)
        v_len = recorded_length(segs)
        media = out / "media" / f"{secrets.token_hex(4)}.mp4"  # random name: the file name would unblind
        media.parent.mkdir(exist_ok=True)
        try:
            media.symlink_to(video.resolve())
        except OSError:
            shutil.copyfile(video, media)
        rel = os.path.relpath(media, out)
        for c in chains_for_adjudication(s.events):
            cr = _criteria(tasks, s.task_id, c.get("label", c["chain_id"]), c["revision"], c["ann"])
            iid = new_id()
            v_origin = round(session_to_video(segs, c["origin"]), 2)
            items.append({"id": iid, "type": "chain", "video": rel, "kind": c["kind"],
                          "content_type": c.get("content_type"), "texts": [html.escape(t) for t in c["texts"]],
                          "n_steps": c["n_steps"], "v_origin": v_origin, "criteria": cr})
            key[iid] = {"type": "chain", "log": str(log.resolve()), "chain_id": c["chain_id"], "segments": segs,
                        "kind": c["kind"], "n_steps": c["n_steps"], "v_origin": v_origin, "v_len": v_len,
                        "revision": c["revision"], "criteria_sha256": _sha(cr)}
        # claims the final-intent verdict cannot settle
        chains = build_chains(s)
        utt = {e["uid"]: e for e in s.of_type("utterance")}
        anns = s.of_type("chain_annotation")
        for cl in s.of_type("completion_claim"):
            ch = chains.get(cl["chain_id"])
            t = float(cl["t"])
            if ch is None or not claim_needs_direct_adjudication(ch, t):
                continue
            r = ch.revision_at(t)
            said = [a for a in anns if a["chain_id"] == ch.chain_id and float(utt[a["uid"]]["t_end"]) <= t]
            rev_ann = [a for a in said if a["action"] in ("new", "revision")]
            cr = _criteria(tasks, s.task_id, ch.label, r, rev_ann[-1] if rev_ann else None)
            iid = new_id()
            v_origin = round(session_to_video(segs, ch.origins[r]), 2)
            items.append({"id": iid, "type": "claim", "video": rel, "kind": cr["kind"],
                          "content_type": cr.get("content_type"),
                          "texts": [html.escape(utt[a["uid"]]["text"]) for a in said],
                          "n_steps": 1, "v_origin": v_origin, "v_claim": round(session_to_video(segs, t), 2),
                          "claim_step": cl.get("step"), "criteria": cr})
            key[iid] = {"type": "claim", "log": str(log.resolve()), "chain_id": ch.chain_id, "segments": segs,
                        "kind": cr["kind"], "n_steps": 1, "v_origin": v_origin, "v_len": v_len,
                        "revision": r, "claim_t": t, "claim_id": cl.get("claim_id"),
                        "claim_step": cl.get("step"), "criteria_sha256": _sha(cr)}
    random.Random(seed).shuffle(items)
    batch = out.name
    (out / "index.html").write_text(PAGE.format(n=len(items), items=json.dumps(items, ensure_ascii=False),
                                                batch=batch), encoding="utf-8")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps({"batch": batch, "items": key}, indent=1), encoding="utf-8")
    return out / "index.html"


# --------------------------------------------------------------------------- merge


def _to_session(lab: dict[str, Any], info: dict[str, Any], annotator: str, where: str) -> dict[str, Any]:
    """Validate one label and convert it to session time. Raises LabelError."""
    segs = [tuple(x) for x in info["segments"]]
    v_len, v_origin = float(info["v_len"]), float(info["v_origin"])
    label = lab.get("label")
    if label not in VERDICT_LABELS:
        raise LabelError(f"{where}: missing or bad label {label!r}")
    r: dict[str, Any] = {"label": label, "annotator": annotator}
    for k in ("v_first", "v_end", "v_onset", "v_seen"):
        v = lab.get(k)
        if v is None:
            continue
        v = float(v)
        if v < -_EPS or v > v_len + _EPS:
            raise LabelError(f"{where}: {k}={v} outside the recording [0, {v_len:.2f}] s")
        if k != "v_seen" and v < v_origin - _EPS:
            raise LabelError(f"{where}: {k}={v} before the request (final intent starts at video {v_origin:.2f} s)")
    is_chain = info["type"] == "chain"
    if is_chain and label == "complied":
        need = "v_end" if info["kind"] == "content" else "v_first"
        if lab.get(need) is None:
            raise LabelError(f"{where}: 'done' needs {need}")
    if is_chain and info["kind"] == "content" and (lab.get("v_onset") is None) == (not lab.get("onset_none")):
        raise LabelError(f"{where}: content item needs exactly one of an onset time or 'no on-topic speech'")
    conv = {"v_first": "t_first_compliant", "v_end": "t_evidence", "v_onset": "t_onset"}
    for vk, tk in conv.items():
        if lab.get(vk) is not None:
            r[tk] = video_to_session(segs, float(lab[vk]))
    if "t_first_compliant" in r and "t_evidence" not in r:
        r["t_evidence"] = r["t_first_compliant"]
    if is_chain and info["kind"] == "content":
        r["onset_none"] = bool(lab.get("onset_none"))
    marks = [float(lab[k]) for k in ("v_first", "v_end", "v_onset") if lab.get(k) is not None]
    seen = max([v_origin, *marks, *([float(lab["v_seen"])] if lab.get("v_seen") is not None else [])])
    r["t_review_start"] = video_to_session(segs, min(v_origin, v_len))
    r["t_review_end"] = video_to_session(segs, min(seen, v_len))
    return r


def _load_ratings(path: Path, annotator: str, items: dict[str, Any]) -> dict[str, dict[str, Any]]:
    labels = json.loads(Path(path).read_text(encoding="utf-8"))
    out, errs = {}, []
    for k, lab in labels.items():
        try:
            iid, step_s = k.split("/")
            step = int(step_s)
        except ValueError:
            errs.append(f"{annotator} {k}: bad key")
            continue
        info = items.get(iid)
        if info is None:
            errs.append(f"{annotator} {k}: unknown item (wrong batch?)")
            continue
        if not 0 <= step < int(info["n_steps"]):
            errs.append(f"{annotator} {k}: step {step} out of range")
            continue
        try:
            out[k] = _to_session(lab, info, annotator, f"{annotator} {k}")
        except (LabelError, ValueError) as e:
            errs.append(str(e))
    if errs:
        raise LabelError(f"{path}: {len(errs)} invalid label(s); nothing merged:\n  " + "\n  ".join(errs))
    return out


def _close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _agree(a: dict[str, Any], b: dict[str, Any], kind: str, is_chain: bool, tol: float) -> bool:
    if a["label"] != b["label"]:
        return False
    if is_chain and a["label"] == "complied":
        if not _close(a.get("t_first_compliant"), b.get("t_first_compliant"), tol):
            return False
        if kind == "content" and not _close(a.get("t_evidence"), b.get("t_evidence"), tol):
            return False
    if is_chain and kind == "content":
        return _close(a.get("t_onset"), b.get("t_onset"), tol)
    return True


def _combine(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Agreed ratings -> one verdict. Times: the later of the two (conservative)."""
    r = {"label": a["label"]}
    for k in ("t_first_compliant", "t_evidence", "t_onset"):
        xs = [x[k] for x in (a, b) if x.get(k) is not None]
        if xs:
            r[k] = max(xs)
    if "onset_none" in a:
        r["onset_none"] = a["onset_none"] and b["onset_none"]
    r["t_review_start"] = min(a["t_review_start"], b["t_review_start"])
    r["t_review_end"] = max(a["t_review_end"], b["t_review_end"])
    return r


def _sig(ev: dict[str, Any]) -> tuple:
    return (ev["type"], ev.get("batch"), ev.get("item"), ev.get("step"), ev.get("annotator"))


def merge(batch_dir: Path, ratings: Sequence[tuple[Path, str]], *, arbiter: tuple[Path, str] | None = None,
          key_path: Path | None = None, tol_s: float = 1.0) -> dict[str, Any]:
    """Merge two independent ratings (+ optional arbiter) into the session logs.

    Appends every independent rating as a ``rating`` event, and one reconciled ``verdict``
    (source ``adjudicated``) per item/step only when the two raters agree (same label; times
    within ``tol_s``) or the arbiter labelled it. Content items also get an adjudicated
    ``speech_onset``. Unresolved and missing items are returned and written to
    ``unresolved.json`` next to the key. Idempotent per batch (re-running after arbitration
    appends only what is new). Any invalid label rejects the merge (``LabelError``)."""
    if len(ratings) != 2:
        raise ValueError("the primary outcome needs exactly two independent ratings (plus an optional arbiter)")
    if len({a for _, a in ratings} | ({arbiter[1]} if arbiter else set())) != len(ratings) + bool(arbiter):
        raise ValueError("annotator ids must be distinct (the arbiter is a third person)")
    key_path = Path(key_path) if key_path else default_key_path(batch_dir)
    _check_key_outside(batch_dir, key_path)
    key = json.loads(key_path.read_text(encoding="utf-8"))
    batch, items = key["batch"], key["items"]
    rs = [_load_ratings(p, a, items) for p, a in ratings]
    arb = _load_ratings(arbiter[0], arbiter[1], items) if arbiter else {}

    per_log: dict[str, list[dict[str, Any]]] = {}
    res: dict[str, Any] = {"agreed": 0, "arbitrated": 0, "unresolved": [], "missing": [], "appended": {}}
    pairs_lab: tuple[list[str], list[str]] = ([], [])
    keys = sorted(set(rs[0]) | set(rs[1]) | set(arb)
                  | {f"{i}/{s}" for i, inf in items.items() for s in range(int(inf["n_steps"]))})
    for k in keys:
        iid, step_s = k.split("/")
        step, info = int(step_s), items[iid]
        is_chain = info["type"] == "chain"
        base: dict[str, Any] = {"chain_id": info["chain_id"], "batch": batch, "item": iid, "step": step}
        a, b = rs[0].get(k), rs[1].get(k)
        for role, r in (("primary", a), ("primary", b), ("arbiter", arb.get(k))):
            if r is not None:
                ev = {"type": "rating", **base, "role": role, "revision": info["revision"],
                      **{x: y for x, y in r.items() if y is not None}}
                if not is_chain:
                    ev["claim_t"] = info["claim_t"]
                per_log.setdefault(info["log"], []).append(ev)
        if a is None or b is None:  # both independent ratings are required; an arbiter cannot replace one
            res["missing"].append(k)
            continue
        pairs_lab[0].append(a["label"])
        pairs_lab[1].append(b["label"])
        if _agree(a, b, info["kind"], is_chain, tol_s):
            v, how, who = _combine(a, b), "agreement", [a["annotator"], b["annotator"]]
            res["agreed"] += 1
        elif k in arb:
            v, how, who = dict(arb[k]), "arbitration", [a["annotator"], b["annotator"], arb[k]["annotator"]]
            res["arbitrated"] += 1
        else:
            res["unresolved"].append(k)
            continue
        ev = {"type": "verdict", "source": "adjudicated", **base, "label": v["label"],
              "annotators": who, "reconciliation": how, "criteria_sha256": info["criteria_sha256"],
              "t_review_start": v["t_review_start"], "t_review_end": v["t_review_end"]}
        for x in ("t_first_compliant", "t_evidence"):
            if v.get(x) is not None:
                ev[x] = v[x]
        if is_chain:
            ev["revision"] = info["revision"]
            if info["kind"] != "multistep":
                del ev["step"]
            if info["kind"] == "content":
                ev["onset_reviewed"] = True
                ev["t_onset"] = v.get("t_onset")
        else:
            ev["claim_t"] = info["claim_t"]
            del ev["step"]
            if info.get("claim_id") is not None:
                ev["claim_id"] = info["claim_id"]
        per_log.setdefault(info["log"], []).append(ev)
        if is_chain and info["kind"] == "content" and v.get("t_onset") is not None:
            per_log[info["log"]].append({"type": "speech_onset", "source": "adjudicated", "on_topic": True,
                                         "t": v["t_onset"], "chain_id": info["chain_id"], "batch": batch,
                                         "item": iid, "annotators": who})
    if pairs_lab[0]:
        res["kappa"] = stats.cohens_kappa(*pairs_lab, categories=VERDICT_LABELS)
    for log, evs in per_log.items():
        existing = set()
        with open(log, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    if e.get("batch") == batch:
                        existing.add(_sig(e))
        new = [e for e in evs if _sig(e) not in existing]
        with open(log, "a", encoding="utf-8") as f:
            for ev in new:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        res["appended"][Path(log).name] = len(new)
    (key_path.parent / "unresolved.json").write_text(
        json.dumps({"unresolved": res["unresolved"], "missing": res["missing"]}, indent=1), encoding="utf-8")
    return res


def _rating_arg(s: str) -> tuple[Path, str]:
    if ":" not in s:
        raise argparse.ArgumentTypeError("expected LABELS.json:ANNOTATOR")
    p, a = s.rsplit(":", 1)
    return Path(p), a


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("logs", nargs="+", type=Path)
    a.add_argument("-o", "--out", type=Path, required=True)
    a.add_argument("--key", type=Path, default=None, help="key path (default <out>.key/key.json)")
    a.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    a.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("merge")
    b.add_argument("batch_dir", type=Path)
    b.add_argument("ratings", nargs=2, type=_rating_arg, help="two LABELS.json:ANNOTATOR")
    b.add_argument("--arbiter", type=_rating_arg, default=None)
    b.add_argument("--key", type=Path, default=None)
    b.add_argument("--tol", type=float, default=1.0, help="time agreement tolerance (s)")
    args = p.parse_args()
    if args.cmd == "prepare":
        print(prepare(args.logs, args.out, args.seed, suite=args.suite, key_path=args.key))
    else:
        print(json.dumps(merge(args.batch_dir, args.ratings, arbiter=args.arbiter, key_path=args.key,
                               tol_s=args.tol), indent=1))


if __name__ == "__main__":
    main()

===== FILE: live_agent/eval/report.py =====
"""Markdown report from scored E2 sessions, per condition, with CIs (proposal v2.11 §7.7).

Usage::

    python -m live_agent.eval.report logs/*.jsonl -o report.md              # primary (adjudicated)
    python -m live_agent.eval.report logs/*.jsonl --source judge -o diag.md  # DIAGNOSTIC only

The primary report scores reconciled ``adjudicated`` verdicts only (D-014) and refuses to
run while any effective chain or completion claim lacks adjudication. ``--source`` other
than ``adjudicated`` produces a report headed DIAGNOSTIC, which is not a result.

Hypothesis tests use fixed, preregistered families (``FAMILIES``); Holm is applied over
the preregistered family size whatever subset is present or displayed. ``--compare`` only
selects which rows are displayed; pairs outside the families are shown as exploratory,
unadjusted, with no decision.

Every number in the output is *measured locally* from the given logs; thresholds quoted
from §8 are *proposed targets*.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence

from live_agent.eval import stats
from live_agent.eval.schema import load_session
from live_agent.eval.scoring import (
    ChainOutcome,
    IncompleteAdjudicationError,
    ScoringConfig,
    SessionScore,
    require_complete,
    score_session,
    summarize,
)

# Preregistered comparison families (proposal §5 RQ1 / §7.2). Difference = A - B.
PRIMARY_FAMILY: tuple[tuple[str, str], ...] = (("A2", "A1"),)  # H1a
H1C_FAMILY: tuple[tuple[str, str], ...] = (  # H1c ablations: each is expected to lower success
    ("A2", "A2-noqc"),
    ("A2", "A2-noledger"),
    ("A2", "A2-nomanifest"),
    ("A2", "A2-nocorrection"),
)
FAMILIES: dict[str, tuple[tuple[str, str], ...]] = {
    "primary (H1a)": PRIMARY_FAMILY,
    "secondary (H1c ablations)": H1C_FAMILY,
}


def _f(x: float | None, pct: bool = False, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.{nd + 1}f}"


def _ci(lo: float, hi: float, pct: bool = True) -> str:
    return f"[{_f(lo, pct)}, {_f(hi, pct)}]"


def _key(c: ChainOutcome) -> tuple[str, int, str]:
    return (c.task_id, c.seed, c.label)


def _rate_line(name: str, k: int, n: int, clusters: Sequence[str] | None = None,
               values: Sequence[float] | None = None, n_boot: int = 4000) -> str:
    if n == 0:
        return f"| {name} | 0/0 | n/a | n/a | n/a |"
    w = stats.wilson(k, n)
    boot = "n/a"
    if clusters is not None and values is not None and len(set(clusters)) > 1:
        b = stats.cluster_bootstrap_mean(values, clusters, n_boot=n_boot)
        boot = _ci(b["lo"], b["hi"])
    return f"| {name} | {k}/{n} | {_f(k / n, True)} | {_ci(*w)} | {boot} |"


def _claim_units(chains: Iterable[ChainOutcome]) -> tuple[list[str], list[float]]:
    """One unit per adjudicated claim (1 = false), clustered by task: the bootstrap of
    the pooled mean is then the task-clustered ratio estimator of FCR."""
    cl, xs = [], []
    for c in chains:
        n = c.n_claims - c.n_claims_unadjudicated
        cl += [c.task_id] * n
        xs += [1.0] * c.n_false_claims + [0.0] * (n - c.n_false_claims)
    return cl, xs


def condition_section(cond: str, sessions: list[SessionScore], n_boot: int = 4000) -> list[str]:
    chains = [c for s in sessions for c in s.chains]
    eff = [c for c in chains if c.in_primary]
    sm = summarize(chains)
    cl = [c.task_id for c in eff]
    L = [f"## Condition `{cond}`", ""]
    L.append(
        f"Sessions: {len(sessions)}; tasks: {len({s.task_id for s in sessions})}; "
        f"effective chains scored: {sm['n_effective']}; withdrawn chains (excluded): "
        f"{sm['n_withdrawn']}; insufficient observation (excluded, rerun): "
        f"{sm['n_insufficient_observation']}."
    )
    L += ["", "| Metric | k/n | Estimate | Wilson 95% CI | Task-clustered bootstrap 95% CI |",
          "|---|---|---|---|---|"]
    L.append(_rate_line("Instruction-level success (primary)", sm["n_success"], sm["n_effective"],
                        cl, [float(c.success) for c in eff], n_boot))
    unk = [c for c in eff if c.outcome.value != "unknown"]
    L.append(_rate_line("Success, excluding 'cannot tell' (sensitivity)",
                        sum(c.success for c in unk), len(unk),
                        [c.task_id for c in unk], [float(c.success) for c in unk], n_boot))
    L.append(_rate_line("Capacity-skip rate", sm["n_capacity_skipped"], sm["n_effective"],
                        cl, [float(c.outcome.value == "capacity_skipped") for c in eff], n_boot))
    L.append(_rate_line("Refusal / degradation rate", sm["n_refused_degraded"], sm["n_effective"],
                        cl, [float(c.outcome.value in ("refused", "degraded")) for c in eff], n_boot))
    served = [c for c in eff if c.served]
    L.append(_rate_line("Conditional success (served chains)", sum(c.success for c in served),
                        len(served), [c.task_id for c in served],
                        [float(c.success) for c in served], n_boot))
    content = [c for c in eff if c.kind == "content"]
    L.append(_rate_line("Content onset <= 15 s (reported separately)",
                        sum(bool(c.onset_ok) for c in content), len(content),
                        [c.task_id for c in content], [float(bool(c.onset_ok)) for c in content], n_boot))
    ccl, cx = _claim_units(chains)
    L.append(_rate_line("FCR (false / all audible completion claims, withdrawn chains incl.)",
                        sm["n_false_claims"], sm["n_claims"], ccl, cx, n_boot))
    L.append(_rate_line("Claim coverage (chains with >= 1 claim)",
                        sum(c.n_claims > 0 for c in eff), len(eff),
                        cl, [float(c.n_claims > 0) for c in eff], n_boot))
    for arm, r in sm["repair"].items():
        L.append(_rate_line(f"Repair rate, arm `{arm}` (RQ2, per failure point)", r["k"], r["n"]))

    # by kind
    L += ["", "**Success by chain kind**", "", "| Kind | k/n | Estimate | Wilson 95% CI |", "|---|---|---|---|"]
    by_kind: dict[str, list[ChainOutcome]] = defaultdict(list)
    for c in eff:
        by_kind[c.kind].append(c)
    for k, cs in sorted(by_kind.items()):
        kk, nn = sum(c.success for c in cs), len(cs)
        L.append(f"| {k} | {kk}/{nn} | {_f(kk / nn, True)} | {_ci(*stats.wilson(kk, nn))} |")
    L += ["", "Outcome counts: " + ", ".join(f"{k}={v}" for k, v in sm["outcomes"].items() if v)]
    rerun = [c for c in chains if c.outcome.value == "insufficient_observation"]
    if rerun:
        L.append("\nFlagged for rerun (deadline window not fully observed): "
                 + "; ".join(f"{c.session_id} {c.chain_id} ({c.missing})" for c in rerun))

    # repair offsets
    for arm, r in sm["repair"].items():
        L.append(f"Repair `{arm}`: earliest eligible request offset j-k = {r['offsets']}")

    # time-to-event
    L += ["", "**Time to event (Kaplan-Meier, right-censored at D)**", "",
          "| Measure | n | events | deadline success | KM median (s) | RMST to horizon (s) |",
          "|---|---|---|---|---|---|"]

    def km_row(name: str, ts: list[float], es: list[bool], H: float) -> None:
        km = stats.kaplan_meier(ts, es)
        med = km.median
        L.append(f"| {name} | {len(ts)} | {sum(es)} | {_f(sum(es) / len(ts), True)} | "
                 f"{_f(med) if med is not None else f'> {H:g}'} | {_f(km.rmst(H))} (H={H:g}) |")

    act = [c for c in eff if c.tvc is not None]
    if act:
        km_row("TVC (action chains)", [c.tvc for c in act], [c.tvc_event for c in act],
               max(c.deadline_s for c in act))
    tf = [c for c in eff if c.tfmr is not None]
    if tf:
        km_row("TFMR (on-topic speech onset)", [c.tfmr for c in tf], [c.tfmr_event for c in tf],
               max(c.tfmr for c in tf))
    tts = [c for c in eff if not c.competing_failure]
    if tts:
        km_row("Time to success, all kinds (excl. order_fail)", [c.time_to_success for c in tts],
               [c.success_event for c in tts], max(c.deadline_s for c in tts))
    n_order = sum(c.competing_failure for c in eff)
    if n_order:
        L.append(f"\n{n_order} multistep chain(s) failed deterministically by step order "
                 "(order_fail): a competing failure, not right-censoring, so they are left "
                 "out of the time-to-success KM row (they count as failures in every rate).")

    # latencies
    va = [x for s in sessions for x in s.visual_ack_s]
    bi = [x for s in sessions for x in s.barge_in_stop_s]
    miss = sum(s.barge_ins_without_stop for s in sessions)
    L += ["", "**Latency (s; p50 / p95 / p99)**", "", "| Measure | n | p50 | p95 | p99 |", "|---|---|---|---|---|"]
    for name, xs in (("Visual acknowledgement", va), ("Barge-in playback stop (client)", bi)):
        p = stats.percentiles(xs)
        L.append(f"| {name} | {len(xs)} | {_f(p['p50'], nd=2)} | {_f(p['p95'], nd=2)} | {_f(p['p99'], nd=2)} |")
    if miss:
        L.append(f"\nBarge-ins with no playback stop: {miss}.")
    if len(sessions) and min(len(xs) for xs in (va, bi)) < 3:
        L.append("\nFewer than 3 latency repetitions in at least one row: treat percentiles as indicative.")
    return L + [""]


def _paired(by_cond: dict[str, list[SessionScore]], a: str, b: str, n_boot: int,
            conf: float = 0.95) -> dict | None:
    if a not in by_cond or b not in by_cond:
        return None
    ca = {_key(c): c for s in by_cond[a] for c in s.chains if c.in_primary}
    cb = {_key(c): c for s in by_cond[b] for c in s.chains if c.in_primary}
    keys = sorted(set(ca) & set(cb))
    if not keys:
        return None
    xa = [float(ca[k].success) for k in keys]
    xb = [float(cb[k].success) for k in keys]
    cl = [k[0] for k in keys]
    r = stats.cluster_bootstrap_diff(xa, xb, cl, n_boot=n_boot)
    if conf != 0.95:
        s = stats.cluster_bootstrap_diff(xa, xb, cl, n_boot=n_boot, conf=conf)
        r["slo"], r["shi"] = s["lo"], s["hi"]
    else:
        r["slo"], r["shi"] = r["lo"], r["hi"]
    r["n"] = len(keys)
    r["unpaired"] = len(set(ca) ^ set(cb))
    return r


def compare(
    by_cond: dict[str, list[SessionScore]],
    display: Iterable[tuple[str, str]] | None = None,
    n_boot: int = 4000,
    alpha: float = 0.05,
) -> list[str]:
    """Preregistered families, Holm over the preregistered family size. ``display``
    (default: every family member present) only selects the rows shown; it never changes
    the family or the adjustment. Displayed pairs outside the families are exploratory."""
    display = list(display) if display is not None else None
    fam_pairs = {p for fam in FAMILIES.values() for p in fam}
    L = ["## Paired comparisons (instruction-level success; cluster = task)", "",
         (f"Families are fixed before data collection; Holm is applied over the preregistered "
          f"family size (alpha = {alpha}); family members not run count as p = 1. "
          "The simultaneous CI is Bonferroni at 1 - alpha/m."), ""]
    unp = []
    for name, fam in FAMILIES.items():
        m = len(fam)
        res = {p: _paired(by_cond, *p, n_boot=n_boot, conf=1 - alpha / m) for p in fam}
        tested = [p for p in fam if res[p] is not None]
        adj = dict(zip(tested, stats.holm([res[p]["p_value"] for p in tested], alpha, m=m)["adjusted"]))
        shown = [p for p in fam if (display is None and res[p] is not None)
                 or (display is not None and p in display)]
        L += [f"**Family: {name}** (m = {m}; tested: {len(tested)})", "",
              ("| Comparison | paired chains | difference | 95% CI | simultaneous CI | bootstrap p "
               "| Holm-adjusted p | decision (Holm) |"),
              "|---|---|---|---|---|---|---|---|"]
        for a, b in shown:
            r = res[(a, b)]
            if r is None:
                L.append(f"| {a} - {b} | 0 | n/a | n/a | n/a | n/a | n/a | not tested |")
                continue
            p_adj = adj[(a, b)]
            dec = ("reject H0" + (" (A > B)" if r["estimate"] > 0 else " (A < B)")) if p_adj <= alpha \
                else "do not reject"
            L.append(f"| {a} - {b} | {r['n']} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} | "
                     f"{_ci(r['slo'], r['shi'])} | {r['p_value']:.4f} | {p_adj:.4f} | {dec} |")
            if r["unpaired"]:
                unp.append(f"{a}-{b}: {r['unpaired']}")
        L.append("")
    extra = [p for p in (display or []) if tuple(p) not in fam_pairs]
    if extra:
        L += ["**Exploratory (not preregistered; unadjusted, no decision)**", "",
              "| Comparison | paired chains | difference | 95% CI | bootstrap p |", "|---|---|---|---|---|"]
        for a, b in extra:
            r = _paired(by_cond, a, b, n_boot=n_boot)
            if r is None:
                L.append(f"| {a} - {b} | 0 | n/a | n/a | n/a |")
                continue
            L.append(f"| {a} - {b} | {r['n']} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} | "
                     f"{r['p_value']:.4f} |")
            if r["unpaired"]:
                unp.append(f"{a}-{b}: {r['unpaired']}")
        L.append("")
    if unp:
        L.append("Chains present in only one condition (dropped from pairing): " + "; ".join(unp))
    L.append("\nH1a target (*proposed target*, §8): A2 - A1 >= +10 pp with the paired CI excluding 0.")
    return L + [""]


def repair_comparison(by_cond: dict[str, list[SessionScore]], n_boot: int = 4000) -> list[str]:
    """RQ2: arms randomised per eligible failure point within a condition (e.g. A2-rq2);
    the unit is the failure point, clustered by task."""
    L = []
    for cond, ss in sorted(by_cond.items()):
        rep = [(c.task_id, r) for s in ss for c in s.chains if c.in_primary for r in c.repairs]
        arms = {r["arm"] for _, r in rep}
        if arms != {"forward_correction", "repeat"}:
            continue
        r = stats.cluster_bootstrap_rate_diff(
            [float(bool(x["success"])) for _, x in rep],
            [x["arm"] == "forward_correction" for _, x in rep],
            [t for t, _ in rep],
            n_boot=n_boot,
        )
        L.append(f"| {cond} | {len(rep)} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} |")
    if not L:
        return []
    return ["## RQ2 repair: forward correction - repeat (earliest eligible request)", "",
            "| Condition | assigned failure points | difference | 95% CI (task-clustered) |",
            "|---|---|---|---|", *L, ""]


def build_report(
    sessions: list[SessionScore],
    pairs: Sequence[tuple[str, str]] | None = None,
    title: str = "E2 evaluation report",
    n_boot: int = 4000,
) -> str:
    """``pairs`` selects displayed comparisons (None = all preregistered ones present).
    Raises ``IncompleteAdjudicationError`` for a primary report with adjudication gaps."""
    require_complete(sessions)
    diagnostic = any(s.diagnostic for s in sessions)
    by_cond: dict[str, list[SessionScore]] = defaultdict(list)
    for s in sessions:
        by_cond[s.condition].append(s)
    L = []
    if diagnostic:
        srcs = sorted({x for s in sessions for x in s.sources})
        title = f"DIAGNOSTIC — {title}"
        L += [f"# {title}", "",
              (f"> **DIAGNOSTIC, NOT A RESULT.** Scored from verdict source(s) {srcs}, not from "
               "reconciled blinded adjudication (D-014). Chains without such verdicts count as "
               "never complied, speech onsets may be unverified scripted lines, and conditions "
               "without an online judge (A1) cannot be compared here."), ""]
    else:
        L += [f"# {title}", ""]
    L += [("All values *measured locally* from the session logs below; thresholds are *proposed "
           "targets* (proposal v2.11 §8). Primary denominator = effective intent chains (final "
           "intent not withdrawn, capacity-skipped included), minus chains whose deadline window "
           "was not fully observed (counted, flagged for rerun). 'Cannot tell' counts as failure "
           "in the primary analysis."), ""]
    L += ["| Condition | sessions | effective chains | success | Wilson 95% CI | insufficient observation |",
          "|---|---|---|---|---|---|"]
    for cond, ss in sorted(by_cond.items()):
        sm = summarize([c for s in ss for c in s.chains])
        L.append(f"| {cond} | {len(ss)} | {sm['n_effective']} | {_f(sm['success_rate'], True)} | "
                 f"{_ci(*stats.wilson(sm['n_success'], sm['n_effective']))} | "
                 f"{sm['n_insufficient_observation']} |")
    L.append("")
    L += compare(by_cond, pairs, n_boot=n_boot)
    L += repair_comparison(by_cond, n_boot=n_boot)
    for cond, ss in sorted(by_cond.items()):
        L += condition_section(cond, ss, n_boot=n_boot)
    return "\n".join(L)


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--compare", action="append", default=None,
                    help="COND_A:COND_B (A - B): select displayed rows; does not change the "
                         "preregistered families or their Holm adjustment")
    ap.add_argument("--source", action="append", default=None, choices=("adjudicated", "human", "judge"),
                    help="verdict source preference (default: adjudicated only = primary). Any "
                         "other choice produces a DIAGNOSTIC report")
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args(argv)
    if args.source and tuple(args.source) != ("adjudicated",):
        cfg = ScoringConfig.diagnostic_config(tuple(args.source))
    else:
        cfg = ScoringConfig()
    scores = [score_session(load_session(p), cfg) for p in args.logs]
    pairs = [tuple(p.split(":", 1)) for p in args.compare] if args.compare else None
    try:
        md = build_report(scores, pairs, n_boot=args.n_boot)
    except IncompleteAdjudicationError as e:
        print(f"error: {e}\n(use --source judge for a DIAGNOSTIC report)", file=sys.stderr)
        raise SystemExit(2) from e
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md + "\n")
    else:
        print(md)


if __name__ == "__main__":
    main()

===== FILE: live_agent/memory/store.py =====
"""SQLite-backed long-term memory service (proposal §5.6, evaluated by E3 §7.3).

One DB file per deployment. Tables:

``records``        every stored record (all kinds), bi-temporal fields for facts.
``record_scopes``  one row per element of a record's ``source_scopes`` (the SQL filter key).
``derivations``    ``derived_from`` edges (child -> parent) for invalidation / erasure cascades.
``embeddings``     one vector per record (pluggable :class:`Embedder`).
``tombstones``     erasure ledger: only (sha256 of id, time, reason code).
``generated_event_log`` (VIEW) everything the persona said / showed.

Invariants enforced here (not by callers):

* Persona output is only ever a ``generated_event``; it is never promoted to a user fact.
* Only ``own_assertion`` sentences from the user become facts; candidates that echo an
  earlier generated event are held ``pending`` until :meth:`MemoryStore.confirm`.
* Retrieval filters on ``source_scopes`` *before* ranking; public mode can never read a
  record with any private source scope.
* Canon records may only derive from canon and are immutable (SQL triggers).
* Episodes are append-only (text cannot be updated); erasure physically deletes rows
  with ``PRAGMA secure_delete=ON`` so the bytes are overwritten in the file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import sqlite3
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..types import Utterance, new_id
from .embed import Embedder, HashingEmbedder
from .extract import CandidateFact, Extractor, RuleExtractor, sanitize
from .schema import (
    CANON,
    CLAIM_PRIORITY,
    ClaimType,
    Kind,
    Provenance,
    Record,
    Status,
    is_private,
    is_single_valued,
    private_scope,
    public_scope,
    union_scopes,
    validate_scope,
)
from .summarize import ExtractiveSummarizer, Summarizer

log = logging.getLogger("live_agent.memory")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    text TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    t REAL NOT NULL,
    created_at REAL NOT NULL,
    subject TEXT, predicate TEXT, value TEXT,
    valid_from REAL, valid_to REAL,
    confidence REAL NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL,
    echo INTEGER NOT NULL DEFAULT 0,
    importance REAL NOT NULL DEFAULT 0.5,
    immutable INTEGER NOT NULL DEFAULT 0,
    provenance TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS records_kind ON records(kind, status);
CREATE INDEX IF NOT EXISTS records_sp ON records(subject, predicate);
CREATE INDEX IF NOT EXISTS records_session ON records(session_id);
CREATE INDEX IF NOT EXISTS records_owner ON records(owner);
CREATE INDEX IF NOT EXISTS records_t ON records(t);
CREATE TABLE IF NOT EXISTS record_scopes (
    record_id TEXT NOT NULL, scope TEXT NOT NULL, PRIMARY KEY (record_id, scope)
);
CREATE INDEX IF NOT EXISTS record_scopes_scope ON record_scopes(scope);
CREATE TABLE IF NOT EXISTS derivations (
    child_id TEXT NOT NULL, parent_id TEXT NOT NULL, PRIMARY KEY (child_id, parent_id)
);
CREATE INDEX IF NOT EXISTS derivations_parent ON derivations(parent_id);
CREATE TABLE IF NOT EXISTS embeddings (
    record_id TEXT PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS tombstones (
    id_hash TEXT NOT NULL, t REAL NOT NULL, reason TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS generated_event_log AS
    SELECT id, text, scope, session_id, t, provenance FROM records WHERE kind = 'generated_event';
CREATE TRIGGER IF NOT EXISTS immutable_no_update BEFORE UPDATE ON records
    WHEN OLD.immutable = 1 BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS immutable_no_delete BEFORE DELETE ON records
    WHEN OLD.immutable = 1 BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS log_append_only BEFORE UPDATE OF text, scope, provenance ON records
    WHEN OLD.kind IN ('episode', 'generated_event') BEGIN SELECT RAISE(ABORT, 'append-only'); END;
"""

_DEFAULT_IMPORTANCE = {
    Kind.USER_FACT: 0.8,
    Kind.LEDGER: 0.7,
    Kind.SUMMARY: 0.6,
    Kind.PROCEDURAL: 0.5,
    Kind.EPISODE: 0.4,
    Kind.GENERATED_EVENT: 0.3,
    Kind.CANDIDATE_BELIEF: 0.2,
}
_KIND_PREFIX = {
    Kind.USER_FACT: "fact", Kind.EPISODE: "ep", Kind.LEDGER: "led", Kind.GENERATED_EVENT: "gen",
    Kind.CANDIDATE_BELIEF: "bel", Kind.PROCEDURAL: "proc", Kind.SUMMARY: "sum",
}


class ImmutableRecordError(RuntimeError):
    pass


class ScopeViolationError(ValueError):
    """A write would widen visibility: e.g. a public record with a private input, a user
    fact in canon, or a record mixing two users' private scopes. Callers must not retry
    the write in a wider scope."""


class ErasureIncompleteError(RuntimeError):
    """Raised by :meth:`ErasureReport.raise_if_incomplete` when not every purge target acked."""


@dataclass
class IngestResult:
    episode: Record | None
    facts: list[Record] = field(default_factory=list)  # stored (active or pending) fact records
    skipped: list[tuple[CandidateFact, str]] = field(default_factory=list)  # (candidate, reason)
    generated_event: Record | None = None  # set when a persona utterance was routed here


@dataclass
class Hit:
    record: Record
    score: float
    relevance: float
    recency: float
    importance: float

    @property
    def tags(self) -> dict[str, Any]:
        return self.record.tags


@dataclass
class RetrievalResult:
    hits: list[Hit]
    elapsed_ms: float
    scanned: int
    truncated: bool  # budget exhausted before all eligible candidates were scored

    def __iter__(self):
        return iter(self.hits)

    def __len__(self) -> int:
        return len(self.hits)

    @property
    def records(self) -> list[Record]:
        return [h.record for h in self.hits]


@dataclass
class Resolution:
    subject: str
    predicate: str
    value: str | None
    record: Record | None
    alternatives: list[Record]  # lower-priority / older active claims
    pending: list[Record]  # echo or conflicting candidates awaiting confirmation

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.pending)


@dataclass
class PurgeAck:
    ok: bool
    detail: str = ""


@dataclass
class ErasureVerification:
    """Structured result of :meth:`MemoryStore.verify_erased`; ``ok`` iff every failing list is empty.

    ``foreign_hits`` (term found in another user's private records or in canon-only
    records) is informational: those rows are not this user's to erase.
    """

    surviving: list[str] = field(default_factory=list)  # deleted ids still present / referenced
    missing_tombstones: list[str] = field(default_factory=list)  # deleted ids without a tombstone
    term_hits: list[str] = field(default_factory=list)  # term residue in erasable records (any scope)
    orphans: list[str] = field(default_factory=list)  # index / embedding / edge rows without a record
    file_hits: list[str] = field(default_factory=list)  # term bytes still in the DB file(s)
    foreign_hits: list[str] = field(default_factory=list)  # informational only

    @property
    def hits(self) -> list[str]:
        return [*self.surviving, *self.missing_tombstones, *self.term_hits, *self.orphans, *self.file_hits]

    @property
    def ok(self) -> bool:
        return not self.hits


MEMORY_DB_TARGET = "memory_db"


@dataclass
class ErasureReport:
    """Result of :meth:`MemoryStore.forget`; passed to purge hooks.

    ``terms`` are held in memory only (never persisted) so hooks can scrub LLM prompt
    caches, unsent BlockScripts and recordings; ``sessions`` tells which generator / LLM
    sessions to restart from canon anchors.

    Erasure is **complete** only when every name in ``required_targets`` has an ok
    acknowledgement in ``acks`` (the store acks ``memory_db`` itself after verifying the
    deletion), and no hook raised. Anything else is a failed erasure: the caller must
    report it as failed and retry the missing purges. Deleted records stay deleted.
    Asynchronous purges (generator reset, recordings) ack later via :meth:`acknowledge`.
    """

    user_id: str
    reason: str
    t: float
    deleted_ids: list[str]
    kinds: dict[str, int]
    sessions: set[str]
    terms: set[str]
    regenerated: list[str] = field(default_factory=list)  # new summary ids
    hook_errors: list[str] = field(default_factory=list)
    required_targets: list[str] = field(default_factory=list)
    acks: dict[str, PurgeAck] = field(default_factory=dict)
    verification: ErasureVerification | None = None

    def acknowledge(self, target: str, ok: bool = True, detail: str = "") -> None:
        if target not in self.required_targets:
            self.required_targets.append(target)
        prev = self.acks.get(target)
        if prev is not None and not prev.ok and ok:
            detail = f"{detail} (after earlier failure: {prev.detail})".strip()
        self.acks[target] = PurgeAck(bool(ok), detail)

    @property
    def pending_targets(self) -> list[str]:
        return [t for t in self.required_targets if not (t in self.acks and self.acks[t].ok)]

    @property
    def complete(self) -> bool:
        return not self.pending_targets

    def raise_if_incomplete(self) -> None:
        if not self.complete:
            raise ErasureIncompleteError(
                f"erasure not complete; pending purge targets: {self.pending_targets}; errors: {self.hook_errors}")


def _hook_name(hook: Callable[..., Any]) -> str:
    return str(getattr(hook, "purge_target", None) or getattr(hook, "__qualname__", None) or repr(hook))


class _RateLimiter:
    def __init__(self, max_events: int, window_s: float, clock: Callable[[], float]) -> None:
        self.max_events, self.window_s, self.clock = max_events, window_s, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        q = self._events[key]
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.max_events:
            return False
        q.append(now)
        return True


class MemoryStore:
    """Long-term memory for one deployment. Not thread-safe; use one instance per process."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        embedder: Embedder | None = None,
        extractor: Extractor | None = None,
        clock: Callable[[], float] = time.time,
        echo_threshold: float = 0.5,
        echo_lexical_floor: float = 0.4,
        viewer_rate: tuple[int, float] = (5, 10.0),
        viewer_max_len: int = 200,
        recency_tau_s: float = 3 * 86400.0,
        weights: tuple[float, float, float] = (0.6, 0.2, 0.2),
    ) -> None:
        self.path = str(path)
        self.embedder: Embedder = embedder or HashingEmbedder()
        self.extractor: Extractor = extractor or RuleExtractor()
        self.clock = clock
        self.echo_threshold = echo_threshold
        self.echo_lexical_floor = echo_lexical_floor
        self.viewer_max_len = viewer_max_len
        self.recency_tau_s = recency_tau_s
        self.weights = weights
        self._viewer_limiter = _RateLimiter(viewer_rate[0], viewer_rate[1], clock)
        self.stats: dict[str, int] = defaultdict(int)
        # hooks: erasure -> external caches; stale -> summary regeneration etc.
        # Every erasure hook is a *required* purge target: it must return a truthy ack
        # (True / non-empty detail string); None, False or an exception leaves the
        # erasure incomplete (see ErasureReport.complete). Name a hook by setting
        # ``hook.purge_target = "<name>"`` or use :meth:`register_purge_target`.
        self.erasure_hooks: list[Callable[[ErasureReport], Any]] = []
        self.required_purge_targets: set[str] = set()  # must ack, even without a hook
        self.purge_hooks: dict[str, Callable[[ErasureReport], Any]] = {}
        self.stale_hooks: list[Callable[[list[Record]], None]] = []
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ low level

    def add_record(
        self,
        kind: Kind,
        scope: str,
        text: str,
        claim_type: ClaimType,
        provenance: Provenance,
        *,
        derived_from: Sequence[str] = (),
        subject: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        valid_from: float | None = None,
        confidence: float = 1.0,
        status: Status = Status.ACTIVE,
        echo: bool = False,
        importance: float | None = None,
        immutable: bool = False,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Record:
        """Insert one record; computes ``source_scopes`` from its parents and embeds it."""
        validate_scope(scope)
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        source_scopes = union_scopes(scope, parents)
        self._check_write_scope(kind, scope, source_scopes, provenance)
        if kind == Kind.GENERATED_EVENT and claim_type == ClaimType.OWN_ASSERTION:
            raise ValueError("generated events are never user assertions")
        now = self.clock()
        owner = provenance.user_id or next((p.provenance.user_id for p in parents if p.provenance.user_id), "")
        provenance.user_id = owner
        if not provenance.timestamp:
            provenance.timestamp = now
        if kind == Kind.USER_FACT and valid_from is None:
            valid_from = provenance.timestamp
        rec = Record(
            id=new_id(_KIND_PREFIX[kind]), kind=kind, scope=scope, source_scopes=source_scopes,
            claim_type=claim_type, text=text, provenance=provenance,
            derived_from=tuple(p.id for p in parents), created_at=now, subject=subject,
            predicate=predicate, value=value, valid_from=valid_from, valid_to=None,
            confidence=confidence, status=status, echo=echo,
            importance=_DEFAULT_IMPORTANCE[kind] if importance is None else importance,
            immutable=immutable, meta=dict(meta or {}),
        )
        self.db.execute(
            "INSERT INTO records (id, kind, scope, claim_type, text, owner, session_id, t, created_at,"
            " subject, predicate, value, valid_from, valid_to, confidence, status, echo, importance,"
            " immutable, provenance, meta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.id, kind.value, scope, claim_type.value, text, owner, provenance.session_id,
                provenance.timestamp, now, subject, predicate, value, valid_from, None, confidence,
                status.value, int(echo), rec.importance, int(immutable), provenance.to_json(),
                json.dumps(rec.meta, ensure_ascii=False),
            ),
        )
        self.db.executemany(
            "INSERT INTO record_scopes (record_id, scope) VALUES (?, ?)",
            [(rec.id, s) for s in sorted(source_scopes)],
        )
        self.db.executemany(
            "INSERT INTO derivations (child_id, parent_id) VALUES (?, ?)",
            [(rec.id, p.id) for p in parents],
        )
        vec = self.embedder.embed([self._embed_text(rec)])[0].astype(np.float32)
        self.db.execute(
            "INSERT INTO embeddings (record_id, model, vec) VALUES (?, ?, ?)",
            (rec.id, self.embedder.name, vec.tobytes()),
        )
        if commit:
            self.db.commit()
        return rec

    @staticmethod
    def _check_write_scope(kind: Kind, scope: str, source_scopes: frozenset[str], prov: Provenance) -> None:
        """Fail-closed scope rules for every write (review findings 12/13)."""
        if scope == CANON:
            if source_scopes != {CANON}:
                raise ScopeViolationError("canon records may only derive from canon records")
            if kind not in (Kind.LEDGER, Kind.PROCEDURAL):
                raise ScopeViolationError(f"{kind.value} records can never be canon")
            if prov.user_id or prov.speaker in ("user", "agent") or prov.speaker.startswith("viewer:"):
                raise ScopeViolationError("user / viewer / agent-origin records can never be canon")
        privs = {s for s in source_scopes if is_private(s)}
        if scope.startswith("public:") and privs:
            raise ScopeViolationError(f"public write {scope!r} has private inputs {sorted(privs)}")
        if len(privs) > 1 or (is_private(scope) and privs - {scope}):
            raise ScopeViolationError(f"record would mix private scopes {sorted(privs | {scope})}")

    def existing_ids(self, ids: Iterable[str]) -> list[str]:
        """The subset of ``ids`` that still exist (order kept)."""
        ids = list(dict.fromkeys(ids))
        have: set[str] = set()
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            have |= set(self._ids(f"SELECT id FROM records WHERE id IN ({','.join('?' * len(chunk))})", chunk))
        return [i for i in ids if i in have]

    def register_purge_target(self, name: str, hook: Callable[[ErasureReport], Any] | None = None) -> None:
        """Declare an external store (recordings, generator state, LLM KV ...) that must
        acknowledge every erasure. With ``hook`` it is called synchronously and must return
        a truthy ack; without, the owner acks later via :meth:`ErasureReport.acknowledge`."""
        self.required_purge_targets.add(name)
        if hook is not None:
            self.purge_hooks[name] = hook

    @staticmethod
    def _embed_text(rec: Record) -> str:
        if rec.subject and rec.predicate and rec.value:
            return f"{rec.text} {rec.value}"
        return rec.text

    def get(self, record_id: str) -> Record | None:
        recs = self._load([record_id])
        return recs[0] if recs else None

    def _require(self, record_id: str) -> Record:
        rec = self.get(record_id)
        if rec is None:
            raise KeyError(record_id)
        return rec

    def _load(self, ids: Sequence[str]) -> list[Record]:
        if not ids:
            return []
        out: dict[str, Record] = {}
        for chunk_start in range(0, len(ids), 500):
            chunk = list(ids[chunk_start:chunk_start + 500])
            q = ",".join("?" * len(chunk))
            rows = self.db.execute(f"SELECT * FROM records WHERE id IN ({q})", chunk).fetchall()
            scopes: dict[str, set[str]] = defaultdict(set)
            for r in self.db.execute(f"SELECT record_id, scope FROM record_scopes WHERE record_id IN ({q})", chunk):
                scopes[r[0]].add(r[1])
            parents: dict[str, list[str]] = defaultdict(list)
            for r in self.db.execute(
                f"SELECT child_id, parent_id FROM derivations WHERE child_id IN ({q}) ORDER BY rowid", chunk
            ):
                parents[r[0]].append(r[1])
            for row in rows:
                out[row["id"]] = self._row_to_record(row, scopes[row["id"]], parents[row["id"]])
        return [out[i] for i in ids if i in out]

    @staticmethod
    def _row_to_record(row: sqlite3.Row, scopes: set[str], parents: list[str]) -> Record:
        return Record(
            id=row["id"], kind=Kind(row["kind"]), scope=row["scope"], source_scopes=frozenset(scopes),
            claim_type=ClaimType(row["claim_type"]), text=row["text"],
            provenance=Provenance.from_json(row["provenance"]), derived_from=tuple(parents),
            created_at=row["created_at"], subject=row["subject"], predicate=row["predicate"],
            value=row["value"], valid_from=row["valid_from"], valid_to=row["valid_to"],
            confidence=row["confidence"], status=Status(row["status"]), echo=bool(row["echo"]),
            importance=row["importance"], immutable=bool(row["immutable"]), meta=json.loads(row["meta"]),
        )

    def _ids(self, sql: str, params: Sequence[Any] = ()) -> list[str]:
        return [r[0] for r in self.db.execute(sql, params)]

    def _set_status(self, record_id: str, status: Status, **cols: Any) -> None:
        sets = ["status = ?"] + [f"{c} = ?" for c in cols]
        try:
            self.db.execute(
                f"UPDATE records SET {', '.join(sets)} WHERE id = ?", [status.value, *cols.values(), record_id]
            )
        except sqlite3.IntegrityError as e:
            raise ImmutableRecordError(record_id) from e

    def _update_meta(self, record_id: str, **kv: Any) -> None:
        rec = self._require(record_id)
        rec.meta.update(kv)
        self.db.execute("UPDATE records SET meta = ? WHERE id = ?", (json.dumps(rec.meta, ensure_ascii=False), record_id))

    # ------------------------------------------------------------------ scope helpers

    @staticmethod
    def _scope_filter_sql(mode: str, user_id: str | None, stream_id: str | None) -> tuple[str, list[Any]]:
        """SQL predicate over ``rs.scope`` that is TRUE for readable scopes."""
        if mode == "private":
            if not user_id:
                raise ValueError("private mode requires user_id")
            return "(rs.scope = 'canon' OR rs.scope = ? OR rs.scope LIKE 'public:%')", [private_scope(user_id)]
        if mode == "public":
            if stream_id:
                return "(rs.scope = 'canon' OR rs.scope = ?)", [public_scope(stream_id)]
            return "(rs.scope = 'canon' OR rs.scope LIKE 'public:%')", []
        raise ValueError(f"unknown mode {mode!r}; expected 'private' or 'public'")

    @staticmethod
    def scope_readable(scopes: Iterable[str], mode: str, user_id: str | None, stream_id: str | None) -> bool:
        """Python mirror of the SQL filter (defence in depth)."""
        for s in scopes:
            if s == CANON:
                continue
            if mode == "private" and (s == private_scope(user_id or "") or s.startswith("public:")):
                continue
            if mode == "public" and (s == public_scope(stream_id) if stream_id else s.startswith("public:")):
                continue
            return False
        return True

    @staticmethod
    def session_write_scope(mode: str | None, user_id: str, stream_id: str | None) -> str:
        """Write scope of an authenticated session: ``private:<user>`` for a 1:1 session
        (also the fail-closed default when the mode is unknown), ``public:<stream>`` for a
        livestream. Never canon; never taken from a client-supplied utterance field."""
        if mode in (None, "", "private"):
            return private_scope(user_id)
        if mode == "public":
            if not stream_id:
                raise ValueError("public session requires stream_id")
            return public_scope(stream_id)
        raise ScopeViolationError(f"session mode {mode!r} cannot be a write scope (expected private/public)")

    def _utterance_scope(self, utt: Utterance, user_id: str, stream_id: str | None, mode: str | None) -> str:
        scope = self.session_write_scope(mode, user_id, stream_id)
        claimed = (utt.scope or "").strip()
        if claimed and claimed not in (scope, mode or "private"):
            # The utterance's own scope field is client data: ignored, but counted and logged.
            self.stats["utterance_scope_ignored"] += 1
            log.warning("utterance %s claims scope %r; using session scope %r", utt.uid, claimed, scope)
        return scope

    # ------------------------------------------------------------------ write policy

    def ingest_user_utterance(
        self,
        utt: Utterance,
        extractor: Extractor | None = None,
        *,
        user_id: str,
        stream_id: str | None = None,
        mode: str | None = None,
    ) -> IngestResult:
        """Append the turn to the episode log and store candidate facts per the write policy.

        The write scope comes from the authenticated session ``mode`` ("private" /
        "public"; ``None`` = private), never from ``utt.scope``; canon is refused.
        Persona utterances are routed to the generated-event log (lineage unknown);
        viewer utterances to :meth:`ingest_viewer_chat`. Only ``own_assertion``
        sentences produce facts.
        """
        ex = extractor or self.extractor
        scope = self._utterance_scope(utt, user_id, stream_id, mode)
        if utt.speaker == "persona":
            gen = self.record_generated_event(utt.text, utt.session_id, scope, source_id=utt.uid, user_id=user_id,
                                              derived_from=None)
            return IngestResult(episode=None, generated_event=gen)
        if utt.speaker.startswith("viewer:"):
            if not stream_id:
                raise ValueError("viewer chat requires stream_id")
            ep = self.ingest_viewer_chat(utt.text, utt.speaker.split(":", 1)[1], stream_id,
                                         session_id=utt.session_id, source_id=utt.uid)
            return IngestResult(episode=ep)

        prov = lambda: Provenance(
            source_id=utt.uid, speaker="user", session_id=utt.session_id, timestamp=self.clock(),
            extractor_version=ex.version, user_id=user_id,
        )
        episode = self.add_record(
            Kind.EPISODE, scope, utt.text, ex.classify(utt.text), prov(),
            meta={"t_end": utt.t_end}, commit=False,
        )
        result = IngestResult(episode=episode)
        for cand in ex.extract(utt.text):
            if cand.claim_type != ClaimType.OWN_ASSERTION:
                result.skipped.append((cand, cand.claim_type.value))
                continue
            if not (cand.subject and cand.predicate and cand.value):
                result.skipped.append((cand, "incomplete"))
                continue
            rec = self._store_user_fact(cand, scope, user_id, episode, prov())
            if rec is None:
                result.skipped.append((cand, "duplicate"))
            else:
                result.facts.append(rec)
        self.db.commit()
        return result

    def _abs_subject(self, subject: str, user_id: str) -> str:
        if subject.startswith(("user:", "viewer:", "persona")):
            return subject
        if subject == "user":
            return f"user:{user_id}"
        if subject.startswith("user/"):
            return f"user:{user_id}/{subject[5:]}"
        return subject

    def _store_user_fact(
        self, cand: CandidateFact, scope: str, user_id: str, episode: Record, prov: Provenance
    ) -> Record | None:
        subject = self._abs_subject(cand.subject or "user", user_id)
        echo_ids = self._echo_matches(cand.text, cand.value or "", user_id)
        derived = [episode.id, *echo_ids]
        meta: dict[str, Any] = {}
        status = Status.ACTIVE
        current = self._current_facts(subject, cand.predicate or "", user_id, claim=ClaimType.OWN_ASSERTION)
        same = [r for r in current if _norm(r.value) == _norm(cand.value)]
        if same:
            return None  # already asserted by the user: no duplicate
        if echo_ids:
            status = Status.PENDING
            meta["echo_of"] = echo_ids
        different = [r for r in current if _norm(r.value) != _norm(cand.value)]
        if status == Status.ACTIVE and different and is_single_valued(cand.predicate):
            if cand.correction:
                meta["supersedes"] = [r.id for r in different]
                self._supersede(different)
            else:
                status = Status.PENDING
                meta["conflict_with"] = [r.id for r in different]
        elif echo_ids and different and is_single_valued(cand.predicate):
            meta["conflict_with"] = [r.id for r in different]
        return self.add_record(
            Kind.USER_FACT, scope, cand.text, ClaimType.OWN_ASSERTION, prov, derived_from=derived,
            subject=subject, predicate=cand.predicate, value=cand.value, confidence=cand.confidence,
            status=status, echo=bool(echo_ids), meta=meta, commit=False,
        )

    def _echo_matches(self, text: str, value: str, user_id: str) -> list[str]:
        """Generated events readable by this user that the candidate semantically echoes."""
        filt, params = self._scope_filter_sql("private", user_id, None)
        rows = self.db.execute(
            "SELECT r.id, r.text, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            " WHERE r.kind = 'generated_event' AND NOT EXISTS (SELECT 1 FROM record_scopes rs"
            f" WHERE rs.record_id = r.id AND NOT {filt})",
            params,
        ).fetchall()
        if not rows:
            return []
        q = self.embedder.embed([f"{text} {value}"])[0]
        mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        sims = mat @ q
        nv = _norm(value)
        hits = []
        for r, s in zip(rows, sims):
            lexical = len(nv) >= 2 and nv in _norm(r["text"])
            if s >= self.echo_threshold or (lexical and s >= self.echo_lexical_floor):
                hits.append(r["id"])
        return hits

    def record_generated_event(
        self,
        text: str,
        session_id: str,
        scope: str,
        *,
        source_id: str = "",
        user_id: str = "",
        derived_from: Sequence[str] | None = None,
        request_index: int | None = None,
        lineage: str | None = None,
    ) -> Record:
        """Log persona output (speech / shown content). Never promoted to a user fact.

        ``scope`` must be the *session's* write scope (persona lines in a private
        conversation are private). ``derived_from`` lists the memory records the line was
        conditioned on; the line inherits their ``source_scopes`` and erasure / correction
        cascade through them. A public ``scope`` with any private input raises
        :class:`ScopeViolationError` (nothing is written). ``derived_from=None`` means the
        lineage is unknown: recorded as ``meta.lineage = "unknown"``; the caller must then
        pass the session scope (never a public scope from a private session).
        """
        validate_scope(scope)
        if scope == CANON:
            raise ScopeViolationError("persona output is never canon")
        if not user_id and is_private(scope):
            user_id = scope.split(":", 1)[1]
        meta: dict[str, Any] = {"lineage": lineage or ("unknown" if derived_from is None else "explicit")}
        if request_index is not None:
            meta["request_index"] = request_index
        prov = Provenance(source_id=source_id, speaker="persona", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.GENERATED_EVENT, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from or (), meta=meta,
        )

    def ingest_viewer_chat(
        self, text: str, viewer_id: str, stream_id: str, *, session_id: str = "", source_id: str = ""
    ) -> Record | None:
        """Public-scope, ``viewer_claim``, rate-limited and sanitised. Returns None if dropped."""
        if not self._viewer_limiter.allow(viewer_id):
            self.stats["viewer_rate_limited"] += 1
            return None
        clean = sanitize(text, self.viewer_max_len)
        if not clean.text:
            self.stats["viewer_empty"] += 1
            return None
        scope = public_scope(stream_id)
        prov = Provenance(source_id=source_id, speaker=f"viewer:{viewer_id}", session_id=session_id,
                          timestamp=self.clock(), extractor_version=self.extractor.version)
        ep = self.add_record(
            Kind.EPISODE, scope, clean.text, ClaimType.VIEWER_CLAIM, prov, importance=0.1,
            meta={"injection": clean.injection, "truncated": clean.truncated}, commit=False,
        )
        if clean.injection:
            self.stats["viewer_injection"] += 1
        else:
            for cand in self.extractor.extract(clean.text):
                if cand.claim_type != ClaimType.OWN_ASSERTION or not (cand.predicate and cand.value):
                    continue
                subj = f"viewer:{viewer_id}" + ((cand.subject or "user")[4:])  # "user/sister" -> "/sister"
                self.add_record(
                    Kind.USER_FACT, scope, cand.text, ClaimType.VIEWER_CLAIM,
                    Provenance(source_id=source_id, speaker=f"viewer:{viewer_id}", session_id=session_id,
                               timestamp=self.clock(), extractor_version=self.extractor.version),
                    derived_from=[ep.id], subject=subj, predicate=cand.predicate, value=cand.value,
                    confidence=0.3, importance=0.1, commit=False,
                )
        self.db.commit()
        return ep

    def record_inference(
        self,
        text: str,
        *,
        user_id: str,
        derived_from: Sequence[str],
        subject: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        confidence: float = 0.5,
        session_id: str = "",
        scope: str | None = None,
    ) -> Record:
        """Agent inference -> ``candidate_belief`` (pending; never a user fact until confirmed)."""
        prov = Provenance(speaker="agent", session_id=session_id, timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.CANDIDATE_BELIEF, scope or private_scope(user_id), text, ClaimType.AGENT_INFERENCE, prov,
            derived_from=derived_from, subject=self._abs_subject(subject, user_id) if subject else None,
            predicate=predicate, value=value, confidence=confidence, status=Status.PENDING,
        )

    def record_observation(
        self,
        text: str,
        *,
        user_id: str,
        subject: str,
        predicate: str,
        value: str,
        confidence: float = 0.9,
        session_id: str = "",
        source_id: str = "",
        derived_from: Sequence[str] = (),
    ) -> Record:
        """System observation (e.g. from a sensor / platform metadata) as a user fact."""
        prov = Provenance(source_id=source_id, speaker="system", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.USER_FACT, private_scope(user_id), text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from, subject=self._abs_subject(subject, user_id), predicate=predicate,
            value=value, confidence=confidence,
        )

    def add_ledger(
        self,
        text: str,
        scope: str,
        *,
        canonical: bool = False,
        key: str | None = None,
        derived_from: Sequence[str] = (),
        session_id: str = "",
        user_id: str = "",
    ) -> Record:
        """Persona / world continuity entry. Canonical anchors are immutable and canon-only.

        A non-canonical entry with a ``key`` supersedes the previous entry with the same key
        in the same scope (bi-temporal: old one keeps ``valid_to``).
        """
        if canonical and scope != CANON:
            raise ValueError("canonical anchors must have scope 'canon'")
        if not canonical and scope == CANON:
            raise ValueError("only canonical anchors live in scope 'canon'")
        if key and not canonical:
            old = self._load(self._ids(
                "SELECT id FROM records WHERE kind = 'ledger' AND scope = ? AND status = 'active'"
                " AND json_extract(meta, '$.key') = ?", (scope, key)))
            self._supersede(old)
        prov = Provenance(speaker="system", session_id=session_id, timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.LEDGER, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=derived_from,
            immutable=canonical, meta={"key": key, "canonical": canonical},
        )

    def add_procedure(
        self,
        text: str,
        outcome: str,
        *,
        derived_from: Sequence[str] = (),
        scope: str | None = None,
        tags: Sequence[str] = (),
        curated: bool = False,
    ) -> Record:
        """A²RD-style prompt-library entry: what worked (``success``) or failed (``failure``).

        Learned entries must name their sources (``derived_from``: the episodes / generated
        events / verdict records they were learned from). Their scope is derived from the
        sources: the most restrictive one wins (a user's private scope > a public stream >
        canon), so a procedure learned in a private session stays private. An explicit
        ``scope`` may only be *more* restrictive than the derived one. Canon therefore
        requires canon-only sources, or ``curated=True`` (operator-authored, no sources).
        """
        if outcome not in ("success", "failure"):
            raise ValueError("outcome must be 'success' or 'failure'")
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        if curated:
            if parents or scope not in (None, CANON):
                raise ValueError("curated procedures are operator-authored canon entries without sources")
            derived = CANON
        else:
            if not parents:
                raise ValueError("learned procedures require derived_from (source lineage)")
            scopes = frozenset().union(*(p.source_scopes for p in parents))
            privs = sorted(s for s in scopes if is_private(s))
            pubs = sorted(s for s in scopes if s.startswith("public:"))
            if len(privs) > 1:
                raise ScopeViolationError(f"procedure would mix private scopes {privs}")
            derived = privs[0] if privs else (pubs[0] if pubs else CANON)
        if scope is None or scope == derived:
            scope = derived
        elif not (is_private(scope) and not is_private(derived)):  # only narrowing to private is allowed
            raise ScopeViolationError(f"procedure scope {scope!r} is wider than its sources ({derived!r})")
        user_id = scope.split(":", 1)[1] if is_private(scope) else ""
        prov = Provenance(speaker="operator" if curated else "system", timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.PROCEDURAL, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=[p.id for p in parents],
            meta={"outcome": outcome, "tags": list(tags), "curated": curated},
        )

    # ------------------------------------------------------------------ confirmation / correction

    def confirm(self, record_id: str, confirmation_id: str | None = None) -> Record:
        """User explicitly confirms a pending echo / conflicting fact or a candidate belief.

        ``confirmation_id`` is the ``episode`` record of the user's confirming turn (e.g.
        "yes, that's right"). It is **required** for a candidate belief: the belief is not
        rewritten; a *new* ``own_assertion`` user fact (speaker="user", derived from the
        confirming episode and the belief) is created and returned, and the belief is kept
        as provenance (status superseded, ``meta.confirmed_by``). For a pending user fact
        it is optional and, when given, is linked into the fact's lineage.
        """
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending (status={rec.status.value})")
        owner = rec.provenance.user_id
        conf = self._require(confirmation_id) if confirmation_id else None
        if conf is not None:
            if conf.kind != Kind.EPISODE or conf.provenance.speaker != "user" or conf.provenance.user_id != owner:
                raise ValueError("confirmation must be an episode spoken by the record's owner")
            if conf.claim_type in (ClaimType.QUESTION, ClaimType.HYPOTHETICAL, ClaimType.QUOTE_OF_PERSONA):
                raise ValueError(f"a {conf.claim_type.value} turn cannot confirm a memory")
        elif rec.kind == Kind.CANDIDATE_BELIEF:
            raise ValueError("confirming an agent inference requires the user's confirming episode")
        now = self.clock()
        others: list[Record] = []
        if rec.subject and rec.predicate and is_single_valued(rec.predicate):
            others = [r for r in self._current_facts(rec.subject, rec.predicate, owner, claim=None)
                      if r.id != rec.id and r.kind == Kind.USER_FACT
                      and r.claim_type in (ClaimType.OWN_ASSERTION, ClaimType.SYSTEM_OBSERVATION)
                      and _norm(r.value) != _norm(rec.value)]
            self._supersede(others)
        if rec.kind == Kind.CANDIDATE_BELIEF:
            assert conf is not None
            prov = Provenance(source_id=conf.provenance.source_id, speaker="user",
                              session_id=conf.provenance.session_id, timestamp=now, user_id=owner)
            fact = self.add_record(
                Kind.USER_FACT, private_scope(owner) if owner else rec.scope, rec.text, ClaimType.OWN_ASSERTION,
                prov, derived_from=[conf.id, rec.id], subject=rec.subject, predicate=rec.predicate,
                value=rec.value, valid_from=now,
                meta={"confirmed_from": rec.id, "confirmed_from_claim": ClaimType.AGENT_INFERENCE.value,
                      "confirmed_by": conf.id, "confirmed_at": now,
                      **({"supersedes": [r.id for r in others]} if others else {})},
                commit=False,
            )
            # the inference is kept (for audit / lineage) but no longer usable on its own
            self._set_status(rec.id, Status.SUPERSEDED, valid_to=now)
            self._update_meta(rec.id, confirmed_as=fact.id, confirmed_by=conf.id)
            self.db.commit()
            return self._require(fact.id)
        if others:
            self._update_meta(rec.id, supersedes=[r.id for r in others])
        if conf is not None:
            self._link_parent(rec.id, conf)
        self._set_status(rec.id, Status.ACTIVE, valid_from=now)
        self._update_meta(rec.id, confirmed_at=now, **({"confirmed_by": conf.id} if conf else {}))
        self.db.commit()
        return self._require(rec.id)

    def _link_parent(self, child_id: str, parent: Record) -> None:
        """Add a lineage edge after insertion (and widen the child's source_scopes accordingly)."""
        child = self._require(child_id)
        scopes = union_scopes(child.scope, [child, parent])
        self._check_write_scope(child.kind, child.scope, scopes, child.provenance)
        self.db.execute("INSERT OR IGNORE INTO derivations (child_id, parent_id) VALUES (?, ?)", (child_id, parent.id))
        self.db.executemany("INSERT OR IGNORE INTO record_scopes (record_id, scope) VALUES (?, ?)",
                            [(child_id, sc) for sc in sorted(scopes)])

    def reject(self, record_id: str) -> Record:
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending")
        self._set_status(rec.id, Status.REJECTED)
        self.db.commit()
        return self._require(rec.id)

    def correct(self, record_id: str, new_value: str, *, text: str | None = None,
                source_id: str = "", session_id: str = "") -> Record:
        """Bi-temporal correction: old value gets ``valid_to`` (kept for audit), new value is
        inserted, and every artifact reachable through ``derived_from`` is marked stale."""
        old = self._require(record_id)
        if old.kind != Kind.USER_FACT or old.status not in (Status.ACTIVE, Status.PENDING):
            raise ValueError("only current user facts can be corrected")
        self._supersede([old])
        prov = Provenance(source_id=source_id, speaker="user", session_id=session_id or old.provenance.session_id,
                          timestamp=self.clock(), user_id=old.provenance.user_id)
        new = self.add_record(
            Kind.USER_FACT, old.scope, text or f"{old.subject} {old.predicate} {new_value}",
            ClaimType.OWN_ASSERTION, prov, subject=old.subject, predicate=old.predicate, value=new_value,
            meta={"supersedes": [old.id]},
        )
        return new

    def _supersede(self, records: Sequence[Record]) -> list[Record]:
        now = self.clock()
        for r in records:
            if r.immutable:
                raise ImmutableRecordError(r.id)
            self._set_status(r.id, Status.SUPERSEDED, valid_to=now)
        stale = self.invalidate_derivatives([r.id for r in records]) if records else []
        self.db.commit()
        return stale

    def invalidate_derivatives(self, root_ids: Sequence[str]) -> list[Record]:
        """Mark every artifact reachable through ``derived_from`` as stale; fire stale hooks."""
        ids = self._descendants(root_ids) - set(root_ids)
        stale: list[Record] = []
        for rec in self._load(sorted(ids)):
            if rec.immutable or rec.status in (Status.SUPERSEDED, Status.STALE, Status.REJECTED):
                continue
            self._set_status(rec.id, Status.STALE)
            rec.status = Status.STALE
            stale.append(rec)
        self.db.commit()
        if stale:
            for hook in list(self.stale_hooks):
                hook(stale)
        return stale

    def regenerate_stale(self, summarizer: Summarizer | None = None) -> list[Record]:
        """Hook helper: rebuild every stale summary from its session's current records."""
        sessions = {r["session_id"] for r in self.db.execute(
            "SELECT session_id FROM records WHERE kind = 'summary' AND status = 'stale'")}
        out = []
        for s in sorted(sessions):
            rec = self.consolidate(s, summarizer)
            if rec is not None:
                out.append(rec)
        return out

    def _descendants(self, root_ids: Iterable[str]) -> set[str]:
        seen = set(root_ids)
        frontier = list(seen)
        while frontier:
            q = ",".join("?" * len(frontier))
            children = self._ids(f"SELECT child_id FROM derivations WHERE parent_id IN ({q})", frontier)
            frontier = [c for c in children if c not in seen]
            seen.update(frontier)
        return seen

    # ------------------------------------------------------------------ read paths

    def _current_facts(self, subject: str, predicate: str, user_id: str, claim: ClaimType | None) -> list[Record]:
        filt, params = self._scope_filter_sql("private", user_id, None)
        sql = ("SELECT r.id FROM records r WHERE r.kind = 'user_fact' AND r.status = 'active'"
               " AND r.subject = ? AND r.predicate = ? AND (r.valid_to IS NULL OR r.valid_to > ?)"
               f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})")
        args: list[Any] = [subject, predicate, self.clock(), *params]
        if claim is not None:
            sql += " AND r.claim_type = ?"
            args.append(claim.value)
        return self._load(self._ids(sql + " ORDER BY r.valid_from", args))

    def retrieve(
        self,
        query: str,
        mode: str,
        user_id: str | None = None,
        stream_id: str | None = None,
        k: int = 8,
        budget_ms: float = 50.0,
        *,
        kinds: Sequence[Kind] | None = None,
        include_pending: bool = False,
        batch: int = 512,
    ) -> RetrievalResult:
        """Scope-filter first (in SQL, on ``source_scopes``), then rank by
        relevance + recency + importance. Pending / stale / superseded records are excluded
        unless ``include_pending`` (which adds pending only)."""
        t0 = time.perf_counter()
        now = self.clock()
        filt, params = self._scope_filter_sql(mode, user_id, stream_id)
        statuses = ["active"] + (["pending"] if include_pending else [])
        sql = (
            "SELECT r.id, r.t, r.importance, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            f" WHERE r.status IN ({','.join('?' * len(statuses))})"
            " AND (r.valid_to IS NULL OR r.valid_to > ?)"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})"
        )
        args: list[Any] = [*statuses, now, *params]
        if kinds:
            sql += f" AND r.kind IN ({','.join('?' * len(kinds))})"
            args += [Kind(x).value for x in kinds]
        sql += " ORDER BY r.t DESC LIMIT ? OFFSET ?"
        qv = self.embedder.embed([query])[0]
        w_rel, w_rec, w_imp = self.weights
        scored: list[tuple[float, float, float, float, str]] = []
        offset, scanned, truncated = 0, 0, False
        while True:
            rows = self.db.execute(sql, [*args, batch, offset]).fetchall()
            if not rows:
                break
            mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
            rel = np.clip(mat @ qv, 0.0, 1.0)
            for r, rv in zip(rows, rel):
                rec_s = math.exp(-max(0.0, now - r["t"]) / self.recency_tau_s)
                imp = float(r["importance"])
                scored.append((w_rel * float(rv) + w_rec * rec_s + w_imp * imp, float(rv), rec_s, imp, r["id"]))
            scanned += len(rows)
            offset += batch
            if len(rows) < batch:
                break
            if (time.perf_counter() - t0) * 1000.0 > budget_ms:
                truncated = True
                break
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]
        recs = {r.id: r for r in self._load([x[4] for x in top])}
        hits = []
        for score, rv, rs, imp, rid in top:
            rec = recs.get(rid)
            if rec is None or not self.scope_readable(rec.source_scopes, mode, user_id, stream_id):
                continue  # defence in depth; the SQL filter should already have excluded it
            hits.append(Hit(rec, score, rv, rs, imp))
        return RetrievalResult(hits, (time.perf_counter() - t0) * 1000.0, scanned, truncated)

    def resolve(self, user_id: str, subject: str, predicate: str) -> Resolution:
        """Conflict resolution: user-asserted (latest valid) > system-observed >
        agent-inferred > viewer-claimed. Echo / conflicting candidates never count until confirmed."""
        subj = self._abs_subject(subject, user_id)
        filt, params = self._scope_filter_sql("private", user_id, None)
        ids = self._ids(
            "SELECT r.id FROM records r WHERE r.kind IN ('user_fact', 'candidate_belief')"
            " AND r.subject = ? AND r.predicate = ? AND r.status IN ('active', 'pending')"
            " AND (r.valid_to IS NULL OR r.valid_to > ?)"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})",
            [subj, predicate, self.clock(), *params],
        )
        recs = self._load(ids)
        active = [r for r in recs if r.status == Status.ACTIVE and r.claim_type in CLAIM_PRIORITY]
        pending = [r for r in recs if r.status == Status.PENDING]
        active.sort(key=lambda r: (CLAIM_PRIORITY[r.claim_type], r.valid_from or 0.0, r.created_at), reverse=True)
        best = active[0] if active else None
        return Resolution(subj, predicate, best.value if best else None, best, active[1:], pending)

    def profile(self, user_id: str) -> list[Record]:
        """Session preload: current valid user facts (user-asserted or system-observed) from
        the user's private scope; single-valued predicates collapsed to the resolved winner."""
        ids = self._ids(
            "SELECT id FROM records WHERE kind = 'user_fact' AND status = 'active' AND scope = ?"
            " AND claim_type IN ('own_assertion', 'system_observation')"
            " AND (valid_to IS NULL OR valid_to > ?) ORDER BY valid_from",
            [private_scope(user_id), self.clock()],
        )
        out: dict[tuple[str, str], Record] = {}
        multi: list[Record] = []
        for r in self._load(ids):
            if not self.scope_readable(r.source_scopes, "private", user_id, None):
                continue
            if is_single_valued(r.predicate):
                key = (r.subject or "", r.predicate or "")
                prev = out.get(key)
                if prev is None or (CLAIM_PRIORITY[r.claim_type], r.valid_from or 0) >= (
                        CLAIM_PRIORITY[prev.claim_type], prev.valid_from or 0):
                    out[key] = r
            else:
                multi.append(r)
        return list(out.values()) + multi

    def canon_anchors(self) -> list[Record]:
        return self._load(self._ids(
            "SELECT id FROM records WHERE kind = 'ledger' AND scope = 'canon' AND immutable = 1 ORDER BY t"))

    def boot_context(self, mode: str, user_id: str | None = None) -> list[Record]:
        """Records a new session may start from. Public sessions boot from canon anchors only."""
        anchors = self.canon_anchors()
        if mode == "public":
            return anchors
        if mode == "private":
            if not user_id:
                raise ValueError("private mode requires user_id")
            return anchors + self.profile(user_id)
        raise ValueError(mode)

    # ------------------------------------------------------------------ consolidation

    def consolidate(self, session_id: str, summarizer: Summarizer | None = None) -> Record | None:
        """Sleep-time summary of one session. Writes a ``summary`` record whose
        ``derived_from`` lists every input and whose ``source_scopes`` is their union.
        Supersedes any previous summary of the same session."""
        summ = summarizer or ExtractiveSummarizer()
        now = self.clock()
        # only usable inputs: stale / superseded / rejected / pending records never feed a summary
        ids = self._ids(
            "SELECT id FROM records WHERE session_id = ? AND status = 'active' AND ("
            " kind IN ('episode', 'generated_event')"
            " OR (kind = 'user_fact' AND (valid_to IS NULL OR valid_to > ?)))"
            " ORDER BY t", [session_id, now])
        recs = self._load(ids)
        # persona lines with unknown / incomplete lineage that repeat a corrected-away value
        retracted = self._retracted_values({r.provenance.user_id for r in recs if r.provenance.user_id})
        if retracted:
            recs = [r for r in recs if not (r.kind == Kind.GENERATED_EVENT
                                            and any(v in _norm(r.text) for v in retracted))]
        # drop turns whose extracted facts were all corrected away (history stays in the episode log)
        retired = set(self._ids(
            "SELECT d.parent_id FROM derivations d JOIN records c ON c.id = d.child_id"
            " WHERE c.kind = 'user_fact' AND c.status IN ('superseded', 'stale', 'rejected')"))
        live = set(self._ids(
            "SELECT d.parent_id FROM derivations d JOIN records c ON c.id = d.child_id"
            " WHERE c.kind = 'user_fact' AND c.status IN ('active', 'pending')"))
        recs = [r for r in recs if not (r.kind == Kind.EPISODE and r.id in retired and r.id not in live)]
        old = self._load(self._ids(
            "SELECT id FROM records WHERE kind = 'summary' AND session_id = ? AND status IN ('active', 'stale')",
            [session_id]))
        for r in old:
            self._set_status(r.id, Status.SUPERSEDED, valid_to=now)
        if not recs:
            self.db.commit()
            return None
        scopes = frozenset().union(*(r.source_scopes for r in recs))
        privs = sorted(s for s in scopes if is_private(s))
        if len(privs) > 1:
            raise ValueError("refusing to summarise across several users' private scopes")
        scope = privs[0] if privs else next((s for s in sorted(scopes) if s.startswith("public:")), CANON)
        if scope == CANON:
            raise ValueError("summaries are never canon")
        text = summ.summarize(recs)
        prov = Provenance(speaker="system", session_id=session_id, timestamp=now,
                          extractor_version=summ.version, user_id=privs[0].split(":", 1)[1] if privs else "")
        return self.add_record(Kind.SUMMARY, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
                               derived_from=[r.id for r in recs], meta={"session": session_id})

    def _retracted_values(self, owners: Iterable[str]) -> set[str]:
        """Normalised values of this user's superseded facts that no current fact still holds."""
        old: set[str] = set()
        cur: set[str] = set()
        for owner in owners:
            for r in self.db.execute(
                    "SELECT status, value FROM records WHERE owner = ? AND kind IN ('user_fact', 'candidate_belief')"
                    " AND value IS NOT NULL AND status IN ('active', 'pending', 'superseded')", [owner]):
                (cur if r["status"] != "superseded" else old).add(_norm(r["value"]))
        return {v for v in old - cur if len(v) >= 2}

    # ------------------------------------------------------------------ erasure

    def _user_records_sql(self) -> str:
        return ("(r.owner = ? OR EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id"
                " AND rs.scope = ?))")

    def _erasable_sql(self) -> str:
        """Records a user's erasure may touch by *content*: their own records, plus any
        public-scoped record carrying no other user's private scope (a public artifact that
        repeats the user's data may be untagged; over-deletion is the safe side). Canon-only
        records and other users' private records are never touched. Params: (user, priv, priv)."""
        return (
            "r.immutable = 0 AND (" + self._user_records_sql() +
            " OR (EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND rs.scope LIKE 'public:%')"
            " AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id"
            " AND rs.scope LIKE 'private:%' AND rs.scope != ?)))"
        )

    def _content_match(self, term: str, user_id: str) -> list[str]:
        priv = private_scope(user_id)
        return self._ids(
            f"SELECT r.id FROM records r WHERE {self._erasable_sql()} AND ("
            " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0)",
            [user_id, priv, priv, term, term])

    def forget(
        self,
        target: str | Record,
        user_id: str,
        reason: str = "user_request",
        *,
        regenerate: bool | Summarizer = True,
        require: Iterable[str] = (),
    ) -> ErasureReport:
        """Physically erase a fact (by record id / Record) or everything matching a query term.

        Cascade: matched records -> source episodes (id link) -> every erasable record
        mentioning the value/term (this user's records of any kind, and public records
        carrying no other user's private scope) -> all descendants through
        ``derived_from``; plus their embeddings, scope rows, derivation edges and id
        references in other records' meta. A tombstone keeps only sha256(id), time and
        reason. Affected session summaries are regenerated from what remains.

        Fail-closed completion: the store verifies its own deletion (ids, descendants,
        term residue in every scope) and acks ``memory_db``; then every erasure hook is
        called and must return a truthy ack. ``require`` names further purge targets
        (recordings, generator state, LLM context ...) that must ack via
        :meth:`ErasureReport.acknowledge`. ``report.complete`` is False until all of them
        acked ok; a hook error never un-deletes anything.
        """
        priv = private_scope(user_id)
        seeds: list[Record] = []
        terms: set[str] = set()
        rid = target.id if isinstance(target, Record) else target
        rec = self.get(rid)
        if rec is not None:
            if rec.provenance.user_id != user_id and priv not in rec.source_scopes:
                raise PermissionError("record does not belong to this user")
            seeds = [rec]
        else:
            term = str(target).strip()
            if not term:
                raise ValueError("empty erasure target")
            terms.add(term)
            seeds = self._load(self._content_match(term, user_id))
        terms |= {s.value for s in seeds if s.value and len(s.value.strip()) >= 2}
        erase: set[str] = {s.id for s in seeds}
        # id link: the episodes the seed facts were extracted from (facts only: a summary's
        # parents are whole sessions and are handled by content match instead)
        for s in seeds:
            if s.kind not in (Kind.USER_FACT, Kind.CANDIDATE_BELIEF):
                continue
            for p in self._load(list(s.derived_from)):
                if p.kind == Kind.EPISODE and (p.provenance.user_id == user_id or priv in p.source_scopes):
                    erase.add(p.id)
        for term in terms:
            erase |= set(self._content_match(term, user_id))
        erase = self._descendants(erase)
        doomed = self._load(sorted(erase))
        if any(r.immutable for r in doomed):
            raise ImmutableRecordError("erasure cascade reached a canon anchor; canon must not derive from user data")
        now = self.clock()
        sessions = {r.provenance.session_id for r in doomed if r.provenance.session_id}
        kinds: dict[str, int] = defaultdict(int)
        for r in doomed:
            kinds[r.kind.value] += 1
        ids = [r.id for r in doomed]
        with self.db:
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                q = ",".join("?" * len(chunk))
                self.db.execute(f"DELETE FROM embeddings WHERE record_id IN ({q})", chunk)
                self.db.execute(f"DELETE FROM record_scopes WHERE record_id IN ({q})", chunk)
                self.db.execute(f"DELETE FROM derivations WHERE child_id IN ({q}) OR parent_id IN ({q})", chunk + chunk)
                self.db.execute(f"DELETE FROM records WHERE id IN ({q})", chunk)
            self.db.executemany(
                "INSERT INTO tombstones (id_hash, t, reason) VALUES (?, ?, ?)",
                [(hashlib.sha256(i.encode()).hexdigest(), now, reason) for i in ids],
            )
            self._scrub_refs(set(ids))
        hook_names = [(_hook_name(h), h) for h in self.erasure_hooks] + list(self.purge_hooks.items())
        required = [MEMORY_DB_TARGET, *dict.fromkeys(
            [n for n, _ in hook_names] + sorted(self.required_purge_targets) + list(require))]
        report = ErasureReport(user_id=user_id, reason=reason, t=now, deleted_ids=ids, kinds=dict(kinds),
                               sessions=sessions, terms=terms, required_targets=required)
        if regenerate and kinds.get(Kind.SUMMARY.value):
            summ = regenerate if not isinstance(regenerate, bool) else None
            for s in sorted(sessions):
                new = self.consolidate(s, summ)
                if new is not None:
                    report.regenerated.append(new.id)
        report.verification = self.verify_erasure(report)
        v = report.verification
        report.acknowledge(MEMORY_DB_TARGET, v.ok, "verified" if v.ok else f"residue: {v.hits[:10]}")
        for name, hook in hook_names:
            try:
                ack = hook(report)
            except Exception as e:  # noqa: BLE001 -- any failure leaves the erasure incomplete (never undone)
                report.hook_errors.append(f"{name}: {e!r}")
                report.acknowledge(name, False, f"error: {e!r}")
                continue
            if name in report.acks and report.acks[name].ok:
                continue  # the hook acknowledged through the report itself
            report.acknowledge(name, bool(ack), ack if isinstance(ack, str) else ("" if ack else "no ack"))
        if not report.complete:
            log.error("erasure for %s incomplete; pending purge targets %s", hashlib.sha256(user_id.encode())
                      .hexdigest()[:12], report.pending_targets)
        return report

    def _scrub_refs(self, deleted: set[str]) -> None:
        """Remove references to erased ids from surviving records' meta (echo_of, supersedes ...)."""
        if not deleted:
            return
        for row in self.db.execute("SELECT id, meta FROM records WHERE immutable = 0 AND meta != '{}'").fetchall():
            meta = json.loads(row["meta"])
            changed = False
            for k, v in list(meta.items()):
                if isinstance(v, list) and any(x in deleted for x in v if isinstance(x, str)):
                    meta[k] = [x for x in v if x not in deleted]
                    changed = True
                elif isinstance(v, str) and v in deleted:
                    del meta[k]
                    changed = True
            if changed:
                self.db.execute("UPDATE records SET meta = ? WHERE id = ?", (json.dumps(meta, ensure_ascii=False), row["id"]))

    def verify_erasure(self, report: ErasureReport, *, raw_file: bool = False) -> ErasureVerification:
        """Verify one :meth:`forget` result (its deleted ids incl. descendants, and its terms)."""
        return self.verify_erased(report.terms, report.user_id, deleted_ids=report.deleted_ids, raw_file=raw_file)

    def verify_erased(
        self,
        term: str | Iterable[str] | None,
        user_id: str | None = None,
        *,
        deleted_ids: Iterable[str] = (),
        raw_file: bool = False,
    ) -> ErasureVerification:
        """Check that erased data is gone from every table.

        * ``deleted_ids`` (a forget report's ids, which include all descendants): no row in
          records / embeddings / record_scopes / derivations, no reference from another
          record's meta or provenance, and a tombstone hash exists for each.
        * ``term``: literal search in *all* scopes (text, value, subject, provenance, meta,
          tombstone reasons). Hits in records this user's erasure may touch fail the check;
          hits in other users' private records or canon-only records are listed in
          ``foreign_hits`` only.
        * orphan index / embedding / edge rows; with ``raw_file``, the DB file bytes (only
          meaningful if no other user legitimately stores the term).

        External stores (recordings, generator / LLM state) are verified by their purge
        targets' acknowledgements on the :class:`ErasureReport`, not here.
        """
        out = ErasureVerification()
        terms = [term] if isinstance(term, str) else list(term or [])
        ids = list(dict.fromkeys(deleted_ids))
        priv = private_scope(user_id) if user_id else None
        if ids:
            tomb = {r[0] for r in self.db.execute("SELECT id_hash FROM tombstones")}
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                q = ",".join("?" * len(chunk))
                for tbl, col in (("records", "id"), ("embeddings", "record_id"), ("record_scopes", "record_id"),
                                 ("derivations", "child_id"), ("derivations", "parent_id")):
                    for r in self.db.execute(f"SELECT DISTINCT {col} FROM {tbl} WHERE {col} IN ({q})", chunk):
                        out.surviving.append(f"{tbl}:{r[0]}")
            idset = set(ids)
            for r in self.db.execute("SELECT id, meta, provenance FROM records"):
                blob = r["meta"] + r["provenance"]
                if any(i in blob for i in idset):
                    out.surviving.append(f"ref:{r['id']}")
            out.missing_tombstones = [i for i in ids if hashlib.sha256(i.encode()).hexdigest() not in tomb]
        for t in terms:
            rows = self.db.execute(
                "SELECT r.id, r.immutable FROM records r WHERE"
                " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0"
                " OR instr(lower(coalesce(r.subject, '')), lower(?)) > 0 OR instr(lower(r.provenance), lower(?)) > 0"
                " OR instr(lower(r.meta), lower(?)) > 0", [t] * 5).fetchall()
            hit_ids = [r["id"] for r in rows]
            scopes: dict[str, set[str]] = defaultdict(set)
            for i in range(0, len(hit_ids), 500):
                chunk = hit_ids[i:i + 500]
                for r in self.db.execute(
                        f"SELECT record_id, scope FROM record_scopes WHERE record_id IN ({','.join('?' * len(chunk))})",
                        chunk):
                    scopes[r[0]].add(r[1])
            for r in rows:
                sc = scopes[r["id"]]
                foreign = any(is_private(s) and s != priv for s in sc)
                canon_only = sc <= {CANON}
                (out.foreign_hits if foreign or canon_only else out.term_hits).append(f"records:{r['id']}")
            for r in self.db.execute("SELECT rowid FROM tombstones WHERE instr(lower(reason), lower(?)) > 0", [t]):
                out.term_hits.append(f"tombstones:{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM embeddings WHERE record_id NOT IN (SELECT id FROM records)"):
            out.orphans.append(f"embeddings(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM record_scopes WHERE record_id NOT IN (SELECT id FROM records)"):
            out.orphans.append(f"record_scopes(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT child_id, parent_id FROM derivations WHERE child_id NOT IN (SELECT id FROM records)"
                " OR parent_id NOT IN (SELECT id FROM records)"):
            out.orphans.append(f"derivations(orphan):{r[0]}->{r[1]}")
        if raw_file and self.path != ":memory:":
            for t in terms:
                needle = t.encode("utf-8")
                for p in (Path(self.path), Path(self.path + "-journal"), Path(self.path + "-wal")):
                    if p.exists() and needle in p.read_bytes():
                        out.file_hits.append(f"file:{p.name}")
        return out


def _norm(v: str | None) -> str:
    return "".join((v or "").lower().split()).strip("。.!！'\"")

===== FILE: live_agent/memory_bridge.py =====
"""Adapter from live_agent.memory.MemoryStore to the orchestrator's MemoryPort.

Scope rules (review findings 12/13):

* The bridge's **session mode** ("private" 1:1 or "public" livestream) is authoritative
  for every write. Pass it at construction (``mode=``, from the server's authenticated
  session); if omitted it is pinned by the first orchestrator call that names a mode
  (``recall(mode=...)`` / ``on_persona_line(scope=...)``, both ``OrchestratorConfig.scope``).
  Until pinned, writes are private (fail closed). ``Utterance.scope`` is never trusted.
* Persona lines carry lineage: ``on_persona_line(..., source_ids=[...])`` stores the
  memory ids the line was conditioned on as parents. With ``source_ids=None`` the lineage
  is unknown, so the bridge links the line to *every* memory recalled in this session
  (a conservative superset: erasure and correction still cascade to it) and writes it
  in the session scope. A public write with a private input is refused (returns None).
* Erasure is complete only when every required purge target acked (see
  :class:`live_agent.memory.ErasureReport`); the orchestrator acks its targets with
  :meth:`MemoryBridge.acknowledge_erasure`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from live_agent.memory.schema import Record
from live_agent.memory.store import ErasureReport, MemoryStore, ScopeViolationError
from live_agent.types import Utterance

log = logging.getLogger("live_agent.memory_bridge")

# External state that can hold erased content (proposal §5.6 erasure list). Each must ack.
DEFAULT_PURGE_TARGETS = ("llm_context", "unsent_scripts", "generator_state", "recordings")


@dataclass
class RecallHit:
    id: str
    text: str
    tags: dict[str, Any]
    rendered: str  # the string form passed to the director


class MemoryBridge:
    def __init__(self, db_path: str, *, user_id: str, stream_id: str, session_id: str,
                 store: MemoryStore | None = None, mode: str | None = None,
                 required_purge_targets: Sequence[str] = DEFAULT_PURGE_TARGETS, recall_k: int = 6):
        self.store = store or MemoryStore(db_path)
        self.user_id = user_id
        self.stream_id = stream_id
        self.session_id = session_id
        self._mode: str | None = None
        if mode is not None:
            self._pin(mode)
        self.required_purge_targets = tuple(required_purge_targets)
        self.recall_k = recall_k
        self._recalled: dict[str, None] = {}  # ordered set of memory ids recalled this session
        self.scope_violations: list[dict[str, Any]] = []
        self.mode_mismatches = 0
        self.on_erasure: list[Callable[[ErasureReport], Any]] = []
        self.store.register_purge_target("bridge_callbacks", self._erasure_hook)

    # ------------------------------------------------------------------ session scope

    @property
    def mode(self) -> str | None:
        return self._mode

    def _pin(self, mode: str) -> str:
        if mode not in ("private", "public"):
            raise ValueError(f"session mode must be 'private' or 'public', got {mode!r}")
        if self._mode is None:
            self._mode = mode
        elif mode != self._mode:
            self.mode_mismatches += 1
            log.warning("caller mode %r differs from session mode %r; session mode wins", mode, self._mode)
        return self._mode

    @property
    def write_scope(self) -> str:
        return MemoryStore.session_write_scope(self._mode, self.user_id, self.stream_id)

    def _scope(self, mode: str) -> str:  # kept for compatibility; writes ignore ``mode`` beyond pinning
        self._pin(mode)
        return self.write_scope

    # ------------------------------------------------------------------ recall

    def recall_hits(self, text: str, *, mode: str) -> list[RecallHit]:
        """Retrieval with record ids; the ids are remembered as this session's lineage superset."""
        session_mode = self._pin(mode)
        read_mode = "public" if "public" in (mode, session_mode) else "private"  # never widen reads
        res = self.store.retrieve(text, read_mode, user_id=self.user_id if read_mode == "private" else None,
                                  stream_id=self.stream_id, k=self.recall_k)
        out = []
        for h in res.hits:
            t = h.tags
            out.append(RecallHit(h.record.id, h.record.text, t,
                                 f"[{t.get('kind')}/{t.get('claim_type')}/{t.get('status', 'active')}] {h.record.text}"))
            self._recalled[h.record.id] = None
        return out

    def recall(self, text: str, *, mode: str) -> list[str]:
        return [h.rendered for h in self.recall_hits(text, mode=mode)]

    # ------------------------------------------------------------------ writes

    def on_user_utterance(self, utt: Utterance) -> None:
        self.store.ingest_user_utterance(utt, user_id=self.user_id, stream_id=self.stream_id,
                                         mode=self._mode or "private")

    def on_persona_line(self, text: str, *, session_id: str, scope: str,
                        source_ids: Iterable[str] | None = None,
                        request_index: int | None = None) -> Record | None:
        """Log a persona line in the session scope with its lineage.

        ``source_ids``: ids of the memories (``recall_hits(...).id``) the line was
        conditioned on. ``None`` = unknown: linked to all memories recalled this session.
        Returns None (nothing written, violation recorded) if the line would be public but
        an input is private, or if an explicit source was erased meanwhile.
        """
        self._pin(scope)
        if source_ids is None:
            parents, lineage = self.store.existing_ids(self._recalled), "session_recall_superset"
        else:
            wanted = list(dict.fromkeys(source_ids))
            parents, lineage = self.store.existing_ids(wanted), "explicit"
            if len(parents) != len(wanted):
                return self._violation(text, "source memory no longer exists (erased)",
                                       sorted(set(wanted) - set(parents)))
        try:
            return self.store.record_generated_event(
                text, session_id, self.write_scope, user_id=self.user_id, derived_from=parents,
                request_index=request_index, lineage=lineage)
        except ScopeViolationError as e:
            return self._violation(text, str(e), parents)

    def _violation(self, text: str, reason: str, ids: list[str]) -> None:
        self.scope_violations.append({"reason": reason, "ids": ids, "chars": len(text)})
        log.error("persona line not recorded: %s", reason)

    # ------------------------------------------------------------------ erasure

    def forget(self, term: str) -> ErasureReport:
        report = self.store.forget(term, self.user_id, reason="user_request",
                                   require=self.required_purge_targets)
        for rid in report.deleted_ids:
            self._recalled.pop(rid, None)
        return report

    @staticmethod
    def acknowledge_erasure(report: ErasureReport, target: str, ok: bool = True, detail: str = "") -> bool:
        """Ack one purge target (e.g. after ``gen.reset()``); returns ``report.complete``."""
        report.acknowledge(target, ok, detail)
        return report.complete

    def _erasure_hook(self, report: ErasureReport) -> bool:
        # Callbacks must return a truthy ack; any missing ack fails the erasure closed.
        acks = [cb(report) for cb in self.on_erasure]
        return all(bool(a) for a in acks)


__all__ = ["DEFAULT_PURGE_TARGETS", "MemoryBridge", "RecallHit"]
