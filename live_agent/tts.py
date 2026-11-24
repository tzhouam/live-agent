"""TTS clients for the puppet generator (the voice that TaoMate-H3 used to generate itself).

Contract: ``await tts.synthesize(text) -> np.ndarray`` float32 mono at ``TTS_RATE`` (32 kHz),
matching the generator chunk contract. Implementations:

- ``SynthTTS`` : deterministic offline pseudo-speech (tests, CPU demo). It is *not* speech:
  syllable-shaped tones derived from the text, enough to exercise transport, mouth animation
  and onset timing end to end without a model.
- ``UrlTTS``  : OpenAI-compatible ``POST {base}/audio/speech`` (a remote TTS model the
  operator already runs); the API key comes from an environment variable, never argv.
- ``EdgeTTS`` : Microsoft Edge neural voices through the optional ``edge-tts`` package
  (free, unofficial endpoint, no SLA; needs the network).
- ``PiperTTS``: local CPU voices through the optional ``piper`` package (offline).

Decoding and resampling reuse the ASR helpers' pattern (PyAV + scipy resample_poly).
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import io
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import numpy as np

TTS_RATE = 32000  # the generator chunk rate; every client resamples to this
# A restrained conversational profile for the adult Mandarin teacher. These
# are Edge's supported prosody controls, not a new voice or an expressive style.
EDGE_RATE = "-4%"
EDGE_PITCH = "-8Hz"
EDGE_VOLUME = "+0%"


def _resample(a: np.ndarray, sr: int, target: int = TTS_RATE) -> np.ndarray:
    if sr == target or len(a) == 0:
        return np.asarray(a, dtype=np.float32)
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(sr, target)
    return resample_poly(a, target // g, sr // g).astype(np.float32)


def decode_audio(data: bytes, target_sr: int = TTS_RATE) -> np.ndarray:
    """Decode any container (mp3/wav/opus, ...) to mono float32 at target_sr (asr.py pattern)."""
    import av

    out = []
    with av.open(io.BytesIO(data)) as container:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=target_sr)
        for frame in container.decode(audio=0):
            for f in resampler.resample(frame):
                out.append(f.to_ndarray().reshape(-1))
        for f in resampler.resample(None):
            out.append(f.to_ndarray().reshape(-1))
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def synth_speech(text: str, rate: int = TTS_RATE) -> np.ndarray:
    """Deterministic pseudo-speech: one tone burst per CJK syllable / ASCII word chunk.

    Not speech and not language-specific audio — a stand-in with a speech-like envelope so
    transport, mouth animation and onset measurement work with no model and no network.
    """
    text = (text or "").strip()
    if not text:
        return np.zeros(0, dtype=np.float32)
    rng = random.Random(int.from_bytes(hashlib.md5(text.encode()).digest()[:8], "little"))
    bursts: list[list] = []  # [duration_s, f0_hz, is_latin]; f0 <= 0 marks a pause
    for ch in text:
        if ch in "，。！？；：、,.!?;:":
            bursts.append([rng.uniform(0.22, 0.34), 0.0, False])
        elif ch.isspace():
            bursts.append([0.07, 0.0, False])
        elif ord(ch) < 0x2E80:  # Latin: merge letters into word chunks of <= 0.20 s
            if bursts and bursts[-1][2] and bursts[-1][0] < 0.20:
                bursts[-1][0] += rng.uniform(0.10, 0.16)
            else:
                bursts.append([rng.uniform(0.10, 0.16), rng.uniform(150, 210), True])
        else:  # CJK: one burst per character
            bursts.append([rng.uniform(0.13, 0.20), rng.uniform(190, 240), False])
    parts: list[np.ndarray] = [np.zeros(int(0.05 * rate), dtype=np.float32)]  # short onset lead-in
    for d, f0, _ in bursts:
        n = int(d * rate)
        t = np.arange(n) / rate
        if f0 <= 0:
            seg = np.zeros(n, dtype=np.float32)
        else:
            vib = 1.0 + 0.01 * np.sin(2 * np.pi * 5.5 * t)
            seg = (0.30 * np.sin(2 * np.pi * f0 * vib * t)
                   + 0.12 * np.sin(2 * np.pi * 2 * f0 * t)
                   + 0.05 * np.sin(2 * np.pi * 3 * f0 * t))
            env = np.minimum(1.0, np.minimum(t / 0.015, (d - t) / 0.04))  # attack 15 ms, release 40 ms
            seg = (seg * np.clip(env, 0.0, 1.0)).astype(np.float32)
        parts.append(seg)
    return np.concatenate(parts).astype(np.float32)


@dataclass
class SynthTTS:
    rate: int = TTS_RATE

    async def synthesize(self, text: str) -> np.ndarray:
        return synth_speech(text, self.rate)


@dataclass
class UrlTTS:
    """OpenAI-compatible speech endpoint: POST {base_url}/audio/speech -> audio bytes."""

    base_url: str
    model: str = "tts-1"
    voice: str = ""
    api_key: str = "EMPTY"
    timeout_s: float = 30.0
    # injectable transport (tests): async (url, headers, payload_json) -> bytes
    post: Callable[[str, dict, dict], Awaitable[bytes]] | None = None

    async def synthesize(self, text: str) -> np.ndarray:
        url = self.base_url.rstrip("/") + "/audio/speech"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"model": self.model, "input": text, "response_format": "wav"}
        if self.voice:
            payload["voice"] = self.voice
        if self.post is not None:
            data = await self.post(url, headers, payload)
        else:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(url, headers=headers, json=payload)
            if r.status_code != 200:
                raise RuntimeError(f"TTS {r.status_code}: {r.text[:200]}")
            data = r.content
        return decode_audio(data)


async def _edge_speak(text: str, voice: str, *, rate: str = EDGE_RATE,
                      pitch: str = EDGE_PITCH, volume: str = EDGE_VOLUME) -> bytes:
    # Loading the optional networking stack can block the first live utterance.
    edge_tts = await asyncio.to_thread(importlib.import_module, "edge_tts")

    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume)
    buf = bytearray()
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    if not buf:
        raise RuntimeError("edge-tts returned no audio")
    return bytes(buf)


@dataclass
class EdgeTTS:
    """Neural Mandarin speech with provider-supported rate, pitch and volume.

    The optional two-argument ``speak`` transport remains injectable for offline
    decoding tests; normal requests pass all prosody controls to Edge directly.
    Synthesis returns the entire utterance, including its final release/pause.
    """

    voice: str = "zh-CN-XiaoxiaoNeural"
    speak: Callable[[str, str], Awaitable[bytes]] | None = field(default=None, repr=False)
    rate: str = EDGE_RATE
    pitch: str = EDGE_PITCH
    volume: str = EDGE_VOLUME

    def __post_init__(self):
        # Validate before networking, using the same signed formats as edge-tts.
        for name, pattern in (("rate", r"[+-]\d+%"), ("pitch", r"[+-]\d+Hz"),
                              ("volume", r"[+-]\d+%")):
            value = getattr(self, name)
            if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
                raise ValueError(f"Edge TTS {name} must use a signed value such as "
                                 + ("'-8Hz'" if name == "pitch" else "'-4%'"))

    async def synthesize(self, text: str) -> np.ndarray:
        if self.speak is not None:
            data = await self.speak(text, self.voice)
        else:
            data = await _edge_speak(text, self.voice, rate=self.rate, pitch=self.pitch,
                                     volume=self.volume)
        return await asyncio.to_thread(decode_audio, data)


@dataclass
class PiperTTS:
    """Local CPU piper voices (offline). Model download and package are the operator's."""

    model_path: str
    voice: object = None  # loaded PiperVoice, lazily

    def _load(self):
        from piper import PiperVoice  # optional dependency

        return PiperVoice.load(self.model_path)

    def _synth_sync(self, text: str) -> np.ndarray:
        voice = self.voice or self._load()
        buf = io.BytesIO()
        voice.synthesize(text, buf)
        return decode_audio(buf.getvalue())

    async def synthesize(self, text: str) -> np.ndarray:
        return await asyncio.to_thread(self._synth_sync, text)


def make_tts(kind: str, *, voice: str = "", base_url: str = "", model: str = "tts-1",
             api_key: str = "EMPTY", model_path: str = "", edge_rate: str = EDGE_RATE,
             edge_pitch: str = EDGE_PITCH, edge_volume: str = EDGE_VOLUME):
    if kind == "synth":
        return SynthTTS()
    if kind == "url":
        if not base_url:
            raise ValueError("url TTS needs --tts-url (OpenAI-compatible base, e.g. http://host:port/v1)")
        return UrlTTS(base_url=base_url, model=model, voice=voice, api_key=api_key)
    if kind == "edge":
        return EdgeTTS(voice=voice or "zh-CN-XiaoxiaoNeural", rate=edge_rate,
                       pitch=edge_pitch, volume=edge_volume)
    if kind == "piper":
        if not model_path:
            raise ValueError("piper TTS needs --puppet-piper-model (path to the .onnx voice)")
        return PiperTTS(model_path=model_path)
    raise ValueError(kind)
