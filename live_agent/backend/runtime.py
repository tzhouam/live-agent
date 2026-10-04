"""Factories for backend-only models and scoped memory; credentials stay here."""

from __future__ import annotations

import argparse


def llm_api_key(args: argparse.Namespace) -> str:
    """The responder's API key comes from an environment variable (never argv: visible in ps); local vLLM
    needs none."""
    import os

    return os.environ.get(args.llm_api_key_env) or "EMPTY"


def make_generator(args: argparse.Namespace):
    if args.generator == "mock":
        from live_agent.generator.mock import MockGenerator

        return MockGenerator(size=(864, 480), render_text=True)  # portrait, like TaoMate-H3 480x864
    if args.generator == "taomate_h3":
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        return TaoMateH3Generator.from_args(args)
    if args.generator == "vllm_omni_h3":  # TaoMate-H3 served by vLLM-Omni (USP4) over its realtime WebSocket
        from live_agent.generator.vllm_omni_h3 import VllmOmniH3Generator

        return VllmOmniH3Generator.from_args(args)
    raise ValueError(args.generator)


def make_memory(args: argparse.Namespace, hello: dict, session_id: str, scope: str = "private"):
    if not args.memory_db:
        return None
    from live_agent.memory_bridge import MemoryBridge

    return MemoryBridge(args.memory_db, user_id=hello.get("user_id", "anon"),
                        stream_id=hello.get("stream_id", "stream-0"), session_id=session_id, mode=scope)


