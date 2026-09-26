"""E2 scoring: intent chains, per-task deadlines, outcome rules (proposal v2.11 §7.2, §8).

Rules implemented (all *proposed targets*, preregistered, identical across conditions):

* Intent chain: opened by a ``new`` annotation; ``revision`` merges into the same chain,
  replaces its intent fields and restarts the clock; ``withdrawal`` withdraws it (a later
  revision re-opens it). Scored once, on the final intent.
* Clock origin: ``t_end`` (VAD endpoint) of the opening or latest revising utterance.
* Primary outcome = blinded, reconciled human adjudication (D-014). Default scoring uses
  ``adjudicated`` verdicts only; a chain the system attempted but that has no complete
  adjudication is ``unadjudicated`` and the primary report refuses to run. Online-judge
  scoring is a labelled diagnostic (``ScoringConfig.diagnostic_config()``).
* Verdicts are bound to the intent revision they judged (``revision``); a mismatch is
  ignored. Judge verdicts without ``revision`` are used only in diagnostic mode.
* Effective chains (proposal denominator): final intent not withdrawn; capacity-skipped
  chains are included and count as failures. Chains whose deadline window was not fully
  observed (``observation_end``) and that did not succeed inside it are
  ``insufficient_observation``: excluded from the primary analysis, counted, flagged for rerun.
* Deadlines D: action 15 s -> first judged-compliant presented frame; content: on-topic
  speech onset <= 15 s (adjudicated onset only in primary mode) AND complete response
  (rubric pass) <= 15 s + preregistered duration (qa 10, explain 30, sing 30); multistep:
  15 s per step measured from the previous step's judged-compliance time, all steps in
  order; correction = restart clock at revision.
* Outcomes: refused/degraded -> fail; capacity skip (of the final revision) -> fail (in
  denominator); withdrawn -> excluded, counted; "cannot tell" -> fail in primary, excluded
  in sensitivity analysis; never complied -> not a success by D; order_fail -> a
  deterministic failure. Time to success: every non-success is "not yet" until the chain's
  full deadline D (no early censoring), so success-by-t per kind is a cumulative incidence
  with all failure types as competing outcomes.
* FCR (primary): completion claims found in the recorded audio by the adjudicated claim
  sweep, each settled by its reconciled claim-level verdict. Logged claims are diagnostic.
* RQ2: every randomised failure point, by assigned arm; withdrawal after assignment is a
  repair failure (sensitivity row excludes it); unobserved target requests are flagged.
"""

from __future__ import annotations

import dataclasses
import enum
import math
from dataclasses import dataclass, field
from typing import Any

from live_agent.eval.schema import SessionLog
from live_agent.types import TaskKind

CONTENT_DURATION_S = {"qa": 10.0, "explain": 30.0, "sing": 30.0}  # proposed target (§7.2)
PRIMARY_SOURCES: tuple[str, ...] = ("adjudicated",)
_EPS = 1e-6


@dataclass(frozen=True)
class ScoringConfig:
    step_deadline_s: float = 15.0  # action / per multistep step / correction (proposed target)
    onset_deadline_s: float = 15.0  # content onset (proposed target)
    content_duration_s: dict[str, float] = field(default_factory=lambda: dict(CONTENT_DURATION_S))
    # Primary: adjudicated verdicts only. Anything else must be declared diagnostic.
    source_preference: tuple[str, ...] = PRIMARY_SOURCES
    # speech_onset sources accepted for the content onset gate / TFMR. "script" onsets
    # (on_topic null: the line was scripted, nobody verified it) only in diagnostic mode.
    onset_sources: tuple[str, ...] = PRIMARY_SOURCES
    diagnostic: bool = False
    claim_grace_s: float = 0.0  # compliance evidence may trail a claim by at most this
    tfmr_horizon_s: float = 15.0  # TFMR censoring horizon

    def __post_init__(self) -> None:
        if not self.diagnostic and (
            tuple(self.source_preference) != PRIMARY_SOURCES
            or tuple(self.onset_sources) != PRIMARY_SOURCES
        ):
            raise ValueError(
                "the primary outcome uses adjudicated verdicts and onsets only (D-014); "
                "other sources require diagnostic=True (see ScoringConfig.diagnostic_config())"
            )

    @classmethod
    def diagnostic_config(cls, sources: tuple[str, ...] = ("judge",), **kw: Any) -> ScoringConfig:
        """Diagnostic scoring (e.g. of the online judge): not a result. Scripted speech
        onsets are accepted as unverified."""
        return cls(source_preference=tuple(sources),
                   onset_sources=("adjudicated", "human", "script"), diagnostic=True, **kw)


