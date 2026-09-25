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
