from __future__ import annotations

import csv
import json
import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask


class TerrariaTask(BenchmarkTask):
    task_kind: Literal["repository-debugging"] = "repository-debugging"
    source_mod: str = Field(min_length=1)
    source_repo: str = Field(pattern=r"^https://github\.com/")
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_license: str = Field(min_length=1)
    starter_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    container_destination: str = Field(pattern=r"^/workspace/[a-z0-9][a-z0-9_-]*$")
    submission_language: Literal["C#"] = "C#"
    game_version: Literal["1.4.4.9"] = "1.4.4.9"
    tmodloader_api: str = Field(min_length=1)
    evaluation_boundary: str = Field(min_length=1)
    expected_cases: int = Field(default=1, gt=0)
    engine_mode: Literal["dedicated-server"] = "dedicated-server"
    expected_engine_cases: int = Field(default=1, gt=0)
    engine_case_names: tuple[str, ...] = Field(default=(), exclude=True, repr=False)
    client_only_exclusions: tuple[str, ...] = Field(default=(), exclude=True, repr=False)
    defect_groups: int = Field(gt=0)
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.difficulty != "hard":
            raise ValueError("Terraria tasks must remain hard")
        prefix = f"{self.starter_name}/"
        if any(not value.startswith(prefix) for value in self.required_files):
            raise ValueError(f"required_files must be below {prefix}")
        if self.container_destination != f"/workspace/{self.starter_name}":
            raise ValueError("container_destination must match starter_name")
        return self


