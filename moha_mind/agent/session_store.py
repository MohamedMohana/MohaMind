"""Persistent session storage and search for MohaMind conversations."""

import re
import sqlite3
from pathlib import Path
from typing import Optional

from moha_mind.utils.logging_config import log
from moha_mind.utils.timezone import now_ksa


class SessionStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "sessions.db"
        self.fts_enabled = False
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id_id ON messages(chat_id, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")

            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                    USING fts5(content, content='messages', content_rowid='id')
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                    END
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
                    END
                    """
                )
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
                        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                    END
                    """
                )
                conn.execute(
                    """
                    INSERT INTO messages_fts(rowid, content)
                    SELECT messages.id, messages.content
                    FROM messages
                    WHERE NOT EXISTS (
                        SELECT 1 FROM messages_fts WHERE messages_fts.rowid = messages.id
                    )
                    """
                )
                self.fts_enabled = True
            except sqlite3.OperationalError as exc:
                self.fts_enabled = False
                log.warning(f"Session search fallback enabled (FTS5 unavailable): {exc}")

    def append_message(self, chat_id: str, role: str, content: str) -> None:
        clean_content = (content or "").strip()
        if not clean_content:
            return

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, role, clean_content, now_ksa().isoformat(timespec="seconds")),
            )

    def load_recent_messages(self, chat_id: str, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE chat_id = ? AND role IN ('user', 'assistant')
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()

        return [
            {
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in reversed(rows)
        ]

    def count_messages(self, chat_id: Optional[str] = None) -> int:
        with self._connect() as conn:
            if chat_id:
                row = conn.execute("SELECT COUNT(*) AS count FROM messages WHERE chat_id = ?", (chat_id,)).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS count FROM messages").fetchone()
        return int(row["count"]) if row else 0

    def search_messages(self, query: str, chat_id: Optional[str] = None, limit: int = 5) -> list[dict]:
        clean_query = query.strip()
        if not clean_query:
            return []

        tokens = [token for token in re.findall(r"\w+", clean_query, flags=re.UNICODE) if len(token) >= 2]
        if self.fts_enabled and tokens:
            results = self._search_fts(tokens=tokens, chat_id=chat_id, limit=limit)
            if results:
                return results

        return self._search_like(query=clean_query, chat_id=chat_id, limit=limit)

    def _search_fts(self, tokens: list[str], chat_id: Optional[str], limit: int) -> list[dict]:
        match_query = " ".join(tokens)
        sql = [
            "SELECT m.chat_id, m.role, m.content, m.created_at",
            "FROM messages_fts",
            "JOIN messages m ON m.id = messages_fts.rowid",
            "WHERE messages_fts MATCH ?",
        ]
        params: list[object] = [match_query]

        if chat_id:
            sql.append("AND m.chat_id = ?")
            params.append(chat_id)

        sql.append("ORDER BY m.id DESC LIMIT ?")
        params.append(limit)

        try:
            with self._connect() as conn:
                rows = conn.execute("\n".join(sql), params).fetchall()
        except sqlite3.OperationalError:
            return []

        return [dict(row) for row in rows]

    def _search_like(self, query: str, chat_id: Optional[str], limit: int) -> list[dict]:
        sql = [
            "SELECT chat_id, role, content, created_at",
            "FROM messages",
            "WHERE lower(content) LIKE ?",
        ]
        params: list[object] = [f"%{query.lower()}%"]

        if chat_id:
            sql.append("AND chat_id = ?")
            params.append(chat_id)

        sql.append("ORDER BY id DESC LIMIT ?")
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute("\n".join(sql), params).fetchall()

        return [dict(row) for row in rows]
