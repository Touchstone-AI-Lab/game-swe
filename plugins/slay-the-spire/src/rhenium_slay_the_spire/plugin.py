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

from .catalog import (
    CATALOG_ID,
    CONTAINER_DESTINATION,
    STARTER_NAME,
    SlayTheSpireCatalog,
    SlayTheSpireTask,
)
from .container import RUNTIME_ID
from .evaluator import SlayTheSpireEvaluator
from .native import NATIVE_RUNTIME_ID, SlayTheSpireNativeRuntimeBuilder
from .runtime_builder import SlayTheSpireRuntimeBuilder

MODTHESPIRE_GUIDANCE = (
    "# Slay the Spire benchmark guidance\n\n"
    "Work only inside this attempt directory. Do not inspect the benchmark "
    "repository, plugin, private tests, reference solution, validation records, "
    "prior runs, or state database. Repair every problem reported in EXAM.md in "
    "the supplied ModTheSpire source tree. The reports are observations, not "
    "diagnoses, and they do not say how many underlying problems there are. "
    "ModTheSpire is a Java 8 Maven project: it builds against the JDK and "
    "Javassist only, with no base game, no display and no network. Do not use "
    "external implementations or network lookup. In strict mode, run the approved "
    "scorer exactly once after implementation and do not edit afterward.\n"
)
NATIVE_GUIDANCE = (
    "# Slay the Spire benchmark guidance\n\n"
    "Work only inside this attempt directory. Do not inspect the benchmark "
    "repository, plugin, private tests, reference solution, validation records, "
    "prior runs, or state database. Repair every problem reported in EXAM.md in "
    "the supplied mod source tree under project/. The reports are observations, not "
    "diagnoses, and they do not say how many underlying problems there are. "
    "The private verifier builds the submitted Java sources offline and runs them in "
    "the real game under a virtual display; the base game is not part of this "
    "workspace. Do not use external implementations or network lookup. In strict "
    "mode, run the approved scorer exactly once after implementation and do not edit "
    "afterward.\n"
)


class SlayTheSpireBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="slay-the-spire",
        game_id="slay-the-spire",
        name="Slay the Spire (ModTheSpire loader)",
        version="0.7.0",
        capabilities=("java", "docker", "bytecode-patching", "repository-debugging"),
    )

    @staticmethod
    def _catalog_id(pack_root: Path, catalog_path: str) -> str:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Slay the Spire catalog is missing: {catalog_path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Slay the Spire catalog is not valid JSON") from error
        identity = raw.get("id") if isinstance(raw, dict) else None
        if identity != CATALOG_ID:
            raise ValueError("unsupported Slay the Spire catalog id")
        return str(identity)

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        self._catalog_id(pack_root, catalog_path)
        return SlayTheSpireCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return SlayTheSpireEvaluator(context, SlayTheSpireCatalog.load(context.pack_root))

    def create_runtime_builder(self, context: BenchmarkContext, spec: RuntimeSpec) -> RuntimeBuilder | None:
        if spec.id == RUNTIME_ID:
            return SlayTheSpireRuntimeBuilder(context, SlayTheSpireCatalog.load(context.pack_root))
        if spec.id == NATIVE_RUNTIME_ID:
            return SlayTheSpireNativeRuntimeBuilder(context, SlayTheSpireCatalog.load(context.pack_root))
        return None

    @staticmethod
    def _task(task: BenchmarkTask) -> SlayTheSpireTask:
        if not isinstance(task, SlayTheSpireTask):
            raise TypeError("Slay the Spire plugin received a non-Slay-the-Spire task")
        return task

    @staticmethod
    def _public_instruction(text: str) -> str:
        return text.replace(CONTAINER_DESTINATION, STARTER_NAME)

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        del language
        return self._public_instruction(self._task(task).authored_prompt).strip()

    def materialize_starter(self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext) -> None:
        spire_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / spire_task.id
        starter = spire_task.starter_name
        shutil.copytree(task_root / "environment" / starter, workspace / starter)
        (workspace / "task.json").write_text(
            json.dumps(
                {
                    "difficulty": task.difficulty,
                    "submission": ".",
                    "fromScratch": False,
                    "language": "java",
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt = self._public_instruction(spire_task.authored_prompt)
        (workspace / "TASK.md").write_text(prompt.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(self, task: BenchmarkTask, destination: Path, context: BenchmarkContext) -> None:
        spire_task = self._task(task)
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        guidance = NATIVE_GUIDANCE if spire_task.game_backed else MODTHESPIRE_GUIDANCE
        if not spire_task.game_backed:
            guidance += ("\nReal-game verification is unavailable for this task. "
                         "Scoring returns incomplete and cannot produce a full benchmark pass.\n")
        (destination / "AGENTS.md").write_text(guidance, encoding="utf-8")
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        spire_task = self._task(task)
        return {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": spire_task.task_kind,
            "sourceMod": spire_task.source_mod,
            "sourceCommit": spire_task.source_commit,
            "submissionLanguage": "Java",
            "buildTool": "maven",
            "javaRelease": 8,
        }

    def sanitize_anonymous_result(self, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(value)
        sanitized.pop("runtime_log", None)
        runtime = sanitized.get("runtime")
        if isinstance(runtime, dict):
            sanitized["runtime"] = {
                key: item for key, item in runtime.items() if key not in {"message", "caseOutcomes"}
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
        if self._task(task).game_backed:
            return (
                "You are the model under test in a Slay the Spire mod repository-repair "
                "benchmark. The workspace holds a real mod's source tree at a fixed commit, "
                "carrying regressions reported only as user-visible symptoms. Work only in the "
                "supplied project and resolve every reported problem at its cause. Do not inspect "
                "or search for upstream fixes, benchmark internals, private tests, reference "
                "solutions, validation records, or prior results. A private verifier builds the "
                "submission offline and checks it inside the real game, without network access."
            )
        return (
            "You are the model under test in a Slay the Spire (ModTheSpire) repository-repair "
            "benchmark. The workspace holds the real ModTheSpire loader and bytecode patch "
            "engine at a fixed commit, carrying regressions reported only as user-visible "
            "symptoms. Work only in the supplied Java 8 Maven workspace and resolve every "
            "reported problem at its cause. Do not inspect or search for upstream fixes, "
            "benchmark internals, private tests, reference solutions, validation records, or "
            "prior results. Historical JUnit diagnostics ran offline, without the base "
            "game, a display or network access. Real-game verification is unavailable for "
            "this task, so benchmark scoring is incomplete and cannot pass."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned "
            "JDK 8 Maven evaluator runtime status, and files changed"
        )
