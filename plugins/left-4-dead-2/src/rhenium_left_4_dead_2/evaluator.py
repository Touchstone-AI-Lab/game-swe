from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import Left4Dead2Catalog, Left4Dead2Task

RUNTIME_ID = "l4d2-23990100-sourcemod-1.12.7246"
RUNTIME_KEY = f"left-4-dead-2/{RUNTIME_ID}"
RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-context"
BASE_TASK_LABEL = "shared-base"
_CASE_LINE = re.compile(r"^(PASS|FAIL) (.*?):", re.MULTILINE)
_FORBIDDEN_SUFFIXES = {".dll", ".dylib", ".exe", ".smx", ".so", ".vpk", ".zip"}
# Container bookkeeping is instant on an idle daemon but can stall for minutes while a
# shared host flushes image layers; a stall must not turn into an incomplete verdict.
_DOCKER_TIMEOUT = 300


def expected_case_names(pack_root: Path, task: Left4Dead2Task) -> tuple[str, ...]:
    path = pack_root / "private" / "harbor" / task.id / "validation" / "case-contracts.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return tuple(row["case"] for row in rows)


class Left4Dead2Runtime:
    """Docker-backed pinned L4D2 dedicated-server verifier."""

    def __init__(self, context: BenchmarkContext, catalog: Left4Dead2Catalog):
        self.context = context
        self.catalog = catalog
        self.docker = shutil.which("docker") or ""

    def _docker(
        self, arguments: list[str], *, timeout: float
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

    def image_id(self, reference: str) -> str:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{.Id}}"], timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError("Left 4 Dead 2 evaluator image is unavailable")
        return result.stdout.strip()

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"],
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError("Left 4 Dead 2 evaluator image is unavailable")
        try:
            labels = json.loads(result.stdout or "null")
        except json.JSONDecodeError as error:
            raise RuntimeError("Left 4 Dead 2 evaluator image has invalid labels") from error
        if labels is None:
            return {}
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise RuntimeError("Left 4 Dead 2 evaluator image has invalid labels")
        return labels

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "left-4-dead-2-docker",
            "runtime": RUNTIME_ID,
            "gameAppId": 222860,
            "gameBuild": "23990100",
            "sourceMod": "1.12.0.7246",
            "network": "none",
        }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            info = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            return {
                **base,
                "available": False,
                "reason": f"Docker daemon probe failed: {error}",
            }
        if info.returncode != 0:
            return {**base, "available": False, "reason": "Docker daemon is unavailable"}
        return {
            **base,
            "available": True,
            "reason": None,
            "dockerVersion": info.stdout.strip(),
            "imagesRequired": len(self.catalog.tasks),
        }

    def run(
        self,
        task: Left4Dead2Task,
        submission: Path,
        logs: Path,
        image_id: str,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        if re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
            raise RuntimeError("Left 4 Dead 2 evaluation requires an immutable image ID")
        source = (submission / task.starter_name).resolve()
        arguments = [
            "create",
            "--pull=never",
            "--user=0:0",
            "--platform=linux/amd64",
            "--network=none",
            "--cpus=4",
            "--memory=12g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--cap-add=CHOWN",
            "--cap-add=DAC_OVERRIDE",
            "--cap-add=FOWNER",
            "--cap-add=FSETID",
            "--cap-add=KILL",
            "--cap-add=SETGID",
            "--cap-add=SETUID",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={source},target={task.container_destination},readonly",
            image_id,
            "bash",
            "-c",
            "set -euo pipefail; install -d -m 0700 /logs /logs/verifier; exec bash /tests/test.sh",
        ]
        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            raise RuntimeError("could not create the isolated Left 4 Dead 2 verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=2700)
            logs.mkdir(parents=True, exist_ok=True)
            copied = self._docker(["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT)
            if copied.returncode:
                raise RuntimeError("could not collect Left 4 Dead 2 verification reports")
            return process, f"image={image_id}\nnetwork=none\n"
        finally:
            removed = self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)
            if removed.returncode:
                raise RuntimeError("could not remove the owned Left 4 Dead 2 verifier")


class Left4Dead2Evaluator:
    def __init__(self, context: BenchmarkContext, catalog: Left4Dead2Catalog):
        self.context = context
        self.catalog = catalog
        self.runtime = Left4Dead2Runtime(context, catalog)

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(
        submission: Path, task: Left4Dead2Task
    ) -> tuple[bool, dict[str, Any]]:
        starter = submission / task.starter_name
        safe = starter.is_dir() and not starter.is_symlink()
        if safe:
            safe = not any(path.is_symlink() for path in starter.rglob("*"))
        if safe:
            safe = all(
                (submission / relative).is_file()
                and not (submission / relative).is_symlink()
                for relative in task.required_files
            )
        if safe:
            safe = not any(
                path.name == ".git" or (path.is_file() and path.suffix.lower() in _FORBIDDEN_SUFFIXES)
                for path in starter.rglob("*")
            )
        return safe, {
            "id": "submission-shape",
            "status": "passed" if safe else "failed",
            "score": 10.0 if safe else 0.0,
            "maximum": 10.0,
            "message": (
                "submission contains the required source-only project tree"
                if safe
                else "submission is missing required source or contains forbidden files"
            ),
        }

    @staticmethod
    def _read_report(path: Path, logs: Path, *, limit: int = 2_000_000, tail: bool = False) -> str:
        if path.is_symlink() or not path.resolve().is_relative_to(logs.resolve()):
            raise ValueError("unsafe Left 4 Dead 2 verification report path")
        if not path.exists():
            return ""
        if not path.is_file() or (not tail and path.stat().st_size > limit):
            raise ValueError("invalid or oversized Left 4 Dead 2 verification report")
        with path.open("rb") as stream:
            if tail:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - limit))
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("oversized Left 4 Dead 2 verification report")
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _read_runtime_log(
        logs: Path, process: subprocess.CompletedProcess[str]
    ) -> str:
        sections = [process.stdout, process.stderr]
        verifier = logs / "verifier" / "verifier.log"
        # Keep engine diagnostics before the temporary logs directory disappears.
        # They do not supply case verdicts and may be safely tail-bounded.
        for server_log in sorted((logs / "verifier").glob("server*.log"))[:20]:
            sections.append(
                f"\n== verifier/{server_log.name} ==\n"
                + Left4Dead2Evaluator._read_report(server_log, logs, limit=16_000, tail=True)
            )
        sections.append("\n== verifier/verifier.log ==\n" + Left4Dead2Evaluator._read_report(verifier, logs))
        return "".join(sections)[-250_000:]

    def evaluate(
        self,
        submission: Path,
        task: Left4Dead2Task,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Left 4 Dead 2 evaluation profile: {profile}")
        if not isinstance(task, Left4Dead2Task):
            raise TypeError("Left 4 Dead 2 evaluator received a non-L4D2 task")
        static_ok, static_check = self._static_check(submission, task)
        checks: list[dict[str, Any]] = [static_check]

        def incomplete(message: str, log: str, status: str) -> dict[str, Any]:
            checks.append(
                {
                    "id": "headless-server",
                    "status": "skipped" if status == "skipped" else "failed",
                    "score": 0.0,
                    "maximum": 90.0,
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
                "headless server assertions are disabled in the core profile"
                if static_ok
                else "headless server assertions were not run for an invalid submission",
                "Left 4 Dead 2 headless runtime did not run\n",
                "skipped" if static_ok else "failed",
            )

        status = self.runtime.status()
        if not bool(status.get("available", False)):
            return incomplete(
                "pinned Left 4 Dead 2 headless runtime is unavailable",
                str(status.get("reason") or "runtime unavailable") + "\n",
                "unavailable",
            )
        artifact = (runtimes or {}).get(RUNTIME_KEY)
        images = artifact.metadata.get("images", {}) if artifact is not None else {}
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        if not image_id:
            return incomplete(
                "managed Left 4 Dead 2 runtime is not prepared",
                f"run rhenium runtime prepare {RUNTIME_KEY}\n",
                "unavailable",
            )

        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        runtime_log = ""
        complete = False
        passed = False
        passed_count = 0
        case_outcomes: dict[str, bool] = {}
        try:
            with tempfile.TemporaryDirectory(
                prefix="left-4-dead-2-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.runtime.run(task, submission, logs, image_id)
                runtime_log = identity_log + self._read_runtime_log(logs, process)
                verifier = logs / "verifier" / "verifier.log"
                reward_path = logs / "verifier" / "reward.txt"
                verifier_text = self._read_report(verifier, logs)
                observed = _CASE_LINE.findall(verifier_text)
                expected = expected_case_names(self.context.pack_root, task)
                observed_names = [name for _status, name in observed]
                reward = self._read_report(reward_path, logs, limit=16).strip()
                complete = bool(
                    process.returncode == 0
                    and reward in {"0", "1"}
                    and len(observed_names) == len(expected)
                    and len(observed_names) == len(set(observed_names))
                    and set(observed_names) == set(expected)
                    and "INVALID_ENVIRONMENT:" not in verifier_text
                )
                passed_count = sum(status == "PASS" for status, _name in observed)
                passed = bool(
                    complete and passed_count == len(expected) and reward == "1"
                )
                if complete:
                    case_outcomes = {name: status == "PASS" for status, name in observed}
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            runtime_log += f"runtime error: {error}\n"

        checks.append(
            {
                "id": "headless-server",
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "score": 90.0 if passed else 0.0,
                "maximum": 90.0,
                "message": (
                    f"all {task.expected_cases} real-server assertions passed"
                    if passed
                    else f"{passed_count}/{task.expected_cases} real-server assertions passed"
                    if complete
                    else "real-server assertions did not complete with the frozen case set"
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
                "passedAssertions": passed_count,
                "failedAssertions": len(case_outcomes) - passed_count if complete else 0,
                "caseOutcomes": case_outcomes,
            },
            "runtime_log": runtime_log,
        }
