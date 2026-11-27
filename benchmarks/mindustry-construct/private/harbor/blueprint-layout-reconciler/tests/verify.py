#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/workspace/mindustry"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
SERVER = Path(os.environ.get("MINDUSTRY_SERVER", "/mindustry/server-release.jar"))

MARKER = "MINDUSTRY_RESULT "
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

MAX_FILES = 100
MAX_FILE_BYTES = 2_000_000
MAX_TREE_BYTES = 10_000_000


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise EnvironmentFailure(f"command timed out: {' '.join(command)}") from error
    except OSError as error:
        raise EnvironmentFailure(f"could not execute command: {error}") from error


def validate_environment() -> None:
    if not SUBMISSION.is_dir():
        raise EnvironmentFailure(f"submission directory is missing: {SUBMISSION}")

    if not SERVER.is_file():
        raise EnvironmentFailure(f"Mindustry server JAR is missing: {SERVER}")

    if not TESTS.is_dir():
        raise EnvironmentFailure(f"tests directory is missing: {TESTS}")

    if not (TESTS / "rubric.json").is_file():
        raise EnvironmentFailure("rubric.json is missing")

    if not (TESTS / "grader/build-test-runner.sh").is_file():
        raise EnvironmentFailure("grader build script is missing")

    java = run(["java", "-version"])
    if java.returncode != 0:
        raise EnvironmentFailure("java is unavailable")

    javac = run(["javac", "-version"])
    if javac.returncode != 0:
        raise EnvironmentFailure("javac is unavailable")


def validate_submission() -> None:
    errors: list[str] = []
    files: list[Path] = []
    total_bytes = 0

    src = SUBMISSION / "src"

    if not src.is_dir():
        errors.append("src directory is missing")

    manifest = SUBMISSION / "plugin.hjson"
    if not manifest.is_file():
        errors.append("plugin.hjson is missing")

    for path in SUBMISSION.rglob("*"):
        if path.is_symlink():
            errors.append(
                f"{path.relative_to(SUBMISSION)}: symbolic links are not allowed"
            )
            continue

        if not path.is_file():
            continue

        files.append(path)
        size = path.stat().st_size
        total_bytes += size

        if size > MAX_FILE_BYTES:
            errors.append(
                f"{path.relative_to(SUBMISSION)}: file exceeds size limit"
            )

    if len(files) > MAX_FILES:
        errors.append(f"project has too many files: {len(files)}")

    if total_bytes > MAX_TREE_BYTES:
        errors.append(f"project exceeds size limit: {total_bytes} bytes")

    if errors:
        raise SubmissionFailure(
            "source/package checks failed:\n- " + "\n- ".join(errors)
        )

    print(
        f"source/package checks passed: files={len(files)} bytes={total_bytes}"
    )


def build_candidate() -> Path:
    build_script = SUBMISSION / "build-reference.sh"

    if not build_script.is_file():
        raise EnvironmentFailure("build-reference.sh is missing")

    completed = run(
        ["bash", str(build_script), str(SERVER)],
        cwd=SUBMISSION,
    )

    if completed.stdout:
        print(completed.stdout, end="")

    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    if completed.returncode != 0:
        raise SubmissionFailure("candidate compilation failed")

    candidate = SUBMISSION / "build/candidate/candidate.jar"

    if not candidate.is_file() or candidate.stat().st_size == 0:
        raise SubmissionFailure("candidate.jar was not produced")

    print(f"candidate build passed: {candidate}")
    return candidate


def build_grader(candidate: Path) -> Path:
    script = TESTS / "grader/build-test-runner.sh"

    grader = Path("/tmp/blueprint-layout-reconciler-tests.jar")
    grader.unlink(missing_ok=True)

    completed = run(
        ["bash", str(script), str(SERVER), str(candidate), str(grader)],
        cwd=TESTS / "grader",
    )

    if completed.stdout:
        print(completed.stdout, end="")

    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    if completed.returncode != 0:
        raise EnvironmentFailure("grader compilation failed")

    if not grader.is_file() or grader.stat().st_size == 0:
        raise EnvironmentFailure("grader JAR was not produced")

    print(f"grader build passed: {grader}")
    return grader


def run_server(candidate: Path, grader: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="mindustry-verifier-") as raw_root:
        root = Path(raw_root)
        config = root / "config"
        mods = config / "mods"
        mods.mkdir(parents=True)

        candidate_target = mods / "candidate.jar"
        grader_target = mods / "test-runner.jar"

        candidate_target.write_bytes(candidate.read_bytes())
        grader_target.write_bytes(grader.read_bytes())

        try:
            completed = subprocess.run(
                ["java", "-jar", str(SERVER)],
                cwd=root,
                input="host Fortress\n",
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ""
            stderr = error.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")

            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")

            log = stdout + stderr
        else:
            log = completed.stdout + completed.stderr

        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / "server.log").write_text(log, encoding="utf-8")

    clean = ANSI.sub("", log)

    payloads = [
        line.split(MARKER, 1)[1].strip()
        for line in clean.splitlines()
        if MARKER in line
    ]

    if len(payloads) != 1:
        raise SubmissionFailure(
            f"invalid result count: expected 1, got {len(payloads)}"
        )

    try:
        result = json.loads(payloads[0])
    except json.JSONDecodeError as error:
        raise SubmissionFailure("grader emitted malformed JSON") from error

    if not isinstance(result, dict):
        raise SubmissionFailure("grader result is not an object")

    return result


def validate_result(result: dict) -> None:
    rubric_data = json.loads(
        (TESTS / "rubric.json").read_text(encoding="utf-8")
    )

    cases = rubric_data.get("cases")

    if not isinstance(cases, list):
        raise EnvironmentFailure("invalid rubric")

    rubric = {item["name"]: item for item in cases}

    if sum(int(item["maximum"]) for item in rubric.values()) != 70:
        raise EnvironmentFailure("runtime rubric total is not 70")

    runtime_score = 0
    seen: set[str] = set()

    for case in result.get("cases", []):
        name = case.get("name")

        if name not in rubric:
            raise SubmissionFailure(f"unknown grader case: {name}")

        if name in seen:
            raise SubmissionFailure(f"duplicate grader case: {name}")

        seen.add(name)

        if case.get("passed") is True:
            runtime_score += int(rubric[name]["maximum"])

    missing = sorted(set(rubric) - seen)

    if missing:
        raise SubmissionFailure(
            "missing grader cases: " + ", ".join(missing)
        )

    total_score = 30 + runtime_score

    print(
        json.dumps(
            {
                "passed": result.get("passed") is True,
                "runtime_score": runtime_score,
                "runtime_maximum": 70,
                "total_score": total_score,
                "total_maximum": 100,
                "cases": result.get("cases", []),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if result.get("passed") is not True:
        raise SubmissionFailure(
            f"runtime cases did not all pass: score={runtime_score}/70"
        )


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)

    try:
        validate_environment()
        validate_submission()
        candidate = build_candidate()
        grader = build_grader(candidate)
        result = run_server(candidate, grader)
        validate_result(result)
    except EnvironmentFailure as error:
        print(f"INVALID_ENVIRONMENT: {error}")
        return 2
    except (SubmissionFailure, OSError) as error:
        print(f"SUBMISSION_FAILED: {error}")
        return 1

    print("VERIFICATION_PASSED: all Mindustry blueprint-layout-reconciler checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
