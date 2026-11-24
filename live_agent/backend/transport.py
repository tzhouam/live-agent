"""WebSocket media encoding, presentation acknowledgements and panel events.

The binary protocol is preserved across the frontend proxy; the browser's audio
output clock is mapped to server monotonic time using ping samples.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import replace
from fractions import Fraction
import json
import logging
from pathlib import Path

import numpy as np
from fastapi import WebSocket

from live_agent.backend.avatar import (AvatarCapture, GESTURES, INTENTS, MAX_PER_CHUNK,
                                       MAX_PER_REQUEST, MODEL, decode_capture, finite_number)
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
                "plan", "note", "adaptive", "depth", "figure", "exercise", "concept", "correct", "skipped", "misconception",
                "mastery", "profile", "changed", "options", "question", "option_texts", "question_html", "option_html", "topic")


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

    def __init__(self, ws: WebSocket, record_path: Path | None = None, video_codec: str = "jpeg",
                 avatar_mesh: bool = False, avatar_video_frames: bool = False):
        self.ws = ws
        self.avatar_mesh = avatar_mesh
        self.avatar_renderer = "mesh" if avatar_mesh else "video"
        self.avatar_video_frames = bool(avatar_mesh and avatar_video_frames is True)
        self._standby_frame_indices: dict[tuple[int, int], tuple[int, ...]] = {}
        self._announced: dict[tuple[int, int], tuple[int, Chunk]] = {}
        self._visual_sources: dict[tuple[int, int], str] = {}
        self._completed: set[tuple[int, int]] = set()
        self._avatar_captures: dict[tuple[int, int], list[AvatarCapture]] = {}
        self._capture_pending: set[tuple[int, int]] = set()
        self._capture_last_tp: dict[tuple[int, int], float] = {}
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
        native_n_frames = len(frames)
        video_frame_indices = None
        if self.avatar_video_frames and self.avatar_renderer == "mesh" and chunk.video is not None \
                and native_n_frames == chunk.n_frames and native_n_frames:
            # Keep a low-rate standby picture while the actual teacher is rendered
            # in the browser. Logical media timing and original recording pixels stay intact.
            stride = max(1, int(np.ceil(chunk.fps / 2)))  # configured standby maximum: 2 fps
            video_frame_indices = tuple(range(0, native_n_frames, stride))
            frames = frames[list(video_frame_indices)]
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
                "n_frames": native_n_frames, "fps": chunk.fps, "sample_rate": chunk.sample_rate,
                "duration": chunk.duration_s,  # media duration (may differ from n_frames / fps)
                "width": int(w), "height": int(h), "transcript": script.transcript,
                "codec": "h264" if segment is not None else "jpeg"}
            if video_frame_indices is not None:
                header["video_frames"] = len(video_frame_indices)
                header["video_frame_indices"] = video_frame_indices
                self._standby_frame_indices[(chunk.request_index, chunk.chunk_index)] = video_frame_indices
            if self.avatar_mesh:
                gesture = chunk.meta.get("avatar_gesture", "idle")
                header["avatar"] = {"renderer": "mesh", "model": MODEL, "epoch": epoch,
                                    "gesture": gesture if gesture in GESTURES else "idle",
                                    "request_time_s": float(chunk.meta.get("request_offset_s", 0.0)),
                                    "request_duration_s": float(chunk.meta.get("request_duration_s", chunk.duration_s)),
                                    "motion_time_s": float(chunk.meta.get("motion_time_s", 0.0))}
                self._announced[(chunk.request_index, chunk.chunk_index)] = (epoch, chunk)
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
        self._starts.clear()
        self._announced.clear()
        self._standby_frame_indices.clear()
        self._visual_sources.clear()
        self._completed.clear()
        self._avatar_captures.clear()
        self._capture_last_tp.clear()
        self._capture_pending.clear()
        message = {"type": "stop"}
        if self.avatar_mesh:
            message["epoch"] = self._epoch
        await self.ws.send_text(json.dumps(message))

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

    def avatar_status(self) -> dict:
        return {"renderer": "mesh", "model": MODEL, "epoch": self._epoch,
                "supported_capabilities": sorted(INTENTS)}

    def on_avatar_renderer(self, msg: dict) -> bool:
        """Fallback is permanent for this session; mid-chunk evidence becomes unknown."""
        if not self.avatar_mesh or msg.get("renderer") != "video" or type(msg.get("epoch", self._epoch)) is not int or msg.get("epoch", self._epoch) != self._epoch:
            return False
        if self.avatar_renderer == "video":
            return True
        self.avatar_renderer = "video"
        for key in self._starts:
            if self._visual_sources.get(key) == "mesh":
                self._visual_sources[key] = "mixed"
        if self.orchestrator is not None:
            from live_agent.types import EventType

            self.orchestrator.log.emit(EventType.AUDIT, now(), where="avatar_renderer", renderer="video",
                                       previous_renderer="mesh", model=MODEL)
        return True

    async def on_avatar_frame(self, msg: dict) -> bool:
        """Accept only a current, playing mesh chunk; decode outside the event loop."""
        if not self.avatar_mesh or self.avatar_renderer != "mesh" or msg.get("renderer") != "mesh" \
                or msg.get("model") != MODEL or msg.get("mime") != "image/jpeg" \
                or type(msg.get("epoch")) is not int or msg.get("epoch") != self._epoch:
            return False
        if any(type(msg.get(field)) is not int for field in ("request", "chunk", "frame")):
            return False
        key = (msg["request"], msg["chunk"])
        announced = self._announced.get(key)
        if announced is None or announced[0] != self._epoch or key not in self._starts \
                or self._visual_sources.get(key) != "mesh" or key in self._capture_pending:
            return False
        captures = self._avatar_captures.get(key, [])
        count = sum(len(values) for (request, _), values in self._avatar_captures.items() if request == key[0])
        if len(captures) >= MAX_PER_CHUNK or count >= MAX_PER_REQUEST:
            return False
        ch = announced[1]
        media_time, tp, frame = msg.get("request_time_s"), msg.get("tp"), msg["frame"]
        offset = float(ch.meta.get("request_offset_s", 0.0))
        if not finite_number(media_time) or not finite_number(tp) or tp < 0 or not 0 <= frame < ch.n_frames:
            return False
        if not offset <= media_time <= offset + ch.duration_s \
                or abs(media_time - (offset + frame / ch.fps)) > max(0.12, 2 / ch.fps):
            return False
        if captures and (media_time <= captures[-1].media_time or frame <= captures[-1].frame):
            return False
        if tp <= self._capture_last_tp.get(key, -float("inf")):
            return False
        t_capture = self._to_server(msg)
        if self.clock_offset_s is not None and not -0.5 <= now() - t_capture <= 3.0:
            return False  # delayed/stale client pictures are not current evidence
        self._capture_pending.add(key)
        epoch = self._epoch
        try:
            pixels = await asyncio.to_thread(decode_capture, msg.get("image"))
        finally:
            self._capture_pending.discard(key)
        if pixels is None or epoch != self._epoch or key not in self._starts \
                or self._visual_sources.get(key) != "mesh":
            return False
        if captures and pixels.shape != captures[0].pixels.shape:
            return False
        self._avatar_captures.setdefault(key, []).append(
            AvatarCapture(frame, float(media_time), t_capture,
                          "client_mapped" if self.clock_offset_s is not None else "server_arrival", pixels))
        self._capture_last_tp[key] = float(tp)
        return True

    def visual_evidence(self, request: int, chunks: list[Chunk], painted: dict) -> tuple[list[Chunk], str | None]:
        """Replace mesh frames with browser captures, preserving audio for speech QC.

        A chunk which switched renderer part way through cannot be reconstructed
        honestly. It and missing captures abstain rather than reuse puppet pixels.
        """
        out, issue = [], None
        for ch in chunks:
            key = (request, ch.chunk_index)
            source = self._visual_sources.get(key, "mesh" if self.avatar_renderer == "mesh" else "unknown")
            if source == "mesh":
                captures = self._avatar_captures.get(key, [])
                # Captures with a common canvas resolution can be stacked as VLM input.
                frames = np.stack([capture.pixels for capture in captures]) if captures else None
                out.append(replace(ch, video=frames, meta={**ch.meta, "visual_source": "browser_mesh",
                                   "avatar_capture_times": [capture.media_time for capture in captures],
                                   "avatar_capture_timestamps": [capture.t_capture for capture in captures],
                                   "avatar_capture_clock_sources": [capture.clock_source for capture in captures]}))
                if not captures:
                    issue = "avatar_frames_missing"
            elif source == "video":
                indices = painted.get(key)
                standby = self._standby_frame_indices.get(key)
                if standby is not None:
                    # A buffered standby chunk may be used after WebGL fails. Only
                    # its transmitted source pictures can be presented evidence.
                    indices = [i for i in (indices or []) if type(i) is int and i in standby]
                if ch.video is not None and indices is not None:
                    keep = sorted(i for i in set(indices) if 0 <= i < len(ch.video))
                    out.append(replace(ch, video=ch.video[keep], meta={**ch.meta, "visual_source": "server_video"}))
                else:
                    out.append(replace(ch, meta={**ch.meta, "visual_source": "server_video"}))
            else:
                issue = "avatar_renderer_changed_during_chunk" if source == "mixed" else "avatar_presentation_unknown"
                out.append(replace(ch, video=None, meta={**ch.meta, "visual_source": source}))
        return out, issue

    def avatar_evidence_time(self, request: int) -> float | None:
        keys = [key for key in self._visual_sources if key[0] == request]
        if not keys:
            return None
        key = max(keys, key=lambda key: key[1])
        if self._visual_sources[key] != "mesh":
            return None  # a later video chunk uses its actual painted-frame timestamp
        times = [capture.t_capture for capture in self._avatar_captures.get(key, [])]
        return max(times) if times else None

    def evict_request(self, request: int) -> None:
        self._completed.difference_update(key for key in tuple(self._completed) if key[0] == request)
        for mapping in (self._announced, self._standby_frame_indices, self._visual_sources,
                        self._avatar_captures, self._capture_last_tp):
            for key in [key for key in mapping if key[0] == request]:
                mapping.pop(key, None)

    def on_client_message(self, msg: dict) -> None:
        t = self._to_server(msg)
        if self.avatar_mesh and any(type(msg.get(field)) is not int for field in ("request", "chunk")):
            return
        key = (int(msg.get("request", -1)), int(msg.get("chunk", -1)))
        if self.avatar_mesh:
            announced = self._announced.get(key)
            if announced is None or announced[0] != self._epoch or type(msg.get("epoch")) is not int or msg.get("epoch") != self._epoch:
                return
            if msg["type"] in ("chunk_start", "chunk_end"):
                if key in self._completed or (msg["type"] == "chunk_start" and key in self._starts) \
                        or (msg["type"] == "chunk_end" and key not in self._starts):
                    return
                renderer = msg.get("renderer")
                if renderer == "mesh" and msg.get("model") == MODEL and self.avatar_renderer == "mesh":
                    source = "mesh"
                elif renderer == "video" and self.avatar_renderer == "video":
                    source = "video"
                else:
                    source = "unknown"
                previous = self._visual_sources.get(key)
                self._visual_sources[key] = source if previous is None or previous == source else "mixed"
        if msg["type"] == "chunk_start":
            self._starts[key] = t
        elif msg["type"] == "chunk_end" and self.orchestrator is not None:
            if self.avatar_mesh:
                self._completed.add(key)
            ch = self._sent.pop(key, None)
            if ch is not None and self.recorder is not None:
                self.recorder.write(ch)  # background-thread encoding
            painted = msg.get("painted")
            standby = self._standby_frame_indices.get(key)
            if standby is not None:
                painted = [i for i in (painted or []) if type(i) is int and i in standby]
            t_paint = (self._to_server({"tp": msg["tp_last_paint"]}) if msg.get("tp_last_paint") is not None
                       and self.clock_offset_s is not None else None)
            self.orchestrator.on_presented(key[0], key[1], self._starts.pop(key, t), t,
                                           painted=[int(i) for i in painted] if painted is not None else None,
                                           t_last_paint=t_paint)
        elif msg["type"] == "chunk_received" and self.orchestrator is not None and self.clock_offset_s is not None:
            self.orchestrator.on_received(key[0], key[1], t)


