from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

RUNTIME_ID = "dst-dedicated-24700372"
RUNTIME_KEY = f"dst/{RUNTIME_ID}"
# The construct pack is built from the same pinned base as the repair pack but
# needs its own runtime key: the Hub keeps one binding per key.
CONSTRUCT_RUNTIME_ID = "dst-dedicated-24700372-construct"
CONSTRUCT_RUNTIME_KEY = f"dst/{CONSTRUCT_RUNTIME_ID}"
DST_APP_ID = 343050
DST_BUILD_ID = "24700372"
RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-context"
BASE_TASK_LABEL = "shared-base"
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_REPORT_LIMIT = 8_000_000
# Probing the daemon, inspecting an image, and creating, copying out of or
# removing an 8 GB verifier container can take minutes on a congested Docker
# host; a timeout here makes the runtime unavailable or the run incomplete.
_DOCKER_TIMEOUT = 300


class DstContainerRuntime:
    """Docker-backed pinned Don't Starve Together dedicated-server verifier."""

    def __init__(self) -> None:
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
            ["image", "inspect", reference, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError("DST evaluator image is unavailable")
        return result.stdout.strip()

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"],
            timeout=_DOCKER_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError("DST evaluator image is unavailable")
        try:
            labels = json.loads(result.stdout or "null")
        except json.JSONDecodeError as error:
            raise RuntimeError("DST evaluator image has invalid labels") from error
        if labels is None:
            return {}
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in labels.items()
        ):
            raise RuntimeError("DST evaluator image has invalid labels")
        return labels

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "dst-docker",
            "runtime": RUNTIME_ID,
            "gameAppId": DST_APP_ID,
            "gameBuild": DST_BUILD_ID,
            "network": "none",
        }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            info = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            return {**base, "available": False, "reason": f"Docker daemon probe failed: {error}"}
        if info.returncode != 0:
            return {**base, "available": False, "reason": "Docker daemon is unavailable"}
        return {**base, "available": True, "reason": None, "dockerVersion": info.stdout.strip()}

    def run(
        self, mod_root: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        """Evaluate ``mod_root`` (the submission's mod tree) inside ``image_id``."""
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError("DST evaluation requires an immutable image ID")
        arguments = [
            "create",
            "--pull=never",
            "--user=0:0",
            "--platform=linux/amd64",
            "--network=none",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={mod_root.resolve()},target=/app/mod,readonly",
            image_id,
            "bash",
            "-c",
            "set -euo pipefail; install -d -m 0700 /logs /logs/verifier; exec bash /tests/test.sh",
        ]
        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            raise RuntimeError("could not create the isolated DST verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=1200)
            logs.mkdir(parents=True, exist_ok=True)
            copied = self._docker(
                ["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT
            )
            if copied.returncode:
                raise RuntimeError("could not collect DST verification reports")
            return process, f"image={image_id}\nnetwork=none\n"
        finally:
            removed = self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)
            if removed.returncode:
                raise RuntimeError("could not remove the owned DST verifier")


def read_report(path: Path, logs: Path, *, limit: int = _REPORT_LIMIT) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(logs.resolve()):
        raise ValueError("unsafe DST verification report path")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing, invalid or oversized DST verification report")
    return path.read_text(encoding="utf-8", errors="replace")


def read_container_evaluation(logs: Path) -> dict[str, Any]:
    """Return the in-container evaluator result, or raise when it is not trustworthy.

    The verifier writes the Harbor reward and the full evaluator result. They
    must agree: reward 1 exactly when the result is complete and passed.
    """
    verifier = logs / "verifier"
    reward = read_report(verifier / "reward.txt", logs, limit=16).strip()
    if reward not in {"0", "1"}:
        raise ValueError("DST verifier reward is malformed")
    try:
        result = json.loads(read_report(verifier / "evaluation.json", logs))
    except json.JSONDecodeError as error:
        raise ValueError("DST verifier evaluation report is not valid JSON") from error
    if not isinstance(result, dict):
        raise ValueError("DST verifier evaluation report has an invalid shape")
    complete, passed = result.get("complete"), result.get("passed")
    checks, score = result.get("checks"), result.get("score")
    if not isinstance(complete, bool) or not isinstance(passed, bool) or not isinstance(checks, list):
        raise ValueError("DST verifier evaluation report has an invalid shape")
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise ValueError("DST verifier evaluation report has an invalid score")
    if passed and not complete:
        raise ValueError("DST verifier evaluation report is inconsistent")
    if (reward == "1") != (complete and passed):
        raise ValueError("DST verifier reward does not match its evaluation report")
    return result
