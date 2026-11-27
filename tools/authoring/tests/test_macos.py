from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rhenium_authoring import cli, macos
from rhenium_authoring.models import SynthesisBundle
from typer.testing import CliRunner


@pytest.mark.parametrize("run_id", ["../outside", "/absolute", "author/a", "x\\y"])
def test_native_paths_reject_traversal(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="invalid authoring"):
        macos._paths(tmp_path, run_id, "synthetic-safe")


def test_native_checks_are_fresh_diagnostics_and_do_not_update_validation(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    monkeypatch: Any,
) -> None:
    root = tmp_path / "native"
    root.mkdir()
    validation = tmp_path / "validation.json"
    validation.write_text('{"passed": false}')
    seen: list[Path] = []

    class FakeHub:
        def evaluate_task(self, key: str, submission: Path, profile: str) -> dict[str, Any]:
            assert key.startswith("stardew-valley/synth/") and profile == "macos"
            assert (submission / "mod/modmain.lua").is_file()
            seen.append(submission)
            return {"result": {"complete": False, "passed": False, "runtime": {"engineComplete": False}}}

    monkeypatch.setattr(macos, "_paths", lambda *_: (root, dst_bundle))
    monkeypatch.setattr(macos, "_hub", lambda *_: FakeHub())
    for _ in range(2):
        report = macos.check_macos(tmp_path, "author-test", dst_bundle.candidate.id)
        assert report["publicationEligible"] is False and report["passed"] is False
        assert len(report["controls"]) == 4
    assert len(set(seen)) == 8
    assert validation.read_text() == '{"passed": false}'


@pytest.mark.parametrize("status,exit_code", [("action_required", 2), ("failed", 1), ("completed", 0)])
def test_native_prepare_cli_preserves_operation_action_state(
    tmp_path: Path,
    monkeypatch: Any,
    status: str,
    exit_code: int,
) -> None:
    monkeypatch.setattr(cli, "_context", lambda: (tmp_path, None))
    monkeypatch.setattr(
        macos, "prepare_macos", lambda *args, **kwargs: {"status": status, "id": "operation-test"}
    )
    result = CliRunner().invoke(cli.app, ["macos-prepare", "run", "candidate", "--game-dir", str(tmp_path)])
    assert result.exit_code == exit_code
    assert json.loads(result.stdout)["status"] == status
