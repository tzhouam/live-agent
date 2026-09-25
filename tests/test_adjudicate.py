"""Record -> blinded adjudication page -> labels -> merge -> scoring uses the adjudicated verdict."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from live_agent.eval.adjudicate import merge, prepare, presented_segments, session_to_video, video_to_session
from live_agent.eval.runner import mock_factory, run_task
from live_agent.eval.schema import load_session
from live_agent.eval.scoring import score_session
from live_agent.eval.tasks import load_suite
from live_agent.llm import ScriptedLLM
from live_agent.sim import Recorder

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = "/usr/bin/ffmpeg"


def responder(messages):
    return json.dumps({"relation": "new", "kind": "action", "steps": [{"intent": "drink_tea", "line": "好的。"}]})


def test_time_mapping_skips_stalls():
    ev = [{"type": "chunk_presented", "t_start": 10.0, "t_end": 11.0},
          {"type": "chunk_presented", "t_start": 12.0, "t_end": 13.0}]  # 1 s stall in between
    segs = presented_segments(ev)
    assert video_to_session(segs, 0.5) == 10.5
    assert video_to_session(segs, 1.5) == 12.5
    assert session_to_video(segs, 12.5) == 1.5


@pytest.mark.skipif(not Path(FFMPEG).exists(), reason="needs ffmpeg with libx264")
def test_adjudication_roundtrip(tmp_path):
    task = {t.task_id: t for t in load_suite(ROOT / "eval/tasks/e2_committed.jsonl")}["E2-A01"]
    base = mock_factory(ROOT / "configs/persona_hanfu", speed=20.0, llm=ScriptedLLM(responder), p_default=0.0)

    def factory(cfg, seed):
        orch, client = base(cfg, seed)
        client.recorder = Recorder(tmp_path / "x.mp4", ffmpeg=FFMPEG)
        return orch, client

    log = asyncio.run(run_task(task, "A2", 0, factory=factory, speed=20.0, out_dir=tmp_path))
    assert log.with_suffix(".mp4").exists()
    before = score_session(load_session(log))
    assert before.chains[0].outcome.value != "success"  # the mock judge (p=0) never saw compliance
    batch = tmp_path / "batch"
    page = prepare([log], batch)
    items = json.loads(page.read_text(encoding="utf-8").split("const ITEMS = ")[1].split(";\n")[0])
    assert len(items) == 1 and "E2-A01" not in json.dumps(items)  # blinded
    it = items[0]
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({f"{it['id']}/0": {"label": "complied", "v_first": it["v_origin"] + 2.0}}))
    merge(batch, labels, annotator="t")
    after = score_session(load_session(log))
    assert after.chains[0].outcome.value == "success"
