"""SQLite-backed long-term memory service (proposal §5.6, evaluated by E3 §7.3).

One DB file per deployment. Tables:

``records``        every stored record (all kinds), bi-temporal fields for facts.
``record_scopes``  one row per element of a record's ``source_scopes`` (the SQL filter key).
``derivations``    ``derived_from`` edges (child -> parent) for invalidation / erasure cascades.
``embeddings``     one vector per record (pluggable :class:`Embedder`).
``tombstones``     erasure ledger: only (sha256 of id, time, reason code).
``generated_event_log`` (VIEW) everything the persona said / showed.

Invariants enforced here (not by callers):

* Persona output is only ever a ``generated_event``; it is never promoted to a user fact.
* Only ``own_assertion`` sentences from the user become facts; candidates that echo an
  earlier generated event are held ``pending`` until :meth:`MemoryStore.confirm`.
* Retrieval filters on ``source_scopes`` *before* ranking; public mode can never read a
  record with any private source scope.
* Canon records may only derive from canon and are immutable (SQL triggers).
* Episodes are append-only (text cannot be updated); erasure physically deletes rows
  with ``PRAGMA secure_delete=ON`` so the bytes are overwritten in the file.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..types import Utterance, new_id
from .embed import Embedder, HashingEmbedder
from .extract import CandidateFact, Extractor, RuleExtractor, sanitize
from .schema import (
    CANON,
    CLAIM_PRIORITY,
    ClaimType,
    Kind,
    Provenance,
    Record,
    Status,
    is_private,
    is_single_valued,
    private_scope,
    public_scope,
    union_scopes,
    validate_scope,
)
from .summarize import ExtractiveSummarizer, Summarizer

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    text TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    t REAL NOT NULL,
    created_at REAL NOT NULL,
    subject TEXT, predicate TEXT, value TEXT,
    valid_from REAL, valid_to REAL,
    confidence REAL NOT NULL DEFAULT 1.0,
    status TEXT NOT NULL,
    echo INTEGER NOT NULL DEFAULT 0,
    importance REAL NOT NULL DEFAULT 0.5,
    immutable INTEGER NOT NULL DEFAULT 0,
    provenance TEXT NOT NULL,
    meta TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS records_kind ON records(kind, status);
CREATE INDEX IF NOT EXISTS records_sp ON records(subject, predicate);
CREATE INDEX IF NOT EXISTS records_session ON records(session_id);
CREATE INDEX IF NOT EXISTS records_owner ON records(owner);
CREATE INDEX IF NOT EXISTS records_t ON records(t);
CREATE TABLE IF NOT EXISTS record_scopes (
    record_id TEXT NOT NULL, scope TEXT NOT NULL, PRIMARY KEY (record_id, scope)
);
CREATE INDEX IF NOT EXISTS record_scopes_scope ON record_scopes(scope);
CREATE TABLE IF NOT EXISTS derivations (
    child_id TEXT NOT NULL, parent_id TEXT NOT NULL, PRIMARY KEY (child_id, parent_id)
);
CREATE INDEX IF NOT EXISTS derivations_parent ON derivations(parent_id);
CREATE TABLE IF NOT EXISTS embeddings (
    record_id TEXT PRIMARY KEY, model TEXT NOT NULL, vec BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS tombstones (
    id_hash TEXT NOT NULL, t REAL NOT NULL, reason TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS generated_event_log AS
    SELECT id, text, scope, session_id, t, provenance FROM records WHERE kind = 'generated_event';
CREATE TRIGGER IF NOT EXISTS immutable_no_update BEFORE UPDATE ON records
    WHEN OLD.immutable = 1 BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS immutable_no_delete BEFORE DELETE ON records
    WHEN OLD.immutable = 1 BEGIN SELECT RAISE(ABORT, 'immutable record'); END;
CREATE TRIGGER IF NOT EXISTS log_append_only BEFORE UPDATE OF text, scope, provenance ON records
    WHEN OLD.kind IN ('episode', 'generated_event') BEGIN SELECT RAISE(ABORT, 'append-only'); END;
"""

_DEFAULT_IMPORTANCE = {
    Kind.USER_FACT: 0.8,
    Kind.LEDGER: 0.7,
    Kind.SUMMARY: 0.6,
    Kind.PROCEDURAL: 0.5,
    Kind.EPISODE: 0.4,
    Kind.GENERATED_EVENT: 0.3,
    Kind.CANDIDATE_BELIEF: 0.2,
}
_KIND_PREFIX = {
    Kind.USER_FACT: "fact", Kind.EPISODE: "ep", Kind.LEDGER: "led", Kind.GENERATED_EVENT: "gen",
    Kind.CANDIDATE_BELIEF: "bel", Kind.PROCEDURAL: "proc", Kind.SUMMARY: "sum",
}


class ImmutableRecordError(RuntimeError):
    pass


@dataclass
class IngestResult:
    episode: Record | None
    facts: list[Record] = field(default_factory=list)  # stored (active or pending) fact records
    skipped: list[tuple[CandidateFact, str]] = field(default_factory=list)  # (candidate, reason)
    generated_event: Record | None = None  # set when a persona utterance was routed here


@dataclass
class Hit:
    record: Record
    score: float
    relevance: float
    recency: float
    importance: float

    @property
    def tags(self) -> dict[str, Any]:
        return self.record.tags


@dataclass
class RetrievalResult:
    hits: list[Hit]
    elapsed_ms: float
    scanned: int
    truncated: bool  # budget exhausted before all eligible candidates were scored

    def __iter__(self):
        return iter(self.hits)

    def __len__(self) -> int:
        return len(self.hits)

    @property
    def records(self) -> list[Record]:
        return [h.record for h in self.hits]


