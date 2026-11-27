from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, NoReturn

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import MindustryCatalog, MindustryTask
from .container import (
    BASE_IMAGE_REFERENCE,
    BASE_TAG,
    BASE_TASK_LABEL,
    MINDUSTRY_VERSION,
    RELEASE_TAG,
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID,
    RUNTIME_ID_LABEL,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_TASK_LABEL,
    SERVER_JAR,
    MindustryContainerRuntime,
    runtime_key,
)

_PLUGIN_ID = "mindustry"
_PLUGIN_VERSION = "0.6.0"
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
# Image builds run on a possibly shared, congested Docker daemon; give each one room.
_BUILD_TIMEOUT = 7200


class MindustryRuntimeBuilder(RuntimeBuilder):
    """Builds the pinned Mindustry verifier base image and one verifier image per task.

    The official-download provider acquires the pinned server jar from the Mindustry
    release; the pack only holds the Dockerfile, the bootstrap scripts and the harness
    sources. The base image installs its packages with network once; evaluation runs
    offline.
    """

    def __init__(self, context: BenchmarkContext, catalog: MindustryCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = MindustryContainerRuntime()

    @property
    def runtime_root(self) -> Path:
        return self.context.pack_root / "private" / "runtime"

    @property
    def harness_root(self) -> Path:
        return self.context.pack_root / "private" / "harbor" / "harness" / "rhenium-harness"

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=_PLUGIN_ID, plugin_version=_PLUGIN_VERSION)

    @staticmethod
    def _tree_fingerprint(root: Path) -> str:
        digest = hashlib.sha256()
        for candidate in sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()):
            if candidate.is_symlink():
                raise RuntimeError("runtime build context contains a symbolic link")
            if "__pycache__" in candidate.relative_to(root).parts:
                continue
            relative = candidate.relative_to(root).as_posix().encode()
            mode = str(stat.S_IMODE(candidate.stat().st_mode)).encode()
            if candidate.is_dir():
                digest.update(b"directory\0" + relative + b"\0" + mode + b"\0")
            elif candidate.is_file():
                digest.update(b"file\0" + relative + b"\0" + mode + b"\0")
                digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            else:
                raise RuntimeError("runtime build context contains an unsupported input type")
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _pinned_digest(spec: RuntimeSpec) -> str:
        if spec.id != RUNTIME_ID:
            raise ValueError("unsupported Mindustry runtime id")
        if spec.source.get("expectedFiles") != [SERVER_JAR]:
            raise ValueError("Mindustry runtime source must declare exactly the server jar")
        digest = spec.source.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Mindustry runtime requires a pinned server SHA-256")
        return digest

    def _check_source(self, spec: RuntimeSpec, root: Path) -> str:
        """Verify the acquired server jar against the pinned catalog digest."""
        expected = self._pinned_digest(spec)
        jar = root / SERVER_JAR
        if jar.is_symlink() or not jar.is_file():
            raise RuntimeError(f"Mindustry runtime source is missing: {SERVER_JAR}")
        digest = hashlib.sha256(jar.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError("Mindustry server SHA-256 does not match the runtime catalog")
        return digest

    @staticmethod
    def _first_from(dockerfile: Path) -> str:
        if not dockerfile.is_file():
            return ""
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            if line.strip().upper().startswith("FROM "):
                return line.split()[1]
        return ""

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        report: dict[str, Any] = {**self.runtime.status(), "runtimeRoot": str(self.runtime_root)}
        try:
            self._pinned_digest(spec)
        except ValueError as error:
            return {**report, "available": False, "reason": str(error)}
        dockerfile = self.runtime_root / "Dockerfile"
        if not dockerfile.is_file():
            return {**report, "available": False, "reason": "Mindustry runtime Dockerfile is missing"}
        if self._first_from(dockerfile) != BASE_IMAGE_REFERENCE:
            return {**report, "available": False, "reason": "runtime Dockerfile is not digest-pinned"}
        if not any(self.harness_root.rglob("HarnessPlugin.java")):
            return {**report, "available": False, "reason": "Rhenium harness sources are missing"}
        return report

    def _task_context(self, task: MindustryTask) -> Path:
        return self.context.pack_root / "private" / "harbor" / task.id / "tests"

    def _base_build_fingerprint(self, source_digest: str) -> str:
        digest = hashlib.sha256()
        digest.update(self._tree_fingerprint(self.runtime_root).encode() + b"\0")
        digest.update(self._tree_fingerprint(self.harness_root).encode() + b"\0")
        digest.update(source_digest.encode())
        return f"sha256:{digest.hexdigest()}"

    def _labels(
        self, spec: RuntimeSpec, task_label: str, build_fingerprint: str, source_digest: str
    ) -> dict[str, str]:
        return {
            RUNTIME_FINGERPRINT_LABEL: self._fingerprint(spec),
            RUNTIME_SOURCE_LABEL: f"{spec.provider}:{SERVER_JAR}:sha256:{source_digest}",
            RUNTIME_TASK_LABEL: task_label,
            RUNTIME_ID_LABEL: spec.id,
            RUNTIME_BUILD_LABEL: build_fingerprint,
        }

    def _build(
        self, *, tag: str, context: Path, dockerfile: Path, labels: dict[str, str], timeout: float
    ) -> str:
        arguments = ["build", "--platform=linux/amd64", "--pull=false", "--tag", tag]
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(dockerfile), str(context)))
        try:
            result = self.runtime._docker(arguments, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as error:
            self._build_failed(str(error))
        if result.returncode != 0:
            self._build_failed(result.stdout + result.stderr)
        return self.runtime.image_id(tag)

    def _build_failed(self, log: str) -> NoReturn:
        # Build output can name private paths; keep it in restricted local state only.
        directory = self.context.cache_dir / "build-logs"
        try:
            if directory.is_symlink():
                raise OSError("unsafe build log directory")
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = directory / f"build-{uuid.uuid4().hex}.log"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(log[-2_000_000:])
        except OSError:
            raise RuntimeError(
                "Mindustry runtime build failed and its private diagnostics could not be saved"
            ) from None
        raise RuntimeError("failed to build Mindustry runtime image; inspect local build logs") from None

    @staticmethod
    def _artifact_identity(base_image: str, images: dict[str, str]) -> str:
        values = {"base": base_image, **images}
        digest = hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in sorted(values.items())).encode()
        ).hexdigest()
        return f"sha256:{digest}"

    def _stage_base_context(self, source: Path, staging: Path) -> None:
        """Assemble the base build context: pack assets plus the acquired server jar."""
        shutil.copyfile(source / SERVER_JAR, staging / SERVER_JAR)
        ignore = shutil.ignore_patterns("__pycache__")
        shutil.copytree(self.runtime_root, staging / "runtime", ignore=ignore)
        shutil.copytree(self.harness_root, staging / "rhenium-harness", ignore=ignore)
        for candidate in staging.rglob("*"):
            if candidate.is_symlink():
                raise RuntimeError("runtime build context contains a symbolic link")

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: Any
    ) -> RuntimeArtifact:
        del destination
        source_digest = self._check_source(spec, source)
        dockerfile = self.runtime_root / "Dockerfile"
        if self._first_from(dockerfile) != BASE_IMAGE_REFERENCE:
            raise RuntimeError("shared Mindustry Dockerfile is not bound to the pinned JDK image")
        base_fingerprint = self._base_build_fingerprint(source_digest)
        progress(0, f"building pinned Mindustry {RELEASE_TAG} verifier base image")
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="mindustry-runtime-", dir=self.context.cache_dir
        ) as raw_staging:
            staging = Path(raw_staging)
            self._stage_base_context(source, staging)
            base_image = self._build(
                tag=BASE_TAG,
                context=staging,
                dockerfile=staging / "runtime" / "Dockerfile",
                labels=self._labels(spec, BASE_TASK_LABEL, base_fingerprint, source_digest),
                timeout=_BUILD_TIMEOUT,
            )
        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            progress(int(index * 90 / max(total, 1)), f"building verifier image for {task.id}")
            context = self._task_context(task)
            if self._first_from(context / "Dockerfile") != BASE_TAG:
                raise RuntimeError(f"task verifier is not bound to the shared runtime: {task.id}")
            tag = f"rhenium-mindustry:{task.id}-{self._fingerprint(spec)[:12]}"
            images[task.id] = self._build(
                tag=tag,
                context=context,
                dockerfile=context / "Dockerfile",
                labels=self._labels(spec, task.id, self._tree_fingerprint(context), source_digest),
                timeout=_BUILD_TIMEOUT,
            )
        progress(100, "Mindustry evaluator images ready")
        return RuntimeArtifact(
            runtime_key=runtime_key(spec.id),
            fingerprint=self._fingerprint(spec),
            kind="docker-images",
            identity=self._artifact_identity(base_image, images),
            metadata={
                "baseImage": base_image,
                "images": images,
                "network": "none",
                "runtime": spec.id,
                "sourceSha256": source_digest,
                "mindustryVersion": MINDUSTRY_VERSION,
            },
        )

    def _artifact_images(
        self, spec: RuntimeSpec, artifact: RuntimeArtifact
    ) -> tuple[str, dict[str, str], str]:
        if artifact.runtime_key != runtime_key(spec.id):
            raise ValueError("runtime artifact has the wrong runtime key")
        if artifact.fingerprint != self._fingerprint(spec) or artifact.kind != "docker-images":
            raise ValueError("runtime artifact is stale or has the wrong kind")
        base_image = artifact.metadata.get("baseImage")
        images = artifact.metadata.get("images")
        source_digest = artifact.metadata.get("sourceSha256")
        if source_digest != self._pinned_digest(spec):
            raise ValueError("runtime artifact was prepared from a different server jar")
        task_ids = {task.id for task in self.catalog.tasks}
        if not isinstance(base_image, str) or _IMAGE_ID.fullmatch(base_image) is None:
            raise ValueError("runtime artifact has an invalid base image")
        if (
            not isinstance(images, dict)
            or set(images) != task_ids
            or any(
                not isinstance(key, str) or not isinstance(value, str) or _IMAGE_ID.fullmatch(value) is None
                for key, value in images.items()
            )
        ):
            raise ValueError("runtime artifact has an incomplete verifier image set")
        typed_images = dict(images)
        if len({base_image, *typed_images.values()}) != len(typed_images) + 1:
            raise ValueError("runtime artifact reuses an image across distinct verifier roles")
        if artifact.identity != self._artifact_identity(base_image, typed_images):
            raise ValueError("runtime artifact identity does not match its images")
        return base_image, typed_images, str(source_digest)

    def _expected_labels(
        self, spec: RuntimeSpec, base_image: str, images: dict[str, str], source_digest: str
    ) -> list[tuple[str, str, dict[str, str]]]:
        owned = [
            (
                BASE_TASK_LABEL,
                base_image,
                self._labels(
                    spec, BASE_TASK_LABEL, self._base_build_fingerprint(source_digest), source_digest
                ),
            )
        ]
        for task in self.catalog.tasks:
            context = self._task_context(task)
            owned.append(
                (
                    task.id,
                    images[task.id],
                    self._labels(spec, task.id, self._tree_fingerprint(context), source_digest),
                )
            )
        return owned

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            base_image, images, source_digest = self._artifact_images(spec, artifact)
            for _label, image_id, labels in self._expected_labels(spec, base_image, images, source_digest):
                if self.runtime.image_id(image_id) != image_id:
                    raise RuntimeError("runtime artifact contains a mutable image identity")
                observed = self.runtime.image_labels(image_id)
                if any(observed.get(key) != value for key, value in labels.items()):
                    raise RuntimeError("runtime artifact image labels do not match")
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        return {
            "available": True,
            "imageCount": len(images),
            "network": "none",
            "identity": artifact.identity,
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        base_image, images, source_digest = self._artifact_images(spec, artifact)
        owned = self._expected_labels(spec, base_image, images, source_digest)
        for task_label, image_id, expected in owned:
            if self.runtime.image_id(image_id) != image_id:
                raise RuntimeError(f"refusing to prune a mutable image: {task_label}")
            labels = self.runtime.image_labels(image_id)
            if any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"refusing to prune an unowned image: {task_label}")
        for task_label, image_id, _expected in reversed(owned):
            removed = self.runtime._docker(["image", "rm", image_id], timeout=300)
            if removed.returncode != 0:
                raise RuntimeError(f"failed to prune evaluator image: {task_label}")
