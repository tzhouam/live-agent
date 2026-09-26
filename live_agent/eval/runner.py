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
    # RQ2: the repair arm is drawn per eligible failure point (seeded), logged per repair.
    "A2-rq2": dict(mode=DirectorMode.CLOSED_LOOP, qc=True, correction=CorrectionMode.RANDOMIZED),
}

CONTENT_DURATION_S = {"qa": 10.0, "explain": 30.0, "sing": 30.0}  # proposal §7 D table [proposed target]


def observation_horizon_s(task: Task) -> float:
    """How long after the last utterance media must be observed so every deadline D is covered."""
    d = 15.0
    for u in task.utterances:
        it = u.intent or {}
        kind = it.get("kind", task.kind)
        if kind == "multistep":
            steps = it.get("steps") or 1
            d = max(d, 15.0 * (len(steps) if isinstance(steps, list) else int(steps)))
        elif kind == "content":
            dur = it.get("prereg_duration_s") or CONTENT_DURATION_S.get(it.get("content_type", ""), 30.0)
            d = max(d, 15.0 + float(dur))
    return d + 5.0


def convert(orch: Orchestrator, user_events: list[dict], *, t0: float, speed: float) -> list[dict]:
    """Map orchestrator TimelineEvents + sim-user events into SCHEMA.md events."""
    ts = lambda t: (t - t0) * speed  # noqa: E731
    uid_to_chain = {e["uid"]: e["chain_id"] for e in user_events if e["type"] == "chain_annotation"}
    gt_uids: dict[str, list[str]] = {}  # GT chain -> uids of its new/revision utterances, in order
    for e in user_events:
        if e["type"] == "chain_annotation" and e["action"] in ("new", "revision"):
            gt_uids.setdefault(e["chain_id"], []).append(e["uid"])
    dchain_to_gt: dict[str, str] = {}
    dchain_uids: dict[str, list[str]] = {}
    for c in orch.director.chains.values():
        dchain_uids[c.chain_id] = [c.opened_by, *c.revisions]
        for uid in dchain_uids[c.chain_id]:
            if uid in uid_to_chain:
                dchain_to_gt[c.chain_id] = uid_to_chain[uid]

    def gt_of(dchain: str, drev: int | None) -> str | None:
        """GT chain of the utterance that defined director revision ``drev`` (a director chain
        revised by an utterance the ground truth treats as a new chain maps per revision)."""
        uids = dchain_uids.get(dchain, [])
        if drev is not None and 0 <= drev < len(uids):
            return uid_to_chain.get(uids[drev])
        return dchain_to_gt.get(dchain)

    def gt_revision(dchain: str, drev: int | None) -> int | None:
        """Director revision r -> GT revision index of the utterance that defined it."""
        uids = dchain_uids.get(dchain, [])
        gt = dchain_to_gt.get(dchain)
        if gt is None or drev is None or drev >= len(uids) or uids[drev] not in gt_uids.get(gt, []):
            return None
        return gt_uids[gt].index(uids[drev])

    # failure (request, director chain) -> earliest correctable request computed by the repair step
    ec = {(ev.request_index, ev.data.get("chain_id")): ev.data.get("earliest_correctable")
          for ev in orch.log.events if ev.type == EventType.REPAIR}
    out: list[dict[str, Any]] = []
    for e in user_events:  # already on the shared clock (monotonic) -> rescale
        e = dict(e)
        for k in ("t_start", "t_end", "t"):
            if k in e:
                e[k] = ts(e[k])
        out.append(e)
    for ev in orch.log.events:
        d, k = ev.data, ev.request_index
        script = orch.scripts.get(k) if k is not None else None
        dchains = script.chain_ids if script is not None else []
        if ev.type == EventType.LOCK and k is not None:
            out.append({"type": "lock", "t": ts(ev.t), "request": k,
                        "chain_ids": [dchain_to_gt[c] for c in dchains if c in dchain_to_gt],
                        "plan_version": d.get("plan_version")})
        elif ev.type == EventType.CHUNK_PRESENTED:
            out.append({"type": "chunk_presented", "request": k, "chunk": ev.chunk_index,
                        "t_start": ts(ev.t), "t_end": ts(d["t_end"])})
        elif ev.type == EventType.VERDICT and d.get("kind") == "action":
            for cid in d.get("chain_ids") or []:  # only the chain(s) the judged request served (exact)
                gt = gt_of(cid, d.get("revision"))
                if gt is None:
                    continue
                v = {"type": "verdict", "source": "judge", "label": d["label"], "chain_id": gt,
                     "request": k, "chunk": 0, "t_evidence": ts(d["t_evidence"]), "qid": d.get("qid")}
                rev = gt_revision(cid, d.get("revision"))
                if rev is not None:
                    v["revision"] = rev
                if d.get("step") is not None:  # multistep: the director's step index (action steps)
                    v["step"] = d["step"]
                if d["label"] == "not_complied":  # RQ2 eligibility audit
                    v["earliest_correctable"] = ec.get((k, cid))
                out.append(v)
        elif ev.type == EventType.COMPLETION_CLAIM:
            gt = gt_of(d.get("chain_id", ""), d.get("revision"))
            if gt:
                c = {"type": "completion_claim", "chain_id": gt, "t": ts(ev.t), "request": k,
                     "text": d.get("text", "")}
                if d.get("step") is not None:
                    c["step"] = d["step"]
                out.append(c)
        elif ev.type == EventType.SPEECH_ONSET:
            for cid in d.get("chain_ids", []):
                gt = dchain_to_gt.get(cid)
                if gt:  # scripted for this chain; on-topic only a human can confirm
                    out.append({"type": "speech_onset", "t": ts(ev.t), "on_topic": None, "source": "script",
                                "onset_source": d.get("onset_source"), "chain_id": gt, "request": k})
        elif ev.type == EventType.REFUSAL:
            gt = dchain_to_gt.get(d.get("chain_id", ""))
            if gt:
                out.append({"type": "refusal", "chain_id": gt, "t": ts(ev.t),
                            "kind": "degraded" if d.get("degraded") else "refused", "reason": d.get("reason", "")})
        elif ev.type == EventType.CAPACITY_SKIP:
            gt = gt_of(d.get("chain_id", ""), d.get("revision")) if d.get("chain_id") else uid_to_chain.get(d.get("uid", ""))
            if gt:
                sk = {"type": "capacity_skip", "chain_id": gt, "t": ts(ev.t)}
                rev = gt_revision(d["chain_id"], d.get("revision")) if d.get("chain_id") else None
                if rev is not None:
                    sk["revision"] = rev
                out.append(sk)
        elif ev.type == EventType.PLAYBACK_STOP:
            out.append({"type": "playback_stop", "t": ts(ev.t), "reason": "erasure" if d.get("erasure") else "barge_in"})
        elif ev.type == EventType.REPAIR:
            gt = gt_of(d.get("chain_id", ""), d.get("revision"))
            if gt:
                r = {"type": "repair_assignment", "chain_id": gt, "t": ts(ev.t),
                     "E": ts(d["t_evidence"]) if d.get("t_evidence") else None,
                     "arm_drawn": bool(d.get("arm_drawn")),
                     "arm": "forward_correction" if d.get("mode") == "gradient" else "repeat",
                     "failure_request": k, "target_request": d.get("earliest_correctable"),
                     "C": d.get("chain_cost_s")}
                if d.get("step") is not None:
                    r["step"] = d["step"]
                rev = gt_revision(d.get("chain_id", ""), d.get("revision"))
                if rev is not None:
                    r["revision"] = rev  # same numbering as the judge verdict's revision
                carried = [j for j, sc in sorted(orch.scripts.items())
                           if sc.provenance.get("retry_of") == k and d.get("chain_id") in sc.chain_ids]
                r["actual_request"] = carried[0] if carried else None  # the request that carried it
                out.append(r)
        elif ev.type == EventType.OBSERVATION_END:
            out.append({"type": "observation_end", "t": ts(ev.t)})
    return out


