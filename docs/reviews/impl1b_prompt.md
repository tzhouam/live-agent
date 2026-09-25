You are the independent reviewer (Codex, GPT-6 Sol) for the live-agent project, Phase 2 checkpoint "impl1b" (round 2):
the **implementation of the A2 control path** against the Chinese proposal `docs/research_proposal_zh.md` v2.11
(inlined), plus the TaoMate-H3 generator adapter and its local measurements.

Review goals, in priority order:
1. **Correctness bugs** in the control path: the single timeline (lock → teacher → student → presented),
   just-in-time locking (P_{k+1} = V_k + R − Λ − σ), KV/order constraints, barge-in and erasure (drop unpresented,
   bridging, generator reset), deadlocks and races in the asyncio orchestration, QC → repair → earliest correctable
   request, "done" spoken only after verification, capability gating (emit/degrade/refuse), prompt compilation.
2. **Fidelity to the proposal:** anything the proposal specifies as mandatory for A2 that is missing, or behaves
   differently, or places where the implementation would make a later E2 result invalid (confounds between A1 and A2,
   leakage between the online judge and the primary outcome, mis-timed events).
3. **Adapter** (`taomate_h3.py`, `SessionView`): session isolation, request numbering, stale chunks, error paths,
   resource leaks on shutdown or cancellation.
4. **Honesty of claims** in `docs/implementation.md` and `docs/m0_measurements.md`: is each claim supported by the
   code and the numbers described, are the number labels right, and is anything overstated?

Output format: a numbered list of findings. For each: severity (blocking / major / minor), file and line or function,
the concrete failure scenario, and the fix. Then a one-line verdict: "ready for E1/E2 pilot", "ready after fixes",
or "not ready". Do not praise; do not restate the code. If you find nothing in a category, say so briefly.

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

===== FILE: docs/reviews/impl1_review.md =====
1. **Blocking — `orchestrator.py:on_presented`.** The expected chunk count is `len(self.chunks[k])`, which can be 1–3 while generation is still running. If playback catches up with generation, an ack for the first chunk can trigger QC and even finish a bounded run before the other chunks exist. Require all four chunk-end acks, schedule QC once, and reject acks for dropped requests.

2. **Blocking — `director.py:on_verified`; `orchestrator.py:_run_checks`.** A verdict from an old plan can complete a revised intent chain. If the user changes “drink tea” to “wave” while tea QC is running, a late tea verdict marks the chain complied and queues “好了。” Check the request’s plan version, revision and step against the chain’s current state before applying any verdict.

3. **Blocking — `director.py:_apply_decision`, `next_script`, `on_verified`.** Multistep segments are queued and locked without waiting for the preceding step to be presented and verified. A failed first step can therefore be followed by step two before its repair; `step_index` advances on any positive verdict without checking the step number. Release each step only after its predecessor passes, and bind verdicts and retries to explicit step IDs.

4. **Blocking — `orchestrator.py:_erase`; `director.py:_open_chains`.** Erasure resets the generator but leaves open chains, pending corrections, scripts, prompts and ledger history containing the deleted term. A later responder call includes an old chain’s `final_intent` in `open_chains`, reintroducing the erased fact. Quiesce locking and QC, remove affected controller state and stored artifacts, then reset; process a forget request before recalling the fact for that request.

5. **Blocking — `server/app.py:WSTransport.stop_playback`; `sim.py:SimClient.stop_playback`.** The WebSocket stop waits behind an entire chunk’s JPEG send under `_send_lock`; the simulator drains queued chunks but lets the current chunk finish and acknowledge. Neither path establishes immediate barge-in, and late acks can still drive QC. Interrupt the active send and playback, send stop promptly, and invalidate subsequent acks for the interrupted generation.

6. **Major — `timeline.py:LockScheduler.lambda_estimate`.** It estimates Λ from lock-to-first-chunk time, including the wait for the previous request’s KV. M0 reports about **1.5 s** idle lead but **3.6–4.5 s** pipelined lead. Feeding the latter into \(P_{k+1}=V_k+R-\Lambda-\sigma\) moves locking toward presentation start, defeating the stated just-in-time policy. Measure teacher plus first-chunk readiness separately from KV waiting, and test the `done_k` prerequisite.

7. **Major — `orchestrator.py:_repair`; `timeline.py:earliest_correctable`.** `chain_cost_s` measures only correction synthesis after the VLM verdict. It omits VLM time, compilation, audit and text encoding; moreover `queue_retry` puts the repair into the next unlocked request regardless of `j_planned`. The logged “earliest correctable” request can disagree with the one that receives the repair. Time the full \(E\rightarrow\) lock-ready chain and reserve the computed request explicitly.

8. **Major — `orchestrator.py:_run_checks`; `qc/judge.py:SpeechCheck`; `orchestrator.py:_lock_loop`.** Speech ASR runs synchronously **after** the request has been presented, and no pre-generation script audit appears in the lock path. The proposal requires script audit before generation and, when feasible, generated-audio ASR within σ before playback. Move these checks to their specified gates, make ASR nonblocking, and record when preplay verification misses its deadline.

9. **Major — `director.py:next_script`, `on_verified`.** The “done only after verification” rule is enforced through the LLM prompt, not on arbitrary LLM lines. A line containing a past-tense completion can be spoken before QC; the code only detects completion language in A1. Gate completion wording in A2 against a current verified action, and log a completion claim when its audio is actually presented rather than when its prompt locks.

10. **Major — `server/app.py:ws_endpoint`.** The single WebSocket receive loop awaits responder LLM and ASR work. During that wait it cannot read presentation acks or another `speech_start`, so QC evidence and barge-in timing are delayed by model latency. Dispatch input work separately while continuously receiving and timestamping control messages.

11. **Major — `director.py:_apply_decision`; `orchestrator.py:_lock_loop`.** Every new utterance clears unsent segments, but displaced unrelated chains remain `OPEN`; `capacity_skips` is never populated or logged. Those chains silently disappear from service and their required failure accounting. Distinguish user revisions from capacity replacement, mark displaced chains `CAPACITY_SKIPPED`, and emit the event.

12. **Major — `capability.py:Capability.usable`; `director.py:_apply_decision`.** Default gating accepts `EXECUTED` capabilities without a success estimate, although E1 human-validated calibration is the proposed reliability gate. Conversely, an unsupported action returned with an empty intent can bypass `decide`, producing a spoken refusal with no refusal event. Require calibrated evidence for E2 A2 gating and route every unsupported action through an explicit degrade/refuse decision.

13. **Major — `director.py:DirectorMode.OPEN_LOOP`, `next_script`.** A1 still uses the A2 intent schema, manifest phrases, canon compiler and ledger-derived responder context. It is therefore not the proposal’s “LLM directly writes the next request prompt” comparator. Implement that comparator and keep backbone, memory, input and presentation paths matched before interpreting A2−A1.

14. **Major — `director.py:next_script`; `orchestrator.py:_run_checks`; `ledger.py`.** Content and memory instructions get speech checks at most; they have no online question or compliance path, so they cannot receive forward repair. The specified drift detector and its three interventions are also absent from the active path. Add task-specific checks and drift triggers, or narrow the A2 pilot and its claims to implemented action tasks.

15. **Major — `generator/base.py:SessionView.reset`, `chunks`; `taomate_h3.py:reset`.** `SessionView` filters chunks only by the offset set at session start. After a reset within that view, chunks already queued from the old generator epoch still have indices above that offset and can be yielded as current output. Tag and filter chunks and timings by generation epoch, drain queued output, and acknowledge reset before new submissions.

16. **Major — `orchestrator.py:start`, `_chunk_loop`, `stop`; `server/app.py:ws_endpoint`; `taomate_h3.py:start`.** A worker error makes the chunk task raise without setting `_stop` or notifying the client; `wait_done` can hang. `stop` cancels tasks without awaiting them. The server also acquires `session_lock` before `orch.start()` but enters its release `finally` only afterward, so startup failure strands the shared generator. Supervise tasks, propagate fatal errors, await cancellation, and put startup and lock acquisition inside cleanup guards.

17. **Major — `server/app.py:WSTransport.on_client_message`; `docs/m0_measurements.md`.** Presentation times are server arrival times for client messages, not measured times of the last displayed frame or heard audio. Network delay and client buffering shift \(V_k\), \(E\), TVC and correction eligibility. Collect client media-clock timestamps with clock mapping and frame-level evidence before using the browser path for timing conclusions.

18. **Major — `types.py:Chunk.encoded`; `server/app.py:WSTransport`; `docs/implementation.md`.** T3 specifies per-chunk fMP4, but the implementation sends JPEG frames and PCM, and M0 explicitly says `Chunk.encoded` is unimplemented. The simulated-client M1 run therefore does not qualify the specified encoding, transport and browser playback path. Implement and measure that path, then run the required soak and whole-system qualification.

19. **Minor — `docs/m0_measurements.md:Parity with the released path`, `docs/implementation.md:Verified so far`.** Video latent differences of 0.39–0.42 exceed the cited released-run variation of 0.31–0.37; those few comparisons cannot support “no evidence of a systematic deviation.” The “real time” wording is supported as short-run adapter throughput, not sustained or client-qualified operation. State those narrower measured claims.

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

- **E1:** a judge-only pilot (5 trials per capability) is the next step. Validated calibration needs the 20%
  human sample.
- **Primary outcome:** nothing has been adjudicated yet. The tool exists; annotators are needed.
- 30-min soak, 768p/1080p, 60 s+ sessions on the TaoMate path, and the browser playback path on a remote
  client (σ, jitter) are not yet measured. The M1 run used the simulated client on the server host.
- None of the simulation outputs are experimental results. The mock judge's success probability is an
  input, not a measurement.

===== FILE: live_agent/types.py =====
"""Core data types shared by every component.

The names follow docs/research_proposal_zh.md (v2.11): a *request* is one 5-second
TaoMate-H3 generation unit (4 chunks); a *BlockScript* is our internal description of
one request; an *intent chain* is the scoring unit for instruction following.
All times are monotonic seconds on the shared presentation timeline unless noted.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def now() -> float:
    return time.monotonic()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------- persona


@dataclass(frozen=True)
class CanonProfile:
    """Persona canon: fields repeated verbatim in every request; never rewritten by an LLM."""

    persona_id: str
    subject: str  # e.g. "a young East Asian woman (S1) in a green hanfu, ..."
    scene: str
    camera: str
    voice: str
    language: str = "Chinese"  # tag inside <d>[...]</d>
    speech_language: str = "Mandarin"  # used in the soundscape description
    negative: str = (
        "No other person or human voice appears. "
        "No captions or readable text appear anywhere in frame."
    )


# --------------------------------------------------------------------------- scripts


@dataclass
class CheckQuestion:
    """A verifiable yes/no question generated at compile time (online VQQA)."""

    qid: str
    text: str
    kind: str = "action"  # action | speech | identity | scene
    deadline_s: float = 15.0


@dataclass
class BlockScript:
    """Internal description of one 5-second request (see proposal §9)."""

    request_index: int
    plan_version: int
    canon: CanonProfile
    action: str  # must match a capability-manifest entry (or "" for idle)
    transcript: str  # spoken line; "" for silence
    soundscape: str = "Quiet room tone."
    corrections: list[str] = field(default_factory=list)  # forward corrections / textual drift fixes
    checks: list[CheckQuestion] = field(default_factory=list)
    chain_ids: list[str] = field(default_factory=list)  # intent chains this request serves
    provenance: dict[str, Any] = field(default_factory=dict)
    capability_ids: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- instructions


class ChainStatus(str, enum.Enum):
    OPEN = "open"
    COMPLIED = "complied"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"  # user withdrew: excluded from the primary denominator
    CAPACITY_SKIPPED = "capacity_skipped"  # dropped by admission control: counts as failure
    REFUSED = "refused"  # compiler refused / degraded: counts as failure


class TaskKind(str, enum.Enum):
    ACTION = "action"
    CONTENT = "content"
    MULTISTEP = "multistep"
    CORRECTION = "correction"
    MEMORY = "memory"
    CHAT = "chat"


@dataclass
class Utterance:
    uid: str
    speaker: str  # "user" | "persona" | "viewer:<id>"
    text: str
    t_end: float  # VAD endpoint on the shared timeline
    session_id: str = ""
    scope: str = "private"


@dataclass
class IntentChain:
    """Scoring unit: one instruction plus the user's later revisions (proposal §14.3)."""

    chain_id: str
    kind: TaskKind
    opened_by: str  # utterance id
    final_intent: str
    clock_origin: float  # end of the opening or latest revising utterance
    revisions: list[str] = field(default_factory=list)
    status: ChainStatus = ChainStatus.OPEN
    steps: list[str] = field(default_factory=list)  # for multistep
    step_index: int = 0
    first_compliant_t: float | None = None
    requests: list[int] = field(default_factory=list)


# --------------------------------------------------------------------------- timeline


class EventType(str, enum.Enum):
    UTTERANCE_END = "utterance_end"
    LOCK = "lock"  # P_k: script frozen
    TEACHER_START = "teacher_start"
    TEACHER_DONE = "teacher_done"
    STUDENT_START = "student_start"
    CHUNK_READY = "chunk_ready"
    CHUNK_PRESENTED = "chunk_presented"  # client presentation ack (start of chunk)
    CHUNK_PRESENTED_END = "chunk_presented_end"
    REQUEST_DONE = "request_done"
    VERDICT = "verdict"
    INTERRUPT = "interrupt"
    PLAYBACK_STOP = "playback_stop"
    COMPLETION_CLAIM = "completion_claim"
    REFUSAL = "refusal"
    CAPACITY_SKIP = "capacity_skip"
    REPAIR = "repair"
    SPEECH_ONSET = "speech_onset"
    AUDIT = "audit"  # pre-generation script audit (proposal §15)
    NARRATION_GUARD = "narration_guard"  # completion wording removed from an unverified line
    ERROR = "error"
    OBSERVATION_END = "observation_end"


@dataclass
class TimelineEvent:
    type: EventType
    t: float
    request_index: int | None = None
    chunk_index: int | None = None
    data: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- generation


@dataclass
class Chunk:
    """One generated chunk (audio+video) of a request."""

    request_index: int
    chunk_index: int  # 0..3 within the request
    n_frames: int
    fps: float
    video: Any = None  # np.ndarray [T,H,W,3] uint8, or None for mock
    audio: Any = None  # np.ndarray [S, C] float32
    sample_rate: int = 32000
    encoded: bytes | None = None  # fMP4 fragment, if the generator encodes
    t_ready: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)  # e.g. prompt, session id

    @property
    def duration_s(self) -> float:
        return self.n_frames / self.fps


# --------------------------------------------------------------------------- QC


class VerdictLabel(str, enum.Enum):
    COMPLIED = "complied"
    NOT_COMPLIED = "not_complied"
    UNKNOWN = "unknown"


@dataclass
class Verdict:
    qid: str
    request_index: int
    label: VerdictLabel
    confidence: float
    rationale: str = ""
    t_evidence: float = 0.0  # E: presentation time of the last frame needed
    t_verdict: float = 0.0

