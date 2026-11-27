from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceKind(StrEnum):
    GITHUB = "github"
    MODRINTH = "modrinth"
    CURSEFORGE = "curseforge"


class RunMode(StrEnum):
    REVIEW = "review"
    YOLO = "yolo"


class RunStatus(StrEnum):
    CREATED = "created"
    HARVESTING = "harvesting"
    SYNTHESIZING = "synthesizing"
    VALIDATING = "validating"
    ACTION_REQUIRED = "action_required"
    AWAITING_REVIEW = "awaiting_review"
    PUBLISHING = "publishing"
    COMPLETE = "complete"
    FAILED = "failed"


class CandidateStatus(StrEnum):
    DISCOVERED = "discovered"
    EXTRACTED = "extracted"
    GENERATED = "generated"
    ACTION_REQUIRED = "action_required"
    REJECTED = "rejected"
    VALIDATED = "validated"
    APPROVED = "approved"
    PUBLISHED = "published"


class SourceProject(StrictModel):
    source: SourceKind
    external_id: str = Field(min_length=1)
    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    project_url: HttpUrl
    source_url: HttpUrl | None = None
    license_spdx: str | None = None
    immutable_ref: str | None = None


class HistoricalFix(StrictModel):
    id: str = Field(min_length=1)
    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    repository_url: HttpUrl
    license_spdx: str
    base_sha: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    fixed_sha: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    issue_text: str = Field(min_length=1, max_length=65_536)
    patch: str = Field(min_length=1, max_length=524_288)
    changed_files: tuple[str, ...] = Field(min_length=1, max_length=100)
    base_files: dict[str, str] = Field(default_factory=dict)
    fixed_files: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def source_context_is_safe_and_bounded(self) -> Self:
        _validate_source_files(self.base_files)
        _validate_source_files(self.fixed_files)
        if set(self.base_files) - set(self.changed_files) or set(self.fixed_files) - set(
            self.changed_files
        ):
            raise ValueError("source context must be limited to changed files")
        return self


class BehaviorCapsule(StrictModel):
    capsule_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    observed_symptoms: tuple[str, ...] = Field(min_length=1)
    expected_behaviors: tuple[str, ...] = Field(min_length=1)
    public_game_apis: tuple[str, ...] = ()
    compatibility_constraints: tuple[str, ...] = ()
    test_oracles: tuple[str, ...] = Field(min_length=1)


