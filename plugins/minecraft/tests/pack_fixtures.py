from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks" / "minecraft-core"
HARNESS = PACK / "private" / "harbor" / "harness"

FROZEN = [
    "build.gradle.kts",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle",
    "gradlew",
    "gradlew.bat",
    "pom.xml",
    ".mvn",
    "mvnw",
    "mvnw.cmd",
    "src/test",
]


def catalog_task(task_id: str, *, tool: str = "gradle", unit: bool = True, synthetic: bool = False) -> dict:
    build: dict[str, object]
    if tool == "javac":
        build = {"tool": "javac", "assemble": "", "test": None, "artifact": "build/libs/Sample.jar"}
    else:
        build = {
            "tool": tool,
            "assemble": "assemble" if tool == "gradle" else "package",
            "test": "test" if unit else None,
            "artifact": "build/libs/Sample.jar" if tool == "gradle" else "target/Sample.jar",
            "frozen_paths": FROZEN,
        }
    task: dict[str, object] = {
        "id": task_id,
        "difficulty": "medium",
        "title": {"en": "Sample repair", "zh": "示例修复"},
        "summary": {"en": "Repair the sample plugin.", "zh": "修复示例插件。"},
        "brief": {"en": "Repair the sample plugin so its command reports the right count.", "zh": "修复。"},
        "requirements": {"en": ["Fix the command."], "zh": ["修复命令。"]},
        "api_usage": {"en": ["Use the Bukkit command API."], "zh": ["使用命令 API。"]},
        "acceptance": {"en": ["The verifier passes."], "zh": ["验证通过。"]},
        "domains": ["commands"],
        "estimated_minutes": 120,
        "required_files": [
            "plugin/src/main/resources/plugin.yml",
            "plugin/src/main/java/dev/sample/SamplePlugin.java",
        ],
        "plugin_name": "Sample",
        "build": build,
        "unit_cases": ["dev.sample.CounterTest.counts"] if unit and tool != "javac" else [],
        "server_cases": ["plugin is enabled", "count command reports two"],
        "clean_room_synthetic": synthetic,
    }
    if not synthetic:
        task["upstream"] = {
            "repository": "https://github.com/example/sample-plugin",
            "base_commit": "a" * 40,
            "fix_commit": "b" * 40,
            "license_spdx": "MIT",
            "license_file": "LICENSE",
            "paper_api": "1.21.11-R0.1-SNAPSHOT",
        }
    return task


def write_pack(root: Path, tasks: list[dict], *, catalog_id: str = "rhenium-minecraft-v1") -> Path:
    """Materialize a minimal but complete Minecraft pack under root."""
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PACK / "benchmark.json", root / "benchmark.json")
    shutil.copytree(PACK / "private" / "runtime", root / "private" / "runtime")
    shutil.copytree(HARNESS, root / "private" / "harbor" / "harness")
    shutil.copyfile(PACK / "runtimes.json", root / "runtimes.json")
    runtimes = json.loads((root / "runtimes.json").read_text(encoding="utf-8"))
    runtimes["task_bindings"] = {task["id"]: ["paper-1.21.11-132"] for task in tasks}
    (root / "runtimes.json").write_text(json.dumps(runtimes, indent=2) + "\n", encoding="utf-8")
    (root / "LICENSE").write_text("Apache-2.0 sample license\n", encoding="utf-8")
    (root / "catalog.json").write_text(
        json.dumps(
            {
                "id": catalog_id,
                "version": "1.0.0",
                "game": "minecraft",
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
        exam = root / "exams" / f"{task['id']}.md"
        exam.parent.mkdir(parents=True, exist_ok=True)
        exam.write_text("# Sample repair\n\nFix the count command in `/app/plugin`.\n", encoding="utf-8")
        harbor = root / "private" / "harbor" / task["id"]
        starter = harbor / "environment" / "plugin"
        (starter / "src" / "main" / "resources").mkdir(parents=True)
        (starter / "src" / "main" / "resources" / "plugin.yml").write_text(
            "name: Sample\nmain: dev.sample.SamplePlugin\nversion: 1.0\napi-version: '1.21'\n",
            encoding="utf-8",
        )
        (starter / "src" / "main" / "java" / "dev" / "sample").mkdir(parents=True)
        (starter / "src" / "main" / "java" / "dev" / "sample" / "SamplePlugin.java").write_text(
            "package dev.sample;\n"
            "public final class SamplePlugin extends org.bukkit.plugin.java.JavaPlugin {}\n",
            encoding="utf-8",
        )
        (starter / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        build = task["build"]
        if build["tool"] != "javac":
            (starter / "src" / "test" / "java").mkdir(parents=True)
            (starter / "src" / "test" / "java" / "CounterTest.java").write_text("class CounterTest {}\n")
            if build["tool"] == "gradle":
                (starter / "build.gradle.kts").write_text("plugins { java }\n", encoding="utf-8")
                (starter / "settings.gradle.kts").write_text(
                    'rootProject.name = "sample"\n', encoding="utf-8"
                )
                (starter / "gradlew").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            else:
                (starter / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        tests = harbor / "tests"
        (tests / "suite").mkdir(parents=True)
        (tests / "suite" / "SampleSuite.java").write_text("class SampleSuite {}\n", encoding="utf-8")
        (harbor / "solution" / "after" / "src" / "main" / "java" / "dev" / "sample").mkdir(parents=True)
        (
            harbor / "solution" / "after" / "src" / "main" / "java" / "dev" / "sample" / "SamplePlugin.java"
        ).write_text(
            "package dev.sample;\n"
            "public final class SamplePlugin extends org.bukkit.plugin.java.JavaPlugin { int x; }\n",
            encoding="utf-8",
        )
        if not task.get("clean_room_synthetic"):
            (harbor / "NOTES.md").write_text("# Notes\n", encoding="utf-8")
            (harbor / "validation").mkdir(parents=True)
            rows = ["case\tlayer\trole\tpublic_report"]
            rows.extend(f"{name}\tunit\tpreserved\tsample" for name in task["unit_cases"])
            rows.extend(f"{name}\tserver\ttarget\tsample" for name in task["server_cases"])
            (harbor / "validation" / "case-contracts.tsv").write_text(
                "\n".join(rows) + "\n", encoding="utf-8"
            )
    materialize(root)
    return root


def materialize(root: Path) -> None:
    """Run the pack's materialize.py against a pack copied under a temporary root."""
    import importlib.util

    scripts = root / "private" / "harbor" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    harness = root / "private" / "harbor" / "harness"
    if not harness.exists():
        shutil.copytree(HARNESS, harness)
    shutil.copyfile(PACK / "private" / "harbor" / "scripts" / "materialize.py", scripts / "materialize.py")
    spec = importlib.util.spec_from_file_location("minecraft_materialize", scripts / "materialize.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.materialize()


@pytest.fixture(name="sample_pack")
def sample_pack_fixture(tmp_path: Path) -> Path:
    return write_pack(tmp_path / "pack", [catalog_task("sample-count-command")])
