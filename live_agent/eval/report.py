"""Markdown report from scored E2 sessions, per condition, with CIs (proposal v2.11 §7.7).

Usage::

    python -m live_agent.eval.report logs/*.jsonl -o report.md              # primary (adjudicated)
    python -m live_agent.eval.report logs/*.jsonl --source judge -o diag.md  # DIAGNOSTIC only

The primary report scores reconciled ``adjudicated`` verdicts only (D-014) and refuses to
run while any effective chain or completion claim lacks adjudication. ``--source`` other
than ``adjudicated`` produces a report headed DIAGNOSTIC, which is not a result.

Hypothesis tests use fixed, preregistered families (``FAMILIES``); Holm is applied over
the preregistered family size whatever subset is present or displayed. ``--compare`` only
selects which rows are displayed; pairs outside the families are shown as exploratory,
unadjusted, with no decision.

Every number in the output is *measured locally* from the given logs; thresholds quoted
from §8 are *proposed targets*.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence

from live_agent.eval import stats
from live_agent.eval.schema import load_session
from live_agent.eval.scoring import (
    RQ2_CONDITIONS,
    ChainOutcome,
    IncompleteAdjudicationError,
    InsufficientObservationError,
    ScoringConfig,
    SessionScore,
    impute_worst_case,
    require_complete,
    require_observed,
    score_session,
    summarize,
)

# Preregistered comparison families (proposal §5 RQ1 / §7.2). Difference = A - B.
PRIMARY_FAMILY: tuple[tuple[str, str], ...] = (("A2", "A1"),)  # H1a
H1C_FAMILY: tuple[tuple[str, str], ...] = (  # H1c ablations: each is expected to lower success
    ("A2", "A2-noqc"),
    ("A2", "A2-noledger"),
    ("A2", "A2-nomanifest"),
    ("A2", "A2-nocorrection"),
)
MISSING_RULES = ("rerun-required", "worst-case")  # preregistered; see build_report
MIN_TASKS = 10  # *proposed target*: fewest independent task clusters for any inferential decision
FAMILIES: dict[str, tuple[tuple[str, str], ...]] = {
    "primary (H1a)": PRIMARY_FAMILY,
    "secondary (H1c ablations)": H1C_FAMILY,
}


def _f(x: float | None, pct: bool = False, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.{nd + 1}f}"


def _ci(lo: float, hi: float, pct: bool = True) -> str:
    return f"[{_f(lo, pct)}, {_f(hi, pct)}]"


def _key(c: ChainOutcome) -> tuple[str, int, str]:
    return (c.task_id, c.seed, c.label)


def _rate_line(name: str, k: int, n: int, clusters: Sequence[str] | None = None,
               values: Sequence[float] | None = None, n_boot: int = 4000) -> str:
    if n == 0:
        return f"| {name} | 0/0 | n/a | n/a | n/a |"
    w = stats.wilson(k, n)
    boot = "n/a"
    if clusters is not None and values is not None and len(set(clusters)) > 1:
        b = stats.cluster_bootstrap_mean(values, clusters, n_boot=n_boot)
        boot = _ci(b["lo"], b["hi"])
    return f"| {name} | {k}/{n} | {_f(k / n, True)} | {_ci(*w)} | {boot} |"


def _claim_units(chains: Iterable[ChainOutcome]) -> tuple[list[str], list[float]]:
    """One unit per adjudicated claim (1 = false), clustered by task: the bootstrap of
    the pooled mean is then the task-clustered ratio estimator of FCR."""
    cl, xs = [], []
    for c in chains:
        n = c.n_claims - c.n_claims_unadjudicated
        cl += [c.task_id] * n
        xs += [1.0] * c.n_false_claims + [0.0] * (n - c.n_false_claims)
    return cl, xs


def condition_section(cond: str, sessions: list[SessionScore], n_boot: int = 4000) -> list[str]:
    chains = [c for s in sessions for c in s.chains]
    eff = [c for c in chains if c.in_primary]
    sm = summarize(chains)
    cl = [c.task_id for c in eff]
    L = [f"## Condition `{cond}`", ""]
    L.append(
        f"Sessions: {len(sessions)}; tasks: {len({s.task_id for s in sessions})}; "
        f"effective chains scored: {sm['n_effective']}; withdrawn chains (excluded): "
        f"{sm['n_withdrawn']}; insufficient observation (excluded, rerun): "
        f"{sm['n_insufficient_observation']}."
    )
    L += ["", "| Metric | k/n | Estimate | Wilson 95% CI | Task-clustered bootstrap 95% CI |",
          "|---|---|---|---|---|"]
    L.append(_rate_line("Instruction-level success (primary)", sm["n_success"], sm["n_effective"],
                        cl, [float(c.success) for c in eff], n_boot))
    unk = [c for c in eff if c.outcome.value != "unknown"]
    L.append(_rate_line("Success, excluding 'cannot tell' (sensitivity)",
                        sum(c.success for c in unk), len(unk),
                        [c.task_id for c in unk], [float(c.success) for c in unk], n_boot))
    L.append(_rate_line("Capacity-skip rate", sm["n_capacity_skipped"], sm["n_effective"],
                        cl, [float(c.outcome.value == "capacity_skipped") for c in eff], n_boot))
    L.append(_rate_line("Refusal / degradation rate", sm["n_refused_degraded"], sm["n_effective"],
                        cl, [float(c.outcome.value in ("refused", "degraded")) for c in eff], n_boot))
    served = [c for c in eff if c.served]
    L.append(_rate_line("Conditional success (served chains)", sum(c.success for c in served),
                        len(served), [c.task_id for c in served],
                        [float(c.success) for c in served], n_boot))
    content = [c for c in eff if c.kind == "content"]
    L.append(_rate_line("Content onset <= 15 s (reported separately)",
                        sum(bool(c.onset_ok) for c in content), len(content),
                        [c.task_id for c in content], [float(bool(c.onset_ok)) for c in content], n_boot))
    ccl, cx = _claim_units(chains)
    L.append(_rate_line("FCR (false / all audible completion claims, withdrawn chains incl.)",
                        sm["n_false_claims"], sm["n_claims"], ccl, cx, n_boot))
    L.append(_rate_line("Claim coverage (chains with >= 1 claim)",
                        sum(c.n_claims > 0 for c in eff), len(eff),
                        cl, [float(c.n_claims > 0) for c in eff], n_boot))
    for arm, r in sm["repair"].items():
        L.append(_rate_line(f"Repair rate, arm `{arm}` (RQ2, every failure point; withdrawal = failure)",
                            r["k"], r["n"]))
        L.append(_rate_line(f"Repair rate, arm `{arm}` (sensitivity: withdrawn excluded)",
                            r["k"], r["n_excl_withdrawn"]))

    # by kind
    L += ["", "**Success by chain kind**", "", "| Kind | k/n | Estimate | Wilson 95% CI |", "|---|---|---|---|"]
    by_kind: dict[str, list[ChainOutcome]] = defaultdict(list)
    for c in eff:
        by_kind[c.kind].append(c)
    for k, cs in sorted(by_kind.items()):
        kk, nn = sum(c.success for c in cs), len(cs)
        L.append(f"| {k} | {kk}/{nn} | {_f(kk / nn, True)} | {_ci(*stats.wilson(kk, nn))} |")
    L += ["", "Outcome counts: " + ", ".join(f"{k}={v}" for k, v in sm["outcomes"].items() if v)]
    rerun = [c for c in chains if c.outcome.value == "insufficient_observation"]
    if rerun:
        L.append("\nFlagged for rerun (deadline window not fully observed): "
                 + "; ".join(f"{c.session_id} {c.chain_id} ({c.missing})" for c in rerun))

    # repair offsets
    for arm, r in sm["repair"].items():
        L.append(f"Repair `{arm}`: earliest eligible request offset j-k = {r['offsets']}; withdrawn after "
                 f"assignment: {r['n_withdrawn']}; target request not observed (excluded, rerun): "
                 f"{r['n_insufficient_observation']}")

    # time-to-event
    L += ["", "**Time to event (Kaplan-Meier, right-censored at D)**", "",
          "| Measure | n | events | deadline success | KM median (s) | RMST to horizon (s) |",
          "|---|---|---|---|---|---|"]

    def km_row(name: str, ts: list[float], es: list[bool], H: float) -> None:
        km = stats.kaplan_meier(ts, es)
        med = km.median
        L.append(f"| {name} | {len(ts)} | {sum(es)} | {_f(sum(es) / len(ts), True)} | "
                 f"{_f(med) if med is not None else f'> {H:g}'} | {_f(km.rmst(H))} (H={H:g}) |")

    act = [c for c in eff if c.tvc is not None]
    if act:
        km_row("TVC (action chains)", [c.tvc for c in act], [c.tvc_event for c in act],
               max(c.deadline_s for c in act))
    tf = [c for c in eff if c.tfmr is not None]
    if tf:
        km_row("TFMR (on-topic speech onset)", [c.tfmr for c in tf], [c.tfmr_event for c in tf],
               max(c.tfmr for c in tf))

    # Success by deadline per kind (common D within each group). Every chain is followed to
    # its full deadline D (unobserved windows are excluded), so nothing is censored before D:
    # the product-limit curve below equals the cumulative incidence of success, with
    # refusal, capacity skip, rubric / onset / order failure and late or no compliance all
    # kept in the risk set as competing outcomes that preclude success by D.
    groups: dict[tuple[str, float], list[ChainOutcome]] = defaultdict(list)
    for c in eff:
        name = c.kind + (f"/{c.content_type}" if c.content_type else "")
        groups[(name, c.deadline_s)].append(c)
    if groups:
        L += ["", ("**Success by the common deadline, per kind (cumulative incidence; competing failures "
                   "kept, no early censoring)**"), "",
              "| Kind | D (s) | n | success by D | Wilson 95% CI | median time to success (s) |",
              "|---|---|---|---|---|---|"]
        for (name, D), cs in sorted(groups.items()):
            ts = [c.time_to_success if c.success else D for c in cs]
            km = stats.kaplan_meier(ts, [c.success for c in cs])
            k = sum(c.success for c in cs)
            med = km.median
            L.append(f"| {name} | {D:g} | {len(cs)} | {k}/{len(cs)} ({_f(k / len(cs), True)}) | "
                     f"{_ci(*stats.wilson(k, len(cs)))} | {_f(med) if med is not None else f'> {D:g}'} |")

    # latencies
    va = [x for s in sessions for x in s.visual_ack_s]
    bi = [x for s in sessions for x in s.barge_in_stop_s]
    miss = sum(s.barge_ins_without_stop for s in sessions)
    L += ["", "**Latency (s; p50 / p95 / p99)**", "", "| Measure | n | p50 | p95 | p99 |", "|---|---|---|---|---|"]
    for name, xs in (("Visual acknowledgement", va), ("Barge-in playback stop (client)", bi)):
        p = stats.percentiles(xs)
        L.append(f"| {name} | {len(xs)} | {_f(p['p50'], nd=2)} | {_f(p['p95'], nd=2)} | {_f(p['p99'], nd=2)} |")
    if miss:
        L.append(f"\nBarge-ins with no playback stop: {miss}.")
    if len(sessions) and min(len(xs) for xs in (va, bi)) < 3:
        L.append("\nFewer than 3 latency repetitions in at least one row: treat percentiles as indicative.")
    return L + [""]


class PairingError(ValueError):
    """The preregistered pair set is incomplete or has duplicate keys."""


def _pair_keys(ss: list[SessionScore]) -> tuple[dict[tuple, ChainOutcome], list[tuple]]:
    """(task, seed, chain label) -> primary chain; plus duplicate keys (over all chains)."""
    seen: dict[tuple, int] = defaultdict(int)
    for s in ss:
        for c in s.chains:
            seen[_key(c)] += 1
    keyed = {_key(c): c for s in ss for c in s.chains if c.in_primary}
    return keyed, sorted(k for k, n in seen.items() if n > 1)


def pair_problems(by_cond: dict[str, list[SessionScore]], a: str, b: str) -> dict[str, list]:
    """Duplicate pair keys (in either condition) and keys present in only one condition."""
    ca, da = _pair_keys(by_cond[a])
    cb, db = _pair_keys(by_cond[b])
    return {"duplicate": [(a, k) for k in da] + [(b, k) for k in db],
            "missing": [(b, k) for k in sorted(set(ca) - set(cb))] + [(a, k) for k in sorted(set(cb) - set(ca))]}


def _paired(by_cond: dict[str, list[SessionScore]], a: str, b: str, n_boot: int,
            conf: float = 0.95) -> dict | None:
    if a not in by_cond or b not in by_cond:
        return None
    ca, _ = _pair_keys(by_cond[a])
    cb, _ = _pair_keys(by_cond[b])
    keys = sorted(set(ca) & set(cb))
    if not keys:
        return None
    xa = [float(ca[k].success) for k in keys]
    xb = [float(cb[k].success) for k in keys]
    cl = [k[0] for k in keys]
    r = stats.cluster_bootstrap_diff(xa, xb, cl, n_boot=n_boot)
    if conf != 0.95:
        s = stats.cluster_bootstrap_diff(xa, xb, cl, n_boot=n_boot, conf=conf)
        r["slo"], r["shi"] = s["lo"], s["hi"]
    else:
        r["slo"], r["shi"] = r["lo"], r["hi"]
    r["n"] = len(keys)
    r["n_tasks"] = len(set(cl))
    r["unpaired"] = len(set(ca) ^ set(cb))
    return r


def _check_pairs(by_cond: dict[str, list[SessionScore]], pairs: Iterable[tuple[str, str]],
                 allow_incomplete: bool) -> dict[tuple[str, str], int]:
    """Raise PairingError on duplicate keys, and on missing pairs unless allowed; returns
    the number of missing keys per pair."""
    missing, errs = {}, []
    for a, b in pairs:
        if a not in by_cond or b not in by_cond:
            continue
        pr = pair_problems(by_cond, a, b)
        if pr["duplicate"]:
            errs.append(f"{a} - {b}: duplicate pair keys " + "; ".join(f"{c} {k}" for c, k in pr["duplicate"][:20]))
        if pr["missing"]:
            missing[(a, b)] = len(pr["missing"])
            if not allow_incomplete:
                errs.append(f"{a} - {b}: {len(pr['missing'])} (task, seed, chain) key(s) missing: "
                            + "; ".join(f"missing in {c}: {k}" for c, k in pr["missing"][:20]))
    if errs:
        raise PairingError("the preregistered pair set is not complete:\n  " + "\n  ".join(errs))
    return missing


def compare(
    by_cond: dict[str, list[SessionScore]],
    display: Iterable[tuple[str, str]] | None = None,
    n_boot: int = 4000,
    alpha: float = 0.05,
    allow_incomplete_pairs: bool = False,
) -> list[str]:
    """Preregistered families, Holm over the preregistered family size. ``display``
    (default: every family member present) only selects the rows shown; it never changes
    the family or the adjustment. Displayed pairs outside the families are exploratory.

    A primary decision needs the complete pair set: every (task, seed, chain label) in both
    conditions, no duplicate keys (``PairingError`` otherwise). With
    ``allow_incomplete_pairs`` an incomplete comparison is shown as EXPLORATORY, without p
    or decision. Below ``MIN_TASKS`` independent task clusters the p-value and decision are
    suppressed. Suppressed members count as p = 1 in Holm."""
    display = list(display) if display is not None else None
    fam_pairs = {p for fam in FAMILIES.values() for p in fam}
    extra = [tuple(p) for p in (display or []) if tuple(p) not in fam_pairs]
    missing = _check_pairs(by_cond, [*fam_pairs, *extra], allow_incomplete_pairs)
    L = ["## Paired comparisons (instruction-level success; cluster = task)", "",
         (f"Families are fixed before data collection; Holm is applied over the preregistered "
          f"family size (alpha = {alpha}); family members not run count as p = 1. "
          "The simultaneous CI is Bonferroni at 1 - alpha/m. A decision needs the complete pair "
          f"set and at least MIN_TASKS = {MIN_TASKS} independent task clusters (*proposed target*)."), ""]
    for name, fam in FAMILIES.items():
        m = len(fam)
        res = {p: _paired(by_cond, *p, n_boot=n_boot, conf=1 - alpha / m) for p in fam}

        def why_not(p: tuple[str, str], res: dict = res) -> str:
            r = res[p]
            if r is None:
                return "not tested"
            if p in missing:
                return f"EXPLORATORY: {missing[p]} pair key(s) missing"
            if r["n_tasks"] < MIN_TASKS:
                return f"no inference: {r['n_tasks']} < {MIN_TASKS} task clusters"
            return ""

        tested = [p for p in fam if not why_not(p)]
        adj = dict(zip(tested, stats.holm([res[p]["p_value"] for p in tested], alpha, m=m)["adjusted"]))
        shown = [p for p in fam if (display is None and res[p] is not None)
                 or (display is not None and p in display)]
        L += [f"**Family: {name}** (m = {m}; tested: {len(tested)})", "",
              ("| Comparison | paired chains | tasks | difference | 95% CI | simultaneous CI | bootstrap p "
               "| Holm-adjusted p | decision (Holm) |"),
              "|---|---|---|---|---|---|---|---|---|"]
        for a, b in shown:
            r, w = res[(a, b)], why_not((a, b))
            if r is None:
                L.append(f"| {a} - {b} | 0 | 0 | n/a | n/a | n/a | n/a | n/a | not tested |")
                continue
            if w:
                L.append(f"| {a} - {b} | {r['n']} | {r['n_tasks']} | {_f(r['estimate'], True)} | "
                         f"{_ci(r['lo'], r['hi'])} | {_ci(r['slo'], r['shi'])} | n/a | n/a | {w} |")
                continue
            p_adj = adj[(a, b)]
            dec = ("reject H0" + (" (A > B)" if r["estimate"] > 0 else " (A < B)")) if p_adj <= alpha \
                else "do not reject"
            L.append(f"| {a} - {b} | {r['n']} | {r['n_tasks']} | {_f(r['estimate'], True)} | "
                     f"{_ci(r['lo'], r['hi'])} | {_ci(r['slo'], r['shi'])} | {r['p_value']:.4f} | "
                     f"{p_adj:.4f} | {dec} |")
        L.append("")
    if extra:
        L += ["**Exploratory (not preregistered; unadjusted, no decision)**", "",
              "| Comparison | paired chains | tasks | difference | 95% CI | bootstrap p |", "|---|---|---|---|---|---|"]
        for a, b in extra:
            r = _paired(by_cond, a, b, n_boot=n_boot)
            if r is None:
                L.append(f"| {a} - {b} | 0 | 0 | n/a | n/a | n/a |")
                continue
            p = f"{r['p_value']:.4f}" if r["n_tasks"] >= MIN_TASKS else "n/a"
            L.append(f"| {a} - {b} | {r['n']} | {r['n_tasks']} | {_f(r['estimate'], True)} | "
                     f"{_ci(r['lo'], r['hi'])} | {p} |")
        L.append("")
    if missing:
        L.append("Incomplete pair sets (allowed explicitly; EXPLORATORY): "
                 + "; ".join(f"{a}-{b}: {n} missing" for (a, b), n in missing.items()))
    L.append("\nH1a target (*proposed target*, §8): A2 - A1 >= +10 pp with the paired CI excluding 0.")
    return L + [""]


def repair_comparison(by_cond: dict[str, list[SessionScore]], n_boot: int = 4000) -> list[str]:
    """RQ2: arms randomised per eligible failure point in the RQ2 conditions
    (``scoring.RQ2_CONDITIONS``); the unit is the failure point, clustered by task. Sessions
    failing the RQ2 audit (an eligible failure without an assignment, or an assignment
    without ``arm_drawn``) are excluded and listed."""
    L, flagged = [], []
    for cond, ss in sorted(by_cond.items()):
        if cond not in RQ2_CONDITIONS:
            continue
        bad = [s for s in ss if s.rq2_problems]
        flagged += [f"{s.session_id}: {p}" for s in bad for p in s.rq2_problems]
        allp = [(c.task_id, r) for s in ss if not s.rq2_problems for c in s.chains for r in c.repairs
                if r["arm_drawn"]]
        if bad:
            L.append(f"| {cond} | excluded: {len(bad)} session(s) failing the RQ2 audit | | | |")
        if {r["arm"] for _, r in allp} != {"forward_correction", "repeat"}:
            continue
        for name, keep in (("primary: withdrawal after assignment = failure", ("success", "failure", "withdrawn")),
                           ("sensitivity: withdrawn excluded", ("success", "failure"))):
            rep = [(t, r) for t, r in allp if r["status"] in keep]
            if not rep:
                continue
            r = stats.cluster_bootstrap_rate_diff(
                [float(x["status"] == "success") for _, x in rep],
                [x["arm"] == "forward_correction" for _, x in rep],
                [t for t, _ in rep],
                n_boot=n_boot,
            )
            L.append(f"| {cond} | {name} | {len(rep)} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} |")
        n_miss = sum(r["status"] == "insufficient_observation" for _, r in allp)
        if n_miss:
            L.append(f"| {cond} | flagged: target request not observed (excluded, rerun) | {n_miss} | | |")
    if not L:
        return []
    out = ["## RQ2 repair: forward correction - repeat (earliest eligible request)", "",
           ("Every randomised eligible failure point is analysed by its assigned arm, including "
            "those on chains later withdrawn or excluded from the chain-level analysis. Eligible "
            "failure point (preregistered): an online `not_complied` action verdict on an open chain "
            "whose earliest correctable request started before `observation_end`."), "",
           "| Condition | analysis | failure points | difference | 95% CI (task-clustered) |",
           "|---|---|---|---|---|", *L, ""]
    if flagged:
        out += ["RQ2 audit failures (sessions excluded from RQ2): " + "; ".join(flagged), ""]
    return out


def build_report(
    sessions: list[SessionScore],
    pairs: Sequence[tuple[str, str]] | None = None,
    title: str = "E2 evaluation report",
    n_boot: int = 4000,
    missing_rule: str = "rerun-required",
    allow_incomplete_pairs: bool = False,
) -> str:
    """``pairs`` selects displayed comparisons (None = all preregistered ones present).

    Raises ``IncompleteAdjudicationError`` for a primary report with adjudication gaps.
    ``missing_rule`` (preregistered handling of unobserved deadline windows):
    ``rerun-required`` (default) raises ``InsufficientObservationError`` while any chain is
    ``insufficient_observation``; ``worst-case`` counts them as failures and labels the
    whole report a SENSITIVITY analysis."""
    if missing_rule not in MISSING_RULES:
        raise ValueError(f"missing_rule must be one of {MISSING_RULES}")
    require_complete(sessions)
    diagnostic = any(s.diagnostic for s in sessions)
    n_imputed = 0
    if missing_rule == "worst-case":
        n_imputed = sum(c.outcome.value == "insufficient_observation" for s in sessions for c in s.chains)
        sessions = impute_worst_case(sessions)
    elif not diagnostic:
        require_observed(sessions)
    by_cond: dict[str, list[SessionScore]] = defaultdict(list)
    for s in sessions:
        by_cond[s.condition].append(s)
    L = []
    if diagnostic:
        srcs = sorted({x for s in sessions for x in s.sources})
        title = f"DIAGNOSTIC — {title}"
        L += [f"# {title}", "",
              (f"> **DIAGNOSTIC, NOT A RESULT.** Scored from verdict source(s) {srcs}, not from "
               "reconciled blinded adjudication (D-014). Chains without such verdicts count as "
               "never complied, speech onsets may be unverified scripted lines, and conditions "
               "without an online judge (A1) cannot be compared here."), ""]
    else:
        L += [f"# {title}", ""]
    if missing_rule == "worst-case":
        L += [(f"> **SENSITIVITY ANALYSIS (worst-case missing-data rule), not the primary result.** "
               f"{n_imputed} chain(s) whose deadline window was not observed are counted as failures."), ""]
    L += [("All values *measured locally* from the session logs below; thresholds are *proposed "
           "targets* (proposal v2.11 §8). Primary denominator = effective intent chains (final "
           "intent not withdrawn, capacity-skipped included), minus chains whose deadline window "
           "was not fully observed (counted, flagged for rerun). 'Cannot tell' counts as failure "
           "in the primary analysis."), ""]
    L += ["| Condition | sessions | effective chains | success | Wilson 95% CI | insufficient observation |",
          "|---|---|---|---|---|---|"]
    for cond, ss in sorted(by_cond.items()):
        sm = summarize([c for s in ss for c in s.chains])
        L.append(f"| {cond} | {len(ss)} | {sm['n_effective']} | {_f(sm['success_rate'], True)} | "
                 f"{_ci(*stats.wilson(sm['n_success'], sm['n_effective']))} | "
                 f"{sm['n_insufficient_observation']} |")
    L.append("")
    L += compare(by_cond, pairs, n_boot=n_boot, allow_incomplete_pairs=allow_incomplete_pairs)
    L += repair_comparison(by_cond, n_boot=n_boot)
    for cond, ss in sorted(by_cond.items()):
        L += condition_section(cond, ss, n_boot=n_boot)
    return "\n".join(L)


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--compare", action="append", default=None,
                    help="COND_A:COND_B (A - B): select displayed rows; does not change the "
                         "preregistered families or their Holm adjustment")
    ap.add_argument("--source", action="append", default=None, choices=("adjudicated", "human", "judge"),
                    help="verdict source preference (default: adjudicated only = primary). Any "
                         "other choice produces a DIAGNOSTIC report")
    ap.add_argument("--missing-rule", choices=MISSING_RULES, default="rerun-required",
                    help="unobserved deadline windows: rerun-required (default: refuse) or worst-case "
                         "(counted as failures; SENSITIVITY report)")
    ap.add_argument("--allow-incomplete-pairs", action="store_true",
                    help="show comparisons with missing (task, seed, chain) pairs as EXPLORATORY (no decision) "
                         "instead of refusing")
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args(argv)
    if args.source and tuple(args.source) != ("adjudicated",):
        cfg = ScoringConfig.diagnostic_config(tuple(args.source))
    else:
        cfg = ScoringConfig()
    scores = [score_session(load_session(p), cfg) for p in args.logs]
    pairs = [tuple(p.split(":", 1)) for p in args.compare] if args.compare else None
    try:
        md = build_report(scores, pairs, n_boot=args.n_boot, missing_rule=args.missing_rule,
                          allow_incomplete_pairs=args.allow_incomplete_pairs)
    except IncompleteAdjudicationError as e:
        print(f"error: {e}\n(use --source judge for a DIAGNOSTIC report)", file=sys.stderr)
        raise SystemExit(2) from e
    except PairingError as e:
        print(f"error: {e}\n(rerun the missing trials, or --allow-incomplete-pairs for an EXPLORATORY report)",
              file=sys.stderr)
        raise SystemExit(2) from e
    except InsufficientObservationError as e:
        print(f"error: {e}\n(rerun, or --missing-rule worst-case for a labelled SENSITIVITY report)",
              file=sys.stderr)
        raise SystemExit(2) from e
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md + "\n")
    else:
        print(md)


if __name__ == "__main__":
    main()
