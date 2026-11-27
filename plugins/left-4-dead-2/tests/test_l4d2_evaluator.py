from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from rhenium_left_4_dead_2.catalog import Left4Dead2Catalog, Left4Dead2Task
from rhenium_left_4_dead_2.evaluator import RUNTIME_KEY, Left4Dead2Evaluator, expected_case_names

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

PACK = Path(__file__).parents[3] / "benchmarks/l4d2-core"


@pytest.mark.parametrize("variant", [
    "gold", "broken", "missing", "duplicate", "wrong-case", "bad-reward",
    "nonzero", "environment", "symlink", "oversized",
])
def test_full_verdict_requires_exact_trusted_complete_evidence(tmp_path: Path, variant: str) -> None:
    catalog = Left4Dead2Catalog.load(PACK)
    task = catalog.tasks[0]
    names = expected_case_names(PACK, task)
    context = BenchmarkContext(project_root=PACK.parents[1], pack_root=PACK,
                               state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")
    evaluator = Left4Dead2Evaluator(context, catalog)
    submission = tmp_path / "submission"
    for name in task.required_files:
        path = submission / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source fixture")
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]

    def run(
        task: Left4Dead2Task, submission: Path, logs: Path, image_id: str,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        del task, submission, image_id
        verifier = logs / "verifier"
        verifier.mkdir()
        rows = [f"PASS {name}: ok" for name in names]
        reward = "1"
        if variant == "broken":
            rows[0] = f"FAIL {names[0]}: observed regression"
            reward = "0"
        elif variant == "missing":
            rows.pop()
        elif variant == "duplicate":
            rows[-1] = rows[0]
        elif variant == "wrong-case":
            rows[-1] = "PASS unexpected: ok"
        elif variant == "bad-reward":
            reward = "success"
        elif variant == "environment":
            rows.append("INVALID_ENVIRONMENT: server unavailable")
        elif variant == "oversized":
            reward = "1" * 17
        (verifier / "verifier.log").write_text("\n".join(rows))
        if variant == "symlink":
            private = tmp_path / "private"
            private.write_text("secret-do-not-read")
            (verifier / "reward.txt").symlink_to(private)
        else:
            (verifier / "reward.txt").write_text(reward)
        return subprocess.CompletedProcess([], 1 if variant == "nonzero" else 0, "", ""), ""

    evaluator.runtime.run = run  # type: ignore[method-assign]
    artifact = RuntimeArtifact(runtime_key=RUNTIME_KEY, fingerprint="fixture", kind="docker-images",
                               identity="fixture", metadata={"images": {task.id: "sha256:" + "a" * 64}})
    result = evaluator.evaluate(submission, task, runtimes={RUNTIME_KEY: artifact})
    assert result["passed"] is (variant == "gold")
    assert result["complete"] is (variant in {"gold", "broken"})
    assert "secret-do-not-read" not in result["runtime_log"]
    if result["complete"]:
        assert set(result["runtime"]["caseOutcomes"]) == set(names)
        assert result["runtime"]["failedAssertions"] == (variant == "broken")
    else:
        assert result["runtime"]["caseOutcomes"] == {}


def test_engine_diagnostics_are_bounded_and_retained_with_trusted_verdict(tmp_path: Path) -> None:
    verifier = tmp_path / "verifier"
    verifier.mkdir()
    (verifier / "verifier.log").write_text("FAIL fixture: real failure summary")
    (verifier / "server-fixture.log").write_text("X" * 80_000 + "engine failed to load dependency")
    result = Left4Dead2Evaluator._read_runtime_log(tmp_path, subprocess.CompletedProcess([], 0, "", ""))
    assert "real failure summary" in result and "engine failed to load dependency" in result
    assert len(result) < 17_000
    outside = tmp_path.parent / "private-log"
    outside.write_text("do-not-read")
    (verifier / "server-secret.log").symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe"):
        Left4Dead2Evaluator._read_runtime_log(tmp_path, subprocess.CompletedProcess([], 0, "", ""))
