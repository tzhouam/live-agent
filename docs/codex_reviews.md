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

### impl1c + impl2c: round 2 (commit ba9b6c0)

Model gpt-6-sol, verified in both rollouts.
- **impl1c:** 8 of 19 round-1 findings RESOLVED or scoped, 11 PARTIAL, plus 5 new findings (4 blocking). Verdict: **not ready**.
- **impl2c:** 6 of 16 RESOLVED, 10 PARTIAL, plus 11 new findings (3 blocking). Verdict: **not ready**.

Every finding was accepted. Fixed in commits e9f6546 and the one after it (164 tests pass). Highlights:
- A superseded decision is discarded by input epoch.
- Deadlines start at the client-stamped utterance end.
- QC evidence is restricted to the frames actually painted.
- Media is evicted after QC.
- The generator reset is confirmed by the workers and adapter buffers are cleared; erasure fails closed and redacts every erased value.
- Public persona lines need complete lineage; the memory mode is fixed at construction; memory runs a paraphrase sweep; correction is atomic.
- Adjudication:
  - negative labels need review through the deadline;
  - media is delivered as metadata-stripped copies;
  - finalized batches are immutable;
  - an audio claim sweep covers FCR;
  - the primary report refuses to run with unobserved windows;
  - RQ2 is analysed per failure point;
  - time to success is reported per kind.

Real-stack verification is in `docs/implementation.md` (server path with erasure). Documented limits: no content-moderation model (audit = blocklist); cross-lingual paraphrases are not caught by the erasure sweep.

### impl1d + impl2d: round 3 (reviewed at commit e9f6546+1; fixes in bb65031)

Model gpt-6-sol, verified.
- **impl1d:** 13 of 24 prior findings RESOLVED or scoped, 11 PARTIAL, plus 5 new material findings (1 blocking: A1 chains never
  closed). Verdict: **not ready**.
- **impl2d:** 15 of 27 RESOLVED, 11 PARTIAL, 1 OPEN, plus 6 new material findings (1 blocking: incomplete pair sets). Verdict:
  **not ready**.

Every finding was accepted, with one explained exception. impl1d #12 says misclassified action requests "can disappear from the
scoring denominator". The E2 denominator comes from ground-truth chain annotations (`chain_annotation` from the task
script or annotator), independent of the director's classification (`runner.convert`, `scoring.score_session`), so
a misclassified request is scored as a failure, not dropped. No code change for that point, but the declined-request
heuristic remains. All other items are fixed (182 tests pass): see the commit message.

### impl1e + impl2e: round 4

Model gpt-6-sol, verified.
- **impl1e:** 21 of 29 RESOLVED or scoped, 6 PARTIAL, plus 2 new findings (1 blocking: the erasure and barge-in shared an unowned lock gate).
- **impl2e:** 4 of 6 RESOLVED, 2 PARTIAL, plus 6 new major findings.

Both verdicts: **not ready**. Every finding was accepted and fixed in the next commit (200+ tests pass):
- **Lock gates:** each gate has a single owner, and erasures are serialized.
- **A1 lifecycle:** a chain closes only after every request it was locked into has been fully presented.
- **Shared memory:** undeliverable messages are disposed of; dead-writer files are swept; reset drains the whole queue.
- **Bridge:** it names unseen speech as well as actions and is reconciled only when the bridge request is fully presented.
- **Barge-in:** old-plan segments stay ineligible until the new decision lands.
- **Evidence time:** taken from the last painted frame across all chunks.
- **Repair offset:** reworded as the observed mock-run value.
- **Pairing:** pairs are checked against the registered expected set.
- **RQ2:** withdrawal history is kept per repair point, the audit matches points to assignments one-to-one, and a target counts as observed only when all its chunks were presented.
- **Media:** stripped metadata is mandatory for primary batches, and container tags are scanned.
- **Memory:** confirmation must restate the proposition; public empty-lineage lines are refused when private context was possible; persistent journals are removed; the raw-file check covers the erased text.

### impl1f + impl2f: round 5

Model gpt-6-sol, verified.
- **impl1f:** 22 of 31 RESOLVED or scoped, 9 PARTIAL, plus 7 new findings (1 blocking: erasure did storage work before stopping playback).
- **impl2f:** 6 of 10 RESOLVED, 1 PARTIAL, plus 4 new major findings.

