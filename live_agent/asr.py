"""ASR client (Qwen3-ASR served by vLLM, OpenAI transcription API) and audio helpers."""

from __future__ import annotations

import io
import wave

import numpy as np


def to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """float32 [S] or [S, C] in [-1, 1] -> 16-bit mono WAV bytes."""
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 2:
        a = a.mean(axis=1)
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


def _strip_tags(text: str) -> str:
    """Qwen3-ASR may prefix 'language Chinese<asr_text>'; keep only the transcript."""
    if "<asr_text>" in text:
        text = text.split("<asr_text>", 1)[1]
    return text.strip()
