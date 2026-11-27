from __future__ import annotations

import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import SlayTheSpireCatalog, SlayTheSpireTask, expected_assertion_count
from .container import RUNTIME_KEY, SlayTheSpireRuntime
from .native import NATIVE_RUNTIME_KEY, NativeDocker, run_native_verifier

W_SHAPE = 10.0
W_SUITE = 90.0

# The private verifier's own summary line, produced from Surefire's output.
_SUMMARY = re.compile(
    r"entrypoint_exit=(?P<exit>-?\d+)\s+Tests run: (?P<run>\d+), "
    r"Failures: (?P<failures>\d+), Errors: (?P<errors>\d+), Skipped: (?P<skipped>\d+)"
)
_FORBIDDEN_SUFFIXES = frozenset({".class", ".jar", ".zip"})
_BUILD_DIRECTORIES = frozenset({"target", "out", "build"})
# The Maven wrapper's bootstrap jar is part of an upstream tree, not a build output.
_WRAPPER_JARS = frozenset({".mvn/wrapper/maven-wrapper.jar"})
_MAX_SUBMISSION_FILES = 20_000
_MAX_REPORT_BYTES = 4 * 1024 * 1024


def parse_surefire_reports(directory: Path) -> list[dict[str, Any]] | None:
    """Per-case outcomes from Surefire's XML reports, or ``None`` when unusable.

    A case is named ``<class>.<method>``. Any unreadable or oversized report, a
    skipped case, or a duplicate name makes the whole set unusable: the caller
    then reports no case names rather than a partial list.
    """
    if not directory.is_dir():
        return None
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for report in sorted(directory.glob("TEST-*.xml")):
        if report.is_symlink() or not report.is_file() or report.stat().st_size > _MAX_REPORT_BYTES:
            return None
        try:
            root = ElementTree.parse(report).getroot()
        except (ElementTree.ParseError, OSError):
            return None
        for testcase in root.iter("testcase"):
            method = str(testcase.get("name") or "").removesuffix("()")
            owner = str(testcase.get("classname") or "")
            if not method or not owner or testcase.find("skipped") is not None:
                return None
            name = f"{owner}.{method}"
            if name in seen:
                return None
            seen.add(name)
            problem = testcase.find("failure")
            if problem is None:
                problem = testcase.find("error")
            message = "ok" if problem is None else str(problem.get("message") or problem.tag)
            cases.append({"name": name, "passed": problem is None, "message": message[:500]})
    return cases or None


