from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from rhenium_balatro import winjob
from rhenium_balatro.bridge import BINDING_NAME, child_environment, load_binding, serial_lock
from rhenium_balatro.native_assets import file_sha, verified_assets
from rhenium_balatro.sidecar import clone
from rhenium_balatro.winjob import OwnedJob


def test_scoped_clone_preserves_arguments_returns_and_exceptions() -> None:
    def source(a: int, b: int = 2, *, amount: int = 3) -> tuple[int, int, int]:
        if a == 0:
            raise ValueError("same exception")
        return a, b, amount

    copied = clone(source, {"UNUSED": "state relocation only"})
    assert copied(1) == source(1)
    assert copied(2, 7, amount=9) == source(2, 7, amount=9)
    with pytest.raises(ValueError, match="same exception"):
        copied(0)


@pytest.mark.skipif(os.name != "nt", reason="native Windows Job Object test")
def test_owned_job_gates_and_reaps_only_its_descendants() -> None:
    job = OwnedJob()
    child: Any = None
    unrelated: Any = None
    try:
        unrelated = subprocess.Popen([sys.executable, "-I", "-c", "import time;time.sleep(60)"])
        program = ("import sys,subprocess,time;sys.stdin.readline();"
                   "subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(60)']);"
                   "time.sleep(60)")
        child = subprocess.Popen([sys.executable, "-I", "-c", program], stdin=subprocess.PIPE)
        job.assign(int(child._handle))
        assert job.active() == 1
        child.stdin.write(b"go\n")
        child.stdin.close()
        end = time.monotonic() + 10
        while job.active() != 2 and time.monotonic() < end:
            time.sleep(.02)
        assert job.active() == 2
        job.terminate()
        child.wait(timeout=5)
        end = time.monotonic() + 5
        while job.active() and time.monotonic() < end:
            time.sleep(.02)
        assert job.active() == 0
        assert unrelated.poll() is None
    finally:
        job.close()
        for process in (child, unrelated):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="Windows environment and lock")
def test_minimum_environment_and_serial_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST_SECRET_NOT_FOR_CHILD", "not forwarded")
    env = child_environment(tmp_path)
    assert "HOST_SECRET_NOT_FOR_CHILD" not in env
    assert env["USERPROFILE"] == str(tmp_path / "profile")
    assert "PYTHONPATH" not in env
    state = tmp_path / "state"
    with serial_lock(state), pytest.raises(OSError), serial_lock(state):
        raise AssertionError("second process lock unexpectedly acquired")
    with serial_lock(state):
        pass


def test_stale_binding_refused_before_process_launch(tmp_path: Path) -> None:
    (tmp_path / BINDING_NAME).write_text(json.dumps({"schema_version": 1,
        "scope": "approved-honest-maintenance-v1", "adapter_sha256": "old"}), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        load_binding(tmp_path)


def test_private_asset_drift_refused_before_import(tmp_path: Path) -> None:
    private = tmp_path / "private/native-v1"
    (private / "fixtures").mkdir(parents=True)
    candidate = private / "fixtures/authored.lua"
    candidate.write_bytes(b"reviewed code")
    descriptor = private / "assets.json"
    descriptor.write_text(json.dumps({"files": {"fixtures/authored.lua": file_sha(candidate)}}),
                          encoding="utf-8")
    expected = file_sha(descriptor)
    assert verified_assets(tmp_path, expected)
    candidate.write_bytes(b"changed")
    with pytest.raises(ValueError, match="authored asset changed"):
        verified_assets(tmp_path, expected)


def test_extra_private_import_is_not_implicitly_reviewed(tmp_path: Path) -> None:
    private = tmp_path / "private/native-v1"
    (private / "fixtures").mkdir(parents=True)
    descriptor = private / "assets.json"
    descriptor.write_text(json.dumps({"files": {}}), encoding="utf-8")
    expected = file_sha(descriptor)
    assert verified_assets(tmp_path, expected)
    (private / "fixtures/__init__.py").write_bytes(b"unreviewed")
    with pytest.raises(ValueError, match="closure changed"):
        verified_assets(tmp_path, expected)


def test_windows_helpers_refuse_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as platform:
        platform.setattr(winjob.sys, "platform", "linux")
        with pytest.raises(OSError, match="native Windows"):
            OwnedJob()
        with pytest.raises(OSError, match="native Windows"):
            winjob.hidden_creation_flags()
