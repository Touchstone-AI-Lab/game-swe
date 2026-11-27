from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog

from .assertions import AssertionManifest
from .catalog import RimWorldCatalog, RimWorldTask, assertion_manifest
from .safe_files import (
    UnsafePathError,
    ensure_directory_nofollow,
    secure_inventory,
    secure_read_bytes,
    secure_tree_hash,
    write_owner_file,
)
from .supervisor import (
    EvidenceError,
    collect_observations,
    encode_private_verdict,
    incomplete_verdict,
    rubric_hash,
    strict_json_object,
    validate_private_verdict,
)

RUNTIME_ID = "rimworld-1.6.4871-linux-x64"
RUNTIME_KEY = f"rimworld/{RUNTIME_ID}"
RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task-key"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-evidence"
RUNTIME_ROLE_LABEL = "io.rhenium.runtime.role"
RUNTIME_ADAPTER_LABEL = "io.rhenium.runtime.adapter-evidence"
RUNTIME_SOURCE_TREE_LABEL = "io.rhenium.runtime.source-evidence"
RUNTIME_RUBRIC_LABEL = "io.rhenium.runtime.rubric-evidence"
RUNTIME_TASK_SOURCE_LABEL = "io.rhenium.runtime.task-source-evidence"
RUNTIME_TOOLCHAIN_LABEL = "io.rhenium.runtime.toolchain"

SDK_IMAGE = (
    "mcr.microsoft.com/dotnet/sdk:8.0.422-bookworm-slim@"
    "sha256:63ebabdcde24cc8134304a6f50719cf1e22bb4e9f7148ac4ef967c7680187356"
)
IMAGE_ROLES = ("builder", "evaluator")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
# Daemon probes, inspections and container bookkeeping on a congested host regularly take
# tens of seconds; a short limit turned such runs into spurious incomplete results.
_DOCKER_TIMEOUT = 300
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_SOURCE_TOKENS = (
    "rhenium-rimworld-verifier",
    "rhenium-rimworld-observer",
    "gcb_rimworld",
    "observations.json",
    "result.json",
    "reward.txt",
    "/logs/verifier",
    "application.quit",
)
_PROPRIETARY_SUFFIXES = {".dll", ".exe", ".so", ".dylib", ".pdb"}
_EMPTY_SHA256 = "sha256:" + hashlib.sha256(b"").hexdigest()
# MSBuild reports each compiler error with the project it belongs to.
_BUILD_ERROR = re.compile(r": error [A-Z]+\d+: .*\[/opt/rhenium/tests/(Submission|Harness/Harness)\.csproj\]")
SUBMISSION_BUILD_FAILED = "RimWorld submission build failed: the submitted sources did not compile"
VERIFIER_BUILD_FAILED = "RimWorld verifier harness build failed (verifier bug, not the submission)"


def build_failure_log(build_log: str) -> str:
    """The public log line for a failed build, attributing it from the compiler's own errors.

    build.sh compiles the submission before the verifier harness, so errors only in the
    submission project are the submission's; any harness error is the verifier's. Anything
    else (no attributable error) stays unattributed.
    """
    projects = {match.group(1) for match in _BUILD_ERROR.finditer(build_log)}
    if projects == {"Submission"}:
        return f"{SUBMISSION_BUILD_FAILED}; private evidence was recorded\n"
    if "Harness/Harness" in projects:
        return f"{VERIFIER_BUILD_FAILED}; private evidence was recorded\n"
    return "RimWorld build failed; private evidence was recorded\n"


@dataclass(frozen=True)
class RuntimeExecution:
    build_process: subprocess.CompletedProcess[str]
    engine_process: subprocess.CompletedProcess[str] | None
    candidate_assembly: str
    adapter_assembly: str
    observation: bytes
    player_log: str
    runtime_log: str


