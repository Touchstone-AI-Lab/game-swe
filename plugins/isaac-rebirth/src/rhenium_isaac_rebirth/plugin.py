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

from .catalog import IsaacCatalog, IsaacTask
from .evaluator import IsaacEvaluator
from .runtime_builder import IsaacRuntimeBuilder

RUNTIME_IDS = {"afterbirth-plus-1.06.t1", "afterbirth-plus-1.06.t1-synth"}


class IsaacRebirthBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="isaac-rebirth",
        game_id="isaac-rebirth",
        name="The Binding of Isaac: Rebirth",
        version="0.6.0",
        capabilities=("lua", "afterbirth-plus", "docker", "native-game"),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return IsaacCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return IsaacEvaluator(context, IsaacCatalog.load(context.pack_root))

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        if spec.id not in RUNTIME_IDS:
            return None
        return IsaacRuntimeBuilder(context, IsaacCatalog.load(context.pack_root))

    @staticmethod
    def _isaac_task(task: BenchmarkTask) -> IsaacTask:
        if not isinstance(task, IsaacTask):
            raise TypeError("Isaac plugin received a non-Isaac task")
        return task

    @staticmethod
    def _starter_ignore(_directory: str, names: list[str]) -> set[str]:
        ignored_suffixes = {".it", ".bak", ".db"}
        retained_data = {"save1.dat", "save2.dat"}
        return {
            name
            for name in names
            if Path(name).suffix in ignored_suffixes or (name.endswith(".dat") and name not in retained_data)
        }

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        isaac_task = self._isaac_task(task)
        del language
        return isaac_task.authored_prompt.strip()

    def materialize_starter(
        self,
        task: BenchmarkTask,
        workspace: Path,
        context: BenchmarkContext,
    ) -> None:
        isaac_task = self._isaac_task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / isaac_task.id
        shutil.copytree(
            task_root / "environment" / isaac_task.starter_name,
            workspace / isaac_task.starter_name,
            ignore=self._starter_ignore,
        )
        if isaac_task.clean_room_synthetic:
            shutil.copy2(context.pack_root / "LICENSE", workspace / "LICENSE")
        marker = {
            "difficulty": task.difficulty,
            "submission": ".",
            "fromScratch": isaac_task.clean_room_synthetic,
            "language": "lua",
        }
        (workspace / "task.json").write_text(
            json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (workspace / "TASK.md").write_text(isaac_task.authored_prompt.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(
        self,
        task: BenchmarkTask,
        destination: Path,
        context: BenchmarkContext,
    ) -> None:
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        isaac_task = self._isaac_task(task)
        source_description = (
            "the supplied anonymous Lua mod and the documented Afterbirth+ APIs"
            if isaac_task.clean_room_synthetic
            else "the supplied Exodus Lua source and the documented Afterbirth+ APIs"
        )
        (destination / "AGENTS.md").write_text(
            "# The Binding of Isaac benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark repository, "
            "plugin, private assertions, reference solution, validation data, prior attempts, "
            f"or state database. Implement the public contract in EXAM.md using {source_description}. "
            "Do not search for upstream "
            "fixes or external implementations. In strict mode, run the approved scorer exactly "
            "once after implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        isaac_task = self._isaac_task(task)
        public = {
            **super().public_task(task),
            "fromScratch": isaac_task.clean_room_synthetic,
            "taskKind": "construct" if isaac_task.clean_room_synthetic else "debugging",
            "gameVersion": isaac_task.game_version,
            "gameBuild": isaac_task.game_build,
            "submissionLanguage": "Lua",
        }
        if isaac_task.clean_room_synthetic:
            public["cleanRoomSynthetic"] = True
        else:
            public["sourceMod"] = isaac_task.source_mod
        return public

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        isaac_task = self._isaac_task(task)
        if not isaac_task.clean_room_synthetic:
            return (
                "You are the model under test in an Afterbirth+ Lua mod repair benchmark. "
                "Work only in the supplied Exodus source workspace and implement the authored task "
                "contract. Do not inspect or search for upstream fixes, benchmark internals, private "
                "tests, reference solutions, or prior results. The private evaluator runs the "
                "submission in the pinned native game without network access."
            )
        source_boundary = (
            "The supplied mod is clean-room synthetic and has no upstream implementation. "
        )
        return (
            "You are the model under test in an Afterbirth+ Lua mod repair benchmark. "
            "Work only in the supplied anonymous Lua mod workspace and implement the authored task "
            f"contract. {source_boundary}The private evaluator runs the "
            "submission in the pinned native game without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "Afterbirth+ runtime status, whether all three processes and 35 assertions ran, "
            "and files changed"
        )
