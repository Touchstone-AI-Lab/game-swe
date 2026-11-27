from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import HttpUrl
from rhenium_authoring.models import (
    CandidateStatus,
    HistoricalFix,
    PublicationRecord,
    RunMode,
    RunStatus,
    SourceKind,
    SourceProject,
    SynthesisBundle,
    SynthInterfaceContract,
    ValidationCheck,
    ValidationReport,
)
from rhenium_authoring.pipeline import AuthoringPipeline, AuthoringRunError
from rhenium_authoring.state import AuthoringStore


class FakeSource:
    def discover(self, game_id: str, limit: int) -> list[SourceProject]:
        del limit
        return [
            SourceProject(
                source=SourceKind.GITHUB,
                external_id="example/private-mod",
                game_id=game_id,
                project_url=HttpUrl("https://github.com/example/private-mod"),
                source_url=HttpUrl("https://github.com/example/private-mod"),
                license_spdx="MIT",
            )
        ]

    def historical_fixes(self, project: SourceProject, limit: int) -> list[HistoricalFix]:
        raise AssertionError("history must use the dedicated GitHub adapter")


class FakeGitHub:
    def __init__(self, bundle: SynthesisBundle):
        self.bundle = bundle

    @staticmethod
    def repository_name(url: str) -> str:
        del url
        return "example/private-mod"

    def historical_fixes(self, project: SourceProject, limit: int) -> list[Any]:
        del project, limit
        return list(self.bundle.provenance)


class FakeSynthesizer:
    def __init__(self, bundle: SynthesisBundle, interface: SynthInterfaceContract):
        self.bundle = bundle
        self.interface = interface
        self.index = 0
        self.fixed_feedback: list[tuple[str, ...]] = []
        self.verifier_feedback: list[tuple[str, ...]] = []
        self.defect_feedback: list[tuple[str, ...]] = []
        self.case_contracts: list[Any] = []
        self.reviews = 0
        self.extract_feedback: list[tuple[str, ...]] = []
        self.interface_feedback: list[tuple[str, ...]] = []

    def extract(self, fix: Any, *, feedback: Any = ()) -> Any:
        del fix
        self.extract_feedback.append(tuple(feedback))
        value = self.bundle.candidate.capsules[self.index % len(self.bundle.candidate.capsules)]
        self.index += 1
        return value

    def compose(self, capsules: Any, max_capsules: int = 7) -> list[Any]:
        del max_capsules
        return [self.bundle.candidate] if capsules else []

    def design_interface(self, candidate: Any, contract: Any, *, feedback: Any = ()) -> Any:
        del candidate, contract
        self.interface_feedback.append(tuple(feedback))
        return self.interface

    def generate_fixed(self, candidate: Any, interface: Any, contract: Any, *, feedback: Any = ()) -> Any:
        del candidate, contract
        assert interface == self.interface
        self.fixed_feedback.append(tuple(feedback))
        return self.bundle.fixed

    def generate_verifier(
        self,
        candidate: Any,
        interface: Any,
        contract: Any,
        *,
        feedback: Any = (),
        case_contract: Any = None,
    ) -> Any:
        del candidate, contract
        assert interface == self.interface
        self.verifier_feedback.append(tuple(feedback))
        self.case_contracts.append(case_contract)
        return self.bundle.verifier

    def inject_defects(
        self,
        candidate: Any,
        fixed: Any,
        interface: Any,
        verifier: Any = None,
        feedback: Any = (),
    ) -> Any:
        del candidate, fixed, verifier
        assert interface == self.interface
        self.defect_feedback.append(tuple(feedback))
        return self.bundle.base

    def author_prompt(self, candidate: Any, interface: Any) -> Any:
        del candidate
        assert interface == self.interface
        return self.bundle.prompt

    def review(self, *args: Any) -> Any:
        del args
        self.reviews += 1
        return self.bundle.review


class FailingSynthesizer(FakeSynthesizer):
    def extract(self, fix: Any, *, feedback: Any = ()) -> Any:
        del fix, feedback
        raise RuntimeError("Kimi behavior fact extractor failed (HTTP 404)")


class FailingFixedSynthesizer(FakeSynthesizer):
    def generate_fixed(self, candidate: Any, interface: Any, contract: Any, *, feedback: Any = ()) -> Any:
        raise RuntimeError("Kimi fixed-project stage failed")


