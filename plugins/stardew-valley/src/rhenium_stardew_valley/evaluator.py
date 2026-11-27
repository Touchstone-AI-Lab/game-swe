from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import StardewCatalog, StardewTask, expected_case_count

# Evaluator images restore and build the starter tree while the image is built, and trial
# builds run offline with --no-restore. Syncing a submission must therefore keep the image's
# obj/ restore state and must not let a submission supply its own obj/ or bin/ output.
BUILD_CONTEXT_LABEL = "io.rhenium.runtime.build-context"
SUBMISSION_SYNC_OPTIONS = (
    "-a",
    "--no-owner",
    "--no-group",
    "--delete",
    "--exclude=obj/",
    "--exclude=bin/",
)

# Bound for Docker control-plane calls (daemon probe, image inspection, container
# create/cp/rm). A shared, busy host can take well over a minute to answer them, and a
# premature timeout turns an otherwise complete evaluation into an incomplete one.
_DOCKER_TIMEOUT = 300


class StardewRuntime:
    """Docker-backed Stardew runtime with proprietary files supplied by the operator."""

    def __init__(self, context: BenchmarkContext, catalog: StardewCatalog):
        self.context = context
        self.catalog = catalog
        self.docker = shutil.which("docker") or ""
        self.image_prefix = "rhenium-stardew"

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

    def image_tag(self, task: StardewTask) -> str:
        return f"{self.image_prefix}:{task.id}-{self.catalog.version}"

    def build_context_digest(self, task: StardewTask) -> str:
        """Identity of the task's build inputs (starter, harness, fixtures, Dockerfile)."""
        root = self.context.pack_root / "private" / "harbor" / task.id / "environment"
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        return f"sha256:{digest.hexdigest()}"

    def image_exists(self, task: StardewTask) -> bool:
        """Whether a tagged image exists AND was built from the current build inputs.

        The tag alone is not an identity: a harness or starter change leaves the old
        image under the same tag, and reusing it would evaluate with stale content.
        """
        try:
            result = self._docker(
                [
                    "image", "inspect", self.image_tag(task), "--format",
                    f'{{{{index .Config.Labels "{BUILD_CONTEXT_LABEL}"}}}}',
                ],
                timeout=_DOCKER_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0 and result.stdout.strip() == self.build_context_digest(task)

    def image_id(self, task: StardewTask) -> str:
        result = self._docker(
            ["image", "inspect", self.image_tag(task), "--format", "{{.Id}}"],
            timeout=_DOCKER_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError("Stardew evaluator image is unavailable")
        return result.stdout.strip()

    def status(self) -> dict[str, Any]:
        if not self.docker:
            return {
                "id": "stardew-docker",
                "available": False,
                "reason": "Docker CLI is not installed",
                "gameVersion": "1.6.15",
                "smapiVersion": "4.1.10",
            }
        try:
            info = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            return {
                "id": "stardew-docker",
                "available": False,
                "reason": f"Docker daemon probe failed: {error}",
                "gameVersion": "1.6.15",
                "smapiVersion": "4.1.10",
            }
        if info.returncode != 0:
            return {
                "id": "stardew-docker",
                "available": False,
                "reason": "Docker daemon is unavailable",
                "gameVersion": "1.6.15",
                "smapiVersion": "4.1.10",
            }
        return {
            "id": "stardew-docker",
            "available": True,
            "reason": None,
            "dockerVersion": info.stdout.strip(),
            "gameVersion": "1.6.15",
            "smapiVersion": "4.1.10",
            "network": "none",
            "imagesRequired": len(self.catalog.tasks),
        }

    def ensure_image(self, task: StardewTask, *, game_dir: Path) -> tuple[str, str]:
        tag = self.image_tag(task)
        if self.image_exists(task):
            return tag, "using prebuilt evaluator image\n"
        if not (game_dir / "Stardew Valley.dll").is_file() or not (game_dir / "Content").is_dir():
            raise RuntimeError(
                "managed Steam source does not contain the pinned Stardew Linux game build"
            )
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        task_root = self.context.pack_root / "private" / "harbor" / task.id
        environment = task_root / "environment"
        with tempfile.TemporaryDirectory(
            prefix="stardew-build-", dir=self.context.cache_dir
        ) as raw_context:
            build_context = Path(raw_context)
            shutil.copytree(environment, build_context, dirs_exist_ok=True)
            shutil.copytree(game_dir, build_context / "game-files")
            result = self._docker(
                [
                    "build",
                    "--pull=false",
                    "--label",
                    f"{BUILD_CONTEXT_LABEL}={self.build_context_digest(task)}",
                    "--tag",
                    tag,
                    "--file",
                    str(build_context / "Dockerfile"),
                    str(build_context),
                ],
                timeout=7200,
            )
        log = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(f"failed to build Stardew evaluator image\n{log[-8000:]}")
        return tag, log

    def run(
        self,
        task: StardewTask,
        submission: Path,
        logs: Path,
        image_id: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        image_id = image_id or self.image_id(task)
        task_root = self.context.pack_root / "private" / "harbor" / task.id
        tests = (task_root / "tests").resolve()
        starter = task.starter_name
        destination = task.container_destination
        command = (
            "set -euo pipefail; "
            f"rsync {' '.join(SUBMISSION_SYNC_OPTIONS)} /submission/{starter}/ {destination}/; "
            "bash /tests/test.sh"
        )
        arguments = [
            "create",
            "--network=none",
            "--cpus=6",
            "--memory=16g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={submission},target=/submission,readonly",
            "--mount",
            f"type=bind,source={tests},target=/tests,readonly",
            "--pull=never",
            image_id,
            "bash",
            "-lc",
            command,
        ]
        timeout = 3000 if task.difficulty == "hard" else 2100
        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode != 0 or not re.fullmatch(r"[0-9a-f]{64}", container_id):
            raise RuntimeError("could not create the isolated Stardew evaluator container")
        try:
            result = self._docker(["start", "--attach", container_id], timeout=timeout)
            logs.mkdir(parents=True, exist_ok=True)
            copied = self._docker(["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT)
            if copied.returncode:
                raise RuntimeError("could not collect Stardew evaluator reports")
            verifier_logs = logs / "verifier"
            if verifier_logs.is_symlink() or (verifier_logs / "smapi.log").is_symlink():
                raise RuntimeError("Stardew evaluator report destination contains a symbolic link")
            verifier_logs.mkdir(exist_ok=True)
            for source_log in (
                "/opt/gcb/user-config/StardewValley/ErrorLogs/SMAPI-latest.txt",
                "/root/.config/StardewValley/ErrorLogs/SMAPI-latest.txt",
            ):
                captured = self._docker(
                    ["cp", f"{container_id}:{source_log}", str(verifier_logs / "smapi.log")],
                    timeout=_DOCKER_TIMEOUT,
                )
                if captured.returncode == 0:
                    break
            return result, f"image={image_id}\nnetwork=none\n"
        finally:
            # Only the container ID returned by our own create request is removed.
            removed = self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)
            if removed.returncode:
                raise RuntimeError("could not remove the owned Stardew evaluator container")


class StardewEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: StardewCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = StardewRuntime(context, catalog)

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(submission: Path, task: StardewTask) -> tuple[bool, dict[str, Any]]:
        starter = submission / task.starter_name
        safe = starter.is_dir() and not starter.is_symlink()
        if safe:
            safe = not any(path.is_symlink() for path in submission.rglob("*"))
        if safe:
            safe = all(
                (submission / relative).is_file()
                and not (submission / relative).is_symlink()
                for relative in task.required_files
            )
        return safe, {
            "id": "submission-shape",
            "status": "passed" if safe else "failed",
            "score": 10.0 if safe else 0.0,
            "maximum": 10.0,
            "message": (
                "submission contains the required real source tree"
                if safe
                else "submission is missing required source files or contains symbolic links"
            ),
        }

    @staticmethod
    def _read_runtime_log(logs: Path, process: subprocess.CompletedProcess[str]) -> str:
        sections = [process.stdout, process.stderr]
        root = logs.resolve()
        # Generated suites may choose different log names. Preserve their bounded
        # diagnostics before the temporary run disappears, without following links.
        for path in sorted((logs / "verifier").glob("*.log"))[:32]:
            if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root):
                with path.open("rb") as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 32_000))
                    content = stream.read(32_000).decode("utf-8", errors="replace")
                sections.append(f"\n== {path.relative_to(logs)} ==\n{content}")
        return "".join(sections)[-200_000:]

    def evaluate(
        self,
        submission: Path,
        task: StardewTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full", "macos"}:
            raise ValueError(f"unsupported Stardew Valley evaluation profile: {profile}")
        if not isinstance(task, StardewTask):
            raise TypeError("Stardew evaluator received a non-Stardew task")
        static_ok, static_check = self._static_check(submission, task)
        if profile == "macos":
            from .native import NATIVE_ID, evaluate_native

            if not static_ok:
                return {"score": 0.0, "complete": False, "passed": False,
                        "checks": [static_check], "runtime": {"status": "incomplete"},
                        "runtime_log": "invalid native submission shape\n"}
            return evaluate_native(self.context, task, submission,
                                   (runtimes or {}).get(f"stardew-valley/{NATIVE_ID}"))
        checks: list[dict[str, Any]] = [static_check]
        if profile == "core" or not static_ok:
            checks.append(
                {
                    "id": "headless-game",
                    "status": "skipped" if static_ok else "failed",
                    "score": 0.0,
                    "maximum": 90.0,
                    "message": (
                        "headless game assertions are disabled in the core profile"
                        if static_ok
                        else "headless game assertions were not run for an invalid submission"
                    ),
                }
            )
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": checks,
                "runtime": {"status": "skipped"},
                "runtime_log": "Stardew headless runtime did not run\n",
            }

        status = self.runtime.status()
        if not bool(status.get("available", False)):
            checks.append(
                {
                    "id": "headless-game",
                    "status": "failed",
                    "score": 0.0,
                    "maximum": 90.0,
                    "message": "pinned Stardew headless runtime is unavailable",
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
            "stardew-1.6.15-smapi-4.1.10-synth"
            if task.clean_room_synthetic
            else "stardew-1.6.15-smapi-4.1.10"
        )
        artifact = (runtimes or {}).get(f"stardew-valley/{runtime_id}")
        images = artifact.metadata.get("images", {}) if artifact is not None else {}
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        if not image_id:
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": [
                    *checks,
                    {
                        "id": "headless-game",
                        "status": "failed",
                        "score": 0.0,
                        "maximum": 90.0,
                        "message": "managed Stardew runtime is not prepared",
                    },
                ],
                "runtime": {"status": "unavailable"},
                "runtime_log": f"run rhenium runtime prepare stardew-valley/{runtime_id}\n",
            }

        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        runtime_log = ""
        passed_count: int | None = None
        failed_count: int | None = None
        case_outcomes: dict[str, bool] = {}
        try:
            with tempfile.TemporaryDirectory(
                prefix="stardew-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.runtime.run(task, submission, logs, image_id)
                runtime_log = identity_log + self._read_runtime_log(logs, process)
                result_path = logs / "verifier" / "result.json"
                reward_path = logs / "verifier" / "reward.txt"
                verdict = (
                    json.loads(result_path.read_text(encoding="utf-8"))
                    if result_path.is_file() and not result_path.is_symlink()
                    and result_path.resolve().is_relative_to(logs.resolve())
                    else {}
                )
                expected = expected_case_count(self.context.pack_root, task)
                cases = verdict.get("cases") if isinstance(verdict, dict) else None
                passed_value = verdict.get("passed") if isinstance(verdict, dict) else None
                failed_value = verdict.get("failed") if isinstance(verdict, dict) else None
                passed_count = passed_value if type(passed_value) is int else None
                failed_count = failed_value if type(failed_value) is int else None
                if isinstance(cases, list) and all(
                    isinstance(case, dict) and isinstance(case.get("Name"), str)
                    and bool(case["Name"]) and type(case.get("Passed")) is bool
                    for case in cases
                ):
                    case_outcomes = {case["Name"]: case["Passed"] for case in cases}
                complete = bool(
                    isinstance(cases, list)
                    and len(cases) == expected
                    and len(case_outcomes) == expected
                    and passed_count is not None
                    and failed_count is not None
                    and passed_count + failed_count == expected
                    and passed_count == sum(case_outcomes.values())
                    and verdict.get("fatal") is None
                )
                reward = (
                    reward_path.read_text(encoding="utf-8").strip()
                    if reward_path.is_file() and not reward_path.is_symlink()
                    and reward_path.resolve().is_relative_to(logs.resolve())
                    else "0"
                )
                passed = bool(
                    complete
                    and process.returncode == 0
                    and passed_count == expected
                    and failed_count == 0
                    and reward == "1"
                )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, TypeError) as error:
            runtime_log += f"runtime error: {error}\n"
            complete = False
            passed = False

        checks.append(
            {
                "id": "headless-game",
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "score": 90.0 if passed else 0.0,
                "maximum": 90.0,
                "message": (
                    "all real-game assertions passed"
                    if passed
                    else "real-game assertions failed"
                    if complete
                    else "real-game assertions did not complete"
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
                "passedAssertions": passed_count or 0,
                "failedAssertions": failed_count or 0,
                "caseOutcomes": case_outcomes,
            },
            "runtime_log": runtime_log,
        }
