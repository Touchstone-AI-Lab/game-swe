from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_balatro import readiness
from rhenium_balatro.bridge import BINDING_NAME
from rhenium_balatro.files import validate_state
from rhenium_balatro.protocol import PROTOCOL


def test_state_inside_pack_rejected_before_creation(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    with pytest.raises(ValueError, match="outside"):
        validate_state(pack, pack / "state")
    assert not pack.exists()


def test_missing_binding_probe_does_not_write(tmp_path: Path) -> None:
    state = tmp_path / "state"
    result = readiness.runtime_status(tmp_path / "pack", state)
    assert result["available"] is False and result["gameStarted"] is False
    assert not state.exists()


@pytest.mark.skipif(os.name != "nt", reason="native Windows readiness helper")
@pytest.mark.parametrize("failure", [None, "nonce", "dependencies", "timeout", "halt"])
def test_probe_is_read_only_bounded_and_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / BINDING_NAME).write_text("fixture")
    if failure == "halt":
        (state / "native-halt.json").write_text("halt")
    before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
    monkeypatch.setattr(readiness, "load_binding", lambda _: {"assets_sha256": "assets", "python": "fixed"})
    monkeypatch.setattr(readiness, "verified_assets", lambda *_: {})
    monkeypatch.setenv("HOST_SECRET_DO_NOT_INHERIT", "private-token")
    calls = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        assert command[-1] == "--probe" and kwargs["timeout"] == 120
        assert "HOST_SECRET_DO_NOT_INHERIT" not in kwargs["env"]
        assert "USERPROFILE" not in kwargs["env"]
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 120)
        request = json.loads(kwargs["input"])
        assert request["operation"] == "probe" and "candidate" not in request and "work" not in request
        response = {"protocol": PROTOCOL, "request_id": request["request_id"],
            "nonce": "wrong" if failure == "nonce" else request["nonce"], "submission_sha256": "",
            "result": {"dependencies_verified": failure != "dependencies", "protected_unchanged": True,
                       "matching_smoke": True}}
        return subprocess.CompletedProcess(command, 0, json.dumps(response).encode(), b"")

    monkeypatch.setattr(readiness.subprocess, "run", run)
    result = readiness.runtime_status(tmp_path / "pack", state)
    assert result["available"] is (failure is None)
    assert result["gameStarted"] is False
    assert len(calls) == (0 if failure == "halt" else 1)
    assert {p: p.read_bytes() for p in state.rglob("*") if p.is_file()} == before
    assert all(value not in json.dumps(result) for value in (str(tmp_path), "private-token", "wrong"))
