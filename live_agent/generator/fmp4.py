"""Incremental decoder for the fragmented-MP4 stream of the vLLM-Omni realtime video endpoint.

The server sends one binary message per generated phase: the first carries the init segment (``ftyp`` +
``moov``), every message carries ``moof``/``mdat`` fragments of H.264 video and AAC audio. Each message is
demuxed on its own (the init segment is prepended) and its packets are decoded with persistent codec
contexts, so decoder state carries across messages. Video frames are counted in decode order (the
muxer's video pts are off by one frame after frame 0); audio pts is the absolute sample index (measured
locally on the server's own encoder, ``tests/data/vllm_omni_fmp4``: offset 0; only the first 1024 samples of
a stream are AAC priming silence).

Both encoders hold media back at a message boundary (x264 about 2 frames, AAC about 3-4 k samples,
measured locally), so a message's audio ends earlier than its video. ``take()`` releases frames only as far
as their audio has been decoded, which keeps each released chunk in A/V sync: the video is delayed by the
few held-back frames (about 0.1-0.2 s) rather than the audio lagging the lips.
"""

from __future__ import annotations

import io
from fractions import Fraction

import numpy as np


def split_init(data: bytes) -> tuple[bytes, bytes]:
    """(leading ftyp/moov boxes, rest) of an fMP4 message."""
    i = 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i:i + 4], "big")
        if data[i + 4:i + 8] not in (b"ftyp", b"moov") or size < 8:
            break
        i += size
    return data[:i], data[i:]


class FMP4StreamDecoder:
    def __init__(self, fps: float = 24.0, sample_rate: int = 32000) -> None:
        self.fps = float(fps)
        self.sample_rate = int(sample_rate)
        self._init = b""
        self._vdec = None
        self._adec = None
        self._frames: list[np.ndarray] = []  # decoded, not yet released; frame index of [0] is _vbase
        self._vbase = 0
        self._audio = np.zeros((0, 2), np.float32)  # decoded, not yet released; sample index of [0] is _abase
        self._abase = 0

    def samples_at(self, frame: int) -> int:
        return int(Fraction(frame) * self.sample_rate / Fraction(self.fps).limit_denominator(1000))

    def frame_at(self, sample: int) -> int:
        """Last frame boundary whose audio is complete at ``sample``."""
        return int(Fraction(sample) * Fraction(self.fps).limit_denominator(1000) / self.sample_rate)

    def push(self, data: bytes) -> None:
        """Decode one server message (blocking; call it off the event loop)."""
        import av

        init, _ = split_init(data)
        if init:
            self._init = init
        elif not self._init:
            raise ValueError("fMP4 stream starts without an init segment")
        blob = data if init else self._init + data
        with av.open(io.BytesIO(blob), format="mp4") as container:
            vstream = container.streams.video[0] if container.streams.video else None
            astream = container.streams.audio[0] if container.streams.audio else None
            if self._vdec is None and vstream is not None:
                self._vdec = av.CodecContext.create(vstream.codec_context.name, "r")
                self._vdec.extradata = vstream.codec_context.extradata
                self._vdec.thread_type = "NONE"  # no frame-threading delay: every packet decodes at once
            if self._adec is None and astream is not None:
                self._adec = av.CodecContext.create(astream.codec_context.name, "r")
                self._adec.extradata = astream.codec_context.extradata
                self._adec.sample_rate = astream.codec_context.sample_rate
                self._adec.layout = astream.codec_context.layout
            for packet in container.demux():
                if packet.size == 0 or packet.pts is None:
                    continue
                if packet.stream.type == "video":
                    # frames are counted, not placed by pts: the server's muxer labels frame i >= 1 with pts
                    # i + 1 (measured on the fixture); the stream has no reordering (pts == dts), so decode
                    # order is display order
                    for frame in self._vdec.decode(packet):
                        self._frames.append(frame.to_ndarray(format="rgb24"))
                elif packet.stream.type == "audio":
                    base = packet.stream.time_base
                    for frame in self._adec.decode(packet):
                        pts = packet.pts if frame.pts is None else frame.pts
                        sample_index = int(round(float(pts * base) * self.sample_rate))
                        pcm = frame.to_ndarray()  # planar float: [channels, samples]
                        if pcm.ndim == 1:
                            pcm = pcm[None, :]
                        pcm = pcm.T.astype(np.float32)
                        if pcm.shape[1] == 1:
                            pcm = np.repeat(pcm, 2, axis=1)
                        self._put_audio(sample_index, pcm[:, :2])

    def flush(self) -> None:
        """End of stream: drain the frame the video decoder still holds (it returns frames one packet late)."""
        if self._vdec is not None:
            for frame in self._vdec.decode(None):
                self._frames.append(frame.to_ndarray(format="rgb24"))

    def _put_audio(self, index: int, pcm: np.ndarray) -> None:
        end = self._abase + len(self._audio)
        if index + len(pcm) <= end:
            return
        if index < end:
            pcm = pcm[end - index:]
            index = end
        if index > end:
            pcm = np.concatenate([np.zeros((index - end, 2), np.float32), pcm])
        self._audio = np.concatenate([self._audio, pcm]) if len(self._audio) else pcm

    @property
    def decoded_frames(self) -> int:
        return self._vbase + len(self._frames)

    def take(self, final: bool = False) -> tuple[int, np.ndarray | None, np.ndarray]:
        """Release the frames whose audio is complete (all of them when ``final``).

        Returns ``(frame_start, video [T,H,W,3] uint8 or None, audio [S,2] float32)``; the audio covers exactly
        the released frames on the fps/sample-rate timeline (zero-padded only at the final flush).
        """
        v_end = self.decoded_frames
        a_end = self._abase + len(self._audio)
        edge = v_end if final else min(v_end, self.frame_at(a_end))
        start = self._vbase
        n = max(0, edge - start)
        if n == 0:
            return start, None, np.zeros((0, 2), np.float32)
        video = np.stack(self._frames[:n])
        del self._frames[:n]
        self._vbase += n
        s0, s1 = self.samples_at(start), self.samples_at(start + n)
        lo, hi = s0 - self._abase, s1 - self._abase
        audio = self._audio[max(0, lo):max(0, hi)]
        if lo < 0:  # released frames start before any decoded audio (stream start): silence
            audio = np.concatenate([np.zeros((min(-lo, s1 - s0), 2), np.float32), audio])
        if len(audio) < s1 - s0:
            audio = np.concatenate([audio, np.zeros((s1 - s0 - len(audio), 2), np.float32)])
        drop = max(0, hi)
        self._audio = self._audio[drop:]
        self._abase += drop
        return start, video, np.ascontiguousarray(audio, dtype=np.float32)


__all__ = ["FMP4StreamDecoder", "split_init"]
