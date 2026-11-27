"""Records of the project-history authoring mode.

A history candidate is one landed upstream fix: the repository at the fix's
first parent is the starter, the landed fix is the reference. Only the public
exam and the hidden live-server suite are model-authored; everything else is
derived mechanically from the repository and verified on the real engine.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, HttpUrl, field_validator, model_validator

from ..models import StrictModel

_SHA = r"^[0-9a-f]{40}$"
_CASE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.'()/_:-]{2,119}$")
_JAVA_RELATIVE = re.compile(r"^[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*\.java$")
_SEED_RELATIVE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")


def _relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError("paths must be normalized relative POSIX paths")
    return value


class HistoryFix(StrictModel):
    """One landed upstream fix found while walking a repository's history."""

    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    repository_url: HttpUrl
    license_spdx: str
    base_sha: str = Field(pattern=_SHA)
    fixed_sha: str = Field(pattern=_SHA)
    origin: Literal["pull", "commit"]
    pull_number: int | None = None
    title: str = Field(min_length=1, max_length=512)
    description: str = Field(default="", max_length=65_536)
    commit_message: str = Field(default="", max_length=65_536)
    changed_files: tuple[str, ...] = Field(min_length=1, max_length=100)
    patch: str = Field(min_length=1, max_length=512 * 1024)
    changed_lines: int = Field(ge=1)

    @field_validator("changed_files")
    @classmethod
    def relative_files(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            _relative(item)
        return value

    @model_validator(mode="after")
    def distinct_revisions(self) -> Self:
        if self.base_sha == self.fixed_sha:
            raise ValueError("a history fix needs distinct base and fixed revisions")
        if self.origin == "pull" and self.pull_number is None:
            raise ValueError("a pull-request fix records its number")
        return self

    @property
    def key(self) -> str:
        """Same identity as the clean-room harvest, so used fixes are shared."""
        return f"{str(self.repository_url).rstrip('/').casefold()}@{self.fixed_sha}"

    @property
    def candidate_id(self) -> str:
        owner, name = self.repository.split("/", 1)
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:32] or "repo"
        return f"{slug}-{self.fixed_sha[:10]}"


class BuildProbe(StrictModel):
    """Mechanically established build facts of one candidate."""

    tool: Literal["gradle", "maven"]
    wrapper: bool
    tool_version: str | None = None
    module: str | None = None
    assemble: str
    test: str | None
    artifact: str
    java_release: Literal[17, 21] = 21
    frozen_paths: tuple[str, ...]
    plugin_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    license_file: str
    paper_api: str = Field(min_length=1)
    unit_cases: tuple[str, ...] = ()
    base_seconds: float = 0.0
    fixed_seconds: float = 0.0

    @field_validator("artifact", "license_file")
    @classmethod
    def relative_paths(cls, value: str) -> str:
        return _relative(value)

    @model_validator(mode="after")
    def unit_cases_follow_test_task(self) -> Self:
        if (self.test is None) != (not self.unit_cases):
            raise ValueError("unit_cases exist exactly when the build has a test task")
        return self


class TriageDecision(StrictModel):
    """Whether the fixed behaviour can be observed on a headless server."""

    reproducible: bool
    reason: str = Field(min_length=1, max_length=2000)
    entry_points: tuple[str, ...] = Field(default=(), max_length=12)
    observation: str = Field(default="", max_length=2000)
    target_behaviours: tuple[str, ...] = Field(default=(), max_length=8)
    preserved_behaviours: tuple[str, ...] = Field(default=(), max_length=8)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class CaseContract(StrictModel):
    """One live-server case and the public obligation it is evidence for."""

    case: str
    role: Literal["target", "preserved", "sentinel"]
    public_report: str = Field(min_length=1, max_length=300)

    @field_validator("case")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if _CASE_NAME.fullmatch(value) is None or '"' in value or "\\" in value:
            raise ValueError("case names are 3-120 printable characters without quotes")
        return value


class AuthoredTask(StrictModel):
    """Everything the author role writes for one candidate."""

    title: str = Field(min_length=8, max_length=120)
    summary: str = Field(min_length=20, max_length=600)
    exam: str = Field(min_length=200, max_length=12_000)
    suite: dict[str, str] = Field(min_length=1, max_length=8)
    seed: dict[str, str] = Field(default_factory=dict, max_length=16)
    cases: tuple[CaseContract, ...] = Field(min_length=3, max_length=16)
    notes: str = Field(min_length=100, max_length=12_000)

    @field_validator("suite")
    @classmethod
    def suite_paths(cls, value: dict[str, str]) -> dict[str, str]:
        for path, text in value.items():
            if _JAVA_RELATIVE.fullmatch(path) is None:
                raise ValueError("suite files are relative .java paths")
            if len(text) > 200_000:
                raise ValueError("suite file is too large")
        return value

    @field_validator("seed")
    @classmethod
    def seed_paths(cls, value: dict[str, str]) -> dict[str, str]:
        for path, text in value.items():
            if _SEED_RELATIVE.fullmatch(path) is None or PurePosixPath(path).suffix in {".jar", ".class"}:
                raise ValueError("seed files are relative data files below the plugin data folder")
            if len(text) > 200_000:
                raise ValueError("seed file is too large")
        return value

    @model_validator(mode="after")
    def case_roles(self) -> Self:
        names = [item.case for item in self.cases]
        if len(set(names)) != len(names):
            raise ValueError("case names must be unique")
        roles = [item.role for item in self.cases]
        if roles.count("sentinel") != 1:
            raise ValueError("exactly one sentinel case proves the plugin is enabled")
        if "target" not in roles:
            raise ValueError("at least one target case is required")
        return self

    @property
    def server_cases(self) -> tuple[str, ...]:
        return tuple(item.case for item in self.cases)

    @property
    def target_cases(self) -> frozenset[str]:
        return frozenset(item.case for item in self.cases if item.role == "target")


class SourcePatch(StrictModel):
    """Full replacement contents for files below the plugin root."""

    files: dict[str, str] = Field(min_length=1, max_length=40)
    rationale: str = Field(min_length=10, max_length=4000)

    @field_validator("files")
    @classmethod
    def main_sources_only(cls, value: dict[str, str]) -> dict[str, str]:
        for path, text in value.items():
            _relative(path)
            parts = PurePosixPath(path).parts
            if "src" not in parts or "test" in parts or not path.endswith((".java", ".yml", ".yaml")):
                raise ValueError("control patches change main sources and resources only")
            if len(text) > 400_000:
                raise ValueError("control file is too large")
        return value


class ReviewVerdict(StrictModel):
    approved: bool
    findings: tuple[str, ...] = Field(default=(), max_length=20)
    derivable_from_exam: bool
    unpublished_conventions: tuple[str, ...] = Field(default=(), max_length=20)
