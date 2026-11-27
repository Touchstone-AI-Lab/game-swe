from __future__ import annotations

import csv
import json
import re
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask, CatalogModel

from .container import (
    CONSTRUCT_RUNTIME_ID,
    CONTAINER_DESTINATION,
    HISTORY_RUNTIME_ID,
    RUNTIME_ID,
    STARTER_NAME,
    SYNTH_RUNTIME_ID,
)

CORE_CATALOG_ID = "rhenium-minecraft-v1"
# Header that materialize.py prepends to every Harbor instruction.md; the public
# exam body must equal the instruction after this header.
HARBOR_INSTRUCTION_HEADER = (
    "# Harbor workspace\n\n"
    "Complete this task in `/app/plugin`; the repository's build files, dependency "
    "declarations and upstream tests are frozen and restored by the verifier.\n\n"
)
SYNTH_CATALOG_ID = "minecraft-clean-room-synth"
# Repository tasks produced by rhenium-author's project-history mode.
HISTORY_CATALOG_ID = "rhenium-minecraft-history-v1"
# Construct tasks: the model writes a whole plugin into a frozen Maven skeleton.
CONSTRUCT_CATALOG_ID = "rhenium-minecraft-construct-v1"
# Header that the construct pack's materialize.py prepends to every Harbor instruction.md.
CONSTRUCT_INSTRUCTION_HEADER = (
    "# Harbor workspace\n\n"
    "Write this plugin in `/app/plugin`; the skeleton's `pom.xml` and anything under "
    "`src/test` are frozen and restored by the verifier.\n\n"
)
CATALOG_IDS = frozenset({CORE_CATALOG_ID, SYNTH_CATALOG_ID, HISTORY_CATALOG_ID, CONSTRUCT_CATALOG_ID})
CATALOG_RUNTIME_IDS = {
    CORE_CATALOG_ID: RUNTIME_ID,
    SYNTH_CATALOG_ID: SYNTH_RUNTIME_ID,
    HISTORY_CATALOG_ID: HISTORY_RUNTIME_ID,
    CONSTRUCT_CATALOG_ID: CONSTRUCT_RUNTIME_ID,
}
LICENSE_ALLOWLIST = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC")
DEFAULT_FROZEN_PATHS = (
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle",
    "gradlew",
    "gradlew.bat",
    "pom.xml",
    ".mvn",
    "mvnw",
    "mvnw.cmd",
    "src/test",
)
_PLUGIN_NAME_LINE = re.compile(r"^name:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?\s*$", re.MULTILINE)
# A name filled in by the build (Maven resource filtering, Gradle expand); the
# verifier then checks the name in the built jar instead.
_PLACEHOLDER_NAME_LINE = re.compile(r"^name:\s*['\"]?\$\{[A-Za-z0-9_.-]+\}['\"]?\s*$", re.MULTILINE)


