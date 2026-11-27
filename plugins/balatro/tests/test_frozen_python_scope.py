"""Approved static-check exceptions never authorize changing frozen code."""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCOPE = Path(__file__).with_name("frozen-python-scope-v1.json")
COPY_ROOTS = (
    "plugins/balatro/src/rhenium_balatro/linux_assets/legacy/",
    "plugins/balatro/runtime/linux/save_capability_v1/fixtures/",
)
AUTHORITIES = (
    "benchmarks/balatro/private/native-v1/assets.json",
    "plugins/balatro/runtime/linux/save_capability_v1/provenance.json",
)


def check_scope(root: Path, expected: dict[str, Any], config: dict[str, Any]) -> None:
    files = {
        path.relative_to(root).as_posix()
        for directory in COPY_ROOTS
        for path in (root / directory).rglob("*.py")
    }
    if files != set(expected) or len(files) != 6:
        raise ValueError("Frozen Python file closure changed")
    assets = json.loads((root / AUTHORITIES[0]).read_text())
    provenance = json.loads((root / AUTHORITIES[1]).read_text())
    for name, record in expected.items():
        if name.startswith(COPY_ROOTS[0]):
            authority = assets["controller_files"][name.removeprefix(COPY_ROOTS[0])]
        else:
            authority = provenance["copied_authored_files"][name.removeprefix(COPY_ROOTS[1])]["sha256"]
        if record["sha256"] != authority:
            raise ValueError("Scope manifest differs from original provenance")
        path = root / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != authority:
            raise ValueError("Frozen Python bytes changed")
    ruff = config["tool"]["ruff"]
    rules = {name: record["ruff_codes"] for name, record in expected.items()}
    if ruff["lint"].get("per-file-ignores") != rules:
        raise ValueError("Ruff exception scope changed")
    if any(key in ruff for key in ("exclude", "extend-exclude")) or any(
        key in ruff["lint"] for key in ("ignore", "extend-ignore", "extend-per-file-ignores")
    ):
        raise ValueError("Additional Ruff bypass is outside this approval")
    mypy = config["tool"]["mypy"]
    if mypy.get("exclude") != ["^" + path for path in COPY_ROOTS] or mypy.get("overrides") != [
        {"module": ["rhenium_balatro.linux_assets.legacy.poc.*"], "follow_imports": "skip"}
    ]:
        raise ValueError("Mypy exception scope changed")
    if not all(mypy.get(key) is True for key in (
        "check_untyped_defs", "disallow_untyped_defs", "warn_unused_ignores"
    )):
        raise ValueError("Maintained Python checking was weakened")


def test_frozen_snapshot_bytes_provenance_and_check_scope() -> None:
    check_scope(ROOT, json.loads(SCOPE.read_text()), tomllib.loads((ROOT / "pyproject.toml").read_text()))


@pytest.mark.parametrize("fault", ["byte", "new-module", "repin", "ruff-rule", "mypy-root"])
def test_scope_gate_rejects_drift_without_touching_real_snapshots(tmp_path: Path, fault: str) -> None:
    expected = json.loads(SCOPE.read_text())
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    for name in (*expected, *AUTHORITIES):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    first = next(iter(expected))
    if fault in {"byte", "repin"}:
        (tmp_path / first).write_bytes(b"changed snapshot\n")
        if fault == "repin":
            expected[first]["sha256"] = hashlib.sha256((tmp_path / first).read_bytes()).hexdigest()
    elif fault == "new-module":
        (tmp_path / COPY_ROOTS[0] / "unchecked.py").write_text("invalid new scope\n")
    elif fault == "ruff-rule":
        config["tool"]["ruff"]["lint"]["per-file-ignores"][first].append("ALL")
    else:
        config["tool"]["mypy"]["exclude"].append("^plugins/")
    with pytest.raises(ValueError):
        check_scope(tmp_path, expected, config)