class FakeValidator:
    def __init__(self, reports: list[ValidationReport]):
        self.reports = reports

    def validate(self, run_root: Path, bundle: SynthesisBundle) -> ValidationReport:
        del run_root, bundle
        return self.reports.pop(0)


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[str] = []

    def publish(self, bundle: SynthesisBundle, validation: ValidationReport) -> PublicationRecord:
        del validation
        self.published.append(bundle.candidate.id)
        return PublicationRecord(
            candidate_id=bundle.candidate.id,
            task_key=f"dst/synth/{bundle.candidate.id}",
            catalog_version="1.0.0",
        )


def test_yolo_pipeline_publishes_only_after_engine_validation(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    (tmp_path / ".rhenium").mkdir()
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    publisher = FakePublisher()
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {"github": FakeSource()},
        FakeGitHub(dst_bundle),  # type: ignore[arg-type]
        validator=FakeValidator([passing_validation]),  # type: ignore[arg-type]
        publisher=publisher,  # type: ignore[arg-type]
    )
    run_id = pipeline.run(
        mode=RunMode.YOLO,
        source_names=("github",),
        game_ids=("dst",),
        limit=2,
    )
    assert store.run(run_id)["status"] == RunStatus.COMPLETE.value
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.PUBLISHED.value
    assert publisher.published == [dst_bundle.candidate.id]


