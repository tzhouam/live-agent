"""LLM / VLM clients.

Production: OpenAI-compatible endpoints served locally with vLLM (e.g. Qwen3-8B for the
responder/planner, Qwen3-VL-8B-Instruct for the QC judge). Tests: ``ScriptedLLM``.
Personal memory never leaves the machine: only local endpoints are configured by default.
"""

from __future__ import annotations

import base64
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


class ChatLLM(Protocol):
    async def chat(self, messages: list[dict[str, Any]], *, max_tokens: int = 512,
                   temperature: float = 0.3, json_mode: bool = False) -> str: ...


@dataclass
class OpenAICompatLLM:
    base_url: str  # e.g. http://127.0.0.1:8100/v1
    model: str
    api_key: str = "EMPTY"
    timeout_s: float = 30.0
    enable_thinking: bool = False  # Qwen3: disable thinking for low latency

    def __post_init__(self) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout_s)

    async def warmup(self) -> None:
        """The SDK imports its resource/type modules lazily on the first request (~1 s from the
        network filesystem here, measured locally), blocking the event loop: do it at start-up."""
        try:
            await self.chat([{"role": "user", "content": "hi"}], max_tokens=1)
        except Exception:  # noqa: BLE001 - a server that is down is reported by the first real call
            pass

    async def chat(self, messages, *, max_tokens=512, temperature=0.3, json_mode=False) -> str:
        extra: dict[str, Any] = {"chat_template_kwargs": {"enable_thinking": self.enable_thinking}}
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        r = await self._client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=max_tokens,
            temperature=temperature, extra_body=extra, **kwargs)
        return r.choices[0].message.content or ""


class ScriptedLLM:
    """Deterministic stand-in: a function from messages to reply text (tests, simulation)."""

    def __init__(self, fn: Callable[[list[dict[str, Any]]], str]):
        self.fn = fn
        self.calls: list[list[dict[str, Any]]] = []

    async def chat(self, messages, *, max_tokens=512, temperature=0.3, json_mode=False) -> str:
        self.calls.append(messages)
        return self.fn(messages)


def parse_json(text: str) -> Any:
    """Extract the first JSON object from an LLM reply (tolerates code fences / thinking tags)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    return json.loads(m.group(0))


def frame_to_data_url(frame: np.ndarray, *, fmt: str = "JPEG", quality: int = 85) -> str:
    """Encode an HxWx3 uint8 frame as a data URL for VLM requests."""
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, format=fmt, quality=quality)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()
