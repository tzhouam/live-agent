"""E2 runner: execute scripted tasks against the live-agent stack and write SCHEMA.md logs.

Conditions (proposal §7.2): A1 open loop; A2 full; A2-noqc (no online checks);
A2-repeat (RQ2 contrast: repeat instead of forward correction); B0 (scripted, no input).

Time: all orchestrator times are monotonic seconds; with a sped-up mock stack they are
rescaled by ``speed`` so that deadlines (15 s ...) apply in *simulated* seconds.
Chains: the director's chains are mapped to the task's ground-truth chains through the
utterance uid that opened / revised them.

Usage:
    python -m live_agent.eval.runner --suite eval/tasks/e2_committed.jsonl \
        --conditions A1 A2 --seeds 0 1 --out .cache/e2 [--mock --speed 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import zlib
from pathlib import Path
from typing import Any

from live_agent.capability import CapabilityManifest, Status
from live_agent.director.director import Director, DirectorMode
from live_agent.eval.schema import SessionLogWriter
from live_agent.eval.sim_user import SimulatedUser
from live_agent.eval.tasks import Task, load_suite
from live_agent.ledger import StateLedger
from live_agent.orchestrator import CorrectionMode, Orchestrator, OrchestratorConfig
from live_agent.sim import SimClient
from live_agent.timeline import EventLog, LockScheduler, SchedulerConfig
from live_agent.types import EventType, Utterance, now

CONDITIONS = {
    "A1": dict(mode=DirectorMode.OPEN_LOOP, qc=False, correction=CorrectionMode.NONE),
    "A2": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.GRADIENT),
    "A2-noqc": dict(mode=DirectorMode.CLOSED_LOOP, qc=False, correction=CorrectionMode.NONE),
    "A2-repeat": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.REPEAT),
}


def convert(orch: Orchestrator, user_events: list[dict], *, t0: float, speed: float) -> list[dict]:
    """Map orchestrator TimelineEvents + sim-user events into SCHEMA.md events."""
    ts = lambda t: (t - t0) * speed  # noqa: E731
    uid_to_chain = {e["uid"]: e["chain_id"] for e in user_events if e["type"] == "chain_annotation"}
    dchain_to_gt: dict[str, str] = {}
    for c in orch.director.chains.values():
        for uid in [c.opened_by, *c.revisions]:
            if uid in uid_to_chain:
                dchain_to_gt[c.chain_id] = uid_to_chain[uid]
    out: list[dict[str, Any]] = []
    for e in user_events:  # already on the shared clock (monotonic) -> rescale
        e = dict(e)
        for k in ("t_start", "t_end", "t"):
            if k in e:
                e[k] = ts(e[k])
        out.append(e)
    script_chains = {k: [dchain_to_gt.get(c) for c in s.chain_ids if dchain_to_gt.get(c)]
                     for k, s in orch.scripts.items()}
    presented_start: dict[int, float] = {}
    for ev in orch.log.events:
        d, k = ev.data, ev.request_index
        if ev.type == EventType.LOCK and k is not None:
            out.append({"type": "lock", "t": ts(ev.t), "request": k, "chain_ids": script_chains.get(k, []),
                        "plan_version": d.get("plan_version")})
        elif ev.type == EventType.CHUNK_PRESENTED:
            out.append({"type": "chunk_presented", "request": k, "chunk": ev.chunk_index,
                        "t_start": ts(ev.t), "t_end": ts(d["t_end"])})
            if ev.chunk_index == 0:
                presented_start[k] = ts(ev.t)
        elif ev.type == EventType.VERDICT and d.get("kind") == "action":
            step = orch.scripts[k].provenance.get("step") if k in orch.scripts else None
            for cid in script_chains.get(k, []):
                v = {"type": "verdict", "source": "judge", "label": d["label"], "chain_id": cid,
                     "request": k, "chunk": 0, "t_evidence": ts(d["t_evidence"]), "qid": d.get("qid")}
                if step is not None:  # multistep: the director's step index (action steps only)
                    v["step"] = step
                out.append(v)
        elif ev.type == EventType.COMPLETION_CLAIM:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "completion_claim", "chain_id": gt, "t": presented_start.get(k, ts(ev.t)),
                            "request": k})
        elif ev.type == EventType.REFUSAL:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "refusal", "chain_id": gt, "t": ts(ev.t),
                            "kind": "degraded" if d.get("degraded") else "refused", "reason": d.get("reason", "")})
        elif ev.type == EventType.PLAYBACK_STOP:
            out.append({"type": "playback_stop", "t": ts(ev.t), "reason": "erasure" if d.get("erasure") else "barge_in"})
        elif ev.type == EventType.REPAIR:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "repair_assignment", "chain_id": gt,
                            "arm": "forward_correction" if d.get("mode") == "gradient" else "repeat",
                            "failure_request": k, "target_request": d.get("earliest_correctable"),
                            "C": d.get("chain_cost_s")})
    # Speech onset: the first presented request carrying a line for a chain.
    for k, s in sorted(orch.scripts.items()):
        if s.transcript and k in presented_start:
            for cid in script_chains.get(k, []):
                out.append({"type": "speech_onset", "t": presented_start[k], "on_topic": True,
                            "chain_id": cid, "request": k})
    return out


async def run_task(task: Task, condition: str, seed: int, *, factory, speed: float, out_dir: Path) -> Path:
    cfg = CONDITIONS[condition]
    # Per-(task, seed) RNG stream, identical across conditions (paired design), different across tasks.
    orch, client = factory(cfg, zlib.crc32(f"{task.task_id}/{seed}".encode()))
    client.orchestrator = orch
    t0 = now()
    user_events: list[dict] = []

    async def send(text: str, meta: dict) -> dict:
        t_start = now()
        if meta.get("barge_in"):
            await orch.on_speech_start(t_start)
        await orch.on_user_utterance(Utterance(meta["uid"], "user", text, now()))
        return {"t_start": t_start, "t_end": now()}

    user = SimulatedUser(task, send, clock=now, sleep=lambda dt: asyncio.sleep(dt / speed),
                         session_id=f"{condition}-{task.task_id}-s{seed}", on_event=user_events.append)
    path = out_dir / f"{condition}-{task.task_id}-s{seed}.jsonl"
    if getattr(client, "recorder", None) is not None:
        client.recorder.path = path.with_suffix(".mp4")  # adjudication looks for <log>.mp4
    client.start()
    await orch.start()
    try:
        await user.run()
        # let the last requests present and be checked
        await asyncio.sleep(15.0 / speed)
    finally:
        await orch.stop()
        client.close()
    with SessionLogWriter(path, session_id=f"{condition}-{task.task_id}-s{seed}", condition=condition,
                          task_id=task.task_id, seed=seed, mode="simulation",
                          backbone=orch.gen.info.name) as w:
        for ev in convert(orch, user_events, t0=t0, speed=speed):
            w.write(ev)
    return path


def mock_factory(config_dir: Path, *, speed: float, llm, p_default: float = 0.7):
    from live_agent.generator.mock import MockGenerator
    from live_agent.qc.judge import ForwardCorrector, MockJudge

    canon = json.loads((config_dir / "canon.json").read_text(encoding="utf-8"))

    def factory(cfg: dict, seed: int):
        manifest = CapabilityManifest.load(config_dir / "capabilities.json")
        manifest.min_status = Status.DOCUMENTED  # simulation: capabilities are not yet executed
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = MockGenerator(teacher_s=1.0, chunk_s=0.5, speed=speed, seed=seed)
        sched = LockScheduler(SchedulerConfig(request_s=5.0 / speed, sigma_s=0.5 / speed, delta_s=0.01,
                                              lambda_prior_s=3.0 / speed, time_scale=1.0 / speed))
        client = SimClient(speed=speed)
        orch = Orchestrator(gen, director, sched, client, judge=MockJudge(p_default=p_default, seed=seed),
                            corrector=ForwardCorrector(None), log=EventLog(),
                            cfg=OrchestratorConfig(correction_mode=cfg["correction"], qc_enabled=cfg["qc"],
                                                   seed=seed))
        return orch, client

    return factory


def live_factory(config_dir: Path, *, backend, llm, vlm, record_dir: Path | None = None,
                 allow_uncalibrated: bool = False):
    """Real stack: shared generator backend (e.g. TaoMate-H3; one session at a time through
    SessionView), LLM responder, VLM judge, LLM forward corrector. Real time (speed 1)."""
    from live_agent.generator.base import SessionView
    from live_agent.qc.judge import ForwardCorrector, VLMJudge
    from live_agent.sim import Recorder

    canon = json.loads((config_dir / "canon.json").read_text(encoding="utf-8"))
    counter = iter(range(10**9))

    def factory(cfg: dict, seed: int):
        manifest = CapabilityManifest.load(config_dir / "capabilities.json")
        if allow_uncalibrated:
            manifest.min_status = Status.DOCUMENTED  # pre-E1 qualification runs only; never for E2 results
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = SessionView(backend)
        sched = LockScheduler(SchedulerConfig(request_s=backend.info.request_seconds))
        rec = Recorder(record_dir / f"session-{next(counter):03d}.mp4") if record_dir else None
        client = SimClient(speed=1.0, recorder=rec)
        orch = Orchestrator(gen, director, sched, client, judge=VLMJudge(vlm), corrector=ForwardCorrector(llm),
                            log=EventLog(), cfg=OrchestratorConfig(correction_mode=cfg["correction"],
                                                                   qc_enabled=cfg["qc"], seed=seed))
        return orch, client

    return factory


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default="eval/tasks/e2_committed.jsonl")
    p.add_argument("--config", default="configs/persona_hanfu")
    p.add_argument("--conditions", nargs="+", default=["A1", "A2"])
    p.add_argument("--seeds", nargs="+", type=int, default=[0])
    p.add_argument("--tasks", nargs="*", default=None)
    p.add_argument("--out", default=".cache/e2")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--llm-url", default="http://127.0.0.1:8101/v1")
    p.add_argument("--llm-model", default="qwen3-8b")
    p.add_argument("--p-default", type=float, default=0.7, help="mock judge success probability")
    p.add_argument("--generator", default="mock", choices=["mock", "taomate_h3"])
    p.add_argument("--vlm-url", default="http://127.0.0.1:8102/v1")
    p.add_argument("--vlm-model", default="qwen3-vl-8b")
    p.add_argument("--allow-uncalibrated", action="store_true",
                   help="live stack: accept 'documented' capabilities (M1 qualification before E1)")
    p.add_argument("--record", action="store_true", help="save the presented stream as MP4 (live stack)")
    args, rest = p.parse_known_args()
    args.extra = rest
    asyncio.run(_main(args))


async def _main(args) -> None:
    from live_agent.llm import OpenAICompatLLM

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in load_suite(args.suite) if not args.tasks or t.task_id in args.tasks]
    llm = OpenAICompatLLM(args.llm_url, args.llm_model)
    backend = None
    if args.generator == "mock":
        speed = args.speed
        factory = mock_factory(Path(args.config), speed=speed, llm=llm, p_default=args.p_default)
    else:
        from live_agent.generator.taomate_h3 import TaoMateH3Generator

        speed = 1.0
        backend = TaoMateH3Generator.from_args(args)
        await backend.start()
        factory = live_factory(Path(args.config), backend=backend, llm=llm,
                               vlm=OpenAICompatLLM(args.vlm_url, args.vlm_model),
                               record_dir=out if args.record else None,
                               allow_uncalibrated=args.allow_uncalibrated)
    try:
        for cond in args.conditions:
            for seed in args.seeds:
                for t in tasks:
                    path = await run_task(t, cond, seed, factory=factory, speed=speed, out_dir=out)
                    print(path, flush=True)
    finally:
        if backend is not None:
            await backend.close()


if __name__ == "__main__":
    main()
