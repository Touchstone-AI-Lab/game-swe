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

from .catalog import CATALOG_IDS, MinecraftCatalog, MinecraftTask
from .container import (
    CONTAINER_DESTINATION,
    PAPER_BUILD,
    PAPER_VERSION,
    RUNTIME_IDS,
    STARTER_NAME,
)
from .evaluator import MinecraftEvaluator
from .runtime_builder import MinecraftRuntimeBuilder


class MinecraftBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="minecraft",
        game_id="minecraft",
        name="Minecraft (Paper server plugins)",
        version="0.6.0",
        capabilities=(
            "java",
            "docker",
            "headless-server",
            "server-plugin",
            "repository-debugging",
            "construct",
        ),
    )

    @staticmethod
    def _catalog_id(pack_root: Path, catalog_path: str) -> str:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Minecraft catalog is missing: {catalog_path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Minecraft catalog is not valid JSON") from error
        identity = raw.get("id") if isinstance(raw, dict) else None
        if identity not in CATALOG_IDS:
            raise ValueError("unsupported Minecraft catalog id")
        return str(identity)

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        self._catalog_id(pack_root, catalog_path)
        return MinecraftCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return MinecraftEvaluator(context, MinecraftCatalog.load(context.pack_root))

    def create_runtime_builder(self, context: BenchmarkContext, spec: RuntimeSpec) -> RuntimeBuilder | None:
        if spec.id not in RUNTIME_IDS:
            return None
        return MinecraftRuntimeBuilder(context, MinecraftCatalog.load(context.pack_root))

    @staticmethod
    def _task(task: BenchmarkTask) -> MinecraftTask:
        if not isinstance(task, MinecraftTask):
            raise TypeError("Minecraft plugin received a non-Minecraft task")
        return task

    @staticmethod
    def _public_instruction(text: str) -> str:
        return text.replace(CONTAINER_DESTINATION, STARTER_NAME).replace(
            "anything under `/tests`", "the private verifier"
        )

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        del language
        return self._public_instruction(self._task(task).authored_prompt).strip()

    def materialize_starter(self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext) -> None:
        minecraft_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / minecraft_task.id
        shutil.copytree(task_root / "environment" / STARTER_NAME, workspace / STARTER_NAME)
        if minecraft_task.clean_room_synthetic:
            shutil.copy2(context.pack_root / "LICENSE", workspace / "LICENSE")
        (workspace / "task.json").write_text(
            json.dumps(
                {
                    "difficulty": task.difficulty,
                    "submission": ".",
                    "fromScratch": minecraft_task.is_construct,
                    "language": "java",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt = self._public_instruction(minecraft_task.authored_prompt)
        (workspace / "TASK.md").write_text(prompt.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(self, task: BenchmarkTask, destination: Path, context: BenchmarkContext) -> None:
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        if self._task(task).is_construct:
            (destination / "AGENTS.md").write_text(
                "# Minecraft benchmark guidance\n\n"
                "Work only inside this attempt directory. Do not inspect the benchmark "
                "repository, plugin, private tests, reference solution, validation records, "
                "prior runs, or state database. Write the new Paper plugin described in EXAM.md "
                "into the supplied skeleton. Its pom.xml is frozen: the verifier restores it "
                "before building, so changes there are discarded and no dependency beyond the "
                "Paper API can be added. Do not use external implementations or network lookup. "
                "In strict mode, run the approved scorer exactly once after implementation and "
                "do not edit afterward.\n",
                encoding="utf-8",
            )
            (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
            return
        (destination / "AGENTS.md").write_text(
            "# Minecraft benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark "
            "repository, plugin, private tests, reference solution, validation records, "
            "prior runs, or state database. Repair every reported problem in the supplied "
            "plugin source tree as described in EXAM.md. The build scripts, dependency "
            "declarations and upstream tests are frozen: the verifier restores them from "
            "the starter before building, so changes there are discarded. Do not use "
            "external implementations or network lookup. In strict mode, run the approved "
            "scorer exactly once after implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        minecraft_task = self._task(task)
        public: dict[str, object] = {
            **super().public_task(task),
            "fromScratch": minecraft_task.is_construct,
            "taskKind": minecraft_task.task_kind,
            "pluginName": minecraft_task.plugin_name,
            "buildTool": minecraft_task.build.tool,
            "submissionLanguage": "Java",
            "paperVersion": PAPER_VERSION,
            "paperBuild": PAPER_BUILD,
            "unitCases": len(minecraft_task.unit_cases),
            "serverCases": len(minecraft_task.server_cases),
        }
        if minecraft_task.upstream is not None:
            public["sourceRepository"] = minecraft_task.upstream.repository
            public["sourceCommit"] = minecraft_task.upstream.base_commit
            public["licenseSpdx"] = minecraft_task.upstream.license_spdx
        elif minecraft_task.clean_room_synthetic:
            public["cleanRoomSynthetic"] = True
        return public

    def sanitize_anonymous_result(self, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(value)
        sanitized.pop("runtime_log", None)
        runtime = sanitized.get("runtime")
        if isinstance(runtime, dict):
            sanitized["runtime"] = {
                key: item
                for key, item in runtime.items()
                if key not in {"cases", "unitCases", "caseOutcomes", "message"}
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
        minecraft_task = self._task(task)
        if minecraft_task.is_construct:
            return (
                "You are the model under test in a Minecraft (Paper server plugin) construction "
                "benchmark. The workspace holds only a skeleton: a frozen Maven build file, a "
                "minimal plugin.yml and an empty plugin class. Write the whole plugin the task "
                "specifies inside that skeleton. Do not inspect or search for benchmark internals, "
                "private tests, reference solutions, validation records, or prior results. The "
                "private evaluator builds the plugin offline and loads it into a pinned real Paper "
                f"{PAPER_VERSION} dedicated server without network access."
            )
        origin = (
            "The supplied plugin is clean-room synthetic and has no upstream implementation. "
            if minecraft_task.clean_room_synthetic
            else "The workspace contains a real open-source Paper plugin at a fixed commit. "
        )
        return (
            "You are the model under test in a Minecraft (Paper server plugin) repository-repair "
            f"benchmark. {origin}Work only in the supplied Java workspace and resolve every "
            "reported problem. Do not inspect or search for upstream fixes, benchmark internals, "
            "private tests, reference solutions, validation records, or prior results. The "
            f"private evaluator builds the plugin offline, runs its unit tests, and loads it into "
            f"a pinned real Paper {PAPER_VERSION} dedicated server without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned Paper "
            "dedicated-server runtime status, and files changed"
        )
