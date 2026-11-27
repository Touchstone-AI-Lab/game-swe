from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_authoring.verifier_checks import VerifierScriptError, validate_verifier_scripts


def test_valid_shell_is_checked_without_running_it(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    scripts = {
        "check.sh": f'#!/bin/bash\nset -eu\nprintf "ran" > "{marker}"\n',
        "nested/test.bash": "#!/bin/bash\nstatus=0\nexit \"$status\"\n",
        "runner": "#!/usr/bin/env bash\nprintf '%s\\n' ok\n",
        "server.lua": "return function() end\n",
    }
    assert validate_verifier_scripts(scripts) == ["check.sh", "nested/test.bash", "runner"]
    assert not marker.exists()


def test_shellcheck_rejects_masked_command_status_without_leaking_source() -> None:
    source = (
        "#!/bin/bash\n"
        "check() {\n"
        "  local status=$(printf 'private-fixture-value')\n"
        "  printf '%s\\n' \"$status\"\n"
        "}\n"
        "check\n"
    )
    with pytest.raises(VerifierScriptError) as captured:
        validate_verifier_scripts({"nested/check.sh": source})
    assert "nested/check.sh:3:SC2155" in captured.value.findings
    assert "private-fixture-value" not in str(captured.value)
    assert "local status" not in str(captured.value)


def test_invalid_shell_syntax_fails_with_safe_diagnostics() -> None:
    with pytest.raises(VerifierScriptError) as captured:
        validate_verifier_scripts({"check.sh": "#!/bin/bash\nif private-fixture-value; then\n"})
    assert "check.sh:BASH_SYNTAX" in captured.value.findings
    assert "private-fixture-value" not in str(captured.value)


@pytest.mark.parametrize("checker", ["bash", "shellcheck"])
def test_missing_checker_fails_closed(monkeypatch: pytest.MonkeyPatch, checker: str) -> None:
    monkeypatch.setattr(
        "rhenium_authoring.verifier_checks.shutil.which",
        lambda name: None if name == checker else f"/checkers/{name}",
    )
    with pytest.raises(VerifierScriptError, match=f"{checker.upper()}_UNAVAILABLE"):
        validate_verifier_scripts({"check.sh": "#!/bin/bash\nprintf ok\n"})


def test_non_shell_verifier_needs_no_shell_checkers(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_lookup(_name: str) -> None:
        pytest.fail("non-shell verifiers must not depend on shell checkers")

    monkeypatch.setattr("rhenium_authoring.verifier_checks.shutil.which", unexpected_lookup)
    assert validate_verifier_scripts({"server.lua": "return function() end\n"}) == []


@pytest.mark.parametrize("path", ["../check.sh", "/private/check.sh", "person@example.com.sh"])
def test_unsafe_diagnostic_path_is_not_echoed(path: str) -> None:
    with pytest.raises(VerifierScriptError, match="UNSAFE_SCRIPT_PATH") as captured:
        validate_verifier_scripts({path: "#!/bin/bash\nprintf ok\n"})
    assert path not in str(captured.value)


@pytest.mark.parametrize("directive", ["disable=SC2155", "external-sources=true"])
def test_generated_shell_cannot_reconfigure_checker(directive: str) -> None:
    with pytest.raises(VerifierScriptError, match="SHELLCHECK_DIRECTIVE"):
        validate_verifier_scripts({"check.sh": f"#!/bin/bash\n# shellcheck {directive}\nprintf ok\n"})


@pytest.mark.parametrize("failure", ["timeout", "invalid-output", "failed-empty"])
def test_checker_failures_are_not_treated_as_clean(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setattr(
        "rhenium_authoring.verifier_checks.shutil.which", lambda name: f"/checkers/{name}"
    )

    def run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["input"] == "#!/bin/bash\nprintf ok\n"
        assert "BASH_ENV" not in kwargs["env"]
        assert "SHELLCHECK_OPTS" not in kwargs["env"]
        if arguments[0].endswith("bash"):
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(arguments, 30, output="private-fixture-value")
        output = "private-fixture-value" if failure == "invalid-output" else "[]"
        return subprocess.CompletedProcess(arguments, 2, output, "private-fixture-value")

    monkeypatch.setattr("rhenium_authoring.verifier_checks.subprocess.run", run)
    with pytest.raises(VerifierScriptError) as captured:
        validate_verifier_scripts({"check.sh": "#!/bin/bash\nprintf ok\n"})
    assert "private-fixture-value" not in str(captured.value)
