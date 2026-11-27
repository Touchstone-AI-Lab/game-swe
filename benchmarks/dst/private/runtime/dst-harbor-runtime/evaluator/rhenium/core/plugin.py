from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .catalog import BenchmarkCatalog, BenchmarkTask
from .runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec


class PluginModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PluginDescriptor(PluginModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    capabilities: tuple[str, ...] = ()
    internal: bool = False

    @model_validator(mode="after")
    def capabilities_are_normalized_and_unique(self) -> PluginDescriptor:
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("plugin capabilities must be unique")
        if any(not value or value.strip() != value for value in self.capabilities):
            raise ValueError("plugin capabilities must be non-blank and normalized")
        return self


class EvaluationProfile(PluginModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    label: str = Field(min_length=1)
    complete_eligible: bool


class BenchmarkContext(PluginModel):
    project_root: Path
    pack_root: Path
    state_dir: Path
    cache_dir: Path


class EvaluationBackend(Protocol):
    """The evaluator contract understood by the game-neutral Hub."""

    def evaluate(
        self,
        submission: Path,
        task: Any,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]: ...

    def runtime_status(self) -> dict[str, Any]: ...


def localized(value: object, language: str) -> Any:
    key = "zh" if language.lower().startswith("zh") else "en"
    if isinstance(value, dict):
        return value.get(key, value.get("en"))
    return getattr(value, key, getattr(value, "en", value))


class BenchmarkPlugin(ABC):
    """Extension point for one game's catalogs, prompts, tools, and evaluator."""

    descriptor: PluginDescriptor

    @property
    def id(self) -> str:
        return self.descriptor.id

    @property
    def game_id(self) -> str:
        return self.descriptor.game_id

    @abstractmethod
    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        """Load and validate a plugin-specific catalog and its private assets."""

    @abstractmethod
    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        """Create an evaluator bound to one benchmark pack."""

    def create_runtime_builder(
        self,
        context: BenchmarkContext,
        spec: RuntimeSpec,
    ) -> RuntimeBuilder | None:
        del context, spec
        return None

    def evaluation_profiles(self, task: BenchmarkTask) -> tuple[EvaluationProfile, ...]:
        del task
        return (
            EvaluationProfile(id="core", label="Core checks", complete_eligible=False),
            EvaluationProfile(id="full", label="Full evaluation", complete_eligible=True),
        )

    def default_profile(self, task: BenchmarkTask) -> str:
        del task
        return "full"

    def task_prompt(self, task: BenchmarkTask, language: str = "en") -> str:
        title = str(localized(task.title, language))
        brief = str(localized(task.brief, language))
        requirements = list(localized(task.requirements, language) or [])
        api_usage = list(localized(task.api_usage, language) or [])
        acceptance = list(localized(task.acceptance, language) or [])
        delivery_heading = "必须交付" if language == "zh" else "Required files"
        requirement_heading = "实现要求" if language == "zh" else "Implementation requirements"
        api_heading = "游戏 API 使用合同" if language == "zh" else "Game API usage contract"
        acceptance_heading = "验收标准" if language == "zh" else "Acceptance criteria"
        lines = [
            f"# {title}",
            "",
            brief,
            "",
            f"## {delivery_heading}",
            "",
            "```text",
            *task.required_files,
            "```",
            "",
            f"## {requirement_heading}",
            "",
        ]
        lines.extend(f"{index}. {value}" for index, value in enumerate(requirements, 1))
        lines.extend(["", f"## {api_heading}", ""])
        lines.extend(f"- {value}" for value in api_usage)
        lines.extend(["", f"## {acceptance_heading}", ""])
        lines.extend(f"- {value}" for value in acceptance)
        return "\n".join(lines).strip()

    def materialize_starter(
        self,
        task: BenchmarkTask,
        workspace: Path,
        context: BenchmarkContext,
    ) -> None:
        del context
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        marker = {
            "difficulty": task.difficulty,
            "submission": ".",
            "fromScratch": True,
        }
        (workspace / "task.json").write_text(
            json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (workspace / "TASK.md").write_text(self.task_prompt(task) + "\n", encoding="utf-8")
        (workspace / "TASK.zh-CN.md").write_text(
            self.task_prompt(task, language="zh") + "\n", encoding="utf-8"
        )

    def materialize_attempt(
        self,
        task: BenchmarkTask,
        destination: Path,
        context: BenchmarkContext,
    ) -> None:
        del context
        (destination / "EXAM.md").write_text(
            self.task_prompt(task, language="zh") + "\n", encoding="utf-8"
        )
        (destination / "AGENTS.md").write_text(
            "# Rhenium benchmark agent guidance\n\n"
            "Work only inside this attempt directory. Do not inspect the private benchmark "
            "repository, evaluator, private assertions, prior attempts, or state database. "
            "Implement the public contract in EXAM.md from scratch. In strict mode, run the "
            "approved scorer exactly once after implementation and do not edit afterward.\n",
            encoding="utf-8",
        )
        (destination / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")

    def completion_report_fields(self) -> str:
        return (
            "anonymous run ID, score, pass/fail status, failed or skipped checks, runtime status, "
            "and files created"
        )

    def sanitize_anonymous_result(self, value: Any) -> Any:
        """Remove plugin-private diagnostics before the Hub applies identity redaction."""
        return value

    def public_task(self, task: BenchmarkTask) -> dict[str, Any]:
        return {
            "difficulty": task.difficulty,
            "title": task.title.model_dump(mode="json"),
            "summary": task.summary.model_dump(mode="json"),
            "domains": task.domains,
            "estimatedMinutes": task.estimated_minutes,
            "fromScratch": True,
        }

    def agent_system_prompt(self, task: BenchmarkTask) -> str:
        del task
        return (
            "You are the model under test in a game-engineering implementation benchmark. "
            "The workspace contains only the public task contract and an empty starter. Build the "
            "requested project from scratch, implement every required file, and verify your work "
            "with public tools available in the workspace. You cannot see private evaluator assets."
        )

    def agent_environment(self, task: BenchmarkTask) -> dict[str, str]:
        del task
        return {}
