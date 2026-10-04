Read-only re-review of the inlined source; I did not run the reported tests.

1. **Major — Successful practice still stays “waiting.”** In [product.js](/data/zhoutaichang/live-agent/frontend/public/assets/product.js), a matching `utterance_end` with `kind: "exercise"` leaves `practiceWaiting` in place. `exercise_open`, grading, and closure update the question and feedback but never `lessonStatus`. Check a successful practice request through question closure; the status still says it is waiting for a question.

2. **Major — A custom lesson can wait indefinitely without starting.** A typed goal has no `lesson_context`. The [orchestrator](/data/zhoutaichang/live-agent/live_agent/orchestrator.py:1454) starts a lesson only when the decision also supplies a nonempty `topic`, while `product.js` treats `kind: "lesson"` alone as a started request. A lesson decision with an empty topic produces no lesson start or failure event and leaves the status waiting. Force that decision for a typed goal to settle the path.

3. **Minor — An outcome can be assigned to the wrong request.** `onLessonEvent()` checks every `utterance_end` against one global `lessonMessage`. Send chat A, then request practice B before A’s decision returns: A’s `kind: "chat"` marks B as “did not start,” and B’s later matching decision does not clear that status.

4. **Minor — Switching editions misstates an error state.** After a connection error, `setEdition()` replaces the error overlay with a generic ready prompt. [live.js](/data/zhoutaichang/live-agent/frontend/public/assets/live.js) refreshes the badge but does not restore the overlay; `connectionErrorText` remains in the previous language. Check a Chinese-edition WebSocket error, then switch to university.

I found no remaining concrete defect in the supplied profile navigation, learner clearing, stale exercise suppression, active-choice translation, or recording ACK wording repairs.