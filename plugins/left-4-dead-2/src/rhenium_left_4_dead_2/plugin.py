from __future__ import annotations

import json
import shutil
from pathlib import Path

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask
from rhenium.core.plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    PluginDescriptor,
)
from rhenium.core.runtime import RuntimeBuilder, RuntimeSpec

from .catalog import Left4Dead2Catalog, Left4Dead2Task
from .evaluator import RUNTIME_ID, Left4Dead2Evaluator
from .runtime_builder import Left4Dead2RuntimeBuilder


class Left4Dead2BenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="left-4-dead-2",
        game_id="left-4-dead-2",
        name="Left 4 Dead 2",
        version="0.6.0",
        capabilities=("sourcepawn", "squirrel", "docker", "headless-server"),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return Left4Dead2Catalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return Left4Dead2Evaluator(context, Left4Dead2Catalog.load(context.pack_root))

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        if spec.id != RUNTIME_ID:
            return None
        return Left4Dead2RuntimeBuilder(context, Left4Dead2Catalog.load(context.pack_root))

    @staticmethod
    def _task(task: BenchmarkTask) -> Left4Dead2Task:
        if not isinstance(task, Left4Dead2Task):
            raise TypeError("Left 4 Dead 2 plugin received a non-L4D2 task")
        return task

    @staticmethod
    def _public_instruction(task: Left4Dead2Task, text: str) -> str:
        return text.replace(task.container_destination, task.starter_name).replace(
            "anything under `/tests`", "the private verifier"
        )

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        del language
        l4d2_task = self._task(task)
        return self._public_instruction(l4d2_task, l4d2_task.authored_prompt).strip()

    def materialize_starter(
        self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext
    ) -> None:
        l4d2_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / l4d2_task.id
        shutil.copytree(
            task_root / "environment" / l4d2_task.starter_name,
            workspace / l4d2_task.starter_name,
        )
        (workspace / "task.json").write_text(
            json.dumps(
                {
                    "difficulty": task.difficulty,
                    "submission": ".",
                    "fromScratch": False,
                    "language": l4d2_task.submission_language.lower(),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt = self._public_instruction(l4d2_task, l4d2_task.authored_prompt)
        (workspace / "TASK.md").write_text(prompt.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(
        self, task: BenchmarkTask, destination: Path, context: BenchmarkContext
    ) -> None:
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        (destination / "AGENTS.md").write_text(
            "# Left 4 Dead 2 benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark "
            "repository, plugin, private tests, reference solution, validation records, "
            "prior runs, or state database. Repair every reported problem in the supplied "
            "source tree as described in EXAM.md. Do not use external implementations or "
            "network lookup. In strict mode, run the approved scorer exactly once after "
            "implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        l4d2_task = self._task(task)
        return {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": l4d2_task.task_kind,
            "sourceMod": l4d2_task.source_mod,
            "sourceRepository": l4d2_task.source_repo,
            "sourceCommit": l4d2_task.source_commit,
            "submissionLanguage": l4d2_task.submission_language,
            "privateCases": l4d2_task.expected_cases,
            "defectGroups": l4d2_task.defect_groups,
        }

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        l4d2_task = self._task(task)
        return (
            "You are the model under test in a Left 4 Dead 2 repository-repair benchmark. "
            f"Work only in the supplied {l4d2_task.submission_language} workspace and resolve "
            "every reported problem. Do not inspect or search for upstream fixes, benchmark "
            "internals, private tests, reference solutions, validation records, or prior "
            "results. The private evaluator runs the submission in a pinned real headless "
            "Left 4 Dead 2 dedicated server without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "Left 4 Dead 2 dedicated-server runtime status, and files changed"
        )
