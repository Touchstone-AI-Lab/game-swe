from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask
from rhenium.core.plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    PluginDescriptor,
)
from rhenium.core.runtime import RuntimeBuilder, RuntimeSpec

from .catalog import RimWorldCatalog, RimWorldTask
from .evaluator import RUNTIME_ID, RimWorldEvaluator
from .runtime_builder import RimWorldRuntimeBuilder
from .safe_files import (
    ensure_directory_nofollow,
    open_directory_nofollow,
    secure_copy_tree,
    secure_inventory,
    secure_read_bytes,
    write_owner_file,
)


class RimWorldBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="rimworld",
        game_id="rimworld",
        name="RimWorld",
        version="0.6.0",
        capabilities=("csharp", "harmony", "docker", "real-game"),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return RimWorldCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return RimWorldEvaluator(context, RimWorldCatalog.load(context.pack_root))

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        if spec.id != RUNTIME_ID:
            return None
        return RimWorldRuntimeBuilder(context, RimWorldCatalog.load(context.pack_root))

    @staticmethod
    def _rimworld_task(task: BenchmarkTask) -> RimWorldTask:
        if not isinstance(task, RimWorldTask):
            raise TypeError("RimWorld plugin received a non-RimWorld task")
        return task

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        rimworld_task = self._rimworld_task(task)
        del language
        return rimworld_task.authored_prompt.strip()

    def materialize_starter(
        self,
        task: BenchmarkTask,
        workspace: Path,
        context: BenchmarkContext,
    ) -> None:
        rimworld_task = self._rimworld_task(task)
        expected = Path(
            os.path.abspath(
                os.fspath(context.state_dir / "workspaces" / rimworld_task.id)
            )
        )
        requested = Path(os.path.abspath(os.fspath(workspace)))
        if requested != expected:
            raise ValueError("RimWorld starter target is not the task-owned workspace")
        ensure_directory_nofollow(expected.parent)
        staging = Path(tempfile.mkdtemp(prefix=f".{rimworld_task.id}-", dir=expected.parent))
        os.chmod(staging, 0o700)
        try:
            self._populate_public_tree(rimworld_task, staging, context, exam_name="TASK.md")
            if expected.exists():
                secure_inventory(expected)
                quarantine = expected.parent / f".{rimworld_task.id}-old-{uuid.uuid4().hex}"
                os.replace(expected, quarantine)
                try:
                    secure_inventory(quarantine)
                    shutil.rmtree(quarantine)
                except BaseException:
                    if not expected.exists():
                        os.replace(quarantine, expected)
                    raise
            os.replace(staging, expected)
        finally:
            if staging.exists():
                secure_inventory(staging)
                shutil.rmtree(staging)

    def _populate_public_tree(
        self,
        task: RimWorldTask,
        destination: Path,
        context: BenchmarkContext,
        *,
        exam_name: str,
    ) -> None:
        task_root = context.pack_root / "private" / "harbor" / task.id
        source = task_root / "environment" / task.starter_name
        secure_copy_tree(source, destination / task.starter_name)
        marker = {
            "difficulty": task.difficulty,
            "submission": ".",
            "fromScratch": False,
            "language": "csharp",
        }
        write_owner_file(
            destination / "task.json",
            (json.dumps(marker, indent=2, ensure_ascii=False) + "\n").encode(),
        )
        exam = secure_read_bytes(
            context.pack_root, f"exams/{task.id}.md", maximum=2_000_000
        ).decode("utf-8")
        write_owner_file(destination / exam_name, (exam.rstrip() + "\n").encode())

    def materialize_attempt(
        self,
        task: BenchmarkTask,
        destination: Path,
        context: BenchmarkContext,
    ) -> None:
        rimworld_task = self._rimworld_task(task)
        descriptor = open_directory_nofollow(destination)
        os.close(descriptor)
        if secure_inventory(destination):
            raise ValueError("RimWorld attempt directory must be empty")
        self._populate_public_tree(rimworld_task, destination, context, exam_name="EXAM.md")
        write_owner_file(
            destination / "AGENTS.md",
            (
            b"# RimWorld benchmark guidance\n\n"
            b"Work only inside this attempt directory. Do not inspect the benchmark "
            b"repository, plugin, private verifier, reference solution, prior runs or "
            b"state database. Implement the public contract in EXAM.md using the supplied "
            b"C# source. Do not search for or retrieve upstream fixes. Do not add game "
            b"assemblies, binaries, generated build output or credentials. In strict mode, "
            b"run the approved scorer exactly once after implementation and do not edit "
            b"the submission afterward.\n"
            ),
        )
        write_owner_file(destination / "CLAUDE.md", b"@AGENTS.md\n")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        rimworld_task = self._rimworld_task(task)
        return {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": rimworld_task.task_kind,
            "sourceMod": rimworld_task.source_mod,
            "sourceCommit": rimworld_task.source_commit,
            "sourceLicense": rimworld_task.source_license,
            "gameVersion": rimworld_task.game_version,
            "unityVersion": rimworld_task.unity_version,
            "targetFramework": rimworld_task.target_framework,
            "harmonyVersion": rimworld_task.harmony_version,
            "submissionLanguage": "C#/.NET",
        }

    def sanitize_anonymous_result(self, value: Any) -> Any:
        """Drop the operator-only per-case outcomes from an anonymous result.

        The Hub passes either a bare evaluator result or a run record that nests it,
        so every ``caseOutcomes`` key is removed wherever it occurs.
        """
        if isinstance(value, dict):
            return {
                key: self.sanitize_anonymous_result(item)
                for key, item in value.items()
                if key != "caseOutcomes"
            }
        if isinstance(value, list):
            return [self.sanitize_anonymous_result(item) for item in value]
        return value

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        self._rimworld_task(task)
        return (
            "You are the model under test in a RimWorld C# mod debugging benchmark. "
            "Work only in the supplied attempt and implement the authored contract. "
            "Do not inspect or search for upstream fixes, benchmark internals, private "
            "tests, reference solutions or prior results. The private evaluator will "
            "compile the source and run assertions in the pinned real game without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, "
            "pinned RimWorld runtime status, whether every real-game assertion ran, and files changed"
        )
