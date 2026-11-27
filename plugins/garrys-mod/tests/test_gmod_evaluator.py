from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from mutation_helpers import load_matrix, materialize_mutation
from rhenium_garrys_mod.addons.catalog import GmodCatalog
from rhenium_garrys_mod.addons.contracts import GmodTaskRuntimeSpec
from rhenium_garrys_mod.addons.evaluator import GmodEvaluator
from rhenium_garrys_mod.addons.server_runner import (
    GmodServerRunnerError,
    _strict_json_loads,
    _validate_evidence,
    parse_framed_marker,
    runtime_result_integrity,
)

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "gmod"
REFERENCES = {
    "prop-ownership-quota-registry": ["table-registry", "array-registry"],
    "staged-prop-alignment": ["frame-map", "frame-rows"],
    "persistent-loadout-profiles": ["profile-map", "profile-rows"],
    "hot-object-round-controller": ["player-map", "player-rows"],
    "contraption-blueprint-duplicator": ["graph-map", "graph-rows"],
}
EXPECTED_LAYER_CHECKS = {
    "hidden-behavior": {"hidden-behavior", "plain-lua"},
    "gmod-integration": {"gmod-integration", "integration"},
    "lifecycle-cleanup": {"lifecycle-cleanup", "integration"},
    "dedicated-server": {"dedicated-server"},
}


@pytest.fixture(scope="session")
def gmod_catalog() -> GmodCatalog:
    return GmodCatalog.load(PACK)


@pytest.fixture
def gmod_evaluator(tmp_path: Path, gmod_catalog: GmodCatalog) -> GmodEvaluator:
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return GmodEvaluator(context, gmod_catalog)


def _check(result: dict[str, object], identifier: str) -> dict[str, object]:
    checks = result["checks"]
    assert isinstance(checks, list)
    return next(item for item in checks if isinstance(item, dict) and item["id"] == identifier)


def _protocol_spec(tmp_path: Path) -> GmodTaskRuntimeSpec:
    return GmodTaskRuntimeSpec(
        task_id="protocol-probe",
        task_version="2.1.0",
        addon_manifest=tmp_path / "addon.json",
        lua_entry=tmp_path / "suite.lua",
        suite_id="protocol-suite",
        runtime_namespace="protocol-probe",
        submission_addon_name="submission",
        private_suite_addon_name="private_suite",
        expected_cases=("authority", "cleanup"),
        phases=("A", "B"),
        timeout_seconds=10.0,
    )


def _runtime_phase(
    spec: GmodTaskRuntimeSpec,
    phase: str,
    *,
    failed_group: str | None = None,
) -> dict[str, object]:
    cases = [{"name": name, "passed": name != failed_group, "message": ""} for name in spec.expected_cases]
    return {
        "phase": phase,
        "nonce": f"nonce-{phase}",
        "process_id": 100 if phase == "A" else 200,
        "exit_code": 0,
        "forced_termination": False,
        "timed_out": False,
        "protocol_accepted": True,
        "nonce_valid": True,
        "marker_count": 1,
        "payload": {
            "phase": phase,
            "suiteId": spec.suite_id,
            "runtimeNamespace": spec.runtime_namespace,
            "taskVersion": spec.task_version,
            "status": "failed" if failed_group else "passed",
            "cases": cases,
        },
        "evidence_hash_valid": True,
        "job_active_processes": 0,
        "residual_processes": [],
        "error": "",
    }


def _runtime_envelope(
    spec: GmodTaskRuntimeSpec,
    *,
    failed_group: str | None = None,
) -> dict[str, object]:
    return {
        "status": "failed" if failed_group else "passed",
        "server_build": "23150012",
        "phase_a": _runtime_phase(spec, "A"),
        "phase_b": _runtime_phase(spec, "B", failed_group=failed_group),
        "phase_b_started": True,
        "pids_distinct": True,
        "data_directory_reused": True,
        "only_data_reused": True,
        "state_hash_valid": True,
        "evidence_groups_complete": True,
        "cleanup": {"run_root": True},
        "residual_processes": [],
        "submission_unchanged": True,
        "suite_unchanged": True,
        "server_install_unchanged": True,
        "error": "",
    }


