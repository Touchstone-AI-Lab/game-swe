from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import SlayTheSpireCatalog
from .container import (
    PLUGIN_ID,
    PLUGIN_VERSION,
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID,
    RUNTIME_ID_LABEL,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_TASK_LABEL,
    SlayTheSpireRuntime,
)


class SlayTheSpireRuntimeBuilder(RuntimeBuilder):
    """Builds one evaluator image per task from the pinned public base image."""

    def __init__(self, context: BenchmarkContext, catalog: SlayTheSpireCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = SlayTheSpireRuntime(context, catalog)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        report = dict(self.runtime.status())
        try:
            reference, _expected = self._source_policy(spec)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        report["sourceImage"] = reference
        report["taskCount"] = len(self.catalog.container_tasks)
        return report

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=PLUGIN_ID, plugin_version=PLUGIN_VERSION)

    @staticmethod
    def _artifact_identity(images: dict[str, str]) -> str:
        digest = hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in sorted(images.items())).encode()
        ).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def _source_policy(spec: RuntimeSpec) -> tuple[str, tuple[str, ...]]:
        reference = spec.source.get("image")
        if not isinstance(reference, str) or not reference:
            raise ValueError("container runtime source does not declare an image")
        if "@sha256:" not in reference:
            raise ValueError("container runtime source image must be digest-pinned")
        raw_expected = spec.source.get("expectedFiles", [])
        if not isinstance(raw_expected, list) or any(not isinstance(value, str) for value in raw_expected):
            raise ValueError("container runtime expectedFiles must be a list of paths")
        expected: list[str] = []
        for value in raw_expected:
            path = PurePosixPath(value)
            if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
                raise ValueError("container runtime expectedFiles paths must be normalized and relative")
            expected.append(value)
        if len(expected) != len(set(expected)):
            raise ValueError("container runtime expectedFiles paths must be unique")
        return reference, tuple(expected)

    def _validate_source(self, spec: RuntimeSpec, source: Path) -> tuple[str, str]:
        reference, expected_files = self._source_policy(spec)
        record_path = source / "image.json"
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("container provider did not record a valid pinned image") from error
        if not isinstance(record, dict) or record.get("schemaVersion") != 1:
            raise RuntimeError("container provider image record has an unsupported schema")
        if record.get("image") != reference:
            raise RuntimeError("container provider image record does not match the runtime source")
        image_id = record.get("imageId")
        if not isinstance(image_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
            raise RuntimeError("container provider image record has an invalid immutable image ID")
        repo_digests = record.get("repoDigests")
        expected_digest = reference.partition("@")[2]
        if not isinstance(repo_digests, list) or not any(
            isinstance(value, str) and value.endswith(expected_digest) for value in repo_digests
        ):
            raise RuntimeError("container provider image record does not contain the pinned digest")
        self.runtime.validate_source_image(reference, image_id, expected_files)
        return reference, image_id

    def _artifact_images(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, str]:
        fingerprint = self._fingerprint(spec)
        if artifact.runtime_key != f"{PLUGIN_ID}/{spec.id}":
            raise ValueError("runtime artifact has the wrong runtime key")
        if artifact.fingerprint != fingerprint:
            raise ValueError("runtime artifact has a stale fingerprint")
        if artifact.kind != "docker-images":
            raise ValueError("runtime artifact has the wrong kind")
        reference, _expected_files = self._source_policy(spec)
        if artifact.metadata.get("runtime") != RUNTIME_ID:
            raise ValueError("runtime artifact has the wrong runtime ID")
        if artifact.metadata.get("sourceImage") != reference:
            raise ValueError("runtime artifact has the wrong source image")
        images = artifact.metadata.get("images")
        task_ids = {task.id for task in self.catalog.container_tasks}
        if (
            not isinstance(images, dict)
            or set(images) != task_ids
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in images.items())
        ):
            raise ValueError("runtime artifact has an incomplete image set")
        typed_images = dict(images)
        if artifact.identity != self._artifact_identity(typed_images):
            raise ValueError("runtime artifact identity does not match its image set")
        return typed_images

    def _expected_labels(self, spec: RuntimeSpec, task_id: str) -> dict[str, str]:
        reference, _expected_files = self._source_policy(spec)
        task = next((item for item in self.catalog.container_tasks if item.id == task_id), None)
        if task is None:
            raise ValueError(f"runtime artifact references an unknown task: {task_id}")
        return {
            RUNTIME_FINGERPRINT_LABEL: self._fingerprint(spec),
            RUNTIME_SOURCE_LABEL: reference,
            RUNTIME_TASK_LABEL: task_id,
            RUNTIME_ID_LABEL: RUNTIME_ID,
            RUNTIME_BUILD_LABEL: self.runtime.build_context_fingerprint(task),
        }

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: Any
    ) -> RuntimeArtifact:
        del destination
        source_reference, source_image_id = self._validate_source(spec, source)
        fingerprint = self._fingerprint(spec)
        images: dict[str, str] = {}
        tasks = self.catalog.container_tasks
        total = len(tasks)
        for index, task in enumerate(tasks, 1):
            progress(int((index - 1) * 100 / total), f"building evaluator image for {task.id}")
            _tag, image_id, _log = self.runtime.build_image(
                task, source_reference=source_reference, fingerprint=fingerprint
            )
            images[task.id] = image_id
        progress(100, "Slay the Spire evaluator images ready")
        return RuntimeArtifact(
            runtime_key=f"{PLUGIN_ID}/{spec.id}",
            fingerprint=fingerprint,
            kind="docker-images",
            identity=self._artifact_identity(images),
            metadata={
                "images": images,
                "network": "none",
                "runtime": RUNTIME_ID,
                "sourceImage": source_reference,
                "sourceImageId": source_image_id,
            },
        )

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            images = self._artifact_images(spec, artifact)
            for task_id, image_id in images.items():
                if self.runtime.image_id(image_id) != image_id:
                    raise RuntimeError(f"evaluator image has a mutable identity: {task_id}")
                labels = self.runtime.image_labels(image_id)
                expected = self._expected_labels(spec, task_id)
                if any(labels.get(key) != value for key, value in expected.items()):
                    raise RuntimeError(f"evaluator image labels do not match: {task_id}")
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        return {
            "available": True,
            "imageCount": len(images),
            "network": "none",
            "identity": artifact.identity,
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        images = self._artifact_images(spec, artifact)
        owned: list[tuple[str, str]] = []
        for task_id, image_id in images.items():
            inspected = self.runtime._docker(
                ["image", "inspect", image_id, "--format", "{{.Id}}"], timeout=10
            )
            if inspected.returncode != 0:
                continue
            if inspected.stdout.strip() != image_id:
                raise RuntimeError(f"refusing to prune a mutable image reference: {task_id}")
            labels = self.runtime.image_labels(image_id)
            expected = self._expected_labels(spec, task_id)
            if any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"refusing to prune an unowned evaluator image: {task_id}")
            owned.append((task_id, image_id))
        for task_id, image_id in owned:
            removed = self.runtime._docker(["image", "rm", image_id], timeout=120)
            if removed.returncode != 0:
                log = (removed.stdout + removed.stderr)[-4000:]
                raise RuntimeError(f"failed to prune evaluator image: {task_id}\n{log}")
