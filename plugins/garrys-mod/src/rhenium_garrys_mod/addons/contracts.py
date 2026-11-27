from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from rhenium.core.catalog import CatalogModel

_PRIVATE_IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9_.:-]{0,127}$"
_NAMESPACE_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
_ADDON_NAME_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"


class GmodPackRuntimeContract(CatalogModel):
    """Immutable Dedicated Server identity required by this benchmark pack."""

    app_id: Literal[4020]
    branch: Literal["stable"]
    build_id: str = Field(pattern=r"^[0-9]+$")
    platform: Literal["windows-x86_64"]
    # A separately pinned native Linux installation; old Windows-only catalogs
    # remain valid and cannot silently opt into a different engine platform.
    linux_build_id: str | None = Field(default=None, pattern=r"^[0-9]+$")


class GmodPublicExamContract(CatalogModel):
    """Exact pack-owned public exam and its semantic anchors."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    interfaces: list[str] = Field(min_length=1)
    contract_evidence: list[str] = Field(min_length=1)
    acceptance_evidence: list[str] = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def path_is_safe(cls, value: str) -> str:
        return _normalized_relative_posix(value)

    @field_validator("interfaces", "contract_evidence", "acceptance_evidence")
    @classmethod
    def evidence_is_unique_and_safe(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("public exam evidence entries must be unique")
        if any(
            not entry.strip()
            or len(entry) > 500
            or any(ord(character) < 32 and character != "\t" for character in entry)
            for entry in value
        ):
            raise ValueError("public exam evidence entries must be non-blank and control-free")
        return value


def _normalized_relative_posix(value: str) -> str:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError("GMod private paths must be normalized relative POSIX paths")
    return value


def _unique_case_names(value: list[str]) -> list[str]:
    if len(set(value)) != len(value):
        raise ValueError("GMod case names must be unique within a case group")
    if any(
        not name.strip() or len(name) > 160 or any(ord(character) < 32 for character in name)
        for name in value
    ):
        raise ValueError("GMod case names must be non-blank, control-free, and at most 160 characters")
    return value


class GmodEvaluationContract(CatalogModel):
    """Private Lua suite ownership and exact case grouping for one task."""

    hidden_suite: str
    hidden_cases: list[str] = Field(min_length=1)
    integration_suite: str
    integration_cases: list[str] = Field(min_length=1)
    lifecycle_cases: list[str] = Field(min_length=1)
    traceability: str | None = None
    mutations: str
    suite_timeout_seconds: float = Field(gt=0, le=60)

    @field_validator("hidden_suite", "integration_suite", "traceability", "mutations")
    @classmethod
    def suite_paths_are_safe(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalized_relative_posix(value)

    @field_validator("hidden_cases", "integration_cases", "lifecycle_cases")
    @classmethod
    def cases_are_unique_and_non_blank(cls, value: list[str]) -> list[str]:
        return _unique_case_names(value)

    @model_validator(mode="after")
    def integration_groups_are_disjoint(self) -> Self:
        overlap = set(self.integration_cases) & set(self.lifecycle_cases)
        if overlap:
            raise ValueError("integration and lifecycle case groups must not overlap")
        return self

    @property
    def integration_case_order(self) -> tuple[str, ...]:
        return tuple((*self.integration_cases, *self.lifecycle_cases))

    def private_paths(self) -> tuple[str, ...]:
        optional = (self.traceability,) if self.traceability is not None else ()
        return (self.hidden_suite, self.integration_suite, self.mutations, *optional)


class GmodSourceContract(CatalogModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def path_is_safe(cls, value: str) -> str:
        return _normalized_relative_posix(value)


class GmodSourceRecord(CatalogModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    task_id: str = Field(alias="taskId", pattern=r"^[a-z0-9][a-z0-9-]*$")
    task_version: str = Field(alias="taskVersion", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    origin_type: Literal["workshop-functional-evidence"] = Field(alias="originType")
    workshop_id: str = Field(alias="workshopId", pattern=r"^[0-9]+$")
    url: HttpUrl
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=200)
    accessed_at: str = Field(alias="accessedAt", pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    license: str = Field(min_length=1, max_length=100)
    license_handling: str = Field(alias="licenseHandling", min_length=1, max_length=500)
    code_copied: Literal[False] = Field(alias="codeCopied")
    assets_copied: Literal[False] = Field(alias="assetsCopied")
    capabilities_observed: list[str] = Field(alias="capabilitiesObserved", min_length=1)
    benchmark_capabilities: list[str] = Field(alias="benchmarkCapabilities", min_length=1)

    @field_validator("capabilities_observed", "benchmark_capabilities")
    @classmethod
    def capabilities_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not item.strip() for item in value):
            raise ValueError("source capabilities must be unique and non-blank")
        return value


class GmodTraceCase(CatalogModel):
    name: str = Field(min_length=1, max_length=160)
    classification: Literal["A", "B", "C"]
    clauses: list[str] = Field(min_length=1)

    @field_validator("clauses")
    @classmethod
    def clauses_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("traceability clauses must be unique")
        return value


class GmodCaseMappings(CatalogModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    hidden_behavior: list[GmodTraceCase] = Field(alias="hidden-behavior", min_length=1)
    gmod_integration: list[GmodTraceCase] = Field(alias="gmod-integration", min_length=1)
    lifecycle_cleanup: list[GmodTraceCase] = Field(alias="lifecycle-cleanup", min_length=1)
    dedicated_server: list[GmodTraceCase] = Field(alias="dedicated-server", min_length=1)


class GmodTraceability(CatalogModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    task_id: str = Field(alias="taskId")
    task_version: str = Field(alias="taskVersion")
    case_mappings: GmodCaseMappings = Field(alias="caseMappings")
    api_coverage: dict[str, list[str]] = Field(alias="apiCoverage", min_length=1)
    acceptance_coverage: dict[str, list[str]] = Field(alias="acceptanceCoverage", min_length=1)
    required_public_tokens: list[str] = Field(alias="requiredPublicTokens", min_length=1)

    @field_validator("required_public_tokens")
    @classmethod
    def tokens_are_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not token for token in value):
            raise ValueError("required public tokens must be unique and non-empty")
        return value


class GmodServerSuiteContract(CatalogModel):
    """Trusted Dedicated Server protocol and installation contract for one task."""

    task_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    addon_manifest: str
    lua_entry: str
    suite_id: str = Field(pattern=_PRIVATE_IDENTIFIER_PATTERN)
    runtime_namespace: str = Field(pattern=_NAMESPACE_PATTERN)
    submission_addon_name: str = Field(pattern=_ADDON_NAME_PATTERN)
    private_suite_addon_name: str = Field(pattern=_ADDON_NAME_PATTERN)
    expected_cases: list[str] = Field(min_length=1)
    phases: list[Literal["A", "B"]] = Field(min_length=1, max_length=2)
    timeout_seconds: float = Field(gt=0, le=600)

    @field_validator("addon_manifest", "lua_entry")
    @classmethod
    def asset_paths_are_safe(cls, value: str) -> str:
        return _normalized_relative_posix(value)

    @field_validator("expected_cases")
    @classmethod
    def cases_are_unique_and_non_blank(cls, value: list[str]) -> list[str]:
        return _unique_case_names(value)

    @model_validator(mode="after")
    def protocol_is_unambiguous(self) -> Self:
        if self.phases not in (["A"], ["A", "B"]):
            raise ValueError("GMod server phases must be exactly A or A followed by B")
        if self.submission_addon_name == self.private_suite_addon_name:
            raise ValueError("submission and private suite addon names must differ")
        return self

    def private_paths(self) -> tuple[str, ...]:
        return (self.addon_manifest, self.lua_entry)


@dataclass(frozen=True)
class GmodTaskRuntimeSpec:
    """Resolved, validated runtime input consumed by the production runner."""

    task_id: str
    task_version: str
    addon_manifest: Path
    lua_entry: Path
    suite_id: str
    runtime_namespace: str
    submission_addon_name: str
    private_suite_addon_name: str
    expected_cases: tuple[str, ...]
    phases: tuple[str, ...]
    timeout_seconds: float

    @property
    def data_directory(self) -> PurePosixPath:
        return PurePosixPath("rhenium_runtime") / self.runtime_namespace

    def state_path(self, run_id: str) -> PurePosixPath:
        return self.data_directory / f"{run_id}-state.json"

    def evidence_path(self, run_id: str, phase: str) -> PurePosixPath:
        return self.data_directory / f"{run_id}-{phase.lower()}-evidence.json"


def resolve_runtime_spec(
    dataset_root: Path,
    task_id: str,
    task_version: str,
    contract: GmodServerSuiteContract,
) -> GmodTaskRuntimeSpec:
    root = dataset_root.resolve()
    prefix = PurePosixPath("private") / "tasks" / task_id

    def resolve_asset(relative: str) -> Path:
        logical = PurePosixPath(relative)
        if not logical.is_relative_to(prefix):
            raise ValueError(f"private asset for {task_id} belongs to another task: {relative}")
        candidate = (root / Path(*logical.parts)).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError(f"private asset is unavailable for {task_id}: {relative}")
        return candidate

    return GmodTaskRuntimeSpec(
        task_id=task_id,
        task_version=task_version,
        addon_manifest=resolve_asset(contract.addon_manifest),
        lua_entry=resolve_asset(contract.lua_entry),
        suite_id=contract.suite_id,
        runtime_namespace=contract.runtime_namespace,
        submission_addon_name=contract.submission_addon_name,
        private_suite_addon_name=contract.private_suite_addon_name,
        expected_cases=tuple(contract.expected_cases),
        phases=tuple(contract.phases),
        timeout_seconds=contract.timeout_seconds,
    )
