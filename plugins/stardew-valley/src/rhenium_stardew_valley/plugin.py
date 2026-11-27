from __future__ import annotations

import json
import shutil
from pathlib import Path

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask
from rhenium.core.plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    EvaluationProfile,
    PluginDescriptor,
)
from rhenium.core.runtime import RuntimeBuilder, RuntimeSpec

from .catalog import StardewCatalog, StardewTask
from .evaluator import StardewEvaluator
from .native import NATIVE_ID, StardewNativeBuilder
from .runtime_builder import StardewRuntimeBuilder

RUNTIME_IDS = {
    "stardew-1.6.15-smapi-4.1.10",
    "stardew-1.6.15-smapi-4.1.10-synth",
}


class StardewValleyBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="stardew-valley",
        game_id="stardew-valley",
        name="Stardew Valley",
        version="0.6.0",
        capabilities=("csharp", "smapi", "docker", "headless-game"),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return StardewCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        catalog = StardewCatalog.load(context.pack_root, "catalog.json")
        return StardewEvaluator(context, catalog)

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        if spec.id == NATIVE_ID:
            return StardewNativeBuilder(context, StardewCatalog.load(context.pack_root))
        if spec.id not in RUNTIME_IDS:
            return None
        return StardewRuntimeBuilder(context, StardewCatalog.load(context.pack_root))

    def evaluation_profiles(self, task: BenchmarkTask) -> tuple[EvaluationProfile, ...]:
        profiles = super().evaluation_profiles(task)
        if self._stardew_task(task).clean_room_synthetic:
            return (*profiles, EvaluationProfile(
                id="macos", label="macOS native maintenance diagnostic", complete_eligible=False,
            ))
        return profiles

    @staticmethod
    def _stardew_task(task: BenchmarkTask) -> StardewTask:
        if not isinstance(task, StardewTask):
            raise TypeError("Stardew plugin received a non-Stardew task")
        return task

    @staticmethod
    def _exam_path(task: StardewTask, context: BenchmarkContext) -> Path:
        exams = (context.pack_root / "exams").resolve()
        exam = (exams / f"{task.id}.md").resolve()
        if not exam.is_relative_to(exams) or not exam.is_file():
            raise ValueError("Stardew public exam is missing")
        return exam

    @staticmethod
    def _public_instruction(text: str) -> str:
        return (
            text.replace("/app/StardewMods", "StardewMods")
            .replace("/app/mod", "mod")
            .replace("anything under `/tests`", "the private verifier")
        )

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        stardew_task = self._stardew_task(task)
        # The authored exam is English. Chinese task metadata remains available in
        # list/report APIs, while evaluation uses the exact validated public contract.
        del language
        return self._public_instruction(stardew_task.authored_prompt).strip()

    def materialize_starter(
        self,
        task: BenchmarkTask,
        workspace: Path,
        context: BenchmarkContext,
    ) -> None:
        stardew_task = self._stardew_task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / stardew_task.id
        source = task_root / "environment" / stardew_task.starter_name
        destination = workspace / stardew_task.starter_name
        shutil.copytree(source, destination)
        if stardew_task.clean_room_synthetic:
            shutil.copy2(context.pack_root / "LICENSE", workspace / "LICENSE")
        marker = {
            "difficulty": task.difficulty,
            "submission": ".",
            "fromScratch": stardew_task.task_kind == "generation",
            "language": "csharp",
        }
        (workspace / "task.json").write_text(
            json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        exam = self._public_instruction(
            self._exam_path(stardew_task, context).read_text(encoding="utf-8")
        )
        (workspace / "TASK.md").write_text(exam.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(
        self,
        task: BenchmarkTask,
        destination: Path,
        context: BenchmarkContext,
    ) -> None:
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        (destination / "AGENTS.md").write_text(
            "# Stardew Valley benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark "
            "repository, plugin, tests, reference solution, prior runs, or state database. "
            "Implement the public contract in EXAM.md using the provided C# source tree. "
            "Do not use external implementations or network lookup. In strict mode, run the "
            "approved scorer exactly once after implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        stardew_task = self._stardew_task(task)
        public = {
            **super().public_task(task),
            "fromScratch": stardew_task.task_kind == "generation",
            "taskKind": stardew_task.task_kind,
            "gameVersion": stardew_task.game_version,
            "smapiVersion": stardew_task.smapi_version,
            "submissionLanguage": "C#/.NET",
        }
        if not stardew_task.clean_room_synthetic:
            public["sourceMod"] = stardew_task.source_mod
        else:
            public["cleanRoomSynthetic"] = True
        return public

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        stardew_task = self._stardew_task(task)
        mode = "new SMAPI mod" if stardew_task.task_kind == "generation" else "SMAPI mod repair"
        source_boundary = (
            "The supplied source is clean-room synthetic and has no upstream implementation to find. "
            if stardew_task.clean_room_synthetic
            else "Do not inspect or search for upstream fixes, benchmark internals, private tests, "
            "reference solutions, or prior results. "
        )
        return (
            f"You are the model under test in a Stardew Valley {mode} benchmark. "
            "Work only in the supplied C# workspace and implement the authored task contract. "
            f"{source_boundary}The private evaluator will compile the "
            "submission and run assertions in the pinned real game without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "Stardew/SMAPI runtime status, and files changed"
        )