@dataclass
class Resolution:
    subject: str
    predicate: str
    value: str | None
    record: Record | None
    alternatives: list[Record]  # lower-priority / older active claims
    pending: list[Record]  # echo or conflicting candidates awaiting confirmation

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.pending)


@dataclass
class ErasureReport:
    """Passed to erasure hooks so the orchestrator can purge external caches.

    ``terms`` are held in memory only (never persisted) so hooks can scrub LLM prompt
    caches, unsent BlockScripts and recordings; ``sessions`` tells which generator / LLM
    sessions to restart from canon anchors.
    """

    user_id: str
    reason: str
    t: float
    deleted_ids: list[str]
    kinds: dict[str, int]
    sessions: set[str]
    terms: set[str]
    regenerated: list[str] = field(default_factory=list)  # new summary ids
    hook_errors: list[str] = field(default_factory=list)


class _RateLimiter:
    def __init__(self, max_events: int, window_s: float, clock: Callable[[], float]) -> None:
        self.max_events, self.window_s, self.clock = max_events, window_s, clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        q = self._events[key]
        while q and now - q[0] >= self.window_s:
            q.popleft()
        if len(q) >= self.max_events:
            return False
        q.append(now)
        return True


class MemoryStore:
    """Long-term memory for one deployment. Not thread-safe; use one instance per process."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        embedder: Embedder | None = None,
        extractor: Extractor | None = None,
        clock: Callable[[], float] = time.time,
        echo_threshold: float = 0.5,
        echo_lexical_floor: float = 0.4,
        viewer_rate: tuple[int, float] = (5, 10.0),
        viewer_max_len: int = 200,
        recency_tau_s: float = 3 * 86400.0,
        weights: tuple[float, float, float] = (0.6, 0.2, 0.2),
    ) -> None:
        self.path = str(path)
        self.embedder: Embedder = embedder or HashingEmbedder()
        self.extractor: Extractor = extractor or RuleExtractor()
        self.clock = clock
        self.echo_threshold = echo_threshold
        self.echo_lexical_floor = echo_lexical_floor
        self.viewer_max_len = viewer_max_len
        self.recency_tau_s = recency_tau_s
        self.weights = weights
        self._viewer_limiter = _RateLimiter(viewer_rate[0], viewer_rate[1], clock)
        self.stats: dict[str, int] = defaultdict(int)
        # hooks: erasure -> external caches; stale -> summary regeneration etc.
        self.erasure_hooks: list[Callable[[ErasureReport], None]] = []
        self.stale_hooks: list[Callable[[list[Record]], None]] = []
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ low level

    def add_record(
        self,
        kind: Kind,
        scope: str,
        text: str,
        claim_type: ClaimType,
        provenance: Provenance,
        *,
        derived_from: Sequence[str] = (),
        subject: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        valid_from: float | None = None,
        confidence: float = 1.0,
        status: Status = Status.ACTIVE,
        echo: bool = False,
        importance: float | None = None,
        immutable: bool = False,
        meta: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> Record:
        """Insert one record; computes ``source_scopes`` from its parents and embeds it."""
        validate_scope(scope)
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        source_scopes = union_scopes(scope, parents)
        if scope == CANON and source_scopes != {CANON}:
            raise ValueError("canon records may only derive from canon records")
        if kind == Kind.GENERATED_EVENT and claim_type == ClaimType.OWN_ASSERTION:
            raise ValueError("generated events are never user assertions")
        now = self.clock()
        owner = provenance.user_id or next((p.provenance.user_id for p in parents if p.provenance.user_id), "")
        provenance.user_id = owner
        if not provenance.timestamp:
            provenance.timestamp = now
        if kind == Kind.USER_FACT and valid_from is None:
            valid_from = provenance.timestamp
        rec = Record(
            id=new_id(_KIND_PREFIX[kind]), kind=kind, scope=scope, source_scopes=source_scopes,
            claim_type=claim_type, text=text, provenance=provenance,
            derived_from=tuple(p.id for p in parents), created_at=now, subject=subject,
            predicate=predicate, value=value, valid_from=valid_from, valid_to=None,
            confidence=confidence, status=status, echo=echo,
            importance=_DEFAULT_IMPORTANCE[kind] if importance is None else importance,
            immutable=immutable, meta=dict(meta or {}),
        )
        self.db.execute(
            "INSERT INTO records (id, kind, scope, claim_type, text, owner, session_id, t, created_at,"
            " subject, predicate, value, valid_from, valid_to, confidence, status, echo, importance,"
            " immutable, provenance, meta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.id, kind.value, scope, claim_type.value, text, owner, provenance.session_id,
                provenance.timestamp, now, subject, predicate, value, valid_from, None, confidence,
                status.value, int(echo), rec.importance, int(immutable), provenance.to_json(),
                json.dumps(rec.meta, ensure_ascii=False),
            ),
        )
        self.db.executemany(
            "INSERT INTO record_scopes (record_id, scope) VALUES (?, ?)",
            [(rec.id, s) for s in sorted(source_scopes)],
        )
        self.db.executemany(
            "INSERT INTO derivations (child_id, parent_id) VALUES (?, ?)",
            [(rec.id, p.id) for p in parents],
        )
        vec = self.embedder.embed([self._embed_text(rec)])[0].astype(np.float32)
        self.db.execute(
            "INSERT INTO embeddings (record_id, model, vec) VALUES (?, ?, ?)",
            (rec.id, self.embedder.name, vec.tobytes()),
        )
        if commit:
            self.db.commit()
        return rec

    @staticmethod
    def _embed_text(rec: Record) -> str:
        if rec.subject and rec.predicate and rec.value:
            return f"{rec.text} {rec.value}"
        return rec.text

    def get(self, record_id: str) -> Record | None:
        recs = self._load([record_id])
        return recs[0] if recs else None

    def _require(self, record_id: str) -> Record:
        rec = self.get(record_id)
        if rec is None:
            raise KeyError(record_id)
        return rec

    def _load(self, ids: Sequence[str]) -> list[Record]:
        if not ids:
            return []
        out: dict[str, Record] = {}
        for chunk_start in range(0, len(ids), 500):
            chunk = list(ids[chunk_start:chunk_start + 500])
            q = ",".join("?" * len(chunk))
            rows = self.db.execute(f"SELECT * FROM records WHERE id IN ({q})", chunk).fetchall()
            scopes: dict[str, set[str]] = defaultdict(set)
            for r in self.db.execute(f"SELECT record_id, scope FROM record_scopes WHERE record_id IN ({q})", chunk):
                scopes[r[0]].add(r[1])
            parents: dict[str, list[str]] = defaultdict(list)
            for r in self.db.execute(
                f"SELECT child_id, parent_id FROM derivations WHERE child_id IN ({q}) ORDER BY rowid", chunk
            ):
                parents[r[0]].append(r[1])
            for row in rows:
                out[row["id"]] = self._row_to_record(row, scopes[row["id"]], parents[row["id"]])
        return [out[i] for i in ids if i in out]

    @staticmethod
    def _row_to_record(row: sqlite3.Row, scopes: set[str], parents: list[str]) -> Record:
        return Record(
            id=row["id"], kind=Kind(row["kind"]), scope=row["scope"], source_scopes=frozenset(scopes),
            claim_type=ClaimType(row["claim_type"]), text=row["text"],
            provenance=Provenance.from_json(row["provenance"]), derived_from=tuple(parents),
            created_at=row["created_at"], subject=row["subject"], predicate=row["predicate"],
            value=row["value"], valid_from=row["valid_from"], valid_to=row["valid_to"],
            confidence=row["confidence"], status=Status(row["status"]), echo=bool(row["echo"]),
            importance=row["importance"], immutable=bool(row["immutable"]), meta=json.loads(row["meta"]),
        )

    def _ids(self, sql: str, params: Sequence[Any] = ()) -> list[str]:
        return [r[0] for r in self.db.execute(sql, params)]

    def _set_status(self, record_id: str, status: Status, **cols: Any) -> None:
        sets = ["status = ?"] + [f"{c} = ?" for c in cols]
        try:
            self.db.execute(
                f"UPDATE records SET {', '.join(sets)} WHERE id = ?", [status.value, *cols.values(), record_id]
            )
        except sqlite3.IntegrityError as e:
            raise ImmutableRecordError(record_id) from e

    def _update_meta(self, record_id: str, **kv: Any) -> None:
        rec = self._require(record_id)
        rec.meta.update(kv)
        self.db.execute("UPDATE records SET meta = ? WHERE id = ?", (json.dumps(rec.meta, ensure_ascii=False), record_id))

    # ------------------------------------------------------------------ scope helpers

    @staticmethod
    def _scope_filter_sql(mode: str, user_id: str | None, stream_id: str | None) -> tuple[str, list[Any]]:
        """SQL predicate over ``rs.scope`` that is TRUE for readable scopes."""
        if mode == "private":
            if not user_id:
                raise ValueError("private mode requires user_id")
            return "(rs.scope = 'canon' OR rs.scope = ? OR rs.scope LIKE 'public:%')", [private_scope(user_id)]
        if mode == "public":
            if stream_id:
                return "(rs.scope = 'canon' OR rs.scope = ?)", [public_scope(stream_id)]
            return "(rs.scope = 'canon' OR rs.scope LIKE 'public:%')", []
        raise ValueError(f"unknown mode {mode!r}; expected 'private' or 'public'")

    @staticmethod
    def scope_readable(scopes: Iterable[str], mode: str, user_id: str | None, stream_id: str | None) -> bool:
        """Python mirror of the SQL filter (defence in depth)."""
        for s in scopes:
            if s == CANON:
                continue
            if mode == "private" and (s == private_scope(user_id or "") or s.startswith("public:")):
                continue
            if mode == "public" and (s == public_scope(stream_id) if stream_id else s.startswith("public:")):
                continue
            return False
        return True

    def _utterance_scope(self, utt: Utterance, user_id: str, stream_id: str | None) -> str:
        if ":" in utt.scope or utt.scope == CANON:
            return validate_scope(utt.scope)
        if utt.scope == "public":
            if not stream_id:
                raise ValueError("public utterance requires stream_id")
            return public_scope(stream_id)
        return private_scope(user_id)

    # ------------------------------------------------------------------ write policy

    def ingest_user_utterance(
        self,
        utt: Utterance,
        extractor: Extractor | None = None,
        *,
        user_id: str,
        stream_id: str | None = None,
    ) -> IngestResult:
        """Append the turn to the episode log and store candidate facts per the write policy.

        Persona utterances are routed to the generated-event log; viewer utterances to
        :meth:`ingest_viewer_chat`. Only ``own_assertion`` sentences produce facts.
        """
        ex = extractor or self.extractor
        scope = self._utterance_scope(utt, user_id, stream_id)
        if utt.speaker == "persona":
            gen = self.record_generated_event(utt.text, utt.session_id, scope, source_id=utt.uid, user_id=user_id)
            return IngestResult(episode=None, generated_event=gen)
        if utt.speaker.startswith("viewer:"):
            if not stream_id:
                raise ValueError("viewer chat requires stream_id")
            ep = self.ingest_viewer_chat(utt.text, utt.speaker.split(":", 1)[1], stream_id,
                                         session_id=utt.session_id, source_id=utt.uid)
            return IngestResult(episode=ep)

        prov = lambda: Provenance(
            source_id=utt.uid, speaker="user", session_id=utt.session_id, timestamp=self.clock(),
            extractor_version=ex.version, user_id=user_id,
        )
        episode = self.add_record(
            Kind.EPISODE, scope, utt.text, ex.classify(utt.text), prov(),
            meta={"t_end": utt.t_end}, commit=False,
        )
        result = IngestResult(episode=episode)
        for cand in ex.extract(utt.text):
            if cand.claim_type != ClaimType.OWN_ASSERTION:
                result.skipped.append((cand, cand.claim_type.value))
                continue
            if not (cand.subject and cand.predicate and cand.value):
                result.skipped.append((cand, "incomplete"))
                continue
            rec = self._store_user_fact(cand, scope, user_id, episode, prov())
            if rec is None:
                result.skipped.append((cand, "duplicate"))
            else:
                result.facts.append(rec)
        self.db.commit()
        return result

    def _abs_subject(self, subject: str, user_id: str) -> str:
        if subject.startswith(("user:", "viewer:", "persona")):
            return subject
        if subject == "user":
            return f"user:{user_id}"
        if subject.startswith("user/"):
            return f"user:{user_id}/{subject[5:]}"
        return subject

    def _store_user_fact(
        self, cand: CandidateFact, scope: str, user_id: str, episode: Record, prov: Provenance
    ) -> Record | None:
        subject = self._abs_subject(cand.subject or "user", user_id)
        echo_ids = self._echo_matches(cand.text, cand.value or "", user_id)
        derived = [episode.id, *echo_ids]
        meta: dict[str, Any] = {}
        status = Status.ACTIVE
        current = self._current_facts(subject, cand.predicate or "", user_id, claim=ClaimType.OWN_ASSERTION)
        same = [r for r in current if _norm(r.value) == _norm(cand.value)]
        if same:
            return None  # already asserted by the user: no duplicate
        if echo_ids:
            status = Status.PENDING
            meta["echo_of"] = echo_ids
        different = [r for r in current if _norm(r.value) != _norm(cand.value)]
        if status == Status.ACTIVE and different and is_single_valued(cand.predicate):
            if cand.correction:
                meta["supersedes"] = [r.id for r in different]
                self._supersede(different)
            else:
                status = Status.PENDING
                meta["conflict_with"] = [r.id for r in different]
        elif echo_ids and different and is_single_valued(cand.predicate):
            meta["conflict_with"] = [r.id for r in different]
        return self.add_record(
            Kind.USER_FACT, scope, cand.text, ClaimType.OWN_ASSERTION, prov, derived_from=derived,
            subject=subject, predicate=cand.predicate, value=cand.value, confidence=cand.confidence,
            status=status, echo=bool(echo_ids), meta=meta, commit=False,
        )

    def _echo_matches(self, text: str, value: str, user_id: str) -> list[str]:
        """Generated events readable by this user that the candidate semantically echoes."""
        filt, params = self._scope_filter_sql("private", user_id, None)
        rows = self.db.execute(
            "SELECT r.id, r.text, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            " WHERE r.kind = 'generated_event' AND NOT EXISTS (SELECT 1 FROM record_scopes rs"
            f" WHERE rs.record_id = r.id AND NOT {filt})",
            params,
        ).fetchall()
        if not rows:
            return []
        q = self.embedder.embed([f"{text} {value}"])[0]
        mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        sims = mat @ q
        nv = _norm(value)
        hits = []
        for r, s in zip(rows, sims):
            lexical = len(nv) >= 2 and nv in _norm(r["text"])
            if s >= self.echo_threshold or (lexical and s >= self.echo_lexical_floor):
                hits.append(r["id"])
        return hits

    def record_generated_event(
        self,
        text: str,
        session_id: str,
        scope: str,
        *,
        source_id: str = "",
        user_id: str = "",
        derived_from: Sequence[str] = (),
        request_index: int | None = None,
    ) -> Record:
        """Log persona output (speech / shown content). Never promoted to a user fact.

        Persona lines in a private conversation are private (pass ``private:<user>``);
        ``derived_from`` should list the memory records the line was conditioned on so the
        line inherits their ``source_scopes``.
        """
        validate_scope(scope)
        if not user_id and is_private(scope):
            user_id = scope.split(":", 1)[1]
        prov = Provenance(source_id=source_id, speaker="persona", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.GENERATED_EVENT, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from, meta={"request_index": request_index} if request_index is not None else None,
        )

    def ingest_viewer_chat(
        self, text: str, viewer_id: str, stream_id: str, *, session_id: str = "", source_id: str = ""
    ) -> Record | None:
        """Public-scope, ``viewer_claim``, rate-limited and sanitised. Returns None if dropped."""
        if not self._viewer_limiter.allow(viewer_id):
            self.stats["viewer_rate_limited"] += 1
            return None
        clean = sanitize(text, self.viewer_max_len)
        if not clean.text:
            self.stats["viewer_empty"] += 1
            return None
        scope = public_scope(stream_id)
        prov = Provenance(source_id=source_id, speaker=f"viewer:{viewer_id}", session_id=session_id,
                          timestamp=self.clock(), extractor_version=self.extractor.version)
        ep = self.add_record(
            Kind.EPISODE, scope, clean.text, ClaimType.VIEWER_CLAIM, prov, importance=0.1,
            meta={"injection": clean.injection, "truncated": clean.truncated}, commit=False,
        )
        if clean.injection:
            self.stats["viewer_injection"] += 1
        else:
            for cand in self.extractor.extract(clean.text):
                if cand.claim_type != ClaimType.OWN_ASSERTION or not (cand.predicate and cand.value):
                    continue
                subj = f"viewer:{viewer_id}" + ((cand.subject or "user")[4:])  # "user/sister" -> "/sister"
                self.add_record(
                    Kind.USER_FACT, scope, cand.text, ClaimType.VIEWER_CLAIM,
                    Provenance(source_id=source_id, speaker=f"viewer:{viewer_id}", session_id=session_id,
                               timestamp=self.clock(), extractor_version=self.extractor.version),
                    derived_from=[ep.id], subject=subj, predicate=cand.predicate, value=cand.value,
                    confidence=0.3, importance=0.1, commit=False,
                )
        self.db.commit()
        return ep

    def record_inference(
        self,
        text: str,
        *,
        user_id: str,
        derived_from: Sequence[str],
        subject: str | None = None,
        predicate: str | None = None,
        value: str | None = None,
        confidence: float = 0.5,
        session_id: str = "",
        scope: str | None = None,
    ) -> Record:
        """Agent inference -> ``candidate_belief`` (pending; never a user fact until confirmed)."""
        prov = Provenance(speaker="agent", session_id=session_id, timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.CANDIDATE_BELIEF, scope or private_scope(user_id), text, ClaimType.AGENT_INFERENCE, prov,
            derived_from=derived_from, subject=self._abs_subject(subject, user_id) if subject else None,
            predicate=predicate, value=value, confidence=confidence, status=Status.PENDING,
        )

    def record_observation(
        self,
        text: str,
        *,
        user_id: str,
        subject: str,
        predicate: str,
        value: str,
        confidence: float = 0.9,
        session_id: str = "",
        source_id: str = "",
        derived_from: Sequence[str] = (),
    ) -> Record:
        """System observation (e.g. from a sensor / platform metadata) as a user fact."""
        prov = Provenance(source_id=source_id, speaker="system", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.USER_FACT, private_scope(user_id), text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from, subject=self._abs_subject(subject, user_id), predicate=predicate,
            value=value, confidence=confidence,
        )

    def add_ledger(
        self,
        text: str,
        scope: str,
        *,
        canonical: bool = False,
        key: str | None = None,
        derived_from: Sequence[str] = (),
        session_id: str = "",
        user_id: str = "",
    ) -> Record:
        """Persona / world continuity entry. Canonical anchors are immutable and canon-only.

        A non-canonical entry with a ``key`` supersedes the previous entry with the same key
        in the same scope (bi-temporal: old one keeps ``valid_to``).
        """
        if canonical and scope != CANON:
            raise ValueError("canonical anchors must have scope 'canon'")
        if not canonical and scope == CANON:
            raise ValueError("only canonical anchors live in scope 'canon'")
        if key and not canonical:
            old = self._load(self._ids(
                "SELECT id FROM records WHERE kind = 'ledger' AND scope = ? AND status = 'active'"
                " AND json_extract(meta, '$.key') = ?", (scope, key)))
            self._supersede(old)
        prov = Provenance(speaker="system", session_id=session_id, timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.LEDGER, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=derived_from,
            immutable=canonical, meta={"key": key, "canonical": canonical},
        )

    def add_procedure(
        self,
        text: str,
        outcome: str,
        *,
        scope: str = CANON,
        tags: Sequence[str] = (),
        derived_from: Sequence[str] = (),
    ) -> Record:
        """A²RD-style prompt-library entry: what worked (``success``) or failed (``failure``)."""
        if outcome not in ("success", "failure"):
            raise ValueError("outcome must be 'success' or 'failure'")
        prov = Provenance(speaker="system", timestamp=self.clock())
        return self.add_record(
            Kind.PROCEDURAL, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=derived_from,
            meta={"outcome": outcome, "tags": list(tags)},
        )

    # ------------------------------------------------------------------ confirmation / correction

    def confirm(self, record_id: str) -> Record:
        """User explicitly confirms a pending echo / conflicting fact or a candidate belief."""
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending (status={rec.status.value})")
        now = self.clock()
        if rec.subject and rec.predicate and is_single_valued(rec.predicate):
            owner = rec.provenance.user_id
            others = [r for r in self._current_facts(rec.subject, rec.predicate, owner, claim=None)
                      if r.id != rec.id and r.kind == Kind.USER_FACT
                      and r.claim_type in (ClaimType.OWN_ASSERTION, ClaimType.SYSTEM_OBSERVATION)
                      and _norm(r.value) != _norm(rec.value)]
            self._supersede(others)
            if others:
                self._update_meta(rec.id, supersedes=[r.id for r in others])
        cols: dict[str, Any] = {"valid_from": now}
        if rec.kind == Kind.CANDIDATE_BELIEF:
            cols.update(kind=Kind.USER_FACT.value, claim_type=ClaimType.OWN_ASSERTION.value)
            self._update_meta(rec.id, confirmed_from=ClaimType.AGENT_INFERENCE.value)
        self._set_status(rec.id, Status.ACTIVE, **cols)
        self._update_meta(rec.id, confirmed_at=now)
        self.db.commit()
        return self._require(rec.id)

    def reject(self, record_id: str) -> Record:
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending")
        self._set_status(rec.id, Status.REJECTED)
        self.db.commit()
        return self._require(rec.id)

    def correct(self, record_id: str, new_value: str, *, text: str | None = None,
                source_id: str = "", session_id: str = "") -> Record:
        """Bi-temporal correction: old value gets ``valid_to`` (kept for audit), new value is
        inserted, and every artifact reachable through ``derived_from`` is marked stale."""
        old = self._require(record_id)
        if old.kind != Kind.USER_FACT or old.status not in (Status.ACTIVE, Status.PENDING):
            raise ValueError("only current user facts can be corrected")
        self._supersede([old])
        prov = Provenance(source_id=source_id, speaker="user", session_id=session_id or old.provenance.session_id,
                          timestamp=self.clock(), user_id=old.provenance.user_id)
        new = self.add_record(
            Kind.USER_FACT, old.scope, text or f"{old.subject} {old.predicate} {new_value}",
            ClaimType.OWN_ASSERTION, prov, subject=old.subject, predicate=old.predicate, value=new_value,
            meta={"supersedes": [old.id]},
        )
        return new

    def _supersede(self, records: Sequence[Record]) -> list[Record]:
        now = self.clock()
        for r in records:
            if r.immutable:
                raise ImmutableRecordError(r.id)
            self._set_status(r.id, Status.SUPERSEDED, valid_to=now)
        stale = self.invalidate_derivatives([r.id for r in records]) if records else []
        self.db.commit()
        return stale

    def invalidate_derivatives(self, root_ids: Sequence[str]) -> list[Record]:
        """Mark every artifact reachable through ``derived_from`` as stale; fire stale hooks."""
        ids = self._descendants(root_ids) - set(root_ids)
        stale: list[Record] = []
        for rec in self._load(sorted(ids)):
            if rec.immutable or rec.status in (Status.SUPERSEDED, Status.STALE, Status.REJECTED):
                continue
            self._set_status(rec.id, Status.STALE)
            rec.status = Status.STALE
            stale.append(rec)
        self.db.commit()
        if stale:
            for hook in list(self.stale_hooks):
                hook(stale)
        return stale

    def regenerate_stale(self, summarizer: Summarizer | None = None) -> list[Record]:
        """Hook helper: rebuild every stale summary from its session's current records."""
        sessions = {r["session_id"] for r in self.db.execute(
            "SELECT session_id FROM records WHERE kind = 'summary' AND status = 'stale'")}
        out = []
        for s in sorted(sessions):
            rec = self.consolidate(s, summarizer)
            if rec is not None:
                out.append(rec)
        return out

    def _descendants(self, root_ids: Iterable[str]) -> set[str]:
        seen = set(root_ids)
        frontier = list(seen)
        while frontier:
            q = ",".join("?" * len(frontier))
            children = self._ids(f"SELECT child_id FROM derivations WHERE parent_id IN ({q})", frontier)
            frontier = [c for c in children if c not in seen]
            seen.update(frontier)
        return seen

    # ------------------------------------------------------------------ read paths

    def _current_facts(self, subject: str, predicate: str, user_id: str, claim: ClaimType | None) -> list[Record]:
        filt, params = self._scope_filter_sql("private", user_id, None)
        sql = ("SELECT r.id FROM records r WHERE r.kind = 'user_fact' AND r.status = 'active'"
               " AND r.subject = ? AND r.predicate = ? AND (r.valid_to IS NULL OR r.valid_to > ?)"
               f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})")
        args: list[Any] = [subject, predicate, self.clock(), *params]
        if claim is not None:
            sql += " AND r.claim_type = ?"
            args.append(claim.value)
        return self._load(self._ids(sql + " ORDER BY r.valid_from", args))

    def retrieve(
        self,
        query: str,
        mode: str,
        user_id: str | None = None,
        stream_id: str | None = None,
        k: int = 8,
        budget_ms: float = 50.0,
        *,
        kinds: Sequence[Kind] | None = None,
        include_pending: bool = False,
        batch: int = 512,
    ) -> RetrievalResult:
        """Scope-filter first (in SQL, on ``source_scopes``), then rank by
        relevance + recency + importance. Pending / stale / superseded records are excluded
        unless ``include_pending`` (which adds pending only)."""
        t0 = time.perf_counter()
        now = self.clock()
        filt, params = self._scope_filter_sql(mode, user_id, stream_id)
        statuses = ["active"] + (["pending"] if include_pending else [])
        sql = (
            "SELECT r.id, r.t, r.importance, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            f" WHERE r.status IN ({','.join('?' * len(statuses))})"
            " AND (r.valid_to IS NULL OR r.valid_to > ?)"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})"
        )
        args: list[Any] = [*statuses, now, *params]
        if kinds:
            sql += f" AND r.kind IN ({','.join('?' * len(kinds))})"
            args += [Kind(x).value for x in kinds]
        sql += " ORDER BY r.t DESC LIMIT ? OFFSET ?"
        qv = self.embedder.embed([query])[0]
        w_rel, w_rec, w_imp = self.weights
        scored: list[tuple[float, float, float, float, str]] = []
        offset, scanned, truncated = 0, 0, False
        while True:
            rows = self.db.execute(sql, [*args, batch, offset]).fetchall()
            if not rows:
                break
            mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
            rel = np.clip(mat @ qv, 0.0, 1.0)
            for r, rv in zip(rows, rel):
                rec_s = math.exp(-max(0.0, now - r["t"]) / self.recency_tau_s)
                imp = float(r["importance"])
                scored.append((w_rel * float(rv) + w_rec * rec_s + w_imp * imp, float(rv), rec_s, imp, r["id"]))
            scanned += len(rows)
            offset += batch
            if len(rows) < batch:
                break
            if (time.perf_counter() - t0) * 1000.0 > budget_ms:
                truncated = True
                break
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]
        recs = {r.id: r for r in self._load([x[4] for x in top])}
        hits = []
        for score, rv, rs, imp, rid in top:
            rec = recs.get(rid)
            if rec is None or not self.scope_readable(rec.source_scopes, mode, user_id, stream_id):
                continue  # defence in depth; the SQL filter should already have excluded it
            hits.append(Hit(rec, score, rv, rs, imp))
        return RetrievalResult(hits, (time.perf_counter() - t0) * 1000.0, scanned, truncated)

    def resolve(self, user_id: str, subject: str, predicate: str) -> Resolution:
        """Conflict resolution: user-asserted (latest valid) > system-observed >
        agent-inferred > viewer-claimed. Echo / conflicting candidates never count until confirmed."""
        subj = self._abs_subject(subject, user_id)
        filt, params = self._scope_filter_sql("private", user_id, None)
        ids = self._ids(
            "SELECT r.id FROM records r WHERE r.kind IN ('user_fact', 'candidate_belief')"
            " AND r.subject = ? AND r.predicate = ? AND r.status IN ('active', 'pending')"
            " AND (r.valid_to IS NULL OR r.valid_to > ?)"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})",
            [subj, predicate, self.clock(), *params],
        )
        recs = self._load(ids)
        active = [r for r in recs if r.status == Status.ACTIVE and r.claim_type in CLAIM_PRIORITY]
        pending = [r for r in recs if r.status == Status.PENDING]
        active.sort(key=lambda r: (CLAIM_PRIORITY[r.claim_type], r.valid_from or 0.0, r.created_at), reverse=True)
        best = active[0] if active else None
        return Resolution(subj, predicate, best.value if best else None, best, active[1:], pending)

    def profile(self, user_id: str) -> list[Record]:
        """Session preload: current valid user facts (user-asserted or system-observed) from
        the user's private scope; single-valued predicates collapsed to the resolved winner."""
        ids = self._ids(
            "SELECT id FROM records WHERE kind = 'user_fact' AND status = 'active' AND scope = ?"
            " AND claim_type IN ('own_assertion', 'system_observation')"
            " AND (valid_to IS NULL OR valid_to > ?) ORDER BY valid_from",
            [private_scope(user_id), self.clock()],
        )
        out: dict[tuple[str, str], Record] = {}
        multi: list[Record] = []
        for r in self._load(ids):
            if not self.scope_readable(r.source_scopes, "private", user_id, None):
                continue
            if is_single_valued(r.predicate):
                key = (r.subject or "", r.predicate or "")
                prev = out.get(key)
                if prev is None or (CLAIM_PRIORITY[r.claim_type], r.valid_from or 0) >= (
                        CLAIM_PRIORITY[prev.claim_type], prev.valid_from or 0):
                    out[key] = r
            else:
                multi.append(r)
        return list(out.values()) + multi

    def canon_anchors(self) -> list[Record]:
        return self._load(self._ids(
            "SELECT id FROM records WHERE kind = 'ledger' AND scope = 'canon' AND immutable = 1 ORDER BY t"))

    def boot_context(self, mode: str, user_id: str | None = None) -> list[Record]:
        """Records a new session may start from. Public sessions boot from canon anchors only."""
        anchors = self.canon_anchors()
        if mode == "public":
            return anchors
        if mode == "private":
            if not user_id:
                raise ValueError("private mode requires user_id")
            return anchors + self.profile(user_id)
        raise ValueError(mode)

    # ------------------------------------------------------------------ consolidation

    def consolidate(self, session_id: str, summarizer: Summarizer | None = None) -> Record | None:
        """Sleep-time summary of one session. Writes a ``summary`` record whose
        ``derived_from`` lists every input and whose ``source_scopes`` is their union.
        Supersedes any previous summary of the same session."""
        summ = summarizer or ExtractiveSummarizer()
        now = self.clock()
        ids = self._ids(
            "SELECT id FROM records WHERE session_id = ? AND ("
            " (kind IN ('episode', 'generated_event'))"
            " OR (kind = 'user_fact' AND status = 'active' AND (valid_to IS NULL OR valid_to > ?)))"
            " ORDER BY t", [session_id, now])
        recs = self._load(ids)
        # drop turns whose extracted facts were all corrected away (history stays in the episode log)
        retired = set(self._ids(
            "SELECT d.parent_id FROM derivations d JOIN records c ON c.id = d.child_id"
            " WHERE c.kind = 'user_fact' AND c.status IN ('superseded', 'stale', 'rejected')"))
        live = set(self._ids(
            "SELECT d.parent_id FROM derivations d JOIN records c ON c.id = d.child_id"
            " WHERE c.kind = 'user_fact' AND c.status IN ('active', 'pending')"))
        recs = [r for r in recs if not (r.kind == Kind.EPISODE and r.id in retired and r.id not in live)]
        old = self._load(self._ids(
            "SELECT id FROM records WHERE kind = 'summary' AND session_id = ? AND status IN ('active', 'stale')",
            [session_id]))
        for r in old:
            self._set_status(r.id, Status.SUPERSEDED, valid_to=now)
        if not recs:
            self.db.commit()
            return None
        scopes = frozenset().union(*(r.source_scopes for r in recs))
        privs = sorted(s for s in scopes if is_private(s))
        if len(privs) > 1:
            raise ValueError("refusing to summarise across several users' private scopes")
        scope = privs[0] if privs else next((s for s in sorted(scopes) if s.startswith("public:")), CANON)
        if scope == CANON:
            raise ValueError("summaries are never canon")
        text = summ.summarize(recs)
        prov = Provenance(speaker="system", session_id=session_id, timestamp=now,
                          extractor_version=summ.version, user_id=privs[0].split(":", 1)[1] if privs else "")
        return self.add_record(Kind.SUMMARY, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
                               derived_from=[r.id for r in recs], meta={"session": session_id})

    # ------------------------------------------------------------------ erasure

    def _user_records_sql(self) -> str:
        return ("(r.owner = ? OR EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id"
                " AND rs.scope = ?))")

    def forget(
        self,
        target: str | Record,
        user_id: str,
        reason: str = "user_request",
        *,
        regenerate: bool | Summarizer = True,
    ) -> ErasureReport:
        """Physically erase a fact (by record id / Record) or everything matching a query term.

        Cascade: matched records -> source episodes (id link) -> every record of this user
        mentioning the value/term (content match: episodes, persona lines, summaries,
        ledger ...) -> all descendants through ``derived_from``; plus their embeddings,
        scope rows and derivation edges. A tombstone keeps only sha256(id), time and
        reason. Affected session summaries are regenerated from what remains, then
        erasure hooks fire so the orchestrator can reset LLM KV / generator sessions and
        delete recordings. Over-deletion (e.g. another fact from the same turn) is
        accepted as the safe side.
        """
        priv = private_scope(user_id)
        mine = self._user_records_sql()
        seeds: list[Record] = []
        terms: set[str] = set()
        rid = target.id if isinstance(target, Record) else target
        rec = self.get(rid)
        if rec is not None:
            if rec.provenance.user_id != user_id and priv not in rec.source_scopes:
                raise PermissionError("record does not belong to this user")
            seeds = [rec]
        else:
            term = str(target).strip()
            if not term:
                raise ValueError("empty erasure target")
            terms.add(term)
            seeds = self._load(self._ids(
                f"SELECT r.id FROM records r WHERE {mine} AND r.immutable = 0 AND ("
                " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0)",
                [user_id, priv, term, term]))
        terms |= {s.value for s in seeds if s.value and len(s.value.strip()) >= 2}
        erase: set[str] = {s.id for s in seeds}
        # id link: the episodes the seed facts were extracted from (facts only: a summary's
        # parents are whole sessions and are handled by content match instead)
        for s in seeds:
            if s.kind not in (Kind.USER_FACT, Kind.CANDIDATE_BELIEF):
                continue
            for p in self._load(list(s.derived_from)):
                if p.kind == Kind.EPISODE and (p.provenance.user_id == user_id or priv in p.source_scopes):
                    erase.add(p.id)
        # content match over all of this user's records (any kind)
        for term in terms:
            erase |= set(self._ids(
                f"SELECT r.id FROM records r WHERE {mine} AND r.immutable = 0 AND ("
                " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0)",
                [user_id, priv, term, term]))
        erase = self._descendants(erase)
        doomed = self._load(sorted(erase))
        if any(r.immutable for r in doomed):
            raise ImmutableRecordError("erasure cascade reached a canon anchor; canon must not derive from user data")
        now = self.clock()
        sessions = {r.provenance.session_id for r in doomed if r.provenance.session_id}
        kinds: dict[str, int] = defaultdict(int)
        for r in doomed:
            kinds[r.kind.value] += 1
        ids = [r.id for r in doomed]
        with self.db:
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                q = ",".join("?" * len(chunk))
                self.db.execute(f"DELETE FROM embeddings WHERE record_id IN ({q})", chunk)
                self.db.execute(f"DELETE FROM record_scopes WHERE record_id IN ({q})", chunk)
                self.db.execute(f"DELETE FROM derivations WHERE child_id IN ({q}) OR parent_id IN ({q})", chunk + chunk)
                self.db.execute(f"DELETE FROM records WHERE id IN ({q})", chunk)
            self.db.executemany(
                "INSERT INTO tombstones (id_hash, t, reason) VALUES (?, ?, ?)",
                [(hashlib.sha256(i.encode()).hexdigest(), now, reason) for i in ids],
            )
        report = ErasureReport(user_id=user_id, reason=reason, t=now, deleted_ids=ids, kinds=dict(kinds),
                               sessions=sessions, terms=terms)
        if regenerate and kinds.get(Kind.SUMMARY.value):
            summ = regenerate if not isinstance(regenerate, bool) else None
            for s in sorted(sessions):
                new = self.consolidate(s, summ)
                if new is not None:
                    report.regenerated.append(new.id)
        for hook in list(self.erasure_hooks):
            try:
                hook(report)
            except Exception as e:  # a failing cache hook must not undo the erasure
                report.hook_errors.append(f"{getattr(hook, '__name__', hook)}: {e!r}")
        return report

    def verify_erased(self, term: str, user_id: str, *, raw_file: bool = False) -> list[str]:
        """Search every table for residue of ``term`` belonging to ``user_id``; returns hits
        (must be empty after :meth:`forget`). ``raw_file`` additionally greps the DB file
        bytes (only meaningful if no other user legitimately stores the term)."""
        priv = private_scope(user_id)
        hits: list[str] = []
        like = [term, term, term, term, term]
        for r in self.db.execute(
            f"SELECT r.id FROM records r WHERE {self._user_records_sql()} AND ("
            " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0"
            " OR instr(lower(coalesce(r.subject, '')), lower(?)) > 0 OR instr(lower(r.provenance), lower(?)) > 0"
            " OR instr(lower(r.meta), lower(?)) > 0)", [user_id, priv, *like]):
            hits.append(f"records:{r[0]}")
        for r in self.db.execute("SELECT rowid FROM tombstones WHERE instr(lower(reason), lower(?)) > 0", [term]):
            hits.append(f"tombstones:{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM embeddings WHERE record_id NOT IN (SELECT id FROM records)"):
            hits.append(f"embeddings(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM record_scopes WHERE record_id NOT IN (SELECT id FROM records)"):
            hits.append(f"record_scopes(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT child_id, parent_id FROM derivations WHERE child_id NOT IN (SELECT id FROM records)"
                " OR parent_id NOT IN (SELECT id FROM records)"):
            hits.append(f"derivations(orphan):{r[0]}->{r[1]}")
        if raw_file and self.path != ":memory:":
            needle = term.encode("utf-8")
            for p in (Path(self.path), Path(self.path + "-journal"), Path(self.path + "-wal")):
                if p.exists() and needle in p.read_bytes():
                    hits.append(f"file:{p.name}")
        return hits


def _norm(v: str | None) -> str:
    return "".join((v or "").lower().split()).strip("。.!！'\"")
