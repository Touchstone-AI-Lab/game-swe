from __future__ import annotations

import hashlib
import json
import os
import stat
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .evaluation import normalize_evaluation


class HostModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationSecurityMode(StrEnum):
    HONEST = "honest"
    UNTRUSTED = "untrusted"


class EvaluationHostDescriptor(HostModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    capabilities: tuple[str, ...] = ()


class EvaluationHostCapability(HostModel):
    available: bool
    disposable: bool
    platform: str = Field(min_length=1)
    reason: str = ""


class HostSecurityPolicy(HostModel):
    network: str = Field(default="none", pattern=r"^none$")
    credential_inventory: tuple[str, ...] = ()
    inherited_environment: tuple[str, ...] = ()
    writable_paths: tuple[str, ...] = (
        "/rhenium/output",
        "/rhenium/state",
        "/rhenium/tmp",
    )
    runtime_read_only: bool = True
    benchmark_read_only: bool = True
    submission_read_only: bool = True
    vcpus: int = Field(default=4, ge=1, le=64)
    memory_mib: int = Field(default=8192, ge=256)
    writable_disk_mib: int = Field(default=4096, ge=64)
    maximum_processes: int = Field(default=64, ge=1, le=4096)
    maximum_open_files: int = Field(default=256, ge=16, le=65_536)
    timeout_seconds: int = Field(default=900, ge=1)
    maximum_result_bytes: int = Field(default=1_048_576, ge=1024, le=16_777_216)
    maximum_submission_bytes: int = Field(default=268_435_456, ge=1024)
    maximum_submission_files: int = Field(default=10_000, ge=1)

    @model_validator(mode="after")
    def security_invariants_are_strict(self) -> HostSecurityPolicy:
        if self.credential_inventory:
            raise ValueError("untrusted host policy must not contain credentials")
        if self.inherited_environment:
            raise ValueError("untrusted host policy must not inherit host environment variables")
        if not self.runtime_read_only or not self.benchmark_read_only or not self.submission_read_only:
            raise ValueError("untrusted host inputs must be read-only")
        if not self.writable_paths or len(set(self.writable_paths)) != len(self.writable_paths):
            raise ValueError("untrusted host writable paths must be non-empty and unique")
        if any(not path.startswith("/rhenium/") or ".." in Path(path).parts for path in self.writable_paths):
            raise ValueError("untrusted host writable paths must stay below /rhenium")
        return self


class HostEvaluationRequest(HostModel):
    run_id: str = Field(pattern=r"^run-[a-f0-9]{16}$")
    nonce: str = Field(min_length=32, max_length=128)
    task_key: str = Field(min_length=5)
    submission: Path
    submission_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: str = Field(min_length=1)
    expected_image_identity: str = Field(min_length=8)
    policy: HostSecurityPolicy


class HostBaseVerification(HostModel):
    provider_id: str
    image_identity: str
    image_verified: bool
    platform: str
    network: str
    credential_inventory: tuple[str, ...] = ()
    inherited_environment: tuple[str, ...] = ()
    runtime_read_only: bool
    benchmark_read_only: bool
    submission_read_only: bool
    writable_paths: tuple[str, ...]
    vcpus: int = Field(ge=1)
    memory_mib: int = Field(ge=256)
    writable_disk_mib: int = Field(ge=64)
    maximum_processes: int = Field(ge=1)
    maximum_open_files: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)


class HostInstance(HostModel):
    provider_id: str
    instance_id: str = Field(min_length=1)
    request_run_id: str
    image_identity: str
    platform: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("host instance creation time must be timezone-aware")
        return value


class HostInputProof(HostModel):
    instance_id: str
    request_run_id: str
    submission_identity: str
    minimum_inputs_only: bool
    submission_read_only: bool
    runtime_read_only: bool
    benchmark_read_only: bool
    writable_paths: tuple[str, ...]


class HostExecution(HostModel):
    instance_id: str
    request_run_id: str
    timed_out: bool
    exit_code: int | None
    residual_processes: tuple[str, ...] = ()
    residual_files: tuple[str, ...] = ()
    result_payload: bytes = Field(repr=False)


class HostDestructionProof(HostModel):
    instance_id: str
    destroyed: bool
    verified: bool
    residual_resources: tuple[str, ...] = ()
    verified_at: datetime

    @field_validator("verified_at")
    @classmethod
    def verified_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("host destruction verification time must be timezone-aware")
        return value


