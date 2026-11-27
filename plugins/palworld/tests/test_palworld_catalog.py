from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from rhenium_palworld.analyzer import ModAnalyzer
from rhenium_palworld.catalog import PalworldCatalog

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "palworld"


def _raw_catalog() -> dict[str, object]:
    value = json.loads((DATASET / "fixed-v1.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_palworld_catalog_contains_original_and_advanced_hard_tasks() -> None:
    catalog = PalworldCatalog.load(DATASET)

    assert catalog.id == "rhenium-palworld-v1"
    assert catalog.version == "2.0.0"
    assert catalog.game == "palworld"
    assert [task.id for task in catalog.tasks] == [
        "guild-storage-ledger",
        "base-containment-mincut",
        "raid-dispatch-queue",
        "server-rule-ballot",
        "guild-draft-canonical-order",
        "outbox-receipt-recovery",
        "pal-workforce-optimal-matching",
        "raid-event-watermark",
        "guild-consistent-checkpoint",
        "world-epoch-fenced-timers",
    ]
    assert {task.difficulty for task in catalog.tasks} == {"hard"}
    assert all(
        sum(check.weight for check in task.integration_checks) == 15 for task in catalog.tasks
    )


def test_every_task_has_bilingual_ue4ss_and_headless_server_contracts() -> None:
    catalog = PalworldCatalog.load(DATASET)

    for task in catalog.tasks:
        assert len(task.requirements.en) >= 8, task.id
        assert len(task.requirements.zh) >= 8, task.id
        assert len(task.api_usage.en) >= 5, task.id
        assert len(task.api_usage.zh) >= 5, task.id
        assert len(task.acceptance.en) >= 5, task.id
        assert len(task.acceptance.zh) >= 5, task.id
        assert task.core_module in task.required_files
        assert "Info.json" in task.required_files
        assert "scripts/main.lua" in task.required_files
        assert any("save" in item.lower() for item in task.requirements.en), task.id
        assert any("IsDedicatedServer" in item for item in task.api_usage.en), task.id
        assert any("RheniumService" in item for item in task.requirements.en), task.id
        assert any(
            any(token in item for token in ("服务端", "专服", "专用服务器"))
            for item in task.requirements.zh
        ), task.id


def test_every_task_declares_a_server_capable_package_manifest_check() -> None:
    catalog = PalworldCatalog.load(DATASET)

    for task in catalog.tasks:
        manifest = [check for check in task.integration_checks if check.glob == "Info.json"]
        assert len(manifest) == 1, task.id
        patterns = [pattern for group in manifest[0].groups for pattern in group.any_of]
        assert any('"Type"' in pattern for pattern in patterns), task.id
        assert any('"IsServer"' in pattern for pattern in patterns), task.id


def test_hidden_assets_are_substantial_and_no_solution_tree_exists() -> None:
    catalog = PalworldCatalog.load(DATASET)

    assert not (DATASET / "gold").exists() or not list((DATASET / "gold").rglob("*.lua"))
    for task in catalog.tasks:
        hidden = (DATASET / task.hidden_test).read_text(encoding="utf-8")
        server = (DATASET / task.server_test).read_text(encoding="utf-8")
        assert hidden.count("run(") >= 6, task.id
        assert f'load_submission, "{task.core_module}"' in hidden, task.id
        assert server.count("ctx:case(") >= 3, task.id
        assert "RheniumService" in server, task.id
        assert "IsDedicatedServer" in server, task.id


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
    assert len(PalworldCatalog.model_validate(too_short).tasks) == 9

    leaked_index = copy.deepcopy(_raw_catalog())
    indexed_tasks = leaked_index["tasks"]
    assert isinstance(indexed_tasks, list) and isinstance(indexed_tasks[0], dict)
    indexed_tasks[0]["order"] = 1
    with pytest.raises(ValidationError, match="Extra inputs"):
        PalworldCatalog.model_validate(leaked_index)

    bad_weight = copy.deepcopy(_raw_catalog())
    weighted_tasks = bad_weight["tasks"]
    assert isinstance(weighted_tasks, list) and isinstance(weighted_tasks[0], dict)
    checks = weighted_tasks[0]["integration_checks"]
    assert isinstance(checks, list) and isinstance(checks[0], dict)
    checks[0]["weight"] = 99
    with pytest.raises(ValidationError, match="total exactly 15"):
        PalworldCatalog.model_validate(bad_weight)

    missing_manifest = copy.deepcopy(_raw_catalog())
    manifest_tasks = missing_manifest["tasks"]
    assert isinstance(manifest_tasks, list) and isinstance(manifest_tasks[0], dict)
    manifest_tasks[0]["required_files"] = [
        path for path in manifest_tasks[0]["required_files"] if path != "Info.json"
    ]
    with pytest.raises(ValidationError, match="Info.json"):
        PalworldCatalog.model_validate(missing_manifest)


def test_load_fails_closed_when_private_assertions_are_missing(tmp_path: Path) -> None:
    (tmp_path / "fixed-v1.json").write_text(
        (DATASET / "fixed-v1.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="hidden test is missing"):
        PalworldCatalog.load(tmp_path)
