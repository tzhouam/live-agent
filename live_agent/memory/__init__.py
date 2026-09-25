"""Long-term memory service (proposal §5.6; evaluated by E3, §7.3).

Typed by provenance (claim types), separated by scope (private / public / canon) with
``source_scopes`` propagated through ``derived_from``; bi-temporal correction; physical,
cascading erasure. Entry point: :class:`MemoryStore`.
"""

from .embed import Embedder, HashingEmbedder
from .extract import CandidateFact, Extractor, RuleExtractor, SanitizedText, sanitize
from .schema import (
    CANON,
    CLAIM_PRIORITY,
    ClaimType,
    Kind,
    Provenance,
    Record,
    Status,
    private_scope,
    public_scope,
)
from .store import (
    ErasureReport,
    Hit,
    ImmutableRecordError,
    IngestResult,
    MemoryStore,
    Resolution,
    RetrievalResult,
)
from .summarize import ExtractiveSummarizer, Summarizer

__all__ = [
    "CANON", "CLAIM_PRIORITY", "CandidateFact", "ClaimType", "Embedder", "ErasureReport",
    "ExtractiveSummarizer", "Extractor", "HashingEmbedder", "Hit", "ImmutableRecordError",
    "IngestResult", "Kind", "MemoryStore", "Provenance", "Record", "Resolution", "RetrievalResult",
    "RuleExtractor", "SanitizedText", "Status", "Summarizer", "private_scope", "public_scope", "sanitize",
]
