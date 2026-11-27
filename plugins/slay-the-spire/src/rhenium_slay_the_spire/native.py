from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import SlayTheSpireCatalog, SlayTheSpireTask
from .container import PLUGIN_ID, PLUGIN_VERSION

NATIVE_RUNTIME_ID = "sts-native-646570-build10180494"
NATIVE_RUNTIME_KEY = f"{PLUGIN_ID}/{NATIVE_RUNTIME_ID}"
GAME_JAR = "desktop-1.0.jar"

_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
_PREPARE_TIMEOUT = 4 * 3600.0


def native_runtime_root(pack_root: Path) -> Path:
    return pack_root / "private" / "native-runtime"


def game_input(pack_root: Path) -> dict[str, Any]:
    """The pack's own record of the licensed game build every native task was authored against."""
    path = native_runtime_root(pack_root) / "game-input.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("the native game input record is missing or invalid") from error
    if not isinstance(value, dict) or not isinstance(value.get("source"), dict):
        raise ValueError("the native game input record has no Steam source")
    digest = (value.get("expected_sha256") or {}).get(GAME_JAR)
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("the native game input record has no pinned JAR digest")
    return value


def task_config(pack_root: Path, task: SlayTheSpireTask) -> dict[str, Any]:
    """Verifier limits and the submitted artifact path, read from the task's own Harbor config."""
    path = pack_root / "private" / "harbor" / task.id / "task.toml"
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    workdir = PurePosixPath(config["environment"]["workdir"])
    artifacts = config.get("artifacts") or []
    if len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        raise ValueError(f"native task must declare exactly one artifact: {task.id}")
    artifact = PurePosixPath(str(artifacts[0]["source"]))
    if not artifact.is_absolute() or not artifact.is_relative_to(workdir) or ".." in artifact.parts:
        raise ValueError(f"native task artifact must sit below its workdir: {task.id}")
    verifier = config["verifier"]
    environment = verifier["environment"]
    if verifier.get("environment_mode") != "separate" or environment.get("network_mode") != "no-network":
        raise ValueError(f"native task verifier must be separate and offline: {task.id}")
    return {
        "artifact": artifact.as_posix(),
        "artifactRelative": artifact.relative_to(workdir).as_posix(),
        "cpus": float(environment["cpus"]),
        "memoryMb": int(environment["memory_mb"]),
        "timeoutSec": float(verifier["timeout_sec"]),
        "authoredVerifierImage": str(environment["docker_image"]),
    }


