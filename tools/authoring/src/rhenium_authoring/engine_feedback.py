from __future__ import annotations

from typing import Literal

from .models import (
    StrictModel,
    SynthesisBundle,
    ValidationCheck,
    ValidationReport,
)


class EngineRepairPlan(StrictModel):
    """One bounded repair routed to the role that owns the failing control."""

    target: Literal["fixed", "verifier", "defects"]
    findings: tuple[str, ...]
    # Cases the real engine proved cannot fail under their mapped defect
    # (expected to fail in a control, passed in every control). Set only on a
    # verifier-targeted plan that escalates from an unsuccessful defect
    # repair; the pipeline shrinks the frozen case contract by exactly these.
    drop_cases: tuple[str, ...] = ()


def plan_engine_repair(
    bundle: SynthesisBundle,
    validation: ValidationReport,
    previous: EngineRepairPlan | None = None,
) -> EngineRepairPlan | None:
    """Turn a failed two-way engine validation into role-scoped repair feedback.

    Returns None when no automated repair is safe: the validation passed, a
    required runtime was unavailable (the ACTION_REQUIRED path is operator
    work, never a model repair), or the report carries no failed control.

    Every finding is built only from ValidationReport receipts and case IDs
    the model itself authored. The fixed-implementer feedback deliberately
    aggregates failures per capsule entrypoint and never names verifier case
    IDs, preserving the barrier that keeps the implementer from seeing the
    independently generated verifier.
    """

    if validation.passed:
        return None
    if any(check.status == "unavailable" for check in validation.checks):
        return None
    checks = {check.id: check for check in validation.checks}
    gold = checks.get("gold")
    if gold is None or "combined-base" not in checks:
        return None
    if gold.status == "failed":
        base = checks["combined-base"]
        suite_cannot_run = (
            gold.observed_counts is not None
            and base.observed_counts is not None
            and gold.observed_counts[0] == 0
            and base.observed_counts[0] == 0
            and gold.observed_counts[1] > 0
        )
        already_tried = previous is not None and previous.target == "verifier"
        if suite_cannot_run and not already_tried:
            # Not even the always-pass sentinel passed on any tree, so the
            # suite itself is what cannot run; fix it before touching fixed.
            messages = gold.observed_messages or base.observed_messages or ()
            return EngineRepairPlan(
                target="verifier",
                findings=(
                    "No case passed on any tree on the real engine, including the reference "
                    "implementation and the always-pass sentinel, so the suite itself cannot run.",
                    *(f"Engine error from your suite: {message}" for message in messages),
                    "Use only the trusted runner interface named in the instructions; do not "
                    "call helper methods or fields it does not define.",
                ),
            )
        return EngineRepairPlan(target="fixed", findings=_fixed_findings(bundle, gold))
    verifier_findings = _verifier_findings(bundle, validation)
    if verifier_findings:
        return EngineRepairPlan(target="verifier", findings=verifier_findings)
    defect_findings = _defect_findings(validation)
    if defect_findings:
        if previous is not None and previous.target == "defects":
            unfailable = _unfailable_cases(bundle, validation)
            if unfailable:
                return EngineRepairPlan(
                    target="verifier",
                    findings=(
                        "The real engine proved these declared FAIL_TO_PASS "
                        "cases cannot fail under their mapped defects, even "
                        "after a defect repair: " + ", ".join(unfailable) + ".",
                        "Remove exactly those cases and keep every other "
                        "declared case, mapping, and assertion unchanged; the "
                        "reduced case contract is supplied.",
                    ),
                    drop_cases=unfailable,
                )
        return EngineRepairPlan(target="defects", findings=defect_findings)
    return None


def _unfailable_cases(
    bundle: SynthesisBundle, validation: ValidationReport
) -> tuple[str, ...]:
    """Expected-to-fail cases that failed in no control at all.

    Only cases whose removal leaves every capsule with at least one mapped
    case qualify; otherwise the task would lose a capsule's entire evidence
    and rejecting the candidate is the honest outcome.
    """

    expected: set[str] = set()
    observed: set[str] = set()
    for check in validation.checks:
        if check.expected_failing_cases is not None:
            expected.update(check.expected_failing_cases)
        if check.observed_failing_cases is not None:
            observed.update(check.observed_failing_cases)
        if check.status == "failed" and check.observed_failing_cases is None:
            return ()
        if (
            check.status == "failed"
            and check.observed_failing_cases is not None
            and check.expected_failing_cases is not None
            and not set(check.observed_failing_cases) <= set(check.expected_failing_cases)
        ):
            # An unexpected failure is not the never-fails pattern.
            return ()
    unfailable = expected - observed
    if not unfailable:
        return ()
    for cases in bundle.verifier.capsule_cases.values():
        if cases and not (set(cases) - unfailable):
            return ()
    return tuple(sorted(unfailable))


