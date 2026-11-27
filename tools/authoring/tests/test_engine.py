from __future__ import annotations

from pathlib import Path

import pytest
import rhenium_authoring.engine as engine
from rhenium_authoring.engine import _assertion_counts, _cases_match, _runtime_unavailable
from rhenium_authoring.models import SynthesisBundle, VerifierBundle

from rhenium.config import Settings


def test_assertion_counts_support_private_runtime_summaries() -> None:
    assert _assertion_counts(
        {"runtime": {"passedAssertions": 7, "failedAssertions": 2}}
    ) == (7, 2)
    assert _assertion_counts(
        {"runtime": {"cases": [{"passed": True}, {"passed": False}]}}
    ) == (1, 1)
    assert _assertion_counts({"runtime": {"status": "failed"}}) is None
    assert _runtime_unavailable(
        {"complete": False, "runtime": {"status": "unavailable"}}
    )
    assert not _runtime_unavailable(
        {"complete": True, "runtime": {"status": "failed"}}
    )
    assert not _runtime_unavailable(
        {"complete": False, "runtime": {"status": "incomplete"}}
    )


def test_equal_failure_counts_do_not_hide_failure_of_the_wrong_case() -> None:
    result = {"runtime": {"caseOutcomes": {"sentinel": False, "regression": True}}}
    assert not _cases_match(result, {"sentinel", "regression"}, {"regression"}, required=True)
    assert _cases_match(result, {"sentinel", "regression"}, {"sentinel"}, required=True)
    assert not _cases_match({"runtime": {}}, {"regression"}, {"regression"}, required=True)


def test_control_receipts_fail_closed_on_missing_control(dst_bundle: SynthesisBundle) -> None:
    report = engine.HubEngineValidator.validate_controls(dst_bundle, {})
    assert not report.complete and not report.passed and not report.engine_backed


def test_complete_control_audit_checks_exact_failure_identities(dst_bundle: SynthesisBundle) -> None:
    bundle = dst_bundle.model_copy(update={
        "candidate": dst_bundle.candidate.model_copy(update={"game_id": "stardew-valley"}),
    })
    failures = {"combined-base": {"once", "capacity"}, "gold": set(), **{
        f"ablation:{key}": set(value) for key, value in bundle.verifier.capsule_cases.items()
    }}
    results = {key: {"complete": True, "passed": not failed, "runtime": {
        "passedAssertions": 3 - len(failed), "failedAssertions": len(failed),
        "caseOutcomes": {name: name not in failed for name in bundle.verifier.case_ids},
    }} for key, failed in failures.items()}
    assert engine.HubEngineValidator.validate_controls(bundle, results).passed
    results["combined-base"]["runtime"]["caseOutcomes"] = {
        "sentinel": False, "once": False, "capacity": True,
    }
    assert not engine.HubEngineValidator.validate_controls(bundle, results).passed


def test_bundle_rejects_overlapping_defect_case_mappings(
    dst_bundle: SynthesisBundle,
) -> None:
    capsule_ids = [capsule.capsule_id for capsule in dst_bundle.candidate.capsules]
    verifier = VerifierBundle(
        files=dst_bundle.verifier.files,
        case_ids=dst_bundle.verifier.case_ids,
        capsule_cases={capsule_ids[0]: ("once",), capsule_ids[1]: ("once",)},
    )
    payload = dst_bundle.model_dump(mode="json")
    payload["verifier"] = verifier.model_dump(mode="json")
    with pytest.raises(ValueError, match="must not overlap"):
        SynthesisBundle.model_validate(payload)