def _relative_posix(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError("catalog paths must be normalized relative POSIX paths")
    return value


class BuildSpec(CatalogModel):
    """How the verifier builds and unit-tests a submission, offline."""

    tool: Literal["gradle", "maven", "javac"]
    wrapper: bool = True
    tool_version: str | None = None
    module: str | None = None
    assemble: str = "assemble"
    test: str | None = "test"
    artifact: str
    java_release: Literal[17, 21] = 21
    frozen_paths: tuple[str, ...] = DEFAULT_FROZEN_PATHS

    @field_validator("artifact")
    @classmethod
    def artifact_is_relative(cls, value: str) -> str:
        return _relative_posix(value)

    @field_validator("frozen_paths")
    @classmethod
    def frozen_paths_are_relative(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _relative_posix(item)
        if len(set(value)) != len(value):
            raise ValueError("frozen_paths must be unique")
        return value

    @model_validator(mode="after")
    def tool_specific_rules(self) -> Self:
        if self.tool == "javac":
            if self.test is not None or self.module is not None or self.tool_version is not None:
                raise ValueError("javac builds have no test task, module or tool version")
            if self.assemble != "":
                raise ValueError("javac builds take no assemble task")
        elif not self.wrapper and not self.tool_version:
            raise ValueError("a build without a committed wrapper must pin tool_version")
        return self


class UpstreamProvenance(CatalogModel):
    repository: str = Field(pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    fix_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    license_spdx: Literal["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"]
    license_file: str
    paper_api: str = Field(min_length=1)

    @field_validator("license_file")
    @classmethod
    def license_file_is_relative(cls, value: str) -> str:
        return _relative_posix(value)


class MinecraftTask(BenchmarkTask):
    task_kind: Literal["repository-debugging", "construct"] = "repository-debugging"
    difficulty: Literal["easy", "medium", "hard"]
    plugin_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    build: BuildSpec
    upstream: UpstreamProvenance | None = None
    unit_cases: tuple[str, ...] = ()
    hidden_unit_overlay: bool = False
    server_cases: tuple[str, ...] = Field(min_length=1)
    clean_room_synthetic: bool = False
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @property
    def starter_name(self) -> str:
        return STARTER_NAME

    @property
    def container_destination(self) -> str:
        return CONTAINER_DESTINATION

    @property
    def is_construct(self) -> bool:
        """Whether the plugin is written from a skeleton rather than repaired."""
        return self.task_kind == "construct"

    @field_validator("unit_cases", "server_cases")
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
        if set(self.unit_cases) & set(self.server_cases):
            raise ValueError("unit_cases and server_cases must be disjoint")
        if (self.build.test is None) != (not self.unit_cases):
            raise ValueError("unit_cases must be declared exactly when the build has a test task")
        if self.is_construct:
            if self.upstream is not None or self.clean_room_synthetic or self.build.tool == "javac":
                raise ValueError(
                    "construct tasks have no upstream and build with the skeleton's frozen build file"
                )
        elif self.clean_room_synthetic:
            if self.build.tool != "javac" or self.upstream is not None:
                raise ValueError("synthetic tasks use the trusted javac build and have no upstream")
        elif self.upstream is None or self.build.tool == "javac":
            raise ValueError("repository tasks declare their upstream and use its own build tool")
        if self.hidden_unit_overlay and not self.unit_cases:
            raise ValueError("a hidden unit overlay needs unit_cases")
        return self


class MinecraftCatalog(BenchmarkCatalog):
    game: Literal["minecraft"]
    tasks: list[MinecraftTask]

    @model_validator(mode="after")
    def catalog_identity(self) -> Self:
        if self.id not in CATALOG_IDS:
            raise ValueError("unsupported Minecraft catalog id")
        synthetic = self.id == SYNTH_CATALOG_ID
        if any(task.clean_room_synthetic != synthetic for task in self.tasks):
            raise ValueError("every task of a Minecraft catalog shares its clean-room status")
        construct = self.id == CONSTRUCT_CATALOG_ID
        if any(task.is_construct != construct for task in self.tasks):
            raise ValueError("construct tasks belong to the construct catalog and only there")
        return self

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Minecraft catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[MinecraftTask] = []
        for task in catalog.tasks:
            loaded.append(task.model_copy(update={"authored_prompt": _validate_task(root, task)}))
        return catalog.model_copy(update={"tasks": loaded})


def _below(root: Path, candidate: Path, label: str, task_id: str) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or not resolved.exists():
        raise ValueError(f"{label} is missing for {task_id}")
    return resolved


def task_manifest(task: MinecraftTask) -> dict[str, object]:
    """The frozen verifier configuration written to tests/task.json."""
    return {
        "schemaVersion": 1,
        "taskId": task.id,
        "pluginName": task.plugin_name,
        "build": {
            "tool": task.build.tool,
            "wrapper": task.build.wrapper,
            "toolVersion": task.build.tool_version,
            "module": task.build.module,
            "assemble": task.build.assemble,
            "test": task.build.test,
            "artifact": task.build.artifact,
            "javaRelease": task.build.java_release,
            "frozenPaths": list(task.build.frozen_paths),
        },
        "unitCases": list(task.unit_cases),
        "serverCases": list(task.server_cases),
        "hiddenUnitOverlay": task.hidden_unit_overlay,
    }


def _validate_task(root: Path, task: MinecraftTask) -> str:
    task_root = root / "private" / "harbor" / task.id
    exam = _below(root, root / "exams" / f"{task.id}.md", "public exam", task.id)
    starter = _below(root, task_root / "environment" / STARTER_NAME, "starter tree", task.id)
    if not starter.is_dir():
        raise ValueError(f"starter tree is not a directory for {task.id}")
    metadata = plugin_metadata_file(starter, task.build.module)
    if metadata is None:
        raise ValueError(f"starter lacks src/main/resources/plugin.yml for {task.id}")
    metadata_text = metadata.read_text(encoding="utf-8", errors="replace")
    match = _PLUGIN_NAME_LINE.search(metadata_text)
    templated = match is None and _PLACEHOLDER_NAME_LINE.search(metadata_text) is not None
    if not templated and (match is None or match.group(1) != task.plugin_name):
        raise ValueError(f"plugin.yml name does not match plugin_name for {task.id}")
    for relative in task.required_files:
        _below(root, task_root / "environment" / relative, f"required file {relative}", task.id)
    tests = task_root / "tests"
    for name in ("Dockerfile", "test.sh", "verify.py", "task.json"):
        _below(root, tests / name, f"tests/{name}", task.id)
    suite_dir = tests / "suite"
    single_suite = tests / "TaskSuite.java"
    has_suite = suite_dir.is_dir() and any(suite_dir.rglob("*.java"))
    if not has_suite and not single_suite.is_file():
        raise ValueError(f"tests lack a grader suite for {task.id}")
    if task.build.tool != "javac":
        _below(root, tests / "starter", "tests/starter", task.id)
    if task.hidden_unit_overlay:
        _below(root, tests / "unit", "tests/unit", task.id)
    manifest_path = tests / "task.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"tests/task.json is not valid JSON for {task.id}") from error
    if manifest != task_manifest(task):
        raise ValueError(f"tests/task.json drifted from the catalog for {task.id}")
    _below(root, task_root / "solution" / "solve.sh", "solution/solve.sh", task.id)
    _below(root, task_root / "solution" / "after", "solution/after", task.id)
    if task.upstream is not None:
        _below(root, starter / task.upstream.license_file, "upstream license file", task.id)
    if not task.clean_room_synthetic:
        instruction = _below(root, task_root / "instruction.md", "Harbor instruction", task.id)
        header = CONSTRUCT_INSTRUCTION_HEADER if task.is_construct else HARBOR_INSTRUCTION_HEADER
        if _exam_body(exam) != _instruction_body(instruction, header):
            raise ValueError(f"public exam drifted from Harbor instruction: {task.id}")
        contracts = _below(root, task_root / "validation" / "case-contracts.tsv", "case contracts", task.id)
        with contracts.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        names = [row.get("case", "") for row in rows]
        expected = [*task.unit_cases, *task.server_cases]
        if sorted(names) != sorted(expected):
            raise ValueError(f"case contracts do not match the frozen case sets for {task.id}")
    return exam.read_text(encoding="utf-8")


def plugin_metadata_file(starter: Path, module: str | None = None) -> Path | None:
    """The starter's plugin.yml: at the root, in the declared module, or in one sub-module.

    Multi-module repositories keep the Paper plugin in a sub-project (for example
    ``spigot/``); the root is tried first, then ``module``, then every direct
    sub-directory, and the first match wins.
    """
    roots = [starter]
    if module:
        roots.append(starter / module)
    roots.extend(sorted(p for p in starter.iterdir() if p.is_dir() and not p.name.startswith(".")))
    for candidate_root in roots:
        for name in ("plugin.yml", "paper-plugin.yml"):
            candidate = candidate_root / "src" / "main" / "resources" / name
            if candidate.is_file():
                return candidate
    return None


def _exam_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        _opening, _front, body = text.split("---", 2)
        return body.strip()
    return text.strip()


def _instruction_body(path: Path, header: str = HARBOR_INSTRUCTION_HEADER) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(header):
        raise ValueError(f"Harbor instruction lacks the workspace header: {path.name}")
    return text[len(header) :].strip()


def expected_case_sets(task: MinecraftTask) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return task.unit_cases, task.server_cases
