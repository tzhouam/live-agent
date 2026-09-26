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

    def in_flight(self):
        """(request, chunk, start time) of the chunk playing right now, if any."""
        return (self._current.request_index, self._current.chunk_index, self._current_t0) if self._current else None

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
            self._current_t0 = t0
            if self._last_end is not None and t0 - self._last_end > 0.05 / self.speed:
                self.stalls.append(Stall(self._last_end, t0))
            await asyncio.sleep(ch.duration_s / self.speed)
            # a simulated client presents exactly the chunk's duration; the measured wall time would
            # add sleep overshoot (x speed) that no real player has
            t1 = t0 + ch.duration_s / self.speed
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
    """Writes a stream of chunks to MP4 (video + audio). Crash-safe: video goes to a fragmented MP4
    (playable even if the writer is killed) and audio is streamed to a raw PCM file with a small
    sidecar, so an interrupted session can be finalised later (`salvage_recordings`).
    Needs an ffmpeg with libx264 (``/usr/bin/ffmpeg`` here)."""

    def __init__(self, path, ffmpeg: str = "/usr/bin/ffmpeg") -> None:
        from pathlib import Path

        self.path = Path(path)
        self.ffmpeg = ffmpeg
        self._proc = None
        self._pcm = None
        self._sr = 32000
        self._ch = 2

    def _paths(self):
        return (self.path.with_suffix(".video.mp4"), self.path.with_suffix(".pcm"),
                self.path.with_suffix(".pcm.json"))

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
            try:
                self._write(chunk)
            except Exception:  # noqa: BLE001 - a recording failure must never affect the session
                pass

    def _write(self, chunk: Chunk) -> None:
        import json
        import subprocess

        import numpy as np

        if chunk.video is None:
            return
        v = np.ascontiguousarray(chunk.video, dtype=np.uint8)
        if chunk.n_frames and len(v) != chunk.n_frames:
            # the recording must hold exactly the presented duration (adjudication time mapping)
            idx = np.minimum((np.arange(chunk.n_frames) * len(v)) // chunk.n_frames, len(v) - 1)
            v = np.ascontiguousarray(v[idx])
        vid, pcm, meta = self._paths()
        if self._proc is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _, h, w, _ = v.shape
            self._proc = subprocess.Popen(
                [self.ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s", f"{w}x{h}", "-r", str(chunk.fps), "-i", "-", "-c:v", "libx264", "-pix_fmt",
                 "yuv420p", "-preset", "veryfast", "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
                 str(vid)], stdin=subprocess.PIPE)
        self._proc.stdin.write(v.tobytes())
        self._proc.stdin.flush()
        n_samples = int(round(chunk.n_frames / chunk.fps * chunk.sample_rate)) if chunk.n_frames else 0
        a = np.zeros((n_samples, 2), np.float32) if chunk.audio is None else np.asarray(chunk.audio, np.float32)
        a = a if a.ndim == 2 else a[:, None]
        if self._pcm is None:
            self._sr, self._ch = chunk.sample_rate, a.shape[1]
            meta.write_text(json.dumps({"sample_rate": self._sr, "channels": self._ch}))
            self._pcm = open(pcm, "ab")
        self._pcm.write((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
        self._pcm.flush()

    def _stop_writers(self) -> None:
        if hasattr(self, "_q"):
            self._q.put(None)
            self._thread.join()
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._proc.wait()
        if self._pcm is not None:
            self._pcm.close()

    def discard(self) -> bool:
        """Erasure: stop recording and delete everything written so far; later chunks are not
        recorded. Returns True when no file of this recording remains."""
        self._stop_writers()
        self.disabled = True
        paths = [self.path, *self._paths(), self.path.with_suffix(".wav")]
        for p in paths:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        return not any(p.exists() for p in paths)

    def close(self) -> None:
        if getattr(self, "disabled", False):
            return
        self._stop_writers()
        finalize_recording(self.path, self.ffmpeg)


def finalize_recording(path, ffmpeg: str = "/usr/bin/ffmpeg") -> bool:
    """Mux <path>.video.mp4 + <path>.pcm into <path> and remove the temporaries."""
    import json
    import subprocess
    from pathlib import Path

    path = Path(path)
    vid, pcm, meta = path.with_suffix(".video.mp4"), path.with_suffix(".pcm"), path.with_suffix(".pcm.json")
    if not vid.exists():
        return False
    if pcm.exists() and meta.exists() and pcm.stat().st_size:
        m = json.loads(meta.read_text())
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(vid), "-f", "s16le", "-ar", str(m["sample_rate"]),
               "-ac", str(m["channels"]), "-i", str(pcm), "-c:v", "copy", "-c:a", "aac", "-shortest", str(path)]
    else:
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(vid), "-c", "copy", str(path)]
    ok = subprocess.run(cmd).returncode == 0 and path.exists()
    if ok:
        for p in (vid, pcm, meta):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
    return ok


def salvage_recordings(directory) -> list[str]:
    """Finalise recordings left unfinished by a killed session (server start-up)."""
    from pathlib import Path

    done = []
    for vid in Path(directory).glob("*.video.mp4"):
        target = vid.with_name(vid.name[: -len(".video.mp4")] + ".mp4")
        if not target.exists() and finalize_recording(target):
            done.append(target.name)
    return done
