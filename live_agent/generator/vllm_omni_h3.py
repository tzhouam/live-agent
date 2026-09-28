"""TaoMate-H3 on a vLLM-Omni USP4 server (``VllmOmniH3Generator``, decisions D-026..D-028).

The server (``vllm serve <MiniMax-H3>/FL2VA --omni`` with ``configs/vllm_omni/taomate_h3_usp4_jit.yaml``) runs
the whole model, audio teacher included, on 4 GPUs under pure Ulysses SP and streams one fragmented-MP4
message per 34/34/34/17-frame phase over ``WS /v1/realtime/video``. This adapter implements the generator
contract of ``live_agent.generator.base`` on that socket:

* ``submit(k, prompt)`` locks request k. The first request of a server session goes in ``session.start``;
  request k >= 1 goes in a ``session.interaction`` prompt update, sent once request k-1 has started (its
  phase-0 chunk arrived), so the update lands inside request k-1 and applies to request k. The server's
  ``taomate_h3_hold_for_prompt`` makes request k wait at its boundary until that update arrives: the stream
  never runs ahead of the director or starts a request on a stale prompt.
* ``chunks()`` yields one chunk per server phase, decoded to RGB frames + 32 kHz stereo audio
  (``live_agent.generator.fmp4``); a few frames per phase are carried into the next chunk to keep A/V sync.
* ``reset()`` stops the server session (its KV/sink is dropped) and the next ``submit`` starts a new one.

Pure asyncio + ``websockets``; no torch here. The server holds the GPUs (its own canhazgpu reservation).
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.generator.fmp4 import FMP4StreamDecoder
from live_agent.types import Chunk, now

PHASES = 4
DEFAULT_MODEL = ("/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/"
                 "42ed227ee7df40d41602854ae760620d6eb651fe/FL2VA")


class ServerError(RuntimeError):
    pass


def session_frames(requests: int) -> int:
    """Frame budget of a server session of ``requests`` five-second requests (124 + 119 per later one)."""
    return 124 + 119 * (requests - 1)


class VllmOmniH3Generator(Generator):
    def __init__(
        self,
        *,
        url: str = "ws://127.0.0.1:8191/v1/realtime/video",
        model: str = DEFAULT_MODEL,
        width: int = 480,
        height: int = 864,
        seed: int = 8301,
        max_requests: int = 6000,  # ~8.3 h per server session (the frame budget is fixed at session.start)
        start_timeout: float = 1800.0,
        ping_s: float = 1.0,
        connect: Any = None,  # tests inject a fake connect()
    ) -> None:
        self.info = GeneratorInfo(name="taomate-h3-vllm-omni", width=width, height=height,
                                  request_seconds=119 / 24,
                                  extra={"native_frames_per_request": 119, "backend": "vllm-omni usp4"})
        self.url = url
        self.model = model
        self.seed = seed
        self.max_requests = max_requests
        self.start_timeout = start_timeout
        self.ping_s = ping_s
        self._connect = connect
        self.errors: list[dict[str, Any]] = []
        self.request_extras: dict[int, dict[str, Any]] = {}
        self._out: asyncio.Queue[Chunk | Exception | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._prompts: dict[int, str] = {}
        self._next = 0
        self._session = 0  # generation epoch, bumped by reset(); chunk.meta["session"]
        self._base = 0  # global index of the current server session's request 0
        self._ws = None
        self._tasks: list[asyncio.Task] = []
        self._send_lock = asyncio.Lock()
        self._decoder: FMP4StreamDecoder | None = None
        self._sent = -1  # highest global request index whose prompt reached the server
        self._started = -1  # highest global request index whose phase-0 chunk arrived
        self._events: dict[str, int] = {}  # event_id -> global request index (current session)
        self._opened: set[int] = set()  # epochs that opened a server session
        self._closed_sessions: set[int] = set()  # epochs whose server session is done / closed

    @classmethod
    def add_args(cls, p) -> None:
        p.add_argument("--omni-url", default="ws://127.0.0.1:8191/v1/realtime/video")
        p.add_argument("--omni-model", default=DEFAULT_MODEL, help="served model path (the FL2VA partition)")
        p.add_argument("--omni-width", type=int, default=480)
        p.add_argument("--omni-height", type=int, default=864)
        p.add_argument("--omni-seed", type=int, default=8301)
        p.add_argument("--omni-max-requests", type=int, default=6000)

    @classmethod
    def from_args(cls, args) -> "VllmOmniH3Generator":
        import argparse

        p = argparse.ArgumentParser(add_help=False)
        cls.add_args(p)
        o, _ = p.parse_known_args(getattr(args, "extra", []) or [])
        return cls(url=o.omni_url, model=o.omni_model, width=o.omni_width, height=o.omni_height,
                   seed=o.omni_seed, max_requests=o.omni_max_requests)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        """Wait until the server answers /health (loading 4 x 62 GB + its warm-up request takes minutes)."""
        if self._connect is not None:
            return
        parts = urlsplit(self.url)
        scheme = "https" if parts.scheme == "wss" else "http"
        health = f"{scheme}://{parts.netloc}/health"
        deadline = time.monotonic() + self.start_timeout
        while True:
            try:
                ok = await asyncio.to_thread(lambda: urllib.request.urlopen(health, timeout=5).status == 200)
                if ok:
                    return
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise ServerError(f"vLLM-Omni server at {health} not ready after {self.start_timeout:.0f} s")
            await asyncio.sleep(2.0)

    async def close(self) -> None:
        await self._stop_session()
        self._out.put_nowait(None)

    # ------------------------------------------------------------------ server session
    async def _open_session(self, prompt: str) -> None:
        if self._connect is not None:
            connect = self._connect
        else:
            from websockets.asyncio.client import connect
        ws = await connect(self.url, max_size=None, open_timeout=30)
        await ws.send(json.dumps({
            "type": "session.start", "model": self.model, "prompt": prompt, "format": "m4s",
            "width": self.info.width, "height": self.info.height, "fps": 24, "seed": self.seed,
            "num_frames": session_frames(self.max_requests),
        }))
        while True:  # the server answers with video.start (or an error)
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            if msg.get("type") == "video.start":
                break
            if msg.get("type") == "error":
                await ws.close()
                raise ServerError(f"session.start rejected: {msg.get('message')}")
        self._ws = ws
        self._decoder = FMP4StreamDecoder(fps=24, sample_rate=self.info.sample_rate)
        epoch = self._session
        self._opened.add(epoch)
        self._tasks = [asyncio.create_task(self._reader(ws, epoch)),
                       asyncio.create_task(self._pinger(ws))]

    async def _stop_session(self) -> None:
        ws, tasks = self._ws, self._tasks
        self._ws, self._tasks, self._decoder = None, [], None
        if ws is not None:
            try:
                async with self._send_lock:
                    await ws.send(json.dumps({"type": "session.stop"}))
            except Exception:  # noqa: BLE001 - the socket may already be gone
                pass
        for task in tasks:
            if task is not asyncio.current_task():
                task.cancel()
        for task in tasks:
            if task is not asyncio.current_task():
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass

    async def _pinger(self, ws) -> None:
        """Keep the server's 60 s stall timer fresh while a request boundary is held."""
        while True:
            await asyncio.sleep(self.ping_s)
            async with self._send_lock:
                await ws.send(json.dumps({"type": "session.ping"}))

    async def _reader(self, ws, epoch: int) -> None:
        pending_meta: dict[str, Any] | None = None
        media_seen = 0
        try:
            async for message in ws:
                if epoch != self._session:
                    return
                if isinstance(message, (bytes, bytearray)):
                    meta, pending_meta = pending_meta or {}, None
                    if meta.get("kind", "media") != "media":
                        continue  # the trailer only arrives when the session ends
                    index = meta.get("generation_chunk_index")
                    index = media_seen if index is None else int(index)
                    media_seen += 1
                    await self._on_media(epoch, index, bytes(message), meta)
                    continue
                msg = json.loads(message)
                kind = msg.get("type")
                if kind == "video.chunk_metadata":
                    pending_meta = msg
                elif kind == "session.done":
                    self._closed_sessions.add(epoch)
                    return
                elif kind == "error" and epoch == self._session:
                    self._fail(f"server: {msg.get('message')}")
                # session.pong / session.interaction.queued: nothing to do
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - connection lost
            if epoch == self._session:
                self._fail(f"server connection lost: {e}")
        finally:
            self._closed_sessions.add(epoch)

    async def _on_media(self, epoch: int, index: int, data: bytes, meta: dict[str, Any]) -> None:
        decoder = self._decoder
        if decoder is None:
            return
        def decode():  # decode and stack (~42 MB of frames per chunk): both off the event loop
            decoder.push(data)
            return decoder.take()

        frame_start, video, audio = await asyncio.to_thread(decode)
        if epoch != self._session:
            return  # reset while decoding
        local, phase = divmod(index, PHASES)
        k = self._base + local
        t_ready = now()
        extras = self.request_extras.setdefault(k, {})
        for event_id in meta.get("started_event_ids") or []:
            target = self._events.get(event_id)
            if target is not None:
                self.request_extras.setdefault(target, {})["prompt_applied_at_chunk"] = index
        if phase == 0 and local > 0 and "prompt_applied_at_chunk" not in extras:
            extras["stale_prompt"] = True  # request started before its prompt: must not happen with the hold
            self.errors.append({"request_index": k, "message": "request started on a stale prompt"})
        n = 0 if video is None else len(video)
        chunk = Chunk(
            request_index=k, chunk_index=phase, n_frames=n, fps=24.0, video=video, audio=audio,
            sample_rate=self.info.sample_rate, t_ready=t_ready,
            meta={"prompt": self._prompts.get(k, ""), "session": epoch, "frame_start": frame_start,
                  "server_chunk_index": index, "started_event_ids": list(meta.get("started_event_ids") or [])},
        )
        timing = self._timings.get(k)
        if phase == 0:
            if timing is not None:
                timing.t_first_chunk = t_ready
            self._started = max(self._started, k)
            await self._send_ready_prompts()
        if phase == PHASES - 1 and timing is not None:
            timing.t_done = t_ready
        extras.setdefault("chunks", []).append({"t_ready": t_ready, "n_frames": n, "server_chunk": index})
        self._out.put_nowait(chunk)

    async def _send_ready_prompts(self) -> None:
        """Send request k's prompt once request k-1 has started (one pending update at a time)."""
        while self._ws is not None and self._sent + 1 < self._next and self._sent <= self._started:
            k = self._sent + 1  # sendable once request k-1 (== self._sent) has started
            event_id = f"s{self._session}-r{k}"
            self._events[event_id] = k
            async with self._send_lock:
                await self._ws.send(json.dumps({
                    "type": "session.interaction",
                    "interaction": {"event_id": event_id, "event": {"prompt": self._prompts[k]}},
                }))
            self._sent = k
            self.request_extras.setdefault(k, {})["t_prompt_sent"] = now()

    def _fail(self, message: str) -> None:
        self.errors.append({"message": message})
        self._out.put_nowait(ServerError(message))

    # ------------------------------------------------------------------ Generator API
    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        k = request_index
        self._timings[k] = RequestTiming(k, t_lock=now())
        self._prompts[k] = prompt
        self._next += 1
        if self._ws is None and k == self._base:
            self._sent = k  # request 0 of the server session travels in session.start
            self.request_extras.setdefault(k, {})["prompt_applied_at_chunk"] = 0
            epoch = self._session
            try:
                await self._open_session(prompt)
            except Exception as e:  # noqa: BLE001
                if epoch == self._session:
                    self._fail(f"cannot start a server session: {e}")
                return
            return
        await self._send_ready_prompts()

    async def chunks(self) -> AsyncIterator[Chunk]:
        while True:
            item = await self._out.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def reset(self) -> None:
        self._session += 1
        await self._stop_session()
        self._base = self._next
        self._sent = self._started = self._next - 1
        self._events.clear()
        # erased text must not linger in adapter memory; queued stale output is discarded
        self._prompts.clear()
        self.request_extras.clear()
        keep = []
        while not self._out.empty():
            item = self._out.get_nowait()
            if item is None:
                keep.append(item)
            elif isinstance(item, Exception):
                self.errors.append({"stale_after_reset": True, "message": str(item)})
        for item in keep:
            self._out.put_nowait(item)

    async def reset_confirmed(self, timeout: float = 30.0) -> bool:
        """Reset and wait until the old server session is closed: ``session.stop`` sent and the socket shut,
        which aborts the server request and drops its session state (KV, sink, teacher tail)."""
        old = self._session
        await self.reset()
        deadline = time.monotonic() + timeout
        while old in self._opened and old not in self._closed_sessions:
            if time.monotonic() > deadline:
                return False
            await asyncio.sleep(0.02)
        return True

    @property
    def timings(self) -> list[RequestTiming]:
        return [self._timings[k] for k in sorted(self._timings)]

    @property
    def session_epoch(self) -> int:
        return self._session

    @property
    def next_request_index(self) -> int:
        return self._next


__all__ = ["VllmOmniH3Generator", "ServerError", "session_frames"]
