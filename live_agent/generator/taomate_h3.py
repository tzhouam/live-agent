"""TaoMate-H3 streaming generator adapter (``TaoMateH3Generator``).

Implements ``live_agent.generator.base.Generator`` on top of two torchrun worker groups
(see ``live_agent/generator/taomate_worker/protocol.py`` for the wire protocol):

* T1 mid-session prompt queue: ``submit(k, prompt)`` locks one 5-second request at a time;
  nothing is precompiled. The text encoder stays resident in the teacher group.
* T2 audio-teacher lookahead: the base-H3 audio teacher for request k starts as soon as k is
  locked (``lookahead=True``), overlapping the student's generation of k-1 when the teacher
  has its own GPUs, and carries the 1 s (40-latent) audio tail across requests.
* T3 per-chunk output: every chunk (34/34/34/17 native 24 fps frames + aligned 32 kHz
  stereo audio) is yielded by ``chunks()`` as soon as its VAE decode finishes.

This module only needs the standard library and numpy; torch lives in the worker
environment (``.venvs/taomate-h3``). The caller must hold a canhazgpu reservation for the
devices it passes (e.g. run the whole program under ``gpu run ...``).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
import threading
import time
from collections.abc import AsyncIterator
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.generator.taomate_worker import protocol as P
from live_agent.types import Chunk, now

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PYTHON = REPO / ".venvs" / "taomate-h3" / "bin" / "python"
DEFAULT_MODEL_ROOT = Path(
    "/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe"
)
DEFAULT_ADAPTER = REPO / ".cache" / "models" / "TaoMate-H3"


class WorkerError(RuntimeError):
    pass


def split_devices(visible: str | None) -> tuple[str, str | None]:
    """Default placement: first 4 (or 8) devices for the student, 2+ leftovers for the teacher."""

    ids = [d for d in (visible or "").split(",") if d.strip()]
    if len(ids) >= 8:
        student, rest = ids[:8], ids[8:]
    elif len(ids) >= 4:
        student, rest = ids[:4], ids[4:]
    else:
        raise ValueError("TaoMate-H3 needs at least 4 visible GPUs for the student")
    teacher = ",".join(rest[: 2 * (len(rest) // 2)]) if len(rest) >= 2 else None
    return ",".join(student), teacher


class TaoMateH3Generator(Generator):
    def __init__(
        self,
        *,
        student_devices: str | None = None,
        teacher_devices: str | None = None,
        colocate_teacher: bool | None = None,
        model_root: Path = DEFAULT_MODEL_ROOT,
        adapter_dir: Path = DEFAULT_ADAPTER,
        python: Path = DEFAULT_PYTHON,
        width: int = 480,  # portrait 480x864, the README's benchmark canvas
        height: int = 864,
        seed: int = 8301,
        lookahead: bool = True,
        launch: bool = True,
        log_dir: Path | None = None,
        start_timeout: float = 1800.0,
        return_latents: bool = False,
        warmup_prompt: str | None = None,
        warmup_timeout: float = 300.0,  # measured warm-up 16-31 s (M0) [measured locally]; generous bound
    ) -> None:
        self.info = GeneratorInfo(name="taomate-h3", width=width, height=height,
                                  request_seconds=119 / 24,
                                  extra={"native_frames_per_request": 119, "lookahead": lookahead})
        if launch and student_devices is None:
            student_devices, auto_teacher = split_devices(os.environ.get("CUDA_VISIBLE_DEVICES"))
            if teacher_devices is None and not colocate_teacher:
                teacher_devices = auto_teacher
        self.student_devices = student_devices
        self.teacher_devices = teacher_devices or student_devices  # None -> colocated
        self.model_root = Path(model_root)
        self.adapter_dir = Path(adapter_dir)
        self.python = Path(python)
        self.seed = seed
        self.lookahead = lookahead
        self.launch = launch
        self.log_dir = Path(log_dir) if log_dir else REPO / ".cache" / "taomate_worker_logs"
        self.start_timeout = start_timeout
        self.return_latents = return_latents
        self.warmup_prompt = warmup_prompt
        self.warmup_timeout = warmup_timeout
        self.warmup_s: float | None = None
        self.authkey = secrets.token_bytes(16)
        self.address: tuple[str, int] | None = None
        self.worker_info: dict[str, dict[str, Any]] = {}
        self.request_extras: dict[int, dict[str, Any]] = {}
        self.errors: list[dict[str, Any]] = []
        self._listener: Listener | None = None
        self._channels: dict[str, P.Channel] = {}
        self._procs: dict[str, subprocess.Popen] = {}
        self._ready: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._out: asyncio.Queue[Chunk | Exception | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._prompts: dict[int, str] = {}
        self._teacher_done: dict[int, dict[str, Any]] = {}
        self._next = 0
        self._session = 0
        self._session_base = 0  # global index of local request 0 in this session
        self._taught = -1  # highest request index sent to the teacher
        self._generated = -1  # highest request index sent to the student
        self._student_done = -1  # highest request index the student finished
        self._clock_offset = time.monotonic() - time.time()
        self._futures: dict[str, asyncio.Future] = {}
        self._reset_acks: dict[int, set[str]] = {}

    @classmethod
    def add_args(cls, p) -> None:
        p.add_argument("--taomate-student-devices", default=None,
                       help="comma list; default: split CUDA_VISIBLE_DEVICES (see split_devices)")
        p.add_argument("--taomate-teacher-devices", default=None)
        p.add_argument("--taomate-colocate-teacher", action="store_true")
        p.add_argument("--taomate-model-root", default=str(DEFAULT_MODEL_ROOT))
        p.add_argument("--taomate-adapter-dir", default=str(DEFAULT_ADAPTER))
        p.add_argument("--taomate-python", default=str(DEFAULT_PYTHON))
        p.add_argument("--taomate-width", type=int, default=480)
        p.add_argument("--taomate-height", type=int, default=864)
        p.add_argument("--taomate-seed", type=int, default=8301)
        p.add_argument("--taomate-no-warmup", action="store_true")

    @classmethod
    def from_args(cls, args) -> "TaoMateH3Generator":
        """Build from the unparsed ``--taomate-*`` options a CLI left in ``args.extra``."""
        import argparse

        p = argparse.ArgumentParser(add_help=False)
        cls.add_args(p)
        o, _ = p.parse_known_args(getattr(args, "extra", []) or [])
        warmup = None
        if not o.taomate_no_warmup:
            warmup = ("integrated_multimodal_description: [Shot 1] A person sits quietly at a desk, "
                      "reading a book in soft daylight.\n\noverall_soundscape: Quiet room tone.\n\n"
                      "non_diegetic_music: N/A")
        return cls(student_devices=o.taomate_student_devices, teacher_devices=o.taomate_teacher_devices,
                   colocate_teacher=o.taomate_colocate_teacher, model_root=Path(o.taomate_model_root),
                   adapter_dir=Path(o.taomate_adapter_dir), python=Path(o.taomate_python),
                   width=o.taomate_width, height=o.taomate_height, seed=o.taomate_seed,
                   warmup_prompt=warmup)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        try:
            await self._start()
        except BaseException:
            await self.close()  # a partial start must not leave workers or the listener alive
            raise

    async def _start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._listener = Listener(("127.0.0.1", 0), authkey=self.authkey)
        self.address = self._listener.address
        self._ready = {P.ROLE_TEACHER: asyncio.Event(), P.ROLE_STUDENT: asyncio.Event()}
        threading.Thread(target=self._accept_loop, daemon=True).start()
        if self.launch:
            self._spawn()
        waiter = asyncio.gather(*(event.wait() for event in self._ready.values()))
        deadline = time.monotonic() + self.start_timeout
        while not waiter.done():
            await asyncio.wait({waiter}, timeout=1.0)
            self._check_processes()
            if self.errors and not waiter.done():
                waiter.cancel()
                raise WorkerError(f"worker failed during start: {self.errors[-1]['message']}")
            if time.monotonic() > deadline:
                waiter.cancel()
                raise WorkerError("TaoMate-H3 workers did not become ready in time")
        if self.warmup_prompt:
            try:  # the first request can stall without a worker disconnect: bound it
                await asyncio.wait_for(self._warmup(self.warmup_prompt), timeout=self.warmup_timeout)
            except asyncio.TimeoutError as e:
                raise WorkerError(f"warm-up request did not finish within {self.warmup_timeout} s") from e

    async def _warmup(self, prompt: str) -> None:
        """Run one throw-away request (Triton JIT, CUDA graphs/allocator, VAE fusions), then
        reset so the caller's session starts at request 0 with a fresh KV/sink/teacher tail."""

        started = now()
        await self.submit(0, prompt)
        received = 0
        async for _chunk in self.chunks():
            received += 1
            if received == 4:
                break
        while self._student_done < 0:
            await asyncio.sleep(0.05)
        self.warmup_s = now() - started
        self.warmup_record = {"timing": self._timings.get(0), "extras": self.request_extras.get(0)}
        await self.reset()
        self._next = self._session_base = 0
        self._taught = self._generated = self._student_done = -1
        self._timings.clear()
        self._prompts.clear()
        self.request_extras.clear()

    def _worker_env(self, role: str, devices: str) -> dict[str, str]:
        env = os.environ.copy()
        assert self.address is not None
        env.update({
            P.ENV_ADDRESS: f"{self.address[0]}:{self.address[1]}",
            P.ENV_AUTHKEY: self.authkey.hex(),
            P.ENV_ROLE: role,
            "CUDA_VISIBLE_DEVICES": devices,
            "OMP_NUM_THREADS": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(REPO), str(REPO / "external" / "TaoMate-H3" / "src"),
                              env.get("PYTHONPATH")])
            ),
        })
        return env

    def _spawn(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        common = ["--width", str(self.info.width), "--height", str(self.info.height),
                  "--model-root", str(self.model_root)]
        plan = {
            P.ROLE_TEACHER: (self.teacher_devices, "teacher_service", common),
            P.ROLE_STUDENT: (self.student_devices, "student_service",
                             [*common, "--adapter", str(self.adapter_dir)]),
        }
        stamp = time.strftime("%Y%m%dT%H%M%S")
        for role, (devices, module, args) in plan.items():
            count = len(devices.split(","))
            command = [
                str(self.python), "-m", "torch.distributed.run", "--standalone",
                f"--nproc-per-node={count}", "--module",
                f"live_agent.generator.taomate_worker.{module}", *args,
            ]
            log = open(self.log_dir / f"{stamp}-{role}.log", "w")
            self._procs[role] = subprocess.Popen(
                command, env=self._worker_env(role, devices), stdout=log,
                stderr=subprocess.STDOUT, cwd=str(REPO),
            )

    def _check_processes(self) -> None:
        for role, proc in self._procs.items():
            code = proc.poll()
            if code is not None and not any(e.get("role") == role and e.get("exit") for e in self.errors):
                self.errors.append({"role": role, "exit": code,
                                    "message": f"{role} worker exited with code {code}"})

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while len(self._channels) < 2:
            try:
                conn = self._listener.accept()
            except (OSError, EOFError):
                return
            channel = P.Channel(conn)
            try:
                hello = channel.recv()
            except (EOFError, OSError):
                continue
            role = hello.get("role")
            if role not in (P.ROLE_TEACHER, P.ROLE_STUDENT) or role in self._channels:
                channel.close()
                continue
            self._channels[role] = channel
            self._post(role, hello)
            threading.Thread(target=self._reader, args=(role, channel), daemon=True).start()

    def _reader(self, role: str, channel: P.Channel) -> None:
        while True:
            try:
                message = channel.recv()
            except (EOFError, OSError, TypeError):  # TypeError: connection closed under us
                self._post(role, {"type": "disconnected"})
                return
            if message.get("type") == P.CHUNK:
                # load the ~40 MB /dev/shm payload here, on this reader thread: done in the event-loop
                # callback it stalled the loop ~0.2-0.4 s per chunk (found by the stall watchdog)
                try:
                    message["video"] = P.from_shm(message.get("video"))
                    message["audio"] = P.from_shm(message.get("audio"))
                except Exception as e:  # noqa: BLE001 - reported on the loop as a fatal adapter error
                    P.discard_shm(message)
                    message["shm_error"] = str(e)
            self._post(role, message)

    def _post(self, role: str, message: dict[str, Any]) -> None:
        if self._loop is None or self._loop.is_closed():
            P.discard_shm(message)  # cannot be delivered: do not leave its payload behind
            return
        try:
            self._loop.call_soon_threadsafe(self._on_message, role, message)
        except RuntimeError:  # loop closed between the check and the call
            P.discard_shm(message)

    def _send(self, role: str, message: dict[str, Any]) -> None:
        channel = self._channels.get(role)
        if channel is None:
            raise WorkerError(f"{role} worker is not connected")
        channel.send(message)

    def _mono(self, t: float | None) -> float | None:
        return None if t is None else t + self._clock_offset

    # ------------------------------------------------------------------ message handling
    def _on_message(self, role: str, message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == P.HELLO:
            self.worker_info.setdefault(role, {})["hello"] = message
            return
        if kind == P.READY:
            self.worker_info.setdefault(role, {})["ready"] = message
            self._ready[role].set()
            return
        if kind == "disconnected":
            if not getattr(self, "_closing", False):
                self._fail({"role": role, "message": f"{role} worker disconnected"})
            return
        if kind == "reset_done":
            self._reset_acks.setdefault(int(message.get("session", -1)), set()).add(role)
            return
        if kind in ("flushed", "full_audio"):
            future = self._futures.pop(kind, None)
            if future is not None and not future.done():
                future.set_result(message)
            return
        session = int(message.get("session", -1))
        if kind == P.ERROR:
            P.discard_shm(message)
            if session == self._session:
                self._fail({"role": role, **message})
            return
        if session != self._session:
            P.discard_shm(message)  # stale media from before a reset/erasure must not linger
            return  # stale reply from a reset session
        k = int(message.get("request_index", -1))
        timing = self._timings.get(k)
        extras = self.request_extras.setdefault(k, {})
        if kind == P.TEACHER_DONE:
            if timing is not None:
                timing.t_teacher_start = self._mono(message["t_start"])
                timing.t_teacher_done = self._mono(message["t_done"])
            extras.update({
                "teacher_text_s": message["t_text_done"] - message["t_start"],
                "teacher_s": message["t_done"] - message["t_start"],
                "teacher_done_received": now(),
                "audio_latent_count": message.get("audio_latent_count"),
                "teacher_peak_allocated_gib": message.get("peak_allocated_gib"),
            })
            if self.return_latents:  # debug/parity: keep the opaque teacher payload
                extras["teacher_blob"] = message["blob"]
            self._teacher_done[k] = message
            self._dispatch()
        elif kind == P.REQUEST_START:
            if timing is not None:
                timing.t_student_start = self._mono(message["t"])
        elif kind == P.CHUNK:
            t_ready = now()
            if message.get("shm_error"):  # missing/corrupt payload (loaded on the reader thread): fatal
                self._fail({"role": role, "type": P.ERROR,
                            "message": f"chunk payload unreadable: {message['shm_error']}"})
                return
            try:  # no-op when the reader thread already loaded the arrays (from_shm is idempotent)
                message["video"] = P.from_shm(message.get("video"))
                message["audio"] = P.from_shm(message.get("audio"))
            except Exception as e:  # noqa: BLE001
                P.discard_shm(message)
                self._fail({"role": role, "type": P.ERROR, "message": f"chunk payload unreadable: {e}"})
                return
            chunk = Chunk(
                request_index=k,
                chunk_index=int(message["chunk_index"]),
                n_frames=int(message["n_frames"]),
                fps=float(message["fps"]),
                video=message.get("video"),
                audio=message.get("audio"),
                sample_rate=int(message.get("sample_rate", 32000)),
                t_ready=t_ready,
                meta={
                    "prompt": self._prompts.get(k, ""),
                    "session": session,
                    "local_index": message.get("local_index"),
                    "frame_start": message.get("frame_start"),
                    "audio_sample_start": message.get("audio_sample_start"),
                    "latent_count": message.get("latent_count"),
                    "audio_context": message.get("audio_context"),
                    "t_phase_start": self._mono(message.get("t_phase_start")),
                    "t_denoised": self._mono(message.get("t_denoised")),
                    "t_decoded": self._mono(message.get("t_decoded")),
                    "t_worker_ready": self._mono(message.get("t_ready")),
                },
            )
            if chunk.chunk_index == 0 and timing is not None:
                timing.t_first_chunk = t_ready
            extras.setdefault("chunks", []).append(
                {key: chunk.meta[key] for key in ("t_phase_start", "t_denoised", "t_decoded",
                                                  "t_worker_ready")} | {"t_ready": t_ready,
                                                                        "n_frames": chunk.n_frames})
            self._out.put_nowait(chunk)
        elif kind == P.REQUEST_DONE:
            if timing is not None:
                timing.t_done = self._mono(message["t"])
            extras.update({
                "audio_teacher_exact_match": message.get("audio_teacher_exact_match"),
                "frames_emitted": message.get("frames_emitted"),
                "student_peak_allocated_gib": message.get("peak_allocated_gib"),
                "latents": message.get("latents"),
            })
            self._student_done = max(self._student_done, k)
            self._dispatch()

    def _fail(self, error: dict[str, Any]) -> None:
        self.errors.append(error)
        self._out.put_nowait(WorkerError(f"{error.get('role')}: {error.get('message')}"))

    def _dispatch(self) -> None:
        """Send teacher and student work that has become eligible, in request order."""

        # teacher: all locked requests (lookahead) or only the one after the student's last
        limit = self._next - 1 if self.lookahead else min(self._next - 1, self._student_done + 1)
        while self._taught < limit:
            k = self._taught + 1
            if not self.lookahead and k > self._session_base and k - 1 > self._student_done:
                break
            self._send(P.ROLE_TEACHER, {
                "type": P.TEACH, "session": self._session, "request_index": k,
                "local_index": k - self._session_base, "prompt": self._prompts[k],
                "seed": self.seed,
            })
            self._taught = k
        # student: next request once its teacher output is available (student queues FIFO)
        while self._generated + 1 in self._teacher_done:
            k = self._generated + 1
            done = self._teacher_done.pop(k)
            self._send(P.ROLE_STUDENT, {
                "type": P.GENERATE, "session": self._session, "request_index": k,
                "local_index": k - self._session_base, "prompt": self._prompts[k],
                "seed": self.seed, "blob": done["blob"], "return_latents": self.return_latents,
            })
            self._generated = k

    # ------------------------------------------------------------------ Generator API
    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        self._timings[request_index] = RequestTiming(request_index, t_lock=now())
        self._prompts[request_index] = prompt
        self._next += 1
        self._dispatch()

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
        self._session_base = self._next
        self._taught = self._generated = self._student_done = self._next - 1
        self._teacher_done.clear()
        # Retained text of earlier requests (prompts, teacher payloads) is released here too, so an
        # erasure does not leave erased content in adapter memory; queued stale output is discarded.
        self._prompts.clear()
        self.request_extras.clear()
        keep = []
        while not self._out.empty():  # drain everything; only the end-of-stream sentinel survives
            item = self._out.get_nowait()
            if item is None:
                keep.append(item)
            elif isinstance(item, Exception):
                self.errors.append({"stale_after_reset": True, "message": str(item)})  # not re-raised later
        for item in keep:
            self._out.put_nowait(item)
        for role in (P.ROLE_TEACHER, P.ROLE_STUDENT):
            self._send(role, {"type": P.RESET, "session": self._session})

    async def reset_confirmed(self, timeout: float = 30.0) -> bool:
        """Reset and wait until both worker groups report their state released (erasure)."""
        await self.reset()
        session = self._session
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._reset_acks.get(session, set()) >= {P.ROLE_TEACHER, P.ROLE_STUDENT}:
                return True
            await asyncio.sleep(0.02)
        return False

    async def flush(self, timeout: float = 120.0) -> dict[str, Any]:
        """Ask the student for the held 5-frame video overlap (end of a session)."""

        return await self._request_reply("flushed", {"type": "flush"}, timeout)

    async def full_audio(self, timeout: float = 120.0) -> dict[str, Any]:
        """One-shot audio decode of the whole session (parity check against streaming)."""

        return await self._request_reply("full_audio", {"type": "full_audio"}, timeout)

    async def _request_reply(self, key: str, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        assert self._loop is not None
        future = self._loop.create_future()
        self._futures[key] = future
        self._send(P.ROLE_STUDENT, message)
        return await asyncio.wait_for(future, timeout)

    async def close(self) -> None:
        """Cancellation-safe: workers are always terminated and resources released, then a
        cancellation is re-raised."""
        self._closing = True
        cancelled = None
        for role in list(self._channels):
            try:
                self._send(role, {"type": P.SHUTDOWN})
            except (WorkerError, OSError):
                pass
        for proc in self._procs.values():
            try:
                await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=120)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError as e:
                cancelled = e
                break
        for proc in self._procs.values():  # bounded, synchronous: runs even when cancelled
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
        pids = [proc.pid for proc in self._procs.values()]
        for channel in self._channels.values():
            try:
                channel.close()
            except OSError:
                pass
        if self._listener is not None:
            self._listener.close()
        P.sweep_shm(pids + list(self._worker_pids()))
        P.sweep_dead_shm()  # files of any rank process that no longer exists
        self._out.put_nowait(None)
        if cancelled is not None:
            raise cancelled

    def _worker_pids(self) -> list[int]:
        """Rank pids reported by the workers (torchrun children write the payload files)."""
        out = []
        for info in self.worker_info.values():
            for key in ("hello", "ready"):
                msg = info.get(key) or {}
                out += [int(x) for x in msg.get("pids", [])]
                if msg.get("pid") is not None:
                    out.append(int(msg["pid"]))
        return sorted(set(out))

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


__all__ = ["TaoMateH3Generator", "WorkerError", "split_devices"]
