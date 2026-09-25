"""Tests for the impl2 Codex review fixes in the evaluation harness (findings 1-7, 9, 11):
adjudication-only primary outcome, dual rating + arbitration, frozen criteria, revision
binding, claims, capacity skips, observation windows, preregistered Holm families, key
placement and label validation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from test_eval import Log

from live_agent.eval import report, stats
from live_agent.eval.adjudicate import (
    LabelError,
    default_key_path,
    merge,
    prepare,
    presented_segments,
    video_to_session,
)
from live_agent.eval.report import build_report, compare
from live_agent.eval.schema import SchemaError, load_session, parse_session
from live_agent.eval.scoring import (
    IncompleteAdjudicationError,
    Outcome,
    ScoringConfig,
    score_session,
    summarize,
)

DIAG = ScoringConfig.diagnostic_config()


# --------------------------------------------------------------------------- finding 1


def test_primary_requires_adjudication_and_ignores_judge():
    L = Log()
    L.new(0.0)
    L.verdict(5.0, source="judge", revision=0)
    c = L.one()
    assert c.outcome == Outcome.UNADJUDICATED and not c.in_primary
    with pytest.raises(IncompleteAdjudicationError, match="no adjudicated verdict"):
        build_report([L.score()], n_boot=50)
    # judge-only scoring is an explicitly labelled diagnostic
    assert L.one(cfg=DIAG).outcome == Outcome.SUCCESS
    md = build_report([L.score(DIAG)], n_boot=50)
    assert md.startswith("# DIAGNOSTIC") and "NOT A RESULT" in md


def test_non_adjudicated_sources_must_be_declared_diagnostic():
    with pytest.raises(ValueError, match="diagnostic"):
        ScoringConfig(source_preference=("adjudicated", "judge"))
    with pytest.raises(ValueError, match="diagnostic"):
        ScoringConfig(onset_sources=("script",))


def test_incomplete_a2_vs_a1_batch_is_rejected_not_biased():
    """A2 has judge verdicts, A1 has none: without full adjudication nothing is reported."""
    ss = []
    for cond in ("A1", "A2"):
        L = Log(cond, "T1", 0)
        L.new(0.0)
        if cond == "A2":
            L.verdict(5.0, source="judge", revision=0)
        else:
            L.verdict(5.0)  # A1 adjudicated
        ss.append(L.score())
    with pytest.raises(IncompleteAdjudicationError):
        build_report(ss, n_boot=50)


def _write_log(path: Path, recs: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    return path


def test_report_cli_primary_exit_and_diagnostic(tmp_path, capsys):
    L = Log("A2", "T1", 0)
    L.new(0.0)
    L.verdict(5.0, source="judge", revision=0)
    p = _write_log(tmp_path / "a.jsonl", L.recs)
    with pytest.raises(SystemExit) as e:
        report.main([str(p)])
    assert e.value.code == 2 and "adjudication gap" in capsys.readouterr().err
    out = tmp_path / "diag.md"
    report.main([str(p), "--source", "judge", "-o", str(out)])
    assert "DIAGNOSTIC" in out.read_text(encoding="utf-8").splitlines()[0]


# --------------------------------------------------------------------------- finding 2 (scoring side)


def test_negative_labels_without_time_are_scored():
    L = Log()
    L.new(0.0)
    L.verdict(None, label="not_complied", t_review_start=0.0, t_review_end=20.0)
    assert L.one().outcome == Outcome.NEVER
    L = Log()
    L.new(0.0)
    L.verdict(None, label="unknown")
    assert L.one().outcome == Outcome.UNKNOWN
    L = Log()
    L.new(0.0, kind="content", content_type="qa")
    L.onset(4.0)
    L.verdict(None, label="not_complied")
    assert L.one().outcome == Outcome.RUBRIC_FAIL


def test_complied_without_time_is_an_error():
    L = Log()
    L.new(0.0)
    L.verdict(None)
    with pytest.raises(ValueError, match="compliance time"):
        L.score()


# --------------------------------------------------------------------------- finding 3 (scoring side)


def test_script_onsets_do_not_pass_the_content_gate_in_primary():
    L = Log()
    L.new(0.0, kind="content", content_type="qa")
    L.onset(3.0, on_topic=None, source="script")  # runner: scripted line, not verified
    L.verdict(12.0)  # adjudicated rubric pass, onset reviewed and none found
    assert L.one().outcome == Outcome.ONSET_FAIL
    L.onset(4.0, on_topic=True, source="script")  # legacy fabricated flag: still not accepted
    assert L.one().outcome == Outcome.ONSET_FAIL
    # diagnostic mode accepts scripted onsets as unverified
    L2 = Log()
    L2.new(0.0, kind="content", content_type="qa")
    L2.onset(3.0, on_topic=None, source="script")
    L2.verdict(12.0, source="judge", revision=0)
    assert L2.one(cfg=DIAG).outcome == Outcome.SUCCESS


def test_content_needs_onset_adjudication():
    L = Log()
    L.new(0.0, kind="content", content_type="qa")
    L.verdict(12.0, onset_reviewed=False)
    c = L.one()
    assert c.outcome == Outcome.UNADJUDICATED and "onset" in c.missing
    L.onset(5.0)  # adjudicated onset
    assert L.one().outcome == Outcome.SUCCESS


def test_schema_speech_onset_and_mode():
    head = {"type": "session", "session_id": "s", "condition": "A2", "task_id": "t", "seed": 0}
    parse_session([head, {"type": "speech_onset", "t": 1.0, "on_topic": None, "source": "script"}])
    with pytest.raises(SchemaError):
        parse_session([head, {"type": "speech_onset", "t": 1.0, "on_topic": True, "source": "llm"}])
    parse_session([dict(head, mode="generator_path", generator_seed=3)])
    with pytest.raises(SchemaError):
        parse_session([dict(head, mode="realtime")])
    parse_session([head, {"type": "observation_end", "t": 30.0},
                   {"type": "capacity_skip", "chain_id": "c", "t": 1.0, "revision": 0}])


# --------------------------------------------------------------------------- finding 4


def test_verdict_revision_binding():
    L = Log()
    L.new(0.0, intent="喝茶")
    L.revise(5.0, intent="放下杯子")
    L.verdict(8.0, source="judge", revision=0)  # tea request presented after the revision
    L.verdict(9.0, source="judge")  # no revision: unbound
    assert L.one(cfg=DIAG).outcome == Outcome.SUCCESS  # diagnostic only: unbound judge accepted
    L2 = Log()
    L2.new(0.0, intent="喝茶")
    L2.revise(5.0, intent="放下杯子")
    L2.verdict(8.0, source="judge", revision=0)
    assert L2.one(cfg=DIAG).outcome == Outcome.NEVER  # bound to the superseded intent
    L2.verdict(10.0, revision=1)
    assert L2.one().outcome == Outcome.SUCCESS and L2.one().tvc == pytest.approx(5.0)


# --------------------------------------------------------------------------- finding 5


def test_claims_on_withdrawn_chains_count_in_fcr():
    L = Log()
    L.new(0.0, chain="c1")
    L.withdraw(4.0, chain="c1")
    L.ev(type="completion_claim", chain_id="c1", t=6.0)  # claimed after the user withdrew
    L.new(8.0, chain="c2")
    L.verdict(10.0, chain="c2")
    sc = L.score()
    c1 = next(c for c in sc.chains if c.chain_id == "c1")
    assert c1.outcome == Outcome.WITHDRAWN and c1.n_claims == 1 and c1.n_claims_unadjudicated == 1
    with pytest.raises(IncompleteAdjudicationError, match="claim-level"):
        build_report([sc], n_boot=50)
    # claim-level adjudication (chain_id + claim_t): not done at claim time -> false
    L.ev(type="verdict", chain_id="c1", claim_t=6.0, source="adjudicated", label="not_complied")
    s = summarize(L.score().chains)
    assert s["n_claims"] == 1 and s["n_false_claims"] == 1 and s["fcr"] == 1.0
    # diagnostic: no complied verdict before the claim -> false
    assert summarize(L.score(DIAG).chains)["n_false_claims"] == 1


def test_claim_before_revision_needs_claim_level_adjudication():
    L = Log()
    L.new(0.0)
    L.ev(type="completion_claim", chain_id="c1", t=3.0)  # about the first intent
    L.revise(5.0)
    L.verdict(8.0)  # final intent done
    c = L.one()
    assert c.outcome == Outcome.SUCCESS and c.n_claims_unadjudicated == 1
    L.ev(type="verdict", chain_id="c1", claim_t=3.0, source="adjudicated", label="complied")
    c = L.one()
    assert c.n_claims == 1 and c.n_false_claims == 0 and c.n_claims_unadjudicated == 0


def test_claims_matched_to_steps():
    L = Log()
    L.new(0.0, kind="multistep", steps=["a", "b"])
    L.verdict(5.0, step=0)
    L.verdict(12.0, step=1)
    L.ev(type="completion_claim", chain_id="c1", t=6.0, step=0)  # true
    L.ev(type="completion_claim", chain_id="c1", t=7.0, step=1)  # false: step 1 only at 12
    L.ev(type="completion_claim", chain_id="c1", t=8.0)  # whole task: false (step 1 missing)
    L.ev(type="completion_claim", chain_id="c1", t=13.0)  # whole task: true
    c = L.one()
    assert c.n_claims == 4 and c.n_false_claims == 2


# --------------------------------------------------------------------------- finding 6


def test_capacity_skip_bound_to_revision_and_precedes_verdicts():
    L = Log()
    L.new(0.0)
    L.ev(type="capacity_skip", chain_id="c1", t=6.0, revision=0)  # after the revision in time...
    L.revise(5.0)
    L.verdict(8.0, revision=1)
    assert L.one().outcome == Outcome.SUCCESS  # ...but it skipped the superseded intent
    L.ev(type="capacity_skip", chain_id="c1", t=7.0, revision=1)
    c = L.one()
    assert c.outcome == Outcome.CAPACITY_SKIPPED and c.in_primary and not c.served


# --------------------------------------------------------------------------- finding 7


def test_insufficient_observation_is_excluded_and_flagged():
    L = Log()
    L.new(0.0, chain="c1")
    L.verdict(None, chain="c1", label="not_complied")
    L.new(0.0, chain="c2")
    L.verdict(4.0, chain="c2")  # success observed before the recording ended
    L.ev(type="observation_end", t=10.0)  # window of c1 needs 15 s
    sc = L.score()
    out = {c.chain_id: c for c in sc.chains}
    assert out["c1"].outcome == Outcome.INSUFFICIENT_OBSERVATION and not out["c1"].in_primary
    assert out["c2"].outcome == Outcome.SUCCESS
    s = summarize(sc.chains)
    assert s["n_effective"] == 1 and s["n_insufficient_observation"] == 1 and s["success_rate"] == 1.0
    md = build_report([sc], n_boot=50)
    assert "Flagged for rerun" in md and "insufficient observation (excluded, rerun): 1" in md
    L.ev(type="observation_end", t=20.0)
    assert L.one("c1").outcome == Outcome.NEVER


def test_observation_end_falls_back_to_last_presented_chunk():
    L = Log()
    L.new(0.0)
    L.verdict(None, label="not_complied")
    L.ev(type="chunk_presented", request=0, chunk=0, t_start=0.0, t_end=12.0)
    assert L.one().outcome == Outcome.INSUFFICIENT_OBSERVATION


def test_order_fail_is_a_competing_failure_not_censoring():
    L = Log()
    L.new(0.0, kind="multistep", steps=["a", "b"])
    L.verdict(10.0, step=0)
    L.verdict(5.0, step=1)
    L.ev(type="observation_end", t=12.0)  # deterministic: no observation needed
    c = L.one()
    assert c.outcome == Outcome.ORDER_FAIL and c.competing_failure and c.in_primary
    md = build_report([L.score()], n_boot=50)
    assert "order_fail" in md and "competing failure" in md


# --------------------------------------------------------------------------- finding 9


def test_holm_uses_preregistered_family_size():
    r = stats.holm([0.01], m=4)
    assert r["adjusted"] == pytest.approx([0.04])
    r = stats.holm([0.01, 0.02], m=4)
    assert r["adjusted"] == pytest.approx([0.04, 0.06])
    with pytest.raises(ValueError):
        stats.holm([0.1, 0.2], m=1)


def _sessions(conds_p, n_tasks=12, n_seeds=3, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for cond, p in conds_p:
        for t in range(n_tasks):
            for s in range(n_seeds):
                L = Log(cond, f"T{t}", s)
                L.new(0.0)
                if rng.random() < p:
                    L.verdict(float(rng.uniform(3, 14)))
                    L.ev(type="completion_claim", chain_id="c1", t=14.5)
                else:
                    L.verdict(None, label="not_complied")
                    if rng.random() < 0.5:
                        L.ev(type="completion_claim", chain_id="c1", t=14.5)
                out.append(L.score())
    return out


def test_families_are_fixed_and_compare_only_selects_display():
    ss = _sessions((("A1", 0.4), ("A2", 0.8), ("A2-noqc", 0.5)))
    by = {}
    for s in ss:
        by.setdefault(s.condition, []).append(s)
    md = "\n".join(compare(by, n_boot=300))
    assert "Family: primary (H1a)** (m = 1; tested: 1)" in md
    assert "Family: secondary (H1c ablations)** (m = 4; tested: 1)" in md
    row = next(x for x in md.splitlines() if x.startswith("| A2 - A2-noqc |"))
    cells = [c.strip() for c in row.strip("|").split("|")]
    p, p_adj = float(cells[5]), float(cells[6])
    assert p_adj == pytest.approx(min(1.0, 4 * p))  # family size 4 even though 1 was run
    assert "reject H0" in "\n".join(x for x in md.splitlines() if x.startswith("| A2 - A1 |"))
    # display selection: hides rows, never changes the adjustment; extra pairs are exploratory
    md2 = "\n".join(compare(by, display=[("A2", "A2-noqc"), ("A2-noqc", "A1")], n_boot=300))
    assert "| A2 - A1 |" not in md2 and row in md2
    assert "Exploratory (not preregistered" in md2 and "| A2-noqc - A1 |" in md2


def test_fcr_and_claim_coverage_get_task_clustered_cis():
    md = build_report(_sessions((("A2", 0.7),)), n_boot=300)
    fcr = next(x for x in md.splitlines() if x.startswith("| FCR"))
    cov = next(x for x in md.splitlines() if x.startswith("| Claim coverage"))
    assert fcr.rstrip("|").split("|")[-1].strip() != "n/a"
    assert cov.rstrip("|").split("|")[-1].strip() != "n/a"


def test_repair_per_failure_point():
    L = Log("A2-rq2", "T1", 0)
    L.new(0.0)
    L.ev(type="chunk_presented", request=3, chunk=0, t_start=18.0, t_end=23.0)
    L.ev(type="observation_end", t=40.0)
    L.ev(type="repair_assignment", chain_id="c1", arm="forward_correction", failure_request=1, target_request=3)
    L.ev(type="repair_assignment", chain_id="c1", arm="repeat", failure_request=2, target_request=4)
    L.verdict(19.0)  # adjudicated: no request field -> mapped through the presented chunk
    c = L.one()
    assert [r["arm"] for r in c.repairs] == ["forward_correction", "repeat"]
    assert [r["success"] for r in c.repairs] == [True, False]
    s = summarize([c])["repair"]
    assert s["forward_correction"]["k"] == 1 and s["repeat"]["n"] == 1


# --------------------------------------------------------------------------- adjudication tool (2, 3, 11)


def _session_file(tmp_path: Path, name: str, task_id: str, utts: list[tuple], extra=(), cond="A2",
                  length=40.0) -> Path:
    """utts: (t_end, text, action, label, ann_extra). Chunks of 1 s, presented back to back
    from t=0 (video time == session time), recorded length ``length``."""
    sid = f"{cond}-{task_id}-s0"
    recs = [{"type": "session", "session_id": sid, "condition": cond, "task_id": task_id, "seed": 0,
             "mode": "simulation"}]
    for i, (t_end, text, action, label, ann) in enumerate(utts):
        uid = f"{sid}:u{i}"
        recs.append({"type": "utterance", "uid": uid, "speaker": "user", "text": text,
                     "t_start": t_end - 1.0, "t_end": t_end})
        recs.append({"type": "chain_annotation", "uid": uid, "action": action, "chain_id": f"{sid}:{label}",
                     "label": label, **ann})
    for k in range(int(length)):
        recs.append({"type": "chunk_presented", "request": k // 5, "chunk": k % 5,
                     "t_start": float(k), "t_end": float(k + 1)})
    recs.append({"type": "observation_end", "t": length})
    recs += list(extra)
    p = _write_log(tmp_path / f"{name}.jsonl", recs)
    p.with_suffix(".mp4").write_bytes(b"\0")
    return p


def _items(page: Path) -> list[dict]:
    return json.loads(page.read_text(encoding="utf-8").split("const ITEMS = ")[1].split(";\n")[0])


def _labels(tmp_path: Path, name: str, d: dict) -> Path:
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def test_key_outside_batch_and_blinding(tmp_path):
    log = _session_file(tmp_path, "A2-E2-A01-s0", "E2-A01", [(3.0, "请喝口茶吧。", "new", "c1",
                                                              {"kind": "action", "intent": "端起茶杯喝一口茶"})])
    batch = tmp_path / "adj" / "b1"
    page = prepare([log], batch)
    key = default_key_path(batch)
    assert key.exists() and batch.resolve() not in key.resolve().parents
    assert not list(batch.rglob("key*"))
    for f in batch.rglob("*"):
        assert "A2" not in f.name and "E2-A01" not in f.name
    text = page.read_text(encoding="utf-8")
    assert "E2-A01" not in text and '"A2' not in text
    with pytest.raises(ValueError, match="must not be inside"):
        prepare([log], batch, key_path=batch / "sub" / "key.json")


def test_items_carry_frozen_criteria(tmp_path):
    logs = [
        _session_file(tmp_path, "x1", "E2-A01", [(3.0, "请喝口茶吧。", "new", "c1", {"kind": "action"})]),
        _session_file(tmp_path, "x2", "E2-C04", [(3.0, "给我讲讲CUDA是什么吧。", "new", "c1",
                                                  {"kind": "content", "content_type": "explain"})]),
        _session_file(tmp_path, "x3", "E2-M02", [(3.0, "先站起来，挥挥手，再坐回去。", "new", "c1",
                                                  {"kind": "multistep", "steps": ["站起来", "挥手", "坐下"]})]),
    ]
    items = {it["kind"]: it for it in _items(prepare(logs, tmp_path / "b"))}
    assert items["action"]["criteria"]["checks"] == ["人物端起茶杯", "茶杯送到嘴边并作饮用动作"]
    c = items["content"]["criteria"]
    assert c["rubric"]["k"] == 3 and len(c["rubric"]["key_points"]) == 3 and c["duration_s"] == 30.0
    m = items["multistep"]
    assert m["n_steps"] == 3 and [s["checks"] for s in m["criteria"]["steps"]][2] == ["人物由站姿回到坐姿"]
    # a chain without preregistered criteria cannot be put in front of annotators
    bad = _session_file(tmp_path, "x4", "T-unknown", [(3.0, "x", "new", "c1", {"kind": "action"})])
    with pytest.raises(ValueError, match="no preregistered criteria"):
        prepare([bad], tmp_path / "b2")


def _one_item(tmp_path, task_id="E2-A01", utts=None, extra=(), name="s"):
    utts = utts or [(3.0, "请喝口茶吧。", "new", "c1", {"kind": "action"})]
    log = _session_file(tmp_path, name, task_id, utts, extra)
    batch = tmp_path / f"batch-{name}"
    items = _items(prepare([log], batch))
    return log, batch, items


def test_merge_agreement_disagreement_arbitration(tmp_path):
    log, batch, items = _one_item(tmp_path)
    iid = items[0]["id"]
    a = _labels(tmp_path, "a", {f"{iid}/0": {"label": "complied", "v_first": 8.0, "v_seen": 20.0}})
    b = _labels(tmp_path, "b", {f"{iid}/0": {"label": "not_complied", "v_seen": 25.0}})
    r = merge(batch, [(a, "R1"), (b, "R2")])
    assert r["unresolved"] == [f"{iid}/0"] and r["agreed"] == 0
    s = load_session(log)
    assert len(s.of_type("rating")) == 2 and not s.of_type("verdict")  # ratings kept, nothing scored
    assert score_session(s).chains[0].outcome == Outcome.UNADJUDICATED
    unres = json.loads((default_key_path(batch).parent / "unresolved.json").read_text())
    assert unres["unresolved"] == [f"{iid}/0"]
    c = _labels(tmp_path, "c", {f"{iid}/0": {"label": "not_complied", "v_seen": 30.0}})
    r = merge(batch, [(a, "R1"), (b, "R2")], arbiter=(c, "R3"))
    assert r["arbitrated"] == 1
    s = load_session(log)
    vs = s.of_type("verdict")
    assert len(vs) == 1 and vs[0]["reconciliation"] == "arbitration" and vs[0]["label"] == "not_complied"
    assert vs[0]["annotators"] == ["R1", "R2", "R3"] and vs[0]["revision"] == 0
    assert vs[0]["t_review_start"] == pytest.approx(3.0) and vs[0]["t_review_end"] == pytest.approx(30.0)
    assert len(s.of_type("rating")) == 3
    assert score_session(s).chains[0].outcome == Outcome.NEVER  # negative label without a time
    # idempotent
    r = merge(batch, [(a, "R1"), (b, "R2")], arbiter=(c, "R3"))
    assert sum(r["appended"].values()) == 0
    with pytest.raises(ValueError, match="exactly two"):
        merge(batch, [(a, "R1")])
    with pytest.raises(ValueError, match="distinct"):
        merge(batch, [(a, "R1"), (b, "R1")])


def test_merge_agreement_uses_later_time(tmp_path):
    log, batch, items = _one_item(tmp_path)
    iid = items[0]["id"]
    a = _labels(tmp_path, "a", {f"{iid}/0": {"label": "complied", "v_first": 8.0}})
    b = _labels(tmp_path, "b", {f"{iid}/0": {"label": "complied", "v_first": 8.6}})
    r = merge(batch, [(a, "R1"), (b, "R2")])
    assert r["agreed"] == 1 and r["kappa"] == 1.0
    c = score_session(load_session(log)).chains[0]
    assert c.outcome == Outcome.SUCCESS and c.tvc == pytest.approx(5.6)
    # times further apart than the tolerance are a disagreement
    _, batch2, items2 = _one_item(tmp_path, name="t")
    j = items2[0]["id"]
    a2 = _labels(tmp_path, "a2", {f"{j}/0": {"label": "complied", "v_first": 8.0}})
    b2 = _labels(tmp_path, "b2", {f"{j}/0": {"label": "complied", "v_first": 12.0}})
    assert merge(batch2, [(a2, "R1"), (b2, "R2")])["unresolved"] == [f"{j}/0"]


def test_merge_rejects_out_of_range_and_incomplete_labels(tmp_path):
    log, batch, items = _one_item(tmp_path)
    iid = items[0]["id"]
    before = log.read_text(encoding="utf-8")
    ok = _labels(tmp_path, "ok", {f"{iid}/0": {"label": "not_complied"}})
    for bad in ({"label": "complied", "v_first": 45.0},  # past the recording (40 s)
                {"label": "complied", "v_first": 1.0},  # before the request (origin 3 s)
                {"label": "complied"},  # done without a time
                {"v_first": 8.0}):  # no label
        p = _labels(tmp_path, "bad", {f"{iid}/0": bad})
        with pytest.raises(LabelError):
            merge(batch, [(ok, "R1"), (p, "R2")])
    p = _labels(tmp_path, "bad", {"zzzzzz/0": {"label": "unknown"}})
    with pytest.raises(LabelError, match="unknown item"):
        merge(batch, [(ok, "R1"), (p, "R2")])
    assert log.read_text(encoding="utf-8") == before  # all-or-nothing


def test_video_to_session_does_not_extrapolate():
    segs = presented_segments([{"type": "chunk_presented", "t_start": 10.0, "t_end": 11.0},
                               {"type": "chunk_presented", "t_start": 12.0, "t_end": 13.0}])
    assert video_to_session(segs, 2.0) == 13.0
    with pytest.raises(ValueError):
        video_to_session(segs, 2.5)


def test_content_item_onset_merge(tmp_path):
    utts = [(3.0, "《静夜思》是谁写的？", "new", "c1", {"kind": "content", "content_type": "qa"})]
    script = {"type": "speech_onset", "t": 4.0, "on_topic": None, "source": "script", "chain_id": "A2-E2-C01-s0:c1"}
    log, batch, items = _one_item(tmp_path, "E2-C01", utts, extra=[script])
    iid = items[0]["id"]
    assert items[0]["criteria"]["rubric"]["answer"] == "李白"
    no_onset = _labels(tmp_path, "n", {f"{iid}/0": {"label": "complied", "v_end": 12.0}})
    good = _labels(tmp_path, "g", {f"{iid}/0": {"label": "complied", "v_onset": 6.0, "v_end": 12.0}})
    with pytest.raises(LabelError, match="onset"):
        merge(batch, [(good, "R1"), (no_onset, "R2")])
    good2 = _labels(tmp_path, "g2", {f"{iid}/0": {"label": "complied", "v_onset": 6.5, "v_end": 12.2}})
    merge(batch, [(good, "R1"), (good2, "R2")])
    s = load_session(log)
    adj = [e for e in s.of_type("speech_onset") if e.get("source") == "adjudicated"]
    assert len(adj) == 1 and adj[0]["on_topic"] is True and adj[0]["t"] == pytest.approx(6.5)
    c = score_session(s).chains[0]
    assert c.outcome == Outcome.SUCCESS and c.onset_s == pytest.approx(3.5)  # the scripted 4.0 is ignored


def test_content_no_onset_label(tmp_path):
    utts = [(3.0, "《静夜思》是谁写的？", "new", "c1", {"kind": "content", "content_type": "qa"})]
    log, batch, items = _one_item(tmp_path, "E2-C01", utts)
    iid = items[0]["id"]
    a = _labels(tmp_path, "a", {f"{iid}/0": {"label": "not_complied", "onset_none": True}})
    b = _labels(tmp_path, "b", {f"{iid}/0": {"label": "not_complied", "onset_none": True}})
    merge(batch, [(a, "R1"), (b, "R2")])
    assert score_session(load_session(log)).chains[0].outcome == Outcome.ONSET_FAIL


def test_claim_items_for_withdrawn_chains(tmp_path):
    utts = [(3.0, "请站起来一下。", "new", "c1", {"kind": "action"}),
            (6.0, "算了，不用站了。", "withdrawal", "c1", {}),
            (10.0, "笑一个吧。", "new", "c2", {"kind": "action"})]
    claim = {"type": "completion_claim", "chain_id": "A2-E2-D04-s0:c1", "t": 7.0}
    log, batch, items = _one_item(tmp_path, "E2-D04", utts, extra=[claim])
    by = {it["type"]: it for it in items}
    assert set(by) == {"chain", "claim"}
    cl = by["claim"]
    assert cl["texts"] == ["请站起来一下。", "算了，不用站了。"] and cl["criteria"]["checks"] == ["人物由坐姿变为站姿"]
    assert cl["v_claim"] == pytest.approx(7.0)
    ch = by["chain"]
    lab = {f"{ch['id']}/0": {"label": "complied", "v_first": 12.0}, f"{cl['id']}/0": {"label": "not_complied"}}
    a, b = _labels(tmp_path, "a", lab), _labels(tmp_path, "b", lab)
    merge(batch, [(a, "R1"), (b, "R2")])
    sc = score_session(load_session(log))
    s = summarize(sc.chains)
    assert s["n_claims"] == 1 and s["n_false_claims"] == 1 and s["n_withdrawn"] == 1 and s["n_success"] == 1
    build_report([sc], n_boot=50)  # complete: no gaps
