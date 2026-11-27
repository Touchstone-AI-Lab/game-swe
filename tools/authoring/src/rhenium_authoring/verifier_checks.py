from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import PurePosixPath

_SHELL_SHEBANG = re.compile(r"^#![^\n]*\b(?:bash|sh|dash|ksh)\b")
_SHELLCHECK_DIRECTIVE = re.compile(r"(?m)^\s*#\s*shellcheck\b")
_SAFE_PATH = re.compile(r"[A-Za-z0-9_./-]+\Z")
_CHECK_TIMEOUT = 30


class VerifierScriptError(ValueError):
    def __init__(self, findings: list[str]):
        self.findings = tuple(findings)
        super().__init__("verifier shell checks failed: " + "; ".join(findings))


def validate_verifier_scripts(files: dict[str, str]) -> list[str]:
    """Statically check verifier shell through stdin, without executing its code."""

    scripts: dict[str, str] = {}
    for raw, content in files.items():
        if PurePosixPath(raw).suffix not in {".sh", ".bash"} and not _SHELL_SHEBANG.match(content):
            continue
        relative_path = PurePosixPath(raw)
        if (
            not _SAFE_PATH.fullmatch(raw)
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or raw != relative_path.as_posix()
        ):
            raise VerifierScriptError(["verifier:UNSAFE_SCRIPT_PATH"])
        scripts[raw] = content
    if not scripts:
        return []

    bash = shutil.which("bash")
    shellcheck = shutil.which("shellcheck")
    missing = [
        f"verifier:{code}_UNAVAILABLE"
        for code, executable in (("BASH", bash), ("SHELLCHECK", shellcheck))
        if executable is None
    ]
    if missing:
        raise VerifierScriptError(missing)
    assert bash is not None and shellcheck is not None

    findings: list[str] = []
    for path, source in sorted(scripts.items()):
        if _SHELLCHECK_DIRECTIVE.search(source):
            findings.append(f"{path}:SHELLCHECK_DIRECTIVE")
            continue
        syntax = _check([bash, "--noprofile", "--norc", "-n"], source, path, "BASH")
        if syntax.returncode != 0:
            findings.append(f"{path}:BASH_SYNTAX")
        lint = _check(
            [shellcheck, "--norc", "--format=json", "--shell=bash", "-"],
            source,
            path,
            "SHELLCHECK",
        )
        try:
            diagnostics = json.loads(lint.stdout)
        except (ValueError, TypeError):
            raise VerifierScriptError([f"{path}:SHELLCHECK_INVALID_OUTPUT"]) from None
        if not isinstance(diagnostics, list):
            raise VerifierScriptError([f"{path}:SHELLCHECK_INVALID_OUTPUT"])
        for diagnostic in diagnostics:
            if (
                not isinstance(diagnostic, dict)
                or type(diagnostic.get("code")) is not int
                or type(diagnostic.get("line")) is not int
                or diagnostic["code"] <= 0
                or diagnostic["line"] <= 0
            ):
                raise VerifierScriptError([f"{path}:SHELLCHECK_INVALID_OUTPUT"])
            findings.append(f"{path}:{diagnostic['line']}:SC{diagnostic['code']}")
        if lint.returncode not in (0, 1) or (lint.returncode != 0 and not diagnostics):
            findings.append(f"{path}:SHELLCHECK_FAILED")
    if findings:
        raise VerifierScriptError(findings)
    return sorted(scripts)


def _check(
    arguments: list[str], source: str, path: str, checker: str
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments,
            input=source,
            capture_output=True,
            text=True,
            check=False,
            timeout=_CHECK_TIMEOUT,
            env={"PATH": os.defpath, "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired:
        raise VerifierScriptError([f"{path}:{checker}_TIMEOUT"]) from None
    except (OSError, UnicodeError):
        raise VerifierScriptError([f"{path}:{checker}_UNAVAILABLE"]) from None
