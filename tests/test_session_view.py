"""SessionView: successive sessions on one shared generator are numbered from 0 and isolated."""

from __future__ import annotations

import asyncio

from live_agent.generator.base import SessionView
from live_agent.generator.mock import MockGenerator


async def _one_session(backend, n):
    view = SessionView(backend)
    await view.start()
    for k in range(n):
        await view.submit(k, f"prompt {k}")
    got = []
    agen = view.chunks()
    while len(got) < 4 * n:
        got.append(await agen.__anext__())
    await view.close()
    return view, got


def test_session_view_renumbers_and_isolates():
    async def main():
        backend = MockGenerator(teacher_s=0.1, chunk_s=0.05, speed=50.0)
        await backend.start()
        v1, c1 = await _one_session(backend, 2)
        v2, c2 = await _one_session(backend, 2)
        await backend.close()
        return v1, c1, v2, c2

    v1, c1, v2, c2 = asyncio.run(main())
    assert sorted({c.request_index for c in c1}) == [0, 1]
    assert sorted({c.request_index for c in c2}) == [0, 1]
    assert v2.next_request_index == 2
    assert all(t.request_index >= 0 for t in v2.timings)
