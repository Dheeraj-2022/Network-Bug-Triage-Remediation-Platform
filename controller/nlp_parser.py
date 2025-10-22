#!/usr/bin/env python3
"""
NLP Log Parser
--------------

Uses transformer embeddings to analyze kernel/driver logs (dmesg).
Generates vector embeddings and optional classification.

Dependencies:
- sentence-transformers
"""

from typing import List, Dict
from sentence_transformers import SentenceTransformer
import numpy as np

class LogParser:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_logs(self, logs: str) -> np.ndarray:
        """Convert multi-line logs into a single embedding vector."""
        lines = [line for line in logs.splitlines() if line.strip()]
        if not lines:
            return np.zeros(384)
        embeddings = self.model.encode(lines)
        return np.mean(embeddings, axis=0)

    def classify_logs(self, logs: str) -> str:
        """
        Stub for log classification.
        Future: fine-tune classifier on labeled dmesg data.
        """
        if "mtu" in logs.lower():
            return "MTU_MISMATCH"
        if "rdma" in logs.lower() or "qp" in logs.lower():
            return "RDMA_ERROR"
        if "driver" in logs.lower() or "oops" in logs.lower():
            return "DRIVER_FAULT"
        return "UNKNOWN"


# Quick self-test
if __name__ == "__main__":
    parser = LogParser()
    test_logs = "mlx5_core 0000:03:00.0: firmware bug detected\neth0: MTU mismatch detected"
    print(parser.classify_logs(test_logs))
    print(parser.embed_logs(test_logs)[:5])
