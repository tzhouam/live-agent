"""Puppet generator: a skeleton-controlled cartoon teacher on CPU (D-047).

The cheap peer of the TaoMate-H3 backends (docs/notes/cheap_avatar_backbone.md): no GPU, no
diffusion. One 5-s request is

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
import random
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from live_agent.generator.base import Generator, GeneratorInfo, RequestTiming
from live_agent.generator.mock import FIRST_LAYOUT, LATER_LAYOUT
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
    r_sh: float = 0.30
    r_el: float = 0.35
    l_sh: float = 0.30
    l_el: float = 0.35
    mouth_open: float = 0.0
    smile: float = 0.0
    brow: float = 0.0
    eye_close: float = 0.0
    item: str = ""


_FIELDS = tuple(f for f in Pose.__dataclass_fields__ if f != "item")

# Animation keyframes: (fraction of the request, pose overrides). Every animation starts and
# ends at the idle pose, so consecutive requests never freeze mid-gesture.
ANIMATIONS: dict[str, list[tuple[float, dict]]] = {
    "idle": [],
    "listen": [(0.10, {"head_tilt": 0.14}), (0.40, {"head_tilt": 0.14, "head_dy": 7.0}),
               (0.70, {"head_tilt": 0.14}), (1.0, {})],
    "explain": [(0.08, {"r_sh": 0.80, "r_el": 1.35}), (0.92, {"r_sh": 0.80, "r_el": 1.35}), (1.0, {})],
    "point": [(0.12, {"r_sh": 1.05, "r_el": 1.45, "item": "pointer", "head_dx": -8.0}),
              (0.80, {"r_sh": 1.05, "r_el": 1.45, "item": "pointer", "head_dx": -8.0}), (1.0, {})],
    "draw": [(0.12, {"r_sh": 1.35, "r_el": 1.05, "item": "chalk", "head_dx": -10.0}),
             (0.85, {"r_sh": 1.35, "r_el": 1.05, "item": "chalk", "head_dx": -10.0}), (1.0, {})],
    "hold": [(0.12, {"r_sh": -0.30, "r_el": -1.55, "l_sh": 0.30, "l_el": 1.55, "item": "book"}),
             (0.85, {"r_sh": -0.30, "r_el": -1.55, "l_sh": 0.30, "l_el": 1.55, "item": "book"}), (1.0, {})],
    "count": [(0.12, {"r_sh": 0.95, "r_el": 0.80, "item": "count"}),
              (0.85, {"r_sh": 0.95, "r_el": 0.80, "item": "count"}), (1.0, {})],
    "thumb": [(0.12, {"r_sh": 0.90, "r_el": 0.70, "item": "thumb", "smile": 0.6}),
              (0.85, {"r_sh": 0.90, "r_el": 0.70, "item": "thumb", "smile": 0.6}), (1.0, {})],
    "spin": [(0.12, {"r_sh": 1.10, "r_el": 0.65}), (0.88, {"r_sh": 1.10, "r_el": 0.65}), (1.0, {})],
    "drink": [(0.10, {"r_sh": 0.55, "r_el": 0.30, "item": "mug"}),
              (0.28, {"r_sh": -0.90, "r_el": -2.50, "item": "mug", "head_dy": 6.0}),
              (0.72, {"r_sh": -0.90, "r_el": -2.50, "item": "mug", "head_dy": 6.0}),
              (0.92, {"r_sh": 0.55, "r_el": 0.30, "item": "mug"}), (1.0, {})],
    "nod": [(0.10, {"head_dy": 13.0}), (0.22, {}), (0.34, {"head_dy": 13.0}), (0.46, {}), (1.0, {})],
    "shake": [(0.12, {"head_dx": -16.0}), (0.28, {"head_dx": 16.0}), (0.44, {"head_dx": -14.0}),
              (0.60, {}), (1.0, {})],
    "smile": [(0.12, {"smile": 1.0}), (0.85, {"smile": 1.0}), (1.0, {})],
    "wave": [(0.12, {"r_sh": 1.50, "r_el": 0.90}), (0.88, {"r_sh": 1.50, "r_el": 0.90}), (1.0, {})],
    "bow": [(0.15, {"head_dy": 40.0, "r_sh": 0.55, "r_el": 0.50, "l_sh": 0.55, "l_el": 0.50}),
            (0.70, {"head_dy": 40.0, "r_sh": 0.55, "r_el": 0.50, "l_sh": 0.55, "l_el": 0.50}), (1.0, {})],
    "think": [(0.12, {"r_sh": -0.55, "r_el": -2.40, "head_tilt": 0.12, "brow": 1.0}),
              (0.88, {"r_sh": -0.55, "r_el": -2.40, "head_tilt": 0.12, "brow": 1.0}), (1.0, {})],
    "present": [(0.12, {"r_sh": 0.85, "r_el": 1.35, "l_sh": 0.85, "l_el": 1.35, "smile": 0.6}),
                (0.88, {"r_sh": 0.85, "r_el": 1.35, "l_sh": 0.85, "l_el": 1.35, "smile": 0.6}), (1.0, {})],
}

# Hand oscillation while an animation holds: (shoulder amplitude, elbow amplitude, Hz)
WIGGLE: dict[str, tuple[float, float, float]] = {
    "explain": (0.10, 0.16, 2.2),
    "draw": (0.06, 0.10, 2.6),
    "spin": (0.14, 0.22, 1.8),
    "wave": (0.0, 0.28, 3.0),
}

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


def pose_at(anim: str, t: float, dur: float, mouth: float, phase: float) -> Pose:
    u = min(1.0, max(0.0, t / dur))
    p = _interp_pose(ANIMATIONS.get(anim, []), u)
    p.head_dy += 1.4 * math.sin(2 * math.pi * t / 3.6 + phase)  # breathing
    p.head_dx += 2.2 * math.sin(2 * math.pi * t / 7.3 + phase * 1.7)  # micro sway
    if (t + phase * 2.9) % 2.9 < 0.13:  # blink
        p.eye_close = 1.0
    p.mouth_open = max(p.mouth_open, mouth)
    w = WIGGLE.get(anim)
    if w and 0.08 < u < 0.95:
        p.r_sh += w[0] * math.sin(2 * math.pi * w[2] * t + phase)
        p.r_el += w[1] * math.cos(2 * math.pi * w[2] * 0.9 * t + phase)
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

SKIN = (255, 219, 186)
HAIR = (56, 42, 36)
JACKET = (58, 84, 104)
SLEEVE = (88, 120, 144)  # lighter than the jacket so the arms read against the torso
SLEEVE_EDGE = (34, 50, 62)
SHIRT = (246, 246, 240)
WALL = (216, 227, 231)
BOARD = (43, 74, 60)
FRAME = (126, 94, 63)
CHALK = (226, 226, 214)
DESK = (150, 111, 72)
DESK_TOP = (182, 142, 95)
MUG = (172, 62, 52)
GLOBE = (96, 140, 170)


def _draw_item(d, P, hx: float, hy: float, item: str, side: int) -> None:
    """What the right hand holds, drawn at the hand position (cartoon approximations)."""
    if item == "pointer":
        tip = (hx - side * 54.0, hy - 104.0)
        d.line([P(hx, hy), P(*tip)], fill=FRAME, width=4)
        d.ellipse([P(tip[0] - 4, tip[1] - 4), P(tip[0] + 4, tip[1] + 4)], fill=(180, 60, 50))
    elif item == "chalk":
        tip = (hx - side * 16.0, hy - 22.0)
        d.line([P(hx, hy), P(*tip)], fill=(240, 240, 235), width=5)
    elif item == "mug":
        d.rectangle([P(hx - 14, hy - 38), P(hx + 14, hy + 2)], fill=MUG, outline=(120, 40, 34), width=2)
        d.arc([P(hx + 10, hy - 26), P(hx + 26, hy - 8)], 270, 90, fill=(120, 40, 34), width=3)
    elif item == "book":
        d.rectangle([P(hx - 34, hy - 46), P(hx + 34, hy + 2)], fill=(204, 178, 116),
                    outline=(150, 124, 70), width=2)
        d.line([P(hx, hy - 46), P(hx, hy + 2)], fill=(150, 124, 70), width=2)
    elif item == "count":
        for j in range(5):
            a = -0.9 + j * 0.45
            d.line([P(hx, hy), P(hx + 14 * math.sin(a), hy - 18 - 4 * math.cos(a))],
                   fill=SKIN, outline=(200, 170, 140), width=4)
    elif item == "thumb":
        d.line([P(hx, hy), P(hx - side * 2.0, hy - 22.0)], fill=SKIN, outline=(200, 170, 140), width=7)


def render_frame(w: int, h: int, p: Pose) -> np.ndarray:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), WALL)
    d = ImageDraw.Draw(img)
    sx, sy = w / 480.0, h / 864.0

    def P(x: float, y: float) -> tuple[float, float]:
        return (x * sx, y * sy)

    def limb(a: tuple[float, float], b: tuple[float, float], width: int) -> None:
        d.line([P(*a), P(*b)], fill=SLEEVE_EDGE, width=width + 6)  # outline first: sleeve reads on jacket
        d.line([P(*a), P(*b)], fill=SLEEVE, width=width)

    # scene: blackboard with chalk marks
    d.rectangle([P(30, 48), P(450, 356)], fill=BOARD, outline=FRAME, width=max(2, int(6 * sx)))
    for cx, cy, ln in ((70, 120, 60), (70, 160, 90), (150, 110, 50), (150, 260, 110), (70, 300, 80)):
        d.line([P(cx, cy), P(cx + ln, cy - 8)], fill=CHALK, width=2)

    # torso and collar (the lower part disappears behind the lectern front drawn last)
    d.polygon([P(168, 592), P(312, 592), P(322, 740), P(158, 740)], fill=JACKET)
    d.polygon([P(216, 592), P(264, 592), P(252, 650), P(228, 650)], fill=SHIRT)
    d.rectangle([P(228, 526 + p.head_dy), P(252, 566 + p.head_dy)], fill=SKIN)  # neck

    # head
    hx, hy = 240.0 + p.head_dx, 470.0 + p.head_dy
    d.ellipse([P(hx - 64, hy - 64), P(hx + 64, hy + 64)], fill=SKIN)
    d.ellipse([P(hx - 70, hy - 8), P(hx - 58, hy + 12)], fill=SKIN)
    d.ellipse([P(hx + 58, hy - 8), P(hx + 70, hy + 12)], fill=SKIN)
    d.pieslice([P(hx - 64, hy - 64), P(hx + 64, hy + 64)], 180, 360, fill=HAIR)
    d.rectangle([P(hx - 64, hy - 64), P(hx - 52, hy - 6)], fill=HAIR)
    d.rectangle([P(hx + 52, hy - 64), P(hx + 64, hy - 6)], fill=HAIR)
    d.rectangle([P(hx - 66, hy - 70), P(hx + 66, hy - 54)], fill=HAIR)

    # face: eyes, glasses, brows, mouth
    ey = hy - 6
    tilt = p.head_tilt
    for exo in (-24.0, 24.0):
        ex = hx + exo + tilt * 18.0
        if p.eye_close > 0.5:
            d.line([P(ex - 9, ey), P(ex + 9, ey)], fill=(40, 30, 26), width=3)
        else:
            d.ellipse([P(ex - 9, ey - 6), P(ex + 9, ey + 6)], fill=(250, 250, 250),
                      outline=(60, 50, 44), width=2)
            d.ellipse([P(ex - 3.5, ey - 4), P(ex + 3.5, ey + 4)], fill=(50, 40, 34))
        d.ellipse([P(ex - 15, ey - 11), P(ex + 15, ey + 11)], outline=(70, 60, 54), width=2)
        by = ey - 20.0 - p.brow * 6.0
        d.line([P(ex - 10, by), P(ex + 10, by - 2 - p.brow * 3)], fill=(50, 38, 32), width=4)
    d.line([P(hx - 9 + tilt * 18, ey - 4), P(hx + 9 + tilt * 18, ey - 4)], fill=(70, 60, 54), width=2)
    my = hy + 34.0
    if p.smile > 0.4 and p.mouth_open < 0.15:
        d.arc([P(hx - 16, my - 16), P(hx + 16, my + 14)], 20, 160, fill=(120, 60, 50), width=4)
    else:
        mw, mh = 13.0 + p.smile * 4.0, 2.0 + p.mouth_open * 22.0
        d.ellipse([P(hx - mw, my - mh * 0.2), P(hx + mw, my + mh)], fill=(150, 80, 70),
                  outline=(110, 60, 52), width=2)

    # the desk surface the character stands behind: drawn under the arms so resting hands
    # and the props read as *on* the lectern, not floating
    d.polygon([P(96, 640), P(384, 640), P(404, 704), P(76, 704)], fill=DESK_TOP)
    d.line([P(96, 640), P(384, 640)], fill=DESK, width=6)  # the back edge props rest against
    d.line([P(104, 646), P(376, 646)], fill=(206, 166, 118), width=3)
    d.ellipse([P(352, 598), P(396, 640)], fill=GLOBE, outline=DESK, width=2)  # globe, on the desk
    d.arc([P(352, 598), P(396, 640)], 200, 340, fill=(220, 230, 235), width=2)
    if p.item != "mug":  # the mug is in the hand while drinking
        d.rectangle([P(386, 600), P(410, 640)], fill=MUG, outline=(120, 40, 34), width=2)
        d.arc([P(408, 608), P(422, 632)], 270, 90, fill=(120, 40, 34), width=3)

    # arms: shoulder -> elbow -> hand, outlined sleeves, items in the right hand
    for side, sh_a, el_a, item in ((1, p.r_sh, p.r_el, p.item), (-1, p.l_sh, p.l_el, "")):
        S = (302.0 if side > 0 else 178.0, 588.0)
        E = (S[0] + side * 66.0 * math.sin(sh_a), S[1] + 66.0 * math.cos(sh_a))
        H = (E[0] + side * 60.0 * math.sin(sh_a + el_a), E[1] + 60.0 * math.cos(sh_a + el_a))
        d.ellipse([P(S[0] - 22, S[1] - 22), P(S[0] + 22, S[1] + 22)], fill=JACKET,
                  outline=SLEEVE_EDGE, width=2)  # shoulder pad covers the sleeve joint
        limb(S, E, max(2, int(24 * sx)))
        limb(E, H, max(2, int(18 * sx)))
        d.ellipse([P(H[0] - 14, H[1] - 14), P(H[0] + 14, H[1] + 14)], fill=SKIN,
                  outline=(200, 170, 140), width=2)
        if item:
            _draw_item(d, P, H[0], H[1], item, side)

    # lectern front, drawn last: hides the lower body
    d.polygon([P(76, 704), P(404, 704), P(424, 864), P(56, 864)], fill=DESK)
    d.rectangle([P(76, 704), P(404, 716)], fill=(120, 88, 56))
    return np.asarray(img, dtype=np.uint8)


def render_chunk(w: int, h: int, n: int, t0: float, dt: float, dur: float, anim: str,
                 mouth: np.ndarray, phase: float) -> np.ndarray:
    frames = [render_frame(w, h, pose_at(anim, t0 + i * dt, dur, float(mouth[i]), phase))
              for i in range(n)]
    return np.stack(frames) if frames else np.zeros((0, h, w, 3), dtype=np.uint8)


# --------------------------------------------------------------------------- generator


class PuppetGenerator(Generator):
    """CPU skeleton-puppet backend; construct directly (tests) or via ``from_args``."""

    def __init__(self, *, tts=None, capabilities: list[tuple[str, str]] | None = None,
                 fps: float = 24.0, size: tuple[int, int] = (864, 480), seed: int = 0):
        self.info = GeneratorInfo(name="puppet", request_seconds=5.0, chunks_per_request=4,
                                  fps=fps, width=size[1], height=size[0], sample_rate=TTS_RATE)
        self.tts = tts or SynthTTS()
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

    @staticmethod
    def add_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--puppet-tts", default="synth", choices=["synth", "url", "edge", "piper"],
                       help="voice source: synth (offline pseudo-speech), url (remote OpenAI-compatible), "
                            "edge (Microsoft Edge neural voices), piper (local CPU voices)")
        p.add_argument("--puppet-tts-voice", default="zh-CN-XiaoxiaoNeural",
                       help="voice name for edge/url TTS")
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
                       model_path=ns.puppet_piper_model)
        return cls(tts=tts, capabilities=caps)

    # ------------------------------------------------------------ contract

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def detect_animation(self, prompt: str) -> str:
        """Intent of the locked prompt -> animation id (longest capability signature found)."""
        best_intent, best_len = "", 0
        for phrase, intent in self._caps:
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
        total = sum(layout)
        fps, sr = self.info.fps, self.info.sample_rate
        dur = total / fps
        track = np.zeros(int(dur * sr), dtype=np.float32)
        if spoken is not None and len(spoken):
            n = min(len(track), len(spoken))
            track[:n] = spoken[:n]
        anim = self.detect_animation(prompt)
        mouth = mouth_track(track, total, fps, sr)
        rng = random.Random(((self.seed & 0xFFFFF) << 20) ^ (k * 7919 + 1))
        phase = rng.random() * 10.0
        base = 0
        base_samples = 0
        for ci, n in enumerate(layout):
            if session != self._session:  # reset happened mid-request
                break
            t0 = base / fps
            frames = await asyncio.to_thread(  # drawing stays off the event loop
                render_chunk, self.info.width, self.info.height, n, t0, 1.0 / fps, dur, anim,
                mouth[base:base + n], phase)
            nsamp = int(n / fps * sr)  # the per-chunk contract count (transport pads/trims too)
            seg = track[base_samples:base_samples + nsamp]
            if len(seg) < nsamp:
                seg = np.concatenate([seg, np.zeros(nsamp - len(seg), dtype=np.float32)])
            audio = np.repeat(seg[:, None], 2, axis=1)  # [S, 2] float32 stereo
            ch = Chunk(k, ci, n, fps, video=frames, audio=audio, sample_rate=sr,
                       t_ready=now(), meta={"prompt": prompt, "session": session})
            if ci == 0:
                tm.t_first_chunk = ch.t_ready
            await self._out.put(ch)
            base += n
            base_samples += nsamp
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
