from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    task_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(64), index=True)
    pack_id: Mapped[str] = mapped_column(String(64), index=True)
    local_task_id: Mapped[str] = mapped_column(String(64), index=True)
    catalog_id: Mapped[str] = mapped_column(String(64), index=True)
    catalog_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium", index=True)
    archetype: Mapped[str] = mapped_column(String(64), default="systems", index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    requirement: Mapped[str] = mapped_column(Text)
    workspace_path: Mapped[str] = mapped_column(Text)
    starter_hash: Mapped[str] = mapped_column(String(64))
    mutation_json: Mapped[str] = mapped_column(Text, default="{}")
    rubric_json: Mapped[str] = mapped_column(Text, default="{}")
    validation_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    runs: Mapped[list[Run]] = relationship(back_populates="task")


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_key: Mapped[str] = mapped_column(ForeignKey("tasks.task_key"), index=True)
    path: Mapped[str] = mapped_column(Text, unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SchemaMetadata(Base):
    __tablename__ = "schema_metadata"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_key: Mapped[str] = mapped_column(ForeignKey("tasks.task_key"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(100), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_key: Mapped[str] = mapped_column(ForeignKey("tasks.task_key"), index=True)
    submission_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(100), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    task: Mapped[Task] = relationship(back_populates="runs")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class AuthSessionRecord(Base):
    __tablename__ = "auth_sessions"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    account_alias: Mapped[str] = mapped_column(String(64), index=True)
    principal: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    secret_json: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class RuntimeRecord(Base):
    __tablename__ = "runtime_artifacts"

    runtime_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    account_alias: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="preparing", index=True)
    artifact_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    target: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(100), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    public_state_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


JsonDict = dict[str, Any]
