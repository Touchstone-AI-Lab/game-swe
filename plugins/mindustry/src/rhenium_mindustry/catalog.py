from __future__ import annotations

import csv
import json
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask, CatalogModel

from .container import CONTAINER_DESTINATION, RELEASE_TAG, STARTER_NAME

CATALOG_ID = "rhenium-mindustry-v2"
# Header that materialize.py prepends to every Harbor instruction.md; the public
# exam body must equal the instruction after this header.
HARBOR_INSTRUCTION_HEADER = (
    "# Harbor workspace\n\n"
    f"Complete this task in `{CONTAINER_DESTINATION}`; the verifier compiles its Java "
    f"sources against the pinned Mindustry {RELEASE_TAG} dedicated server.\n\n"
)
DEFAULT_SOURCE_ROOTS = ("core/src", "server/src")
DEFAULT_EXTRA_SOURCES = ("annotations/src/main/java/mindustry/annotations/Annotations.java",)
CASE_ROLES = frozenset({"sentinel", "target", "preserved"})
# The grader suite class the trusted harness loads from the task's tests/suite tree.
SUITE_SOURCE = "suite/rhenium/mindustry/grader/TaskSuite.java"


def _relative_posix(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError("catalog paths must be normalized relative POSIX paths")
    return value


class BuildSpec(CatalogModel):
    """The trusted offline build: javac over the game's own sources against the pinned server."""

    tool: Literal["mindustry-source"]
    source_roots: tuple[str, ...] = DEFAULT_SOURCE_ROOTS
    extra_sources: tuple[str, ...] = DEFAULT_EXTRA_SOURCES
    java_release: Literal[17] = 17

    @field_validator("source_roots", "extra_sources")
    @classmethod
    def paths_are_relative_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _relative_posix(item)
        if len(set(value)) != len(value):
            raise ValueError("build paths must be unique")
        return value

    @field_validator("source_roots")
    @classmethod
    def has_source_roots(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("a build needs at least one source root")
        return value


class UpstreamProvenance(CatalogModel):
    repository: str = Field(pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    release_tag: str = Field(pattern=r"^v[0-9]+(\.[0-9]+)?$")
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    fix_commits: tuple[str, ...] = Field(min_length=1)
    license_spdx: Literal["GPL-3.0"]
    license_file: str

    @field_validator("fix_commits")
    @classmethod
    def fix_commits_are_full_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if len(item) != 40 or any(character not in "0123456789abcdef" for character in item):
                raise ValueError("fix commits must be full lower-case SHA-1 hashes")
        if len(set(value)) != len(value):
            raise ValueError("fix commits must be unique")
        return value

    @field_validator("license_file")
    @classmethod
    def license_file_is_relative(cls, value: str) -> str:
        return _relative_posix(value)


class MindustryTask(BenchmarkTask):
    task_kind: Literal["repository-debugging"] = "repository-debugging"
    difficulty: Literal["easy", "medium", "hard"]
    build: BuildSpec
    upstream: UpstreamProvenance
    server_cases: tuple[str, ...] = Field(min_length=1)
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @property
    def starter_name(self) -> str:
        return STARTER_NAME

    @property
    def container_destination(self) -> str:
        return CONTAINER_DESTINATION

    @field_validator("server_cases")
    @classmethod
    def case_names_are_unique_and_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not name.strip() or name != name.strip() for name in value):
            raise ValueError("case names must be non-blank without surrounding whitespace")
        if len(set(value)) != len(value):
            raise ValueError("case names must be unique")
        return value

    @model_validator(mode="after")
    def task_rules(self) -> Self:
        prefix = f"{STARTER_NAME}/"
        if any(not value.startswith(prefix) for value in self.required_files):
            raise ValueError(f"required_files must be below {prefix}")
        if self.upstream.release_tag != RELEASE_TAG:
            raise ValueError(f"tasks must be based on the pinned {RELEASE_TAG} release")
        return self


class MindustryCatalog(BenchmarkCatalog):
    game: Literal["mindustry"]
    tasks: list[MindustryTask]

    @model_validator(mode="after")
    def catalog_identity(self) -> Self:
        if self.id != CATALOG_ID:
            raise ValueError("unsupported Mindustry catalog id")
        return self

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Mindustry catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[MindustryTask] = []
        for task in catalog.tasks:
            loaded.append(task.model_copy(update={"authored_prompt": _validate_task(root, task)}))
        return catalog.model_copy(update={"tasks": loaded})


def _below(root: Path, candidate: Path, label: str, task_id: str) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or not resolved.exists():
        raise ValueError(f"{label} is missing for {task_id}")
    return resolved


def task_manifest(task: MindustryTask) -> dict[str, object]:
    """The frozen verifier configuration written to tests/task.json."""
    return {
        "schemaVersion": 1,
        "taskId": task.id,
        "starter": STARTER_NAME,
        "build": {
            "tool": task.build.tool,
            "sourceRoots": list(task.build.source_roots),
            "extraSources": list(task.build.extra_sources),
            "javaRelease": task.build.java_release,
        },
        "serverCases": list(task.server_cases),
    }


def _validate_task(root: Path, task: MindustryTask) -> str:
    task_root = root / "private" / "harbor" / task.id
    exam = _below(root, root / "exams" / f"{task.id}.md", "public exam", task.id)
    starter = _below(root, task_root / "environment" / STARTER_NAME, "starter tree", task.id)
    if not starter.is_dir():
        raise ValueError(f"starter tree is not a directory for {task.id}")
    for source_root in task.build.source_roots:
        if not _below(root, starter / source_root, f"source root {source_root}", task.id).is_dir():
            raise ValueError(f"source root {source_root} is not a directory for {task.id}")
    for extra in task.build.extra_sources:
        _below(root, starter / extra, f"source {extra}", task.id)
    _below(root, starter / task.upstream.license_file, "upstream license file", task.id)
    for relative in task.required_files:
        _below(root, task_root / "environment" / relative, f"required file {relative}", task.id)
    tests = task_root / "tests"
    for name in ("Dockerfile", "test.sh", "verify.py", "task.json"):
        _below(root, tests / name, f"tests/{name}", task.id)
    _below(root, tests / SUITE_SOURCE, f"tests/{SUITE_SOURCE}", task.id)
    try:
        manifest = json.loads((tests / "task.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"tests/task.json is not valid JSON for {task.id}") from error
    if manifest != task_manifest(task):
        raise ValueError(f"tests/task.json drifted from the catalog for {task.id}")
    _below(root, task_root / "solution" / "solve.sh", "solution/solve.sh", task.id)
    after = _below(root, task_root / "solution" / "after", "solution/after", task.id)
    if not after.is_dir() or not any(path.is_file() for path in after.rglob("*")):
        raise ValueError(f"solution/after holds no reference files for {task.id}")
    instruction = _below(root, task_root / "instruction.md", "Harbor instruction", task.id)
    if _exam_body(exam) != _instruction_body(instruction):
        raise ValueError(f"public exam drifted from Harbor instruction: {task.id}")
    contracts = _below(root, task_root / "validation" / "case-contracts.tsv", "case contracts", task.id)
    with contracts.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if sorted(row.get("case", "") for row in rows) != sorted(task.server_cases):
        raise ValueError(f"case contracts do not match the frozen case set for {task.id}")
    roles = [row.get("role", "") for row in rows]
    if any(role not in CASE_ROLES for role in roles):
        raise ValueError(f"case contracts use an unknown role for {task.id}")
    if roles.count("sentinel") < 1 or roles.count("target") < 1 or roles.count("preserved") < 2:
        raise ValueError(f"case contracts need a sentinel, targets and two preserved cases: {task.id}")
    return exam.read_text(encoding="utf-8")


def _exam_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        _opening, _front, body = text.split("---", 2)
        return body.strip()
    return text.strip()


def _instruction_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(HARBOR_INSTRUCTION_HEADER):
        raise ValueError(f"Harbor instruction lacks the workspace header: {path.name}")
    return text[len(HARBOR_INSTRUCTION_HEADER) :].strip()