Both verdicts: **not ready**. Every finding was accepted and fixed in the next commit (208 tests pass).
- **Config bug found while fixing #35:** every capability's `degrade_to` line was an acceptance or completion phrase.
- **#10 (audio input path):** handled by refusing primary E2 decisions for non-browser logs. The TTS-driven client is open.
- **Pending:** the GPU re-check of the round-5 adapter change (rank-PID gather at worker start-up) is queued; GPUs 3–5 and 7 are held by another user.

### impl1g + impl2g: round 6

Model gpt-6-sol, verified.
- **impl1g:** 29 of 38 RESOLVED or scoped, 9 PARTIAL, plus 4 new major findings.
- **impl2g:** 8 of 10 RESOLVED, 2 PARTIAL, plus 3 new findings (1 blocking: in a private session, a `viewer:`-tagged utterance was written into public scope).

Both verdicts: **not ready**. Every finding was accepted and fixed in the next commit (all tests pass).

### impl1h + impl2h: round 7

Model gpt-6-sol, verified.
- **impl1h:** 35 RESOLVED or scoped, 5 PARTIAL (2 only because the worker code was not inlined), plus 3 new findings (1 blocking: QC still running during an erasure could re-log erased content).
- **impl2h:** 10 RESOLVED, 2 PARTIAL, plus 3 new major findings.

Both verdicts: **not ready**. Every finding was accepted and fixed in the next commit.

