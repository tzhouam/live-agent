"""Tests for live_agent.eval: scoring rules (proposal v2.11 §7.2), statistics, task suite,
simulated user, report."""

from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest

from live_agent.eval import stats
from live_agent.eval.report import build_report
from live_agent.eval.schema import (
    SchemaError,
    SessionLogWriter,
    load_session,
    parse_session,
)
from live_agent.eval.scoring import (
    Outcome,
    ScoringConfig,
    build_chains,
    score_session,
    summarize,
)
from live_agent.eval.sim_user import SimulatedUser, VirtualClock
from live_agent.eval.tasks import load_suite, suite_counts

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "eval" / "tasks" / "e2_committed.jsonl"


# --------------------------------------------------------------------------- helpers


class Log:
    """Tiny builder for session logs."""

    def __init__(self, condition="A2", task_id="T1", seed=0, sid=None, sweep=True):
        self.recs = [{"type": "session", "session_id": sid or f"{condition}-{task_id}-{seed}",
                      "condition": condition, "task_id": task_id, "seed": seed}]
        if sweep:  # the session's recording was swept for audible completion claims
            self.recs.append({"type": "claim_sweep", "source": "adjudicated"})
        self.n = 0

    def utt(self, t_end, text="x", dur=1.0, barge_in=False):
        self.n += 1
        uid = f"u{self.n}"
        self.recs.append({"type": "utterance", "uid": uid, "speaker": "user", "text": text,
                          "t_start": t_end - dur, "t_end": t_end, "barge_in": barge_in})
        return uid

    def new(self, t_end, chain="c1", kind="action", **kw):
        uid = self.utt(t_end)
        self.recs.append({"type": "chain_annotation", "uid": uid, "action": "new",
                          "chain_id": chain, "label": chain, "kind": kind, **kw})
        return uid

    def revise(self, t_end, chain="c1", **kw):
        uid = self.utt(t_end)
        self.recs.append({"type": "chain_annotation", "uid": uid, "action": "revision",
                          "chain_id": chain, **kw})
        return uid

    def withdraw(self, t_end, chain="c1", barge_in=False):
        uid = self.utt(t_end, barge_in=barge_in)
        self.recs.append({"type": "chain_annotation", "uid": uid, "action": "withdrawal",
                          "chain_id": chain})
        return uid

    def verdict(self, t, label="complied", chain="c1", source="adjudicated", **kw):
        ev = {"type": "verdict", "chain_id": chain, "source": source, "label": label,
              "t_first_compliant": t, "t_evidence": t, **kw}
        if source == "adjudicated":
            ev.setdefault("onset_reviewed", True)  # content items: the onset was reviewed
        self.recs.append(ev)

    def onset(self, t, chain="c1", on_topic=True, source="adjudicated"):
        self.recs.append({"type": "speech_onset", "t": t, "on_topic": on_topic, "chain_id": chain,
                          "source": source})

    def aclaim(self, t, label="complied", chain="c1", **kw):
        """A completion claim found by the adjudicated audio sweep, with its claim verdict."""
        self.recs.append({"type": "completion_claim", "source": "adjudicated", "chain_id": chain, "t": t, **kw})
        self.recs.append({"type": "verdict", "source": "adjudicated", "chain_id": chain, "claim_t": t,
                          "label": label, **kw})

    def ev(self, **kw):
        self.recs.append(kw)

    def score(self, cfg=None):
        return score_session(parse_session(self.recs), cfg)

    def one(self, chain="c1", cfg=None):
        return next(c for c in self.score(cfg).chains if c.chain_id == chain)


# --------------------------------------------------------------------------- scoring


def test_action_success_and_deadline():
    L = Log()
    L.new(10.0)
    L.verdict(18.0)
    c = L.one()
    assert c.outcome == Outcome.SUCCESS and c.tvc == pytest.approx(8.0) and c.tvc_event
    L = Log()
    L.new(10.0)
    L.verdict(26.0)  # 16 s > 15 s
    c = L.one()
    assert c.outcome == Outcome.LATE and not c.success
    assert c.tvc == 15.0 and not c.tvc_event  # censored at D


