"""Tests for the Codex review fixes in the evaluation harness (impl2 findings 1-7, 9, 11 and
impl2c round 2: NEW-1..9, R1-5/7/11): adjudication-only primary outcome, dual rating +
arbitration with review coverage, frozen criteria and absolute deadlines, revision binding,
audio claim sweep, capacity skips, observation windows and the missing-data rule,
preregistered Holm families, RQ2 per failure point, blinded media, immutable batches."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from test_eval import Log

from live_agent.eval import report, stats
from live_agent.eval.adjudicate import (
    BlindingError,
    LabelError,
    MergeConflictError,
    check_blinded,
    covered,
    default_key_path,
    merge,
    prepare,
    presented_segments,
    video_to_session,
)
from live_agent.eval.report import MIN_TASKS, PairingError, build_report, compare
from live_agent.eval.schema import SchemaError, load_session, parse_session
from live_agent.eval.scoring import (
    IncompleteAdjudicationError,
    InsufficientObservationError,
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


# --------------------------------------------------------------------------- finding 5 / R1-5: claims


def test_primary_fcr_uses_adjudicated_sweep_claims_incl_withdrawn_chains():
    L = Log()
    L.new(0.0, chain="c1")
    L.withdraw(4.0, chain="c1")
    L.aclaim(6.0, "not_complied", chain="c1")  # heard after the user withdrew: false
    L.ev(type="completion_claim", chain_id="c1", t=6.5)  # logged claim: diagnostic only
    L.new(8.0, chain="c2")
    L.verdict(10.0, chain="c2")
    L.aclaim(11.0, "complied", chain="c2")
    sc = L.score()
    c1 = next(c for c in sc.chains if c.chain_id == "c1")
    assert c1.outcome == Outcome.WITHDRAWN and c1.n_claims == 1 and c1.n_false_claims == 1
    s = summarize(sc.chains)
    assert s["n_claims"] == 2 and s["n_false_claims"] == 1 and s["fcr"] == 0.5
    build_report([sc], n_boot=50)  # complete
    # diagnostic: the logged claims, judged by time (no complied verdict before it -> false)
    assert summarize(L.score(DIAG).chains)["n_claims"] == 1


def test_missing_claim_sweep_or_claim_verdict_is_a_gap():
    L = Log(sweep=False)
    L.new(0.0)
    L.verdict(5.0)
    with pytest.raises(IncompleteAdjudicationError, match="claim sweep"):
        build_report([L.score()], n_boot=50)
    L = Log()
    L.new(0.0)
    L.verdict(5.0)
    L.ev(type="completion_claim", chain_id="c1", t=6.0, source="adjudicated")  # no claim verdict
    with pytest.raises(IncompleteAdjudicationError, match="claim-level verdict"):
        build_report([L.score()], n_boot=50)


def test_diagnostic_claims_matched_to_steps():
    L = Log()
    L.new(0.0, kind="multistep", steps=["a", "b"])
    L.verdict(5.0, step=0)
    L.verdict(12.0, step=1)
    L.ev(type="completion_claim", chain_id="c1", t=6.0, step=0)  # true
    L.ev(type="completion_claim", chain_id="c1", t=7.0, step=1)  # false: step 1 only at 12
    L.ev(type="completion_claim", chain_id="c1", t=8.0)  # whole task: false (step 1 missing)
    L.ev(type="completion_claim", chain_id="c1", t=13.0)  # whole task: true
    c = L.one(cfg=ScoringConfig.diagnostic_config(("adjudicated",)))
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


# --------------------------------------------------------------------------- finding 7 / NEW-1


def _short_observed():
    L = Log()
    L.new(0.0, chain="c1")
    L.verdict(None, chain="c1", label="not_complied")
    L.new(0.0, chain="c2")
    L.verdict(4.0, chain="c2")  # success observed before the recording ended
    L.ev(type="observation_end", t=10.0)  # window of c1 needs 15 s
    return L


def test_insufficient_observation_blocks_primary_report():
    L = _short_observed()
    sc = L.score()
    out = {c.chain_id: c for c in sc.chains}
    assert out["c1"].outcome == Outcome.INSUFFICIENT_OBSERVATION and not out["c1"].in_primary
    assert out["c2"].outcome == Outcome.SUCCESS
    s = summarize(sc.chains)
    assert s["n_effective"] == 1 and s["n_insufficient_observation"] == 1
    with pytest.raises(InsufficientObservationError, match="c1"):
        build_report([sc], n_boot=50)  # default rule: rerun-required
    md = build_report([sc], n_boot=50, missing_rule="worst-case")
    assert "SENSITIVITY ANALYSIS (worst-case missing-data rule)" in md and "1 chain(s)" in md
    assert "| A2 | 1 | 2 | 50.0% |" in md  # imputed failure back in the denominator
    L.ev(type="observation_end", t=20.0)
    assert L.one("c1").outcome == Outcome.NEVER
    build_report([L.score()], n_boot=50)


def test_report_cli_missing_rule(tmp_path, capsys):
    p = _write_log(tmp_path / "a.jsonl", _short_observed().recs)
    with pytest.raises(SystemExit) as e:
        report.main([str(p)])
    assert e.value.code == 2 and "unobserved deadline window" in capsys.readouterr().err
    out = tmp_path / "wc.md"
    report.main([str(p), "--missing-rule", "worst-case", "-o", str(out)])
    assert "SENSITIVITY" in out.read_text(encoding="utf-8")


def test_observation_end_falls_back_to_last_presented_chunk():
    L = Log()
    L.new(0.0)
    L.verdict(None, label="not_complied")
    L.ev(type="chunk_presented", request=0, chunk=0, t_start=0.0, t_end=12.0)
    assert L.one().outcome == Outcome.INSUFFICIENT_OBSERVATION


# --------------------------------------------------------------------------- NEW-9


def test_time_to_success_has_no_early_censoring_and_per_kind_table():
    L = Log()
    L.new(0.0, kind="multistep", steps=["a", "b"], chain="m")
    L.verdict(10.0, step=0, chain="m")
    L.verdict(5.0, step=1, chain="m")  # order_fail: deterministic
    L.new(0.0, chain="a1")
    L.ev(type="refusal", chain_id="a1", t=1.0)
    L.new(0.0, chain="a2")
    L.verdict(6.0, chain="a2")
    L.ev(type="observation_end", t=40.0)
    out = {c.chain_id: c for c in L.score().chains}
    assert out["m"].outcome == Outcome.ORDER_FAIL and out["m"].time_to_success == 30.0  # = D
    assert out["a1"].time_to_success == 15.0 and out["a2"].time_to_success == pytest.approx(6.0)
    md = build_report([L.score()], n_boot=50)
    assert "Success by the common deadline, per kind" in md
    assert "| action | 15 | 2 | 1/2 (50.0%) |" in md and "| multistep | 30 | 1 | 0/1 (0.0%) |" in md
    assert "Time to success, all kinds" not in md


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
                    L.aclaim(14.5, "complied")
                else:
                    L.verdict(None, label="not_complied")
                    if rng.random() < 0.5:
                        L.aclaim(14.5, "not_complied")
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
    p, p_adj = float(cells[6]), float(cells[7])
    assert p_adj == pytest.approx(min(1.0, 4 * p))  # family size 4 even though 1 was run
    assert "reject H0" in "\n".join(x for x in md.splitlines() if x.startswith("| A2 - A1 |"))
    md2 = "\n".join(compare(by, display=[("A2", "A2-noqc"), ("A2-noqc", "A1")], n_boot=300))
    assert "| A2 - A1 |" not in md2 and row in md2
    assert "Exploratory (not preregistered" in md2 and "| A2-noqc - A1 |" in md2


def test_fcr_and_claim_coverage_get_task_clustered_cis():
    md = build_report(_sessions((("A2", 0.7),)), n_boot=300)
    fcr = next(x for x in md.splitlines() if x.startswith("| FCR"))
    cov = next(x for x in md.splitlines() if x.startswith("| Claim coverage"))
    assert fcr.rstrip("|").split("|")[-1].strip() != "n/a"
    assert cov.rstrip("|").split("|")[-1].strip() != "n/a"


# --------------------------------------------------------------------------- NEW-8: RQ2


def test_repair_every_failure_point_with_preregistered_handling():
    L = Log("A2-rq2", "T1", 0)
    L.new(0.0, chain="c1")
    L.ev(type="chunk_presented", request=3, chunk=0, t_start=18.0, t_end=23.0)
    L.ev(type="observation_end", t=40.0)
    L.ev(type="repair_assignment", chain_id="c1", arm="forward_correction", failure_request=1, target_request=3,
         arm_drawn=True, t=12.0)
    L.ev(type="repair_assignment", chain_id="c1", arm="repeat", failure_request=2, target_request=9,
         arm_drawn=True, t=13.0)
    L.verdict(19.0, chain="c1")  # no request field -> mapped through the presented chunk
    L.new(1.0, chain="c2")
    L.withdraw(20.0, chain="c2")
    L.ev(type="repair_assignment", chain_id="c2", arm="repeat", failure_request=1, target_request=3,
         arm_drawn=True, t=12.0)
    sc = L.score()
    c1 = next(c for c in sc.chains if c.chain_id == "c1")
    assert [r["status"] for r in c1.repairs] == ["success", "insufficient_observation"]
    c2 = next(c for c in sc.chains if c.chain_id == "c2")
    assert c2.outcome == Outcome.WITHDRAWN and c2.repairs[0]["status"] == "withdrawn"
    s = summarize(sc.chains)["repair"]
    assert s["forward_correction"]["k"] == 1 and s["forward_correction"]["n"] == 1
    assert s["repeat"] == {**s["repeat"], "n": 1, "k": 0, "n_withdrawn": 1, "n_insufficient_observation": 1,
                           "n_excl_withdrawn": 0}
    md = build_report([sc], n_boot=100)
    assert "withdrawal after assignment = failure" in md and "sensitivity: withdrawn excluded" in md
    assert "target request not observed (excluded, rerun)" in md


# --------------------------------------------------------------------------- adjudication tool


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
    p.with_suffix(".mp4").write_bytes(b"\0not-a-real-mp4")
    return p


def _items(page: Path) -> list[dict]:
    return json.loads(page.read_text(encoding="utf-8").split("const ITEMS = ")[1].split(";\n")[0])


def _labels(tmp_path: Path, name: str, d: dict) -> Path:
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


SWEEP_NONE = {"complete": True, "v_watched": [[0.0, 40.0]], "claims": []}


def test_key_outside_batch_media_not_symlinked_and_blinded(tmp_path):
    log = _session_file(tmp_path, "A2-E2-A01-s0", "E2-A01", [(3.0, "请喝口茶吧。", "new", "c1",
                                                              {"kind": "action", "intent": "端起茶杯喝一口茶"})])
    batch = tmp_path / "adj" / "b1"
    page = prepare([log], batch)
    key = default_key_path(batch)
    assert key.exists() and batch.resolve() not in key.resolve().parents
    assert not list(batch.rglob("key*"))
    media = list((batch / "media").iterdir())
    assert media and not any(m.is_symlink() for m in media)  # hard link or copy, never a symlink
    for f in batch.rglob("*"):
        assert "A2" not in f.name and "E2-A01" not in f.name
    text = page.read_text(encoding="utf-8")
    assert "E2-A01" not in text and '"A2' not in text and str(tmp_path) not in text
    with pytest.raises(ValueError, match="must not be inside"):
        prepare([log], batch, key_path=batch / "sub" / "key.json")


def test_check_blinded_catches_leaks(tmp_path):
    b = tmp_path / "b"
    (b / "media").mkdir(parents=True)
    (b / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    check_blinded(b, ["A2-E2-A01-s0"], ["A2"])
    (b / "media" / "x.mp4").write_bytes(b"\0\0title=A2-E2-A01-s0\0")  # metadata leak
    with pytest.raises(BlindingError, match="contains"):
        check_blinded(b, ["A2-E2-A01-s0"], ["A2"])
    (b / "media" / "x.mp4").unlink()
    (b / "media" / "y.mp4").symlink_to(tmp_path / "A2-E2-A01-s0.mp4")
    with pytest.raises(BlindingError, match="symlink"):
        check_blinded(b, [], [])
    (b / "media" / "y.mp4").unlink()
    (b / "index.html").write_text("<p>condition A2-noqc</p>", encoding="utf-8")
    with pytest.raises(BlindingError, match="condition"):
        check_blinded(b, [], ["A2-noqc"])


def test_items_carry_frozen_criteria_and_absolute_deadlines(tmp_path):
    logs = [
        _session_file(tmp_path, "x1", "E2-A01", [(3.0, "请喝口茶吧。", "new", "c1", {"kind": "action"})]),
        _session_file(tmp_path, "x2", "E2-C04", [(3.0, "给我讲讲CUDA是什么吧。", "new", "c1",
                                                  {"kind": "content", "content_type": "explain"})], length=60.0),
        _session_file(tmp_path, "x3", "E2-M02", [(3.0, "先站起来，挥挥手，再坐回去。", "new", "c1",
                                                  {"kind": "multistep", "steps": ["站起来", "挥手", "坐下"]})]),
    ]
    page = prepare(logs, tmp_path / "b")
    items = {it["kind"]: it for it in _items(page) if it["type"] == "chain"}
    assert items["action"]["criteria"]["checks"] == ["人物端起茶杯", "茶杯送到嘴边并作饮用动作"]
    assert items["action"]["dl"]["done_by"] == {"v": 18.0, "beyond": False}
    c = items["content"]
    assert c["criteria"]["rubric"]["k"] == 3 and c["criteria"]["duration_s"] == 30.0
    # proposal D: onset <= origin + 15 s; complete answer <= origin + 15 s + duration
    assert c["dl"]["onset_by"] == {"v": 18.0, "beyond": False}
    assert c["dl"]["complete_by"] == {"v": 48.0, "beyond": False}
    assert "request end + " in page.read_text(encoding="utf-8")
    m = items["multistep"]
    assert m["n_steps"] == 3 and [s["checks"] for s in m["criteria"]["steps"]][2] == ["人物由站姿回到坐姿"]
    assert sum(it["type"] == "sweep" for it in _items(page)) == 3  # one audio claim sweep per session
    bad = _session_file(tmp_path, "x4", "T-unknown", [(3.0, "x", "new", "c1", {"kind": "action"})])
    with pytest.raises(ValueError, match="no preregistered criteria"):
        prepare([bad], tmp_path / "b2")


def _one_item(tmp_path, task_id="E2-A01", utts=None, extra=(), name="s", length=40.0):
    utts = utts or [(3.0, "请喝口茶吧。", "new", "c1", {"kind": "action"})]
    log = _session_file(tmp_path, name, task_id, utts, extra, length=length)
    batch = tmp_path / f"batch-{name}"
    items = _items(prepare([log], batch))
    chain = [it for it in items if it["type"] == "chain"]
    sweep = next(it for it in items if it["type"] == "sweep")
    return log, batch, chain, sweep


def test_merge_agreement_disagreement_arbitration(tmp_path):
    log, batch, items, sw = _one_item(tmp_path)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    a = _labels(tmp_path, "a", {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 8.0, "v_watched": [[0.0, 20.0]]}, sk: SWEEP_NONE})
    b = _labels(tmp_path, "b", {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 25.0]]}, sk: SWEEP_NONE})
    r = merge(batch, [(a, "R1"), (b, "R2")])
    assert list(r["unresolved"]) == [f"{iid}/0"] and r["agreed"] == 1  # the sweep agreed
    s = load_session(log)
    assert len([e for e in s.of_type("rating") if e.get("item") == iid]) == 2
    assert not [v for v in s.of_type("verdict") if v.get("item") == iid]  # ratings kept, nothing scored
    assert score_session(s).chains[0].outcome == Outcome.UNADJUDICATED
    unres = json.loads((default_key_path(batch).parent / "unresolved.json").read_text())
    assert list(unres["unresolved"]) == [f"{iid}/0"]
    c = _labels(tmp_path, "c", {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 30.0]]}})
    r = merge(batch, [(a, "R1"), (b, "R2")], arbiter=(c, "R3"))  # adding an arbiter is allowed
    assert r["arbitrated"] == 1
    s = load_session(log)
    vs = [v for v in s.of_type("verdict") if v.get("item") == iid]
    assert len(vs) == 1 and vs[0]["reconciliation"] == "arbitration" and vs[0]["label"] == "not_complied"
    assert vs[0]["annotators"] == ["R1", "R2", "R3"] and vs[0]["revision"] == 0
    assert vs[0]["t_review_start"] == pytest.approx(3.0) and vs[0]["t_review_end"] == pytest.approx(30.0)
    assert len([e for e in s.of_type("rating") if e.get("item") == iid]) == 3
    sc = score_session(s)
    assert sc.chains[0].outcome == Outcome.NEVER and sc.claim_sweep
    build_report([sc], n_boot=50)
    before = log.read_text(encoding="utf-8")
    merge(batch, [(a, "R1"), (b, "R2")], arbiter=(c, "R3"))  # identical inputs: no-op
    assert log.read_text(encoding="utf-8") == before
    with pytest.raises(ValueError, match="exactly two"):
        merge(batch, [(a, "R1")])
    with pytest.raises(ValueError, match="distinct"):
        merge(batch, [(a, "R1"), (b, "R1")])


def test_finalized_batch_is_immutable_unless_replaced(tmp_path):
    log, batch, items, sw = _one_item(tmp_path)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    lab = {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 8.0}, sk: SWEEP_NONE}
    a, b = _labels(tmp_path, "a", lab), _labels(tmp_path, "b", lab)
    merge(batch, [(a, "R1"), (b, "R2")])
    assert score_session(load_session(log)).chains[0].outcome == Outcome.SUCCESS
    corrected = {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 20.0]]}, sk: SWEEP_NONE}
    b2 = _labels(tmp_path, "b2", corrected)
    a2 = _labels(tmp_path, "a2", corrected)
    with pytest.raises(MergeConflictError):
        merge(batch, [(a2, "R1"), (b2, "R2")])
    assert score_session(load_session(log)).chains[0].outcome == Outcome.SUCCESS  # untouched
    merge(batch, [(a2, "R1"), (b2, "R2")], replace=True)
    s = load_session(log)
    vs = [v for v in s.of_type("verdict") if v.get("item") == iid]
    assert len(vs) == 1 and vs[0]["label"] == "not_complied"  # old success removed atomically
    assert len([e for e in s.of_type("rating") if e.get("item") == iid]) == 2
    assert score_session(s).chains[0].outcome == Outcome.NEVER
    assert not list(log.parent.glob("*.tmp-*"))


def test_negative_labels_need_review_through_the_deadline(tmp_path):
    log, batch, items, sw = _one_item(tmp_path)  # origin 3 s -> deadline 18 s
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    short = {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 4.0]]}, sk: SWEEP_NONE}
    full = {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 18.0]]}, sk: SWEEP_NONE}
    r = merge(batch, [(_labels(tmp_path, "a", short), "R1"), (_labels(tmp_path, "b", short), "R2")])
    assert "reviewed less than the deadline window" in r["unresolved"][f"{iid}/0"]  # escalated
    assert score_session(load_session(log)).chains[0].outcome == Outcome.UNADJUDICATED
    r = merge(batch, [(_labels(tmp_path, "a", short), "R1"), (_labels(tmp_path, "b", short), "R2")],
              arbiter=(_labels(tmp_path, "c", full), "R3"))
    assert r["arbitrated"] == 1
    assert score_session(load_session(log)).chains[0].outcome == Outcome.NEVER
    # recording shorter than the deadline: review to its end suffices (then flagged unobserved)
    log2, batch2, items2, sw2 = _one_item(tmp_path, name="t", length=12.0)
    j, sk2 = items2[0]["id"], f"{sw2['id']}/0"
    lab = {f"{j}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 12.0]]}, sk2: dict(SWEEP_NONE, v_watched=[[0.0, 12.0]])}
    r = merge(batch2, [(_labels(tmp_path, "a2", lab), "R1"), (_labels(tmp_path, "b2", lab), "R2")])
    assert not r["unresolved"]
    assert score_session(load_session(log2)).chains[0].outcome == Outcome.INSUFFICIENT_OBSERVATION


def test_multistep_negative_review_counts_from_previous_step(tmp_path):
    utts = [(3.0, "先站起来，挥挥手，再坐回去。", "new", "c1", {"kind": "multistep", "steps": ["a", "b", "c"]})]
    log, batch, items, sw = _one_item(tmp_path, "E2-M02", utts)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    # step 0 done at 10 -> step 1 "not done" needs review to 25
    lab = {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 10.0}, f"{iid}/1": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 20.0]]},
           sk: SWEEP_NONE}
    r = merge(batch, [(_labels(tmp_path, "a", lab), "R1"), (_labels(tmp_path, "b", lab), "R2")])
    assert list(r["unresolved"]) == [f"{iid}/1"] and r["agreed"] == 2
    lab[f"{iid}/1"]["v_watched"] = [[0.0, 25.0]]
    r = merge(batch, [(_labels(tmp_path, "a3", lab), "R1"), (_labels(tmp_path, "b3", lab), "R2")], replace=True)
    assert not r["unresolved"]
    assert score_session(load_session(log)).chains[0].outcome == Outcome.NEVER


def test_merge_agreement_uses_later_time(tmp_path):
    log, batch, items, sw = _one_item(tmp_path)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    a = _labels(tmp_path, "a", {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 8.0}, sk: SWEEP_NONE})
    b = _labels(tmp_path, "b", {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 8.6}, sk: SWEEP_NONE})
    r = merge(batch, [(a, "R1"), (b, "R2")])
    assert r["agreed"] == 2 and r["kappa"] == 1.0
    c = score_session(load_session(log)).chains[0]
    assert c.outcome == Outcome.SUCCESS and c.tvc == pytest.approx(5.6)
    _, batch2, items2, _ = _one_item(tmp_path, name="t")
    j = items2[0]["id"]
    a2 = _labels(tmp_path, "a2", {f"{j}/0": {"v_onset": 4.0, "label": "complied", "v_first": 8.0}})
    b2 = _labels(tmp_path, "b2", {f"{j}/0": {"v_onset": 4.0, "label": "complied", "v_first": 12.0}})
    assert list(merge(batch2, [(a2, "R1"), (b2, "R2")])["unresolved"]) == [f"{j}/0"]


def test_merge_rejects_out_of_range_and_incomplete_labels(tmp_path):
    log, batch, items, _ = _one_item(tmp_path)
    iid = items[0]["id"]
    before = log.read_text(encoding="utf-8")
    ok = _labels(tmp_path, "ok", {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 20.0]]}})
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


def test_content_item_onset_merge_and_order(tmp_path):
    utts = [(3.0, "《静夜思》是谁写的？", "new", "c1", {"kind": "content", "content_type": "qa"})]
    script = {"type": "speech_onset", "t": 4.0, "on_topic": None, "source": "script", "chain_id": "A2-E2-C01-s0:c1"}
    log, batch, items, sw = _one_item(tmp_path, "E2-C01", utts, extra=[script])
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    assert items[0]["criteria"]["rubric"]["answer"] == "李白"
    good = _labels(tmp_path, "g", {f"{iid}/0": {"label": "complied", "v_onset": 6.0, "v_end": 12.0}, sk: SWEEP_NONE})
    for bad in ({"label": "complied", "v_end": 12.0},  # no onset decision
                {"label": "complied", "v_onset": 13.0, "v_end": 12.0}):  # answer ends before onset
        with pytest.raises(LabelError, match="onset"):
            merge(batch, [(good, "R1"), (_labels(tmp_path, "n", {f"{iid}/0": bad}), "R2")])
    good2 = _labels(tmp_path, "g2", {f"{iid}/0": {"label": "complied", "v_onset": 6.5, "v_end": 12.2}, sk: SWEEP_NONE})
    merge(batch, [(good, "R1"), (good2, "R2")])
    s = load_session(log)
    adj = [e for e in s.of_type("speech_onset") if e.get("source") == "adjudicated"]
    assert len(adj) == 1 and adj[0]["on_topic"] is True and adj[0]["t"] == pytest.approx(6.5)
    c = score_session(s).chains[0]
    assert c.outcome == Outcome.SUCCESS and c.onset_s == pytest.approx(3.5)  # the scripted 4.0 is ignored


def test_content_no_onset_needs_review_to_onset_deadline(tmp_path):
    utts = [(3.0, "《静夜思》是谁写的？", "new", "c1", {"kind": "content", "content_type": "qa"})]
    log, batch, items, sw = _one_item(tmp_path, "E2-C01", utts)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    lab = {f"{iid}/0": {"label": "not_complied", "onset_none": True, "v_watched": [[0.0, 28.0]]}, sk: SWEEP_NONE}  # 3+15+10
    merge(batch, [(_labels(tmp_path, "a", lab), "R1"), (_labels(tmp_path, "b", lab), "R2")])
    assert score_session(load_session(log)).chains[0].outcome == Outcome.ONSET_FAIL


def _sweep_session(tmp_path):
    utts = [(3.0, "请站起来一下。", "new", "c1", {"kind": "action"}),
            (6.0, "算了，不用站了。", "withdrawal", "c1", {}),
            (10.0, "笑一个吧。", "new", "c2", {"kind": "action"})]
    logged = {"type": "completion_claim", "chain_id": "A2-E2-D04-s0:c1", "t": 7.0}
    return _one_item(tmp_path, "E2-D04", utts, extra=[logged])


def test_audio_claim_sweep_items_and_merge(tmp_path):
    log, batch, items, sw = _sweep_session(tmp_path)
    assert [len(r["revisions"]) for r in sw["refs"]] == [1, 1]
    assert sw["refs"][0]["revisions"][0]["criteria"]["checks"] == ["人物由坐姿变为站姿"]
    assert "7.0" not in json.dumps(sw) and "claim" not in json.dumps(sw["refs"])  # logged claims hidden
    ch, sk = items[0]["id"], f"{sw['id']}/0"
    r0, r1 = sw["refs"][0]["ref"], sw["refs"][1]["ref"]
    claims_a = [{"v_claim": 7.0, "ref": r0, "label": "not_complied"},
                {"v_claim": 14.0, "ref": r1, "label": "complied", "v_evidence": 12.0}]
    claims_b = [{"v_claim": 7.4, "ref": r0, "label": "not_complied"},
                {"v_claim": 14.2, "ref": r1, "label": "complied", "v_evidence": 12.5},
                {"v_claim": 30.0, "ref": r1, "label": "complied", "v_evidence": 20.0}]  # only B heard this
    chain = {f"{ch}/0": {"v_onset": 11.0, "label": "complied", "v_first": 12.0}}
    a = _labels(tmp_path, "a", {**chain, sk: {"complete": True, "v_watched": [[0.0, 40.0]], "claims": claims_a}})
    b = _labels(tmp_path, "b", {**chain, sk: {"complete": True, "v_watched": [[0.0, 40.0]], "claims": claims_b}})
    r = merge(batch, [(a, "R1"), (b, "R2")])
    assert sk in r["unresolved"] and "one rater only" in r["unresolved"][sk]
    assert not load_session(log).of_type("claim_sweep")
    c = _labels(tmp_path, "c", {sk: {"complete": True, "v_watched": [[0.0, 40.0]], "claims": []}})  # arbiter: no such claim
    merge(batch, [(a, "R1"), (b, "R2")], arbiter=(c, "R3"))
    s = load_session(log)
    adj = [e for e in s.of_type("completion_claim") if e.get("source") == "adjudicated"]
    assert [round(e["t"], 1) for e in adj] == [7.4, 14.2]  # later time of each agreed pair
    sc = score_session(s)
    assert sc.claim_sweep
    sm = summarize(sc.chains)
    assert sm["n_claims"] == 2 and sm["n_false_claims"] == 1  # the claim on the withdrawn chain is false
    build_report([sc], n_boot=50)


def test_sweep_evidence_must_precede_claim_and_review_whole_recording(tmp_path):
    _, batch, _, sw = _sweep_session(tmp_path)
    sk, r1 = f"{sw['id']}/0", sw["refs"][1]["ref"]
    ok = _labels(tmp_path, "ok", {sk: SWEEP_NONE})
    for bad in ({"complete": True, "v_watched": [[0.0, 40.0]],
                 "claims": [{"v_claim": 14.0, "ref": r1, "label": "complied", "v_evidence": 16.0}]},  # after
                {"complete": True, "v_watched": [[0.0, 40.0]],
                 "claims": [{"v_claim": 14.0, "ref": r1, "label": "complied"}]},  # no evidence
                {"complete": True, "v_watched": [[0.0, 40.0]],
                 "claims": [{"v_claim": 8.0, "ref": r1, "label": "not_complied"}]},  # before the request
                {"complete": False, "v_watched": [[0.0, 40.0]], "claims": []}):  # not finished
        with pytest.raises(LabelError):
            merge(batch, [(ok, "R1"), (_labels(tmp_path, "bad", {sk: bad}), "R2")])
    short = _labels(tmp_path, "short", {sk: {"complete": True, "v_watched": [[0.0, 20.0]], "claims": []}})
    r = merge(batch, [(ok, "R1"), (short, "R2")])
    assert "incomplete review" in r["unresolved"][sk]


# --------------------------------------------------------------------------- round 3 (impl2d)


def _paired_sessions(conds, tasks, seeds=2, drop=()):
    out = []
    for cond in conds:
        for t in range(tasks):
            for s in range(seeds):
                if (cond, t, s) in drop:
                    continue
                L = Log(cond, f"T{t}", s)
                L.new(0.0)
                if cond == "A2" or (t + s) % 2:
                    L.verdict(5.0)
                else:
                    L.verdict(None, label="not_complied")
                out.append(L.score())
    return out


def test_incomplete_pair_set_blocks_decision_unless_allowed(tmp_path, capsys):
    ss = _paired_sessions(("A1", "A2"), 12, drop={("A1", 3, 1)})
    with pytest.raises(PairingError, match="missing in A1"):
        build_report(ss, n_boot=100)
    md = build_report(ss, n_boot=100, allow_incomplete_pairs=True)
    row = next(x for x in md.splitlines() if x.startswith("| A2 - A1 |"))
    assert "EXPLORATORY: 1 pair key(s) missing" in row and "reject" not in row
    # CLI: exit 2
    L1, L2 = Log("A1", "T0", 0), Log("A2", "T0", 0)
    for L in (L1, L2):
        L.new(0.0)
        L.verdict(5.0)
    L2.new(0.0, chain="c2")
    L2.verdict(5.0, chain="c2")
    paths = [_write_log(tmp_path / f"{i}.jsonl", L.recs) for i, L in enumerate((L1, L2))]
    with pytest.raises(SystemExit) as e:
        report.main([str(p) for p in paths])
    assert e.value.code == 2 and "missing in A1" in capsys.readouterr().err


def test_duplicate_pair_keys_rejected_even_when_incomplete_allowed():
    ss = _paired_sessions(("A1", "A2"), 12)
    ss.append(ss[0])  # the same A1 session twice
    with pytest.raises(PairingError, match="duplicate"):
        build_report(ss, n_boot=100, allow_incomplete_pairs=True)


def test_no_inference_below_min_tasks():
    assert MIN_TASKS == 10
    md = build_report(_paired_sessions(("A1", "A2"), 5, seeds=4), n_boot=200)
    row = next(x for x in md.splitlines() if x.startswith("| A2 - A1 |"))
    assert "no inference: 5 < 10 task clusters" in row and "reject" not in row
    assert "MIN_TASKS = 10" in md
    md = build_report(_paired_sessions(("A1", "A2"), 10), n_boot=200)
    assert "reject H0" in next(x for x in md.splitlines() if x.startswith("| A2 - A1 |"))


def test_early_step_is_nonqualifying_and_needs_its_window_observed():
    def run(obs_end):
        L = Log()
        L.new(0.0, kind="multistep", steps=["a", "b"])
        L.verdict(10.0, step=0)
        L.verdict(5.0, step=1)  # step 2 seen only before step 1
        L.ev(type="observation_end", t=obs_end)
        return L.one()
    assert run(12.0).outcome == Outcome.INSUFFICIENT_OBSERVATION  # step-2 window ends at 25
    assert run(25.0).outcome == Outcome.ORDER_FAIL


def test_merge_early_step_label_needs_review_through_its_window(tmp_path):
    utts = [(3.0, "先站起来，挥挥手，再坐回去。", "new", "c1", {"kind": "multistep", "steps": ["a", "b", "c"]})]
    _, batch, items, sw = _one_item(tmp_path, "E2-M02", utts)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    lab = {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 10.0},
           f"{iid}/1": {"label": "complied", "v_first": 6.0, "v_watched": [[0.0, 12.0]]}, sk: SWEEP_NONE}
    r = merge(batch, [(_labels(tmp_path, "a", lab), "R1"), (_labels(tmp_path, "b", lab), "R2")])
    assert f"{iid}/1" in r["unresolved"]  # early "done" needs review to 10 + 15 = 25


def test_response_onset_for_every_chain(tmp_path):
    L = Log()
    L.new(0.0)
    L.verdict(5.0, onset_reviewed=False)
    c = L.one()
    assert c.outcome == Outcome.UNADJUDICATED and "response onset" in c.missing
    L.onset(2.0)
    c = L.one()
    assert c.outcome == Outcome.SUCCESS and c.tfmr == 2.0 and c.tfmr_event
    # merge: action item onset decision required, emitted as an adjudicated onset
    log, batch, items, sw = _one_item(tmp_path)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    with pytest.raises(LabelError, match="response-onset"):
        merge(batch, [(_labels(tmp_path, "x", {f"{iid}/0": {"label": "complied", "v_first": 8.0}}), "R1"),
                      (_labels(tmp_path, "y", {f"{iid}/0": {"label": "complied", "v_first": 8.0}}), "R2")])
    lab = {f"{iid}/0": {"label": "complied", "v_first": 8.0, "v_onset": 5.0}, sk: SWEEP_NONE}
    merge(batch, [(_labels(tmp_path, "a", lab), "R1"), (_labels(tmp_path, "b", lab), "R2")])
    s = load_session(log)
    assert [e["t"] for e in s.of_type("speech_onset") if e.get("source") == "adjudicated"] == [5.0]
    assert score_session(s).chains[0].tfmr == pytest.approx(2.0)
    # "none by the deadline" needs the onset window watched (origin 3 + 15 = 18)
    _, batch2, items2, sw2 = _one_item(tmp_path, name="n")
    j, sk2 = items2[0]["id"], f"{sw2['id']}/0"
    lab = {f"{j}/0": {"label": "complied", "v_first": 8.0, "onset_none": True, "v_watched": [[0.0, 9.0]]},
           sk2: SWEEP_NONE}
    r = merge(batch2, [(_labels(tmp_path, "a2", lab), "R1"), (_labels(tmp_path, "b2", lab), "R2")])
    assert f"{j}/0" in r["unresolved"]


def test_review_coverage_is_the_union_of_watched_intervals(tmp_path):
    assert covered([[0, 10], [10.3, 40]], 3, 18) and not covered([[0, 10], [14, 40]], 3, 18)
    _, batch, items, sw = _one_item(tmp_path)
    iid, sk = items[0]["id"], f"{sw['id']}/0"
    gap = {f"{iid}/0": {"v_onset": 4.0, "label": "not_complied", "v_watched": [[0.0, 10.0], [14.0, 40.0]]},
           sk: SWEEP_NONE}  # skipped 10-14: the furthest position (40) is not coverage
    r = merge(batch, [(_labels(tmp_path, "a", gap), "R1"), (_labels(tmp_path, "b", gap), "R2")])
    assert f"{iid}/0" in r["unresolved"]
    sw_gap = {"complete": True, "v_watched": [[0.0, 20.0], [30.0, 40.0]], "claims": []}
    lab = {f"{iid}/0": {"v_onset": 4.0, "label": "complied", "v_first": 8.0}, sk: sw_gap}
    r = merge(batch, [(_labels(tmp_path, "c", lab), "R1"), (_labels(tmp_path, "d", lab), "R2")], replace=True)
    assert "incomplete review" in r["unresolved"][sk]


def test_sweep_one_to_one_across_three_raters_and_revision(tmp_path):
    log, batch, items, sw = _sweep_session(tmp_path)
    ch, sk, r1 = items[0]["id"], f"{sw['id']}/0", sw["refs"][1]["ref"]
    chain = {f"{ch}/0": {"v_onset": 11.0, "label": "complied", "v_first": 12.0}}
    full = [[0.0, 40.0]]
    a = {"complete": True, "v_watched": full, "claims": [{"v_claim": 14.0, "ref": r1, "label": "complied",
                                                          "v_evidence": 12.0}]}
    b = {"complete": True, "v_watched": full, "claims": [{"v_claim": 14.4, "ref": r1, "label": "complied",
                                                          "v_evidence": 12.0, "step": None},
                                                         {"v_claim": 15.2, "ref": r1, "label": "complied",
                                                          "v_evidence": 12.0}]}  # a second, nearby mark
    c = {"complete": True, "v_watched": full, "claims": [{"v_claim": 14.3, "ref": r1, "label": "complied",
                                                          "v_evidence": 12.0}]}  # one audible claim
    merge(batch, [(_labels(tmp_path, "a", {**chain, sk: a}), "R1"), (_labels(tmp_path, "b", {**chain, sk: b}), "R2")],
          arbiter=(_labels(tmp_path, "c", {sk: c}), "R3"))
    adj = [e for e in load_session(log).of_type("completion_claim") if e.get("source") == "adjudicated"]
    assert len(adj) == 1  # the arbiter's single mark is reserved by the agreed pair, not reused


def test_sweep_matching_respects_intent_revision(tmp_path):
    utts = [(3.0, "跟我挥挥手吧。", "new", "c1", {"kind": "action"}),
            (7.0, "哦对了，用左手挥。", "revision", "c1", {"kind": "action"})]
    _, batch, items, sw = _one_item(tmp_path, "E2-D01", utts)
    ch, sk, r0 = items[0]["id"], f"{sw['id']}/0", sw["refs"][0]["ref"]
    chain = {f"{ch}/0": {"v_onset": 8.0, "label": "complied", "v_first": 9.0}}
    mk = lambda t: {"complete": True, "v_watched": [[0.0, 40.0]],
                    "claims": [{"v_claim": t, "ref": r0, "label": "not_complied"}]}
    r = merge(batch, [(_labels(tmp_path, "a", {**chain, sk: mk(6.8)}), "R1"),
                      (_labels(tmp_path, "b", {**chain, sk: mk(7.2)}), "R2")])  # revision 0 vs 1
    assert "one rater only" in r["unresolved"][sk]


def test_repair_withdrawal_rule_applies_before_success():
    L = Log("A2", "T1", 0)
    L.new(0.0, chain="c1")
    L.ev(type="chunk_presented", request=3, chunk=0, t_start=18.0, t_end=23.0)
    L.ev(type="observation_end", t=40.0)
    L.ev(type="repair_assignment", chain_id="c1", arm="repeat", failure_request=1, target_request=3, t=10.0)
    L.withdraw(15.0, chain="c1")  # after the assignment
    L.verdict(19.0, chain="c1", source="judge")  # the locked target still played compliant content
    c = L.one(cfg=DIAG)
    assert c.repairs[0]["status"] == "withdrawn" and not c.repairs[0]["success"]
    L2 = Log("A2", "T1", 0)
    L2.new(0.0, chain="c1")
    L2.withdraw(5.0, chain="c1")
    L2.ev(type="repair_assignment", chain_id="c1", arm="repeat", failure_request=1, target_request=3, t=10.0)
    assert L2.one(cfg=DIAG).repairs[0]["status"] == "ineligible"


def test_rq2_audit_eligible_failures_and_arm_drawn():
    L = Log("A2-rq2", "T1", 0)
    L.new(0.0, chain="c1")
    L.ev(type="chunk_presented", request=1, chunk=0, t_start=5.0, t_end=10.0)
    L.ev(type="chunk_presented", request=3, chunk=0, t_start=15.0, t_end=20.0)
    L.ev(type="observation_end", t=40.0)
    L.verdict(20.0)
    # eligible: online not_complied on an open chain, earliest correctable request 3 presented
    L.ev(type="verdict", source="judge", label="not_complied", chain_id="c1", request=1, t_evidence=9.0,
         revision=0, earliest_correctable=3)
    # not eligible: j never presented before observation_end
    L.ev(type="verdict", source="judge", label="not_complied", chain_id="c1", request=2, t_evidence=12.0,
         revision=0, earliest_correctable=9)
    sc = L.score()
    assert len(sc.rq2_problems) == 1 and "k=1" in sc.rq2_problems[0]
    L.ev(type="repair_assignment", chain_id="c1", arm="repeat", failure_request=1, target_request=3, t=9.5)
    sc = L.score()
    assert sc.rq2_problems == ["assignment c1 k=1: arm not randomised (arm_drawn)"]
    md = build_report([sc], n_boot=50)
    assert "RQ2 audit failures" in md and "excluded: 1 session(s)" in md
    L.recs[-1]["arm_drawn"] = True
    assert L.score().rq2_problems == []