===== FILE: live_agent/capability.py =====
"""Capability manifest: what the generator is *measured* to render reliably (proposal §8, §14.2).

Each entry maps an intent (e.g. "drink_tea") to the exact English action phrase that
goes into the H3 prompt, plus calibrated statistics from experiment E1. The compiler
only emits entries whose status is at least ``executed`` and whose success rate is
above threshold; everything else is degraded (e.g. to a verbal reply) or refused.
Refusals and degradations are logged and count as failures in scoring.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


class Status(str, enum.Enum):
    DOCUMENTED = "documented"
    CODE_READ = "code_read"
    EXECUTED = "executed"  # rendered at least once in M0/M1
    CALIBRATED = "calibrated"  # E1 statistics available

    @property
    def rank(self) -> int:
        return ["documented", "code_read", "executed", "calibrated"].index(self.value)


@dataclass
class Capability:
    cap_id: str
    intent: str  # canonical intent key, e.g. "drink_tea"
    phrase: str  # exact action phrase used in the prompt
    aliases: list[str] = field(default_factory=list)  # user-language triggers (中文/English)
    status: Status = Status.DOCUMENTED
    p_success: float | None = None  # E1: fraction judged compliant within deadline
    p_ci: tuple[float, float] | None = None
    tvc_median_s: float | None = None
    side_effects: list[str] = field(default_factory=list)
    check_question: str = ""  # default QC question for this action
    degrade_to: str = ""  # verbal fallback line when refused/degraded

    def usable(self, min_status: Status, min_p: float) -> bool:
        if self.status.rank < min_status.rank:
            return False
        if self.status == Status.CALIBRATED and (self.p_success or 0.0) < min_p:
            return False
        if self.p_success is not None and self.p_success < min_p:  # measured (e.g. judge-only E1) below threshold
            return False
        return True


class Decision(str, enum.Enum):
    EMIT = "emit"
    DEGRADE = "degrade"
    REFUSE = "refuse"


@dataclass
class CompileResult:
    decision: Decision
    capability: Capability | None
    reason: str


class CapabilityManifest:
    def __init__(self, caps: list[Capability], *, min_status: Status = Status.EXECUTED, min_p: float = 0.6):
        self.caps = {c.cap_id: c for c in caps}
        self.min_status = min_status
        self.min_p = min_p

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: str | Path, **kw) -> CapabilityManifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        caps = []
        for d in data["capabilities"]:
            d = dict(d)
            d["status"] = Status(d.get("status", "documented"))
            if d.get("p_ci") is not None:
                d["p_ci"] = tuple(d["p_ci"])
            caps.append(Capability(**d))
        return cls(caps, min_status=Status(data.get("min_status", kw.get("min_status", "executed"))),
                   min_p=data.get("min_p", kw.get("min_p", 0.6)))

    def save(self, path: str | Path) -> None:
        out = {
            "min_status": self.min_status.value,
            "min_p": self.min_p,
            "capabilities": [
                {**asdict(c), "status": c.status.value} for c in self.caps.values()
            ],
        }
        Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ lookup
    def match(self, text: str) -> Capability | None:
        """Find the capability whose intent or alias occurs in ``text`` (longest alias wins)."""
        best: tuple[int, Capability] | None = None
        low = text.lower()
        for c in self.caps.values():
            for a in [c.intent, *c.aliases]:
                if a and a.lower() in low and (best is None or len(a) > best[0]):
                    best = (len(a), c)
        return best[1] if best else None

    def by_intent(self, intent: str) -> Capability | None:
        for c in self.caps.values():
            if c.intent == intent:
                return c
        return None

    def decide(self, intent: str) -> CompileResult:
        cap = self.by_intent(intent)
        if cap is None:
            return CompileResult(Decision.REFUSE, None, f"no capability for intent {intent!r}")
        if cap.usable(self.min_status, self.min_p):
            return CompileResult(Decision.EMIT, cap, "ok")
        if cap.degrade_to:
            return CompileResult(Decision.DEGRADE, cap, f"status={cap.status.value} p={cap.p_success}")
        return CompileResult(Decision.REFUSE, cap, f"status={cap.status.value} p={cap.p_success}")

    def update_from_calibration(self, cap_id: str, *, successes: int, trials: int,
                                ci: tuple[float, float], tvc_median_s: float | None,
                                validated: bool = False) -> None:
        """Record an E1 estimate. Only human-validated labels (judge agreement checked on the 20%
        sample) make a capability ``calibrated``; a judge-only pass marks it ``executed``."""
        c = self.caps[cap_id]
        c.status = Status.CALIBRATED if validated else Status.EXECUTED
        c.p_success = successes / trials if trials else 0.0
        c.p_ci = ci
        c.tvc_median_s = tvc_median_s

===== FILE: live_agent/ledger.py =====
"""State ledger: online CANVAS + A²RD continuity layer (proposal §8.2 layer 3, §10.4).

The ledger keeps
- the immutable canon (persona appearance, scene, camera, voice) -- never overwritten;
- the *current* state that may legitimately change (props and who holds them, pose,
  whether the book is open, what was last done/said) -- updated only from events that
  were *presented* (and, for claimed completions, verified);
- per-request textual state (A²RD style) for audit and for composing the next request.

It produces the canon block for each BlockScript and the textual drift corrections
("the hairpin is jade, not gold") used by the text-correction intervention.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from live_agent.types import CanonProfile


@dataclass
class PropState:
    name: str
    location: str  # e.g. "on the desk"
    carrier: str | None = None  # "S1" when held


@dataclass
class RequestState:
    request_index: int
    action: str
    transcript: str
    presented: bool = False
    verified: dict[str, str] = field(default_factory=dict)  # qid -> verdict label
    identity_score: float | None = None
    notes: str = ""


class StateLedger:
    def __init__(self, canon: CanonProfile, props: list[PropState] | None = None):
        self._canon = canon
        self.props: dict[str, PropState] = {p.name: p for p in (props or [])}
        self.pose: str = "seated at the desk"
        self.history: list[RequestState] = []
        self.generated_not_presented: list[int] = []  # requests generated but never shown

    # ---------------------------------------------------------------- canon
    @property
    def canon(self) -> CanonProfile:
        return self._canon  # frozen dataclass: cannot be mutated

    @classmethod
    def from_config(cls, path: str | Path) -> StateLedger:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        canon = CanonProfile(
            persona_id=d["persona_id"], subject=d["subject"], scene=d["scene"],
            camera=d["camera"], voice=d["voice"], language=d.get("language", "Chinese"),
            speech_language=d.get("speech_language", "Mandarin"),
            negative=d.get("negative", CanonProfile.__dataclass_fields__["negative"].default),
        )
        props = [PropState("book", "open on the desk"), PropState("teacup", "on the desk"),
                 PropState("teapot", "on the desk")]
        return cls(canon, props)

    # ---------------------------------------------------------------- updates
    def record_request(self, request_index: int, action: str, transcript: str) -> None:
        self.history.append(RequestState(request_index, action, transcript))

    def redact(self, term: str) -> int:
        """Erasure: remove a term from per-request history (it feeds continuity / bridging text)."""
        n = 0
        for r in self.history:
            for f in ("action", "transcript", "notes"):
                v = getattr(r, f)
                if term in v:
                    setattr(r, f, v.replace(term, "[已删除]"))
                    n += 1
        return n

    def mark_presented(self, request_index: int) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.presented = True
        if request_index in self.generated_not_presented:
            self.generated_not_presented.remove(request_index)

    def mark_generated_not_presented(self, request_index: int) -> None:
        """Interrupt case (proposal §10.5, option 3): content exists in generator state but was not shown."""
        if request_index not in self.generated_not_presented:
            self.generated_not_presented.append(request_index)

    def apply_verified_action(self, intent: str) -> None:
        """Update prop/pose state after an action was *verified* on presented frames."""
        if intent == "stand_up":
            self.pose = "standing beside the desk"
        elif intent in ("put_down_book",):
            self.props.setdefault("book", PropState("book", "on the desk")).location = "closed on the desk"
            self.props["book"].carrier = None
        elif intent == "pick_up_book":
            self.props.setdefault("book", PropState("book", "")).carrier = "S1"
            self.props["book"].location = "held open in her hands"
        elif intent == "drink_tea":
            self.props.setdefault("teacup", PropState("teacup", "on the desk")).location = "on the desk"

    def record_verdict(self, request_index: int, qid: str, label: str) -> None:
        for r in self.history:
            if r.request_index == request_index:
                r.verified[qid] = label

    # ---------------------------------------------------------------- prompt helpers
    def continuity_sentence(self) -> str:
        """Current (non-canon) state restated each request, e.g. pose and held props."""
        held = [p.name for p in self.props.values() if p.carrier == "S1"]
        parts = [f"S1 is {self.pose}"]
        if held:
            parts.append("holding the " + " and the ".join(held))
        return ", ".join(parts)

    def bridging_note(self) -> str | None:
        """If generated-but-unshown content exists, return an explicit bridging instruction."""
        if not self.generated_not_presented:
            return None
        return "S1 calmly returns to her previous posture and looks into the lens"

    @staticmethod
    def drift_correction(attribute: str, correct: str, wrong: str | None = None) -> str:
        """Textual drift correction (intervention 1 in proposal §10.4)."""
        if wrong:
            return f"Her {attribute} is {correct}, not {wrong}"
        return f"Her {attribute} is {correct}"

    def snapshot(self) -> dict:
        return {
            "canon": asdict(self._canon),
            "pose": self.pose,
            "props": {k: asdict(v) for k, v in self.props.items()},
            "history": [asdict(h) for h in self.history[-20:]],
            "generated_not_presented": list(self.generated_not_presented),
        }

===== FILE: live_agent/timeline.py =====
"""Single timeline, just-in-time locking and correction eligibility (proposal §10, §11).

Events per request k: lock P_k -> teacher (G_a) -> student (first chunk G_1) -> ready
-> presented V_k (4 chunks, ~R seconds). Hard constraints:

    ready_{k+1} = max(P_{k+1} + G_a, done_k) + G_1 + delta
    V_{k+1}     = max(ready_{k+1}, V_k + R)

Just-in-time lock (D-018):  P_{k+1} = V_k + R - Lambda - sigma, Lambda = G_a + G_1 + delta,
estimated online from measured request timings (a high quantile, for safety).
"Early" lock (contrast): P_{k+1} = V_k.
"""

from __future__ import annotations

import enum
import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO

from live_agent.generator.base import RequestTiming
from live_agent.types import EventType, TimelineEvent, now


class LockMode(str, enum.Enum):
    JIT = "jit"
    EARLY = "early"


@dataclass
class SchedulerConfig:
    request_s: float = 5.0
    sigma_s: float = 0.5  # safety margin (also used for the spoken-audio ASR check)
    delta_s: float = 0.15  # mux + transport estimate until measured
    lambda_prior_s: float = 3.0  # used until enough timings are observed
    lambda_quantile: float = 0.9
    min_observations: int = 3
    mode: LockMode = LockMode.JIT
    time_scale: float = 1.0  # simulation: wall seconds per content second (1/speed)


class LockScheduler:
    def __init__(self, cfg: SchedulerConfig | None = None):
        self.cfg = cfg or SchedulerConfig()
        self._timings: list[RequestTiming] = []
        self.presented_start: dict[int, float] = {}  # V_k
        self.locks: dict[int, float] = {}  # P_k
        self.durations: dict[int, float] = {}  # playback duration of request k (sum of its chunks)

    # ------------------------------------------------------------ observations
    def observe_timing(self, t: RequestTiming) -> None:
        self._timings = [x for x in self._timings if x.request_index != t.request_index] + [t]
        self._timings = self._timings[-50:]

    def on_lock(self, k: int, t: float) -> None:
        self.locks[k] = t

    def on_presented(self, k: int, t: float) -> None:
        self.presented_start.setdefault(k, t)

    def on_duration(self, k: int, seconds: float) -> None:
        """Playback length of request k (e.g. 124 frames for the first request, 119 later)."""
        self.durations[k] = seconds * self.cfg.time_scale

    # ------------------------------------------------------------ estimates
    def effective_leads(self) -> list[float]:
        """Lambda samples: first chunk ready minus max(lock, previous request done).

        Lock -> first chunk alone includes the wait for request k-1's final KV commit when the
        lock came early (M0: ~1.5 s idle vs 3.6-4.5 s pipelined); feeding that into
        P_{k+1} = V_k + R - Lambda - sigma would push locks earlier and earlier. The KV wait is
        a separate constraint (ready_{k+1} >= done_k + G_1) and is not part of Lambda."""
        by_k = {x.request_index: x for x in self._timings}
        out = []
        for k, x in sorted(by_k.items()):
            if x.t_first_chunk is None:
                continue
            prev = by_k.get(k - 1)
            # Unknown predecessor: lock time (conservative: may include some KV wait).
            start = max(x.t_lock, prev.t_done) if prev is not None and prev.t_done is not None else x.t_lock
            out.append(x.t_first_chunk - start)
        return out

    def lambda_estimate(self) -> float:
        leads = self.effective_leads()
        if len(leads) < self.cfg.min_observations:
            return self.cfg.lambda_prior_s
        leads.sort()
        idx = min(len(leads) - 1, int(round(self.cfg.lambda_quantile * (len(leads) - 1))))
        return leads[idx] + self.cfg.delta_s

    def mean_request_time(self) -> float | None:
        vals = [x.t_done - x.t_lock for x in self._timings if x.t_done is not None]
        return statistics.fmean(vals) if vals else None

    def keeps_up(self) -> bool | None:
        """Throughput condition: mean full-pipeline time per request < R (with 10% margin)."""
        m = self.mean_request_time()
        return None if m is None else m < 0.9 * self.cfg.request_s

    # ------------------------------------------------------------ locking
    def expected_presentation(self, k: int) -> float | None:
        """V_k if known, else extrapolated from the latest known presentation start."""
        if k in self.presented_start:
            return self.presented_start[k]
        known = [i for i in self.presented_start if i < k]
        if not known:
            return None
        j = max(known)
        return self.presented_start[j] + sum(self.durations.get(i, self.cfg.request_s) for i in range(j, k))

    def lock_time(self, k_next: int) -> float | None:
        """Wall-clock time at which request ``k_next`` should be locked.

        Returns None while the time is not yet determined (start-up: request k_next-1 has
        not started presenting, so V_{k_next-1} is unknown). The caller waits and asks again;
        locking early would commit content far ahead of playback and delay every instruction.
        """
        if k_next == 0:
            return now()
        v_prev = self.expected_presentation(k_next - 1)
        if v_prev is None:
            return None
        if self.cfg.mode == LockMode.EARLY:
            return v_prev
        return v_prev + self.cfg.request_s - self.lambda_estimate() - self.cfg.sigma_s

    # ------------------------------------------------------------ corrections
    def planned_lock(self, j: int) -> float | None:
        """P_j: actual lock time if already locked, else the planned one (None if unknown)."""
        if j in self.locks:
            return self.locks[j]
        v_prev = self.expected_presentation(j - 1)
        if v_prev is None:
            return None
        if self.cfg.mode == LockMode.EARLY:
            return v_prev
        return v_prev + self.cfg.request_s - self.lambda_estimate() - self.cfg.sigma_s

    def earliest_correctable(self, t_evidence: float, chain_cost_s: float, next_unlocked: int) -> int:
        """First request j >= next_unlocked with P_j >= E + C (no upper bound; proposal §10.3)."""
        t_ready = t_evidence + chain_cost_s
        j = next_unlocked
        for _ in range(10_000):
            pj = self.planned_lock(j)
            if pj is None or pj >= t_ready:
                return j
            j += 1
        return j


def tvc_model(A: float, wait: float, lam: float, sigma: float, inertia: float, R: float,
              mode: LockMode = LockMode.JIT, lookahead: int = 0) -> float:
    """Illustrative latency model (proposal §11): returns predicted TVC for one instruction."""
    if mode == LockMode.JIT:
        return A + wait + lam + sigma + inertia
    return A + wait + (lookahead + 1) * R + inertia


# ---------------------------------------------------------------------- event log


class EventLog:
    """Append-only JSONL log of timeline events (consumed by live_agent.eval)."""

    def __init__(self, path: str | Path | None = None):
        self.events: list[TimelineEvent] = []
        self.path = Path(path) if path else None
        self._fh: IO[str] | None = open(path, "a", encoding="utf-8") if path else None

    def redact(self, term: str, replacement: str = "[已删除]") -> int:
        """Erasure: replace ``term`` in every logged string (memory and file). Returns #events touched."""
        def scrub(x):
            if isinstance(x, str):
                return x.replace(term, replacement)
            if isinstance(x, list):
                return [scrub(v) for v in x]
            if isinstance(x, dict):
                return {k: scrub(v) for k, v in x.items()}
            return x

        n = 0
        for e in self.events:
            new = scrub(e.data)
            if new != e.data:
                e.data = new
                n += 1
        if self.path is not None and self._fh is not None:
            self._fh.close()
            lines = self.path.read_text(encoding="utf-8").splitlines()
            self.path.write_text("".join(json.dumps(scrub(json.loads(x)), ensure_ascii=False) + "\n"
                                         for x in lines if x.strip()), encoding="utf-8")
            self._fh = open(self.path, "a", encoding="utf-8")
        return n

    def emit(self, type_: EventType, t: float | None = None, **kw) -> TimelineEvent:
        ev = TimelineEvent(type=type_, t=now() if t is None else t,
                           request_index=kw.pop("request_index", None),
                           chunk_index=kw.pop("chunk_index", None), data=kw)
        self.events.append(ev)
        if self._fh:
            d = asdict(ev)
            d["type"] = ev.type.value
            self._fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            self._fh.flush()
        return ev

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

