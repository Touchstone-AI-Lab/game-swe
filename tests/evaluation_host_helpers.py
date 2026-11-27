from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from rhenium.core.evaluation_host import (
    DisposableEvaluationHost,
    EvaluationHostCapability,
    EvaluationHostDescriptor,
    HostBaseVerification,
    HostDestructionProof,
    HostEvaluationRequest,
    HostExecution,
    HostInputProof,
    HostInstance,
)


class FakeDisposableHost(DisposableEvaluationHost):
    descriptor = EvaluationHostDescriptor(
        id="fake-disposable",
        name="Fake disposable host",
        version="1.0.0",
        capabilities=("test-only",),
    )

    def __init__(self, failure: str | None = None, result: dict[str, Any] | None = None):
        self.failure = failure
        self.result = result or {
            "score": 100.0,
            "complete": True,
            "passed": True,
            "checks": [{"id": "fake-engine", "status": "passed"}],
        }
        self.destroy_called = False

    def doctor(self) -> EvaluationHostCapability:
        if self.failure == "doctor-error":
            raise RuntimeError("synthetic doctor failure")
        return EvaluationHostCapability(
            available=self.failure != "unavailable",
            disposable=self.failure != "not-disposable",
            platform="test-x86_64",
            reason="synthetic failure" if self.failure else "",
        )

    def verify_base(self, request: HostEvaluationRequest) -> HostBaseVerification:
        if self.failure == "base-error":
            raise RuntimeError("synthetic base failure")
        return HostBaseVerification(
            provider_id="wrong" if self.failure == "provider-mismatch" else self.id,
            image_identity=(
                "sha256:wrong-image" if self.failure == "image-mismatch" else request.expected_image_identity
            ),
            image_verified=self.failure != "image-unverified",
            platform="test-x86_64",
            network="bridge" if self.failure == "network" else "none",
            credential_inventory=("TEST_FAKE_TOKEN",) if self.failure == "credentials" else (),
            inherited_environment=("TEST_FAKE_API_KEY",) if self.failure == "environment" else (),
            runtime_read_only=self.failure != "runtime-writable",
            benchmark_read_only=self.failure != "benchmark-writable",
            submission_read_only=self.failure != "submission-writable",
            writable_paths=("/host/home" if self.failure == "writable-path" else "/rhenium/output",),
            vcpus=65 if self.failure == "cpu" else 2,
            memory_mib=16384 if self.failure == "memory" else 4096,
            writable_disk_mib=8192 if self.failure == "disk" else 2048,
            maximum_processes=4097 if self.failure == "process-limit" else 32,
            maximum_open_files=65_537 if self.failure == "file-limit" else 128,
            timeout_seconds=901 if self.failure == "timeout-policy" else 300,
        )

    def create(self, request: HostEvaluationRequest) -> HostInstance:
        if self.failure == "create-error":
            raise RuntimeError("synthetic create failure")
        return HostInstance(
            provider_id=self.id,
            instance_id="instance-1",
            request_run_id=("run-0000000000000000" if self.failure == "instance-run" else request.run_id),
            image_identity=(
                "sha256:wrong-instance"
                if self.failure == "instance-image"
                else request.expected_image_identity
            ),
            platform="test-x86_64",
            created_at=datetime.now(UTC),
        )

    def stage_inputs(self, instance: HostInstance, request: HostEvaluationRequest) -> HostInputProof:
        if self.failure == "stage-error":
            raise RuntimeError("synthetic stage failure")
        return HostInputProof(
            instance_id="wrong" if self.failure == "input-instance" else instance.instance_id,
            request_run_id="run-0000000000000000" if self.failure == "input-run" else request.run_id,
            submission_identity=(
                "0" * 64 if self.failure == "input-submission" else request.submission_identity
            ),
            minimum_inputs_only=self.failure != "extra-inputs",
            submission_read_only=self.failure != "input-submission-writable",
            runtime_read_only=self.failure != "input-runtime-writable",
            benchmark_read_only=self.failure != "input-benchmark-writable",
            writable_paths=("/host/home" if self.failure == "input-writable-path" else "/rhenium/output",),
        )

    def execute(self, instance: HostInstance, request: HostEvaluationRequest) -> HostExecution:
        if self.failure == "execute-error":
            raise RuntimeError("synthetic execution failure")
        envelope: Any = {
            "runId": ("run-0000000000000000" if self.failure == "result-run" else request.run_id),
            "nonce": "0" * 32 if self.failure == "result-nonce" else request.nonce,
            "result": self.result,
        }
        if self.failure == "malformed-result":
            payload = b"not-json"
        elif self.failure == "oversized-result":
            payload = b"x" * (request.policy.maximum_result_bytes + 1)
        else:
            payload = json.dumps(envelope).encode()
        return HostExecution(
            instance_id="wrong" if self.failure == "execution-instance" else instance.instance_id,
            request_run_id=("run-0000000000000000" if self.failure == "execution-run" else request.run_id),
            timed_out=self.failure == "execution-timeout",
            exit_code=1 if self.failure == "exit-code" else 0,
            residual_processes=("fake-process",) if self.failure == "process-residue" else (),
            residual_files=("/rhenium/tmp/residue",) if self.failure == "file-residue" else (),
            result_payload=payload,
        )

    def destroy(self, instance: HostInstance) -> None:
        del instance
        self.destroy_called = True
        if self.failure == "destroy-error":
            raise RuntimeError("synthetic destruction failure")

    def verify_destroyed(self, instance: HostInstance) -> HostDestructionProof:
        if self.failure == "destroy-verify-error":
            raise RuntimeError("synthetic destruction verification failure")
        return HostDestructionProof(
            instance_id="wrong" if self.failure == "destroy-instance" else instance.instance_id,
            destroyed=self.failure != "not-destroyed",
            verified=self.failure != "destroy-unverified",
            residual_resources=("fake-disk",) if self.failure == "resource-residue" else (),
            verified_at=(
                instance.created_at - timedelta(seconds=1)
                if self.failure == "destroy-before-create"
                else datetime.now(UTC)
            ),
        )
