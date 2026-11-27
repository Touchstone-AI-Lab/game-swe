from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Self

from pydantic import Field

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask

CATALOG_ID = "slay-the-spire-core"
STARTER_NAME = "modthespire"
CONTAINER_DESTINATION = "/app/modthespire"
# Native tasks ship their source tree as environment/project. Game-backed verifier
# admission is separate from this layout: the retired enum r2 probe never started the game.
NATIVE_STARTER_NAME = "project"

# A source-tree layout or a licensed classpath does not prove that a verifier
# starts the game. Keep admission explicit; unknown tasks fail closed.
GAME_BACKED_TASKS = frozenset({
    "basemod-dynamic-descriptions-r2",
    "stslib-block-ledger-r1",
    "stslib-icon-layout-r1",
    "downfall-stasis-lifecycle-r1",
    "basemod-phase-transitions-r1",
    "downfall-socket-flow-r3",
    "mts-enum-identity-r3",
    "mts-load-order-regressions-r2",
    "mts-mod-identity-regressions-r2",
})

# The private verifier declares how many JUnit assertions a complete run observes.
# It is read from the authored verifier rather than restated in the catalog, so the
# pack stays the single source of truth for its own pass criterion.
_EXPECTED = re.compile(r"^EXPECTED=([0-9]+)$", re.MULTILINE)


class SlayTheSpireTask(BenchmarkTask):
    """A mod repair task with its source layout and verifier admission status."""

    task_kind: Literal["debugging"]
    source_mod: str = Field(min_length=1)
    # The pack pins each task to the parent of the upstream fix; the catalog records
    # the branch or commit that base was taken from.
    source_commit: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    authored_prompt: str = Field(default="", exclude=True, repr=False)
    expected_assertions: int = Field(default=0, ge=0, exclude=True, repr=False)
    native_runtime: bool = Field(default=False, exclude=True, repr=False)

    @property
    def game_backed(self) -> bool:
        return self.native_runtime and self.id in GAME_BACKED_TASKS

    @property
    def starter_name(self) -> str:
        return NATIVE_STARTER_NAME if self.native_runtime else STARTER_NAME

    @property
    def container_destination(self) -> str:
        return CONTAINER_DESTINATION


class SlayTheSpireCatalog(BenchmarkCatalog):
    game: Literal["slay-the-spire"]
    tasks: list[SlayTheSpireTask]

    @property
    def container_tasks(self) -> list[SlayTheSpireTask]:
        """Tasks the container runtime builds and evaluates (not the native ones)."""
        return [task for task in self.tasks if not task.native_runtime]

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Slay the Spire catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        if catalog.id != CATALOG_ID:
            raise ValueError("unsupported Slay the Spire catalog id")
        loaded: list[SlayTheSpireTask] = []
        for task in catalog.tasks:
            task_root = root / "private" / "harbor" / task.id
            verifier = task_root / "tests" / "test.sh"
            exam = root / "exams" / f"{task.id}.md"
            native = not (task_root / "environment" / STARTER_NAME).exists() and (
                task_root / "environment" / NATIVE_STARTER_NAME
            ).is_dir()
            required = {
                "starter": task_root / "environment" / (NATIVE_STARTER_NAME if native else STARTER_NAME),
                "environment Dockerfile": task_root / "environment" / "Dockerfile",
                "instruction": task_root / "instruction.md",
                "exam": exam,
                "verifier": verifier,
                "reference": task_root / "solution" / "after",
                "oracle script": task_root / "solution" / "solve.sh",
            }
            for label, candidate in required.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")
            for relative in task.required_files:
                candidate = (task_root / "environment" / relative).resolve()
                if not candidate.is_relative_to(root) or not candidate.is_file():
                    raise ValueError(f"required file {relative} is missing for {task.id}")
            matches = _EXPECTED.findall(verifier.read_text(encoding="utf-8"))
            if not native and (len(matches) != 1 or int(matches[0]) < 1):
                raise ValueError(f"verifier assertion count is invalid for {task.id}")
            if (
                exam.read_text(encoding="utf-8").strip()
                != required["instruction"].read_text(encoding="utf-8").strip()
            ):
                raise ValueError(f"public exam drifted from the Harbor instruction: {task.id}")
            loaded.append(
                task.model_copy(
                    update={
                        "authored_prompt": exam.read_text(encoding="utf-8"),
                        "expected_assertions": 0 if native else int(matches[0]),
                        "native_runtime": native,
                    }
                )
            )
        return catalog.model_copy(update={"tasks": loaded})


def expected_assertion_count(pack_root: Path, task: SlayTheSpireTask) -> int:
    """The verifier's own declared assertion count, read from the authored pack."""
    verifier = pack_root / "private" / "harbor" / task.id / "tests" / "test.sh"
    match = _EXPECTED.search(verifier.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError("private verifier does not declare an expected assertion count")
    return int(match.group(1))