class SlayTheSpireEvaluator:
    """Evaluates admitted real-game tasks; loader checks remain internal diagnostics."""

    def __init__(self, context: BenchmarkContext, catalog: SlayTheSpireCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = SlayTheSpireRuntime(context, catalog)
        self.native = NativeDocker()

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(submission: Path, task: SlayTheSpireTask) -> tuple[bool, dict[str, Any]]:
        problems: list[str] = []
        starter = submission / task.starter_name
        if not starter.is_dir() or starter.is_symlink():
            problems.append(f"{task.starter_name}: the submission must contain this source tree")
        else:
            seen = 0
            for candidate in submission.rglob("*"):
                relative = candidate.relative_to(submission)
                if candidate.is_symlink():
                    problems.append(f"{relative}: symbolic links are not allowed")
                    continue
                if not candidate.is_file():
                    continue
                seen += 1
                parts = relative.parts
                inside_build_output = any(part in _BUILD_DIRECTORIES for part in parts[:-1])
                below_starter = "/".join(parts[1:])
                if ".git" in parts:
                    problems.append(f"{relative}: version-control metadata is not allowed")
                elif (
                    candidate.suffix.lower() in _FORBIDDEN_SUFFIXES
                    and not inside_build_output
                    and below_starter not in _WRAPPER_JARS
                ):
                    problems.append(f"{relative}: compiled artifacts outside build output")
            if seen > _MAX_SUBMISSION_FILES:
                problems.append("submission holds more files than the upstream tree")
            for required in task.required_files:
                if not (submission / required).is_file():
                    problems.append(f"{required}: required file is missing")
        ok = not problems
        return ok, {
            "id": "submission-shape",
            "status": "passed" if ok else "failed",
            "score": W_SHAPE if ok else 0.0,
            "maximum": W_SHAPE,
            "message": (
                "submission contains the required ModTheSpire source tree" if ok else "; ".join(problems[:5])
            ),
        }

    @staticmethod
    def _read_runtime_log(logs: Path, process: subprocess.CompletedProcess[str]) -> str:
        sections = [(process.stdout + process.stderr)[-4000:]]
        for name in ("summary.txt", "maven.log"):
            candidate = logs / "verifier" / name
            if candidate.is_file():
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                sections.append(f"== {name} ==\n{text[-12000:]}")
        return "\n".join(section for section in sections if section.strip()) + "\n"

    def evaluate(
        self,
        submission: Path,
        task: SlayTheSpireTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Slay the Spire evaluation profile: {profile}")
        if not isinstance(task, SlayTheSpireTask):
            raise TypeError("Slay the Spire evaluator received a non-Slay-the-Spire task")
        if not task.game_backed:
            _, shape = self._static_check(submission, task)
            return {
                "score": float(shape["score"]),
                "complete": False,
                "passed": False,
                "checks": [shape, {
                    "id": "native-engine",
                    "status": "incomplete",
                    "score": 0.0,
                    "maximum": W_SUITE,
                    "message": "this task has no real-game verifier; loader-only results cannot pass",
                }],
                "runtime": {"status": "incomplete"},
                "runtime_log": "real-game verification is unavailable for this task\n",
            }
        return self._evaluate_native(submission, task, profile, runtimes)

    def _evaluate_loader_diagnostic(
        self,
        submission: Path,
        task: SlayTheSpireTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        """Legacy verifier diagnostics; only evaluate() admits a benchmark result."""
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Slay the Spire evaluation profile: {profile}")
        if not isinstance(task, SlayTheSpireTask):
            raise TypeError("Slay the Spire evaluator received a non-Slay-the-Spire task")
        static_ok, static_check = self._static_check(submission, task)
        checks: list[dict[str, Any]] = [static_check]

        def incomplete(message: str, log: str, status: str) -> dict[str, Any]:
            checks.append(
                {
                    "id": "private-suite",
                    "status": "skipped" if status == "skipped" else "failed",
                    "score": 0.0,
                    "maximum": W_SUITE,
                    "message": message,
                }
            )
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": checks,
                "runtime": {"status": status},
                "runtime_log": log,
            }

        if profile == "core" or not static_ok:
            return incomplete(
                "the private JUnit suite is disabled in the core profile"
                if static_ok
                else "the private JUnit suite was not run for an invalid submission",
                "the ModTheSpire verifier did not run\n",
                "skipped" if static_ok else "failed",
            )

        status = self.runtime.status()
        if not bool(status.get("available", False)):
            return incomplete(
                "the pinned JDK 8 Maven evaluator runtime is unavailable",
                str(status.get("reason") or "runtime unavailable") + "\n",
                "unavailable",
            )

        artifact = (runtimes or {}).get(RUNTIME_KEY)
        images = artifact.metadata.get("images", {}) if artifact is not None else {}
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        if not image_id:
            return incomplete(
                "the managed Slay the Spire runtime is not prepared",
                f"run rhenium runtime prepare {RUNTIME_KEY}\n",
                "unavailable",
            )

        expected = task.expected_assertions or expected_assertion_count(self.context.pack_root, task)
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        runtime_log = ""
        complete = False
        passed = False
        observed = failures = errors = 0
        cases: list[dict[str, Any]] = []
        try:
            with tempfile.TemporaryDirectory(
                prefix="slay-the-spire-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.runtime.run(task, submission, logs, image_id)
                runtime_log = identity_log + self._read_runtime_log(logs, process)
                summary_path = logs / "verifier" / "summary.txt"
                reward_path = logs / "verifier" / "reward.txt"
                summary = (
                    summary_path.read_text(encoding="utf-8", errors="replace")
                    if summary_path.is_file()
                    else ""
                )
                match = _SUMMARY.search(summary)
                reward = reward_path.read_text(encoding="utf-8").strip() if reward_path.is_file() else "0"
                if match is not None:
                    observed = int(match.group("run"))
                    failures = int(match.group("failures"))
                    errors = int(match.group("errors"))
                    skipped = int(match.group("skipped"))
                    entrypoint_exit = int(match.group("exit"))
                    # Every declared assertion must have been observed exactly once for
                    # the result to count; a build failure produces no summary at all.
                    complete = bool(
                        process.returncode == 0
                        and observed == expected
                        and skipped == 0
                        and failures + errors <= expected
                    )
                    passed = bool(
                        complete and failures == 0 and errors == 0 and entrypoint_exit == 0 and reward == "1"
                    )
                parsed = parse_surefire_reports(logs / "verifier" / "surefire") if complete else None
                # Case names are reported only when they account for exactly the
                # counted outcomes; they never change the verdict.
                if (
                    parsed is not None
                    and len(parsed) == observed
                    and sum(not case["passed"] for case in parsed) == failures + errors
                ):
                    cases = parsed
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            runtime_log += f"runtime error: {error}\n"
            complete = False
            passed = False

        checks.append(
            {
                "id": "private-suite",
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "score": W_SUITE if passed else 0.0,
                "maximum": W_SUITE,
                "message": (
                    f"all {expected} private assertions passed"
                    if passed
                    else f"{max(observed - failures - errors, 0)}/{expected} private assertions passed"
                    if complete
                    else "the private JUnit suite did not complete"
                ),
                **({"details": {"cases": cases}} if cases else {}),
            }
        )
        return {
            "score": 100.0 if passed else float(static_check["score"]),
            "complete": complete,
            "passed": passed,
            "checks": checks,
            "runtime": {
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "expectedAssertions": expected,
                "passedAssertions": max(observed - failures - errors, 0) if complete else 0,
                "failedAssertions": failures + errors if complete else 0,
                "caseOutcomes": {case["name"]: case["passed"] for case in cases},
            },
            "runtime_log": runtime_log,
        }

    def _evaluate_native(
        self,
        submission: Path,
        task: SlayTheSpireTask,
        profile: str,
        runtimes: dict[str, RuntimeArtifact] | None,
    ) -> dict[str, Any]:
        """Runs the task's own verifier in the licensed game, from the Steam-built native runtime."""
        static_ok, static_check = self._static_check(submission, task)
        checks: list[dict[str, Any]] = [static_check]

        def incomplete(message: str, log: str, status: str) -> dict[str, Any]:
            checks.append(
                {
                    "id": "native-engine",
                    "status": "skipped" if status == "skipped" else "failed",
                    "score": 0.0,
                    "maximum": W_SUITE,
                    "message": message,
                }
            )
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": checks,
                "runtime": {"status": status},
                "runtime_log": log,
            }

        if profile == "core" or not static_ok:
            return incomplete(
                "the native game verifier is disabled in the core profile"
                if static_ok
                else "the native game verifier was not run for an invalid submission",
                "the native Slay the Spire verifier did not run\n",
                "skipped" if static_ok else "failed",
            )
        artifact = (runtimes or {}).get(NATIVE_RUNTIME_KEY)
        tasks = artifact.metadata.get("tasks", {}) if artifact is not None else {}
        entry = tasks.get(task.id) if isinstance(tasks, dict) else None
        if not isinstance(entry, dict):
            return incomplete(
                "the native Slay the Spire runtime is not prepared",
                "log in with rhenium auth login steam, then run rhenium runtime prepare "
                f"{NATIVE_RUNTIME_KEY}\n",
                "unavailable",
            )

        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        runtime_log = ""
        result: dict[str, Any] = {}
        build_exit = None
        verifier_exit = None
        try:
            with tempfile.TemporaryDirectory(
                prefix="slay-the-spire-native-", dir=self.context.cache_dir
            ) as raw_run:
                process, verifier = run_native_verifier(
                    self.native, self.context.pack_root, task, entry, submission, Path(raw_run)
                )
                verifier_exit = process.returncode
                runtime_log = (process.stdout + process.stderr)[-4000:]
                for name in ("summary.txt", "build.log", "engine.log"):
                    candidate = verifier / name
                    if candidate.is_file():
                        text = candidate.read_text(encoding="utf-8", errors="replace")
                        runtime_log += f"\n== {name} ==\n{text[-6000:]}"
                result_path = verifier / "result.json"
                if result_path.is_file():
                    loaded = json.loads(result_path.read_text(encoding="utf-8"))
                    result = loaded if isinstance(loaded, dict) else {}
                build_path = verifier / "build-exit.txt"
                if build_path.is_file():
                    build_exit = int(build_path.read_text(encoding="utf-8").strip() or "-1")
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            runtime_log += f"runtime error: {error}\n"

        raw_cases = result.get("cases")
        cases: list[Any] = raw_cases if isinstance(raw_cases, list) else []
        expected_value = result.get("expected")
        passed_value = result.get("passed")
        failed_value = result.get("failed")
        counts_valid = all(type(value) is int and value >= 0 for value in (
            expected_value, passed_value, failed_value
        ))
        expected = expected_value if type(expected_value) is int and expected_value > 0 else 0
        observed_passed = passed_value if type(passed_value) is int and passed_value >= 0 else 0
        observed_failed = failed_value if type(failed_value) is int and failed_value >= 0 else 0
        case_records_valid = all(
            isinstance(case, dict)
            and isinstance(case.get("id"), str)
            and bool(case["id"])
            and type(case.get("passed")) is bool
            for case in cases
        )
        unique_cases = {case["id"] for case in cases} if case_records_valid else set()
        # A reward alone is not enough: the build must succeed and every declared case
        # must have been observed under this run's nonce (the verifier's "complete").
        complete = bool(
            result.get("complete") is True
            and verifier_exit == 0
            and build_exit == 0
            and counts_valid
            and expected > 0
            and len(cases) == expected
            and case_records_valid
            and len(unique_cases) == expected
            and sum(case["passed"] for case in cases) == observed_passed
            and observed_passed + observed_failed == expected
        )
        passed = bool(complete and observed_passed == expected and result.get("reward") == 1)
        checks.append(
            {
                "id": "native-engine",
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "score": W_SUITE if passed else 0.0,
                "maximum": W_SUITE,
                "message": (
                    f"all {expected} native engine cases passed"
                    if passed
                    else f"{observed_passed}/{expected} native engine cases passed"
                    if complete
                    else "the native game verifier did not complete"
                ),
            }
        )
        return {
            "score": 100.0 if passed else float(static_check["score"]),
            "complete": complete,
            "passed": passed,
            "checks": checks,
            "runtime": {
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "expectedCases": expected,
                "passedCases": observed_passed if complete else 0,
                "failedCases": expected - observed_passed if complete else 0,
                "caseOutcomes": {
                    str(case.get("id")): bool(case.get("passed")) for case in cases if isinstance(case, dict)
                }
                if complete
                else {},
            },
            "runtime_log": runtime_log,
        }
