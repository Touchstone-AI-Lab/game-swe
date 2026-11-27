from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks" / "slay-the-spire-core"
BASE_IMAGE = "maven:3.9-eclipse-temurin-8@sha256:" + "d" * 64


def catalog_task(task_id: str = "sample-regressions") -> dict[str, object]:
    return {
        "id": task_id,
        "difficulty": "hard",
        "title": {"en": "Sample regressions", "zh": "示例回归"},
        "summary": {"en": "Repair the loader.", "zh": "修复加载器。"},
        "brief": {"en": "Repair the loader.", "zh": "修复加载器。"},
        "requirements": {"en": ["Fix the causes."], "zh": ["修复根因。"]},
        "api_usage": {"en": ["Use the JDK 8 APIs in the tree."], "zh": ["使用树中的 JDK 8 API。"]},
        "acceptance": {"en": ["Every private assertion passes."], "zh": ["全部私有断言通过。"]},
        "domains": ["java", "debugging"],
        "estimated_minutes": 180,
        "required_files": ["modthespire/pom.xml"],
        "task_kind": "debugging",
        "source_mod": "ModTheSpire",
        "source_commit": "master",
    }


def write_pack(
    root: Path, tasks: list[dict[str, object]], *, catalog_id: str = "slay-the-spire-core"
) -> Path:
    """Materialize a minimal but complete Slay the Spire pack."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "benchmark.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "pack_id": "core",
                "plugin": "slay-the-spire",
                "catalog": "catalog.json",
                "runtime_catalog": "runtimes.json",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "runtimes.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "runtimes": [
                    {
                        "id": "modthespire-jdk8-maven",
                        "name": "ModTheSpire offline JDK 8 Maven evaluator",
                        "version": "sha256:dddddddddddd",
                        "provider": "container",
                        "restricted": False,
                        "host_platforms": ["linux-x64"],
                        "source": {
                            "kind": "container-image",
                            "image": BASE_IMAGE,
                            "expectedFiles": ["usr/share/maven/bin/mvn"],
                        },
                    }
                ],
                "task_bindings": {str(task["id"]): ["modthespire-jdk8-maven"] for task in tasks},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "catalog.json").write_text(
        json.dumps(
            {
                "id": catalog_id,
                "version": "1.0.0",
                "game": "slay-the-spire",
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
        exam_text = "# Sample regressions\n\nRepair every reported problem in `/app/modthespire`.\n"
        (root / "exams").mkdir(exist_ok=True)
        (root / "exams" / f"{task_id}.md").write_text(exam_text, encoding="utf-8")
        harbor = root / "private" / "harbor" / task_id
        starter = harbor / "environment" / "modthespire"
        (starter / "src" / "main" / "java").mkdir(parents=True)
        (starter / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        (starter / "src" / "main" / "java" / "Loader.java").write_text("class Loader {}\n")
        (harbor / "environment" / "Dockerfile").write_text(
            f"FROM {BASE_IMAGE}\nWORKDIR /app\nCOPY modthespire /app/modthespire\n", encoding="utf-8"
        )
        (harbor / "instruction.md").write_text(exam_text, encoding="utf-8")
        tests = harbor / "tests"
        tests.mkdir(parents=True)
        (tests / "test.sh").write_text("#!/bin/bash\nEXPECTED=4\nmvn -B -o clean test\n", encoding="utf-8")
        (tests / "SampleTest.java").write_text("class SampleTest {}\n", encoding="utf-8")
        solution = harbor / "solution"
        (solution / "after" / "src" / "main" / "java").mkdir(parents=True)
        (solution / "after" / "src" / "main" / "java" / "Loader.java").write_text(
            "class Loader { int fixed; }\n", encoding="utf-8"
        )
        (solution / "solve.sh").write_text(
            "#!/bin/bash\ncp -a /solution/after/. /app/modthespire/\n", encoding="utf-8"
        )
    return root


@pytest.fixture(name="sample_pack")
def sample_pack_fixture(tmp_path: Path) -> Path:
    return write_pack(tmp_path / "pack", [catalog_task()])
