from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask
from rhenium.core.plugin import BenchmarkContext, BenchmarkPlugin, EvaluationBackend, PluginDescriptor
from rhenium.core.runtime import RuntimeBuilder, RuntimeSpec

from .catalog import BalatroTask, anonymous_document, load_catalog
from .evaluator import BalatroEvaluator
from .files import asset, digest, empty_destination, read_file, write_new
from .results import anonymous_result


class BalatroBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="balatro", game_id="balatro", name="Balatro", version="0.3.0",
        capabilities=("lua", "repair-starter", "anonymous-attempt", "reviewed-linux-container"),
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        return load_catalog(pack_root, catalog_path)

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        if sys.platform == "linux":
            from .container_evaluator import BalatroContainerEvaluator
            from .container_host import RUNTIME_ID as CONTAINER_ID
            from .linux_layout import pack_runtime

            if pack_runtime(context) == CONTAINER_ID:
                return BalatroContainerEvaluator(context)
            from .linux_evaluator import BalatroLinuxEvaluator

            return BalatroLinuxEvaluator(context)
        return BalatroEvaluator(context)

    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec,
    ) -> RuntimeBuilder | None:
        from .container_builder import BalatroContainerBuilder
        from .container_host import RUNTIME_ID as CONTAINER_ID
        from .linux_managed import RUNTIME_ID as CONTROLLED_ID
        from .linux_managed import BalatroLinuxRuntimeBuilder
        from .linux_managed_v2 import RUNTIME_ID as CONTROLLED_V2
        from .linux_managed_v2 import BalatroLinuxRuntimeBuilderV2
        from .linux_runtime import RUNTIME_ID, BalatroLinuxProbeBuilder

        if spec.id == CONTAINER_ID:
            return BalatroContainerBuilder(context)
        if spec.id == CONTROLLED_V2:
            return BalatroLinuxRuntimeBuilderV2(context)

        if spec.id == CONTROLLED_ID:
            return BalatroLinuxRuntimeBuilder(context)
        return BalatroLinuxProbeBuilder(context) if spec.id == RUNTIME_ID else None

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        del language
        if not isinstance(task, BalatroTask):
            raise TypeError("incompatible task")
        return task.authored_prompt

    def materialize_attempt(
        self, task: BenchmarkTask, destination: Path, context: BenchmarkContext,
    ) -> None:
        if not isinstance(task, BalatroTask):
            raise TypeError("incompatible task")
        if destination.resolve().is_relative_to(context.pack_root.resolve()):
            raise ValueError("attempt cannot be written into the pack")
        root = asset(context.pack_root, task.package)
        # Read/validate everything before writing any participant file.
        payload: dict[str, bytes] = {}
        if digest(read_file(root, "package.json")) != task.package_sha256:
            raise ValueError("package identity changed")
        for name in (*task.editable_files, *task.immutable_files, *task.public_documents):
            data = read_file(root, name)
            if digest(data) != task.snapshot_files[name]:
                raise ValueError("public asset changed after catalog loading")
            if name == "CONTRACT.md":
                continue  # The verbatim rules, except identity, are already in EXAM.md.
            if name in task.public_documents:
                data = anonymous_document(data.decode("utf-8"), task.id).encode("utf-8")
            payload[name] = data
        payload["EXAM.md"] = (task.authored_prompt + "\n").encode("utf-8")
        payload["AGENTS.md"] = (
            b"# Attempt guidance\n\nWork only inside this attempt. Repair the supplied starter using "
            b"EXAM.md and any supplied API.md. Preserve immutable files. Do not inspect the private "
            b"repository, scorer, private assertions or previous results. In strict mode use the "
            b"approved command in PROMPT.md exactly once after finishing; do not edit afterward.\n"
        )
        payload["CLAUDE.md"] = b"@AGENTS.md\n"
        empty_destination(destination)
        for name, data in payload.items():
            if task.id.encode() in data:
                raise ValueError("anonymous material contains an internal task identifier")
            write_new(destination, name, data)

    def materialize_starter(
        self, task: BenchmarkTask, workspace: Path, context: BenchmarkContext,
    ) -> None:
        # Hub regenerates starters on startup. Reuse only an exact intact snapshot.
        # An altered workspace is an explicit conflict, never silently overwritten.
        if workspace.exists() and any(workspace.iterdir()):
            if not isinstance(task, BalatroTask):
                raise TypeError("incompatible task")
            from tempfile import TemporaryDirectory

            context.state_dir.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=context.state_dir, prefix="starter-check-") as folder:
                expected = Path(folder) / "expected"
                self.materialize_attempt(task, expected, context)
                names = {p.relative_to(expected).as_posix() for p in expected.rglob("*") if p.is_file()}
                actual = {p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file()}
                if names != actual or any(read_file(expected, n) != read_file(workspace, n) for n in names):
                    raise ValueError("existing starter differs; preserve it and choose a new state directory")
            return
        self.materialize_attempt(task, workspace, context)

    def public_task(self, task: BenchmarkTask) -> dict[str, Any]:
        return {**super().public_task(task), "fromScratch": False,
                "calibrationStatus": "unmeasured", "estimatedMinutesBasis": "author-planning-estimate"}

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        del task
        return ("Repair the supplied starter using only the public specification. Work inside the "
                "attempt directory and use only the approved scorer command. Private evaluator "
                "assets and prior results are outside the attempt boundary.")

    def sanitize_anonymous_result(self, value: Any) -> Any:
        return anonymous_result(value)

    def completion_report_fields(self) -> str:
        return ("anonymous run ID, submission hash, score, complete/pass status, failed or missing checks, "
                "runtime or source-review requirements, and files changed; no private engine logs")
