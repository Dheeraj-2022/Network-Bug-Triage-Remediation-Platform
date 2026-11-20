#!/usr/bin/env python3
"""
Vector store abstraction for the retrieval pipeline.

Supports pluggable backends with automatic selection:

* **Chroma** / **FAISS** when installed (production).
* **NumpyVectorStore** — a dependency-free cosine-similarity store used as the
  universal fallback. It reuses the platform's existing sentence-transformers
  embeddings (via :class:`controller.nlp_parser.LogParser`); when even that is
  unavailable it falls back to a deterministic hashing embedder so retrieval
  still returns sensible ordering.

All backends expose the same minimal interface::

    store.add(documents)          # documents: List[Document]
    store.search(query, k) -> List[(Document, score)]
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

LOG = logging.getLogger("nbt.ai.vectorstore")


@dataclass
class Document:
    """A single retrievable knowledge chunk."""

    doc_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Embedders
# ---------------------------------------------------------------------------
class _Embedder:
    """Wraps the existing LogParser embeddings, with a hashing fallback."""

    def __init__(self) -> None:
        self._parser = None
        self._dim = 256
        try:
            from controller.nlp_parser import LogParser

            self._parser = LogParser()
            # Probe dimensionality.
            self._dim = int(getattr(self._parser, "embedding_dim", 384))
            if self._parser.model is None:
                # Model failed to load; use hashing embedder for stable vectors.
                self._parser = None
        except Exception:
            LOG.debug("LogParser unavailable; using hashing embedder")
            self._parser = None

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> np.ndarray:
        if self._parser is not None:
            try:
                vec = self._parser.embed_logs(text)
                arr = np.asarray(vec, dtype=float).ravel()
                if arr.size and np.any(arr):
                    return arr
            except Exception:
                LOG.debug("Embedding via LogParser failed; hashing fallback")
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> np.ndarray:
        """Deterministic bag-of-tokens hashing embedding (no deps)."""
        vec = np.zeros(self._dim, dtype=float)
        for token in _tokenize(text):
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            vec[h % self._dim] += 1.0
        return vec


def _tokenize(text: str) -> List[str]:
    return [t for t in "".join(
        c.lower() if c.isalnum() else " " for c in (text or "")
    ).split() if t]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class NumpyVectorStore:
    """Dependency-free in-memory cosine-similarity store."""

    backend_name = "numpy"

    def __init__(self) -> None:
        self._embedder = _Embedder()
        self._docs: List[Document] = []
        self._matrix: Optional[np.ndarray] = None

    def add(self, documents: List[Document]) -> None:
        if not documents:
            return
        vectors = [self._embedder.embed(d.text) for d in documents]
        new = np.vstack(vectors)
        if self._matrix is None:
            self._matrix = new
        else:
            self._matrix = np.vstack([self._matrix, new])
        self._docs.extend(documents)

    def search(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        if self._matrix is None or not self._docs:
            return []
        q = self._embedder.embed(query)
        scores = [_cosine(q, self._matrix[i]) for i in range(len(self._docs))]
        ranked = sorted(
            zip(self._docs, scores), key=lambda x: x[1], reverse=True
        )
        return ranked[: max(0, k)]

    def __len__(self) -> int:
        return len(self._docs)


class ChromaVectorStore:
    """Chroma-backed store (in-memory client). Optional dependency."""

    backend_name = "chroma"

    def __init__(self) -> None:
        import chromadb  # type: ignore

        self._embedder = _Embedder()
        self._client = chromadb.Client()
        self._collection = self._client.create_collection(
            name="nbt_knowledge", get_or_create=True
        )
        self._count = 0

    def add(self, documents: List[Document]) -> None:
        if not documents:
            return
        self._collection.add(
            ids=[d.doc_id for d in documents],
            documents=[d.text for d in documents],
            embeddings=[self._embedder.embed(d.text).tolist() for d in documents],
            metadatas=[d.metadata or {"_": ""} for d in documents],
        )
        self._count += len(documents)

    def search(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        if self._count == 0:
            return []
        res = self._collection.query(
            query_embeddings=[self._embedder.embed(query).tolist()],
            n_results=min(k, self._count),
        )
        out: List[Tuple[Document, float]] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i, doc_id in enumerate(ids):
            # Chroma returns L2/cosine distance; convert to a similarity score.
            dist = dists[i] if i < len(dists) else 1.0
            score = 1.0 / (1.0 + float(dist))
            out.append(
                (
                    Document(
                        doc_id=doc_id,
                        text=docs[i] if i < len(docs) else "",
                        metadata=metas[i] if i < len(metas) else {},
                    ),
                    score,
                )
            )
        return out

    def __len__(self) -> int:
        return self._count


def build_vector_store(backend: str = "auto") -> Any:
    """Factory that selects the best available vector-store backend."""
    order = (
        ["chroma", "numpy"]
        if backend == "auto"
        else [backend]
    )
    for name in order:
        try:
            if name == "chroma":
                store = ChromaVectorStore()
                LOG.info("Using Chroma vector store")
                return store
            if name == "faiss":
                # FAISS shares the numpy embedding path; treat as numpy for
                # simplicity while signalling intent in logs.
                import faiss  # type: ignore  # noqa: F401

                LOG.info("FAISS present; using numpy cosine store wrapper")
                return NumpyVectorStore()
            if name == "numpy":
                return NumpyVectorStore()
        except Exception as exc:
            LOG.debug("Vector backend '%s' unavailable: %s", name, exc)
            continue
    return NumpyVectorStore()
