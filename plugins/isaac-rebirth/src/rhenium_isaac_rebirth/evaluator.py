from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import VERIFIER_PARTS, IsaacCatalog, IsaacTask, expected_case_names, verifier_root

VERIFIER_IMAGE = "gcb-isaac-exodus-verifier:abp-v1.06.t1"
DEFAULT_APPARMOR_PROFILE = "gcb-isaac-steam"
# Container bookkeeping is instant on an idle daemon but can stall for minutes while a
# shared host flushes image layers; a stall must not turn into an incomplete verdict.
_DOCKER_TIMEOUT = 300
# The verifier image is built from this task's tests/, so its run-game.sh is the one baked in.
IMAGE_SOURCE_TASK = "isaac-exodus-release-regressions"
# Upper bound for one three-process verifier container. The harness enforces its own
# per-phase budgets; this only reaps a container that outlives all of them.
_RUN_TIMEOUT = 7200
# Harness lines that explain an infrastructure outcome. Steam's own output in the same
# log is never copied into a result.
_HARNESS_MARKER = re.compile(r"^GCB_(?:RUNTIME_INVALID|RUNTIME_NOTE|ISAAC_STARTED|SUITE_FINISHED)\b.*$")
# test.sh's closing status line of a complete run. The Exodus verifier runs three game
# processes whose suites each report a summary and a runtime sentinel case; a construct
# verifier runs one process with one suite and no sentinel.
_EXODUS_STATUS = re.compile(r"runtime_exit=0 secret_exit=0 james_exit=0 main_exit=0 ")
_CONSTRUCT_STATUS = re.compile(
    r"^runtime_exit=0 passed=\d+ failed=\d+ expected=\d+ summaries=\d+ fatals=\d+ "
    r"case_occurrences_ok=[01] cases=",
    re.MULTILINE,
)
_SENTINELS = frozenset({"runtime_sentinel_main", "runtime_sentinel_secret", "runtime_sentinel_james"})


