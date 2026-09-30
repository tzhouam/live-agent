"""Audio and video stay aligned through the server's own media paths: the session recording (ffmpeg, AAC) and the
chunk -> page wire format. A white flash and an audio click are placed at the same instants; each path must keep them
within a millisecond or two (lip sync is judged in tens of milliseconds)."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from live_agent.types import Chunk

av = pytest.importorskip("av")

FPS, SR = 24.0, 32000
SHAPE = [34, 34, 34, 17]  # one TaoMate-H3 request: four phases of frames at 24 fps, 32 kHz stereo audio
# (chunk, frame within the chunk). Not the final frame: the recorder's final mux (-shortest) may trim the last
# tens of ms of audio at the very end of a recording, which is a session-end effect, not a sync one.
FLASHES = [(0, 10), (1, 5), (2, 30), (3, 12)]


def _chunks():
    """Audio lengths as the stream decoder releases them: samples_at(end) - samples_at(start) on one timeline."""
    out, start = [], 0
    for k, n in enumerate(SHAPE):
        video = np.full((n, 64, 64, 3), 30, np.uint8)
        audio = np.zeros((int(start + n) * SR // int(FPS) - start * SR // int(FPS), 2), np.float32)
        for c, f in FLASHES:
            if c == k:
                video[f] = 250
                s = (start + f) * SR // int(FPS) - start * SR // int(FPS)
                audio[s:s + 64] = 0.9  # a 2 ms click at the flash frame's start
        out.append(Chunk(request_index=0, chunk_index=k, n_frames=n, fps=FPS, video=video, audio=audio, sample_rate=SR))
        start += n
    return out


def _expected_times():
    return [(sum(SHAPE[:c]) + f) / FPS for c, f in FLASHES]


def _flash_and_click_times(path: Path):
    with av.open(str(path)) as cont:
        vs = cont.streams.video[0]
        flashes = [float(fr.pts * vs.time_base) for fr in cont.decode(vs) if fr.to_ndarray(format="gray").mean() > 150]
    with av.open(str(path)) as cont:
        a = cont.streams.audio[0]
        clicks, prev = [], 0.0
        for fr in cont.decode(a):
            x = np.abs(fr.to_ndarray()).max(axis=0)
            t0 = float(fr.pts * a.time_base)
            for i in np.flatnonzero(x > 0.4):
                t = t0 + i / a.rate
                if t - prev > 0.1:
                    clicks.append(t)
                prev = max(prev, t) if clicks else prev
    return flashes, clicks


@pytest.mark.skipif(not shutil.which("ffmpeg") and not Path("/usr/bin/ffmpeg").exists(), reason="needs ffmpeg")
def test_the_session_recording_keeps_flash_and_click_together(tmp_path):
    from live_agent.sim import Recorder

    rec = Recorder(tmp_path / "s.mp4", ffmpeg=shutil.which("ffmpeg") or "/usr/bin/ffmpeg")
    for ch in _chunks():
        rec._write(ch)  # synchronous path of write()
    rec.close()
    flashes, clicks = _flash_and_click_times(tmp_path / "s.mp4")
    expected = _expected_times()
    assert len(flashes) == len(expected) and len(clicks) == len(expected), (flashes, clicks)
    for e, f, c in zip(expected, flashes, clicks):
        assert abs(f - e) < 1e-3  # the flash frame is where it was put
        assert abs(c - e) < 2e-3, (e, c)  # and so is the click: the AAC encoder delay is hidden by the edit list


def test_the_transport_payload_keeps_the_click_on_its_flash_frame():
    """Through the real WSTransport.send_chunk: the header, the H.264 segment and the PCM the page receives. Decoded
    as the page does (frame i shown at start + i / fps, PCM sample j at start + j / sample_rate), every click is at
    its flash frame and each chunk's audio lasts exactly its frames (the page schedules chunk k+1 at start + duration)."""
    import asyncio
    import io
    import json

    from live_agent.server.app import WSTransport
    from live_agent.types import BlockScript, CanonProfile

    class FakeWS:
        def __init__(self):
            self.msgs = []

        async def send_text(self, t):
            self.msgs.append(json.loads(t))

        async def send_bytes(self, b):
            self.msgs.append(bytes(b))

    ws = FakeWS()
    tr = WSTransport(ws, None, video_codec="h264")
    script = BlockScript(request_index=0, plan_version=0, canon=CanonProfile(persona_id="p", subject="", scene="", camera="",
                                                                         voice=""), action="", transcript="你好")

    async def go():
        for ch in _chunks():
            await tr.send_chunk(ch, script)
    asyncio.run(go())
    i, found = 0, 0
    while i < len(ws.msgs):
        head, seg, pcm = ws.msgs[i], ws.msgs[i + 1], ws.msgs[i + 2]
        i += 3
        assert head["type"] == "chunk" and head["codec"] == "h264" and sum(head["sizes"]) == len(seg)
        with av.open(io.BytesIO(seg), format="h264") as c:
            frames = [f.to_ndarray(format="gray").mean() for f in c.decode(video=0)]
        pcm = np.frombuffer(pcm, np.int16)
        assert len(frames) == head["n_frames"] and head["duration"] == head["n_frames"] / head["fps"]
        assert abs(len(pcm) / head["sample_rate"] - head["duration"]) < 1 / head["sample_rate"]
        flash = [k for k, m in enumerate(frames) if m > 150]
        loud = np.flatnonzero(np.abs(pcm) > 20000)
        assert len(flash) == (1 if len(loud) else 0)
        if flash:
            found += 1
            assert abs(loud[0] / head["sample_rate"] - flash[0] / head["fps"]) < 1 / head["sample_rate"] + 1e-9
    assert found == len(FLASHES)


def test_the_page_wire_format_keeps_audio_on_the_frame_timeline():
    """Each chunk's PCM covers its frames to within one sample (the page schedules chunk k at the previous start plus
    n_frames / fps and maps frame i to start + i / fps, so a click stays with its flash)."""
    from live_agent.server.app import to_pcm16

    start = 0
    for ch in _chunks():
        pcm = np.frombuffer(to_pcm16(ch.audio, int(ch.duration_s * SR)), np.int16)
        assert abs(len(pcm) - ch.n_frames / FPS * SR) < 1  # no padding or trimming that would shift the clock
        for c, f in FLASHES:
            if c == ch.chunk_index:
                click = np.flatnonzero(np.abs(pcm) > 20000)[0] / SR
                assert abs(click - f / FPS) < 1 / SR + 1e-9  # where the page will show the flash frame
        start += ch.n_frames
