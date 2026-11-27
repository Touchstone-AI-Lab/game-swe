from __future__ import annotations

import csv
import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask


class Left4Dead2Task(BenchmarkTask):
    task_kind: Literal["repository-debugging"]
    source_mod: str = Field(min_length=1)
    source_repo: str = Field(pattern=r"^https://github\.com/")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    starter_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    container_destination: str = Field(pattern=r"^/app/[a-z0-9][a-z0-9_-]*$")
    submission_language: Literal["SourcePawn", "Squirrel"]
    expected_cases: int = Field(gt=0)
    defect_groups: int = Field(gt=0)
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @model_validator(mode="after")
    def paths_match_starter(self) -> Self:
        prefix = f"{self.starter_name}/"
        if any(not value.startswith(prefix) for value in self.required_files):
            raise ValueError(f"required_files must be below {prefix}")
        if self.container_destination != f"/app/{self.starter_name}":
            raise ValueError("container_destination must match starter_name")
        return self


class Left4Dead2Catalog(BenchmarkCatalog):
    game: Literal["left-4-dead-2"]
    tasks: list[Left4Dead2Task]

    @staticmethod
    def _expected_from_metadata(metadata: dict[str, object]) -> int:
        for key in ("expected_private_cases", "expected_server_cases"):
            value = metadata.get(key)
            if type(value) is int and value > 0:
                return value
        raise ValueError("L4D2 task metadata has no expected case count")

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Left 4 Dead 2 catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[Left4Dead2Task] = []
        for task in catalog.tasks:
            task_root = root / "private" / "harbor" / task.id
            instruction = task_root / "instruction.md"
            exam = root / "exams" / f"{task.id}.md"
            task_toml = task_root / "task.toml"
            required = {
                "starter": task_root / "environment" / task.starter_name,
                "instruction": instruction,
                "exam": exam,
                "verifier Dockerfile": task_root / "tests" / "Dockerfile",
                "verifier entrypoint": task_root / "tests" / "test.sh",
                "verifier": task_root / "tests" / "verify.py",
                "solution": task_root / "solution",
                "case contracts": task_root / "validation" / "case-contracts.tsv",
                "task metadata": task_toml,
            }
            for label, candidate in required.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")
            if exam.read_bytes() != instruction.read_bytes():
                raise ValueError(f"public exam drifted from Harbor instruction: {task.id}")

            raw = tomllib.loads(task_toml.read_text(encoding="utf-8"))
            metadata = raw.get("metadata")
            if not isinstance(metadata, dict):
                raise ValueError(f"task metadata is invalid for {task.id}")
            if metadata.get("source_repo") != task.source_repo:
                raise ValueError(f"source repository drifted for {task.id}")
            if metadata.get("base_commit") != task.source_commit:
                raise ValueError(f"source commit drifted for {task.id}")
            if metadata.get("independent_defect_groups") != task.defect_groups:
                raise ValueError(f"defect-group count drifted for {task.id}")
            if cls._expected_from_metadata(metadata) != task.expected_cases:
                raise ValueError(f"private case count drifted for {task.id}")

            contracts = required["case contracts"]
            assert contracts.is_file()
            with contracts.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            names = [row.get("case", "") for row in rows]
            if len(names) != task.expected_cases or len(names) != len(set(names)):
                raise ValueError(f"case contracts are incomplete or duplicated for {task.id}")
            loaded.append(
                task.model_copy(update={"authored_prompt": instruction.read_text(encoding="utf-8")})
            )
        return catalog.model_copy(update={"tasks": loaded})


def expected_case_count(task: Left4Dead2Task) -> int:
    return task.expected_cases
