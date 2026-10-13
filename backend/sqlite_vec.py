"""
backend/sqlite_vec.py

Minimal, self-contained SQLite + NumPy vector store.
Stores text chunk metadata and raw float32 vector blobs in SQLite.
Executes exact cosine similarity via vectorized NumPy dot-products.
Zero external vector database dependencies (pure stdlib sqlite3 + numpy).
"""

from __future__ import annotations

import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


class SQLiteNumPyVectorStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._create_schema()
        self._matrix_cache: Optional[np.ndarray] = None
        self._ids_cache: Optional[List[str]] = None
        self._meta_cache: Optional[List[Dict[str, Any]]] = None

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    filepath TEXT,
                    metadata_json TEXT,
                    embedding BLOB
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS store_meta (
                    key TEXT PRIMARY KEY,
                    val TEXT
                );
                """
            )

    def add_chunks(
        self,
        ids: List[str],
        embeddings: List[List[float]] | np.ndarray,
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Insert or replace chunks and their vector embeddings."""
        embed_arr = np.asarray(embeddings, dtype=np.float32)
        records = []
        for i in range(len(ids)):
            meta = metadatas[i] if i < len(metadatas) else {}
            fp = meta.get("file_path", "")
            blob = embed_arr[i].tobytes()
            records.append((ids[i], fp, json.dumps(meta), blob))

        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?)",
                records,
            )

        # Invalidate in-memory cache
        self._matrix_cache = None
        self._ids_cache = None
        self._meta_cache = None

    def _load_cache(self) -> None:
        if self._matrix_cache is not None:
            return

        cur = self._conn.cursor()
        cur.execute("SELECT id, metadata_json, embedding FROM chunks")
        rows = cur.fetchall()

        if not rows:
            self._matrix_cache = np.empty((0, 0), dtype=np.float32)
            self._ids_cache = []
            self._meta_cache = []
            return

        self._ids_cache = [r[0] for r in rows]
        self._meta_cache = [json.loads(r[1]) if r[1] else {} for r in rows]
        blobs = b"".join(r[2] for r in rows)
        dim = len(rows[0][2]) // 4  # float32 = 4 bytes
        matrix = np.frombuffer(blobs, dtype=np.float32).reshape(len(rows), dim)

        # Pre-normalize for instant cosine distance via dot product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix_cache = matrix / norms

    def query(
        self,
        query_embedding: List[float] | np.ndarray,
        top_k: int = 30,
    ) -> List[Dict[str, Any]]:
        """Retrieve top_k nearest neighbors by exact cosine similarity."""
        self._load_cache()
        if len(self._ids_cache) == 0:
            return []

        q = np.asarray(query_embedding, dtype=np.float32).reshape(-1)
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        # Vectorized dot product cosine similarity
        sims = np.dot(self._matrix_cache, q)
        k = min(top_k, len(sims))
        top_indices = np.argpartition(-sims, k)[:k]
        top_sorted = top_indices[np.argsort(-sims[top_indices])]

        results = []
        for idx in top_sorted:
            results.append({
                "id": self._ids_cache[idx],
                "score": float(sims[idx]),
                "metadata": self._meta_cache[idx],
            })
        return results

    def count(self) -> int:
        cur = self._conn.cursor()
        cur.execute("SELECT count(*) FROM chunks")
        return cur.fetchone()[0]

    def close(self) -> None:
        self._conn.close()