===== FILE: live_agent/director/director.py =====
"""Online director (proposal §8.2 layers 1-2, §9, §10).

Responsibilities
- Interpret each user utterance with the responder LLM: new intent chain, revision of
  an open chain, withdrawal, or chat. The plan is a queue of *segments* (one per 5-s request:
  an action intent and at most ~5 s of speech).
- Admission control (§4): at most one unexecuted instruction. A newer instruction supersedes
  an older unexecuted one, which is logged as a *capacity skip* (distinct from the user's own
  revision / withdrawal, which only touch the chain they target).
- Multistep chains are released step by step: step i+1 is queued only after step i was verified.
- Verdicts and retries are bound to (chain, revision, step): a late verdict about a superseded
  intent or another step is ignored.
- At each lock, build the BlockScript for the next request: canon from the ledger (verbatim),
  action via the capability manifest (emit / degrade / refuse), pending forward corrections,
  compile-time check questions. Repairs are reserved for their earliest correctable request.
- Narration policy: completion is voiced only after QC verified the action on presented
  frames; completion wording in LLM lines is removed in code (not only by the prompt).

Modes: ``closed_loop`` (A2) and ``open_loop`` (A1 comparator, proposal §7.2: the LLM writes the
next request's prompt directly — a free visible-action phrase and the line; no manifest, no
ledger context, no QC, no corrections, no narration guard, no step gating). Both modes share
the generator, canon compiler, LLM, memory and presentation path.
"""

from __future__ import annotations

import enum
import re
from collections import deque
from dataclasses import dataclass, field

from live_agent.capability import CapabilityManifest, Decision
from live_agent.ledger import StateLedger
from live_agent.llm import ChatLLM, parse_json
from live_agent.types import (BlockScript, ChainStatus, CheckQuestion, IntentChain, TaskKind,
                              Utterance, new_id)

CHARS_PER_REQUEST = 22  # ~4.5 Chinese characters/s x 5 s [estimate; calibrate in E1]


class DirectorMode(str, enum.Enum):
    CLOSED_LOOP = "closed_loop"  # A2
    OPEN_LOOP = "open_loop"  # A1


@dataclass
class Segment:
    chain_id: str | None
    plan_version: int
    intent: str = ""  # capability intent (closed loop)
    line: str = ""
    step: int | None = None
    is_completion_remark: bool = False
    correction: str = ""  # forward correction attached to a retried action
    retry_of: int | None = None  # request index whose check failed
    revision: int | None = None  # chain revision count this segment was planned under
    action_text: str = ""  # open loop: the LLM's own visible-action phrase
    min_request: int = 0  # reserved slot: do not lock before this request index


@dataclass
class DirectorEvents:
    """Things the orchestrator must log (consumed by the eval schema)."""

    refusals: list[tuple[str, str]] = field(default_factory=list)  # (chain_id, reason)
    degradations: list[tuple[str, str]] = field(default_factory=list)
    completion_claims: list[tuple[str, int, int | None]] = field(default_factory=list)  # (chain, request, step)
    capacity_skips: list[tuple[str, int]] = field(default_factory=list)  # (chain_id, revision)
    narration_guards: list[tuple[str, str]] = field(default_factory=list)  # (original, cleaned)


RESPONDER_SYSTEM = """你是直播数字人「{name}」的应答大脑。人设：{bio}
人设能做的动作只有这些 intent：{intents}。
输出一个 JSON 对象（不要输出任何其他文字），字段：
- "relation": "new"（用户提出新的要求）| "revision"（用户改口、纠正尚未完成的要求）| "withdrawal"（用户取消尚未完成的要求）| "chat"（闲聊、提问、陈述）
- "target_chain": relation 为 revision/withdrawal 时，被修改的链 id（从下面的未完成链中选）；否则 null
- "kind": "action"（要求做一个动作）| "multistep"（按顺序做多个动作）| "content"（讲解、唱歌、回答知识问题）| "memory"（要求记住或忘记某事）| "chat"
- "steps": [{{"intent": ..., "line": ...}}]，按顺序执行
- "memory_note": 用户陈述了关于**他自己**的事实时，用第三人称写成一句（如「用户的妹妹住在杭州」）；否则 null
- "forget_term": 用户要求忘记某事时，写出关键词；否则 null
规则：
1. 只有当用户**明确要求人设做动作**时（kind 为 action 或 multistep），steps 里才写动作 intent；其他情况 intent 一律写 ""。
2. 用户要求的动作不在上面的列表里时，intent 写 ""，并在 line 里礼貌说明做不到。
3. 每个 line 不超过 {chars} 个汉字；长回答拆成多个 step。
4. 只说意图（「好，我喝口茶」），不说已经完成（不说「我喝完了」）。
5. 称呼用户用「你」。绝不把用户说的关于他自己的事说成是人设自己的事。
示例：
用户：喝口茶吧 → {{"relation":"new","target_chain":null,"kind":"action","steps":[{{"intent":"drink_tea","line":"好，我喝口茶。"}}],"memory_note":null,"forget_term":null}}
用户：你能飞起来吗 → {{"relation":"chat","target_chain":null,"kind":"chat","steps":[{{"intent":"","line":"我可飞不起来，不过可以给你讲讲飞行的原理。"}}],"memory_note":null,"forget_term":null}}
用户：我妹妹住在杭州 → {{"relation":"chat","target_chain":null,"kind":"chat","steps":[{{"intent":"","line":"原来你妹妹住在杭州，那里很美。"}}],"memory_note":"用户的妹妹住在杭州","forget_term":null}}
用户：忘掉我妹妹的事 → {{"relation":"chat","target_chain":null,"kind":"memory","steps":[{{"intent":"","line":"好的，关于你妹妹的事我已经忘掉了。"}}],"memory_note":null,"forget_term":"妹妹"}}
用户（有未完成链 chain-1：翻书）：不对，先挥挥手 → {{"relation":"revision","target_chain":"chain-1","kind":"action","steps":[{{"intent":"wave","line":"好，先挥挥手。"}}],"memory_note":null,"forget_term":null}}
当前未完成的指令链：{open_chains}
人设当前状态：{state}
相关记忆（带来源标签，只作参考）：{memories}"""

# A1 comparator: the LLM writes the request prompt content directly (free action phrase + line).
OPEN_LOOP_SYSTEM = """你是直播数字人「{name}」的导演，直接为下一段 5 秒的视频写提示。人设：{bio}
画面里的人设是一位女性，视频模型读英文动作描述、中文台词。
输出一个 JSON 对象（不要输出任何其他文字），字段：
- "relation": "new" | "revision" | "withdrawal" | "chat"（含义：新要求 / 改口 / 取消 / 闲聊）
- "target_chain": relation 为 revision/withdrawal 时，被修改的链 id；否则 null
- "kind": "action" | "multistep" | "content" | "memory" | "chat"
- "steps": [{{"action": 英文短语，描述她在画面里可见地做什么（如 "she lifts the teacup and takes a sip"），没有动作就写 "", "line": 她说的中文台词}}]，每个 step 是一段 5 秒视频
- "memory_note": 用户陈述了关于他自己的事实时写成一句；否则 null
- "forget_term": 用户要求忘记某事时写关键词；否则 null
每个 line 不超过 {chars} 个汉字。
当前未完成的指令链：{open_chains}
相关记忆（只作参考）：{memories}"""


class Director:
    def __init__(self, llm: ChatLLM, manifest: CapabilityManifest, ledger: StateLedger, *,
                 persona_name: str, persona_bio: str, mode: DirectorMode = DirectorMode.CLOSED_LOOP,
                 idle_intent: str = "idle_read", listen_intent: str = "listen"):
        self.llm = llm
        self.manifest = manifest
        self.ledger = ledger
        self.mode = mode
        self.persona_name = persona_name
        self.persona_bio = persona_bio
        self.idle_intent = idle_intent
        self.listen_intent = listen_intent
        self.plan_version = 0
        self.queue: deque[Segment] = deque()
        self.held: dict[str, dict[int, list[Segment]]] = {}  # multistep: steps not yet released
        self.chains: dict[str, IntentChain] = {}
        self.latest_chain: str | None = None  # the newest instruction (admission control)
        self.pending_corrections: dict[int, list[str]] = {}  # request index -> correction sentences
        self.events = DirectorEvents()
        self.listening = False
        self.memory_notes: list[tuple[str, str]] = []  # (utterance id, note)
        self.erased_terms: set[str] = set()

    @property
    def closed(self) -> bool:
        return self.mode == DirectorMode.CLOSED_LOOP

    # ------------------------------------------------------------ utterances
    def _open_chains(self) -> list[IntentChain]:
        return [c for c in self.chains.values() if c.status == ChainStatus.OPEN]

    async def on_user_utterance(self, utt: Utterance, memories: list[str] | None = None) -> dict:
        """Interpret an utterance and update the plan. Returns the parsed decision."""
        open_chains = [{"chain_id": c.chain_id, "intent": c.final_intent} for c in self._open_chains()]
        if self.closed:
            intents = ", ".join(sorted({c.intent for c in self.manifest.caps.values()
                                        if c.usable(self.manifest.min_status, self.manifest.min_p)})) or "（暂无）"
            sys = RESPONDER_SYSTEM.format(
                name=self.persona_name, bio=self.persona_bio, intents=intents, chars=CHARS_PER_REQUEST,
                open_chains=open_chains or "无", state=self.ledger.continuity_sentence(),
                memories=memories or "无")
        else:
            sys = OPEN_LOOP_SYSTEM.format(name=self.persona_name, bio=self.persona_bio, chars=CHARS_PER_REQUEST,
                                          open_chains=open_chains or "无", memories=memories or "无")
        raw = await self.llm.chat([{"role": "system", "content": sys},
                                   {"role": "user", "content": utt.text}], json_mode=True)
        try:
            d = parse_json(raw)
        except ValueError:
            d = {"relation": "chat", "kind": "chat", "steps": [{"intent": "", "line": "抱歉，我没听清，可以再说一次吗？"}]}
        self._apply_decision(utt, d)
        return d

    def _validate(self, kind: TaskKind, steps: list[dict]) -> str | None:
        """Closed loop: enforce the contract in code. Returns a refusal reason or None."""
        allowed = {c.intent for c in self.manifest.caps.values()}
        is_action = kind in (TaskKind.ACTION, TaskKind.MULTISTEP)
        unsupported = []
        for st in steps:
            it = st.get("intent") or ""
            if not is_action:
                st["intent"] = ""
            elif it and it not in allowed:
                unsupported.append(it)
                st["intent"] = ""
        if is_action and unsupported:
            return f"unsupported intent(s): {', '.join(unsupported)}"
        if is_action and not any(st.get("intent") for st in steps):
            return "action requested but no supported capability"  # LLM declined with a line only
        return None

    def _guard(self, line: str) -> str:
        """Closed loop: remove clauses that claim completion from an (unverified) LLM line."""
        if not self.closed or not _claims_completion(line):
            return line
        kept = [c for c in re.split(r"(?<=[。！？!?；;，,])", line) if c and not _claims_completion(c)]
        clean = "".join(kept)
        self.events.narration_guards.append((line, clean))
        return clean

    def _apply_decision(self, utt: Utterance, d: dict) -> None:
        relation = d.get("relation", "new")
        kind = TaskKind(d.get("kind", "chat")) if d.get("kind") in TaskKind._value2member_map_ else TaskKind.CHAT
        steps = [dict(s) for s in d.get("steps", []) if isinstance(s, dict)]
        refusal = self._validate(kind, steps) if self.closed else None
        for st in steps:
            st["line"] = self._guard(st.get("line") or "")
        target = self.chains.get(d.get("target_chain") or "")
        if d.get("memory_note"):
            self.memory_notes.append((utt.uid, d["memory_note"]))
        self.plan_version += 1
        self.listening = False

        if relation == "withdrawal" and target and target.status == ChainStatus.OPEN:
            target.status = ChainStatus.WITHDRAWN
            self._drop_chain_segments(target.chain_id)
            self._enqueue_chat(steps)
            return
        if relation == "revision" and target and target.status == ChainStatus.OPEN:
            self._drop_chain_segments(target.chain_id)
            target.revisions.append(utt.uid)
            target.final_intent = utt.text
            target.clock_origin = utt.t_end
            target.kind = kind if kind != TaskKind.CHAT else target.kind
            target.steps = [s.get("intent", "") for s in steps]
            target.step_index = 0
            chain = target
        elif kind in (TaskKind.CHAT, TaskKind.MEMORY) and relation in ("chat", "new", "withdrawal", "revision"):
            self._enqueue_chat(steps)
            return
        else:
            chain = IntentChain(chain_id=new_id("chain"), kind=kind, opened_by=utt.uid,
                                final_intent=utt.text, clock_origin=utt.t_end,
                                steps=[s.get("intent", "") for s in steps])
            self.chains[chain.chain_id] = chain
        self._admit(chain.chain_id)
        if refusal:
            chain.status = ChainStatus.REFUSED
            self.events.refusals.append((chain.chain_id, refusal))
            self._enqueue_chat(steps)  # the spoken explanation, not bound to the refused chain
            return
        self._enqueue_chain(chain, steps)

    # ------------------------------------------------------------ queue management
    def _admit(self, chain_id: str) -> None:
        """At most one unexecuted instruction: older unexecuted chains are capacity-skipped."""
        for c in self._open_chains():
            if c.chain_id != chain_id and self._unexecuted(c.chain_id):
                self._drop_chain_segments(c.chain_id)
                c.status = ChainStatus.CAPACITY_SKIPPED
                self.events.capacity_skips.append((c.chain_id, len(c.revisions)))
        self.latest_chain = chain_id

    def _unexecuted(self, chain_id: str) -> bool:
        return any(s.chain_id == chain_id and not s.is_completion_remark for s in self.queue) or \
            bool(self.held.get(chain_id))

    def _drop_chain_segments(self, chain_id: str) -> None:
        self.queue = deque(s for s in self.queue if s.chain_id != chain_id)
        self.held.pop(chain_id, None)

    def _enqueue_chat(self, steps: list[dict]) -> None:
        """Chat / explanation lines go first; they do not displace instructions."""
        segs = [Segment(chain_id=None, plan_version=self.plan_version, line=line)
                for s in steps for line in _split_line(s.get("line", ""))]
        for seg in reversed(segs):
            self.queue.appendleft(seg)

    def _segments_for_step(self, chain: IntentChain, i: int, s: dict, n_steps: int) -> list[Segment]:
        out = []
        for j, line in enumerate(_split_line(s.get("line", "")) or [""]):
            out.append(Segment(chain_id=chain.chain_id, plan_version=self.plan_version,
                               intent=(s.get("intent") or "") if j == 0 else "",
                               action_text=(s.get("action") or "") if j == 0 else "",
                               line=line, step=i if n_steps > 1 else None, revision=len(chain.revisions)))
        return [x for x in out if x.intent or x.action_text or x.line]

    def _enqueue_chain(self, chain: IntentChain, steps: list[dict]) -> None:
        per_step = [self._segments_for_step(chain, i, s, len(steps)) for i, s in enumerate(steps)]
        if self.closed and chain.kind == TaskKind.MULTISTEP and len(steps) > 1:
            first = self._release_upto(chain, -1)
            self.held[chain.chain_id] = {i: segs for i, segs in enumerate(per_step) if i > first}
            released = [seg for i in range(first + 1) for seg in per_step[i]]
        else:
            released = [seg for segs in per_step for seg in segs]
        self.queue.extend(released)

    def _release_upto(self, chain: IntentChain, after: int) -> int:
        """Index of the last step released together after step ``after``: all following
        content steps up to and including the next action step."""
        i = after + 1
        while i < len(chain.steps) - 1 and not chain.steps[i]:
            i += 1
        return min(i, len(chain.steps) - 1)

    def _action_steps(self, chain: IntentChain) -> list[int]:
        idx = [i for i, s in enumerate(chain.steps) if s]
        return idx or [0]

    def _expected_step(self, chain: IntentChain) -> int | None:
        acts = self._action_steps(chain)
        return acts[chain.step_index] if chain.step_index < len(acts) else None

    def _matches(self, chain: IntentChain, revision: int | None, step: int | None) -> bool:
        if revision is not None and revision != len(chain.revisions):
            return False  # verdict about a superseded intent
        exp = self._expected_step(chain)
        return exp is not None and (step if step is not None else self._action_steps(chain)[0]) == exp

    def on_barge_in(self) -> None:
        """User started speaking: stop planning ahead; next requests show the persona listening.
        Unsent segments of open chains are kept (the utterance decides what happens to them)."""
        self.plan_version += 1
        self.queue = deque(s for s in self.queue if s.chain_id is not None and not s.is_completion_remark)
        self.listening = True

    # ------------------------------------------------------------ verdict feedback
    def on_verified(self, chain_id: str, intent: str, request_index: int, t: float, *,
                    revision: int | None = None, step: int | None = None) -> bool:
        chain = self.chains.get(chain_id)
        if not chain or chain.status != ChainStatus.OPEN or not self._matches(chain, revision, step):
            return False
        self.ledger.apply_verified_action(intent)
        done_step = self._expected_step(chain)
        chain.step_index += 1
        if chain.first_compliant_t is None:
            chain.first_compliant_t = t
        held = self.held.get(chain_id, {})
        released: list[Segment] = []
        if held and done_step is not None:
            last = self._release_upto(chain, done_step)
            for i in range(done_step + 1, last + 1):
                released += held.pop(i, [])
        if chain.step_index >= len(self._action_steps(chain)):
            chain.status = ChainStatus.COMPLIED
            released += held.pop(len(chain.steps) - 1, []) if held else []
            self.held.pop(chain_id, None)
            if self.closed:
                # Narration policy: completion is voiced only after verification (after the
                # chain's remaining spoken content, if any).
                released.append(Segment(chain_id=chain_id, plan_version=self.plan_version,
                                        line="好了。", is_completion_remark=True,
                                        revision=len(chain.revisions)))
        for seg in reversed(released):
            self.queue.appendleft(seg)
        return True

    def schedule_correction(self, request_index: int, sentence: str) -> None:
        self.pending_corrections.setdefault(request_index, []).append(sentence)

    def queue_retry(self, chain_id: str, intent: str, *, correction: str, failed_request: int,
                    revision: int | None = None, step: int | None = None, min_request: int = 0) -> bool:
        """Forward repair: retry the action no earlier than ``min_request`` (the earliest
        correctable request). Dropped if the chain is no longer open, the verdict was about a
        superseded intent or another step, or a newer instruction exists (admission control:
        the chain is then capacity-skipped)."""
        chain = self.chains.get(chain_id)
        if chain is None or chain.status != ChainStatus.OPEN or not self._matches(chain, revision, step):
            return False
        if self.latest_chain != chain_id:
            chain.status = ChainStatus.CAPACITY_SKIPPED
            self.events.capacity_skips.append((chain_id, len(chain.revisions)))
            return False
        self.queue.appendleft(Segment(chain_id=chain_id, plan_version=self.plan_version, intent=intent,
                                      line="", correction=correction, retry_of=failed_request, step=step,
                                      revision=len(chain.revisions), min_request=min_request))
        return True

    # ------------------------------------------------------------ erasure
    def purge(self, term: str) -> int:
        """Erasure (§12): remove the term from all controller state that can reach a prompt."""
        self.erased_terms.add(term)
        n = 0
        before = len(self.queue)
        self.queue = deque(s for s in self.queue if term not in s.line and term not in s.action_text)
        n += before - len(self.queue)
        for cid, steps in list(self.held.items()):
            for i, segs in list(steps.items()):
                steps[i] = [s for s in segs if term not in s.line and term not in s.action_text]
        for c in self.chains.values():
            if term in c.final_intent:
                c.final_intent = c.final_intent.replace(term, "[已删除]")
                n += 1
        self.memory_notes = [(u, x) for u, x in self.memory_notes if term not in x]
        self.pending_corrections = {k: [x for x in v if term not in x] for k, v in self.pending_corrections.items()}
        n += self.ledger.redact(term)
        return n

    # ------------------------------------------------------------ script building
    def _pop_segment(self, request_index: int) -> Segment | None:
        for i, seg in enumerate(self.queue):
            if seg.min_request <= request_index:
                del self.queue[i]
                return seg
        return None

    def next_script(self, request_index: int) -> BlockScript:
        seg = self._pop_segment(request_index)
        if seg is None:
            intent = self.listen_intent if self.listening else self.idle_intent
            seg = Segment(chain_id=None, plan_version=self.plan_version, intent=intent, line="")
        chain = self.chains.get(seg.chain_id or "")
        if chain is not None and chain.status not in (ChainStatus.OPEN, ChainStatus.COMPLIED):
            seg = Segment(chain_id=None, plan_version=self.plan_version, intent=self.idle_intent,
                          line=seg.line)  # chain closed meanwhile: keep the words, drop the binding

        action_phrase, cap_ids, checks = "", [], []
        line = seg.line
        if not self.closed:
            if seg.action_text:
                action_phrase = seg.action_text
            elif seg.intent:  # idle / listen filler: same phrase as A2
                cap = self.manifest.by_intent(seg.intent)
                action_phrase = cap.phrase if cap else ""
        elif seg.intent:
            res = self.manifest.decide(seg.intent)
            if res.decision == Decision.EMIT and res.capability:
                action_phrase = res.capability.phrase
                cap_ids.append(res.capability.cap_id)
                if seg.chain_id and res.capability.check_question:
                    checks.append(CheckQuestion(qid=new_id("q"), text=res.capability.check_question,
                                                kind="action"))
            elif seg.chain_id is None:
                action_phrase = ""  # filler intent not usable: no action
            elif res.decision == Decision.DEGRADE and res.capability:
                self.events.degradations.append((seg.chain_id, res.reason))
                line = line or res.capability.degrade_to
                self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
            else:
                self.events.refusals.append((seg.chain_id, res.reason))
                line = line or "这个我现在做不到，不过我们可以聊聊别的。"
                self._fail_chain(seg.chain_id, ChainStatus.REFUSED)
        if line and self.closed:
            checks.append(CheckQuestion(qid=new_id("q"), text="台词是否被完整、准确地说出？", kind="speech"))
        if seg.is_completion_remark and seg.chain_id:
            self.events.completion_claims.append((seg.chain_id, request_index, seg.step))
        elif not self.closed and seg.chain_id and _claims_completion(line):
            self.events.completion_claims.append((seg.chain_id, request_index, seg.step))

        corrections = list(self.pending_corrections.pop(request_index, []))
        if seg.correction:
            corrections.append(seg.correction)
        if self.closed:
            bridge = self.ledger.bridging_note()
            if bridge:
                corrections.append(bridge)
                self.ledger.generated_not_presented.clear()  # bridge once, then continue normally
        script = BlockScript(request_index=request_index, plan_version=seg.plan_version,
                             canon=self.ledger.canon, action=action_phrase, transcript=line,
                             corrections=corrections, checks=checks,
                             chain_ids=[seg.chain_id] if seg.chain_id else [],
                             capability_ids=cap_ids,
                             provenance={"intent": seg.intent, "step": seg.step, "retry_of": seg.retry_of,
                                         "revision": seg.revision,
                                         "completion_remark": seg.is_completion_remark})
        if seg.chain_id and seg.chain_id in self.chains:
            self.chains[seg.chain_id].requests.append(request_index)
        self.ledger.record_request(request_index, action_phrase, line)
        return script

    def _fail_chain(self, chain_id: str | None, status: ChainStatus) -> None:
        if chain_id and chain_id in self.chains and self.chains[chain_id].status == ChainStatus.OPEN:
            self.chains[chain_id].status = status
            self._drop_chain_segments(chain_id)


