"""VllmOmniH3Generator against a fake vLLM-Omni realtime server that holds each request boundary until its prompt
update arrives (model_config.taomate_h3_hold_for_prompt) and records the prompt every request ran with."""

import asyncio
import json

import numpy as np

import live_agent.generator.vllm_omni_h3 as mod
from live_agent.generator.vllm_omni_h3 import VllmOmniH3Generator


class StubDecoder:
    def __init__(self, fps=24, sample_rate=32000):
        self.n = 0

    def push(self, data):
        pass

    def take(self, final=False):
        start = self.n
        self.n += 34
        return start, np.zeros((34, 4, 4, 3), np.uint8), np.zeros((45333, 2), np.float32)


class FakeServer:
    """One WebSocket session: request 0 uses session.start's prompt; request r >= 1 starts only after a prompt
    update was applied (at a chunk boundary) since request r-1 started; updates are last-write-wins."""

    def __init__(self):
        self.inbox = asyncio.Queue()
        self.used = []  # prompt of each request, in order
        self.pings = 0
        self.stopped = False
        self._pending = None  # (event_id, prompt) received, not yet applied
        self._current = None
        self._applied_since_start = False
        self._task = None
        self._wake = asyncio.Event()

    # websocket client API used by the adapter
    async def send(self, text):
        msg = json.loads(text)
        kind = msg["type"]
        if kind == "session.start":
            self._current = msg["prompt"]
            await self.inbox.put(json.dumps({"type": "video.start", "request_id": "x"}))
            self._task = asyncio.create_task(self._run())
        elif kind == "session.interaction":
            self._pending = (msg["interaction"]["event_id"], msg["interaction"]["event"]["prompt"])
            self._wake.set()
        elif kind == "session.ping":
            self.pings += 1
        elif kind == "session.stop":
            self.stopped = True
            if self._task:
                self._task.cancel()
            await self.inbox.put(json.dumps({"type": "session.done", "stopped": True}))

    async def recv(self):
        return await self.inbox.get()

    async def close(self):
        self.stopped = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.inbox.get()
        if item is StopAsyncIteration:
            raise StopAsyncIteration
        return item

    def _apply(self):
        if self._pending is None:
            return []
        event_id, prompt = self._pending
        self._pending = None
        self._current = prompt
        self._applied_since_start = True
        return [event_id]

    async def _run(self):
        chunk = 0
        started = self._apply()  # nothing pending at session start
        for r in range(50):
            if r > 0:
                started += self._apply()
                while not self._applied_since_start:  # the hold
                    self._wake.clear()
                    await self._wake.wait()
                    started += self._apply()
            self.used.append(self._current)
            self._applied_since_start = False
            for p in range(4):
                await self.inbox.put(json.dumps({"type": "video.chunk_metadata", "kind": "media",
                                                 "generation_chunk_index": chunk, "started_event_ids": started}))
                await self.inbox.put(b"fmp4")
                started = []
                chunk += 1
                await asyncio.sleep(0.005)
                started += self._apply()  # interactions apply at every chunk boundary


def _gen(servers, monkeypatch):
    monkeypatch.setattr(mod, "FMP4StreamDecoder", StubDecoder)

    async def connect(url, **kwargs):
        server = FakeServer()
        servers.append(server)
        return server

    return VllmOmniH3Generator(connect=connect, ping_s=0.01)


async def _take(gen, n):
    out = []
    it = gen.chunks().__aiter__()
    for _ in range(n):
        out.append(await asyncio.wait_for(it.__anext__(), timeout=5))
    return out


def test_each_request_runs_with_the_prompt_locked_for_it_even_when_locked_late(monkeypatch):
    async def main():
        servers = []
        gen = _gen(servers, monkeypatch)
        await gen.start()
        await gen.submit(0, "p0")
        first = await _take(gen, 4)  # request 0 complete; request 1 is held at the server
        await asyncio.sleep(0.05)
        assert servers[0].used == ["p0"]  # nothing ran ahead
        await gen.submit(1, "p1")  # late lock
        second = await _take(gen, 4)
        assert servers[0].used == ["p0", "p1"]
        assert [(c.request_index, c.chunk_index) for c in first + second] == [(0, i) for i in range(4)] + [(1, i) for i in range(4)]
        assert second[0].meta["prompt"] == "p1" and not gen.errors
        assert servers[0].pings > 0  # the stall timer is kept fresh while held
        await gen.close()

    asyncio.run(main())


def test_early_locks_are_released_one_request_at_a_time(monkeypatch):
    async def main():
        servers = []
        gen = _gen(servers, monkeypatch)
        for k in range(4):  # all locked up front: last-write-wins would overwrite them if sent at once
            await gen.submit(k, f"p{k}")
        chunks = await _take(gen, 16)
        assert servers[0].used[:4] == ["p0", "p1", "p2", "p3"]
        assert [c.request_index for c in chunks] == [k for k in range(4) for _ in range(4)]
        assert all("stale_prompt" not in gen.request_extras.get(k, {}) for k in range(4))
        await gen.close()

    asyncio.run(main())


def test_reset_stops_the_server_session_and_starts_a_fresh_one(monkeypatch):
    async def main():
        servers = []
        gen = _gen(servers, monkeypatch)
        await gen.submit(0, "p0")
        await _take(gen, 2)
        epoch = gen.session_epoch
        assert await gen.reset_confirmed(timeout=5)
        assert servers[0].stopped and gen.session_epoch == epoch + 1
        k = gen.next_request_index
        await gen.submit(k, "fresh")
        chunks = await _take(gen, 4)
        assert len(servers) == 2 and servers[1].used[0] == "fresh"  # new session: fresh KV, prompt in session.start
        assert all(c.meta["session"] == gen.session_epoch and c.request_index == k for c in chunks)
        await gen.close()

    asyncio.run(main())
