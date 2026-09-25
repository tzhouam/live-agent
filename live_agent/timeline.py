"""Single timeline, just-in-time locking and correction eligibility (proposal §10, §11).

Events per request k: lock P_k -> teacher (G_a) -> student (first chunk G_1) -> ready
-> presented V_k (4 chunks, ~R seconds). Hard constraints:

    ready_{k+1} = max(P_{k+1} + G_a, done_k) + G_1 + delta
    V_{k+1}     = max(ready_{k+1}, V_k + R)

Just-in-time lock (D-018):  P_{k+1} = V_k + R - Lambda - sigma, Lambda = G_a + G_1 + delta,
estimated online from measured request timings (a high quantile, for safety).
"Early" lock (contrast): P_{k+1} = V_k.
"""

from __future__ import annotations

import enum
import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO

from live_agent.generator.base import RequestTiming
from live_agent.types import EventType, TimelineEvent, now


class LockMode(str, enum.Enum):
    JIT = "jit"
    EARLY = "early"


@dataclass
class SchedulerConfig:
    request_s: float = 5.0
    sigma_s: float = 0.5  # safety margin (also used for the spoken-audio ASR check)
    delta_s: float = 0.15  # mux + transport estimate until measured
    lambda_prior_s: float = 3.0  # used until enough timings are observed
    lambda_quantile: float = 0.9
    min_observations: int = 3
    mode: LockMode = LockMode.JIT
    time_scale: float = 1.0  # simulation: wall seconds per content second (1/speed)


class LockScheduler:
    def __init__(self, cfg: SchedulerConfig | None = None):
        self.cfg = cfg or SchedulerConfig()
        self._timings: list[RequestTiming] = []
        self.presented_start: dict[int, float] = {}  # V_k
        self.locks: dict[int, float] = {}  # P_k
        self.durations: dict[int, float] = {}  # playback duration of request k (sum of its chunks)
        self.restart: int = 0  # first request after the latest interruption (timeline restarts here)

    # ------------------------------------------------------------ observations
    def observe_timing(self, t: RequestTiming) -> None:
        self._timings = [x for x in self._timings if x.request_index != t.request_index] + [t]
        self._timings = self._timings[-50:]

    def on_lock(self, k: int, t: float) -> None:
        self.locks[k] = t

    def on_presented(self, k: int, t: float) -> None:
        self.presented_start.setdefault(k, t)

    def interrupt(self, next_k: int) -> None:
        """Barge-in / erasure: everything before ``next_k`` was dropped or already shown; the
        timeline restarts at ``next_k``, which is locked immediately (like request 0)."""
        self.restart = next_k

    def on_duration(self, k: int, seconds: float) -> None:
        """Playback length of request k (e.g. 124 frames for the first request, 119 later)."""
        self.durations[k] = seconds * self.cfg.time_scale

    # ------------------------------------------------------------ estimates
    def effective_leads(self) -> list[float]:
        """Lambda samples: first chunk ready minus max(lock, previous request done).

        Lock -> first chunk alone includes the wait for request k-1's final KV commit when the
        lock came early (M0: ~1.5 s idle vs 3.6-4.5 s pipelined); feeding that into
        P_{k+1} = V_k + R - Lambda - sigma would push locks earlier and earlier. The KV wait is
        a separate constraint (ready_{k+1} >= done_k + G_1) and is not part of Lambda."""
        by_k = {x.request_index: x for x in self._timings}
        out = []
        for k, x in sorted(by_k.items()):
            if x.t_first_chunk is None:
                continue
            prev = by_k.get(k - 1)
            # Unknown predecessor: lock time (conservative: may include some KV wait).
            start = max(x.t_lock, prev.t_done) if prev is not None and prev.t_done is not None else x.t_lock
            out.append(x.t_first_chunk - start)
        return out

    def lambda_estimate(self) -> float:
        leads = self.effective_leads()
        if len(leads) < self.cfg.min_observations:
            return self.cfg.lambda_prior_s
        leads.sort()
        idx = min(len(leads) - 1, int(round(self.cfg.lambda_quantile * (len(leads) - 1))))
        return leads[idx] + self.cfg.delta_s

    def mean_request_time(self) -> float | None:
        vals = [x.t_done - x.t_lock for x in self._timings if x.t_done is not None]
        return statistics.fmean(vals) if vals else None

    def keeps_up(self) -> bool | None:
        """Throughput condition: mean full-pipeline time per request < R (with 10% margin)."""
        m = self.mean_request_time()
        return None if m is None else m < 0.9 * self.cfg.request_s

    # ------------------------------------------------------------ locking
    def expected_presentation(self, k: int) -> float | None:
        """V_k if known, else extrapolated from the latest known presentation start."""
        if k in self.presented_start:
            return self.presented_start[k]
        floor = self.restart if k >= self.restart else 0
        known = [i for i in self.presented_start if floor <= i < k]
        if not known:
            return None
        j = max(known)
        return self.presented_start[j] + sum(self.durations.get(i, self.cfg.request_s) for i in range(j, k))

    def lock_time(self, k_next: int) -> float | None:
        """Wall-clock time at which request ``k_next`` should be locked.

        Returns None while the time is not yet determined (start-up: request k_next-1 has
        not started presenting, so V_{k_next-1} is unknown). The caller waits and asks again;
        locking early would commit content far ahead of playback and delay every instruction.
        """
        if k_next == 0 or k_next == self.restart:
            return now()
        v_prev = self.expected_presentation(k_next - 1)
        if v_prev is None:
            return None
        if self.cfg.mode == LockMode.EARLY:
            return v_prev
        return v_prev + self.cfg.request_s - self.lambda_estimate() - self.cfg.sigma_s

    # ------------------------------------------------------------ corrections
    def planned_lock(self, j: int) -> float | None:
        """P_j: actual lock time if already locked, else the planned one (None if unknown)."""
        if j in self.locks:
            return self.locks[j]
        v_prev = self.expected_presentation(j - 1)
        if v_prev is None:
            return None
        if self.cfg.mode == LockMode.EARLY:
            return v_prev
        return v_prev + self.cfg.request_s - self.lambda_estimate() - self.cfg.sigma_s

    def earliest_correctable(self, t_evidence: float, chain_cost_s: float, next_unlocked: int) -> int:
        """First request j >= next_unlocked with P_j >= E + C (no upper bound; proposal §10.3)."""
        t_ready = t_evidence + chain_cost_s
        j = next_unlocked
        for _ in range(10_000):
            pj = self.planned_lock(j)
            if pj is None or pj >= t_ready:
                return j
            j += 1
        return j