def _split_line(line: str, n: int = CHARS_PER_REQUEST) -> list[str]:
    """Split a spoken line into <= n-character pieces at punctuation where possible."""
    line = (line or "").strip()
    if not line:
        return []
    out, cur = [], ""
    for piece in re.split(r"(?<=[。！？!?；;，,])", line):
        if len(cur) + len(piece) <= n:
            cur += piece
        else:
            if cur:
                out.append(cur)
            while len(piece) > n:
                out.append(piece[:n])
                piece = piece[n:]
            cur = piece
    if cur:
        out.append(cur)
    return [x for x in out if re.search(r"[\w一-鿿]", x)]


_COMPLETION = re.compile(r"(做完|喝完|吃完|写完|翻好|做好了|完成了|搞定|好了[。！!]?$|已经(做|喝|吃|写|翻|挥|放|拿|站|坐)|done|finished)")


def _claims_completion(line: str) -> bool:
    return bool(_COMPLETION.search(line or ""))

===== FILE: live_agent/qc/judge.py =====
"""Online QC (proposal §8.2 layer 5): deadline-bounded checks on *presented* content.

- ``VLMJudge``: asks a VLM a yes/no question about K frames sampled from the presented
  chunks of a request; may abstain (UNKNOWN).
- ``SpeechCheck``: ASR of the generated audio vs the scripted line (character error rate).
- ``ForwardCorrector``: VQQA-style "semantic gradient": turns failed Q/A into a correction
  sentence for the earliest correctable request (never regenerates presented content).
- ``MockJudge``: for tests/simulation; decides compliance from the prompt with a
  per-capability success probability.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from live_agent.llm import ChatLLM, frame_to_data_url, parse_json
from live_agent.types import CheckQuestion, Chunk, Verdict, VerdictLabel, now

JUDGE_PROMPT = """你是严格的视频质检员。下面是直播画面中按时间顺序抽取的 {k} 帧。
问题：{question}
只根据画面回答，只输出 JSON：{{"answer": "yes" | "no" | "unsure", "confidence": 0到1之间的小数, "reason": "一句话"}}"""


def sample_frames(chunks: Sequence[Chunk], k: int = 4) -> list[np.ndarray]:
    frames = [f for c in chunks if c.video is not None for f in c.video]
    if not frames:
        return []
    idx = np.linspace(0, len(frames) - 1, num=min(k, len(frames))).round().astype(int)
    return [frames[i] for i in idx]


@dataclass
class VLMJudge:
    vlm: ChatLLM
    k: int = 4
    min_confidence: float = 0.6

    async def judge(self, q: CheckQuestion, chunks: Sequence[Chunk], request_index: int,
                    t_evidence: float) -> Verdict:
        frames = sample_frames(chunks, self.k)
        if not frames:
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, "no frames", t_evidence, now())
        content = [{"type": "text", "text": JUDGE_PROMPT.format(k=len(frames), question=q.text)}]
        content += [{"type": "image_url", "image_url": {"url": frame_to_data_url(f)}} for f in frames]
        try:
            d = parse_json(await self.vlm.chat([{"role": "user", "content": content}], max_tokens=128,
                                               temperature=0.0, json_mode=True))
            ans, conf = str(d.get("answer", "unsure")).lower(), float(d.get("confidence", 0.0))
            reason = str(d.get("reason", ""))
        except Exception as e:  # abstain on any judge failure
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, f"judge error: {e}", t_evidence, now())
        if conf < self.min_confidence or ans not in ("yes", "no"):
            label = VerdictLabel.UNKNOWN
        else:
            label = VerdictLabel.COMPLIED if ans == "yes" else VerdictLabel.NOT_COMPLIED
        return Verdict(q.qid, request_index, label, conf, reason, t_evidence, now())


def char_error_rate(ref: str, hyp: str) -> float:
    """Levenshtein distance / len(ref) on characters, ignoring punctuation and spaces."""
    norm = lambda s: re.sub(r"[\s\W_]+", "", s.lower())  # noqa: E731
    r, h = norm(ref), norm(hyp)
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return prev[-1] / len(r)


@dataclass
class SpeechCheck:
    """Compare ASR of generated speech with the scripted line (used within sigma before playback)."""

    asr: Callable[[np.ndarray, int], str]  # (audio [S,C] float32, sample_rate) -> text
    max_cer: float = 0.10

    def check(self, q: CheckQuestion, script_line: str, chunks: Sequence[Chunk], request_index: int,
              t_evidence: float) -> Verdict:
        audio = [c.audio for c in chunks if c.audio is not None and len(c.audio)]
        if not audio:
            return Verdict(q.qid, request_index, VerdictLabel.UNKNOWN, 0.0, "no audio", t_evidence, now())
        sr = chunks[0].sample_rate
        text = self.asr(np.concatenate(audio, axis=0), sr)
        cer = char_error_rate(script_line, text)
        label = VerdictLabel.COMPLIED if cer <= self.max_cer else VerdictLabel.NOT_COMPLIED
        return Verdict(q.qid, request_index, label, 1.0 - min(cer, 1.0), f"asr={text!r} cer={cer:.2f}",
                       t_evidence, now())


CORRECTION_PROMPT = """视频生成模型没有执行下面的动作。请把动作描述改写成更明确、更容易被画出来的英文短句（一句，不超过 30 个词），
只描述人物 S1 的可见动作，不要改变人物外貌、场景或镜头。
原动作：{action}
失败的检查问答：{qa}
只输出 JSON：{{"correction": "..."}}"""


@dataclass
class ForwardCorrector:
    llm: ChatLLM | None = None

    async def correction(self, action_phrase: str, failed: Sequence[Verdict], questions: dict[str, str]) -> str:
        qa = "; ".join(f"Q: {questions.get(v.qid, v.qid)} A: {v.label.value} ({v.rationale})" for v in failed)
        if self.llm is not None:
            try:
                d = parse_json(await self.llm.chat(
                    [{"role": "user", "content": CORRECTION_PROMPT.format(action=action_phrase, qa=qa)}],
                    max_tokens=96, temperature=0.2, json_mode=True))
                text = str(d.get("correction", "")).strip()
                if text:
                    return text
            except Exception:
                pass
        # Template fallback: emphasise visibility and timing.
        return f"This time S1 clearly and visibly does it: {action_phrase}, facing the lens, within the first two seconds"


class MockJudge:
    """Simulated judge: an action 'renders' with probability p (per phrase), boosted by corrections."""

    def __init__(self, p_default: float = 0.7, p_by_phrase: dict[str, float] | None = None,
                 correction_boost: float = 0.2, seed: int = 0):
        self.p_default = p_default
        self.p_by_phrase = p_by_phrase or {}
        self.boost = correction_boost
        self._rng = random.Random(seed)

    async def judge(self, q: CheckQuestion, chunks: Sequence[Chunk], request_index: int,
                    t_evidence: float) -> Verdict:
        prompt = chunks[0].meta.get("prompt", "") if chunks else ""
        p = self.p_default
        for phrase, pp in self.p_by_phrase.items():
            if phrase in prompt:
                p = pp
        if "clearly and visibly" in prompt:
            p = min(1.0, p + self.boost)
        ok = self._rng.random() < p
        return Verdict(q.qid, request_index, VerdictLabel.COMPLIED if ok else VerdictLabel.NOT_COMPLIED,
                       0.9, "mock", t_evidence, now())

===== FILE: live_agent/orchestrator.py =====
"""Orchestrator: runs the live agent on the single timeline (proposal §10, §11).

Concurrent loops
- lock loop     : at each just-in-time lock time, ask the director for the next BlockScript,
                  audit it (§15), compile it to an H3 prompt and submit it (event LOCK).
- chunk loop    : forward generated chunks to the client transport (event CHUNK_READY).
- presentation  : client acks (start/end of each chunk) drive V_k and the evidence time E;
                  when all chunks of a request have been presented, run its QC checks once.
- input         : user utterances (after ASR) go to memory + director; speech onset = barge-in.

