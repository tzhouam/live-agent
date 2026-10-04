"""Compatibility entrypoint for the API backend; use live_agent.backend.app.

Browser pages are served independently by frontend/server.mjs.
"""

from live_agent.backend.app import build_app, main
from live_agent.backend.runtime import llm_api_key, make_generator, make_memory
from live_agent.backend.transport import WSTransport, encode_h264, encode_jpeg, panel_event, to_pcm16

__all__ = ["build_app", "main", "llm_api_key", "make_generator", "make_memory",
           "WSTransport", "encode_h264", "encode_jpeg", "panel_event", "to_pcm16"]

if __name__ == "__main__":
    main()
