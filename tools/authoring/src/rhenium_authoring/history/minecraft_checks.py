"""Checks run on the author's answer before any engine time is spent."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import AuthoredTask

BASE_IMAGE = "gcb-minecraft-paper-verifier:1.21.11-132"
_CASE = re.compile(r'@GcbCase\s*\(\s*(?:value\s*=\s*)?"((?:[^"\\]|\\.)*)"')
_PUBLIC_CLASS = re.compile(r"^\s*public\s+(?:final\s+|abstract\s+)*class\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
_FORBIDDEN = (
    ("System.exit", "the suite must not exit the JVM"),
    ("Bukkit.shutdown", "the suite must not stop the server"),
    ("getServer().shutdown", "the suite must not stop the server"),
    ("MINECRAFT_RESULT", "the suite must not print result markers"),
    ("Runtime.getRuntime().halt", "the suite must not halt the JVM"),
)
_COMPILE = (
    "set -e; cp=$(cat /opt/gcb/classpath.colon):/opt/gcb/harness/gcb-harness.jar:/candidate.jar; "
    'mkdir -p /tmp/out; javac --release 21 -proc:none -Xlint:none -encoding UTF-8 -cp "$cp" '
    '-d /tmp/out $(find /suite -name "*.java")'
)


def static_findings(task: AuthoredTask) -> list[str]:
    findings: list[str] = []
    declared: list[str] = []
    implements = False
    for path, source in sorted(task.suite.items()):
        declared.extend(_CASE.findall(source))
        implements = implements or "GcbSuite" in source and "implements" in source
        for public in _PUBLIC_CLASS.findall(source):
            if f"{public}.java" != path.rsplit("/", 1)[-1]:
                findings.append(f"{path}: public class {public} must live in {public}.java")
        for needle, message in _FORBIDDEN:
            if needle in source:
                findings.append(f"{path}: {message}")
    if not implements:
        findings.append("no suite class implements io.gamecodebench.harness.GcbSuite")
    names = [case.case for case in task.cases]
    for name in names:
        count = declared.count(name)
        if count != 1:
            findings.append(f"case {name!r} must be annotated exactly once with @GcbCase (found {count})")
    for extra in sorted(set(declared) - set(names)):
        findings.append(f"@GcbCase({extra!r}) is not listed in cases")
    return findings


def compile_findings(
    task: AuthoredTask, candidate_jar: Path, *, docker: str | None = None
) -> list[str] | None:
    """javac errors of the suite against Paper, the harness and the candidate jar.

    ``None`` means the check could not run (no Docker or no prepared base image);
    the engine still compiles the suite, so this only saves engine time.
    """
    executable = docker or shutil.which("docker")
    if not executable or not candidate_jar.is_file():
        return None
    probe = subprocess.run(
        [executable, "image", "inspect", BASE_IMAGE], capture_output=True, text=True, timeout=60, check=False
    )
    if probe.returncode != 0:
        return None
    with tempfile.TemporaryDirectory(prefix="history-suite-") as raw:
        suite = Path(raw) / "suite"
        for relative, source in task.suite.items():
            target = suite / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        Path(raw).chmod(0o755)
        for path in suite.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
        completed = subprocess.run(
            [
                executable,
                "run",
                "--rm",
                "--network=none",
                "--pull=never",
                "--mount",
                f"type=bind,source={suite},target=/suite,readonly",
                "--mount",
                f"type=bind,source={candidate_jar.resolve()},target=/candidate.jar,readonly",
                "--entrypoint",
                "bash",
                BASE_IMAGE,
                "-c",
                _COMPILE,
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    if completed.returncode == 0:
        return []
    # javac prints each error with its source line and caret; keep that context.
    output = (completed.stdout + completed.stderr).strip()
    return ["javac rejected the suite:\n" + output[:6000]]