class IsaacRuntime:
    """Docker-backed native Afterbirth+ runtime prepared on a licensed Linux host."""

    def __init__(self, context: BenchmarkContext):
        self.context = context
        self.docker = shutil.which("docker") or ""
        self.apparmor_profile = DEFAULT_APPARMOR_PROFILE

    def _docker(
        self,
        arguments: list[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise RuntimeError("Docker CLI is not installed")
        return subprocess.run(
            [self.docker, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def image_id(self) -> str:
        result = self._docker(
            ["image", "inspect", VERIFIER_IMAGE, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError("pinned Isaac verifier image is unavailable")
        return result.stdout.strip()

    def status(self, *, probe_image: bool = True) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "isaac-native-docker",
            "image": VERIFIER_IMAGE,
            "gameVersion": "Afterbirth+ v1.06.T1",
            "gameBuild": "Steam App 250900 build 22878971",
            "network": "none",
            "apparmorProfile": self.apparmor_profile,
        }
        if sys.platform != "linux":
            return {
                **base,
                "available": False,
                "reason": "the pinned Isaac runtime requires a licensed Linux host",
            }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            info = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
            if info.returncode != 0:
                return {**base, "available": False, "reason": "Docker daemon is unavailable"}
            image_id = self.image_id() if probe_image else None
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            return {**base, "available": False, "reason": str(error)}
        return {
            **base,
            "available": True,
            "reason": None,
            "dockerVersion": info.stdout.strip(),
            "imageId": image_id,
        }

    def run(
        self,
        submission: Path,
        logs: Path,
        image_id: str | None = None,
        starter_name: str = "exodus",
        harness: Path | None = None,
        verifier: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        image_id = image_id or self.image_id()
        exodus = (submission / starter_name).resolve()
        logs = logs.resolve()
        logs.mkdir(parents=True, exist_ok=True)
        name = f"rhenium-isaac-{uuid.uuid4().hex[:12]}"
        # A task that ships its own launch script replaces only /tests/run-game.sh of the
        # shared image; the suites and test.sh stay the image's unless the task also names
        # a shared verifier, whose test.sh and suites then replace the image's.
        harness_mount = (
            ["--mount", f"type=bind,src={harness.resolve()},dst=/tests/run-game.sh,readonly"]
            if harness is not None
            else []
        )
        verifier_mounts: list[str] = []
        if verifier is not None:
            for part in VERIFIER_PARTS:
                source = (verifier / part).resolve()
                verifier_mounts += ["--mount", f"type=bind,src={source},dst=/tests/{part},readonly"]
        arguments = [
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            name,
            "--network",
            "none",
            "--cpus",
            "4",
            "--memory",
            "8g",
            "--shm-size",
            "1g",
            "--security-opt",
            f"apparmor={self.apparmor_profile}",
            "--security-opt",
            "seccomp=unconfined",
            "-e",
            "GTK_A11Y=none",
            "--mount",
            f"type=bind,src={exodus},dst=/app/exodus,readonly",
            "--mount",
            f"type=bind,src={logs},dst=/logs",
            *harness_mount,
            *verifier_mounts,
            image_id,
            "bash",
            "/tests/test.sh",
        ]
        try:
            process = self._docker(arguments, timeout=_RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            with suppress(OSError, subprocess.SubprocessError):
                self._docker(["rm", "--force", name], timeout=_DOCKER_TIMEOUT)
            raise
        with suppress(OSError, subprocess.SubprocessError):
            self._docker(
                [
                    "run",
                    "--rm",
                    "--pull",
                    "never",
                    "--network",
                    "none",
                    "--mount",
                    f"type=bind,src={logs},dst=/logs",
                    image_id,
                    "chown",
                    "-R",
                    f"{getattr(os, 'getuid', lambda: 0)()}:{getattr(os, 'getgid', lambda: 0)()}",
                    "/logs",
                ],
                timeout=_DOCKER_TIMEOUT,
            )
        return process, image_id


class IsaacEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: IsaacCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = IsaacRuntime(context)

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(submission: Path, task: IsaacTask) -> tuple[bool, dict[str, Any]]:
        root = submission.resolve()
        safe = root.is_dir()
        if safe:
            try:
                safe = not any(path.is_symlink() for path in root.rglob("*"))
            except OSError:
                safe = False
        for relative in task.required_files:
            candidate = (root / relative).resolve()
            safe = safe and candidate.is_relative_to(root) and candidate.is_file()
        return safe, {
            "id": "submission-shape",
            "status": "passed" if safe else "failed",
            "score": 10.0 if safe else 0.0,
            "maximum": 10.0,
            "message": (
                "submission contains the required Lua mod tree"
                if safe and task.clean_room_synthetic
                else "submission contains the required Exodus source tree"
                if safe
                else "submission is missing required files or contains symbolic links"
            ),
        }

    def _runtime_evidence(
        self,
        logs: Path,
        process: subprocess.CompletedProcess[str],
        task: IsaacTask,
    ) -> tuple[bool, bool, int, int, str]:
        game_log = logs / "verifier" / "game.log"
        reward_path = logs / "verifier" / "reward.txt"
        text = game_log.read_text(encoding="utf-8", errors="replace") if game_log.is_file() else ""
        events = re.findall(r"\[GCB_CASE\] (PASS|FAIL) ([a-z0-9_]+)(?: |$)", text)
        expected = expected_case_names(self.context.pack_root, task)
        counts = Counter(name for _, name in events)
        passed = sum(status == "PASS" for status, _ in events)
        failed = sum(status == "FAIL" for status, _ in events)
        summaries = len(re.findall(r"\[GCB_SUMMARY\]", text))
        fatals = len(re.findall(r"\[GCB_FATAL\]", text))
        sentinels = {name: status for status, name in events if name in _SENTINELS}
        if task.clean_room_synthetic:
            processes, status = 1, _CONSTRUCT_STATUS
        else:
            processes, status = 3, _EXODUS_STATUS
        exits = status.search(process.stdout + process.stderr)
        reward = reward_path.read_text(encoding="utf-8").strip() if reward_path.is_file() else ""
        complete = bool(
            process.returncode == 0
            and exits is not None
            and len(events) == task.expected_cases
            and set(counts) == set(expected)
            and all(counts[name] == 1 for name in expected)
            and summaries == processes
            and fatals == 0
            and all(sentinels.get(name) == "PASS" for name in sentinels)
            and len(sentinels) == (0 if task.clean_room_synthetic else 3)
            and reward in {"0", "1"}
        )
        success = bool(complete and passed == task.expected_cases and failed == 0 and reward == "1")
        evidence = (
            f"processes={f'{processes}/{processes}' if exits is not None else 'incomplete'} "
            f"assertions={passed + failed}/{task.expected_cases} passed={passed} failed={failed} "
            f"summaries={summaries}/{processes} fatals={fatals}"
        )
        return complete, success, passed, failed, evidence

    @staticmethod
    def _case_report(logs: Path) -> tuple[dict[str, bool], str]:
        """Name-level outcomes and the verifier marker lines of one finished run.

        Reporting only. The caller uses the outcomes solely for a run that
        `_runtime_evidence` already accepted as complete, where every expected
        case appears exactly once.
        """
        game_log = logs / "verifier" / "game.log"
        text = game_log.read_text(encoding="utf-8", errors="replace") if game_log.is_file() else ""
        outcomes = {
            name: status == "PASS"
            for status, name in re.findall(r"\[GCB_CASE\] (PASS|FAIL) ([a-z0-9_]+)(?: |$)", text)
        }
        markers = [line for line in text.splitlines() if "[GCB_" in line]
        return outcomes, "\n".join(markers)[-60_000:]

    @staticmethod
    def _harness_report(logs: Path, process: subprocess.CompletedProcess[str]) -> str:
        """The launch harness's own marker lines and test.sh's closing status line.

        Reporting only: they say which game process failed to start or finish and why.
        """
        runtime_log = logs / "verifier" / "runtime.log"
        text = runtime_log.read_text(encoding="utf-8", errors="replace") if runtime_log.is_file() else ""
        lines = [line for line in text.splitlines() if _HARNESS_MARKER.match(line)]
        lines += [
            line
            for line in (process.stdout or "").splitlines()
            if line.startswith(("runtime_exit=", "INVALID_ARTIFACT"))
        ]
        return "\n".join(lines)[-8_000:]

    def harness(self, task: IsaacTask) -> Path | None:
        """The launch script a derived Exodus task ships next to its copy of test.sh."""
        if task.clean_room_synthetic or task.id == IMAGE_SOURCE_TASK:
            return None
        candidate = self.context.pack_root / "private" / "harbor" / task.id / "tests" / "run-game.sh"
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.context.pack_root.resolve()) or not resolved.is_file():
            return None
        return resolved

    def verifier(self, task: IsaacTask) -> Path | None:
        """The shared verifier whose test.sh and suites replace the image's for this task."""
        if task.clean_room_synthetic or task.id == IMAGE_SOURCE_TASK:
            return None
        return verifier_root(self.context.pack_root, task)

    @staticmethod
    def _verifier_digest(verifier: Path | None) -> str:
        if verifier is None:
            return "image"
        digest = hashlib.sha256()
        for part in VERIFIER_PARTS:
            root = verifier / part
            for path in sorted([root] if root.is_file() else root.rglob("*")):
                if path.is_file():
                    digest.update(path.relative_to(verifier).as_posix().encode("utf-8") + b"\0")
                    digest.update(path.read_bytes() + b"\0")
        return digest.hexdigest()[:16]

    def evaluate(
        self,
        submission: Path,
        task: IsaacTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Isaac evaluation profile: {profile}")
        if not isinstance(task, IsaacTask):
            raise TypeError("Isaac evaluator received a non-Isaac task")
        static_ok, static_check = self._static_check(submission, task)
        checks: list[dict[str, Any]] = [static_check]
        if profile == "core" or not static_ok:
            checks.append(
                {
                    "id": "native-game",
                    "status": "skipped" if static_ok else "failed",
                    "score": 0.0,
                    "maximum": 90.0,
                    "message": (
                        "native game assertions are disabled in the core profile"
                        if static_ok
                        else "native game assertions were not run for an invalid submission"
                    ),
                }
            )
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": checks,
                "runtime": {"status": "skipped"},
                "runtime_log": "Isaac native runtime did not run\n",
            }

        status = self.runtime.status(probe_image=False)
        if not bool(status.get("available", False)):
            checks.append(
                {
                    "id": "native-game",
                    "status": "failed",
                    "score": 0.0,
                    "maximum": 90.0,
                    "message": "pinned Isaac native runtime is unavailable",
                }
            )
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": checks,
                "runtime": {"status": "unavailable"},
                "runtime_log": str(status.get("reason") or "runtime unavailable") + "\n",
            }

        runtime_id = (
            "afterbirth-plus-1.06.t1-synth"
            if task.clean_room_synthetic
            else "afterbirth-plus-1.06.t1"
        )
        artifact = (runtimes or {}).get(f"isaac-rebirth/{runtime_id}")
        if artifact is None:
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": [
                    *checks,
                    {
                        "id": "native-game",
                        "status": "failed",
                        "score": 0.0,
                        "maximum": 90.0,
                        "message": "managed Isaac runtime is not prepared",
                    },
                ],
                "runtime": {"status": "unavailable"},
                "runtime_log": f"run rhenium runtime prepare isaac-rebirth/{runtime_id}\n",
            }

        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        evidence = "runtime did not produce complete evidence"
        harness = self.harness(task)
        harness_digest = (
            hashlib.sha256(harness.read_bytes()).hexdigest()[:16] if harness is not None else "image"
        )
        verifier = self.verifier(task)
        verifier_digest = self._verifier_digest(verifier)
        images = artifact.metadata.get("images")
        image_id = (
            str(images.get(task.id) or "")
            if isinstance(images, dict)
            else artifact.identity
        )
        if not image_id:
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": [
                    *checks,
                    {
                        "id": "native-game",
                        "status": "failed",
                        "score": 0.0,
                        "maximum": 90.0,
                        "message": "managed Isaac runtime has no image for this task",
                    },
                ],
                "runtime": {"status": "unavailable"},
                "runtime_log": "prepared Isaac runtime is incomplete\n",
            }
        try:
            with tempfile.TemporaryDirectory(
                prefix="isaac-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                process, image_id = self.runtime.run(
                    submission, logs, image_id, task.starter_name, harness, verifier
                )
                complete, passed, passed_count, failed_count, evidence = self._runtime_evidence(
                    logs, process, task
                )
                case_outcomes, marker_log = self._case_report(logs)
                harness_log = self._harness_report(logs, process)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, TypeError) as error:
            complete = False
            passed = False
            passed_count = 0
            failed_count = 0
            evidence = f"runtime error: {error}"
            case_outcomes, marker_log, harness_log = {}, "", ""

        checks.append(
            {
                "id": "native-game",
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "score": 90.0 if passed else 0.0,
                "maximum": 90.0,
                "message": (
                    f"all {task.expected_cases} real-game assertions passed"
                    if passed
                    else f"real-game assertions completed with {failed_count} failures"
                    if complete
                    else "all required real-game assertions did not complete"
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
                "imageId": image_id,
                "passedAssertions": passed_count,
                "failedAssertions": failed_count,
                "caseOutcomes": case_outcomes if complete else {},
            },
            "runtime_log": (
                f"image={image_id} harness={harness_digest} verifier={verifier_digest} "
                f"{evidence}\n{harness_log}\n{marker_log}\n"
            ),
        }
