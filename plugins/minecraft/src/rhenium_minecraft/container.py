"""Docker-backed pinned Paper dedicated-server verifier.

The verifier images carry the pinned Paper build, its Mojang-derived server
classes, the trusted GcbHarness plugin and one task's private tests. They are
built locally from operator-provided files and are never published.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

PAPER_VERSION = "1.21.11"
PAPER_BUILD = "132"
RUNTIME_ID = f"paper-{PAPER_VERSION}-{PAPER_BUILD}"
SYNTH_RUNTIME_ID = f"{RUNTIME_ID}-synth"
# Repository tasks authored automatically from project history live in their own
# pack; a runtime key is global, so that pack binds its own runtime id.
HISTORY_RUNTIME_ID = f"{RUNTIME_ID}-history"
# Construct tasks (a plugin written from a frozen skeleton) live in their own pack too.
CONSTRUCT_RUNTIME_ID = f"{RUNTIME_ID}-construct"
RUNTIME_IDS = frozenset({RUNTIME_ID, SYNTH_RUNTIME_ID, HISTORY_RUNTIME_ID, CONSTRUCT_RUNTIME_ID})
SERVER_JAR = f"paper-{PAPER_VERSION}-{PAPER_BUILD}.jar"
EULA_FILE = "eula.txt"
BASE_TAG = f"gcb-minecraft-paper-verifier:{PAPER_VERSION}-{PAPER_BUILD}"
BASE_IMAGE_REFERENCE = (
    "eclipse-temurin:21-jdk@sha256:92a2a4d7a928d057e7bd999c418d66c26a34eb9a0442f3ab67721c3f88110b2d"
)
RESULT_MARKER = "MINECRAFT_RESULT "
RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-context"
BASE_TASK_LABEL = "shared-base"
STARTER_NAME = "plugin"
CONTAINER_DESTINATION = "/app/plugin"
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_REPORT_LIMIT = 8_000_000
# Offline build plus unit tests plus one server boot, with headroom.
_VERIFIER_TIMEOUT = 2400
# Container bookkeeping is instant on an idle daemon but can stall for minutes while a
# shared host flushes image layers; a stall must not turn into an incomplete verdict.
_DOCKER_TIMEOUT = 300
# The verifier's own limit for one server run (boot, cases, shutdown). Its 420 s default
# is ample on an idle host, but a shared host that is flushing image layers can spend
# minutes saving chunks at shutdown after every case has already reported; the whole
# run stays inside _VERIFIER_TIMEOUT either way.
_SERVER_TIMEOUT = 1200


def runtime_key(runtime_id: str) -> str:
    return f"minecraft/{runtime_id}"


class MinecraftContainerRuntime:
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
            raise RuntimeError("Minecraft evaluator image is unavailable")
        return result.stdout.strip()

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"], timeout=_DOCKER_TIMEOUT
        )
        if result.returncode != 0:
            raise RuntimeError("Minecraft evaluator image is unavailable")
        try:
            labels = json.loads(result.stdout or "null")
        except json.JSONDecodeError as error:
            raise RuntimeError("Minecraft evaluator image has invalid labels") from error
        if labels is None:
            return {}
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in labels.items()
        ):
            raise RuntimeError("Minecraft evaluator image has invalid labels")
        return labels

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "minecraft-docker",
            "runtime": RUNTIME_ID,
            "paperVersion": PAPER_VERSION,
            "paperBuild": PAPER_BUILD,
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
            raise RuntimeError("Minecraft evaluation requires an immutable image ID")
        starter = submission.resolve() / STARTER_NAME
        arguments = [
            "create",
            "--pull=never",
            "--user=0:0",
            "--platform=linux/amd64",
            "--network=none",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=2048",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--env",
            f"GCB_SERVER_TIMEOUT={_SERVER_TIMEOUT}",
            "--mount",
            f"type=bind,source={starter},target=/submission/{STARTER_NAME},readonly",
            image_id,
            "bash",
            "-c",
            "set -euo pipefail; install -d -m 0700 /logs /logs/verifier; exec bash /tests/test.sh",
        ]
        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            raise RuntimeError("could not create the isolated Minecraft verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=_VERIFIER_TIMEOUT)
            logs.mkdir(parents=True, exist_ok=True)
            copied = self._docker(["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT)
            if copied.returncode:
                raise RuntimeError("could not collect Minecraft verification reports")
            return process, f"image={image_id}\nnetwork=none\n"
        finally:
            removed = self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)
            if removed.returncode:
                raise RuntimeError("could not remove the owned Minecraft verifier")


def read_report(path: Path, logs: Path, *, limit: int = _REPORT_LIMIT) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(logs.resolve()):
        raise ValueError("unsafe Minecraft verification report path")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing, invalid or oversized Minecraft verification report")
    return path.read_text(encoding="utf-8", errors="replace")


def _case_list(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"Minecraft verifier report has an invalid {label} case list")
    cases: list[dict[str, Any]] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str)
            or not item["name"]
            or type(item.get("passed")) is not bool
        ):
            raise ValueError(f"Minecraft verifier report has an invalid {label} case")
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
        raise ValueError("Minecraft verifier reward is malformed")
    try:
        result = json.loads(read_report(verifier / "result.json", logs))
    except json.JSONDecodeError as error:
        raise ValueError("Minecraft verifier result is not valid JSON") from error
    if not isinstance(result, dict) or result.get("schemaVersion") != 1:
        raise ValueError("Minecraft verifier result has an unsupported schema")
    complete, passed = result.get("complete"), result.get("passed")
    if type(complete) is not bool or type(passed) is not bool:
        raise ValueError("Minecraft verifier result has an invalid shape")
    if passed and not complete:
        raise ValueError("Minecraft verifier result is inconsistent")
    if (reward == "1") != (complete and passed):
        raise ValueError("Minecraft verifier reward does not match its result")
    for layer in ("build", "unit", "live"):
        section = result.get(layer)
        if not isinstance(section, dict) or not isinstance(section.get("status"), str):
            raise ValueError(f"Minecraft verifier result lacks the {layer} layer")
    _case_list(result["unit"].get("cases", []), "unit")
    _case_list(result["live"].get("cases", []), "live")
    return result
