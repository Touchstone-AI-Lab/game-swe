"""Regenerate the derived assets of the Don't Starve Together repair tasks.

Canonical task content stays in ``catalog.json``, ``exams/``, ``server/`` and
each task's hand-prepared ``environment/mod`` (the starter) and
``solution/after`` (the upstream reference). This script only derives the
duplicated Harbor assets and the gold patch from them, so an intentional
authoring change is followed by one regeneration and a deterministic diff. It
never writes the starter or the reference trees.

Run from anywhere::

    python benchmarks/dst/private/harbor/scripts/materialize.py
"""
from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
HARBOR_ROOT = SCRIPT_ROOT.parent
PACK_ROOT = HARBOR_ROOT.parents[1]
REPO_ROOT = PACK_ROOT.parents[1]
CATALOG_PATH = PACK_ROOT / "catalog.json"
EXAMS_ROOT = PACK_ROOT / "exams"
HARNESS_ROOT = HARBOR_ROOT / "harness"
RUNTIME_ROOT = PACK_ROOT / "private" / "runtime" / "dst-harbor-runtime"
HARBOR_REVISION = "9a2e3b135cc8fb1e41131020f83370cb2f12ae93"
DST_BUILD_ID = "24700372"
INSTRUCTION_HEADER = (
    "# Harbor workspace\n\n"
    "The mod to repair is the source tree in `/app/mod`; the verifier grades that "
    "directory.\n\n"
)

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
    version: str = "1.0.0"


