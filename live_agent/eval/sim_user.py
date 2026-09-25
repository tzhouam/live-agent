"""Simulated user: replays a task's scripted utterances against any agent transport and
emits ``utterance`` + ``chain_annotation`` events in the SCHEMA.md format.

Transport-agnostic: the caller supplies

* ``send_utterance(text, meta) -> Awaitable[dict | None]`` - deliver the utterance (TTS into
  the live session, a websocket message, a direct call...). It may return
  ``{"t_start": ..., "t_end": ...}`` measured on the shared timeline (e.g. from VAD);
  otherwise the clock before/after the await is used.
* ``clock() -> float`` - the shared presentation-timeline clock.
* ``sleep(seconds) -> Awaitable`` - defaults to ``asyncio.sleep``; tests use VirtualClock.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from live_agent.eval.tasks import Task

SendFn = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any] | None]]


class VirtualClock:
    """Deterministic clock for tests and offline replay."""

    def __init__(self, t0: float = 0.0):
        self.t = t0

    def now(self) -> float:
        return self.t

    async def sleep(self, dt: float) -> None:
        self.t += max(0.0, dt)
        await asyncio.sleep(0)

    def advance(self, dt: float) -> None:
        self.t += dt


class SimulatedUser:
    def __init__(
        self,
        task: Task,
        send_utterance: SendFn,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        session_id: str = "",
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.task = task
        self.send = send_utterance
        self.clock = clock
        self.sleep = sleep
        self.session_id = session_id or task.task_id
        self.on_event = on_event
        self.events: list[dict[str, Any]] = []

    def chain_id(self, label: str) -> str:
        return f"{self.session_id}:{label}"

    def _emit(self, ev: dict[str, Any]) -> None:
        self.events.append(ev)
        if self.on_event is not None:
            self.on_event(ev)

    async def run(self) -> list[dict[str, Any]]:
        t0 = self.clock()
        for i, u in enumerate(self.task.utterances):
            wait = t0 + u.offset_s - self.clock()
            if wait > 0:
                await self.sleep(wait)
            uid = f"{self.session_id}:u{i}"
            meta = {"uid": uid, "barge_in": u.barge_in, "task_id": self.task.task_id}
            t_start = self.clock()
            r = await self.send(u.text, meta) or {}
            t_end = float(r.get("t_end", self.clock()))
            t_start = float(r.get("t_start", t_start))
            self._emit(
                {
                    "type": "utterance",
                    "uid": uid,
                    "speaker": "user",
                    "text": u.text,
                    "t_start": t_start,
                    "t_end": t_end,
                    "barge_in": u.barge_in,
                }
            )
            if u.annotation == "none":
                continue
            ann: dict[str, Any] = {
                "type": "chain_annotation",
                "uid": uid,
                "action": u.annotation,
                "chain_id": self.chain_id(u.chain),
                "label": u.chain,
            }
            if u.intent:
                it = u.intent
                ann["kind"] = it["kind"]
                ann["intent"] = it.get("intent", "")
                for k in ("content_type", "prereg_duration_s"):
                    if k in it:
                        ann[k] = it[k]
                if "steps" in it:
                    ann["steps"] = [s.get("intent", "") for s in it["steps"]]
            self._emit(ann)
        if self.task.duration_s is not None:
            rest = t0 + self.task.duration_s - self.clock()
            if rest > 0:
                await self.sleep(rest)
        return self.events