def test_never_complied_is_censored_at_D():
    L = Log()
    L.new(0.0)
    L.verdict(5.0, label="not_complied")
    c = L.one()
    assert c.outcome == Outcome.NEVER
    assert c.time_to_success == 15.0 and not c.success_event
    assert c.tvc == 15.0 and not c.tvc_event


def test_revision_merges_into_same_chain_and_restarts_clock():
    L = Log()
    L.new(10.0, intent="挥手")
    L.revise(20.0, intent="用左手挥手")
    L.verdict(14.0)  # compliance with the old intent, before the revision: ignored
    L.verdict(33.0)  # 13 s after the revision: in time only because the clock restarted
    chains = build_chains(parse_session(L.recs))
    assert list(chains) == ["c1"] and chains["c1"].clock_origin == 20.0
    c = L.one()
    assert c.outcome == Outcome.SUCCESS and c.n_revisions == 1
    assert c.tvc == pytest.approx(13.0)
    s = summarize(L.score().chains)
    assert s["n_effective"] == 1  # scored once


def test_revision_verdict_version_filter():
    L = Log()
    L.new(0.0)
    L.revise(2.0)
    L.verdict(5.0, revision=0)  # judged against the superseded intent
    assert L.one().outcome == Outcome.UNADJUDICATED  # the final intent has no verdict
    L.verdict(6.0, revision=1)
    assert L.one().outcome == Outcome.SUCCESS


def test_revision_can_change_goal_kind():
    L = Log()
    L.new(0.0, kind="action")
    L.revise(4.0, kind="content", content_type="sing")
    L.onset(10.0)
    L.verdict(40.0)  # response end 36 s after revision <= 15 + 30
    c = L.one()
    assert c.kind == "content" and c.outcome == Outcome.SUCCESS and c.deadline_s == 45.0


def test_withdrawal_excluded_from_denominator():
    L = Log()
    L.new(0.0, chain="c1")
    L.withdraw(3.0, chain="c1")
    L.new(5.0, chain="c2")
    L.verdict(9.0, chain="c2")
    sc = L.score()
    s = summarize(sc.chains)
    assert s["n_withdrawn"] == 1 and s["n_effective"] == 1 and s["success_rate"] == 1.0
    assert next(c for c in sc.chains if c.chain_id == "c1").outcome == Outcome.WITHDRAWN


def test_revision_after_withdrawal_reopens():
    L = Log()
    L.new(0.0)
    L.withdraw(2.0)
    L.revise(4.0)
    L.verdict(6.0)
    assert L.one().outcome == Outcome.SUCCESS


def test_capacity_skip_counts_as_failure_in_denominator():
    L = Log()
    L.new(0.0, chain="c1")
    L.new(1.0, chain="c2")
    L.ev(type="capacity_skip", chain_id="c2", t=1.5)
    L.verdict(5.0, chain="c1")
    L.verdict(6.0, chain="c2")  # even if something compliant appears, skip = failure
    s = summarize(L.score().chains)
    assert s["n_effective"] == 2 and s["n_success"] == 1
    assert s["capacity_skip_rate"] == 0.5
    assert s["conditional_success_rate"] == 1.0  # among served chains


def test_refusal_and_degradation_fail():
    L = Log()
    L.new(0.0, chain="c1")
    L.new(0.0, chain="c2")
    L.ev(type="refusal", chain_id="c1", t=1.0, kind="refused")
    L.ev(type="refusal", chain_id="c2", t=1.0, kind="degraded")
    L.verdict(3.0, chain="c2")
    out = {c.chain_id: c.outcome for c in L.score().chains}
    assert out == {"c1": Outcome.REFUSED, "c2": Outcome.DEGRADED}
    assert summarize(L.score().chains)["refusal_degradation_rate"] == 1.0


def test_unknown_is_failure_with_sensitivity_exclusion():
    L = Log()
    L.new(0.0, chain="c1")
    L.verdict(5.0, chain="c1", label="unknown")
    L.new(0.0, chain="c2")
    L.verdict(5.0, chain="c2")
    s = summarize(L.score().chains)
    assert s["n_unknown"] == 1 and s["success_rate"] == 0.5
    assert s["success_rate_excl_unknown"] == 1.0


