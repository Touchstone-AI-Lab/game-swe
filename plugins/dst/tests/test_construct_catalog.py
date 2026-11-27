"""Catalog tests of the construct pack, restored from the pre-repair plugin.

The construct pack moved from ``benchmarks/dst`` to ``benchmarks/dst-construct``;
its catalog content is unchanged.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from rhenium_dst.analyzer import ModAnalyzer
from rhenium_dst.catalog import DstCatalog
from rhenium_dst.construct_catalog import DstConstructCatalog

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "dst-construct"
REPAIR = ROOT / "benchmarks" / "dst"


def _raw_catalog() -> dict[str, object]:
    value = json.loads((DATASET / "fixed-v1.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_dst_catalog_contains_the_ten_hard_tasks() -> None:
    catalog = DstConstructCatalog.load(DATASET)

    assert catalog.id == "rhenium-dst-v2"
    assert catalog.version == "2.1.0"
    assert catalog.game == "dst"
    assert [task.id for task in catalog.tasks] == [
        "camp-supply-ledger",
        "container-transfer-transaction",
        "rescue-dispatch-queue",
        "world-rule-ballot",
        "combat-target-arbiter",
        "waystone-route-network",
        "status-effect-stack",
        "fuel-ration-allocator",
        "trade-escrow-exchange",
        "loot-roll-arbiter",
    ]
    assert {task.difficulty for task in catalog.tasks} == {"hard"}
    assert all(sum(check.weight for check in task.integration_checks) == 15 for task in catalog.tasks)


def test_every_task_has_bilingual_api_and_headless_server_contracts() -> None:
    catalog = DstConstructCatalog.load(DATASET)

    for task in catalog.tasks:
        assert len(task.requirements.en) >= 8, task.id
        assert len(task.requirements.zh) >= 8, task.id
        assert len(task.api_usage.en) >= 5, task.id
        assert len(task.api_usage.zh) >= 5, task.id
        assert len(task.acceptance.en) >= 5, task.id
        assert len(task.acceptance.zh) >= 5, task.id
        assert task.core_module in task.required_files
        assert any("OnSave" in item for item in task.requirements.en + task.api_usage.en)
        assert any("主模拟" in item or "服务端" in item for item in task.requirements.zh)


def test_hidden_assets_are_substantial_and_no_solution_tree_exists() -> None:
    catalog = DstConstructCatalog.load(DATASET)

    assert not (DATASET / "gold").exists() or not list((DATASET / "gold").rglob("*.lua"))
    for task in catalog.tasks:
        hidden = (DATASET / task.hidden_test).read_text(encoding="utf-8")
        server = (DATASET / task.server_test).read_text(encoding="utf-8")
        assert hidden.count("run(") >= 6, task.id
        assert f'load_submission, "{task.core_module}"' in hidden, task.id
        assert server.count("ctx:case(") >= 3, task.id
        assert "TheWorld" in server, task.id


def test_all_private_lua_suites_parse() -> None:
    analyzer = ModAnalyzer()

    for suite_root in (DATASET / "hidden", DATASET / "server"):
        analysis = analyzer.analyze(suite_root)
        assert analysis["syntax_errors"] == [], suite_root


def test_schema_allows_catalog_growth_but_rejects_index_and_rubric_drift() -> None:
    too_short = copy.deepcopy(_raw_catalog())
    tasks = too_short["tasks"]
    assert isinstance(tasks, list)
    tasks.pop()
    assert len(DstConstructCatalog.model_validate(too_short).tasks) == 9

    leaked_index = copy.deepcopy(_raw_catalog())
    indexed_tasks = leaked_index["tasks"]
    assert isinstance(indexed_tasks, list) and isinstance(indexed_tasks[0], dict)
    indexed_tasks[0]["order"] = 1
    with pytest.raises(ValidationError, match="Extra inputs"):
        DstConstructCatalog.model_validate(leaked_index)

    bad_weight = copy.deepcopy(_raw_catalog())
    weighted_tasks = bad_weight["tasks"]
    assert isinstance(weighted_tasks, list) and isinstance(weighted_tasks[0], dict)
    checks = weighted_tasks[0]["integration_checks"]
    assert isinstance(checks, list) and isinstance(checks[0], dict)
    checks[0]["weight"] = 99
    with pytest.raises(ValidationError, match="total exactly 15"):
        DstConstructCatalog.model_validate(bad_weight)


def test_load_fails_closed_when_private_assertions_are_missing(tmp_path: Path) -> None:
    (tmp_path / "fixed-v1.json").write_text(
        (DATASET / "fixed-v1.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="hidden test is missing"):
        DstConstructCatalog.load(tmp_path)


def test_repair_loader_dispatches_construct_catalogs_by_id(tmp_path: Path) -> None:
    # The restored Harbor verifier calls DstCatalog.load(pack, "fixed-v1.json").
    construct = DstCatalog.load(DATASET, "fixed-v1.json")
    assert isinstance(construct, DstConstructCatalog)
    assert construct.id == "rhenium-dst-v2"
    single = DstCatalog.load(
        DATASET / "private" / "harbor" / "camp-supply-ledger" / "tests" / "pack", "fixed-v1.json"
    )
    assert [task.id for task in single.tasks] == ["camp-supply-ledger"]

    # Any catalog file whose id is not the repair catalog's uses the construct model.
    other_pack = tmp_path / "pack"
    for name in ("hidden", "server"):
        (other_pack / name).mkdir(parents=True)
        for suite in (DATASET / name).glob("*.lua"):
            (other_pack / name / suite.name).write_bytes(suite.read_bytes())
    (other_pack / "catalog.json").write_bytes((DATASET / "fixed-v1.json").read_bytes())
    assert isinstance(DstCatalog.load(other_pack), DstConstructCatalog)

    # The repair catalog still loads with the repair model.
    repair = DstCatalog.load(REPAIR)
    assert isinstance(repair, DstCatalog) and repair.id == "dst-core"
