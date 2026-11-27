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

from .catalog import TerrariaCatalog, TerrariaTask
from .evaluator import (
    ENGINE_RUNTIME_ID,
    SOURCE_RUNTIME_ID,
    TMODLOADER_VERSION,
    TerrariaEvaluator,
)
from .runtime_builder import (
    TerrariaEngineRuntimeBuilder,
    TerrariaSourceProjectionRuntimeBuilder,
)


class TerrariaBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="terraria",
        game_id="terraria",
        name="Terraria",
        version="0.7.0",
        capabilities=(
            "csharp",
            "dotnet",
            "docker",
            "repository-debugging",
            "real-tmodloader",
        ),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return TerrariaCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return TerrariaEvaluator(context, TerrariaCatalog.load(context.pack_root))

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        catalog = TerrariaCatalog.load(context.pack_root)
        if spec.id == SOURCE_RUNTIME_ID:
            return TerrariaSourceProjectionRuntimeBuilder(context, catalog)
        if spec.id == ENGINE_RUNTIME_ID:
            return TerrariaEngineRuntimeBuilder(context, catalog)
        return None

    @staticmethod
    def _task(task: BenchmarkTask) -> TerrariaTask:
        if not isinstance(task, TerrariaTask):
            raise TypeError("Terraria plugin received a non-Terraria task")
        return task

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        del language
        return self._task(task).authored_prompt.strip()

    def materialize_starter(
        self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext
    ) -> None:
        terraria_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        source = (
            context.pack_root
            / "private"
            / "harbor"
            / task.id
            / "environment"
            / terraria_task.starter_name
        )
        shutil.copytree(source, workspace / terraria_task.starter_name)
        (workspace / "task.json").write_text(
            json.dumps(
                {
                    "difficulty": task.difficulty,
                    "submission": ".",
                    "fromScratch": False,
                    "language": "csharp",
                    "gameVersion": terraria_task.game_version,
                    "tModLoaderApi": terraria_task.tmodloader_api,
                    "evaluationBoundary": terraria_task.evaluation_boundary,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (workspace / "TASK.md").write_text(
            terraria_task.authored_prompt.rstrip() + "\n", encoding="utf-8"
        )

    def materialize_attempt(
        self, task: BenchmarkTask, destination: Path, context: BenchmarkContext
    ) -> None:
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        (destination / "AGENTS.md").write_text(
            "# Terraria benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark repository, "
            "private tests, reference solutions, validation controls, or prior attempts. Implement "
            "the public contract in EXAM.md using C# and the supplied frozen mod source. Do not use "
            "network lookup or third-party implementations. In strict mode, run the approved scorer "
            "exactly once after implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        terraria_task = self._task(task)
        return {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": terraria_task.task_kind,
            "gameVersion": terraria_task.game_version,
            "tModLoaderApi": terraria_task.tmodloader_api,
            "evaluationBoundary": terraria_task.evaluation_boundary,
            "submissionLanguage": "C#",
            "sourceMod": terraria_task.source_mod,
            "sourceRepository": terraria_task.source_repo,
            "sourceCommit": terraria_task.source_commit,
            "privateCases": terraria_task.expected_cases,
            "realEngineCases": terraria_task.expected_engine_cases,
            "engineMode": terraria_task.engine_mode,
            "tModLoaderVersion": TMODLOADER_VERSION,
            "clientOnlyExclusions": list(terraria_task.client_only_exclusions),
            "defectGroups": terraria_task.defect_groups,
        }

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        self._task(task)
        return (
            "You are the model under test in a Terraria/tModLoader repository-repair benchmark. "
            "Work only in the supplied source workspace and repair every reported regression. Do not "
            "inspect benchmark internals, private tests, reference solutions, validation controls, "
            "prior results, or external implementations. The private evaluator compiles the affected "
            "production mod files in a pinned .NET 8 source projection and runs deterministic "
            "behavioral checks and, for the full profile, compiles the submitted production files "
            "into a verifier mod loaded by a pinned real tModLoader dedicated server. Client-only "
            "map, rendering, and input details remain in the deterministic projection layer."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "Terraria source-projection and real tModLoader runtime status, and files changed"
        )
