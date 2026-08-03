#!/usr/bin/env python3
"""
Knowledge base loader.

Ingests the on-disk knowledge corpus (runbooks, RDMA references, kernel-log
pattern guides) into :class:`Document` chunks. Markdown files are split on
headings so retrieval returns focused sections rather than whole documents.

The knowledge base is the substrate for the hybrid retriever and, ultimately,
for the LLM's grounded root-cause analysis.
"""

from __future__ import annotations

import logging
import os
from typing import List

from controller.ai.config import get_ai_config
from controller.ai.vector_store import Document

LOG = logging.getLogger("nbt.ai.kb")


def _split_markdown(text: str) -> List[str]:
    """Split markdown into chunks at top-level (## ) headings."""
    chunks: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c]


class KnowledgeBase:
    """Loads and holds the corpus of knowledge documents."""

    def __init__(self, knowledge_dir: str | None = None):
        cfg = get_ai_config()
        self.knowledge_dir = knowledge_dir or cfg.retrieval.knowledge_dir
        self.documents: List[Document] = []

    def load(self) -> "KnowledgeBase":
        self.documents = []
        if not os.path.isdir(self.knowledge_dir):
            LOG.warning("Knowledge dir not found: %s", self.knowledge_dir)
            return self
        for root, _dirs, files in os.walk(self.knowledge_dir):
            for fname in sorted(files):
                if not fname.lower().endswith((".md", ".txt")):
                    continue
                path = os.path.join(root, fname)
                category = os.path.basename(root)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        text = fh.read()
                except Exception:
                    LOG.exception("Failed to read KB file %s", path)
                    continue
                chunks = _split_markdown(text) if fname.endswith(".md") else [text]
                for idx, chunk in enumerate(chunks):
                    self.documents.append(
                        Document(
                            doc_id=f"{category}/{fname}#{idx}",
                            text=chunk,
                            metadata={
                                "source": os.path.relpath(path, self.knowledge_dir),
                                "category": category,
                                "type": "knowledge",
                            },
                        )
                    )
        LOG.info(
            "Loaded %d knowledge chunks from %s",
            len(self.documents),
            self.knowledge_dir,
        )
        return self

    def as_documents(self) -> List[Document]:
        return list(self.documents)
