"""Record -> blinded adjudication page -> labels -> merge -> scoring uses the adjudicated verdict."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from live_agent.eval.adjudicate import (
    default_key_path,
    merge,
    prepare,
    presented_segments,
    session_to_video,
    video_to_session,
)
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
    video = log.with_suffix(".mp4")
    assert video.exists()
    # plant condition-revealing container metadata: delivery must strip it
    tagged = tmp_path / "tagged.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(video), "-c", "copy", "-metadata",
                    f"title={log.stem}", str(tagged)], check=True)
    assert log.stem.encode() in tagged.read_bytes()
    os.replace(tagged, video)
    before = score_session(load_session(log))
    assert before.chains[0].outcome.value == "unadjudicated"  # primary: judge verdicts never count
    batch = tmp_path / "batch"
    page = prepare([log], batch)  # runs check_blinded on the delivered batch
    assert not (batch / "key.json").exists() and default_key_path(batch).exists()  # key kept apart
    media = list((batch / "media").iterdir())
    assert len(media) == 1 and not media[0].is_symlink() and log.stem.encode() not in media[0].read_bytes()
    assert not json.loads(default_key_path(batch).read_text())["media_warnings"]  # stripped by ffmpeg
    items = json.loads(page.read_text(encoding="utf-8").split("const ITEMS = ")[1].split(";\n")[0])
    assert "E2-A01" not in json.dumps(items)  # blinded
    it = next(i for i in items if i["type"] == "chain")
    sw = next(i for i in items if i["type"] == "sweep")
    assert it["criteria"]["checks"]  # preregistered checks frozen into the item
    lab = {f"{it['id']}/0": {"label": "complied", "v_first": it["v_origin"] + 2.0},
           f"{sw['id']}/0": {"complete": True, "v_seen": sw["v_len"], "claims": []}}
    ratings = []
    for name in ("R1", "R2"):  # two independent raters who agree
        p = tmp_path / f"labels-{name}.json"
        p.write_text(json.dumps(lab))
        ratings.append((p, name))
    res = merge(batch, ratings)
    assert res["agreed"] == 2 and not res["unresolved"]
    after = score_session(load_session(log))
    assert after.chains[0].outcome.value == "success" and after.claim_sweep