def test_action_required_run_resumes_without_model_or_source_credentials(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    (tmp_path / ".rhenium").mkdir()
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    unavailable = ValidationReport(
        candidate_id=dst_bundle.candidate.id,
        complete=False,
        passed=False,
        base_failed=False,
        gold_passed=False,
        engine_backed=False,
        checks=(ValidationCheck(id="real-engine", status="unavailable", message="runtime is not prepared"),),
    )
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {"github": FakeSource()},
        FakeGitHub(dst_bundle),  # type: ignore[arg-type]
        validator=FakeValidator([unavailable]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    run_id = pipeline.run(
        mode=RunMode.REVIEW,
        source_names=("github",),
        game_ids=("dst",),
        limit=2,
    )
    assert store.run(run_id)["status"] == RunStatus.ACTION_REQUIRED.value

    resume = AuthoringPipeline(
        tmp_path,
        store,
        None,
        {},
        None,
        validator=FakeValidator([passing_validation]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    resume.resume(run_id)
    assert store.run(run_id)["status"] == RunStatus.AWAITING_REVIEW.value
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value


def test_failed_synthesis_persists_private_retry_input(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    (tmp_path / ".rhenium").mkdir()
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FailingSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {"github": FakeSource()},
        FakeGitHub(dst_bundle),  # type: ignore[arg-type]
        validator=FakeValidator([]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    try:
        pipeline.run(
            mode=RunMode.REVIEW,
            source_names=("github",),
            game_ids=("dst",),
            limit=2,
        )
    except AuthoringRunError as error:
        run_id = error.run_id
    else:
        raise AssertionError("expected synthesis failure")
    persisted = tmp_path / ".rhenium" / "authoring" / "runs" / run_id / "historical-fixes.json"
    assert persisted.is_file()
    assert persisted.stat().st_mode & 0o777 == 0o600
    assert store.run(run_id)["status"] == RunStatus.FAILED.value


def test_successful_model_checkpoints_survive_a_later_stage_failure(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FailingFixedSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {},
        None,
    )
    run_id = pipeline.run(
        mode=RunMode.REVIEW,
        source_names=(),
        game_ids=("dst",),
        limit=2,
        seed_fixes=dst_bundle.provenance,
    )
    # The model failure rejects the candidate; the run itself completes.
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "Kimi fixed-project stage failed" in str(record["reason"])
    checkpoints = tmp_path / ".rhenium/authoring/runs" / run_id / "checkpoints"
    interface = checkpoints / dst_bundle.candidate.id / "interface.json"
    assert SynthInterfaceContract.model_validate_json(interface.read_text()) == dst_interface_contract
    assert interface.stat().st_mode & 0o777 == 0o600
    assert interface.parent.stat().st_mode & 0o777 == 0o700
    assert checkpoints.stat().st_mode & 0o777 == 0o700
    assert len(list((checkpoints / "capsules").glob("*.json"))) == 2
    assert not (interface.parent / "fixed.json").exists()


@pytest.mark.parametrize(
    ("game_id", "required", "starter_prefix"),
    [
        (
            "stardew-valley",
            ("Directory.Build.props", "Synthetic.sln", "Synthetic.csproj", "manifest.json"),
            "mod/",
        ),
        ("isaac-rebirth", ("main.lua", "metadata.xml"), "mod/"),
        ("minecraft", ("src/main/resources/plugin.yml",), "plugin/"),
    ],
)
def test_pipeline_rejects_interface_paths_below_the_starter_directory(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
    game_id: str,
    required: tuple[str, ...],
    starter_prefix: str,
) -> None:
    bundle = dst_bundle.model_copy(
        update={
            "candidate": dst_bundle.candidate.model_copy(update={"game_id": game_id}),
        }
    )
    interface = dst_interface_contract.model_copy(
        update={
            "game_id": game_id,
            "project_files": (
                *dst_interface_contract.project_files,
                *required,
                f"{starter_prefix}extra/File.txt",
            ),
        }
    )
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(bundle, interface),
        {},
        None,  # type: ignore[arg-type]
    )
    run_id = pipeline.run(
        mode=RunMode.REVIEW,
        source_names=(),
        game_ids=(game_id,),
        limit=2,
        seed_fixes=bundle.provenance,
    )
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "relative to the mod root" in str(record["reason"])


def test_pipeline_rejects_interface_missing_required_game_entrypoint(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    interface = dst_interface_contract.model_copy(
        update={
            "project_files": tuple(
                path for path in dst_interface_contract.project_files if path != "modmain.lua"
            )
        }
    )
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(dst_bundle, interface),  # type: ignore[arg-type]
        {},
        None,
    )
    run_id = pipeline.run(
        mode=RunMode.REVIEW,
        source_names=(),
        game_ids=("dst",),
        limit=2,
        seed_fixes=dst_bundle.provenance,
    )
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "omitted required game project files" in str(record["reason"])


def _report(
    dst_bundle: SynthesisBundle, checks: tuple[ValidationCheck, ...], **flags: bool
) -> ValidationReport:
    values = {
        "complete": True,
        "passed": False,
        "base_failed": True,
        "gold_passed": True,
        "engine_backed": True,
        **flags,
    }
    return ValidationReport(candidate_id=dst_bundle.candidate.id, checks=checks, **values)


def _gold_failure(dst_bundle: SynthesisBundle) -> ValidationReport:
    return _report(
        dst_bundle,
        gold_passed=False,
        checks=(
            ValidationCheck(id="combined-base", status="passed", message="ok"),
            ValidationCheck(
                id="gold",
                status="failed",
                message="gold failed",
                observed_complete=True,
                observed_passed=False,
                observed_counts=(1, 2),
                expected_failing_cases=(),
                observed_failing_cases=("capacity", "once"),
                observed_case_ids=("capacity", "once", "sentinel"),
            ),
        ),
    )


def _pipeline(
    tmp_path: Path,
    synthesizer: FakeSynthesizer,
    dst_bundle: SynthesisBundle,
    reports: list[ValidationReport],
) -> tuple[AuthoringPipeline, AuthoringStore]:
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        synthesizer,  # type: ignore[arg-type]
        {"github": FakeSource()},
        FakeGitHub(dst_bundle),  # type: ignore[arg-type]
        validator=FakeValidator(reports),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    return pipeline, store


def test_gold_failure_triggers_one_fixed_repair_round(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    # Neutral entrypoint IDs so the barrier check below is not confused by
    # case-ID substrings inside entrypoint names.
    capsules = dst_bundle.candidate.capsules
    contract = dst_interface_contract.model_copy(
        update={
            "entrypoints": tuple(
                entry.model_copy(update={"id": f"entry-{index}"})
                for index, entry in enumerate(dst_interface_contract.entrypoints)
            ),
            "capsule_entrypoints": {
                capsules[0].capsule_id: ("entry-0",),
                capsules[1].capsule_id: ("entry-1",),
            },
        }
    )
    synthesizer = FakeSynthesizer(dst_bundle, contract)
    pipeline, store = _pipeline(
        tmp_path, synthesizer, dst_bundle, [_gold_failure(dst_bundle), passing_validation]
    )
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    # The implementer received engine feedback on the repair round only.
    assert synthesizer.fixed_feedback[0] == ()
    repair_feedback = synthesizer.fixed_feedback[1]
    assert repair_feedback
    # Information barrier: the implementer never sees verifier case IDs.
    joined = " ".join(repair_feedback)
    for case_id in dst_bundle.verifier.case_ids:
        assert case_id not in joined
    # Aggregation names the contracted entrypoints instead.
    assert "entry-0" in joined and "entry-1" in joined
    # Defects were re-injected onto the repaired implementation.
    assert len(synthesizer.defect_feedback) == 2
    # The repaired candidate re-passed independent review.
    assert synthesizer.reviews == 2
    checkpoints = tmp_path / ".rhenium/authoring/runs" / run_id / "checkpoints"
    candidate_checkpoints = checkpoints / dst_bundle.candidate.id
    assert (candidate_checkpoints / "fixed-repair1.json").is_file()
    assert (candidate_checkpoints / "review-repair1.json").is_file()
    assert (candidate_checkpoints / "validation.json").is_file()


def test_defect_mismatch_routes_case_ids_to_the_injector(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    failed = _report(
        dst_bundle,
        base_failed=False,
        checks=(
            ValidationCheck(id="gold", status="passed", message="ok"),
            ValidationCheck(
                id="combined-base",
                status="failed",
                message="wrong failure set",
                observed_complete=True,
                observed_passed=False,
                observed_counts=(2, 1),
                expected_failing_cases=("capacity", "once"),
                observed_failing_cases=("once",),
                observed_case_ids=("capacity", "once", "sentinel"),
            ),
        ),
    )
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [failed, passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    assert len(synthesizer.fixed_feedback) == 1
    assert synthesizer.defect_feedback[0] == ()
    repair_feedback = " ".join(synthesizer.defect_feedback[1])
    assert "capacity" in repair_feedback and "once" in repair_feedback


def test_case_set_mismatch_routes_frozen_contract_to_the_verifier(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    failed = _report(
        dst_bundle,
        base_failed=False,
        checks=(
            ValidationCheck(id="gold", status="passed", message="ok"),
            ValidationCheck(
                id="combined-base",
                status="failed",
                message="unexpected case set",
                observed_complete=True,
                observed_passed=False,
                observed_counts=(1, 1),
                expected_failing_cases=("capacity", "once"),
                observed_failing_cases=("once",),
                observed_case_ids=("once", "sentinel"),
            ),
        ),
    )
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [failed, passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    assert len(synthesizer.verifier_feedback) == 2
    assert synthesizer.verifier_feedback[1]
    assert "capacity" in " ".join(synthesizer.verifier_feedback[1])
    # The repair freezes the declared case contract.
    assert synthesizer.case_contracts == [None, dst_bundle.verifier]


def test_unavailable_engine_never_triggers_model_repair(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    unavailable = ValidationReport(
        candidate_id=dst_bundle.candidate.id,
        complete=False,
        passed=False,
        base_failed=False,
        gold_passed=False,
        engine_backed=False,
        checks=(ValidationCheck(id="real-engine", status="unavailable", message="runtime is not prepared"),),
    )
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [unavailable])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.run(run_id)["status"] == RunStatus.ACTION_REQUIRED.value
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.ACTION_REQUIRED.value
    assert synthesizer.fixed_feedback == [()]
    assert synthesizer.reviews == 1


def test_failed_repair_round_rejects_with_repair_reason(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(
        tmp_path,
        synthesizer,
        dst_bundle,
        [_gold_failure(dst_bundle), _gold_failure(dst_bundle)],
    )
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "after 1 engine repair round(s)" in str(record["reason"])
    assert synthesizer.reviews == 2


def test_zero_repair_rounds_keeps_single_shot_semantics(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        synthesizer,  # type: ignore[arg-type]
        {"github": FakeSource()},
        FakeGitHub(dst_bundle),  # type: ignore[arg-type]
        validator=FakeValidator([_gold_failure(dst_bundle)]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
        engine_repair_rounds=0,
    )
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "engine repair round" not in str(record["reason"])
    assert synthesizer.fixed_feedback == [()]


def _unavailable_report(dst_bundle: SynthesisBundle) -> ValidationReport:
    return ValidationReport(
        candidate_id=dst_bundle.candidate.id,
        complete=False,
        passed=False,
        base_failed=False,
        gold_passed=False,
        engine_backed=False,
        checks=(ValidationCheck(id="real-engine", status="unavailable", message="runtime is not prepared"),),
    )


def _action_required_run(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> tuple[AuthoringStore, str]:
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [_unavailable_report(dst_bundle)])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.run(run_id)["status"] == RunStatus.ACTION_REQUIRED.value
    return store, run_id


def test_resume_repairs_engine_failures_with_model_service(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    store, run_id = _action_required_run(tmp_path, dst_bundle, dst_interface_contract)
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    resume = AuthoringPipeline(
        tmp_path,
        store,
        synthesizer,  # type: ignore[arg-type]
        {},
        None,
        validator=FakeValidator([_gold_failure(dst_bundle), passing_validation]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    resume.resume(run_id)
    assert store.run(run_id)["status"] == RunStatus.AWAITING_REVIEW.value
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    # The implementer received engine feedback and defects were re-injected.
    assert len(synthesizer.fixed_feedback) == 1 and synthesizer.fixed_feedback[0]
    assert len(synthesizer.defect_feedback) == 1
    # The repaired candidate re-passed independent review.
    assert synthesizer.reviews == 1
    checkpoints = tmp_path / ".rhenium/authoring/runs" / run_id / "checkpoints"
    candidate_checkpoints = checkpoints / dst_bundle.candidate.id
    assert (candidate_checkpoints / "fixed-resume-repair1.json").is_file()
    assert (candidate_checkpoints / "review-resume-repair1.json").is_file()
    assert (candidate_checkpoints / "validation-resume0.json").is_file()
    assert (candidate_checkpoints / "validation-resume1.json").is_file()


def test_resume_without_model_service_never_repairs(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    store, run_id = _action_required_run(tmp_path, dst_bundle, dst_interface_contract)
    resume = AuthoringPipeline(
        tmp_path,
        store,
        None,
        {},
        None,
        validator=FakeValidator([_gold_failure(dst_bundle)]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    resume.resume(run_id)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "engine repair round" not in str(record["reason"])


def test_resume_repair_that_still_fails_rejects_with_repair_reason(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    store, run_id = _action_required_run(tmp_path, dst_bundle, dst_interface_contract)
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    resume = AuthoringPipeline(
        tmp_path,
        store,
        synthesizer,  # type: ignore[arg-type]
        {},
        None,
        validator=FakeValidator([_gold_failure(dst_bundle), _gold_failure(dst_bundle)]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    resume.resume(run_id)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "after 1 engine repair round(s)" in str(record["reason"])


class RepairCrashSynthesizer(FakeSynthesizer):
    def generate_fixed(self, candidate: Any, interface: Any, contract: Any, *, feedback: Any = ()) -> Any:
        if feedback:
            raise ValueError("fixed implementer changed exact shared load metadata")
        return super().generate_fixed(candidate, interface, contract, feedback=feedback)


def test_resume_abandons_failed_repair_and_keeps_engine_verdict(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    store, run_id = _action_required_run(tmp_path, dst_bundle, dst_interface_contract)
    synthesizer = RepairCrashSynthesizer(dst_bundle, dst_interface_contract)
    resume = AuthoringPipeline(
        tmp_path,
        store,
        synthesizer,  # type: ignore[arg-type]
        {},
        None,
        validator=FakeValidator([_gold_failure(dst_bundle)]),  # type: ignore[arg-type]
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    resume.resume(run_id)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert store.run(run_id)["status"] == RunStatus.AWAITING_REVIEW.value


def test_crashed_resume_stays_resumable(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    store, run_id = _action_required_run(tmp_path, dst_bundle, dst_interface_contract)
    resume = AuthoringPipeline(
        tmp_path,
        store,
        None,
        {},
        None,
        validator=FakeValidator([]),  # type: ignore[arg-type]  # validator crash
        publisher=FakePublisher(),  # type: ignore[arg-type]
    )
    with pytest.raises(AuthoringRunError):
        resume.resume(run_id)
    assert store.run(run_id)["status"] == RunStatus.ACTION_REQUIRED.value


class FlakyReviewSynthesizer(FakeSynthesizer):
    """Rejects the first independent review, approves afterwards."""

    def review(self, *args: Any) -> Any:
        self.reviews += 1
        if self.reviews == 1:
            return self.bundle.review.model_copy(
                update={"approved": False, "rationale": "first draft too weak"}
            )
        return self.bundle.review


def test_target_regenerates_rejected_candidates_until_validated(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = FlakyReviewSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    run_id = pipeline.run(
        mode=RunMode.REVIEW,
        source_names=("github",),
        game_ids=("dst",),
        limit=2,
        target=1,
    )
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    assert synthesizer.reviews == 2
    checkpoints = tmp_path / ".rhenium/authoring/runs" / run_id / "checkpoints"
    # The rejected attempt's private artifacts were rotated aside, not lost.
    assert (checkpoints / f"{dst_bundle.candidate.id}-attempt1" / "review.json").is_file()
    assert (checkpoints / dst_bundle.candidate.id / "review.json").is_file()


def test_without_target_a_rejected_candidate_is_not_regenerated(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = FlakyReviewSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [])
    run_id = pipeline.run(
        mode=RunMode.REVIEW,
        source_names=("github",),
        game_ids=("dst",),
        limit=2,
    )
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.REJECTED.value
    assert synthesizer.reviews == 1


class LeakyExtractSynthesizer(FakeSynthesizer):
    """First capsule extraction quotes source identity; the retry is clean."""

    def extract(self, fix: Any, *, feedback: Any = ()) -> Any:
        value = FakeSynthesizer.extract(self, fix, feedback=feedback)
        if len(self.extract_feedback) == 1:
            self.index -= 1  # the clean retry re-serves the same capsule
            return value.model_copy(update={"observed_symptoms": ("Delivery repeats in private-mod.",)})
        return value


def test_leaky_capsule_is_retried_with_neutral_feedback(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = LeakyExtractSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    # The retry carried neutral feedback that never repeats the leaked term.
    assert synthesizer.extract_feedback[0] == ()
    assert synthesizer.extract_feedback[1]
    assert "private-mod" not in " ".join(synthesizer.extract_feedback[1])


class AlwaysLeakyExtractSynthesizer(FakeSynthesizer):
    def extract(self, fix: Any, *, feedback: Any = ()) -> Any:
        value = FakeSynthesizer.extract(self, fix, feedback=feedback)
        self.index -= 1
        return value.model_copy(update={"observed_symptoms": ("Delivery repeats in private-mod.",)})


def test_undeidentifiable_fixes_are_dropped_and_run_fails_closed(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = AlwaysLeakyExtractSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [])
    with pytest.raises(AuthoringRunError, match="at least two eligible fixes"):
        pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    del store


class LeakyPromptSynthesizer(FakeSynthesizer):
    def author_prompt(self, candidate: Any, interface: Any) -> Any:
        prompt = FakeSynthesizer.author_prompt(self, candidate, interface)
        return prompt.model_copy(update={"markdown": prompt.markdown + "\nUpstream is private-mod."})


def test_candidate_leak_rejects_the_candidate_not_the_run(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = LeakyPromptSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "identity terms" in str(record["reason"])
    assert store.run(run_id)["status"] == RunStatus.AWAITING_REVIEW.value


def test_model_stage_failure_rejects_the_candidate_not_the_run(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = FailingFixedSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    record = store.candidates(run_id)[0]
    assert record["status"] == CandidateStatus.REJECTED.value
    assert "Kimi fixed-project stage failed" in str(record["reason"])
    assert store.run(run_id)["status"] == RunStatus.AWAITING_REVIEW.value


class WrongIdentityExtractSynthesizer(FakeSynthesizer):
    """First extraction invents a different capsule identity; retry is clean."""

    def extract(self, fix: Any, *, feedback: Any = ()) -> Any:
        value = FakeSynthesizer.extract(self, fix, feedback=feedback)
        if len(self.extract_feedback) == 1:
            self.index -= 1
            raise ValueError("fact extractor changed the required clean-room identity")
        return value


def test_wrong_extract_identity_is_retried_with_feedback(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = WrongIdentityExtractSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    assert synthesizer.extract_feedback[0] == ()
    assert any("required_capsule_id" in item for item in synthesizer.extract_feedback[1])


class LeakyInterfaceSynthesizer(FakeSynthesizer):
    """First interface design quotes a source file stem; the retry is clean."""

    def design_interface(self, candidate: Any, contract: Any, *, feedback: Any = ()) -> Any:
        value = FakeSynthesizer.design_interface(self, candidate, contract, feedback=feedback)
        if len(self.interface_feedback) == 1:
            return value.model_copy(update={"loader_identity": "private-mod"})
        return value


def test_leaky_interface_is_retried_with_neutral_feedback(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = LeakyInterfaceSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    assert synthesizer.interface_feedback[0] == ()
    assert synthesizer.interface_feedback[1]
    assert "private-mod" not in " ".join(synthesizer.interface_feedback[1])


def test_composites_validated_in_earlier_runs_are_skipped(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    first = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    assert store.candidates(first)[0]["status"] == CandidateStatus.VALIDATED.value
    again = FakeSynthesizer(dst_bundle, dst_interface_contract)
    pipeline2, _ = (
        AuthoringPipeline(
            tmp_path,
            store,
            again,  # type: ignore[arg-type]
            {"github": FakeSource()},
            FakeGitHub(dst_bundle),  # type: ignore[arg-type]
            validator=FakeValidator([]),  # type: ignore[arg-type]
            publisher=FakePublisher(),  # type: ignore[arg-type]
        ),
        store,
    )
    second = pipeline2.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2)
    # The same capsule composition is not regenerated or re-validated.
    assert store.candidates(second) == []
    assert again.reviews == 0


def test_harvest_quota_is_per_game_so_no_game_is_starved(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    visited: list[str] = []

    class TwoGameSource:
        def discover(self, game_id: str, limit: int) -> list[SourceProject]:
            del limit
            return [
                SourceProject(
                    source=SourceKind.GITHUB,
                    external_id=f"example/{game_id}-mod",
                    game_id=game_id,
                    project_url=HttpUrl(f"https://github.com/example/{game_id}-mod"),
                    source_url=HttpUrl(f"https://github.com/example/{game_id}-mod"),
                    license_spdx="MIT",
                )
            ]

    class ProlificGitHub:
        @staticmethod
        def repository_name(url: str) -> str:
            return url.removeprefix("https://github.com/")

        def historical_fixes(self, project: SourceProject, limit: int) -> list[Any]:
            visited.append(project.game_id)
            # The first game alone could fill a shared cap.
            return [
                fix.model_copy(update={"game_id": project.game_id}) for fix in dst_bundle.provenance
            ] * limit

    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {"github": TwoGameSource()},  # type: ignore[dict-item]
        ProlificGitHub(),  # type: ignore[arg-type]
    )
    fixes = pipeline._harvest(("github",), ("dst", "garrys-mod"), 2)
    assert visited == ["dst", "garrys-mod"]
    assert [fix.game_id for fix in fixes] == ["dst", "dst", "garrys-mod", "garrys-mod"]


class NotedReviewSynthesizer(FakeSynthesizer):
    """Rejects the first review with a rationale, approves afterwards."""

    def __init__(self, bundle: SynthesisBundle, interface: SynthInterfaceContract, note: str):
        super().__init__(bundle, interface)
        self.note = note

    def review(self, *args: Any) -> Any:
        self.reviews += 1
        if self.reviews == 1:
            return self.bundle.review.model_copy(update={"approved": False, "rationale": self.note})
        return self.bundle.review


def test_review_rationale_reaches_the_next_attempt_when_it_is_leak_free(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = NotedReviewSynthesizer(
        dst_bundle, dst_interface_contract, "The fixed project fails its own capacity case."
    )
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2, target=1)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    assert synthesizer.fixed_feedback[0] == ()
    assert any("fails its own capacity case" in item for item in synthesizer.fixed_feedback[1])
    assert any("fails its own capacity case" in item for item in synthesizer.verifier_feedback[1])


def test_leaky_review_rationale_is_withheld_from_the_next_attempt(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    passing_validation: ValidationReport,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    synthesizer = NotedReviewSynthesizer(
        dst_bundle, dst_interface_contract, "Copied a path from private-mod verbatim."
    )
    pipeline, store = _pipeline(tmp_path, synthesizer, dst_bundle, [passing_validation])
    run_id = pipeline.run(mode=RunMode.REVIEW, source_names=("github",), game_ids=("dst",), limit=2, target=1)
    assert store.candidates(run_id)[0]["status"] == CandidateStatus.VALIDATED.value
    # The reviewer saw private sources; its leaking words never cross the barrier.
    assert synthesizer.fixed_feedback == [(), ()]
    assert synthesizer.verifier_feedback == [(), ()]


def test_harvest_skips_fixes_used_by_earlier_runs(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    from rhenium_authoring.pipeline import fix_key, used_fix_keys

    class OneGameSource:
        def discover(self, game_id: str, limit: int) -> list[SourceProject]:
            del limit
            return [
                SourceProject(
                    source=SourceKind.GITHUB,
                    external_id="example/dst-mod",
                    game_id=game_id,
                    project_url=HttpUrl("https://github.com/example/dst-mod"),
                    source_url=HttpUrl("https://github.com/example/dst-mod"),
                    license_spdx="MIT",
                )
            ]

    first, second = (
        dst_bundle.provenance[0],
        dst_bundle.provenance[0].model_copy(update={"id": "github-pr-2", "fixed_sha": "f" * 40}),
    )

    class TwoFixGitHub:
        @staticmethod
        def repository_name(url: str) -> str:
            return url.removeprefix("https://github.com/")

        def historical_fixes(self, project: SourceProject, limit: int) -> list[Any]:
            del project, limit
            return [first, second]

    runs = tmp_path / ".rhenium" / "authoring" / "runs" / "author-old"
    runs.mkdir(parents=True)
    (runs / "historical-fixes.json").write_text(json.dumps([json.loads(first.model_dump_json())]))
    assert used_fix_keys(tmp_path) == frozenset({fix_key(first)})
    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {"github": OneGameSource()},  # type: ignore[dict-item]
        TwoFixGitHub(),  # type: ignore[arg-type]
    )
    assert [fix.id for fix in pipeline._harvest(("github",), ("dst",), 2)] == [first.id, second.id]
    fresh = pipeline._harvest(("github",), ("dst",), 2, used_fix_keys(tmp_path))
    assert [fix.id for fix in fresh] == [second.id]


def test_harvest_caps_fixes_per_repository(
    tmp_path: Path, dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    class OneGameSource:
        def discover(self, game_id: str, limit: int) -> list[SourceProject]:
            del limit
            return [
                SourceProject(
                    source=SourceKind.GITHUB,
                    external_id=f"example/{name}",
                    game_id=game_id,
                    project_url=HttpUrl(f"https://github.com/example/{name}"),
                    source_url=HttpUrl(f"https://github.com/example/{name}"),
                    license_spdx="MIT",
                )
                for name in ("prolific", "quiet")
            ]

    class ProlificGitHub:
        @staticmethod
        def repository_name(url: str) -> str:
            return url.removeprefix("https://github.com/")

        def historical_fixes(self, project: SourceProject, limit: int) -> list[Any]:
            count = limit if "prolific" in project.external_id else 1
            return [
                dst_bundle.provenance[0].model_copy(update={"id": f"{project.external_id}-{i}"})
                for i in range(count)
            ]

    store = AuthoringStore(tmp_path / ".rhenium/authoring/authoring.sqlite")
    pipeline = AuthoringPipeline(
        tmp_path,
        store,
        FakeSynthesizer(dst_bundle, dst_interface_contract),  # type: ignore[arg-type]
        {"github": OneGameSource()},  # type: ignore[dict-item]
        ProlificGitHub(),  # type: ignore[arg-type]
    )
    unlimited = pipeline._harvest(("github",), ("dst",), 6)
    assert [fix.id for fix in unlimited] == [f"example/prolific-{i}" for i in range(6)]
    capped = pipeline._harvest(("github",), ("dst",), 6, frozenset(), 2)
    assert [fix.id for fix in capped] == ["example/prolific-0", "example/prolific-1", "example/quiet-0"]
