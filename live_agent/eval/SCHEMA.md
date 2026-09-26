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
`simulation`, `generator_path` or `browser`. Only `browser` sessions use the end-to-end input
path (TTS → VAD/ASR → client playback). The primary report refuses any other mode, or a
missing mode, with exit 2; `--allow-non-e2e` labels the whole report "GENERATOR-PATH
PILOT, not the end-to-end E2 result". `chunks_per_request` (int) is needed to decide
whether an RQ2 target request was fully observed. Other keys are free-form metadata.

## Events

| type | required fields | optional fields | emitted by |
|---|---|---|---|
| `utterance` | `uid`, `speaker` (`user`/`persona`/`viewer:<id>`), `text`, `t_start`, `t_end` (VAD endpoint) | `barge_in` (bool) | sim user / ASR |
| `chain_annotation` | `uid` (of the utterance), `action` (`new`/`revision`/`withdrawal`), `chain_id` | `label` (task-local chain label for cross-condition pairing and for looking up the preregistered criteria, e.g. `c1`), `kind` (`action`/`content`/`multistep`; `correction` is treated as `action`), `intent`, `content_type` (`qa`/`explain`/`sing`), `prereg_duration_s`, `steps` (list or int), `checks`, `rubric` | sim user (script) or annotator |
| `lock` | `t`, `request` | `chain_ids`, `plan_version` | orchestrator (diagnostic; not needed for scoring) |
| `chunk_presented` | `request`, `chunk`, `t_start`, `t_end` | `frame_hash` | client presentation ack |
| `observation_end` | `t` (last presented media time of the session) | | runner |
| `verdict` | `source` (`adjudicated`/`human`/`judge`), `label` (`complied`/`not_complied`/`unknown`), and `chain_id` **or** `claim_id` | `revision`, `step` (multistep, 0-based), `request`, `chunk`, `earliest_correctable` (judge `not_complied`: request j), `repair_request` + `revision` (an adjudicated RQ2 repair-target verdict), `t_first_compliant`, `t_evidence`, `t_review_start`, `t_review_end`, `claim_t` (claim-level verdict), `onset_reviewed`, `t_onset`, `annotators`, `reconciliation` (`agreement`/`arbitration`), `batch`, `item`, `criteria_sha256`, `qid` | judge / adjudication tool |
| `rating` | `annotator`, `chain_id`, `label` | `role` (`primary`/`arbiter`), `kind` (`claim_sweep` for a swept claim), `step`, `revision`, `claim_t`, the same time fields as a verdict, `onset_none`, `review_ok`, `t_review_needed`, `batch`, `item` | adjudication tool (one annotator's independent label; kept for agreement statistics, **never scored**) |
| `completion_claim` | `chain_id`, `t` | `source` (`system` (default) / `adjudicated`), `step`, `claim_id`, `request`, `text`, `batch`, `item` | orchestrator (`system`, diagnostic) / audio claim sweep (`adjudicated`, primary) |
| `claim_sweep` | `source` (`adjudicated`) | `n_claims`, `annotators`, `reconciliation`, `t_review_end`, `batch`, `item` | adjudication tool: the session's recording was swept for audible completion claims (required per session in primary scoring) |
| `refusal` | `chain_id`, `t` | `kind` (`refused` (default) / `degraded`), `reason` | compiler / safety filter |
| `capacity_skip` | `chain_id`, `t` | `revision`, `reason` | admission control |
| `speech_onset` | `t`, `on_topic` (`true`/`false`/`null`) | `source` (`script` (default) / `adjudicated` / `human`), `chain_id` (**required for the onset to count toward a chain**), `request` | runner (`script`) / adjudication tool (`adjudicated`) |
| `visual_ack` | `t`, `uid` (the utterance acknowledged) | `kind` (`reaction_clip`/`freeze`) | client |
| `playback_stop` | `t` | `reason` | client |
| `repair_assignment` | `chain_id`, `arm` (`forward_correction`/`repeat`), `failure_request` (k), `target_request` (j = earliest request with P_j ≥ E + C) | `t` (assignment time), `revision` (of the chain's intent at the failure), `arm_drawn` (bool: the arm was randomised), `step`, `E`, `C`, `actual_request` | orchestrator (RQ2: arm randomised per eligible failure point, condition `A2-rq2`) |

## Contract the runner must satisfy

* **Judge verdicts** (`source: "judge"`) carry `revision` = the number of revisions of the
  chain's intent the judged request was planned under, and `step` for multistep. Each
  verdict is attached only to the chain the judged request served. Judge verdicts without
  `revision` are used only in diagnostic scoring.
* **`completion_claim.t`** is the presentation time of the chunk in which the claim line
  is heard (not the request start), with `step` when the claim is about one step. Claims
  are emitted for chains that are later withdrawn too. Logged claims (no `source`, i.e.
  `system`) are **diagnostic only**: primary FCR uses the claims found in the recorded
  audio by the adjudicated claim sweep.
* **`repair_assignment`**: one per randomised eligible failure point, with `t` (assignment
  time), `arm_drawn: true` in `A2-rq2`, and `step` if any; `target_request` may be null.
* **RQ2 eligibility (preregistered).** An eligible failure point is an online `judge`
  verdict `not_complied` on a chain open at its evidence time (`t_evidence`, not the judged
  chunk's start) (opened, not withdrawn, and
  the verdict's `revision` equal to the one then in force), whose `earliest_correctable`
  request j exists and started presenting before `observation_end`. So judge
  `not_complied` verdicts must carry `request` and `earliest_correctable` (null if none).
  In `A2-rq2` sessions eligible points and assignments must match **one-to-one** on
  (chain, revision, step, `failure_request`, `target_request` = `earliest_correctable`).
  An eligible point without an assignment, an assignment matching no eligible point, a
  duplicate assignment, a missing `revision`, or `arm_drawn` not true is an audit failure;
  such a session is excluded from RQ2 and listed. The arm comparison uses only matched,
  randomised points.
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

* **Delivery (`prepare`).** The blinded page (shuffled items, random ids) and the media go in
  the batch directory; the key (`item → log, chain, condition`) goes to
  `<batch>.key/key.json` or `--key`, **never inside the batch**. Media are independent
  files under random names: a stream copy with container metadata and chapters stripped
  by ffmpeg, never a symlink. For a primary batch stripping must succeed; `prepare
  --allow-unstripped` makes a **DIAGNOSTIC** batch (hard link or copy, `media_warnings`
  and `diagnostic_batch` in the key) whose merged events all carry `diagnostic_batch:
  true` and are dropped by primary scoring. `check_blinded` then refuses the batch if any
  of these contains a session id, task id, log name or source path:
  * any delivered file name or file byte;
  * any container, stream or chapter tag read with ffprobe, which is also checked for
    condition names;
  * text files and file names, which are also checked for condition names.
* **Request items**: one per effective chain (final intent; per step for multistep).
  Each shows the preregistered criteria frozen from the task suite
  (`eval/tasks/e2_committed.jsonl`: action `checks`, content `rubric` and duration, each
  multistep step's `intent` and `checks`) and the **absolute deadlines** in video time from
  the end of the final request: action/step 1 by origin + 15 s; content onset by origin +
  15 s and complete answer by origin + 15 s + duration (the D table); later multistep steps
  within 15 s of the previous. An item without criteria is an error. **Every** request
  item also asks for the response onset: on-topic speech for content, the first meaningful
  spoken response otherwise (a time, or "none by the onset deadline"). Merge writes it as
  an adjudicated `speech_onset` and marks the verdict `onset_reviewed`.
* **Repair-target items (RQ2)**: one per randomised (`arm_drawn`) repair assignment whose
  target request j was presented. The window is request j's presented video, and the rater
  sees the request **as of the assignment-time revision**: the user's lines up to that
  revision and its criteria, or its step's criteria. "Done" needs a first-compliant frame
  inside the window, and negative labels need the whole window watched. Merge writes an
  adjudicated `verdict` with `repair_request` = j and `revision`. These verdicts are never
  used as chain compliance.
* **Claim sweep items**: one per session. The rater watches the **whole** recording
  without seeing the logged claims, marks every audible completion claim, chooses its
  referent request (and step), and judges it against the request as it stood at that
  moment, citing an evidence frame after that request and **at or before** the claim
  ("done" requires one). The sweep must be marked complete.
* **Validation (`merge`)**: labels must lie inside the recording and after the request;
  "done" needs its time; content needs one onset decision and onset ≤ answer end; claim
  evidence must not follow the claim. Any error rejects the whole file (`LabelError`).
* **Review coverage**: the page records the intervals each rater actually played
  (`v_watched`: continuous playback at ≤ 2× speed; seeking or skipping adds nothing). The
  union of a rater's intervals in the item (gaps ≤ 0.5 s bridged) must cover **from the
  request through the applicable deadline**, clipped to the recording end, for these
  labels to count:
  * "not done" or "cannot tell": action origin + 15 s; content origin + 15 s + duration;
    multistep step *i* the rater's step *i−1* time + 15 s;
  * "none by the onset deadline": origin + 15 s;
  * a multistep step marked done only **before** its predecessor (nonqualifying
    evidence): its own window, step *i−1* time + 15 s.

  **Positive marks** need continuous coverage from the request to the mark: the first
  compliant frame, the response onset, and the answer end of a content "done". A
  repair-target "done" needs coverage from the window start to its first compliant frame.
  A sweep must cover the whole recording. If either primary review is too short, the item
  stays **unresolved and must be relabelled**; the arbiter never replaces an insufficient
  primary review.
* **Reconciliation**: two independent label files plus an optional **arbiter**. Every label
  is kept as a `rating` event. One reconciled `verdict` per item/step is written only when
  both raters reviewed enough and agree (same label; times within `--tol`, default 1 s; the
  later time is used), or when both reviewed enough but disagree and the arbiter (with a
  sufficient review) breaks the tie. Every accepted item therefore rests on two sufficient
  independent reviews. Sweep
  claims are reconciled **strictly one-to-one across all three raters**. The referent is the
  chain, step and intent revision in force at the claim. Rater A–B pairs with the same
  referent within `--tol` are matched first, and agreed pairs are accepted. Arbiter marks
  are then reserved for agreed pairs and assigned to at most one dispute each: a label
  disagreement, or a claim heard by one rater only. Each audible claim is therefore
  accepted at most once. A one-rater claim the arbiter did not hear is dropped; a claim
  both raters heard but the arbiter did not rate stays unresolved. A resolved sweep writes adjudicated `completion_claim` +
  claim-level `verdict` (`chain_id` + `claim_t`) events and a `claim_sweep` marker.
  Unresolved and missing items are listed in `unresolved.json` next to the key.
* **One batch per item**: each session's chain, RQ2 repair target and claim sweep is
  finalized by exactly one batch. Merging a batch whose items another batch already
  finalized raises `MergeConflictError`. `--replace` atomically removes the earlier batch's
  events for those items (ratings, verdicts, onsets, claims) and writes the new ones.
  Scoring lists any item that still has adjudicated verdicts from two batches as an
  adjudication gap.
* **Immutability**: the inputs of a merged batch are fingerprinted (`merge_state.json` next
  to the key). Re-running with identical inputs is a no-op, and adding an arbiter to a
  batch merged without one is allowed. Any other change raises `MergeConflictError` unless
  `--replace`, which atomically rewrites every log without that batch's events (all events
  carry `batch`) plus the new ones.

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
  bound to its final intent. **Every** effective chain also needs a response-onset decision,
  (`onset_reviewed` or an adjudicated `speech_onset`). This includes capacity-skipped,
  refused and degraded chains, which keep their failure outcome and use the decision for
  TFMR (a missing one is a gap). Multistep needs a verdict for every step up to the first
  one not done. Otherwise the outcome is `unadjudicated`, and the primary report refuses
  to run and lists the gaps. Every session also needs an adjudicated `claim_sweep`, and
  every adjudicated claim needs its claim-level verdict.
* **Deadlines D:**
  * action: first judged-compliant frame ≤ 15 s;
  * content: adjudicated on-topic `speech_onset` ≤ 15 s **and** a `complied` rubric
    verdict with `t_evidence` ≤ 15 s + preregistered duration (qa 10, explain 30, sing 30,
    or `prereg_duration_s`);
  * multistep: step *i* complied ≤ 15 s after step *i−1*'s compliance (step 0: after the
    origin), with every step in order. A step seen only before its predecessor is
    nonqualifying evidence. The result is `order_fail` only once that step's own window
    (step *i−1* time + 15 s) was observed without a qualifying occurrence; otherwise it is
    `insufficient_observation`.
* **Observation:** a chain that did not succeed, whose failure rests on the *absence* of
  compliance up to a time later than `observation_end`, is `insufficient_observation`.
  **Preregistered missing-data rule** (`report --missing-rule`): `rerun-required`
  (default) refuses the primary report, listing those chains, until they are rerun;
  `worst-case` counts them as failures in a report labelled SENSITIVITY ANALYSIS.
* **Outcomes:** `success`, `late`, `never` (censored at D), `unknown` (a "cannot tell"
  verdict inside the window decided the failure: counted as a failure in the primary
  analysis and excluded in the sensitivity analysis), `onset_fail`, `rubric_fail`,
  `order_fail` (a step done only before its predecessor and not within its own observed window),
  `refused`, `degraded`, `capacity_skipped`, `withdrawn`, `unadjudicated`,
  `insufficient_observation`.
* **Time to success:** success time for a success, otherwise the chain's full deadline D.
  Nothing is censored before D. The report shows success by the common deadline per kind
  (and content type / D) with its product-limit curve's median. With no censoring before
  D this equals the cumulative incidence of success, and refusal, skip, rubric, onset and
  order failures are competing outcomes that stay in the denominator. No all-kind pooled
  curve is reported, because the deadlines differ.
* **FCR** = false claims / all audible completion claims, **withdrawn chains included**.
  Primary: the claims are the adjudicated sweep's `completion_claim`s, each settled by its
  claim-level verdict (`unknown` = false); a session without an adjudicated `claim_sweep`,
  or a claim without its verdict, is an adjudication gap. Diagnostic (logged claims): a
  claim is judged against the intent revision in force when it was heard, and it is true
  only if a `complied` verdict bound to that revision, for the claimed `step` (or every
  step when none is named), has its compliance time in [origin of that revision, `t` +
  `claim_grace_s` (default 0)]. **Claim coverage**
  is the share of primary chains with at least one claim; coverage among successful chains
  is also reported. Both get task-clustered bootstrap CIs.
* **Repair (RQ2):** the unit is **every** randomised failure point (one
  `repair_assignment` each), analysed by assigned arm, including those on chains later
  withdrawn or excluded from the chain analysis. Only `arm_drawn` points in sessions
  passing the RQ2 audit enter the comparison. Status is decided in this order:
  `not_randomized` (no `arm_drawn`: descriptive only); `ineligible` (the chain was not
  open at assignment time `t`: excluded);
  `withdrawn` (any withdrawal, from the chain's withdrawal history, at or after the
  assignment and before the target request finished presenting, even if a later revision
  reopened the chain: a failure in the primary row, excluded in a sensitivity row,
  **whatever the target request showed**); `insufficient_observation` (checked before
  success; see below); `success` (the adjudicated repair-target verdict
  for (chain, j, assignment-time revision, step) is `complied`, so a later revision of the
  chain cannot undo a repair; diagnostic mode without one falls back to a complied verdict
  bound to that revision whose request is j); `insufficient_observation` (not **every** chunk,
  per `chunks_per_request`, of the target request was presented before `observation_end`,
  or that count is unknown: excluded, flagged for rerun);
  `unadjudicated` (primary: no repair-target verdict; blocks the primary report); otherwise
  `failure`. The offset j−k is reported. **The primary RQ2 row requires every matched point's
  target to be fully observed.** Otherwise it is REFUSED and the targets to rerun are
  listed, and the rows that exclude unobserved targets are shown as labelled missing-data
  sensitivity analyses.
* **TVC** (action chains): first compliant frame − origin, censored at 15 s.
  **TFMR** (every chain kind): first accepted `speech_onset` − origin, censored at 15 s.
  Primary uses the adjudicated meaningful-response onset.
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
  * **Registered pair set:** `--suite` + `--expected-seeds` (+ optional
    `--expected-tasks`) define it: every (task, seed, chain label) whose final intent in
    the suite is not withdrawn. Both conditions must contain exactly that set. The report
    exits 2 and lists the keys when:
    * no set is registered;
    * a key is missing from either condition, even from both;
    * a key lies outside the set.

    Duplicate keys are always an error.
  * **Registered script:** every session's logged user side must equal the registered task:
    utterance texts, annotation actions and labels, and the intent fields `kind`,
    `intent`, `content_type`, `prereg_duration_s` and `steps`. Every scored chain's
    adjudicated verdicts must carry the hash of the registered final criteria
    (`criteria_sha256`, see `adjudicate.final_criteria_sha`). A mismatch, or no registered
    suite (`build_report(tasks=...)`; the CLI always loads `--suite`), is a pair problem.
  * `--allow-incomplete-pairs` shows a comparison with any of these pair problems as
    EXPLORATORY, with no p-value and no decision.
  * **Minimum clusters:** below `MIN_TASKS` = 10 independent task clusters (*proposed
    target*), the p-value and decision are suppressed ("no inference").
  * Suppressed family members count as p = 1 in Holm.

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
{"type":"verdict","chain_id":"s1:c1","source":"adjudicated","label":"complied","revision":0,"t_first_compliant":10.1,"t_evidence":10.1,"annotators":["R1","R2"],"reconciliation":"agreement","t_review_start":3.1,"t_review_end":20.0,"onset_reviewed":true,"t_onset":4.2}
{"type":"speech_onset","source":"adjudicated","on_topic":true,"t":4.2,"chain_id":"s1:c1"}
{"type":"claim_sweep","source":"adjudicated","n_claims":1,"annotators":["R1","R2"],"reconciliation":"agreement"}
{"type":"completion_claim","source":"adjudicated","chain_id":"s1:c1","t":12.1}
{"type":"verdict","source":"adjudicated","chain_id":"s1:c1","claim_t":12.1,"label":"complied","revision":0,"t_evidence":10.1}
```
