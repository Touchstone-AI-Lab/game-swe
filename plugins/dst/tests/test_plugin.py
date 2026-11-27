from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rhenium_dst.catalog import DstCatalog, DstTask
from rhenium_dst.plugin import DstBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "dst"


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT, pack_root=PACK, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )


def _task() -> DstTask:
    return DstCatalog.load(PACK).tasks[0]


def test_starter_workspace_holds_the_vendored_mod_and_the_public_exam(tmp_path: Path) -> None:
    plugin = DstBenchmarkPlugin()
    task = _task()
    workspace = tmp_path / "workspace"

    plugin.materialize_starter(task, workspace, _context(tmp_path))

    starter = PACK / "private" / "harbor" / task.id / "environment" / "mod"
    assert sorted(path.name for path in workspace.iterdir()) == ["TASK.md", "mod", "task.json"]
    assert (workspace / "mod" / "modmain.lua").read_bytes() == (starter / "modmain.lua").read_bytes()
    marker = json.loads((workspace / "task.json").read_text(encoding="utf-8"))
    assert marker["fromScratch"] is False and marker["language"] == "lua"
    prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
    assert "/app/mod" not in prompt and "`mod`" in prompt
    assert prompt.strip() == plugin.task_prompt(task)


def test_attempt_bundle_has_guidance_and_no_private_material(tmp_path: Path) -> None:
    plugin = DstBenchmarkPlugin()
    task = _task()
    attempt = tmp_path / "attempt"
    attempt.mkdir()

    plugin.materialize_attempt(task, attempt, _context(tmp_path))

    names = {path.name for path in attempt.iterdir()}
    assert names == {"AGENTS.md", "CLAUDE.md", "EXAM.md", "mod", "task.json"}
    assert "Repair every reported problem" in (attempt / "AGENTS.md").read_text(encoding="utf-8")
    assert (attempt / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    files = [path for path in attempt.rglob("*") if path.is_file()]
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)
    for private in (task.id, "dst/core", "rhenium_server_test", "gold.patch", *task.server_cases):
        assert private not in text


def test_public_task_describes_the_upstream_repair() -> None:
    plugin = DstBenchmarkPlugin()
    task = _task()
    public = plugin.public_task(task)
    assert public["fromScratch"] is False
    assert public["taskKind"] == "repository-debugging"
    assert public["sourceRepository"] == task.upstream.repository
    assert public["licenseSpdx"] == task.upstream.license_spdx
    assert public["serverCases"] == len(task.server_cases)
    assert "repository-repair" in plugin.agent_system_prompt(task)


def test_anonymous_results_hide_case_level_diagnostics() -> None:
    plugin = DstBenchmarkPlugin()
    result: dict[str, Any] = {
        "score": 10.0,
        "runtime_log": "server log",
        "runtime": {"status": "failed", "message": "3/12", "caseOutcomes": {"hidden case": False}},
        "checks": [{"id": "headless-server", "status": "failed", "details": {"cases": [{"name": "hidden"}]}}],
    }
    sanitized = plugin.sanitize_anonymous_result(result)
    assert "runtime_log" not in sanitized
    assert sanitized["runtime"] == {"status": "failed"}
    assert sanitized["checks"] == [{"id": "headless-server", "status": "failed"}]
    assert result["runtime"]["caseOutcomes"] == {"hidden case": False}
