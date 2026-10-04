"""Puppet generator (CPU skeleton rig, D-047): chunk protocol, audio/mouth coupling,
intent mapping, TTS clients. Everything runs offline; the synth voice stands in for speech."""

from __future__ import annotations

import asyncio
import io
import json
import wave
from pathlib import Path

import numpy as np
import pytest

from live_agent.generator.puppet import (ANIMATIONS, PuppetGenerator, _ANIM_BY_INTENT,
                                         mouth_track, render_chunk, render_frame)
from live_agent.orchestrator import audio_onset_s
from live_agent.prompt.h3_compiler import compile_prompt, extract_dialogue
from live_agent.tts import EdgeTTS, SynthTTS, TTS_RATE, UrlTTS, make_tts, synth_speech
from live_agent.types import BlockScript, CanonProfile, now

ROOT = Path(__file__).resolve().parents[1]
TEACHER = ROOT / "configs" / "persona_teacher"
CANON = CanonProfile(persona_id="t", subject="a friendly teacher", scene="a bright classroom",
                     camera="medium close-up", voice="a warm Mandarin voice")


def make_prompt(action: str = "", line: str = "", k: int = 0) -> str:
    s = BlockScript(request_index=k, plan_version=1, canon=CANON, action=action, transcript=line)
    return compile_prompt(s)


def teacher_caps() -> list[tuple[str, str]]:
    data = json.loads((TEACHER / "capabilities.json").read_text(encoding="utf-8"))
    return [(c["phrase"], c["intent"]) for c in data["capabilities"]]


def gen(**kw) -> PuppetGenerator:
    kw.setdefault("capabilities", teacher_caps())
    kw.setdefault("size", (320, 180))  # small frames keep the test fast; the rig scales
    return PuppetGenerator(**kw)


async def collect(g: PuppetGenerator, n_chunks: int, timeout: float = 20.0) -> list:
    out = []

    async def pull():
        async for ch in g.chunks():
            out.append(ch)
            if len(out) >= n_chunks:
                return

    await asyncio.wait_for(pull(), timeout)
    return out


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- protocol


def test_chunk_layout_audio_and_frame_contract():
    async def main():
        g = gen()
        await g.start()
        try:
            await g.submit(0, make_prompt(line="同学们好，今天学习加法。"))
            chunks = await collect(g, 4)
            assert [c.chunk_index for c in chunks] == [0, 1, 2, 3]
            assert [c.n_frames for c in chunks] == [39, 34, 34, 17]  # TaoMate-H3 first-request layout
            sr, fps = g.info.sample_rate, g.info.fps
            for c in chunks:
                assert c.video.shape == (c.n_frames, g.info.height, g.info.width, 3)
                assert c.video.dtype == np.uint8
                assert c.audio.dtype == np.float32 and c.audio.shape[1] == 2
                assert c.audio.shape[0] == int(c.n_frames / fps * sr)
                assert c.duration_s == pytest.approx(c.n_frames / fps)
                assert c.meta["prompt"].startswith("integrated_multimodal_description:")
            await g.submit(1, make_prompt(line="好", k=1))
            later = await collect(g, 4)
            assert [c.n_frames for c in later] == [34, 34, 34, 17]
            # timings: the TTS call is the teacher phase; drawing is the student phase
            tm = {t.request_index: t for t in g.timings}
            for k in (0, 1):
                t = tm[k]
                assert t.t_lock <= t.t_teacher_start <= t.t_teacher_done <= t.t_student_start
                assert t.t_student_start <= t.t_first_chunk <= t.t_done
                assert t.teacher_s is not None and t.teacher_s >= 0.0
            with pytest.raises(ValueError):
                await g.submit(5, make_prompt(k=5))  # requests are strictly sequential
        finally:
            await g.close()

    run(main())


def test_reset_bumps_epoch_and_silent_requests_stay_silent():
    async def main():
        g = gen()
        await g.start()
        try:
            await g.submit(0, make_prompt(line="你好"))
            first = await collect(g, 1)
            assert first[0].meta["session"] == 0
            await g.reset()
            await g.submit(1, make_prompt(k=1))  # no line, no action: a silent filler request
            chunks = await collect(g, 4)
            # chunks of the new epoch carry it; any trailing request-0 chunk keeps the old epoch
            # (same mid-request window as the mock) and is dropped by SessionView
            assert any(c.request_index == 1 and c.meta["session"] == 1 for c in chunks)
            assert all(c.meta["session"] == 1 for c in chunks if c.request_index == 1)
            assert all(float(np.abs(c.audio).max()) == 0.0
                       for c in chunks if c.request_index == 1)  # no line: silent filler
        finally:
            await g.close()

    run(main())


def test_tts_failure_surfaces_to_the_chunk_consumer():
    class Boom:
        async def synthesize(self, text):
            raise RuntimeError("tts down")

    async def main():
        g = gen(tts=Boom())
        await g.start()
        try:
            await g.submit(0, make_prompt(line="你好"))

            async def pull():
                async for _ in g.chunks():
                    pass

            with pytest.raises(RuntimeError, match="tts down"):
                await asyncio.wait_for(pull(), 10)
        finally:
            await g.close()

    run(main())


# --------------------------------------------------------------------------- voice and mouth