def test_content_requires_onset_and_completion_and_rubric():
    def run(onset, end, label="complied", ctype="explain"):
        L = Log()
        L.new(0.0, kind="content", content_type=ctype)
        if onset is not None:
            L.onset(onset)
        L.verdict(end, label=label)
        return L.one()

    assert run(8.0, 40.0).outcome == Outcome.SUCCESS  # 40 <= 15 + 30
    assert run(16.0, 40.0).outcome == Outcome.ONSET_FAIL  # onset late
    assert run(None, 40.0).outcome == Outcome.ONSET_FAIL
    assert run(8.0, 46.0).outcome == Outcome.LATE  # completion late
    assert run(8.0, 40.0, "not_complied").outcome == Outcome.RUBRIC_FAIL
    assert run(8.0, 24.0, ctype="qa").outcome == Outcome.SUCCESS  # 15 + 10
    assert run(8.0, 26.0, ctype="qa").outcome == Outcome.LATE
    c = run(16.0, 40.0)
    assert c.onset_ok is False and c.onset_s == 16.0


def test_off_topic_onset_does_not_count():
    L = Log()
    L.new(0.0, kind="content", content_type="qa")
    L.onset(3.0, on_topic=False)
    L.verdict(12.0)
    c = L.one()
    assert c.outcome == Outcome.ONSET_FAIL and c.tfmr == 15.0 and not c.tfmr_event


def test_prereg_duration_override():
    L = Log()
    L.new(0.0, kind="content", content_type="explain", prereg_duration_s=10.0)
    L.onset(5.0)
    L.verdict(30.0)
    assert L.one().outcome == Outcome.LATE


def test_multistep_ordering_and_per_step_deadline():
    def run(times, steps=3):
        L = Log()
        L.new(0.0, kind="multistep", steps=["a", "b", "c"][:steps])
        for i, t in times:
            L.verdict(t, step=i)
        return L.one()

    c = run([(0, 10.0), (1, 24.0), (2, 38.0)])  # each gap <= 15, total 38 > 15 but <= 45
    assert c.outcome == Outcome.SUCCESS and c.steps_complied == 3 and c.time_to_success == 38.0
    c = run([(0, 10.0), (1, 26.0), (2, 30.0)])  # step 1 16 s after step 0
    assert c.outcome == Outcome.LATE and c.steps_complied == 1
    c = run([(0, 10.0), (1, 5.0), (2, 20.0)])  # step 1 only before step 0: out of order
    assert c.outcome == Outcome.ORDER_FAIL and c.steps_complied == 1
    assert c.time_to_success == 45.0  # not a success by D = 3 x 15 (no early censoring)
    c = run([(0, 10.0)])
    assert c.outcome == Outcome.UNADJUDICATED  # step 1 not adjudicated
    L = Log()
    L.new(0.0, kind="multistep", steps=["a", "b", "c"])
    L.verdict(10.0, step=0)
    L.verdict(None, step=1, label="not_complied")  # reviewed, not done: no time needed
    c = L.one()
    assert c.outcome == Outcome.NEVER and c.steps_complied == 1 and c.time_to_success == 45.0


def test_source_preference():
    L = Log()
    L.new(0.0)
    L.verdict(5.0, source="judge")
    L.verdict(5.0, source="human", label="not_complied")
    cfg = ScoringConfig.diagnostic_config(("human", "judge"))
    assert L.one(cfg=cfg).outcome == Outcome.NEVER  # human beats judge
    assert L.one(cfg=ScoringConfig.diagnostic_config()).outcome == Outcome.SUCCESS
    assert L.one().outcome == Outcome.UNADJUDICATED  # primary: neither source counts


def test_chunk_lookup_for_compliance_time():
    L = Log()
    L.new(0.0)
    L.ev(type="chunk_presented", request=2, chunk=1, t_start=7.0, t_end=8.4)
    L.ev(type="verdict", chain_id="c1", source="adjudicated", label="complied",
         request=2, chunk=1, t_evidence=8.4, onset_reviewed=True)
    assert L.one().tvc == pytest.approx(7.0)


