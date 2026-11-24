"""Versioned browser-avatar contract and bounded visual evidence.

These are pictures of the displayed teacher, never student-camera input. All
limits are configuration bounds, not measured quality or performance claims.
"""
from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass

import numpy as np

MODEL = "teacher-mesh-v1"
INTENTS = frozenset({"idle_teach", "listen", "explain", "present_board", "point_board",
                     "smile", "think", "nod", "shake_head", "wave"})
GESTURES = frozenset({"idle", "listen", "explain", "present", "point", "smile", "think", "nod", "shake", "wave"})
MAX_IMAGE_CHARS = 160_000
MAX_JPEG_BYTES = 120_000
MAX_PER_CHUNK = 12
MAX_PER_REQUEST = 24


def negotiated(hello: dict, *, generator: str, teacher: bool) -> bool:
    return (teacher and generator == "puppet" and hello.get("renderer") == "mesh"
            and hello.get("avatar_model") == MODEL)


def configure_manifest(manifest) -> None:
    """Adapt a session-local manifest to the browser rig's actual abilities."""
    from live_agent.generator.puppet import BROWSER_POINT_PHRASE

    manifest.supported_intents = INTENTS
    point = manifest.by_intent("point_board")
    if point is not None:
        point.phrase = BROWSER_POINT_PHRASE


def finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def decode_capture(data: str) -> np.ndarray | None:
    """Decode only small JPEGs and cap in-memory evidence resolution."""
    from PIL import Image, UnidentifiedImageError

    if not isinstance(data, str) or len(data) > MAX_IMAGE_CHARS or not data.startswith("data:image/jpeg;base64,"):
        return None
    try:
        raw = base64.b64decode(data.partition(",")[2], validate=True)
        if len(raw) > MAX_JPEG_BYTES:
            return None
        with Image.open(io.BytesIO(raw)) as image:
            w, h = image.size
            if image.format != "JPEG" or not 1 <= w <= 640 or not 1 <= h <= 1152:
                return None
            image.load()
            image = image.convert("RGB")
            image.thumbnail((320, 576))
            return np.array(image)
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return None


@dataclass(frozen=True)
class AvatarCapture:
    frame: int
    media_time: float
    t_capture: float
    clock_source: str
    pixels: np.ndarray
