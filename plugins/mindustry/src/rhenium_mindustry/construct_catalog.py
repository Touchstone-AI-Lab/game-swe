"""Catalog of the restored construct pack (``rhenium-mindustry-v1``).

These are the generation tasks that ask for a Mindustry server plugin written
from an empty scaffold. The repair catalog lives in :mod:`.catalog`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask

CONSTRUCT_CATALOG_ID = "rhenium-mindustry-v1"


class MindustryConstructTask(BenchmarkTask):
    task_kind: Literal["generation"] = "generation"
    game_version: Literal["159"] = "159"
    server_test_dir: str = Field(min_length=1)
    map_name: str = Field(min_length=1)
    expected_cases: int = Field(default=1, gt=0)
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.difficulty != "hard":
            raise ValueError("Mindustry tasks must remain hard")
        return self


class MindustryConstructCatalog(BenchmarkCatalog):
    game: Literal["mindustry"]
    tasks: list[MindustryConstructTask]

    @model_validator(mode="after")
    def catalog_identity(self) -> Self:
        if self.id != CONSTRUCT_CATALOG_ID:
            raise ValueError("unsupported Mindustry construct catalog id")
        return self

    @classmethod
    def load(
        cls,
        pack_root: Path | str,
        catalog_path: str = "catalog.json",
    ) -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()

        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Mindustry catalog is missing: {catalog_path}")

        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[MindustryConstructTask] = []

        for task in catalog.tasks:
            task_root = (root / "private" / "harbor" / task.id).resolve()

            if not task_root.is_relative_to(root) or not task_root.is_dir():
                raise ValueError(f"Harbor task is missing: {task.id}")

            server_test_root = (root / "private" / task.server_test_dir).resolve()

            if not server_test_root.is_relative_to(root):
                raise ValueError(f"Invalid server_test_dir for {task.id}")

            required = {
                "instruction": task_root / "instruction.md",
                "task metadata": task_root / "task.toml",
                "environment Dockerfile": task_root / "environment" / "Dockerfile",
                "environment build script": (
                    task_root
                    / "environment"
                    / "mindustry"
                    / "build-reference.sh"
                ),
                "environment manifest": (
                    task_root
                    / "environment"
                    / "mindustry"
                    / "plugin.hjson"
                ),
                "verifier entrypoint": task_root / "tests" / "test.sh",
                "verifier": task_root / "tests" / "verify.py",
                "rubric": task_root / "tests" / "rubric.json",
                "solution": task_root / "solution",
            }

            for label, candidate in required.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")

            rubric = json.loads(
                required["rubric"].read_text(encoding="utf-8")
            )
            cases = rubric.get("cases")

            if not isinstance(cases, list) or not cases:
                raise ValueError(f"rubric cases are invalid for {task.id}")

            names: list[str] = []

            for case in cases:
                if not isinstance(case, dict):
                    raise ValueError(f"rubric case is invalid for {task.id}")

                name = case.get("name")

                if not isinstance(name, str) or not name:
                    raise ValueError(f"rubric case name is invalid for {task.id}")

                names.append(name)

            if len(names) != len(set(names)):
                raise ValueError(
                    f"rubric case names are duplicated for {task.id}"
                )

            loaded.append(
                task.model_copy(
                    update={
                        "expected_cases": len(names),
                        "authored_prompt": required[
                            "instruction"
                        ].read_text(encoding="utf-8"),
                    }
                )
            )

        return catalog.model_copy(update={"tasks": loaded})


def expected_case_names(
    pack_root: Path,
    task: MindustryConstructTask,
) -> tuple[str, ...]:
    rubric = (
        pack_root
        / "private"
        / "harbor"
        / task.id
        / "tests"
        / "rubric.json"
    )

    raw = json.loads(rubric.read_text(encoding="utf-8"))
    cases = raw.get("cases")

    if not isinstance(cases, list):
        raise ValueError("Mindustry rubric cases are invalid")

    names = tuple(
        case["name"]
        for case in cases
        if isinstance(case, dict)
        and isinstance(case.get("name"), str)
    )

    if len(names) != task.expected_cases:
        raise ValueError("Mindustry rubric case count changed")

    if len(names) != len(set(names)):
        raise ValueError("Mindustry rubric case names are duplicated")

    return names