def test_fcr_and_claim_coverage():
    L = Log()
    for c, label in (("c1", "complied"), ("c2", "not_complied"), ("c3", "unknown")):
        L.new(0.0, chain=c)
        L.verdict(5.0, chain=c)
        L.aclaim(6.0, label, chain=c)  # primary: claims from the audio sweep, judged directly
    L.new(0.0, chain="c4")
    L.verdict(5.0, chain="c4")
    L.ev(type="completion_claim", chain_id="c4", t=6.0)  # logged only: diagnostic, not primary
    s = summarize(L.score().chains)
    assert s["n_claims"] == 3 and s["n_false_claims"] == 2  # unknown counts as false
    assert s["claim_coverage"] == 0.75


def test_fcr_diagnostic_logged_claims():
    L = Log()
    L.new(0.0, chain="c1")
    L.verdict(5.0, chain="c1")
    L.ev(type="completion_claim", chain_id="c1", t=6.0)  # supported
    L.new(0.0, chain="c2")
    L.verdict(7.0, chain="c2", label="not_complied")
    L.ev(type="completion_claim", chain_id="c2", t=6.0)  # contradicted
    L.new(0.0, chain="c3")
    L.verdict(9.0, chain="c3")
    L.ev(type="completion_claim", chain_id="c3", t=6.0)  # premature: contradicted
    L.new(0.0, chain="c4")
    L.verdict(20.0, chain="c4")
    L.ev(type="completion_claim", chain_id="c4", t=6.0, claim_id="k4")
    L.ev(type="verdict", claim_id="k4", source="adjudicated", label="complied")  # direct adjudication
    s = summarize(L.score(ScoringConfig.diagnostic_config(("adjudicated",))).chains)
    assert s["n_claims"] == 4 and s["n_false_claims"] == 2 and s["fcr"] == 0.5
    assert s["claim_coverage"] == 1.0


def test_repair_rate():
    L = Log()
    L.new(0.0)
    L.ev(type="repair_assignment", chain_id="c1", arm="forward_correction",
         failure_request=1, target_request=3)
    L.verdict(20.0, request=3)
    c = L.one()
    assert c.repairs[0]["success"] and c.repairs[0]["offset"] == 2
    L2 = Log()
    L2.new(0.0)
    L2.ev(type="repair_assignment", chain_id="c1", arm="repeat", failure_request=1, target_request=3)
    L2.verdict(25.0, request=4)
    assert L2.one().repairs[0]["success"] is False


def test_latencies():
    L = Log()
    uid = L.new(10.0)
    L.ev(type="visual_ack", t=10.4, uid=uid)
    b = L.withdraw(20.0, barge_in=True)  # t_start = 19.0
    L.ev(type="visual_ack", t=19.3, uid=b)
    L.ev(type="playback_stop", t=19.2)
    sc = L.score()
    assert sc.visual_ack_s == pytest.approx([0.4, 0.3])
    assert sc.barge_in_stop_s == pytest.approx([0.2])


def test_schema_rejects_bad_events():
    with pytest.raises(SchemaError):
        parse_session([{"type": "utterance", "uid": "u"}])
    with pytest.raises(SchemaError):
        parse_session([{"type": "session", "session_id": "s", "condition": "A", "task_id": "t",
                        "seed": 0}, {"type": "verdict", "source": "judge", "label": "maybe",
                                     "chain_id": "c"}])


def test_writer_roundtrip(tmp_path):
    p = tmp_path / "s.jsonl"
    with SessionLogWriter(p, session_id="s", condition="A2", task_id="T", seed=1) as w:
        w.write({"type": "utterance", "uid": "u1", "speaker": "user", "text": "喝茶",
                 "t_start": 0.0, "t_end": 1.0})
        w.write({"type": "chain_annotation", "uid": "u1", "action": "new", "chain_id": "c",
                 "kind": "action"})
        w.write({"type": "verdict", "chain_id": "c", "source": "adjudicated", "label": "complied",
                 "t_evidence": 5.0, "onset_reviewed": True})
    s = load_session(p)
    assert "喝茶" in p.read_text(encoding="utf-8")
    assert score_session(s).chains[0].success