def test_synth_voice_is_deterministic_and_audible():
    a = synth_speech("同学们好，今天我们学习加法。")
    b = synth_speech("同学们好，今天我们学习加法。")
    assert np.array_equal(a, b)
    assert not np.array_equal(a, synth_speech("另一句话"))
    assert len(synth_speech("")) == 0
    assert np.abs(a).max() > 0.05  # well above the 0.02 RMS onset threshold
    t = np.arange(len(a)) / TTS_RATE
    speech = a[t > 0.06]
    rms = float(np.sqrt(np.mean(np.square(speech))))
    assert rms > 0.02


def test_mouth_track_follows_the_audio_envelope():
    a = synth_speech("你好，同学们。")
    m = mouth_track(a, 48, 24.0, TTS_RATE)
    assert len(m) == 48
    assert m[0] < 0.3  # the 50 ms onset lead-in stays (near-)closed; smoothing smears one frame
    assert float(m.max()) > 0.3  # opens during syllables
    assert float(m.min()) >= 0.0
    assert float(mouth_track(np.zeros(1000, dtype=np.float32), 10, 24.0, TTS_RATE).max()) == 0.0


def test_mouth_and_pose_change_the_drawn_frames():
    f_closed = render_frame(320, 180, _pose(mouth_open=0.0))
    f_open = render_frame(320, 180, _pose(mouth_open=1.0))
    assert not np.array_equal(f_closed, f_open)
    f_drink = render_chunk(320, 180, 6, 1.0, 1.0 / 24, 5.0, "drink", np.ones(6, dtype=np.float32) * 0.1, 0.3)
    f_idle = render_chunk(320, 180, 6, 1.0, 1.0 / 24, 5.0, "idle", np.ones(6, dtype=np.float32) * 0.1, 0.3)
    assert not np.array_equal(f_drink, f_idle)  # the rig performs the mapped animation
    assert f_drink.shape == (6, 180, 320, 3)


def _pose(**kw):
    from live_agent.generator.puppet import Pose
    return Pose(**kw)


def test_generated_speech_has_a_measurable_onset():
    async def main():
        g = gen()
        await g.start()
        try:
            await g.submit(0, make_prompt(line="同学们好，今天学习加法。"))
            chunks = await collect(g, 4)
            onset = audio_onset_s(chunks[0])
            assert onset is not None and onset < 0.5  # speech energy starts early in request 0
            assert extract_dialogue(chunks[0].meta["prompt"]) == "同学们好，今天学习加法。"
        finally:
            await g.close()

    run(main())


# --------------------------------------------------------------------------- intent -> animation


def test_every_teacher_capability_maps_to_a_performed_animation():
    g = gen()
    for phrase, intent in teacher_caps():
        anim = g.detect_animation(make_prompt(action=phrase))
        assert anim == _ANIM_BY_INTENT[intent], f"{intent} -> {anim}"
        assert anim in ANIMATIONS


def test_unknown_or_missing_action_falls_back_to_idle():
    g = gen()
    assert g.detect_animation(make_prompt(action="she suddenly flies out of the window.")) == "idle"
    assert g.detect_animation(make_prompt()) == "idle"
    assert g.detect_animation("not a prompt at all") == "idle"


# --------------------------------------------------------------------------- TTS clients


def wav_bytes(samples: np.ndarray, rate: int) -> bytes:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def test_edge_tts_decodes_and_resamples():
    src = (0.2 * np.sin(2 * np.pi * 220 * np.arange(16000) / 16000)).astype(np.float32)

    async def speak(text, voice):
        assert voice == "zh-CN-XiaoxiaoNeural" and text == "你好"
        return wav_bytes(src, 16000)

    out = asyncio.run(EdgeTTS(speak=speak).synthesize("你好"))
    assert out.dtype == np.float32 and len(out) == pytest.approx(32000, rel=0.02)  # 1 s at 32 kHz


def test_url_tts_posts_openai_compatible_speech_request():
    src = np.zeros(8000, dtype=np.float32)
    seen = {}

    async def post(url, headers, payload):
        seen.update(url=url, headers=headers, payload=payload)
        return wav_bytes(src, 16000)

    tts = UrlTTS(base_url="http://tts.example/v1", model="tts-1", voice="alloy",
                 api_key="k", post=post)
    out = asyncio.run(tts.synthesize("同学们好"))
    assert seen["url"] == "http://tts.example/v1/audio/speech"
    assert seen["headers"]["Authorization"] == "Bearer k"
    assert seen["payload"]["model"] == "tts-1" and seen["payload"]["input"] == "同学们好"
    assert seen["payload"]["voice"] == "alloy"
    assert out.dtype == np.float32 and len(out) == pytest.approx(16000, rel=0.02)


def test_make_tts_validates_its_options():
    assert isinstance(make_tts("synth"), SynthTTS)
    with pytest.raises(ValueError):
        make_tts("url")  # a remote TTS needs its base url
    with pytest.raises(ValueError):
        make_tts("piper")  # and piper needs the .onnx voice path
    with pytest.raises(ValueError):
        make_tts("nope")


def test_from_args_loads_persona_capabilities():
    import argparse

    args = argparse.Namespace(config=str(TEACHER), extra=["--puppet-tts", "synth"])
    g = PuppetGenerator.from_args(args)
    assert len(g._caps) == 17  # the teacher manifest
    assert isinstance(g.tts, SynthTTS)
