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
    recorder: object | None = None  # optional Recorder of the presented stream

    def __post_init__(self) -> None:
        self._q: asyncio.Queue[tuple[Chunk, BlockScript]] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._last_end: float | None = None
        self._current: Chunk | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._play())

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        await self._q.put((chunk, script))

    async def stop_playback(self) -> None:
        """Barge-in: stop *now*. The chunk being played is cut (never acknowledged as presented)
        and everything queued is discarded."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            if self._current is not None:
                self.dropped.append((self._current.request_index, self._current.chunk_index))
                self._current = None
            self._task = asyncio.create_task(self._play())
        while not self._q.empty():
            ch, _ = self._q.get_nowait()
            self.dropped.append((ch.request_index, ch.chunk_index))
        self._last_end = None  # the gap after an interruption is not a stall

    async def _play(self) -> None:
        while True:
            ch, _script = await self._q.get()
            self._current = ch
            t0 = now()
            if self._last_end is not None and t0 - self._last_end > 0.05 / self.speed:
                self.stalls.append(Stall(self._last_end, t0))
            await asyncio.sleep(ch.duration_s / self.speed)
            t1 = now()
            self._current = None
            self._last_end = t1
            self.presented.append((ch.request_index, ch.chunk_index, t0, t1))
            if self.recorder is not None:
                self.recorder.write(ch)
            if self.orchestrator is not None:
                self.orchestrator.on_presented(ch.request_index, ch.chunk_index, t0, t1)

    def close(self) -> None:
        if self._task:
            self._task.cancel()
        if self.recorder is not None:
            self.recorder.close()


class Recorder:
    """Writes the *presented* stream (what a viewer saw) to MP4: raw frames are piped to ffmpeg,
    audio is buffered and muxed on close. Needs an ffmpeg with libx264 (``/usr/bin/ffmpeg`` here)."""

    def __init__(self, path, ffmpeg: str = "/usr/bin/ffmpeg") -> None:
        from pathlib import Path

        self.path = Path(path)
        self.ffmpeg = ffmpeg
        self._proc = None
        self._audio: list = []
        self._sr = 32000

    def write(self, chunk: Chunk) -> None:
        """Non-blocking: frames are encoded on a background thread (the caller is the playback loop)."""
        if getattr(self, "disabled", False):
            return
        import queue
        import threading

        if not hasattr(self, "_q"):
            self._q = queue.Queue()
            self._thread = threading.Thread(target=self._drain, daemon=True)
            self._thread.start()
        self._q.put(chunk)

    def _drain(self) -> None:
        while True:
            chunk = self._q.get()
            if chunk is None:
                return
            self._write(chunk)

    def _write(self, chunk: Chunk) -> None:
        import subprocess

        import numpy as np

        if chunk.video is None:
            return
        v = np.ascontiguousarray(chunk.video, dtype=np.uint8)
        if self._proc is None:
            _, h, w, _ = v.shape
            self._tmp = self.path.with_suffix(".video.mp4")
            self._proc = subprocess.Popen(
                [self.ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{w}x{h}", "-r", str(chunk.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt",
                 "yuv420p", "-preset", "veryfast", str(self._tmp)], stdin=subprocess.PIPE)
        self._proc.stdin.write(v.tobytes())
        if chunk.audio is not None:
            self._audio.append(np.asarray(chunk.audio, dtype=np.float32))
            self._sr = chunk.sample_rate

    def discard(self) -> bool:
        """Erasure: stop recording and delete everything written so far; later chunks are not
        recorded. Returns True when no file of this recording remains."""
        if hasattr(self, "_q"):
            self._q.put(None)
            self._thread.join()
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._proc.wait()
        self._audio.clear()
        self.disabled = True
        paths = [self.path, self.path.with_suffix(".video.mp4"), self.path.with_suffix(".wav")]
        for p in paths:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        return not any(p.exists() for p in paths)

    def close(self) -> None:
        import subprocess
        import wave

        if getattr(self, "disabled", False):
            return

        import numpy as np

        if hasattr(self, "_q"):
            self._q.put(None)
            self._thread.join()
        if self._proc is None:
            return
        self._proc.stdin.close()
        self._proc.wait()
        if not self._audio:
            self._tmp.replace(self.path)
            return
        a = np.concatenate(self._audio)
        a = a if a.ndim == 2 else a[:, None]
        wav = self.path.with_suffix(".wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(a.shape[1])
            w.setsampwidth(2)
            w.setframerate(self._sr)
            w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
        subprocess.run([self.ffmpeg, "-y", "-loglevel", "error", "-i", str(self._tmp), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-shortest", str(self.path)], check=True)
        self._tmp.unlink()
        wav.unlink()
