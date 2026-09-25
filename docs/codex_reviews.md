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