Everything that the evaluation needs is written to the EventLog as JSONL. A worker failure
stops the session (event ERROR) instead of hanging it.
"""

from __future__ import annotations

import asyncio
import enum
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from live_agent.director.director import CHARS_PER_REQUEST, Director, DirectorMode
from live_agent.generator.base import Generator
from live_agent.prompt.h3_compiler import compile_prompt
from live_agent.qc.judge import ForwardCorrector
from live_agent.timeline import EventLog, LockScheduler
from live_agent.types import (BlockScript, ChainStatus, Chunk, EventType, Utterance, Verdict,
                              VerdictLabel, now)


class Transport(Protocol):
    """Client side: plays chunks and reports presentation times via Orchestrator.on_presented."""

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None: ...

    async def stop_playback(self) -> None: ...


class MemoryPort(Protocol):
    """Minimal memory interface used by the orchestrator (adapter over live_agent.memory)."""

    def recall(self, text: str, *, mode: str) -> list[str]: ...

    def on_user_utterance(self, utt: Utterance) -> None: ...

    def on_persona_line(self, text: str, *, session_id: str, scope: str) -> None: ...


class Judge(Protocol):
    async def judge(self, q, chunks, request_index: int, t_evidence: float) -> Verdict: ...


class CorrectionMode(str, enum.Enum):
    GRADIENT = "gradient"  # forward semantic gradient (A2)
    REPEAT = "repeat"  # contrast: repeat the instruction unchanged
    RANDOMIZED = "randomized"  # RQ2: arm drawn per eligible failure point (seeded, logged)
    NONE = "none"  # ablation / open loop


@dataclass
class OrchestratorConfig:
    session_id: str = "session-0"
    scope: str = "private"  # "private" (1:1) | "public" (test livestream)
    correction_mode: CorrectionMode = CorrectionMode.GRADIENT
    qc_enabled: bool = True
    max_requests: int | None = None  # stop after N requests (tests / batch runs)
    text_encode_s: float = 0.06  # part of the correction chain C [measured locally, M0 teacher text encode]
    seed: int = 0


_FORGET = re.compile(r"(忘掉|忘了|忘记|删掉|删除|别记|不要记)")


def audio_onset_s(chunk: Chunk, threshold: float = 0.02, window_s: float = 0.02) -> float | None:
    """Offset (s) of the first 20 ms window whose RMS exceeds ``threshold``; None if silent/absent."""
    a = chunk.audio
    if a is None or len(a) == 0:
        return None
    a = np.asarray(a, dtype=np.float32)
    a = a.mean(axis=1) if a.ndim == 2 else a
    w = max(1, int(window_s * chunk.sample_rate))
    n = len(a) // w
    if n == 0:
        return None
    rms = np.sqrt((a[: n * w].reshape(n, w) ** 2).mean(axis=1))
    idx = np.nonzero(rms > threshold)[0]
    return float(idx[0] * w / chunk.sample_rate) if len(idx) else None


class Orchestrator:
    def __init__(self, generator: Generator, director: Director, scheduler: LockScheduler,
                 transport: Transport, *, judge: Judge | None = None,
                 corrector: ForwardCorrector | None = None, speech_check=None,
                 memory: MemoryPort | None = None, log: EventLog | None = None,
                 cfg: OrchestratorConfig | None = None):
        self.gen = generator
        self.director = director
        self.sched = scheduler
        self.transport = transport
        self.judge = judge
        self.corrector = corrector or ForwardCorrector()
        self.speech_check = speech_check
        self.memory = memory
        self.log = log or EventLog()
        self.cfg = cfg or OrchestratorConfig()
        self.scripts: dict[int, BlockScript] = {}
        self.prompts: dict[int, str] = {}
        self.chunks: dict[int, list[Chunk]] = defaultdict(list)
        self.presented: dict[int, set[int]] = defaultdict(set)
        self.chunk_start: dict[tuple[int, int], float] = {}
        self.next_lock = 0
        self._tasks: list[asyncio.Task] = []
        self._aux: set[asyncio.Task] = set()
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()  # cleared while an erasure quiesces locking
        self._ready.set()
        self._rng = random.Random(self.cfg.seed)
        self._chain_costs: list[float] = []
        self._checked: set[int] = set()
        self._onset_done: set[int] = set()
        self._claims: dict[int, list[tuple[str, int | None]]] = {}  # request -> [(chain, step)]
        self.dropped: set[int] = set()  # requests discarded by a barge-in / erasure (never fully shown)
        self.error: BaseException | None = None
        self.last_presented_end: float | None = None

    @property
    def n_chunks(self) -> int:
        return self.gen.info.chunks_per_request

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        await self.gen.start()
        self._tasks = [asyncio.create_task(self._guarded(self._lock_loop(), "lock_loop")),
                       asyncio.create_task(self._guarded(self._chunk_loop(), "chunk_loop"))]

    async def _guarded(self, coro, name: str) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a failed loop must end the session visibly
            self.error = e
            self.log.emit(EventType.ERROR, now(), where=name, error=f"{type(e).__name__}: {e}")
            self._stop.set()

    def _spawn(self, coro, name: str) -> None:
        t = asyncio.create_task(self._guarded(coro, name))
        self._aux.add(t)
        t.add_done_callback(self._aux.discard)

    async def stop(self) -> None:
        self._stop.set()
        tasks = [*self._tasks, *self._aux]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.log.emit(EventType.OBSERVATION_END, self.last_presented_end or now())
        try:
            await self.gen.close()
        finally:
            self.log.close()

    async def wait_done(self) -> None:
        await self._stop.wait()

    # ------------------------------------------------------------------ lock loop
    async def _lock_loop(self) -> None:
        while not self._stop.is_set():
            k = self.next_lock
            if self.cfg.max_requests is not None and k >= self.cfg.max_requests:
                return
            # Re-evaluate while waiting: V_{k-1} becomes known (or better extrapolated) meanwhile.
            tl = None
            while not self._stop.is_set():
                tl = self.sched.lock_time(k)
                if tl is not None and tl <= now():
                    break
                await asyncio.sleep(0.01 if tl is None else min(0.05, tl - now()))
            # Never run more than two requests ahead of presentation (bounded backlog).
            while k >= 2 and not self._resolved(k - 2) and not self._stop.is_set():
                await asyncio.sleep(0.01)
            await self._ready.wait()  # erasure in progress
            if self._stop.is_set():
                return
            script = self.director.next_script(k)
            self._audit(script)
            prompt = compile_prompt(script, first_request=(k == 0))
            self.scripts[k], self.prompts[k] = script, prompt
            t = now()
            await self.gen.submit(k, prompt)
            self.sched.on_lock(k, t)
            self.next_lock = k + 1
            self.log.emit(EventType.LOCK, t, request_index=k, plan_version=script.plan_version,
                          lambda_est=self.sched.lambda_estimate(), planned_lock=tl,
                          action=script.action, transcript=script.transcript,
                          chain_ids=script.chain_ids, corrections=script.corrections,
                          capability_ids=script.capability_ids, prompt=prompt,
                          step=script.provenance.get("step"), revision=script.provenance.get("revision"),
                          checks=[{"qid": q.qid, "text": q.text, "kind": q.kind} for q in script.checks])
            if script.transcript and self.memory:
                # lineage: None = linked to every memory recalled this session (over-links, so
                # erasure/correction reach it); a None return is a refused (scope-violating) write
                rec = self.memory.on_persona_line(script.transcript, session_id=self.cfg.session_id,
                                                  scope=self.cfg.scope)
                if rec is None and getattr(self.memory, "scope_violations", None):
                    self.log.emit(EventType.AUDIT, now(), request_index=k, ok=False,
                                  issues=["persona_line_not_recorded"],
                                  detail=str(self.memory.scope_violations[-1]))
            claims = [(c, s) for c, rid, s in self._drain(self.director.events.completion_claims) if rid == k]
            if claims:
                self._claims[k] = claims  # logged when the line is actually heard (speech onset)
            self._drain_director_events(t)

    def _audit(self, script: BlockScript) -> None:
        """Pre-generation script audit (§15): the model cannot be steered word by word, so the
        script is checked before it is generated. Shared by all conditions (safety substrate)."""
        issues = []
        for term in self.director.erased_terms:
            if term in script.transcript or term in script.action or any(term in c for c in script.corrections):
                script.transcript = script.transcript.replace(term, "")
                script.action = script.action.replace(term, "")
                script.corrections = [c for c in script.corrections if term not in c]
                issues.append("erased_term")
        if len(script.transcript) > 2 * CHARS_PER_REQUEST:
            script.transcript = script.transcript[: 2 * CHARS_PER_REQUEST]
            issues.append("too_long")
        self.log.emit(EventType.AUDIT, now(), request_index=script.request_index, ok=not issues, issues=issues)

    def _drain_director_events(self, t: float) -> None:
        ev = self.director.events
        for chain_id, reason in self._drain(ev.refusals):
            self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason)
        for chain_id, reason in self._drain(ev.degradations):
            self.log.emit(EventType.REFUSAL, t, chain_id=chain_id, reason=reason, degraded=True)
        for chain_id, revision in self._drain(ev.capacity_skips):
            self.log.emit(EventType.CAPACITY_SKIP, t, chain_id=chain_id, revision=revision)
        for original, cleaned in self._drain(ev.narration_guards):
            self.log.emit(EventType.NARRATION_GUARD, t, original=original, cleaned=cleaned)

    def _resolved(self, k: int) -> bool:
        return k in self.sched.presented_start or k in self.dropped

    @staticmethod
    def _drain(items: list) -> list:
        out = list(items)
        items.clear()
        return out

    # ------------------------------------------------------------------ chunk loop
    async def _chunk_loop(self) -> None:
        async for ch in self.gen.chunks():
            self.chunks[ch.request_index].append(ch)
            self.log.emit(EventType.CHUNK_READY, ch.t_ready, request_index=ch.request_index,
                          chunk_index=ch.chunk_index, n_frames=ch.n_frames)
            if ch.chunk_index == self.n_chunks - 1:
                self.sched.on_duration(ch.request_index,
                                       sum(c.duration_s for c in self.chunks[ch.request_index]))
                for tm in self.gen.timings:
                    if tm.request_index == ch.request_index:
                        self.sched.observe_timing(tm)
                        self.log.emit(EventType.REQUEST_DONE, now(), request_index=ch.request_index,
                                      lead_s=tm.lead_s, teacher_s=tm.teacher_s,
                                      total_s=(tm.t_done - tm.t_lock) if tm.t_done else None)
            if ch.request_index in self.dropped:
                continue  # generated before a barge-in: never shown
            script = self.scripts.get(ch.request_index)
            if script is not None:
                await self.transport.send_chunk(ch, script)

    # ------------------------------------------------------------------ presentation acks
    def on_presented(self, request_index: int, chunk_index: int, t_start: float, t_end: float) -> None:
        """Called by the transport when a chunk *finished* presenting (with its start/end times)."""
        if request_index in self.dropped:
            return  # late ack of interrupted content: not evidence
        if chunk_index == 0:
            self.sched.on_presented(request_index, t_start)
            self.director.ledger.mark_presented(request_index)
        self.presented[request_index].add(chunk_index)
        self.chunk_start[(request_index, chunk_index)] = t_start
        self.last_presented_end = max(self.last_presented_end or t_end, t_end)
        self.log.emit(EventType.CHUNK_PRESENTED, t_start, request_index=request_index,
                      chunk_index=chunk_index, t_end=t_end)
        self._maybe_onset(request_index, chunk_index, t_start)
        if len(self.presented[request_index]) == self.n_chunks and request_index not in self._checked:
            self._checked.add(request_index)
            if self.cfg.qc_enabled:
                self._spawn(self._run_checks(request_index, t_evidence=t_end), "qc")
        self._maybe_finish()

    def _maybe_onset(self, k: int, ci: int, t_start: float) -> None:
        """Speech onset / completion claim time = presentation time of the first audible audio
        of a request that carries a line (energy onset in the presented chunk)."""
        script = self.scripts.get(k)
        if k in self._onset_done or script is None or not script.transcript:
            return
        chunk = next((c for c in self.chunks.get(k, []) if c.chunk_index == ci), None)
        off = audio_onset_s(chunk) if chunk is not None else None
        if off is None:
            if ci < self.n_chunks - 1:
                return  # silent chunk: look at the next one
            if 0 not in self.presented[k]:
                return
            t, source = self.chunk_start.get((k, 0), t_start), "request_start"  # no audible audio found
        else:
            t, source = t_start + off, "audio_energy"
        self._onset_done.add(k)
        self.log.emit(EventType.SPEECH_ONSET, t, request_index=k, chain_ids=script.chain_ids,
                      onset_source=source)
        for chain_id, step in self._claims.pop(k, []):
            self.log.emit(EventType.COMPLETION_CLAIM, t, request_index=k, chain_id=chain_id, step=step,
                          text=script.transcript)

    def _maybe_finish(self) -> None:
        m = self.cfg.max_requests
        if m is None:
            return
        last = m - 1
        done = last in self.dropped or len(self.presented.get(last, ())) == self.n_chunks
        if done and all(self._resolved(k) for k in range(m)):
            self._stop.set()

    # ------------------------------------------------------------------ QC
    async def _run_checks(self, k: int, t_evidence: float) -> None:
        script = self.scripts.get(k)
        if script is None or not script.checks or self.director.mode == DirectorMode.OPEN_LOOP:
            return
        chunks = list(self.chunks[k])
        action_verdicts: list[Verdict] = []
        revision, step = script.provenance.get("revision"), script.provenance.get("step")
        for q in script.checks:
            if q.kind == "speech":
                if self.speech_check is None:
                    continue
                v = await asyncio.to_thread(self.speech_check.check, q, script.transcript, chunks, k, t_evidence)
            elif self.judge is not None:
                v = await self.judge.judge(q, chunks, k, t_evidence)
            else:
                continue
            if k in self.dropped:
                return
            if q.kind == "action":
                action_verdicts.append(v)
            self.log.emit(EventType.VERDICT, v.t_verdict, request_index=k, qid=v.qid, kind=q.kind,
                          label=v.label.value, confidence=v.confidence, rationale=v.rationale,
                          t_evidence=t_evidence, source="online_monitor", chain_ids=script.chain_ids,
                          revision=revision, step=step)
            self.director.ledger.record_verdict(k, v.qid, v.label.value)
        intent = script.provenance.get("intent", "")
        for chain_id in script.chain_ids:
            if action_verdicts and all(v.label == VerdictLabel.COMPLIED for v in action_verdicts):
                self.director.on_verified(chain_id, intent, k, t_evidence, revision=revision, step=step)
            elif any(v.label == VerdictLabel.NOT_COMPLIED for v in action_verdicts):
                await self._repair(chain_id, intent, script, action_verdicts, t_evidence)
        self._drain_director_events(now())

    async def _repair(self, chain_id: str, intent: str, script: BlockScript, failed: list[Verdict],
                      t_evidence: float) -> None:
        mode = self.cfg.correction_mode
        if mode == CorrectionMode.NONE:
            return
        if mode == CorrectionMode.RANDOMIZED:
            mode = self._rng.choice([CorrectionMode.GRADIENT, CorrectionMode.REPEAT])
        if mode == CorrectionMode.GRADIENT:
            qtext = {q.qid: q.text for q in script.checks}
            sentence = await self.corrector.correction(script.action, failed, qtext)
        else:
            sentence = ""
        # C = everything between the evidence time E and a lockable correction: VLM verdict,
        # correction synthesis, compile/audit (measured here) + text encoding (measured in M0).
        t0 = now()
        compile_prompt(BlockScript(request_index=script.request_index, plan_version=script.plan_version,
                                   canon=script.canon, action=script.action, transcript="",
                                   corrections=[sentence] if sentence else []))
        cost = (now() - t_evidence) + self.cfg.text_encode_s
        self._chain_costs.append(cost)
        j = self.sched.earliest_correctable(t_evidence, cost, self.next_lock)
        queued = self.director.queue_retry(chain_id, intent, correction=sentence,
                                           failed_request=script.request_index,
                                           revision=script.provenance.get("revision"),
                                           step=script.provenance.get("step"), min_request=j)
        self.log.emit(EventType.REPAIR, now(), request_index=script.request_index,
                      chain_id=chain_id, mode=mode.value, correction=sentence, queued=queued,
                      earliest_correctable=j, next_unlocked=self.next_lock, chain_cost_s=cost,
                      compile_s=now() - t0, step=script.provenance.get("step"),
                      revision=script.provenance.get("revision"))

    # ------------------------------------------------------------------ user input
    async def on_speech_start(self, t: float | None = None) -> None:
        """Barge-in: stop playback now; stop planning ahead; mark unshown generated content."""
        t = now() if t is None else t
        await self._drop_unpresented()
        self.log.emit(EventType.PLAYBACK_STOP, now(), t_speech_onset=t, dropped=sorted(self.dropped))
        self.director.on_barge_in()
        self._maybe_finish()

    async def _drop_unpresented(self) -> None:
        """Stop playback and discard everything locked but not (fully) presented."""
        for k in range(self.next_lock):
            if len(self.presented.get(k, ())) < self.n_chunks:
                self.dropped.add(k)
                self._claims.pop(k, None)  # a claim that is never heard is not a claim
                self.director.ledger.mark_generated_not_presented(k)
        await self.transport.stop_playback()

    async def on_user_utterance(self, utt: Utterance) -> dict[str, Any]:
        self.log.emit(EventType.UTTERANCE_END, utt.t_end, uid=utt.uid, speaker=utt.speaker, text=utt.text)
        # A forget request must not recall the very fact it asks to erase into the responder.
        memories = None
        if self.memory and not _FORGET.search(utt.text):
            memories = self.memory.recall(utt.text, mode=self.cfg.scope)
        if self.memory:
            self.memory.on_user_utterance(utt)
        decision = await self.director.on_user_utterance(utt, memories)
        term = (decision or {}).get("forget_term")
        if term and self.memory is not None and hasattr(self.memory, "forget"):
            await self._erase(term)
        self._drain_director_events(now())
        if term:  # the decision itself names the erased term
            decision = json.loads(json.dumps(decision, ensure_ascii=False).replace(term, "[已删除]"))
        self.log.emit(EventType.UTTERANCE_END, now(), uid=utt.uid, decision=decision,
                      chains={c.chain_id: c.status.value for c in self.director.chains.values()})
        return decision

    async def _erase(self, term: str) -> None:
        """Erasure (proposal §12): quiesce locking, memory cascade, purge controller state and
        stored prompts, drop unpresented content, restart the generator from canon. Fails closed:
        an incomplete memory erasure is logged as an ERROR."""
        self._ready.clear()
        ack = getattr(self.memory, "acknowledge_erasure", None)
        report = None

        def acknowledge(target: str, ok: bool, detail: str = "") -> None:
            if ack is not None and report is not None:
                ack(report, target, ok=ok, detail=detail)

        try:
            report = self.memory.forget(term)
            purged = self.director.purge(term)
            acknowledge("unsent_scripts", True, f"controller items purged: {purged}")
            # The responder is stateless per call; its context is rebuilt from purged state.
            acknowledge("llm_context", True, "stateless responder; memory notes and chains purged")
            for k, s in self.scripts.items():
                if term in s.transcript or term in s.action:
                    s.transcript = s.transcript.replace(term, "[已删除]")
                    s.action = s.action.replace(term, "[已删除]")
                if term in self.prompts.get(k, ""):
                    self.prompts[k] = self.prompts[k].replace(term, "[已删除]")
            self.log.redact(term)  # in memory and in the JSONL file
            await self._drop_unpresented()
            self.director.ledger.generated_not_presented.clear()  # erased content must not be bridged to
            try:
                await self.gen.reset()
                acknowledge("generator_state", True, "generator session reset to canon")
            except Exception as e:  # noqa: BLE001
                acknowledge("generator_state", False, f"reset failed: {e}")
            recorder = getattr(self.transport, "recorder", None)
            if recorder is None:
                acknowledge("recordings", True, "event log redacted; no media recording")
            else:  # presented audio/video cannot be redacted by text replacement
                acknowledge("recordings", False, f"media recording {getattr(recorder, 'path', '')} must be deleted")
        finally:
            self._ready.set()
        complete = getattr(report, "complete", True)
        pending = list(getattr(report, "pending_targets", []) or [])
        self.log.emit(EventType.PLAYBACK_STOP, now(), erasure=True,
                      deleted=len(getattr(report, "deleted_ids", []) or []),
                      kinds=getattr(report, "kinds", None), controller_purged=purged,
                      generator_reset=True, erasure_complete=complete, pending_targets=pending)
        if not complete:
            self.log.emit(EventType.ERROR, now(), where="erasure", error="memory erasure incomplete",
                          detail=str(getattr(report, "errors", "")))
        self._maybe_finish()

    def open_chains(self) -> list[str]:
        return [c.chain_id for c in self.director.chains.values() if c.status == ChainStatus.OPEN]

===== FILE: live_agent/generator/base.py =====
"""Generator interface.

