from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path
from typing import cast

import pytest

from rhenium.core.evaluation_host import (
    HostEvaluationRequest,
    HostSecurityPolicy,
    evaluate_on_disposable_host,
    hash_untrusted_submission,
    sanitize_disposable_result,
)
from rhenium.core.registry import discover_evaluation_hosts
from rhenium.hub import BenchmarkHub
from tests.conftest import FixturePlugin
from tests.evaluation_host_helpers import FakeDisposableHost


def _request(tmp_path: Path) -> HostEvaluationRequest:
    submission = tmp_path / "submission"
    submission.mkdir(exist_ok=True)
    return HostEvaluationRequest(
        run_id="run-0123456789abcdef",
        nonce="0123456789abcdef0123456789abcdef",
        task_key="fixture/core/shared-task",
        submission=submission,
        submission_identity="1" * 64,
        profile="full",
        expected_image_identity="sha256:trusted-image",
        policy=HostSecurityPolicy(),
    )


def test_complete_disposable_lifecycle_returns_attested_result(tmp_path: Path) -> None:
    provider = FakeDisposableHost()

    result = evaluate_on_disposable_host(provider, _request(tmp_path))

    assert result["complete"] is True
    assert result["passed"] is True
    assert result["security"] == {
        "mode": "untrusted",
        "attested": True,
        "provider": "fake-disposable",
        "network": "none",
        "credentialsAbsent": True,
        "destroyed": True,
    }
    assert result["hostAttestation"]["destructionVerified"] is True
    assert result["hostAttestation"]["runId"] == "run-0123456789abcdef"
    assert result["hostAttestation"]["minimumInputsOnly"] is True
    assert result["hostAttestation"]["resultIdentityVerified"] is True
    assert result["hostAttestation"]["resourceLimits"]["memoryMiB"] == 4096
    assert result["hostAttestation"]["residualProcesses"] == []
    assert result["hostAttestation"]["residualFiles"] == []
    assert result["hostAttestation"]["residualResources"] == []
    assert provider.destroy_called is True


def test_untrusted_submission_hash_is_bounded_and_deterministic(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "nested").mkdir(parents=True)
    (submission / "b.txt").write_text("b", encoding="utf-8")
    (submission / "nested" / "a.txt").write_text("a", encoding="utf-8")

    first = hash_untrusted_submission(submission, maximum_files=2, maximum_bytes=2)
    second = hash_untrusted_submission(submission, maximum_files=2, maximum_bytes=2)

    assert first == second
    with pytest.raises(ValueError, match="input limit"):
        hash_untrusted_submission(submission, maximum_files=1, maximum_bytes=2)


