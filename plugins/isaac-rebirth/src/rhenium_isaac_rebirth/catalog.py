from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask

BASELINE_TASK = "isaac-exodus-release-regressions"
# The parts of a shared verifier that replace the image's /tests/<part>.
VERIFIER_PARTS = ("test.sh", "suite", "secret-suite", "james-suite")
VERIFIER_FILES = (
    "test.sh",
    "suite/main.lua",
    "suite/metadata.xml",
    "secret-suite/main.lua",
    "secret-suite/metadata.xml",
    "james-suite/main.lua",
    "james-suite/metadata.xml",
)


class IsaacTask(BenchmarkTask):
    source_mod: str = Field(min_length=1)
    game_version: Literal["Afterbirth+ v1.06.T1"]
    game_build: Literal["Steam App 250900 build 22878971"]
    expected_cases: int = Field(ge=1)
    clean_room_synthetic: bool = False
    # A derived Exodus task may name a shared verifier under private/verifiers/<name>/ whose
    # test.sh and three suites replace the ones baked into the image. None keeps the image's.
    verifier: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @property
    def starter_name(self) -> str:
        return "mod" if self.clean_room_synthetic else "exodus"

    @model_validator(mode="after")
    def validated_task_contract(self) -> Self:
        if self.clean_room_synthetic:
            if self.source_mod != "Clean-room synthetic":
                raise ValueError("synthetic Isaac tasks must not claim an upstream source mod")
            if self.verifier is not None:
                raise ValueError("synthetic Isaac tasks build their own verifier image")
        elif self.source_mod != "Exodus" or not self.id.startswith("isaac-exodus-"):
            raise ValueError("Isaac real-game tasks must derive from the validated Exodus tree")
        if self.difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("Isaac task difficulty must be easy, medium, or hard")
        required = {f"{self.starter_name}/main.lua", f"{self.starter_name}/metadata.xml"}
        if not required.issubset(self.required_files):
            raise ValueError("required_files must include the Isaac Lua entry points")
        if any(not value.startswith(f"{self.starter_name}/") for value in self.required_files):
            raise ValueError(f"required_files must be below {self.starter_name}/")
        return self


class IsaacCatalog(BenchmarkCatalog):
    game: Literal["isaac-rebirth"]
    tasks: list[IsaacTask]

    @model_validator(mode="after")
    def contains_the_validated_task(self) -> Self:
        if self.id == "isaac-core":
            ids = [task.id for task in self.tasks]
            if "isaac-exodus-release-regressions" not in ids:
                raise ValueError("the Isaac core catalog must keep the validated Exodus baseline task")
            if any(task.id == BASELINE_TASK and task.verifier is not None for task in self.tasks):
                raise ValueError("the frozen Exodus baseline keeps the verifier baked into its image")
            if len(set(ids)) != len(ids):
                raise ValueError("Isaac core task ids must be unique")
            if any(task.clean_room_synthetic for task in self.tasks):
                raise ValueError("the Isaac core catalog contains only real-game Exodus tasks")
        elif not self.tasks or any(not task.clean_room_synthetic for task in self.tasks):
            raise ValueError("non-core Isaac catalogs may contain only clean-room synthetic tasks")
        return self

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Isaac catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded_tasks: list[IsaacTask] = []
        for task in catalog.tasks:
            task_root = root / "private" / "harbor" / task.id
            exam = root / "exams" / f"{task.id}.md"
            candidates = {
                "starter": task_root / "environment" / task.starter_name,
                "exam": exam,
                "verifier": task_root / "tests" / "test.sh",
                "runtime image": task_root / "scripts" / "private-runtime.Dockerfile",
            }
            for label, candidate in candidates.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")
            for relative in task.required_files:
                required = (task_root / "environment" / relative).resolve()
                if not required.is_relative_to(root) or not required.is_file():
                    raise ValueError(f"required starter file is missing for {task.id}: {relative}")
            if not task.clean_room_synthetic:
                expected_saves = {"save1.dat": "[]", "save2.dat": '{"Register":[]}'}
                for name, expected_text in expected_saves.items():
                    save = candidates["starter"] / name
                    if not save.is_file() or save.read_text(encoding="utf-8").strip() != expected_text:
                        raise ValueError(f"deterministic mod-data fixture is invalid for {task.id}: {name}")
            verifier = candidates["verifier"].read_text(encoding="utf-8")
            expected = re.findall(r"^expected=([0-9]+)$", verifier, re.MULTILINE)
            if expected != [str(task.expected_cases)]:
                raise ValueError(f"verifier case count is invalid for {task.id}")
            shared = verifier_root(root, task)
            if shared is not None:
                for relative in VERIFIER_FILES:
                    part = (shared / relative).resolve()
                    if not part.is_relative_to(root) or not part.is_file():
                        raise ValueError(f"shared verifier {task.verifier} is missing {relative}")
                # The task's test.sh is the copy the case list is read from; it must be the
                # test.sh that actually runs.
                if (shared / "test.sh").read_bytes() != candidates["verifier"].read_bytes():
                    raise ValueError(f"{task.id} test.sh differs from shared verifier {task.verifier}")
            loaded_tasks.append(task.model_copy(update={"authored_prompt": exam.read_text(encoding="utf-8")}))
        return catalog.model_copy(update={"tasks": loaded_tasks})


def verifier_root(pack_root: Path, task: IsaacTask) -> Path | None:
    """The shared verifier directory a derived task runs instead of the image's suites."""
    if task.verifier is None:
        return None
    root = pack_root.resolve()
    shared = (root / "private" / "verifiers" / task.verifier).resolve()
    if not shared.is_relative_to(root / "private" / "verifiers") or not shared.is_dir():
        raise ValueError(f"shared verifier is missing for {task.id}: {task.verifier}")
    return shared


def expected_case_names(pack_root: Path, task: IsaacTask) -> tuple[str, ...]:
    verifier = (pack_root / "private" / "harbor" / task.id / "tests" / "test.sh").read_text(encoding="utf-8")
    match = re.search(r"^expected_cases=\(\n(?P<body>.*?)^\)$", verifier, re.MULTILINE | re.DOTALL)
    if match is None:
        raise ValueError("private verifier does not declare expected case names")
    names = tuple(line.strip() for line in match.group("body").splitlines() if line.strip())
    if len(names) != task.expected_cases or len(set(names)) != task.expected_cases:
        raise ValueError("private verifier case names are incomplete or duplicated")
    if any(re.fullmatch(r"[a-z0-9_]+", name) is None for name in names):
        raise ValueError("private verifier case names are invalid")
    return names
