from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import CandidateStatus, RunMode, RunStatus

SCHEMA_VERSION = 3


class AuthoringStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        self._initialize()
        self.path.chmod(0o600)

    # Parallel candidate workers write here while the host is busy with image builds;
    # a writer waits for the lock instead of failing the whole run after five seconds.
    BUSY_TIMEOUT_SECONDS = 120

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=self.BUSY_TIMEOUT_SECONDS)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RuntimeError("authoring database schema is newer than this tool")
            if version == 0:
                connection.execute(
                    """
                    CREATE TABLE runs (
                        id TEXT PRIMARY KEY,
                        mode TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        error TEXT
                    )
                    """
                )
            if version == 1:
                connection.execute("ALTER TABLE candidates RENAME TO candidates_v1")
            if version < 2:
                connection.execute(
                    """
                    CREATE TABLE candidates (
                        id TEXT NOT NULL,
                        run_id TEXT NOT NULL REFERENCES runs(id),
                        game_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        reason TEXT,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (run_id, id)
                    )
                    """
                )
                if version == 1:
                    connection.execute(
                        """
                        INSERT INTO candidates(
                            id, run_id, game_id, status, payload_json, reason, updated_at
                        )
                        SELECT id, run_id, game_id, status, payload_json, reason, updated_at
                        FROM candidates_v1
                        """
                    )
                    connection.execute("DROP TABLE candidates_v1")
                connection.execute("CREATE INDEX candidates_run_id ON candidates(run_id)")
                connection.execute("PRAGMA user_version = 2")
            if version < 3:
                # Project-history mode walks each repository's merged pull requests
                # and default-branch commits page by page; the cursor lets a later
                # run continue further back instead of re-reading the same pages.
                connection.execute(
                    """
                    CREATE TABLE history_cursors (
                        repository TEXT NOT NULL,
                        source TEXT NOT NULL,
                        next_page INTEGER NOT NULL,
                        exhausted INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (repository, source)
                    )
                    """
                )
                connection.execute("PRAGMA user_version = 3")

    def create_run(self, mode: RunMode) -> str:
        run_id = f"author-{uuid.uuid4().hex[:16]}"
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs(id, mode, status, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                (run_id, mode.value, RunStatus.CREATED.value, now, now),
            )
            connection.commit()
        return run_id

    def update_run(self, run_id: str, status: RunStatus, error: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = ?, updated_at = ?, error = ? WHERE id = ?",
                (status.value, now, error, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)
            connection.commit()

    def run(self, run_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)

    def put_candidate(
        self,
        run_id: str,
        candidate_id: str,
        game_id: str,
        status: CandidateStatus,
        payload: dict[str, Any],
        reason: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO candidates(id, run_id, game_id, status, payload_json, reason, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    reason = excluded.reason,
                    updated_at = excluded.updated_at
                """,
                (candidate_id, run_id, game_id, status.value, serialized, reason, now),
            )
            connection.commit()

    def history_cursor(self, repository: str, source: str) -> tuple[int, bool]:
        """The next page to read and whether that history is exhausted."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT next_page, exhausted FROM history_cursors WHERE repository = ? AND source = ?",
                (repository.casefold(), source),
            ).fetchone()
        return (1, False) if row is None else (int(row["next_page"]), bool(row["exhausted"]))

    def advance_history_cursor(
        self, repository: str, source: str, next_page: int, *, exhausted: bool
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO history_cursors(repository, source, next_page, exhausted, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(repository, source) DO UPDATE SET
                    next_page = excluded.next_page,
                    exhausted = excluded.exhausted,
                    updated_at = excluded.updated_at
                """,
                (repository.casefold(), source, next_page, int(exhausted), now),
            )
            connection.commit()

    def validated_candidate_ids(self) -> set[str]:
        """Candidate IDs that reached validated or published in any run."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT id FROM candidates WHERE status IN ('validated', 'published')"
            ).fetchall()
        return {str(row["id"]) for row in rows}

    def candidates(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM candidates WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [
            {**dict(row), "payload": json.loads(str(row["payload_json"]))}
            for row in rows
        ]
