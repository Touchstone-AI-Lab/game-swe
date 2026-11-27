from __future__ import annotations

from pathlib import Path
from typing import Any

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask
from rhenium.core.plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    PluginDescriptor,
)
from rhenium.core.runtime import RuntimeArtifact


class ContractEvaluator:
    def __init__(self, context: BenchmarkContext):
        self.context = context

    def runtime_status(self) -> dict[str, Any]:
        return {"id": "contract-local", "available": True}

    def evaluate(
        self,
        submission: Path,
        task: BenchmarkTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        del runtimes
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported contract evaluation profile: {profile}")
        answer = submission / "answer.txt"
        required_ok = answer.is_file() and not answer.is_symlink()
        checks: list[dict[str, Any]] = [
            {
                "id": "required-file",
                "status": "passed" if required_ok else "failed",
                "score": 25.0 if required_ok else 0.0,
                "maximum": 25.0,
                "message": "answer.txt is present" if required_ok else "answer.txt is missing",
            }
        ]
        expected_ok = False
        if profile == "full" and required_ok:
            expected = (self.context.pack_root / "expected.txt").read_text(encoding="utf-8")
            expected_ok = answer.read_text(encoding="utf-8") == expected
        checks.append(
            {
                "id": "private-contract",
                "status": (
                    "skipped" if profile == "core" else ("passed" if expected_ok else "failed")
                ),
                "score": 75.0 if expected_ok else 0.0,
                "maximum": 75.0,
                "message": (
                    "private contract disabled"
                    if profile == "core"
                    else ("private contract passed" if expected_ok else "private contract failed")
                ),
            }
        )
        earned = sum(float(check["score"]) for check in checks)
        complete = profile == "full"
        passed = complete and required_ok and expected_ok
        return {
            "score": earned,
            "complete": complete,
            "passed": passed,
            "checks": checks,
            "runtime": {"status": "passed" if passed else "skipped" if not complete else "failed"},
            "runtime_log": "contract evaluator\n",
        }


class ContractBenchmarkPlugin(BenchmarkPlugin):
    descriptor = PluginDescriptor(
        id="contract",
        game_id="contract",
        name="Rhenium Contract Fixture",
        version="0.6.0",
        capabilities=("deterministic", "dependency-free"),
        internal=True,
    )

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        root = pack_root.resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"contract catalog is missing: {catalog_path}")
        catalog = BenchmarkCatalog.model_validate_json(path.read_text(encoding="utf-8"))
        if catalog.game != self.game_id:
            raise ValueError("contract catalog targets the wrong game")
        expected = (root / "expected.txt").resolve()
        if not expected.is_relative_to(root) or not expected.is_file():
            raise ValueError("contract expected result is missing")
        return catalog

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        return ContractEvaluator(context)