A generator consumes one compiled prompt per request (5 s for TaoMate-H3) and yields
the request's chunks as they become ready. Implementations:

- ``MockGenerator``   : deterministic, CPU-only, configurable latencies (tests / sim).
- ``TaoMateH3Generator``: wraps the TaoMate-H3 streaming runtime with the T1 prompt
  queue, T2 audio-teacher lookahead and T3 per-chunk output (see proposal §6.2).

Contract (mirrors the single timeline of proposal §10):
- ``submit(request_index, prompt)`` *locks* the prompt for that request (event LOCK).
  Requests must be submitted in order; request k+1 may only start generating after
  request k's final KV commit (KV dependency).
- ``chunks()`` is an async iterator over ``Chunk`` objects in generation order.
- ``reset(prompt)`` starts a new generation session (fresh KV/sink); used for
  session-reset drift correction and erasure.
- ``timings`` exposes the measured G_a (teacher) and G_1 (first chunk) of recent
  requests so the scheduler can estimate Lambda.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from live_agent.types import Chunk


@dataclass
class RequestTiming:
    request_index: int
    t_lock: float
    t_teacher_start: float | None = None
    t_teacher_done: float | None = None
    t_student_start: float | None = None
    t_first_chunk: float | None = None
    t_done: float | None = None

    @property
    def teacher_s(self) -> float | None:
        if self.t_teacher_start is None or self.t_teacher_done is None:
            return None
        return self.t_teacher_done - self.t_teacher_start

    @property
    def lead_s(self) -> float | None:
        """Lock -> first chunk ready (Lambda without transport)."""
        if self.t_first_chunk is None:
            return None
        return self.t_first_chunk - self.t_lock


@dataclass
class GeneratorInfo:
    name: str
    request_seconds: float = 5.0
    chunks_per_request: int = 4
    fps: float = 24.0
    width: int = 864
    height: int = 480
    sample_rate: int = 32000
    extra: dict = field(default_factory=dict)


class Generator(abc.ABC):
    info: GeneratorInfo

    @abc.abstractmethod
    async def start(self) -> None:
        """Load models / spawn workers."""

    @abc.abstractmethod
    async def submit(self, request_index: int, prompt: str) -> None:
        """Lock the prompt for ``request_index`` (must be the next index)."""

    @abc.abstractmethod
    def chunks(self) -> AsyncIterator[Chunk]:
        """Async iterator over generated chunks, in order."""

    @abc.abstractmethod
    async def reset(self) -> None:
        """Drop all generator state (KV, sink, teacher tail); next submit starts a new session."""

    @abc.abstractmethod
    async def close(self) -> None: ...

    @property
    @abc.abstractmethod
    def timings(self) -> list[RequestTiming]: ...

    @property
    def next_request_index(self) -> int:
        raise NotImplementedError


class SessionView(Generator):
    """One live session on a long-lived shared generator (TaoMate-H3 workers take ~130 s to start).

    ``start`` resets the backend (fresh KV/sink/teacher tail) and numbers this session's requests
    from 0; ``close`` resets again instead of shutting the workers down. Chunks are filtered by
    the backend's generation epoch (``chunk.meta["session"]``), so output queued before any reset
    (session start, barge-in reset, erasure) is never yielded. Only one view may be active at a
    time (the caller serialises). ``seed`` (optional) sets the backend's generation seed.
    """

    def __init__(self, backend: Generator, seed: int | None = None) -> None:
        self.backend = backend
        self.info = backend.info
        self.seed = seed
        self._offset = 0
        self._epoch = None

    async def start(self) -> None:
        if self.seed is not None and hasattr(self.backend, "seed"):
            self.backend.seed = self.seed
        await self.reset()
        self._offset = self.backend.next_request_index

    async def submit(self, request_index: int, prompt: str) -> None:
        await self.backend.submit(request_index + self._offset, prompt)

    async def chunks(self) -> AsyncIterator[Chunk]:
        from dataclasses import replace

        async for ch in self.backend.chunks():
            if ch.request_index < self._offset:
                continue  # stale chunk from an earlier session
            if self._epoch is not None and ch.meta.get("session", self._epoch) != self._epoch:
                continue  # generated before the latest reset
            yield replace(ch, request_index=ch.request_index - self._offset)

    async def reset(self) -> None:
        await self.backend.reset()  # indices stay monotonic within the session
        self._epoch = getattr(self.backend, "session_epoch", None)

    async def close(self) -> None:
        await self.backend.reset()

    @property
    def timings(self) -> list[RequestTiming]:
        from dataclasses import replace

        return [replace(t, request_index=t.request_index - self._offset)
                for t in self.backend.timings if t.request_index >= self._offset]

    @property
    def next_request_index(self) -> int:
        return self.backend.next_request_index - self._offset

