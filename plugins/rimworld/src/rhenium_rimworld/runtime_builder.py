from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .assertions import generated_dispatch_source, load_assertion_manifest
from .catalog import RimWorldCatalog, RimWorldTask
from .evaluator import (
    _DOCKER_TIMEOUT,
    IMAGE_ROLES,
    RUNTIME_ADAPTER_LABEL,
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID,
    RUNTIME_ID_LABEL,
    RUNTIME_ROLE_LABEL,
    RUNTIME_RUBRIC_LABEL,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_SOURCE_TREE_LABEL,
    RUNTIME_TASK_LABEL,
    RUNTIME_TASK_SOURCE_LABEL,
    RUNTIME_TOOLCHAIN_LABEL,
    SDK_IMAGE,
    RimWorldRuntime,
)
from .safe_files import (
    UnsafePathError,
    ensure_directory_nofollow,
    secure_copy_file,
    secure_copy_tree,
    secure_file_mode,
    secure_file_sha256,
    secure_read_bytes,
    secure_tree_hash,
    write_owner_file,
)
from .supervisor import strict_json_object

_PLUGIN_ID = "rimworld"
_PLUGIN_VERSION = "0.6.0"
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_IDENTITY = re.compile(
    r"^steam:294100/294103@3402513235443928324;"
    r"version-sha256=[0-9a-f]{64};source=sha256:[0-9a-f]{64}$"
)
_LAUNCHER = "RimWorldLinux"
_SOURCE_FILES = (_LAUNCHER, "UnityPlayer.so", "Version.txt")
_SOURCE_DIRECTORIES = ("Data/Core", "RimWorldLinux_Data")
_COMMON_ADAPTER_FILES = (
    "tests/Submission.csproj",
    "tests/Support.cs",
    "tests/packages.lock.json",
    "tests/build.sh",
    "tests/test.sh",
    "tests/ModsConfig.xml",
    "tests/Harness/Harness.csproj",
    "tests/Harness/Verifier.cs",
    "tests/Harness/packages.lock.json",
    "tests/ModMetadata/Verifier/About.xml",
)
_EXPECTED_TYPES = {
    "RimWorldLinux": "file",
    "UnityPlayer.so": "file",
    "Version.txt": "file",
    "Data/Core/About/About.xml": "file",
    "RimWorldLinux_Data/Managed/Assembly-CSharp.dll": "file",
    "RimWorldLinux_Data/Managed/UnityEngine.CoreModule.dll": "file",
}


class RimWorldRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: RimWorldCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = RimWorldRuntime(context, catalog)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        self._source_policy(spec)
        return self.runtime.status()

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=_PLUGIN_ID, plugin_version=_PLUGIN_VERSION)

    @staticmethod
    def _artifact_identity(
        images: dict[str, dict[str, str]], evidence: dict[str, dict[str, str]]
    ) -> str:
        payload = json.dumps(
            {"images": images, "evidence": evidence},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"sha256:{hashlib.sha256(payload).hexdigest()}"

    @staticmethod
    def _source_policy(spec: RuntimeSpec) -> tuple[tuple[str, ...], dict[str, str], str]:
        expected_raw = spec.source.get("expectedFiles")
        if not isinstance(expected_raw, list) or not expected_raw:
            raise ValueError("Steam runtime must declare expectedFiles")
        expected: list[str] = []
        for raw in expected_raw:
            if not isinstance(raw, str):
                raise ValueError("Steam runtime expectedFiles must contain strings")
            path = PurePosixPath(raw)
            if not raw or path.is_absolute() or ".." in path.parts or raw != path.as_posix():
                raise ValueError("Steam runtime expectedFiles must be normalized relative paths")
            expected.append(raw)
        if len(expected) != len(set(expected)):
            raise ValueError("Steam runtime expectedFiles must be unique")
        if set(expected) != set(_EXPECTED_TYPES):
            raise ValueError("Steam runtime expectedFiles do not match the reviewed source policy")

        hashes_raw = spec.source.get("sha256", {})
        if not isinstance(hashes_raw, dict):
            raise ValueError("Steam runtime sha256 must be an object")
        hashes: dict[str, str] = {}
        for raw_path, raw_digest in hashes_raw.items():
            if not isinstance(raw_path, str) or not isinstance(raw_digest, str):
                raise ValueError("Steam runtime sha256 entries must map paths to strings")
            path = PurePosixPath(raw_path)
            if (
                not raw_path
                or path.is_absolute()
                or ".." in path.parts
                or raw_path != path.as_posix()
                or _SHA256.fullmatch(raw_digest) is None
                or raw_path not in _EXPECTED_TYPES
            ):
                raise ValueError("Steam runtime sha256 entry is invalid")
            hashes[raw_path] = raw_digest

        depots = spec.source.get("depots")
        if (
            spec.source.get("kind") != "steam-depots"
            or spec.source.get("appId") != 294100
            or spec.source.get("os") != "linux"
            or depots != [{"id": 294103, "manifest": "3402513235443928324"}]
        ):
            raise ValueError("RimWorld runtime source is not the pinned Linux Steam manifest")
        return (
            tuple(expected),
            hashes,
            "steam:294100/294103@3402513235443928324",
        )

    @classmethod
    def _validate_source(cls, spec: RuntimeSpec, source: Path) -> tuple[str, str]:
        expected, hashes, base_identity = cls._source_policy(spec)
        for relative in expected:
            try:
                secure_file_mode(source, relative)
            except (OSError, UnsafePathError) as error:
                raise RuntimeError(
                    f"Steam acquisition is missing expected RimWorld file: {relative}"
                ) from error
            expected_digest = hashes.get(relative)
            if expected_digest is not None and secure_file_sha256(
                source, relative, maximum=2_000_000_000
            ) != expected_digest:
                raise RuntimeError(f"Steam acquisition SHA-256 mismatch: {relative}")
        version_bytes = secure_read_bytes(source, "Version.txt", maximum=4096)
        try:
            version = version_bytes.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError as error:
            raise RuntimeError("Steam acquisition has an invalid RimWorld Version.txt") from error
        if not version or version.split()[0] != "1.6.4871":
            raise RuntimeError("Steam acquisition is not RimWorld 1.6.4871")
        # A Steam depot carries no POSIX mode, so the acquisition never has an executable
        # launcher; the build context restores that bit instead of demanding it here.
        version_hash = hashlib.sha256(version_bytes).hexdigest()
        return base_identity, version_hash

    @staticmethod
    def _task_key(pack_root: Path, task: RimWorldTask) -> str:
        manifest = strict_json_object(
            secure_read_bytes(pack_root, "benchmark.json", maximum=100_000), maximum=100_000
        )
        pack_id = manifest.get("pack_id")
        if manifest.get("plugin") != _PLUGIN_ID or not isinstance(pack_id, str):
            raise ValueError("RimWorld benchmark manifest has an invalid identity")
        return f"{_PLUGIN_ID}/{pack_id}/{task.id}"

    def _stage_build_context(
        self,
        task: RimWorldTask,
        source: Path,
        destination: Path,
    ) -> tuple[str, str, str, str, str]:
        task_root = self.context.pack_root / "private" / "harbor" / task.id
        secure_copy_file(
            task_root / "environment",
            "Dockerfile",
            destination,
            destination_relative="Dockerfile",
            maximum=1_000_000,
        )
        for relative in (*_COMMON_ADAPTER_FILES, task.mod_metadata_path, *task.runtime_data_files):
            secure_copy_file(
                task_root,
                relative,
                destination,
                maximum=2_000_000,
            )
        assertions = load_assertion_manifest(self.context.pack_root, task.id)
        write_owner_file(
            destination / "tests" / "Harness" / "GeneratedAssertions.cs",
            generated_dispatch_source(assertions),
        )
        adapter_evidence = self._adapter_evidence(task_root, task)
        rubric_evidence = assertions.rubric_hash()
        task_source_evidence = secure_tree_hash(
            task_root / "environment" / task.starter_root
        )
        game_destination = destination / "game-files"
        ensure_directory_nofollow(game_destination)
        for relative in _SOURCE_FILES:
            secure_copy_file(
                source,
                relative,
                game_destination,
                maximum=2_000_000_000,
            )
        launcher = game_destination / _LAUNCHER
        launcher.chmod(launcher.stat().st_mode | 0o111)
        for relative in _SOURCE_DIRECTORIES:
            secure_copy_tree(source / relative, game_destination / relative)
        source_evidence = secure_tree_hash(game_destination)
        build_evidence = self._combined_evidence(
            adapter_evidence,
            source_evidence,
            rubric_evidence,
            task_source_evidence,
        )
        return (
            build_evidence,
            adapter_evidence,
            source_evidence,
            rubric_evidence,
            task_source_evidence,
        )

    @staticmethod
    def _combined_evidence(
        adapter_evidence: str,
        source_evidence: str,
        rubric_evidence: str,
        task_source_evidence: str,
    ) -> str:
        raw = json.dumps(
            {
                "adapter": adapter_evidence,
                "rubric": rubric_evidence,
                "runtimeSource": source_evidence,
                "taskSource": task_source_evidence,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"sha256:{hashlib.sha256(raw).hexdigest()}"

    @staticmethod
    def _adapter_evidence(task_root: Path, task: RimWorldTask) -> str:
        assertions_raw = secure_read_bytes(
            task_root,
            "tests/assertions.json",
            maximum=1_000_000,
        )
        assertions = load_assertion_manifest(task_root.parents[2], task.id)
        inputs: dict[str, dict[str, str | int]] = {}
        for relative in (
            "environment/Dockerfile",
            *_COMMON_ADAPTER_FILES,
            task.mod_metadata_path,
            *task.runtime_data_files,
        ):
            data = secure_read_bytes(task_root, relative, maximum=2_000_000)
            mode = secure_file_mode(task_root, relative)
            inputs[relative] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "mode": 0o755 if mode & 0o111 else 0o644,
            }
        generated = generated_dispatch_source(assertions)
        inputs["tests/Harness/GeneratedAssertions.cs"] = {
            "sha256": hashlib.sha256(generated).hexdigest(),
            "mode": 0o644,
        }
        raw = json.dumps(
            {
                "inputs": inputs,
                "privateAssertions": hashlib.sha256(assertions_raw).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"sha256:{hashlib.sha256(raw).hexdigest()}"

    def _current_adapter_evidence(self, task: RimWorldTask) -> str:
        task_root = self.context.pack_root / "private" / "harbor" / task.id
        return self._adapter_evidence(task_root, task)

    def _expected_labels(
        self,
        spec: RuntimeSpec,
        task: RimWorldTask,
        *,
        role: str,
        source_identity: str,
        evidence: dict[str, str],
    ) -> dict[str, str]:
        return {
            RUNTIME_FINGERPRINT_LABEL: self._fingerprint(spec),
            RUNTIME_SOURCE_LABEL: source_identity,
            RUNTIME_TASK_LABEL: self._task_key(self.context.pack_root, task),
            RUNTIME_ID_LABEL: RUNTIME_ID,
            RUNTIME_BUILD_LABEL: evidence["build"],
            RUNTIME_ROLE_LABEL: role,
            RUNTIME_ADAPTER_LABEL: evidence["adapter"],
            RUNTIME_SOURCE_TREE_LABEL: evidence["source"],
            RUNTIME_RUBRIC_LABEL: evidence["rubric"],
            RUNTIME_TASK_SOURCE_LABEL: evidence["taskSource"],
            RUNTIME_TOOLCHAIN_LABEL: SDK_IMAGE,
        }

    def _artifact_data(
        self, spec: RuntimeSpec, artifact: RuntimeArtifact
    ) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], str]:
        if artifact.runtime_key != f"{_PLUGIN_ID}/{spec.id}":
            raise ValueError("runtime artifact has the wrong runtime key")
        if artifact.fingerprint != self._fingerprint(spec):
            raise ValueError("runtime artifact has a stale fingerprint")
        if artifact.kind != "docker-image-roles":
            raise ValueError("runtime artifact has the wrong kind")
        if set(artifact.metadata) != {
            "images",
            "evidence",
            "network",
            "runtime",
            "sourceIdentity",
            "engineLaunchValidated",
        }:
            raise ValueError("runtime artifact metadata has an invalid shape")
        if artifact.metadata.get("runtime") != RUNTIME_ID:
            raise ValueError("runtime artifact has the wrong runtime ID")
        if (
            artifact.metadata.get("network") != "none"
            or artifact.metadata.get("engineLaunchValidated") is not False
        ):
            raise ValueError("runtime artifact has invalid execution claims")
        source_identity = artifact.metadata.get("sourceIdentity")
        if not isinstance(source_identity, str) or _SOURCE_IDENTITY.fullmatch(source_identity) is None:
            raise ValueError("runtime artifact has an invalid source identity")
        images_raw = artifact.metadata.get("images")
        evidence_raw = artifact.metadata.get("evidence")
        task_ids = {task.id for task in self.catalog.tasks}
        if not isinstance(images_raw, dict) or set(images_raw) != task_ids:
            raise ValueError("runtime artifact has an incomplete image set")
        if not isinstance(evidence_raw, dict) or set(evidence_raw) != task_ids:
            raise ValueError("runtime artifact has incomplete build evidence")
        images: dict[str, dict[str, str]] = {}
        evidence: dict[str, dict[str, str]] = {}
        for task_id in task_ids:
            task_images = images_raw.get(task_id)
            task_evidence = evidence_raw.get(task_id)
            if (
                not isinstance(task_images, dict)
                or set(task_images) != set(IMAGE_ROLES)
                or any(
                    not isinstance(value, str) or _IMAGE_ID.fullmatch(value) is None
                    for value in task_images.values()
                )
            ):
                raise ValueError("runtime artifact has malformed role image IDs")
            if (
                not isinstance(task_evidence, dict)
                or set(task_evidence)
                != {"build", "adapter", "source", "rubric", "taskSource"}
                or any(
                    not isinstance(value, str)
                    or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
                    for value in task_evidence.values()
                )
            ):
                raise ValueError("runtime artifact has malformed build evidence")
            images[task_id] = dict(task_images)
            evidence[task_id] = dict(task_evidence)
        if artifact.identity != self._artifact_identity(images, evidence):
            raise ValueError("runtime artifact identity does not match its images and evidence")
        return images, evidence, source_identity

    def artifact_task_images(
        self,
        spec: RuntimeSpec,
        artifact: RuntimeArtifact,
        task_key: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        images, evidence, _source_identity = self._artifact_data(spec, artifact)
        task_id = task_key.rsplit("/", 1)[-1]
        task = next((item for item in self.catalog.tasks if item.id == task_id), None)
        if task is None or self._task_key(self.context.pack_root, task) != task_key:
            raise ValueError("runtime artifact request has the wrong canonical task key")
        return images[task_id], evidence[task_id]

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        base_source_identity, version_hash = self._validate_source(spec, source)
        ensure_directory_nofollow(destination)
        fingerprint = self._fingerprint(spec)
        images: dict[str, dict[str, str]] = {}
        evidence: dict[str, dict[str, str]] = {}
        total = len(self.catalog.tasks) * len(IMAGE_ROLES)
        completed = 0
        with tempfile.TemporaryDirectory(prefix="rimworld-build-", dir=destination) as raw_staging:
            staging_root = Path(raw_staging)
            for task in self.catalog.tasks:
                task_context = staging_root / task.id
                ensure_directory_nofollow(task_context)
                (
                    build_hash,
                    adapter_hash,
                    source_hash,
                    rubric_hash,
                    task_source_hash,
                ) = self._stage_build_context(task, source, task_context)
                staged_base_identity, staged_version_hash = self._validate_source(
                    spec, task_context / "game-files"
                )
                if (
                    staged_base_identity != base_source_identity
                    or staged_version_hash != version_hash
                ):
                    raise RuntimeError("RimWorld source changed while it was being staged")
                task_evidence = {
                    "build": build_hash,
                    "adapter": adapter_hash,
                    "source": source_hash,
                    "rubric": rubric_hash,
                    "taskSource": task_source_hash,
                }
                evidence[task.id] = task_evidence
                source_identity = (
                    f"{base_source_identity};version-sha256={version_hash};source={source_hash}"
                )
                task_key = self._task_key(self.context.pack_root, task)
                task_images: dict[str, str] = {}
                for role in IMAGE_ROLES:
                    progress(int(completed * 100 / total), f"building {role} image for {task.id}")
                    _tag, image_id, _log = self.runtime.build_image(
                        task,
                        build_context=task_context,
                        role=role,
                        fingerprint=fingerprint,
                        source_identity=source_identity,
                        task_key=task_key,
                        build_evidence=build_hash,
                        adapter_evidence=adapter_hash,
                        source_evidence=source_hash,
                        rubric_evidence=rubric_hash,
                        task_source_evidence=task_source_hash,
                    )
                    task_images[role] = image_id
                    completed += 1
                images[task.id] = task_images
        source_hashes = {item["source"] for item in evidence.values()}
        if len(source_hashes) != 1:
            raise RuntimeError("RimWorld task images were built from different source snapshots")
        source_identity = (
            f"{base_source_identity};version-sha256={version_hash};source={next(iter(source_hashes))}"
        )
        progress(100, "RimWorld evaluator image roles ready")
        return RuntimeArtifact(
            runtime_key=f"{_PLUGIN_ID}/{spec.id}",
            fingerprint=fingerprint,
            kind="docker-image-roles",
            identity=self._artifact_identity(images, evidence),
            metadata={
                "images": images,
                "evidence": evidence,
                "network": "none",
                "runtime": RUNTIME_ID,
                "sourceIdentity": source_identity,
                "engineLaunchValidated": False,
            },
        )

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            status = self.runtime.status()
            if not bool(status.get("available", False)):
                raise RuntimeError(str(status.get("reason") or "Docker host is unavailable"))
            images, evidence, source_identity = self._artifact_data(spec, artifact)
            for task in self.catalog.tasks:
                if evidence[task.id]["adapter"] != self._current_adapter_evidence(task):
                    raise RuntimeError(
                        f"runtime artifact does not match current pack inputs: {task.id}"
                    )
                manifest = load_assertion_manifest(self.context.pack_root, task.id)
                expected_task_source = secure_tree_hash(
                    self.context.pack_root
                    / "private"
                    / "harbor"
                    / task.id
                    / "environment"
                    / task.starter_root
                )
                if (
                    evidence[task.id]["rubric"] != manifest.rubric_hash()
                    or evidence[task.id]["taskSource"] != expected_task_source
                ):
                    raise RuntimeError(
                        f"runtime artifact does not match current task evidence: {task.id}"
                    )
                if evidence[task.id]["build"] != self._combined_evidence(
                    evidence[task.id]["adapter"],
                    evidence[task.id]["source"],
                    evidence[task.id]["rubric"],
                    evidence[task.id]["taskSource"],
                ):
                    raise RuntimeError(f"runtime artifact build evidence is invalid: {task.id}")
                for role, image_id in images[task.id].items():
                    if self.runtime.image_id(image_id) != image_id:
                        raise RuntimeError(f"evaluator image has a mutable identity: {task.id}/{role}")
                    image_os, image_arch = self.runtime.image_platform(image_id)
                    if image_os != "linux" or image_arch not in {"amd64", "x86_64"}:
                        raise RuntimeError(
                            f"evaluator image is not Linux x86_64: {task.id}/{role}"
                        )
                    labels = self.runtime.image_labels(image_id)
                    expected = self._expected_labels(
                        spec,
                        task,
                        role=role,
                        source_identity=source_identity,
                        evidence=evidence[task.id],
                    )
                    if set(labels).issuperset(expected) is False or any(
                        labels.get(key) != value for key, value in expected.items()
                    ):
                        raise RuntimeError(f"evaluator image labels do not match: {task.id}/{role}")
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        return {
            "available": True,
            "imageCount": sum(len(task_images) for task_images in images.values()),
            "roles": list(IMAGE_ROLES),
            "network": "none",
            "identity": artifact.identity,
            "engineLaunchValidated": False,
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        images, evidence, source_identity = self._artifact_data(spec, artifact)
        owned: list[tuple[str, str, str]] = []
        for task in self.catalog.tasks:
            for role, image_id in images[task.id].items():
                try:
                    inspected_id = self.runtime.image_id(image_id)
                except FileNotFoundError:
                    continue
                if inspected_id != image_id:
                    raise RuntimeError(
                        f"refusing to prune a mutable image reference: {task.id}/{role}"
                    )
                labels = self.runtime.image_labels(image_id)
                expected = self._expected_labels(
                    spec,
                    task,
                    role=role,
                    source_identity=source_identity,
                    evidence=evidence[task.id],
                )
                if any(labels.get(key) != value for key, value in expected.items()):
                    raise RuntimeError(
                        f"refusing to prune an unowned evaluator image: {task.id}/{role}"
                    )
                owned.append((task.id, role, image_id))
        for task_id, role, image_id in owned:
            removed = self.runtime._docker(["image", "rm", image_id], timeout=_DOCKER_TIMEOUT)
            if removed.returncode != 0:
                raise RuntimeError(f"failed to prune evaluator image: {task_id}/{role}")
