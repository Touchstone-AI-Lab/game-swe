#!/usr/bin/env python3
"""Verifier for one Mindustry (game source) repair task.

Runs inside the task's verifier image with no network. Two layers:

1. shape checks and the offline build: every ``*.java`` file below the declared
   source roots of the submitted Mindustry tree is compiled with ``javac`` against
   the pinned dedicated-server jar, which supplies Arc, the generated
   ``mindustry.gen`` classes and every other runtime dependency;
2. the hidden grader suite on the real headless server: the compiled candidate
   classes are put in front of the pinned server jar on the class path, and the
   trusted Rhenium harness plugin (bundled with the task's frozen suite) runs the
   cases in the live server and prints one nonce-tagged result line.

Everything fails closed: a missing product, an unexpected case set or a malformed
harness payload makes the run incomplete, never a pass. Exit codes: 0 passed,
1 submission failed, 2 the environment itself was invalid.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SUBMISSION = Path(os.environ.get("RHENIUM_SUBMISSION", "/submission/mindustry"))
WORKSPACE = Path(os.environ.get("RHENIUM_WORKSPACE", "/app/mindustry"))
TESTS = Path(os.environ.get("RHENIUM_TESTS", "/tests"))
LOGS = Path(os.environ.get("RHENIUM_LOGS", "/logs/verifier"))
MINDUSTRY = Path(os.environ.get("RHENIUM_MINDUSTRY", "/opt/mindustry"))
HOME = Path(os.environ.get("RHENIUM_HOME", "/opt/rhenium"))
WORK = Path(os.environ.get("RHENIUM_WORK", "/work"))
SERVER_TIMEOUT = int(os.environ.get("RHENIUM_SERVER_TIMEOUT", "600"))
BUILD_TIMEOUT = int(os.environ.get("RHENIUM_BUILD_TIMEOUT", "900"))

MARKER = "MINDUSTRY_RESULT "
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
SERVER_JAR = "server-release.jar"
GRADER_JAR = "rhenium-grader.jar"
MAX_FILES = 4000
MAX_FILE_BYTES = 4_000_000
MAX_TREE_BYTES = 80_000_000
FORBIDDEN_SUFFIXES = {".class", ".jar", ".zip"}


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value if isinstance(value, str) else ""


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    log_name: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        if log_name:
            (LOGS / log_name).write_text(_text(error.stdout) + _text(error.stderr), encoding="utf-8")
        raise SubmissionFailure(f"command timed out after {timeout}s: {' '.join(command[:2])}") from error
    except OSError as error:
        raise EnvironmentFailure(f"could not execute {command[0]}: {error}") from error
    if log_name:
        (LOGS / log_name).write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed


# --- pure helpers (unit-tested from the plugin test suite) -------------------


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


def extract_payloads(server_log: str) -> list[str]:
    clean = strip_ansi(server_log)
    return [line.split(MARKER, 1)[1].strip() for line in clean.splitlines() if MARKER in line]


def check_case_set(observed: list[dict[str, Any]], expected: list[str]) -> str | None:
    names = [case["name"] for case in observed]
    if len(names) != len(set(names)):
        return "duplicate case names"
    missing = sorted(set(expected) - set(names))
    extra = sorted(set(names) - set(expected))
    if missing:
        return "missing cases: " + ", ".join(missing[:10])
    if extra:
        return "unexpected cases: " + ", ".join(extra[:10])
    return None


def validate_shape(root: Path) -> list[str]:
    problems: list[str] = []
    if root.is_symlink() or not root.is_dir():
        return [f"{root} is not a directory"]
    count = 0
    total = 0
    for candidate in root.rglob("*"):
        relative = candidate.relative_to(root)
        if candidate.is_symlink():
            problems.append(f"{relative}: symbolic links are not allowed")
            continue
        if not candidate.is_file():
            continue
        count += 1
        size = candidate.stat().st_size
        total += size
        if ".git" in relative.parts:
            problems.append(f"{relative}: version-control metadata is not allowed")
        elif candidate.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"{relative}: compiled artifacts are not allowed")
        if size > MAX_FILE_BYTES:
            problems.append(f"{relative}: file exceeds {MAX_FILE_BYTES} bytes")
    if count > MAX_FILES:
        problems.append(f"too many files: {count}")
    if total > MAX_TREE_BYTES:
        problems.append(f"tree exceeds {MAX_TREE_BYTES} bytes")
    return problems


def source_files(root: Path, build: dict[str, Any]) -> list[str]:
    """Relative paths of every Java source the trusted build compiles, sorted."""
    files: set[str] = set()
    for source_root in build["sourceRoots"]:
        directory = root / source_root
        if not directory.is_dir():
            raise SubmissionFailure(f"source root is missing: {source_root}")
        for path in directory.rglob("*.java"):
            if path.is_file() and not path.is_symlink():
                files.add(path.relative_to(root).as_posix())
    for extra in build.get("extraSources", []):
        if not (root / extra).is_file():
            raise SubmissionFailure(f"required source is missing: {extra}")
        files.add(extra)
    if not files:
        raise SubmissionFailure("no Java sources to compile")
    return sorted(files)


def parse_envelope(payloads: list[str], nonce: str, expected: list[str]) -> dict[str, Any]:
    """Validate the harness payloads; returns the live-layer result."""
    if len(payloads) != 1:
        return {
            "status": "incomplete",
            "payloadCount": len(payloads),
            "cases": [],
            "problem": f"expected exactly one harness payload, saw {len(payloads)}",
        }
    try:
        envelope = json.loads(payloads[0])
    except json.JSONDecodeError:
        return {
            "status": "incomplete",
            "payloadCount": 1,
            "cases": [],
            "problem": "harness payload is not JSON",
        }
    if not isinstance(envelope, dict) or envelope.get("schema") != 1 or envelope.get("nonce") != nonce:
        return {
            "status": "incomplete",
            "payloadCount": 1,
            "cases": [],
            "problem": "harness payload nonce mismatch",
        }
    if envelope.get("fatal"):
        return {
            "status": "incomplete",
            "payloadCount": 1,
            "cases": [],
            "problem": f"harness fatal: {str(envelope['fatal'])[:400]}",
        }
    cases: list[dict[str, Any]] = []
    raw_cases = envelope.get("cases")
    if isinstance(raw_cases, list):
        for item in raw_cases:
            if (
                isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and type(item.get("passed")) is bool
            ):
                cases.append(
                    {
                        "name": item["name"],
                        "passed": item["passed"],
                        "message": str(item.get("message", ""))[:400],
                    }
                )
    problem = check_case_set(cases, expected)
    if problem:
        return {"status": "incomplete", "payloadCount": 1, "cases": cases, "problem": problem}
    passed = all(case["passed"] for case in cases)
    order = {name: index for index, name in enumerate(expected)}
    return {
        "status": "passed" if passed else "failed",
        "payloadCount": 1,
        "game": str(envelope.get("game", ""))[:80],
        "cases": sorted(cases, key=lambda case: order[case["name"]]),
    }


# --- layers ------------------------------------------------------------------


def load_task() -> dict[str, Any]:
    try:
        task = json.loads((TESTS / "task.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EnvironmentFailure(f"task.json is unreadable: {error}") from error
    if not isinstance(task, dict) or task.get("schemaVersion") != 1:
        raise EnvironmentFailure("task.json has an unsupported schema")
    for key in ("taskId", "build", "serverCases"):
        if key not in task:
            raise EnvironmentFailure(f"task.json lacks {key}")
    if task["build"].get("tool") != "mindustry-source":
        raise EnvironmentFailure("unsupported build tool")
    return task


def validate_environment() -> None:
    checks = {
        "server jar": MINDUSTRY / SERVER_JAR,
        "grader plugin": HOME / "grader" / GRADER_JAR,
        "submission": SUBMISSION,
    }
    for label, path in checks.items():
        if not path.exists():
            raise EnvironmentFailure(f"{label} is missing: {path}")
    for tool in ("java", "javac", "rsync"):
        if shutil.which(tool) is None:
            raise EnvironmentFailure(f"{tool} is unavailable")


def sync_submission() -> None:
    problems = validate_shape(SUBMISSION)
    if problems:
        raise SubmissionFailure("submission shape checks failed:\n- " + "\n- ".join(problems[:20]))
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    completed = run(
        ["rsync", "-a", "--no-owner", "--no-group", "--delete", f"{SUBMISSION}/", f"{WORKSPACE}/"],
        cwd=WORKSPACE,
        timeout=300,
    )
    if completed.returncode != 0:
        raise EnvironmentFailure("could not copy the submission into the workspace")


def build_submission(task: dict[str, Any]) -> Path:
    build = task["build"]
    files = source_files(WORKSPACE, build)
    classes = WORK / "classes"
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True)
    argfile = WORK / "sources.txt"
    argfile.write_text("".join(f"{WORKSPACE / name}\n" for name in files), encoding="utf-8")
    completed = run(
        [
            "javac",
            "-J-Xmx3g",
            "--release",
            str(build.get("javaRelease", 17)),
            "-proc:none",
            "-nowarn",
            "-Xlint:none",
            "-encoding",
            "UTF-8",
            "-cp",
            str(MINDUSTRY / SERVER_JAR),
            "-d",
            str(classes),
            f"@{argfile}",
        ],
        cwd=WORKSPACE,
        timeout=BUILD_TIMEOUT,
        log_name="build-submission.log",
    )
    if completed.returncode != 0:
        raise SubmissionFailure(f"offline build failed with exit status {completed.returncode}")
    if not any(classes.rglob("*.class")):
        raise SubmissionFailure("the build produced no classes")
    log(f"offline build passed: {len(files)} sources compiled")
    return classes


def run_server(task: dict[str, Any], classes: Path) -> dict[str, Any]:
    server = WORK / "server"
    if server.exists():
        shutil.rmtree(server)
    mods = server / "config" / "mods"
    mods.mkdir(parents=True)
    shutil.copyfile(HOME / "grader" / GRADER_JAR, mods / GRADER_JAR)
    nonce = secrets.token_hex(16)
    command = [
        "java",
        "-Xms512m",
        "-Xmx2g",
        "-Djava.awt.headless=true",
        "-Drhenium.harness.mode=suite",
        f"-Drhenium.harness.nonce={nonce}",
        "-cp",
        f"{classes}:{MINDUSTRY / SERVER_JAR}",
        "mindustry.server.ServerLauncher",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=server,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=SERVER_TIMEOUT,
        )
        output = completed.stdout + completed.stderr
        exit_status: int | None = completed.returncode
    except subprocess.TimeoutExpired as error:
        output = _text(error.stdout) + _text(error.stderr)
        exit_status = None
    (LOGS / "server.log").write_text(output, encoding="utf-8")
    payloads = extract_payloads(output)
    if exit_status is None:
        return {"status": "server-timeout", "serverExit": None, "payloadCount": len(payloads), "cases": []}
    result = parse_envelope(payloads, nonce, list(task["serverCases"]))
    result["serverExit"] = exit_status
    if result["status"] in {"passed", "failed"}:
        passed = sum(case["passed"] for case in result["cases"])
        log(f"live server {result['status']}: {passed}/{len(result['cases'])}")
    else:
        log(f"live server incomplete: {result.get('problem')}")
    return result


def write_result(result: dict[str, Any]) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (LOGS / "reward.txt").write_text(f"{result['reward']}\n", encoding="utf-8")


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "taskId": None,
        "build": {"status": "not-run"},
        "live": {"status": "not-run", "cases": []},
        "complete": False,
        "passed": False,
        "reward": 0,
    }
    try:
        task = load_task()
        result["taskId"] = task["taskId"]
        validate_environment()
        WORK.mkdir(parents=True, exist_ok=True)
        try:
            sync_submission()
            classes = build_submission(task)
        except SubmissionFailure as error:
            result["build"] = {"status": "failed", "problem": str(error)}
            log(f"SUBMISSION_FAILED: {error}")
            write_result(result)
            return 1
        result["build"] = {"status": "passed"}
        result["live"] = run_server(task, classes)
        result["complete"] = result["live"]["status"] in {"passed", "failed"}
        result["passed"] = bool(result["complete"] and result["live"]["status"] == "passed")
        result["reward"] = 1 if result["passed"] else 0
        write_result(result)
        if not result["complete"]:
            log("SUBMISSION_FAILED: verification did not complete with the frozen case set")
            return 1
        if not result["passed"]:
            log("SUBMISSION_FAILED: one or more cases failed")
            return 1
        log("VERIFICATION_PASSED: build and real-server cases all passed")
        return 0
    except EnvironmentFailure as error:
        result["environment"] = str(error)
        write_result(result)
        log(f"INVALID_ENVIRONMENT: {error}")
        return 2
    except (SubmissionFailure, OSError) as error:
        write_result(result)
        log(f"SUBMISSION_FAILED: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