def test_all_references_pass_every_core_check(
    gmod_catalog: GmodCatalog,
    gmod_evaluator: GmodEvaluator,
) -> None:
    tasks = {task.id: task for task in gmod_catalog.tasks}
    for task_id, names in REFERENCES.items():
        sources: list[str] = []
        for name in names:
            reference = PACK / "private" / "tasks" / task_id / "references" / name
            result = gmod_evaluator.evaluate(reference, tasks[task_id], profile="core")
            assert result["score"] == 60.0
            assert result["complete"] is False
            assert result["passed"] is False
            assert all(
                check["status"] == "passed" for check in result["checks"] if check["id"] != "dedicated-server"
            )
            sources.append((reference / tasks[task_id].core_module).read_text(encoding="utf-8"))
        assert sources[0] != sources[1]


def test_scoring_rubric_is_exact_and_integration_groups_do_not_overlap(
    gmod_catalog: GmodCatalog,
    gmod_evaluator: GmodEvaluator,
) -> None:
    expected_maxima = {
        "required-files": 5.0,
        "lua-syntax": 5.0,
        "hidden-behavior": 30.0,
        "gmod-integration": 15.0,
        "lifecycle-cleanup": 5.0,
        "dedicated-server": 40.0,
    }
    for task in gmod_catalog.tasks:
        reference = PACK / "private" / "tasks" / task.id / "references" / REFERENCES[task.id][0]
        result = gmod_evaluator.evaluate(reference, task, profile="core")
        maxima = {str(check["id"]): check["maximum"] for check in result["checks"]}
        assert maxima == expected_maxima
        assert sum(maxima.values()) == 100.0
        assert result["score"] == sum(float(check["score"]) for check in result["checks"])
        assert set(task.evaluation.integration_cases).isdisjoint(task.evaluation.lifecycle_cases)


def test_all_75_mutations_are_caught_by_the_declared_case(
    tmp_path: Path,
    gmod_catalog: GmodCatalog,
    gmod_evaluator: GmodEvaluator,
) -> None:
    total = 0
    evidence: list[dict[str, object]] = []
    for task in gmod_catalog.tasks:
        matrix = load_matrix(PACK, task.id)
        total += len(matrix)
        for mutation in matrix:
            destination = tmp_path / task.id / str(mutation["id"])
            materialize_mutation(PACK, task.id, mutation, destination)
            result = gmod_evaluator.evaluate(destination, task, profile="core")
            required = _check(result, "required-files")
            syntax = _check(result, "lua-syntax")
            check = _check(result, str(mutation["check"]))
            details = check["details"]
            assert isinstance(details, dict)
            cases = details["cases"]
            assert isinstance(cases, list)
            caught = next(item for item in cases if item["name"] == mutation["case"])
            assert mutation["expectedLayer"] in EXPECTED_LAYER_CHECKS[str(mutation["check"])]
            assert required["status"] == "passed", mutation["id"]
            assert syntax["status"] == "passed", mutation["id"]
            assert check["status"] == "failed", mutation["id"]
            assert caught["passed"] is False, mutation["id"]
            failed_cases = {
                str(item["name"])
                for candidate in result["checks"]
                if isinstance(candidate, dict)
                and isinstance(candidate.get("details"), dict)
                for item in candidate["details"].get("cases", [])
                if isinstance(item, dict) and item.get("passed") is False
            }
            evidence.append(
                {
                    "task": task.id,
                    "mutation": mutation["id"],
                    "expectedLayer": mutation["expectedLayer"],
                    "expectedCase": mutation["case"],
                    "score": result["score"],
                    "requiredFilesPassed": required["status"] == "passed",
                    "syntaxPassed": syntax["status"] == "passed",
                    "targetCaseFailed": caught["passed"] is False,
                    "incidentalFailedCases": sorted(failed_cases - {str(mutation["case"])}),
                }
            )
    assert total == 75
    evidence_path = os.environ.get("RHENIUM_GMOD_MUTATION_EVIDENCE")
    if evidence_path:
        Path(evidence_path).write_text(
            json.dumps({"schemaVersion": 1, "mutations": evidence}, indent=2) + "\n",
            encoding="utf-8",
        )


