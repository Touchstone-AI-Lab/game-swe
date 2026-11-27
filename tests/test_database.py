from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rhenium.config import Settings
from rhenium.database import UnsupportedStateError, initialize_database


def _settings(tmp_path: Path, database: Path) -> Settings:
    return Settings(
        root=tmp_path,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        database_url=f"sqlite:///{database}",
        benchmark_paths=(tmp_path / "benchmarks",),
        web_dist=None,
    )


def test_fresh_database_records_v4_runtime_schema(tmp_path: Path) -> None:
    database = tmp_path / "state" / "fresh.sqlite"
    initialize_database(_settings(tmp_path, database))

    with sqlite3.connect(database) as connection:
        marker = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()
        task_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        run_columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)").fetchall()}
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}

    assert marker == ("4",)
    assert {"task_key", "game_id", "pack_id", "local_task_id", "catalog_version"} <= task_columns
    assert "task_key" in run_columns and "task_id" not in run_columns
    assert "task_key" in job_columns and "task_id" not in job_columns
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"auth_sessions", "runtime_artifacts", "operations"} <= tables


def test_unversioned_database_is_rejected_without_mutation(tmp_path: Path) -> None:
    database = tmp_path / "unversioned.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE candidates (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO candidates VALUES ('keep-me')")
        connection.commit()

    with pytest.raises(UnsupportedStateError, match="Back up.*fresh RHENIUM_STATE_DIR"):
        initialize_database(_settings(tmp_path, database))

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id FROM candidates").fetchone() == ("keep-me",)
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_metadata'"
            ).fetchone()
            is None
        )


def test_v3_database_is_rejected_without_upgrade(tmp_path: Path) -> None:
    database = tmp_path / "state" / "v3.sqlite"
    settings = _settings(tmp_path, database)
    initialize_database(settings)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE schema_metadata SET value='3' WHERE key='schema_version'")
        connection.execute("DROP TABLE operations")
        connection.commit()

    with pytest.raises(UnsupportedStateError, match="schema 3; expected 4"):
        initialize_database(settings)

    with sqlite3.connect(database) as connection:
        marker = connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_version'"
        ).fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert marker == ("3",)
    assert "operations" not in tables


def test_v4_database_reopens_with_its_rows(tmp_path: Path) -> None:
    database = tmp_path / "state" / "reopen.sqlite"
    settings = _settings(tmp_path, database)
    initialize_database(settings)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO settings (key, value_json, updated_at) "
            "VALUES ('keep', '\"value\"', CURRENT_TIMESTAMP)"
        )
        connection.commit()

    initialize_database(settings)
    with sqlite3.connect(database) as connection:
        kept = connection.execute("SELECT value_json FROM settings WHERE key='keep'").fetchone()
    assert kept == ('"value"',)
