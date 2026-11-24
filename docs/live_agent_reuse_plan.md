# Reuse as a realtime (non-teaching) live agent — co-design plan

Status: **implemented (option B) on 2026-10-13** — see decision D-068 in `docs/decision_log.md` for
what shipped and the recorded evidence. Originally a proposal (2026-10-13) awaiting owner approval;
the owner approved it by requesting implementation, adding one directive adopted as part of D-068:
the live agent's speech path is audio-first (generate the TTS audio, let the video follow it —
already how the CPU puppet and browser-mesh paths work by construction). Produced
with the imdesign co-design workflow.

**Assumption** (correct on approval): "realtime live agent" means the repo's original
purpose — a live conversational persona for 1:1 interaction (like the existing `hanfu`
reading host), not the teaching classroom that most recent work (D-032…D-067) was built
around. If "live agent" instead means **livestreaming to multiple viewers**, that is a
different scope with hard gates — see §8.

## 1. Problem statement

The repo already *is* a realtime live agent at its core; the classroom is a scenario
wired on top. Reusing it means: run a non-teaching persona end-to-end, make sure
teaching affordances don't leak into that experience, and decide how far to decouple
rather than rewrite.

## 2. Existing behavior — what is already reusable as-is

The domain-generic core (≈80% of the ~11.4k test lines cover it):

| Subsystem | Where | Reuse status |
|---|---|---|
| Realtime loop: 5 s requests, JIT prompt locking, chunk streaming, soft-switch barge-in, VLM QC + repair, erasure | `live_agent/orchestrator.py`, `timeline.py`, `director/director.py` | Generic |
| Generator abstraction (mock / CPU VTuber puppet / browser mesh / TaoMate-H3 / vLLM-Omni) + capability manifest | `live_agent/generator/`, `capability.py`, `backend/runtime.py:16-33` | Generic |
| Scoped memory (private/public/canon) with deletion cascade | `live_agent/memory/`, `memory_bridge.py` | Generic |
| WS transport (H.264/PCM chunks), recording, Node frontend + FastAPI backend split | `backend/transport.py`, `backend/app.py`, `frontend/` | Generic |
| A working non-teaching persona | `configs/persona_hanfu/` (no `board`, no teaching style) | **Already runs**: `PERSONA=hanfu scripts/run_live.sh demo` |

Teaching-specific and separable in principle: `curriculum.py`, `lesson.py`,
`exercise.py`, `teaching_quality.py`, `board_*.py`, `attention.py`, `student.py`, plus
the student frontend editions.

## 3. Where teaching is actually entangled (the real work)

Teaching is persona-flagged (`canon.json` `board: true`) but the branches live in
runtime code, in five places:

1. `types.py` — `Segment`/`BlockScript` carry `board`, `lesson`, `exercise`, `gesture`,
   `progress` fields.
2. `director/director.py` (~40% of it) — lesson backlog/resume, exercise
   waiting/timeout, `student_context` in every responder prompt, teaching review inside
   `decide` (`director.py:295-421, 840-939`).
3. `orchestrator.py` (~800 lines) — teaching dispatch inside `_on_user_utterance`,
   `_lesson_loop`/`_review_outline`/`_revise_section`, attention nudging,
   `_erase_learning` (`orchestrator.py:1199-1237, 1424-1584`).
4. `backend/app.py` — `/api/curriculum` routes, board/image/profile/attention wiring
   gated on `canon.board` (`app.py:242-272`), `lesson_context` on text input.
5. Frontend — lesson/board/exercise UI and the three student editions.

## 4. Options

| | A. Config-only reuse | **B. Persona-gated live mode (recommended)** | C. Extract teaching behind ports |
|---|---|---|---|
| What | Run `PERSONA=hanfu` (or a new persona) on existing modes; touch nothing | Extend the existing canon-flag pattern: lazy teaching wiring in the backend + a "live" frontend edition that hides lesson/practice/catalogue | Move teaching into a feature package with a narrow interface; scrub `types.py`/director/orchestrator |
| Effort | ~0 | Small: ~3 focused changes, each testable | Large: director (~40%), orchestrator (~800 lines), app.py, data model |
| Risk | Teaching UI/endpoints still visible/callable in the live experience | Low — teacher persona behavior must stay byte-identical (existing tests enforce this) | High regression risk on a heavily-tested working system |
| When it's right | Spike / quick demo | The default answer for one or two live personas | Only if teaching is retired or several new scenarios ship |

**Recommendation: B, preceded by an A spike.** The repo's own idiom is per-persona
config flags (D-032 introduced exactly this instead of a teaching director fork); a big
extraction contradicts that pattern until a second non-teaching scenario proves the
need.

## 5. Proposed design (Option B)

- **Backend**: in `backend/app.py`/`runtime.py`, load curriculum, board image makers,
  `ProfileStore`, and the attention monitor only when the persona's flag is set
  (`canon.board` today; a clearer `persona.features` list if preferred). Zero behavior
  change for the teacher persona.
- **Frontend**: a live edition (`?edition=live` or persona-driven): stage + chat/voice +
  traces + memory panel stay; catalogue, lesson request, practice, learner-profile page
  hidden. All of these are already edition-configured, so this follows the existing
  mechanism.
- **Launcher**: document (or alias) `PERSONA=<live-persona> scripts/run_live.sh
  puppet-full` as the supported live-agent mode; it needs no GPUs.
- **Governance**: record as a decision-log entry on adoption — it repositions the demo
  scenario without touching the TaoMate-H3 backbone decision (D-017).

## 6. Implementation plan (each step independently shippable)

1. **Spike (no code)**: run the `hanfu` persona in `puppet-full` and, if GPUs allow,
   `omni`; list every teaching leak (UI elements, API calls, prompts). This validates
   the assumption before any change.
2. **Backend gating** + tests: teaching resources conditional; teacher-path tests
   unchanged and green.
3. **Frontend live edition** + tests; adapt `scripts/student_frontend_check.py` into a
   live-persona check asserting no teaching endpoints are called.
4. **Launcher/docs/decision log** update.

## 7. Validation plan

- `python3 -m pytest` and `npm --prefix frontend test` fully green with no
  teacher-behavior edits (that's the regression gate for B).
- New live-persona browser check: conversation, interruption, memory write/erase, no
  lesson/board/exercise UI or API traffic.
- For the GPU realtime path, reuse `scripts/server_check.sh` and the lipsync page check.

## 8. Risks, tradeoffs, open questions

- **If "live agent" = public livestream**: currently blocked by phase rules
  (`docs/PROJECT.md`: no public broadcasts; D-001 makes a *private scripted-viewer test
  stream* the second scenario). Technical gaps on top: one active session enforced
  (`app.py:70-77`), no multi-viewer fan-out, `public:<stream>` memory scope untested at
  scale. That path needs an explicit owner decision + its own design packet.
- **Option C deferred**: carrying dormant teaching code costs keeping ~2.6k test lines
  green; acceptable now, revisit after a second non-teaching persona ships.
- **Calibration debt travels with the reuse**: capabilities remain uncalibrated
  (`ALLOW_UNCALIBRATED=1`, E1 pending) — reusing the runtime inherits that, unchanged.
- **Language**: `hanfu` is Mandarin; if the new agent should teach/speak English, that
  capability is explicitly unestablished in the docs.

**Bottom line:** nothing architectural. Verify the existing non-teaching persona path
(step 1), then gate teaching wiring and add a live frontend edition so the reuse is a
supported mode rather than an easter egg.
