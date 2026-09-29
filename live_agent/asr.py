"""ASR client (Qwen3-ASR served by vLLM, OpenAI transcription API) and audio helpers."""

from __future__ import annotations

import io
import wave

import numpy as np


ASR_RATE = 16000  # Qwen3-ASR native rate; the vLLM endpoint rejects 32 kHz WAV (measured locally)


def resample(a: np.ndarray, sr: int, target: int = ASR_RATE) -> np.ndarray:
    if sr == target or len(a) == 0:
        return a
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(sr, target)
    return resample_poly(a, target // g, sr // g).astype(np.float32)


def to_wav_bytes(audio: np.ndarray, sample_rate: int, target_rate: int | None = ASR_RATE) -> bytes:
    """float32 [S] or [S, C] in [-1, 1] -> 16-bit mono WAV bytes (resampled to ``target_rate``)."""
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 2:
        a = a.mean(axis=1)
    if target_rate is not None:
        a, sample_rate = resample(a, sample_rate, target_rate), target_rate
    pcm = (np.clip(a, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


def decode_audio_bytes(data: bytes, target_sr: int = 16000) -> np.ndarray:
    """Decode any container (webm/opus from the browser, wav, ...) to mono float32 at target_sr."""
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


class OpenAIASR:
    def __init__(self, base_url: str = "http://127.0.0.1:8103/v1", model: str = "qwen3-asr",
                 timeout_s: float = 30.0):
        from openai import AsyncOpenAI, OpenAI

        self.model = model
        self._async = AsyncOpenAI(base_url=base_url, api_key="EMPTY", timeout=timeout_s)
        self._sync = OpenAI(base_url=base_url, api_key="EMPTY", timeout=timeout_s)

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        r = await self._async.audio.transcriptions.create(
            model=self.model, file=("audio.wav", to_wav_bytes(audio, sample_rate), "audio/wav"))
        return _strip_tags(r.text)

    def transcribe_sync(self, audio: np.ndarray, sample_rate: int) -> str:
        r = self._sync.audio.transcriptions.create(
            model=self.model, file=("audio.wav", to_wav_bytes(audio, sample_rate), "audio/wav"))
        return _strip_tags(r.text)


class HostedRealtimeASR:
    """Speech recognition through a hosted realtime audio model (Alibaba Model Studio realtime WebSocket API, e.g.
    qwen-audio-3.0-realtime-plus): frees the GPU the local Qwen3-ASR needs. One connection per utterance: the audio
    is appended as 16 kHz PCM16, committed, and the input-audio transcription is returned (the model's own reply,
    asked to be a verbatim transcript, is the fallback). ~6.5 s for a 5 s clip sent at once [measured locally]."""

    PROMPT = "你是语音转写器。把用户说的话逐字写出来，不要回答、不要改写、不要加任何别的字。"

    def __init__(self, url: str, model: str, api_key: str, timeout_s: float = 20.0):
        self.url = f"{url}{'&' if '?' in url else '?'}model={model}"
        self.model, self.api_key, self.timeout_s = model, api_key, timeout_s

    @staticmethod
    def _pcm16(audio: np.ndarray, sample_rate: int) -> bytes:
        a = np.asarray(audio, dtype=np.float32)
        if a.ndim == 2:
            a = a.mean(axis=1)
        if sample_rate != 16000 and len(a):
            n = int(round(len(a) * 16000 / sample_rate))
            a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
        return (np.clip(a, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

    async def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        import asyncio
        import base64
        import json

        import websockets

        pcm = self._pcm16(audio, sample_rate)
        async with websockets.connect(self.url, additional_headers={"Authorization": f"Bearer {self.api_key}"},
                                      open_timeout=10) as ws:
            await asyncio.wait_for(ws.recv(), self.timeout_s)  # session.created
            await ws.send(json.dumps({"type": "session.update", "session": {
                "modalities": ["text"], "instructions": self.PROMPT, "input_audio_format": "pcm16",
                "input_audio_transcription": {"model": self.model}, "turn_detection": None}}))
            for i in range(0, len(pcm), 6400):  # 0.2 s per message
                await ws.send(json.dumps({"type": "input_audio_buffer.append",
                                          "audio": base64.b64encode(pcm[i:i + 6400]).decode()}))
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await ws.send(json.dumps({"type": "response.create"}))
            transcript, reply = None, []
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), self.timeout_s))
                kind = m.get("type", "")
                if kind == "conversation.item.input_audio_transcription.completed":
                    transcript = m.get("transcript")
                elif kind == "response.text.delta":
                    reply.append(m.get("delta", ""))
                elif kind == "error":
                    raise RuntimeError(str(m.get("error") or m)[:200])
                elif kind == "response.done":
                    break
        return (transcript or "".join(reply)).strip()

    def transcribe_sync(self, audio: np.ndarray, sample_rate: int) -> str:
        import asyncio

        return asyncio.run(self.transcribe(audio, sample_rate))  # called from a worker thread


def _strip_tags(text: str) -> str:
    """Qwen3-ASR may prefix 'language Chinese<asr_text>'; keep only the transcript."""
    if "<asr_text>" in text:
        text = text.split("<asr_text>", 1)[1]
    return text.strip()
