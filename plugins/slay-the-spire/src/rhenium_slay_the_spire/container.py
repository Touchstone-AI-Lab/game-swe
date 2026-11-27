from __future__ import annotations

import hashlib
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext

from .catalog import CONTAINER_DESTINATION, STARTER_NAME, SlayTheSpireCatalog, SlayTheSpireTask

PLUGIN_ID = "slay-the-spire"
PLUGIN_VERSION = "0.7.0"
RUNTIME_ID = "modthespire-jdk8-maven"
RUNTIME_KEY = f"{PLUGIN_ID}/{RUNTIME_ID}"

RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-context"

_EVALUATION_TIMEOUT = 2400.0
_BUILD_TIMEOUT = 7200.0


class SlayTheSpireRuntime:
    """Docker seam for the ModTheSpire evaluator images.

    The pack carries no licensed content: every task image is built from the
    task's own environment Dockerfile on top of one publicly readable,
    digest-pinned JDK 8 Maven image acquired by the container provider. Image
    builds warm the Maven repository and need network; evaluation never does.
    """

    def __init__(self, context: BenchmarkContext, catalog: SlayTheSpireCatalog):
        self.context = context
        self.catalog = catalog

    def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        executable = shutil.which("docker")
        if executable is None:
            raise RuntimeError("docker is not installed")
        return subprocess.run(
            [executable, *arguments], capture_output=True, text=True, timeout=timeout, check=False
        )

    def image_tag(self, task: SlayTheSpireTask, fingerprint: str) -> str:
        return f"rhenium-slay-the-spire:{task.id}-{fingerprint[:12]}"

    def image_id(self, reference: str) -> str:
        result = self._docker(["image", "inspect", reference, "--format", "{{.Id}}"], timeout=30)
        if result.returncode != 0:
            raise RuntimeError("docker could not inspect the evaluator image")
        return result.stdout.strip()

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"], timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError("docker could not inspect the evaluator image labels")
        import json

        labels = json.loads(result.stdout or "null")
        return {str(key): str(value) for key, value in (labels or {}).items()}

    def status(self) -> dict[str, Any]:
        try:
            result = self._docker(["version", "--format", "{{.Server.Version}}"], timeout=30)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        if result.returncode != 0:
            return {"available": False, "reason": "docker daemon is unavailable"}
        return {
            "available": True,
            "reason": None,
            "dockerVersion": result.stdout.strip(),
            "runtime": RUNTIME_ID,
            "network": "none",
        }

    def validate_source_image(
        self, reference: str, recorded_image_id: str, expected_files: tuple[str, ...]
    ) -> None:
        """Bind the provider's record to the image this host will actually build on."""
        if self.image_id(reference) != recorded_image_id:
            raise RuntimeError("container source record does not match the pulled image ID")
        if not expected_files:
            return
        command = (
            'for path in "$@"; do [ -e "/$path" ] || { '
            'echo "missing expected source file: $path" >&2; exit 1; }; done'
        )
        result = self._docker(
            [
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--pull=never",
                "--entrypoint",
                "/bin/sh",
                reference,
                "-eu",
                "-c",
                command,
                "rhenium-source-check",
                *expected_files,
            ],
            timeout=120,
        )
        if result.returncode != 0:
            log = (result.stdout + result.stderr)[-4000:]
            raise RuntimeError(f"container source is missing required runtime files\n{log}")

    def environment_root(self, task: SlayTheSpireTask) -> Path:
        return self.context.pack_root / "private" / "harbor" / task.id / "environment"

    def build_context_fingerprint(self, task: SlayTheSpireTask) -> str:
        environment = self.environment_root(task)
        digest = hashlib.sha256()
        for candidate in sorted(
            environment.rglob("*"), key=lambda path: path.relative_to(environment).as_posix()
        ):
            if candidate.is_symlink():
                raise RuntimeError(f"task build context contains a symbolic link: {task.id}")
            relative = candidate.relative_to(environment).as_posix().encode()
            mode = str(stat.S_IMODE(candidate.stat().st_mode)).encode()
            if candidate.is_dir():
                digest.update(b"directory\0" + relative + b"\0" + mode + b"\0")
            elif candidate.is_file():
                digest.update(b"file\0" + relative + b"\0" + mode + b"\0")
                digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            else:
                raise RuntimeError(f"task build context contains an unsupported file: {task.id}")
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def dockerfile_base_images(dockerfile: Path) -> list[str]:
        """Every image a Dockerfile builds on, in order."""
        bases: list[str] = []
        for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
            fields = raw_line.strip().split()
            if len(fields) >= 2 and fields[0].lower() == "from":
                bases.append(fields[1])
        return bases

    def build_image(
        self, task: SlayTheSpireTask, *, source_reference: str, fingerprint: str
    ) -> tuple[str, str, str]:
        """Build and label one task image from the exact provider-acquired source."""
        environment = self.environment_root(task)
        dockerfile = environment / "Dockerfile"
        if self.dockerfile_base_images(dockerfile) != [source_reference]:
            raise RuntimeError("task Dockerfile is not bound to the acquired container source")
        tag = self.image_tag(task, fingerprint)
        labels = {
            RUNTIME_FINGERPRINT_LABEL: fingerprint,
            RUNTIME_SOURCE_LABEL: source_reference,
            RUNTIME_TASK_LABEL: task.id,
            RUNTIME_ID_LABEL: RUNTIME_ID,
            RUNTIME_BUILD_LABEL: self.build_context_fingerprint(task),
        }
        arguments = ["build", "--pull=false", "--tag", tag]
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(dockerfile), str(environment)))
        result = self._docker(arguments, timeout=_BUILD_TIMEOUT)
        log = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(f"failed to build the Slay the Spire evaluator image\n{log[-8000:]}")
        return tag, self.image_id(tag), log

    def run(
        self, task: SlayTheSpireTask, submission: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        """Grade one submission offline in the prepared task image."""
        tests = (self.context.pack_root / "private" / "harbor" / task.id / "tests").resolve()
        verifier_logs = logs / "verifier"
        verifier_logs.mkdir(parents=True, exist_ok=True)
        # The container drops every capability, so its root cannot write into a bind
        # mount owned by the host user unless the directory is world-writable.
        verifier_logs.chmod(0o777)
        logs.chmod(0o777)
        # The pinned JDK 8 Maven image carries no rsync, so the submission is staged
        # with coreutils. Ownership is deliberately not preserved: the container drops
        # every capability, so a chown would fail and abort before any test ran. The
        # destination is replaced wholesale, which is what --delete would have given.
        command = (
            "set -euo pipefail; "
            f"rm -rf {CONTAINER_DESTINATION}; mkdir -p {CONTAINER_DESTINATION}; "
            f"cp -R --preserve=mode,timestamps /submission/{STARTER_NAME}/. "
            f"{CONTAINER_DESTINATION}/; "
            "bash /tests/test.sh; "
            # Surefire's per-case reports are copied out beside the summary so the
            # evaluator can name each observed case; the summary stays authoritative.
            # The directory is world-writable so the host user can clean it up.
            "mkdir -p -m 0777 /logs/verifier/surefire; "
            f"cp {CONTAINER_DESTINATION}/target/surefire-reports/TEST-*.xml "
            "/logs/verifier/surefire/ 2>/dev/null || true"
        )
        arguments = [
            "run",
            "--rm",
            "--network=none",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={submission},target=/submission,readonly",
            "--mount",
            f"type=bind,source={tests},target=/tests,readonly",
            "--mount",
            f"type=bind,source={logs},target=/logs",
            "--pull=never",
            image_id,
            "bash",
            "-lc",
            command,
        ]
        result = self._docker(arguments, timeout=_EVALUATION_TIMEOUT)
        return result, f"image={image_id}\nnetwork=none\n"
