"""E2 scoring: intent chains, per-task deadlines, outcome rules (proposal v2.11 §7.2, §8).

Rules implemented (all *proposed targets*, preregistered, identical across conditions):

* Intent chain: opened by a ``new`` annotation; ``revision`` merges into the same chain,
  replaces its intent fields and restarts the clock; ``withdrawal`` withdraws it (a later
  revision re-opens it). Scored once, on the final intent.
* Clock origin: ``t_end`` (VAD endpoint) of the opening or latest revising utterance.
* Effective chains (primary denominator): final intent not withdrawn; capacity-skipped
  chains are included and count as failures.
* Deadlines D: action 15 s -> first judged-compliant presented frame; content: on-topic
  speech onset <= 15 s AND complete response (rubric pass) <= 15 s + preregistered duration
  (qa 10, explain 30, sing 30); multistep: 15 s per step measured from the previous step's
  judged-compliance time, all steps in order; correction = restart clock at revision.
* Outcomes: refused/degraded -> fail; capacity skip -> fail (in denominator); withdrawn ->
  excluded, counted; "cannot tell" -> fail in primary, excluded in sensitivity analysis;
  never complied -> censored at D.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import Any

from live_agent.eval.schema import VERDICT_SOURCES, SessionLog
from live_agent.types import TaskKind

CONTENT_DURATION_S = {"qa": 10.0, "explain": 30.0, "sing": 30.0}  # proposed target (§7.2)


@dataclass(frozen=True)
class ScoringConfig:
    step_deadline_s: float = 15.0  # action / per multistep step / correction (proposed target)
    onset_deadline_s: float = 15.0  # content onset (proposed target)
    content_duration_s: dict[str, float] = field(default_factory=lambda: dict(CONTENT_DURATION_S))
    source_preference: tuple[str, ...] = VERDICT_SOURCES  # adjudicated > human > judge
    claim_grace_s: float = 0.0  # compliance evidence may trail a claim by at most this
    tfmr_horizon_s: float = 15.0  # TFMR censoring horizon


class Outcome(str, enum.Enum):
    SUCCESS = "success"
    LATE = "late"  # complied, but after the deadline
    NEVER = "never"  # no compliant verdict: censored at D
    UNKNOWN = "unknown"  # judge "cannot tell" decided the failure
    ONSET_FAIL = "onset_fail"  # content: no on-topic speech onset within 15 s
    RUBRIC_FAIL = "rubric_fail"  # content: response judged not meeting rubric
    ORDER_FAIL = "order_fail"  # multistep: steps complied out of order
    REFUSED = "refused"
    DEGRADED = "degraded"
    CAPACITY_SKIPPED = "capacity_skipped"
    WITHDRAWN = "withdrawn"


# --------------------------------------------------------------------------- chains


@dataclass
class Chain:
    chain_id: str
    label: str  # task-local label used to pair chains across conditions
    kind: TaskKind
    opened_uid: str
    origins: list[float]  # clock origins in order: opening, then each revision
    intent: str = ""
    content_type: str | None = None
    prereg_duration_s: float | None = None
    n_steps: int = 1
    revisions: list[str] = field(default_factory=list)
    withdrawn: bool = False
    withdrawn_t: float | None = None

    @property
    def clock_origin(self) -> float:
        return self.origins[-1]

    def origin_at(self, t: float) -> float:
        """Clock origin in force at time t (for judging claims made before a revision)."""
        cur = self.origins[0]
        for o in self.origins:
            if o <= t:
                cur = o
        return cur


def _kind(v: Any) -> TaskKind:
    k = TaskKind(v) if v is not None else TaskKind.ACTION
    return TaskKind.ACTION if k == TaskKind.CORRECTION else k


def _apply_intent(ch: Chain, ann: dict[str, Any]) -> None:
    if "kind" in ann:
        ch.kind = _kind(ann["kind"])
    if "intent" in ann:
        ch.intent = ann["intent"]
    if "content_type" in ann:
        ch.content_type = ann["content_type"]
    if "prereg_duration_s" in ann:
        ch.prereg_duration_s = ann["prereg_duration_s"]
    if "steps" in ann:
        ch.n_steps = len(ann["steps"]) if isinstance(ann["steps"], list) else int(ann["steps"])
    elif "kind" in ann and ch.kind != TaskKind.MULTISTEP:
        ch.n_steps = 1


def build_chains(session: SessionLog) -> dict[str, Chain]:
    utts = {e["uid"]: e for e in session.of_type("utterance")}
    anns = sorted(session.of_type("chain_annotation"), key=lambda a: utts[a["uid"]]["t_end"])
    chains: dict[str, Chain] = {}
    for a in anns:
        u = utts.get(a["uid"])
        if u is None:
            raise ValueError(f"annotation refers to unknown utterance {a['uid']}")
        cid = a["chain_id"]
        if a["action"] == "new":
            if cid in chains:
                raise ValueError(f"chain {cid} opened twice")
            ch = Chain(cid, a.get("label", cid), _kind(a.get("kind")), a["uid"], [float(u["t_end"])])
            _apply_intent(ch, a)
            chains[cid] = ch
            continue
        if cid not in chains:
            raise ValueError(f"{a['action']} of unknown chain {cid}")
        ch = chains[cid]
        if a["action"] == "revision":
            ch.revisions.append(a["uid"])
            ch.origins.append(float(u["t_end"]))
            ch.withdrawn, ch.withdrawn_t = False, None
            _apply_intent(ch, a)
        else:  # withdrawal
            ch.withdrawn, ch.withdrawn_t = True, float(u["t_end"])
    return chains


# --------------------------------------------------------------------------- outcomes


@dataclass
class ChainOutcome:
    session_id: str
    condition: str
    task_id: str
    seed: int
    chain_id: str
    label: str
    kind: str
    content_type: str | None
    outcome: Outcome
    clock_origin: float
    n_revisions: int
    deadline_s: float  # D for this chain
    time_to_success: float  # min(time, censor point); for KM
    success_event: bool
    tvc: float | None = None  # action chains: first judged-compliant frame - origin (censored at D)
    tvc_event: bool = False
    onset_s: float | None = None  # content: first on-topic speech onset - origin
    onset_ok: bool | None = None
    tfmr: float | None = None
    tfmr_event: bool = False
    steps_complied: int = 0
    n_claims: int = 0
    n_false_claims: int = 0
    repair_arm: str | None = None
    repair_success: bool | None = None
    repair_offset: int | None = None  # target_request - failure_request

    @property
    def success(self) -> bool:
        return self.outcome == Outcome.SUCCESS

    @property
    def effective(self) -> bool:
        return self.outcome != Outcome.WITHDRAWN

    @property
    def served(self) -> bool:
        """Attempted by the system (not refused, degraded, or capacity-skipped)."""
        return self.effective and self.outcome not in (
            Outcome.REFUSED,
            Outcome.DEGRADED,
            Outcome.CAPACITY_SKIPPED,
        )


@dataclass
class SessionScore:
    session_id: str
    condition: str
    task_id: str
    seed: int
    chains: list[ChainOutcome]
    visual_ack_s: list[float]
    barge_in_stop_s: list[float]
    barge_ins_without_stop: int


def _compliance_time(v: dict[str, Any], chunks: dict[tuple[int, int], dict[str, Any]]) -> float:
    """Presentation time of the first frame judged compliant."""
    if v.get("t_first_compliant") is not None:
        return float(v["t_first_compliant"])
    key = (v.get("request"), v.get("chunk"))
    if key in chunks:
        return float(chunks[key]["t_start"])
    if v.get("t_evidence") is None:
        raise ValueError(f"verdict without any time: {v}")
    return float(v["t_evidence"])


def _pick_source(vs: list[dict[str, Any]], pref: tuple[str, ...]) -> list[dict[str, Any]]:
    for s in pref:
        sel = [v for v in vs if v["source"] == s]
        if sel:
            return sel
    return []


def _score_chain(
    ch: Chain,
    verdicts: list[dict[str, Any]],
    chunks: dict[tuple[int, int], dict[str, Any]],
    onsets: list[dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[Outcome, dict[str, Any]]:
    """Deadline rules for a non-withdrawn, non-skipped, non-refused chain."""
    o = ch.clock_origin
    n_rev = len(ch.revisions)
    vs = [
        v
        for v in verdicts
        if v.get("revision") is None or int(v["revision"]) == n_rev
    ]
    vs = [dict(v, _tc=_compliance_time(v, chunks)) for v in vs]
    vs = [v for v in vs if v["_tc"] >= o]
    info: dict[str, Any] = {}
    D = cfg.step_deadline_s

    if ch.kind == TaskKind.CONTENT:
        dur = ch.prereg_duration_s
        if dur is None:
            dur = cfg.content_duration_s[ch.content_type or "qa"]
        D_c = cfg.onset_deadline_s + dur
        info["deadline"] = D_c
        on = [e["t"] - o for e in onsets if e["on_topic"] and e["t"] >= o]
        onset = min(on) if on else None
        info["onset_s"] = onset
        info["onset_ok"] = onset is not None and onset <= cfg.onset_deadline_s
        # rubric verdicts: t_evidence = presentation time of the end of the response
        rub = sorted(vs, key=lambda v: float(v.get("t_evidence", v["_tc"])))
        done = [float(v.get("t_evidence", v["_tc"])) - o for v in rub if v["label"] == "complied"]
        comp = min(done) if done else None
        info["t_complete"] = comp
        in_time = [v for v in rub if float(v.get("t_evidence", v["_tc"])) - o <= D_c]
        if not info["onset_ok"]:
            return Outcome.ONSET_FAIL, info
        if comp is not None and comp <= D_c:
            return Outcome.SUCCESS, info
        if comp is not None:
            return Outcome.LATE, info
        if any(v["label"] == "unknown" for v in in_time):
            return Outcome.UNKNOWN, info
        if any(v["label"] == "not_complied" for v in in_time):
            return Outcome.RUBRIC_FAIL, info
        return Outcome.NEVER, info

    # action (incl. corrections) and multistep: per-step 15 s from previous compliance
    n = ch.n_steps if ch.kind == TaskKind.MULTISTEP else 1
    prev = o
    done_steps = 0
    for i in range(n):
        step_vs = [v for v in vs if int(v.get("step", 0)) == i]
        ok = sorted(v["_tc"] for v in step_vs if v["label"] == "complied" and v["_tc"] >= prev)
        info["deadline"] = prev - o + D  # censor point if we stop here
        if not ok:
            window = [v for v in step_vs if prev <= v["_tc"] <= prev + D]
            if any(v["label"] == "unknown" for v in window):
                out = Outcome.UNKNOWN
            elif any(v["label"] == "complied" and v["_tc"] < prev for v in step_vs):
                out = Outcome.ORDER_FAIL
            else:
                out = Outcome.NEVER
            info["steps_complied"] = done_steps
            return out, info
        t_ok = ok[0]
        if i == 0 and n == 1:
            info["tvc"] = t_ok - o
        if t_ok - prev > D:
            info["steps_complied"] = done_steps
            info["t_late"] = t_ok - o
            return Outcome.LATE, info
        prev = t_ok
        done_steps += 1
    info["steps_complied"] = done_steps
    info["t_complete"] = prev - o
    info["deadline"] = D * n
    return Outcome.SUCCESS, info


def _claims(
    ch: Chain,
    claims: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    claim_verdicts: dict[str, list[dict[str, Any]]],
    chunks: dict[tuple[int, int], dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[int, int]:
    """Return (n_claims, n_contradicted). A claim is contradicted unless a complied verdict
    for that chain (and step, if the claim names one) has its compliant frame in
    [origin in force at claim time, t_claim + grace]. A verdict that carries the claim's
    ``claim_id`` adjudicates the claim directly and takes precedence ("unknown" = false)."""
    n_false = 0
    for c in claims:
        cid = c.get("claim_id")
        if cid is not None and cid in claim_verdicts:
            direct = _pick_source(claim_verdicts[cid], cfg.source_preference)
            if direct:
                n_false += int(direct[-1]["label"] != "complied")
                continue
        lo = ch.origin_at(float(c["t"]))
        hi = float(c["t"]) + cfg.claim_grace_s
        ok = False
        for v in verdicts:
            if v["label"] != "complied":
                continue
            if "step" in c and int(v.get("step", 0)) != int(c["step"]):
                continue
            if lo <= _compliance_time(v, chunks) <= hi:
                ok = True
                break
        n_false += int(not ok)
    return len(claims), n_false


def score_session(session: SessionLog, cfg: ScoringConfig | None = None) -> SessionScore:
    cfg = cfg or ScoringConfig()
    chains = build_chains(session)
    chunks = {(int(e["request"]), int(e["chunk"])): e for e in session.of_type("chunk_presented")}

    by_chain: dict[str, dict[str, list[dict[str, Any]]]] = {c: {} for c in chains}

    def put(cid: str | None, key: str, ev: dict[str, Any]) -> None:
        if cid in by_chain:
            by_chain[cid].setdefault(key, []).append(ev)

    claim_verdicts: dict[str, list[dict[str, Any]]] = {}
    for e in session.events:
        t = e["type"]
        if t == "verdict":
            if "claim_id" in e:
                claim_verdicts.setdefault(e["claim_id"], []).append(e)
            else:
                put(e["chain_id"], "verdict", e)
        elif t in ("completion_claim", "refusal", "capacity_skip", "repair_assignment") or (
            t == "speech_onset" and e.get("chain_id") is not None
        ):
            put(e["chain_id"], t, e)

    out: list[ChainOutcome] = []
    for cid, ch in chains.items():
        ev = by_chain[cid]
        o = ch.clock_origin
        verdicts = _pick_source(ev.get("verdict", []), cfg.source_preference)
        onsets = ev.get("speech_onset", [])
        skips = [e for e in ev.get("capacity_skip", []) if e["t"] >= o]
        refusals = [e for e in ev.get("refusal", []) if e["t"] >= o]

        info: dict[str, Any] = {}
        if ch.withdrawn:
            outcome = Outcome.WITHDRAWN
        elif skips:
            outcome = Outcome.CAPACITY_SKIPPED
        elif refusals:
            kinds = {e.get("kind", "refused") for e in refusals}
            outcome = Outcome.REFUSED if "refused" in kinds else Outcome.DEGRADED
        else:
            outcome, info = _score_chain(ch, verdicts, chunks, onsets, cfg)

        if ch.kind == TaskKind.CONTENT:
            dur = ch.prereg_duration_s or cfg.content_duration_s[ch.content_type or "qa"]
            D = cfg.onset_deadline_s + dur
        elif ch.kind == TaskKind.MULTISTEP:
            D = cfg.step_deadline_s * ch.n_steps
        else:
            D = cfg.step_deadline_s
        success = outcome == Outcome.SUCCESS
        if success:
            tts = float(info.get("t_complete", info.get("tvc", 0.0)))
        else:
            tts = float(info.get("deadline", D))  # censored where failure became certain

        rec = ChainOutcome(
            session_id=session.session_id,
            condition=session.condition,
            task_id=session.task_id,
            seed=session.seed,
            chain_id=cid,
            label=ch.label,
            kind=ch.kind.value,
            content_type=ch.content_type,
            outcome=outcome,
            clock_origin=o,
            n_revisions=len(ch.revisions),
            deadline_s=D,
            time_to_success=tts,
            success_event=success,
            steps_complied=int(info.get("steps_complied", 0)),
        )
        if ch.kind == TaskKind.ACTION and outcome != Outcome.WITHDRAWN:
            if info.get("tvc") is not None and info["tvc"] <= D:
                rec.tvc, rec.tvc_event = info["tvc"], True
            else:
                rec.tvc, rec.tvc_event = D, False  # censored at D
        if ch.kind == TaskKind.CONTENT and outcome != Outcome.WITHDRAWN:
            rec.onset_s = info.get("onset_s")
            rec.onset_ok = bool(info.get("onset_ok", False))
        if outcome != Outcome.WITHDRAWN:
            on = [e["t"] - o for e in onsets if e["on_topic"] and e["t"] >= o]
            first = min(on) if on else None
            if first is not None and first <= cfg.tfmr_horizon_s:
                rec.tfmr, rec.tfmr_event = first, True
            else:
                rec.tfmr, rec.tfmr_event = cfg.tfmr_horizon_s, False
            rec.n_claims, rec.n_false_claims = _claims(
                ch, ev.get("completion_claim", []), verdicts, claim_verdicts, chunks, cfg
            )
        rep = ev.get("repair_assignment", [])
        if rep:
            r = rep[-1]
            tgt = int(r["target_request"])
            step = r.get("step")
            rec.repair_arm = r["arm"]
            rec.repair_offset = tgt - int(r["failure_request"])
            rec.repair_success = any(
                v["label"] == "complied"
                and v.get("request") is not None
                and int(v["request"]) == tgt
                and (step is None or int(v.get("step", 0)) == int(step))
                for v in verdicts
            )
        out.append(rec)

    # latencies
    utts = {e["uid"]: e for e in session.of_type("utterance")}
    acks = []
    for e in session.of_type("visual_ack"):
        u = utts.get(e["uid"])
        if u is None:
            continue
        ref = u["t_start"] if u.get("barge_in") else u["t_end"]
        acks.append(float(e["t"]) - float(ref))
    stops = sorted(float(e["t"]) for e in session.of_type("playback_stop"))
    barge, missing = [], 0
    for u in utts.values():
        if not u.get("barge_in"):
            continue
        after = [s for s in stops if s >= float(u["t_start"])]
        if after:
            barge.append(after[0] - float(u["t_start"]))
        else:
            missing += 1

    return SessionScore(
        session_id=session.session_id,
        condition=session.condition,
        task_id=session.task_id,
        seed=session.seed,
        chains=out,
        visual_ack_s=acks,
        barge_in_stop_s=barge,
        barge_ins_without_stop=missing,
    )


# --------------------------------------------------------------------------- aggregation


def _rate(k: int, n: int) -> float:
    return k / n if n else math.nan


def summarize(chains: list[ChainOutcome]) -> dict[str, Any]:
    """Point estimates for one condition (CIs are added in report.py)."""
    eff = [c for c in chains if c.effective]
    n = len(eff)
    succ = sum(c.success for c in eff)
    skipped = sum(c.outcome == Outcome.CAPACITY_SKIPPED for c in eff)
    refused = sum(c.outcome in (Outcome.REFUSED, Outcome.DEGRADED) for c in eff)
    unknown = sum(c.outcome == Outcome.UNKNOWN for c in eff)
    served = [c for c in eff if c.served]
    content = [c for c in eff if c.kind == TaskKind.CONTENT.value]
    claims = sum(c.n_claims for c in eff)
    false_claims = sum(c.n_false_claims for c in eff)
    rep = [c for c in eff if c.repair_arm is not None]
    return {
        "n_effective": n,
        "n_success": succ,
        "success_rate": _rate(succ, n),
        "n_withdrawn": sum(not c.effective for c in chains),
        "capacity_skip_rate": _rate(skipped, n),
        "n_capacity_skipped": skipped,
        "refusal_degradation_rate": _rate(refused, n),
        "n_refused_degraded": refused,
        "n_unknown": unknown,
        "success_rate_excl_unknown": _rate(succ, n - unknown),  # sensitivity analysis
        "conditional_success_rate": _rate(sum(c.success for c in served), len(served)),
        "n_served": len(served),
        "content_onset_rate": _rate(sum(bool(c.onset_ok) for c in content), len(content)),
        "n_content": len(content),
        "n_claims": claims,
        "n_false_claims": false_claims,
        "fcr": _rate(false_claims, claims),
        "claim_coverage": _rate(sum(c.n_claims > 0 for c in eff), n),
        "claim_coverage_of_successes": _rate(
            sum(c.n_claims > 0 for c in eff if c.success), succ
        ),
        "repair": {
            arm: {
                "n": sum(c.repair_arm == arm for c in rep),
                "k": sum(bool(c.repair_success) for c in rep if c.repair_arm == arm),
                "offsets": sorted(c.repair_offset for c in rep if c.repair_arm == arm),
            }
            for arm in sorted({c.repair_arm for c in rep})
        },
        "outcomes": {o.value: sum(c.outcome == o for c in chains) for o in Outcome},
    }
