"""Exercise explicit additional-runtime wiring without Docker or licensed inputs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

PACK = Path(__file__).parents[1] / "benchmarks/slay-the-spire-core"


def load_preparer(root: Path) -> ModuleType:
    runtime = root / "private/native-runtime"
    runtime.mkdir(parents=True)
    entry = runtime / "prepare_tasks.py"
    entry.write_bytes((PACK / "private/native-runtime/prepare_tasks.py").read_bytes())
    (runtime / "recipe-manifest.json").write_text(json.dumps({"files": {}}))
    metadata = root / "validation/native-engine"
    task = "downfall-example"
    (metadata / task).mkdir(parents=True)
    (metadata / "tasks.json").write_text(json.dumps([{"id": task}]))
    source = root / "private/harbor" / task
    source.mkdir(parents=True)
    content = b"frozen fixture source\n"
    (source / "source.txt").write_bytes(content)
    (metadata / task / "frozen-manifest.json").write_text(json.dumps({
        "files": {"source.txt": hashlib.sha256(content).hexdigest()},
    }))
    spec = importlib.util.spec_from_file_location("sts_test_preparer", entry)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downfall_preparation_requires_explicit_runtime_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_preparer(tmp_path / "pack")
    output = tmp_path / "prepared"
    monkeypatch.setattr(sys, "argv", [
        "prepare_tasks.py", "--runtime-workspace", str(tmp_path / "sdk"), "--output", str(output),
    ])
    with pytest.raises(ValueError, match="supply --runtime-map"):
        module.main()
    assert not output.exists()


def test_downfall_preparation_forwards_map_and_preserves_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_preparer(tmp_path / "pack")
    output = tmp_path / "prepared"
    runtime_map = tmp_path / "runtime-map.json"
    runtime_map.write_text(json.dumps({"old": "local-image"}))
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        assert check
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", [
        "prepare_tasks.py", "--runtime-workspace", str(tmp_path / "sdk"), "--output", str(output),
        "--runtime-map", str(runtime_map),
    ])
    module.main()
    assert len(commands) == 1
    assert commands[0][-2:] == ["--runtime-map", str(runtime_map.resolve())]
    source = tmp_path / "pack/private/harbor/downfall-example/source.txt"
    assert (output / "canonical/downfall-example/source.txt").read_bytes() == source.read_bytes()
