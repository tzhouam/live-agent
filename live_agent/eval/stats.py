"""Statistics for E1-E6 (proposal v2.11 §7.7): binomial intervals, Kaplan-Meier with
right-censoring, clustered bootstrap (cluster = task), Holm, Cohen's kappa,
non-inferiority, and simulation-based power for a paired clustered binary outcome."""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import optimize, stats

# --------------------------------------------------------------------------- binomial


def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Two-sided Wilson score interval."""
    if n == 0:
        return (math.nan, math.nan)
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return (float(lo), float(hi))


def wilson_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided upper Wilson bound at level ``conf``."""
    return wilson(k, n, 2 * conf - 1)[1]


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson interval."""
    if n == 0:
        return (math.nan, math.nan)
    a = 1 - conf
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return (lo, hi)


def clopper_pearson_upper(k: int, n: int, conf: float = 0.95) -> float:
    """Exact one-sided upper bound (RQ5 leakage: 0/300 -> 0.00994)."""
    if n == 0:
        return math.nan
    return 1.0 if k == n else float(stats.beta.ppf(conf, k + 1, n - k))


# --------------------------------------------------------------------------- Kaplan-Meier


@dataclass
class KMResult:
    times: np.ndarray  # distinct event times
    survival: np.ndarray  # S(t) just after each event time
    at_risk: np.ndarray
    events: np.ndarray
    greenwood_var: np.ndarray

    def s_at(self, t: float) -> float:
        idx = np.searchsorted(self.times, t, side="right") - 1
        return 1.0 if idx < 0 else float(self.survival[idx])

    @property
    def median(self) -> float | None:
        """Smallest t with S(t) <= 0.5; None if not reached (report as '> horizon')."""
        hit = np.nonzero(self.survival <= 0.5 + 1e-12)[0]
        return float(self.times[hit[0]]) if hit.size else None

    def quantile(self, q: float) -> float | None:
        """Time by which a fraction q has had the event (e.g. q=0.95 -> p95)."""
        hit = np.nonzero(1 - self.survival >= q - 1e-12)[0]
        return float(self.times[hit[0]]) if hit.size else None

    def rmst(self, horizon: float) -> float:
        """Restricted mean time to event: integral of S(t) over [0, horizon]."""
        grid = np.concatenate([[0.0], self.times[self.times < horizon], [horizon]])
        s = np.concatenate([[1.0], self.survival[self.times < horizon]])
        return float(np.sum(np.diff(grid) * s))


def kaplan_meier(times: Sequence[float], events: Sequence[bool | int]) -> KMResult:
    """Product-limit estimator; ties: events before censorings at the same time."""
    t = np.asarray(times, dtype=float)
    e = np.asarray(events, dtype=bool)
    if t.size == 0:
        z = np.zeros(0)
        return KMResult(z, z, z, z, z)
    ut = np.unique(t[e])
    s, var_sum = 1.0, 0.0
    surv, risk, ev, gw = [], [], [], []
    for u in ut:
        n = int(np.sum(t >= u))
        d = int(np.sum((t == u) & e))
        s *= 1 - d / n
        if n > d:
            var_sum += d / (n * (n - d))
        surv.append(s)
        risk.append(n)
        ev.append(d)
        gw.append(s * s * var_sum)
    return KMResult(ut, np.array(surv), np.array(risk), np.array(ev), np.array(gw))


# --------------------------------------------------------------------------- bootstrap


def _cluster_index(clusters: Sequence[Hashable]) -> tuple[np.ndarray, int]:
    labels = {c: i for i, c in enumerate(dict.fromkeys(clusters))}
    return np.array([labels[c] for c in clusters], dtype=int), len(labels)


def cluster_bootstrap_mean(
    x: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Percentile CI of a pooled mean, resampling whole clusters with replacement."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {"estimate": math.nan, "lo": math.nan, "hi": math.nan, "boot": np.zeros(0)}
    idx, C = _cluster_index(clusters)
    sums = np.bincount(idx, weights=x, minlength=C)
    cnts = np.bincount(idx, minlength=C).astype(float)
    rng = np.random.default_rng(rng)
    draw = rng.integers(0, C, size=(n_boot, C))
    boot = sums[draw].sum(1) / cnts[draw].sum(1)
    a = (1 - conf) / 2
    return {
        "estimate": float(x.mean()),
        "lo": float(np.quantile(boot, a)),
        "hi": float(np.quantile(boot, 1 - a)),
        "boot": boot,
    }


def cluster_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Paired difference mean(a - b); units paired by position, clusters resampled whole.
    Also returns a two-sided bootstrap p-value (2 x the smaller tail mass at 0)."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    r = cluster_bootstrap_mean(d, clusters, n_boot=n_boot, conf=conf, rng=rng)
    boot = r["boot"]
    if boot.size:
        p = 2 * min(np.mean(boot <= 0), np.mean(boot >= 0))
        r["p_value"] = float(min(1.0, p))
    else:
        r["p_value"] = math.nan
    return r


def cluster_bootstrap_rate_diff(
    x: Sequence[float],
    in_a: Sequence[bool],
    clusters: Sequence[Hashable],
    n_boot: int = 4000,
    conf: float = 0.95,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Unpaired difference mean(x | A) - mean(x | not A) with clusters resampled whole
    (e.g. RQ2 forward-correction vs repeat arms randomised within tasks)."""
    x = np.asarray(x, dtype=float)
    g = np.asarray(in_a, dtype=bool)
    idx, C = _cluster_index(clusters)
    sa = np.bincount(idx, weights=x * g, minlength=C)
    na = np.bincount(idx, weights=g.astype(float), minlength=C)
    sb = np.bincount(idx, weights=x * ~g, minlength=C)
    nb = np.bincount(idx, weights=(~g).astype(float), minlength=C)
    est = (x[g].mean() if g.any() else math.nan) - (x[~g].mean() if (~g).any() else math.nan)
    rng = np.random.default_rng(rng)
    draw = rng.integers(0, C, size=(n_boot, C))
    with np.errstate(divide="ignore", invalid="ignore"):
        boot = sa[draw].sum(1) / na[draw].sum(1) - sb[draw].sum(1) / nb[draw].sum(1)
    boot = boot[np.isfinite(boot)]
    a = (1 - conf) / 2
    if boot.size == 0:
        return {"estimate": float(est), "lo": math.nan, "hi": math.nan, "p_value": math.nan}
    p = min(1.0, 2 * min(np.mean(boot <= 0), np.mean(boot >= 0)))
    return {
        "estimate": float(est),
        "lo": float(np.quantile(boot, a)),
        "hi": float(np.quantile(boot, 1 - a)),
        "p_value": float(p),
    }