def test_staged_validation_never_uses_the_operator_hub_database(
    tmp_path: Path, dst_bundle: SynthesisBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator_db = tmp_path / "operator.sqlite"
    operator_db.write_bytes(b"existing operator state")
    monkeypatch.setenv("RHENIUM_DATABASE_URL", f"sqlite:///{operator_db}")
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "operator-hub"))
    captured: list[Settings] = []

    class CapturingHub:
        task_keys: tuple[str, ...] = ()
        discovery_errors: list[dict[str, str]] = []

        def __init__(self, *, settings: Settings, manifest_paths: tuple[Path, ...]):
            del manifest_paths
            captured.append(settings)

    validator = engine.HubEngineValidator(tmp_path)
    pack = tmp_path / "staged-pack"
    monkeypatch.setattr(validator.publisher, "stage", lambda *_args: pack)
    monkeypatch.setattr(engine, "BenchmarkHub", CapturingHub)
    run_root = tmp_path / ".rhenium/authoring/runs/run-one"
    report = validator.validate(run_root, dst_bundle)
    expected_state = run_root / "validation-state" / dst_bundle.candidate.id
    assert captured[0].state_dir == expected_state
    assert captured[0].database_url == f"sqlite:///{expected_state / 'state.sqlite'}"
    assert captured[0].cache_dir == expected_state / "cache"
    assert operator_db.read_bytes() == b"existing operator state"
    assert report.passed is False


def test_failed_checks_carry_structured_engine_evidence(dst_bundle: SynthesisBundle) -> None:
    bundle = dst_bundle.model_copy(update={
        "candidate": dst_bundle.candidate.model_copy(update={"game_id": "stardew-valley"}),
    })
    base_failures = {
        case for cases in bundle.verifier.capsule_cases.values() for case in cases
    }
    failures = {"combined-base": base_failures, "gold": {"sentinel"}, **{
        f"ablation:{key}": set(value) for key, value in bundle.verifier.capsule_cases.items()
    }}
    results = {key: {"complete": True, "passed": not failed, "runtime": {
        "passedAssertions": 3 - len(failed), "failedAssertions": len(failed),
        "caseOutcomes": {name: name not in failed for name in bundle.verifier.case_ids},
    }} for key, failed in failures.items()}
    report = engine.HubEngineValidator.validate_controls(bundle, results)
    assert not report.passed
    checks = {check.id: check for check in report.checks}
    gold = checks["gold"]
    assert gold.status == "failed"
    assert gold.observed_complete is True
    assert gold.observed_passed is False
    assert gold.observed_counts == (2, 1)
    assert gold.expected_failing_cases == ()
    assert gold.observed_failing_cases == ("sentinel",)
    assert gold.observed_case_ids == tuple(sorted(bundle.verifier.case_ids))
    base = checks["combined-base"]
    assert base.status == "passed"
    assert base.expected_failing_cases == tuple(sorted(base_failures))
    assert base.observed_failing_cases == tuple(sorted(base_failures))


def test_left_4_dead_2_requires_exact_case_outcomes(dst_bundle: SynthesisBundle) -> None:
    bundle = dst_bundle.model_copy(update={
        "candidate": dst_bundle.candidate.model_copy(update={"game_id": "left-4-dead-2"}),
    })
    base_failures = {
        case for cases in bundle.verifier.capsule_cases.values() for case in cases
    }
    failures = {"combined-base": base_failures, "gold": set(), **{
        f"ablation:{key}": set(value) for key, value in bundle.verifier.capsule_cases.items()
    }}
    results = {key: {"complete": True, "passed": not failed, "runtime": {
        "passedAssertions": 3 - len(failed), "failedAssertions": len(failed),
    }} for key, failed in failures.items()}
    # Counts alone are not enough for a caseOutcomes-emitting evaluator.
    assert not engine.HubEngineValidator.validate_controls(bundle, results).passed
    for key, failed in failures.items():
        results[key]["runtime"]["caseOutcomes"] = {
            name: name not in failed for name in bundle.verifier.case_ids
        }
    assert engine.HubEngineValidator.validate_controls(bundle, results).passed


def test_games_without_case_outcomes_are_judged_by_counts(dst_bundle: SynthesisBundle) -> None:
    base_failures = {
        case for cases in dst_bundle.verifier.capsule_cases.values() for case in cases
    }
    failures = {"combined-base": base_failures, "gold": set(), **{
        f"ablation:{key}": set(value)
        for key, value in dst_bundle.verifier.capsule_cases.items()
    }}
    results = {key: {"complete": True, "passed": not failed, "runtime": {
        "passedAssertions": 3 - len(failed), "failedAssertions": len(failed),
    }} for key, failed in failures.items()}
    report = engine.HubEngineValidator.validate_controls(dst_bundle, results)
    assert report.passed
    checks = {check.id: check for check in report.checks}
    assert checks["gold"].observed_counts == (3, 0)
    assert checks["gold"].observed_failing_cases is None
    assert checks["gold"].observed_case_ids is None