# --------------------------------------------------------------------------- stats


def test_clopper_pearson_known_values():
    assert stats.clopper_pearson_upper(0, 300) == pytest.approx(0.00994, abs=5e-5)
    assert stats.clopper_pearson_upper(0, 300) == pytest.approx(1 - 0.05 ** (1 / 300), rel=1e-9)
    lo, hi = stats.clopper_pearson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(1 - 0.025 ** 0.1, rel=1e-9)  # 0.3085
    lo, hi = stats.clopper_pearson(5, 10)
    assert lo == pytest.approx(0.187086, abs=1e-5) and hi == pytest.approx(0.812914, abs=1e-5)


def test_wilson_known_values():
    lo, hi = stats.wilson(5, 10)
    assert lo == pytest.approx(0.236593, abs=1e-5) and hi == pytest.approx(0.763407, abs=1e-5)
    lo, hi = stats.wilson(0, 300)
    assert lo == 0.0 and hi == pytest.approx(0.012643, abs=1e-5)
    assert stats.wilson_upper(0, 300) < hi


def test_kaplan_meier_toy():
    km = stats.kaplan_meier([1, 2, 2, 3, 4, 5], [1, 1, 0, 1, 0, 1])
    assert km.times.tolist() == [1, 2, 3, 5]
    assert km.survival == pytest.approx([5 / 6, 2 / 3, 4 / 9, 0.0])
    assert km.at_risk.tolist() == [6, 5, 3, 1]
    assert km.median == 3.0
    assert km.rmst(5.0) == pytest.approx(1 + 5 / 6 + 2 / 3 + 2 * 4 / 9)
    assert km.s_at(0.5) == 1.0 and km.s_at(4.0) == pytest.approx(4 / 9)
    # Greenwood at t=1: S^2 * d/(n(n-d)) = (25/36) * 1/30
    assert km.greenwood_var[0] == pytest.approx(25 / 36 / 30)


def test_kaplan_meier_all_censored_median_not_reached():
    km = stats.kaplan_meier([15, 15, 15, 3], [0, 0, 0, 1])
    assert km.median is None and km.s_at(10) == pytest.approx(0.75)


def test_cohens_kappa_example():
    # 2x2 table [[20, 5], [10, 15]]: po = .7, pe = .5, kappa = .4
    r1 = ["y"] * 25 + ["n"] * 25
    r2 = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert stats.cohens_kappa(r1, r2) == pytest.approx(0.4)
    assert stats.cohens_kappa(["a", "b"], ["a", "b"]) == 1.0


def test_holm():
    r = stats.holm([0.01, 0.04, 0.03, 0.005])
    assert r["adjusted"] == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert r["reject"] == [True, False, False, True]


def test_cluster_bootstrap_diff_and_noninferiority():
    rng = np.random.default_rng(1)
    tasks = np.repeat(np.arange(40), 5)
    a = (rng.random(200) < 0.8).astype(float)
    b = (rng.random(200) < 0.5).astype(float)
    r = stats.cluster_bootstrap_diff(a, b, tasks, n_boot=2000)
    assert r["lo"] < r["estimate"] < r["hi"] and r["lo"] > 0 and r["p_value"] < 0.01
    same = stats.cluster_bootstrap_diff(a, a, tasks, n_boot=500)
    assert same["estimate"] == 0 and same["lo"] == 0 and same["hi"] == 0
    ni = stats.noninferiority(a, a - 0.0, tasks, margin=0.05)
    assert ni["noninferior"]
    ni = stats.noninferiority(b, a, tasks, margin=0.05)
    assert not ni["noninferior"]


def test_cluster_bootstrap_mean_single_cluster_width_zero():
    r = stats.cluster_bootstrap_mean([1, 0, 1, 1], ["t"] * 4, n_boot=200)
    assert r["estimate"] == 0.75 and r["lo"] == r["hi"] == 0.75


