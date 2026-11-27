from __future__ import annotations

from pathlib import Path

from rhenium_contract.plugin import ContractBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "contract"


def test_dependency_free_contract_plugin_exercises_core_and_full_profiles(tmp_path: Path) -> None:
    plugin = ContractBenchmarkPlugin()
    catalog = plugin.load_catalog(PACK, "catalog.json")
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = plugin.create_evaluator(context)
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "answer.txt").write_text("contract-ok\n", encoding="utf-8")

    core = evaluator.evaluate(submission, catalog.tasks[0], profile="core")
    full = evaluator.evaluate(submission, catalog.tasks[0], profile="full")

    assert plugin.descriptor.internal is True
    assert core["complete"] is False and core["passed"] is False
    assert full["complete"] is True and full["passed"] is True
    assert full["score"] == 100.0


def test_contract_plugin_keeps_non_secret_plugin_result_fields() -> None:
    plugin = ContractBenchmarkPlugin()
    value = {"payload": {"answer": "public"}, "evidenceSummary": "public"}

    assert plugin.sanitize_anonymous_result(value) is value
