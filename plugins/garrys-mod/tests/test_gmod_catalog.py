from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from rhenium_garrys_mod.addons.catalog import GmodCatalog
from rhenium_garrys_mod.addons.public_assets import (
    PublicExamError,
    validate_catalog_exams,
)

from rhenium.core.manifest import BenchmarkManifest

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "gmod"
TASK_IDS = [
    "prop-ownership-quota-registry",
    "staged-prop-alignment",
    "persistent-loadout-profiles",
    "hot-object-round-controller",
    "contraption-blueprint-duplicator",
]
CLAUSE = re.compile(r"\bT[1-5]-[A-Z]+-[0-9]{2}\b")
CASE = re.compile(r'case\("([^"]+)"')
GROUPS = re.compile(r"local\s+groups\s*=\s*\{([^}]*)\}")
QUOTED = re.compile(r'"([^"]+)"')


def _runtime_groups(path: Path) -> list[str]:
    match = GROUPS.search(path.read_text(encoding="utf-8"))
    assert match is not None
    quoted = QUOTED.findall(match.group(1))
    return quoted or re.findall(r"([a-z][a-z0-9_-]*)\s*=", match.group(1))


def test_manifest_and_catalog_bind_five_isolated_tasks() -> None:
    manifest = BenchmarkManifest.load(PACK / "benchmark.json")
    catalog = GmodCatalog.load(PACK)

    assert manifest.pack_id == "addons"
    assert manifest.plugin == "garrys-mod"
    assert catalog.game == "garrys-mod"
    assert catalog.id == "rhenium-gmod-v2"
    assert catalog.version == "2.2.0"
    assert catalog.runtime.model_dump() == {
        "app_id": 4020,
        "branch": "stable",
        "build_id": "23150012",
        "platform": "windows-x86_64",
        "linux_build_id": "23150012",
    }
    assert [task.id for task in catalog.tasks] == TASK_IDS
    assert len({task.public_exam.sha256 for task in catalog.tasks}) == 5
    for field in (
        "suite_id",
        "runtime_namespace",
        "submission_addon_name",
        "private_suite_addon_name",
    ):
        assert len({getattr(task.server_runtime, field) for task in catalog.tasks}) == 5


def test_public_contracts_and_private_cases_are_fully_traceable() -> None:
    catalog = GmodCatalog.load(PACK)
    assets = validate_catalog_exams(
        catalog,
        pack_root=PACK,
        private_markers={task.id: task.private_exam_markers() for task in catalog.tasks},
    )
    for ordinal, task in enumerate(catalog.tasks, 1):
        assert len(task.requirements.en) >= 8
        assert len(task.requirements.zh) == len(task.requirements.en)
        assert len(task.api_usage.en) >= 5
        assert len(task.api_usage.zh) == len(task.api_usage.en)
        assert len(task.acceptance.en) >= 5
        assert len(task.acceptance.zh) == len(task.acceptance.en)
        assert re.findall(r"^## ([0-9]+)\.", assets[task.id].text, re.MULTILINE) == [
            str(number) for number in range(1, 14)
        ]
        public_clauses = set(CLAUSE.findall(assets[task.id].text))
        assert len(public_clauses) >= 25
        assert all(clause.startswith(f"T{ordinal}-") for clause in public_clauses)

        trace_path = PACK / "private" / "tasks" / task.id / "contract-traceability.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        expected = {
            "hidden-behavior": task.evaluation.hidden_cases,
            "gmod-integration": task.evaluation.integration_cases,
            "lifecycle-cleanup": task.evaluation.lifecycle_cases,
            "dedicated-server": task.server_runtime.expected_cases,
        }
        integration_cases = CASE.findall(
            (PACK / task.evaluation.integration_suite).read_text(encoding="utf-8")
        )
        assert {
            "hidden-behavior": CASE.findall(
                (PACK / task.evaluation.hidden_suite).read_text(encoding="utf-8")
            ),
            "gmod-integration": integration_cases[: len(task.evaluation.integration_cases)],
            "lifecycle-cleanup": integration_cases[len(task.evaluation.integration_cases) :],
            "dedicated-server": _runtime_groups(PACK / task.server_runtime.lua_entry),
        } == expected
        assert set(trace["caseMappings"]) == set(expected)
        for group, names in expected.items():
            rows = trace["caseMappings"][group]
            assert [row["name"] for row in rows] == names
            assert all(set(row["clauses"]) <= public_clauses for row in rows)
            assert all(row["classification"] != "C" for row in rows)


def test_workshop_records_preserve_clean_room_boundary() -> None:
    for task_id in TASK_IDS:
        value = json.loads((PACK / "sources" / f"{task_id}.json").read_text(encoding="utf-8"))
        assert value["taskId"] == task_id
        assert value["originType"] == "workshop-functional-evidence"
        assert value["workshopId"].isdigit()
        assert value["codeCopied"] is False
        assert value["assetsCopied"] is False
        assert value["license"] and value["licenseHandling"]


def test_catalog_fails_closed_for_exam_source_and_traceability_drift(tmp_path: Path) -> None:
    copied = tmp_path / "gmod"
    shutil.copytree(PACK, copied)
    exam = copied / "exams" / f"{TASK_IDS[0]}.md"
    exam.write_bytes(exam.read_bytes() + b"\n")
    with pytest.raises(PublicExamError, match="digest drifted"):
        GmodCatalog.load(copied)

    shutil.rmtree(copied)
    shutil.copytree(PACK, copied)
    source = copied / "sources" / f"{TASK_IDS[0]}.json"
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="source record digest drifted"):
        GmodCatalog.load(copied)

    shutil.rmtree(copied)
    shutil.copytree(PACK, copied)
    trace_path = copied / "private" / "tasks" / TASK_IDS[0] / "contract-traceability.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["caseMappings"]["hidden-behavior"][0]["classification"] = "Z"
    trace_path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(ValueError, match="traceability schema is invalid"):
        GmodCatalog.load(copied)

    shutil.rmtree(copied)
    shutil.copytree(PACK, copied)
    trace_path = copied / "private" / "tasks" / TASK_IDS[0] / "contract-traceability.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["caseMappings"]["hidden-behavior"][0]["classification"] = "C"
    trace_path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(ValueError, match="scored implementation-detail case is forbidden"):
        GmodCatalog.load(copied)


def test_production_plugin_contains_no_task_business_language() -> None:
    production = ROOT / "plugins" / "garrys-mod" / "src" / "rhenium_garrys_mod" / "addons"
    source = "\n".join(path.read_text(encoding="utf-8") for path in production.glob("*.py"))
    for marker in (*TASK_IDS, "three-point", "weapon_smg1", "StartTouch", "duplicator.Paste"):
        assert marker not in source
