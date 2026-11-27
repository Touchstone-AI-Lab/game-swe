from __future__ import annotations

from collections.abc import Generator
from contextlib import suppress
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .models import Base, SchemaMetadata

SCHEMA_VERSION = "4"


class UnsupportedStateError(RuntimeError):
    """Raised when the state database was not created by this schema version."""


_FRESH_STATE = "Back up the state directory and configure a fresh RHENIUM_STATE_DIR."


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.ensure_directories()
        self.engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
        )
        if settings.database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _configure_sqlite(connection: object, _: object) -> None:
        cursor = connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def create_all(self) -> None:
        tables = set(inspect(self.engine).get_table_names())
        if tables:
            marker_value: str | None = None
            if "schema_metadata" in tables:
                with self.session_factory() as session:
                    marker = session.get(SchemaMetadata, "schema_version")
                    marker_value = marker.value if marker else None
            if marker_value != SCHEMA_VERSION:
                raise UnsupportedStateError(
                    f"Unsupported Rhenium state schema {marker_value or 'unknown'}; expected "
                    f"{SCHEMA_VERSION}. {_FRESH_STATE}"
                )

        Base.metadata.create_all(self.engine)
        with self.session_factory() as session:
            marker = session.get(SchemaMetadata, "schema_version")
            if marker is None:
                session.add(SchemaMetadata(key="schema_version", value=SCHEMA_VERSION))
                session.commit()
            elif marker.value != SCHEMA_VERSION:
                raise UnsupportedStateError("state schema changed while initializing")

            # A v4 marker without canonical task keys is inconsistent and must fail closed.
            task_columns = {column["name"] for column in inspect(self.engine).get_columns("tasks")}
            if "task_key" not in task_columns or "game_id" not in task_columns:
                raise UnsupportedStateError(
                    f"The state database schema marker does not match its task table. {_FRESH_STATE}"
                )
        if self.settings.database_url.startswith("sqlite:///"):
            database_path = Path(self.settings.database_url.removeprefix("sqlite:///")).expanduser()
            with suppress(OSError):
                database_path.chmod(0o600)

    def session(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session


def initialize_database(settings: Settings) -> Database:
    database = Database(settings)
    database.create_all()
    return database
