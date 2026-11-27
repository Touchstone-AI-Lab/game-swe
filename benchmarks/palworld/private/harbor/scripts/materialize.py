from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
HARBOR_ROOT = SCRIPT_ROOT.parent
PACK_ROOT = HARBOR_ROOT.parents[1]
CATALOG_PATH = PACK_ROOT / "fixed-v1.json"
EXAMS_ROOT = PACK_ROOT / "exams"
HIDDEN_ROOT = PACK_ROOT / "hidden"
SERVER_ROOT = PACK_ROOT / "server"
HARNESS_ROOT = HARBOR_ROOT / "harness"
HARBOR_REVISION = "9a2e3b135cc8fb1e41131020f83370cb2f12ae93"


@dataclass(frozen=True)
class TaskMetadata:
    description: str
    keywords: tuple[str, ...]


TASKS = {
    "outbox-receipt-recovery": TaskMetadata(
        description=(
            "Build a durable supply outbox with uncertain delivery receipts and ordered crash recovery."
        ),
        keywords=("durability", "idempotency", "recovery", "uncertain-outcomes"),
    ),
    "pal-workforce-optimal-matching": TaskMetadata(
        description=(
            "Compute exact Pal workforce assignments under four lexicographic optimization objectives."
        ),
        keywords=("optimization", "matching", "determinism", "persistence"),
    ),
    "raid-event-watermark": TaskMetadata(
        description=(
            "Settle raid contributions using revisioned retractions and irreversible event-time watermarks."
        ),
        keywords=("event-time", "retractions", "watermarks", "recovery"),
    ),
    "guild-consistent-checkpoint": TaskMetadata(
        description="Compute the greatest causally consistent checkpoint across sparse guild outpost logs.",
        keywords=("causality", "fixed-points", "snapshots", "recovery"),
    ),
    "world-epoch-fenced-timers": TaskMetadata(
        description=(
            "Fence delayed callbacks with world epochs and per-task delivery generations across recovery."
        ),
        keywords=("lifecycle", "fencing", "timers", "recovery"),
    ),
    "guild-storage-ledger": TaskMetadata(
        description=(
            "Build a server-authoritative Palworld guild-supply ledger with quotas, "
            "idempotent reservations, rollback, and restart-safe persistence."
        ),
        keywords=("quotas", "idempotency", "inventory", "persistence"),
    ),
    "base-containment-mincut": TaskMetadata(
        description=(
            "Compute an exact directed containment cut with hard implications, "
            "history stability, canonical ties, and verified recovery."
        ),
        keywords=("min-cut", "hard-constraints", "canonical-optimum", "recovery"),
    ),
    "raid-dispatch-queue": TaskMetadata(
        description=(
            "Build a deterministic priority raid-dispatch queue with exclusive leases, "
            "expiry, retries, and restart-safe ordering."
        ),
        keywords=("scheduling", "leases", "lifecycle", "persistence"),
    ),
    "server-rule-ballot": TaskMetadata(
        description=(
            "Build a server-authoritative timed world-rule ballot with a frozen electorate, "
            "revisioned votes, quorum, deterministic ties, and persistence."
        ),
        keywords=("voting", "authority", "timers", "persistence"),
    ),
    "guild-draft-canonical-order": TaskMetadata(
        description=(
            "Compute an exact guild draft order under weighted preferences and hard precedence, "
            "with minimax and total displacement, canonical ties, and verified recovery."
        ),
        keywords=("subset-dp", "minimax", "canonical-order", "recovery"),
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
    estimated_minutes_value = task["estimated_minutes"]
    if not isinstance(estimated_minutes_value, int):
        raise TypeError(f"{task_id} estimated_minutes must be an integer")
    estimated_minutes = estimated_minutes_value
    keywords = ("palworld", "ue4ss", "lua", "game-modding", "generation") + metadata.keywords
    tags = ("game-modding", "palworld", "ue4ss", "lua", "generation", "composite")
    content_reference = f"benchmarks/palworld/exams/{task_id}.md"
    return f'''schema_version = "1.4"

artifacts = ["/app/mod"]

[task]
name = "gamecodebench/palworld-{task_id}"
version = "1.0.0"
description = {json.dumps(metadata.description)}
authors = [{{ name = "Rui Hu" }}]
keywords = {_quoted_list(keywords)}

[metadata]
category = "programming"
difficulty = "hard"
tags = {_quoted_list(tags)}
task_kind = "generation-composite"
game = "Palworld Dedicated Server"
mod_loader = "RE-UE4SS"
language = "Lua 5.4"
content_reference = {json.dumps(content_reference)}
content_reference_pack = "rhenium-palworld-v1"
harbor_reference_repository = "https://github.com/harbor-framework/harbor"
harbor_reference_revision = "{HARBOR_REVISION}"
verification_profile = "portable-lua-5.4-plus-simulated-ue4ss"
real_server_validation = "external; not executed by this Harbor task"

[verifier]
network_mode = "no-network"
timeout_sec = 180.0
user = "root"
environment_mode = "separate"

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


def materialize() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_tasks = {str(task["id"]): task for task in catalog["tasks"]}
    if set(catalog_tasks) != set(TASKS):
        raise ValueError("Harbor task map must exactly match the Palworld catalog")

    for task_id, metadata in TASKS.items():
        task = catalog_tasks[task_id]
        root = HARBOR_ROOT / task_id
        _write(root / "task.toml", _task_toml(task, metadata))
        _write(root / "instruction.md", _instruction(task_id))

        _copy(HARNESS_ROOT / "Dockerfile", root / "environment" / "Dockerfile")
        _copy(HARNESS_ROOT / "starter-README.md", root / "environment" / "mod" / "README.md")

        _copy(HARNESS_ROOT / "test.sh", root / "tests" / "test.sh")
        _copy(HARNESS_ROOT / "verifier.Dockerfile", root / "tests" / "Dockerfile")
        _copy(HARNESS_ROOT / "verify.py", root / "tests" / "verify.py")
        _copy(HARNESS_ROOT / "lua_runner.py", root / "tests" / "lua_runner.py")
        _copy(HIDDEN_ROOT / f"{task_id}.lua", root / "tests" / "behavior.lua")
        _copy(SERVER_ROOT / f"{task_id}.lua", root / "tests" / "server.lua")
        spec = {
            "task_id": task_id,
            "required_files": task["required_files"],
            "minimum_lua_lines": task["minimum_lua_lines"],
            "integration_checks": task["integration_checks"],
        }
        _write(root / "tests" / "spec.json", json.dumps(spec, ensure_ascii=False, indent=2) + "\n")

        _copy(HARNESS_ROOT / "solve.sh", root / "solution" / "solve.sh")


if __name__ == "__main__":
    materialize()