def test_full_profile_fails_closed_without_the_pinned_server(
    monkeypatch: pytest.MonkeyPatch,
    gmod_catalog: GmodCatalog,
    gmod_evaluator: GmodEvaluator,
) -> None:
    monkeypatch.setattr(gmod_evaluator.server, "status", lambda: {"available": False})
    task = gmod_catalog.tasks[0]
    reference = PACK / "private" / "tasks" / task.id / "references" / "table-registry"

    result = gmod_evaluator.evaluate(reference, task, profile="full")

    assert result["score"] == 60.0
    assert result["complete"] is False
    assert result["passed"] is False
    assert _check(result, "dedicated-server")["status"] == "failed"


def test_runtime_protocol_rejects_duplicate_json_fields(tmp_path: Path) -> None:
    spec = _protocol_spec(tmp_path)
    output = (
        '@@RHENIUM_GMOD@@nonce:{"runId":"run","phase":"A",'
        '"serverBuild":"23150012","suiteId":"protocol-suite",'
        '"runtimeNamespace":"protocol-probe","taskVersion":"2.1.0",'
        '"status":"passed","status":"failed","cases":['
        '{"name":"authority","passed":true},{"name":"cleanup","passed":true}],'
        '"stateHash":"' + "0" * 64 + '","evidenceHash":"' + "1" * 64 + '"}@@RHENIUM_END@@'
    )

    with pytest.raises(GmodServerRunnerError, match="duplicate field: status"):
        parse_framed_marker(
            output,
            spec=spec,
            nonce="nonce",
            run_id="run",
            build="23150012",
            phase="A",
        )
    with pytest.raises(GmodServerRunnerError, match="duplicate field: runId"):
        _strict_json_loads(b'{"runId":"one","runId":"two"}')
    with pytest.raises(GmodServerRunnerError, match="non-finite number: NaN"):
        _strict_json_loads(b'{"value":NaN}')