===== FILE: live_agent/generator/taomate_h3.py =====
"""TaoMate-H3 streaming generator adapter (``TaoMateH3Generator``).

Implements ``live_agent.generator.base.Generator`` on top of two torchrun worker groups
(see ``live_agent/generator/taomate_worker/protocol.py`` for the wire protocol):

* T1 mid-session prompt queue: ``submit(k, prompt)`` locks one 5-second request at a time;
  nothing is precompiled. The text encoder stays resident in the teacher group.
* T2 audio-teacher lookahead: the base-H3 audio teacher for request k starts as soon as k is
  locked (``lookahead=True``), overlapping the student's generation of k-1 when the teacher
  has its own GPUs, and carries the 1 s (40-latent) audio tail across requests.
* T3 per-chunk output: every chunk (34/34/34/17 native 24 fps frames + aligned 32 kHz
  stereo audio) is yielded by ``chunks()`` as soon as its VAE decode finishes.

This module only needs the standard library and numpy; torch lives in the worker
environment (``.venvs/taomate-h3``). The caller must hold a canhazgpu reservation for the
devices it passes (e.g. run the whole program under ``gpu run ...``).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
import threading
import time
from collections.abc import AsyncIterator
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.generator.taomate_worker import protocol as P
from live_agent.types import Chunk, now

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PYTHON = REPO / ".venvs" / "taomate-h3" / "bin" / "python"
DEFAULT_MODEL_ROOT = Path(
    "/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe"
)
DEFAULT_ADAPTER = REPO / ".cache" / "models" / "TaoMate-H3"


class WorkerError(RuntimeError):
    pass


def split_devices(visible: str | None) -> tuple[str, str | None]:
    """Default placement: first 4 (or 8) devices for the student, 2+ leftovers for the teacher."""

    ids = [d for d in (visible or "").split(",") if d.strip()]
    if len(ids) >= 8:
        student, rest = ids[:8], ids[8:]
    elif len(ids) >= 4:
        student, rest = ids[:4], ids[4:]
    else:
        raise ValueError("TaoMate-H3 needs at least 4 visible GPUs for the student")
    teacher = ",".join(rest[: 2 * (len(rest) // 2)]) if len(rest) >= 2 else None
    return ",".join(student), teacher


class TaoMateH3Generator(Generator):
    def __init__(
        self,
        *,
        student_devices: str | None = None,
        teacher_devices: str | None = None,
        colocate_teacher: bool | None = None,
        model_root: Path = DEFAULT_MODEL_ROOT,
        adapter_dir: Path = DEFAULT_ADAPTER,
        python: Path = DEFAULT_PYTHON,
        width: int = 480,  # portrait 480x864, the README's benchmark canvas
        height: int = 864,
        seed: int = 8301,
        lookahead: bool = True,
        launch: bool = True,
        log_dir: Path | None = None,
        start_timeout: float = 1800.0,
        return_latents: bool = False,
        warmup_prompt: str | None = None,
    ) -> None:
        self.info = GeneratorInfo(name="taomate-h3", width=width, height=height,
                                  request_seconds=119 / 24,
                                  extra={"native_frames_per_request": 119, "lookahead": lookahead})
        if launch and student_devices is None:
            student_devices, auto_teacher = split_devices(os.environ.get("CUDA_VISIBLE_DEVICES"))
            if teacher_devices is None and not colocate_teacher:
                teacher_devices = auto_teacher
        self.student_devices = student_devices
        self.teacher_devices = teacher_devices or student_devices  # None -> colocated
        self.model_root = Path(model_root)
        self.adapter_dir = Path(adapter_dir)
        self.python = Path(python)
        self.seed = seed
        self.lookahead = lookahead
        self.launch = launch
        self.log_dir = Path(log_dir) if log_dir else REPO / ".cache" / "taomate_worker_logs"
        self.start_timeout = start_timeout
        self.return_latents = return_latents
        self.warmup_prompt = warmup_prompt
        self.warmup_s: float | None = None
        self.authkey = secrets.token_bytes(16)
        self.address: tuple[str, int] | None = None
        self.worker_info: dict[str, dict[str, Any]] = {}
        self.request_extras: dict[int, dict[str, Any]] = {}
        self.errors: list[dict[str, Any]] = []
        self._listener: Listener | None = None
        self._channels: dict[str, P.Channel] = {}
        self._procs: dict[str, subprocess.Popen] = {}
        self._ready: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._out: asyncio.Queue[Chunk | Exception | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._prompts: dict[int, str] = {}
        self._teacher_done: dict[int, dict[str, Any]] = {}
        self._next = 0
        self._session = 0
        self._session_base = 0  # global index of local request 0 in this session
        self._taught = -1  # highest request index sent to the teacher
        self._generated = -1  # highest request index sent to the student
        self._student_done = -1  # highest request index the student finished
        self._clock_offset = time.monotonic() - time.time()
        self._futures: dict[str, asyncio.Future] = {}

    @classmethod
    def add_args(cls, p) -> None:
        p.add_argument("--taomate-student-devices", default=None,
                       help="comma list; default: split CUDA_VISIBLE_DEVICES (see split_devices)")
        p.add_argument("--taomate-teacher-devices", default=None)
        p.add_argument("--taomate-colocate-teacher", action="store_true")
        p.add_argument("--taomate-model-root", default=str(DEFAULT_MODEL_ROOT))
        p.add_argument("--taomate-adapter-dir", default=str(DEFAULT_ADAPTER))
        p.add_argument("--taomate-python", default=str(DEFAULT_PYTHON))
        p.add_argument("--taomate-width", type=int, default=480)
        p.add_argument("--taomate-height", type=int, default=864)
        p.add_argument("--taomate-seed", type=int, default=8301)
        p.add_argument("--taomate-no-warmup", action="store_true")

    @classmethod
    def from_args(cls, args) -> "TaoMateH3Generator":
        """Build from the unparsed ``--taomate-*`` options a CLI left in ``args.extra``."""
        import argparse

        p = argparse.ArgumentParser(add_help=False)
        cls.add_args(p)
        o, _ = p.parse_known_args(getattr(args, "extra", []) or [])
        warmup = None
        if not o.taomate_no_warmup:
            warmup = ("integrated_multimodal_description: [Shot 1] A person sits quietly at a desk, "
                      "reading a book in soft daylight.\n\noverall_soundscape: Quiet room tone.\n\n"
                      "non_diegetic_music: N/A")
        return cls(student_devices=o.taomate_student_devices, teacher_devices=o.taomate_teacher_devices,
                   colocate_teacher=o.taomate_colocate_teacher, model_root=Path(o.taomate_model_root),
                   adapter_dir=Path(o.taomate_adapter_dir), python=Path(o.taomate_python),
                   width=o.taomate_width, height=o.taomate_height, seed=o.taomate_seed,
                   warmup_prompt=warmup)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._listener = Listener(("127.0.0.1", 0), authkey=self.authkey)
        self.address = self._listener.address
        self._ready = {P.ROLE_TEACHER: asyncio.Event(), P.ROLE_STUDENT: asyncio.Event()}
        threading.Thread(target=self._accept_loop, daemon=True).start()
        if self.launch:
            self._spawn()
        waiter = asyncio.gather(*(event.wait() for event in self._ready.values()))
        deadline = time.monotonic() + self.start_timeout
        while not waiter.done():
            await asyncio.wait({waiter}, timeout=1.0)
            self._check_processes()
            if self.errors and not waiter.done():
                waiter.cancel()
                raise WorkerError(f"worker failed during start: {self.errors[-1]['message']}")
            if time.monotonic() > deadline:
                waiter.cancel()
                raise WorkerError("TaoMate-H3 workers did not become ready in time")
        if self.warmup_prompt:
            await self._warmup(self.warmup_prompt)

    async def _warmup(self, prompt: str) -> None:
        """Run one throw-away request (Triton JIT, CUDA graphs/allocator, VAE fusions), then
        reset so the caller's session starts at request 0 with a fresh KV/sink/teacher tail."""

        started = now()
        await self.submit(0, prompt)
        received = 0
        async for _chunk in self.chunks():
            received += 1
            if received == 4:
                break
        while self._student_done < 0:
            await asyncio.sleep(0.05)
        self.warmup_s = now() - started
        self.warmup_record = {"timing": self._timings.get(0), "extras": self.request_extras.get(0)}
        await self.reset()
        self._next = self._session_base = 0
        self._taught = self._generated = self._student_done = -1
        self._timings.clear()
        self._prompts.clear()
        self.request_extras.clear()

    def _worker_env(self, role: str, devices: str) -> dict[str, str]:
        env = os.environ.copy()
        assert self.address is not None
        env.update({
            P.ENV_ADDRESS: f"{self.address[0]}:{self.address[1]}",
            P.ENV_AUTHKEY: self.authkey.hex(),
            P.ENV_ROLE: role,
            "CUDA_VISIBLE_DEVICES": devices,
            "OMP_NUM_THREADS": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(REPO), str(REPO / "external" / "TaoMate-H3" / "src"),
                              env.get("PYTHONPATH")])
            ),
        })
        return env

    def _spawn(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        common = ["--width", str(self.info.width), "--height", str(self.info.height),
                  "--model-root", str(self.model_root)]
        plan = {
            P.ROLE_TEACHER: (self.teacher_devices, "teacher_service", common),
            P.ROLE_STUDENT: (self.student_devices, "student_service",
                             [*common, "--adapter", str(self.adapter_dir)]),
        }
        stamp = time.strftime("%Y%m%dT%H%M%S")
        for role, (devices, module, args) in plan.items():
            count = len(devices.split(","))
            command = [
                str(self.python), "-m", "torch.distributed.run", "--standalone",
                f"--nproc-per-node={count}", "--module",
                f"live_agent.generator.taomate_worker.{module}", *args,
            ]
            log = open(self.log_dir / f"{stamp}-{role}.log", "w")
            self._procs[role] = subprocess.Popen(
                command, env=self._worker_env(role, devices), stdout=log,
                stderr=subprocess.STDOUT, cwd=str(REPO),
            )

    def _check_processes(self) -> None:
        for role, proc in self._procs.items():
            code = proc.poll()
            if code is not None and not any(e.get("role") == role and e.get("exit") for e in self.errors):
                self.errors.append({"role": role, "exit": code,
                                    "message": f"{role} worker exited with code {code}"})

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while len(self._channels) < 2:
            try:
                conn = self._listener.accept()
            except (OSError, EOFError):
                return
            channel = P.Channel(conn)
            try:
                hello = channel.recv()
            except (EOFError, OSError):
                continue
            role = hello.get("role")
            if role not in (P.ROLE_TEACHER, P.ROLE_STUDENT) or role in self._channels:
                channel.close()
                continue
            self._channels[role] = channel
            self._post(role, hello)
            threading.Thread(target=self._reader, args=(role, channel), daemon=True).start()

    def _reader(self, role: str, channel: P.Channel) -> None:
        while True:
            try:
                message = channel.recv()
            except (EOFError, OSError, TypeError):  # TypeError: connection closed under us
                self._post(role, {"type": "disconnected"})
                return
            self._post(role, message)

    def _post(self, role: str, message: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._on_message, role, message)
        except RuntimeError:  # loop closed between the check and the call
            pass

    def _send(self, role: str, message: dict[str, Any]) -> None:
        channel = self._channels.get(role)
        if channel is None:
            raise WorkerError(f"{role} worker is not connected")
        channel.send(message)

    def _mono(self, t: float | None) -> float | None:
        return None if t is None else t + self._clock_offset

    # ------------------------------------------------------------------ message handling
    def _on_message(self, role: str, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == P.HELLO:
            self.worker_info.setdefault(role, {})["hello"] = message
            return
        if kind == P.READY:
            self.worker_info.setdefault(role, {})["ready"] = message
            self._ready[role].set()
            return
        if kind == "disconnected":
            if not getattr(self, "_closing", False):
                self._fail({"role": role, "message": f"{role} worker disconnected"})
            return
        if kind in ("flushed", "full_audio"):
            future = self._futures.pop(kind, None)
            if future is not None and not future.done():
                future.set_result(message)
            return
        session = int(message.get("session", -1))
        if kind == P.ERROR:
            if session == self._session:
                self._fail({"role": role, **message})
            return
        if session != self._session:
            return  # stale reply from a reset session
        k = int(message.get("request_index", -1))
        timing = self._timings.get(k)
        extras = self.request_extras.setdefault(k, {})
        if kind == P.TEACHER_DONE:
            if timing is not None:
                timing.t_teacher_start = self._mono(message["t_start"])
                timing.t_teacher_done = self._mono(message["t_done"])
            extras.update({
                "teacher_text_s": message["t_text_done"] - message["t_start"],
                "teacher_s": message["t_done"] - message["t_start"],
                "teacher_done_received": now(),
                "audio_latent_count": message.get("audio_latent_count"),
                "teacher_peak_allocated_gib": message.get("peak_allocated_gib"),
            })
            if self.return_latents:  # debug/parity: keep the opaque teacher payload
                extras["teacher_blob"] = message["blob"]
            self._teacher_done[k] = message
            self._dispatch()
        elif kind == P.REQUEST_START:
            if timing is not None:
                timing.t_student_start = self._mono(message["t"])
        elif kind == P.CHUNK:
            t_ready = now()
            chunk = Chunk(
                request_index=k,
                chunk_index=int(message["chunk_index"]),
                n_frames=int(message["n_frames"]),
                fps=float(message["fps"]),
                video=P.from_shm(message.get("video")),
                audio=P.from_shm(message.get("audio")),
                sample_rate=int(message.get("sample_rate", 32000)),
                t_ready=t_ready,
                meta={
                    "prompt": self._prompts.get(k, ""),
                    "session": session,
                    "local_index": message.get("local_index"),
                    "frame_start": message.get("frame_start"),
                    "audio_sample_start": message.get("audio_sample_start"),
                    "latent_count": message.get("latent_count"),
                    "audio_context": message.get("audio_context"),
                    "t_phase_start": self._mono(message.get("t_phase_start")),
                    "t_denoised": self._mono(message.get("t_denoised")),
                    "t_decoded": self._mono(message.get("t_decoded")),
                    "t_worker_ready": self._mono(message.get("t_ready")),
                },
            )
            if chunk.chunk_index == 0 and timing is not None:
                timing.t_first_chunk = t_ready
            extras.setdefault("chunks", []).append(
                {key: chunk.meta[key] for key in ("t_phase_start", "t_denoised", "t_decoded",
                                                  "t_worker_ready")} | {"t_ready": t_ready,
                                                                        "n_frames": chunk.n_frames})
            self._out.put_nowait(chunk)
        elif kind == P.REQUEST_DONE:
            if timing is not None:
                timing.t_done = self._mono(message["t"])
            extras.update({
                "audio_teacher_exact_match": message.get("audio_teacher_exact_match"),
                "frames_emitted": message.get("frames_emitted"),
                "student_peak_allocated_gib": message.get("peak_allocated_gib"),
                "latents": message.get("latents"),
            })
            self._student_done = max(self._student_done, k)
            self._dispatch()

    def _fail(self, error: dict[str, Any]) -> None:
        self.errors.append(error)
        self._out.put_nowait(WorkerError(f"{error.get('role')}: {error.get('message')}"))

    def _dispatch(self) -> None:
        """Send teacher and student work that has become eligible, in request order."""

        # teacher: all locked requests (lookahead) or only the one after the student's last
        limit = self._next - 1 if self.lookahead else min(self._next - 1, self._student_done + 1)
        while self._taught < limit:
            k = self._taught + 1
            if not self.lookahead and k > self._session_base and k - 1 > self._student_done:
                break
            self._send(P.ROLE_TEACHER, {
                "type": P.TEACH, "session": self._session, "request_index": k,
                "local_index": k - self._session_base, "prompt": self._prompts[k],
                "seed": self.seed,
            })
            self._taught = k
        # student: next request once its teacher output is available (student queues FIFO)
        while self._generated + 1 in self._teacher_done:
            k = self._generated + 1
            done = self._teacher_done.pop(k)
            self._send(P.ROLE_STUDENT, {
                "type": P.GENERATE, "session": self._session, "request_index": k,
                "local_index": k - self._session_base, "prompt": self._prompts[k],
                "seed": self.seed, "blob": done["blob"], "return_latents": self.return_latents,
            })
            self._generated = k

    # ------------------------------------------------------------------ Generator API
    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        self._timings[request_index] = RequestTiming(request_index, t_lock=now())
        self._prompts[request_index] = prompt
        self._next += 1
        self._dispatch()

    async def chunks(self) -> AsyncIterator[Chunk]:
        while True:
            item = await self._out.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def reset(self) -> None:
        self._session += 1
        self._session_base = self._next
        self._taught = self._generated = self._student_done = self._next - 1
        self._teacher_done.clear()
        for role in (P.ROLE_TEACHER, P.ROLE_STUDENT):
            self._send(role, {"type": P.RESET, "session": self._session})

    async def flush(self, timeout: float = 120.0) -> dict[str, Any]:
        """Ask the student for the held 5-frame video overlap (end of a session)."""

        return await self._request_reply("flushed", {"type": "flush"}, timeout)

    async def full_audio(self, timeout: float = 120.0) -> dict[str, Any]:
        """One-shot audio decode of the whole session (parity check against streaming)."""

        return await self._request_reply("full_audio", {"type": "full_audio"}, timeout)

    async def _request_reply(self, key: str, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert self._loop is not None
        future = self._loop.create_future()
        self._futures[key] = future
        self._send(P.ROLE_STUDENT, message)
        return await asyncio.wait_for(future, timeout)

    async def close(self) -> None:
        self._closing = True
        for role in list(self._channels):
            try:
                self._send(role, {"type": P.SHUTDOWN})
            except (WorkerError, OSError):
                pass
        for proc in self._procs.values():
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=120)
            except asyncio.TimeoutError:
                proc.terminate()
                try:
                    await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=30)
                except asyncio.TimeoutError:
                    proc.kill()
        for channel in self._channels.values():
            channel.close()
        if self._listener is not None:
            self._listener.close()
        self._out.put_nowait(None)

    @property
    def timings(self) -> list[RequestTiming]:
        return [self._timings[k] for k in sorted(self._timings)]

    @property
    def session_epoch(self) -> int:
        """Generation epoch; bumped by reset(); carried as chunk.meta["session"]."""
        return self._session

    @property
    def next_request_index(self) -> int:
        return self._next


__all__ = ["TaoMateH3Generator", "WorkerError", "split_devices"]

===== FILE: live_agent/sim.py =====
"""Simulated playback client (transport) for CPU tests and offline simulation.

Plays chunks in real time (optionally sped up), reports presentation start/end times to
the orchestrator, records stalls (gaps between chunks), and implements stop_playback()
(drops everything queued). Time scale: one simulated second = 1/speed wall seconds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from live_agent.types import BlockScript, Chunk, now


@dataclass
class Stall:
    t_start: float
    t_end: float


@dataclass
class SimClient:
    speed: float = 1.0
    orchestrator: object | None = None  # set after construction
    presented: list[tuple[int, int, float, float]] = field(default_factory=list)
    stalls: list[Stall] = field(default_factory=list)
    dropped: list[tuple[int, int]] = field(default_factory=list)
    recorder: object | None = None  # optional Recorder of the presented stream

    def __post_init__(self) -> None:
        self._q: asyncio.Queue[tuple[Chunk, BlockScript]] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._last_end: float | None = None
        self._current: Chunk | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._play())

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        await self._q.put((chunk, script))

    async def stop_playback(self) -> None:
        """Barge-in: stop *now*. The chunk being played is cut (never acknowledged as presented)
        and everything queued is discarded."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            if self._current is not None:
                self.dropped.append((self._current.request_index, self._current.chunk_index))
                self._current = None
            self._task = asyncio.create_task(self._play())
        while not self._q.empty():
            ch, _ = self._q.get_nowait()
            self.dropped.append((ch.request_index, ch.chunk_index))
        self._last_end = None  # the gap after an interruption is not a stall

    async def _play(self) -> None:
        while True:
            ch, _script = await self._q.get()
            self._current = ch
            t0 = now()
            if self._last_end is not None and t0 - self._last_end > 0.05 / self.speed:
                self.stalls.append(Stall(self._last_end, t0))
            await asyncio.sleep(ch.duration_s / self.speed)
            t1 = now()
            self._current = None
            self._last_end = t1
            self.presented.append((ch.request_index, ch.chunk_index, t0, t1))
            if self.recorder is not None:
                self.recorder.write(ch)
            if self.orchestrator is not None:
                self.orchestrator.on_presented(ch.request_index, ch.chunk_index, t0, t1)

    def close(self) -> None:
        if self._task:
            self._task.cancel()
        if self.recorder is not None:
            self.recorder.close()


class Recorder:
    """Writes the *presented* stream (what a viewer saw) to MP4: raw frames are piped to ffmpeg,
    audio is buffered and muxed on close. Needs an ffmpeg with libx264 (``/usr/bin/ffmpeg`` here)."""

    def __init__(self, path, ffmpeg: str = "/usr/bin/ffmpeg") -> None:
        from pathlib import Path

        self.path = Path(path)
        self.ffmpeg = ffmpeg
        self._proc = None
        self._audio: list = []
        self._sr = 32000

    def write(self, chunk: Chunk) -> None:
        """Non-blocking: frames are encoded on a background thread (the caller is the playback loop)."""
        import queue
        import threading

        if not hasattr(self, "_q"):
            self._q = queue.Queue()
            self._thread = threading.Thread(target=self._drain, daemon=True)
            self._thread.start()
        self._q.put(chunk)

    def _drain(self) -> None:
        while True:
            chunk = self._q.get()
            if chunk is None:
                return
            self._write(chunk)

    def _write(self, chunk: Chunk) -> None:
        import subprocess

        import numpy as np

        if chunk.video is None:
            return
        v = np.ascontiguousarray(chunk.video, dtype=np.uint8)
        if self._proc is None:
            _, h, w, _ = v.shape
            self._tmp = self.path.with_suffix(".video.mp4")
            self._proc = subprocess.Popen(
                [self.ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{w}x{h}", "-r", str(chunk.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt",
                 "yuv420p", "-preset", "veryfast", str(self._tmp)], stdin=subprocess.PIPE)
        self._proc.stdin.write(v.tobytes())
        if chunk.audio is not None:
            self._audio.append(np.asarray(chunk.audio, dtype=np.float32))
            self._sr = chunk.sample_rate

    def close(self) -> None:
        import subprocess
        import wave

        import numpy as np

        if hasattr(self, "_q"):
            self._q.put(None)
            self._thread.join()
        if self._proc is None:
            return
        self._proc.stdin.close()
        self._proc.wait()
        if not self._audio:
            self._tmp.replace(self.path)
            return
        a = np.concatenate(self._audio)
        a = a if a.ndim == 2 else a[:, None]
        wav = self.path.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(a.shape[1])
            w.setsampwidth(2)
            w.setframerate(self._sr)
            w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        subprocess.run([self.ffmpeg, "-y", "-loglevel", "error", "-i", str(self._tmp), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-shortest", str(self.path)], check=True)
        self._tmp.unlink()
        wav.unlink()

===== FILE: live_agent/server/app.py =====
"""Live-agent server: FastAPI + WebSocket, one session per connection.

Wire protocol (WS /ws), JSON text frames unless noted:
  client -> server
    {"type":"hello","mode":"private"|"public","user_id":"u1"}
    {"type":"speech_start"}                        barge-in (push-to-talk pressed)
    binary frame                                   recorded speech (webm/opus or wav) -> ASR
    {"type":"text","text":"..."}                   typed utterance (fallback / tests)
    {"type":"chunk_start","request":k,"chunk":c}   presentation start (server stamps arrival)
    {"type":"chunk_end","request":k,"chunk":c}     presentation end
    {"type":"ping","t":...}
  server -> client
    {"type":"chunk","request":k,"chunk":c,"n_frames":n,"fps":24,"sample_rate":sr,
     "width":w,"height":h,"transcript":"..."}      followed by n binary JPEG frames and one binary PCM16 frame
    {"type":"stop"}                                 drop everything queued (barge-in)
    {"type":"transcript","text":"..."}             ASR result of the user's speech
    {"type":"status", ...}

Presentation times are stamped with the *server* monotonic clock on arrival of the
client's chunk_start / chunk_end messages (network delay is logged via ping RTT).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.generator.base import SessionView
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import BlockScript, Chunk, Utterance, new_id, now

log = logging.getLogger("live_agent.server")
STATIC = Path(__file__).parent / "static"


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def to_pcm16(audio: np.ndarray | None, n_samples: int) -> bytes:
    if audio is None or len(audio) == 0:
        return np.zeros(n_samples, dtype=np.int16).tobytes()
    a = audio.mean(axis=1) if audio.ndim == 2 else audio
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


class WSTransport:
    """Orchestrator transport over one WebSocket connection.

    Presentation times: the client reports, for each chunk, when its audio starts / ends at the
    audio *output* (AudioContext.getOutputTimestamp -> performance clock, ``tp`` in ms). The
    server maps that clock to its own with the lowest-RTT ping sample (NTP-style,
    offset = t_server - (t_client_send + rtt/2)). Until a mapping exists, arrival time is used
    (and the event says so)."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.orchestrator: Orchestrator | None = None
        self._send_lock = asyncio.Lock()
        self._starts: dict[tuple[int, int], float] = {}
        self._epoch = 0  # incremented on stop; stale sends are skipped
        self.clock_offset_s: float | None = None
        self.clock_rtt_s: float | None = None

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        epoch = self._epoch
        frames = chunk.video if chunk.video is not None else np.zeros((chunk.n_frames, 8, 8, 3), np.uint8)
        # Encode off the event loop.
        loop = asyncio.get_running_loop()
        jpegs = await loop.run_in_executor(None, lambda: [encode_jpeg(f) for f in frames])
        pcm = to_pcm16(chunk.audio, int(chunk.duration_s * chunk.sample_rate))
        async with self._send_lock:
            if epoch != self._epoch:
                return
            h, w = frames.shape[1:3]
            await self.ws.send_text(json.dumps({
                "type": "chunk", "request": chunk.request_index, "chunk": chunk.chunk_index,
                "n_frames": len(jpegs), "fps": chunk.fps, "sample_rate": chunk.sample_rate,
                "width": int(w), "height": int(h), "transcript": script.transcript}))
            for j in jpegs:
                if epoch != self._epoch:
                    return  # interrupted mid-chunk: the client discards the partial chunk
                await self.ws.send_bytes(j)
            if epoch == self._epoch:
                await self.ws.send_bytes(pcm)

    async def stop_playback(self) -> None:
        """Immediate: does not wait for an in-flight chunk send (which aborts at its next frame)."""
        self._epoch += 1
        await self.ws.send_text(json.dumps({"type": "stop"}))

    def on_clock(self, msg: dict) -> None:
        rtt = float(msg["rtt"]) / 1000.0
        if self.clock_rtt_s is None or rtt <= self.clock_rtt_s:
            self.clock_rtt_s = rtt
            self.clock_offset_s = float(msg["t_server"]) - (float(msg["t_client"]) / 1000.0 + rtt / 2)

    def _to_server(self, msg: dict) -> float:
        if msg.get("tp") is not None and self.clock_offset_s is not None:
            return float(msg["tp"]) / 1000.0 + self.clock_offset_s
        return now()

    def on_client_message(self, msg: dict) -> None:
        t = self._to_server(msg)
        key = (int(msg.get("request", -1)), int(msg.get("chunk", -1)))
        if msg["type"] == "chunk_start":
            self._starts[key] = t
        elif msg["type"] == "chunk_end" and self.orchestrator is not None:
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t)


def build_app(args: argparse.Namespace) -> FastAPI:
    app = FastAPI()
    cfg_dir = Path(args.config)
    canon = json.loads((cfg_dir / "canon.json").read_text(encoding="utf-8"))

    app.state.shared_gen = None
    app.state.session_lock = asyncio.Lock()

    @app.on_event("startup")
    async def _startup() -> None:
        # Heavy generators are started once and shared (reset per session); the mock is per session.
        if args.generator != "mock":
            gen = make_generator(args)
            await gen.start()
            app.state.shared_gen = gen

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.shared_gen is not None:
            await app.state.shared_gen.close()

    @app.get("/")
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hello = json.loads(await ws.receive_text())
        mode = "public" if hello.get("mode") == "public" else "private"
        session_id = new_id("sess")
        transport = WSTransport(ws)
        shared = app.state.shared_gen is not None
        if shared:
            if app.state.session_lock.locked():
                await ws.send_text(json.dumps({"type": "error", "error": "generator busy (one live session at a time)"}))
                await ws.close()
                return
            await app.state.session_lock.acquire()
        orch = None
        inputs: asyncio.Queue = asyncio.Queue()
        worker = None
        try:
            from live_agent.llm import OpenAICompatLLM

            llm = OpenAICompatLLM(args.llm_url, args.llm_model)
            manifest = CapabilityManifest.load(cfg_dir / "capabilities.json")
            if args.dev_allow_uncalibrated:
                manifest.min_status = Status.DOCUMENTED
            ledger = StateLedger.from_config(cfg_dir / "canon.json")
            director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                                persona_bio=canon["persona_bio"], mode=DirectorMode(args.director_mode))
            generator = SessionView(app.state.shared_gen) if shared else make_generator(args)
            sched = LockScheduler(SchedulerConfig(request_s=generator.info.request_seconds,
                                                  lambda_prior_s=args.lambda_prior))
            judge = speech = None
            if args.vlm_url:
                from live_agent.qc.judge import VLMJudge

                judge = VLMJudge(OpenAICompatLLM(args.vlm_url, args.vlm_model))
            asr = None
            if args.asr_url:
                from live_agent.asr import OpenAIASR
                from live_agent.qc.judge import SpeechCheck

                asr = OpenAIASR(args.asr_url, args.asr_model)
                speech = SpeechCheck(asr.transcribe_sync)
            from live_agent.qc.judge import ForwardCorrector

            log_dir = Path(args.log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            orch = Orchestrator(generator, director, sched, transport, judge=judge, corrector=ForwardCorrector(llm),
                                speech_check=speech, memory=make_memory(args, hello, session_id, mode),
                                log=EventLog(log_dir / f"{session_id}.jsonl"),
                                cfg=OrchestratorConfig(session_id=session_id, scope=mode,
                                                       correction_mode=CorrectionMode(args.correction_mode)))
            transport.orchestrator = orch
            await orch.start()
            await ws.send_text(json.dumps({"type": "status", "session": session_id, "mode": mode,
                                           "generator": generator.info.name}))

            async def handle_inputs() -> None:
                """Utterances are processed in order, off the receive loop, so presentation acks
                and barge-in keep being read (and timestamped) while ASR / the LLM run."""
                while True:
                    kind, payload = await inputs.get()
                    try:
                        if kind == "audio":
                            from live_agent.asr import decode_audio_bytes

                            audio = decode_audio_bytes(payload, 16000)
                            text = await asr.transcribe(audio, 16000)
                            await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                        else:
                            text = payload
                        if text:
                            await orch.on_user_utterance(Utterance(new_id("utt"), "user", text, now(),
                                                                   session_id=session_id, scope=mode))
                    except Exception:  # noqa: BLE001
                        log.exception("input handling failed")

            worker = asyncio.create_task(handle_inputs())
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    if asr is not None:
                        inputs.put_nowait(("audio", msg["bytes"]))
                    continue
                data = json.loads(msg["text"])
                t = data.get("type")
                if t in ("chunk_start", "chunk_end"):
                    transport.on_client_message(data)
                elif t == "speech_start":
                    await orch.on_speech_start()
                elif t == "text" and data.get("text", "").strip():
                    inputs.put_nowait(("text", data["text"].strip()))
                elif t == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "t": data.get("t"), "ts": now()}))
                elif t == "clock":
                    transport.on_clock(data)
        except WebSocketDisconnect:
            pass
        finally:
            if worker is not None:
                worker.cancel()
            if orch is not None:
                await orch.stop()
            if shared:
                app.state.session_lock.release()

    return app


