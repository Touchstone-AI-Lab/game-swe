from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROBE = Path(__file__).resolve().parents[1] / "runtime/linux/probe_host_v1.py"
SPEC = importlib.util.spec_from_file_location("balatro_linux_host_probe", PROBE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample() -> dict[str, Any]:
    return {"system": "Linux", "machine": "x86_64", "x11_socket": True,
            "display_present": True, "commands": {"docker": {"exit_code": 0,
                "stdout": json.dumps({"Os": "linux", "Arch": "amd64"})}}}


def test_available_host_is_not_engine_evidence() -> None:
    result = MODULE.classify(sample())
    assert result["host_prerequisites_available"]
    assert not result["real_engine_validated"]


def test_docker_cli_or_wrong_host_is_not_a_working_linux_host() -> None:
    for change in ({"system": "Windows"}, {"x11_socket": False},
                   {"commands": {"docker": {"exit_code": 1, "stdout": "null"}}},
                   {"commands": {"docker": {"exit_code": 0, "stdout": "invalid"}}}):
        assert not MODULE.classify({**sample(), **change})["host_prerequisites_available"]


def test_timeout_is_incomplete_and_not_retried() -> None:
    with patch.object(MODULE.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 20)) as run:
        result = MODULE.command(["docker", "version"])
    assert run.call_count == 1
    assert result["exit_code"] is None and result["timed_out"] is True