# --------------------------------------------------------------------------- multiplicity


def holm(pvalues: Sequence[float], alpha: float = 0.05) -> dict[str, list]:
    """Holm step-down; returns adjusted p-values and reject flags in input order."""
    p = np.asarray(pvalues, dtype=float)
    m = p.size
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return {"adjusted": adj.tolist(), "reject": (adj <= alpha).tolist()}


# --------------------------------------------------------------------------- agreement


def cohens_kappa(r1: Sequence[Hashable], r2: Sequence[Hashable], categories=None) -> float:
    if len(r1) != len(r2) or not r1:
        raise ValueError("ratings must be non-empty and equal length")
    cats = list(categories) if categories is not None else sorted(set(r1) | set(r2), key=str)
    ix = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    m = np.zeros((k, k))
    for a, b in zip(r1, r2):
        m[ix[a], ix[b]] += 1
    n = m.sum()
    po = np.trace(m) / n
    pe = float(m.sum(1) @ m.sum(0)) / (n * n)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return float((po - pe) / (1 - pe))


# --------------------------------------------------------------------------- non-inferiority


def noninferiority(
    new: Sequence[float],
    ref: Sequence[float],
    clusters: Sequence[Hashable],
    margin: float,
    alpha: float = 0.025,
    n_boot: int = 4000,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, Any]:
    """One-sided non-inferiority of ``new`` vs ``ref`` (higher is better), paired units,
    clustered bootstrap. Non-inferior iff the one-sided (1 - alpha) lower bound of
    mean(new - ref) exceeds -margin. margin > 0, e.g. 0.05 for 5 pp (RQ3 H3b, RQ5)."""
    r = cluster_bootstrap_diff(new, ref, clusters, n_boot=n_boot, conf=1 - 2 * alpha, rng=rng)
    return {
        "estimate": r["estimate"],
        "lower": r["lo"],
        "margin": margin,
        "alpha": alpha,
        "noninferior": bool(r["lo"] > -margin),
    }