class TerrariaCatalog(BenchmarkCatalog):
    game: Literal["terraria"]
    tasks: list[TerrariaTask]

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Terraria catalog is missing: {catalog_path}")

        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[TerrariaTask] = []
        for task in catalog.tasks:
            task_root = (root / "private" / "harbor" / task.id).resolve()
            if not task_root.is_relative_to(root) or not task_root.is_dir():
                raise ValueError(f"Harbor task is missing: {task.id}")

            required = {
                "instruction": task_root / "instruction.md",
                "exam": root / "exams" / f"{task.id}.md",
                "task metadata": task_root / "task.toml",
                "environment Dockerfile": task_root / "environment" / "Dockerfile",
                "starter repository": task_root / "environment" / task.starter_name,
                "verifier entrypoint": task_root / "tests" / "test.sh",
                "case contracts": task_root / "validation" / "case-contracts.tsv",
                "rubric": task_root / "tests" / "rubric.json",
                "engine rubric": task_root / "engine-rubric.json",
                "engine fixture": task_root / "engine",
                "solution": task_root / "solution",
            }
            for label, candidate in required.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")

            if required["exam"].read_bytes() != required["instruction"].read_bytes():
                raise ValueError(f"public exam drifted from Harbor instruction: {task.id}")

            metadata_raw = tomllib.loads(required["task metadata"].read_text(encoding="utf-8"))
            metadata = metadata_raw.get("metadata")
            if not isinstance(metadata, dict):
                raise ValueError(f"task metadata is invalid for {task.id}")
            if metadata.get("source_repo") != task.source_repo:
                raise ValueError(f"source repository drifted for {task.id}")
            if metadata.get("base_commit") != task.source_commit:
                raise ValueError(f"source commit drifted for {task.id}")
            if metadata.get("source_license") != task.source_license:
                raise ValueError(f"source license drifted for {task.id}")
            if metadata.get("independent_defect_groups") != task.defect_groups:
                raise ValueError(f"defect-group count drifted for {task.id}")
            if metadata.get("game_build") != task.game_version:
                raise ValueError(f"game version drifted for {task.id}")
            if task.tmodloader_api not in str(metadata.get("tmodloader_api", "")):
                raise ValueError(f"tModLoader API description drifted for {task.id}")
            if metadata.get("evaluation_boundary") != task.evaluation_boundary:
                raise ValueError(f"evaluation boundary drifted for {task.id}")

            rubric = json.loads(required["rubric"].read_text(encoding="utf-8"))
            cases = rubric.get("cases")
            if not isinstance(cases, list) or not cases:
                raise ValueError(f"rubric cases are invalid for {task.id}")
            names = [case.get("name") for case in cases if isinstance(case, dict)]
            if any(not isinstance(name, str) or not name for name in names):
                raise ValueError(f"rubric case name is invalid for {task.id}")
            if len(names) != len(cases) or len(names) != len(set(names)):
                raise ValueError(f"rubric case names are invalid for {task.id}")
            if metadata.get("expected_private_cases") != len(names):
                raise ValueError(f"private case count drifted for {task.id}")

            engine_rubric = json.loads(required["engine rubric"].read_text(encoding="utf-8"))
            if engine_rubric.get("schema_version") != 1:
                raise ValueError(f"engine rubric schema is invalid for {task.id}")
            engine_mode = engine_rubric.get("mode")
            if engine_mode != "dedicated-server":
                raise ValueError(f"engine mode is invalid for {task.id}")
            engine_cases = engine_rubric.get("cases")
            if (
                not isinstance(engine_cases, list)
                or not engine_cases
                or any(not isinstance(name, str) or not name for name in engine_cases)
                or len(engine_cases) != len(set(engine_cases))
            ):
                raise ValueError(f"engine rubric cases are invalid for {task.id}")
            exclusions = engine_rubric.get("client_only_exclusions")
            if (
                not isinstance(exclusions, list)
                or any(not isinstance(value, str) or not value.strip() for value in exclusions)
            ):
                raise ValueError(f"engine exclusions are invalid for {task.id}")

            engine = required["engine fixture"]
            projects = list(engine.glob("*/*.csproj"))
            if len(projects) != 1 or not (engine / "tModLoader.targets").is_file():
                raise ValueError(f"engine verifier project is invalid for {task.id}")
            project_root = projects[0].parent
            if not (project_root / "build.txt").is_file():
                raise ValueError(f"engine verifier metadata is missing for {task.id}")
            if not any(project_root.glob("*.cs")):
                raise ValueError(f"engine verifier source is missing for {task.id}")

            with required["case contracts"].open(encoding="utf-8", newline="") as handle:
                contracts = list(csv.DictReader(handle, delimiter="\t"))
            contract_names = [row.get("case", "") for row in contracts]
            if contract_names != names:
                raise ValueError(f"case contracts drifted from rubric for {task.id}")
            rubric_groups = {
                case.get("group") for case in cases if isinstance(case, dict)
            }
            contract_groups = {row.get("group") for row in contracts}
            if (
                None in rubric_groups
                or "" in contract_groups
                or rubric_groups != contract_groups
                or len(rubric_groups) != task.defect_groups
            ):
                raise ValueError(f"defect groups drifted for {task.id}")

            starter = required["starter repository"]
            for relative in task.required_files:
                relative_path = Path(relative)
                if relative_path.parts[:1] != (task.starter_name,):
                    raise ValueError(f"required file escaped starter for {task.id}")
                candidate = (task_root / "environment" / relative_path).resolve()
                if not candidate.is_relative_to(starter.parent.resolve()) or not candidate.is_file():
                    raise ValueError(f"required source is missing for {task.id}: {relative}")

            loaded.append(
                task.model_copy(
                    update={
                        "expected_cases": len(names),
                        "engine_mode": engine_mode,
                        "expected_engine_cases": len(engine_cases),
                        "engine_case_names": tuple(engine_cases),
                        "client_only_exclusions": tuple(exclusions),
                        "authored_prompt": required["instruction"].read_text(encoding="utf-8"),
                    }
                )
            )
        return catalog.model_copy(update={"tasks": loaded})


def expected_case_names(pack_root: Path, task: TerrariaTask) -> tuple[str, ...]:
    rubric = pack_root / "private" / "harbor" / task.id / "tests" / "rubric.json"
    raw = json.loads(rubric.read_text(encoding="utf-8"))
    cases = raw.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Terraria rubric cases are invalid")
    names = tuple(
        case["name"]
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("name"), str)
    )
    if len(names) != task.expected_cases or len(names) != len(set(names)):
        raise ValueError("Terraria rubric case set changed")
    return names


def expected_engine_case_names(pack_root: Path, task: TerrariaTask) -> tuple[str, ...]:
    rubric = pack_root / "private" / "harbor" / task.id / "engine-rubric.json"
    raw = json.loads(rubric.read_text(encoding="utf-8"))
    cases = raw.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Terraria engine rubric cases are invalid")
    names = tuple(name for name in cases if isinstance(name, str))
    if (
        names != task.engine_case_names
        or len(names) != task.expected_engine_cases
        or len(names) != len(set(names))
    ):
        raise ValueError("Terraria engine rubric case set changed")
    return names
