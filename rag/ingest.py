"""
Ingest markdown sources into Postgres+pgvector using the same deterministic
embeddings as refimatch_agent.retrieval._hash_embedding (dim=64).
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv

load_dotenv()

DIM = 64
SEED = 42


def _stable_seed(text: str) -> int:
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % (2**32)


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n == 0:
        return v
    return v / n


def hash_embedding(text: str) -> np.ndarray:
    rng = np.random.default_rng(_stable_seed(text) + SEED)
    v = rng.standard_normal(DIM)
    return _l2_normalize(v.astype(np.float32))


def chunk_markdown(text: str, source: str) -> list[tuple[str, str]]:
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    out: list[tuple[str, str]] = []
    for i, p in enumerate(parts):
        cid = f"{source}-{i:03d}"
        out.append((cid, p))
    return out


def vector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in vec.tolist()) + "]"


def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is required for ingest")

    sources_dir = Path(__file__).resolve().parent / "sources"
    rows: list[tuple[str, str, str]] = []
    for md in sorted(sources_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        for cid, chunk in chunk_markdown(text, md.stem):
            emb = hash_embedding(cid + "\n" + chunk)
            rows.append((cid, chunk, vector_literal(emb)))

    ddl = """
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS rag_documents (
      id text PRIMARY KEY,
      content text NOT NULL,
      embedding vector(64) NOT NULL
    );
    """

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(ddl)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rag_documents")
            cur.executemany(
                "INSERT INTO rag_documents (id, content, embedding) VALUES (%s, %s, %s::vector)",
                rows,
            )
    print(f"ingested {len(rows)} chunks")


if __name__ == "__main__":
    main()
