"""Controlled honest scoring on an explicitly prepared, smoke-verified Linux host."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import BalatroTask
from .files import read_json, validate_state
from .linux_bridge import BINDING_NAME, invoke, serial_lock
from .linux_layout import execution_context, pack_runtime
from .linux_worker import make_host, verify_binding
from .native_assets import json_write_new
from .protocol import classify_poc_result
from .results import incomplete
from .review import candidate_identity, candidate_reviewed
from .submission import seal_submission, verify_seal


class BalatroLinuxEvaluator:
    def __init__(self, context: BenchmarkContext) -> None:
        self.runtime_key = "balatro/" + pack_runtime(context)
        self.context = execution_context(context)

    @classmethod
    def with_prepared_context(
        cls, context: BenchmarkContext, runtime_key: str,
    ) -> BalatroLinuxEvaluator:
        """Use a verified inner native artifact in a separately owned host profile."""
        from .linux_managed_v2 import RUNTIME_KEY

        if runtime_key != RUNTIME_KEY:
            raise ValueError("Unsupported inner native runtime")
        evaluator = cls.__new__(cls)
        evaluator.context, evaluator.runtime_key = context, runtime_key
        return evaluator

    def runtime_status(self) -> dict[str, Any]:
        try:
            binding = read_json(self.context.state_dir, BINDING_NAME)
            artifact = RuntimeArtifact.model_validate(binding["artifact"])
            host = make_host(self.context, artifact, binding)
            verify_binding(host, binding)
            if (self.context.state_dir / "linux-halt.json").exists():
                raise ValueError("Incomplete operation requires review")
            return {"available": True, "scope": "source-reviewed-native-linux", "untrustedSandbox": False}
        except (OSError, ValueError, RuntimeError, KeyError, StopIteration):
            return {
                "available": False,
                "scope": "source-reviewed-native-linux",
                "reason": "Managed artifact and current-host operator smoke are required",
            }

    def evaluate(
        self,
        submission: Path,
        task: Any,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile != "full":
            return incomplete("unsupported_profile")
        if not isinstance(task, BalatroTask):
            return incomplete("invalid_submission")
        try:
            validate_state(self.context.pack_root, self.context.state_dir)
            sealed = seal_submission(submission, task, self.context.state_dir / "submissions")
            verify_seal(sealed)
        except (OSError, ValueError):
            return incomplete("invalid_submission")
        if (
            not runtimes
            or set(runtimes) != {self.runtime_key}
            or not (self.context.state_dir / BINDING_NAME).is_file()
        ):
            return {**incomplete("runtime_action_required"), "submissionSha256": sealed.sha256}
        invocation_attempted = False
        try:
            with serial_lock(self.context.state_dir):
                halt = self.context.state_dir / "linux-halt.json"
                if halt.exists():
                    return {**incomplete("environment_failure"), "submissionSha256": sealed.sha256}
                binding = read_json(self.context.state_dir, BINDING_NAME)
                artifact = runtimes[self.runtime_key]
                if artifact.model_dump(mode="json") != binding["artifact"]:
                    raise ValueError("Core artifact differs from the operator smoke binding")
                host = make_host(self.context, artifact, binding)
                verify_binding(host, binding)
                submission_sha, candidate_sha = candidate_identity(sealed.directory)
                scoped = {**host.assets, "environment": host.environment, "harness": host.harness}
                if submission_sha != sealed.sha256 or not candidate_reviewed(
                    self.context.state_dir, scoped, host.assets_sha256, task.id, submission_sha, candidate_sha
                ):
                    return {**incomplete("submission_review_required"), "submissionSha256": sealed.sha256}
                invocation_attempted = True
                value, work = invoke(
                    self.context,
                    artifact,
                    binding,
                    "evaluate",
                    task=task.id,
                    candidate=sealed.directory,
                    submission_sha256=sealed.sha256,
                )
                verify_seal(sealed)
                host.verify()
                descriptor = host.assets["tasks"][task.id]
                expected = {
                    "environment": host.environment,
                    "harness": host.harness,
                    "task": descriptor["task_sha256"],
                    "candidate": candidate_sha,
                }
                if (
                    "bridge_error" in value
                    or value.get("fingerprints") != expected
                    or value.get("runtime_count") != descriptor["expected_processes"]
                ):
                    result = incomplete("environment_failure")
                else:
                    result = classify_poc_result(
                        value["evaluation"],
                        tuple(descriptor["required"]),
                        expected,
                        descriptor["expected_processes"],
                    )
                json_write_new(work / "platform-result.json", {**result, "submissionSha256": sealed.sha256})
                if result["complete"] is not True:
                    json_write_new(
                        halt, {"reason": "incomplete_operation_requires_review", "operation": work.name}
                    )
                return {**result, "submissionSha256": sealed.sha256}
        except (OSError, ValueError, RuntimeError, KeyError, StopIteration, subprocess.SubprocessError):
            halt = self.context.state_dir / "linux-halt.json"
            if invocation_attempted and not halt.exists():
                json_write_new(halt, {"reason": "controller_failure_requires_review"})
            return {**incomplete("environment_failure"), "submissionSha256": sealed.sha256}
