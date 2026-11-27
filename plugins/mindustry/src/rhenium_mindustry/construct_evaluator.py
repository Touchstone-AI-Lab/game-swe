"""Evaluator of the restored construct pack (``rhenium-mindustry-v1``).

It compiles a from-scratch server plugin inside the task's evaluator image and
runs the task's private headless verifier. The repair evaluator lives in
:mod:`.evaluator`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .construct_catalog import MindustryConstructCatalog, MindustryConstructTask, expected_case_names

RUNTIME_ID = "mindustry"
RUNTIME_KEY = "mindustry/mindustry"
# The pinned dedicated-server build the runtime catalog acquires.
GAME_VERSION = "159.7"
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN_SUFFIXES = {".class", ".jar", ".zip"}
# The Docker daemon may be shared and congested; container bookkeeping gets room.
_DOCKER_TIMEOUT = 300


class MindustryConstructRuntime:
    def __init__(self, context: BenchmarkContext, catalog: MindustryConstructCatalog):
        self.context = context
        self.catalog = catalog
        self.docker = shutil.which("docker") or ""

    def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise RuntimeError("Docker CLI is not installed")
        return subprocess.run(
            [self.docker, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def status(self) -> dict[str, Any]:
        base = {
            "id": "mindustry-docker",
            "runtime": RUNTIME_ID,
            "gameVersion": GAME_VERSION,
            "network": "none",
        }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            result = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            return {**base, "available": False, "reason": str(error)}
        if result.returncode != 0:
            return {**base, "available": False, "reason": "Docker daemon is unavailable"}
        return {
            **base,
            "available": True,
            "reason": None,
            "dockerVersion": result.stdout.strip(),
            "imagesRequired": len(self.catalog.tasks),
        }

    def run(
        self,
        task: MindustryConstructTask,
        submission: Path,
        logs: Path,
        image_id: str,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError("Mindustry evaluation requires an immutable image ID")

        task_root = self.context.pack_root / "private" / "harbor" / task.id
        tests = (task_root / "tests").resolve()
        submission = submission.resolve()
        logs = logs.resolve()
        logs.mkdir(parents=True, exist_ok=True)

        arguments = [
            "create",
            "--pull=never",
            "--network=none",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={submission},target=/solution,readonly",
            "--mount",
            f"type=bind,source={tests},target=/tests,readonly",
            image_id,
            "bash",
            "-c",
            # Reports are written inside the container and copied out afterwards: a bound host
            # directory is unwritable once every capability, DAC_OVERRIDE included, is dropped.
            # The submission is the workspace overlay the task contract describes: the files
            # named by required_files, on top of the starter the image already carries.
            "set -euo pipefail; install -d -m 0755 /logs /logs/verifier; "
            "cp -R /solution/. /workspace/mindustry/; "
            "exec bash /tests/test.sh",
        ]
        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            raise RuntimeError("could not create the isolated Mindustry verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=900)
            copied = self._docker(["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT)
            if copied.returncode != 0:
                raise RuntimeError("could not collect the Mindustry verifier reports")
            if any(path.is_symlink() for path in logs.rglob("*")):
                raise RuntimeError("Mindustry verifier reports contain a symbolic link")
            return process, f"image={image_id}\nnetwork=none\n"
        finally:
            with suppress(OSError, subprocess.SubprocessError):
                self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)


class MindustryConstructEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: MindustryConstructCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = MindustryConstructRuntime(context, catalog)

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(submission: Path, task: MindustryConstructTask) -> tuple[bool, dict[str, Any]]:
        safe = submission.is_dir() and not submission.is_symlink()
        if safe:
            safe = not any(path.is_symlink() for path in submission.rglob("*"))
        if safe:
            safe = all((submission / relative).is_file() for relative in task.required_files)
        if safe:
            safe = not any(
                path.name == ".git"
                or (path.is_file() and path.suffix.lower() in _FORBIDDEN_SUFFIXES)
                for path in submission.rglob("*")
                if path.relative_to(submission).parts[:1] != ("build",)
            )
        return safe, {
            "id": "submission-shape",
            "status": "passed" if safe else "failed",
            "score": 10.0 if safe else 0.0,
            "maximum": 10.0,
            "message": (
                "submission contains the required source-only files"
                if safe
                else "submission is missing required source or contains forbidden files"
            ),
        }

    @staticmethod
    def _runtime_artifact(
        task: MindustryConstructTask,
        runtimes: dict[str, RuntimeArtifact] | None,
    ) -> RuntimeArtifact:
        if not runtimes or RUNTIME_KEY not in runtimes:
            raise RuntimeError("prepared Mindustry runtime is required")
        artifact = runtimes[RUNTIME_KEY]
        images = artifact.metadata.get("images")
        if not isinstance(images, dict) or task.id not in images:
            raise RuntimeError(f"prepared Mindustry runtime is missing task image: {task.id}")
        return artifact

    def evaluate(
        self,
        submission: Path,
        task: MindustryConstructTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Mindustry evaluation profile: {profile}")

        static_ok, static_check = self._static_check(submission, task)
        expected = expected_case_names(self.context.pack_root, task)
        criteria_maximum = 1 + len(expected)
        if profile == "core" or not static_ok:
            return {
                "taskId": task.id,
                "profile": profile,
                "score": static_check["score"],
                "maximum": static_check["maximum"],
                "complete": False,
                "passed": False,
                "checks": [static_check],
                "criteriaScore": 1 if static_ok else 0,
                "criteriaMaximum": criteria_maximum,
            }

        artifact = self._runtime_artifact(task, runtimes)
        image_id = str(artifact.metadata["images"][task.id])
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError("prepared Mindustry image identity is invalid")

        with tempfile.TemporaryDirectory(prefix="rhenium-mindustry-") as temp:
            logs = Path(temp) / "logs"
            process, runtime_log = self.runtime.run(task, submission, logs, image_id)
            reward_path = logs / "verifier" / "reward.txt"
            verifier_log = logs / "verifier" / "verifier.log"

            reward = reward_path.read_text(encoding="utf-8").strip() if reward_path.is_file() else ""
            output = (process.stdout or "") + (process.stderr or "")
            if verifier_log.is_file():
                output += "\n" + verifier_log.read_text(encoding="utf-8", errors="replace")

            passed_names = {
                match.group(1)
                for match in re.finditer(r'"name"\s*:\s*"([^"]+)"\s*,\s*"passed"\s*:\s*true', output)
            }
            failed_names = {
                match.group(1)
                for match in re.finditer(r'"name"\s*:\s*"([^"]+)"\s*,\s*"passed"\s*:\s*false', output)
            }
            observed = passed_names | failed_names
            complete = observed == set(expected)
            runtime_passed = (
                process.returncode == 0
                and reward == "1"
                and complete
                and not failed_names
            )

            runtime_check = {
                "id": "private-headless-verifier",
                "status": "passed" if runtime_passed else "failed",
                "score": 90.0 if runtime_passed else 0.0,
                "maximum": 90.0,
                "message": (
                    f"all {len(expected)} private Mindustry cases passed"
                    if runtime_passed
                    else "private Mindustry verifier did not pass completely"
                ),
            }
            return {
                "taskId": task.id,
                "profile": profile,
                "score": static_check["score"] + runtime_check["score"],
                "maximum": 100.0,
                "complete": complete,
                "passed": static_ok and runtime_passed,
                "checks": [static_check, runtime_check],
                "runtime": runtime_log,
                "criteriaScore": 1 + len(passed_names) if complete else 1,
                "criteriaMaximum": criteria_maximum,
            }
