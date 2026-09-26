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
| `rating` | `annotator`, `chain_id`, `label` | `role` (`primary`/`arbiter`), `kind` (`claim_sweep` for a swept claim), `step`, `revision`, `claim_t`, the same time fields as a verdict, `onset_none`, `review_ok`, `t_review_needed`, `batch`, `item` | adjudication tool (one annotator's independent label; kept for agreement statistics, **never scored**) |
| `completion_claim` | `chain_id`, `t` | `source` (`system` (default) / `adjudicated`), `step`, `claim_id`, `request`, `text`, `batch`, `item` | orchestrator (`system`, diagnostic) / audio claim sweep (`adjudicated`, primary) |
| `claim_sweep` | `source` (`adjudicated`) | `n_claims`, `annotators`, `reconciliation`, `t_review_end`, `batch`, `item` | adjudication tool: the session's recording was swept for audible completion claims (required per session in primary scoring) |
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
  are emitted for chains that are later withdrawn too. Logged claims (no `source`, i.e.
  `system`) are **diagnostic only**: primary FCR uses the claims found in the recorded
  audio by the adjudicated claim sweep.
* **`repair_assignment`**: one per randomised eligible failure point, with `step` if any;
  `target_request` may be null.
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
  by ffmpeg, else a hard link or plain copy with a warning (`media_warnings` in the key);
  never a symlink. `check_blinded` then scans every delivered file name and byte for
  session ids, task ids, log names and source paths, and text files and names for
  condition names, and refuses the batch on any hit.
* **Request items**: one per effective chain (final intent; per step for multistep).
  Each shows the preregistered criteria frozen from the task suite
  (`eval/tasks/e2_committed.jsonl`: action `checks`, content `rubric` and duration, each
  multistep step's `intent` and `checks`) and the **absolute deadlines** in video time from
  the end of the final request: action/step 1 by origin + 15 s; content onset by origin +
  15 s and complete answer by origin + 15 s + duration (the D table); later multistep steps
  within 15 s of the previous. An item without criteria is an error. Content items also
  ask for the on-topic speech onset (a time, or "no on-topic speech").
* **Claim sweep items**: one per session. The rater watches the **whole** recording
  without seeing the logged claims, marks every audible completion claim, chooses its
  referent request (and step), and judges it against the request as it stood at that
  moment, citing an evidence frame after that request and **at or before** the claim
  ("done" requires one). The sweep must be marked complete.
* **Validation (`merge`)**: labels must lie inside the recording and after the request;
  "done" needs its time; content needs one onset decision and onset ≤ answer end; claim
  evidence must not follow the claim. Any error rejects the whole file (`LabelError`).
* **Review coverage**: each label records the reviewed interval (to the furthest point the
  rater played in that item). "Not done", "cannot tell" and "no on-topic speech" count only
  if it reaches the applicable deadline (action origin + 15 s; content origin + 15 s +
  duration, or origin + 15 s for the onset; multistep step *i* the rater's step *i−1*
  time + 15 s), clipped to the recording end. A sweep must reach the recording end.
  Shorter reviews are **escalated** to the arbiter, not accepted.
* **Reconciliation**: two independent label files plus an optional **arbiter**. Every label
  is kept as a `rating` event. One reconciled `verdict` per item/step is written only when
  both raters reviewed enough and agree (same label; times within `--tol`, default 1 s; the
  later time is used), or else the arbiter (with sufficient review) labelled it. Sweep
  claims are matched one-to-one by referent and time; agreed pairs are accepted, and label
  disagreements and one-rater claims go to the arbiter (an arbiter who did not hear a
  one-rater claim drops it). A resolved sweep writes adjudicated `completion_claim` +
  claim-level `verdict` (`chain_id` + `claim_t`) events and a `claim_sweep` marker.
  Unresolved and missing items are listed in `unresolved.json` next to the key.
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
  bound to its final intent. Content also needs an onset decision (`onset_reviewed` or an
  adjudicated `speech_onset`). Multistep needs a verdict for every step up to the first
  one not done. Otherwise the outcome is `unadjudicated`, and the primary report refuses
  to run and lists the gaps. Every session also needs an adjudicated `claim_sweep`, and
  every adjudicated claim needs its claim-level verdict.
* **Deadlines D:**
  * action: first judged-compliant frame ≤ 15 s;
  * content: adjudicated on-topic `speech_onset` ≤ 15 s **and** a `complied` rubric
    verdict with `t_evidence` ≤ 15 s + preregistered duration (qa 10, explain 30, sing 30,
    or `prereg_duration_s`);
  * multistep: step *i* complied ≤ 15 s after step *i−1*'s compliance (step 0: after the
    origin), with every step in order.
* **Observation:** a chain that did not succeed, whose failure rests on the *absence* of
  compliance up to a time later than `observation_end`, is `insufficient_observation`.
  **Preregistered missing-data rule** (`report --missing-rule`): `rerun-required`
  (default) refuses the primary report, listing those chains, until they are rerun;
  `worst-case` counts them as failures in a report labelled SENSITIVITY ANALYSIS.
* **Outcomes:** `success`, `late`, `never` (censored at D), `unknown` (a "cannot tell"
  verdict inside the window decided the failure: counted as a failure in the primary
  analysis and excluded in the sensitivity analysis), `onset_fail`, `rubric_fail`,
  `order_fail` (a step done only before its predecessor: a deterministic failure),
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
  withdrawn or excluded from the chain analysis. Status: `success` (a `complied` verdict
  whose request, explicit or the presented chunk containing its compliance time, is
  `target_request`); `withdrawn` (the chain was withdrawn after assignment: a failure in
  the primary row, excluded in a sensitivity row); `insufficient_observation` (the target
  request was not fully presented before `observation_end`: excluded, flagged for rerun);
  `unadjudicated` (blocks the primary report); otherwise `failure`. The offset j−k is
  reported.
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
{"type":"claim_sweep","source":"adjudicated","n_claims":1,"annotators":["R1","R2"],"reconciliation":"agreement"}
{"type":"completion_claim","source":"adjudicated","chain_id":"s1:c1","t":12.1}
{"type":"verdict","source":"adjudicated","chain_id":"s1:c1","claim_t":12.1,"label":"complied","revision":0,"t_evidence":10.1}
```
