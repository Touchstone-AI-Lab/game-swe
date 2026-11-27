"""Docker-backed pinned Mindustry dedicated-server verifier.

The verifier images carry the pinned ``server-release.jar``, the trusted Rhenium
harness and one task's frozen grader suite. They are built locally from the
operator-provided jar and are never published.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

MINDUSTRY_VERSION = "159.7"
RELEASE_TAG = f"v{MINDUSTRY_VERSION}"
RUNTIME_ID = f"mindustry-{MINDUSTRY_VERSION}"
SERVER_JAR = "server-release.jar"
BASE_TAG = f"rhenium-mindustry-verifier:{MINDUSTRY_VERSION}"
BASE_IMAGE_REFERENCE = (
    "eclipse-temurin:17-jdk@sha256:bc033b57e11b773c3043babfd664e7a5ef110805548b921cbfc3e8c67a0725d6"
)
RESULT_MARKER = "MINDUSTRY_RESULT "
RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-context"
# Every verifier container carries a per-run label so it can be found and removed even
# when `docker create` times out before it returns the container ID.
RUN_LABEL = "io.rhenium.mindustry.run"
BASE_TASK_LABEL = "shared-base"
STARTER_NAME = "mindustry"
CONTAINER_DESTINATION = "/app/mindustry"
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_REPORT_LIMIT = 8_000_000
# Offline build of the game sources plus one server run, with headroom.
_VERIFIER_TIMEOUT = 2400
# The Docker daemon may be shared and congested; container bookkeeping gets room.
_DOCKER_TIMEOUT = 300
# Removing the verifier container runs after the report is collected. On a daemon that
# is flushing image layers it has been observed to stall past five minutes; it gets a
# longer window so a stall does not void a collected verdict, and still fails closed.
_REMOVE_TIMEOUT = 900


def runtime_key(runtime_id: str = RUNTIME_ID) -> str:
    return f"mindustry/{runtime_id}"


class MindustryContainerRuntime:
    """Runs one task's verifier image with the submission mounted read-only."""

    def __init__(self) -> None:
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

    def image_id(self, reference: str) -> str:
        result = self._docker(["image", "inspect", reference, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT)
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError("Mindustry evaluator image is unavailable")
        return result.stdout.strip()

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"],
            timeout=_DOCKER_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError("Mindustry evaluator image is unavailable")
        try:
            labels = json.loads(result.stdout or "null")
        except json.JSONDecodeError as error:
            raise RuntimeError("Mindustry evaluator image has invalid labels") from error
        if labels is None:
            return {}
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in labels.items()
        ):
            raise RuntimeError("Mindustry evaluator image has invalid labels")
        return labels

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "mindustry-docker",
            "runtime": RUNTIME_ID,
            "mindustryVersion": MINDUSTRY_VERSION,
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
        self, submission: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError("Mindustry evaluation requires an immutable image ID")
        starter = submission.resolve() / STARTER_NAME
        run_label = f"{RUN_LABEL}={uuid.uuid4().hex}"
        arguments = [
            "create",
            "--label",
            run_label,
            "--pull=never",
            "--user=0:0",
            "--platform=linux/amd64",
            "--network=none",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=2048",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={starter},target=/submission/{STARTER_NAME},readonly",
            image_id,
            "bash",
            "-c",
            "set -euo pipefail; install -d -m 0700 /logs /logs/verifier; exec bash /tests/test.sh",
        ]
        try:
            created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        except subprocess.TimeoutExpired:
            self._remove_labelled(run_label)
            raise RuntimeError(
                "could not create the isolated Mindustry verifier: Docker did not answer"
            ) from None
        container_id = created.stdout.strip()
        if created.returncode or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            self._remove_labelled(run_label)
            raise RuntimeError("could not create the isolated Mindustry verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=_VERIFIER_TIMEOUT)
            logs.mkdir(parents=True, exist_ok=True)
            copied = self._docker(["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT)
            if copied.returncode:
                raise RuntimeError("could not collect Mindustry verification reports")
            return process, f"image={image_id}\nnetwork=none\n"
        finally:
            removed = self._docker(["rm", "--force", container_id], timeout=_REMOVE_TIMEOUT)
            if removed.returncode:
                raise RuntimeError("could not remove the owned Mindustry verifier")

    def _remove_labelled(self, run_label: str) -> None:
        """Best-effort removal of a verifier container whose creation did not complete."""
        try:
            listed = self._docker(
                ["ps", "--all", "--quiet", "--no-trunc", "--filter", f"label={run_label}"],
                timeout=_DOCKER_TIMEOUT,
            )
            for container_id in listed.stdout.split():
                if re.fullmatch(r"[0-9a-f]{64}", container_id):
                    self._docker(["rm", "--force", container_id], timeout=_REMOVE_TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            # The run already fails closed; a leftover container keeps its label for later cleanup.
            return


def read_report(path: Path, logs: Path, *, limit: int = _REPORT_LIMIT) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(logs.resolve()):
        raise ValueError("unsafe Mindustry verification report path")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing, invalid or oversized Mindustry verification report")
    return path.read_text(encoding="utf-8", errors="replace")


def _case_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Mindustry verifier report has an invalid case list")
    cases: list[dict[str, Any]] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or not item["name"]
            or type(item.get("passed")) is not bool
        ):
            raise ValueError("Mindustry verifier report has an invalid case")
        cases.append(item)
    return cases


def read_verifier_result(logs: Path) -> dict[str, Any]:
    """Return the in-container verifier result, or raise when it is not trustworthy.

    The verifier writes the Harbor reward and its structured result. They must
    agree: reward 1 exactly when the result is complete and passed.
    """
    verifier = logs / "verifier"
    reward = read_report(verifier / "reward.txt", logs, limit=16).strip()
    if reward not in {"0", "1"}:
        raise ValueError("Mindustry verifier reward is malformed")
    try:
        result = json.loads(read_report(verifier / "result.json", logs))
    except json.JSONDecodeError as error:
        raise ValueError("Mindustry verifier result is not valid JSON") from error
    if not isinstance(result, dict) or result.get("schemaVersion") != 1:
        raise ValueError("Mindustry verifier result has an unsupported schema")
    complete, passed = result.get("complete"), result.get("passed")
    if type(complete) is not bool or type(passed) is not bool:
        raise ValueError("Mindustry verifier result has an invalid shape")
    if passed and not complete:
        raise ValueError("Mindustry verifier result is inconsistent")
    if (reward == "1") != (complete and passed):
        raise ValueError("Mindustry verifier reward does not match its result")
    for layer in ("build", "live"):
        section = result.get(layer)
        if not isinstance(section, dict) or not isinstance(section.get("status"), str):
            raise ValueError(f"Mindustry verifier result lacks the {layer} layer")
    _case_list(result["live"].get("cases", []))
    return result