**Documented residual (impl1 #36):** the narration guard is a pattern-based mitigation (explicit markers; action verb + perfective or resultative in one clause; questions exempt). It cannot recognise every paraphrase of completion. The outcome measure does not depend on it: false completion claims are counted from the recorded audio by the adjudicated claim sweep (FCR, H1b).

### impl1i + impl2i: round 8

Model gpt-6-sol, verified. The worker services and the M0 document were inlined this time.
- **impl1i:** 43 of 45 prior findings RESOLVED or scoped, 2 PARTIAL, plus 4 new major findings. No blocking findings.
- **impl2i:** 15 of 16 RESOLVED (the remaining one concerned diagnostic fields only), plus 4 new major findings.

Codex found no issue in the inlined M0 figures or the prompt compiler; it confirmed that the M0 figures support short-run generator throughput only. Every finding was accepted and fixed in the next commit (all tests pass).
- **Control path:**
  - Action checks drive control independently of the (later) speech check.
  - Action deadlines do not apply to content replies.
  - Inputs keep the epoch from when they were received.
  - Audit-withheld segments refuse their chain.
  - Audibility of speech in a cut chunk is marked uncertain.
  - `stop` awaits the generator close to completion.
  - LOCK and onset events map to ground truth per served utterance.
- **Evaluation:** `observation_end` is validated against the presented media; the TFMR window is checked.
- **Memory:**
  - Learned ledger entries need lineage.
  - Pending-erasure receipts can be resumed and hold no erased content.
  - A session start with a pending receipt fails closed.

### impl1j + impl2j: round 9

Model gpt-6-sol, verified.
- **impl1j:** 3 PARTIAL, plus 4 new major findings.
- **impl2j:** 2 PARTIAL, plus 5 new findings (1 blocking: the erasure receipt was written after the deletion commit).

Both verdicts: **not ready**. Every finding was accepted and fixed in the next commit (all tests pass).

**Bug found while fixing #4:** the mock recording wrote one frame per chunk, and the simulated client stamped chunk ends with the wall clock, which the speed-up amplified. The recorder now writes exactly `n_frames` per chunk, and the sim reports nominal chunk ends. `chunk_presented` carries `n_frames`.

### impl1k + impl2k: round 10

Model gpt-6-sol, verified.
- **impl1k:** 1 new major finding: a step with abstaining QC never reached a terminal state.
- **impl2k:** 2 PARTIAL, plus 4 new major findings.

Both verdicts: **not ready**. Fixed in the next commit (full suite green in 3 consecutive runs).
- **Deadline sweeper:** an independent step-deadline sweeper, with deadlines scaled by the simulation time scale; a revision resets the step clock.
- **Mapping:** the runner maps an ambiguous chain merge only when it is unambiguous without a revision.
- **Evaluation:**
  - claims are matched by occurrence first, and a three-way dispute stays unresolved;
  - batch commit manifests make `--replace` crash-detectable.
- **Memory:**
  - only the authenticated `user` role asserts facts;
  - erasure selects every residue field, and resume re-selects.
- **Accepted as a documented limit:** swapped equal-length chunks in a recording are undetectable, because frame hashes do not survive lossy encoding.
- **Consequence surfaced by the deadline sweeper:** forward repair of an action rarely fits D = 15 s with 5 s requests. This is recorded in `docs/implementation.md` as a proposal-level decision.

### impl1l + impl2l: round 11

Model gpt-6-sol, verified.
- **impl1l:** 1 PARTIAL, 2 OPEN, plus 3 new major findings.
- **impl2l:** 8 RESOLVED, 1 PARTIAL, plus 5 new major findings.

Both verdicts: **not ready**. Every finding was accepted and fixed in the next commit (full suite green).
- **Honesty correction:** the "2.2 s / 3.6 s on-topic speech onset" in `docs/implementation.md` is re-labelled as an audio-energy onset proxy (a diagnostic), because energy onset is not verified speech.
- **Review status after 11 rounds:** every blocking finding raised so far has been fixed. Each round still produces a few new major findings, increasingly about edge cases (race windows, crash recovery, provenance corner cases). The reviewer has not yet returned "ready".

### taomate_port1: vLLM-Omni port of TaoMate-H3 (USP4 realtime)

Model gpt-6-sol, verified (`docs/reviews/taomate_port1_meta.txt`: rollout models = gpt-6-sol x5). Inlined: the port's `vllm_omni/diffusion/models/taomate_h3/*` (worktree `/data/zhoutaichang/worldmodel/vllm-omni-taomate` @ 1bdfee369) and the reference `external/TaoMate-H3` streaming/teacher/LoRA files. Review: `docs/reviews/taomate_port1_review.md`.
- 6 major, 4 minor findings. Disposition:
  - (1) teacher text refinement: **not a defect** -- the vLLM-Omni DiT re-runs `condition_proj` + token refiner inside every forward (`minimax_h3_transformer.py` `_embed`), with the LoRA disabled for teacher forwards.
  - (2) chunk metadata `session_id` used the request id: **fixed** (now the bound AR session id).
  - (3) commit rollback coverage: **accepted as documented behaviour** -- the AR runner releases the whole session on any failure (`_bound_ar_session`), so no phase is retried against a half-advanced cache; the per-layer replacement during commit is the release's memory-peak design.
  - (4) held five-frame tail on client disconnect: **accepted** -- an aborted session has no consumer; finite frame budgets flush it.
  - (5) audio VAE equivalence: **verified by code** -- `MiniMaxH3AudioVAE.decode_latent` denormalizes with the same mean/std and calls the bundled `decode`, permuting `[2, 1, S]` to `[1, 2, S]`; tail padding is an intentional difference (release raises).
  - (6)(7)(8) parity checks: geometry and sigma ladders are exact against the clone (script, 2026-09-27); LoRA docstring corrected; the Euler update is the same float32 math in a fused op order.
  - (9) request-mode `forward` needs the AR binding: **docstring narrowed** (it is the runner's warmup path, not an offline path).
  - (10) real-time margin: **measured** 4.1 s per 4.958 s request (eager) with per-stage timing now logged (`taomate_h3_log_timings`); rank-0-only output conversion and teacher placement remain open optimizations.

### taomate_port2: two-GPU (USP2) real-time optimization of the TaoMate-H3 port

Model gpt-6-sol, verified (`docs/reviews/taomate_port2_meta.txt`: rollout models = gpt-6-sol). Inlined: `taomate_h3/{cuda_graph,transformer,audio_teacher,pipeline}.py`, the TaoMate prompt handler, the generic prompt handler and `worker/input_batch.py`, the graph tests, the USP2 deploy config and the recipe (worktree @ 66e71a2e0).
- 2 blocking, 6 major, 1 minor. Disposition:
  - (1) blocking, a rank-local capture failure can strand the peer inside a DiT collective before `_agree`: **accepted as the runtime's general property, documented** -- an eager forward that raises on one rank has the same failure mode (the AR runner relies on the NCCL watchdog); hit/miss divergence between ranks cannot occur because both ranks see the same shape sequence and keep their own resident set (keys include the rank's span). Not reproduced (would need a fault injection under a distributed timeout; noted as a check).
  - (2) major, tensors hidden in non-container kwargs would keep stale addresses: **fixed** -- `clone_static` passes tensors inside dicts/lists/tuples, primitives, `torch.device`/`dtype`/`Size` and tensor-free dataclasses, and rejects any other object; `copy_into` refreshes a same-pointer alias whose strides differ. The first version of the guard rejected the branch's `VideoTokenLayout` (plain ints) and silently disabled every teacher graph on the next server start (a 100-request session then ran with the eager teacher at 5.66 s per request, measured locally); a CPU test now clones the real teacher kwargs. Retained outputs across replays are clones (`_clone_outputs`); an eviction test on GPU is still to be run.
  - (3) major, AdaLN bypass and probe scope: **verified by code** -- `ExactProjectionCache.prepare` sets `_key = None` when `max_bytes` is 0, and the lookup misses on `_key is None`, so a capture neither reads nor writes cache entries (eager forwards keep the cache; the projections it caches are exact, so bypassing changes no numerics). A later shape that falls back to the upstream `_embed` (span mismatch) synchronizes inside capture, which raises on both ranks alike and disables graphs (eager fallback) -- the intended behaviour.
  - (4) major, plan identity by counts only: **fixed** -- the plan cache key carries a SHA-1 of the text/audio/video row positions (teacher layouts are functions of the counts, so the digest is a guard, not a behaviour change).
  - (5) minor, fixed-slot equivalence over full forwards: **accepted** -- per-row parity is unit-tested; the full-forward comparison is covered indirectly by the sessions streaming end to end with graphs (no NaN, content changes with prompts); a numeric eager-vs-replay diff on GPU remains a listed check.
  - (6) major, pre-captured lengths can be evicted by out-of-range sessions: **fixed** -- range captures are pinned (never evicted; `stats()` reports `pinned`; growing past `max_entries` with all entries pinned is logged once). Memory per graph is an estimate (recipe now says so).
  - (7) major, prompt-length repair ordering: **verified by code** -- the model runner calls `apply_interaction_at_chunk_boundary(req)` then `prepare_next_chunk(req)` back to back (`diffusion_model_runner.py` ~L1445), so the recorded length precedes the request snapshot whatever phase the update arrived in; all-ones tags are only the fallback when no tags fit (the handler always supplies them). Prompts over 256 tokens run unpinned with a one-time warning and lazy captures (documented).
  - (8) major, "GPU time" label: **fixed in the docs** -- stage sums are wall time with device synchronizations; the client-side period is reported separately (4.98 s mean over ten requests without instrumentation).
  - (9) blocking for the prompt-update workload, sustained real time not shown: **measured, confirmed as a deficit** -- 100 requests with a different 3-60 word prompt every request (measured locally, no instrumentation): 5.14 s per request mean, 5.09 s once warm (requests 20-100), 20 s of request-start drift over 101 requests, four live captures for a 3-token prompt (range lower bound lowered from 8 to 1). The recipe and note state the 3% deficit for that workload, the buffer implication (one second lasts 5-8 requests) and the candidate levers (frame transport off the step loop, prompt re-encode hiding, LoRA-merged FP8 student weights, student CUDA graphs).

### adaptive1: adaptive lessons from a student profile and teacher exercises (8433281, D-038)

Model gpt-6-sol, verified (`docs/reviews/adaptive1_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0e610). Inlined: `live_agent/{student,exercise,lesson}.py`, the commit's diff of director/orchestrator/app/page/persona (`docs/reviews/adaptive1_diff.patch`) and `tests/test_student.py`.
- 4 high, 10 medium. Disposition (fixes in the commit after 8433281, regression tests in `tests/test_student.py`):
  - (1) high, the page could pick any profile id: **partially accepted** -- the page may now pick only ids on the server's `--students` allow-list (default: the single `--student`). There are no per-student accounts in this demo (one shared access token), so real authorization is **open** until user accounts exist.
  - (2) high, erasure left grade / subject / exam fields and the page's copy: **fixed** -- `purge` covers name, grade, concept subjects, notes, history and any exam field; the page gets a fresh view after erasure.
  - (3) high, pending work could re-create erased data: **fixed** -- `_erase_learning` closes a pending exercise that mentions the term (and drops its lines, reminder and answer board) and bumps a profile epoch; grading and exercise generation started before it write nothing.
  - (4) high, a second exercise request replaced the open one: **fixed** -- one exercise at a time (a request while one is open recalls it); a late generation result is dropped if another exercise opened or an erasure intervened.
  - (5) reminder spoken after the answer: **fixed** -- reminders carry the exercise and are dropped when it closes.
  - (6) concurrent saves: **partially accepted** -- unique temp files and a per-process lock; across processes the last writer wins (documented; one generator session at a time in the demo).
  - (7) rule grader false answers: **fixed** -- negations, questions and hedges go to the LLM; "不会" counts only as a whole reply.
  - (8) malformed LLM grading: **fixed** -- `is_answer` / `correct` must be JSON booleans (else the responder handles the utterance); string feedback is one line; the correct option is added unless the feedback states it ("答案是 B" / "选 B").
  - (9) exercise open before its question played: **fixed for the cut case** -- if the opening line is cut before it was shown, the exercise closes and reopens when posed again. Opening on playback acks instead of on lock is **open** (answers during the question are intended to count).
  - (10) superseded grading logged as a decision: **fixed** -- returns an explicit `superseded` outcome; nothing is applied. Re-grading an earlier answer after a newer side question is **not done** (the reminder asks again).
  - (11) requested exercises did not gate the next section: **fixed** -- with a profile, any open exercise holds the next section, and wrong answers during a lesson count as lesson mistakes whatever their source.
  - (12) mistakes leaked across lessons: **fixed** -- cleared on lesson start and stop.
  - (13) mastery claims too strong: **fixed** -- no subject-score prior (only the latest exam's lost points, 0.4); "mastered" needs >= 3 graded exercises; the page labels values as uncalibrated estimates with their source (≈ for exam-derived).
  - (14) personal data spread: **fixed in part** -- prompts carry no exam dates; the durable event log records only `profile_changed` (the view goes to the page on its own message). Retention at the hosted LLM provider is outside this code: **open**, noted for the privacy section.

### curriculum1: student profile page and course knowledge base (b429013..5b8a67c, D-039, D-040)

Model gpt-6-sol, verified (`docs/reviews/curriculum1_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0e870). Inlined: `live_agent/curriculum.py`, `tests/test_curriculum.py`, `tools/check_curriculum.py`, the code diff of the other files (`docs/reviews/curriculum1_diff.patch`), `configs/curriculum/{pedagogy,math}.json` in full and a generated summary of every subject file (`docs/reviews/curriculum1_data_summary.txt`). The other subject files (about 330 KB) were not inlined. Repo dirty at review time (10 files): the uncommitted two-GPU launcher option and the review's own evidence files, none of them reviewed code.
- 4 high, 9 medium, 1 low. Disposition (fixes in the commit after 5b8a67c, regression tests in `tests/test_curriculum.py` and `tests/test_student.py`):
  - (1) high, profiles not separated by student: **partially accepted, open** -- as adaptive1 finding 1: the web server listens on 127.0.0.1 only and is reached through the token-protected proxy, so every token holder can edit every allow-listed profile. Per-student accounts and teacher-only reset are open until the demo has user accounts.
  - (2) high, "初中二年级" parsed as grade 2: **fixed** -- the stage form (初/高 + optional 中) is parsed first; the profile API accepts only a recognisable grade and stores its normalised name (初中三年级 -> 初三; 幼儿园 -> 422).
  - (3) high, reset without a version, work in flight writes into the reset profile: **fixed** -- reset needs the loaded version (409 otherwise); the store counts resets and an open session bumps its profile epoch when the count changes, so grading or exercise generation started before is dropped. Docstring and page now say the saved copy is replaced by the seed.
  - (4) high, "art" matched "Smart Learning"; "三角形" flagged as above grade 7: **fixed** -- English topics match whole words only; the above/below-grade note needs every textbook grade that teaches the topic (same wording or containing it) to be above (below) the student, so a concept taught in several grades is never flagged. Single-character topics still get no curriculum reference (**not done**: too ambiguous to match safely).
  - (5) medium, a real but unrelated chapter accepted as verified: **fixed** -- model picks are candidates (`located`, similarity 0.7, labelled "未核实是否对应本课"), get no requirement from the chapter name and never trigger a grade note; a short partial chapter name no longer counts as a copy; a non-object JSON reply is handled.
  - (6) medium, irrelevant requirement attached: **fixed** -- the requirement must match the asked topic (floor 0.6 instead of 0.5); the chapter name contributes only when the chapter itself is a strong match; requirements are labelled "意译".
  - (7) medium, senior-high categories as fixed grades: **fixed** -- stage ranges from grade 10 render as "课标高中阶段（具体年级各校安排不一）", grades 11-12 as estimates, no grade note between senior-high grades, math grade 12 basis set to `estimate` (its own notes said so).
  - (8) medium, delete/clear did not do what the page says: **fixed** -- deleting a concept also removes it from the exams' lost-point lists (else it came back from the exam); "clear history" erases the exercise evidence (history, attempts, notes, exercise-based estimates; teacher-set estimates stay); the page wording for clear and reset matches.
  - (9) medium, weak API validation, half-applied saves: **fixed** -- the whole request is validated before anything changes (types, lengths, finite mastery in [0, 1], score within full, edit counts); a bad field returns 422 and nothing is applied.
  - (10) medium, locator latency, cache and prompt injection: **fixed in part** -- topics are one line of at most 40 characters without control characters or 「」 before they reach any prompt; concurrent lookups of the same topic share one model call. The 16k-character index is still sent per new topic (3-6 s, measured locally in D-040; cached afterwards), and picks stay cached per topic across grades (they are re-ranked by grade on use) -- **accepted as is**.
  - (11) medium, grade guidance vs the 22-character line limit, repeated context, labels: **fixed** -- every teaching block states the spoken-line limit as a hard rule that overrides its sentence lengths and is headed as editorial advice with estimated numbers; the per-utterance responder gets the brief form (tone, wording, feedback) instead of the full profile.
  - (12) medium, claims more precise than their support: **fixed in the data** -- grade 5 no longer claims the end-of-stage 3000 characters; the Wikipedia Piaget summary is `secondary`; a note states which fields are cited and which are estimates. Per-field labels inside each grade's text are **not done** (the prompt header carries the label).
  - (13) medium, version check only process-local: **rejected with evidence** -- `run_live.sh` starts one uvicorn process (no workers option) and the generator allows one live session at a time; documented in D-039's open points.
  - (14) low, validator reports success with broken provenance: **fixed** -- a source without URL, a requirement block without source, a grade without source or with an unknown `basis`, and a missing grade inside the subject's range are errors unless documented in the file's new `gaps` (地理 and 信息科技 grade 9: not taught in the 2022 compulsory scheme).

### lipsync1: lip sync on the demo page and its measurement (on top of 1da3243, D-044)

Model gpt-6-sol, verified (`docs/reviews/lipsync1_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0f2f7). Inlined: the page diff (`docs/reviews/lipsync1_page.patch`), `tools/av_sync.py`, `scripts/lipsync_page_check.py`, `tests/test_av_alignment.py`, `live_agent/generator/fmp4.py`, the measurements (`docs/reviews/lipsync1_results.md`).
- 2 high, 5 medium, 1 low. Disposition (fixed before commit; re-reviewed as lipsync2):
  - (1) high, chunk_end sent from audio `onended` with an incomplete `painted` list when the picture is delayed: **fixed** -- render sends chunk_end when the picture reaches the end; onended only covers a stalled render loop (hidden tab: at once; else after 1 s + the offset).
  - (2) high, zero-padded high-pass put spikes at every run's edges: **fixed** -- run mean removed and ends mirrored; model offsets remeasured (-44.8 / -37.9 ms, peak correlation 0.118 -> 0.161).
  - (3) medium, interval conditioned on the selected lobe; absolute zero unvalidated: **fixed in the report, partly open** -- unrestricted interval and main-lobe share reported, long runs split into 10 s pieces; five real speakers (Wikitongues, CC BY / BY-SA) measured the same way give -167..+79 ms (median -79); the model's -45 ms lies inside, so no server-side shift. An independently synchronised reference (e.g. a clapperboard recording) is still missing: the method cannot certify absolute sync better than that spread.
  - (4) medium, an offset change could strand the picture on a removed chunk: **fixed** -- chunks are kept until `t >= end + 0.35 s`. The new offset-change check then found a worse bug: moving back gave a negative frame index, drawImage threw, and the render loop stopped for the rest of the session; the draw now requires `t >= start`, clamps the index, and a render error can no longer stop the loop.
  - (5) medium, one-refresh display compensation unverified: **partially accepted** -- labelled as an estimate in the code and README (no page API gives the photon time); the beep-and-flash test lets the viewer correct the whole chain by eye and ear.
  - (6) medium, fallback clock subtracted only one latency stage: **fixed** -- baseLatency + outputLatency.
  - (7) medium, page check compared the page against its own heard time: **fixed** -- injected output delays (getOutputTimestamp reporting 250 ms; the fallback) checked against AudioContext.currentTime; offset change mid-playback, stop on a new comment, and reconnect checks added; alignment tests use the 34/34/34/17 shape (the recorder's `-shortest` mux may trim the last tens of ms of audio at the very end of a recording: noted, not a sync effect). Physical capture (camera + microphone on a real screen and headset) is **open**: not possible on this host.
  - (8) low, calibration during playback / repeated clicks / ducking: **fixed** -- a second click cancels the first run, beeps bypass the push-to-talk gain, help text says to test when the teacher is quiet and after changing headsets, a device-change notice appears when an offset is set.

### lipsync2: lip sync, fixes for round lipsync1 (D-044)

Model gpt-6-sol, verified (`docs/reviews/lipsync2_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0f313). Inlined: the page diff, `tools/av_sync.py`, `scripts/lipsync_page_check.py`, `tests/test_av_alignment.py`, the results (`docs/reviews/lipsync2_results.md`, with the five reference speakers).
- 1 blocking, 3 major, 1 minor. Disposition (fixed before commit; re-reviewed as lipsync3):
  - (1) blocking, retention covered 0 -> +300 ms only: **fixed** -- chunks stay drawable for the whole slider swing (`end + 0.65 s`); the page check moves -300 -> +300 and +300 -> -300 mid-playback (live stack: longest pause between paints 17.3 / 23.1 ms, right frames).
  - (2) major, caption / board / painted evidence on backward moves: **fixed for caption and board** -- they follow the chunk on screen in either direction (each chunk carries the board view in effect), checked per paint; **painted evidence not re-sent (accepted as is)** -- the server uses it conservatively (QC frames restricted to painted ones, E = last painted frame), so a revisited frame missing from the list never claims an unseen frame, and frames skipped by a forward move are correctly absent.
  - (3) major, onended fallback before a healthy render loop reached the end: **fixed** -- it acks only in a hidden tab or when no animation frame ran for 0.5 s, re-checking every 250 ms.
  - (4) major, absolute zero: **open** (as lipsync1 finding 3): no independently synchronised reference here; no server-side shift because the model's offset lies inside the real-speech spread measured the same way, and each viewer can correct the whole chain.
  - (5) minor, wire test bypassed the transport: **fixed** -- a test runs `WSTransport.send_chunk` against a fake socket and decodes the header, H.264 segment and PCM with PyAV (click at its flash frame within one sample, 34/34/34/17 shape).

### craft1: teaching-craft knowledge base and the enriched lesson workflow (c9b9cba, D-043)

Model gpt-6-sol, verified (`docs/reviews/craft1_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0f331). Inlined: `live_agent/lesson.py`, `live_agent/curriculum.py`, `tests/test_curriculum.py`, the diff of orchestrator / app / exercise / validator / implementation doc (`docs/reviews/craft1_diff.patch`), the D-043 entry, the measured runs (`docs/reviews/craft1_runs.txt`) and `configs/curriculum/teaching_craft.json` in full. The five research notes (~430 KB) and the synthesis report were not inlined. A first launch aborted before the model ran (the run log had a byte-cut character; rebuilt as valid UTF-8, one extra commit).
- 0 blocking, 4 high, 5 medium. Disposition (fixes in the commit after c9b9cba, regression tests in `tests/test_curriculum.py`):
  - (1) high, the self-check's pass rule was not enforced (the judge's "pass" accepted, scores for nonexistent items accepted): **fixed** -- `check_section` requires one integer 0-2 per applicable item (else `ValueError`, logged as `check_failed`, no verdict) and computes `pass` itself (no 0, at most three 1s).
  - (2) high, a rewrite could drop the planned exercise or the mistakes-first correction: **fixed** -- `rewrite_keeps` rejects a rewrite that lost the exercise or no longer names the last mistake's concept in its first point when the original did (`revise_rejected` event, original plays). A section whose planned exercise the model produced malformed still plays without one (the section event records `exercise: null`): **open**, noted (a fallback through `make_exercise` is the candidate fix).
  - (3) high, the subject cross-check tested membership, not agreement with the topic; `subject_of` could prefer a weak lexical hit: **fixed** -- the curriculum's placement (a lexical match with similarity >= 0.8, else a cached locator pick) always wins; the model's label is used only when the curriculum has no placement and knows the label; `subject_of` returns "" for weak hits; the outline prompt lists the curriculum's own subject names; the outline event logs `subject_source` (placed vs model).
  - (4) high, "wait time / pupil tries first" moves become monologue while the checklist credits them as participation: **accepted, made explicit** -- the section prompt, the craft header and the checklist now say the script's questions are self-answered and only exercises are answered by the student; `student_action` counts only exercises, tries and restatements. Real pause-and-answer questions in the script are **open** (the exercise mechanism is the available pause).
  - (5) medium, conflicting constraints for review sections; unchecked outline counts: **fixed in part** -- a review section's board is 1-3 points (`MIN_ITEMS` by depth); exercises are capped at three per lesson; sections stay capped at six. Objective count, intro part count vs section count and topical relevance of `main` sections are **not checked** deterministically (noted).
  - (6) medium, `道德与法治/思想政治` cannot match the outline prompt's `道德与法治`: **fixed** -- the outline prompt lists the curriculum's subject names verbatim (the fuzzy containment fallback stays).
  - (7) medium, doubled lookahead does not bound a `revise` playback gap: **fixed in part** -- judge + rewrite run under a 30 s deadline (`lesson_revise_deadline_s`; on expiry the original plays, `revise_timeout` logged). A time-based buffer and a live measurement with exercise waits are **open**.
  - (8) medium, provenance labels stronger in the decision log than in the data checks: **fixed** -- every uncited number in the craft file is marked （估计） or （引用） (the validator warns on unlabelled numbers outside example lines); the craft header says "未标「引用」的数字为估计"; masters carry `kind` (teacher / school / system) and `evidence` (documented results, positions, reported lessons) separately from `honours` (verified titles only; 9 entries have evidence only, as warnings); D-043 now says "34 entries (30 teachers, 1 school, 3 systems)" and "three of four closings had a 延伸". Whether a source supports a claim is still not machine-checked (the notes' cited/secondary labels are the audit trail).
  - (9) medium, knowledge-base text reaches writer prompts without a trust boundary: **fixed** -- `clean()` strips control characters and caps an entry at 200 characters; the validator rejects control characters and over-long text; the craft header states the block is reference material, not instructions.
  - Decision-log claims the reviewer could not verify from the inlined material (that the sources substantiate each honour or move, that the skill port works, that lessons improve learning): stated as such in D-043; the recommended blinded paired comparison (old vs enriched prompts, independent teacher ratings, judge-vs-human agreement, playback gaps) is the open evaluation.

### lipsync3: lip sync, fixes for round lipsync2 (D-044)

Model gpt-6-sol, verified (`docs/reviews/lipsync3_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0f32e). Inlined: the page diff, `scripts/lipsync_page_check.py`, `tests/test_av_alignment.py`, the results (`docs/reviews/lipsync3_results.md`). Round-2 findings 1, 5 closed; 3 fixed for a healthy render loop; 4 open as reported.
- 2 major, 1 minor. Disposition (re-reviewed as lipsync4):
  - (1) major, end evidence stale after a backward move: **accepted as a snapshot (the reviewer's second option)** -- the first chunk_end is final; paints after it (the slider taking the picture back into an ended chunk) are not reported, so `painted` stays conservative and E is a lower bound in that case; commented at the send and in D-044. Re-sending evidence would change the ack protocol for a slider-drag corner case.
  - (2) major, the fallback could wait forever while rendering throws: **fixed** -- it looks at `lastGoodRender` (set only after a frame renders without an error).
  - (3) minor, the check did not force re-entry into an ended chunk or check the board: **fixed** -- the page switches the offset right after a boundary between requests; the check asserts the first paint after a backward switch is the chunk that just ended (chunk_end sent) and that every paint shows its own chunk's caption and board.

### lipsync4: lip sync, fixes for round lipsync3 (D-044)

Model gpt-6-sol, verified (`docs/reviews/lipsync4_meta.txt`: rollout models = gpt-6-sol x5, thread 01a0f33e). Inlined: the page diff, `scripts/lipsync_page_check.py`, the live results (`docs/reviews/lipsync4_results.md`). No new functional defect; round-3 fixes confirmed (render fallback by inspection, ended-chunk caption and board by the live trace); the snapshot limitation stands as accepted.
- 1 major (open), 2 minor. Disposition:
  - (1) major, absolute lip sync unverified physically: **open** -- the checks verify the page's clock arithmetic (including injected output delays) but not light and sound at the viewer; a camera + microphone recording of the calibration flash and beep on a real screen and headset would settle it. Not possible on this host; the owner can check with the page's beep-and-flash test.
  - (2) minor, the render-error fallback was untested: **fixed** -- the check makes every frame's rendering throw for 4 s and requires chunk_end from the audio clock (3 sent on the mock and on the live stack) and drawing to resume after.
  - (3) minor, the offset check's pass condition did not require its boundary: **fixed** -- it requires a request boundary, the ended chunk kept and re-entered, and with `--expect-boards` (a lesson playing) that the line and board differ across it; the live lesson run passes all of them.