class DisposableEvaluationHost(ABC):
    """Trusted adapter for a credential-free, networkless disposable host."""

    descriptor: EvaluationHostDescriptor

    @property
    def id(self) -> str:
        return self.descriptor.id

    @abstractmethod
    def doctor(self) -> EvaluationHostCapability:
        """Read-only capability and readiness check."""

    @abstractmethod
    def verify_base(self, request: HostEvaluationRequest) -> HostBaseVerification:
        """Verify immutable image identity and effective security policy."""

    @abstractmethod
    def create(self, request: HostEvaluationRequest) -> HostInstance:
        """Create or restore one clean disposable instance."""

    @abstractmethod
    def stage_inputs(self, instance: HostInstance, request: HostEvaluationRequest) -> HostInputProof:
        """Inject only the minimum immutable evaluation inputs."""

    @abstractmethod
    def execute(self, instance: HostInstance, request: HostEvaluationRequest) -> HostExecution:
        """Execute the evaluator inside the disposable boundary."""

    @abstractmethod
    def destroy(self, instance: HostInstance) -> None:
        """Destroy the instance and all run-scoped mutable resources."""

    @abstractmethod
    def verify_destroyed(self, instance: HostInstance) -> HostDestructionProof:
        """Independently verify that run-scoped resources no longer exist."""


_FORBIDDEN_RESULT_FIELD_PARTS = {
    "analysis",
    "cases",
    "command",
    "credential",
    "details",
    "evidence",
    "nonce",
    "outputtail",
    "private",
    "payload",
    "pattern",
    "runtimelog",
    "suite",
    "trajectorypath",
    "workspacepath",
}

_FORBIDDEN_RESULT_VALUE_PARTS = (
    "/rhenium/",
    "\\rhenium\\",
    "private case",
    "private suite",
)


class UnsafeHostSubmission(ValueError):
    pass


def hash_untrusted_submission(
    root: Path,
    *,
    maximum_files: int,
    maximum_bytes: int,
) -> str:
    """Hash a bounded regular-file tree without following links or junctions."""

    resolved = root.resolve(strict=True)
    if root.is_symlink() or getattr(root, "is_junction", lambda: False)():
        raise UnsafeHostSubmission("submission root must not be a link or junction")
    digest = hashlib.sha256(b"rhenium-submission-v1\0")
    file_count = 0
    byte_count = 0

    def walk_error(error: OSError) -> None:
        raise error

    def add_record(kind: bytes, relative: str, size: int = 0) -> None:
        encoded = relative.encode("utf-8")
        digest.update(kind)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(size.to_bytes(8, "big"))

    for directory, directory_names, file_names in os.walk(
        resolved,
        followlinks=False,
        onerror=walk_error,
    ):
        current = Path(directory)
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise UnsafeHostSubmission("submission must not contain links or junctions")
        add_record(b"D", current.relative_to(resolved).as_posix())
        directory_names.sort()
        for name in list(directory_names):
            candidate = current / name
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise UnsafeHostSubmission("submission must not contain links or junctions")
        for name in sorted(file_names):
            candidate = current / name
            before = candidate.lstat()
            if candidate.is_symlink():
                raise UnsafeHostSubmission("submission must not contain links or junctions")
            if not stat.S_ISREG(before.st_mode):
                raise UnsafeHostSubmission("submission must contain regular files only")
            file_count += 1
            byte_count += before.st_size
            if file_count > maximum_files or byte_count > maximum_bytes:
                raise UnsafeHostSubmission("submission exceeds the host input limit")
            relative = candidate.relative_to(resolved).as_posix()
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(candidate, flags)
            actual_size = 0
            try:
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode):
                    raise UnsafeHostSubmission("submission must contain regular files only")
                if (opened.st_dev, opened.st_ino, opened.st_size) != (
                    before.st_dev,
                    before.st_ino,
                    before.st_size,
                ):
                    raise UnsafeHostSubmission("submission changed while it was being hashed")
                add_record(b"F", relative, opened.st_size)
                while chunk := os.read(descriptor, 1024 * 1024):
                    actual_size += len(chunk)
                    if byte_count - before.st_size + actual_size > maximum_bytes:
                        raise UnsafeHostSubmission("submission exceeds the host input limit")
                    digest.update(chunk)
            finally:
                os.close(descriptor)
            after = candidate.lstat()
            if (
                actual_size != before.st_size
                or not stat.S_ISREG(after.st_mode)
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            ):
                raise UnsafeHostSubmission("submission changed while it was being hashed")
    return digest.hexdigest()


