# E1 pilot: capability execution on TaoMate-H3 (2026-09-26)

Status: **judge-only pilot, not a calibration.** All numbers are *measured locally*. The labels come from a
VLM judge (Qwen3-VL-8B), and this pilot shows that judge to be unreliable in both directions. Human
validation (`scripts/e1_validate.py`) is required before any capability is `calibrated` and usable in E2
(`--allow-uncalibrated` is only for qualification runs).

## Setup

- `scripts/e1_calibrate.py --generator taomate_h3 --trials 5 --save-clips` on GPUs 0-5: student 4 GPUs, teacher 2,
  480x864.
- Per trial: reset, then idle request → action request → idle request.
- The judge answers the capability's check question on the action request. v1 = the pilot judge: K=4 frames,
  state-phrased question.
- 24 capabilities × 5 trials = 120 trials. Mean wall time per trial 12.3 s. Clips are in `.cache/e1/clips/`.
- Afterwards, all 120 clips were re-judged offline (`scripts/e1_rejudge.py`) with v1 and with v2 (contrast mode:
  K=8 frames including the first and last, "did the action happen in this clip").
- Offline v1 reproduced the online labels on all 120 clips.

## Judge-labelled success (k/5)

| Capability | v1 | v2 | Capability | v1 | v2 |
|---|---|---|---|---|---|
| drink_tea | 3 | 3 | think | 0 | 0 |
| turn_page | 5 | 5 | listen | 3 | 3 |
| wave | 5 | 5 | idle_read | 5 | 5 |
| nod | 0 | 0 | frown | 0 | 2 |
| shake_head | 0 | 0 | sit_down | 5 | **0** |
| smile | 5 | 5 | wave_left | 5 | 5 |
| put_down_book | 4 | 4 | write_brush | 5 | 5 |
| pick_up_book | 5 | 5 | show_writing | 5 | 5 |
| look_window | 5 | 5 | pick_up_fan | 3 | 3 |
| pour_tea | 0 | 0 | fan_self | 1 | 1 |
| eat_pastry | 5 | 5 | put_down_fan | 0 | 0 |
| stand_up | 0 | 0 | bow | 1 | 3 |

With n=5 per capability, a Wilson 95% CI for 5/5 is [0.57, 1.00] and for 0/5 is [0.00, 0.43].

## Judge failures found by inspection (spot check by Claude, not human labels)

- **False positive (state question):** `sit_down`, trial 0. The persona stays seated reading throughout, yet v1
  said "done". "Is she seated?" is already true without any action. v2 labels all five `sit_down` clips "not
  done". `idle_read`, `smile` and `listen` have the same risk.
- **False negative (late action):** `stand_up`, trial 0. The persona stands up at the end of the action request;
  the last frame shows her standing. v1 said "not done", and v2 still says "sat throughout" (confidence 1.0)
  although its last sampled frame shows her standing.
- **Consequence:** judge-only rates are not capability estimates, and the online QC loop inherits these errors.
  Low judge rates (nod, shake_head, stand_up, pour_tea, think, frown, put_down_fan) may be judge misses rather
  than generator failures, and high rates of state-like capabilities may be false positives.

## Decisions (D-025)

- Runtime and E1 judges use v2 (contrast, K=8). It removes the observed state false positive and was no worse
  on the other clips (9/120 labels differ; the direction per clip needs human labels).
- The manifest stays below `calibrated`: all 24 capabilities are `executed` (they ran on the real
  generator). `.cache/e1/capabilities.calibrated.json` records the judge-only p, which the gate uses only to
  degrade (p < 0.6).
- **Next step (needs people):** label the 24-clip stratified sample (`.cache/e1_val/index.html`, two raters),
  run `scripts/e1_validate.py agree`, then run full E1 (30 trials per capability) with the validated judge
  configuration. If neither judge reaches acceptable agreement, a stronger judge or human-only E1 labels are
  needed. For head motions (nod, shake_head), a frame-based judge may be the wrong instrument altogether.