def _marker_payload(spec: GmodTaskRuntimeSpec) -> dict[str, object]:
    return {
        "runId": "run",
        "phase": "A",
        "serverBuild": "23150012",
        "suiteId": spec.suite_id,
        "runtimeNamespace": spec.runtime_namespace,
        "taskVersion": spec.task_version,
        "status": "passed",
        "cases": [
            {"name": name, "passed": True, "message": "ok"}
            for name in spec.expected_cases
        ],
        "stateHash": "0" * 64,
        "evidenceHash": "1" * 64,
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("runId", "wrong", "runId is inconsistent"),
        ("phase", "B", "phase is inconsistent"),
        ("serverBuild", "0", "serverBuild is inconsistent"),
        ("suiteId", "wrong", "suiteId is inconsistent"),
        ("runtimeNamespace", "wrong", "runtimeNamespace is inconsistent"),
        ("taskVersion", "0", "taskVersion is inconsistent"),
    ],
)
def test_runtime_protocol_rejects_wrong_marker_identity(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    spec = _protocol_spec(tmp_path)
    payload = _marker_payload(spec)
    payload[field] = value
    output = f"@@RHENIUM_GMOD@@nonce:{json.dumps(payload)}@@RHENIUM_END@@"

    with pytest.raises(GmodServerRunnerError, match=message):
        parse_framed_marker(
            output,
            spec=spec,
            nonce="nonce",
            run_id="run",
            build="23150012",
            phase="A",
        )


def test_runtime_protocol_rejects_wrong_nonce_duplicate_marker_and_malformed_json(
    tmp_path: Path,
) -> None:
    spec = _protocol_spec(tmp_path)
    payload = json.dumps(_marker_payload(spec))
    valid = f"@@RHENIUM_GMOD@@nonce:{payload}@@RHENIUM_END@@"
    attempts = [
        (valid.replace("@@RHENIUM_GMOD@@nonce:", "@@RHENIUM_GMOD@@wrong:"), "nonce"),
        (valid + valid, "exactly one"),
        ("@@RHENIUM_GMOD@@nonce:{@@RHENIUM_END@@", "valid JSON"),
    ]
    for output, message in attempts:
        with pytest.raises(GmodServerRunnerError, match=message):
            parse_framed_marker(
                output,
                spec=spec,
                nonce="nonce",
                run_id="run",
                build="23150012",
                phase="A",
            )


def test_runtime_evidence_binds_assertions_to_scored_groups(tmp_path: Path) -> None:
    spec = _protocol_spec(tmp_path)
    payload = {
        "runId": "run",
        "phase": "B",
        "suiteId": spec.suite_id,
        "runtimeNamespace": spec.runtime_namespace,
        "taskVersion": spec.task_version,
        "status": "failed",
        "cases": [
            {"name": "authority", "passed": True},
            {"name": "cleanup", "passed": False},
        ],
    }
    mismatched = {
        "runId": "run",
        "phase": "B",
        "suiteId": spec.suite_id,
        "runtimeNamespace": spec.runtime_namespace,
        "taskVersion": spec.task_version,
        "assertions": [
            {"group": "authority", "name": "owner denied", "passed": False},
            {"group": "cleanup", "name": "hook removed", "passed": True},
        ],
    }

    with pytest.raises(GmodServerRunnerError, match="group status is inconsistent"):
        _validate_evidence(
            mismatched,
            spec=spec,
            run_id="run",
            phase="B",
            payload=payload,
        )

    matched_assertions = [
        {"group": "authority", "name": "owner denied", "passed": True},
        {"group": "cleanup", "name": "hook removed", "passed": False},
    ]
    matched = {
        **mismatched,
        "assertions": matched_assertions,
    }
    assert (
        _validate_evidence(
            matched,
            spec=spec,
            run_id="run",
            phase="B",
            payload=payload,
        )
        == matched
    )

    matched_assertions.append({"group": "cleanup", "name": "", "passed": False})
    with pytest.raises(GmodServerRunnerError, match="malformed assertion"):
        _validate_evidence(
            matched,
            spec=spec,
            run_id="run",
            phase="B",
            payload=payload,
        )


def test_runtime_integrity_failure_cannot_keep_runtime_points_or_complete(
    monkeypatch: pytest.MonkeyPatch,
    gmod_catalog: GmodCatalog,
    gmod_evaluator: GmodEvaluator,
) -> None:
    task = gmod_catalog.tasks[0]
    spec = task.runtime_spec(PACK)
    reference = PACK / "private" / "tasks" / task.id / "references" / "table-registry"

    behavior_failure = _runtime_envelope(spec, failed_group=spec.expected_cases[0])
    assert runtime_result_integrity(
        behavior_failure,
        spec=spec,
        pinned_build="23150012",
    )
    monkeypatch.setattr(gmod_evaluator.server, "run", lambda *_args: behavior_failure)
    partial = gmod_evaluator.evaluate(reference, task, profile="full")
    assert partial["score"] == 92.0
    assert partial["complete"] is True
    assert partial["passed"] is False
    partial_details = _check(partial, "dedicated-server")["details"]
    assert isinstance(partial_details, dict)
    assert partial_details["integrity_valid"] is True

    forged_pass = _runtime_envelope(spec, failed_group=spec.expected_cases[0])
    forged_pass["status"] = "passed"
    assert not runtime_result_integrity(
        forged_pass,
        spec=spec,
        pinned_build="23150012",
    )

    invalid_cleanup = _runtime_envelope(spec)
    invalid_cleanup["status"] = "failed"
    invalid_cleanup["cleanup"] = {"run_root": False}
    assert not runtime_result_integrity(
        invalid_cleanup,
        spec=spec,
        pinned_build="23150012",
    )
    monkeypatch.setattr(gmod_evaluator.server, "run", lambda *_args: invalid_cleanup)
    invalid = gmod_evaluator.evaluate(reference, task, profile="full")
    assert invalid["score"] == 60.0
    assert invalid["complete"] is False
    assert invalid["passed"] is False
    dedicated = _check(invalid, "dedicated-server")
    assert dedicated["score"] == 0.0
    invalid_details = dedicated["details"]
    assert isinstance(invalid_details, dict)
    assert invalid_details["integrity_valid"] is False

    missing_phase_a = _runtime_envelope(spec)
    missing_phase_a.pop("phase_a")
    monkeypatch.setattr(gmod_evaluator.server, "run", lambda *_args: missing_phase_a)
    skipped = gmod_evaluator.evaluate(reference, task, profile="full")
    assert skipped["score"] == 60.0
    assert skipped["complete"] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "skipped"),
        (("status",), "failed"),
        (("server_build",), "wrong"),
        (("phase_a", "phase"), "B"),
        (("phase_a", "protocol_accepted"), False),
        (("phase_a", "nonce_valid"), False),
        (("phase_a", "marker_count"), 2),
        (("phase_a", "evidence_hash_valid"), False),
        (("phase_a", "timed_out"), True),
        (("phase_a", "forced_termination"), True),
        (("phase_a", "exit_code"), 1),
        (("phase_a", "job_active_processes"), 1),
        (("phase_a", "residual_processes"), [777]),
        (("phase_b_started",), False),
        (("pids_distinct",), False),
        (("data_directory_reused",), False),
        (("only_data_reused",), False),
        (("state_hash_valid",), False),
        (("evidence_groups_complete",), False),
        (("cleanup", "run_root"), False),
        (("residual_processes",), [888]),
        (("submission_unchanged",), False),
        (("suite_unchanged",), False),
        (("server_install_unchanged",), False),
        (("error",), "server crash"),
    ],
)
def test_runtime_integrity_rejects_each_untrusted_envelope_dimension(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
) -> None:
    spec = _protocol_spec(tmp_path)
    envelope = _runtime_envelope(spec)
    target: dict[str, object] = envelope
    for component in path[:-1]:
        nested = target[component]
        assert isinstance(nested, dict)
        target = nested
    target[path[-1]] = value

    assert not runtime_result_integrity(
        envelope,
        spec=spec,
        pinned_build="23150012",
    )


