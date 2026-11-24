"""Teacher prosody reaches Edge without changing text or losing the audio tail."""

import asyncio
import io
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.io.wavfile import write

from live_agent import tts


def test_teacher_voice_keeps_xiaoxiao_with_a_restrained_default_profile():
    voice = tts.make_tts("edge")
    assert voice.voice == "zh-CN-XiaoxiaoNeural"
    assert (voice.rate, voice.pitch, voice.volume) == ("-4%", "-8Hz", "+0%")


def test_provider_receives_overrides_and_returns_the_complete_utterance(monkeypatch):
    # Include audible content past the old fixed request window. The transport
    # must return it; the generator separately decides how much video to render.
    sr = tts.TTS_RATE
    samples = np.zeros(round(6.4 * sr), dtype=np.float32)
    samples[5 * sr:6 * sr] = 0.2 * np.sin(2 * np.pi * 230 * np.arange(sr) / sr)
    encoded = io.BytesIO()
    write(encoded, sr, samples)
    payload = encoded.getvalue()
    calls = []

    class Communicate:
        def __init__(self, text, voice, **options):
            calls.append((text, voice, options))

        async def stream(self):
            yield {"type": "SentenceBoundary", "text": "provider metadata"}
            # Providers can split the container header or tail across packets.
            for start in range(0, len(payload), 7311):
                yield {"type": "audio", "data": payload[start:start + 7311]}

    monkeypatch.setattr(tts.importlib, "import_module",
                        lambda name: SimpleNamespace(Communicate=Communicate))
    client = tts.make_tts("edge", voice="zh-CN-XiaoxiaoNeural", edge_rate="-7%",
                          edge_pitch="-10Hz", edge_volume="+2%")
    text = "先看分母。它表示平均分成了几份。"
    audio = asyncio.run(client.synthesize(text))
    assert calls == [(text, "zh-CN-XiaoxiaoNeural",
                      {"rate": "-7%", "pitch": "-10Hz", "volume": "+2%"})]
    assert audio.dtype == np.float32
    assert audio.shape == samples.shape
    np.testing.assert_allclose(audio, samples, atol=1e-6)
    assert np.max(np.abs(audio[5 * sr:])) > 0.1


@pytest.mark.parametrize("option,value", [
    ("rate", "slow"), ("rate", "4%"), ("rate", "+1%\n"),
    ("pitch", "-8%"), ("pitch", "8Hz"), ("pitch", 8),
    ("volume", "+2Hz"), ("volume", "0%"),
])
def test_invalid_edge_prosody_fails_before_opening_a_network_session(option, value, monkeypatch):
    def unexpected_import(name):
        raise AssertionError("invalid settings must fail before loading the provider")

    monkeypatch.setattr(tts.importlib, "import_module", unexpected_import)
    with pytest.raises(ValueError, match=option):
        tts.EdgeTTS(**{option: value})


def test_provider_without_audio_reports_failure(monkeypatch):
    class Communicate:
        def __init__(self, *args, **kwargs):
            pass

        async def stream(self):
            yield {"type": "SentenceBoundary", "text": "no audio follows"}

    monkeypatch.setattr(tts.importlib, "import_module",
                        lambda name: SimpleNamespace(Communicate=Communicate))
    with pytest.raises(RuntimeError, match="returned no audio"):
        asyncio.run(tts.EdgeTTS().synthesize("先看分母。"))
