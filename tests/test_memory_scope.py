"""Regression tests for Codex impl2 review findings 12-15 (memory scope, lineage, correction, erasure)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_agent.memory import (
    CANON,
    ClaimType,
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
    # unpinned bridge: pinned by the orchestrator's first mode-bearing call, private until then
    b2 = MemoryBridge(":memory:", user_id=V, stream_id=S, session_id="s2", store=mem)
    assert b2.mode is None and b2.write_scope == private_scope(V)
    b2.recall("hi", mode="public")
    assert b2.mode == "public" and b2.write_scope == public_scope(S)
    b2.recall("hi", mode="private")  # later mismatch never changes the session mode
    assert b2.mode == "public" and b2.mode_mismatches == 1
    with pytest.raises(ValueError):
        bridge(mem, mode="canon")


# ---------------------------------------------------------------- finding 13: lineage of persona output


def test_persona_line_lineage_from_recall(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("我妹妹住在巴黎"))
    hits = b.recall_hits("妹妹 巴黎", mode="private")
    assert hits and all(h.id and h.rendered.endswith(h.text) for h in hits)
    assert b.recall("妹妹 巴黎", mode="private") == [h.rendered for h in hits]
    fact = next(h for h in hits if h.tags["kind"] == "user_fact")
    g = b.on_persona_line("你妹妹在巴黎？", session_id="sess", scope="private", source_ids=[fact.id])
    assert g.derived_from == (fact.id,) and g.source_scopes == {private_scope(U)}
    assert g.meta["lineage"] == "explicit" and g.scope == private_scope(U)
    # unknown lineage: linked to every memory recalled this session, in the session scope
    g2 = b.on_persona_line("巴黎很美", session_id="sess", scope="private")
    assert set(g2.derived_from) == {h.id for h in hits} and g2.meta["lineage"] == "session_recall_superset"
    assert g2.scope == private_scope(U)
    # the lineage makes erasure cascade to both lines
    rep = b.forget("巴黎")
    assert mem.get(g.id) is None and mem.get(g2.id) is None and g.id in rep.deleted_ids


def test_public_persona_line_with_private_input_refused(mem):
    priv = bridge(mem, mode="private")
    priv.on_user_utterance(utt("我妹妹住在巴黎"))
    fact_id = mem._ids("SELECT id FROM records WHERE kind = 'user_fact'")[0]
    pub = bridge(mem, mode="public")
    before = mem.db.execute("SELECT count(*) FROM records").fetchone()[0]
    assert pub.on_persona_line("她妹妹住在巴黎", session_id="live", scope="public", source_ids=[fact_id]) is None
    assert pub.scope_violations and "private inputs" in pub.scope_violations[0]["reason"]
    assert mem.db.execute("SELECT count(*) FROM records").fetchone()[0] == before
    # direct store API fails closed as well
    with pytest.raises(ScopeViolationError):
        mem.record_generated_event("x", "live", public_scope(S), derived_from=[fact_id])
    # a caller claiming public in a private session still writes private
    g = priv.on_persona_line("hello", session_id="sess", scope="public", source_ids=[])
    assert g.scope == private_scope(U) and priv.mode_mismatches == 1
    # public recall never returns private ids, so the superset lineage of a public line stays public
    pub.recall("巴黎 妹妹", mode="public")
    g2 = pub.on_persona_line("welcome everyone", session_id="live", scope="public")
    assert g2.scope == public_scope(S) and g2.source_scopes <= {public_scope(S), CANON}


def test_persona_line_with_erased_explicit_source_not_recorded(mem):
    b = bridge(mem, mode="private")
    b.on_user_utterance(utt("I work at Acme"))
    (hit,) = [h for h in b.recall_hits("Acme", mode="private") if h.tags["kind"] == "user_fact"]
    b.forget("Acme")
    assert b.on_persona_line("How is Acme?", session_id="sess", scope="private", source_ids=[hit.id]) is None
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
