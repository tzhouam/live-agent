"""WebSocket media encoding, presentation acknowledgements and panel events.

The binary protocol is preserved across the frontend proxy; the browser's audio
output clock is mapped to server monotonic time using ping samples.
"""

from __future__ import annotations

import asyncio
import io
from fractions import Fraction
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import WebSocket

from live_agent.orchestrator import Orchestrator
from live_agent.types import BlockScript, Chunk, now

log = logging.getLogger("live_agent.backend.transport")


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def encode_h264(frames: np.ndarray, crf: int = 26) -> tuple[bytes, list[int]]:
    """One self-contained H.264 segment per chunk (baseline, IDR first, no B-frames: decodable on its own,
    so a barge-in can drop any chunk). Returns the Annex-B bytes and the size of each frame's access unit.
    About 5x smaller than per-frame JPEG q80 at 480x864 [measured locally], which the remote bridge needs."""
    import av

    n, h, w = frames.shape[:3]
    enc = av.CodecContext.create("libx264", "w")
    enc.width, enc.height, enc.pix_fmt = w, h, "yuv420p"
    enc.time_base = Fraction(1, 24)
    enc.framerate = Fraction(24, 1)
    enc.options = {"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline", "crf": str(crf),
                   "g": str(max(n, 1) + 1), "bf": "0", "threads": "4"}
    out, sizes = [], []

    def keep(packets):
        for pkt in packets:
            b = bytes(pkt)
            out.append(b)
            sizes.append(len(b))

    for i, f in enumerate(frames):
        vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24").reformat(format="yuv420p")
        vf.pts = i
        keep(enc.encode(vf))
    keep(enc.encode(None))
    return b"".join(out), sizes


