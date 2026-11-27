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

from .catalog import CATALOG_ID, MindustryCatalog, MindustryTask
from .construct_catalog import CONSTRUCT_CATALOG_ID, MindustryConstructCatalog, MindustryConstructTask
from .construct_evaluator import RUNTIME_ID as CONSTRUCT_RUNTIME_ID
from .construct_evaluator import MindustryConstructEvaluator
from .construct_runtime_builder import MindustryConstructRuntimeBuilder
from .container import CONTAINER_DESTINATION, MINDUSTRY_VERSION, RUNTIME_ID, STARTER_NAME
from .evaluator import MindustryEvaluator
from .runtime_builder import MindustryRuntimeBuilder

# The plugin serves two catalogs and dispatches on the catalog id: the repair catalog
# (game-source repairs) and the restored construct catalog (a server plugin written
# from an empty scaffold). Each has its own evaluator and runtime.
_CATALOG_IDS = frozenset({CATALOG_ID, CONSTRUCT_CATALOG_ID})


class MindustryBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="mindustry",
        game_id="mindustry",
        name="Mindustry (dedicated server)",
        version="0.6.0",
        capabilities=("java", "docker", "headless-server", "repository-debugging", "server-plugin"),
    )

    @staticmethod
    def _catalog_id(pack_root: Path, catalog_path: str = "catalog.json") -> str:
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Mindustry catalog is missing: {catalog_path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Mindustry catalog is not valid JSON") from error
        catalog_id = raw.get("id") if isinstance(raw, dict) else None
        if not isinstance(catalog_id, str) or catalog_id not in _CATALOG_IDS:
            raise ValueError("unsupported Mindustry catalog id")
        return catalog_id

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        if self._catalog_id(pack_root, catalog_path) == CONSTRUCT_CATALOG_ID:
            return MindustryConstructCatalog.load(pack_root, catalog_path)
        return MindustryCatalog.load(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        if self._catalog_id(context.pack_root) == CONSTRUCT_CATALOG_ID:
            return MindustryConstructEvaluator(context, MindustryConstructCatalog.load(context.pack_root))
        return MindustryEvaluator(context, MindustryCatalog.load(context.pack_root))

    def create_runtime_builder(self, context: BenchmarkContext, spec: RuntimeSpec) -> RuntimeBuilder | None:
        if self._catalog_id(context.pack_root) == CONSTRUCT_CATALOG_ID:
            if spec.id != CONSTRUCT_RUNTIME_ID:
                return None
            return MindustryConstructRuntimeBuilder(
                context, MindustryConstructCatalog.load(context.pack_root)
            )
        if spec.id != RUNTIME_ID:
            return None
        return MindustryRuntimeBuilder(context, MindustryCatalog.load(context.pack_root))

    @staticmethod
    def _task(task: BenchmarkTask) -> MindustryTask:
        if not isinstance(task, MindustryTask):
            raise TypeError("Mindustry plugin received a non-Mindustry task")
        return task

    @staticmethod
    def _public_instruction(text: str) -> str:
        return text.replace(CONTAINER_DESTINATION, STARTER_NAME).replace(
            "anything under `/tests`", "the private verifier"
        )

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        del language
        if isinstance(task, MindustryConstructTask):
            return task.authored_prompt.strip()
        return self._public_instruction(self._task(task).authored_prompt).strip()

    @staticmethod
    def _materialize_construct_starter(
        task: MindustryConstructTask, workspace: Path, context: BenchmarkContext
    ) -> None:
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)

        task_root = context.pack_root / "private" / "harbor" / task.id
        environment = task_root / "environment" / "mindustry"
        for source in environment.iterdir():
            destination = workspace / source.name
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        (workspace / "src").mkdir(exist_ok=True)

        marker = {
            "difficulty": task.difficulty,
            "submission": ".",
            "fromScratch": True,
            "language": "java",
        }
        (workspace / "task.json").write_text(
            json.dumps(marker, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (workspace / "TASK.md").write_text(
            task.authored_prompt.rstrip() + "\n",
            encoding="utf-8",
        )

    def materialize_starter(self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext) -> None:
        if isinstance(task, MindustryConstructTask):
            self._materialize_construct_starter(task, workspace, context)
            return
        mindustry_task = self._task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        task_root = context.pack_root / "private" / "harbor" / mindustry_task.id
        shutil.copytree(task_root / "environment" / STARTER_NAME, workspace / STARTER_NAME)
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
        prompt = self._public_instruction(mindustry_task.authored_prompt)
        (workspace / "TASK.md").write_text(prompt.rstrip() + "\n", encoding="utf-8")

    def materialize_attempt(self, task: BenchmarkTask, destination: Path, context: BenchmarkContext) -> None:
        if isinstance(task, MindustryConstructTask):
            self._materialize_construct_starter(task, destination, context)
            (destination / "TASK.md").replace(destination / "EXAM.md")
            (destination / "AGENTS.md").write_text(
                "# Mindustry benchmark guidance\n\n"
                "Work only inside this attempt directory. Do not inspect the benchmark repository, "
                "private tests, reference solution, validation controls, prior attempts, or state "
                "database. Implement the public contract in EXAM.md using Java and the supplied "
                "Mindustry build environment. Do not use network lookup or external implementations. "
                "In strict mode, run the approved scorer exactly once after implementation and do not "
                "edit afterward.\n",
                encoding="utf-8",
            )
            (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
            return
        self.materialize_starter(task, destination, context)
        (destination / "TASK.md").replace(destination / "EXAM.md")
        (destination / "AGENTS.md").write_text(
            "# Mindustry benchmark guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the benchmark "
            "repository, plugin, private tests, reference solution, validation records, "
            "prior runs, or state database. Repair every reported problem in the supplied "
            "Mindustry source tree as described in EXAM.md. The verifier compiles the Java "
            "sources under `mindustry/core/src` and `mindustry/server/src` against the pinned "
            "dedicated server; generated classes and game assets come from that server and "
            "are not rebuilt. Do not use external implementations, upstream history or "
            "network lookup. In strict mode, run the approved scorer exactly once after "
            "implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        if isinstance(task, MindustryConstructTask):
            return {
                **super().public_task(task),
                "fromScratch": True,
                "taskKind": task.task_kind,
                "gameVersion": task.game_version,
                "submissionLanguage": "Java",
            }
        mindustry_task = self._task(task)
        return {
            **super().public_task(task),
            "fromScratch": False,
            "taskKind": mindustry_task.task_kind,
            "buildTool": mindustry_task.build.tool,
            "submissionLanguage": "Java",
            "mindustryVersion": MINDUSTRY_VERSION,
            "serverCases": len(mindustry_task.server_cases),
            "sourceRepository": mindustry_task.upstream.repository,
            "sourceRelease": mindustry_task.upstream.release_tag,
            "sourceCommit": mindustry_task.upstream.base_commit,
            "licenseSpdx": mindustry_task.upstream.license_spdx,
        }

    def sanitize_anonymous_result(self, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(value)
        sanitized.pop("runtime_log", None)
        runtime = sanitized.get("runtime")
        if isinstance(runtime, dict):
            sanitized["runtime"] = {
                key: item for key, item in runtime.items() if key not in {"cases", "caseOutcomes", "message"}
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
        if isinstance(task, MindustryConstructTask):
            return (
                "You are the model under test in a Mindustry server-plugin generation benchmark. "
                "Work only in the supplied attempt workspace and implement the authored contract. "
                "Do not inspect benchmark internals, private tests, reference solutions, validation "
                "controls, prior results, or external implementations. The private evaluator compiles "
                "the submission and runs it against the pinned Mindustry 159 headless server without "
                "network access."
            )
        self._task(task)
        return (
            "You are the model under test in a Mindustry repository-repair benchmark. The workspace "
            f"contains the open-source Mindustry game at release {MINDUSTRY_VERSION} with real upstream "
            "defects. Work only in the supplied Java workspace and resolve every reported problem. Do "
            "not inspect or search for upstream fixes, benchmark internals, private tests, reference "
            "solutions, validation records, or prior results. The private evaluator compiles the game "
            f"sources offline against the pinned Mindustry {MINDUSTRY_VERSION} dedicated server and runs "
            "them as a real headless server without network access."
        )

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or incomplete checks, pinned Mindustry "
            "dedicated-server runtime status, and files changed"
        )
