#!/usr/bin/env python3
"""
Hybrid retrieval pipeline.

Combines three complementary signals to ground the LLM's reasoning:

1. **Vector search** over the knowledge base (semantic similarity).
2. **Keyword / lexical search** (token overlap) — robust for exact counter names
   and log fingerprints that embeddings can smear.
3. **Incident history** retrieval from memory — surfaces past incidents and the
   remediations that resolved them for the same host / fault domain.

Scores from the vector and keyword channels are min-max normalised and blended
using the configured weights, then fused with any incident-history hits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from controller.ai.config import AIConfig, get_ai_config
from controller.ai.knowledge_base import KnowledgeBase
from controller.ai.vector_store import Document, build_vector_store, _tokenize

LOG = logging.getLogger("nbt.ai.retriever")


@dataclass
class RetrievedItem:
    text: str
    source: str
    score: float
    channel: str  # vector | keyword | incident
    metadata: Dict[str, Any]


def _minmax(scores: List[float]) -> List[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


class HybridRetriever:
    """Vector + keyword + incident-history retriever."""

    def __init__(
        self,
        config: Optional[AIConfig] = None,
        memory: Any = None,
    ):
        self.cfg = config or get_ai_config()
        self.memory = memory
        self._kb = KnowledgeBase(self.cfg.retrieval.knowledge_dir).load()
        self._store = build_vector_store(self.cfg.retrieval.vector_backend)
        self._store.add(self._kb.as_documents())
        self._docs: List[Document] = self._kb.as_documents()
        LOG.info(
            "HybridRetriever ready: %d docs, vector-backend=%s",
            len(self._docs),
            getattr(self._store, "backend_name", "unknown"),
        )

    # ------------------------------------------------------------------
    @property
    def backend_name(self) -> str:
        return getattr(self._store, "backend_name", "unknown")

    def _keyword_search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []
        scored: List[Tuple[Document, float]] = []
        for doc in self._docs:
            d_tokens = set(_tokenize(doc.text))
            if not d_tokens:
                continue
            overlap = len(q_tokens & d_tokens)
            if overlap:
                score = overlap / (len(q_tokens) ** 0.5)
                scored.append((doc, float(score)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def retrieve(
        self,
        query: str,
        host: Optional[str] = None,
        fault_domain: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[RetrievedItem]:
        k = top_k or self.cfg.retrieval.top_k
        vw = self.cfg.retrieval.vector_weight
        kw = self.cfg.retrieval.keyword_weight

        vector_hits = self._store.search(query, k=k * 2)
        keyword_hits = self._keyword_search(query, k=k * 2)

        # Normalise each channel independently, then fuse by doc_id.
        v_norm = _minmax([s for _, s in vector_hits])
        k_norm = _minmax([s for _, s in keyword_hits])

        fused: Dict[str, Dict[str, Any]] = {}
        for (doc, _), n in zip(vector_hits, v_norm):
            fused.setdefault(doc.doc_id, {"doc": doc, "v": 0.0, "k": 0.0})
            fused[doc.doc_id]["v"] = n
        for (doc, _), n in zip(keyword_hits, k_norm):
            fused.setdefault(doc.doc_id, {"doc": doc, "v": 0.0, "k": 0.0})
            fused[doc.doc_id]["k"] = n

        items: List[RetrievedItem] = []
        for entry in fused.values():
            doc: Document = entry["doc"]
            score = vw * entry["v"] + kw * entry["k"]
            channel = (
                "vector+keyword"
                if entry["v"] > 0 and entry["k"] > 0
                else ("vector" if entry["v"] > 0 else "keyword")
            )
            items.append(
                RetrievedItem(
                    text=doc.text,
                    source=doc.metadata.get("source", doc.doc_id),
                    score=round(score, 4),
                    channel=channel,
                    metadata=doc.metadata,
                )
            )

        # Incident-history channel from memory.
        items.extend(self._incident_hits(host, fault_domain))

        items.sort(key=lambda x: x.score, reverse=True)
        return items[:k]

    def _incident_hits(
        self, host: Optional[str], fault_domain: Optional[str]
    ) -> List[RetrievedItem]:
        if self.memory is None:
            return []
        try:
            incidents = self.memory.similar_incidents(
                host=host, fault_domain=fault_domain, limit=3
            )
        except Exception:
            LOG.debug("Incident retrieval failed", exc_info=True)
            return []
        out: List[RetrievedItem] = []
        for inc in incidents:
            summary = (
                f"Past incident on {inc.get('host')} ({inc.get('fault_domain')}): "
                f"{inc.get('root_cause', 'n/a')}. Remediation "
                f"'{inc.get('playbook', 'none')}' -> "
                f"resolved={inc.get('resolved')}."
            )
            out.append(
                RetrievedItem(
                    text=summary,
                    source=f"incident:{inc.get('event_id', 'unknown')}",
                    score=0.85,  # incident history is high-value context
                    channel="incident",
                    metadata=inc,
                )
            )
        return out

    def format_context(self, items: List[RetrievedItem]) -> str:
        """Render retrieved items into a compact prompt-ready string."""
        if not items:
            return "(no relevant knowledge retrieved)"
        lines = []
        for i, it in enumerate(items, 1):
            lines.append(
                f"[{i}] ({it.channel}, score={it.score}, src={it.source})\n"
                f"{it.text.strip()}"
            )
        return "\n\n".join(lines)