class NativeDocker:
    """Docker seam shared by the native runtime builder and the evaluator."""

    def run(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        executable = shutil.which("docker")
        if executable is None:
            raise RuntimeError("docker is not installed")
        return subprocess.run(
            [executable, *arguments], capture_output=True, text=True, timeout=timeout, check=False
        )

    def image_id(self, reference: str) -> str:
        result = self.run(["image", "inspect", reference, "--format", "{{.Id}}"], timeout=30)
        if result.returncode != 0:
            raise RuntimeError("docker could not inspect the native verifier image")
        return result.stdout.strip()

    def status(self) -> dict[str, Any]:
        try:
            result = self.run(["version", "--format", "{{.Server.Version}}"], timeout=30)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        if result.returncode != 0:
            return {"available": False, "reason": "docker daemon is unavailable"}
        return {"available": True, "reason": None, "dockerVersion": result.stdout.strip()}


class SlayTheSpireNativeRuntimeBuilder(RuntimeBuilder):
    """Builds the native verifier images from the Steam-downloaded game JAR.

    The game bytes come only from the pinned Steam depot; the images are built by the
    pack's own preparation recipe (private/native-runtime/prepare.py) and stay local.
    """

    def __init__(
        self, context: BenchmarkContext, catalog: SlayTheSpireCatalog, docker: NativeDocker | None = None
    ):
        self.context = context
        self.catalog = catalog
        self.docker = docker or NativeDocker()

    @property
    def tasks(self) -> list[SlayTheSpireTask]:
        return [task for task in self.catalog.tasks if task.game_backed]

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=PLUGIN_ID, plugin_version=PLUGIN_VERSION)

    @staticmethod
    def _artifact_identity(tasks: dict[str, dict[str, Any]]) -> str:
        lines = [f"{task}={entry['verifierImage']}" for task, entry in sorted(tasks.items())]
        return "sha256:" + hashlib.sha256("\n".join(lines).encode()).hexdigest()

    def _source_policy(self, spec: RuntimeSpec) -> str:
        """The spec must name exactly the depot the pack records; returns the pinned JAR digest."""
        record = game_input(self.context.pack_root)
        if spec.provider != "steam" or not spec.restricted:
            raise ValueError("the native runtime must come from the restricted Steam provider")
        source = spec.source
        expected = record["source"]
        for key in ("kind", "appId", "depots"):
            if source.get(key) != expected.get(key):
                raise ValueError(f"native runtime source {key} does not match the pack's game input")
        if GAME_JAR not in (source.get("expectedFiles") or []):
            raise ValueError(f"native runtime source must expect {GAME_JAR}")
        digest = record["expected_sha256"][GAME_JAR]
        if (source.get("sha256") or {}).get(GAME_JAR) != digest:
            raise ValueError("native runtime source must pin the pack's game JAR digest")
        return str(digest)

    def _validate_source(self, spec: RuntimeSpec, source: Path) -> Path:
        digest = self._source_policy(spec)
        jar = source / GAME_JAR
        if jar.is_symlink() or not jar.is_file():
            raise RuntimeError(f"the Steam download does not contain {GAME_JAR}")
        with jar.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise RuntimeError(f"the downloaded {GAME_JAR} does not match the pinned build")
        return jar

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        report = dict(self.docker.status())
        try:
            report["gameSha256"] = self._source_policy(spec)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        report["taskCount"] = len(self.tasks)
        return report

    def _work_directory(self, destination: Path, fingerprint: str) -> Path:
        work = destination.resolve() / f"prepare-{fingerprint[:12]}"
        repository = native_runtime_root(self.context.pack_root).resolve().parents[3]
        if work.is_relative_to(repository):
            raise RuntimeError(
                "the native runtime is prepared outside the repository; set RHENIUM_CACHE_DIR "
                "to a directory outside the clone"
            )
        return work

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: Any
    ) -> RuntimeArtifact:
        jar = self._validate_source(spec, source)
        fingerprint = self._fingerprint(spec)
        work = self._work_directory(destination, fingerprint)
        try:
            return self._build(spec, jar, destination, fingerprint, work, progress)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            # Operations expose exception messages publicly. Keep recipe output,
            # private source paths and subprocess arguments in the private cache.
            with contextlib.suppress(OSError):
                descriptor = os.open(
                    destination / "prepare.log",
                    os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
                    0o600,
                )
                with os.fdopen(descriptor, "a", encoding="utf-8") as log:
                    os.fchmod(log.fileno(), 0o600)
                    log.write(f"\n{type(error).__name__}: {error}\n")
            raise RuntimeError(
                "native runtime preparation failed; inspect private preparation diagnostics"
            ) from None

    def _build(
        self,
        spec: RuntimeSpec,
        jar: Path,
        destination: Path,
        fingerprint: str,
        work: Path,
        progress: Any,
    ) -> RuntimeArtifact:
        if work.exists():
            shutil.rmtree(work)
        destination.mkdir(parents=True, exist_ok=True)
        script = native_runtime_root(self.context.pack_root) / "prepare.py"
        log_path = destination / "prepare.log"
        steps = 0
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as log:
            os.fchmod(log.fileno(), 0o600)
            process = subprocess.Popen(
                [sys.executable, str(script), "--game-jar", str(jar), "--output", str(work)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                # The recipe builds FROM local image IDs, which only the classic builder
                # resolves; BuildKit treats them as registry references.
                env={**os.environ, "DOCKER_BUILDKIT": "0"},
            )
            assert process.stdout is not None
            deadline = time.monotonic() + _PREPARE_TIMEOUT
            pending = b""
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(process.args, _PREPARE_TIMEOUT)
                        for key, _ in selector.select(timeout=remaining):
                            chunk = os.read(key.fd, 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            log.write(chunk)
                            log.flush()
                            pending += chunk
                            while b"\n" in pending:
                                line, pending = pending.split(b"\n", 1)
                                if line.startswith(b"PREPARE "):
                                    steps += 1
                                    phase = line.removeprefix(b"PREPARE ").decode("utf-8", "replace")
                                    progress(min(95, steps * 9), "native runtime: " + phase.strip())
                            pending = pending[-65536:]
                code = process.wait(timeout=max(0, deadline - time.monotonic()))
            except BaseException:
                # Kill only the preparation process group created above, including
                # children retaining the output pipe after their parent exits.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
            finally:
                process.stdout.close()
        if code != 0:
            raise RuntimeError(f"preparation recipe exited {code}")
        receipt = json.loads((work / "preparation.json").read_text(encoding="utf-8"))
        prepared = {row["task"]: row for row in receipt.get("tasks", [])}
        tasks: dict[str, dict[str, Any]] = {}
        for task in self.tasks:
            row = prepared.get(task.id)
            if row is None:
                raise RuntimeError(f"native preparation did not produce {task.id}")
            image = str(row["verifier_image"])
            if _IMAGE_ID.fullmatch(image) is None or self.docker.image_id(image) != image:
                raise RuntimeError(f"native verifier image is not an immutable local image: {task.id}")
            config = task_config(self.context.pack_root, task)
            tasks[task.id] = {
                "verifierImage": image,
                **{key: value for key, value in config.items() if key != "authoredVerifierImage"},
            }
        progress(100, "native Slay the Spire verifier images ready")
        return RuntimeArtifact(
            runtime_key=f"{PLUGIN_ID}/{spec.id}",
            fingerprint=fingerprint,
            kind="docker-images",
            identity=self._artifact_identity(tasks),
            location=str(work),
            metadata={
                "runtime": NATIVE_RUNTIME_ID,
                "network": "none",
                "gameSha256": receipt.get("game_sha256"),
                "recipeManifestSha256": receipt.get("recipe_manifest_sha256"),
                "tasks": tasks,
            },
        )

    def _artifact_tasks(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, dict[str, Any]]:
        if artifact.runtime_key != f"{PLUGIN_ID}/{spec.id}":
            raise ValueError("runtime artifact has the wrong runtime key")
        if artifact.fingerprint != self._fingerprint(spec):
            raise ValueError("runtime artifact has a stale fingerprint")
        if artifact.kind != "docker-images" or artifact.metadata.get("runtime") != NATIVE_RUNTIME_ID:
            raise ValueError("runtime artifact is not a native Slay the Spire runtime")
        tasks = artifact.metadata.get("tasks")
        if not isinstance(tasks, dict) or set(tasks) != {task.id for task in self.tasks}:
            raise ValueError("runtime artifact has an incomplete native task set")
        if artifact.identity != self._artifact_identity(tasks):
            raise ValueError("runtime artifact identity does not match its images")
        return tasks

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            tasks = self._artifact_tasks(spec, artifact)
            for task_id, entry in tasks.items():
                image = str(entry.get("verifierImage") or "")
                if _IMAGE_ID.fullmatch(image) is None or self.docker.image_id(image) != image:
                    raise RuntimeError(f"native verifier image is missing or mutable: {task_id}")
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        return {"available": True, "imageCount": len(tasks), "network": "none", "identity": artifact.identity}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        tasks = self._artifact_tasks(spec, artifact)
        for image in sorted({str(entry["verifierImage"]) for entry in tasks.values()}):
            inspected = self.docker.run(["image", "inspect", image, "--format", "{{.Id}}"], timeout=10)
            if inspected.returncode != 0:
                continue
            removed = self.docker.run(["image", "rm", image], timeout=120)
            if removed.returncode != 0:
                raise RuntimeError(f"failed to prune native verifier image {image}")
        # Core removes the selected runtime's cache under its resolved cache root.
        # An artifact's descriptive location is never a recursive deletion target.


def run_native_verifier(
    docker: NativeDocker,
    pack_root: Path,
    task: SlayTheSpireTask,
    entry: dict[str, Any],
    submission: Path,
    scratch: Path,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Runs the task's own offline verifier on the submitted artifact, as Harbor's separate verifier would.

    The verifier writes /logs as root with private permissions, so its results are
    copied out with ``docker cp`` (owned by the caller) instead of a bind mount.
    """
    submitted = (submission / task.starter_name / str(entry["artifactRelative"])).resolve()
    if not submitted.is_dir() or not submitted.is_relative_to(submission.resolve()):
        raise ValueError(f"the submission has no {task.starter_name}/{entry['artifactRelative']} directory")
    tests = scratch / "tests"
    verifier = scratch / "verifier"
    shutil.copytree(pack_root / "private" / "harbor" / task.id / "tests", tests)
    name = f"rhenium-sts-native-{scratch.name}".lower()
    name = re.sub(r"[^a-z0-9_.-]", "-", name)
    memory = f"{int(entry['memoryMb'])}m"
    try:
        process = docker.run(
            [
                "run",
                "--pull=never",
                "--name",
                name,
                "--network",
                "none",
                "--cpus",
                str(entry["cpus"]),
                "--env",
                f"JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount={max(1, math.ceil(float(entry['cpus'])))}",
                "--memory",
                memory,
                "--memory-swap",
                memory,
                "--mount",
                f"type=bind,src={tests},dst=/tests",
                "--mount",
                f"type=bind,src={submitted},dst={entry['artifact']},readonly",
                "--workdir",
                "/tests",
                str(entry["verifierImage"]),
                "bash",
                "/tests/test.sh",
            ],
            timeout=float(entry["timeoutSec"]),
        )
        copied = docker.run(["cp", f"{name}:/logs/verifier", str(verifier)], timeout=120)
        if copied.returncode != 0:
            raise RuntimeError("could not copy the native verifier results out of the container")
    finally:
        docker.run(["rm", "-f", name], timeout=120)
    return process, verifier
