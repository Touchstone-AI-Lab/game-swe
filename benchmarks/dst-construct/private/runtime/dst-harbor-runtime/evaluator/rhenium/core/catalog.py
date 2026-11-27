from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CatalogModel(BaseModel):
    """Strict immutable base for public benchmark contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalizedText(CatalogModel):
    en: str = Field(min_length=1)
    zh: str = Field(min_length=1)

    @field_validator("en", "zh")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("localized text must not be blank")
        return value


class LocalizedList(CatalogModel):
    en: list[str] = Field(min_length=1)
    zh: list[str] = Field(min_length=1)

    @field_validator("en", "zh")
    @classmethod
    def entries_must_not_be_blank(cls, value: list[str]) -> list[str]:
        if any(not entry.strip() for entry in value):
            raise ValueError("localized list entries must not be blank")
        return value


class BenchmarkTask(CatalogModel):
    """Fields shared by coding tasks for any supported game."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    difficulty: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: LocalizedText
    summary: LocalizedText
    brief: LocalizedText
    requirements: LocalizedList
    api_usage: LocalizedList
    acceptance: LocalizedList
    domains: list[str] = Field(min_length=1)
    estimated_minutes: int = Field(ge=1)
    required_files: list[str] = Field(min_length=1)

    @field_validator("domains")
    @classmethod
    def domains_must_be_unique_and_non_blank(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not item.strip() for item in value):
            raise ValueError("domains must be unique and non-blank")
        return value

    @field_validator("required_files")
    @classmethod
    def required_paths_must_be_safe(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("required_files must be unique")
        for raw in value:
            path = PurePosixPath(raw)
            if path.is_absolute() or ".." in path.parts or raw != path.as_posix():
                raise ValueError("required_files paths must be normalized relative POSIX paths")
        return value


class BenchmarkCatalog(CatalogModel):
    """A variable-size catalog owned by one game plugin."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    game: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: LocalizedText
    description: LocalizedText
    tasks: Sequence[BenchmarkTask] = Field(min_length=1)

    @model_validator(mode="after")
    def task_ids_are_unique(self) -> Self:
        identifiers = [task.id for task in self.tasks]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("task IDs must be unique")
        return self