class CompositeCandidate(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    capsules: tuple[BehaviorCapsule, ...] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def capsules_share_game_and_are_unique(self) -> CompositeCandidate:
        if any(value.game_id != self.game_id for value in self.capsules):
            raise ValueError("composite capsules must share one game")
        identifiers = [value.capsule_id for value in self.capsules]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("composite capsules must be unique")
        return self


class SynthModule(StrictModel):
    path: str = Field(min_length=1)
    identifier: str = Field(min_length=1)
    loading: str = Field(min_length=1)


class SynthInput(StrictModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    description: str = Field(min_length=1)


class LegacySynthEntrypoint(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    module_identifier: str = Field(min_length=1)
    trigger: str = Field(min_length=1)
    inputs: tuple[SynthInput, ...]
    observable_outcomes: tuple[str, ...] = Field(min_length=1)


class LegacySynthInterfaceContract(StrictModel):
    """Reader for already-staged, unversioned interface snapshots."""

    game_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    project_name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    project_files: tuple[str, ...] = Field(min_length=1, max_length=512)
    modules: tuple[SynthModule, ...] = Field(min_length=1)
    entrypoints: tuple[LegacySynthEntrypoint, ...] = Field(min_length=1)
    capsule_entrypoints: dict[str, tuple[str, ...]] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def references_are_valid(self) -> Self:
        _validate_files(dict.fromkeys(self.project_files, "required"))
        if len(set(self.project_files)) != len(self.project_files):
            raise ValueError("interface project paths must be unique")
        module_ids = {module.identifier for module in self.modules}
        if len(module_ids) != len(self.modules):
            raise ValueError("interface module identifiers must be unique")
        if any(module.path not in self.project_files for module in self.modules):
            raise ValueError("interface module references an undeclared project file")
        entrypoint_ids = {entrypoint.id for entrypoint in self.entrypoints}
        if len(entrypoint_ids) != len(self.entrypoints):
            raise ValueError("interface entrypoint IDs must be unique")
        if any(entrypoint.module_identifier not in module_ids for entrypoint in self.entrypoints):
            raise ValueError("interface entrypoint references an unknown module")
        if any(not entries or not set(entries) <= entrypoint_ids
               for entries in self.capsule_entrypoints.values()):
            raise ValueError("interface capsule mapping references unknown or empty entrypoints")
        return self


class SynthEntrypoint(LegacySynthEntrypoint):
    signature: str = Field(
        min_length=1,
        description="Exact public callable method name/signature including ordered parameter types.",
    )
    return_type: str = Field(
        min_length=1,
        description="Exact language or CLR return type, shared by implementation and verifier.",
    )
    return_schema: str = Field(
        min_length=1,
        description="Complete return-value shape and meaning: field names/types, units, format and bounds. "
        "For strings specify the exact invariant serialization, not a vague log message.",
    )
    observation_channel: Literal["return-value", "game-state"] = Field(
        description="The agreed public observation channel; never undeclared static fields or logs.",
    )


_MINECRAFT_PLUGIN_YML = "src/main/resources/plugin.yml"
_MINECRAFT_API_VERSION = "1.21"
_MINECRAFT_FORBIDDEN_KEYS = ("depend", "softdepend", "libraries", "load")
_YAML_TOP_LEVEL = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$")
_VOID_TYPES = frozenset({"void", "system.void", "java.lang.void"})


def _plugin_yml_top_level(text: str) -> dict[str, str]:
    """Top-level scalar keys of a plugin.yml; nested values are kept as empty strings."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped or line[:1].isspace():
            continue
        match = _YAML_TOP_LEVEL.match(stripped)
        if match is None:
            continue
        values[match.group(1)] = match.group(2)
    return values


def _unquoted(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


class SynthInterfaceContract(LegacySynthInterfaceContract):
    """Versioned exact public loading and result ABI for new generation."""

    schema_version: Literal[2]
    loader_identity: str = Field(
        min_length=1,
        description="Exact public game/loader identity. For Stardew this is manifest.json UniqueID.",
    )
    metadata_files: dict[str, str] = Field(
        description="Exact serialized load metadata keyed by project-relative path, copied byte-for-byte "
        "by the fixed/base projects. For Stardew include complete manifest.json with UniqueID and EntryDll. "
        "Declarative metadata is allowed here; implementation code is not.",
    )
    entrypoints: tuple[SynthEntrypoint, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def exact_loading_metadata_is_valid(self) -> Self:
        _validate_files(self.metadata_files)
        if not set(self.metadata_files) <= set(self.project_files):
            raise ValueError("interface metadata references an undeclared project file")
        if self.game_id == "stardew-valley":
            try:
                manifest = json.loads(self.metadata_files["manifest.json"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Stardew interface requires serialized manifest.json") from error
            if not isinstance(manifest, dict) or manifest.get("UniqueID") != self.loader_identity:
                raise ValueError("Stardew manifest UniqueID must match loader_identity")
            entry_dll = manifest.get("EntryDll")
            if (not isinstance(entry_dll, str) or not entry_dll.endswith(".dll")
                    or PurePosixPath(entry_dll).name != entry_dll or "\\" in entry_dll):
                raise ValueError("Stardew manifest must declare one exact EntryDll filename")
            if any(entrypoint.observation_channel != "return-value" or
                   entrypoint.return_type.casefold() in {"void", "system.void"}
                   for entrypoint in self.entrypoints):
                raise ValueError("Stardew public API entrypoints must return observable values")
        if self.game_id == "minecraft":
            self._validate_minecraft_plugin_yml()
        if any(
            entrypoint.observation_channel == "return-value"
            and entrypoint.return_type.strip().casefold() in _VOID_TYPES
            for entrypoint in self.entrypoints
        ):
            raise ValueError("return-value entrypoints must not declare a void return type")
        return self

    def _validate_minecraft_plugin_yml(self) -> None:
        text = self.metadata_files.get(_MINECRAFT_PLUGIN_YML)
        if text is None:
            raise ValueError("Minecraft interface requires serialized src/main/resources/plugin.yml")
        values = _plugin_yml_top_level(text)
        if _unquoted(values.get("name", "")) != self.loader_identity:
            raise ValueError("Minecraft plugin.yml name must match loader_identity")
        main = _unquoted(values.get("main", ""))
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", main):
            raise ValueError("Minecraft plugin.yml must declare a fully qualified main class")
        main_path = "src/main/java/" + main.replace(".", "/") + ".java"
        if main_path not in self.project_files:
            raise ValueError("Minecraft plugin.yml main class must be a declared src/main/java file")
        if _unquoted(values.get("api-version", "")) != _MINECRAFT_API_VERSION:
            raise ValueError("Minecraft plugin.yml api-version must be '1.21'")
        forbidden = [key for key in _MINECRAFT_FORBIDDEN_KEYS if key in values]
        if forbidden:
            raise ValueError(
                "Minecraft plugin.yml must not declare " + ", ".join(forbidden)
            )


class GeneratedProject(StrictModel):
    project_name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    files: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def files_are_safe_and_bounded(self) -> Self:
        _validate_files(self.files)
        return self


class DefectReport(StrictModel):
    capsule_id: str
    symptom: str = Field(min_length=1)
    affected_files: tuple[str, ...] = Field(min_length=1)


class DefectInjection(StrictModel):
    capsule_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    symptom: str = Field(min_length=1)
    replacements: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def replacement_files_are_safe(self) -> Self:
        _validate_files(self.replacements)
        return self


class DefectInjections(StrictModel):
    injections: tuple[DefectInjection, ...] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def capsule_ids_are_unique(self) -> Self:
        identities = [injection.capsule_id for injection in self.injections]
        if len(set(identities)) != len(identities):
            raise ValueError("defect injection capsule IDs must be unique")
        return self


class DefectiveProject(StrictModel):
    files: dict[str, str] = Field(min_length=1)
    defects: tuple[DefectReport, ...] = Field(min_length=2, max_length=7)
    ablations: dict[str, dict[str, str]] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def files_are_safe_and_defects_are_unique(self) -> Self:
        _validate_files(self.files)
        identifiers = [defect.capsule_id for defect in self.defects]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("defect capsule IDs must be unique")
        if set(self.ablations) != set(identifiers):
            raise ValueError("one single-defect ablation is required per capsule")
        for files in self.ablations.values():
            _validate_files(files)
        return self


class VerifierBundle(StrictModel):
    files: dict[str, str] = Field(min_length=1)
    case_ids: tuple[str, ...] = Field(
        min_length=1,
        description="All real-engine case names, including FAIL_TO_PASS and unaffected PASS_TO_PASS cases.",
    )
    capsule_cases: dict[str, tuple[str, ...]] = Field(
        min_length=1,
        description="Disjoint per-capsule FAIL_TO_PASS names only: each fails with that defect and passes "
        "when repaired. Normal inputs, sentinels and other PASS_TO_PASS cases belong only in case_ids.",
    )

    @model_validator(mode="after")
    def files_and_case_mapping_are_valid(self) -> Self:
        _validate_files(self.files)
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("verifier case IDs must be unique")
        known = set(self.case_ids)
        if any(not cases or not set(cases) <= known for cases in self.capsule_cases.values()):
            raise ValueError("capsule case mapping references unknown or empty cases")
        return self


class AuthoredPrompt(StrictModel):
    markdown: str = Field(min_length=1)


class ReviewDecision(StrictModel):
    approved: bool
    leakage_findings: tuple[str, ...] = ()
    contract_findings: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)


class ValidationCheck(StrictModel):
    id: str
    status: Literal["passed", "failed", "unavailable"]
    message: str
    # Structured engine evidence for feedback-driven repair. Values hold only
    # booleans, assertion counts, and case IDs the model itself authored, so
    # they add no leakage surface. All optional: older validation.json files
    # and unavailable checks omit them.
    observed_complete: bool | None = None
    observed_passed: bool | None = None
    observed_counts: tuple[int, int] | None = None
    expected_failing_cases: tuple[str, ...] | None = None
    observed_failing_cases: tuple[str, ...] | None = None
    observed_case_ids: tuple[str, ...] | None = None
    # Distinct engine failure messages from the model-authored suite's own
    # cases (truncated); shown only to the verifier author during repair.
    observed_messages: tuple[str, ...] | None = None


class ValidationReport(StrictModel):
    candidate_id: str
    complete: bool
    passed: bool
    base_failed: bool
    gold_passed: bool
    engine_backed: bool
    checks: tuple[ValidationCheck, ...] = ()

    @model_validator(mode="after")
    def cannot_pass_incomplete(self) -> ValidationReport:
        if self.passed and (
            not self.complete
            or not self.base_failed
            or not self.gold_passed
            or not self.engine_backed
        ):
            raise ValueError("a passing validation must be complete and engine-backed")
        return self


class CleanRoomManifest(StrictModel):
    schema_version: Literal[1] = 1
    candidate_id: str
    game_id: str
    synthetic: Literal[True] = True
    license: Literal["Apache-2.0"] = "Apache-2.0"
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    base_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fixed_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PublicationRecord(StrictModel):
    candidate_id: str
    task_key: str
    catalog_version: str
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SynthesisBundle(StrictModel):
    candidate: CompositeCandidate
    fixed: GeneratedProject
    base: DefectiveProject
    verifier: VerifierBundle
    prompt: AuthoredPrompt
    review: ReviewDecision
    provenance: tuple[HistoricalFix, ...] = Field(min_length=2, max_length=7)
    # Older staged bundles remain readable; every new generation supplies this contract.
    interface_contract: SynthInterfaceContract | LegacySynthInterfaceContract | None = None

    @model_validator(mode="after")
    def provenance_matches_candidate(self) -> Self:
        if len(self.provenance) != len(self.candidate.capsules):
            raise ValueError("one private provenance record is required per capsule")
        if any(fix.game_id != self.candidate.game_id for fix in self.provenance):
            raise ValueError("bundle provenance must share the candidate game")
        capsule_ids = {capsule.capsule_id for capsule in self.candidate.capsules}
        if self.interface_contract is not None:
            contract = self.interface_contract
            if contract.game_id != self.candidate.game_id:
                raise ValueError("interface contract must share the candidate game")
            if set(contract.capsule_entrypoints) != capsule_ids:
                raise ValueError("interface mappings must cover every candidate capsule")
            if contract.project_name != self.fixed.project_name:
                raise ValueError("fixed project changed the shared interface project name")
            if not set(contract.project_files) <= set(self.fixed.files):
                raise ValueError("fixed project is missing a shared interface file")
            if isinstance(contract, SynthInterfaceContract):
                for path, content in contract.metadata_files.items():
                    if any(tree.get(path) != content for tree in (
                        self.fixed.files, self.base.files, *self.base.ablations.values()
                    )):
                        raise ValueError("generated project changed exact shared load metadata")
        if {defect.capsule_id for defect in self.base.defects} != capsule_ids:
            raise ValueError("synthetic defects must cover every candidate capsule")
        fixed_paths = set(self.fixed.files)
        if set(self.base.files) != fixed_paths or any(
            set(files) != fixed_paths for files in self.base.ablations.values()
        ):
            raise ValueError("base, fixed, and ablation trees must contain identical paths")
        if any(
            path not in fixed_paths
            for defect in self.base.defects
            for path in defect.affected_files
        ):
            raise ValueError("synthetic defect references a missing project file")
        if set(self.verifier.capsule_cases) != capsule_ids:
            raise ValueError("verifier mappings must cover every candidate capsule")
        observed: set[str] = set()
        for cases in self.verifier.capsule_cases.values():
            if observed.intersection(cases):
                raise ValueError("defect-specific verifier case mappings must not overlap")
            observed.update(cases)
        return self


def _validate_files(files: dict[str, str]) -> None:
    if len(files) > 512:
        raise ValueError("generated project contains too many files")
    total = 0
    for raw, content in files.items():
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or raw != path.as_posix():
            raise ValueError("generated file path is unsafe")
        if not raw or not content:
            raise ValueError("generated file path and content must be non-empty")
        total += len(content.encode("utf-8"))
    if total > 4 * 1024 * 1024:
        raise ValueError("generated project exceeds the 4 MiB source limit")


def _validate_source_files(files: dict[str, str]) -> None:
    total = 0
    for raw, content in files.items():
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or raw != path.as_posix():
            raise ValueError("source context file path is unsafe")
        total += len(content.encode("utf-8"))
    if total > 512 * 1024:
        raise ValueError("source context exceeds the 512 KiB limit")