def to_pcm16(audio: np.ndarray | None, n_samples: int) -> bytes:
    if audio is None or len(audio) == 0:
        return np.zeros(n_samples, dtype=np.int16).tobytes()
    a = audio.mean(axis=1) if audio.ndim == 2 else audio
    return (np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()


PANEL_EVENTS = {"lock", "verdict", "repair", "completion_claim", "refusal", "capacity_skip", "narration_guard",
                "playback_stop", "speech_onset", "utterance_end", "audit", "error", "request_done", "continuity", "lesson", "attention"}
PANEL_FIELDS = ("action", "transcript", "chain_ids", "chain_id", "step", "retry_of", "corrections", "kind", "label",
                "confidence", "rationale", "mode", "correction", "queued", "earliest_correctable", "reason", "text",
                "original", "cleaned", "erasure", "erasure_complete", "pending_targets", "deleted", "dropped",
                "decision", "applied", "chains", "recalled", "issues", "error", "where", "lead_s", "total_s", "onset_source",
                "audibility", "revision", "speaker", "uid", "request_id", "exercise_request_id", "counts", "expected", "wrong", "target", "gave_up", "anchor_removed", "stage",
                "title", "sections", "section", "lines", "points", "board", "seconds",
                "attempt", "labels",
                "point", "judgements", "state", "stable", "nudge",
                "plan", "note", "adaptive", "depth", "exercise", "concept", "correct", "skipped", "misconception",
                "mastery", "profile", "changed", "options", "question", "option_texts", "topic")


def panel_event(ev, t0: float) -> dict | None:
    """Compact, display-only form of a timeline event (the full log stays on disk)."""
    if ev.type.value not in PANEL_EVENTS:
        return None
    if ev.type.value == "error" and ev.data.get("where") in ("event_loop_stack",):
        return None
    data = {k: ev.data[k] for k in PANEL_FIELDS if k in ev.data}
    if isinstance(data.get("rationale"), str):
        data["rationale"] = data["rationale"][:160]
    return {"type": "event", "event": ev.type.value, "t": round(ev.t - t0, 2), "request": ev.request_index,
            "data": data}


class WSTransport:
    """Orchestrator transport over one WebSocket connection.

    Presentation times: the client reports, for each chunk, when its audio starts / ends at the
    audio *output* (AudioContext.getOutputTimestamp -> performance clock, ``tp`` in ms). The
    server maps that clock to its own with the lowest-RTT ping sample (NTP-style,
    offset = t_server - (t_client_send + rtt/2)). Until a mapping exists, arrival time is used
    (and the event says so)."""

    def __init__(self, ws: WebSocket, record_path: Path | None = None, video_codec: str = "jpeg"):
        self.ws = ws
        self.video_codec = video_codec  # "h264" when the page can decode it (WebCodecs), else "jpeg"
        self.orchestrator: Orchestrator | None = None
        # trace recording: exactly the chunks the client reports as played (chunk_end acks), in order
        self.record_path = record_path
        self.recorder = None
        self._part = 1
        self._sent: dict[tuple[int, int], Chunk] = {}
        if record_path is not None:
            self._new_recorder()
        self._send_lock = asyncio.Lock()
        self._starts: dict[tuple[int, int], float] = {}
        self._epoch = 0  # incremented on stop; stale sends are skipped
        self.clock_offset_s: float | None = None
        self.clock_rtt_s: float | None = None

    def _new_recorder(self) -> None:
        from live_agent.sim import Recorder

        path = self.record_path if self._part == 1 else self.record_path.with_name(
            f"{self.record_path.stem}-part{self._part}{self.record_path.suffix}")
        self.recorder = Recorder(path)

    def restart_recording(self) -> None:
        """After an erasure deleted the recording, continue in a new part file."""
        if self.record_path is not None:
            self._part += 1
            self._new_recorder()

    async def send_chunk(self, chunk: Chunk, script: BlockScript) -> None:
        if self.recorder is not None:
            self._sent[(chunk.request_index, chunk.chunk_index)] = chunk
        epoch = self._epoch
        frames = chunk.video if chunk.video is not None else np.zeros((chunk.n_frames, 8, 8, 3), np.uint8)
        # Encode off the event loop.
        loop = asyncio.get_running_loop()
        segment, sizes, jpegs = None, None, None
        if self.video_codec == "h264" and chunk.video is not None and len(frames):
            try:
                segment, sizes = await loop.run_in_executor(None, encode_h264, frames)
                if len(sizes) != len(frames):
                    segment = sizes = None  # one access unit per frame or nothing: fall back for this chunk
            except Exception:  # noqa: BLE001 - never lose a chunk to the encoder
                log.exception("H.264 encode failed; sending JPEG")
                segment = sizes = None
        if segment is None:
            jpegs = await loop.run_in_executor(None, lambda: [encode_jpeg(f) for f in frames])
        pcm = to_pcm16(chunk.audio, int(chunk.duration_s * chunk.sample_rate))
        async with self._send_lock:
            if epoch != self._epoch:
                return
            h, w = frames.shape[1:3]
            header = {
                "type": "chunk", "request": chunk.request_index, "chunk": chunk.chunk_index,
                "n_frames": len(frames), "fps": chunk.fps, "sample_rate": chunk.sample_rate,
                "duration": chunk.duration_s,  # media duration (may differ from n_frames / fps)
                "width": int(w), "height": int(h), "transcript": script.transcript,
                "codec": "h264" if segment is not None else "jpeg"}
            if segment is not None:
                header["sizes"] = sizes
            board = getattr(script, "board", None)
            if board is not None and chunk.chunk_index == 0:
                header["board"] = board  # shown when this chunk starts playing: aligned with the line
            await self.ws.send_text(json.dumps(header))
            if segment is not None:
                await self.ws.send_bytes(segment)
            else:
                for j in jpegs:
                    if epoch != self._epoch:
                        return  # interrupted mid-chunk: the client discards the partial chunk
                    await self.ws.send_bytes(j)
            if epoch == self._epoch:
                await self.ws.send_bytes(pcm)

    async def send_json(self, obj: dict) -> None:
        """Small control/panel messages, sent between (never inside) a chunk's binary frames."""
        async with self._send_lock:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))

    async def stop_playback(self) -> None:
        """Immediate: does not wait for an in-flight chunk send (which aborts at its next frame)."""
        self._epoch += 1
        self._sent.clear()  # interrupted chunks were never (fully) shown: not recorded
        await self.ws.send_text(json.dumps({"type": "stop"}))

    def in_flight(self):
        """(request, chunk, start time) of a chunk that started playing but has not ended."""
        if not self._starts:
            return None
        (k, ci), t = max(self._starts.items(), key=lambda kv: kv[1])
        return (k, ci, t)

    def on_clock(self, msg: dict) -> None:
        rtt = float(msg["rtt"]) / 1000.0
        if self.clock_rtt_s is None or rtt <= self.clock_rtt_s:
            self.clock_rtt_s = rtt
            self.clock_offset_s = float(msg["t_server"]) - (float(msg["t_client"]) / 1000.0 + rtt / 2)

    def _to_server(self, msg: dict) -> float:
        if msg.get("tp") is not None and self.clock_offset_s is not None:
            return float(msg["tp"]) / 1000.0 + self.clock_offset_s
        return now()

    def on_client_message(self, msg: dict) -> None:
        t = self._to_server(msg)
        key = (int(msg.get("request", -1)), int(msg.get("chunk", -1)))
        if msg["type"] == "chunk_start":
            self._starts[key] = t
        elif msg["type"] == "chunk_end" and self.orchestrator is not None:
            ch = self._sent.pop(key, None)
            if ch is not None and self.recorder is not None:
                self.recorder.write(ch)  # background-thread encoding
            painted = msg.get("painted")
            t_paint = (self._to_server({"tp": msg["tp_last_paint"]}) if msg.get("tp_last_paint") is not None
                       and self.clock_offset_s is not None else None)
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t,
                                           painted=[int(i) for i in painted] if painted is not None else None,
                                           t_last_paint=t_paint)
        elif msg["type"] == "chunk_received" and self.orchestrator is not None and self.clock_offset_s is not None:
            self.orchestrator.on_received(key[0], key[1], t)


