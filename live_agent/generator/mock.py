"""CPU-only mock generator with TaoMate-H3-shaped timing (for tests and simulation).

Timings are parameters, not measurements. Frames are tiny solid-colour arrays whose
colour encodes the request index; audio is silence. ``chunk.meta['prompt']`` carries
the locked prompt so a mock judge can decide compliance.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator

import numpy as np

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.types import Chunk, now

# TaoMate-H3 chunk layout (frames): first request 39/34/34/17, later requests 119 split 34/34/34/17.
FIRST_LAYOUT = (39, 34, 34, 17)
LATER_LAYOUT = (34, 34, 34, 17)


class MockGenerator(Generator):
    def __init__(self, *, teacher_s: float = 1.0, chunk_s: float = 0.6, jitter: float = 0.0,
                 fps: float = 24.0, size: tuple[int, int] = (48, 86), speed: float = 1.0, seed: int = 0):
        self.info = GeneratorInfo(name="mock", fps=fps, width=size[1], height=size[0])
        self.teacher_s = teacher_s
        self.chunk_s = chunk_s
        self.jitter = jitter
        self.speed = speed  # divide all sleeps (tests use large speed-ups)
        self._rng = random.Random(seed)
        self._queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
        self._out: asyncio.Queue[Chunk | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._next = 0
        self._session = 0
        self._first_in_session = True
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _sleep(self, s: float) -> None:
        s = max(0.0, s + (self._rng.uniform(-self.jitter, self.jitter) if self.jitter else 0.0))
        await asyncio.sleep(s / self.speed)

    async def _run(self) -> None:
        while True:
            k, prompt = await self._queue.get()
            session = self._session
            tm = self._timings[k]
            tm.t_teacher_start = now()
            await self._sleep(self.teacher_s)
            tm.t_teacher_done = now()
            tm.t_student_start = now()
            layout = FIRST_LAYOUT if self._first_in_session else LATER_LAYOUT
            self._first_in_session = False
            for ci, n in enumerate(layout):
                await self._sleep(self.chunk_s * n / 34)
                if session != self._session:  # reset happened mid-request
                    break
                shade = (k * 37) % 255
                video = np.full((1, self.info.height, self.info.width, 3), shade, dtype=np.uint8)
                audio = np.zeros((int(n / self.info.fps * self.info.sample_rate), 2), dtype=np.float32)
                if "<d>" in prompt and ci == 0:  # a scripted line: audible "speech" from 0.2 s
                    t = np.arange(len(audio)) / self.info.sample_rate
                    audio[:, :] = (0.1 * np.sin(2 * np.pi * 220 * t) * (t >= 0.2))[:, None]
                ch = Chunk(k, ci, n, self.info.fps, video=video, audio=audio,
                           sample_rate=self.info.sample_rate, t_ready=now(),
                           meta={"prompt": prompt, "session": session})
                if ci == 0:
                    tm.t_first_chunk = ch.t_ready
                await self._out.put(ch)
            tm.t_done = now()

    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        self._next += 1
        self._timings[request_index] = RequestTiming(request_index, t_lock=now())
        await self._queue.put((request_index, prompt))

    async def chunks(self) -> AsyncIterator[Chunk]:
        while True:
            ch = await self._out.get()
            if ch is None:
                return
            yield ch

    async def reset(self) -> None:
        self._session += 1
        self._first_in_session = True
        while not self._queue.empty():
            self._queue.get_nowait()

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self._out.put(None)

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
