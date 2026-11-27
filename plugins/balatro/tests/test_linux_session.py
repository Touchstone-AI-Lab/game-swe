import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rhenium_balatro.files import digest
from rhenium_balatro.linux_session import LinuxSessionHost, legacy_tree_hash


def host_without_engine(tmp_path: Path) -> LinuxSessionHost:
    host = object.__new__(LinuxSessionHost)
    host.environment, host.harness = "environment", "harness"
    owned = tmp_path / "owned"
    owned.mkdir()
    process: Any = SimpleNamespace(owns_directory=True, directory=owned)
    host.runtimes = [process]
    return host


def test_fingerprints_separate_shared_environment_and_candidate(tmp_path: Path) -> None:
    host = host_without_engine(tmp_path)
    first, second = tmp_path / "one", tmp_path / "two"
    for path, content in ((first, "return 1"), (second, "return 2")):
        path.mkdir()
        (path / "main.lua").write_text(content)
    task = {"scenario.py": {"size": 4, "sha256": "fixed"}}
    a, b = host.fingerprints(task, first), host.fingerprints(task, second)
    assert a["candidate"] != b["candidate"]
    assert {k: a[k] for k in ("environment", "harness", "task")} == {
        k: b[k] for k in ("environment", "harness", "task")
    }
    assert a["task"] == digest(json.dumps(task, sort_keys=True).encode()) == legacy_tree_hash(task)


def test_scenario_writes_confined_to_owned_new_processes(tmp_path: Path) -> None:
    host = host_without_engine(tmp_path)
    target = tmp_path / "owned/trace.json"
    host.write(target, {"frame": 1})
    host.write(target, {"frame": 2})  # Frozen scenarios update their current-run trace.
    assert json.loads(target.read_text()) == {"frame": 2}
    outside = tmp_path / "old-evidence.json"
    outside.write_text("preserve")
    with pytest.raises(ValueError, match="escaped"):
        host.write(outside, {"passed": True})
    assert outside.read_text() == "preserve"
    host.runtimes[0].owns_directory = False
    with pytest.raises(ValueError, match="escaped"):
        host.write(target, {"passed": True})