def _field_token(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _contains_private_result_fields(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            token = _field_token(str(key))
            if any(part in token for part in _FORBIDDEN_RESULT_FIELD_PARTS):
                return True
            if _contains_private_result_fields(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_private_result_fields(item) for item in value)
    return False


def _contains_private_result_values(value: Any, forbidden_values: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        return any(_contains_private_result_values(item, forbidden_values) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_private_result_values(item, forbidden_values) for item in value)
    if isinstance(value, str):
        folded = value.casefold()
        return any(secret.casefold() in folded for secret in forbidden_values if secret)
    return False


def sanitize_disposable_result(value: Any) -> Any:
    """Remove fields that may carry private evaluator protocol from a guest result."""

    if isinstance(value, dict):
        return {
            key: sanitize_disposable_result(item)
            for key, item in value.items()
            if not any(part in _field_token(str(key)) for part in _FORBIDDEN_RESULT_FIELD_PARTS)
        }
    if isinstance(value, list):
        return [sanitize_disposable_result(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_disposable_result(item) for item in value)
    return value


def fail_closed_untrusted_evaluation(provider_id: str | None, code: str) -> dict[str, Any]:
    return {
        "score": 0.0,
        "complete": False,
        "passed": False,
        "checks": [
            {
                "id": "disposable-evaluation-host",
                "status": "failed",
                "score": 0.0,
                "maximum": 100.0,
                "message": f"Untrusted evaluation failed closed ({code}).",
            }
        ],
        "runtime_log": "",
        "security": {
            "mode": EvaluationSecurityMode.UNTRUSTED.value,
            "attested": False,
            "provider": provider_id,
            "failureCode": code,
        },
    }


def _base_is_valid(
    provider: DisposableEvaluationHost,
    request: HostEvaluationRequest,
    value: HostBaseVerification,
    capability: EvaluationHostCapability,
) -> bool:
    policy = request.policy
    return bool(
        value.provider_id == provider.id
        and value.platform == capability.platform
        and value.image_identity == request.expected_image_identity
        and value.image_verified
        and value.network == "none"
        and not value.credential_inventory
        and not value.inherited_environment
        and value.runtime_read_only
        and value.benchmark_read_only
        and value.submission_read_only
        and "/rhenium/output" in value.writable_paths
        and set(value.writable_paths).issubset(policy.writable_paths)
        and value.vcpus <= policy.vcpus
        and value.memory_mib <= policy.memory_mib
        and value.writable_disk_mib <= policy.writable_disk_mib
        and value.maximum_processes <= policy.maximum_processes
        and value.maximum_open_files <= policy.maximum_open_files
        and value.timeout_seconds <= policy.timeout_seconds
    )


def _input_is_valid(
    request: HostEvaluationRequest,
    instance: HostInstance,
    value: HostInputProof,
) -> bool:
    return bool(
        value.instance_id == instance.instance_id
        and value.request_run_id == request.run_id
        and value.submission_identity == request.submission_identity
        and value.minimum_inputs_only
        and value.submission_read_only
        and value.runtime_read_only
        and value.benchmark_read_only
        and "/rhenium/output" in value.writable_paths
        and set(value.writable_paths).issubset(request.policy.writable_paths)
    )


def _parse_result(
    request: HostEvaluationRequest,
    instance: HostInstance,
    execution: HostExecution,
) -> tuple[dict[str, Any] | None, str | None]:
    if execution.instance_id != instance.instance_id or execution.request_run_id != request.run_id:
        return None, "execution-identity-mismatch"
    if execution.timed_out:
        return None, "evaluation-timeout"
    if execution.exit_code != 0:
        return None, "evaluation-process-failed"
    if execution.residual_processes:
        return None, "residual-processes"
    if execution.residual_files:
        return None, "residual-files"
    if len(execution.result_payload) > request.policy.maximum_result_bytes:
        return None, "result-too-large"
    try:
        envelope = json.loads(execution.result_payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "malformed-result"
    if not isinstance(envelope, dict):
        return None, "malformed-result"
    if envelope.get("runId") != request.run_id or envelope.get("nonce") != request.nonce:
        return None, "result-identity-mismatch"
    result = envelope.get("result")
    if not isinstance(result, dict):
        return None, "malformed-result"
    if _contains_private_result_fields(result):
        return None, "private-result-field"
    forbidden_values = (
        request.run_id,
        request.nonce,
        request.expected_image_identity,
        str(request.submission),
        instance.instance_id,
        *_FORBIDDEN_RESULT_VALUE_PARTS,
    )
    if _contains_private_result_values(result, forbidden_values):
        return None, "private-result-value"
    try:
        normalized = normalize_evaluation(result)
    except ValueError:
        return None, "invalid-evaluation-result"
    if normalized["score"] > 100:
        return None, "invalid-evaluation-result"
    return normalized, None


def evaluate_on_disposable_host(
    provider: DisposableEvaluationHost | None,
    request: HostEvaluationRequest,
) -> dict[str, Any]:
    """Run the complete disposable lifecycle and fail closed on any missing proof."""

    if provider is None:
        return fail_closed_untrusted_evaluation(None, "provider-unavailable")
    try:
        capability = provider.doctor()
    except Exception:
        return fail_closed_untrusted_evaluation(provider.id, "provider-doctor-error")
    if not capability.available or not capability.disposable:
        return fail_closed_untrusted_evaluation(provider.id, "provider-not-ready")
    try:
        base = provider.verify_base(request)
    except Exception:
        return fail_closed_untrusted_evaluation(provider.id, "base-verification-error")
    if not _base_is_valid(provider, request, base, capability):
        return fail_closed_untrusted_evaluation(provider.id, "base-verification-failed")

    instance: HostInstance | None = None
    inputs: HostInputProof | None = None
    execution: HostExecution | None = None
    result: dict[str, Any] | None = None
    failure: str | None = None
    try:
        instance = provider.create(request)
        if (
            instance.provider_id != provider.id
            or instance.request_run_id != request.run_id
            or instance.image_identity != request.expected_image_identity
            or instance.platform != base.platform
        ):
            failure = "instance-identity-mismatch"
        else:
            inputs = provider.stage_inputs(instance, request)
            if not _input_is_valid(request, instance, inputs):
                failure = "input-proof-failed"
            else:
                execution = provider.execute(instance, request)
                result, failure = _parse_result(request, instance, execution)
    except Exception:
        failure = "host-lifecycle-error"
    finally:
        if instance is not None:
            try:
                provider.destroy(instance)
            except Exception:
                failure = "destruction-error"

    if instance is None:
        return fail_closed_untrusted_evaluation(provider.id, failure or "instance-not-created")
    try:
        destruction = provider.verify_destroyed(instance)
    except Exception:
        return fail_closed_untrusted_evaluation(provider.id, "destruction-verification-error")
    if not (
        destruction.instance_id == instance.instance_id
        and destruction.destroyed
        and destruction.verified
        and not destruction.residual_resources
        and destruction.verified_at >= instance.created_at
    ):
        return fail_closed_untrusted_evaluation(provider.id, "destruction-verification-failed")
    if failure is not None or result is None or inputs is None or execution is None:
        return fail_closed_untrusted_evaluation(provider.id, failure or "missing-result")

    result = dict(result)
    result["security"] = {
        "mode": EvaluationSecurityMode.UNTRUSTED.value,
        "attested": True,
        "provider": provider.id,
        "network": "none",
        "credentialsAbsent": True,
        "destroyed": True,
    }
    result["hostAttestation"] = {
        "provider": provider.id,
        "runId": request.run_id,
        "taskKey": request.task_key,
        "profile": request.profile,
        "imageIdentity": base.image_identity,
        "instanceId": instance.instance_id,
        "platform": instance.platform,
        "createdAt": instance.created_at.isoformat(),
        "submissionIdentity": request.submission_identity,
        "minimumInputsOnly": inputs.minimum_inputs_only,
        "network": base.network,
        "credentialInventory": [],
        "inheritedEnvironment": [],
        "writablePaths": list(base.writable_paths),
        "runtimeReadOnly": base.runtime_read_only,
        "benchmarkReadOnly": base.benchmark_read_only,
        "submissionReadOnly": base.submission_read_only,
        "resourceLimits": {
            "vcpus": base.vcpus,
            "memoryMiB": base.memory_mib,
            "writableDiskMiB": base.writable_disk_mib,
            "maximumProcesses": base.maximum_processes,
            "maximumOpenFiles": base.maximum_open_files,
            "timeoutSeconds": base.timeout_seconds,
            "maximumResultBytes": request.policy.maximum_result_bytes,
        },
        "resultBytes": len(execution.result_payload),
        "resultIdentityVerified": True,
        "residualProcesses": [],
        "residualFiles": [],
        "destroyed": destruction.destroyed,
        "destructionVerified": destruction.verified,
        "residualResources": [],
        "verifiedAt": destruction.verified_at.isoformat(),
    }
    return result
