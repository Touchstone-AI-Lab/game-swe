from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rhenium.core.catalog import BenchmarkTask
from rhenium.core.plugin import BenchmarkContext

from .catalog import GmodTask


class GmodAddonSupport:
    """Pack-specific public material helpers owned by the unified plugin."""

    @staticmethod
    def _gmod_task(task: BenchmarkTask) -> GmodTask:
        if not isinstance(task, GmodTask):
            raise TypeError("GMod plugin received a non-GMod task")
        return task

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        gmod_task = self._gmod_task(task)
        del language
        if not gmod_task.authored_prompt:
            raise ValueError("GMod task is not bound to its canonical public exam")
        return gmod_task.authored_prompt.strip()

    def materialize_starter(
        self,
        task: BenchmarkTask,
        workspace: Path,
        context: BenchmarkContext,
    ) -> None:
        gmod_task = self._gmod_task(task)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        marker = {
            "difficulty": task.difficulty,
            "submission": ".",
            "fromScratch": True,
            "language": "GLua/Lua 5.1",
        }
        (workspace / "task.json").write_text(
            json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (workspace / "TASK.md").write_text(
            gmod_task.authored_prompt.rstrip() + "\n", encoding="utf-8"
        )

    def materialize_attempt(
        self,
        task: BenchmarkTask,
        destination: Path,
        context: BenchmarkContext,
    ) -> None:
        gmod_task = self._gmod_task(task)
        (destination / "EXAM.md").write_text(
            gmod_task.authored_prompt.rstrip() + "\n", encoding="utf-8"
        )
        for name in ("AGENTS.md", "CLAUDE.md"):
            source = context.project_root / name
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"canonical attempt guidance is missing: {name}")
            shutil.copy2(source, destination / name)

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        self._gmod_task(task)
        return (
            "You are the model under test in a Garry's Mod server engineering benchmark. "
            "Implement only the public addon contract in the empty attempt. Use the Lua 5.1 "
            "compatible subset (no GLua-only operators). Keep any plain-Lua core, service, or "
            "state machine independent of GMod globals; keep authority on the server and derive "
            "player and entity identity only from trusted server objects. Private Lua suites, "
            "Dedicated Server assertions, references, and mutations are not visible to you."
        )

    def public_task(self, task: BenchmarkTask) -> dict[str, object]:
        gmod_task = self._gmod_task(task)
        return {
            "difficulty": task.difficulty,
            "title": task.title.model_dump(mode="json"),
            "summary": task.summary.model_dump(mode="json"),
            "domains": task.domains,
            "estimatedMinutes": task.estimated_minutes,
            "fromScratch": True,
            "taskVersion": gmod_task.task_version,
            "submissionLanguage": "GLua/Lua 5.1",
        }

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or skipped checks, real GMod "
            "Dedicated Server Phase A/B status, and files created"
        )

    def sanitize_anonymous_result(self, value: Any) -> Any:
        omitted = {
            "analysis",
            "command",
            "details",
            "ended_at_utc",
            "error",
            "output_tail",
            "payload",
            "process_id",
            "run_id",
            "runtime_log",
            "started_at_utc",
            "submission_hash",
        }
        private_fragments = ("evidence", "marker", "nonce")

        def sanitize(item: Any) -> Any:
            if isinstance(item, dict):
                return {
                    field: sanitize(field_value)
                    for field, field_value in item.items()
                    if field not in omitted
                    and not any(fragment in field.casefold() for fragment in private_fragments)
                }
            if isinstance(item, list):
                return [sanitize(entry) for entry in item]
            if isinstance(item, tuple):
                return tuple(sanitize(entry) for entry in item)
            return item

        return sanitize(value)
