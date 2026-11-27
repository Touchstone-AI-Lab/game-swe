from __future__ import annotations

from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .bridge import BINDING_NAME, invoke, load_binding, serial_lock
from .catalog import BalatroTask
from .files import validate_state
from .native_assets import json_write_new, verified_assets
from .protocol import classify_poc_result
from .results import incomplete
from .review import candidate_identity, candidate_reviewed
from .submission import seal_submission, verify_seal


def classify_native(value: dict[str, Any], assets: dict[str, Any], task: str,
                    submission_sha: str, candidate_sha: str | None = None) -> dict[str, Any]:
    """Bind the response to operator-reviewed inputs independently of the child."""
    if candidate_sha is None:
        # Compatibility for immutable operator matrices; live scoring supplies an
        # independently computed candidate fingerprint, never a control-role label.
        controls = [c for c in assets["controls"][task].values() if c["seal_sha256"] == submission_sha]
        if not controls:
            return incomplete("invalid_submission")
        candidate_sha = controls[0]["candidate_sha256"]
    descriptor = assets["tasks"][task]
    expected = {"environment": assets["environment"], "harness": assets["harness"],
                "task": descriptor["task_sha256"], "candidate": candidate_sha}
    raw = value.get("evaluation")
    if ("bridge_error" in value or value.get("fingerprints") != expected
            or value.get("runtime_count") != descriptor["expected_processes"]
            or not isinstance(raw, dict) or raw.get("platform_inputs_unchanged") is not True):
        return incomplete("environment_failure")
    return classify_poc_result(raw, tuple(descriptor["required"]), expected,
                               descriptor["expected_processes"])


class BalatroEvaluator:
    """Operator-reviewed honest submissions with an explicit prepared local binding."""

    def __init__(self, context: BenchmarkContext) -> None:
        self.context = context

    def runtime_status(self) -> dict[str, Any]:
        from .readiness import runtime_status

        return runtime_status(self.context.pack_root, self.context.state_dir)

    def evaluate(
        self, submission: Path, task: Any, profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        del runtimes
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
        if not (self.context.state_dir / BINDING_NAME).is_file():
            return {**incomplete("runtime_action_required"), "submissionSha256": sealed.sha256}
        try:
            with serial_lock(self.context.state_dir):
                binding = load_binding(self.context.state_dir)
                assets = verified_assets(self.context.pack_root, binding["assets_sha256"])
                submission_sha, candidate_sha = candidate_identity(sealed.directory)
                if submission_sha != sealed.sha256:
                    raise ValueError("sealed identity changed")
                if not candidate_reviewed(self.context.state_dir, assets, binding["assets_sha256"],
                                          task.id, submission_sha, candidate_sha):
                    return {**incomplete("submission_review_required"), "submissionSha256": sealed.sha256}
                value, work = invoke(self.context.pack_root, self.context.state_dir, binding, "evaluate",
                    task=task.id, candidate=sealed.directory, submission_hash=sealed.sha256)
                verify_seal(sealed)
                result = classify_native(value, assets, task.id, sealed.sha256, candidate_sha)
                json_write_new(work / "platform-result.json", {**result, "submissionSha256": sealed.sha256})
                halt = self.context.state_dir / "native-halt.json"
                if result["complete"] is not True and not halt.exists():
                    json_write_new(halt, {"reason": "incomplete_native_operation_requires_review",
                                          "operation": work.name})
                return {**result, "submissionSha256": sealed.sha256}
        except (OSError, ValueError, RuntimeError, KeyError):
            return {**incomplete("environment_failure"), "submissionSha256": sealed.sha256}
