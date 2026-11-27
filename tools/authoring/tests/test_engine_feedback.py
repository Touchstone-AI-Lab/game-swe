from __future__ import annotations

from rhenium_authoring.engine_feedback import plan_engine_repair
from rhenium_authoring.models import (
    SynthesisBundle,
    SynthInterfaceContract,
    ValidationCheck,
    ValidationReport,
)


def _report(
    bundle: SynthesisBundle, checks: tuple[ValidationCheck, ...], *, passed: bool = False
) -> ValidationReport:
    return ValidationReport(
        candidate_id=bundle.candidate.id,
        complete=passed,
        passed=passed,
        base_failed=passed,
        gold_passed=passed,
        engine_backed=passed,
        checks=checks,
    )


def _bundle_with_contract(
    dst_bundle: SynthesisBundle, contract: SynthInterfaceContract
) -> SynthesisBundle:
    return dst_bundle.model_copy(update={"interface_contract": contract})


def test_passed_or_unavailable_validation_plans_no_repair(
    dst_bundle: SynthesisBundle,
) -> None:
    passed = _report(dst_bundle, (), passed=True)
    assert plan_engine_repair(dst_bundle, passed) is None
    unavailable = _report(dst_bundle, (
        ValidationCheck(id="real-engine", status="unavailable", message="not prepared"),
    ))
    assert plan_engine_repair(dst_bundle, unavailable) is None
    # A mixed report with any unavailable control is still operator work.
    mixed = _report(dst_bundle, (
        ValidationCheck(id="gold", status="failed", message="failed"),
        ValidationCheck(id="combined-base", status="unavailable", message="skipped"),
    ))
    assert plan_engine_repair(dst_bundle, mixed) is None