class Outcome(str, enum.Enum):
    SUCCESS = "success"
    LATE = "late"  # complied, but after the deadline
    NEVER = "never"  # no compliant verdict: censored at D
    UNKNOWN = "unknown"  # "cannot tell" decided the failure
    ONSET_FAIL = "onset_fail"  # content: no on-topic speech onset within 15 s
    RUBRIC_FAIL = "rubric_fail"  # content: response judged not meeting rubric
    ORDER_FAIL = "order_fail"  # multistep: steps complied out of order (competing failure)
    REFUSED = "refused"
    DEGRADED = "degraded"
    CAPACITY_SKIPPED = "capacity_skipped"
    WITHDRAWN = "withdrawn"
    UNADJUDICATED = "unadjudicated"  # primary mode: adjudication missing (report rejects)
    INSUFFICIENT_OBSERVATION = "insufficient_observation"  # window not observed: rerun


NOT_PRIMARY = (Outcome.WITHDRAWN, Outcome.UNADJUDICATED, Outcome.INSUFFICIENT_OBSERVATION)


class IncompleteAdjudicationError(ValueError):
    """The primary analysis needs a reconciled adjudicated verdict for every chain and claim."""


class InsufficientObservationError(ValueError):
    """Some deadline windows were not observed: rerun those trials, or select a
    preregistered missing-data rule explicitly (report ``--missing-rule``)."""


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

    def revision_at(self, t: float) -> int:
        """Index of the intent revision in force at time t (0 = the opening intent)."""
        r = 0
        for i, o in enumerate(self.origins):
            if o <= t:
                r = i
        return r

    def origin_at(self, t: float) -> float:
        """Clock origin in force at time t (for judging claims made before a revision)."""
        return self.origins[self.revision_at(t)]


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
    time_to_success: float  # min(time, censor point); for KM (not meaningful for order_fail)
    success_event: bool
    competing_failure: bool = False  # order_fail: deterministic failure, not right-censoring
    tvc: float | None = None  # action chains: first judged-compliant frame - origin (censored at D)
    tvc_event: bool = False
    onset_s: float | None = None  # content: first on-topic speech onset - origin
    onset_ok: bool | None = None
    tfmr: float | None = None
    tfmr_event: bool = False
    steps_complied: int = 0
    n_claims: int = 0  # audible completion claims (all, incl. withdrawn chains)
    n_false_claims: int = 0
    n_claims_unadjudicated: int = 0  # primary mode: claims without a usable adjudication
    repairs: list[dict[str, Any]] = field(default_factory=list)  # one per RQ2 failure point
    missing: str = ""  # what adjudication is missing / why observation is insufficient

    @property
    def success(self) -> bool:
        return self.outcome == Outcome.SUCCESS

    @property
    def effective(self) -> bool:
        """Proposal definition: final intent not withdrawn."""
        return self.outcome != Outcome.WITHDRAWN

    @property
    def in_primary(self) -> bool:
        """Counted in the primary denominator (effective, adjudicated, observed)."""
        return self.outcome not in NOT_PRIMARY

    @property
    def served(self) -> bool:
        """Attempted by the system (not refused, degraded, or capacity-skipped)."""
        return self.in_primary and self.outcome not in (
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
    diagnostic: bool = False
    sources: tuple[str, ...] = PRIMARY_SOURCES
    observation_end: float | None = None
    claim_sweep: bool = False  # an adjudicated audio claim sweep covers this session
    rq2_problems: list[str] = field(default_factory=list)  # RQ2 audit (RQ2_CONDITIONS only)


def _vtime(v: dict[str, Any], chunks: dict[tuple[int, int], dict[str, Any]]) -> float | None:
    """Presentation time of the first frame judged compliant (for a negative label: the
    evidence time if any, else None = the label covers its whole reviewed interval)."""
    if v.get("t_first_compliant") is not None:
        return float(v["t_first_compliant"])
    key = (v.get("request"), v.get("chunk"))
    if key in chunks:
        return float(chunks[key]["t_start"])
    if v.get("t_evidence") is not None:
        return float(v["t_evidence"])
    if v["label"] == "complied":
        raise ValueError(f"'complied' verdict without a compliance time: {v}")
    return None


def _t_end(v: dict[str, Any]) -> float | None:
    """Content completion time (end of the response) of a verdict."""
    if v.get("t_evidence") is not None:
        return float(v["t_evidence"])
    return v["_tc"]


def _pick_source(vs: list[dict[str, Any]], pref: tuple[str, ...]) -> list[dict[str, Any]]:
    for s in pref:
        sel = [v for v in vs if v["source"] == s]
        if sel:
            return sel
    return []


def _bound(v: dict[str, Any], rev: int, cfg: ScoringConfig) -> bool:
    """Is verdict v about intent revision ``rev``? Adjudicated/human verdicts without a
    ``revision`` are made on the final intent (the caller passes the final revision)."""
    if v.get("revision") is not None:
        return int(v["revision"]) == rev
    return v["source"] != "judge" or cfg.diagnostic  # unbound judge verdicts: diagnostic only


def _onset_accepted(e: dict[str, Any], cfg: ScoringConfig) -> bool:
    src = e.get("source", "script")  # legacy onsets without source were scripted, unverified
    if src not in cfg.onset_sources:
        return False
    if e.get("on_topic") is True:
        return True
    return cfg.diagnostic and src == "script" and e.get("on_topic") is None


def _content_deadline(ch: Chain, cfg: ScoringConfig) -> float:
    dur = ch.prereg_duration_s
    if dur is None:
        dur = cfg.content_duration_s[ch.content_type or "qa"]
    return cfg.onset_deadline_s + dur


def _adjudication_gap(ch: Chain, vs: list[dict[str, Any]], adj_onsets: list[dict[str, Any]]) -> str:
    """'' when the final intent is fully adjudicated, else what is missing."""
    if not vs:
        return "no adjudicated verdict for the final intent"
    if not (any(v.get("onset_reviewed") for v in vs) or adj_onsets):
        # every chain: the meaningful (on-topic) response onset, or "none by the deadline"
        return f"{ch.kind.value}: response onset not adjudicated"
    if ch.kind == TaskKind.CONTENT:
        return ""
    if ch.kind == TaskKind.MULTISTEP:
        for i in range(ch.n_steps):
            sv = [v for v in vs if int(v.get("step", 0)) == i]
            if not sv:
                return f"multistep: step {i} not adjudicated"
            if not any(v["label"] == "complied" for v in sv):
                return ""  # later steps are moot
    return ""


def _score_chain(
    ch: Chain,
    vs: list[dict[str, Any]],
    onsets: list[dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[Outcome, dict[str, Any]]:
    """Deadline rules for a non-withdrawn, non-skipped, non-refused chain. ``vs`` are the
    verdicts bound to the final revision, each with ``_tc`` (None for untimed negatives).
    ``info['needs_until']`` = the session time through which absence of compliance had to
    be observed for a failure outcome to be certain."""
    o = ch.clock_origin
    vs = [v for v in vs if v["_tc"] is None or v["_tc"] >= o - _EPS]
    info: dict[str, Any] = {}
    D = cfg.step_deadline_s

    if ch.kind == TaskKind.CONTENT:
        D_c = _content_deadline(ch, cfg)
        info["deadline"] = D_c
        on = [float(e["t"]) - o for e in onsets if float(e["t"]) >= o]
        onset = min(on) if on else None
        info["onset_s"] = onset
        info["onset_ok"] = onset is not None and onset <= cfg.onset_deadline_s
        # rubric verdicts: t_evidence = presentation time of the end of the response
        done = sorted(_t_end(v) - o for v in vs if v["label"] == "complied")
        comp = done[0] if done else None
        info["t_complete"] = comp
        in_time = [v for v in vs if v["_tc"] is None or _t_end(v) - o <= D_c]
        if not info["onset_ok"]:
            if onset is None:
                info["needs_until"] = o + cfg.onset_deadline_s
            return Outcome.ONSET_FAIL, info
        if comp is not None and comp <= D_c:
            return Outcome.SUCCESS, info
        if comp is not None:
            return Outcome.LATE, info
        info["needs_until"] = o + D_c
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
        ok = sorted(v["_tc"] for v in step_vs if v["label"] == "complied" and v["_tc"] >= prev - _EPS)
        info["deadline"] = prev - o + D  # censor point if we stop here
        if not ok:
            window = [v for v in step_vs if v["_tc"] is None or prev <= v["_tc"] <= prev + D]
            # a step seen only before its predecessor is nonqualifying evidence: the failure
            # (order_fail) is certain only once its own window [prev, prev + D] was observed
            info["needs_until"] = prev + D
            if any(v["label"] == "complied" and v["_tc"] < prev for v in step_vs):
                out = Outcome.ORDER_FAIL
            else:
                out = Outcome.UNKNOWN if any(v["label"] == "unknown" for v in window) else Outcome.NEVER
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


def _claim_key(chain_id: str, t: float) -> tuple[str, float]:
    return (chain_id, round(float(t), 3))


def _claims(
    ch: Chain,
    claims: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    direct: dict[Any, list[dict[str, Any]]],
    chunks: dict[tuple[int, int], dict[str, Any]],
    cfg: ScoringConfig,
) -> tuple[int, int, int]:
    """Return (n_claims, n_false, n_unadjudicated) over the chain's completion claims,
    withdrawn chains included. A claim-level verdict (``claim_id``, or ``chain_id`` +
    ``claim_t``) settles a claim directly; ``unknown`` counts as false.

    Primary mode: the claims are the ones found by the adjudicated audio claim sweep
    (``completion_claim`` with ``source: adjudicated``), each settled by its reconciled
    claim-level verdict; a claim without one is unadjudicated.

    Diagnostic mode (logged claims): a claim is judged against the intent revision in force
    when it was heard. It is true only if a ``complied`` verdict bound to that revision (for
    the claimed step, or for every step when no step is named) has its compliance time in
    [origin of that revision, t_claim + grace]."""
    n_false = n_unadj = 0
    n_rev = len(ch.revisions)
    for c in claims:
        t = float(c["t"])
        dv = direct.get(("id", c.get("claim_id"))) if c.get("claim_id") is not None else None
        dv = dv or direct.get(_claim_key(ch.chain_id, t))
        dv = _pick_source(dv or [], cfg.source_preference)
        if dv:
            n_false += int(dv[-1]["label"] != "complied")
            continue
        if not cfg.diagnostic:
            n_unadj += 1
            continue
        r = ch.revision_at(t)
        lo, hi = ch.origins[r], t + cfg.claim_grace_s
        steps = [int(c["step"])] if c.get("step") is not None else list(range(ch.n_steps))
        ok = True
        for s in steps:
            hit = False
            for v in verdicts:
                if v["label"] != "complied" or int(v.get("step", 0)) != s:
                    continue
                vr = v.get("revision")
                if vr is None and v["source"] != "judge":
                    vr = n_rev  # adjudicated on the final intent
                if vr is not None and int(vr) != r:
                    continue
                tc = _vtime(v, chunks)
                if tc is not None and lo - _EPS <= tc <= hi + _EPS:
                    hit = True
                    break
            ok = ok and hit
        n_false += int(not ok)
    return len(claims), n_false, n_unadj


def _request_at(t: float, chunks: dict[tuple[int, int], dict[str, Any]]) -> int | None:
    for (k, _), c in chunks.items():
        if float(c["t_start"]) - _EPS <= t < float(c["t_end"]):
            return k
    return None


def _repair(r: dict[str, Any], ch: Chain, outcome: Outcome, vs: list[dict[str, Any]],
            chunks: dict[tuple[int, int], dict[str, Any]], obs_end: float | None) -> dict[str, Any]:
    """One RQ2 failure point (preregistered handling):

    * ``withdrawn`` (checked first): the user withdrew the chain at or after the
      assignment time (``t``, else ``E``): a repair failure in the primary analysis,
      excluded in a sensitivity row, whatever the target request later showed;
    * ``ineligible``: the chain had already been withdrawn when the arm was assigned
      (excluded, flagged);
    * ``success``: a complied verdict (for the assigned step) whose request -- explicit
      ``request``, else the presented chunk containing its compliance time -- is the
      target request j;
    * ``insufficient_observation``: request j was not fully presented before
      ``observation_end``: flagged, excluded, rerun;
    * ``unadjudicated``: the chain lacks adjudication (the primary report refuses);
    * ``failure``: otherwise."""
    tgt = int(r["target_request"]) if r.get("target_request") is not None else None
    step = r.get("step")

    def req(v: dict[str, Any]) -> int | None:
        if v.get("request") is not None:
            return int(v["request"])
        return _request_at(v["_tc"], chunks) if v["_tc"] is not None else None

    ok = tgt is not None and any(
        v["label"] == "complied" and req(v) == tgt and (step is None or int(v.get("step", 0)) == int(step))
        for v in vs
    )
    ends = [float(c["t_end"]) for (k, _), c in chunks.items() if k == tgt]
    ta = r.get("t", r.get("E"))
    if ch.withdrawn and ta is not None and ch.withdrawn_t is not None and ch.withdrawn_t < float(ta) - _EPS:
        status = "ineligible"
    elif ch.withdrawn:
        status = "withdrawn"
    elif ok:
        status = "success"
    elif tgt is not None and obs_end is not None and (not ends or max(ends) > obs_end + _EPS):
        status = "insufficient_observation"
    elif outcome == Outcome.UNADJUDICATED:
        status = "unadjudicated"
    else:
        status = "failure"
    return {
        "arm": r["arm"],
        "failure_request": int(r["failure_request"]),
        "target_request": tgt,
        "step": step,
        "offset": (tgt - int(r["failure_request"])) if tgt is not None else None,
        "status": status,
        "success": status == "success",
        "arm_drawn": bool(r.get("arm_drawn")),
    }


RQ2_CONDITIONS = ("A2-rq2",)  # conditions whose repair arm is randomised per failure point


def rq2_problems(session: SessionLog, chains: dict[str, Chain],
                 chunks: dict[tuple[int, int], dict[str, Any]], obs_end: float | None) -> list[str]:
    """Audit an RQ2 session (preregistered definition). An **eligible failure point** is an
    online ``judge`` verdict ``not_complied`` on a chain open at its evidence time (opened,
    not withdrawn, verdict revision = the revision then in force), whose
    ``earliest_correctable`` request j exists and started presenting before
    ``observation_end``. Every eligible point needs a ``repair_assignment`` with the same
    chain and ``failure_request``, and every assignment needs ``arm_drawn: true``."""
    probs = []
    assigned = {(r["chain_id"], int(r["failure_request"])) for r in session.of_type("repair_assignment")}
    for r in session.of_type("repair_assignment"):
        if r.get("arm_drawn") is not True:
            probs.append(f"assignment {r['chain_id']} k={r['failure_request']}: arm not randomised (arm_drawn)")
    starts: dict[int, float] = {}
    for (k, _), c in chunks.items():
        starts[k] = min(starts.get(k, math.inf), float(c["t_start"]))
    for v in session.of_type("verdict"):
        if v["source"] != "judge" or v["label"] != "not_complied" or v.get("request") is None:
            continue
        ch = chains.get(v.get("chain_id"))
        t = _vtime(v, chunks)
        if ch is None or t is None or t < ch.origins[0]:
            continue
        if ch.withdrawn and ch.withdrawn_t is not None and ch.withdrawn_t <= t:
            continue
        if v.get("revision") is not None and int(v["revision"]) != ch.revision_at(t):
            continue
        j = v.get("earliest_correctable")
        if j is None or int(j) not in starts or (obs_end is not None and starts[int(j)] >= obs_end):
            continue
        if (ch.chain_id, int(v["request"])) not in assigned:
            probs.append(f"eligible failure {ch.chain_id} k={v['request']} (j={j}) has no repair_assignment")
    return probs


def observation_end(session: SessionLog) -> float | None:
    """Last presented media time: the ``observation_end`` event, else the end of the last
    presented chunk, else None (hand-built logs without media: no check)."""
    ends = [float(e["t"]) for e in session.of_type("observation_end")]
    if ends:
        return max(ends)
    ch = [float(e["t_end"]) for e in session.of_type("chunk_presented")]
    return max(ch) if ch else None


def score_session(session: SessionLog, cfg: ScoringConfig | None = None) -> SessionScore:
    cfg = cfg or ScoringConfig()
    chains = build_chains(session)
    chunks = {(int(e["request"]), int(e["chunk"])): e for e in session.of_type("chunk_presented")}
    obs_end = observation_end(session)

    by_chain: dict[str, dict[str, list[dict[str, Any]]]] = {c: {} for c in chains}

    def put(cid: str | None, key: str, ev: dict[str, Any]) -> None:
        if cid in by_chain:
            by_chain[cid].setdefault(key, []).append(ev)

    direct: dict[Any, list[dict[str, Any]]] = {}
    for e in session.events:
        t = e["type"]
        if t == "verdict":
            if e.get("claim_id") is not None:
                direct.setdefault(("id", e["claim_id"]), []).append(e)
            elif e.get("claim_t") is not None:
                direct.setdefault(_claim_key(e["chain_id"], e["claim_t"]), []).append(e)
            else:
                put(e["chain_id"], "verdict", e)
        elif t == "completion_claim":
            # primary: claims found in the recorded audio by the adjudicated sweep; diagnostic:
            # the orchestrator's logged claims
            if (e.get("source") == "adjudicated") != cfg.diagnostic:
                put(e["chain_id"], t, e)
        elif t in ("refusal", "capacity_skip", "repair_assignment") or (
            t == "speech_onset" and e.get("chain_id") is not None
        ):
            put(e["chain_id"], t, e)

    out: list[ChainOutcome] = []
    for cid, ch in chains.items():
        ev = by_chain[cid]
        o = ch.clock_origin
        n_rev = len(ch.revisions)
        all_v = _pick_source(ev.get("verdict", []), cfg.source_preference)
        vs = [dict(v, _tc=_vtime(v, chunks)) for v in all_v if _bound(v, n_rev, cfg)]
        onsets = [e for e in ev.get("speech_onset", []) if _onset_accepted(e, cfg)]
        adj_onsets = [e for e in onsets if e.get("source") == "adjudicated" and float(e["t"]) >= o]
        skips = [
            e for e in ev.get("capacity_skip", [])
            if (int(e["revision"]) == n_rev if e.get("revision") is not None else e["t"] >= o)
        ]
        refusals = [e for e in ev.get("refusal", []) if e["t"] >= o]

        info: dict[str, Any] = {}
        missing = ""
        if ch.withdrawn:
            outcome = Outcome.WITHDRAWN
        elif skips:
            outcome = Outcome.CAPACITY_SKIPPED
        elif refusals:
            kinds = {e.get("kind", "refused") for e in refusals}
            outcome = Outcome.REFUSED if "refused" in kinds else Outcome.DEGRADED
        else:
            gap = "" if cfg.diagnostic else _adjudication_gap(ch, vs, adj_onsets)
            if gap:
                outcome, missing = Outcome.UNADJUDICATED, gap
            else:
                outcome, info = _score_chain(ch, vs, onsets, cfg)
                need = info.get("needs_until")
                if need is not None and obs_end is not None and need > obs_end + _EPS:
                    missing = f"observed to {obs_end:.2f} s, window needs {need:.2f} s ({outcome.value})"
                    outcome = Outcome.INSUFFICIENT_OBSERVATION

        if ch.kind == TaskKind.CONTENT:
            D = _content_deadline(ch, cfg)
        elif ch.kind == TaskKind.MULTISTEP:
            D = cfg.step_deadline_s * ch.n_steps
        else:
            D = cfg.step_deadline_s
        success = outcome == Outcome.SUCCESS
        # success by the chain's full deadline D; every non-success stays "not yet" until D
        # (no early censoring: refusal, skip, rubric and order failures preclude success)
        tts = float(info.get("t_complete", info.get("tvc", 0.0))) if success else D

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
            n_revisions=n_rev,
            deadline_s=D,
            time_to_success=tts,
            success_event=success,
            competing_failure=outcome == Outcome.ORDER_FAIL,
            steps_complied=int(info.get("steps_complied", 0)),
            missing=missing,
        )
        if rec.in_primary and ch.kind == TaskKind.ACTION:
            if info.get("tvc") is not None and info["tvc"] <= D:
                rec.tvc, rec.tvc_event = info["tvc"], True
            else:
                rec.tvc, rec.tvc_event = D, False  # censored at D
        if rec.in_primary and ch.kind == TaskKind.CONTENT:
            rec.onset_s = info.get("onset_s")
            rec.onset_ok = bool(info.get("onset_ok", False))
        if rec.in_primary:
            on = [float(e["t"]) - o for e in onsets if float(e["t"]) >= o]
            first = min(on) if on else None
            if first is not None and first <= cfg.tfmr_horizon_s:
                rec.tfmr, rec.tfmr_event = first, True
            else:
                rec.tfmr, rec.tfmr_event = cfg.tfmr_horizon_s, False
        # every audible completion claim, withdrawn chains included
        rec.n_claims, rec.n_false_claims, rec.n_claims_unadjudicated = _claims(
            ch, ev.get("completion_claim", []), all_v, direct, chunks, cfg
        )
        # RQ2: every randomised failure point, whatever later happens to the chain
        for r in ev.get("repair_assignment", []):
            rec.repairs.append(_repair(r, ch, rec.outcome, vs, chunks, obs_end))
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
    barge, missing_stop = [], 0
    for u in utts.values():
        if not u.get("barge_in"):
            continue
        after = [s for s in stops if s >= float(u["t_start"])]
        if after:
            barge.append(after[0] - float(u["t_start"]))
        else:
            missing_stop += 1

    return SessionScore(
        session_id=session.session_id,
        condition=session.condition,
        task_id=session.task_id,
        seed=session.seed,
        chains=out,
        visual_ack_s=acks,
        barge_in_stop_s=barge,
        barge_ins_without_stop=missing_stop,
        diagnostic=cfg.diagnostic,
        sources=tuple(cfg.source_preference),
        observation_end=obs_end,
        claim_sweep=any(e.get("source") == "adjudicated" for e in session.of_type("claim_sweep")),
        rq2_problems=rq2_problems(session, chains, chunks, obs_end) if session.condition in RQ2_CONDITIONS else [],
    )


def adjudication_gaps(sessions: list[SessionScore]) -> list[str]:
    """Human-readable list of what blocks the primary analysis (empty = complete)."""
    gaps = []
    for s in sessions:
        if not s.diagnostic and not s.claim_sweep:
            gaps.append(f"{s.session_id}: no adjudicated audio claim sweep (FCR needs every audible claim)")
        for c in s.chains:
            if c.outcome == Outcome.UNADJUDICATED:
                gaps.append(f"{s.session_id} {c.chain_id}: {c.missing}")
            if c.n_claims_unadjudicated:
                gaps.append(f"{s.session_id} {c.chain_id}: {c.n_claims_unadjudicated} completion "
                            "claim(s) without a reconciled claim-level verdict")
            if any(r["status"] == "unadjudicated" for r in c.repairs):
                gaps.append(f"{s.session_id} {c.chain_id}: RQ2 failure point on an unadjudicated chain")
    return gaps


def require_complete(sessions: list[SessionScore]) -> None:
    """Raise unless every chain and claim needed by the primary analysis is adjudicated."""
    if any(s.diagnostic for s in sessions):
        return
    gaps = adjudication_gaps(sessions)
    if gaps:
        raise IncompleteAdjudicationError(
            f"{len(gaps)} adjudication gap(s); the primary report needs a reconciled "
            "adjudicated verdict for every effective chain and claim:\n  " + "\n  ".join(gaps)
        )


def observation_gaps(sessions: list[SessionScore]) -> list[str]:
    return [f"{s.session_id} {c.chain_id}: {c.missing}" for s in sessions for c in s.chains
            if c.outcome == Outcome.INSUFFICIENT_OBSERVATION]


def require_observed(sessions: list[SessionScore]) -> None:
    """Raise unless every deadline window was observed (preregistered rule 'rerun-required')."""
    gaps = observation_gaps(sessions)
    if gaps:
        raise InsufficientObservationError(
            f"{len(gaps)} chain(s) with an unobserved deadline window; rerun these trials (and "
            "their pairs) or select a preregistered missing-data rule explicitly:\n  " + "\n  ".join(gaps)
        )


def impute_worst_case(sessions: list[SessionScore]) -> list[SessionScore]:
    """Missing-data rule 'worst-case' (sensitivity only): every insufficiently observed
    chain counts as a failure (outcome ``never`` at its deadline)."""
    out = []
    for s in sessions:
        ch = [dataclasses.replace(c, outcome=Outcome.NEVER, missing=f"worst-case imputed: {c.missing}",
                                  success_event=False, time_to_success=c.deadline_s)
              if c.outcome == Outcome.INSUFFICIENT_OBSERVATION else c for c in s.chains]
        out.append(dataclasses.replace(s, chains=ch))
    return out


# --------------------------------------------------------------------------- aggregation


def _rate(k: int, n: int) -> float:
    return k / n if n else math.nan


def _repair_summary(rs: list[dict[str, Any]]) -> dict[str, Any]:
    """Primary: success / (success + failure + withdrawn); sensitivity excludes withdrawn.
    Insufficiently observed points are excluded and counted (rerun)."""
    st = [r["status"] for r in rs]
    k = st.count("success")
    n = k + st.count("failure") + st.count("withdrawn")
    return {"n": n, "k": k, "n_withdrawn": st.count("withdrawn"),
            "n_insufficient_observation": st.count("insufficient_observation"),
            "n_unadjudicated": st.count("unadjudicated"),
            "n_ineligible": st.count("ineligible"),
            "n_excl_withdrawn": n - st.count("withdrawn"),
            "offsets": sorted(r["offset"] for r in rs if r["offset"] is not None)}


def summarize(chains: list[ChainOutcome]) -> dict[str, Any]:
    """Point estimates for one condition (CIs are added in report.py). The primary
    denominator excludes withdrawn, unadjudicated and insufficiently observed chains (the
    last two are counted separately). FCR counts every claim, withdrawn chains included."""
    eff = [c for c in chains if c.in_primary]
    n = len(eff)
    succ = sum(c.success for c in eff)
    skipped = sum(c.outcome == Outcome.CAPACITY_SKIPPED for c in eff)
    refused = sum(c.outcome in (Outcome.REFUSED, Outcome.DEGRADED) for c in eff)
    unknown = sum(c.outcome == Outcome.UNKNOWN for c in eff)
    served = [c for c in eff if c.served]
    content = [c for c in eff if c.kind == TaskKind.CONTENT.value]
    claims = sum(c.n_claims - c.n_claims_unadjudicated for c in chains)
    false_claims = sum(c.n_false_claims for c in chains)
    reps = [r for c in chains for r in c.repairs]  # every randomised failure point
    return {
        "n_effective": n,
        "n_success": succ,
        "success_rate": _rate(succ, n),
        "n_withdrawn": sum(c.outcome == Outcome.WITHDRAWN for c in chains),
        "n_insufficient_observation": sum(c.outcome == Outcome.INSUFFICIENT_OBSERVATION for c in chains),
        "n_unadjudicated": sum(c.outcome == Outcome.UNADJUDICATED for c in chains),
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
        "n_claims_unadjudicated": sum(c.n_claims_unadjudicated for c in chains),
        "fcr": _rate(false_claims, claims),
        "claim_coverage": _rate(sum(c.n_claims > 0 for c in eff), n),
        "claim_coverage_of_successes": _rate(
            sum(c.n_claims > 0 for c in eff if c.success), succ
        ),
        "repair": {arm: _repair_summary([r for r in reps if r["arm"] == arm])
                   for arm in sorted({r["arm"] for r in reps})},
        "outcomes": {o.value: sum(c.outcome == o for c in chains) for o in Outcome},
    }
