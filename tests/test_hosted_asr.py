"""Hosted ASR lifecycle checks without a provider, credentials or recorded speech."""

from __future__ import annotations

import asyncio
import base64
import json
import time

import numpy as np
import pytest

from live_agent.asr import HostedRealtimeASR


class Wire:
    def __init__(self, events, *, initial=None, update=None, commit=None, heartbeat=False):
        self.events = events
        self.initial = initial or {"type": "session.created"}
        self.update = update or [{"type": "session.updated"}]
        self.commit = [{"type": "input_audio_buffer.committed"}] if commit is None else commit
        self.heartbeat = heartbeat
        self.queue = None
        self.sent = []
        self.updated = self.committed = self.closed = False
        self.connect_kwargs = {}

    def connect(self, url, **kwargs):
        self.connect_kwargs = kwargs
        self.url = url
        return self

    async def __aenter__(self):
        self.queue = asyncio.Queue()
        self.queue.put_nowait(self.initial)
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def send(self, message):
        event = json.loads(message)
        self.sent.append(event)
        kind = event["type"]
        if kind == "session.update":
            for item in self.update:
                self.queue.put_nowait(item)
        elif kind == "input_audio_buffer.append":
            assert self.updated, "audio sent before configuration was acknowledged"
        elif kind == "input_audio_buffer.commit":
            for item in self.commit:
                self.queue.put_nowait(item)
        elif kind == "response.create":
            assert any(item["type"] == "input_audio_buffer.commit" for item in self.sent), (
                "inference requested before audio commit")
            for item in self.events:
                self.queue.put_nowait(item)

    async def recv(self):
        if self.heartbeat and self.committed and self.queue.empty():
            await asyncio.sleep(0.002)
            return json.dumps({"type": "rate_limits.updated"})
        event = await self.queue.get()
        self.updated |= event["type"] == "session.updated"
        self.committed |= event["type"] == "input_audio_buffer.committed"
        return json.dumps(event)


def transcribe(monkeypatch, wire, *, timeout=0.3):
    import websockets

    monkeypatch.setattr(websockets, "connect", wire.connect)
    client = HostedRealtimeASR("wss://provider.example/realtime", "qwen-audio-3.0-realtime-plus", "test-key", timeout)
    return asyncio.run(client.transcribe(np.zeros(3200, dtype=np.float32), 16000))


def test_configuration_ack_precedes_upload_and_commit_precedes_inference_with_preserved_parameters(monkeypatch):
    wire = Wire([{"type": "response.text.done", "text": "请讲乘法。"}],
                update=[{"type": "rate_limits.updated"}, {"type": "session.updated"}],
                commit=[{"type": "conversation.item.input_audio_transcription.delta", "text": "请讲"},
                        {"type": "input_audio_buffer.committed"}])
    assert transcribe(monkeypatch, wire) == "请讲乘法。"
    session = wire.sent[0]["session"]
    assert session["turn_detection"] is None
    assert session["input_audio_format"] == "pcm16"
    assert session["input_audio_transcription"] == {"model": "qwen-audio-3.0-realtime-plus"}
    audio = next(event["audio"] for event in wire.sent if event["type"] == "input_audio_buffer.append")
    assert len(base64.b64decode(audio)) == 6400
    assert wire.connect_kwargs["close_timeout"] <= 1.0 and wire.closed
    kinds = [event["type"] for event in wire.sent]
    assert kinds[-2:] == ["input_audio_buffer.commit", "response.create"]


def test_final_input_transcription_does_not_wait_for_assistant_response_done(monkeypatch):
    wire = Wire([{"type": "conversation.item.input_audio_transcription.completed", "transcript": "老师你好。"}])
    assert transcribe(monkeypatch, wire) == "老师你好。"
    assert wire.closed


def test_final_input_transcription_before_commit_ack_ends_the_operation(monkeypatch):
    wire = Wire([], commit=[{"type": "conversation.item.input_audio_transcription.completed", "transcript": "谢谢老师。"}])
    assert transcribe(monkeypatch, wire) == "谢谢老师。"
    assert not wire.committed


