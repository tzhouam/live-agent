"""LLM / VLM clients.

Local vLLM and configured hosted providers supply the responder/planner and visual judge.
Tests use ``ScriptedLLM``. Memory is stored locally; recalled memories, learner-profile
context and other prompt inputs are sent to the configured provider for each model call.
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

    async def close(self) -> None:
        await self._client.close()

    async def chat(self, messages, *, max_tokens=512, temperature=0.3, json_mode=False) -> str:
        if "dashscope" in self.base_url or "aliyuncs.com" in self.base_url:  # hosted Qwen: top-level switch
            extra: dict[str, Any] = {"enable_thinking": self.enable_thinking}
        else:  # local vLLM: the chat template decides
            extra = {"chat_template_kwargs": {"enable_thinking": self.enable_thinking}}
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        r = await self._client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=max_tokens,
            temperature=temperature, extra_body=extra, **kwargs)
        return r.choices[0].message.content or ""


@dataclass
class AnthropicCompatLLM:
    """Anthropic Messages API client (e.g. Alibaba Model Studio's ``.../apps/anthropic`` endpoint for hosted Qwen).
    Same ``chat`` contract as OpenAICompatLLM; system messages go to the top-level ``system`` field."""

    base_url: str  # e.g. https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic
    model: str
    api_key: str = ""
    timeout_s: float = 30.0
    enable_thinking: bool = False

    def __post_init__(self) -> None:
        import httpx

        self._client = httpx.AsyncClient(timeout=self.timeout_s)

    async def warmup(self) -> None:
        try:
            await self.chat([{"role": "user", "content": "hi"}], max_tokens=1)
        except Exception:  # noqa: BLE001 - reported by the first real call
            pass

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(self, messages, *, max_tokens=512, temperature=0.3, json_mode=False) -> str:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system" and isinstance(m["content"], str))
        if json_mode:  # no response_format in this API: say it (the prompts already ask for JSON)
            system = (system + "\n\n" if system else "") + "只输出一个 JSON 对象，不要输出任何其他文字。"
        body: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature,
                                "messages": [m for m in messages if m["role"] != "system"]}
        if not self.enable_thinking:  # hybrid-thinking models (qwen3.8-flash) think by default: ~3x slower
            body["thinking"] = {"type": "disabled"}
        if system:
            body["system"] = system
        r = await self._client.post(self.base_url.rstrip("/") + "/v1/messages", json=body,
                                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        if r.status_code != 200:
            raise RuntimeError(f"LLM {r.status_code}: {r.text[:200]}")
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")


def make_chat_llm(base_url: str, model: str, api_key: str = "EMPTY"):
    """The client matching the endpoint's API: Anthropic Messages for ``.../anthropic`` URLs, else OpenAI-compatible."""
    if "/anthropic" in base_url:
        return AnthropicCompatLLM(base_url, model, api_key=api_key)
    return OpenAICompatLLM(base_url, model, api_key=api_key)


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


class RuleResponder(ScriptedLLM):
    """CPU-only stand-in for the responder LLM (demo / smoke runs without model servers).

    Maps an utterance to the responder JSON contract by keyword: a capability alias found in the
    text becomes an action step, "忘掉/忘记 X" becomes a forget request, anything else a short chat
    reply. It is deliberately simple — for running the stack, not for evaluation.
    """

    def __init__(self, manifest) -> None:
        import json as _json
        import re as _re

        aliases = []
        for c in manifest.caps.values():
            for a in [c.intent, *getattr(c, "aliases", [])]:
                if a and _re.search(r"[\u4e00-\u9fff]", a):
                    aliases.append((a, c.intent, c.phrase))
        aliases.sort(key=lambda x: -len(x[0]))  # longest alias first

        def fn(messages):
            text = messages[-1]["content"]
            closed = "intent" in messages[0]["content"]  # A2 prompt lists intents; A1 asks for actions
            m = _re.search(r"(?:忘掉|忘记|忘了|删掉|删除)(?:我)?(.{1,8}?)(?:的事|住在哪|吧|。|$)", text)
            if m and m.group(1).strip():
                return _json.dumps({"relation": "chat", "kind": "memory", "forget_term": m.group(1).strip(),
                                    "steps": [{"intent": "", "line": ""}]}, ensure_ascii=False)
            for alias, intent, phrase in aliases:
                if alias in text:
                    step = {"intent": intent, "line": f"好，我{alias}。"} if closed else \
                        {"action": phrase, "line": f"好，我{alias}。"}
                    return _json.dumps({"relation": "new", "kind": "action", "steps": [step]}, ensure_ascii=False)
            return _json.dumps({"relation": "chat", "kind": "chat",
                                "steps": [{"intent": "", "line": "嗯，我在听，你接着说。"}]}, ensure_ascii=False)

        super().__init__(fn)
