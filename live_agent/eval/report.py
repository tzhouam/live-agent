"""Markdown report from scored E2 sessions, per condition, with CIs (proposal v2.11 §7.7).

Usage::

    python -m live_agent.eval.report logs/*.jsonl --compare A2:A1 --compare A2-QC:A2 -o report.md

Every number in the output is *measured locally* from the given logs; thresholds quoted
from §8 are *proposed targets*.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence

from live_agent.eval import stats
from live_agent.eval.schema import load_session
from live_agent.eval.scoring import (
    ChainOutcome,
    ScoringConfig,
    SessionScore,
    score_session,
    summarize,
)


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


def condition_section(cond: str, sessions: list[SessionScore], n_boot: int = 4000) -> list[str]:
    chains = [c for s in sessions for c in s.chains]
    eff = [c for c in chains if c.effective]
    sm = summarize(chains)
    cl = [c.task_id for c in eff]
    L = [f"## Condition `{cond}`", ""]
    L.append(
        f"Sessions: {len(sessions)}; tasks: {len({s.task_id for s in sessions})}; "
        f"effective chains: {sm['n_effective']}; withdrawn chains (excluded): {sm['n_withdrawn']}."
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
                        sum(bool(c.onset_ok) for c in content), len(content)))
    L.append(_rate_line("FCR (contradicted / completion claims)", sm["n_false_claims"], sm["n_claims"]))
    L.append(_rate_line("Claim coverage (chains with >= 1 claim)",
                        sum(c.n_claims > 0 for c in eff), len(eff)))
    for arm, r in sm["repair"].items():
        L.append(_rate_line(f"Repair rate, arm `{arm}` (RQ2)", r["k"], r["n"]))

    # by kind
    L += ["", "**Success by chain kind**", "", "| Kind | k/n | Estimate | Wilson 95% CI |", "|---|---|---|---|"]
    by_kind: dict[str, list[ChainOutcome]] = defaultdict(list)
    for c in eff:
        by_kind[c.kind].append(c)
    for k, cs in sorted(by_kind.items()):
        kk, nn = sum(c.success for c in cs), len(cs)
        L.append(f"| {k} | {kk}/{nn} | {_f(kk / nn, True)} | {_ci(*stats.wilson(kk, nn))} |")
    L += ["", "Outcome counts: " + ", ".join(f"{k}={v}" for k, v in sm["outcomes"].items() if v)]

    # repair offsets
    for arm, r in sm["repair"].items():
        L.append(f"Repair `{arm}`: earliest eligible request offset j-k = {r['offsets']}")

    # time-to-event
    L += ["", "**Time to event (Kaplan-Meier, right-censored at D)**", "",
          "| Measure | n | events | deadline success | KM median (s) | RMST to horizon (s) |",
          "|---|---|---|---|---|---|"]
    act = [c for c in eff if c.tvc is not None]
    if act:
        km = stats.kaplan_meier([c.tvc for c in act], [c.tvc_event for c in act])
        H = max(c.deadline_s for c in act)
        med = km.median
        L.append(f"| TVC (action chains) | {len(act)} | {sum(c.tvc_event for c in act)} | "
                 f"{_f(sum(c.tvc_event for c in act) / len(act), True)} | "
                 f"{_f(med) if med is not None else f'> {H:g}'} | {_f(km.rmst(H))} (H={H:g}) |")
    tf = [c for c in eff if c.tfmr is not None]
    if tf:
        km = stats.kaplan_meier([c.tfmr for c in tf], [c.tfmr_event for c in tf])
        H = max(c.tfmr for c in tf)
        med = km.median
        L.append(f"| TFMR (on-topic speech onset) | {len(tf)} | {sum(c.tfmr_event for c in tf)} | "
                 f"{_f(sum(c.tfmr_event for c in tf) / len(tf), True)} | "
                 f"{_f(med) if med is not None else f'> {H:g}'} | {_f(km.rmst(H))} (H={H:g}) |")

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


def compare(
    by_cond: dict[str, list[SessionScore]],
    pairs: Iterable[tuple[str, str]],
    n_boot: int = 4000,
    alpha: float = 0.05,
) -> list[str]:
    rows = []
    for a, b in pairs:
        if a not in by_cond or b not in by_cond:
            rows.append((a, b, None))
            continue
        ca = {_key(c): c for s in by_cond[a] for c in s.chains if c.effective}
        cb = {_key(c): c for s in by_cond[b] for c in s.chains if c.effective}
        keys = sorted(set(ca) & set(cb))
        if not keys:
            rows.append((a, b, None))
            continue
        r = stats.cluster_bootstrap_diff(
            [float(ca[k].success) for k in keys],
            [float(cb[k].success) for k in keys],
            [k[0] for k in keys],
            n_boot=n_boot,
        )
        r["n"] = len(keys)
        r["unpaired"] = len(set(ca) ^ set(cb))
        rows.append((a, b, r))
    valid = [r for _, _, r in rows if r is not None]
    adj = stats.holm([r["p_value"] for r in valid], alpha)["adjusted"] if valid else []
    L = ["## Paired comparisons (instruction-level success; cluster = task)", "",
         "| Comparison | paired chains | difference | 95% CI | bootstrap p | Holm-adjusted p |",
         "|---|---|---|---|---|---|"]
    i = 0
    for a, b, r in rows:
        if r is None:
            L.append(f"| {a} - {b} | 0 | n/a | n/a | n/a | n/a |")
            continue
        L.append(f"| {a} - {b} | {r['n']} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} | "
                 f"{r['p_value']:.4f} | {adj[i]:.4f} |")
        i += 1
    unp = [f"{a}-{b}: {r['unpaired']}" for a, b, r in rows if r and r["unpaired"]]
    if unp:
        L.append("\nChains present in only one condition (dropped from pairing): " + "; ".join(unp))
    L.append("\nH1a target (*proposed target*, §8): A2 - A1 >= +10 pp with the paired CI excluding 0.")
    return L + [""]


def repair_comparison(by_cond: dict[str, list[SessionScore]], n_boot: int = 4000) -> list[str]:
    L = []
    for cond, ss in by_cond.items():
        rep = [c for s in ss for c in s.chains if c.effective and c.repair_arm is not None]
        arms = {c.repair_arm for c in rep}
        if arms != {"forward_correction", "repeat"}:
            continue
        r = stats.cluster_bootstrap_rate_diff(
            [float(bool(c.repair_success)) for c in rep],
            [c.repair_arm == "forward_correction" for c in rep],
            [c.task_id for c in rep],
            n_boot=n_boot,
        )
        L.append(f"| {cond} | {len(rep)} | {_f(r['estimate'], True)} | {_ci(r['lo'], r['hi'])} |")
    if not L:
        return []
    return ["## RQ2 repair: forward correction - repeat (earliest eligible request)", "",
            "| Condition | assigned failure points | difference | 95% CI (task-clustered) |",
            "|---|---|---|---|", *L, ""]


def build_report(
    sessions: list[SessionScore],
    pairs: Sequence[tuple[str, str]] = (),
    title: str = "E2 evaluation report",
    n_boot: int = 4000,
) -> str:
    by_cond: dict[str, list[SessionScore]] = defaultdict(list)
    for s in sessions:
        by_cond[s.condition].append(s)
    L = [f"# {title}", "",
         "All values *measured locally* from the session logs below; thresholds are *proposed "
         "targets* (proposal v2.11 §8). Primary denominator = effective intent chains (final "
         "intent not withdrawn, capacity-skipped included). 'Cannot tell' counts as failure "
         "in the primary analysis.", ""]
    L += ["| Condition | sessions | effective chains | success | Wilson 95% CI |", "|---|---|---|---|---|"]
    for cond, ss in sorted(by_cond.items()):
        sm = summarize([c for s in ss for c in s.chains])
        L.append(f"| {cond} | {len(ss)} | {sm['n_effective']} | {_f(sm['success_rate'], True)} | "
                 f"{_ci(*stats.wilson(sm['n_success'], sm['n_effective']))} |")
    L.append("")
    if pairs:
        L += compare(by_cond, pairs, n_boot=n_boot)
    L += repair_comparison(by_cond, n_boot=n_boot)
    for cond, ss in sorted(by_cond.items()):
        L += condition_section(cond, ss, n_boot=n_boot)
    return "\n".join(L)


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--compare", action="append", default=[], help="COND_A:COND_B (A - B)")
    ap.add_argument("--source", action="append", default=None,
                    help="verdict source preference order (default adjudicated, human, judge)")
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args(argv)
    cfg = ScoringConfig(source_preference=tuple(args.source)) if args.source else ScoringConfig()
    scores = [score_session(load_session(p), cfg) for p in args.logs]
    pairs = [tuple(p.split(":", 1)) for p in args.compare]
    md = build_report(scores, pairs, n_boot=args.n_boot)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md + "\n")
    else:
        print(md)


if __name__ == "__main__":
    main()
