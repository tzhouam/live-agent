"""Regression tests for Codex impl2 review findings 12-15 (memory scope, lineage, correction, erasure)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_agent.memory import (
    CANON,
    SIMILARITY_REVIEW_TARGET,
    ClaimType,
    ErasureInProgressError,
    Kind,
    MemoryStore,
    Provenance,
    ScopeViolationError,
    Status,
    private_scope,
    public_scope,
)
from live_agent.memory_bridge import DEFAULT_PURGE_TARGETS, MemoryBridge
from live_agent.types import Utterance

U, V, S = "alice", "bob", "stream1"


class Clock:
    def __init__(self) -> None:
        self.t = 1_000_000.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


@pytest.fixture
def mem():
    m = MemoryStore(":memory:", clock=Clock())
    yield m
    m.close()


def bridge(mem: MemoryStore, mode: str | None = "private", **kw) -> MemoryBridge:
    return MemoryBridge(":memory:", user_id=U, stream_id=S, session_id="sess", store=mem, mode=mode, **kw)


_n = 0


def utt(text: str, scope: str = "private", speaker: str = "user", session: str = "sess") -> Utterance:
    global _n
    _n += 1
    return Utterance(uid=f"x{_n}", speaker=speaker, text=text, t_end=float(_n), session_id=session, scope=scope)


# ---------------------------------------------------------------- finding 12: write scope


@pytest.mark.parametrize("claimed", ["canon", "public", public_scope(S), private_scope(V)])
def test_utterance_scope_field_is_ignored(mem, claimed):
    r = mem.ingest_user_utterance(utt("我妹妹住在巴黎", scope=claimed), user_id=U, stream_id=S, mode="private")
    assert r.episode.scope == private_scope(U) and r.facts[0].scope == private_scope(U)
    assert mem.stats["utterance_scope_ignored"] == 1
    assert mem.retrieve("巴黎", "public", stream_id=S).hits == []
    # no mode given: fail closed to private, still ignoring the utterance field
    r2 = mem.ingest_user_utterance(utt("I like cats", scope=claimed), user_id=U, stream_id=S)
    assert r2.facts[0].scope == private_scope(U)


def test_session_mode_decides_scope_and_canon_refused(mem):
    r = mem.ingest_user_utterance(utt("I like tea", scope="private"), user_id=U, stream_id=S, mode="public")
    assert r.facts[0].scope == public_scope(S)
    with pytest.raises(ScopeViolationError):
        mem.ingest_user_utterance(utt("I like tea"), user_id=U, stream_id=S, mode="canon")


def test_user_origin_records_never_canon(mem):
    for kind, claim, speaker, uid in [
        (Kind.USER_FACT, ClaimType.OWN_ASSERTION, "user", U),
        (Kind.EPISODE, ClaimType.OWN_ASSERTION, "user", U),
        (Kind.LEDGER, ClaimType.SYSTEM_OBSERVATION, "viewer:v1", ""),
        (Kind.LEDGER, ClaimType.SYSTEM_OBSERVATION, "system", U),
        (Kind.SUMMARY, ClaimType.SYSTEM_OBSERVATION, "system", ""),
    ]:
        with pytest.raises(ScopeViolationError):
            mem.add_record(kind, CANON, "x", claim, Provenance(speaker=speaker, user_id=uid))
    with pytest.raises(ScopeViolationError):
        mem.record_generated_event("hello", "s", CANON)


def test_learned_procedure_needs_lineage_and_inherits_most_restrictive_scope(mem):
    ep = mem.ingest_user_utterance(utt("wave at my sister in Paris"), user_id=U, stream_id=S).episode
    pub = mem.ingest_viewer_chat("nice wave", "v1", S)
    anchor = mem.add_ledger("persona waves with the right hand", CANON, canonical=True)
    with pytest.raises(ValueError):
        mem.add_procedure("wave works", "success")  # no source lineage
    p = mem.add_procedure("wave works", "success", derived_from=[ep.id, pub.id, anchor.id])
    assert p.scope == private_scope(U) and private_scope(U) in p.source_scopes
    assert p.provenance.user_id == U
    assert p.id not in {h.record.id for h in mem.retrieve("wave works", "public", stream_id=S, k=50)}
    for bad in (CANON, public_scope(S)):
        with pytest.raises(ScopeViolationError):
            mem.add_procedure("wave works", "success", derived_from=[ep.id], scope=bad)
    q = mem.add_procedure("wave in public works", "success", derived_from=[pub.id, anchor.id])
    assert q.scope == public_scope(S)
    with pytest.raises(ScopeViolationError):
        mem.add_procedure("wave", "success", derived_from=[pub.id], scope=CANON)
    c = mem.add_procedure("canon-derived", "success", derived_from=[anchor.id])
    assert c.scope == CANON and c.source_scopes == {CANON}
    other = mem.ingest_user_utterance(utt("I like jazz"), user_id=V, stream_id=S).episode
    with pytest.raises(ScopeViolationError):
        mem.add_procedure("mix", "success", derived_from=[ep.id, other.id])
    with pytest.raises(ValueError):
        mem.add_procedure("curated with sources", "success", derived_from=[anchor.id], curated=True)


def test_bridge_derives_scope_from_session_not_utterance(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("我妹妹住在巴黎", scope="canon"))
    b.on_user_utterance(utt("I like cats", scope=public_scope(S)))
    scopes = {r[0] for r in mem.db.execute("SELECT scope FROM records")}
    assert scopes == {private_scope(U)}


def test_bridge_mode_required_and_immutable(mem):
    with pytest.raises(TypeError):
        MemoryBridge(":memory:", user_id=U, stream_id=S, session_id="s", store=mem)  # no mode
    for bad in (None, "canon", ""):
        with pytest.raises(ValueError):
            bridge(mem, mode=bad)
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("我妹妹住在巴黎"))
    with pytest.raises(ScopeViolationError):  # a private session can never become public
        b.recall("巴黎", mode="public")
    with pytest.raises(ScopeViolationError):
        b.on_persona_line("她妹妹住在巴黎", session_id="sess", scope="public", lineage="none")
    assert b.mode == "private" and b.write_scope == private_scope(U)
    assert mem.db.execute("SELECT count(*) FROM records WHERE scope LIKE 'public:%'").fetchone()[0] == 0


# ---------------------------------------------------------------- finding 13: lineage of persona output


def test_persona_line_lineage_from_recall(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("我妹妹住在巴黎"))
    hits = b.recall_hits("妹妹 巴黎", mode="private")
    assert hits and all(h.id and h.rendered.endswith(h.text) for h in hits)
    assert b.recall("妹妹 巴黎", mode="private") == [h.rendered for h in hits]
    fact = next(h for h in hits if h.tags["kind"] == "user_fact")
    g = b.on_persona_line("你妹妹在巴黎？", session_id="sess", scope="private", source_ids=[fact.id],
                          lineage="complete")
    assert g.derived_from == (fact.id,) and g.source_scopes == {private_scope(U)}
    assert g.meta["lineage"] == "complete" and g.scope == private_scope(U)
    # unknown lineage (default, even with ids): linked to every memory recalled / turn ingested
    g2 = b.on_persona_line("巴黎很美", session_id="sess", scope="private", source_ids=[])
    ingested = set(mem._ids("SELECT id FROM records WHERE kind IN ('episode', 'user_fact')"))
    assert set(g2.derived_from) == {h.id for h in hits} | ingested
    assert g2.meta["lineage"] == "session_superset" and g2.scope == private_scope(U)
    # the lineage makes erasure cascade to both lines
    rep = b.forget("巴黎")
    assert mem.get(g.id) is None and mem.get(g2.id) is None and g.id in rep.deleted_ids


def test_public_persona_line_requires_recall_token(mem):
    priv = bridge(mem, mode="private")
    priv.on_user_utterance(utt("我妹妹住在巴黎"))
    fact_id = mem._ids("SELECT id FROM records WHERE kind = 'user_fact'")[0]
    priv_token = priv.recall_hits("妹妹 巴黎", mode="private").recall_id
    pub = bridge(mem, mode="public")
    before = mem.db.execute("SELECT count(*) FROM records").fetchone()[0]
    # caller assertions without a token are never enough in public
    for kw in ({}, {"source_ids": []}, {"lineage": "none"}, {"source_ids": [], "lineage": "complete"},
               {"source_ids": [fact_id], "lineage": "complete"}):
        assert pub.on_persona_line("大家好", session_id="live", scope="public", **kw) is None
        assert "recall token" in pub.scope_violations[-1]["reason"]
    # a token not issued by this bridge session (forged / from the private session) is refused
    for tok in ("recall-forged", priv_token):
        assert pub.on_persona_line("她妹妹住在巴黎", session_id="live", scope="public", recall_id=tok) is None
        assert "unknown recall token" in pub.scope_violations[-1]["reason"]
    assert mem.db.execute("SELECT count(*) FROM records").fetchone()[0] == before
    # direct store API fails closed as well
    for kw in ({}, {"derived_from": None}, {"derived_from": []}, {"derived_from": [], "lineage": "unknown"},
               {"derived_from": [fact_id], "lineage": "complete"}):
        with pytest.raises(ScopeViolationError):
            mem.record_generated_event("x", "live", public_scope(S), **kw)
    with pytest.raises(ScopeViolationError):
        mem.add_record(Kind.GENERATED_EVENT, public_scope(S), "x", ClaimType.SYSTEM_OBSERVATION,
                       Provenance(speaker="persona"))
    with pytest.raises(ValueError):
        mem.record_generated_event("x", "live", public_scope(S), derived_from=[fact_id], lineage="none")
    # a valid token: lineage is exactly what the bridge handed out, computed by the bridge
    mem.ingest_viewer_chat("大家好呀主播", "v1", S)
    res = pub.recall_hits("大家好", mode="public")
    assert res.ids and res.recall_id
    g = pub.on_persona_line("欢迎大家", session_id="live", scope="public", recall_id=res.recall_id)
    assert set(g.derived_from) == set(res.ids) and g.meta["lineage"] == "complete"
    assert g.scope == public_scope(S) and g.source_scopes <= {public_scope(S), CANON}
    # source_ids must be a subset of what was handed out under the token
    assert pub.on_persona_line("x", session_id="live", scope="public", recall_id=res.recall_id,
                               source_ids=[fact_id]) is None
    # a decision without recall gets an empty token -> lineage "none"
    g0 = pub.on_persona_line("好的，忘掉了", session_id="live", scope="public", recall_id=pub.no_recall())
    assert g0.derived_from == () and g0.meta["lineage"] == "none"
    # a persona utterance ingested in a public session has unknown lineage -> refused
    with pytest.raises(ScopeViolationError):
        mem.ingest_user_utterance(utt("hi", speaker="persona"), user_id=U, stream_id=S, mode="public")


def test_recall_token_works_in_private_and_rejects_erased_sources(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("I work at Acme"))
    res = b.recall_hits("Acme", mode="private")
    g = b.on_persona_line("How is Acme?", session_id="sess", scope="private", recall_id=res.recall_id)
    assert set(g.derived_from) == set(res.ids) and g.scope == private_scope(U)
    b.forget("Acme")
    assert b.on_persona_line("Acme again", session_id="sess", scope="private", recall_id=res.recall_id) is None
    assert "erased" in b.scope_violations[-1]["reason"]


def test_persona_line_with_erased_explicit_source_not_recorded(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("I work at Acme"))
    (hit,) = [h for h in b.recall_hits("Acme", mode="private") if h.tags["kind"] == "user_fact"]
    b.forget("Acme")
    assert b.on_persona_line("How is Acme?", session_id="sess", scope="private", source_ids=[hit.id],
                             lineage="complete") is None
    assert "erased" in b.scope_violations[-1]["reason"]
    assert b.on_persona_line("How are you?", session_id="sess", scope="private").derived_from == ()


# ---------------------------------------------------------------- finding 14: consolidation / confirmation


def test_consolidate_excludes_stale_and_retracted_persona_lines(mem):
    (old,) = mem.ingest_user_utterance(utt("我住在巴黎", session="k"), user_id=U).facts
    mem.ingest_user_utterance(utt("我喜欢猫", session="k"), user_id=U)
    linked = mem.record_generated_event("巴黎的秋天很美", "k", private_scope(U), derived_from=[old.id])
    unlinked = mem.record_generated_event("你在巴黎住得开心吗", "k", private_scope(U))  # lineage unknown
    ok = mem.record_generated_event("猫咪真可爱", "k", private_scope(U))
    mem.ingest_user_utterance(utt("不对，我搬到了东京", session="k"), user_id=U)
    assert mem.get(linked.id).status == Status.STALE
    s = mem.consolidate("k")
    assert linked.id not in s.derived_from and unlinked.id not in s.derived_from
    assert ok.id in s.derived_from and "巴黎" not in s.text and "东京" in s.text


def test_confirm_requires_user_turn_and_links_it(mem):
    (f,) = mem.ingest_user_utterance(utt("我住在巴黎"), user_id=U).facts
    b = mem.record_inference("user speaks French", user_id=U, derived_from=[f.id],
                             subject="user", predicate="speaks", value="French")
    q = mem.ingest_user_utterance(utt("我会说法语吗？"), user_id=U).episode
    other = mem.ingest_user_utterance(utt("yes"), user_id=V).episode
    with pytest.raises(ValueError):
        mem.confirm(b.id, q.id)  # a question does not confirm
    with pytest.raises(ValueError):
        mem.confirm(b.id, other.id)  # another user's turn does not confirm
    gen = mem.record_generated_event("yes", "sess", private_scope(U))
    with pytest.raises(ValueError):
        mem.confirm(b.id, gen.id)  # persona output does not confirm
    assert mem.get(b.id).status == Status.PENDING
    # pending echo fact: optional confirmation episode is linked into its lineage
    mem.record_generated_event("你最爱喝龙井", "sess", private_scope(U))
    (e,) = mem.ingest_user_utterance(utt("我最爱喝龙井"), user_id=U).facts
    yes = mem.ingest_user_utterance(utt("是的，我最爱喝龙井。"), user_id=U).episode
    c = mem.confirm(e.id, yes.id)
    assert c.id == e.id and yes.id in c.derived_from and c.meta["confirmed_by"] == yes.id


# ---------------------------------------------------------------- finding 15: erasure acknowledgements


def test_bridge_forget_is_incomplete_until_every_target_acks(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("I work at Acme"))
    rep = b.forget("Acme")
    assert rep.deleted_ids and rep.acks["memory_db"].ok and rep.acks["bridge_callbacks"].ok
    assert not rep.complete and set(rep.pending_targets) == set(DEFAULT_PURGE_TARGETS)
    for t in DEFAULT_PURGE_TARGETS[:-1]:
        assert b.acknowledge_erasure(rep, t) is False
    assert b.acknowledge_erasure(rep, DEFAULT_PURGE_TARGETS[-1], detail="no recordings") is True


def test_callback_without_ack_or_with_error_fails_closed(mem):
    b = bridge(mem, mode="private", required_purge_targets=())
    b.on_user_utterance(utt("I work at Acme"))
    b.on_erasure.append(lambda r: None)  # a notification that never acks
    rep = b.forget("Acme")
    assert not rep.complete and rep.pending_targets == ["bridge_callbacks"]
    b.on_erasure[:] = [lambda r: 1 / 0]
    b.on_user_utterance(utt("I work at Globex"))
    rep2 = b.forget("Globex")
    assert not rep2.complete and rep2.hook_errors and "ZeroDivisionError" in rep2.hook_errors[0]
    assert all(mem.get(i) is None for i in rep2.deleted_ids)  # deletion is never rolled back
    b.on_erasure[:] = [lambda r: "flushed"]
    b.on_user_utterance(utt("I work at Initech"))
    assert b.forget("Initech").complete


def test_store_verification_failure_blocks_memory_db_ack(mem, monkeypatch):
    (f,) = mem.ingest_user_utterance(utt("I work at Acme"), user_id=U).facts
    real = mem.verify_erasure

    def residue(report, **kw):
        v = real(report, **kw)
        v.term_hits.append("records:ghost")
        return v

    monkeypatch.setattr(mem, "verify_erasure", residue)
    rep = mem.forget(f.id, U)
    assert not rep.acks["memory_db"].ok and not rep.complete


def test_forget_scrubs_id_references_in_surviving_records(mem):
    (a,) = mem.ingest_user_utterance(utt("我住在巴黎"), user_id=U).facts
    (b,) = mem.ingest_user_utterance(utt("不对，我搬到了东京"), user_id=U).facts
    assert b.meta["supersedes"] == [a.id]
    rep = mem.forget(a.id, U)
    assert mem.get(b.id) is not None and mem.get(b.id).meta["supersedes"] == []
    v = mem.verify_erasure(rep)
    assert v.ok and not v.surviving


# ---------------------------------------------------------------- round 2: R1-14 confirmation binding


def test_confirmation_must_bind_to_the_proposition(mem):
    (f,) = mem.ingest_user_utterance(utt("我住在巴黎", session="c"), user_id=U).facts
    b = mem.record_inference("user speaks French", user_id=U, derived_from=[f.id],
                             subject="user", predicate="speaks", value="French", session_id="c")
    unrelated = mem.ingest_user_utterance(utt("I like cats", session="c"), user_id=U).episode
    with pytest.raises(ValueError):
        mem.confirm(b.id, unrelated.id)  # unrelated turn by the right user
    neg = mem.ingest_user_utterance(utt("No, I don't speak French", session="c"), user_id=U).episode
    with pytest.raises(ValueError):
        mem.confirm(b.id, neg.id)  # mentions the value but denies it
    # rule (b): an affirmative answer that is the first user turn after the persona's question
    q = mem.record_generated_event("你会说法语吗？", "c", private_scope(U), derived_from=[b.id], lineage="complete")
    yes = mem.ingest_user_utterance(utt("是的", session="c"), user_id=U).episode
    assert mem.get(b.id).status == Status.PENDING
    with pytest.raises(ValueError):
        mem.confirm(b.id, yes.id)  # a bare "yes" without the question does not bind
    fact = mem.confirm(b.id, yes.id, question_id=q.id)
    assert fact.value == "French" and mem.get(b.id).meta["confirmed_rule"] == "answer"


def test_confirmation_answer_must_follow_the_question_directly(mem):
    b = mem.record_inference("user speaks French", user_id=U, derived_from=[], subject="user",
                             predicate="speaks", value="French", session_id="c")
    q = mem.record_generated_event("你会说法语吗？", "c", private_scope(U), derived_from=[b.id], lineage="complete")
    mem.ingest_user_utterance(utt("我喜欢猫", session="c"), user_id=U)
    late_yes = mem.ingest_user_utterance(utt("对", session="c"), user_id=U).episode
    with pytest.raises(ValueError):
        mem.confirm(b.id, late_yes.id, question_id=q.id)
    other_q = mem.record_generated_event("你喜欢猫吗？", "c", private_scope(U), lineage="none")
    with pytest.raises(ValueError):
        mem.confirm(b.id, late_yes.id, question_id=other_q.id)  # question not about this inference
    stated = mem.ingest_user_utterance(utt("对，我会说French", session="c"), user_id=U).episode
    assert mem.confirm(b.id, stated.id).value == "French"  # rule (a): the turn states the value


# ---------------------------------------------------------------- round 2: R1-15 similarity sweep


def test_forget_sweeps_unlinked_paraphrases(mem):
    (f,) = mem.ingest_user_utterance(utt("My sister lives in Paris.", session="p"), user_id=U).facts
    # persona paraphrase with no lineage and without the literal term "Paris"
    para = mem.record_generated_event("So your sister lives in France", "p", private_scope(U))
    unrelated = mem.record_generated_event("Shall we make tea?", "p", private_scope(U))
    rep = mem.forget(f.id, U)
    assert para.id in rep.swept_ids and mem.get(para.id) is None
    assert mem.get(unrelated.id) is not None
    assert rep.acks["memory_db"].ok and rep.complete


def test_forget_reports_similar_user_facts_for_review(mem):
    (a,) = mem.ingest_user_utterance(utt("I work at Acme"), user_id=U).facts
    r = mem.ingest_user_utterance(utt("I work at Globex too"), user_id=U)  # similar turn, other value
    (g,) = r.facts
    rep = mem.forget(a.id, U)
    # user-origin records are never silently deleted by similarity: kept and reported
    assert mem.get(g.id) is not None and mem.get(r.episode.id) is not None
    assert r.episode.id in rep.review_ids and SIMILARITY_REVIEW_TARGET in rep.pending_targets
    assert not rep.complete and f"records:{r.episode.id}" in rep.verification.review
    rep.acknowledge(SIMILARITY_REVIEW_TARGET, detail="user kept Globex")
    assert rep.complete


def test_verify_erased_flags_surviving_similar_artifact(mem):
    (f,) = mem.ingest_user_utterance(utt("My sister lives in Paris."), user_id=U).facts
    rep = mem.forget(f.id, U)
    assert mem.verify_erasure(rep).ok
    # an artifact written after the erasure (e.g. a stale cache replaying the line)
    late = mem.record_generated_event("your sister lives in paris", "p", private_scope(U))
    v = mem.verify_erasure(rep)
    assert not v.ok and f"records:{late.id}" in v.similar


# ---------------------------------------------------------------- round 2: NEW-10 atomic correction


def test_correction_is_atomic(mem, monkeypatch):
    (old,) = mem.ingest_user_utterance(utt("I work at Acme"), user_id=U).facts
    gen = mem.record_generated_event("Acme sounds fun", "sess", private_scope(U), derived_from=[old.id],
                                     lineage="complete")
    fired = []
    mem.stale_hooks.append(fired.append)

    def boom(texts):
        raise RuntimeError("embedder down")

    monkeypatch.setattr(mem.embedder, "embed", boom)
    with pytest.raises(RuntimeError):
        mem.correct(old.id, "Globex")
    with pytest.raises(RuntimeError):
        mem.ingest_user_utterance(utt("不对，我在Globex工作"), user_id=U)
    monkeypatch.undo()
    # nothing half-applied: old fact current, descendant not stale, no hook fired
    assert mem.get(old.id).status == Status.ACTIVE and mem.get(old.id).valid_to is None
    assert mem.get(gen.id).status == Status.ACTIVE and fired == []
    assert mem.resolve(U, "user", "works_at").value == "Acme"
    new = mem.correct(old.id, "Globex")
    assert mem.get(old.id).status == Status.SUPERSEDED and mem.get(gen.id).status == Status.STALE
    assert mem.resolve(U, "user", "works_at").record.id == new.id
    assert len(fired) == 1 and fired[0][0].id == gen.id  # hooks run once, after the commit


def test_sweep_deletes_similar_turns_that_back_no_fact(mem):
    (f,) = mem.ingest_user_utterance(utt("我妹妹住在杭州"), user_id=U).facts
    req = mem.ingest_user_utterance(utt("忘掉我妹妹住哪"), user_id=U)  # the forget request itself
    assert req.facts == []
    rep = mem.forget("杭州", U)
    assert mem.get(req.episode.id) is None and req.episode.id in rep.swept_ids
    assert rep.review_ids == [] and rep.complete and mem.get(f.id) is None


# ---------------------------------------------------------------- round 3: physical erasure (WAL)


def _wal_store(tmp_path):
    return MemoryStore(tmp_path / "wal.sqlite", clock=Clock(), journal_mode="wal")


def test_wal_erasure_is_physical_and_verified(tmp_path):
    mem = _wal_store(tmp_path)
    assert mem.journal_mode == "wal"
    assert mem.db.execute("PRAGMA secure_delete").fetchone()[0] == 1
    (f,) = mem.ingest_user_utterance(utt("我妹妹住在巴黎"), user_id=U).facts
    mem.ingest_user_utterance(utt("我喜欢猫"), user_id=U)
    wal = tmp_path / "wal.sqlite-wal"
    assert wal.exists() and "巴黎".encode() in wal.read_bytes()  # the WAL holds the text before erasure
    rep = mem.forget("巴黎", U)
    assert rep.acks["memory_db"].ok and rep.complete
    assert not wal.exists() or wal.stat().st_size == 0
    for p in tmp_path.iterdir():
        assert "巴黎".encode() not in p.read_bytes(), p
    assert mem.verify_erased("巴黎", U, raw_file=True).ok
    assert mem.get(f.id) is None
    mem.close()


def test_wal_residue_blocks_memory_db_ack(tmp_path, monkeypatch):
    mem = _wal_store(tmp_path)
    mem.ingest_user_utterance(utt("我妹妹住在巴黎"), user_id=U)
    monkeypatch.setattr(mem, "_physical_purge", lambda: "")  # pretend the purge ran but it did not
    rep = mem.forget("巴黎", U)
    assert not rep.acks["memory_db"].ok and not rep.complete
    assert any(h.startswith("file:") for h in rep.verification.file_hits)
    mem.close()


def test_wal_checkpoint_blocked_by_reader_fails_closed(tmp_path):
    import sqlite3

    mem = _wal_store(tmp_path)
    mem.ingest_user_utterance(utt("我妹妹住在巴黎"), user_id=U)
    reader = sqlite3.connect(tmp_path / "wal.sqlite")
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM records").fetchone()  # holds a WAL read snapshot
    rep = mem.forget("巴黎", U)
    assert not rep.acks["memory_db"].ok and not rep.complete
    assert mem._ids("SELECT id FROM records WHERE text LIKE '%巴黎%'") == []  # never un-deleted
    reader.rollback()
    reader.close()
    mem.close()


# ---------------------------------------------------------------- round 4


def test_value_mention_alone_does_not_confirm(mem):
    mem.record_generated_event("你妹妹住在北京吧", "sess", private_scope(U))
    (e,) = mem.ingest_user_utterance(utt("我妹妹住在北京"), user_id=U).facts
    assert e.status == Status.PENDING and e.echo
    for text in ("I visited 北京 last year", "我去过北京", "我住在北京"):  # value only / wrong subject
        turn = mem.ingest_user_utterance(utt(text), user_id=U).episode
        with pytest.raises(ValueError):
            mem.confirm(e.id, turn.id)
    ok = mem.ingest_user_utterance(utt("对，我妹妹确实住北京"), user_id=U).episode
    assert mem.confirm(e.id, ok.id).status == Status.ACTIVE
    # English: subject + predicate + value
    b = mem.record_inference("sister works at Acme", user_id=U, derived_from=[], subject="user/sister",
                             predicate="works_at", value="Acme")
    for text in ("Acme is great", "I work at Acme"):
        with pytest.raises(ValueError):
            mem.confirm(b.id, mem.ingest_user_utterance(utt(text), user_id=U).episode.id)
    yes = mem.ingest_user_utterance(utt("Yes, my sister works at Acme"), user_id=U).episode
    assert mem.confirm(b.id, yes.id).value == "Acme"


def test_public_empty_token_refused_when_private_context_possible(mem):
    pub = bridge(mem, mode="public")
    assert pub.private_context_risk() == []
    ok = pub.on_persona_line("大家好", session_id="live", scope="public", recall_id=pub.no_recall())
    assert ok is not None and ok.meta["lineage"] == "none"
    # the same user has a private conversation meanwhile: the responder may carry it
    priv = bridge(mem, mode="private")
    priv.on_user_utterance(utt("我妹妹住在巴黎"))
    assert pub.private_context_risk()
    assert pub.on_persona_line("她妹妹住在巴黎", session_id="live", scope="public",
                               recall_id=pub.no_recall()) is None
    assert "private context" in pub.scope_violations[-1]["reason"]
    # an explicit isolated-context token (no memory notes in the responder context) is accepted
    g = pub.on_persona_line("欢迎", session_id="live", scope="public",
                            recall_id=pub.no_recall(isolated_context=True))
    assert g is not None and g.scope == public_scope(S)
    # tokens with public hits carry their own verified lineage and are unaffected
    mem.ingest_viewer_chat("大家好呀", "v1", S)
    res = pub.recall_hits("大家好", mode="public")
    assert pub.on_persona_line("嗨", session_id="live", scope="public", recall_id=res.recall_id) is not None
    # a private bridge that recalled private data reports the risk too
    priv.recall_hits("巴黎", mode="private")
    assert any(r.startswith("private:") for r in priv.private_context_risk())


@pytest.mark.parametrize("journal_mode", ["persist", "truncate", "delete", "wal"])
def test_erasure_by_id_is_physical_in_every_journal_mode(tmp_path, journal_mode):
    mem = MemoryStore(tmp_path / "j.sqlite", clock=Clock(), journal_mode=journal_mode)
    ep = mem.ingest_user_utterance(utt("今天和小芳去了西湖边的咖啡馆"), user_id=U).episode  # no fact, no term
    mem.ingest_user_utterance(utt("我喜欢猫"), user_id=U)
    rep = mem.forget(ep.id, U)  # by id: terms are empty
    assert rep.terms == set() and ep.text in rep.erased_texts
    assert rep.acks["memory_db"].ok, rep.acks["memory_db"].detail
    journal = tmp_path / "j.sqlite-journal"
    assert not journal.exists() or journal.stat().st_size == 0
    for p in tmp_path.iterdir():
        assert "西湖边的咖啡馆".encode() not in p.read_bytes(), p
    mem.close()


def test_raw_check_searches_erased_text_not_only_terms(tmp_path, monkeypatch):
    mem = MemoryStore(tmp_path / "p.sqlite", clock=Clock(), journal_mode="persist")
    ep = mem.ingest_user_utterance(utt("今天和小芳去了西湖边的咖啡馆"), user_id=U).episode
    monkeypatch.setattr(mem, "_physical_purge", lambda: "")  # the bytes are left behind
    rep = mem.forget(ep.id, U)
    assert rep.terms == set()
    assert not rep.acks["memory_db"].ok and any("erased text" in h for h in rep.verification.file_hits)
    mem.close()


# ---------------------------------------------------------------- round 5


def test_confirmation_cues_must_share_one_clause(mem):
    mem.record_generated_event("你妹妹住在北京吧", "sess", private_scope(U))
    (e,) = mem.ingest_user_utterance(utt("我妹妹住在北京"), user_id=U).facts
    assert e.status == Status.PENDING
    for text in ("我住在北京，我妹妹住在上海", "我住在北京但我妹妹住在上海", "I live in 北京 and my sister lives in Shanghai"):
        turn = mem.ingest_user_utterance(utt(text), user_id=U).episode
        with pytest.raises(ValueError):
            mem.confirm(e.id, turn.id)
    ok = mem.ingest_user_utterance(utt("对。我妹妹住在北京，没错"), user_id=U).episode
    assert mem.confirm(e.id, ok.id).status == Status.ACTIVE


def _run(coro):
    import asyncio

    return asyncio.run(coro)


@pytest.mark.parametrize("journal_mode", ["wal", "persist", "delete"])
def test_forget_async_same_semantics_off_thread(tmp_path, journal_mode):
    import asyncio
    import threading

    mem = MemoryStore(tmp_path / "a.sqlite", clock=Clock(), journal_mode=journal_mode)
    b = bridge(mem, mode="private", required_purge_targets=("generator_state",))
    b.on_user_utterance(utt("我妹妹住在巴黎"))
    b.on_user_utterance(utt("我喜欢猫"))
    hook_threads = []

    def kv(report):
        hook_threads.append(threading.get_ident())
        return True

    mem.register_purge_target("kv", kv)
    real = mem._forget_in_worker
    seen = {}
    go = threading.Event()

    def spy(*a):
        seen["thread"] = threading.get_ident()
        assert go.wait(10)  # hold the worker until the main thread has probed the blocked state
        return real(*a)

    mem._forget_in_worker = spy

    async def main():
        task = asyncio.create_task(b.forget_async("巴黎"))
        await asyncio.sleep(0)
        # while the worker runs, the store is blocked and the bridge degrades safely
        while not seen:
            await asyncio.sleep(0.001)
        assert mem.erasing
        assert b.recall_hits("猫", mode="private") == []
        assert b.on_persona_line("x", session_id="sess", scope="private") is None
        b.on_user_utterance(utt("我喜欢狗"))  # deferred, ingested afterwards
        with pytest.raises(ErasureInProgressError):
            mem.retrieve("猫", "private", user_id=U)
        go.set()
        return await task

    main_thread = threading.get_ident()
    rep = _run(main())
    assert seen["thread"] != main_thread and hook_threads == [main_thread]
    assert rep.acks["memory_db"].ok and rep.acks["kv"].ok and rep.pending_targets == ["generator_state"]
    assert b.acknowledge_erasure(rep, "generator_state")
    assert mem.verify_erasure(rep, raw_file=True).ok
    for p in tmp_path.iterdir():
        assert "巴黎".encode() not in p.read_bytes(), p
    texts = {r[0] for r in mem.db.execute("SELECT text FROM records WHERE kind = 'episode'")}
    assert {"我喜欢猫", "我喜欢狗"} <= texts and b._deferred == []
    assert not mem.erasing
    mem.close()


def test_forget_async_in_memory_runs_inline(mem):
    b = bridge(mem, mode="private", required_purge_targets=())
    b.on_user_utterance(utt("I work at Acme"))
    rep = _run(b.forget_async("Acme"))
    assert rep.complete and rep.deleted_ids and mem.verify_erasure(rep).ok


# ---------------------------------------------------------------- round 6


def test_viewer_events_only_in_public_sessions(mem):
    before = mem.db.execute("SELECT count(*) FROM records").fetchone()[0]
    for mode in (None, "private"):
        with pytest.raises(ScopeViolationError):
            mem.ingest_user_utterance(utt("I live in Tokyo", speaker="viewer:v1"), user_id=U, stream_id=S, mode=mode)
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("我住在东京", speaker="viewer:v1", scope="public"))
    assert "viewer events" in b.scope_violations[-1]["reason"]
    assert mem.db.execute("SELECT count(*) FROM records").fetchone()[0] == before
    assert mem.db.execute("SELECT count(*) FROM records WHERE scope LIKE 'public:%'").fetchone()[0] == 0
    pub = bridge(mem, mode="public")
    pub.on_user_utterance(utt("主播好", speaker="viewer:v1"))
    (ep,) = mem._load(mem._ids("SELECT id FROM records WHERE kind = 'episode'"))
    assert ep.scope == public_scope(S) and ep.claim_type == ClaimType.VIEWER_CLAIM


def test_confirmation_subject_must_be_the_clause_subject(mem):
    mem.record_generated_event("你住在北京吧", "sess", private_scope(U))
    (e,) = mem.ingest_user_utterance(utt("我住在北京"), user_id=U).facts
    assert e.status == Status.PENDING and e.subject == f"user:{U}"
    for text in ("我妈妈住在北京", "我不住在北京", "我没住在北京", "他住在北京", "My mom lives in 北京",
                 "I don't live in 北京", "I no longer live in 北京"):
        turn = mem.ingest_user_utterance(utt(text, session="c"), user_id=U).episode
        with pytest.raises(ValueError):
            mem.confirm(e.id, turn.id)
    ok = mem.ingest_user_utterance(utt("对，我住在北京", session="c"), user_id=U).episode
    assert mem.confirm(e.id, ok.id).status == Status.ACTIVE


# ---------------------------------------------------------------- round 8: #19 ledger lineage


def test_learned_ledger_needs_lineage_and_derives_scope(mem):
    ep = mem.ingest_user_utterance(utt("我妹妹住在巴黎"), user_id=U).episode
    pub = mem.ingest_viewer_chat("主播换了发簪", "v1", S)
    anchor = mem.add_ledger("persona wears a jade hairpin", CANON, canonical=True)
    with pytest.raises(ValueError):
        mem.add_ledger("postcard promised", public_scope(S))  # no lineage, not curated
    with pytest.raises(ValueError):
        mem.add_ledger("postcard promised", curated=True)  # curated needs an explicit scope
    led = mem.add_ledger("persona promised a postcard", derived_from=[ep.id, pub.id])
    assert led.scope == private_scope(U) and led.provenance.user_id == U
    with pytest.raises(ScopeViolationError):
        mem.add_ledger("persona promised a postcard", public_scope(S), derived_from=[ep.id])
    p = mem.add_ledger("hairpin moved to the left", derived_from=[pub.id, anchor.id])
    assert p.scope == public_scope(S)
    with pytest.raises(ValueError):
        mem.add_ledger("from canon only", derived_from=[anchor.id])  # needs an explicit scope
    q = mem.add_ledger("from canon only", public_scope(S), derived_from=[anchor.id])
    assert q.source_scopes == {public_scope(S), CANON}
    c = mem.add_ledger("teacup on the left", public_scope(S), curated=True)
    assert c.meta["curated"] and c.provenance.speaker == "operator"


# ---------------------------------------------------------------- round 8: #20 pending-erasure receipts


def _receipt_rows(mem):
    return mem.db.execute("SELECT * FROM erasure_receipts").fetchall()


def test_failed_purge_leaves_receipt_and_retry_by_id_resumes(tmp_path):
    mem = MemoryStore(tmp_path / "r.sqlite", clock=Clock(), journal_mode="wal")
    (f,) = mem.ingest_user_utterance(utt("我妹妹住在巴黎", session="s9"), user_id=U).facts
    calls = {"rec": 0, "kv": 0}
    state = {"rec_ok": False}

    def recordings(report):
        calls["rec"] += 1
        if not state["rec_ok"]:
            raise RuntimeError("storage offline")
        assert "巴黎" in report.terms and not report.content_lost  # content still in memory
        return "deleted"

    def kv(report):
        calls["kv"] += 1
        return True

    mem.register_purge_target("recordings", recordings)
    mem.register_purge_target("kv", kv)
    rep = mem.forget("巴黎", U)
    assert not rep.complete and rep.pending_targets == ["recordings"] and rep.receipt_id
    (row,) = _receipt_rows(mem)
    persisted = " ".join(str(x) for x in row)
    assert "巴黎" not in persisted and "妹妹" not in persisted  # no erased content on disk
    assert f.id in json.loads(row["deleted_ids"]) and json.loads(row["sessions"]) == ["s9"]
    assert mem.pending_erasures(U)[0]["pending"] == ["recordings"]
    for p in tmp_path.iterdir():
        assert "巴黎".encode() not in p.read_bytes(), p
    # retry by record id: resumes the receipt instead of an empty new erasure
    state["rec_ok"] = True
    rep2 = mem.forget(f.id, U)
    assert rep2.receipt_id == rep.receipt_id and rep2.complete and f.id in rep2.deleted_ids
    assert calls == {"rec": 2, "kv": 1}  # acked targets are not re-run
    assert _receipt_rows(mem) == [] and mem.pending_erasures(U) == []
    mem.close()


def test_retry_by_term_and_late_ack_resume_receipt(mem):
    b = bridge(mem, mode="private", required_purge_targets=("recordings",))
    b.on_user_utterance(utt("I work at Acme"))
    rep = b.forget("Acme")
    assert not rep.complete and len(b.pending_erasures()) == 1
    again = b.forget("Acme")  # nothing matches any more: resumes the pending receipt
    assert again.receipt_id == rep.receipt_id and not again.complete
    assert b.acknowledge_erasure(again, "recordings", detail="deleted")  # persisted on ack
    assert b.pending_erasures() == [] and _receipt_rows(mem) == []


def test_receipt_survives_restart_with_content_lost(tmp_path):
    from live_agent.memory import store as store_mod

    path = tmp_path / "k.sqlite"
    mem = MemoryStore(path, clock=Clock())
    mem.ingest_user_utterance(utt("I work at Acme", session="s7"), user_id=U)
    rep = mem.forget("Acme", U, require=["generator_state"])
    rid = rep.receipt_id
    mem.close()
    store_mod._RECEIPT_CONTENT.clear()  # process restart: in-memory content is gone
    mem2 = MemoryStore(path, clock=Clock())
    (p,) = mem2.pending_erasures(U)
    assert p["receipt_id"] == rid and p["content_lost"] and p["sessions"] == ["s7"]
    with pytest.raises(PermissionError):
        mem2.forget(rid, V, resume=rid)
    seen = []
    mem2.register_purge_target("generator_state", lambda r: seen.append(r) or "reset sessions " + ",".join(r.sessions))
    r2 = mem2.forget(rid, U, resume=rid)
    assert seen[0].content_lost and seen[0].terms == set() and seen[0].sessions == {"s7"}
    assert r2.complete and mem2.pending_erasures(U) == []
    mem2.close()


def test_forget_async_writes_receipt_and_resume_async(tmp_path):
    mem = MemoryStore(tmp_path / "q.sqlite", clock=Clock())
    b = bridge(mem, mode="private", required_purge_targets=("recordings",))
    b.on_user_utterance(utt("I work at Acme"))
    rep = _run(b.forget_async("Acme"))
    assert not rep.complete and b.pending_erasures()[0]["receipt_id"] == rep.receipt_id
    mem.register_purge_target("recordings", lambda r: True)
    rep2 = _run(b.resume_erasure_async(rep.receipt_id))
    assert rep2.complete and b.pending_erasures() == []
    mem.close()


# ---------------------------------------------------------------- round 9: receipt in the deletion transaction


@pytest.mark.parametrize("crash_at", ["_regenerate_summaries", "_physical_purge"])
def test_crash_after_delete_leaves_recoverable_receipt(tmp_path, monkeypatch, crash_at):
    from live_agent.memory import store as store_mod

    path = tmp_path / "c.sqlite"
    mem = MemoryStore(path, clock=Clock(), journal_mode="wal")
    (f,) = mem.ingest_user_utterance(utt("我妹妹住在巴黎", session="s5"), user_id=U).facts
    mem.ingest_user_utterance(utt("我喜欢猫", session="s5"), user_id=U)
    mem.consolidate("s5")

    def crash(*a, **kw):
        raise KeyboardInterrupt("simulated crash")

    monkeypatch.setattr(mem, crash_at, crash)
    with pytest.raises(KeyboardInterrupt):
        mem.forget("巴黎", U, require=["recordings"])
    mem.db.close()  # the process dies: no further writes on this connection
    store_mod._RECEIPT_CONTENT.clear()

    mem2 = MemoryStore(path, clock=Clock())
    assert mem2.get(f.id) is None  # the deletion committed ...
    (p,) = mem2.pending_erasures(U)  # ... together with its receipt
    assert p["sessions"] == ["s5"] and "memory_db" in p["pending"] and p["content_lost"]
    assert mem2.recover_interrupted() == [p["receipt_id"]]
    (p2,) = mem2.pending_erasures(U)
    assert p2["pending"] == ["recordings"]  # DB side finished; the external target still pending
    assert mem2._ids("SELECT id FROM records WHERE kind = 'summary' AND session_id = 's5' AND status = 'active'")
    for q in tmp_path.iterdir():
        assert "巴黎".encode() not in q.read_bytes(), q
    mem2.close()


def test_deletion_and_receipt_roll_back_together(tmp_path, monkeypatch):
    mem = MemoryStore(tmp_path / "t.sqlite", clock=Clock())
    (f,) = mem.ingest_user_utterance(utt("I work at Acme"), user_id=U).facts

    def boom(ids):
        raise RuntimeError("crash inside the deletion transaction")

    monkeypatch.setattr(mem, "_scrub_refs", boom)
    with pytest.raises(RuntimeError):
        mem.forget(f.id, U)
    assert mem.get(f.id) is not None and mem.pending_erasures(U) == []  # all or nothing
    mem.close()
