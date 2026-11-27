from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask

from .assertions import AssertionManifest, load_assertion_manifest
from .safe_files import normalized_relative, secure_inventory, secure_read_bytes

_FIXTURE_METHOD = re.compile(
    r"private\s+static\s+CaseObservation\s+([A-Z][A-Za-z0-9]*)\s*\("
)


def _unique_catalog_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate RimWorld catalog key: {key}")
        result[key] = value
    return result


def _reject_catalog_constant(token: str) -> None:
    raise ValueError(f"non-finite RimWorld catalog value: {token}")


class RimWorldTask(BenchmarkTask):
    task_kind: Literal["debugging"]
    source_mod: str = Field(min_length=1, max_length=160)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_target_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_license: Literal["MIT"]
    game_version: Literal["1.6.4871"]
    unity_version: Literal["2022.3.35f1"]
    target_framework: Literal["net472"]
    harmony_version: Literal["2.4.2"]
    starter_root: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    package_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    assembly_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9._-]*$")
    mod_metadata_path: str
    runtime_data_files: list[str] = Field(default_factory=list, max_length=64)
    private_protocol: Literal[
        "rhenium-rimworld-private-v2", "rhenium-rimworld-private-v3"
    ]
    expected_assertions: int = Field(ge=1, le=512)
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @property
    def starter_name(self) -> str:
        return self.starter_root

    @model_validator(mode="after")
    def required_files_are_safe(self) -> Self:
        try:
            metadata_path = normalized_relative(self.mod_metadata_path)
        except ValueError as error:
            raise ValueError("mod_metadata_path must be normalized and relative") from error
        expected_metadata = f"tests/ModMetadata/{self.starter_root}/About.xml"
        if metadata_path.as_posix() != expected_metadata:
            raise ValueError(
                f"mod_metadata_path must be the task-owned path {expected_metadata}"
            )
        runtime_prefix = f"tests/ModMetadata/{self.starter_root}/Defs/"
        if len(self.runtime_data_files) != len(set(self.runtime_data_files)):
            raise ValueError("runtime_data_files must be unique")
        for raw in self.runtime_data_files:
            path = normalized_relative(raw)
            if not raw.startswith(runtime_prefix) or path.suffix != ".xml":
                raise ValueError("runtime_data_files must be task-owned definition XML")
        prefix = f"{self.starter_name}/"
        seen: set[str] = set()
        for raw in self.required_files:
            path = PurePosixPath(raw)
            if (
                not raw.startswith(prefix)
                or path.is_absolute()
                or ".." in path.parts
                or raw != path.as_posix()
                or raw in seen
            ):
                raise ValueError(f"required_files must be unique normalized paths below {prefix}")
            seen.add(raw)
        return self


class RimWorldCatalog(BenchmarkCatalog):
    game: Literal["rimworld"]
    tasks: list[RimWorldTask]

    @classmethod
    def load(cls, pack_root: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(pack_root)
        try:
            normalized_relative(catalog_path)
        except ValueError as error:
            raise ValueError("RimWorld catalog path must be normalized and relative") from error
        inventory = {
            entry.relative: entry
            for entry in secure_inventory(
                root, maximum_entries=20_000, maximum_bytes=200_000_000
            )
        }
        catalog_entry = inventory.get(catalog_path)
        if catalog_entry is None or catalog_entry.is_dir:
            raise ValueError(f"RimWorld catalog is missing: {catalog_path}")
        try:
            catalog_raw = secure_read_bytes(root, catalog_path, maximum=2_000_000)
            catalog_value = json.loads(
                catalog_raw.decode("utf-8", errors="strict"),
                object_pairs_hook=_unique_catalog_object,
                parse_constant=_reject_catalog_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("RimWorld catalog is malformed") from error
        if not isinstance(catalog_value, dict):
            raise ValueError("RimWorld catalog must be an object")
        catalog = cls.model_validate(catalog_value)
        loaded: list[RimWorldTask] = []
        for task in catalog.tasks:
            task_relative = f"private/harbor/{task.id}"
            required: dict[str, tuple[str, bool]] = {
                "starter": (f"{task_relative}/environment/{task.starter_name}", True),
                "exam": (f"exams/{task.id}.md", False),
                "verifier": (f"{task_relative}/tests/test.sh", False),
                "harness": (f"{task_relative}/tests/Harness/Verifier.cs", False),
                "assertions": (f"{task_relative}/tests/assertions.json", False),
                "Dockerfile": (f"{task_relative}/environment/Dockerfile", False),
                "reference": (f"{task_relative}/solution/after", True),
                "provenance": (f"{task_relative}/validation/provenance.md", False),
                "license": (f"{task_relative}/environment/{task.starter_name}/LICENSE", False),
            }
            for relative in task.runtime_data_files:
                required[f"runtime definition {relative}"] = (f"{task_relative}/{relative}", False)
            for label, (relative_path, is_dir) in required.items():
                entry = inventory.get(relative_path)
                if entry is None or entry.is_dir is not is_dir:
                    raise ValueError(f"{label} is missing for {task.id}")
            harness_relative = required["harness"][0]
            text = secure_read_bytes(root, harness_relative, maximum=2_000_000).decode("utf-8")
            assertions = load_assertion_manifest(root, task.id)
            fixtures = _FIXTURE_METHOD.findall(text)
            if (
                assertions.task_key != f"rimworld/core/{task.id}"
                or assertions.protocol != task.private_protocol
                or len(assertions.cases) != task.expected_assertions
                or len(fixtures) != len(set(fixtures))
                or not {case.fixture for case in assertions.cases}.issubset(set(fixtures))
            ):
                raise ValueError(f"private assertion fixture declaration is invalid for {task.id}")
            for relative_required in task.required_files:
                relative_source = PurePosixPath(relative_required).relative_to(task.starter_name)
                candidate = f"{required['starter'][0]}/{relative_source.as_posix()}"
                entry = inventory.get(candidate)
                if entry is None or entry.is_dir:
                    raise ValueError(f"required source file is missing for {task.id}")
            loaded.append(
                task.model_copy(
                    update={
                        "authored_prompt": secure_read_bytes(
                            root, required["exam"][0], maximum=2_000_000
                        ).decode("utf-8")
                    }
                )
            )
        return catalog.model_copy(update={"tasks": loaded})


def expected_case_names(pack_root: Path, task: RimWorldTask) -> tuple[str, ...]:
    return assertion_manifest(pack_root, task).case_names


def assertion_manifest(pack_root: Path, task: RimWorldTask) -> AssertionManifest:
    manifest = load_assertion_manifest(pack_root, task.id)
    if (
        manifest.task_key != f"rimworld/core/{task.id}"
        or manifest.protocol != task.private_protocol
        or len(manifest.cases) != task.expected_assertions
    ):
        raise ValueError("private assertion manifest does not match the catalog task")
    return manifest