def make_generator(args: argparse.Namespace):
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator

        return MockGenerator(size=(480, 864))
    if args.generator == "taomate_h3":
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        return TaoMateH3Generator.from_args(args)
    raise ValueError(args.generator)


def make_memory(args: argparse.Namespace, hello: dict, session_id: str, scope: str = "private"):
    if not args.memory_db:
        return None
    from live_agent.memory_bridge import MemoryBridge

    return MemoryBridge(args.memory_db, user_id=hello.get("user_id", "anon"),
                        stream_id=hello.get("stream_id", "stream-0"), session_id=session_id, mode=scope)


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--asr-url", default="http://127.0.0.1:8103/v1")
    p.add_argument("--asr-model", default="qwen3-asr")
    p.add_argument("--memory-db", default=".cache/memory.sqlite")
    p.add_argument("--log-dir", default=".cache/sessions")
    p.add_argument("--director-mode", default="closed_loop", choices=["closed_loop", "open_loop"])
    p.add_argument("--correction-mode", default="gradient", choices=["gradient", "repeat", "none"])
    p.add_argument("--lambda-prior", type=float, default=3.0)
    p.add_argument("--dev-allow-uncalibrated", action="store_true",
                   help="allow capabilities that were never executed (development only)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8200)
    # TaoMate-H3 generator options are parsed by the adapter (see taomate_h3.py).
    args, rest = p.parse_known_args()
    args.extra = rest
    uvicorn.run(build_app(args), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

===== FILE: live_agent/server/static/index.html =====
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live Agent</title>
<style>
  :root { --bg:#f6f3ec; --ink:#1c1b19; --muted:#6b665c; --accent:#a33a24; --line:#d9d2c2; --card:#fffdf8; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font-family:"Noto Sans SC",system-ui,sans-serif; }
  main { max-width: 980px; margin: 0 auto; padding: 24px 16px; display:flex; flex-direction:column; gap:16px; }
  header { display:flex; justify-content:space-between; align-items:baseline; border-bottom:1px solid var(--ink); padding-bottom:8px; }
  h1 { font-family:"Noto Serif SC",serif; font-size:24px; margin:0; }
  .status { font-size:13px; color:var(--muted); }
  canvas { width:100%; aspect-ratio: 864 / 480; background:#111; border-radius:8px; display:block; }
  .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  button { font:inherit; padding:10px 16px; border-radius:8px; border:1px solid var(--ink); background:var(--card); cursor:pointer; min-height:44px; }
  button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
  button:disabled { opacity:.5; cursor:not-allowed; }
  input[type=text] { flex:1; min-width:200px; font:inherit; padding:10px 12px; border-radius:8px; border:1px solid var(--line); background:var(--card); min-height:44px; }
  .caption { min-height:24px; font-size:16px; }
  .log { font-family: ui-monospace, monospace; font-size:12px; color:var(--muted); background:var(--card); border:1px solid var(--line); border-radius:8px; padding:8px; height:140px; overflow:auto; white-space:pre-wrap; }
  label { font-size:14px; }
</style>
</head>
<body>
<main>
  <header>
    <h1>Live Agent · 书房里的汉服读书人</h1>
    <span class="status" id="status">未连接</span>
  </header>
  <canvas id="screen" width="864" height="480" aria-label="数字人画面"></canvas>
  <div class="caption" id="caption" aria-live="polite"></div>
  <div class="row">
    <label>模式
      <select id="mode"><option value="private">一对一私聊</option><option value="public">测试直播</option></select>
    </label>
    <label>用户 ID <input type="text" id="uid" value="user-1" style="flex:0;width:120px"></label>
    <button class="primary" id="connect">连接</button>
  </div>
  <div class="row">
    <button id="talk" disabled aria-label="按住说话">按住说话</button>
    <input type="text" id="text" placeholder="或输入文字，回车发送" disabled aria-label="文字输入">
    <button id="send" disabled>发送</button>
  </div>
  <div class="log" id="log" aria-label="事件日志"></div>
</main>
<script>
const $ = (id) => document.getElementById(id);
const canvas = $("screen"), g = canvas.getContext("2d");
let ws = null, audioCtx = null, playhead = 0, queue = [], pending = null, recorder = null, epoch = 0;

function logLine(s) { const el = $("log"); el.textContent += s + "\n"; el.scrollTop = el.scrollHeight; }
function setStatus(s) { $("status").textContent = s; }

$("connect").onclick = () => {
  audioCtx = new AudioContext();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => {
    ws.send(JSON.stringify({type: "hello", mode: $("mode").value, user_id: $("uid").value}));
    setStatus("已连接"); ["talk","text","send"].forEach(id => $(id).disabled = false); $("connect").disabled = true;
    const ping = () => ws.readyState === 1 && ws.send(JSON.stringify({type: "ping", t: performance.now()}));
    ping(); setTimeout(ping, 300); setTimeout(ping, 600); setInterval(ping, 5000);
  };
  ws.onclose = () => { setStatus("连接已关闭"); };
  ws.onmessage = onMessage;
  requestAnimationFrame(render);
};

async function onMessage(ev) {
  if (typeof ev.data === "string") {
    const m = JSON.parse(ev.data);
    if (m.type === "chunk") { pending = {meta: m, frames: [], pcm: null, epoch}; }
    else if (m.type === "stop") { stopAll(); logLine("[stop] 打断：清空待播内容"); }
    else if (m.type === "transcript") { logLine("[你] " + m.text); }
    else if (m.type === "status") { setStatus(`会话 ${m.session} · ${m.mode} · ${m.generator}`); }
    else if (m.type === "pong") {
      const rtt = performance.now() - m.t;
      // clock mapping sample for the server: client send time, server receive time, RTT (ms)
      send({type: "clock", t_client: m.t, t_server: m.ts, rtt});
      logLine(`[rtt] ${rtt.toFixed(0)} ms`);
    }
    return;
  }
  if (!pending) return;
  if (pending.frames.length < pending.meta.n_frames) {
    pending.frames.push(createImageBitmap(new Blob([ev.data], {type: "image/jpeg"})));
  } else {
    pending.pcm = new Int16Array(ev.data);
    const c = pending; pending = null;
    c.frames = await Promise.all(c.frames);
    if (c.epoch === epoch) schedule(c);
  }
}

function schedule(c) {
  const m = c.meta, sr = m.sample_rate;
  const buf = audioCtx.createBuffer(1, Math.max(1, c.pcm.length), sr);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < c.pcm.length; i++) ch[i] = c.pcm[i] / 32768;
  const start = Math.max(audioCtx.currentTime + 0.05, playhead);
  const dur = m.n_frames / m.fps;
  const src = audioCtx.createBufferSource(); src.buffer = buf; src.connect(audioCtx.destination); src.start(start);
  playhead = start + dur;
  queue.push({...c, start, end: start + dur, src, startedSent: false, endedSent: false});
}

function stopAll() {
  epoch += 1; pending = null;
  for (const q of queue) { try { q.src.stop(); } catch (e) {} }
  queue = []; playhead = audioCtx ? audioCtx.currentTime : 0;
}

// AudioContext time -> performance clock (ms) at the audio *output* (includes output latency).
function ctxToPerf(t) {
  const o = audioCtx.getOutputTimestamp ? audioCtx.getOutputTimestamp() : null;
  if (!o || !o.performanceTime) return performance.now() + (t - audioCtx.currentTime) * 1000;
  return o.performanceTime + (t - o.contextTime) * 1000;
}

function send(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }

function render() {
  if (audioCtx) {
    const t = audioCtx.currentTime;
    for (const q of queue) {
      if (!q.startedSent && t >= q.start) { q.startedSent = true; send({type: "chunk_start", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.start)}); if (q.meta.transcript) $("caption").textContent = q.meta.transcript; }
      if (q.startedSent && t < q.end) {
        const idx = Math.min(q.frames.length - 1, Math.floor((t - q.start) * q.meta.fps));
        g.drawImage(q.frames[idx], 0, 0, canvas.width, canvas.height);
      }
      if (!q.endedSent && t >= q.end) { q.endedSent = true; send({type: "chunk_end", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.end)}); }
    }
    queue = queue.filter(q => !q.endedSent);
  }
  requestAnimationFrame(render);
}

$("talk").onpointerdown = async () => {
  send({type: "speech_start"}); stopAll();
  const stream = await navigator.mediaDevices.getUserMedia({audio: true});
  recorder = new MediaRecorder(stream, {mimeType: "audio/webm;codecs=opus"});
  const parts = [];
  recorder.ondataavailable = (e) => parts.push(e.data);
  recorder.onstop = async () => { stream.getTracks().forEach(t => t.stop()); ws.send(await new Blob(parts).arrayBuffer()); };
  recorder.start(); $("talk").textContent = "松开结束";
};
$("talk").onpointerup = () => { if (recorder && recorder.state === "recording") recorder.stop(); $("talk").textContent = "按住说话"; };
function sendText() { const v = $("text").value.trim(); if (!v) return; send({type: "speech_start"}); stopAll(); send({type: "text", text: v}); logLine("[你] " + v); $("text").value = ""; }
$("send").onclick = sendText;
$("text").onkeydown = (e) => { if (e.key === "Enter") sendText(); };
</script>
</body>
</html>
