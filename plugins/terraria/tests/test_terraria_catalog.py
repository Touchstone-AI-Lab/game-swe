from pathlib import Path

from rhenium_terraria.catalog import (
    TerrariaCatalog,
    expected_case_names,
    expected_engine_case_names,
)

PACK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "terraria-core"
TASK_CASES = {
    "terraria-magic-storage-compressed-io-regressions-hard": 68,
    "terraria-fargos-enchanted-tree-transactions-hard": 78,
    "terraria-overhaul-entity-chunk-lifetime-hard": 78,
    "terraria-improvegame-space-wand-authority-hard": 82,
    "terraria-spirit-branching-quest-replication-hard": 97,
    "terraria-modliquid-map-persistence-hard": 103,
    "terraria-aequus-carpentry-replication-hard": 87,
    "terraria-starlight-ability-state-hard": 84,
    "terraria-fargos-toggle-presets-hard": 82,
    "terraria-calamity-overhaul-time-replication-hard": 78,
}
TASK_GROUPS = {task_id: 7 for task_id in TASK_CASES}
TASK_GROUPS["terraria-magic-storage-compressed-io-regressions-hard"] = 11
TASK_GROUPS["terraria-fargos-enchanted-tree-transactions-hard"] = 15
TASK_GROUPS["terraria-overhaul-entity-chunk-lifetime-hard"] = 16
TASK_GROUPS["terraria-improvegame-space-wand-authority-hard"] = 14
TASK_GROUPS["terraria-spirit-branching-quest-replication-hard"] = 16
TASK_GROUPS["terraria-modliquid-map-persistence-hard"] = 17
TASK_GROUPS["terraria-aequus-carpentry-replication-hard"] = 12
TASK_GROUPS["terraria-starlight-ability-state-hard"] = 11
TASK_GROUPS["terraria-fargos-toggle-presets-hard"] = 10
TASK_GROUPS["terraria-calamity-overhaul-time-replication-hard"] = 8


def test_catalog_loads_independently_authored_task() -> None:
    catalog = TerrariaCatalog.load(PACK_ROOT)
    assert {task.id: task.expected_cases for task in catalog.tasks} == TASK_CASES
    for task in catalog.tasks:
        assert task.difficulty == "hard"
        assert task.task_kind == "repository-debugging"
        assert task.defect_groups == TASK_GROUPS[task.id]
        assert "source projection" in task.evaluation_boundary
        assert "real tModLoader" in task.evaluation_boundary
        assert len(expected_case_names(PACK_ROOT, task)) == TASK_CASES[task.id]
        assert task.engine_mode == "dedicated-server"
        assert len(expected_engine_case_names(PACK_ROOT, task)) == 3


def test_required_files_exist_in_frozen_snapshot() -> None:
    for task in TerrariaCatalog.load(PACK_ROOT).tasks:
        environment = PACK_ROOT / "private" / "harbor" / task.id / "environment"
        for relative in task.required_files:
            assert (environment / relative).is_file(), relative


def test_public_exam_is_exact_authored_prompt() -> None:
    for task_id in TASK_CASES:
        task_root = PACK_ROOT / "private" / "harbor" / task_id
        exam = PACK_ROOT / "exams" / f"{task_id}.md"
        assert exam.read_bytes() == (task_root / "instruction.md").read_bytes()
