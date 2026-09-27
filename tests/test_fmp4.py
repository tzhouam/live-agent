"""The fMP4 decoder against chunks made by vLLM-Omni's own streaming encoder (tests/data/vllm_omni_fmp4)."""

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("av")

from live_agent.generator.fmp4 import FMP4StreamDecoder, split_init  # noqa: E402

DATA = Path(__file__).parent / "data" / "vllm_omni_fmp4"
MANIFEST = json.loads((DATA / "manifest.json").read_text())


def _grey(frame_index):
    return (frame_index * 9) % 200 + 20  # how the fixture paints frame i


def test_first_message_carries_the_init_segment_only_once():
    init, rest = split_init((DATA / "chunk0.m4s").read_bytes())
    assert init and rest
    assert split_init((DATA / "chunk1.m4s").read_bytes())[0] == b""


def test_released_chunks_are_in_order_and_av_aligned():
    dec = FMP4StreamDecoder(fps=24, sample_rate=32000)
    total_frames = sum(c["num_frames"] for c in MANIFEST["chunks"])
    released = []
    for c in MANIFEST["chunks"]:
        dec.push((DATA / c["file"]).read_bytes())
        start, video, audio = dec.take()
        assert video is not None and len(video) > 0  # every message releases something
        assert start == sum(len(v) for _, v, _ in released)  # contiguous
        assert len(audio) == dec.samples_at(start + len(video)) - dec.samples_at(start)
        released.append((start, video, audio))
        # frames are held back only as far as the encoders held media (a few frames, never a whole chunk)
        assert c["frame_start"] + c["num_frames"] - (start + len(video)) <= 6
    dec.push((DATA / "trailer.m4s").read_bytes())
    dec.flush()
    start, video, audio = dec.take(final=True)
    released.append((start, video, audio))
    frames = np.concatenate([v for _, v, _ in released if v is not None])
    # the server's encoder emits 152 video packets for 153 frames: its close() drops the last frame (an upstream
    # quirk at session end only; a live session never closes mid-stream)
    assert len(frames) == total_frames - 1
    greys = frames[:, 80, 48, 0].astype(int)
    expected = np.array([_grey(i) for i in range(len(frames))])
    assert np.max(np.abs(greys - expected)) <= 3  # every frame lands at its own index (h264 rounding only)


def test_audio_is_continuous_across_message_boundaries():
    dec = FMP4StreamDecoder(fps=24, sample_rate=32000)
    parts = []
    for c in MANIFEST["chunks"]:
        dec.push((DATA / c["file"]).read_bytes())
        parts.append(dec.take()[2])
    x = np.concatenate(parts)[:, 0]
    n = np.arange(2048, len(x))  # after AAC priming (1024 samples)
    ref = MANIFEST["amplitude"] * np.sin(2 * np.pi * MANIFEST["tone_hz"] * n / MANIFEST["sample_rate"])
    assert np.sqrt(np.mean((x[n] - ref) ** 2)) < 0.01  # sample-accurate: the tone's phase never jumps
