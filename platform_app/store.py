"""SQLite persistence layer for the learning platform.

Replaces the in-memory submission dict (SWE Quiz) and adds a durable game
registry (Game Forge). Uses only the Python standard library so there are no
extra installation requirements.

Writes are serialised through a single module-level lock; SQLite handles the
rest. All queries are parameterised — no string interpolation of user data.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any

from platform_app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS swe_quiz_submissions (
    id            TEXT PRIMARY KEY,
    scenario_id   TEXT NOT NULL,
    score         REAL NOT NULL,
    selections    TEXT NOT NULL,
    feedback      TEXT NOT NULL,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS game_forge_games (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    topic         TEXT,
    audience      TEXT,
    html_path     TEXT NOT NULL,
    bytes         INTEGER NOT NULL,
    created_at    REAL NOT NULL
);
"""

_lock = threading.Lock()


class Store:
    """Thread-safe, connection-per-operation SQLite store."""

    def __init__(self, path) -> None:
        self._path = str(path)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init(self) -> None:
        with _lock, self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ---------------- SWE Quiz ----------------
    def save_submission(
        self,
        scenario_id: str,
        score: float,
        selections: dict[str, str],
        feedback: dict[str, Any],
    ) -> str:
        submission_id = uuid.uuid4().hex
        with _lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO swe_quiz_submissions"
                " (id, scenario_id, score, selections, feedback, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    submission_id,
                    scenario_id,
                    float(score),
                    json.dumps(selections),
                    json.dumps(feedback),
                    time.time(),
                ),
            )
        return submission_id

    def get_submission(self, submission_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM swe_quiz_submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "scenario_id": row["scenario_id"],
            "score": row["score"],
            "selections": json.loads(row["selections"]),
            "feedback": json.loads(row["feedback"]),
            "created_at": row["created_at"],
        }

    # ---------------- Game Forge ----------------
    def register_game(
        self,
        name: str,
        html_path: str,
        bytes_size: int,
        topic: str | None = None,
        audience: str | None = None,
    ) -> str:
        game_id = uuid.uuid4().hex
        with _lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO game_forge_games"
                " (id, name, topic, audience, html_path, bytes, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (game_id, name, topic, audience, html_path, bytes_size, time.time()),
            )
        return game_id

    def list_games(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM game_forge_games ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "topic": row["topic"],
                "audience": row["audience"],
                "html_path": row["html_path"],
                "bytes": row["bytes"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete_game(self, game_id: str) -> bool:
        with _lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM game_forge_games WHERE id = ?", (game_id,)
            )
        return cursor.rowcount > 0

    def healthy(self) -> bool:
        """Lightweight readiness probe: can we read the schema?"""
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1 FROM swe_quiz_submissions LIMIT 1").fetchone()
            return True
        except sqlite3.Error:
            return False


store = Store(settings.database_path)
