"""Persistent memory system — stores facts, conversations, and emotional context."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MemoryEntry:
    """A single memory: a fact, observation, or conversation snippet."""

    id: int
    category: str  # "fact", "preference", "event", "emotion", "conversation"
    content: str
    importance: int  # 1-5 scale
    timestamp: float
    persona_name: str

    @property
    def age_description(self) -> str:
        elapsed = time.time() - self.timestamp
        if elapsed < 3600:
            minutes = int(elapsed / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        if elapsed < 86400:
            hours = int(elapsed / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = int(elapsed / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


class MemoryStore:
    """SQLite-backed persistent memory for persona conversations."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            data_dir = Path.home() / ".persona-mcp"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "memory.db")

        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                persona_name TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 3,
                timestamp REAL NOT NULL,
                tags TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS mood_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                persona_name TEXT NOT NULL,
                mood TEXT NOT NULL,
                reason TEXT,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_persona
                ON memories(persona_name);
            CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(persona_name, category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance
                ON memories(importance DESC);
        """)
        self._conn.commit()

    def remember(
        self,
        persona_name: str,
        content: str,
        category: str = "fact",
        importance: int = 3,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        """Store a new memory."""
        now = time.time()
        cursor = self._conn.execute(
            """INSERT INTO memories (persona_name, category, content, importance, timestamp, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (persona_name, category, content, importance, now, json.dumps(tags or [])),
        )
        self._conn.commit()
        return MemoryEntry(
            id=cursor.lastrowid or 0,
            category=category,
            content=content,
            importance=importance,
            timestamp=now,
            persona_name=persona_name,
        )

    def recall(
        self,
        persona_name: str,
        category: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Retrieve memories, optionally filtered by category or keyword."""
        sql = "SELECT * FROM memories WHERE persona_name = ?"
        params: list[str | int] = [persona_name]

        if category:
            sql += " AND category = ?"
            params.append(category)

        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")

        sql += " ORDER BY importance DESC, timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            MemoryEntry(
                id=r["id"],
                category=r["category"],
                content=r["content"],
                importance=r["importance"],
                timestamp=r["timestamp"],
                persona_name=r["persona_name"],
            )
            for r in rows
        ]

    def forget(self, memory_id: int) -> bool:
        """Remove a specific memory."""
        cursor = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_memory_summary(self, persona_name: str) -> str:
        """Generate a natural-language summary of what the persona remembers."""
        memories = self.recall(persona_name, limit=50)
        if not memories:
            return "No memories yet — this is the start of a new relationship."

        facts = [m for m in memories if m.category == "fact"]
        preferences = [m for m in memories if m.category == "preference"]
        events = [m for m in memories if m.category == "event"]
        emotions = [m for m in memories if m.category == "emotion"]

        lines: list[str] = ["WHAT YOU REMEMBER ABOUT THE USER:"]

        if facts:
            lines.append("\nFacts:")
            for m in facts[:10]:
                lines.append(f"  - {m.content} (learned {m.age_description})")

        if preferences:
            lines.append("\nPreferences & Likes:")
            for m in preferences[:10]:
                lines.append(f"  - {m.content}")

        if events:
            lines.append("\nRecent Events in Their Life:")
            for m in events[:5]:
                lines.append(f"  - {m.content} ({m.age_description})")

        if emotions:
            lines.append("\nEmotional Context:")
            for m in emotions[:5]:
                lines.append(f"  - {m.content} ({m.age_description})")

        return "\n".join(lines)

    def log_mood(self, persona_name: str, mood: str, reason: str | None = None) -> None:
        """Log a mood change for the persona."""
        self._conn.execute(
            "INSERT INTO mood_log (persona_name, mood, reason, timestamp) VALUES (?, ?, ?, ?)",
            (persona_name, mood, reason, time.time()),
        )
        self._conn.commit()

    def get_current_mood(self, persona_name: str) -> str:
        """Get the persona's most recent mood."""
        row = self._conn.execute(
            "SELECT mood FROM mood_log WHERE persona_name = ? ORDER BY timestamp DESC LIMIT 1",
            (persona_name,),
        ).fetchone()
        return row["mood"] if row else "neutral"

    def set_user_profile(self, key: str, value: str) -> None:
        """Store or update a user profile field (name, age, interests, etc.)."""
        self._conn.execute(
            """INSERT INTO user_profile (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?""",
            (key, value, time.time(), value, time.time()),
        )
        self._conn.commit()

    def get_user_profile(self) -> dict[str, str]:
        """Retrieve the full user profile."""
        rows = self._conn.execute("SELECT key, value FROM user_profile").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def clear_all(self, persona_name: str) -> int:
        """Clear all memories for a persona. Returns count of deleted memories."""
        cursor = self._conn.execute(
            "DELETE FROM memories WHERE persona_name = ?", (persona_name,)
        )
        self._conn.execute(
            "DELETE FROM mood_log WHERE persona_name = ?", (persona_name,)
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
