"""Puppet generator (CPU skeleton rig, D-047): chunk protocol, audio/mouth coupling,
intent mapping, TTS clients. Everything runs offline; the synth voice stands in for speech."""

from __future__ import annotations

import asyncio
import io
import json
import math
import wave
from pathlib import Path

import numpy as np
import pytest

from live_agent.generator.puppet import (ANIMATIONS, Pose, PuppetGenerator, _ANIM_BY_INTENT,
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
    kw.setdefault("speech_timing", "fixed")  # explicit legacy layout checks
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


def _facial_box(name):
    """Locate the authored facial region in the neutral portrait, wherever the rig moves it."""
    from live_agent.generator.puppet_art import _scaled_art

    rig, _, _, _, _, _, _, _, boxes, *_ = _scaled_art(480, 864)
    x = round(rig["bust_position"][0] - rig["bust_size"][0] / 2)
    y = round(rig["bust_position"][1])
    a, b, c, d = boxes[name]
    return x + a, y + b, x + c, y + d


def _assert_changes_inside(a, b, bounds):
    changed = np.any(a != b, axis=2)
    y, x = np.where(changed)
    assert len(x), "the expression must be visible"
    x0, y0, x1, y1 = bounds
    assert x.min() >= x0 and x.max() < x1
    assert y.min() >= y0 and y.max() < y1


def test_vtuber_expression_does_not_change_the_hair_or_scene():
    """Speaking/blinking replace only facial patches, avoiding whole-sprite jitter."""
    neutral = render_frame(480, 864, _pose())
    speaking = render_frame(480, 864, _pose(mouth_open=1.0))
    blinking = render_frame(480, 864, _pose(eye_close=1.0))
    _assert_changes_inside(neutral, speaking, _facial_box("mouth"))
    _assert_changes_inside(neutral, blinking, _facial_box("eyes"))


def test_vtuber_assets_are_cached_and_rendering_preserves_the_cached_art(monkeypatch):
    from live_agent.generator import puppet_art

    neutral = render_frame(480, 864, _pose())

    def unexpected_read(*args, **kwargs):
        raise AssertionError("warm rendering must not reopen artwork files")

    monkeypatch.setattr(puppet_art.Image, "open", unexpected_read)
    render_frame(480, 864, _pose(head_tilt=0.2, mouth_open=1.0, r_sh=1.2))
    assert np.array_equal(render_frame(480, 864, _pose()), neutral)


def test_smiling_keeps_eyes_open_and_blinking_is_independent():
    neutral = render_frame(480, 864, _pose())
    smiling = render_frame(480, 864, _pose(smile=1.0))
    blinking = render_frame(480, 864, _pose(smile=1.0, eye_close=1.0))
    x0, y0, x1, y1 = _facial_box("eyes")
    assert np.array_equal(neutral[y0:y1, x0:x1], smiling[y0:y1, x0:x1])
    assert not np.array_equal(smiling[y0:y1, x0:x1], blinking[y0:y1, x0:x1])
    _assert_changes_inside(neutral, smiling, _facial_box("mouth"))
    _assert_changes_inside(smiling, blinking, _facial_box("eyes"))


def test_audio_driven_mouth_has_distinct_speech_apertures():
    quiet = render_frame(480, 864, _pose(mouth_open=0.25))
    loud = render_frame(480, 864, _pose(mouth_open=1.0))
    _assert_changes_inside(quiet, loud, _facial_box("mouth"))


def test_gesture_transitions_keep_complete_sprites_and_props_inside_the_portrait(monkeypatch):
    """Check the renderer's actual transformed art, including margins beyond the joints."""
    from live_agent.generator.puppet import pose_at
    from live_agent.generator import puppet_art

    art = puppet_art._scaled_art(480, 864)
    shadow_ids = {id(part) for part in art[-1].values()}
    context = None
    observed = set()

    def inspect(image, part, position, anchor, angle=0.0):
        if id(part) in shadow_ids:
            return
        transformed, origin = puppet_art._joint_placement(part, position, anchor, angle)
        bounds = transformed.getchannel("A").getbbox()
        if bounds is None:
            return
        x0, y0, x1, y1 = bounds
        x0 += origin[0]
        x1 += origin[0]
        y0 += origin[1]
        y1 += origin[1]
        assert 0 <= x0 < x1 <= 480, (context, part.size, angle, (x0, x1))
        assert 0 <= y0 < y1 <= 864, (context, part.size, angle, (y0, y1))
        observed.add(id(part))

    monkeypatch.setattr(puppet_art, "_paste_joint", inspect)
    for anim in ANIMATIONS:
        for phase in (0.0, 1.7, 4.0):
            for t in np.linspace(0.0, 5.0, 121):
                context = (anim, float(t), phase)
                p = pose_at(anim, float(t), 5.0, 0.0, phase)
                render_frame(480, 864, p)
    for name in ("mug", "held_book", "pointer", "open_hand", "elbow_cap"):
        assert id(art[2][name]) in observed, name


def test_drinking_and_book_gestures_keep_their_scene_contacts(monkeypatch):
    from live_agent.generator.puppet import pose_at
    from live_agent.generator import puppet_art

    art = puppet_art._scaled_art(480, 864)
    rig, _, parts, *_ = art
    calls = []
    paste = puppet_art._paste_joint

    def capture(image, part, position, anchor, angle=0.0):
        if part is parts["mug"] or part is parts["held_book"]:
            transformed, origin = puppet_art._joint_placement(part, position, anchor, angle)
            calls.append((part, position, origin, transformed))
        paste(image, part, position, anchor, angle)

    monkeypatch.setattr(puppet_art, "_paste_joint", capture)
    render_frame(480, 864, _pose())
    resting_mug_origin = next(origin for part, _, origin, _ in calls if part is parts["mug"])
    calls.clear()
    render_frame(480, 864, pose_at("drink", 0.5, 5.0, 0.0, 0.0))
    pickup = next(call for call in calls if call[0] is parts["mug"])
    assert np.max(np.abs(np.asarray(pickup[2]) - resting_mug_origin)) <= 3

    calls.clear()
    drinking = pose_at("drink", 2.5, 5.0, 0.0, 0.0)
    render_frame(480, 864, drinking)
    _, _, origin, mug = next(call for call in calls if call[0] is parts["mug"])
    rim = np.asarray(origin) + (mug.width * 0.5, mug.height * 0.1)
    x0, y0, x1, y1 = _facial_box("mouth")
    mouth = puppet_art._motion(rig, drinking)[0](((x0 + x1) / 2, (y0 + y1) / 2))
    assert np.max(np.abs(rim - mouth)) <= 12

    calls.clear()
    render_frame(480, 864, pose_at("hold", 2.5, 5.0, 0.0, 0.0))
    _, position, origin, book = next(call for call in calls if call[0] is parts["held_book"])
    assert abs(position[0] - rig["bust_position"][0]) <= 3
    assert abs(position[1] - (rig["tabletop_y"] + 45)) <= 6
    assert origin[1] < rig["tabletop_y"] < origin[1] + book.height < rig["foreground_y"]


def test_globe_gesture_contacts_the_sphere(monkeypatch):
    from PIL import Image
    from live_agent.generator.puppet import pose_at
    from live_agent.generator import puppet_art

    art = puppet_art._scaled_art(480, 864)
    parts = art[2]
    palms, globes = [], []

    def capture(image, part, position, anchor, angle=0.0):
        if part.size == parts["open_hand"].size or part is parts["globe"]:
            transformed, origin = puppet_art._joint_placement(part, position, anchor, angle)
            alpha = transformed.getchannel("A")
            if part is parts["globe"]:
                # The lower stand is not the sphere that the gesture rotates.
                alpha.paste(0, (0, round(alpha.height * 0.7), alpha.width, alpha.height))
            mask = Image.new("L", (480, 864))
            mask.paste(alpha, origin)
            (globes if part is parts["globe"] else palms).append(np.asarray(mask))

    monkeypatch.setattr(puppet_art, "_paste_joint", capture)
    render_frame(480, 864, pose_at("spin", 2.5, 5.0, 0.0, 0.0))
    assert len(palms) == len(globes) == 1
    assert np.count_nonzero((palms[0] > 100) & (globes[0] > 100)) >= 20


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


def test_edge_voice_decoding_keeps_the_live_event_loop_responsive(monkeypatch):
    import threading
    from live_agent import tts

    started, release = threading.Event(), threading.Event()

    def slow_decode(data):
        started.set()
        assert release.wait(2), "the event loop could not release the audio decoder"
        return np.zeros(32, dtype=np.float32)

    async def speak(text, voice):
        return b"encoded speech"

    monkeypatch.setattr(tts, "decode_audio", slow_decode)

    async def main():
        task = asyncio.create_task(EdgeTTS(speak=speak).synthesize("你好"))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            # A live input can be handled while decoding remains unfinished.
            await asyncio.sleep(0)
            assert not task.done()
            release.set()
            assert len(await task) == 32
        finally:
            release.set()
            if not task.done():
                task.cancel()

    run(main())


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


def test_partial_blink_and_rounded_speech_stay_inside_facial_regions():
    neutral = render_frame(480, 864, _pose())
    partial = render_frame(480, 864, _pose(eye_close=.5))
    closed = render_frame(480, 864, _pose(eye_close=1))
    assert np.any(partial != neutral) and np.any(partial != closed)
    _assert_changes_inside(neutral, partial, _facial_box("eyes"))
    wide = render_frame(480, 864, _pose(mouth_open=.65))
    rounded = render_frame(480, 864, _pose(mouth_open=.65, mouth_round=1))
    _assert_changes_inside(wide, rounded, _facial_box("mouth"))


def test_idle_motion_is_continuous_between_requests_and_blink_has_intermediate_states():
    from live_agent.generator.puppet import pose_at
    end = pose_at('idle', 5, 5, 0, .3, motion_time=5)
    start = pose_at('idle', 0, 3, 0, .3, motion_time=5)
    assert end.head_dx == start.head_dx and end.head_dy == start.head_dy
    assert end.eye_close == start.eye_close
    samples = [pose_at('idle', t, 5, 0, 0).eye_close for t in np.arange(0,.25,1/24)]
    assert any(0 < value < 1 for value in samples)


def test_acoustic_mouth_variety_is_smooth_and_silent_audio_has_no_shapes():
    from live_agent.generator.puppet import speech_shape_track
    sr=24000; fps=24; t=np.arange(sr)/sr
    low = speech_shape_track(np.sin(2*np.pi*200*t).astype(np.float32),24,fps,sr)
    high = speech_shape_track(np.sin(2*np.pi*3000*t).astype(np.float32),24,fps,sr)
    assert low[-1] > .9 and high[-1] < .1
    assert np.max(np.abs(np.diff(low))) <= .3
    assert not speech_shape_track(np.zeros(sr,dtype=np.float32),24,fps,sr).any()


def test_teaching_gestures_keep_natural_elbow_direction_and_small_wrist_steps():
    """Speech gestures must not reverse the resting elbow or sweep off the desk."""
    from live_agent.generator.puppet import pose_at
    for anim in ('explain', 'present'):
        wrists = []
        for t in np.linspace(0, 3, 73):
            p = pose_at(anim, float(t), 3, 0, 1.7)
            assert -1.6 < p.r_el <= -0.85
            assert p.l_sh == Pose().l_sh and p.l_el == Pose().l_el
            wrists.append((363 + 145 * math.sin(p.r_sh) + 128 * math.sin(p.r_sh + p.r_el),
                           377 + 145 * math.cos(p.r_sh) + 128 * math.cos(p.r_sh + p.r_el)))
        assert np.max(np.linalg.norm(np.diff(wrists, axis=0), axis=1)) < 12
        assert np.max(np.abs(np.array(wrists[0]) - wrists[-1])) < 1e-8


def test_hand_oscillation_fades_at_hold_boundaries():
    from live_agent.generator.puppet import pose_at
    for anim in ('explain', 'draw', 'spin', 'wave'):
        for u in (.16, .82):
            before = pose_at(anim, 5 * u - 1e-6, 5, 0, 1.7)
            after = pose_at(anim, 5 * u + 1e-6, 5, 0, 1.7)
            assert max(abs(getattr(before, f) - getattr(after, f))
                       for f in ('r_sh', 'r_el', 'l_sh', 'l_el')) < 1e-4
