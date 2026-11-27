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

from .addons.catalog import GmodCatalog, GmodTask
from .addons.evaluator import GmodEvaluator
from .addons.plugin import GmodAddonSupport
from .darkrp.catalog import GLUATEST_RUNTIME_IDS, GarrysModCatalog, GarrysModTask
from .darkrp.evaluator import GarrysModEvaluator
from .darkrp.runtime_builder import GarrysModRuntimeBuilder

# The clean-room Addons construction pack (`garrys-mod/addons`) keeps its own task model:
# an addon written from an empty workspace, judged by plain-Lua suites and the pinned
# native App 4020 Dedicated Server (Phase A/B). It never uses a managed runtime key.
_ADDON_CATALOG_ID = "rhenium-gmod-v2"
# Every other supported pack uses the GLuaTest task model: a real source tree evaluated
# by a private GLuaTest suite in a managed headless dedicated server. The DarkRP pack
# ships a gamemode, the addon-repair pack ships one server addon per task, and the
# repository-maintenance authoring tool stages clean-room gamemode repairs in a separate
# synth pack. Each GLuaTest pack owns its own runtime key.
_GLUATEST_CATALOG_IDS = frozenset(GLUATEST_RUNTIME_IDS)

RUNTIME_IDS = frozenset(GLUATEST_RUNTIME_IDS.values())


class GarrysModBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="garrys-mod",
        game_id="garrys-mod",
        name="Garry's Mod",
        version="0.6.0",
        capabilities=(
            "lua",
            "glua",
            "static-analysis",
            "docker",
            "headless-server",
            "windows-dedicated-server",
            "linux-dedicated-server",
        ),
    )

    def __init__(self) -> None:
        self._addon_support = GmodAddonSupport()

    @staticmethod
    def _catalog_id(pack_root: Path, catalog_path: str = "catalog.json") -> str:
        root = pack_root.resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Garry's Mod catalog is missing: {catalog_path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Garry's Mod catalog is invalid") from error
        identifier = value.get("id") if isinstance(value, dict) else None
        if identifier != _ADDON_CATALOG_ID and identifier not in _GLUATEST_CATALOG_IDS:
            raise ValueError(f"unsupported Garry's Mod catalog: {identifier!r}")
        return str(identifier)

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        if self._catalog_id(pack_root, catalog_path) == _ADDON_CATALOG_ID:
            return GmodCatalog.load(pack_root, catalog_path)
        return GarrysModCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        if self._catalog_id(context.pack_root) == _ADDON_CATALOG_ID:
            return GmodEvaluator(context, GmodCatalog.load(context.pack_root, "catalog.json"))
        return GarrysModEvaluator(context, GarrysModCatalog.load(context.pack_root, "catalog.json"))

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        catalog_id = self._catalog_id(context.pack_root)
        # The Addons pack uses the operator-prepared native server, never a managed runtime.
        if spec.id in RUNTIME_IDS and GLUATEST_RUNTIME_IDS.get(catalog_id) == spec.id:
            return GarrysModRuntimeBuilder(context, GarrysModCatalog.load(context.pack_root))
        return None

    @staticmethod
    def _task(task: BenchmarkTask) -> GarrysModTask:
        if not isinstance(task, GarrysModTask):
            raise TypeError("Garry's Mod plugin received a non-Garry's Mod task")
        return task

    @staticmethod
    def _exam_path(task: GarrysModTask, context: BenchmarkContext) -> Path:
        exams = (context.pack_root / "exams").resolve()
        exam = (exams / f"{task.id}.md").resolve()
        if not exam.is_relative_to(exams) or not exam.is_file():
            raise ValueError("Garry's Mod public exam is missing")
        return exam

    @staticmethod
    def _public_instruction(text: str, task: GarrysModTask) -> str:
        """Rewrite the Harbor container paths of an exam into workspace-relative ones."""
        text = text.replace("/app/darkrp", "darkrp")
        if task.source_kind == "addon":
            text = text.replace(task.container_destination, task.starter_name)
        return text.replace("anything under `/tests`", "the private verifier")

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        if isinstance(task, GmodTask):
            return self._addon_support.task_prompt(task, language)
        # The authored exam is English. Chinese task metadata stays available in the
        # list and report APIs, while evaluation uses the exact validated contract.
        del language
        gmod_task = self._task(task)
        return self._public_instruction(gmod_task.authored_prompt, gmod_task).strip()

    def materialize_starter(
        self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext
    ) -> None:
        if isinstance(task, GmodTask):
            self._addon_support.materialize_starter(task, workspace, context)
            return
        gmod_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / gmod_task.id
        shutil.copytree(
            task_root / "environment" / gmod_task.starter_name,
            workspace / gmod_task.starter_name,
        )
        if gmod_task.clean_room_synthetic:
            shutil.copy2(context.pack_root / "LICENSE", workspace / "LICENSE")
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
        exam = self._public_instruction(
            self._exam_path(gmod_task, context).read_text(encoding="utf-8"), gmod_task
        )
        (workspace / "TASK.md").write_text(exam.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(
        self, task: BenchmarkTask, destination: Path, context: BenchmarkContext
    ) -> None:
        if isinstance(task, GmodTask):
            self._addon_support.materialize_attempt(task, destination, context)
            return
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        heading = (
            "# Garry's Mod synthetic benchmark guidance\n\n"
            if self._task(task).clean_room_synthetic
            else "# Garry's Mod benchmark guidance\n\n"
        )
        guidance = (
            heading
            + "Work only inside this attempt directory. Do not inspect the benchmark "
            "repository, plugin, tests, reference solution, prior runs, or state database. "
            "Repair the reported problems in the provided GLua source tree as described in "
            "EXAM.md. Do not use external implementations or network lookup. In strict mode, "
            "run the approved scorer exactly once after implementation and do not edit "
            "afterward.\n"
        )
        (destination / "AGENTS.md").write_text(
            guidance,
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        if isinstance(task, GmodTask):
            return self._addon_support.public_task(task)
        gmod_task = self._task(task)
        public = {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": gmod_task.task_kind,
            "submissionLanguage": "Lua (GLua)",
        }
        if gmod_task.clean_room_synthetic:
            public["cleanRoomSynthetic"] = True
        else:
            public["sourceMod"] = gmod_task.source_mod
            public["sourceCommit"] = gmod_task.source_commit
        return public

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        if isinstance(task, GmodTask):
            return self._addon_support.agent_system_prompt(task)
        gmod_task = self._task(task)
        if gmod_task.source_kind == "addon":
            return (
                "You are the model under test in a Garry's Mod addon repair benchmark. "
                "Work only in the supplied GLua workspace and resolve every problem the task "
                "reports. Do not inspect or search for upstream fixes, benchmark internals, "
                "private tests, reference solutions, or prior results. The private evaluator "
                "runs the addon on a real headless dedicated server without network access."
            )
        if not gmod_task.clean_room_synthetic:
            return (
                "You are the model under test in a Garry's Mod DarkRP repair benchmark. "
                "Work only in the supplied GLua workspace and resolve every problem the task "
                "reports. Do not inspect or search for upstream fixes, benchmark internals, "
                "private tests, reference solutions, or prior results. The private evaluator "
                "runs the gamemode on a real headless dedicated server without network access."
            )
        source_boundary = (
            "The supplied gamemode is clean-room synthetic and has no upstream implementation. "
        )
        return (
            "You are the model under test in a Garry's Mod repair benchmark. "
            "Work only in the supplied GLua workspace and resolve every problem the task "
            f"reports. {source_boundary}The private evaluator "
            "runs the gamemode on a real headless dedicated server without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "Garry's Mod server runtime status, Addon Phase A/B status when applicable, and "
            "files changed or created"
        )

    def sanitize_anonymous_result(self, value: Any) -> Any:
        """Drop private runtime diagnostics before the Hub applies identity redaction.

        One rule serves every pack: the Addons subsystem's sanitizer also drops the
        GLuaTest audit's private fields.
        """
        return self._addon_support.sanitize_anonymous_result(value)
