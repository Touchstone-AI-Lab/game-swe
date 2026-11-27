"""Declared task exclusions: an amendment that takes tasks out of a frozen study.

A study configuration cannot change once attempts carry its digest, so a later
decision to drop tasks is declared in ``task-exclusions.json`` beside the study's
ledger. Excluded tasks are skipped by ``e1 run`` and left out of every ledger,
report and export; their attempt records stay on disk untouched. Every task of the
configuration must be registered or excluded, so a task removed from the inventory
cannot silently fall out of (or break) a study.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .e1config import StudyConfig
from .inventory import BY_KEY
from .paths import StudyPaths

EXCLUSIONS_FILE = "task-exclusions.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Amendment(_Strict):
    """One decision: which tasks leave the study, why, when and by whom."""

    tasks: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)
    decided_at: str = Field(alias="decidedAt", pattern=r"^\d{4}-\d{2}-\d{2}$")
    decided_by: str = Field(alias="decidedBy", min_length=1)

    @model_validator(mode="after")
    def fields_are_meaningful(self) -> Self:
        date.fromisoformat(self.decided_at)
        if not self.reason.strip() or not self.decided_by.strip():
            raise ValueError("an amendment needs a reason and who decided it")
        if any(not task.strip() for task in self.tasks):
            raise ValueError("an amendment names an empty task key")
        return self


class TaskExclusions(_Strict):
    study_id: str = Field(alias="studyId")
    config_digest: str = Field(alias="configDigest", pattern=r"^[0-9a-f]{64}$")
    amendments: tuple[Amendment, ...] = Field(min_length=1)


@dataclass(frozen=True)
class Exclusions:
    """The excluded task keys of one study and the amendments that excluded them."""

    tasks: frozenset[str]
    amendments: tuple[Amendment, ...]

    def public(self) -> list[dict[str, object]]:
        return [amendment.model_dump(mode="json", by_alias=True) for amendment in self.amendments]


def load(paths: StudyPaths, config: StudyConfig, config_digest: str) -> Exclusions:
    """Read and check the study's declared exclusions; an absent file excludes nothing.

    Fails closed when the file belongs to another study or configuration, excludes a
    task the configuration does not list or excludes one twice, and, with or without
    the file, when a configured task is neither registered nor excluded.
    """
    path = paths.e1_study(config.study_id) / EXCLUSIONS_FILE
    amendments: tuple[Amendment, ...] = ()
    # Anything at the path (a directory, a dangling link) must read as a declaration.
    if path.is_symlink() or path.exists():
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ValueError(f"{path} cannot be read ({error.strerror})") from None
        declared = TaskExclusions.model_validate_json(content)
        if declared.study_id != config.study_id:
            raise ValueError(f"{path} is declared for study {declared.study_id!r}, not {config.study_id!r}")
        if declared.config_digest != config_digest:
            raise ValueError(
                f"{path} is declared for configuration {declared.config_digest}, "
                f"not the loaded one ({config_digest})"
            )
        amendments = declared.amendments
    excluded: set[str] = set()
    configured = set(config.tasks)
    for amendment in amendments:
        for task in amendment.tasks:
            if task not in configured:
                raise ValueError(f"{path} excludes {task}, which the study configuration does not list")
            if task in excluded:
                raise ValueError(f"{path} excludes {task} twice")
            excluded.add(task)
    unknown = [task for task in config.tasks if task not in BY_KEY and task not in excluded]
    if unknown:
        listed = ", ".join(unknown[:5]) + (f" and {len(unknown) - 5} more" if len(unknown) > 5 else "")
        raise ValueError(
            f"{len(unknown)} configured task(s) are neither registered nor excluded in {path}: {listed}"
        )
    return Exclusions(frozenset(excluded), amendments)


def refuse_excluded(task: str, attempt_id: str, excluded: Collection[str]) -> None:
    """Refuse to act on one attempt of an excluded task."""
    if task in excluded:
        raise ValueError(
            f"{attempt_id} is an attempt of {task}, which {EXCLUSIONS_FILE} excludes from the study"
        )