TASKS = {
    "dst-fixed-bundle-regressions": TaskMetadata(
        description=(
            "Repair the DST Fixed server mod so gifts and bundles opened into an inventory "
            "keep the base game's unwrap behaviour and the bundle preview lists and draws "
            "every item."
        ),
        keywords=("bundles", "gifts", "events", "rpc", "persistence"),
        version="2.0.0",
    ),
    "dst-fixed-module-regressions": TaskMetadata(
        description=(
            "Repair six optional DST Fixed modules: watch naming, combinable equipment, "
            "the Desert Stone portal, bung-blocked creatures, Glommer statue repairs and "
            "moon dial glass delivery."
        ),
        keywords=("items", "creatures", "loot", "portals", "persistence"),
        version="2.0.0",
    ),
    "dsmmo-release-regressions": TaskMetadata(
        description=(
            "Repair the DsMMO server mod so its skill handlers stop raising Lua errors for damage "
            "without an attacker, self-inflicted damage, non-combat targets, empty haunts and "
            "tool-less digging, saves from another Exp-gain setting are recalculated, and an "
            "incomplete eat command is handled."
        ),
        keywords=("skills", "events", "combat", "crashes", "persistence", "commands"),
        version="2.0.0",
    ),
    "composting-together-regressions": TaskMetadata(
        description=(
            "Repair the Composting Together compost pile: recipe cost, composting time, "
            "inspection, dedicated-server crashes, bonus carry-over and save/load state."
        ),
        keywords=("structures", "containers", "timers", "persistence", "crashes"),
    ),
    "glassic-api-regressions": TaskMetadata(
        description=(
            "Repair the Glassic API library so recipe sorting keeps crafting filters intact, "
            "mod skins for a base-game character never remove it from the character list, and "
            "skin builds, the skin inventory and character-exclusive skins behave as documented."
        ),
        keywords=("library", "crafting", "skins", "characters"),
        version="2.0.0",
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


def instruction(task_id: str) -> str:
    return INSTRUCTION_HEADER + _exam_body(EXAMS_ROOT / f"{task_id}.md")


def _task_toml(task: dict[str, object], metadata: TaskMetadata) -> str:
    task_id = str(task["id"])
    estimated_minutes = task["estimated_minutes"]
    if not isinstance(estimated_minutes, int):
        raise TypeError(f"{task_id} estimated_minutes must be an integer")
    upstream = task["upstream"]
    if not isinstance(upstream, dict):
        raise TypeError(f"{task_id} upstream provenance is missing")
    cases = task["server_cases"]
    if not isinstance(cases, list):
        raise TypeError(f"{task_id} server_cases must be a list")
    keywords = ("dst", "dont-starve-together", "lua", "game-modding", "repository-debugging")
    tags = ("game-modding", "dst", "lua", "repository-debugging", "bug-fix", "composite")
    return f'''schema_version = "1.4"

artifacts = ["/app/mod"]

[task]
name = "gamecodebench/dst-{task_id}"
version = "{metadata.version}"
description = {json.dumps(metadata.description)}
authors = [{{ name = "GameCodeBench" }}]
keywords = {_quoted_list(keywords + metadata.keywords)}

[metadata]
category = "programming"
difficulty = {json.dumps(task["difficulty"])}
tags = {_quoted_list(tags)}
task_kind = "repository-debugging"
game = "Don't Starve Together Dedicated Server"
game_version = "Steam app 343050 build {DST_BUILD_ID}"
mod_loader = "DST Mod API 10"
language = "Lua 5.1"
source_mod = {json.dumps(task["source_mod"])}
source_repo = {json.dumps(upstream["repository"])}
source_license = {json.dumps(upstream["license_spdx"])}
base_commit = {json.dumps(upstream["base_commit"])}
reverted_fix_commits = {_quoted_list(list(upstream["fix_commits"]))}
gold_patch_origin = "upstream"
expected_server_cases = {len(cases)}
content_reference = "benchmarks/dst/exams/{task_id}.md"
content_reference_pack = "dst-core"
harbor_reference_repository = "https://github.com/harbor-framework/harbor"
harbor_reference_revision = "{HARBOR_REVISION}"
verification_profile = "rhenium-dst-full"
real_server_validation = "in-verifier; Steam app 343050 build {DST_BUILD_ID}"

[verifier]
network_mode = "no-network"
timeout_sec = 900.0
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


def _tree(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed in task trees: {path}")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path
    return files


def gold_patch(starter: Path, reference: Path, prefix: str = "mod") -> str:
    """A deterministic unified diff from the starter tree to the reference tree."""
    before, after = _tree(starter), _tree(reference)
    chunks: list[str] = []
    for relative in sorted(set(before) | set(after)):
        old = before[relative].read_bytes() if relative in before else b""
        new = after[relative].read_bytes() if relative in after else b""
        if old == new:
            continue
        try:
            old_text = old.decode("utf-8").splitlines(keepends=True)
            new_text = new.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as error:
            raise ValueError(f"binary files differ between starter and reference: {relative}") from error
        chunks.append(f"diff --git a/{prefix}/{relative} b/{prefix}/{relative}\n")
        diff = difflib.unified_diff(
            old_text,
            new_text,
            fromfile=f"a/{prefix}/{relative}" if relative in before else "/dev/null",
            tofile=f"b/{prefix}/{relative}" if relative in after else "/dev/null",
            n=3,
        )
        for line in diff:
            chunks.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    if not chunks:
        raise ValueError("the starter and reference trees are identical")
    return "".join(chunks)


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
        _write(root / "instruction.md", instruction(task_id))
        _copy(HARNESS_ROOT / "Dockerfile", root / "environment" / "Dockerfile")

        tests = root / "tests"
        if (tests / "pack").exists():
            shutil.rmtree(tests / "pack")
        _copy(HARNESS_ROOT / "test.sh", tests / "test.sh")
        _copy(HARNESS_ROOT / "verifier.Dockerfile", tests / "Dockerfile")
        _copy(HARNESS_ROOT / "verify.py", tests / "verify.py")
        # A one-task pack the verifier's catalog loader accepts.
        single = {**catalog, "tasks": [task]}
        _write(tests / "pack" / "catalog.json", json.dumps(single, ensure_ascii=False, indent=2) + "\n")
        _copy(PACK_ROOT / str(task["server_test"]), tests / "pack" / str(task["server_test"]))

        solution = root / "solution"
        _copy(HARNESS_ROOT / "solve.sh", solution / "solve.sh")
        _write(
            solution / "gold.patch",
            gold_patch(root / "environment" / "mod", solution / "after"),
        )
        (tests / "test.sh").chmod(0o755)
        (solution / "solve.sh").chmod(0o755)


if __name__ == "__main__":
    materialize()
