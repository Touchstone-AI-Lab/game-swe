"""Catalog model of the construct pack (catalog ``rhenium-dst-v2``, ``fixed-v1.json``).

A construct task asks for a mod written from an empty workspace. The model is
the one the pack was authored and validated against before the repair pack
replaced it in ``benchmarks/dst``; it is restored unchanged for the
``benchmarks/dst-construct`` pack. The repair catalog lives in ``catalog.py``.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from rhenium.core.catalog import (
    BenchmarkCatalog,
    BenchmarkTask,
    CatalogModel,
    LocalizedText,
)

CONSTRUCT_CATALOG_ID = "rhenium-dst-v2"
CONSTRUCT_CATALOG_FILE = "fixed-v1.json"


class PatternGroup(CatalogModel):
    name: str = Field(min_length=1)
    any_of: list[str] = Field(min_length=1)

    @field_validator("any_of")
    @classmethod
    def patterns_must_compile(cls, value: list[str]) -> list[str]:
        for pattern in value:
            if not pattern:
                raise ValueError("integration patterns must not be empty")
            re.compile(pattern)
        return value


class IntegrationCheck(CatalogModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    label: LocalizedText
    weight: int = Field(gt=0)
    glob: str = "**/*.lua"
    groups: list[PatternGroup] = Field(min_length=1)
    none_of: list[str] = Field(default_factory=list)

    @field_validator("none_of")
    @classmethod
    def exclusions_must_compile(cls, value: list[str]) -> list[str]:
        for pattern in value:
            if not pattern:
                raise ValueError("integration exclusion patterns must not be empty")
            re.compile(pattern)
        return value


class DstConstructTask(BenchmarkTask):
    difficulty: Literal["hard"]
    core_module: str
    hidden_test: str
    server_test: str
    minimum_lua_lines: int = Field(ge=100)
    integration_checks: list[IntegrationCheck] = Field(min_length=1)
    # Optional frozen case names. When declared, a suite result whose case set
    # differs (missing, extra, renamed or duplicated names) is not evidence.
    hidden_cases: tuple[str, ...] = ()
    server_cases: tuple[str, ...] = ()
    clean_room_synthetic: bool = False
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @field_validator("core_module", "hidden_test", "server_test")
    @classmethod
    def paths_must_be_safe_relative_posix(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value != path.as_posix():
            raise ValueError("catalog paths must be normalized relative POSIX paths")
        return value

    @field_validator("hidden_cases", "server_cases")
    @classmethod
    def case_names_are_unique_and_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not name.strip() for name in value) or len(set(value)) != len(value):
            raise ValueError("declared case names must be unique and non-blank")
        return value

    @model_validator(mode="after")
    def integration_weight_is_fixed(self) -> Self:
        if sum(check.weight for check in self.integration_checks) != 15:
            raise ValueError("integration check weights must total exactly 15")
        if len({check.id for check in self.integration_checks}) != len(self.integration_checks):
            raise ValueError("integration check IDs must be unique within a task")
        if self.core_module not in self.required_files:
            raise ValueError("core_module must be included in required_files")
        return self


class DstConstructCatalog(BenchmarkCatalog):
    game: Literal["dst"]
    tasks: list[DstConstructTask]

    @model_validator(mode="after")
    def all_dst_tasks_are_hard(self) -> Self:
        if any(task.difficulty != "hard" for task in self.tasks):
            raise ValueError("every DST task must be hard")
        return self

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = CONSTRUCT_CATALOG_FILE) -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"DST catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[DstConstructTask] = []
        for task in catalog.tasks:
            hidden = (root / task.hidden_test).resolve()
            server_test = (root / task.server_test).resolve()
            if not hidden.is_relative_to(root) or not hidden.is_file():
                raise ValueError(f"hidden test is missing for {task.id}: {task.hidden_test}")
            if not server_test.is_relative_to(root) or not server_test.is_file():
                raise ValueError(f"server test is missing for {task.id}: {task.server_test}")
            authored = ""
            if task.clean_room_synthetic:
                exam = (root / "exams" / f"{task.id}.md").resolve()
                if not exam.is_relative_to(root) or not exam.is_file():
                    raise ValueError(f"synthetic exam is missing for {task.id}")
                authored = exam.read_text(encoding="utf-8")
                starter = (root / "private" / "harbor" / task.id / "environment" / "mod").resolve()
                if not starter.is_relative_to(root) or not starter.is_dir():
                    raise ValueError(f"synthetic starter is missing for {task.id}")
            loaded.append(task.model_copy(update={"authored_prompt": authored}))
        return catalog.model_copy(update={"tasks": loaded})
