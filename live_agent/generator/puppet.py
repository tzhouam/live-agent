"""Puppet generator: a skeleton-controlled VTuber-style teacher on CPU (D-047).

The cheap peer of the TaoMate-H3 backends (docs/notes/cheap_avatar_backbone.md): no GPU, no
diffusion. Each request uses four chunks; teaching speech follows the complete
utterance's duration, while silent/action clips keep their nominal layout. It is

- the spoken line synthesized by a TTS client (``live_agent.tts``) — the real "teacher"
  latency, and
- frames drawn by a 2D skeleton rig: capability intents map to keyframed poses, and the mouth
  follows the audio envelope of the very samples the viewer hears, so lip sync holds by
  construction. Action compliance is deterministic: the animation either plays or the request
  is dropped. The judge still runs for log comparability; verdicts on this path are expected
  to be ``complied`` whenever the frames were painted.

Only the compiled prompt string reaches the generator (interface contract): the spoken line
comes from ``extract_dialogue``, and the action is matched against the capability phrases of
the configured persona (longest signature found in the prompt wins; otherwise idle).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.generator.mock import FIRST_LAYOUT, LATER_LAYOUT
from live_agent.generator.puppet_art import render_frame
from live_agent.prompt.h3_compiler import extract_dialogue
from live_agent.tts import SynthTTS, TTS_RATE, make_tts
from live_agent.types import Chunk, now

_ACTION_RE = re.compile(r"(she [^.]*\.)")  # the mock's heuristic: the action sentence


# --------------------------------------------------------------------------- rig


@dataclass
class Pose:
    """Skeleton parameters (idle defaults). Arm angles are radians from straight-down;
    positive rotates the right arm to the viewer's right / the left arm to the viewer's left
    (negative crosses inward). ``item`` is what the right hand holds."""

    head_dx: float = 0.0
    head_dy: float = 0.0
    head_tilt: float = 0.0
    r_sh: float = 0.15
    r_el: float = -0.85
    l_sh: float = 0.15
    l_el: float = -0.85
    mouth_open: float = 0.0
    mouth_round: float = 0.0
    smile: float = 0.0
    brow: float = 0.0
    eye_close: float = 0.0
    palm_open: float = 0.0
    item: str = ""


_FIELDS = tuple(f for f in Pose.__dataclass_fields__ if f != "item")

# Animation keyframes: (fraction of the request, pose overrides). Every animation starts and
# ends at the idle pose, so consecutive requests never freeze mid-gesture.
def _raised(sh: float, el: float, *, both: bool = False, **extra) -> list[tuple[float, dict]]:
    """Fold the elbow before opening the shoulder, keeping the transition on camera."""
    tucked = {"r_sh": -0.80, "r_el": 2.65}
    held = {"r_sh": sh, "r_el": el, **extra}
    if both:
        tucked.update(l_sh=-0.80, l_el=2.65)
        held.update(l_sh=sh, l_el=el)
    return [(0.06, tucked), (0.16, held), (0.82, held), (0.92, tucked), (1.0, {})]


ANIMATIONS: dict[str, list[tuple[float, dict]]] = {
    "idle": [],
    "listen": [(0.10, {"head_tilt": 0.08}), (0.40, {"head_tilt": 0.08, "head_dy": 4.0}),
               (0.70, {"head_tilt": 0.08}), (1.0, {})],
    # Ordinary speech keeps the elbow below the shoulder and bends it in the
    # same direction as the resting pose. Avoid the old backward elbow sweep.
    "explain": [(0.24, {"r_sh": 0.08, "r_el": -1.55, "palm_open": 0.8}),
                (0.70, {"r_sh": 0.08, "r_el": -1.55, "palm_open": 0.8}), (1.0, {})],
    "point": _raised(0.03, 2.80, item="pointer", head_dx=-4.0),
    "draw": _raised(-0.45, 2.73, item="chalk", head_dx=-4.0),
    "hold": [(0.14, {"r_sh": 0.07, "r_el": -0.77, "l_sh": 0.07, "l_el": -0.77, "item": "book"}),
             (0.85, {"r_sh": 0.07, "r_el": -0.77, "l_sh": 0.07, "l_el": -0.77, "item": "book"}), (1.0, {})],
    "count": _raised(-0.45, 2.73, item="count"),
    "thumb": _raised(-0.62, 2.68, item="thumb", smile=0.6),
    "spin": [(0.14, {"l_sh": -0.82, "l_el": 1.75}),
             (0.86, {"l_sh": -0.82, "l_el": 1.75}), (1.0, {})],
    "drink": [(0.10, {"r_sh": 0.39, "r_el": -0.61, "item": "mug"}),
              (0.28, {"r_sh": -0.91, "r_el": -2.15, "item": "mug", "head_dy": 3.0}),
              (0.72, {"r_sh": -0.91, "r_el": -2.15, "item": "mug", "head_dy": 3.0}),
              (0.92, {"r_sh": 0.39, "r_el": -0.61, "item": "mug"}), (1.0, {})],
    "nod": [(0.10, {"head_dy": 4.0}), (0.22, {}), (0.34, {"head_dy": 4.0}), (0.46, {}), (1.0, {})],
    "shake": [(0.12, {"head_dx": -8.0}), (0.28, {"head_dx": 8.0}), (0.44, {"head_dx": -7.0}),
              (0.60, {}), (1.0, {})],
    "smile": [(0.12, {"smile": 1.0}), (0.85, {"smile": 1.0}), (1.0, {})],
    "wave": _raised(0.40, 2.78, item="wave", smile=0.5),
    "bow": [(0.15, {"head_dy": 10.0}), (0.70, {"head_dy": 10.0}), (1.0, {})],
    "think": [(0.12, {"r_sh": -0.84, "r_el": -2.22, "head_tilt": 0.06, "brow": 1.0}),
              (0.88, {"r_sh": -0.84, "r_el": -2.22, "head_tilt": 0.06, "brow": 1.0}), (1.0, {})],
    "present": [(0.24, {"r_sh": 0.16, "r_el": -1.35, "palm_open": 1.0, "smile": 0.3}),
                (0.70, {"r_sh": 0.16, "r_el": -1.35, "palm_open": 1.0, "smile": 0.3}), (1.0, {})],
}

# Hand oscillation while a gesture holds: (shoulder amplitude, elbow amplitude, Hz)
WIGGLE: dict[str, tuple[float, float, float]] = {
    "explain": (0.008, 0.018, 0.35),
    "draw": (0.018, 0.045, 0.9),
    "spin": (0.035, 0.055, 0.7),
    "wave": (0.0, 0.07, 1.0),
}

# The browser rig points with its authored index hand, without a pointer prop.
# Keep this alias separate from the legacy persona capability phrase.
BROWSER_POINT_PHRASE = (
    "she points toward the teaching board with her right index finger, "
    "then gently lowers her hand to rest at the desk"
)

_ANIM_BY_INTENT = {  # teacher capabilities + hanfu-persona aliases
    "idle_teach": "idle", "listen": "listen", "explain": "explain", "point_board": "point",
    "draw_board": "draw", "hold_up_book": "hold", "count_fingers": "count", "thumbs_up": "thumb",
    "spin_globe": "spin", "drink_water": "drink", "nod": "nod", "shake_head": "shake",
    "smile": "smile", "wave": "wave", "bow": "bow", "think": "think", "present_board": "present",
    "idle_read": "idle", "idle": "idle", "drink_tea": "drink", "turn_page": "draw",
    "look": "listen", "read": "listen",
}


def _smoothstep(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def _interp_pose(keys: list[tuple[float, dict]], u: float) -> Pose:
    if not keys:
        return Pose()
    keys = sorted(keys, key=lambda kv: kv[0])
    if keys[0][0] > 0.0:
        keys = [(0.0, {})] + keys
    if keys[-1][0] < 1.0:
        keys = keys + [(1.0, {})]
    defaults = Pose()
    i = max(j for j, kv in enumerate(keys) if kv[0] <= u)
    if i >= len(keys) - 1:
        kf = keys[-1][1]
        return Pose(**{f: kf.get(f, getattr(defaults, f)) for f in _FIELDS},
                    **({"item": kf.get("item", "")}))
    (u0, k0), (u1, k1) = keys[i], keys[i + 1]
    s = _smoothstep((u - u0) / max(1e-9, u1 - u0))
    vals = {}
    for f in _FIELDS:
        a, b = k0.get(f, getattr(defaults, f)), k1.get(f, getattr(defaults, f))
        vals[f] = a + (b - a) * s
    return Pose(**vals, item=k0.get("item", ""))


def pose_at(anim: str, t: float, dur: float, mouth: float, phase: float,
            motion_time: float | None = None) -> Pose:
    u = min(1.0, max(0.0, t / dur))
    p = _interp_pose(ANIMATIONS.get(anim, []), u)
    clock = t if motion_time is None else motion_time
    p.head_dy += 1.4 * math.sin(2 * math.pi * clock / 3.6 + phase)
    p.head_dx += 2.2 * math.sin(2 * math.pi * clock / 7.3 + phase * 1.7)
    blink = (clock + phase * 2.9) % 2.9
    if blink < 0.24:
        p.eye_close = _smoothstep(blink / 0.08) if blink < 0.08 else 1 - _smoothstep((blink - 0.08) / 0.16)
    p.mouth_open = max(p.mouth_open, mouth)
    w = WIGGLE.get(anim)
    if w and 0.16 < u < 0.82:
        envelope = _smoothstep((u - 0.16) / 0.08) * _smoothstep((0.82 - u) / 0.12)
        sh = envelope * w[0] * math.sin(2 * math.pi * w[2] * clock + phase)
        el = envelope * w[1] * math.cos(2 * math.pi * w[2] * 0.9 * clock + phase)
        if anim == "spin":
            p.l_sh += sh
            p.l_el += el
        else:
            p.r_sh += sh
            p.r_el += el
    return p


def mouth_track(audio: np.ndarray, n_frames: int, fps: float, sr: int) -> np.ndarray:
    """Per-frame mouth openness (0..1): window RMS, peak-normalised to the 95th percentile
    and smoothed — the same audio the viewer hears drives the mouth, so sync holds by
    construction."""
    out = np.zeros(n_frames, dtype=np.float32)
    if len(audio) == 0:
        return out
    for i in range(n_frames):
        s0, s1 = int(i / fps * sr), int((i + 1) / fps * sr)
        seg = audio[s0:s1]
        if len(seg):
            out[i] = float(np.sqrt(np.mean(np.square(seg, dtype=np.float64))))
    hi = float(np.percentile(out[out > 0], 95)) if np.any(out > 0) else 0.0
    if hi <= 1e-6:
        return np.zeros(n_frames, dtype=np.float32)
    out = np.clip(out / (hi * 0.7), 0.0, 1.0)
    if len(out) >= 3:  # 3-tap smoothing
        out = np.convolve(out, np.array([0.25, 0.5, 0.25], dtype=np.float32), mode="same")
    return out.astype(np.float32)


# --------------------------------------------------------------------------- drawing

def speech_shape_track(audio: np.ndarray, n_frames: int, fps: float, sr: int) -> np.ndarray:
    """Coarse acoustic variety, not phoneme recognition: darker voiced sounds round
    the lips, brighter sounds spread them. Silence does not animate the mouth."""
    shapes = np.zeros(n_frames, dtype=np.float32)
    previous = 0.0
    for i in range(n_frames):
        segment = audio[int(i / fps * sr):int((i + 1) / fps * sr)]
        target = 0.0
        if len(segment) > 1 and np.sqrt(np.mean(segment.astype(np.float64) ** 2)) > 1e-4:
            spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
            frequencies = np.fft.rfftfreq(len(segment), 1 / sr)
            centroid = float(np.sum(spectrum * frequencies) / max(1e-9, spectrum.sum()))
            target = float(np.clip((1800 - centroid) / 1500, 0, 1))
        previous += 0.3 * (target - previous)
        shapes[i] = previous
    return shapes

def render_chunk(w: int, h: int, n: int, t0: float, dt: float, dur: float, anim: str,
                 mouth: np.ndarray, phase: float, motion_start: float = 0.0,
                 shapes: np.ndarray | None = None) -> np.ndarray:
    frames = []
    for i in range(n):
        t = t0 + i * dt
        pose = pose_at(anim, t, dur, float(mouth[i]), phase, motion_start + t)
        pose.mouth_round = float(shapes[i]) if shapes is not None else 0.0
        frames.append(render_frame(w, h, pose))
    return np.stack(frames) if frames else np.zeros((0, h, w, 3), dtype=np.uint8)


# --------------------------------------------------------------------------- generator


class PuppetGenerator(Generator):
    """CPU skeleton-puppet backend; construct directly (tests) or via ``from_args``."""

    def __init__(self, *, tts=None, capabilities: list[tuple[str, str]] | None = None,
                 fps: float = 24.0, size: tuple[int, int] = (864, 480), seed: int = 0,
                 speech_timing: str = "natural"):
        if speech_timing not in ("natural", "fixed"):
            raise ValueError("speech_timing must be natural or fixed")
        self.info = GeneratorInfo(name="puppet", request_seconds=5.0, chunks_per_request=4,
                                  fps=fps, width=size[1], height=size[0], sample_rate=TTS_RATE)
        self.tts = tts or SynthTTS()
        self.speech_timing = speech_timing
        self._caps = capabilities or []
        self.seed = seed  # SessionView forwards the session seed here
        self._queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
        self._out: asyncio.Queue[Chunk | None] = asyncio.Queue()
        self._timings: dict[int, RequestTiming] = {}
        self._next = 0
        self._session = 0
        self._first_in_session = True
        self._task: asyncio.Task | None = None
        self._error: BaseException | None = None
        self._motion_time = 0.0

    @staticmethod
    def add_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--puppet-tts", default="synth", choices=["synth", "url", "edge", "piper"],
                       help="voice source: synth (offline pseudo-speech), url (remote OpenAI-compatible), "
                            "edge (Microsoft Edge neural voices), piper (local CPU voices)")
        p.add_argument("--puppet-tts-voice", default="zh-CN-XiaoxiaoNeural",
                       help="voice name for edge/url TTS")
        p.add_argument("--puppet-tts-rate", default="-4%", help="Edge speaking rate")
        p.add_argument("--puppet-tts-pitch", default="-8Hz", help="Edge voice pitch")
        p.add_argument("--puppet-tts-volume", default="+0%", help="Edge speech volume")
        p.add_argument("--puppet-speech-timing", choices=["natural", "fixed"], default="natural",
                       help="natural: follow complete teaching speech; fixed: retain nominal minimum duration")
        p.add_argument("--tts-url", default="", help="url mode: OpenAI-compatible base, e.g. http://host:port/v1")
        p.add_argument("--tts-model", default="tts-1", help="url mode: model id")
        p.add_argument("--tts-api-key-env", default="TTS_API_KEY",
                       help="environment variable holding the TTS API key (url mode)")
        p.add_argument("--puppet-piper-model", default="", help="piper mode: path to the .onnx voice")

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "PuppetGenerator":
        import os

        p = argparse.ArgumentParser(add_help=False)
        cls.add_args(p)
        ns, _ = p.parse_known_args(args.extra)
        caps: list[tuple[str, str]] = []
        caps_path = Path(args.config) / "capabilities.json"
        if caps_path.exists():
            data = json.loads(caps_path.read_text())
            caps = [(c.get("phrase", ""), c.get("intent", "")) for c in data.get("capabilities", [])]
        tts = make_tts(ns.puppet_tts, voice=ns.puppet_tts_voice, base_url=ns.tts_url,
                       model=ns.tts_model, api_key=os.environ.get(ns.tts_api_key_env) or "EMPTY",
                       model_path=ns.puppet_piper_model, edge_rate=ns.puppet_tts_rate,
                       edge_pitch=ns.puppet_tts_pitch, edge_volume=ns.puppet_tts_volume)
        return cls(tts=tts, capabilities=caps, speech_timing=ns.puppet_speech_timing)

    # ------------------------------------------------------------ contract

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def detect_animation(self, prompt: str) -> str:
        """Intent of the locked prompt -> animation id (longest capability signature found)."""
        best_intent, best_len = "", 0
        for phrase, intent in [*self._caps, (BROWSER_POINT_PHRASE, "point_board")]:
            sig = phrase.split("{")[0].split(",")[0].strip()
            if len(sig) >= 10 and sig in prompt and len(sig) > best_len:
                best_intent, best_len = intent, len(sig)
        return _ANIM_BY_INTENT.get(best_intent, "idle")

    async def _run(self) -> None:
        while True:
            k, prompt = await self._queue.get()
            session = self._session
            try:
                await self._run_request(k, prompt, session)
            except BaseException as e:  # a TTS/worker failure stops the session (ERROR), never hangs
                self._error = e
                await self._out.put(None)
                return

    async def _run_request(self, k: int, prompt: str, session: int) -> None:
        tm = self._timings[k]
        line = extract_dialogue(prompt)
        tm.t_teacher_start = now()
        spoken = await self.tts.synthesize(line) if line else None  # the real teacher latency
        tm.t_teacher_done = now()
        tm.t_student_start = now()
        layout = FIRST_LAYOUT if self._first_in_session else LATER_LAYOUT
        self._first_in_session = False
        fps, sr = self.info.fps, self.info.sample_rate
        anim = self.detect_animation(prompt)
        total = sum(layout)
        if spoken is not None and len(spoken):
            # Complete every utterance, including a short breath after its end.
            # Four indexed chunks preserve the transport/acknowledgement contract.
            speech_frames = math.ceil((len(spoken) / sr + 0.22) * fps)
            if self.speech_timing == "natural" and anim in ("idle", "explain", "present"):
                total = max(math.ceil(1.8 * fps), speech_frames)
            else:
                total = max(total, speech_frames)
            boundaries = [round(total * sum(layout[:i]) / sum(layout)) for i in range(5)]
            layout = [b - a for a, b in zip(boundaries, boundaries[1:])]
        dur = total / fps
        track = np.zeros(int(dur * sr), dtype=np.float32)
        if spoken is not None and len(spoken):
            track[:len(spoken)] = spoken
        mouth = mouth_track(track, total, fps, sr)
        phase = (self.seed % 997) / 997 * 10.0
        motion_start = self._motion_time
        shapes = speech_shape_track(track, total, fps, sr)
        base = 0
        base_samples = 0
        for ci, n in enumerate(layout):
            if session != self._session:  # reset happened mid-request
                break
            t0 = base / fps
            frames = await asyncio.to_thread(  # drawing stays off the event loop
                render_chunk, self.info.width, self.info.height, n, t0, 1.0 / fps, dur, anim,
                mouth[base:base + n], phase, motion_start, shapes[base:base + n])
            nsamp = int(n / fps * sr)  # the per-chunk contract count (transport pads/trims too)
            seg = track[base_samples:base_samples + nsamp]
            if len(seg) < nsamp:
                seg = np.concatenate([seg, np.zeros(nsamp - len(seg), dtype=np.float32)])
            audio = np.repeat(seg[:, None], 2, axis=1)  # [S, 2] float32 stereo
            ch = Chunk(k, ci, n, fps, video=frames, audio=audio, sample_rate=sr,
                       t_ready=now(), meta={"prompt": prompt, "session": session, "request_duration_s": dur,
                                             "avatar_gesture": anim, "request_offset_s": t0,
                                             "motion_time_s": motion_start + t0})
            if ci == 0:
                tm.t_first_chunk = ch.t_ready
            await self._out.put(ch)
            base += n
            base_samples += nsamp
        if session == self._session:
            self._motion_time += base / fps
        tm.t_done = now()

    async def submit(self, request_index: int, prompt: str) -> None:
        if request_index != self._next:
            raise ValueError(f"expected request {self._next}, got {request_index}")
        self._next += 1
        self._timings[request_index] = RequestTiming(request_index, t_lock=now())
        await self._queue.put((request_index, prompt))

    async def chunks(self) -> AsyncIterator[Chunk]:
        while True:
            ch = await self._out.get()
            if ch is None:
                if self._error is not None:
                    raise self._error
                return
            yield ch

    async def reset(self) -> None:
        self._session += 1
        self._first_in_session = True
        self._motion_time = 0.0
        while not self._queue.empty():
            self._queue.get_nowait()

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        await self._out.put(None)

    @property
    def timings(self) -> list[RequestTiming]:
        return [self._timings[k] for k in sorted(self._timings)]

    @property
    def session_epoch(self) -> int:
        """Generation epoch; bumped by reset(); carried as chunk.meta["session"]."""
        return self._session

    @property
    def next_request_index(self) -> int:
        return self._next