def test_missing_commit_ack_does_not_block_completed_transcription(monkeypatch):
    wire = Wire([{"type": "conversation.item.input_audio_transcription.completed", "transcript": "讲一下分数。"}], commit=[])
    assert transcribe(monkeypatch, wire) == "讲一下分数。"
    assert not wire.committed and wire.closed


def test_delayed_commit_ack_does_not_block_the_completed_text_fallback(monkeypatch):
    wire = Wire([{"type": "response.text.delta", "delta": "请讲"},
                 {"type": "input_audio_buffer.committed"},
                 {"type": "response.text.done", "text": "请讲乘法。"}], commit=[])
    assert transcribe(monkeypatch, wire) == "请讲乘法。"


def test_completed_fallback_text_is_authoritative_without_response_done(monkeypatch):
    wire = Wire([{"type": "response.text.delta", "delta": "不完整"},
                 {"type": "response.text.done", "text": "完整的语音转写。"}])
    assert transcribe(monkeypatch, wire) == "完整的语音转写。"


def test_explicit_empty_transcription_does_not_become_a_generated_reply(monkeypatch):
    wire = Wire([{"type": "conversation.item.input_audio_transcription.completed", "transcript": ""},
                 {"type": "response.text.done", "text": "我猜用户说了你好。"}])
    assert transcribe(monkeypatch, wire) == ""


@pytest.mark.parametrize("where", ["initial", "update", "commit", "result"])
def test_provider_errors_fail_at_each_acknowledgement_stage(monkeypatch, where):
    event = {"type": "error", "error": {"type": "invalid_request_error", "code": "invalid_value", "message": "private request data"}}
    options = {}
    events = [{"type": "response.text.done", "text": "unused"}]
    if where == "initial":
        options["initial"] = event
    elif where in ("update", "commit"):
        options[where] = [event]
    else:
        events = [event]
    wire = Wire(events, **options)
    with pytest.raises(RuntimeError, match="invalid_request_error invalid_value") as failure:
        transcribe(monkeypatch, wire)
    assert "private request data" not in str(failure.value)
    assert wire.closed


def test_failed_transcription_is_terminal_without_waiting_for_timeout(monkeypatch):
    wire = Wire([{"type": "conversation.item.input_audio_transcription.failed",
                   "error": {"type": "transcription_error", "code": "transcription_failed"}}])
    with pytest.raises(RuntimeError, match="transcription_failed"):
        transcribe(monkeypatch, wire)


def test_failed_response_does_not_return_its_partial_text(monkeypatch):
    wire = Wire([{"type": "response.text.delta", "delta": "半句话"},
                 {"type": "response.done", "response": {"status": "failed"}}])
    with pytest.raises(RuntimeError, match="did not complete"):
        transcribe(monkeypatch, wire)


def test_completed_response_can_supply_full_text_without_delta_events(monkeypatch):
    wire = Wire([{"type": "response.done", "response": {"status": "completed", "output": [
        {"content": [{"type": "text", "text": "讲一下分数。"}]}]}}])
    assert transcribe(monkeypatch, wire) == "讲一下分数。"


def test_nonterminal_events_do_not_extend_the_total_deadline(monkeypatch):
    wire = Wire([], heartbeat=True)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline during transcription result"):
        transcribe(monkeypatch, wire, timeout=0.04)
    assert time.monotonic() - started < 0.3
    assert wire.closed


def test_connection_cleanup_is_inside_the_total_deadline(monkeypatch):
    class SlowClose(Wire):
        async def __aexit__(self, *args):
            try:
                await asyncio.sleep(1)
            finally:
                self.closed = True

    wire = SlowClose([{"type": "response.text.done", "text": "已完成"}])
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="deadline during transcription result"):
        transcribe(monkeypatch, wire, timeout=0.04)
    assert time.monotonic() - started < 0.3
    assert wire.closed


def test_cancellation_closes_connection_and_is_not_converted_to_failure(monkeypatch):
    import websockets

    wire = Wire([])
    monkeypatch.setattr(websockets, "connect", wire.connect)

    async def main():
        client = HostedRealtimeASR("wss://provider.example", "model", "test-key")
        task = asyncio.create_task(client.transcribe(np.zeros(100), 16000))
        while not wire.committed:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert wire.closed

    asyncio.run(main())
