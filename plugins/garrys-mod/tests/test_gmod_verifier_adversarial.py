from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from adversarial_helpers import (
    CASES,
    EXPECTED_CORE_SCORES,
    _mutation_map,
    case_clauses,
    materialize_adversarial,
)
from rhenium_garrys_mod.addons.catalog import GmodCatalog
from rhenium_garrys_mod.addons.evaluator import GmodEvaluator

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "gmod"
REQUIRED_CATEGORIES = {
    "empty-api",
    "fixed-output",
    "partial-implementation",
    "state-pollution",
    "stale-request",
    "identity-confusion",
    "cleanup-omission",
    "protocol-forgery",
}
REFERENCE_NAMES = {
    "prop-ownership-quota-registry": ("table-registry", "array-registry"),
    "staged-prop-alignment": ("frame-map", "frame-rows"),
    "persistent-loadout-profiles": ("profile-map", "profile-rows"),
    "hot-object-round-controller": ("player-map", "player-rows"),
    "contraption-blueprint-duplicator": ("graph-map", "graph-rows"),
}
INTERLEAVED_CASES = {
    "prop-ownership-quota-registry": ("happy-path-only", "stale-generation"),
    "staged-prop-alignment": ("translation-only", "non-atomic-execute"),
    "persistent-loadout-profiles": ("ammo-happy-path", "partial-give-continues"),
    "hot-object-round-controller": ("unordered-deadline", "variant-happy-path"),
    "contraption-blueprint-duplicator": ("hardcoded-transform", "partial-graph-survives"),
}


def _evaluator(state: Path, catalog: GmodCatalog) -> GmodEvaluator:
    return GmodEvaluator(
        BenchmarkContext(
            project_root=ROOT,
            pack_root=PACK,
            state_dir=state,
            cache_dir=state / "cache",
        ),
        catalog,
    )


def _checks(result: dict[str, object]) -> dict[str, dict[str, object]]:
    checks = result["checks"]
    assert isinstance(checks, list)
    return {
        str(check["id"]): check
        for check in checks
        if isinstance(check, dict) and isinstance(check.get("id"), str)
    }


def test_adversarial_catalog_has_eight_independent_fault_models_per_task() -> None:
    catalog = GmodCatalog.load(PACK)
    assert set(CASES) == {task.id for task in catalog.tasks}
    assert sum(len(cases) for cases in CASES.values()) == 40
    for task in catalog.tasks:
        cases = CASES[task.id]
        assert len(cases) == 8
        assert {case.category for case in cases} == REQUIRED_CATEGORIES
        assert len({case.id for case in cases}) == 8
        public = (PACK / task.public_exam.path).read_text(encoding="utf-8")
        for case in cases:
            clauses = case_clauses(PACK, task, case)
            assert clauses
            assert all(clause in public for clause in clauses)
            if case.replacement is None:
                assert case.mutation_ids
            if case.category not in {"empty-api", "fixed-output", "protocol-forgery"}:
                assert len(case.mutation_ids) >= 2


def test_all_40_adversarial_submissions_receive_exact_partial_core_scores(
    tmp_path: Path,
) -> None:
    catalog = GmodCatalog.load(PACK)
    evaluator = _evaluator(tmp_path / "state", catalog)
    for task in catalog.tasks:
        mutations = _mutation_map(PACK, task.id)
        for case in CASES[task.id]:
            submission = tmp_path / "submissions" / task.id / case.id
            materialize_adversarial(PACK, task, case, submission)
            result = evaluator.evaluate(submission, task, profile="core")
            checks = _checks(result)

            assert result["score"] == EXPECTED_CORE_SCORES[task.id][case.id]
            assert result["complete"] is False
            assert result["passed"] is False
            assert checks["required-files"]["status"] == "passed"
            assert checks["lua-syntax"]["status"] == "passed"
            assert result["score"] < 60.0

            if case.category == "protocol-forgery":
                continue
            for mutation_id in case.mutation_ids:
                mutation = mutations[mutation_id]
                details = checks[str(mutation["check"])]["details"]
                assert isinstance(details, dict)
                rows = details["cases"]
                assert isinstance(rows, list)
                caught = next(row for row in rows if row["name"] == mutation["case"])
                assert caught["passed"] is False, f"{task.id}/{case.id}/{mutation_id}"


