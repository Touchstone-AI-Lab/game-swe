from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask

_EXPECTED = re.compile(r"^EXPECTED=([0-9]+)$", re.MULTILINE)

# Each GLuaTest pack is served by the same task model and evaluator, and each one owns
# its own runtime key (RuntimeManager keys runtimes by game and runtime ID, so two packs
# cannot share one ID). The ID is chosen by catalog identity, never by task content.
GLUATEST_RUNTIME_IDS = {
    "darkrp-core": "gmod-gluatest-darkrp",
    "garrys-mod-clean-room-synth": "gmod-gluatest-synth",
    "gmod-addon-repairs": "gmod-gluatest-addons",
}


class GarrysModTask(BenchmarkTask):
    task_kind: Literal["debugging"]
    source_mod: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    authored_prompt: str = Field(default="", exclude=True, repr=False)
    clean_room_synthetic: bool = False
    # "gamemode" tasks ship a gamemode tree (DarkRP, clean-room synth); "addon" tasks
    # ship one server addon that the verifier installs under garrysmod/addons.
    source_kind: Literal["gamemode", "addon"] = "gamemode"
    starter_directory: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]*$")

    @model_validator(mode="after")
    def addon_tasks_name_their_tree(self) -> Self:
        if self.source_kind == "addon":
            if self.starter_directory is None:
                raise ValueError("an addon task must name its starter directory")
            if self.clean_room_synthetic:
                raise ValueError("an addon task cannot be clean-room synthetic")
        elif self.starter_directory is not None:
            raise ValueError("only addon tasks may name a starter directory")
        return self

    @property
    def starter_name(self) -> str:
        if self.starter_directory is not None:
            return self.starter_directory
        return "gamemode" if self.clean_room_synthetic else "darkrp"

    @property
    def container_destination(self) -> str:
        if self.source_kind == "addon":
            return f"/app/{self.starter_name}"
        return "/app/darkrp"


class GarrysModCatalog(BenchmarkCatalog):
    game: Literal["garrys-mod"]
    tasks: list[GarrysModTask]

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Garry's Mod catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[GarrysModTask] = []
        for task in catalog.tasks:
            task_root = root / "private" / "harbor" / task.id
            verifier = task_root / "tests" / "test.sh"
            required = {
                "starter": task_root / "environment" / task.starter_name,
                "exam": root / "exams" / f"{task.id}.md",
                "suite": task_root / "tests" / "suite.lua",
                "verifier": verifier,
                "Dockerfile": task_root / "environment" / "Dockerfile",
                "reference": task_root / "solution" / "after",
            }
            for label, candidate in required.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")
            matches = _EXPECTED.findall(verifier.read_text(encoding="utf-8"))
            if len(matches) != 1 or int(matches[0]) < 1:
                raise ValueError(f"verifier case count is invalid for {task.id}")
            loaded.append(
                task.model_copy(
                    update={"authored_prompt": required["exam"].read_text(encoding="utf-8")}
                )
            )
        return catalog.model_copy(update={"tasks": loaded})


def expected_case_count(pack_root: Path, task: GarrysModTask) -> int:
    verifier = pack_root / "private" / "harbor" / task.id / "tests" / "test.sh"
    match = _EXPECTED.search(verifier.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError("private verifier does not declare an expected case count")
    return int(match.group(1))
