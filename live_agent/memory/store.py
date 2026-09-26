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

import asyncio
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
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

log = logging.getLogger("live_agent.memory")

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
CREATE TABLE IF NOT EXISTS erasure_receipts (
    id TEXT PRIMARY KEY, user_hash TEXT NOT NULL, t REAL NOT NULL, reason TEXT NOT NULL,
    deleted_ids TEXT NOT NULL, kinds TEXT NOT NULL, sessions TEXT NOT NULL,
    required TEXT NOT NULL, acks TEXT NOT NULL, content_lost INTEGER NOT NULL DEFAULT 0
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


class ScopeViolationError(ValueError):
    """A write would widen visibility: e.g. a public record with a private input, a user
    fact in canon, or a record mixing two users' private scopes. Callers must not retry
    the write in a wider scope."""


class ErasureInProgressError(RuntimeError):
    """The store is blocked while :meth:`MemoryStore.forget_async` runs in a worker thread."""


class ErasureIncompleteError(RuntimeError):
    """Raised by :meth:`ErasureReport.raise_if_incomplete` when not every purge target acked."""


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
class PurgeAck:
    ok: bool
    detail: str = ""


@dataclass
class ErasureVerification:
    """Structured result of :meth:`MemoryStore.verify_erased`; ``ok`` iff every failing list is empty.

    ``foreign_hits`` (term found in another user's private records or in canon-only
    records) is informational: those rows are not this user's to erase.
    """

    surviving: list[str] = field(default_factory=list)  # deleted ids still present / referenced
    missing_tombstones: list[str] = field(default_factory=list)  # deleted ids without a tombstone
    term_hits: list[str] = field(default_factory=list)  # term residue in erasable records (any scope)
    orphans: list[str] = field(default_factory=list)  # index / embedding / edge rows without a record
    file_hits: list[str] = field(default_factory=list)  # term bytes still in the DB file(s)
    similar: list[str] = field(default_factory=list)  # derived artifacts semantically close to erased content
    review: list[str] = field(default_factory=list)  # similar user-origin records (need a human / user decision)
    foreign_hits: list[str] = field(default_factory=list)  # informational only

    @property
    def hits(self) -> list[str]:
        return [*self.surviving, *self.missing_tombstones, *self.term_hits, *self.orphans, *self.file_hits,
                *self.similar]

    @property
    def ok(self) -> bool:
        return not self.hits


MEMORY_DB_TARGET = "memory_db"
SIMILARITY_REVIEW_TARGET = "similarity_review"  # pending while similar user records await review
# kinds the similarity sweep deletes (persona / derived artifacts); user-origin kinds are only reported
_SWEEP_DELETE = (Kind.GENERATED_EVENT, Kind.SUMMARY, Kind.LEDGER, Kind.PROCEDURAL)


@dataclass
class ErasureReport:
    """Result of :meth:`MemoryStore.forget`; passed to purge hooks.

    ``terms`` are held in memory only (never persisted) so hooks can scrub LLM prompt
    caches, unsent BlockScripts and recordings; ``sessions`` tells which generator / LLM
    sessions to restart from canon anchors.

    Erasure is **complete** only when every name in ``required_targets`` has an ok
    acknowledgement in ``acks`` (the store acks ``memory_db`` itself after verifying the
    deletion), and no hook raised. Anything else is a failed erasure: the caller must
    report it as failed and retry the missing purges. Deleted records stay deleted.
    Asynchronous purges (generator reset, recordings) ack later via :meth:`acknowledge`.
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
    required_targets: list[str] = field(default_factory=list)
    acks: dict[str, PurgeAck] = field(default_factory=dict)
    verification: ErasureVerification | None = None
    swept_ids: list[str] = field(default_factory=list)  # derived artifacts deleted by the similarity sweep
    review_ids: list[str] = field(default_factory=list)  # similar user-origin records kept for review
    # in-memory only (never persisted): embeddings and texts of the erased content, for verification
    query_vecs: Any = field(default=None, repr=False)
    erased_texts: list[str] = field(default_factory=list, repr=False)
    # pending-erasure receipt (persisted until every required target acks; see MemoryStore.forget)
    receipt_id: str = ""
    # True when resumed after the in-memory content (terms / texts) was lost: purge targets
    # must then purge every session in ``sessions`` wholesale
    content_lost: bool = False
    _on_change: Any = field(default=None, repr=False, compare=False)

    def acknowledge(self, target: str, ok: bool = True, detail: str = "") -> None:
        if target not in self.required_targets:
            self.required_targets.append(target)
        prev = self.acks.get(target)
        if prev is not None and not prev.ok and ok:
            detail = f"{detail} (after earlier failure: {prev.detail})".strip()
        self.acks[target] = PurgeAck(bool(ok), detail)
        if self._on_change is not None:
            self._on_change(self)

    @property
    def pending_targets(self) -> list[str]:
        return [t for t in self.required_targets if not (t in self.acks and self.acks[t].ok)]

    @property
    def complete(self) -> bool:
        return not self.pending_targets

    def raise_if_incomplete(self) -> None:
        if not self.complete:
            raise ErasureIncompleteError(
                f"erasure not complete; pending purge targets: {self.pending_targets}; errors: {self.hook_errors}")


def _atomic(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Run a MemoryStore method as one transaction (retire + insert + lineage + commit);
    stale hooks fire only after the commit, nothing is left half-applied on error."""
    import functools

    @functools.wraps(fn)
    def wrapper(self: MemoryStore, *a: Any, **kw: Any) -> Any:
        with self._tx():
            return fn(self, *a, **kw)

    return wrapper


# Erased content needed to retry external purges (terms, texts, vectors) lives only in this
# process's memory, keyed by (db path, receipt id); it is never written to disk.
_RECEIPT_CONTENT: dict[tuple[str, str], dict[str, Any]] = {}
_RECEIPT_LOCK = threading.Lock()


def _user_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()


def _hook_name(hook: Callable[..., Any]) -> str:
    return str(getattr(hook, "purge_target", None) or getattr(hook, "__qualname__", None) or repr(hook))


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
    """Long-term memory for one deployment. Not thread-safe; use one instance per process
    (``forget_async`` is the one operation that runs off-thread, on its own connection)."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        embedder: Embedder | None = None,
        extractor: Extractor | None = None,
        clock: Callable[[], float] = time.time,
        echo_threshold: float = 0.5,
        erase_sim_threshold: float = 0.5,
        journal_mode: str | None = None,
        echo_lexical_floor: float = 0.4,
        viewer_rate: tuple[int, float] = (5, 10.0),
        viewer_max_len: int = 200,
        recency_tau_s: float = 3 * 86400.0,
        weights: tuple[float, float, float] = (0.6, 0.2, 0.2),
    ) -> None:
        self.path = str(path)
        self.embedder: Embedder = embedder or HashingEmbedder()
        self.extractor: Extractor = extractor or RuleExtractor()
        # settings a worker connection (forget_async) must share
        self._worker_config: dict[str, Any] = {
            "embedder": self.embedder, "extractor": self.extractor, "clock": clock,
            "echo_threshold": echo_threshold, "erase_sim_threshold": erase_sim_threshold,
            "echo_lexical_floor": echo_lexical_floor, "viewer_rate": viewer_rate,
            "viewer_max_len": viewer_max_len, "recency_tau_s": recency_tau_s, "weights": weights}
        self._erasing = False
        self._async_lock: asyncio.Lock | None = None
        self._content_key = os.path.abspath(self.path) if self.path != ":memory:" else f":memory:{id(self)}"
        self._deferred_receipts: list[ErasureReport] = []
        self.clock = clock
        self.echo_threshold = echo_threshold
        # estimate (HashingEmbedder cosine), not calibrated: see forget()
        self.erase_sim_threshold = erase_sim_threshold
        self.echo_lexical_floor = echo_lexical_floor
        self.viewer_max_len = viewer_max_len
        self.recency_tau_s = recency_tau_s
        self.weights = weights
        self._viewer_limiter = _RateLimiter(viewer_rate[0], viewer_rate[1], clock)
        self.stats: dict[str, int] = defaultdict(int)
        # hooks: erasure -> external caches; stale -> summary regeneration etc.
        # Every erasure hook is a *required* purge target: it must return a truthy ack
        # (True / non-empty detail string); None, False or an exception leaves the
        # erasure incomplete (see ErasureReport.complete). Name a hook by setting
        # ``hook.purge_target = "<name>"`` or use :meth:`register_purge_target`.
        self.erasure_hooks: list[Callable[[ErasureReport], Any]] = []
        self.required_purge_targets: set[str] = set()  # must ack, even without a hook
        self.purge_hooks: dict[str, Callable[[ErasureReport], Any]] = {}
        self._tx_depth = 0
        self._pending_stale: list[Record] = []  # stale hooks fire only after a successful commit
        self.stale_hooks: list[Callable[[list[Record]], None]] = []
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA secure_delete = ON")
        if int(self.db.execute("PRAGMA secure_delete").fetchone()[0]) != 1:
            raise RuntimeError("SQLite build does not support secure_delete; erasure could not be physical")
        if journal_mode:
            if journal_mode.lower() not in ("delete", "truncate", "persist", "wal"):
                raise ValueError(f"unsupported journal_mode {journal_mode!r}")
            self.db.execute(f"PRAGMA journal_mode = {journal_mode}")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(_SCHEMA)
        self.db.commit()

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def _tx(self) -> Iterator[None]:
        """One atomic unit of work: nested ``_commit`` calls are deferred to the outermost
        block; any exception rolls everything back and drops queued stale hooks."""
        self._tx_depth += 1
        try:
            yield
        except BaseException:
            self._tx_depth -= 1
            if self._tx_depth == 0:
                self.db.rollback()
                self._pending_stale.clear()
            raise
        self._tx_depth -= 1
        self._commit()

    def _commit(self) -> None:
        """Commit unless inside :meth:`_tx`; then fire queued stale hooks (after the commit)."""
        if self._tx_depth:
            return
        self.db.commit()
        stale, self._pending_stale = self._pending_stale, []
        if stale:
            for hook in list(self.stale_hooks):
                hook(stale)

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
        self._guard()
        validate_scope(scope)
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        source_scopes = union_scopes(scope, parents)
        self._check_write_scope(kind, scope, source_scopes, provenance)
        if (kind == Kind.GENERATED_EVENT and scope.startswith("public:")
                and (meta or {}).get("lineage") not in self.COMPLETE_LINEAGE):
            raise ScopeViolationError("public persona output requires complete source lineage")
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
            self._commit()
        return rec

    @staticmethod
    def _check_write_scope(kind: Kind, scope: str, source_scopes: frozenset[str], prov: Provenance) -> None:
        """Fail-closed scope rules for every write (review findings 12/13)."""
        if scope == CANON:
            if source_scopes != {CANON}:
                raise ScopeViolationError("canon records may only derive from canon records")
            if kind not in (Kind.LEDGER, Kind.PROCEDURAL):
                raise ScopeViolationError(f"{kind.value} records can never be canon")
            if prov.user_id or prov.speaker in ("user", "agent") or prov.speaker.startswith("viewer:"):
                raise ScopeViolationError("user / viewer / agent-origin records can never be canon")
        privs = {s for s in source_scopes if is_private(s)}
        if scope.startswith("public:") and privs:
            raise ScopeViolationError(f"public write {scope!r} has private inputs {sorted(privs)}")
        if len(privs) > 1 or (is_private(scope) and privs - {scope}):
            raise ScopeViolationError(f"record would mix private scopes {sorted(privs | {scope})}")

    def existing_ids(self, ids: Iterable[str]) -> list[str]:
        """The subset of ``ids`` that still exist (order kept)."""
        ids = list(dict.fromkeys(ids))
        have: set[str] = set()
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            have |= set(self._ids(f"SELECT id FROM records WHERE id IN ({','.join('?' * len(chunk))})", chunk))
        return [i for i in ids if i in have]

    def register_purge_target(self, name: str, hook: Callable[[ErasureReport], Any] | None = None) -> None:
        """Declare an external store (recordings, generator state, LLM KV ...) that must
        acknowledge every erasure. With ``hook`` it is called synchronously and must return
        a truthy ack; without, the owner acks later via :meth:`ErasureReport.acknowledge`."""
        self.required_purge_targets.add(name)
        if hook is not None:
            self.purge_hooks[name] = hook

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
        self._guard()
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
        self._guard()
        return [r[0] for r in self.db.execute(sql, params)]

    def _set_status(self, record_id: str, status: Status, **cols: Any) -> None:
        self._guard()
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

    @staticmethod
    def session_write_scope(mode: str | None, user_id: str, stream_id: str | None) -> str:
        """Write scope of an authenticated session: ``private:<user>`` for a 1:1 session
        (also the fail-closed default when the mode is unknown), ``public:<stream>`` for a
        livestream. Never canon; never taken from a client-supplied utterance field."""
        if mode in (None, "", "private"):
            return private_scope(user_id)
        if mode == "public":
            if not stream_id:
                raise ValueError("public session requires stream_id")
            return public_scope(stream_id)
        raise ScopeViolationError(f"session mode {mode!r} cannot be a write scope (expected private/public)")

    def _utterance_scope(self, utt: Utterance, user_id: str, stream_id: str | None, mode: str | None) -> str:
        scope = self.session_write_scope(mode, user_id, stream_id)
        claimed = (utt.scope or "").strip()
        if claimed and claimed not in (scope, mode or "private"):
            # The utterance's own scope field is client data: ignored, but counted and logged.
            self.stats["utterance_scope_ignored"] += 1
            log.warning("utterance %s claims scope %r; using session scope %r", utt.uid, claimed, scope)
        return scope

    # ------------------------------------------------------------------ write policy

    @_atomic
    def ingest_user_utterance(
        self,
        utt: Utterance,
        extractor: Extractor | None = None,
        *,
        user_id: str,
        stream_id: str | None = None,
        mode: str | None = None,
    ) -> IngestResult:
        """Append the turn to the episode log and store candidate facts per the write policy.

        The write scope comes from the authenticated session ``mode`` ("private" /
        "public"; ``None`` = private), never from ``utt.scope``; canon is refused.
        Persona utterances are routed to the generated-event log (lineage unknown);
        viewer utterances to :meth:`ingest_viewer_chat`. Only ``own_assertion``
        sentences produce facts.
        """
        ex = extractor or self.extractor
        scope = self._utterance_scope(utt, user_id, stream_id, mode)
        if utt.speaker == "persona":
            gen = self.record_generated_event(utt.text, utt.session_id, scope, source_id=utt.uid, user_id=user_id,
                                              derived_from=None)
            return IngestResult(episode=None, generated_event=gen)
        if utt.speaker.startswith("viewer:"):
            # the role comes from the authenticated session: viewers exist only in a public one
            if mode != "public":
                self.stats["viewer_outside_public"] += 1
                raise ScopeViolationError("viewer events are only accepted in an authenticated public session")
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
        self._commit()
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

    #: lineage values: "complete" = ``derived_from`` lists every memory input; "none" = the
    #: caller asserts there were no memory inputs (``derived_from`` empty); anything else
    #: ("unknown", "session_recall_superset", ...) is incomplete.
    COMPLETE_LINEAGE = ("complete", "none")

    def record_generated_event(
        self,
        text: str,
        session_id: str,
        scope: str,
        *,
        source_id: str = "",
        user_id: str = "",
        derived_from: Sequence[str] | None = None,
        request_index: int | None = None,
        lineage: str | None = None,
    ) -> Record:
        """Log persona output (speech / shown content). Never promoted to a user fact.

        ``scope`` must be the *session's* write scope (persona lines in a private
        conversation are private). ``derived_from`` lists the memory records the line was
        conditioned on; the line inherits their ``source_scopes`` and erasure / correction
        cascade through them. ``lineage`` says how complete that list is (default
        "unknown"; see :attr:`COMPLETE_LINEAGE`). Fail closed: a **public** line requires
        complete lineage ("complete", or "none" with no parents) and no private input,
        otherwise :class:`ScopeViolationError` and nothing is written. Private lines may
        have incomplete lineage (they stay private).
        """
        validate_scope(scope)
        if scope == CANON:
            raise ScopeViolationError("persona output is never canon")
        lineage = lineage or "unknown"
        if lineage == "none" and derived_from:
            raise ValueError("lineage='none' asserts no memory inputs but derived_from is non-empty")
        if lineage == "complete" and derived_from is None:
            raise ValueError("lineage='complete' requires derived_from")
        if not user_id and is_private(scope):
            user_id = scope.split(":", 1)[1]
        meta: dict[str, Any] = {"lineage": lineage}
        if request_index is not None:
            meta["request_index"] = request_index
        prov = Provenance(source_id=source_id, speaker="persona", session_id=session_id,
                          timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.GENERATED_EVENT, scope, text, ClaimType.SYSTEM_OBSERVATION, prov,
            derived_from=derived_from or (), meta=meta,
        )

    @_atomic
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
        self._commit()
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

    @_atomic
    def add_ledger(
        self,
        text: str,
        scope: str | None = None,
        *,
        canonical: bool = False,
        key: str | None = None,
        derived_from: Sequence[str] = (),
        session_id: str = "",
        user_id: str = "",
        curated: bool = False,
    ) -> Record:
        """Persona / world continuity entry. Canonical anchors are immutable and canon-only.

        Learned (non-canonical) entries must name their sources (``derived_from``); their
        scope is derived from the sources, the most restrictive one wins (a user's private
        scope > a public stream), and an explicit ``scope`` may only be narrower. Sources
        that are all canon give no scope: pass one. Entries without sources are allowed
        only as operator-authored ``curated=True`` entries with an explicit scope (never a
        public default). A non-canonical entry with a ``key`` supersedes the previous entry
        with the same key in the same scope (bi-temporal: old one keeps ``valid_to``).
        """
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        if canonical:
            if scope not in (None, CANON):
                raise ValueError("canonical anchors must have scope 'canon'")
            scope = CANON
        else:
            if scope == CANON:
                raise ValueError("only canonical anchors live in scope 'canon'")
            if not parents:
                if not curated:
                    raise ValueError("learned ledger entries require derived_from (source lineage); "
                                     "operator-authored entries pass curated=True and an explicit scope")
                if scope is None:
                    raise ValueError("curated ledger entries need an explicit scope")
            else:
                scopes = frozenset().union(*(p.source_scopes for p in parents))
                privs = sorted(x for x in scopes if is_private(x))
                pubs = sorted(x for x in scopes if x.startswith("public:"))
                if len(privs) > 1:
                    raise ScopeViolationError(f"ledger entry would mix private scopes {privs}")
                derived = privs[0] if privs else (pubs[0] if pubs else None)
                if scope is None:
                    if derived is None:
                        raise ValueError("ledger entry derived only from canon needs an explicit scope")
                    scope = derived
                elif derived is not None and scope != derived and not (is_private(scope) and not is_private(derived)):
                    raise ScopeViolationError(f"ledger scope {scope!r} is wider than its sources ({derived!r})")
            validate_scope(scope)
        if key and not canonical:
            old = self._load(self._ids(
                "SELECT id FROM records WHERE kind = 'ledger' AND scope = ? AND status = 'active'"
                " AND json_extract(meta, '$.key') = ?", (scope, key)))
            self._supersede(old)
        if not user_id and is_private(scope):
            user_id = scope.split(":", 1)[1]
        prov = Provenance(speaker="operator" if curated else "system", session_id=session_id,
                          timestamp=self.clock(), user_id="" if canonical else user_id)
        return self.add_record(
            Kind.LEDGER, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=[p.id for p in parents],
            immutable=canonical, meta={"key": key, "canonical": canonical, "curated": curated},
        )

    @_atomic
    def add_procedure(
        self,
        text: str,
        outcome: str,
        *,
        derived_from: Sequence[str] = (),
        scope: str | None = None,
        tags: Sequence[str] = (),
        curated: bool = False,
    ) -> Record:
        """A²RD-style prompt-library entry: what worked (``success``) or failed (``failure``).

        Learned entries must name their sources (``derived_from``: the episodes / generated
        events / verdict records they were learned from). Their scope is derived from the
        sources: the most restrictive one wins (a user's private scope > a public stream >
        canon), so a procedure learned in a private session stays private. An explicit
        ``scope`` may only be *more* restrictive than the derived one. Canon therefore
        requires canon-only sources, or ``curated=True`` (operator-authored, no sources).
        """
        if outcome not in ("success", "failure"):
            raise ValueError("outcome must be 'success' or 'failure'")
        parents = [self._require(pid) for pid in dict.fromkeys(derived_from)]
        if curated:
            if parents or scope not in (None, CANON):
                raise ValueError("curated procedures are operator-authored canon entries without sources")
            derived = CANON
        else:
            if not parents:
                raise ValueError("learned procedures require derived_from (source lineage)")
            scopes = frozenset().union(*(p.source_scopes for p in parents))
            privs = sorted(s for s in scopes if is_private(s))
            pubs = sorted(s for s in scopes if s.startswith("public:"))
            if len(privs) > 1:
                raise ScopeViolationError(f"procedure would mix private scopes {privs}")
            derived = privs[0] if privs else (pubs[0] if pubs else CANON)
        if scope is None or scope == derived:
            scope = derived
        elif not (is_private(scope) and not is_private(derived)):  # only narrowing to private is allowed
            raise ScopeViolationError(f"procedure scope {scope!r} is wider than its sources ({derived!r})")
        user_id = scope.split(":", 1)[1] if is_private(scope) else ""
        prov = Provenance(speaker="operator" if curated else "system", timestamp=self.clock(), user_id=user_id)
        return self.add_record(
            Kind.PROCEDURAL, scope, text, ClaimType.SYSTEM_OBSERVATION, prov, derived_from=[p.id for p in parents],
            meta={"outcome": outcome, "tags": list(tags), "curated": curated},
        )

    # ------------------------------------------------------------------ confirmation / correction

    @_atomic
    def confirm(self, record_id: str, confirmation_id: str | None = None, *,
                question_id: str | None = None) -> Record:
        """User explicitly confirms a pending echo / conflicting fact or a candidate belief.

        ``confirmation_id`` is the ``episode`` record of the user's confirming turn. It is
        **required** for a candidate belief: the belief is not rewritten; a *new*
        ``own_assertion`` user fact (speaker="user", derived from the confirming episode and
        the belief) is created and returned, and the belief is kept as provenance (status
        superseded, ``meta.confirmed_as``). It is also required for a pending echo /
        conflicting user fact, and is linked into that fact's lineage.

        Binding rule (the turn must confirm *this* proposition, see :meth:`_confirmation_binds`):
        either (a) the turn restates it: value + predicate cue + subject cue; or (b)
        ``question_id`` names the persona line that asked about it (a generated event
        derived from the record, same session) and the turn is an affirmative answer and
        the first user turn after that question.
        """
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending (status={rec.status.value})")
        owner = rec.provenance.user_id
        conf = self._require(confirmation_id) if confirmation_id else None
        if conf is not None:
            if conf.kind != Kind.EPISODE or conf.provenance.speaker != "user" or conf.provenance.user_id != owner:
                raise ValueError("confirmation must be an episode spoken by the record's owner")
            if conf.id in rec.derived_from or conf.created_at < rec.created_at:
                raise ValueError("the confirming turn must be a later turn, not the record's own source")
            if conf.claim_type in (ClaimType.QUESTION, ClaimType.HYPOTHETICAL, ClaimType.QUOTE_OF_PERSONA):
                raise ValueError(f"a {conf.claim_type.value} turn cannot confirm a memory")
            why = self._confirmation_binds(rec, conf, question_id)
            if why is None:
                raise ValueError("confirming turn is not bound to this proposition "
                                 "(no subject+predicate+value restatement and no answered question)")
        else:
            raise ValueError("confirmation requires the user's confirming turn (episode id)")
        now = self.clock()
        others: list[Record] = []
        if rec.subject and rec.predicate and is_single_valued(rec.predicate):
            others = [r for r in self._current_facts(rec.subject, rec.predicate, owner, claim=None)
                      if r.id != rec.id and r.kind == Kind.USER_FACT
                      and r.claim_type in (ClaimType.OWN_ASSERTION, ClaimType.SYSTEM_OBSERVATION)
                      and _norm(r.value) != _norm(rec.value)]
            self._supersede(others)
        if rec.kind == Kind.CANDIDATE_BELIEF:
            assert conf is not None
            prov = Provenance(source_id=conf.provenance.source_id, speaker="user",
                              session_id=conf.provenance.session_id, timestamp=now, user_id=owner)
            fact = self.add_record(
                Kind.USER_FACT, private_scope(owner) if owner else rec.scope, rec.text, ClaimType.OWN_ASSERTION,
                prov, derived_from=[conf.id, rec.id], subject=rec.subject, predicate=rec.predicate,
                value=rec.value, valid_from=now,
                meta={"confirmed_from": rec.id, "confirmed_from_claim": ClaimType.AGENT_INFERENCE.value,
                      "confirmed_by": conf.id, "confirmed_at": now,
                      **({"supersedes": [r.id for r in others]} if others else {})},
                commit=False,
            )
            # the inference is kept (for audit / lineage) but no longer usable on its own
            self._set_status(rec.id, Status.SUPERSEDED, valid_to=now)
            self._update_meta(rec.id, confirmed_as=fact.id, confirmed_by=conf.id, confirmed_rule=why)
            self._commit()
            return self._require(fact.id)
        if others:
            self._update_meta(rec.id, supersedes=[r.id for r in others])
        if conf is not None:
            self._link_parent(rec.id, conf)
        self._set_status(rec.id, Status.ACTIVE, valid_from=now)
        self._update_meta(rec.id, confirmed_at=now, **({"confirmed_by": conf.id} if conf else {}))
        self._commit()
        return self._require(rec.id)

    def _confirmation_binds(self, rec: Record, conf: Record, question_id: str | None) -> str | None:
        """Return the rule that binds ``conf`` to ``rec`` or None.

        * "proposition": one clause of the turn (split on ，。；,;！？!? and 但/而/可是/并且/but/
          and/whereas/although) restates the subject-predicate-value proposition: it contains
          the value **and** a predicate cue (e.g. 住/live for ``lives_in``) **and** a subject
          cue (我/I for the user; 妹妹/sister for ``user:<id>/sister``) **as the clause's
          grammatical subject**: the text before the first predicate cue must contain the
          subject cue, must not name another person (我妈妈住在北京 does not confirm "I live in
          Beijing") and must not negate the predicate (我不住在北京). A bare value mention
          ("I visited Beijing") or cues spread over clauses ("我住在北京，我妹妹住在上海")
          do not bind.
        * "answer": ``question_id`` is the persona line that asked about this record (a
          generated event derived from it, same session) and the turn is an affirmative
          answer and the first user turn after it.
        Negated turns never bind.
        """
        if _NEGATION.search(conf.text):
            return None
        nv = _norm(rec.value)
        text = conf.text
        if len(nv) >= 2:
            for clause in _clauses(text):  # all three cues must come from the same clause
                if nv in _norm(clause) and _clause_states(clause, rec.subject, rec.predicate):
                    return "proposition"
        if question_id:
            q = self._require(question_id)
            if (q.kind == Kind.GENERATED_EVENT and rec.id in q.derived_from
                    and q.provenance.session_id == conf.provenance.session_id
                    and q.provenance.timestamp <= conf.provenance.timestamp and _AFFIRM.search(text)):
                between = self._ids(
                    "SELECT id FROM records WHERE kind = 'episode' AND session_id = ? AND owner = ?"
                    " AND t >= ? AND t < ? AND id != ?",
                    [conf.provenance.session_id, conf.provenance.user_id, q.provenance.timestamp,
                     conf.provenance.timestamp, conf.id])
                if not between:
                    return "answer"
        return None

    def _link_parent(self, child_id: str, parent: Record) -> None:
        """Add a lineage edge after insertion (and widen the child's source_scopes accordingly)."""
        child = self._require(child_id)
        scopes = union_scopes(child.scope, [child, parent])
        self._check_write_scope(child.kind, child.scope, scopes, child.provenance)
        self.db.execute("INSERT OR IGNORE INTO derivations (child_id, parent_id) VALUES (?, ?)", (child_id, parent.id))
        self.db.executemany("INSERT OR IGNORE INTO record_scopes (record_id, scope) VALUES (?, ?)",
                            [(child_id, sc) for sc in sorted(scopes)])

    @_atomic
    def reject(self, record_id: str) -> Record:
        rec = self._require(record_id)
        if rec.status != Status.PENDING:
            raise ValueError(f"{record_id} is not pending")
        self._set_status(rec.id, Status.REJECTED)
        self._commit()
        return self._require(rec.id)

    @_atomic
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
        self._commit()
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
        self._pending_stale.extend(stale)
        self._commit()
        return stale

    @_atomic
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
        self._guard()
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

    @_atomic
    def consolidate(self, session_id: str, summarizer: Summarizer | None = None) -> Record | None:
        """Sleep-time summary of one session. Writes a ``summary`` record whose
        ``derived_from`` lists every input and whose ``source_scopes`` is their union.
        Supersedes any previous summary of the same session."""
        summ = summarizer or ExtractiveSummarizer()
        now = self.clock()
        # only usable inputs: stale / superseded / rejected / pending records never feed a summary
        ids = self._ids(
            "SELECT id FROM records WHERE session_id = ? AND status = 'active' AND ("
            " kind IN ('episode', 'generated_event')"
            " OR (kind = 'user_fact' AND (valid_to IS NULL OR valid_to > ?)))"
            " ORDER BY t", [session_id, now])
        recs = self._load(ids)
        # persona lines with unknown / incomplete lineage that repeat a corrected-away value
        retracted = self._retracted_values({r.provenance.user_id for r in recs if r.provenance.user_id})
        if retracted:
            recs = [r for r in recs if not (r.kind == Kind.GENERATED_EVENT
                                            and any(v in _norm(r.text) for v in retracted))]
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
            self._commit()
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

    def _retracted_values(self, owners: Iterable[str]) -> set[str]:
        """Normalised values of this user's superseded facts that no current fact still holds."""
        old: set[str] = set()
        cur: set[str] = set()
        for owner in owners:
            for r in self.db.execute(
                    "SELECT status, value FROM records WHERE owner = ? AND kind IN ('user_fact', 'candidate_belief')"
                    " AND value IS NOT NULL AND status IN ('active', 'pending', 'superseded')", [owner]):
                (cur if r["status"] != "superseded" else old).add(_norm(r["value"]))
        return {v for v in old - cur if len(v) >= 2}

    # ------------------------------------------------------------------ erasure

    def _user_records_sql(self) -> str:
        return ("(r.owner = ? OR EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id"
                " AND rs.scope = ?))")

    def _erasable_sql(self) -> str:
        """Records a user's erasure may touch by *content*: their own records, plus any
        public-scoped record carrying no other user's private scope (a public artifact that
        repeats the user's data may be untagged; over-deletion is the safe side). Canon-only
        records and other users' private records are never touched. Params: (user, priv, priv)."""
        return (
            "r.immutable = 0 AND (" + self._user_records_sql() +
            " OR (EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND rs.scope LIKE 'public:%')"
            " AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id"
            " AND rs.scope LIKE 'private:%' AND rs.scope != ?)))"
        )

    def _content_match(self, term: str, user_id: str) -> list[str]:
        priv = private_scope(user_id)
        return self._ids(
            f"SELECT r.id FROM records r WHERE {self._erasable_sql()} AND ("
            " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0)",
            [user_id, priv, priv, term, term])

    def forget(
        self,
        target: str | Record,
        user_id: str,
        reason: str = "user_request",
        *,
        regenerate: bool | Summarizer = True,
        require: Iterable[str] = (),
        resume: str | None = None,
    ) -> ErasureReport:
        """Physically erase a fact (by record id / Record) or everything matching a query term.

        Pending-erasure receipts: every erasure writes a receipt (ids, kinds, sessions,
        required targets, ok flags; **no erased content**) that stays until every required
        target acked ok. ``resume=<receipt id>`` retries its pending targets instead of
        erasing anew; a record-id target that an unfinished receipt already deleted (or a
        term it erased, while nothing matches it any more) resumes that receipt automatically. The erased terms / texts needed by retries are kept in
        this process's memory only; if they are gone (restart), the resumed report has
        ``content_lost=True`` and purge targets must purge the listed sessions wholesale.
        See :meth:`pending_erasures`.

        Cascade: matched records -> source episodes (id link) -> every erasable record
        mentioning the value/term (this user's records of any kind, and public records
        carrying no other user's private scope) -> all descendants through
        ``derived_from``; plus their embeddings, scope rows, derivation edges and id
        references in other records' meta. A tombstone keeps only sha256(id), time and
        reason. Affected session summaries are regenerated from what remains.

        Fail-closed completion: the store verifies its own deletion (ids, descendants,
        term residue in every scope) and acks ``memory_db``; then every erasure hook is
        called and must return a truthy ack. ``require`` names further purge targets
        (recordings, generator state, LLM context ...) that must ack via
        :meth:`ErasureReport.acknowledge`. ``report.complete`` is False until all of them
        acked ok; a hook error never un-deletes anything.
        """
        hook_names = self._purge_hook_names()
        resume = resume or self._receipt_for_target(target, user_id)
        if resume:
            return self._run_purge_hooks(self._resume_report(resume, user_id), hook_names)
        report = self._forget_db(target, user_id, reason, regenerate=regenerate,
                                 require=self._required_names(hook_names, require))
        return self._run_purge_hooks(report, hook_names)

    # ------------------------------------------------------------------ erasure receipts

    def pending_erasures(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Unfinished erasures (receipt id, time, sessions, pending targets, content_lost)."""
        sql, args = "SELECT * FROM erasure_receipts", []
        if user_id is not None:
            sql, args = sql + " WHERE user_hash = ?", [_user_hash(user_id)]
        out = []
        for r in self.db.execute(sql + " ORDER BY t", args).fetchall():
            acks = json.loads(r["acks"])
            with _RECEIPT_LOCK:
                lost = bool(r["content_lost"]) or (self._content_key, r["id"]) not in _RECEIPT_CONTENT
            out.append({"receipt_id": r["id"], "t": r["t"], "sessions": json.loads(r["sessions"]),
                        "pending": [x for x in json.loads(r["required"]) if not acks.get(x)],
                        "content_lost": lost})
        return out

    def _receipt_for_target(self, target: str | Record, user_id: str) -> str | None:
        rid = target.id if isinstance(target, Record) else str(target).strip()
        if not rid or self.get(rid) is not None:
            return None
        rows = self.db.execute("SELECT id, deleted_ids FROM erasure_receipts WHERE user_hash = ? ORDER BY t DESC",
                               [_user_hash(user_id)]).fetchall()
        for r in rows:  # a record id this receipt deleted
            if rid in json.loads(r["deleted_ids"]):
                return r["id"]
        if rows and not self._content_match(rid, user_id):  # a term it erased (content in memory)
            with _RECEIPT_LOCK:
                for r in rows:
                    content = _RECEIPT_CONTENT.get((self._content_key, r["id"]))
                    if content and rid.lower() in {t.lower() for t in content["terms"]}:
                        return r["id"]
        return None

    def _write_receipt(self, report: ErasureReport) -> None:
        report.receipt_id = report.receipt_id or new_id("erasure")
        with _RECEIPT_LOCK:
            _RECEIPT_CONTENT[(self._content_key, report.receipt_id)] = {
                "terms": set(report.terms), "erased_texts": list(report.erased_texts),
                "query_vecs": report.query_vecs}
        self.db.execute(
            "INSERT OR REPLACE INTO erasure_receipts (id, user_hash, t, reason, deleted_ids, kinds, sessions,"
            " required, acks, content_lost) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (report.receipt_id, _user_hash(report.user_id), report.t, report.reason, json.dumps(report.deleted_ids),
             json.dumps(report.kinds), json.dumps(sorted(report.sessions)), json.dumps(report.required_targets),
             json.dumps({k: a.ok for k, a in report.acks.items()}), int(report.content_lost)))
        self._commit()

    def _save_receipt(self, report: ErasureReport) -> None:
        """Persist ack state (ok flags only; details can name content); drop when complete."""
        if not report.receipt_id:
            return
        if self._erasing:  # another erasure holds the DB: flushed when it finishes
            self._deferred_receipts.append(report)
            return
        if report.complete:
            self.db.execute("DELETE FROM erasure_receipts WHERE id = ?", [report.receipt_id])
            with _RECEIPT_LOCK:
                _RECEIPT_CONTENT.pop((self._content_key, report.receipt_id), None)
        else:
            self.db.execute("UPDATE erasure_receipts SET required = ?, acks = ?, content_lost = ? WHERE id = ?",
                            (json.dumps(report.required_targets),
                             json.dumps({k: a.ok for k, a in report.acks.items()}), int(report.content_lost),
                             report.receipt_id))
        self.db.commit()
        self._truncate_journals()  # receipt pages only, but keep the journals as clean as after the purge

    def _flush_deferred_receipts(self) -> None:
        pending, self._deferred_receipts = self._deferred_receipts, []
        for r in pending:
            self._save_receipt(r)

    def _resume_report(self, receipt_id: str, user_id: str) -> ErasureReport:
        row = self.db.execute("SELECT * FROM erasure_receipts WHERE id = ?", [receipt_id]).fetchone()
        if row is None:
            raise KeyError(f"no pending erasure receipt {receipt_id!r}")
        if row["user_hash"] != _user_hash(user_id):
            raise PermissionError("erasure receipt does not belong to this user")
        with _RECEIPT_LOCK:
            content = _RECEIPT_CONTENT.get((self._content_key, receipt_id))
        acks = json.loads(row["acks"])
        report = ErasureReport(
            user_id=user_id, reason=row["reason"], t=row["t"], deleted_ids=json.loads(row["deleted_ids"]),
            kinds=json.loads(row["kinds"]), sessions=set(json.loads(row["sessions"])),
            terms=set(content["terms"]) if content else set(), required_targets=json.loads(row["required"]),
            acks={k: PurgeAck(bool(v), "from receipt") for k, v in acks.items()},
            erased_texts=list(content["erased_texts"]) if content else [],
            query_vecs=content["query_vecs"] if content else None,
            receipt_id=receipt_id, content_lost=bool(row["content_lost"]) or content is None)
        if MEMORY_DB_TARGET in report.pending_targets:
            physical = self._physical_purge()
            report.verification = self.verify_erasure(report, raw_file=True)
            ok = report.verification.ok and not physical
            report.acknowledge(MEMORY_DB_TARGET, ok, "re-verified" if ok else f"residue: {report.verification.hits[:10]}")
        return report

    @property
    def erasing(self) -> bool:
        return self._erasing

    def _guard(self) -> None:
        if self._erasing:
            raise ErasureInProgressError("memory store is blocked while an erasure runs")

    async def forget_async(
        self,
        target: str | Record,
        user_id: str,
        reason: str = "user_request",
        *,
        regenerate: bool | Summarizer = True,
        require: Iterable[str] = (),
        resume: str | None = None,
    ) -> ErasureReport:
        """:meth:`forget` without blocking the event loop (VACUUM / checkpoint can be slow).

        The database work runs in a worker thread on its **own** SQLite connection (opened
        in that thread, same settings); this store is blocked meanwhile (any read / write
        raises :class:`ErasureInProgressError`, so nothing can re-derive from data being
        erased or hold a transaction that would stall VACUUM / the WAL checkpoint).
        Purge hooks then run on the caller's (event-loop) thread. Same report semantics as
        :meth:`forget`. Erasures are serialised. An in-memory DB (``:memory:``) cannot be
        opened from another thread, so it is erased inline.
        """
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        async with self._async_lock:
            hook_names = self._purge_hook_names()
            required = self._required_names(hook_names, require)
            resume = resume or self._receipt_for_target(target, user_id)
            if resume:  # retry of external purges; DB work only if memory_db is still pending
                return self._run_purge_hooks(self._resume_report(resume, user_id), hook_names)
            if self.path == ":memory:":
                report = self._forget_db(target, user_id, reason, regenerate=regenerate, require=required)
            else:
                self._guard()
                self.db.commit()  # this connection holds no transaction while the worker runs
                mode = self.journal_mode
                self._erasing = True
                try:
                    report = await asyncio.to_thread(self._forget_in_worker, target, user_id, reason,
                                                     regenerate, required, mode)
                finally:
                    self._erasing = False
                    self._flush_deferred_receipts()
            return self._run_purge_hooks(report, hook_names)

    def _forget_in_worker(self, target: str | Record, user_id: str, reason: str,
                          regenerate: bool | Summarizer, required: list[str], mode: str) -> ErasureReport:
        worker = MemoryStore(self.path, journal_mode=mode if mode in ("persist", "truncate") else None,
                             **self._worker_config)
        try:
            return worker._forget_db(target, user_id, reason, regenerate=regenerate, require=required)
        finally:
            worker.close()

    def _purge_hook_names(self) -> list[tuple[str, Callable[[ErasureReport], Any]]]:
        return [(_hook_name(h), h) for h in self.erasure_hooks] + list(self.purge_hooks.items())

    def _required_names(self, hook_names: list[tuple[str, Any]], require: Iterable[str]) -> list[str]:
        return list(dict.fromkeys([n for n, _ in hook_names] + sorted(self.required_purge_targets) + list(require)))

    def _forget_db(self, target: str | Record, user_id: str, reason: str, *,
                   regenerate: bool | Summarizer, require: Iterable[str]) -> ErasureReport:
        """The database part of :meth:`forget` (cascade, delete, physical purge, verification,
        ``memory_db`` ack); purge hooks are run by the caller."""
        priv = private_scope(user_id)
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
            seeds = self._load(self._content_match(term, user_id))
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
        for term in terms:
            erase |= set(self._content_match(term, user_id))
        erase = self._descendants(erase)
        # similarity sweep: unlinked paraphrases of the erased content (literal search misses them)
        query_vecs = self._erasure_query_vecs(erase, terms)
        swept, review = self._similar_records(query_vecs, user_id, exclude=erase)
        erase = self._descendants(erase | set(swept))
        review = [r for r in review if r not in erase]
        doomed = self._load(sorted(erase))
        if any(r.immutable for r in doomed):
            raise ImmutableRecordError("erasure cascade reached a canon anchor; canon must not derive from user data")
        now = self.clock()
        sessions = {r.provenance.session_id for r in doomed if r.provenance.session_id}
        kinds: dict[str, int] = defaultdict(int)
        for r in doomed:
            kinds[r.kind.value] += 1
        ids = [r.id for r in doomed]
        # captured before deletion, held in memory only: the raw-file check searches for these bytes
        erased_texts = sorted({x for r in doomed for x in (r.text, r.value or "", r.subject or "")
                               if len(x.strip()) >= 2 and not x.startswith("user:")})
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
            self._scrub_refs(set(ids))
        required = [MEMORY_DB_TARGET, *dict.fromkeys(list(require))]
        if review:
            required.append(SIMILARITY_REVIEW_TARGET)
        report = ErasureReport(user_id=user_id, reason=reason, t=now, deleted_ids=ids, kinds=dict(kinds),
                               sessions=sessions, terms=terms, required_targets=required,
                               swept_ids=sorted(swept), review_ids=review, query_vecs=query_vecs,
                               erased_texts=erased_texts)
        if regenerate and kinds.get(Kind.SUMMARY.value):
            summ = regenerate if not isinstance(regenerate, bool) else None
            for s in sorted(sessions):
                new = self.consolidate(s, summ)
                if new is not None:
                    report.regenerated.append(new.id)
        self._write_receipt(report)  # before the purge, so the journals are cleaned after it too
        physical = self._physical_purge()
        # raw-file verification is mandatory for a file-backed DB before acking memory_db
        report.verification = self.verify_erasure(report, raw_file=True)
        v = report.verification
        ok = v.ok and not physical
        report.acknowledge(MEMORY_DB_TARGET, ok, "verified (logical + raw file)" if ok
                           else f"residue: {v.hits[:10]}; physical purge: {physical or 'ok'}")
        return report

    def _run_purge_hooks(self, report: ErasureReport,
                         hook_names: list[tuple[str, Callable[[ErasureReport], Any]]]) -> ErasureReport:
        report._on_change = self._save_receipt  # later acks (e.g. the orchestrator's) are persisted
        for name, hook in hook_names:
            if name in report.acks and report.acks[name].ok:
                continue  # acked before (resumed receipt)
            try:
                ack = hook(report)
            except Exception as e:  # noqa: BLE001 -- any failure leaves the erasure incomplete (never undone)
                report.hook_errors.append(f"{name}: {e!r}")
                report.acknowledge(name, False, f"error: {e!r}")
                continue
            if name in report.acks and report.acks[name].ok:
                continue  # the hook acknowledged through the report itself
            report.acknowledge(name, bool(ack), ack if isinstance(ack, str) else ("" if ack else "no ack"))
        if not report.complete:
            log.error("erasure for %s incomplete; pending purge targets %s (receipt %s)",
                      _user_hash(report.user_id)[:12], report.pending_targets, report.receipt_id)
        self._save_receipt(report)
        return report

    def _erasure_query_vecs(self, ids: Iterable[str], terms: Iterable[str]) -> np.ndarray | None:
        """Embeddings of the erased user content (facts, beliefs, turns, persona lines, ledger)
        and of the query terms. Summaries are left out (they span whole sessions)."""
        ids = list(ids)
        vecs: list[np.ndarray] = []
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            for r in self.db.execute(
                    "SELECT e.vec FROM embeddings e JOIN records r ON r.id = e.record_id"
                    f" WHERE r.kind != 'summary' AND e.record_id IN ({','.join('?' * len(chunk))})", chunk):
                vecs.append(np.frombuffer(r[0], dtype=np.float32))
        terms = [t for t in terms if t]
        if terms:
            vecs.extend(self.embedder.embed(terms).astype(np.float32))
        return np.stack(vecs) if vecs else None

    def _similar_records(self, query_vecs: np.ndarray | None, user_id: str,
                         exclude: Iterable[str] = ()) -> tuple[list[str], list[str]]:
        """Records readable to ``user_id`` (private mode: own private, public, canon) whose
        cosine to any erased vector is >= ``erase_sim_threshold`` (0.5, an estimate for the
        default HashingEmbedder: paraphrased persona lines score ~0.53-0.66, unrelated
        sentences ~0-0.35; structure-sharing sentences like "I work at X/Y" ~0.6).
        Returns (records to delete, records to review). Deleted: persona / derived artifacts
        and turns that back no current fact (questions, commands, chit-chat: nothing but
        log). Reviewed, never silently deleted: user facts, candidate beliefs and turns
        that are the source of a current fact. Canon / immutable records are never returned."""
        if query_vecs is None or not len(query_vecs):
            return [], []
        excl = set(exclude)
        filt, params = self._scope_filter_sql("private", user_id, None)
        rows = self.db.execute(
            "SELECT r.id, r.kind, e.vec FROM records r JOIN embeddings e ON e.record_id = r.id"
            " WHERE r.immutable = 0"
            f" AND NOT EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND NOT {filt})"
            " AND EXISTS (SELECT 1 FROM record_scopes rs WHERE rs.record_id = r.id AND rs.scope != 'canon')",
            params).fetchall()
        rows = [r for r in rows if r["id"] not in excl]
        if not rows:
            return [], []
        mat = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        sims = (mat @ query_vecs.T).max(axis=1)
        delete, review = [], []
        for r, sim in zip(rows, sims):
            if sim < self.erase_sim_threshold:
                continue
            kind = Kind(r["kind"])
            if kind == Kind.EPISODE:
                backs_fact = self.db.execute(
                    "SELECT 1 FROM derivations d JOIN records c ON c.id = d.child_id WHERE d.parent_id = ?"
                    " AND c.kind IN ('user_fact', 'candidate_belief') AND c.status IN ('active', 'pending')",
                    [r["id"]]).fetchone()
                (review if backs_fact else delete).append(r["id"])
            else:
                (delete if kind in _SWEEP_DELETE else review).append(r["id"])
        return delete, review

    @property
    def journal_mode(self) -> str:
        return str(self.db.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def _physical_purge(self) -> str:
        """Make an erasure physical: commit, VACUUM (rebuilds the file; freed pages were
        already zeroed by ``secure_delete``), then :meth:`_truncate_journals`. Returns "" on
        success, else the problem."""
        if self.path == ":memory:":
            return ""
        try:
            self.db.commit()
            self.db.execute("VACUUM")
        except sqlite3.Error as e:
            return f"sqlite error: {e!r}"
        return self._truncate_journals()

    def _truncate_journals(self) -> str:
        """WAL mode: checkpoint and TRUNCATE the WAL so no old frame keeps erased bytes;
        PERSIST / TRUNCATE journal mode: switch to DELETE and back so the old rollback
        journal file is removed. Returns "" on success, else the problem."""
        if self.path == ":memory:":
            return ""
        try:
            self.db.commit()
            mode = self.journal_mode
            if mode in ("persist", "truncate"):
                self.db.execute("PRAGMA journal_mode = DELETE")
                self.db.execute(f"PRAGMA journal_mode = {mode}")
                journal = Path(self.path + "-journal")
                if journal.exists() and journal.stat().st_size:
                    return f"rollback journal not removed ({journal.stat().st_size} bytes)"
            if mode == "wal":
                busy, _, _ = self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if busy:
                    return "wal checkpoint busy (another connection holds the WAL)"
                wal = Path(self.path + "-wal")
                if wal.exists() and wal.stat().st_size:
                    return f"wal not truncated ({wal.stat().st_size} bytes)"
        except sqlite3.Error as e:
            return f"sqlite error: {e!r}"
        return ""

    def _scrub_refs(self, deleted: set[str]) -> None:
        """Remove references to erased ids from surviving records' meta (echo_of, supersedes ...)."""
        if not deleted:
            return
        for row in self.db.execute("SELECT id, meta FROM records WHERE immutable = 0 AND meta != '{}'").fetchall():
            meta = json.loads(row["meta"])
            changed = False
            for k, v in list(meta.items()):
                if isinstance(v, list) and any(x in deleted for x in v if isinstance(x, str)):
                    meta[k] = [x for x in v if x not in deleted]
                    changed = True
                elif isinstance(v, str) and v in deleted:
                    del meta[k]
                    changed = True
            if changed:
                self.db.execute("UPDATE records SET meta = ? WHERE id = ?", (json.dumps(meta, ensure_ascii=False), row["id"]))

    def verify_erasure(self, report: ErasureReport, *, raw_file: bool = False) -> ErasureVerification:
        """Verify one :meth:`forget` result (its deleted ids incl. descendants, and its terms)."""
        return self.verify_erased(report.terms, report.user_id, deleted_ids=report.deleted_ids, raw_file=raw_file,
                                  query_vecs=report.query_vecs, erased_texts=report.erased_texts)

    def verify_erased(
        self,
        term: str | Iterable[str] | None,
        user_id: str | None = None,
        *,
        deleted_ids: Iterable[str] = (),
        raw_file: bool = False,
        query_vecs: np.ndarray | None = None,
        erased_texts: Iterable[str] = (),
    ) -> ErasureVerification:
        """Check that erased data is gone from every table.

        * ``deleted_ids`` (a forget report's ids, which include all descendants): no row in
          records / embeddings / record_scopes / derivations, no reference from another
          record's meta or provenance, and a tombstone hash exists for each.
        * ``term``: literal search in *all* scopes (text, value, subject, provenance, meta,
          tombstone reasons). Hits in records this user's erasure may touch fail the check;
          hits in other users' private records or canon-only records are listed in
          ``foreign_hits`` only.
        * orphan index / embedding / edge rows; with ``raw_file`` (mandatory inside
          :meth:`forget`), the bytes of the DB file and its ``-wal`` / ``-journal``: a hit
          fails unless the term legitimately survives in a foreign / canon record (then it
          is listed in ``foreign_hits``). ``erased_texts`` (the erased records' text / value,
          captured by :meth:`forget` before deletion) are searched in the files too, so an
          erasure by record id is verified on its content; a hit fails unless some
          surviving record still contains that exact text.

        * ``query_vecs`` (embeddings of the erased content, kept in memory on the report):
          surviving derived artifacts at or above ``erase_sim_threshold`` fail (``similar``);
          user-origin records are listed in ``review`` (they need a decision, and keep the
          report's ``similarity_review`` target pending).

        External stores (recordings, generator / LLM state) are verified by their purge
        targets' acknowledgements on the :class:`ErasureReport`, not here.
        """
        out = ErasureVerification()
        terms = [term] if isinstance(term, str) else list(term or [])
        ids = list(dict.fromkeys(deleted_ids))
        priv = private_scope(user_id) if user_id else None
        if ids:
            tomb = {r[0] for r in self.db.execute("SELECT id_hash FROM tombstones")}
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                q = ",".join("?" * len(chunk))
                for tbl, col in (("records", "id"), ("embeddings", "record_id"), ("record_scopes", "record_id"),
                                 ("derivations", "child_id"), ("derivations", "parent_id")):
                    for r in self.db.execute(f"SELECT DISTINCT {col} FROM {tbl} WHERE {col} IN ({q})", chunk):
                        out.surviving.append(f"{tbl}:{r[0]}")
            idset = set(ids)
            for r in self.db.execute("SELECT id, meta, provenance FROM records"):
                blob = r["meta"] + r["provenance"]
                if any(i in blob for i in idset):
                    out.surviving.append(f"ref:{r['id']}")
            out.missing_tombstones = [i for i in ids if hashlib.sha256(i.encode()).hexdigest() not in tomb]
        for t in terms:
            rows = self.db.execute(
                "SELECT r.id, r.immutable FROM records r WHERE"
                " instr(lower(r.text), lower(?)) > 0 OR instr(lower(coalesce(r.value, '')), lower(?)) > 0"
                " OR instr(lower(coalesce(r.subject, '')), lower(?)) > 0 OR instr(lower(r.provenance), lower(?)) > 0"
                " OR instr(lower(r.meta), lower(?)) > 0", [t] * 5).fetchall()
            hit_ids = [r["id"] for r in rows]
            scopes: dict[str, set[str]] = defaultdict(set)
            for i in range(0, len(hit_ids), 500):
                chunk = hit_ids[i:i + 500]
                for r in self.db.execute(
                        f"SELECT record_id, scope FROM record_scopes WHERE record_id IN ({','.join('?' * len(chunk))})",
                        chunk):
                    scopes[r[0]].add(r[1])
            for r in rows:
                sc = scopes[r["id"]]
                foreign = any(is_private(s) and s != priv for s in sc)
                canon_only = sc <= {CANON}
                (out.foreign_hits if foreign or canon_only else out.term_hits).append(f"records:{r['id']}")
            for r in self.db.execute("SELECT rowid FROM tombstones WHERE instr(lower(reason), lower(?)) > 0", [t]):
                out.term_hits.append(f"tombstones:{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM embeddings WHERE record_id NOT IN (SELECT id FROM records)"):
            out.orphans.append(f"embeddings(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT record_id FROM record_scopes WHERE record_id NOT IN (SELECT id FROM records)"):
            out.orphans.append(f"record_scopes(orphan):{r[0]}")
        for r in self.db.execute(
                "SELECT child_id, parent_id FROM derivations WHERE child_id NOT IN (SELECT id FROM records)"
                " OR parent_id NOT IN (SELECT id FROM records)"):
            out.orphans.append(f"derivations(orphan):{r[0]}->{r[1]}")
        if user_id and query_vecs is not None:
            sim_del, sim_rev = self._similar_records(query_vecs, user_id)
            out.similar = [f"records:{i}" for i in sim_del]
            out.review = [f"records:{i}" for i in sim_rev]
        if raw_file and self.path != ":memory:":
            files = [p for p in (Path(self.path), Path(self.path + "-journal"), Path(self.path + "-wal"))
                     if p.exists()]
            blobs = {p.name: p.read_bytes() for p in files}
            for t in terms:
                needles = {v.encode("utf-8") for v in (t, t.lower(), t.upper(), t.title()) if v}
                # the term legitimately survives in another user's / canon records: bytes are expected
                legit = any(h for h in out.foreign_hits if self._record_has_term(h, t))
                for name, blob in blobs.items():
                    if any(n in blob for n in needles):
                        (out.foreign_hits if legit else out.file_hits).append(f"file:{name}")
            for t in dict.fromkeys(erased_texts):
                if t in terms:
                    continue
                needle = t.encode("utf-8")
                if not any(needle in blob for blob in blobs.values()):
                    continue
                survives = self.db.execute(
                    "SELECT id FROM records WHERE instr(text, ?) > 0 OR instr(coalesce(value, ''), ?) > 0 LIMIT 1",
                    [t, t]).fetchone()
                (out.foreign_hits if survives else out.file_hits).append(
                    f"file(erased text{'; still in ' + survives[0] if survives else ''})")
        return out

    def _record_has_term(self, hit: str, term: str) -> bool:
        kind, _, rid = hit.partition(":")
        if kind != "records":
            return False
        r = self.db.execute("SELECT text, coalesce(value, '') AS v, meta, provenance FROM records WHERE id = ?",
                            [rid]).fetchone()
        return bool(r) and any(term.lower() in str(x).lower() for x in r)


_AFFIRM = re.compile(r"^\W*(yes|yeah|yep|right|correct|exactly|sure|that'?s right|对|是的|是啊|是呀|没错|对的|嗯|确实|正确|当然)",
                     re.IGNORECASE)
_NEGATION = re.compile(r"^\W*(no\b|nope|not\b|不|没有|别)|不对|不是|wrong|incorrect|isn'?t|don'?t", re.IGNORECASE)


_PRED_CUES: dict[str, tuple[str, ...]] = {
    "lives_in": ("住", "搬", "live", "lives", "living", "moved", "reside"),
    "works_at": ("工作", "上班", "work", "works", "job"),
    "favorite": ("最爱", "最喜欢", "favorite", "favourite"),
    "likes": ("喜欢", "爱", "like", "likes", "love", "enjoy"),
    "speaks": ("说", "讲", "会", "speak", "speaks"),
    "name": ("叫", "名字", "name", "called"),
    "age": ("岁", "age", "years old"),
    "birthday": ("生日", "birthday", "born"),
}
_REL_CUES: dict[str, tuple[str, ...]] = {
    "sister": ("妹妹", "姐姐", "姐妹", "sister", "sis"), "brother": ("哥哥", "弟弟", "brother"),
    "mother": ("妈妈", "母亲", "妈", "mother", "mom", "mum"), "father": ("爸爸", "父亲", "爸", "father", "dad"),
    "wife": ("老婆", "妻子", "wife"), "husband": ("老公", "丈夫", "husband"), "son": ("儿子", "son"),
    "daughter": ("女儿", "daughter"), "friend": ("朋友", "friend"),
    "boyfriend": ("男朋友", "boyfriend"), "girlfriend": ("女朋友", "girlfriend"),
}
_SELF_CUES = ("我", "i", "i'm", "me", "my", "mine")


def _predicate_cues(predicate: str | None) -> tuple[str, ...]:
    p = predicate or ""
    key = "favorite" if p.startswith("favorite") else p
    return _PRED_CUES.get(key, tuple(w for w in p.split("_") if len(w) >= 2))


def _subject_cues(subject: str | None) -> tuple[str, ...]:
    """``user:<id>`` -> self cues; ``user:<id>/sister`` -> relation cues."""
    tail = (subject or "").split("/", 1)
    if len(tail) == 1:
        return _SELF_CUES
    rel = tail[1].split("/")[0]
    return _REL_CUES.get(rel, (rel,))


_CLAUSE_SPLIT = re.compile(r"[，。；,;！？!?、\n]|但是|但|而且|并且|而|可是|不过|\bbut\b|\band\b|\bwhereas\b|\balthough\b|\bwhile\b",
                           re.IGNORECASE)


def _clauses(text: str) -> list[str]:
    return [c for c in (x.strip() for x in _CLAUSE_SPLIT.split(text)) if c]


_ALL_KIN = tuple(w for ws in _REL_CUES.values() for w in ws)
_OTHER_PERSON = ("他", "她", "他们", "她们", "你", "you", "he", "she", "they", "his", "her", "their", "your")
_PRE_NEGATION = re.compile(r"不|没|别|未|\bnot\b|n't|\bnever\b|\bno longer\b", re.IGNORECASE)


def _cue_positions(text: str, cues: Iterable[str]) -> list[int]:
    low = text.lower()
    out = []
    for c in cues:
        if c.isascii():
            m = re.search(rf"(?<![a-z']){re.escape(c)}(?![a-z])", low)
            if m:
                out.append(m.start())
        else:
            i = text.find(c)
            if i >= 0:
                out.append(i)
    return out


def _clause_states(clause: str, subject: str | None, predicate: str | None) -> bool:
    """True if ``clause`` asserts ``predicate`` with ``subject`` as its grammatical subject:
    the span before the first predicate cue holds the subject cue, no other person / kin
    noun, and no negation."""
    pos = _cue_positions(clause, _predicate_cues(predicate))
    if not pos:
        return False
    head = clause[:min(pos)]
    subj = _subject_cues(subject)
    if not _has_cue(head, subj) or _PRE_NEGATION.search(head):
        return False
    others = [w for w in _ALL_KIN + _OTHER_PERSON if w not in subj]
    return not _has_cue(head, others)


def _has_cue(text: str, cues: Iterable[str]) -> bool:
    low = text.lower()
    for c in cues:
        if c.isascii():
            if re.search(rf"(?<![a-z']){re.escape(c)}(?![a-z])", low):
                return True
        elif c in text:
            return True
    return False


def _norm(v: str | None) -> str:
    return "".join((v or "").lower().split()).strip("。.!！'\"")