def test_all_40_adversarial_submissions_fail_closed_in_real_runtime_when_requested() -> None:
    if os.environ.get("RHENIUM_GMOD_ADVERSARIAL_RUNTIME") != "1":
        pytest.skip("set RHENIUM_GMOD_ADVERSARIAL_RUNTIME=1 for the controlled native runtime audit")
    catalog = GmodCatalog.load(PACK)
    evidence: list[dict[str, object]] = []
    evidence_path_value = os.environ.get("RHENIUM_GMOD_ADVERSARIAL_EVIDENCE")
    evidence_path = Path(evidence_path_value) if evidence_path_value else None

    def write_evidence() -> None:
        if evidence_path is not None:
            evidence_path.write_text(
                json.dumps({"schemaVersion": 1, "cases": evidence}, indent=2) + "\n",
                encoding="utf-8",
            )

    state_parent = ROOT / ".rhenium"
    state_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmod-adversarial-", dir=state_parent) as raw_state:
        state = Path(raw_state)
        evaluator = _evaluator(state, catalog)
        if not evaluator.runtime_status()["available"]:
            pytest.skip("pinned GMod Dedicated Server is unavailable on the state volume")
        for task in catalog.tasks:
            for case in CASES[task.id]:
                submission = state / "submissions" / task.id / case.id
                materialize_adversarial(PACK, task, case, submission)
                result = evaluator.evaluate(submission, task, profile="full")
                runtime = result["runtime"]
                assert isinstance(runtime, dict)
                assert result["passed"] is False
                assert result["score"] < 100.0
                assert runtime.get("status") in {"passed", "failed"}
                if case.category == "protocol-forgery":
                    phase_a = runtime.get("phase_a")
                    assert isinstance(phase_a, dict)
                    assert runtime.get("status") == "failed"
                    assert phase_a.get("protocol_accepted") is False
                    assert int(phase_a.get("marker_count", 0)) >= 2
                capture_layers = [
                    check["id"]
                    for check in result["checks"]
                    if isinstance(check, dict) and check.get("status") == "failed"
                ]
                evidence.append(
                    {
                        "task": task.id,
                        "case": case.id,
                        "category": case.category,
                        "clauses": list(case_clauses(PACK, task, case)),
                        "faultModel": case.fault_model,
                        "expectedCoreScore": EXPECTED_CORE_SCORES[task.id][case.id],
                        "actualScore": result["score"],
                        "complete": result["complete"],
                        "passed": result["passed"],
                        "runtimeStatus": runtime.get("status"),
                        "captureLayers": capture_layers,
                        "runId": runtime.get("run_id"),
                        "phaseA": runtime.get("phase_a"),
                        "phaseB": runtime.get("phase_b"),
                        "cleanup": runtime.get("cleanup"),
                    }
                )
                write_evidence()

    assert len(evidence) == 40


def test_reference_controls_remain_stable_when_interleaved_with_adversarial_runs() -> None:
    if os.environ.get("RHENIUM_GMOD_STABILITY_RUNTIME") != "1":
        pytest.skip("set RHENIUM_GMOD_STABILITY_RUNTIME=1 for the controlled stability audit")
    catalog = GmodCatalog.load(PACK)
    rows: list[dict[str, Any]] = []
    evidence_path_value = os.environ.get("RHENIUM_GMOD_STABILITY_EVIDENCE")
    evidence_path = Path(evidence_path_value) if evidence_path_value else None

    def write_evidence() -> None:
        if evidence_path is not None:
            evidence_path.write_text(
                json.dumps({"schemaVersion": 1, "runs": rows}, indent=2) + "\n",
                encoding="utf-8",
            )

    state_parent = ROOT / ".rhenium"
    state_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmod-stability-", dir=state_parent) as raw_state:
        state = Path(raw_state)
        evaluator = _evaluator(state, catalog)
        if not evaluator.runtime_status()["available"]:
            pytest.skip("pinned GMod Dedicated Server is unavailable on the state volume")
        for task in catalog.tasks:
            references = REFERENCE_NAMES[task.id]
            adversarial = {case.id: case for case in CASES[task.id]}
            sequence = (
                ("reference", references[0]),
                ("adversarial", INTERLEAVED_CASES[task.id][0]),
                ("reference", references[1]),
                ("adversarial", INTERLEAVED_CASES[task.id][1]),
                ("reference", references[0]),
            )
            for kind, name in sequence:
                if kind == "reference":
                    submission = PACK / "private" / "tasks" / task.id / "references" / name
                else:
                    submission = state / "submissions" / task.id / name
                    materialize_adversarial(PACK, task, adversarial[name], submission)
                result = evaluator.evaluate(submission, task, profile="full")
                runtime = result["runtime"]
                assert isinstance(runtime, dict)
                if kind == "reference":
                    assert result["score"] == 100.0
                    assert result["complete"] is True
                    assert result["passed"] is True
                    assert runtime.get("status") == "passed"
                    assert runtime.get("phase_b_started") is True
                    assert runtime.get("pids_distinct") is True
                    assert runtime.get("state_hash_valid") is True
                    assert runtime.get("evidence_groups_complete") is True
                    assert runtime.get("residual_processes") == []
                    cleanup = runtime.get("cleanup")
                    assert isinstance(cleanup, dict) and cleanup and all(cleanup.values())
                else:
                    assert result["score"] < 100.0
                    assert result["passed"] is False
                rows.append(
                    {
                        "task": task.id,
                        "kind": kind,
                        "name": name,
                        "score": result["score"],
                        "complete": result["complete"],
                        "passed": result["passed"],
                        "runtime": runtime,
                    }
                )
                write_evidence()

    reference_rows = [row for row in rows if row["kind"] == "reference"]
    adversarial_rows = [row for row in rows if row["kind"] == "adversarial"]
    assert len(reference_rows) == 15
    assert len(adversarial_rows) == 10
    assert {row["name"] for row in reference_rows} == {
        name for names in REFERENCE_NAMES.values() for name in names
    }
    run_ids = [row["runtime"]["run_id"] for row in rows]
    assert len(set(run_ids)) == len(run_ids)
    nonces = [
        phase["nonce"]
        for row in rows
        for phase in (row["runtime"].get("phase_a"), row["runtime"].get("phase_b"))
        if isinstance(phase, dict)
    ]
    assert len(set(nonces)) == len(nonces)