def _fixed_findings(bundle: SynthesisBundle, gold: ValidationCheck) -> tuple[str, ...]:
    findings = [
        "The pinned real game engine ran the full behavioral suite against the "
        "clean-room implementation and it did not pass.",
    ]
    if gold.observed_complete is False:
        findings.append(
            "The evaluation did not run to completion: the project likely fails "
            "to build or load in the real game. Re-check the exact loader "
            "metadata, module identifiers and entrypoint signatures in the "
            "shared interface contract."
        )
    if gold.observed_counts is not None:
        passed_count, failed_count = gold.observed_counts
        findings.append(
            f"{failed_count} of {passed_count + failed_count} behavioral "
            f"assertions failed; {passed_count} passed."
        )
    if gold.observed_failing_cases:
        case_to_capsule = {
            case: capsule_id
            for capsule_id, cases in bundle.verifier.capsule_cases.items()
            for case in cases
        }
        per_capsule: dict[str, int] = {}
        baseline_failures = 0
        for case in gold.observed_failing_cases:
            capsule_id = case_to_capsule.get(case)
            if capsule_id is None:
                baseline_failures += 1
            else:
                per_capsule[capsule_id] = per_capsule.get(capsule_id, 0) + 1
        entrypoint_map = (
            bundle.interface_contract.capsule_entrypoints
            if bundle.interface_contract is not None
            else {}
        )
        for capsule_id in sorted(per_capsule):
            entrypoints = ", ".join(entrypoint_map.get(capsule_id, ("unknown",)))
            findings.append(
                f"{per_capsule[capsule_id]} failing assertion(s) exercise the "
                f"behavior exposed through the contracted entrypoint(s): {entrypoints}."
            )
        if baseline_failures:
            findings.append(
                f"{baseline_failures} failing assertion(s) cover baseline "
                "behavior (module loading and ordinary inputs that must keep "
                "working)."
            )
    findings.append(
        "Revise the implementation so every contracted public behavior holds "
        "exactly as specified, including signatures, return schemas and the "
        "observable outcomes promised for each entrypoint."
    )
    return tuple(findings)


def _verifier_findings(
    bundle: SynthesisBundle, validation: ValidationReport
) -> tuple[str, ...]:
    declared = set(bundle.verifier.case_ids)
    findings: list[str] = []
    for check in validation.checks:
        if check.observed_case_ids is None:
            continue
        observed = set(check.observed_case_ids)
        if observed == declared:
            continue
        missing = sorted(declared - observed)
        unexpected = sorted(observed - declared)
        detail: list[str] = []
        if missing:
            detail.append(f"declared but never executed: {', '.join(missing)}")
        if unexpected:
            detail.append(f"executed but never declared: {', '.join(unexpected)}")
        findings.append(
            f"Engine control '{check.id}' ran a different case set than the "
            f"verifier declares ({'; '.join(detail)})."
        )
    if findings:
        findings.append(
            "Make the executed suite match the declared case_ids exactly; the "
            "materialized runner verifies exact case names and counts."
        )
    return tuple(findings)


def _defect_findings(validation: ValidationReport) -> tuple[str, ...]:
    findings: list[str] = []
    for check in validation.checks:
        if check.status != "failed" or check.id == "gold":
            continue
        detail: list[str] = []
        if check.observed_complete is False:
            detail.append("the control did not run to completion in the real game")
        if check.observed_passed is True:
            detail.append("the defective control passed instead of failing")
        if check.observed_counts is not None:
            passed_count, failed_count = check.observed_counts
            detail.append(f"{failed_count} assertion(s) failed and {passed_count} passed")
        if (
            check.expected_failing_cases is not None
            and check.observed_failing_cases is not None
            and set(check.expected_failing_cases) != set(check.observed_failing_cases)
        ):
            expected = ", ".join(check.expected_failing_cases) or "none"
            observed = ", ".join(check.observed_failing_cases) or "none"
            detail.append(
                f"expected exactly these failing cases: {expected}; "
                f"the engine observed: {observed}"
            )
        summary = "; ".join(detail) if detail else "the control receipt did not match"
        findings.append(f"Engine control '{check.id}': {summary}.")
    if findings:
        findings.append(
            "Each injected defect must make exactly its mapped capsule_cases "
            "fail in the real game while every other case, including sentinels "
            "and ordinary inputs, keeps passing."
        )
    return tuple(findings)
