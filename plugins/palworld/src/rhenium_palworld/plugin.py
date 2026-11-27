from __future__ import annotations

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

from .catalog import PalworldCatalog, PalworldTask
from .evaluator import PalworldEvaluator
from .native_runtime import PLUGIN_VERSION, RUNTIME_ID
from .runtime import PalworldRuntimeConfig
from .runtime_builder import PalworldRuntimeBuilder


class PalworldBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="palworld",
        game_id="palworld",
        name="Palworld",
        version=PLUGIN_VERSION,
        capabilities=("lua", "static-analysis", "sandbox", "headless-server"),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return PalworldCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return PalworldEvaluator(PalworldRuntimeConfig.load(context))

    def create_runtime_builder(self, context: BenchmarkContext, spec: RuntimeSpec) -> RuntimeBuilder | None:
        return PalworldRuntimeBuilder(context) if spec.id == RUNTIME_ID else None

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        prompt = super().task_prompt(task, language)
        if language == "zh":
            return prompt.replace("游戏 API 使用合同", "UE4SS API 使用合同")
        return prompt.replace("Game API usage contract", "UE4SS API usage contract")

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        if not isinstance(task, PalworldTask):
            raise TypeError("Palworld plugin received a non-Palworld task")
        return (
            "You are the model under test in a Palworld engineering benchmark. "
            "The workspace contains only the public task contract and an empty starter; implement "
            "the requested UE4SS Lua mod from scratch. Keep plain-Lua state machines independent "
            "of UE4SS globals, keep authority on the dedicated server, and use the documented "
            "UE4SS API signatures exactly. You cannot see private Lua or dedicated-server "
            "assertions. Before submitting, inspect every required file and run "
            "`python -m rhenium_palworld.public_check .` for public syntax diagnostics."
        )

    def materialize_attempt(
        self,
        task: BenchmarkTask,
        destination: Path,
        context: BenchmarkContext,
    ) -> None:
        if not isinstance(task, PalworldTask):
            raise TypeError("Palworld plugin received a non-Palworld task")
        exams_root = (context.pack_root / "exams").resolve()
        exam = (exams_root / f"{task.id}.md").resolve()
        if not exam.is_relative_to(exams_root) or not exam.is_file():
            super().materialize_attempt(task, destination, context)
            return
        shutil.copy2(exam, destination / "EXAM.md")
        shutil.copy2(context.project_root / "AGENTS.md", destination / "AGENTS.md")
        shutil.copy2(context.project_root / "CLAUDE.md", destination / "CLAUDE.md")

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or skipped checks, headless "
            "dedicated-server status, and files created"
        )
