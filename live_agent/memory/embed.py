"""Pluggable text embedders.

The default :class:`HashingEmbedder` is deterministic and offline: a signed feature-hashing
bag of character n-grams (CJK unigrams + bigrams; Latin word tokens + boundary-padded
character trigrams). It is a lexical baseline, good enough for echo detection of
near-verbatim paraphrases and for tests; a sentence-embedding backend can be plugged in
through the :class:`Embedder` protocol later (same ``dim`` must be used for a DB file).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import numpy as np

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]+")
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Return float32 array [len(texts), dim], rows L2-normalised (zero rows allowed)."""
        ...


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


class HashingEmbedder:
    """Deterministic signed feature hashing over character n-grams."""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim
        self.name = f"hash-ngram-v1-{dim}"

    def features(self, text: str) -> list[str]:
        t = normalize_text(text)
        feats: list[str] = []
        for run in _CJK.findall(t):
            feats.extend(f"u:{c}" for c in run)
            feats.extend(f"b:{run[i:i + 2]}" for i in range(len(run) - 1))
        for w in _WORD.findall(t):
            feats.append(f"w:{w}")
            padded = f"#{w}#"
            feats.extend(f"t:{padded[i:i + 3]}" for i in range(len(padded) - 2))
        return feats

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for f in self.features(text):
            h = hashlib.blake2b(f.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            v[idx] += sign
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vec(t) for t in texts]).astype(np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine of rows of ``b`` against vector ``a`` (inputs are already L2-normalised)."""
    if b.size == 0:
        return np.zeros(0, dtype=np.float32)
    return b @ a