def test_power_simulation_sanity():
    null = stats.simulate_power(0.5, 0.0, icc=0.1, n_tasks=30, n_seeds=5, n_sims=3000, rng=0)
    assert null["power"] < 0.08  # ~ alpha
    big = stats.simulate_power(0.4, 0.3, icc=0.1, n_tasks=40, n_seeds=5, n_sims=1000, rng=0)
    assert big["power"] > 0.95
    small = stats.simulate_power(0.5, 0.1, icc=0.2, n_tasks=20, n_seeds=5, n_sims=2000, rng=0)
    more = stats.simulate_power(0.5, 0.1, icc=0.2, n_tasks=80, n_seeds=5, n_sims=2000, rng=0)
    assert more["power"] > small["power"] + 0.1
    holm3 = stats.simulate_power(0.5, 0.1, icc=0.2, n_tasks=80, n_seeds=5, n_sims=2000, rng=0,
                                 n_comparisons=3)
    assert holm3["power"] < more["power"]
    m = stats.min_tasks_for_power(0.8, baseline=0.5, effect=0.1, icc=0.1, n_seeds=5,
                                  n_sims=500, rng=0)
    assert m["n_tasks"] is not None and m["curve"][m["n_tasks"]] >= 0.8


def test_marginal_calibration():
    s = stats._latent_sigma(0.3)
    b = stats._intercept_for_marginal(0.7, s)
    z = np.random.default_rng(0).normal(size=200_000)
    assert np.mean(1 / (1 + np.exp(-(b + s * z)))) == pytest.approx(0.7, abs=3e-3)


# --------------------------------------------------------------------------- tasks, sim user, report


def test_committed_suite_loads():
    tasks = load_suite(SUITE)
    assert len(tasks) == 30
    cats = suite_counts(tasks)
    assert all(v["current"] >= 1 for v in cats.values())
    assert all(t.persona == "hanfu_scholar_study" for t in tasks)
    finals = [i for t in tasks for i in t.final_intents().values()]
    assert any(i is None for i in finals)  # at least one withdrawn chain in the suite
    assert any(u.barge_in for t in tasks for u in t.utterances)


def test_sim_user_emits_annotations_and_scores():
    tasks = {t.task_id: t for t in load_suite(SUITE)}
    task = tasks["E2-D04"]  # withdrawal then a new chain
    clock = VirtualClock()
    sent = []

    async def send(text, meta):
        sent.append((clock.now(), text))
        await clock.sleep(1.0)  # TTS playout

    user = SimulatedUser(task, send, clock.now, clock.sleep, session_id="s1")
    events = asyncio.run(user.run())
    assert [round(t, 3) for t, _ in sent] == [2.0, 5.0, 9.0]
    anns = [e for e in events if e["type"] == "chain_annotation"]
    assert [a["action"] for a in anns] == ["new", "withdrawal", "new"]
    assert anns[2]["chain_id"] == "s1:c2" and anns[2]["label"] == "c2"
    assert clock.now() == pytest.approx(task.duration_s)
    recs = [{"type": "session", "session_id": "s1", "condition": "A2", "task_id": task.task_id,
             "seed": 0}, *events,
            {"type": "verdict", "chain_id": "s1:c2", "source": "adjudicated", "label": "complied",
             "t_evidence": 16.0, "onset_reviewed": True}]
    sc = score_session(parse_session(recs))
    s = summarize(sc.chains)
    assert s["n_withdrawn"] == 1 and s["n_effective"] == 1 and s["n_success"] == 1


def test_report_end_to_end(tmp_path):
    scores = []
    rng = np.random.default_rng(0)
    for cond, p in (("A1", 0.4), ("A2", 0.8)):
        for task in range(12):
            for seed in range(3):
                L = Log(cond, f"T{task}", seed)
                L.new(0.0)
                if rng.random() < p:
                    L.verdict(float(rng.uniform(3, 14)))
                else:
                    L.verdict(None, label="not_complied")  # reviewed, never done: no time
                L.ev(type="completion_claim", chain_id="c1", t=14.5)
                scores.append(L.score())
    md = build_report(scores, pairs=[("A2", "A1")], n_boot=500)
    assert "## Paired comparisons" in md and "| A2 - A1 | 36 |" in md
    assert "TVC (action chains)" in md and "FCR" in md
    assert "nan" not in md.lower().replace("n/a", "")