def test_gold_failure_routes_to_fixed_without_case_ids(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    capsules = dst_bundle.candidate.capsules
    contract = dst_interface_contract.model_copy(update={
        "entrypoints": tuple(
            entry.model_copy(update={"id": f"entry-{index}"})
            for index, entry in enumerate(dst_interface_contract.entrypoints)
        ),
        "capsule_entrypoints": {
            capsules[0].capsule_id: ("entry-0",),
            capsules[1].capsule_id: ("entry-1",),
        },
    })
    bundle = _bundle_with_contract(dst_bundle, contract)
    report = _report(bundle, (
        ValidationCheck(id="combined-base", status="passed", message="ok"),
        ValidationCheck(
            id="gold", status="failed", message="failed",
            observed_complete=True, observed_passed=False, observed_counts=(0, 3),
            expected_failing_cases=(),
            observed_failing_cases=("capacity", "once", "sentinel"),
            observed_case_ids=("capacity", "once", "sentinel"),
        ),
    ))
    plan = plan_engine_repair(bundle, report)
    assert plan is not None and plan.target == "fixed"
    joined = " ".join(plan.findings)
    for case_id in bundle.verifier.case_ids:
        assert case_id not in joined
    assert "entry-0" in joined and "entry-1" in joined
    assert "baseline" in joined  # the sentinel failure is aggregated, not named
    assert "3 of 3" in joined


def test_gold_incomplete_run_still_routes_to_fixed(dst_bundle: SynthesisBundle) -> None:
    report = _report(dst_bundle, (
        ValidationCheck(id="combined-base", status="passed", message="ok"),
        ValidationCheck(
            id="gold", status="failed", message="failed",
            observed_complete=False, observed_passed=False,
        ),
    ))
    plan = plan_engine_repair(dst_bundle, report)
    assert plan is not None and plan.target == "fixed"
    assert any("did not run to completion" in finding for finding in plan.findings)


def test_case_set_mismatch_routes_to_verifier_with_case_ids(
    dst_bundle: SynthesisBundle,
) -> None:
    report = _report(dst_bundle, (
        ValidationCheck(id="gold", status="passed", message="ok"),
        ValidationCheck(
            id="combined-base", status="failed", message="wrong cases",
            observed_complete=True, observed_passed=False,
            expected_failing_cases=("capacity", "once"),
            observed_failing_cases=("once", "spurious"),
            observed_case_ids=("once", "sentinel", "spurious"),
        ),
    ))
    plan = plan_engine_repair(dst_bundle, report)
    assert plan is not None and plan.target == "verifier"
    joined = " ".join(plan.findings)
    assert "capacity" in joined  # declared but never executed
    assert "spurious" in joined  # executed but never declared


def test_wrong_failure_identity_routes_to_defects(dst_bundle: SynthesisBundle) -> None:
    report = _report(dst_bundle, (
        ValidationCheck(id="gold", status="passed", message="ok"),
        ValidationCheck(
            id="combined-base", status="failed", message="wrong failures",
            observed_complete=True, observed_passed=False, observed_counts=(2, 1),
            expected_failing_cases=("capacity", "once"),
            observed_failing_cases=("once",),
            observed_case_ids=("capacity", "once", "sentinel"),
        ),
        ValidationCheck(
            id="ablation-behavior-bbbbbbbbbbbbbbbb", status="failed", message="passed",
            observed_complete=True, observed_passed=True, observed_counts=(3, 0),
            expected_failing_cases=("capacity",),
            observed_failing_cases=(),
            observed_case_ids=("capacity", "once", "sentinel"),
        ),
    ))
    plan = plan_engine_repair(dst_bundle, report)
    assert plan is not None and plan.target == "defects"
    joined = " ".join(plan.findings)
    assert "capacity" in joined and "once" in joined
    assert "passed instead of failing" in joined


def test_count_only_games_still_route_defect_repairs(dst_bundle: SynthesisBundle) -> None:
    report = _report(dst_bundle, (
        ValidationCheck(id="gold", status="passed", message="ok"),
        ValidationCheck(
            id="combined-base", status="failed", message="wrong counts",
            observed_complete=True, observed_passed=False, observed_counts=(3, 0),
        ),
    ))
    plan = plan_engine_repair(dst_bundle, report)
    assert plan is not None and plan.target == "defects"
    assert any("0 assertion(s) failed and 3 passed" in finding for finding in plan.findings)


def test_report_without_control_checks_plans_no_repair(dst_bundle: SynthesisBundle) -> None:
    report = _report(dst_bundle, (
        ValidationCheck(id="gold", status="passed", message="ok"),
    ))
    assert plan_engine_repair(dst_bundle, report) is None


def test_repeated_defect_mismatch_escalates_to_verifier_case_drop(
    dst_bundle: SynthesisBundle,
) -> None:
    # "extra" is declared FAIL_TO_PASS for its capsule but never fails
    # anywhere; its capsule keeps "once", so dropping it is safe.
    capsules = dst_bundle.candidate.capsules
    bundle = dst_bundle.model_copy(update={
        "verifier": dst_bundle.verifier.model_copy(update={
            "case_ids": ("sentinel", "once", "capacity", "extra"),
            "capsule_cases": {
                capsules[0].capsule_id: ("once", "extra"),
                capsules[1].capsule_id: ("capacity",),
            },
        }),
    })
    report = _report(bundle, (
        ValidationCheck(id="gold", status="passed", message="ok"),
        ValidationCheck(
            id="combined-base", status="failed", message="wrong failures",
            observed_complete=True, observed_passed=False,
            expected_failing_cases=("capacity", "extra", "once"),
            observed_failing_cases=("capacity", "once"),
            observed_case_ids=("capacity", "extra", "once", "sentinel"),
        ),
    ))
    first = plan_engine_repair(bundle, report)
    assert first is not None and first.target == "defects" and not first.drop_cases
    second = plan_engine_repair(bundle, report, first)
    assert second is not None and second.target == "verifier"
    assert second.drop_cases == ("extra",)
    assert "extra" in " ".join(second.findings)


def test_case_drop_never_empties_a_capsule(dst_bundle: SynthesisBundle) -> None:
    # Both of a capsule's cases never fail: dropping them would erase the
    # capsule's evidence, so the plan stays a defect repair.
    bundle = dst_bundle.model_copy(update={
        "verifier": dst_bundle.verifier.model_copy(update={
            "capsule_cases": {
                dst_bundle.candidate.capsules[0].capsule_id: ("once",),
                dst_bundle.candidate.capsules[1].capsule_id: ("capacity",),
            },
        }),
    })
    report = _report(bundle, (
        ValidationCheck(id="gold", status="passed", message="ok"),
        ValidationCheck(
            id="combined-base", status="failed", message="wrong failures",
            observed_complete=True, observed_passed=False,
            expected_failing_cases=("capacity", "once"),
            observed_failing_cases=(),
            observed_case_ids=("capacity", "once", "sentinel"),
        ),
    ))
    first = plan_engine_repair(bundle, report)
    assert first is not None and first.target == "defects"
    second = plan_engine_repair(bundle, report, first)
    assert second is not None and second.target == "defects" and not second.drop_cases


def test_suite_that_cannot_run_anywhere_routes_to_the_verifier_first(
    dst_bundle: SynthesisBundle,
) -> None:
    broken = "attempt to call method 'chat_messages' (a nil value)"
    report = _report(dst_bundle, (
        ValidationCheck(
            id="combined-base", status="failed", message="failed",
            observed_complete=True, observed_passed=False, observed_counts=(0, 3),
        ),
        ValidationCheck(
            id="gold", status="failed", message="failed",
            observed_complete=True, observed_passed=False, observed_counts=(0, 3),
            observed_messages=(broken,),
        ),
    ))
    first = plan_engine_repair(dst_bundle, report)
    assert first is not None and first.target == "verifier"
    assert any(broken in finding for finding in first.findings)
    # If the suite was already repaired and still nothing passes, fixed is next.
    second = plan_engine_repair(dst_bundle, report, first)
    assert second is not None and second.target == "fixed"


def test_partial_gold_failure_still_routes_to_fixed(dst_bundle: SynthesisBundle) -> None:
    report = _report(dst_bundle, (
        ValidationCheck(
            id="combined-base", status="passed", message="ok",
            observed_complete=True, observed_passed=False, observed_counts=(1, 2),
        ),
        ValidationCheck(
            id="gold", status="failed", message="failed",
            observed_complete=True, observed_passed=False, observed_counts=(2, 1),
        ),
    ))
    plan = plan_engine_repair(dst_bundle, report)
    assert plan is not None and plan.target == "fixed"