class _FakeRuntimeManager:
    def __init__(self, rows: list[dict[str, object]], error: Exception | None = None):
        self.rows = rows
        self.error = error
        self.prepared: list[tuple[str, str]] = []

    def list(self, game_id: str | None = None) -> list[dict[str, object]]:
        del game_id
        return self.rows

    def prepare(self, key: str, *, account_alias: str = "default") -> dict[str, object]:
        if self.error is not None:
            raise self.error
        self.prepared.append((key, account_alias))
        return {"key": key, "ready": True}


def _prepare_fixture(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    monkeypatch: pytest.MonkeyPatch,
    manager: _FakeRuntimeManager,
    *,
    prepare_account: str | None,
) -> tuple[engine.HubEngineValidator, list[Settings]]:
    operator_hub = tmp_path / ".rhenium" / "hub"
    operator_hub.mkdir(parents=True)
    (operator_hub / "state.sqlite").write_bytes(b"operator sessions")
    (operator_hub / "cache").mkdir()
    captured: list[Settings] = []

    class CapturingHub:
        task_keys: tuple[str, ...] = ()
        discovery_errors: list[dict[str, str]] = []
        runtime_manager = manager

        def __init__(self, *, settings: Settings, manifest_paths: tuple[Path, ...]):
            del manifest_paths
            captured.append(settings)

    validator = engine.HubEngineValidator(tmp_path, prepare_account=prepare_account)
    monkeypatch.setattr(validator.publisher, "stage", lambda *_args: tmp_path / "staged-pack")
    monkeypatch.setattr(engine, "BenchmarkHub", CapturingHub)
    return validator, captured


