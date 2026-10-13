"""
backend/fts5_bm25.py

Persisted BM25 search using SQLite FTS5 with code-aware tokenization.
Splits camelCase, PascalCase, snake_case, and dotted identifiers into constituent subtokens
plus original tokens, enabling precise lexical retrieval on identifiers.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def tokenize_code(text: str) -> str:
    """
    Code-aware tokenizer:
    Splits camelCase, snake_case, PascalCase, and kebab-case into subtokens.
    Example: 'getUserInfo' -> 'getUserInfo get user info'
             'parse_owner_repo' -> 'parse_owner_repo parse owner repo'
    """
    # Find all identifier tokens
    raw_tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    result_tokens = []

    for tok in raw_tokens:
        result_tokens.append(tok)
        # Split on underscores
        parts = tok.split("_")
        if len(parts) > 1:
            for p in parts:
                if p:
                    result_tokens.append(p)

        # Split on camelCase / PascalCase
        subparts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b|\d)|[0-9]+", tok)
        if len(subparts) > 1:
            for sp in subparts:
                result_tokens.append(sp.lower())

    return " ".join(result_tokens)


class SQLiteFTS5BM25:
    """SQLite FTS5 virtual table backing persisted BM25 lexical search."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._init_fts5()

    def _init_fts5(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5(
                    filepath UNINDEXED,
                    tokenized_content,
                    tokenize = 'unicode61'
                );
                """
            )

    def index_sources(self, sources: Dict[str, str]) -> None:
        """Tokenize and populate FTS5 table with code sources."""
        records = []
        for fp, src in sources.items():
            tokens = tokenize_code(src[:8000])  # Cap at 8KB for fast lexical index
            records.append((fp, tokens))

        with self._conn:
            self._conn.execute("DELETE FROM code_fts;")
            self._conn.executemany(
                "INSERT INTO code_fts (filepath, tokenized_content) VALUES (?, ?);",
                records,
            )

    def query(self, query_text: str, top_k: int = 30) -> List[Tuple[str, float]]:
        """
        Run code-aware FTS5 BM25 match query.
        Returns list of (file_path, normalized_bm25_score).
        """
        subtokens = tokenize_code(query_text).split()
        # Clean tokens to avoid FTS5 syntax errors
        clean_tokens = [
            re.sub(r"[^A-Za-z0-9]", "", t) for t in subtokens
            if len(t) >= 2 and not t.isdigit()
        ]
        if not clean_tokens:
            return []

        # Deduplicate while preserving order, cap query to top 20 terms
        seen = set()
        unique_terms = []
        for t in clean_tokens:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique_terms.append(t)
            if len(unique_terms) >= 20:
                break

        # Build OR match query: term1 OR term2 ...
        match_expr = " OR ".join(f'"{t}"' for t in unique_terms)

        cur = self._conn.cursor()
        try:
            cur.execute(
                """
                SELECT filepath, bm25(code_fts) as rank
                FROM code_fts
                WHERE code_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
                """,
                (match_expr, top_k),
            )
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            return []

        if not rows:
            return []

        # SQLite bm25 returns negative values where lower is better (e.g. -5.2 < -1.1)
        # Convert to positive similarity scores where higher is better
        max_abs = max(abs(r[1]) for r in rows) if rows else 1.0
        if max_abs == 0:
            max_abs = 1.0

        results = []
        for fp, rank in rows:
            # Positive normalized score: -(-5.2) / 5.2 * 10
            pos_score = (abs(rank) / max_abs) * 10.0
            results.append((fp, round(pos_score, 3)))

        return results

    def close(self) -> None:
        self._conn.close()
