from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask


class StardewTask(BenchmarkTask):
    task_kind: Literal["debugging", "generation"]
    source_mod: str = Field(min_length=1)
    game_version: Literal["1.6.15"]
    smapi_version: Literal["4.1.10"]
    authored_prompt: str = Field(default="", exclude=True, repr=False)
    clean_room_synthetic: bool = False

    @property
    def starter_name(self) -> str:
        if self.clean_room_synthetic:
            return "mod"
        return "mod" if self.task_kind == "generation" else "StardewMods"

    @property
    def container_destination(self) -> str:
        if self.clean_room_synthetic:
            return "/app/mod"
        return "/app/mod" if self.task_kind == "generation" else "/app/StardewMods"

    @model_validator(mode="after")
    def required_files_match_starter(self) -> Self:
        prefix = f"{self.starter_name}/"
        if any(not value.startswith(prefix) for value in self.required_files):
            raise ValueError(f"required_files must be below {prefix}")
        return self


class StardewCatalog(BenchmarkCatalog):
    game: Literal["stardew-valley"]
    tasks: list[StardewTask]

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Stardew Valley catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded_tasks: list[StardewTask] = []
        for task in catalog.tasks:
            task_root = root / "private" / "harbor" / task.id
            starter = task_root / "environment" / task.starter_name
            instruction = root / "exams" / f"{task.id}.md"
            verifier = task_root / "tests" / "test.sh"
            dockerfile = task_root / "environment" / "Dockerfile"
            for label, candidate in {
                "starter": starter,
                "exam": instruction,
                "verifier": verifier,
                "Dockerfile": dockerfile,
            }.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")
            expected_matches = re.findall(
                r"^EXPECTED=([0-9]+)$", verifier.read_text(encoding="utf-8"), re.MULTILINE
            )
            if len(expected_matches) != 1 or int(expected_matches[0]) < 1:
                raise ValueError(f"verifier case count is invalid for {task.id}")
            loaded_tasks.append(
                task.model_copy(update={"authored_prompt": instruction.read_text(encoding="utf-8")})
            )
        return catalog.model_copy(update={"tasks": loaded_tasks})


def expected_case_count(pack_root: Path, task: StardewTask) -> int:
    verifier = pack_root / "private" / "harbor" / task.id / "tests" / "test.sh"
    match = re.search(r"^EXPECTED=([0-9]+)$", verifier.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise ValueError("private verifier does not declare an expected case count")
    return int(match.group(1))
