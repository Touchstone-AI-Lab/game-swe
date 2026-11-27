"""Regenerate the Mindustry (game source) Harbor task packages.

Canonical task content is ``catalog.json``, ``exams/<task>.md``, each task's
``environment/mindustry`` starter, ``tests/suite`` grader sources,
``solution/after``, ``NOTES.md`` and ``validation/``. This script derives
everything else a Harbor 1.4 package needs (``task.toml``, ``instruction.md``,
both Dockerfiles, ``tests/{test.sh,verify.py,task.json}``, ``solution/solve.sh``)
so an authoring change is followed by one regeneration and a deterministic diff.
It never writes a starter, a suite or a reference.

Run from anywhere::

    python benchmarks/mindustry-core/private/harbor/scripts/materialize.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
HARBOR_ROOT = SCRIPT_ROOT.parent
PACK_ROOT = HARBOR_ROOT.parents[1]
CATALOG_PATH = PACK_ROOT / "catalog.json"
EXAMS_ROOT = PACK_ROOT / "exams"
HARNESS_ROOT = HARBOR_ROOT / "harness"
HARBOR_REVISION = "9a2e3b135cc8fb1e41131020f83370cb2f12ae93"
MINDUSTRY_VERSION = "159.7"
STARTER_NAME = "mindustry"
INSTRUCTION_HEADER = (
    "# Harbor workspace\n\n"
    "Complete this task in `/app/mindustry`; the verifier compiles its Java sources against "
    f"the pinned Mindustry v{MINDUSTRY_VERSION} dedicated server.\n\n"
)
DEFAULT_SOURCE_ROOTS = ("core/src", "server/src")
DEFAULT_EXTRA_SOURCES = ("annotations/src/main/java/mindustry/annotations/Annotations.java",)


def _quoted_list(values: list[str] | tuple[str, ...]) -> str:
    return "[" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + "]"


def _exam_body(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if source.startswith("---\n"):
        _opening, _front_matter, body = source.split("---", 2)
        return body.lstrip()
    return source


def task_manifest(task: dict[str, object]) -> dict[str, object]:
    build = task["build"]
    assert isinstance(build, dict)
    return {
        "schemaVersion": 1,
        "taskId": task["id"],
        "starter": STARTER_NAME,
        "build": {
            "tool": build["tool"],
            "sourceRoots": list(build.get("source_roots", DEFAULT_SOURCE_ROOTS)),
            "extraSources": list(build.get("extra_sources", DEFAULT_EXTRA_SOURCES)),
            "javaRelease": build.get("java_release", 17),
        },
        "serverCases": list(task["server_cases"]),  # type: ignore[call-overload]
    }


def _task_toml(task: dict[str, object], manifest: dict[str, object], catalog_id: str) -> str:
    task_id = str(task["id"])
    upstream = task["upstream"]
    if not isinstance(upstream, dict):
        raise TypeError(f"{task_id} lacks upstream provenance")
    estimated_minutes = task["estimated_minutes"]
    if not isinstance(estimated_minutes, int):
        raise TypeError(f"{task_id} estimated_minutes must be an integer")
    domains = task.get("domains", [])
    assert isinstance(domains, list)
    keywords = ("mindustry", "java", "game-source", "repository-debugging", *[str(item) for item in domains])
    tags = ("mindustry", "java", "repository-debugging")
    summary = task["summary"]
    description = str(summary["en"]) if isinstance(summary, dict) else ""
    cases = manifest["serverCases"]
    assert isinstance(cases, list)
    fixes = upstream["fix_commits"]
    assert isinstance(fixes, list)
    return f'''schema_version = "1.4"

artifacts = ["/app/mindustry"]

[task]
name = "rhenium/mindustry-{task_id}"
version = "1.0.0"
description = {json.dumps(description)}
authors = [{{ name = "Rhenium" }}]
keywords = {_quoted_list(keywords)}

[metadata]
category = "programming"
difficulty = {json.dumps(str(task["difficulty"]))}
tags = {_quoted_list(tags)}
task_kind = "repository-debugging"
game = "Mindustry (dedicated server)"
game_version = "Mindustry v{MINDUSTRY_VERSION}"
language = "Java 17"
build_tool = "mindustry-source"
source_repo = {json.dumps(str(upstream["repository"]))}
source_release = {json.dumps(str(upstream["release_tag"]))}
base_commit = {json.dumps(str(upstream["base_commit"]))}
fix_commits = {_quoted_list([str(item) for item in fixes])}
source_license = {json.dumps(str(upstream["license_spdx"]))}
expected_server_cases = {len(cases)}
content_reference = {json.dumps(f"benchmarks/{PACK_ROOT.name}/exams/{task_id}.md")}
content_reference_pack = {json.dumps(catalog_id)}
harbor_reference_repository = "https://github.com/harbor-framework/harbor"
harbor_reference_revision = "{HARBOR_REVISION}"
verification_profile = "rhenium-mindustry-full"
real_server_validation = "in-verifier; Mindustry v{MINDUSTRY_VERSION} dedicated server"

[verifier]
network_mode = "no-network"
timeout_sec = 2400.0
user = "root"
environment_mode = "separate"

[verifier.environment]
network_mode = "no-network"

[agent]
# The image contains mini-swe-agent. A Harbor job supplies only the model
# endpoint hostname through agents[].extra_allowed_hosts.
network_mode = "allowlist"
allowed_hosts = []
timeout_sec = {estimated_minutes * 60}.0
user = "agent"

[environment]
network_mode = "no-network"
build_timeout_sec = 3600.0
cpus = 4
memory_mb = 8192
storage_mb = 16384
gpus = 0
mcp_servers = []

[verifier.env]

[environment.env]

[solution.env]
'''


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def materialize() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for task in catalog["tasks"]:
        task_id = str(task["id"])
        root = HARBOR_ROOT / task_id
        manifest = task_manifest(task)
        starter = root / "environment" / STARTER_NAME
        if not starter.is_dir():
            raise FileNotFoundError(f"starter is missing: {starter}")
        if not (root / "tests" / "suite" / "rhenium" / "mindustry" / "grader" / "TaskSuite.java").is_file():
            raise FileNotFoundError(f"grader suite is missing for {task_id}")
        _write(root / "task.toml", _task_toml(task, manifest, str(catalog["id"])))
        _write(root / "instruction.md", INSTRUCTION_HEADER + _exam_body(EXAMS_ROOT / f"{task_id}.md"))
        _copy(HARNESS_ROOT / "agent.Dockerfile.tmpl", root / "environment" / "Dockerfile")
        tests = root / "tests"
        _copy(HARNESS_ROOT / "verifier.Dockerfile.tmpl", tests / "Dockerfile")
        _copy(HARNESS_ROOT / "test.sh", tests / "test.sh")
        _copy(HARNESS_ROOT / "verify.py", tests / "verify.py")
        _write(tests / "task.json", json.dumps(manifest, indent=2, sort_keys=False) + "\n")
        _copy(HARNESS_ROOT / "solve.sh", root / "solution" / "solve.sh")
        (tests / "test.sh").chmod(0o755)
        (root / "solution" / "solve.sh").chmod(0o755)


if __name__ == "__main__":
    materialize()
