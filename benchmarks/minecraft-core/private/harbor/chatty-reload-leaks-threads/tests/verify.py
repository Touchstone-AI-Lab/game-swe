#!/usr/bin/env python3
"""Verifier for one Minecraft (Paper plugin) repair task.

Runs inside the task's verifier image with no network. Three layers:

1. shape + offline build with the repository's own build tool (or the trusted
   javac build for clean-room tasks), after restoring the frozen build files
   and upstream tests from the starter snapshot;
2. the repository's own unit tests, parsed from their JUnit XML reports;
3. the hidden grader suite on the real Paper server through GcbHarness.

Everything fails closed: a missing product, an unexpected case set or a
malformed harness payload makes the run incomplete, never a pass. Exit codes
follow the Mindustry verifier: 0 passed, 1 submission failed, 2 the
environment itself was invalid.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/submission/plugin"))
WORKSPACE = Path(os.environ.get("GCB_WORKSPACE", "/app/plugin"))
TESTS = Path(os.environ.get("GCB_TESTS", "/tests"))
LOGS = Path(os.environ.get("GCB_LOGS", "/logs/verifier"))
PAPER = Path(os.environ.get("GCB_PAPER", "/opt/paper"))
HOME = Path(os.environ.get("GCB_HOME", "/opt/gcb"))
SERVER_TIMEOUT = int(os.environ.get("GCB_SERVER_TIMEOUT", "420"))
BUILD_TIMEOUT = int(os.environ.get("GCB_BUILD_TIMEOUT", "900"))
TEST_TIMEOUT = int(os.environ.get("GCB_TEST_TIMEOUT", "900"))

MARKER = "MINECRAFT_RESULT "
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SERVER_JAR = "paper-1.21.11-132.jar"
HARNESS_NAME = "GcbHarness"
GRADER_NAME = "GcbGrader"
MAX_FILES = 3000
MAX_FILE_BYTES = 8_000_000
MAX_TREE_BYTES = 60_000_000
BUILD_DIRECTORIES = {"build", "target", ".gradle", "out"}
FORBIDDEN_SUFFIXES = {".class", ".jar", ".zip"}
# Build-tool wrapper bootstrap jars are frozen paths and restored from the starter.
WRAPPER_JARS = {"gradle/wrapper/gradle-wrapper.jar", ".mvn/wrapper/maven-wrapper.jar"}


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    log_name: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired as error:
        output = _text(error.stdout) + _text(error.stderr)
        if log_name:
            (LOGS / log_name).write_text(output, encoding="utf-8")
        raise SubmissionFailure(f"command timed out after {timeout}s: {' '.join(command[:3])}") from error
    except OSError as error:
        raise EnvironmentFailure(f"could not execute {command[0]}: {error}") from error
    if log_name:
        (LOGS / log_name).write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed


def _text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or "" if isinstance(value, str) else ""


# --- pure helpers (unit-tested from the plugin test suite) -------------------


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


def extract_payloads(server_log: str) -> list[str]:
    clean = strip_ansi(server_log)
    return [line.split(MARKER, 1)[1].strip() for line in clean.splitlines() if MARKER in line]


def parse_junit_reports(paths: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    """Per-test outcomes from JUnit XML; skipped and duplicated tests are unobserved."""
    seen: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for path in sorted(paths):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        for case in root.iter("testcase"):
            classname = case.get("classname") or ""
            name = case.get("name") or ""
            if not classname or not name:
                continue
            identity = f"{classname}.{name}"
            if case.find("skipped") is not None:
                continue
            failure = case.find("failure")
            error = case.find("error")
            if failure is not None or error is not None:
                node = failure if failure is not None else error
                message = (node.get("message") or node.get("type") or "failed").strip()
                record = {"name": identity, "passed": False, "message": message[:400]}
            else:
                record = {"name": identity, "passed": True, "message": "ok"}
            if identity in seen:
                duplicates.add(identity)
            seen[identity] = record
    for identity in duplicates:
        seen.pop(identity, None)
    return list(seen.values()), sorted(duplicates)


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


def validate_shape(root: Path, required: list[str]) -> list[str]:
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
        parts = relative.parts
        if ".git" in parts:
            problems.append(f"{relative}: version-control metadata is not allowed")
        elif (
            candidate.suffix.lower() in FORBIDDEN_SUFFIXES
            and not any(part in BUILD_DIRECTORIES for part in parts[:-1])
            and relative.as_posix() not in WRAPPER_JARS
        ):
            problems.append(f"{relative}: compiled artifacts outside build output")
        if size > MAX_FILE_BYTES:
            problems.append(f"{relative}: file exceeds {MAX_FILE_BYTES} bytes")
    if count > MAX_FILES:
        problems.append(f"too many files: {count}")
    if total > MAX_TREE_BYTES:
        problems.append(f"tree exceeds {MAX_TREE_BYTES} bytes")
    for relative in required:
        if not (root / relative).is_file():
            problems.append(f"{relative}: required file is missing")
    return problems


def restore_frozen_paths(workspace: Path, frozen: Path, paths: list[str]) -> list[str]:
    """Replace every frozen path in the workspace with the starter's copy (or remove it)."""
    restored: list[str] = []
    for relative in paths:
        target = workspace / relative
        source = frozen / relative
        if target.is_symlink() or target.exists():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        if source.is_dir():
            shutil.copytree(source, target, symlinks=False)
            restored.append(relative)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            shutil.copymode(source, target)
            restored.append(relative)
    return restored


