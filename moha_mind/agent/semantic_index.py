"""SQLite-backed semantic index over memory markdown + daily logs.

Each indexable chunk (a non-trivial line from a memory file, or a paragraph
from a daily log) is stored with its embedding as a BLOB. Search computes
cosine similarity in Python — fine for the scale MohaMind operates at
(thousands of chunks, not millions).

Features:
- `sync()` re-indexes files whose mtime changed since last sync.
- `search(query, ...)` returns ranked chunks with source metadata.
- Privacy-aware: sensitive categories can be excluded from indexing.
- Backend-agnostic: uses any object satisfying the `Embedder` protocol.

The file format is boring on purpose — no external vector DB, no compile
step, plays well with backup tools.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from moha_mind.agent.embeddings import Embedder
from moha_mind.agent.memory import MEMORY_FILES, MemoryManager
from moha_mind.agent.privacy import PrivacyPolicy
from moha_mind.utils.logging_config import log


@dataclass
class SemanticResult:
    source: str  # "memory" | "daily_log" | "note"
    category: str
    chunk: str
    score: float
    line_number: int = 0
    path: str = ""


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    if not blob:
        return []
    dim = len(blob) // 4
    return list(struct.unpack(f"{dim}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _split_chunks(content: str, *, min_len: int = 8) -> list[tuple[int, str]]:
    """Split a markdown file into (line_number, chunk_text) tuples.

    Skips headings, comments, and empty lines. Keeps bullets and free prose.
    """
    out: list[tuple[int, str]] = []
    for i, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        clean = line.lstrip("-*•").strip()
        if len(clean) < min_len:
            continue
        out.append((i, clean))
    return out


class SemanticIndex:
    """Tiny, dependency-light vector store backed by SQLite."""

    def __init__(self, memory: MemoryManager, embedder: Optional[Embedder]):
        self.memory = memory
        self.embedder = embedder
        self.db_path = memory.memory_path / ".semantic.db"
        self._initialize()

    # ------------- schema -------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    category TEXT NOT NULL,
                    path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    indexed_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_state (
                    path TEXT PRIMARY KEY,
                    mtime REAL NOT NULL,
                    last_indexed TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(category)")

    # ------------- public API -------------
    def is_available(self) -> bool:
        return self.embedder is not None

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
        return int(row["n"]) if row else 0

    def sync(self, *, force: bool = False, policy: Optional[PrivacyPolicy] = None) -> int:
        """Re-index files whose mtime changed. Returns number of chunks re-indexed."""
        if not self.embedder:
            return 0
        policy = policy or PrivacyPolicy.from_settings()

        changes = 0
        targets = list(self._iter_targets(policy=policy))
        for source, category, path in targets:
            try:
                changes += self._sync_file(source, category, path, force=force)
            except Exception as exc:
                log.warning(f"Semantic sync failed for {path}: {exc}")
        return changes

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        categories: Optional[list[str]] = None,
        include_sensitive: bool = False,
        policy: Optional[PrivacyPolicy] = None,
    ) -> list[SemanticResult]:
        if not self.embedder or not query.strip():
            return []

        policy = policy or PrivacyPolicy.from_settings()
        vectors = self.embedder.encode([query.strip()])
        if not vectors or not vectors[0]:
            return []
        qvec = vectors[0]

        with self._connect() as conn:
            rows = conn.execute("SELECT category, source, path, line_number, text, embedding FROM chunks").fetchall()

        scored: list[SemanticResult] = []
        for row in rows:
            category = row["category"]
            if categories and category not in categories:
                continue
            if not include_sensitive and policy.is_sensitive(category):
                continue
            score = _cosine(qvec, _unpack(row["embedding"]))
            if score <= 0:
                continue
            scored.append(
                SemanticResult(
                    source=row["source"],
                    category=category,
                    chunk=row["text"],
                    score=score,
                    line_number=int(row["line_number"] or 0),
                    path=row["path"],
                )
            )

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    # ------------- internals -------------
    def _iter_targets(self, *, policy: PrivacyPolicy) -> Iterable[tuple[str, str, Path]]:
        for category, filename in MEMORY_FILES.items():
            if policy.is_sensitive(category):
                continue
            path = self.memory.memory_path / filename
            if path.exists():
                yield "memory", category, path

        daily_dir = self.memory.memory_path / "daily_log"
        if daily_dir.exists():
            for path in sorted(daily_dir.glob("*.md")):
                yield "daily_log", "daily_log", path

        notes_dir = self.memory.memory_path / "notes"
        if notes_dir.exists():
            for path in sorted(notes_dir.glob("*.md")):
                yield "note", "notes", path

    def _sync_file(self, source: str, category: str, path: Path, *, force: bool) -> int:
        mtime = path.stat().st_mtime
        with self._connect() as conn:
            state = conn.execute("SELECT mtime FROM file_state WHERE path = ?", (str(path),)).fetchone()
            if state and not force and float(state["mtime"]) >= mtime:
                return 0

            content = path.read_text(encoding="utf-8")
            chunks = _split_chunks(content)
            conn.execute("DELETE FROM chunks WHERE path = ?", (str(path),))
            if not chunks:
                conn.execute(
                    "INSERT OR REPLACE INTO file_state(path, mtime, last_indexed) VALUES (?, ?, datetime('now'))",
                    (str(path), mtime),
                )
                return 0

            texts = [chunk for _, chunk in chunks]
            vectors = self.embedder.encode(texts) if self.embedder else []  # type: ignore[union-attr]
            if len(vectors) != len(texts):
                log.warning(f"Embedder returned {len(vectors)} vectors for {len(texts)} chunks in {path.name}")
                return 0

            for (line_no, text), vec in zip(chunks, vectors):
                if not vec:
                    continue
                conn.execute(
                    """
                    INSERT INTO chunks(source, category, path, line_number, text, text_hash, embedding, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (source, category, str(path), line_no, text, _hash(text), _pack(vec)),
                )

            conn.execute(
                "INSERT OR REPLACE INTO file_state(path, mtime, last_indexed) VALUES (?, ?, datetime('now'))",
                (str(path), mtime),
            )

        return len(chunks)
