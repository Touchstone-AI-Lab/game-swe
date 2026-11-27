"""Regenerate the Garry's Mod Addons Harbor task packages.

Canonical task content stays in ``catalog.json``, ``exams/``, ``sources/`` and
``private/tasks/``. This script only derives the duplicated Harbor assets from
it, so an intentional authoring change is followed by one regeneration and a
deterministic diff. ``solution/reference/`` is a copy of the task's first
canonical reference; nothing here authors or alters a reference.

Run from anywhere::

    python benchmarks/gmod/private/harbor/scripts/materialize.py
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
HARBOR_ROOT = SCRIPT_ROOT.parent
PACK_ROOT = HARBOR_ROOT.parents[1]
REPO_ROOT = PACK_ROOT.parents[1]
CATALOG_PATH = PACK_ROOT / "catalog.json"
HARNESS_ROOT = HARBOR_ROOT / "harness"
RUNTIME_ROOT = PACK_ROOT / "private" / "runtime" / "gmod-harbor-runtime"
HARBOR_REVISION = "9a2e3b135cc8fb1e41131020f83370cb2f12ae93"
GMOD_BUILD_ID = "23150012"

# The verifier runs the repository's own evaluator. These source trees are
# vendored byte-for-byte into the runtime build context; tests assert that the
# copies never drift from the plugin.
VENDORED_SOURCES = (
    (REPO_ROOT / "src" / "rhenium" / "__init__.py", Path("rhenium") / "__init__.py"),
    (REPO_ROOT / "src" / "rhenium" / "core", Path("rhenium") / "core"),
    (REPO_ROOT / "plugins" / "garrys-mod" / "src" / "rhenium_garrys_mod", Path("rhenium_garrys_mod")),
)
VENDORED_SUFFIXES = {".py", ".lua", ".json"}


@dataclass(frozen=True)
class TaskMetadata:
    description: str
    keywords: tuple[str, ...]


TASKS = {
    "prop-ownership-quota-registry": TaskMetadata(
        description=(
            "Build a server-authoritative Prop ownership and quota registry with idempotent "
            "requests, delayed disconnect cleanup, and restart-safe persistence."
        ),
        keywords=("ownership", "quotas", "entity-lifecycle", "idempotency"),
    ),
    "staged-prop-alignment": TaskMetadata(
        description=(
            "Build a staged three-point Prop alignment Toolgun with deterministic rigid transforms, "
            "constraints, rollback, and Undo."
        ),
        keywords=("toolgun", "geometry", "constraints", "transactions"),
    ),
    "persistent-loadout-profiles": TaskMetadata(
        description=(
            "Build named authoritative weapon and ammo loadout profiles that survive respawn "
            "and server restart."
        ),
        keywords=("loadouts", "player-lifecycle", "persistence", "authority"),
    ),
    "hot-object-round-controller": TaskMetadata(
        description=(
            "Build a Hot Object round controller that orders physical touch events and settles "
            "exactly one multiplayer consequence."
        ),
        keywords=("event-ordering", "rounds", "timers", "player-lifecycle"),
    ),
    "contraption-blueprint-duplicator": TaskMetadata(
        description=(
            "Build a contraption blueprint duplicator that canonicalizes, persists, and restores "
            "an entity and constraint graph with rollback and Undo."
        ),
        keywords=("graph-serialization", "constraints", "persistence", "rollback"),
    ),
}


def _quoted_list(values: tuple[str, ...] | list[str]) -> str:
    return "[" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + "]"


def _exam_body(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if source.startswith("---\n"):
        _opening, _front_matter, body = source.split("---", 2)
        return body.lstrip()
    return source


def _instruction(task: dict[str, object]) -> str:
    public_exam = task["public_exam"]
    if not isinstance(public_exam, dict):
        raise TypeError("public_exam must be an object")
    return (
        "# Harbor workspace\n\n"
        "Complete this task in `/app/addon`; every required file must be written under that directory.\n\n"
        + _exam_body(PACK_ROOT / str(public_exam["path"]))
    )


def _task_toml(task: dict[str, object], metadata: TaskMetadata) -> str:
    task_id = str(task["id"])
    estimated_minutes = task["estimated_minutes"]
    if not isinstance(estimated_minutes, int):
        raise TypeError(f"{task_id} estimated_minutes must be an integer")
    server_runtime = task["server_runtime"]
    if not isinstance(server_runtime, dict) or not isinstance(server_runtime["timeout_seconds"], int):
        raise TypeError(f"{task_id} server_runtime.timeout_seconds must be an integer")
    phases = server_runtime["phases"]
    if not isinstance(phases, list):
        raise TypeError(f"{task_id} server_runtime.phases must be a list")
    # Every phase may use the task timeout; the rest covers the plain-Lua suites
    # and the first hard-linked server view of a fresh container.
    verifier_timeout = server_runtime["timeout_seconds"] * len(phases) + 600
    keywords = ("garrys-mod", "gmod", "glua", "lua", "game-modding", "generation") + metadata.keywords
    tags = ("game-modding", "garrys-mod", "lua", "generation", "composite")
    public_exam = task["public_exam"]
    if not isinstance(public_exam, dict):
        raise TypeError("public_exam must be an object")
    content_reference = f"benchmarks/gmod/{public_exam['path']}"
    return f'''schema_version = "1.4"

artifacts = ["/app/addon"]

[task]
name = "gamecodebench/gmod-{task_id}"
version = "1.0.0"
description = {json.dumps(metadata.description)}
authors = [{{ name = "Changyi" }}, {{ name = "Yunta Hsieh" }}]
keywords = {_quoted_list(keywords)}

[metadata]
category = "programming"
difficulty = {json.dumps(task["difficulty"])}
tags = {_quoted_list(tags)}
task_kind = "generation-composite"
game = "Garry's Mod Dedicated Server"
mod_loader = "Garry's Mod Addon (Sandbox, gm_flatgrass)"
language = "GLua restricted to the Lua 5.1 compatible subset"
content_reference = {json.dumps(content_reference)}
content_reference_pack = "rhenium-gmod-v2"
content_reference_task_version = {json.dumps(task["task_version"])}
harbor_reference_repository = "https://github.com/harbor-framework/harbor"
harbor_reference_revision = "{HARBOR_REVISION}"
verification_profile = "rhenium-garrys-mod-addons-full"
real_server_validation = "in-verifier; Steam app 4020 Linux build {GMOD_BUILD_ID}"

[verifier]
network_mode = "no-network"
timeout_sec = {verifier_timeout}.0
user = "root"
environment_mode = "separate"

[verifier.environment]
network_mode = "no-network"

[agent]
# The image already contains Codex CLI and mini-swe-agent. A Harbor job supplies
# only the model endpoint hostname through agents[].extra_allowed_hosts.
network_mode = "allowlist"
allowed_hosts = []
timeout_sec = {estimated_minutes * 60}.0
user = "agent"

[environment]
network_mode = "no-network"
build_timeout_sec = 1800.0
cpus = 4
memory_mb = 8192
storage_mb = 20480
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


def _copy_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ValueError(f"refusing to export a linked asset: {path}")
        if not path.is_file() or "__pycache__" in relative.parts:
            continue
        _copy(path, destination / relative)


def _vendor_evaluator() -> None:
    destination_root = RUNTIME_ROOT / "evaluator"
    if destination_root.exists():
        shutil.rmtree(destination_root)
    for source, relative in VENDORED_SOURCES:
        if source.is_file():
            _copy(source, destination_root / relative)
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and path.suffix in VENDORED_SUFFIXES and "__pycache__" not in path.parts:
                _copy(path, destination_root / relative / path.relative_to(source))


def materialize() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_tasks = {str(task["id"]): task for task in catalog["tasks"]}
    if set(catalog_tasks) != set(TASKS):
        raise ValueError("Harbor task map must exactly match the GMod Addons catalog")

    _vendor_evaluator()
    for task_id, metadata in TASKS.items():
        task = catalog_tasks[task_id]
        root = HARBOR_ROOT / task_id
        _write(root / "task.toml", _task_toml(task, metadata))
        _write(root / "instruction.md", _instruction(task))

        _copy(HARNESS_ROOT / "Dockerfile", root / "environment" / "Dockerfile")
        _copy(HARNESS_ROOT / "starter-TASK.md", root / "environment" / "addon" / "TASK.md")

        tests = root / "tests"
        if (tests / "pack").exists():
            shutil.rmtree(tests / "pack")
        _copy(HARNESS_ROOT / "test.sh", tests / "test.sh")
        _copy(HARNESS_ROOT / "verifier.Dockerfile", tests / "Dockerfile")
        _copy(HARNESS_ROOT / "verify.py", tests / "verify.py")
        # A one-task pack the unmodified Addons catalog loader accepts. Its
        # traceability validation checks the mutation matrix against the task's
        # references, so the whole private task tree is part of the pack. It
        # exists only inside the separate verifier image.
        pack = tests / "pack"
        single = {**catalog, "tasks": [task]}
        _write(pack / "catalog.json", json.dumps(single, ensure_ascii=False, indent=2) + "\n")
        _copy(PACK_ROOT / task["public_exam"]["path"], pack / task["public_exam"]["path"])
        _copy(PACK_ROOT / task["source"]["path"], pack / task["source"]["path"])
        private = Path("private") / "tasks" / task_id
        _copy_tree(PACK_ROOT / private, pack / private)

        solution = root / "solution"
        if (solution / "reference").exists():
            shutil.rmtree(solution / "reference")
        references = sorted(path for path in (PACK_ROOT / private / "references").iterdir() if path.is_dir())
        if not references:
            raise ValueError(f"{task_id} has no canonical reference")
        _copy_tree(references[0], solution / "reference")
        _copy(HARNESS_ROOT / "solve.sh", solution / "solve.sh")
        (tests / "test.sh").chmod(0o755)
        (solution / "solve.sh").chmod(0o755)


if __name__ == "__main__":
    materialize()