# --------------------------------------------------------------------------- power


def _latent_sigma(icc: float) -> float:
    """Logit-scale random-effect SD giving latent-variable ICC (residual var pi^2/3)."""
    if icc <= 0:
        return 0.0
    return math.sqrt(icc / (1 - icc) * math.pi**2 / 3)


_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(40)
_GH_W = _GH_W / _GH_W.sum()


def _intercept_for_marginal(p: float, sigma: float) -> float:
    """beta such that E[expit(beta + sigma Z)] = p, Z ~ N(0,1)."""
    if sigma == 0:
        return math.log(p / (1 - p))

    def f(b: float) -> float:
        return float(np.sum(_GH_W / (1 + np.exp(-(b + sigma * _GH_X))))) - p

    return float(optimize.brentq(f, -40, 40))


def simulate_power(
    baseline: float,
    effect: float,
    icc: float,
    n_tasks: int,
    n_seeds: int,
    alpha: float = 0.05,
    n_comparisons: int = 1,
    n_sims: int = 2000,
    rng: np.random.Generator | int | None = 0,
) -> dict[str, float]:
    """Power for a paired, task-clustered binary outcome (proposal §7.2 power analysis).

    Model: task random intercept u_t ~ N(0, sigma^2) on the logit scale, shared by both
    arms (pairing), sigma from the latent ICC; arm intercepts calibrated so the marginal
    success rates are ``baseline`` and ``baseline + effect``; each (task, seed, arm) trial
    is Bernoulli. Analysis: two-sided one-sample t-test on per-task mean differences
    (the cluster-level analogue of the clustered bootstrap) at alpha / n_comparisons
    (Holm's first, strictest step: conservative). Power counts only rejections in the
    direction of ``effect``."""
    p1 = baseline + effect
    if not (0 < baseline < 1 and 0 < p1 < 1):
        raise ValueError("baseline and baseline+effect must be in (0, 1)")
    if n_tasks < 2:
        raise ValueError("need >= 2 tasks")
    rng = np.random.default_rng(rng)
    sigma = _latent_sigma(icc)
    b0 = _intercept_for_marginal(baseline, sigma)
    b1 = _intercept_for_marginal(p1, sigma)
    u = rng.normal(0.0, sigma, size=(n_sims, n_tasks))
    y0 = rng.binomial(n_seeds, 1 / (1 + np.exp(-(b0 + u))))
    y1 = rng.binomial(n_seeds, 1 / (1 + np.exp(-(b1 + u))))
    d = (y1 - y0) / n_seeds
    mean = d.mean(1)
    sd = d.std(1, ddof=1)
    a = alpha / n_comparisons
    crit = stats.t.ppf(1 - a / 2, n_tasks - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = np.where(sd > 0, mean / (sd / math.sqrt(n_tasks)), np.sign(mean) * np.inf)
    sign = 1.0 if effect >= 0 else -1.0
    reject = (np.abs(tstat) > crit) & (np.sign(tstat) == sign)
    if effect == 0:
        reject = np.abs(tstat) > crit
    power = float(reject.mean())
    return {
        "power": power,
        "mc_se": math.sqrt(power * (1 - power) / n_sims),
        "alpha_per_test": a,
        "sigma_logit": sigma,
        "n_trials_per_arm": n_tasks * n_seeds,
    }


def min_tasks_for_power(
    target: float = 0.8,
    task_grid: Sequence[int] = (10, 20, 30, 40, 60, 80, 100, 120, 160),
    **kw: Any,
) -> dict[str, Any]:
    """Smallest task count in ``task_grid`` reaching ``target`` power (None if none)."""
    curve = {}
    for t in task_grid:
        curve[t] = simulate_power(n_tasks=t, **kw)["power"]
        if curve[t] >= target:
            return {"n_tasks": t, "curve": curve}
    return {"n_tasks": None, "curve": curve}


def percentiles(x: Sequence[float], qs: Sequence[float] = (50, 95, 99)) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {f"p{int(q)}": math.nan for q in qs}
    return {f"p{int(q)}": float(np.percentile(x, q)) for q in qs}