def grader_plugin_yml(candidate: str) -> str:
    return (
        f"name: {GRADER_NAME}\n"
        "main: io.gamecodebench.grader.GraderPlugin\n"
        "version: 0.1.0\n"
        "api-version: '1.21'\n"
        f"depend: [{HARNESS_NAME}, {candidate}]\n"
        "description: GameCodeBench task grader\n"
    )


GRADER_MAIN = """package io.gamecodebench.grader;

public final class GraderPlugin extends org.bukkit.plugin.java.JavaPlugin {
    @Override
    public void onEnable() {
        io.gamecodebench.harness.GcbHarnessApi.registerFromJar(this);
    }
}
"""


def plugin_yml_name(text: str) -> str | None:
    match = re.search(r"^name:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


# --- layers ------------------------------------------------------------------


def starter_dir() -> Path | None:
    """The starter mirror: baked into the image by the Dockerfile, or mounted with tests/."""
    for candidate in (HOME / "starter", TESTS / "starter"):
        if candidate.is_dir():
            return candidate
    return None


def load_task() -> dict[str, Any]:
    try:
        task = json.loads((TESTS / "task.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EnvironmentFailure(f"task.json is unreadable: {error}") from error
    if not isinstance(task, dict) or task.get("schemaVersion") != 1:
        raise EnvironmentFailure("task.json has an unsupported schema")
    for key in ("taskId", "pluginName", "build", "unitCases", "serverCases"):
        if key not in task:
            raise EnvironmentFailure(f"task.json lacks {key}")
    return task


def validate_environment(task: dict[str, Any]) -> None:
    checks = {
        "server jar": PAPER / SERVER_JAR,
        "patched server": PAPER / "versions" / "1.21.11" / "paper-1.21.11.jar",
        "libraries": PAPER / "libraries",
        "eula": PAPER / "eula.txt",
        "world": PAPER / "world" / "level.dat",
        "classpath": HOME / "classpath.colon",
        "harness": HOME / "harness" / "gcb-harness.jar",
        "javac build": HOME / "javac-build.sh",
        "submission": SUBMISSION,
    }
    for label, path in checks.items():
        if not path.exists():
            raise EnvironmentFailure(f"{label} is missing: {path}")
    if not re.search(r"^\s*eula\s*=\s*true\s*$", (PAPER / "eula.txt").read_text(), re.I | re.M):
        raise EnvironmentFailure("the EULA is not accepted in the runtime image")
    if task["build"]["tool"] != "javac" and starter_dir() is None:
        raise EnvironmentFailure("the starter mirror is missing (tests/starter)")
    if not any(TESTS.rglob("*.java")):
        raise EnvironmentFailure("no grader suite sources under /tests")
    for tool in ("java", "javac", "jar", "rsync"):
        if shutil.which(tool) is None:
            raise EnvironmentFailure(f"{tool} is unavailable")
    build = task["build"]
    if build["tool"] in {"gradle", "maven"} and not build.get("wrapper", True):
        binary = "gradle" if build["tool"] == "gradle" else "mvn"
        if shutil.which(binary) is None:
            raise EnvironmentFailure(f"{binary} is unavailable and the repository has no wrapper")


def sync_submission(task: dict[str, Any]) -> None:
    problems = validate_shape(SUBMISSION, [])
    if problems:
        raise SubmissionFailure("submission shape checks failed:\n- " + "\n- ".join(problems[:20]))
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    completed = run(
        [
            "rsync",
            "-a",
            "--no-owner",
            "--no-group",
            "--delete",
            "--exclude=build/",
            "--exclude=target/",
            "--exclude=.gradle/",
            "--exclude=out/",
            f"{SUBMISSION}/",
            f"{WORKSPACE}/",
        ],
        cwd=WORKSPACE,
        timeout=300,
    )
    if completed.returncode != 0:
        raise EnvironmentFailure("could not copy the submission into the workspace")
    frozen = task["build"].get("frozenPaths") or []
    if task["build"]["tool"] != "javac":
        starter = starter_dir()
        if starter is None:
            raise EnvironmentFailure("the starter mirror is missing (tests/starter)")
        restored = restore_frozen_paths(WORKSPACE, starter, list(frozen))
        log(f"frozen paths restored from the starter: {', '.join(restored) or 'none'}")
    if task.get("hiddenUnitOverlay"):
        overlay = TESTS / "unit"
        target = WORKSPACE / "src" / "test"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(overlay, target)
        log("hidden unit tests overlaid onto src/test")


def build_command(task: dict[str, Any], phase: str) -> list[str]:
    build = task["build"]
    tool = build["tool"]
    module = build.get("module")
    if tool == "gradle":
        prefix = f"{module}:" if module else ""
        tasks = build["assemble"] if phase == "assemble" else build["test"]
        wrapper = "./gradlew" if build.get("wrapper", True) else "gradle"
        command = [wrapper, "--offline", "--no-daemon", "--console=plain", "-q", "--stacktrace"]
        if phase == "test":
            command.append("--continue")
        command.extend(f"{prefix}{part}" for part in str(tasks).split())
        return command
    if tool == "maven":
        goals = build["assemble"] if phase == "assemble" else build["test"]
        wrapper = "./mvnw" if build.get("wrapper", True) else "mvn"
        command = [wrapper, "-o", "-B", "-q", "-Dmaven.repo.local=/opt/m2"]
        if module:
            command.extend(["-pl", module, "-am"])
        if phase == "assemble":
            command.append("-DskipTests")
        else:
            command.append("-Dmaven.test.failure.ignore=true")
        command.extend(str(goals).split())
        return command
    raise EnvironmentFailure(f"unsupported build tool: {tool}")


def build_submission(task: dict[str, Any]) -> Path:
    build = task["build"]
    artifact = WORKSPACE / build["artifact"]
    if build["tool"] == "javac":
        completed = run(
            ["bash", str(HOME / "javac-build.sh"), str(WORKSPACE), str(artifact)],
            cwd=WORKSPACE,
            timeout=BUILD_TIMEOUT,
            log_name="build-submission.log",
        )
    else:
        wrapper = WORKSPACE / ("gradlew" if build["tool"] == "gradle" else "mvnw")
        if build.get("wrapper", True):
            wrapper.chmod(0o755)
        completed = run(
            build_command(task, "assemble"),
            cwd=WORKSPACE,
            timeout=BUILD_TIMEOUT,
            log_name="build-submission.log",
        )
    if completed.returncode != 0:
        raise SubmissionFailure(f"offline build failed with exit status {completed.returncode}")
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise SubmissionFailure(f"build produced no artifact at {build['artifact']}")
    listing = run(["unzip", "-p", str(artifact), "plugin.yml"], cwd=WORKSPACE, timeout=60)
    name = plugin_yml_name(listing.stdout) if listing.returncode == 0 else None
    if name is None:
        listing = run(["unzip", "-p", str(artifact), "paper-plugin.yml"], cwd=WORKSPACE, timeout=60)
        name = plugin_yml_name(listing.stdout) if listing.returncode == 0 else None
    if name != task["pluginName"]:
        raise SubmissionFailure(
            f"the built jar declares plugin name {name!r}, expected {task['pluginName']!r}"
        )
    log(f"offline build passed: {build['artifact']}")
    return artifact


def run_unit_tests(task: dict[str, Any]) -> dict[str, Any]:
    expected = list(task["unitCases"])
    if not expected:
        return {"status": "skipped", "cases": []}
    # Reports may live in a sub-module (Gradle spigot/build, Maven <module>/target).
    for pattern in ("**/build/test-results/**/*.xml", "**/target/surefire-reports/*.xml"):
        for stale in WORKSPACE.glob(pattern):
            stale.unlink()
    completed = run(build_command(task, "test"), cwd=WORKSPACE, timeout=TEST_TIMEOUT, log_name="unit.log")
    reports = [
        *WORKSPACE.glob("**/build/test-results/**/*.xml"),
        *WORKSPACE.glob("**/target/surefire-reports/TEST-*.xml"),
    ]
    observed, duplicates = parse_junit_reports(reports)
    observed = [case for case in observed if case["name"] in set(expected)]
    problem = check_case_set(observed, expected)
    # A duplicated identity inside the frozen set is ambiguous and fails closed;
    # repeated or parameterised tests outside it are simply unobserved (they are
    # never frozen, exactly like skipped tests).
    duplicates = [name for name in duplicates if name in set(expected)]
    if duplicates:
        problem = problem or ("duplicated unit cases: " + ", ".join(duplicates[:5]))
    if problem:
        log(f"unit tests incomplete: {problem} (test command exit {completed.returncode})")
        return {"status": "incomplete", "cases": observed, "problem": problem}
    passed = all(case["passed"] for case in observed)
    log(
        f"unit tests {'passed' if passed else 'failed'}: {sum(c['passed'] for c in observed)}/{len(expected)}"
    )
    return {
        "status": "passed" if passed else "failed",
        "cases": sorted(observed, key=lambda c: expected.index(c["name"])),
    }


def build_grader(task: dict[str, Any], candidate_jar: Path) -> Path:
    work = LOGS.parent / "grader"
    if work.exists():
        shutil.rmtree(work)
    sources = work / "src"
    classes = work / "classes"
    sources.mkdir(parents=True)
    classes.mkdir()
    suite_files = sorted(
        path for path in TESTS.rglob("*.java") if "unit" not in path.relative_to(TESTS).parts[:1]
    )
    # Keep each suite's relative path: a public Java class must live in a file
    # named after it, and suites may be split across package directories.
    for path in suite_files:
        target = sources / path.relative_to(TESTS)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    main = sources / "GraderPlugin.java"
    main.write_text(GRADER_MAIN, encoding="utf-8")
    classpath = (HOME / "classpath.colon").read_text(encoding="utf-8").strip()
    classpath = f"{classpath}:{HOME / 'harness' / 'gcb-harness.jar'}:{candidate_jar}"
    completed = run(
        [
            "javac",
            "--release",
            "21",
            "-proc:none",
            "-Xlint:none",
            "-encoding",
            "UTF-8",
            "-cp",
            classpath,
            "-d",
            str(classes),
            *[str(path) for path in sorted(sources.rglob("*.java"))],
        ],
        cwd=work,
        timeout=300,
        log_name="grader-compile.log",
    )
    if completed.returncode != 0:
        raise SubmissionFailure("the grader suite does not compile against the submission")
    (classes / "plugin.yml").write_text(grader_plugin_yml(task["pluginName"]), encoding="utf-8")
    jar = work / "gcb-grader.jar"
    completed = run(["jar", "--create", "--file", str(jar), "-C", str(classes), "."], cwd=work, timeout=120)
    if completed.returncode != 0 or not jar.is_file():
        raise EnvironmentFailure("could not package the grader plugin")
    return jar


def seed_plugin_data(seed: Path, plugins: Path) -> list[str]:
    """Copy tests/seed/<PluginName>/... into the server's plugins/ directory.

    A task whose symptom depends on configuration that must already exist when
    the candidate plugin enables (start-up behaviour) ships that data folder
    under tests/seed. Only data files are accepted: a jar under the seed would be
    an extra plugin and makes the environment invalid.
    """
    if not seed.is_dir():
        return []
    for candidate in seed.rglob("*"):
        if candidate.is_symlink():
            raise EnvironmentFailure(f"tests/seed contains a symbolic link: {candidate.relative_to(seed)}")
        if candidate.is_file() and candidate.suffix.lower() in FORBIDDEN_SUFFIXES:
            relative = candidate.relative_to(seed)
            raise EnvironmentFailure(f"tests/seed contains a compiled artifact: {relative}")
    shutil.copytree(seed, plugins, dirs_exist_ok=True)
    return sorted(path.name for path in seed.iterdir() if path.is_dir())


def run_server(task: dict[str, Any], candidate_jar: Path, grader_jar: Path) -> dict[str, Any]:
    plugins = PAPER / "plugins"
    for stale in plugins.glob("*.jar"):
        stale.unlink()
    seeded = seed_plugin_data(TESTS / "seed", plugins)
    if seeded:
        log(f"plugin data seeded from tests/seed: {', '.join(seeded)}")
    shutil.copyfile(candidate_jar, plugins / "candidate.jar")
    shutil.copyfile(HOME / "harness" / "gcb-harness.jar", plugins / "gcb-harness.jar")
    shutil.copyfile(grader_jar, plugins / "gcb-grader.jar")
    nonce = secrets.token_hex(16)
    command = [
        "java",
        "-Xms1G",
        "-Xmx2G",
        "-XX:+UseG1GC",
        "-Dgcb.mode=run-suite",
        f"-Dgcb.nonce={nonce}",
        f"-Dgcb.candidate={task['pluginName']}",
        "-Dterminal.jline=false",
        "-Dterminal.ansi=false",
        "-Dnet.kyori.ansi.colorLevel=none",
        "-jar",
        SERVER_JAR,
        "--nogui",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=PAPER,
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
    if len(payloads) != 1:
        return {
            "status": "incomplete",
            "serverExit": exit_status,
            "payloadCount": len(payloads),
            "cases": [],
            "problem": f"expected exactly one harness payload, saw {len(payloads)}",
        }
    try:
        envelope = json.loads(payloads[0])
    except json.JSONDecodeError:
        return {
            "status": "incomplete",
            "serverExit": exit_status,
            "payloadCount": 1,
            "cases": [],
            "problem": "harness payload is not valid JSON",
        }
    if not isinstance(envelope, dict) or envelope.get("nonce") != nonce:
        return {
            "status": "incomplete",
            "serverExit": exit_status,
            "payloadCount": 1,
            "cases": [],
            "problem": "harness payload nonce mismatch",
        }
    if envelope.get("fatal"):
        return {
            "status": "incomplete",
            "serverExit": exit_status,
            "payloadCount": 1,
            "cases": [],
            "problem": f"harness fatal: {envelope['fatal']}",
        }
    raw_cases = envelope.get("cases")
    cases = []
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
                        "ticks": item.get("ticks"),
                    }
                )
    problem = check_case_set(cases, list(task["serverCases"]))
    if problem:
        return {
            "status": "incomplete",
            "serverExit": exit_status,
            "payloadCount": 1,
            "cases": cases,
            "problem": problem,
        }
    passed = all(case["passed"] for case in cases)
    log(f"live server {'passed' if passed else 'failed'}: {sum(c['passed'] for c in cases)}/{len(cases)}")
    return {
        "status": "passed" if passed else "failed",
        "serverExit": exit_status,
        "payloadCount": 1,
        "cases": cases,
    }


def write_result(result: dict[str, Any]) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (LOGS / "reward.txt").write_text(f"{result['reward']}\n", encoding="utf-8")


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "taskId": None,
        "pluginName": None,
        "build": {"status": "not-run"},
        "unit": {"status": "not-run", "cases": []},
        "live": {"status": "not-run", "cases": []},
        "complete": False,
        "passed": False,
        "reward": 0,
    }
    try:
        task = load_task()
        result["taskId"], result["pluginName"] = task["taskId"], task["pluginName"]
        result["build"] = {
            "status": "not-run",
            "tool": task["build"]["tool"],
            "artifact": task["build"]["artifact"],
        }
        validate_environment(task)
        try:
            sync_submission(task)
            candidate_jar = build_submission(task)
        except SubmissionFailure as error:
            result["build"]["status"] = "failed"
            result["build"]["problem"] = str(error)
            log(f"SUBMISSION_FAILED: {error}")
            write_result(result)
            return 1
        result["build"]["status"] = "passed"
        result["unit"] = run_unit_tests(task)
        try:
            grader_jar = build_grader(task, candidate_jar)
        except SubmissionFailure as error:
            result["live"] = {"status": "grader-compile-failed", "cases": [], "problem": str(error)}
            log(f"SUBMISSION_FAILED: {error}")
            write_result(result)
            return 1
        result["live"] = run_server(task, candidate_jar, grader_jar)
        unit_observed = result["unit"]["status"] in {"passed", "failed", "skipped"}
        live_observed = result["live"]["status"] in {"passed", "failed"}
        result["complete"] = bool(unit_observed and live_observed)
        result["passed"] = bool(
            result["complete"]
            and result["unit"]["status"] in {"passed", "skipped"}
            and result["live"]["status"] == "passed"
        )
        result["reward"] = 1 if result["passed"] else 0
        write_result(result)
        if not result["complete"]:
            log("SUBMISSION_FAILED: verification did not complete with the frozen case sets")
            return 1
        if not result["passed"]:
            log("SUBMISSION_FAILED: one or more cases failed")
            return 1
        log("VERIFICATION_PASSED: build, unit tests and real-server cases all passed")
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