def test_real_dedicated_server_runs_both_phases_when_available(
    gmod_catalog: GmodCatalog,
) -> None:
    state_parent = ROOT / ".rhenium"
    state_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmod-plugin-test-", dir=state_parent) as raw_state:
        state = Path(raw_state)
        context = BenchmarkContext(
            project_root=ROOT,
            pack_root=PACK,
            state_dir=state,
            cache_dir=state / "cache",
        )
        evaluator = GmodEvaluator(context, gmod_catalog)
        if not evaluator.runtime_status()["available"]:
            pytest.skip("pinned GMod Dedicated Server is unavailable on the state volume")
        task = gmod_catalog.tasks[0]
        reference = PACK / "private" / "tasks" / task.id / "references" / "table-registry"
        result = evaluator.evaluate(reference, task, profile="full")

    assert result["score"] == 100.0
    assert result["complete"] is True
    assert result["passed"] is True
    assert result["runtime"]["phase_b_started"] is True
    assert result["runtime"]["pids_distinct"] is True
    assert all(result["runtime"]["cleanup"].values())


def test_lua_runner_rejects_path_escape_and_infinite_submission(tmp_path: Path) -> None:
    source_root = ROOT / "plugins" / "garrys-mod" / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(source_root), environment.get("PYTHONPATH", "")) if value
    )
    submission = tmp_path / "submission"
    submission.mkdir()
    (tmp_path / "outside.lua").write_text("return {secret = true}\n", encoding="utf-8")
    hidden = tmp_path / "escape.lua"
    hidden.write_text(
        "local ok = pcall(load_submission, '../outside.lua')\n"
        "return {cases={{name='escape',passed=not ok,message=''}}}\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-m",
        "rhenium_garrys_mod.addons.lua.suite_runner",
        "--submission",
        str(submission),
        "--test",
        str(hidden),
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, env=environment, timeout=8, check=False
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["status"] == "passed"

    (submission / "loop.lua").write_text("while true do end\n", encoding="utf-8")
    hidden.write_text(
        "load_submission('loop.lua')\nreturn {cases={{name='unreachable',passed=true,message=''}}}\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    completed = subprocess.run(
        command, capture_output=True, text=True, env=environment, timeout=8, check=False
    )
    assert completed.returncode != 0
    assert time.monotonic() - started < 8