def test_untrusted_submission_hash_commits_to_empty_directories(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    (first / "empty-a").mkdir(parents=True)
    (second / "empty-b").mkdir(parents=True)

    first_digest = hash_untrusted_submission(first, maximum_files=1, maximum_bytes=1)
    second_digest = hash_untrusted_submission(second, maximum_files=1, maximum_bytes=1)

    assert first_digest != second_digest


def test_untrusted_submission_hash_rejects_links(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("must not be read", encoding="utf-8")
    link = submission / "link.txt"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    with pytest.raises(ValueError, match="links or junctions"):
        hash_untrusted_submission(submission, maximum_files=10, maximum_bytes=1024)


def test_guest_sanitizer_removes_private_protocol_recursively() -> None:
    value = {
        "score": 100,
        "runtime_log": "private log",
        "runtime": {
            "cases": [{"name": "private case"}],
            "status": "passed",
        },
        "checks": [{"id": "public-layer", "status": "passed"}],
    }

    sanitized = sanitize_disposable_result(value)

    assert sanitized == {
        "score": 100,
        "runtime": {"status": "passed"},
        "checks": [{"id": "public-layer", "status": "passed"}],
    }


@pytest.mark.parametrize(
    ("failure", "code"),
    [
        ("doctor-error", "provider-doctor-error"),
        ("unavailable", "provider-not-ready"),
        ("not-disposable", "provider-not-ready"),
        ("base-error", "base-verification-error"),
        ("provider-mismatch", "base-verification-failed"),
        ("network", "base-verification-failed"),
        ("credentials", "base-verification-failed"),
        ("environment", "base-verification-failed"),
        ("image-mismatch", "base-verification-failed"),
        ("image-unverified", "base-verification-failed"),
        ("runtime-writable", "base-verification-failed"),
        ("benchmark-writable", "base-verification-failed"),
        ("submission-writable", "base-verification-failed"),
        ("writable-path", "base-verification-failed"),
        ("cpu", "base-verification-failed"),
        ("memory", "base-verification-failed"),
        ("disk", "base-verification-failed"),
        ("process-limit", "base-verification-failed"),
        ("file-limit", "base-verification-failed"),
        ("timeout-policy", "base-verification-failed"),
        ("create-error", "host-lifecycle-error"),
        ("instance-image", "instance-identity-mismatch"),
        ("instance-run", "instance-identity-mismatch"),
        ("stage-error", "host-lifecycle-error"),
        ("input-instance", "input-proof-failed"),
        ("input-run", "input-proof-failed"),
        ("extra-inputs", "input-proof-failed"),
        ("input-submission", "input-proof-failed"),
        ("input-submission-writable", "input-proof-failed"),
        ("input-runtime-writable", "input-proof-failed"),
        ("input-benchmark-writable", "input-proof-failed"),
        ("input-writable-path", "input-proof-failed"),
        ("execute-error", "host-lifecycle-error"),
        ("execution-instance", "execution-identity-mismatch"),
        ("execution-run", "execution-identity-mismatch"),
        ("execution-timeout", "evaluation-timeout"),
        ("exit-code", "evaluation-process-failed"),
        ("process-residue", "residual-processes"),
        ("file-residue", "residual-files"),
        ("malformed-result", "malformed-result"),
        ("oversized-result", "result-too-large"),
        ("result-run", "result-identity-mismatch"),
        ("result-nonce", "result-identity-mismatch"),
        ("destroy-error", "destruction-error"),
        ("destroy-verify-error", "destruction-verification-error"),
        ("destroy-instance", "destruction-verification-failed"),
        ("not-destroyed", "destruction-verification-failed"),
        ("destroy-unverified", "destruction-verification-failed"),
        ("resource-residue", "destruction-verification-failed"),
        ("destroy-before-create", "destruction-verification-failed"),
    ],
)
def test_each_missing_security_proof_fails_closed(tmp_path: Path, failure: str, code: str) -> None:
    result = evaluate_on_disposable_host(FakeDisposableHost(failure), _request(tmp_path))

    assert result["score"] == 0
    assert result["complete"] is False
    assert result["passed"] is False
    assert result["security"]["failureCode"] == code


@pytest.mark.parametrize(
    "private_field",
    ["nonce", "privatePath", "suiteId", "evidence", "command", "runtime_log"],
)
def test_private_guest_result_fields_fail_closed(tmp_path: Path, private_field: str) -> None:
    provider = FakeDisposableHost(
        result={
            "score": 100,
            "complete": True,
            "passed": True,
            "checks": [],
            private_field: "must-not-cross-boundary",
        }
    )

    result = evaluate_on_disposable_host(provider, _request(tmp_path))

    assert result["security"]["failureCode"] == "private-result-field"
    assert "must-not-cross-boundary" not in str(result)


@pytest.mark.parametrize(
    "private_value",
    [
        "0123456789abcdef0123456789abcdef",
        "sha256:trusted-image",
        "instance-1",
        "/rhenium/private/suite.lua",
        "failure in private case hidden-one",
    ],
)
def test_private_guest_result_values_fail_closed(tmp_path: Path, private_value: str) -> None:
    provider = FakeDisposableHost(
        result={
            "score": 100,
            "complete": True,
            "passed": True,
            "checks": [{"id": "public-layer", "message": private_value}],
        }
    )

    result = evaluate_on_disposable_host(provider, _request(tmp_path))

    assert result["security"]["failureCode"] == "private-result-value"
    assert private_value not in str(result)


def test_inconsistent_evaluation_result_fails_closed(tmp_path: Path) -> None:
    provider = FakeDisposableHost(result={"score": 100, "complete": False, "passed": True, "checks": []})

    result = evaluate_on_disposable_host(provider, _request(tmp_path))

    assert result["security"]["failureCode"] == "invalid-evaluation-result"


def test_out_of_range_evaluation_score_fails_closed(tmp_path: Path) -> None:
    provider = FakeDisposableHost(result={"score": 100.01, "complete": True, "passed": True, "checks": []})

    result = evaluate_on_disposable_host(provider, _request(tmp_path))

    assert result["security"]["failureCode"] == "invalid-evaluation-result"


def test_hub_untrusted_mode_never_falls_back_to_local_evaluator(
    hub: BenchmarkHub, fixture_plugin: FixturePlugin, tmp_path: Path
) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")

    result = hub.evaluate_task(
        "fixture/core/shared-task",
        submission,
        security_mode="untrusted",
        host_provider="missing",
        host_image="sha256:trusted-image",
    )

    assert result["status"] == "failed"
    assert result["result"]["score"] == 0
    assert result["result"]["complete"] is False
    assert result["result"]["security"]["failureCode"] == "provider-unavailable"
    assert fixture_plugin.calls == []


def test_hub_untrusted_mode_requires_explicit_provider_and_image(hub: BenchmarkHub, tmp_path: Path) -> None:
    provider = FakeDisposableHost()
    hub.evaluation_hosts[provider.id] = provider
    submission = tmp_path / "submission"
    submission.mkdir()

    no_provider = hub.evaluate_task("fixture/core/shared-task", submission, security_mode="untrusted")
    no_image = hub.evaluate_task(
        "fixture/core/shared-task",
        submission,
        security_mode="untrusted",
        host_provider=provider.id,
    )

    assert no_provider["result"]["security"]["failureCode"] == "provider-not-selected"
    assert no_image["result"]["security"]["failureCode"] == "image-identity-not-selected"


def test_honest_mode_rejects_disposable_host_options(hub: BenchmarkHub, tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()

    with pytest.raises(ValueError, match="require --security-mode untrusted"):
        hub.evaluate_task(
            "fixture/core/shared-task",
            submission,
            host_provider="fake-disposable",
        )


def test_untrusted_selector_values_are_validated_without_echoing_arbitrary_provider(
    hub: BenchmarkHub, tmp_path: Path
) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()

    invalid_provider = hub.evaluate_task(
        "fixture/core/shared-task",
        submission,
        security_mode="untrusted",
        host_provider="../../do-not-echo",
        host_image="sha256:trusted-image",
    )
    invalid_image = hub.evaluate_task(
        "fixture/core/shared-task",
        submission,
        security_mode="untrusted",
        host_provider="fake-disposable",
        host_image="latest",
    )

    assert invalid_provider["result"]["security"] == {
        "mode": "untrusted",
        "attested": False,
        "provider": None,
        "failureCode": "provider-id-invalid",
    }
    assert "do-not-echo" not in str(invalid_provider)
    assert invalid_image["result"]["security"]["failureCode"] == "image-identity-invalid"


def test_hub_records_honest_mode_without_claiming_disposable_safety(
    hub: BenchmarkHub, tmp_path: Path
) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")

    result = hub.evaluate_task("fixture/core/shared-task", submission)

    assert result["status"] == "passed"
    assert result["result"]["security"] == {
        "mode": "honest",
        "attested": False,
        "disposableHost": False,
    }


def test_hub_anonymous_result_keeps_summary_but_removes_host_attestation(
    hub: BenchmarkHub, tmp_path: Path
) -> None:
    provider = FakeDisposableHost()
    hub.evaluation_hosts[provider.id] = provider
    attempt = tmp_path.parent / f"{tmp_path.name}-attempt"
    attempt.mkdir()
    (attempt / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")
    try:
        hub.register_attempt("fixture/core/shared-task", attempt, "strict")
        result = hub.evaluate_attempt(
            attempt,
            security_mode="untrusted",
            host_provider=provider.id,
            host_image="sha256:trusted-image",
        )
    finally:
        for path in attempt.iterdir():
            path.unlink()
        attempt.rmdir()

    assert result["result"]["security"]["attested"] is True
    assert "hostAttestation" not in result["result"]
    assert "instance-1" not in str(result)


class _EntryPoint:
    def __init__(self, name: str, value: object):
        self.name = name
        self.value = value

    def load(self) -> object:
        return self.value


def test_evaluation_host_entry_point_discovery_is_isolated() -> None:
    healthy = FakeDisposableHost()
    providers, errors = discover_evaluation_hosts(
        cast(
            tuple[EntryPoint, ...],
            (
                _EntryPoint("fake-disposable", healthy),
                _EntryPoint("broken", RuntimeError("not a provider")),
            ),
        )
    )

    assert set(providers) == {"fake-disposable"}
    assert errors[0]["kind"] == "evaluation-host"
