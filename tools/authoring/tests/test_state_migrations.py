from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from rhenium_authoring.models import CandidateStatus, RunMode
from rhenium_authoring.state import SCHEMA_VERSION, AuthoringStore


def _legacy_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error TEXT
            );
            CREATE TABLE candidates (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(id),
                game_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                reason TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX candidates_run_id ON candidates(run_id);
            INSERT INTO runs VALUES (
                'author-original', 'review', 'failed', 'created-original',
                'updated-original', 'original run failure'
            );
            PRAGMA user_version = 1;
            """
        )
        connection.execute(
            "INSERT INTO candidates VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "synthetic-repeated",
                "author-original",
                "dst",
                "rejected",
                json.dumps({"evidence": "original evidence", "count": 2}),
                "original review finding",
                "updated-candidate",
            ),
        )


def _snapshot(path: Path) -> dict[str, object]:
    with sqlite3.connect(path) as connection:
        return {
            "version": connection.execute("PRAGMA user_version").fetchone()[0],
            "runs": connection.execute("SELECT * FROM runs ORDER BY id").fetchall(),
            "candidates": connection.execute(
                "SELECT * FROM candidates ORDER BY run_id, id"
            ).fetchall(),
            "schema": connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY name"
            ).fetchall(),
        }


def test_fresh_store_keeps_repeated_candidates_separate_and_updates_same_run(tmp_path: Path) -> None:
    path = tmp_path / "authoring.sqlite"
    store = AuthoringStore(path)
    first = store.create_run(RunMode.REVIEW)
    retry = store.create_run(RunMode.REVIEW)
    store.put_candidate(
        first,
        "synthetic-repeated",
        "dst",
        CandidateStatus.REJECTED,
        {"evidence": "first"},
        reason="original finding",
    )
    original = store.candidates(first)
    store.put_candidate(
        retry,
        "synthetic-repeated",
        "dst",
        CandidateStatus.GENERATED,
        {"evidence": "retry"},
    )
    store.put_candidate(
        retry,
        "synthetic-repeated",
        "dst",
        CandidateStatus.ACTION_REQUIRED,
        {"evidence": "retry validated"},
        reason="runtime unavailable",
    )
    reopened = AuthoringStore(path)
    assert reopened.candidates(first) == original
    rows = reopened.candidates(retry)
    assert len(rows) == 1
    assert rows[0]["run_id"] == retry
    assert rows[0]["status"] == CandidateStatus.ACTION_REQUIRED.value
    assert rows[0]["payload"] == {"evidence": "retry validated"}
    assert rows[0]["reason"] == "runtime unavailable"
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3
        columns = connection.execute("PRAGMA table_info(candidates)").fetchall()
        primary_key = {row[1]: row[5] for row in columns if row[5]}
        assert primary_key == {"run_id": 1, "id": 2}


def test_v1_upgrade_preserves_all_records_and_allows_same_candidate_in_retry(tmp_path: Path) -> None:
    path = tmp_path / "authoring.sqlite"
    _legacy_database(path)
    before = _snapshot(path)
    store = AuthoringStore(path)
    after = _snapshot(path)
    assert after["version"] == 3
    assert after["runs"] == before["runs"]
    assert after["candidates"] == before["candidates"]
    original = store.candidates("author-original")
    retry = store.create_run(RunMode.REVIEW)
    store.put_candidate(
        retry,
        "synthetic-repeated",
        "dst",
        CandidateStatus.GENERATED,
        {"evidence": "new generation"},
    )
    assert store.candidates("author-original") == original
    assert store.candidates(retry)[0]["payload"] == {"evidence": "new generation"}
    assert store.run("author-original")["error"] == "original run failure"
    assert AuthoringStore(path).candidates("author-original") == original


def test_failed_upgrade_rolls_back_schema_records_and_version(tmp_path: Path) -> None:
    path = tmp_path / "authoring.sqlite"
    _legacy_database(path)
    before = _snapshot(path)

    def deny_drop(
        action: int,
        table: str | None,
        column: str | None,
        database: str | None,
        trigger: str | None,
    ) -> int:
        del column, database, trigger
        if action == sqlite3.SQLITE_DROP_TABLE and table == "candidates_v1":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    class FailingMigrationStore(AuthoringStore):
        @contextmanager
        def connect(self) -> Iterator[sqlite3.Connection]:
            with super().connect() as connection:
                connection.set_authorizer(deny_drop)
                yield connection

    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        FailingMigrationStore(path)
    assert _snapshot(path) == before
    recovered = AuthoringStore(path)
    assert recovered.candidates("author-original")[0]["payload"]["evidence"] == "original evidence"


def test_newer_version_is_rejected_without_changing_existing_data(tmp_path: Path) -> None:
    path = tmp_path / "authoring.sqlite"
    _legacy_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")
    before = _snapshot(path)
    with pytest.raises(RuntimeError, match="newer"):
        AuthoringStore(path)
    assert _snapshot(path) == before


def _v2_database(path: Path) -> None:
    """A schema-2 store as the previous tool release left it."""
    _legacy_database(path)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            ALTER TABLE candidates RENAME TO candidates_v1;
            CREATE TABLE candidates (
                id TEXT NOT NULL,
                run_id TEXT NOT NULL REFERENCES runs(id),
                game_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                reason TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (run_id, id)
            );
            INSERT INTO candidates SELECT * FROM candidates_v1;
            DROP TABLE candidates_v1;
            CREATE INDEX candidates_run_id ON candidates(run_id);
            PRAGMA user_version = 2;
            """
        )


def test_v2_upgrade_adds_history_cursors_and_keeps_every_record(tmp_path: Path) -> None:
    path = tmp_path / "authoring.sqlite"
    _v2_database(path)
    before = _snapshot(path)
    assert before["version"] == 2
    store = AuthoringStore(path)
    after = _snapshot(path)
    assert after["version"] == 3
    assert after["runs"] == before["runs"]
    assert after["candidates"] == before["candidates"]
    assert store.history_cursor("Owner/Repo", "pulls") == (1, False)
    store.advance_history_cursor("Owner/Repo", "pulls", 4, exhausted=False)
    store.advance_history_cursor("owner/repo", "commits", 2, exhausted=True)
    reopened = AuthoringStore(path)
    # Repository names are case-insensitive on GitHub; one cursor per source.
    assert reopened.history_cursor("owner/REPO", "pulls") == (4, False)
    assert reopened.history_cursor("OWNER/repo", "commits") == (2, True)
