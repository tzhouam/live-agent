"""Wire video for the demo page: H.264 segments (WebCodecs) with JPEG fallback."""

import asyncio
import json
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("av")

from live_agent.backend.transport import WSTransport, encode_h264, encode_jpeg  # noqa: E402
from live_agent.types import Chunk  # noqa: E402


def _frames(n=34, h=864, w=480):
    rng = np.random.default_rng(0)
    base = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    return np.stack([np.roll(base, 4 * i, axis=1) for i in range(n)])  # a moving picture


def test_h264_segment_is_self_contained_one_access_unit_per_frame_and_smaller():
    import av

    frames = _frames()
    seg, sizes = encode_h264(frames)
    assert len(sizes) == len(frames) and sum(sizes) == len(seg)
    assert seg.startswith(b"\x00\x00\x00\x01")  # Annex-B, parameter sets + IDR first
    dec = av.CodecContext.create("h264", "r")  # a fresh decoder: decodable without earlier chunks
    n, off = 0, 0
    for size in sizes:
        n += len(dec.decode(av.Packet(seg[off:off + size])))
        off += size
    n += len(dec.decode(None))
    assert n == len(frames)
    assert len(seg) < sum(len(encode_jpeg(f)) for f in frames)


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def send_bytes(self, data):
        self.sent.append(bytes(data))


def _send(codec):
    ws = FakeWS()
    transport = WSTransport(ws, None, video_codec=codec)
    chunk = Chunk(request_index=0, chunk_index=0, n_frames=6, fps=24.0, video=_frames(6, 64, 48),
                  audio=np.zeros((8000, 2), np.float32), sample_rate=32000)
    asyncio.run(transport.send_chunk(chunk, SimpleNamespace(transcript="")))  # send_chunk reads only the line
    return ws.sent


def test_transport_sends_one_h264_segment_or_n_jpegs_then_pcm():
    h264 = _send("h264")
    assert h264[0]["codec"] == "h264" and len(h264[0]["sizes"]) == 6 and len(h264) == 3  # header, segment, pcm
    jpeg = _send("jpeg")
    assert jpeg[0]["codec"] == "jpeg" and "sizes" not in jpeg[0] and len(jpeg) == 1 + 6 + 1
