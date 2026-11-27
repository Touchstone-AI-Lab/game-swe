"""Game-owned transport to the explicitly prepared, reviewed Linux host."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from . import container_host as host
from .catalog import BalatroTask
from .container_builder import BalatroContainerBuilder
from .linux_bridge import serial_lock
from .results import incomplete


class BalatroContainerEvaluator:
    def __init__(self, context: BenchmarkContext) -> None:
        self.context = context

    def runtime_status(self) -> dict[str, Any]:
        # Core supplies the authoritative prepared artifact to evaluate(). No DB lookup,
        # authentication, build or game startup is permitted during this readiness view.
        return {"available": False, "scope": "source-reviewed-linux-container",
                "reason": "A prepared core-supplied runtime and reviewed source are required"}

    def evaluate(
        self, submission: Path, task: Any, profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile != "full":
            return incomplete("unsupported_profile")
        if not isinstance(task, BalatroTask):
            return incomplete("invalid_submission")
        if not runtimes or set(runtimes) != {host.RUNTIME_KEY}:
            return incomplete("runtime_action_required")
        try:
            artifact = runtimes[host.RUNTIME_KEY]
            from .container_operator import runtime_spec

            builder = BalatroContainerBuilder(self.context)
            if not builder.verify(runtime_spec(self.context), artifact)["available"]:
                return incomplete("runtime_action_required")
            root, record = host.load_record(artifact)
            with serial_lock(root / "host-serial"):
                from .linux_process import game_process_guard

                game_process_guard(None)
                work = self.context.state_dir / "container-operations" / uuid.uuid4().hex
                return host.run_worker(
                    record["image_id"], {"operation": "evaluate", "image": record["image_id"],
                        "context": self.context.model_dump(mode="json"), "root": str(root),
                        "native": record["native"], "submission": str(submission.resolve()),
                        "task": task.id}, work,
                    readonly=(self.context.pack_root, root, submission.resolve()),
                    writable=(root / "operator-state", root / "plugin-cache", work),
                )
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration,
                subprocess.SubprocessError):
            return incomplete("environment_failure")