def test_explicit_prepare_seeds_sessions_and_prepares_runtimes(
    tmp_path: Path, dst_bundle: SynthesisBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = _FakeRuntimeManager(
        [
            {"key": "dst/ready-synth", "ready": True},
            {"key": "dst/cold-synth", "ready": False},
        ]
    )
    validator, captured = _prepare_fixture(
        tmp_path, dst_bundle, monkeypatch, manager, prepare_account="alt"
    )
    run_root = tmp_path / ".rhenium/authoring/runs/run-one"
    report = validator.validate(run_root, dst_bundle)
    # Every runtime of the game is prepared with the named account: the seeded
    # operator record can be ready without images for the staged candidate.
    assert manager.prepared == [("dst/ready-synth", "alt"), ("dst/cold-synth", "alt")]
    state = run_root / "validation-state" / dst_bundle.candidate.id
    assert (state / "state.sqlite").read_bytes() == b"operator sessions"
    assert (state / "state.sqlite").stat().st_mode & 0o777 == 0o600
    # The operator acquisition cache is reused; the state database stays isolated.
    assert captured[0].cache_dir == tmp_path / ".rhenium" / "hub" / "cache"
    assert captured[0].database_url == f"sqlite:///{state / 'state.sqlite'}"
    assert report.passed is False  # empty task keys still fail closed


def test_prepare_requiring_interaction_stays_operator_work(
    tmp_path: Path, dst_bundle: SynthesisBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rhenium.core.runtime import RuntimeActionRequired

    manager = _FakeRuntimeManager(
        [{"key": "dst/cold-synth", "ready": False}],
        error=RuntimeActionRequired("login", "scan the secret QR at https://private"),
    )
    validator, _captured = _prepare_fixture(
        tmp_path, dst_bundle, monkeypatch, manager, prepare_account="default"
    )
    report = validator.validate(tmp_path / ".rhenium/authoring/runs/run-two", dst_bundle)
    check = report.checks[0]
    assert check.status == "unavailable"
    assert "interactive operator step" in check.message
    assert "private" not in check.message and "QR" not in check.message


def test_without_prepare_account_runtimes_are_untouched(
    tmp_path: Path, dst_bundle: SynthesisBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = _FakeRuntimeManager([{"key": "dst/cold-synth", "ready": False}])
    validator, captured = _prepare_fixture(
        tmp_path, dst_bundle, monkeypatch, manager, prepare_account=None
    )
    run_root = tmp_path / ".rhenium/authoring/runs/run-three"
    validator.validate(run_root, dst_bundle)
    assert manager.prepared == []
    state = run_root / "validation-state" / dst_bundle.candidate.id
    assert not (state / "state.sqlite").exists()
    assert captured[0].cache_dir == state / "cache"


def test_failed_case_messages_are_recorded_for_the_verifier_author(
    dst_bundle: SynthesisBundle,
) -> None:
    failures = {"combined-base": {"once", "capacity"}, "gold": {"sentinel"}, **{
        f"ablation:{key}": set(value) for key, value in dst_bundle.verifier.capsule_cases.items()
    }}
    results = {key: {"complete": True, "passed": not failed, "runtime": {
        "passedAssertions": 3 - len(failed), "failedAssertions": len(failed),
        "cases": [
            {"name": name, "passed": name not in failed,
             "message": "ok" if name not in failed else "attempt to call a nil value"}
            for name in dst_bundle.verifier.case_ids
        ],
    }} for key, failed in failures.items()}
    report = engine.HubEngineValidator.validate_controls(dst_bundle, results)
    gold = {check.id: check for check in report.checks}["gold"]
    assert gold.observed_messages == ("attempt to call a nil value",)


def test_minecraft_controls_require_exact_case_outcomes(dst_bundle: SynthesisBundle) -> None:
    bundle = dst_bundle.model_copy(update={
        "candidate": dst_bundle.candidate.model_copy(update={"game_id": "minecraft"}),
    })
    assert "minecraft" in engine.EXACT_CASE_GAMES
    base_failures = {case for cases in bundle.verifier.capsule_cases.values() for case in cases}
    failures = {"combined-base": base_failures, "gold": set(), **{
        f"ablation:{key}": set(value) for key, value in bundle.verifier.capsule_cases.items()
    }}
    results = {key: {"complete": True, "passed": not failed, "runtime": {
        "passedAssertions": 3 - len(failed), "failedAssertions": len(failed),
    }} for key, failed in failures.items()}
    assert not engine.HubEngineValidator.validate_controls(bundle, results).passed
    for key, failed in failures.items():
        results[key]["runtime"]["caseOutcomes"] = {
            name: name not in failed for name in bundle.verifier.case_ids
        }
    assert engine.HubEngineValidator.validate_controls(bundle, results).passed


def test_every_control_engine_log_is_persisted_privately(
    tmp_path: Path, dst_bundle: SynthesisBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    labels: list[str] = []

    class EvaluatingHub:
        task_keys = (f"dst/synth/{dst_bundle.candidate.id}",)
        discovery_errors: list[dict[str, str]] = []

        def __init__(self, *, settings: Settings, manifest_paths: tuple[Path, ...]):
            del manifest_paths
            self.settings = settings

        def evaluate_task(self, task_key: str, submission: Path, profile: str) -> dict[str, object]:
            # Like the real Hub: the runtime log is written under the state
            # directory and never returned inline with the result.
            del task_key, profile
            labels.append(submission.name)
            run_id = f"run-{len(labels)}"
            log = self.settings.state_dir / "runs" / run_id / "runtime.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(f"server log for {submission.name}\n", encoding="utf-8")
            result = {"complete": True, "passed": False, "runtime": {"status": "failed"}}
            return {"id": run_id, "result": result}

    validator = engine.HubEngineValidator(tmp_path)
    monkeypatch.setattr(validator.publisher, "stage", lambda *_args: tmp_path / "staged-pack")
    monkeypatch.setattr(engine, "BenchmarkHub", EvaluatingHub)
    run_root = tmp_path / ".rhenium/authoring/runs/run-logs"
    run_root.mkdir(parents=True)
    report = validator.validate(run_root, dst_bundle)
    assert not report.passed
    logs = run_root / "candidates" / dst_bundle.candidate.id / "engine-logs"
    assert sorted(path.name for path in logs.iterdir()) == sorted(f"{label}.log" for label in labels)
    assert {"combined-base.log", "gold.log"} <= {path.name for path in logs.iterdir()}
    for path in logs.iterdir():
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.read_text(encoding="utf-8") == f"server log for {path.stem}\n"
    assert logs.stat().st_mode & 0o777 == 0o700