class RimWorldRuntime:
    """Docker-backed client runner; availability never implies a successful game launch."""

    def __init__(self, context: BenchmarkContext, catalog: RimWorldCatalog):
        self.context = context
        self.catalog = catalog
        self.docker = shutil.which("docker") or ""
        self.image_prefix = "rhenium-rimworld"

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

    @staticmethod
    def _missing_object(result: subprocess.CompletedProcess[str]) -> bool:
        text = (result.stdout + result.stderr).lower()
        return result.returncode != 0 and (
            "no such image" in text
            or "no such object" in text
            or "no such container" in text
        )

    def image_tag(self, task: RimWorldTask, fingerprint: str, role: str) -> str:
        if role not in IMAGE_ROLES:
            raise ValueError("unknown RimWorld image role")
        return f"{self.image_prefix}:{role}-{task.id}-{self.catalog.version}-{fingerprint[:12]}"

    def image_id(self, reference: str) -> str:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
        )
        if result.returncode != 0 or not result.stdout.strip():
            if self._missing_object(result):
                raise FileNotFoundError("RimWorld evaluator image is unavailable")
            raise RuntimeError("Docker daemon could not inspect the RimWorld evaluator image")
        value = result.stdout.strip()
        if _IMAGE_ID.fullmatch(value) is None:
            raise RuntimeError("RimWorld evaluator image returned a malformed immutable ID")
        return value

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"],
            timeout=_DOCKER_TIMEOUT,
        )
        if result.returncode != 0:
            if self._missing_object(result):
                raise FileNotFoundError("RimWorld evaluator image is unavailable")
            raise RuntimeError("Docker daemon could not inspect RimWorld image labels")
        try:
            labels = json.loads(result.stdout or "null")
        except json.JSONDecodeError as error:
            raise RuntimeError("RimWorld evaluator image has invalid labels") from error
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in labels.items()
        ):
            raise RuntimeError("RimWorld evaluator image has invalid labels")
        return labels

    @staticmethod
    def _json_string_fields(raw: str, count: int) -> tuple[str, ...]:
        decoder = json.JSONDecoder()
        remaining = raw.lstrip()
        values: list[str] = []
        try:
            for _index in range(count):
                value, end = decoder.raw_decode(remaining)
                if not isinstance(value, str) or not value:
                    raise ValueError("Docker identity field is not a string")
                values.append(value)
                remaining = remaining[end:].lstrip()
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError("Docker identity is invalid") from error
        if remaining:
            raise RuntimeError("Docker identity has unexpected fields")
        return tuple(values)

    def image_platform(self, reference: str) -> tuple[str, str]:
        result = self._docker(
            [
                "image",
                "inspect",
                reference,
                "--format",
                "{{json .Os}} {{json .Architecture}}",
            ],
            timeout=_DOCKER_TIMEOUT,
        )
        if result.returncode != 0:
            if self._missing_object(result):
                raise FileNotFoundError("RimWorld evaluator image is unavailable")
            raise RuntimeError("Docker daemon could not inspect RimWorld image platform")
        operating_system, architecture = self._json_string_fields(result.stdout, 2)
        return operating_system.lower(), architecture.lower()

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "rimworld-docker",
            "runtime": RUNTIME_ID,
            "network": "none",
            "gameVersion": "1.6.4871",
            "runnerPlatform": "linux-x64",
            "engineLaunchValidated": False,
        }
        if platform.system().lower() != "linux" or platform.machine().lower() not in {
            "amd64",
            "x86_64",
        }:
            return {
                **base,
                "available": False,
                "reason": "the RimWorld runtime requires a Linux x86_64 Docker host",
            }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            info = self._docker(
                [
                    "info",
                    "--format",
                    (
                        "{{json .ServerVersion}} {{json .OperatingSystem}} "
                        "{{json .OSType}} {{json .Architecture}}"
                    ),
                ],
                timeout=_DOCKER_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError):
            return {**base, "available": False, "reason": "Docker daemon probe failed"}
        if info.returncode != 0:
            return {**base, "available": False, "reason": "Docker daemon is unavailable"}
        try:
            version, operating_system, os_type, architecture = self._json_string_fields(
                info.stdout, 4
            )
        except RuntimeError:
            return {**base, "available": False, "reason": "Docker daemon identity is invalid"}
        if os_type.lower() != "linux" or architecture.lower() not in {"amd64", "x86_64"}:
            return {
                **base,
                "available": False,
                "reason": "Docker daemon is not Linux x86_64",
            }
        return {
            **base,
            "available": True,
            "reason": None,
            "dockerVersion": version,
            "dockerOperatingSystem": operating_system,
            "dockerOSType": os_type,
            "dockerArchitecture": architecture,
            "imageRolesRequired": list(IMAGE_ROLES),
        }

    @staticmethod
    def _mount(source: Path, target: str, *, readonly: bool) -> str:
        raw = os.fspath(source)
        if any(character in raw for character in (",", "\n", "\r", "\x00")):
            raise ValueError("Docker bind-mount path contains an unsupported character")
        suffix = ",readonly" if readonly else ""
        return f"type=bind,source={raw},target={target}{suffix}"

    @staticmethod
    def _user() -> str:
        uid = getattr(os, "getuid", lambda: 65532)()
        gid = getattr(os, "getgid", lambda: 65532)()
        return f"{uid if uid != 0 else 65532}:{gid if uid != 0 else 65532}"

    @classmethod
    def _sandbox_arguments(cls, *, user: str) -> list[str]:
        return [
            "--init",
            "--network=none",
            "--read-only",
            "--user",
            user,
            "--cpus=6",
            "--memory=16g",
            "--memory-swap=16g",
            # Bounds the container's own processes. An nproc ulimit cannot do this: the
            # kernel counts every task of the same uid on the host, so a busy host made
            # the container fail to exec its init.
            "--pids-limit=512",
            "--shm-size=512m",
            "--ulimit",
            "nofile=1024:1024",
            "--ulimit",
            "core=0:0",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--log-driver=local",
            "--log-opt=max-size=10m",
            "--log-opt=max-file=1",
            # The local driver compresses rotated files by default, which Docker refuses
            # to combine with a single file, so every container failed to start.
            "--log-opt=compress=false",
            "--pull=never",
        ]

    def build_image(
        self,
        task: RimWorldTask,
        *,
        build_context: Path,
        role: str,
        fingerprint: str,
        source_identity: str,
        task_key: str,
        build_evidence: str,
        adapter_evidence: str,
        source_evidence: str,
        rubric_evidence: str,
        task_source_evidence: str,
    ) -> tuple[str, str, str]:
        if role not in IMAGE_ROLES:
            raise ValueError("unknown RimWorld image role")
        dockerfile = build_context / "Dockerfile"
        from_lines = [
            line.split()[1]
            for line in dockerfile.read_text(encoding="utf-8").splitlines()
            if line.strip().lower().startswith("from ")
        ]
        if not from_lines or set(from_lines) != {SDK_IMAGE}:
            raise RuntimeError("task Dockerfile is not bound to the pinned SDK image")
        tag = self.image_tag(task, fingerprint, role)
        labels = {
            RUNTIME_FINGERPRINT_LABEL: fingerprint,
            RUNTIME_SOURCE_LABEL: source_identity,
            RUNTIME_TASK_LABEL: task_key,
            RUNTIME_ID_LABEL: RUNTIME_ID,
            RUNTIME_BUILD_LABEL: build_evidence,
            RUNTIME_ROLE_LABEL: role,
            RUNTIME_ADAPTER_LABEL: adapter_evidence,
            RUNTIME_SOURCE_TREE_LABEL: source_evidence,
            RUNTIME_RUBRIC_LABEL: rubric_evidence,
            RUNTIME_TASK_SOURCE_LABEL: task_source_evidence,
            RUNTIME_TOOLCHAIN_LABEL: SDK_IMAGE,
        }
        arguments = ["build", "--pull=false", "--target", f"{role}-runtime", "--tag", tag]
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(dockerfile), str(build_context)))
        result = self._docker(arguments, timeout=7200)
        log = (result.stdout + result.stderr)[-200_000:]
        if result.returncode != 0:
            # Without the builder's own output an operator cannot tell a missing base image
            # from a compile error in the adapter.
            raise RuntimeError(f"failed to build a RimWorld {role} image\n{log[-4000:]}")
        return tag, self.image_id(tag), log

    def _inspect_owned_container(
        self, name: str, labels: dict[str, str]
    ) -> tuple[str, str] | None:
        inspected = self._docker(
            ["container", "inspect", name, "--format", "{{json .}}"], timeout=_DOCKER_TIMEOUT
        )
        if inspected.returncode != 0:
            if self._missing_object(inspected):
                return None
            raise RuntimeError("Docker daemon could not inspect the evaluation container")
        try:
            value = strict_json_object(inspected.stdout.encode(), maximum=2_000_000)
        except EvidenceError as error:
            raise RuntimeError("evaluation container identity is invalid") from error
        container_id = value.get("Id")
        state = value.get("State")
        config = value.get("Config")
        observed_labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            not isinstance(container_id, str)
            or _CONTAINER_ID.fullmatch(container_id) is None
            or not isinstance(state, dict)
            or not isinstance(observed_labels, dict)
            or any(observed_labels.get(key) != expected for key, expected in labels.items())
        ):
            raise RuntimeError("refusing to manage an unowned evaluation container")
        status = state.get("Status")
        if not isinstance(status, str):
            raise RuntimeError("evaluation container status is invalid")
        return container_id, status

    def _cleanup_owned_container(self, name: str, labels: dict[str, str]) -> None:
        inspected = self._inspect_owned_container(name, labels)
        if inspected is None:
            return
        container_id, _status = inspected
        removed = self._docker(["container", "rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)
        if removed.returncode != 0:
            raise RuntimeError("failed to stop the owned evaluation container")
        if self._inspect_owned_container(container_id, labels) is not None:
            raise RuntimeError("owned evaluation container did not stop")

    def _run_container(
        self,
        arguments: list[str],
        *,
        name: str,
        labels: dict[str, str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return self._docker(arguments, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            self._cleanup_owned_container(name, labels)
            raise

    def _copy_owned_logs(self, name: str, labels: dict[str, str], destination: Path) -> None:
        inspected = self._inspect_owned_container(name, labels)
        if inspected is None:
            return
        container_id, status = inspected
        try:
            if status == "running":
                raise RuntimeError("evaluation container is still running after Docker returned")
            copied = self._docker(
                ["container", "cp", f"{container_id}:/logs/.", os.fspath(destination)],
                timeout=_DOCKER_TIMEOUT,
            )
            if copied.returncode != 0:
                raise RuntimeError("failed to copy private evaluation evidence")
        finally:
            self._cleanup_owned_container(name, labels)

    @staticmethod
    def _container_identity(task_key: str, evaluation_id: str, role: str) -> dict[str, str]:
        return {
            "io.rhenium.evaluation.id": evaluation_id,
            "io.rhenium.evaluation.task-key": task_key,
            "io.rhenium.evaluation.role": role,
            "io.rhenium.runtime.id": RUNTIME_ID,
        }

    def execute(
        self,
        task: RimWorldTask,
        *,
        snapshot: Path,
        evidence_dir: Path,
        images: dict[str, str],
        evaluation_id: str,
        nonce: str,
        task_key: str,
        submission_hash: str,
    ) -> RuntimeExecution:
        build_output = evidence_dir / "build-output"
        run_assemblies = evidence_dir / "run-assemblies"
        logs = evidence_dir / "runtime"
        for directory in (build_output, run_assemblies, logs):
            ensure_directory_nofollow(directory)
        container_user = self._user()
        container_uid, container_gid = container_user.split(":", 1)
        os.chmod(build_output, 0o777)
        builder_name = f"rhenium-rimworld-build-{uuid.uuid4().hex[:16]}"
        builder_labels = self._container_identity(task_key, evaluation_id, "builder")
        builder_args = ["run", "--rm", "--name", builder_name]
        for key, value in builder_labels.items():
            builder_args.extend(("--label", f"{key}={value}"))
        builder_args.extend(self._sandbox_arguments(user=container_user))
        builder_args.extend(
            (
                "--mount",
                self._mount(snapshot, "/submission", readonly=True),
                "--mount",
                self._mount(build_output, "/output", readonly=False),
                "--tmpfs",
                "/tmp:rw,exec,nosuid,nodev,size=256m",
                "--tmpfs",
                (
                    "/work:rw,exec,nosuid,nodev,size=2g,"
                    f"uid={container_uid},gid={container_gid},mode=0700"
                ),
                images["builder"],
                "bash",
                "/opt/rhenium/build.sh",
            )
        )
        build_process = self._run_container(
            builder_args, name=builder_name, labels=builder_labels, timeout=600 + _DOCKER_TIMEOUT
        )
        os.chmod(build_output, 0o700)
        if build_process.returncode != 0:
            return RuntimeExecution(
                build_process,
                None,
                _EMPTY_SHA256,
                _EMPTY_SHA256,
                b"",
                "",
                (build_process.stdout + build_process.stderr)[-200_000:],
            )

        candidate_relative = f"candidate/{task.assembly_name}.dll"
        candidate_bytes = secure_read_bytes(
            build_output, candidate_relative, maximum=50_000_000
        )
        adapter_bytes = secure_read_bytes(
            build_output,
            "verifier/RheniumRimWorldVerifier.dll",
            maximum=50_000_000,
        )
        write_owner_file(run_assemblies / f"{task.assembly_name}.dll", candidate_bytes)
        write_owner_file(run_assemblies / "RheniumRimWorldVerifier.dll", adapter_bytes)
        candidate_hash = "sha256:" + hashlib.sha256(candidate_bytes).hexdigest()
        adapter_hash = "sha256:" + hashlib.sha256(adapter_bytes).hexdigest()
        runner_name = f"rhenium-rimworld-run-{uuid.uuid4().hex[:16]}"
        runner_labels = self._container_identity(task_key, evaluation_id, "evaluator")
        runner_args = ["run", "--name", runner_name]
        for key, value in runner_labels.items():
            runner_args.extend(("--label", f"{key}={value}"))
        runner_args.extend(self._sandbox_arguments(user=container_user))
        for key, value in {
            # Unity writes its player preferences under HOME. Without one it targets the
            # read-only root, fails to create /.config, and the game dies before any
            # assertion runs; /tmp is the container's own writable tmpfs.
            "HOME": "/tmp",
            "RHENIUM_EVALUATION_ID": evaluation_id,
            "RHENIUM_EVALUATION_NONCE": nonce,
            "RHENIUM_TASK_KEY": task_key,
            "RHENIUM_SUBMISSION_SHA256": submission_hash,
            "RHENIUM_CANDIDATE_ASSEMBLY_SHA256": candidate_hash,
        }.items():
            runner_args.extend(("--env", f"{key}={value}"))
        runner_args.extend(
            (
                "--mount",
                self._mount(run_assemblies, "/assemblies", readonly=True),
                "--tmpfs",
                "/tmp:rw,exec,nosuid,nodev,size=256m",
                "--mount",
                # The verifier's evidence has to survive the container: a tmpfs is gone the
                # moment it exits, so copying /logs afterwards always came back empty.
                self._mount(logs, "/logs", readonly=False),
                "--tmpfs",
                (
                    "/state:rw,noexec,nosuid,nodev,size=1g,"
                    f"uid={container_uid},gid={container_gid},mode=0700"
                ),
                "--tmpfs",
                (
                    "/opt/rimworld/Mods:rw,exec,nosuid,nodev,size=256m,"
                    f"uid={container_uid},gid={container_gid},mode=0700"
                ),
                images["evaluator"],
                "bash",
                "/opt/rhenium/test.sh",
            )
        )
        engine_process = self._run_container(
            runner_args, name=runner_name, labels=runner_labels, timeout=700 + _DOCKER_TIMEOUT
        )
        self._cleanup_owned_container(runner_name, runner_labels)
        log_entries = secure_inventory(
            logs, maximum_entries=1_000, maximum_bytes=128_000_000
        )
        observation_files = [
            entry for entry in log_entries if not entry.is_dir and entry.relative.endswith(".json")
        ]
        observation = (
            secure_read_bytes(logs, "verifier/observations.json", maximum=1_000_000)
            if [entry.relative for entry in observation_files] == ["verifier/observations.json"]
            else b""
        )
        player_log = (
            secure_read_bytes(logs, "verifier/Player.log", maximum=20_000_000).decode(
                "utf-8", errors="replace"
            )
            if any(entry.relative == "verifier/Player.log" for entry in log_entries)
            else ""
        )
        runtime_log = (
            build_process.stdout
            + build_process.stderr
            + engine_process.stdout
            + engine_process.stderr
        )[-200_000:]
        return RuntimeExecution(
            build_process,
            engine_process,
            candidate_hash,
            adapter_hash,
            observation,
            player_log,
            runtime_log,
        )


class RimWorldEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: RimWorldCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = RimWorldRuntime(context, catalog)

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _task_key(pack_root: Path, task: RimWorldTask) -> str:
        raw = secure_read_bytes(pack_root, "benchmark.json", maximum=100_000)
        manifest = strict_json_object(raw, maximum=100_000)
        if set(manifest) != {
            "schema_version",
            "pack_id",
            "plugin",
            "catalog",
            "runtime_catalog",
        }:
            raise ValueError("RimWorld benchmark manifest has an invalid shape")
        if manifest.get("schema_version") != 2 or manifest.get("plugin") != "rimworld":
            raise ValueError("RimWorld benchmark manifest has an invalid identity")
        pack_id = manifest.get("pack_id")
        if not isinstance(pack_id, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]*", pack_id) is None:
            raise ValueError("RimWorld benchmark manifest has an invalid pack ID")
        return f"rimworld/{pack_id}/{task.id}"

    def _base_identity(
        self, task: RimWorldTask, assertions: AssertionManifest
    ) -> dict[str, str]:
        catalog = "sha256:" + hashlib.sha256(
            secure_read_bytes(self.context.pack_root, "catalog.json", maximum=2_000_000)
        ).hexdigest()
        rubric = rubric_hash(assertions)
        return {
            "catalog": catalog,
            "rubric": rubric,
            "submission": _EMPTY_SHA256,
            "candidateAssembly": _EMPTY_SHA256,
            "adapterAssembly": _EMPTY_SHA256,
            "runtimeFingerprint": _EMPTY_SHA256,
            "runtimeArtifact": _EMPTY_SHA256,
            "builderImage": _EMPTY_SHA256,
            "evaluatorImage": _EMPTY_SHA256,
            "buildEvidence": _EMPTY_SHA256,
            "adapterEvidence": _EMPTY_SHA256,
            "sourceEvidence": _EMPTY_SHA256,
        }

    @staticmethod
    def _snapshot_submission(
        submission: Path,
        task: RimWorldTask,
        destination: Path,
    ) -> tuple[str, dict[str, Any]]:
        try:
            entries = secure_inventory(
                submission, maximum_entries=1_000, maximum_bytes=20_000_000
            )
            files = {entry.relative: entry for entry in entries if not entry.is_dir}
            if any(
                Path(entry.relative).suffix.lower() in _PROPRIETARY_SUFFIXES
                for entry in files.values()
            ):
                raise UnsafePathError("submission contains a binary")
            missing = [relative for relative in task.required_files if relative not in files]
            if missing:
                raise UnsafePathError("submission is missing required source")
            ensure_directory_nofollow(destination)
            for relative in task.required_files:
                data = secure_read_bytes(submission, relative, maximum=2_000_000)
                if Path(relative).suffix.lower() == ".cs":
                    lowered = data.decode("utf-8", errors="replace").lower()
                    if any(token in lowered for token in _FORBIDDEN_SOURCE_TOKENS):
                        raise UnsafePathError("submission contains a private-harness marker")
                write_owner_file(destination / relative, data)
            snapshot_hash = secure_tree_hash(destination)
        except (OSError, UnsafePathError, UnicodeError, ValueError):
            return _EMPTY_SHA256, {
                "id": "submission-shape",
                "status": "failed",
                "score": 0.0,
                "maximum": 10.0,
                "message": "submission is not a safe task-scoped C# source snapshot",
            }
        return snapshot_hash, {
            "id": "submission-shape",
            "status": "passed",
            "score": 10.0,
            "maximum": 10.0,
            "message": "submission source was snapshotted for evaluation",
        }

    @staticmethod
    def _public_result(
        *,
        evaluation_id: str,
        static_check: dict[str, Any],
        complete: bool,
        passed: bool,
        runtime_status: str,
        message: str,
        runtime_log: str,
        case_outcomes: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        engine_check = {
            "id": "real-game",
            "status": "passed" if passed else "failed" if complete else "incomplete",
            "score": 90.0 if passed else 0.0,
            "maximum": 90.0,
            "message": message,
        }
        return {
            "score": 100.0 if passed else float(static_check["score"]),
            "complete": complete,
            "passed": passed,
            "checks": [static_check, engine_check],
            "evaluationId": evaluation_id,
            "runtime": {
                "status": runtime_status,
                "engineAssertionsRan": complete,
                # Name-level pass/fail for the operator, only for a complete verdict; the
                # plugin strips it from anonymous results. Messages stay private.
                "caseOutcomes": dict(case_outcomes or {}) if complete else {},
            },
            "runtime_log": runtime_log[-200_000:],
        }

    def evaluate(
        self,
        submission: Path,
        task: RimWorldTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported RimWorld evaluation profile: {profile}")
        if not isinstance(task, RimWorldTask):
            raise TypeError("RimWorld evaluator received a non-RimWorld task")

        evaluation_id = f"evaluation-{uuid.uuid4().hex[:24]}"
        nonce = uuid.uuid4().hex + uuid.uuid4().hex[:16]
        task_key = self._task_key(self.context.pack_root, task)
        assertions = assertion_manifest(self.context.pack_root, task)
        identity = self._base_identity(task, assertions)
        evidence_dir = self.context.state_dir / "evaluations" / evaluation_id
        ensure_directory_nofollow(evidence_dir)
        snapshot = evidence_dir / "submission"
        submission_hash, static_check = self._snapshot_submission(submission, task, snapshot)
        identity["submission"] = submission_hash

        def finish_incomplete(
            *, message: str, runtime_status: str, fatal: str, runtime_log: str
        ) -> dict[str, Any]:
            verdict = incomplete_verdict(
                assertions=assertions,
                evaluation_id=evaluation_id,
                nonce=nonce,
                task_key=task_key,
                fatal=fatal,
                identity=identity,
            )
            encoded = encode_private_verdict(verdict)
            validate_private_verdict(encoded, assertions)
            write_owner_file(evidence_dir / "result.private.json", encoded)
            return self._public_result(
                evaluation_id=evaluation_id,
                static_check=static_check,
                complete=False,
                passed=False,
                runtime_status=runtime_status,
                message=message,
                runtime_log=runtime_log,
            )

        if static_check["status"] != "passed":
            return finish_incomplete(
                message="real-game assertions did not run for an invalid submission",
                runtime_status="failed",
                fatal="INVALID_SUBMISSION",
                runtime_log="submission snapshot validation failed\n",
            )
        if profile == "core":
            return finish_incomplete(
                message="real-game assertions are disabled in the core profile",
                runtime_status="skipped",
                fatal="CORE_PROFILE",
                runtime_log="RimWorld runtime did not run\n",
            )

        artifact = (runtimes or {}).get(RUNTIME_KEY)
        if artifact is None:
            return finish_incomplete(
                message="managed RimWorld runtime is not prepared",
                runtime_status="unavailable",
                fatal="RUNTIME_UNAVAILABLE",
                runtime_log=f"run rhenium runtime prepare {RUNTIME_KEY}\n",
            )
        try:
            status = self.runtime.status()
            if not bool(status.get("available", False)):
                raise RuntimeError("Docker host is unavailable")
            runtime_catalog = RuntimeCatalog.load(self.context.pack_root, "runtimes.json")
            spec = next((item for item in runtime_catalog.runtimes if item.id == RUNTIME_ID), None)
            if spec is None:
                raise ValueError("RimWorld runtime specification is missing")
            from .runtime_builder import RimWorldRuntimeBuilder

            builder = RimWorldRuntimeBuilder(self.context, self.catalog)
            builder.runtime = self.runtime
            verification = builder.verify(spec, artifact)
            if not bool(verification.get("available", False)):
                raise RuntimeError("runtime artifact verification failed")
            images, evidence = builder.artifact_task_images(spec, artifact, task_key)
            identity.update(
                {
                    "runtimeFingerprint": "sha256:" + artifact.fingerprint,
                    "runtimeArtifact": artifact.identity,
                    "builderImage": images["builder"],
                    "evaluatorImage": images["evaluator"],
                    "buildEvidence": evidence["build"],
                    "adapterEvidence": evidence["adapter"],
                    "sourceEvidence": evidence["source"],
                }
            )
            execution = self.runtime.execute(
                task,
                snapshot=snapshot,
                evidence_dir=evidence_dir,
                images=images,
                evaluation_id=evaluation_id,
                nonce=nonce,
                task_key=task_key,
                submission_hash=submission_hash,
            )
            write_owner_file(
                evidence_dir / "runtime.private.log",
                execution.runtime_log.encode("utf-8", errors="replace"),
            )
            identity["candidateAssembly"] = execution.candidate_assembly
            identity["adapterAssembly"] = execution.adapter_assembly
            if execution.build_process.returncode != 0 or execution.engine_process is None:
                return finish_incomplete(
                    message="real-game assertions did not start",
                    runtime_status="incomplete",
                    fatal="BUILD_FAILED",
                    runtime_log=build_failure_log(execution.runtime_log),
                )
            verdict = collect_observations(
                execution.observation,
                assertions=assertions,
                evaluation_id=evaluation_id,
                nonce=nonce,
                task_key=task_key,
                process_status=execution.engine_process.returncode,
                player_log=execution.player_log,
                identity=identity,
            )
            encoded = encode_private_verdict(verdict)
            checked = validate_private_verdict(encoded, assertions)
            write_owner_file(evidence_dir / "result.private.json", encoded)
        except (
            EvidenceError,
            FileNotFoundError,
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            UnsafePathError,
            TypeError,
            ValueError,
        ) as error:
            with suppress(OSError):
                write_owner_file(
                    evidence_dir / "failure.private.txt",
                    (f"{type(error).__name__}: {error}\n").encode(),
                )
            return finish_incomplete(
                message="real-game evidence failed integrity validation",
                runtime_status="incomplete",
                fatal="INTEGRITY_FAILURE",
                runtime_log="RimWorld evaluation evidence failed integrity validation\n",
            )

        complete = checked["complete"] is True
        passed = complete and checked["reward"] == 1
        case_outcomes = {
            str(case["id"]): case["status"] == "passed" for case in checked["cases"]
        }
        return self._public_result(
            evaluation_id=evaluation_id,
            static_check=static_check,
            complete=complete,
            passed=passed,
            runtime_status="passed" if passed else "failed" if complete else "incomplete",
            message=(
                "all required real-game assertions passed"
                if passed
                else "one or more required real-game assertions failed"
                if complete
                else "real-game assertions did not complete"
            ),
            runtime_log="RimWorld evaluation finished; private evidence was recorded\n",
            case_outcomes=case_outcomes,
        )
