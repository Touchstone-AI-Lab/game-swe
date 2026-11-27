from __future__ import annotations

import copy
import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest
from rhenium_balatro.files import read_json
from rhenium_balatro.native_assets import ASSETS
from rhenium_balatro.review import candidate_identity, candidate_reviewed, record_review

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks/balatro"


def test_candidate_identity_matches_all_original_controller_control_hashes() -> None:
    assets = read_json(PACK, ASSETS)
    for controls in assets["controls"].values():
        for control in controls.values():
            assert candidate_identity(PACK / "private/native-v1" / control["source"]) == (
                control["seal_sha256"], control["candidate_sha256"])


@pytest.mark.parametrize("drift", [None, "adapter_sha256", "environment", "task_sha256",
                                  "candidate_sha256", "submission_sha256", "assets_sha256", "extra"])
def test_new_submission_requires_exact_current_operator_review(tmp_path: Path, drift: str | None) -> None:
    assets = {"environment": "e", "harness": "h", "tasks": {"task": {"task_sha256": "t"}},
              "controls": {"task": {}}}
    arguments = (tmp_path, assets, "a", "task", "f" * 64, "c" * 64)
    assert candidate_reviewed(*arguments) is False
    record = record_review(*arguments, reviewed_sha="f" * 64)
    assert record_review(*arguments, reviewed_sha="f" * 64) == record
    if drift:
        record[drift] = "tampered"
        (tmp_path / "reviews" / ("task-" + "f" * 64 + ".json")).write_text(json.dumps(record))
    assert candidate_reviewed(*arguments) is (drift is None)


def test_review_cannot_authorize_bytes_different_from_operator_hash(tmp_path: Path) -> None:
    assets = {"environment": "e", "harness": "h", "tasks": {"task": {"task_sha256": "t"}}}
    with pytest.raises(ValueError, match="changed since"):
        record_review(tmp_path, assets, "a", "task", "f" * 64, "c" * 64, "different")
    assert not list(tmp_path.iterdir())


def test_submission_identity_changes_after_source_edit(tmp_path: Path) -> None:
    source = tmp_path / "main.lua"
    source.write_bytes(b"return 1\n")
    before = candidate_identity(tmp_path)
    source.write_bytes(b"return 2\n")
    assert all(a != b for a, b in zip(before, candidate_identity(tmp_path), strict=True))


@pytest.mark.parametrize("passed", [True, False])
def test_semantic_grader_accepts_non_control_fingerprint(passed: bool) -> None:
    from rhenium_balatro.evaluator import classify_native

    fp = {key: key for key in ("environment", "harness", "task", "candidate")}
    assets = {"environment": fp["environment"], "harness": fp["harness"],
        "tasks": {"task": {"task_sha256": fp["task"], "required": ["private-case"],
                           "expected_processes": 1}}, "controls": {"task": {}}}
    raw = {"complete": True, "passed": passed, "not_executed": [],
        "classification": "pass" if passed else "behavior_mismatch", "platform_inputs_unchanged": True,
        "checks": [{"id": "private-case", "observed": int(passed), "expected": 1, "passed": passed}],
        "processes": [{"run_id": "unique", "fingerprints": copy.deepcopy(fp),
                       "cleanup": {"normal_exit": True, "protected_unchanged": True}}]}
    result = classify_native({"evaluation": raw, "fingerprints": fp, "runtime_count": 1},
                             assets, "task", "new-submission", fp["candidate"])
    assert result["complete"] is True
    assert result["passed"] is passed
    assert result["category"] == ("complete_pass" if passed else "behavior_failure")


def test_evaluator_refuses_unreviewed_then_scores_reviewed_new_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rhenium_balatro import evaluator
    from rhenium_balatro.bridge import BINDING_NAME
    from rhenium_balatro.plugin import BalatroBenchmarkPlugin

    from rhenium.core.plugin import BenchmarkContext

    plugin = BalatroBenchmarkPlugin()
    task = plugin.load_catalog(PACK, "catalog.json").tasks[0]
    context = BenchmarkContext(project_root=ROOT, pack_root=PACK,
                               state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")
    attempt = tmp_path / "attempt"
    plugin.materialize_attempt(task, attempt, context)
    file = attempt / "starter/joker.lua"
    file.write_bytes(file.read_bytes() + b"\n-- unit-only new reviewed bytes\n")
    seal, candidate = candidate_identity(attempt / "starter")
    assets = read_json(PACK, ASSETS)
    assert seal not in {c["seal_sha256"] for c in assets["controls"][task.id].values()}
    context.state_dir.mkdir()
    (context.state_dir / BINDING_NAME).write_text("fixture")
    monkeypatch.setattr(evaluator, "load_binding", lambda _: {"assets_sha256": "fixture"})
    monkeypatch.setattr(evaluator, "verified_assets", lambda *_: assets)
    # This tests admission/semantic grading with a fake engine, on either host OS.
    # The separate native Windows tests exercise the real serial lock and Job.
    monkeypatch.setattr(evaluator, "serial_lock", lambda _state: nullcontext())
    calls = []

    def invoke(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], Path]:
        calls.append(kwargs)
        fp = {"environment": assets["environment"], "harness": assets["harness"],
              "task": assets["tasks"][task.id]["task_sha256"], "candidate": candidate}
        descriptor = assets["tasks"][task.id]
        raw = {"complete": True, "passed": True, "classification": "pass", "not_executed": [],
            "platform_inputs_unchanged": True,
            "checks": [{"id": key, "observed": 1, "expected": 1, "passed": True}
                       for key in descriptor["required"]],
            "processes": [{"run_id": str(i), "fingerprints": fp,
                           "cleanup": {"normal_exit": True, "protected_unchanged": True}}
                          for i in range(descriptor["expected_processes"])]}
        return ({"evaluation": raw, "fingerprints": fp, "runtime_count": descriptor["expected_processes"]},
                context.state_dir / "fake-operation")

    monkeypatch.setattr(evaluator, "invoke", invoke)
    backend = evaluator.BalatroEvaluator(context)
    first = backend.evaluate(attempt, task)
    assert first["reason"] == "submission_review_required" and first["complete"] is False
    assert calls == []
    record_review(context.state_dir, assets, "fixture", task.id, seal, candidate, seal)
    second = backend.evaluate(attempt, task)
    assert second["passed"] is True and second["complete"] is True and len(calls) == 1
