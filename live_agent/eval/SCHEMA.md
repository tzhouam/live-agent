# E2 session-log schema (v1)

The orchestrator, simulated user, online judge and human adjudication tool all append to
one JSONL file per **session** (= one task × one seed × one condition). Scoring
(`live_agent/eval/scoring.py`) implements proposal v2.11 §7.2 (intent chains, deadline
table D, outcome rules) and §8 metrics. Validation lives in `live_agent/eval/schema.py`
(`SessionLogWriter`, `load_session`). Events may appear in any order; the loader sorts
them by time.

**Times:** all `t*` fields are seconds on the **shared presentation timeline** (the clock
the client uses to timestamp presented frames, `live_agent.types.now`). Do not use wall-clock time.

## Header (line 1)

```json
{"type": "session", "schema_version": 1, "session_id": "A2-E2-D04-s3",
 "condition": "A2", "task_id": "E2-D04", "seed": 3,
 "mode": "realtime|near_realtime", "backbone": "taomate-h3"}
```
Required: `session_id`, `condition`, `task_id`, `seed`. Other keys are free-form metadata.

## Events

| type | required fields | optional fields | emitted by |
|---|---|---|---|
| `utterance` | `uid`, `speaker` (`user`/`persona`/`viewer:<id>`), `text`, `t_start`, `t_end` (VAD endpoint) | `barge_in` (bool) | sim user / ASR |
| `chain_annotation` | `uid` (of the utterance), `action` (`new`/`revision`/`withdrawal`), `chain_id` | `label` (task-local chain label for cross-condition pairing, e.g. `c1`), `kind` (`action`/`content`/`multistep`; `correction` is treated as `action`), `intent`, `content_type` (`qa`/`explain`/`sing`), `prereg_duration_s`, `steps` (list or int) | sim user (script) or annotator |
| `lock` | `t`, `request` | `chain_ids`, `plan_version` | orchestrator (diagnostic; not needed for scoring) |
| `chunk_presented` | `request`, `chunk`, `t_start`, `t_end` | `frame_hash` | client presentation ack |
| `verdict` | `source` (`adjudicated`/`human`/`judge`), `label` (`complied`/`not_complied`/`unknown`), and `chain_id` **or** `claim_id` | `step` (multistep, 0-based), `request`, `chunk`, `t_first_compliant`, `t_evidence`, `revision` (number of revisions the judged intent includes), `qid`, `annotator` | judge / human tool |
| `completion_claim` | `chain_id`, `t` | `step`, `claim_id`, `text` | orchestrator (persona says "done") |
| `refusal` | `chain_id`, `t` | `kind` (`refused` (default) / `degraded`), `reason` | compiler / safety filter |
| `capacity_skip` | `chain_id`, `t` | `reason` | admission control |
| `speech_onset` | `t`, `on_topic` (bool) | `chain_id` (**required for the onset to count toward a chain**), `request` | client audio playback + annotation |
| `visual_ack` | `t`, `uid` (the utterance acknowledged) | `kind` (`reaction_clip`/`freeze`) | client |
| `playback_stop` | `t` | `reason` | client |
| `repair_assignment` | `chain_id`, `arm` (`forward_correction`/`repeat`), `failure_request` (k), `target_request` (j = earliest request with P_j ≥ E + C) | `step`, `E`, `C` | orchestrator (RQ2 randomisation) |

## Time fields on verdicts

* `t_first_compliant`: presentation time of the **first frame judged compliant**. It defines
  TVC and the judged-compliance time of a multistep step. If it is missing, the scorer
  uses the `t_start` of `chunk_presented(request, chunk)`, then `t_evidence`.
* `t_evidence`: presentation time of the **last** frame (or audio) needed for the verdict
  (E in §5.4). For content chains this is the **end of the response**, and it is the
  completion time.
* Verdicts whose compliance time is earlier than the chain's current clock origin are
  ignored, because they judged a superseded intent. When `revision` is present it must
  equal the chain's final revision count.
* Per chain, only the highest-preference source present is used: `adjudicated` >
  `human` > `judge`. Override the order with `ScoringConfig.source_preference`, for
  example `("judge",)` to score the online QC.

## Scoring rules (summary; all *proposed targets*, identical across conditions)

* **Chain.** `new` opens a chain. `revision` merges into it: the intent fields are
  replaced and the clock restarts at the revising utterance's `t_end`. `withdrawal`
  withdraws the chain, and a later `revision` reopens it. Each chain is scored once, on
  its final intent.
* **Effective chains** (primary denominator) are all chains that do not end withdrawn.
  Capacity-skipped chains are included.
* **Precedence:** withdrawn → capacity-skipped (fail) → refused/degraded (fail) →
  deadline rules. A skip or refusal only counts if it happened at or after the final clock
  origin.
* **Deadlines D:**
  * action: first judged-compliant frame ≤ 15 s;
  * content: on-topic `speech_onset` ≤ 15 s **and** a `complied` rubric verdict with
    `t_evidence` ≤ 15 s + preregistered duration (qa 10, explain 30, sing 30, or
    `prereg_duration_s`);
  * multistep: step *i* complied ≤ 15 s after step *i−1*'s compliance (step 0: after the
    origin), with every step in order.
* **Outcomes:** `success`, `late`, `never` (censored at D), `unknown` (a "cannot tell"
  verdict inside the window decided the failure: counted as a failure in the primary
  analysis and excluded in the sensitivity analysis), `onset_fail`, `rubric_fail`,
  `order_fail`, `refused`, `degraded`, `capacity_skipped`, `withdrawn`.
* **FCR:** a claim is contradicted unless a `complied` verdict for that chain (and step,
  if the claim names one) has its compliance time in [origin in force at the claim,
  `t` + `claim_grace_s` (default 0)]. A verdict carrying the claim's `claim_id` settles
  the claim directly, and `unknown` counts as contradicted. **Claim coverage** is the
  share of effective chains with at least one claim; coverage among successful chains is
  also reported.
* **Repair (RQ2):** success means a `complied` verdict on `request == target_request`.
  The offset j−k is reported.
* **TVC** (action chains): first compliant frame − origin, censored at 15 s.
  **TFMR**: first on-topic `speech_onset` − origin, censored at 15 s.
  **Visual-ack latency**: `visual_ack.t` minus the utterance's `t_end`, or its `t_start`
  for a barge-in.
  **Barge-in stop latency**: the first `playback_stop` at or after a barge-in
  utterance's `t_start`, minus that `t_start`.
* **Conditional success** = successes / served chains (effective chains that were not
  refused, degraded or skipped).

## Minimal example

```jsonl
{"type":"session","schema_version":1,"session_id":"s1","condition":"A2","task_id":"E2-A01","seed":0}
{"type":"utterance","uid":"s1:u0","speaker":"user","text":"请喝口茶吧。","t_start":2.0,"t_end":3.1}
{"type":"chain_annotation","uid":"s1:u0","action":"new","chain_id":"s1:c1","label":"c1","kind":"action","intent":"端起茶杯喝一口茶"}
{"type":"visual_ack","t":3.5,"uid":"s1:u0"}
{"type":"chunk_presented","request":2,"chunk":0,"t_start":9.6,"t_end":11.0}
{"type":"verdict","chain_id":"s1:c1","source":"adjudicated","label":"complied","request":2,"chunk":0,"t_evidence":11.0}
{"type":"completion_claim","chain_id":"s1:c1","t":12.0}
```