async def run_task(task: Task, condition: str, seed: int, *, factory, speed: float, out_dir: Path,
                   mode: str = "simulation") -> Path:
    cfg = CONDITIONS[condition]
    # Per-(task, seed) RNG stream, identical across conditions (paired design), different across tasks.
    stream = zlib.crc32(f"{task.task_id}/{seed}".encode())
    orch, client = factory(cfg, stream)
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
        # observe media until every deadline D of the task has passed (scorer checks observation_end)
        await asyncio.wait_for(orch._stop.wait(), timeout=observation_horizon_s(task) / speed)
    except asyncio.TimeoutError:
        pass
    finally:
        await orch.stop()
        client.close()
    if orch.error is not None:
        raise RuntimeError(f"{condition}/{task.task_id}: session failed: {orch.error}")
    header = dict(session_id=f"{condition}-{task.task_id}-s{seed}", condition=condition,
                  task_id=task.task_id, seed=seed, mode=mode, backbone=orch.gen.info.name,
                  chunks_per_request=orch.gen.info.chunks_per_request)
    gseed = getattr(orch.gen, "seed", None)  # the session's effective seed (SessionView sets the backend's)
    with SessionLogWriter(path, **header, **({"generator_seed": gseed} if gseed is not None else {})) as w:
        for ev in convert(orch, user_events, t0=t0, speed=speed):
            w.write(ev)
    return path


def schedule(tasks: list[Task], conditions: list[str], seeds: list[int]) -> list[tuple[Task, str, int]]:
    """Counterbalanced order: per (seed, task) the conditions run back to back, rotated so each
    condition appears in each position equally often (no condition-blocked warm-up/drift)."""
    out = []
    i = 0
    for seed in seeds:
        for t in tasks:
            rot = conditions[i % len(conditions):] + conditions[: i % len(conditions)]
            out += [(t, c, seed) for c in rot]
            i += 1
    return out


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
        # E2 gating needs human-validated E1 calibration; earlier runs are qualification only.
        manifest.min_status = Status.DOCUMENTED if allow_uncalibrated else Status.CALIBRATED
        ledger = StateLedger.from_config(config_dir / "canon.json")
        director = Director(llm, manifest, ledger, persona_name=canon["display_name"],
                            persona_bio=canon["persona_bio"], mode=cfg["mode"])
        gen = SessionView(backend, seed=seed)
        sched = LockScheduler(SchedulerConfig(request_s=backend.info.request_seconds))
        rec = Recorder(record_dir / f"session-{next(counter):03d}.mp4") if record_dir else None
        client = SimClient(speed=1.0, recorder=rec)
        orch = Orchestrator(gen, director, sched, client, judge=VLMJudge(vlm, k=8, contrast=True), corrector=ForwardCorrector(llm),
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
    await llm.warmup()
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
    mode = "simulation" if backend is None else "generator_path"
    try:
        for t, cond, seed in schedule(tasks, args.conditions, args.seeds):
            path = await run_task(t, cond, seed, factory=factory, speed=speed, out_dir=out, mode=mode)
            print(path, flush=True)
    finally:
        if backend is not None:
            await backend.close()


if __name__ == "__main__":
    main()
