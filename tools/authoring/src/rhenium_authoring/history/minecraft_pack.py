"""Write accepted history candidates in the ``benchmarks/minecraft-core`` layout.

The canonical per-task inputs are written here (catalog entry, exam, starter,
suite, seed, ``solution/after``, case contracts, notes); every derived Harbor
file comes from the pack's own copy of ``materialize.py``, exactly as for the
hand-authored pack. The same writer stages a one-task pack for engine
validation and appends to ``benchmarks/minecraft-history`` on publication.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .minecraft_build import CORE_PACK
from .models import AuthoredTask, BuildProbe, HistoryFix, TriageDecision

PACK_DIRECTORY = "minecraft-history"
PACK_ID = "history"
CATALOG_ID = "rhenium-minecraft-history-v1"
RUNTIME_ID = "paper-1.21.11-132-history"
_TASK_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_UNIT_REPORT = "upstream unit test must keep passing"
_PACK_NAME = "Minecraft Paper plugin repair tasks from project history"
_PACK_DESCRIPTION = (
    "Repository tasks authored by rhenium-author's project-history mode: the upstream tree at the parent "
    "of a landed fix is the starter and the landed fix is the reference; exams and live-server suites are "
    "model-authored and every task passed engine-backed controls on a real Paper 1.21.11 server."
)


@dataclass
class HistoryTask:
    """Everything needed to write one task; paths point at local checkouts."""

    fix: HistoryFix
    probe: BuildProbe
    triage: TriageDecision
    authored: AuthoredTask
    base_tree: Path
    reference_tree: Path
    applied: list[str]
    controls_markdown: str = ""
    extra: dict[str, object] = field(default_factory=dict)
    published_id: str | None = None

    @property
    def task_id(self) -> str:
        return self.published_id or self.fix.candidate_id


def published_task_id(fix: HistoryFix, requested: str) -> str:
    """A descriptive id for publication.

    Candidate ids end in the fix commit's prefix, which is fine for local run
    directories but must not become a public task id.
    """
    if not 8 <= len(requested) <= 64 or not _TASK_ID.fullmatch(requested):
        raise ValueError("a task id is 8-64 lowercase letters or digits joined by single hyphens")
    if any(sha.casefold()[:7] in requested for sha in (fix.fixed_sha, fix.base_sha)):
        raise ValueError("a task id must not carry an upstream commit")
    return requested


def catalog_entry(task: HistoryTask) -> dict[str, object]:
    fix, probe, authored = task.fix, task.probe, task.authored
    targets = [case.public_report for case in authored.cases if case.role == "target"]
    preserved = [case.public_report for case in authored.cases if case.role == "preserved"]
    requirements = [*targets, *preserved, "every upstream unit test keeps passing"]
    unit = len(probe.unit_cases)
    acceptance = [
        f"offline {probe.tool} build succeeds",
        f"all {unit} upstream JUnit tests pass" if unit else "the repository has no upstream JUnit tests",
        f"{len(authored.cases)} live-server cases pass",
    ]
    required = sorted({f"plugin/{path}" for path in task.applied if (task.base_tree / path).is_file()})
    metadata = next(
        (
            path.relative_to(task.base_tree).as_posix()
            for path in sorted(task.base_tree.glob("**/src/main/resources/*plugin.yml"))
            if path.name in {"plugin.yml", "paper-plugin.yml"}
        ),
        None,
    )
    if metadata is not None:
        required.insert(0, f"plugin/{metadata}")
    return {
        "id": task.task_id,
        "difficulty": task.triage.difficulty,
        "title": {"en": authored.title, "zh": authored.title},
        "summary": {"en": authored.summary, "zh": authored.summary},
        "brief": {"en": authored.summary, "zh": authored.summary},
        "requirements": {"en": requirements, "zh": requirements},
        "api_usage": {
            "en": list(task.triage.entry_points) or ["Paper API"],
            "zh": list(task.triage.entry_points) or ["Paper API"],
        },
        "acceptance": {"en": acceptance, "zh": acceptance},
        "domains": ["repository-debugging", "project-history"],
        "estimated_minutes": {"easy": 45, "medium": 90, "hard": 150}[task.triage.difficulty],
        "required_files": list(dict.fromkeys(required)),
        "plugin_name": probe.plugin_name,
        "build": {
            "tool": probe.tool,
            "wrapper": probe.wrapper,
            "tool_version": probe.tool_version,
            "module": probe.module,
            "assemble": probe.assemble,
            "test": probe.test,
            "artifact": probe.artifact,
            "java_release": probe.java_release,
            "frozen_paths": list(probe.frozen_paths),
        },
        "upstream": {
            "repository": str(fix.repository_url).rstrip("/"),
            "base_commit": fix.base_sha,
            "fix_commit": fix.fixed_sha,
            "license_spdx": fix.license_spdx,
            "license_file": probe.license_file,
            "paper_api": probe.paper_api,
        },
        "unit_cases": list(probe.unit_cases),
        "server_cases": list(authored.server_cases),
        "clean_room_synthetic": False,
    }


def case_contracts(task: HistoryTask) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["case", "layer", "role", "public_report"])
    for name in task.probe.unit_cases:
        writer.writerow([name, "unit", "preserved", _UNIT_REPORT])
    for case in task.authored.cases:
        writer.writerow([case.case, "server", case.role, case.public_report])
    return buffer.getvalue()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def initialize_pack(pack: Path, project_root: Path) -> None:
    """Create an empty history pack with the core pack's trusted assets."""
    core = project_root / CORE_PACK
    pack.mkdir(parents=True, exist_ok=True)
    if not (pack / "benchmark.json").is_file():
        _write(
            pack / "benchmark.json",
            json.dumps(
                {
                    "schema_version": 2,
                    "pack_id": PACK_ID,
                    "plugin": "minecraft",
                    "catalog": "catalog.json",
                    "runtime_catalog": "runtimes.json",
                },
                indent=2,
            )
            + "\n",
        )
    if not (pack / "catalog.json").is_file():
        _write(
            pack / "catalog.json",
            json.dumps(
                {
                    "id": CATALOG_ID,
                    "version": "0.1.0",
                    "game": "minecraft",
                    # The catalog schema requires a zh entry; the repository carries English only.
                    "name": {"en": _PACK_NAME, "zh": _PACK_NAME},
                    "description": {"en": _PACK_DESCRIPTION, "zh": _PACK_DESCRIPTION},
                    "tasks": [],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )
    if not (pack / "runtimes.json").is_file():
        runtimes = json.loads((core / "runtimes.json").read_text(encoding="utf-8"))
        (runtime,) = runtimes["runtimes"]
        runtime["id"] = RUNTIME_ID
        _write(
            pack / "runtimes.json",
            json.dumps({**runtimes, "runtimes": [runtime], "task_bindings": {}}, indent=2) + "\n",
        )
    for relative in ("private/runtime", "private/harbor/harness"):
        target = pack / relative
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(core / relative, target, ignore=shutil.ignore_patterns("__pycache__"))
    script = pack / "private" / "harbor" / "scripts" / "materialize.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(core / "private" / "harbor" / "scripts" / "materialize.py", script)


def write_task(pack: Path, task: HistoryTask) -> None:
    """Write one task's canonical inputs, replacing an earlier copy of the same id."""
    root = pack / "private" / "harbor" / task.task_id
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(task.base_tree, root / "environment" / "plugin", symlinks=False)
    for relative, text in task.authored.suite.items():
        _write(root / "tests" / "suite" / relative, text)
    for relative, text in task.authored.seed.items():
        _write(root / "tests" / "seed" / task.probe.plugin_name / relative, text)
    for relative in task.applied:
        source = task.reference_tree / relative
        if source.is_file():
            target = root / "solution" / "after" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    _write(root / "validation" / "case-contracts.tsv", case_contracts(task))
    if task.controls_markdown:
        _write(root / "validation" / "controls.md", task.controls_markdown)
    fix = task.fix
    origin = f"pull request #{fix.pull_number}" if fix.origin == "pull" else "direct commit"
    header = (
        f"# {task.task_id}\n\n## Upstream\n\n"
        f"- Repository: {str(fix.repository_url).rstrip('/')} ({fix.license_spdx})\n"
        f"- Base commit: `{fix.base_sha}`\n- Fix commit: `{fix.fixed_sha}` ({origin})\n"
        f"- Build: {task.probe.tool} `{task.probe.assemble}`, artifact `{task.probe.artifact}`, "
        f"{len(task.probe.unit_cases)} upstream unit cases\n"
        "- Authored by rhenium-author project-history mode; starter is a GitHub tarball of the base "
        "commit with CI/IDE folders, build output and non-wrapper archives removed.\n\n"
    )
    _write(root / "NOTES.md", header + task.authored.notes.strip() + "\n")
    _write(pack / "exams" / f"{task.task_id}.md", task.authored.exam.strip() + "\n")


def add_task(pack: Path, task: HistoryTask) -> None:
    """Append (or replace) one task in the catalog and runtime bindings, then materialize."""
    catalog_path = pack / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    tasks = [item for item in catalog["tasks"] if item.get("id") != task.task_id]
    tasks.append(catalog_entry(task))
    catalog["tasks"] = tasks
    _write(catalog_path, json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    runtimes_path = pack / "runtimes.json"
    runtimes = json.loads(runtimes_path.read_text(encoding="utf-8"))
    runtimes.setdefault("task_bindings", {})[task.task_id] = [RUNTIME_ID]
    _write(runtimes_path, json.dumps(runtimes, indent=2) + "\n")
    write_task(pack, task)
    materialize(pack)


def materialize(pack: Path) -> None:
    script = pack / "private" / "harbor" / "scripts" / "materialize.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise RuntimeError("materialize.py failed: " + (completed.stderr or completed.stdout)[-2000:])


def stage(parent: Path, project_root: Path, task: HistoryTask) -> Path:
    """A fresh one-task pack for engine validation."""
    pack = parent / PACK_DIRECTORY
    if pack.exists():
        shutil.rmtree(pack)
    initialize_pack(pack, project_root)
    add_task(pack, task)
    return pack
