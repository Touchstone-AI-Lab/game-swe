from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks" / "mindustry-core"
HARNESS = PACK / "private" / "harbor" / "harness"
SUITE = Path("tests/suite/rhenium/mindustry/grader/TaskSuite.java")
BASE_COMMIT = "c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c"
SERVER_CASES = [
    "the server answers",
    "the command reports two",
    "the old command still works",
    "status still works",
]


def catalog_task(task_id: str) -> dict[str, object]:
    return {
        "id": task_id,
        "difficulty": "medium",
        "title": {"en": "Sample repair", "zh": "示例修复"},
        "summary": {"en": "Repair the sample server behaviour.", "zh": "修复示例服务器行为。"},
        "brief": {"en": "The sample command reports the wrong count.", "zh": "示例命令报告的数量错误。"},
        "requirements": {"en": ["Fix the command."], "zh": ["修复命令。"]},
        "api_usage": {"en": ["Server console commands."], "zh": ["服务器控制台命令。"]},
        "acceptance": {"en": ["The verifier passes."], "zh": ["验证通过。"]},
        "domains": ["server-console"],
        "estimated_minutes": 60,
        "required_files": ["mindustry/LICENSE", "mindustry/core/src/mindustry/Vars.java"],
        "build": {"tool": "mindustry-source"},
        "upstream": {
            "repository": "https://github.com/Anuken/Mindustry",
            "release_tag": "v159.7",
            "base_commit": BASE_COMMIT,
            "fix_commits": ["b" * 40],
            "license_spdx": "GPL-3.0",
            "license_file": "LICENSE",
        },
        "server_cases": list(SERVER_CASES),
    }


def write_pack(
    root: Path, tasks: list[dict[str, object]], *, catalog_id: str = "rhenium-mindustry-v2"
) -> Path:
    """Materialize a minimal but complete Mindustry pack under root."""
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PACK / "benchmark.json", root / "benchmark.json")
    shutil.copytree(PACK / "private" / "runtime", root / "private" / "runtime")
    shutil.copytree(
        HARNESS, root / "private" / "harbor" / "harness", ignore=shutil.ignore_patterns("__pycache__")
    )
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    runtimes["task_bindings"] = {str(task["id"]): ["mindustry-159.7"] for task in tasks}
    (root / "runtimes.json").write_text(json.dumps(runtimes, indent=2) + "\n", encoding="utf-8")
    (root / "catalog.json").write_text(
        json.dumps(
            {
                "id": catalog_id,
                "version": "1.0.0",
                "game": "mindustry",
                "name": {"en": "Sample", "zh": "示例"},
                "description": {"en": "Sample pack", "zh": "示例题包"},
                "tasks": tasks,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for task in tasks:
        task_id = str(task["id"])
        exam = root / "exams" / f"{task_id}.md"
        exam.parent.mkdir(parents=True, exist_ok=True)
        exam.write_text("# Sample repair\n\nFix the count command in `/app/mindustry`.\n", encoding="utf-8")
        harbor = root / "private" / "harbor" / task_id
        starter = harbor / "environment" / "mindustry"
        (starter / "core" / "src" / "mindustry").mkdir(parents=True)
        (starter / "core" / "src" / "mindustry" / "Vars.java").write_text(
            "package mindustry;\npublic class Vars {}\n", encoding="utf-8"
        )
        (starter / "server" / "src" / "mindustry" / "server").mkdir(parents=True)
        (starter / "server" / "src" / "mindustry" / "server" / "ServerLauncher.java").write_text(
            "package mindustry.server;\npublic class ServerLauncher {}\n", encoding="utf-8"
        )
        annotations = starter / "annotations" / "src" / "main" / "java" / "mindustry" / "annotations"
        annotations.mkdir(parents=True)
        (annotations / "Annotations.java").write_text(
            "package mindustry.annotations;\npublic class Annotations {}\n", encoding="utf-8"
        )
        (starter / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\nVersion 3\n", encoding="utf-8")
        suite = harbor / SUITE
        suite.parent.mkdir(parents=True)
        suite.write_text(
            "package rhenium.mindustry.grader;\n"
            + "".join(f'// suite.test("{name}", ctx -> {{}});\n' for name in SERVER_CASES)
            + "public class TaskSuite {}\n",
            encoding="utf-8",
        )
        after = harbor / "solution" / "after" / "core" / "src" / "mindustry"
        after.mkdir(parents=True)
        (after / "Vars.java").write_text(
            "package mindustry;\npublic class Vars { int x; }\n", encoding="utf-8"
        )
        (harbor / "NOTES.md").write_text("# Notes\n", encoding="utf-8")
        (harbor / "validation").mkdir(parents=True)
        cases = list(SERVER_CASES)
        roles = ["sentinel", "target"] + ["preserved"] * (len(cases) - 2)
        rows = ["case\tlayer\trole\tpublic_report"]
        rows.extend(f"{name}\tserver\t{role}\tsample" for name, role in zip(cases, roles, strict=True))
        (harbor / "validation" / "case-contracts.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    materialize(root)
    return root


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def materialize(root: Path) -> None:
    """Run the pack's materialize.py against a pack copied under a temporary root."""
    scripts = root / "private" / "harbor" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PACK / "private" / "harbor" / "scripts" / "materialize.py", scripts / "materialize.py")
    load_module(scripts / "materialize.py", "mindustry_materialize").materialize()


@pytest.fixture(name="sample_pack")
def sample_pack_fixture(tmp_path: Path) -> Path:
    return write_pack(tmp_path / "pack", [catalog_task("sample-count-command")])
