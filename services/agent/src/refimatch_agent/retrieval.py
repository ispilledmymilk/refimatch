from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def _stable_seed(text: str) -> int:
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % (2**32)


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n == 0:
        return v
    return v / n


def _hash_embedding(text: str, dim: int = 64, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(_stable_seed(text) + seed)
    v = rng.standard_normal(dim)
    return _l2_normalize(v.astype(np.float32))


@dataclass
class RetrievedChunk:
    id: str
    text: str
    score: float


class MemoryRetriever:
    """Deterministic pseudo-embeddings for CI and local dev without Postgres."""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks
        self._emb = np.stack([_hash_embedding(c["id"] + "\n" + c["text"]) for c in chunks])

    @classmethod
    def from_json_path(cls, path: Path) -> MemoryRetriever:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["chunks"])

    def search(self, query: str, k: int = 4) -> list[RetrievedChunk]:
        q = _hash_embedding(query)
        sims = self._emb @ q
        idx = np.argsort(-sims)[:k]
        out: list[RetrievedChunk] = []
        for i in idx:
            c = self._chunks[int(i)]
            out.append(RetrievedChunk(id=c["id"], text=c["text"], score=float(sims[int(i)])))
        return out


def build_default_retriever() -> MemoryRetriever:
    bundled = Path(__file__).resolve().parent / "data" / "rag_chunks.json"
    override = os.environ.get("REFIMATCH_RAG_CHUNKS_PATH")
    path = Path(override) if override else bundled
    if not path.exists():
        return MemoryRetriever(
            [
                {
                    "id": "fallback",
                    "text": (
                        "Refinance comparisons should prioritize total cost, "
                        "payment, and breakeven."
                    ),
                }
            ]
        )
    return MemoryRetriever.from_json_path(path)


class PgRetriever:
    """pgvector-backed retrieval (expects rag_documents from rag/ingest.py)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def search(self, query: str, k: int = 4) -> list[RetrievedChunk]:
        import psycopg

        q = _hash_embedding(query)
        qlit = "[" + ",".join(f"{float(x):.8f}" for x in q.tolist()) + "]"
        sql = """
        SELECT id, content, (embedding <-> %s::vector) AS dist
        FROM rag_documents
        ORDER BY dist ASC
        LIMIT %s
        """
        out: list[RetrievedChunk] = []
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (qlit, k))
                for row in cur.fetchall():
                    rid, content, dist = row
                    score = 1.0 / (1.0 + float(dist))
                    out.append(RetrievedChunk(id=str(rid), text=str(content), score=score))
        return out


def get_retriever() -> MemoryRetriever | PgRetriever:
    backend = os.environ.get("REFIMATCH_RAG_BACKEND", "memory").lower()
    if backend == "pg":
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            return build_default_retriever()
        return PgRetriever(dsn)
    return build_default_retriever()
