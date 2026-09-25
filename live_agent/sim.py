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

    def __post_init__(self) -> None:
        self._q: asyncio.Queue[tuple[Chunk, BlockScript]] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._last_end: float | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._play())

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        await self._q.put((chunk, script))

    async def stop_playback(self) -> None:
        while not self._q.empty():
            ch, _ = self._q.get_nowait()
            self.dropped.append((ch.request_index, ch.chunk_index))

    async def _play(self) -> None:
        while True:
            ch, _script = await self._q.get()
            t0 = now()
            if self._last_end is not None and t0 - self._last_end > 0.05 / self.speed:
                self.stalls.append(Stall(self._last_end, t0))
            await asyncio.sleep(ch.duration_s / self.speed)
            t1 = now()
            self._last_end = t1
            self.presented.append((ch.request_index, ch.chunk_index, t0, t1))
            if self.orchestrator is not None:
                self.orchestrator.on_presented(ch.request_index, ch.chunk_index, t0, t1)

    def close(self) -> None:
        if self._task:
            self._task.cancel()
