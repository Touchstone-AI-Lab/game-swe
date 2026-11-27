from __future__ import annotations

import json
import shutil
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

from .catalog import CONTAINER_DESTINATION, STARTER_NAME, DstCatalog, DstTask
from .construct_catalog import DstConstructCatalog, DstConstructTask
from .container import CONSTRUCT_RUNTIME_ID, DST_BUILD_ID, RUNTIME_ID
from .evaluator import DstEvaluator
from .runtime import DstRuntimeConfig
from .runtime_builder import DstRuntimeBuilder


class DstBenchmarkPlugin(BenchmarkPlugin):
    """Serves the repair pack (catalog ``dst-core``) and the construct pack.

    Every hook dispatches on the task's catalog model: a ``DstConstructTask``
    keeps the construct behavior it was validated with (an empty from-scratch
    workspace, the generated task prompt and the authored exam), and a
    ``DstTask`` gets the repair behavior.
    """

    descriptor = PluginDescriptor(
        id="dst",
        game_id="dst",
        name="Don't Starve Together",
        version="0.6.0",
        capabilities=(
            "lua",
            "docker",
            "headless-server",
            "repository-debugging",
            "static-analysis",
            "sandbox",
        ),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return DstCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return DstEvaluator(DstRuntimeConfig.load(context))

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        if spec.id == RUNTIME_ID:
            return DstRuntimeBuilder(context, DstCatalog.load(context.pack_root))
        if spec.id == CONSTRUCT_RUNTIME_ID:
            return DstRuntimeBuilder(context, DstConstructCatalog.load(context.pack_root))
        return None

    @staticmethod
    def _task(task: BenchmarkTask) -> DstTask:
        if not isinstance(task, DstTask):
            raise TypeError("DST plugin received a non-DST task")
        return task

    @staticmethod
    def _public_instruction(text: str) -> str:
        return text.replace(CONTAINER_DESTINATION, STARTER_NAME).replace(
            "anything under `/tests`", "the private verifier"
        )

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        if isinstance(task, DstConstructTask):
            if task.clean_room_synthetic:
                return task.authored_prompt.strip()
            prompt = super().task_prompt(task, language)
            if language == "zh":
                return prompt.replace("游戏 API 使用合同", "原版 API 使用合同")
            return prompt.replace("Game API usage contract", "Base-game API usage contract")
        # The authored exam is English. Chinese task metadata stays available in
        # the list and report APIs, while evaluation uses the validated contract.
        del language
        return self._public_instruction(self._task(task).authored_prompt).strip()

    def materialize_starter(
        self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext
    ) -> None:
        if isinstance(task, DstConstructTask):
            self._materialize_construct_starter(task, workspace, context)
            return
        dst_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        source = context.pack_root / "private" / "harbor" / dst_task.id / "environment" / STARTER_NAME
        shutil.copytree(source, workspace / STARTER_NAME, symlinks=False)
        (workspace / "task.json").write_text(
            json.dumps(
                {
                    "difficulty": task.difficulty,
                    "submission": ".",
                    "fromScratch": False,
                    "language": "lua",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt = self._public_instruction(dst_task.authored_prompt)
        (workspace / "TASK.md").write_text(prompt.rstrip() + "\n", encoding="utf-8")

    def _materialize_construct_starter(
        self, task: DstConstructTask, workspace: Path, context: BenchmarkContext
    ) -> None:
        if not task.clean_room_synthetic:
            super().materialize_starter(task, workspace, context)
            return
        if workspace.exists():
            shutil.rmtree(workspace)
        source = context.pack_root / "private" / "harbor" / task.id / "environment" / "mod"
        shutil.copytree(source, workspace)
        shutil.copy2(context.pack_root / "LICENSE", workspace / "LICENSE")
        (workspace / "task.json").write_text(
            '{"difficulty":"hard","submission":".","fromScratch":false,"language":"lua"}\n',
            encoding="utf-8",
        )
        (workspace / "TASK.md").write_text(task.authored_prompt.rstrip() + "\n", encoding="utf-8")

    def _materialize_construct_attempt(
        self, task: DstConstructTask, destination: Path, context: BenchmarkContext
    ) -> None:
        exams_root = (context.pack_root / "exams").resolve()
        exam = (exams_root / f"{task.id}.md").resolve()
        if not exam.is_relative_to(exams_root) or not exam.is_file():
            super().materialize_attempt(task, destination, context)
            return
        shutil.copy2(exam, destination / "EXAM.md")
        shutil.copy2(context.project_root / "AGENTS.md", destination / "AGENTS.md")
        shutil.copy2(context.project_root / "CLAUDE.md", destination / "CLAUDE.md")

    def materialize_attempt(
        self, task: BenchmarkTask, destination: Path, context: BenchmarkContext
    ) -> None:
        if isinstance(task, DstConstructTask):
            self._materialize_construct_attempt(task, destination, context)
            return
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        (destination / "AGENTS.md").write_text(
            "# Don't Starve Together benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark "
            "repository, plugin, private tests, reference solution, validation records, "
            "prior runs, or state database. Repair every reported problem in the supplied "
            f"mod tree under `{STARTER_NAME}/` as described in EXAM.md. Do not use external "
            "implementations or network lookup. In strict mode, run the approved scorer "
            "exactly once after implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        if isinstance(task, DstConstructTask):
            return super().public_task(task)
        dst_task = self._task(task)
        return {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": dst_task.task_kind,
            "sourceMod": dst_task.source_mod,
            "sourceRepository": dst_task.upstream.repository,
            "sourceCommit": dst_task.upstream.base_commit,
            "licenseSpdx": dst_task.upstream.license_spdx,
            "submissionLanguage": "Lua 5.1",
            "gameBuild": DST_BUILD_ID,
            "serverCases": len(dst_task.server_cases),
        }

    def sanitize_anonymous_result(self, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        sanitized = dict(value)
        sanitized.pop("runtime_log", None)
        sanitized.pop("server_log", None)
        runtime = sanitized.get("runtime")
        if isinstance(runtime, dict):
            sanitized["runtime"] = {
                key: item for key, item in runtime.items() if key not in {"caseOutcomes", "message"}
            }
        checks = sanitized.get("checks")
        if isinstance(checks, list):
            sanitized["checks"] = [
                {key: item for key, item in check.items() if key != "details"}
                if isinstance(check, dict)
                else check
                for check in checks
            ]
        return sanitized

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        if isinstance(task, DstConstructTask):
            source_boundary = (
                "The supplied mod is clean-room synthetic and has no upstream implementation. "
                if task.clean_room_synthetic
                else "The workspace contains only the public task contract and an empty starter; "
                "implement the requested mod from scratch. "
            )
            return (
                "You are the model under test in a Don't Starve Together engineering benchmark. "
                f"{source_boundary}Keep plain-Lua state machines independent of DST "
                "globals, keep authority on the master simulation, and use the documented base-game "
                "API signatures exactly. You cannot see private Lua or dedicated-server assertions. "
                "Before submitting, inspect every required file and run "
                "`python -m rhenium_dst.public_check .` for public syntax diagnostics."
            )
        self._task(task)
        return (
            "You are the model under test in a Don't Starve Together mod repository-repair "
            "benchmark. The workspace contains a real open-source server mod at a fixed "
            "commit, carrying defects reported only as operator or player symptoms. Work "
            f"only in the supplied Lua workspace under `{STARTER_NAME}/` and resolve every "
            "reported problem at its cause. Do not inspect or search for upstream fixes, "
            "benchmark internals, private tests, reference solutions, validation records, "
            "or prior results. The private evaluator runs the mod on the pinned Don't "
            "Starve Together dedicated server without network access. Before submitting, "
            "you may run `python -m rhenium_dst.public_check mod` for public Lua syntax "
            "diagnostics."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "dedicated-server runtime status, and files changed"
        )
