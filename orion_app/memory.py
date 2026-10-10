from __future__ import annotations

import re
import sqlite3
from pathlib import Path


MAX_MESSAGES_PER_CONVERSATION = 999_999
_STOP_WORDS = {
    "about", "after", "again", "also", "because", "could", "from", "have",
    "into", "just", "more", "please", "that", "their", "there", "these",
    "they", "this", "those", "what", "when", "where", "which", "while",
    "with", "would", "your",
}


class ConversationMemory:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages (conversation_id, id DESC)
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                USING fts5(conversation_id UNINDEXED, message_id UNINDEXED, content)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def add_message(self, conversation_id: str, role: str, content: str) -> dict:
        cleaned = content.strip()
        if role not in ("user", "assistant"):
            raise ValueError("role must be user or assistant")
        if not cleaned:
            raise ValueError("message content cannot be empty")

        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, cleaned),
            )
            message_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO messages_fts (conversation_id, message_id, content) VALUES (?, ?, ?)",
                (conversation_id, str(message_id), cleaned),
            )
            overflow = connection.execute(
                """
                SELECT id FROM messages WHERE conversation_id = ?
                ORDER BY id DESC LIMIT -1 OFFSET ?
                """,
                (conversation_id, MAX_MESSAGES_PER_CONVERSATION),
            ).fetchall()
            if overflow:
                old_ids = [row["id"] for row in overflow]
                placeholders = ",".join("?" for _ in old_ids)
                connection.execute(
                    f"DELETE FROM messages_fts WHERE message_id IN ({placeholders})",
                    [str(message_id) for message_id in old_ids],
                )
                connection.execute(
                    f"DELETE FROM messages WHERE id IN ({placeholders})",
                    old_ids,
                )
            row = connection.execute(
                "SELECT id, role, content, created_at FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
        return dict(row)

    def recent(self, conversation_id: str, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at FROM (
                    SELECT id, role, content, created_at
                    FROM messages WHERE conversation_id = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id
                """,
                (conversation_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    def export(self, conversation_id: str, export_format: str = "markdown") -> str:
        import json
        messages = self.recent(conversation_id, limit=500)
        if export_format.lower() == "json":
            return json.dumps(messages, indent=2, ensure_ascii=False)
        lines = [f"# Orion Chat Export - Conversation: {conversation_id}", ""]
        for msg in messages:
            sender = "Nico de Angelo" if msg.get("role") == "assistant" else "User"
            timestamp = msg.get("created_at", "")
            lines.append(f"### {sender} ({timestamp})")
            lines.append(msg.get("content", ""))
            lines.append("")
        return "\n".join(lines)

    def context(self, conversation_id: str, query: str, recent_limit: int = 8) -> list[dict]:
        terms = [
            term for term in dict.fromkeys(re.findall(r"[A-Za-z0-9_]{3,}", query.lower()))
            if term not in _STOP_WORDS
        ][:8]
        selected: dict[int, sqlite3.Row] = {}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content FROM (
                    SELECT id, role, content FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id
                """,
                (conversation_id, recent_limit),
            ).fetchall()
            for row in rows:
                selected[row["id"]] = row

            if terms:
                match = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
                try:
                    rows = connection.execute(
                        """
                        SELECT m.id, m.role, m.content FROM messages_fts
                        JOIN messages m ON m.id = CAST(messages_fts.message_id AS INTEGER)
                        WHERE messages_fts.conversation_id = ? AND messages_fts MATCH ?
                        ORDER BY rank LIMIT 4
                        """,
                        (conversation_id, match),
                    ).fetchall()
                except sqlite3.OperationalError as error:
                    raise RuntimeError("Conversation memory search failed.") from error
                for row in rows:
                    selected[row["id"]] = row

        ordered = sorted(selected.items())
        return [{"role": row["role"], "content": row["content"]} for _, row in ordered]

    def count(self, conversation_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return row["count"]

    def clear(self, conversation_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM messages_fts WHERE conversation_id = ?",
                (conversation_id,),
            )
            connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            )