def tvc_model(A: float, wait: float, lam: float, sigma: float, inertia: float, R: float,
              mode: LockMode = LockMode.JIT, lookahead: int = 0) -> float:
    """Illustrative latency model (proposal §11): returns predicted TVC for one instruction."""
    if mode == LockMode.JIT:
        return A + wait + lam + sigma + inertia
    return A + wait + (lookahead + 1) * R + inertia


# ---------------------------------------------------------------------- event log


class EventLog:
    """Append-only JSONL log of timeline events (consumed by live_agent.eval)."""

    def __init__(self, path: str | Path | None = None):
        self.events: list[TimelineEvent] = []
        self.path = Path(path) if path else None
        self._fh: IO[str] | None = open(path, "a", encoding="utf-8") if path else None

    def redact(self, term: str, replacement: str = "[已删除]") -> int:
        """Erasure: replace ``term`` in every logged string (memory and file). Returns #events touched."""
        def scrub(x):
            if isinstance(x, str):
                return x.replace(term, replacement)
            if isinstance(x, list):
                return [scrub(v) for v in x]
            if isinstance(x, dict):
                return {k: scrub(v) for k, v in x.items()}
            return x

        n = 0
        for e in self.events:
            new = scrub(e.data)
            if new != e.data:
                e.data = new
                n += 1
        if self.path is not None and self._fh is not None:
            self._fh.close()
            lines = self.path.read_text(encoding="utf-8").splitlines()
            self.path.write_text("".join(json.dumps(scrub(json.loads(x)), ensure_ascii=False) + "\n"
                                         for x in lines if x.strip()), encoding="utf-8")
            self._fh = open(self.path, "a", encoding="utf-8")
        return n

    def emit(self, type_: EventType, t: float | None = None, **kw) -> TimelineEvent:
        ev = TimelineEvent(type=type_, t=now() if t is None else t,
                           request_index=kw.pop("request_index", None),
                           chunk_index=kw.pop("chunk_index", None), data=kw)
        self.events.append(ev)
        if self._fh:
            d = asdict(ev)
            d["type"] = ev.type.value
            self._fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            self._fh.flush()
        return ev

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None
