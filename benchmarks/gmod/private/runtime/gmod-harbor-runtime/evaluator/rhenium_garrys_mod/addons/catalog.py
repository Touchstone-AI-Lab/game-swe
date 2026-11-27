from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask

from .contracts import (
    GmodEvaluationContract,
    GmodPackRuntimeContract,
    GmodPublicExamContract,
    GmodServerSuiteContract,
    GmodSourceContract,
    GmodSourceRecord,
    GmodTaskRuntimeSpec,
    resolve_runtime_spec,
)
from .public_assets import path_uses_link_or_junction, validate_catalog_exams


class GmodTask(BenchmarkTask):
    difficulty: Literal["medium", "medium-hard", "hard", "expert"]
    task_version: str
    core_module: str
    server_module: str
    evaluation: GmodEvaluationContract
    server_runtime: GmodServerSuiteContract
    source: GmodSourceContract
    public_exam: GmodPublicExamContract
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @field_validator("core_module", "server_module")
    @classmethod
    def private_paths_are_safe(cls, value: str) -> str:
        path = PurePosixPath(value)
        if "\\" in value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
            raise ValueError("GMod catalog paths must be normalized relative POSIX paths")
        return value

    @model_validator(mode="after")
    def submitted_modules_are_required(self) -> Self:
        if self.core_module not in self.required_files or self.server_module not in self.required_files:
            raise ValueError("core_module and server_module must be required files")
        prefix = f"private/tasks/{self.id}/"
        for relative in self.private_paths():
            if not relative.startswith(prefix):
                raise ValueError(f"private assets for {self.id} must live below {prefix}")
        if self.server_runtime.task_version != self.task_version:
            raise ValueError("server runtime task_version must match the task version")
        return self

    def private_paths(self) -> tuple[str, ...]:
        return (*self.evaluation.private_paths(), *self.server_runtime.private_paths())

    def runtime_spec(self, dataset_root: Path) -> GmodTaskRuntimeSpec:
        return resolve_runtime_spec(
            dataset_root,
            self.id,
            self.task_version,
            self.server_runtime,
        )

    def private_exam_markers(self) -> tuple[str, ...]:
        runtime = self.server_runtime
        return (
            *self.private_paths(),
            *self.evaluation.hidden_cases,
            *self.evaluation.integration_cases,
            *self.evaluation.lifecycle_cases,
            runtime.suite_id,
            runtime.runtime_namespace,
            runtime.submission_addon_name,
            runtime.private_suite_addon_name,
        )


class GmodCatalog(BenchmarkCatalog):
    game: Literal["garrys-mod"]
    runtime: GmodPackRuntimeContract
    contract_traceability_required: bool = False
    tasks: list[GmodTask]

    @model_validator(mode="after")
    def runtime_identities_are_unique(self) -> Self:
        suite_ids = [task.server_runtime.suite_id for task in self.tasks]
        namespaces = [task.server_runtime.runtime_namespace for task in self.tasks]
        submission_addons = [task.server_runtime.submission_addon_name for task in self.tasks]
        private_addons = [task.server_runtime.private_suite_addon_name for task in self.tasks]
        if len(set(suite_ids)) != len(suite_ids):
            raise ValueError("GMod server suite IDs must be unique across tasks")
        if len(set(namespaces)) != len(namespaces):
            raise ValueError("GMod runtime namespaces must be unique across tasks")
        if len(set(submission_addons)) != len(submission_addons):
            raise ValueError("GMod submission addon names must be unique across tasks")
        if len(set(private_addons)) != len(private_addons):
            raise ValueError("GMod private suite addon names must be unique across tasks")
        exam_paths = [task.public_exam.path for task in self.tasks]
        if len(set(exam_paths)) != len(exam_paths):
            raise ValueError("each GMod task must own a different public exam")
        for task in self.tasks:
            if task.public_exam.path != f"exams/{task.id}.md":
                raise ValueError(f"public exam path is not canonical for {task.id}")
            if len(task.acceptance.en) != len(task.acceptance.zh):
                raise ValueError(f"localized acceptance lists drifted for {task.id}")
            if len(task.public_exam.acceptance_evidence) != len(task.acceptance.en):
                raise ValueError(f"acceptance evidence is not one-to-one for {task.id}")
        return self

    @classmethod
    def load(cls, dataset_dir: Path | str, catalog_path: str = "catalog.json") -> Self:
        root = Path(dataset_dir).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"GMod catalog is missing: {catalog_path}")
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        for task in catalog.tasks:
            for relative in task.private_paths():
                if path_uses_link_or_junction(root, PurePosixPath(relative)):
                    raise ValueError(f"private asset must not use links for {task.id}: {relative}")
                private = (root / relative).resolve()
                if not private.is_relative_to(root) or not private.is_file():
                    raise ValueError(f"private asset is missing for {task.id}: {relative}")
            manifest = (root / task.server_runtime.addon_manifest).resolve()
            try:
                addon = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise ValueError(f"private suite addon manifest is invalid for {task.id}") from error
            if not isinstance(addon, dict):
                raise ValueError(f"private suite addon manifest must be an object for {task.id}")
            source_relative = PurePosixPath(task.source.path)
            if path_uses_link_or_junction(root, source_relative):
                raise ValueError(f"source record must not use links for {task.id}")
            source_path = (root / Path(*source_relative.parts)).resolve()
            if not source_path.is_relative_to(root) or not source_path.is_file():
                raise ValueError(f"source record is missing for {task.id}")
            source_raw = source_path.read_bytes()
            if hashlib.sha256(source_raw).hexdigest() != task.source.sha256:
                raise ValueError(f"source record digest drifted for {task.id}")
            try:
                source = GmodSourceRecord.model_validate_json(source_raw)
            except (UnicodeError, ValueError) as error:
                raise ValueError(f"source record is invalid for {task.id}") from error
            if source.task_id != task.id or source.task_version != task.task_version:
                raise ValueError(f"source record identity drifted for {task.id}")
            if catalog.contract_traceability_required:
                trace_relative = PurePosixPath("private") / "tasks" / task.id / "contract-traceability.json"
                if path_uses_link_or_junction(root, trace_relative):
                    raise ValueError(f"contract traceability must not use links for {task.id}")
                traceability = (root / Path(*trace_relative.parts)).resolve()
                if not traceability.is_relative_to(root) or not traceability.is_file():
                    raise ValueError(f"contract traceability is missing for {task.id}")
                try:
                    trace = json.loads(traceability.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as error:
                    raise ValueError(f"contract traceability is invalid for {task.id}") from error
                if (
                    not isinstance(trace, dict)
                    or trace.get("taskId") != task.id
                    or trace.get("taskVersion") != task.task_version
                ):
                    raise ValueError(f"contract traceability identity drifted for {task.id}")
        from .traceability import validate_gmod_private_contracts

        public_assets = validate_catalog_exams(
            catalog,
            pack_root=root,
            private_markers={task.id: task.private_exam_markers() for task in catalog.tasks},
        )
        if catalog.contract_traceability_required:
            validate_gmod_private_contracts(
                catalog,
                pack_root=root,
                public_assets=public_assets,
            )
        tasks = [
            task.model_copy(update={"authored_prompt": public_assets[task.id].text})
            for task in catalog.tasks
        ]
        return catalog.model_copy(update={"tasks": tasks})
