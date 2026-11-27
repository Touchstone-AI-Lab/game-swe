"""Regenerate the Don't Starve Together Harbor task packages.

Canonical task content stays in ``exams/``, ``hidden/``, ``server/`` and
``fixed-v1.json``. This script only derives the duplicated Harbor assets from
it, so an intentional authoring change is followed by one regeneration and a
deterministic diff. It never writes ``solution/reference/``: those reference
mods are authored and validated by hand.

Run from anywhere::

    python benchmarks/dst-construct/private/harbor/scripts/materialize.py
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
CATALOG_PATH = PACK_ROOT / "fixed-v1.json"
EXAMS_ROOT = PACK_ROOT / "exams"
HARNESS_ROOT = HARBOR_ROOT / "harness"
RUNTIME_ROOT = PACK_ROOT / "private" / "runtime" / "dst-harbor-runtime"
HARBOR_REVISION = "9a2e3b135cc8fb1e41131020f83370cb2f12ae93"
DST_BUILD_ID = "24700372"

# The verifier runs the repository's own evaluator. These source trees are
# vendored byte-for-byte into the runtime build context; tests assert that the
# copies never drift from the plugin.
VENDORED_SOURCES = (
    (REPO_ROOT / "src" / "rhenium" / "__init__.py", Path("rhenium") / "__init__.py"),
    (REPO_ROOT / "src" / "rhenium" / "core", Path("rhenium") / "core"),
    (REPO_ROOT / "plugins" / "dst" / "src" / "rhenium_dst", Path("rhenium_dst")),
)


@dataclass(frozen=True)
class TaskMetadata:
    description: str
    keywords: tuple[str, ...]
    # Harbor package version. The five original tasks moved to 1.1.0 with DST
    # catalog 2.1.0, which changed their public exams and private suites.
    version: str = "1.0.0"


TASKS = {
    "camp-supply-ledger": TaskMetadata(
        description=(
            "Build a server-authoritative camp supply ledger with daily per-player quotas, "
            "idempotent reservations, rollback, and reload-safe persistence."
        ),
        keywords=("quotas", "idempotency", "inventory", "persistence"),
        version="1.1.0",
    ),
    "container-transfer-transaction": TaskMetadata(
        description=(
            "Build an atomic container transfer transaction with capacity preflight, "
            "reverse compensation, retry deduplication, and recovery."
        ),
        keywords=("transactions", "containers", "rollback", "recovery"),
        version="1.1.0",
    ),
    "rescue-dispatch-queue": TaskMetadata(
        description=(
            "Build a deterministic rescue dispatch queue with priority aging, exclusive leases, "
            "heartbeat expiry, and restart-safe ordering."
        ),
        keywords=("scheduling", "leases", "lifecycle", "persistence"),
        version="1.1.0",
    ),
    "world-rule-ballot": TaskMetadata(
        description=(
            "Build a server-authoritative timed world-rule ballot with a frozen electorate, "
            "revisioned votes, quorum, deterministic ties, and replication."
        ),
        keywords=("voting", "authority", "timers", "replication"),
        version="1.1.0",
    ),
    "combat-target-arbiter": TaskMetadata(
        description=(
            "Build a deterministic combat target arbiter over ordered threat events with decay, "
            "taunt leases, invalidation, and stable tie-breaking."
        ),
        keywords=("combat", "event-ordering", "determinism", "leases"),
        version="1.1.0",
    ),
    "trade-escrow-exchange": TaskMetadata(
        description=(
            "Build a server-authoritative two-player trade escrow with revisioned offers, "
            "mutual confirmation, atomic inventory exchange, and crash-safe settlement."
        ),
        keywords=("trading", "transactions", "inventory", "persistence"),
    ),
    "status-effect-stack": TaskMetadata(
        description=(
            "Build a server-authoritative status effect manager with stacking policies, exact expiry, "
            "tick-independent accrual, dispel ordering, and real component modifiers."
        ),
        keywords=("status-effects", "timers", "combat", "persistence"),
    ),
    "waystone-route-network": TaskMetadata(
        description=(
            "Build a server-authoritative waystone travel network with deterministic cheapest routes, "
            "ticketed fares, cooldowns, rollback, and reload-safe state."
        ),
        keywords=("pathfinding", "authority", "inventory", "persistence"),
    ),
    "loot-roll-arbiter": TaskMetadata(
        description=(
            "Build a server-authoritative need/greed loot roll with a frozen eligible set, a published "
            "deterministic generator, fairness demotion, and exactly-once delivery."
        ),
        keywords=("loot", "determinism", "authority", "persistence"),
    ),
    "fuel-ration-allocator": TaskMetadata(
        description=(
            "Build a server-authoritative camp fuel depot with priority classes, max-min fair integer "
            "allocation, reservations, measured delivery, and rollback."
        ),
        keywords=("resource-allocation", "fairness", "fueled", "persistence"),
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


def _instruction(task_id: str) -> str:
    return (
        "# Harbor workspace\n\n"
        "Complete this task in `/app/mod`; every required file must be written under that directory.\n\n"
        + _exam_body(EXAMS_ROOT / f"{task_id}.md")
    )


def _task_toml(task: dict[str, object], metadata: TaskMetadata) -> str:
    task_id = str(task["id"])
    estimated_minutes = task["estimated_minutes"]
    if not isinstance(estimated_minutes, int):
        raise TypeError(f"{task_id} estimated_minutes must be an integer")
    keywords = ("dst", "dont-starve-together", "lua", "game-modding", "generation") + metadata.keywords
    tags = ("game-modding", "dst", "lua", "generation", "composite")
    content_reference = f"benchmarks/dst-construct/exams/{task_id}.md"
    return f'''schema_version = "1.4"

artifacts = ["/app/mod"]

[task]
name = "gamecodebench/dst-{task_id}"
version = "{metadata.version}"
description = {json.dumps(metadata.description)}
authors = [{{ name = "Xingzhi Li" }}]
keywords = {_quoted_list(keywords)}

[metadata]
category = "programming"
difficulty = "hard"
tags = {_quoted_list(tags)}
task_kind = "generation-composite"
game = "Don't Starve Together Dedicated Server"
mod_loader = "DST Mod API 10"
language = "Lua 5.1"
content_reference = {json.dumps(content_reference)}
content_reference_pack = "rhenium-dst-v2"
harbor_reference_repository = "https://github.com/harbor-framework/harbor"
harbor_reference_revision = "{HARBOR_REVISION}"
verification_profile = "rhenium-dst-full"
real_server_validation = "in-verifier; Steam app 343050 build {DST_BUILD_ID}"

[verifier]
network_mode = "no-network"
timeout_sec = 600.0
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
storage_mb = 10240
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


def _vendor_evaluator() -> None:
    destination_root = RUNTIME_ROOT / "evaluator"
    if destination_root.exists():
        shutil.rmtree(destination_root)
    for source, relative in VENDORED_SOURCES:
        if source.is_file():
            _copy(source, destination_root / relative)
            continue
        for path in sorted(source.rglob("*.py")):
            _copy(path, destination_root / relative / path.relative_to(source))


def materialize() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_tasks = {str(task["id"]): task for task in catalog["tasks"]}
    if set(catalog_tasks) != set(TASKS):
        raise ValueError("Harbor task map must exactly match the DST catalog")

    _vendor_evaluator()
    for task_id, metadata in TASKS.items():
        task = catalog_tasks[task_id]
        root = HARBOR_ROOT / task_id
        _write(root / "task.toml", _task_toml(task, metadata))
        _write(root / "instruction.md", _instruction(task_id))

        _copy(HARNESS_ROOT / "Dockerfile", root / "environment" / "Dockerfile")
        _copy(HARNESS_ROOT / "starter-README.md", root / "environment" / "mod" / "README.md")

        tests = root / "tests"
        if (tests / "pack").exists():
            shutil.rmtree(tests / "pack")
        _copy(HARNESS_ROOT / "test.sh", tests / "test.sh")
        _copy(HARNESS_ROOT / "verifier.Dockerfile", tests / "Dockerfile")
        _copy(HARNESS_ROOT / "verify.py", tests / "verify.py")
        # A one-task pack the unmodified DST catalog loader accepts.
        single = {**catalog, "tasks": [task]}
        _write(tests / "pack" / "fixed-v1.json", json.dumps(single, ensure_ascii=False, indent=2) + "\n")
        _copy(PACK_ROOT / str(task["hidden_test"]), tests / "pack" / str(task["hidden_test"]))
        _copy(PACK_ROOT / str(task["server_test"]), tests / "pack" / str(task["server_test"]))

        _copy(HARNESS_ROOT / "solve.sh", root / "solution" / "solve.sh")
        (root / "tests" / "test.sh").chmod(0o755)
        (root / "solution" / "solve.sh").chmod(0o755)


if __name__ == "__main__":
    materialize()
