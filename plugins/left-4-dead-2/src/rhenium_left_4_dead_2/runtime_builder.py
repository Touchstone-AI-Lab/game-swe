from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import Left4Dead2Catalog, Left4Dead2Task
from .evaluator import (
    BASE_TASK_LABEL,
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID,
    RUNTIME_ID_LABEL,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_TASK_LABEL,
    Left4Dead2Runtime,
)

_PLUGIN_ID = "left-4-dead-2"
_PLUGIN_VERSION = "0.6.0"
_BASE_TAG = "gcb-l4d2-sourcemod-verifier:23990100-sm1.12.7246"


class Left4Dead2RuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: Left4Dead2Catalog):
        self.context = context
        self.catalog = catalog
        self.runtime = Left4Dead2Runtime(context, catalog)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        del spec
        return self.runtime.status()

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=_PLUGIN_ID, plugin_version=_PLUGIN_VERSION)

    @staticmethod
    def _tree_fingerprint(root: Path) -> str:
        digest = hashlib.sha256()
        for candidate in sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()):
            if candidate.is_symlink():
                raise RuntimeError("runtime build context contains a symbolic link")
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
    def _source_policy(spec: RuntimeSpec) -> tuple[str, tuple[str, ...]]:
        reference = spec.source.get("image")
        if not isinstance(reference, str) or re.search(r"@sha256:[0-9a-f]{64}$", reference) is None:
            raise ValueError("container runtime source must declare a digest-pinned image")
        raw_expected = spec.source.get("expectedFiles", [])
        if not isinstance(raw_expected, list) or any(
            not isinstance(value, str) for value in raw_expected
        ):
            raise ValueError("container runtime expectedFiles must be a list of paths")
        expected: list[str] = []
        for value in raw_expected:
            path = PurePosixPath(value)
            if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
                raise ValueError("container runtime expectedFiles paths must be normalized")
            expected.append(value)
        return reference, tuple(expected)

    def _validate_source(self, spec: RuntimeSpec, source: Path) -> tuple[str, str]:
        reference, expected_files = self._source_policy(spec)
        try:
            record = json.loads((source / "image.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("container provider did not record a valid pinned image") from error
        if not isinstance(record, dict) or record.get("schemaVersion") != 1:
            raise RuntimeError("container provider image record has an unsupported schema")
        if record.get("image") != reference:
            raise RuntimeError("container provider image record does not match the runtime source")
        image_id = record.get("imageId")
        if not isinstance(image_id, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None:
            raise RuntimeError("container provider image record has an invalid image ID")
        repo_digests = record.get("repoDigests")
        expected_digest = reference.partition("@")[2]
        if not isinstance(repo_digests, list) or not any(
            isinstance(value, str) and value.endswith(expected_digest) for value in repo_digests
        ):
            raise RuntimeError("container provider image record lacks the pinned digest")
        if self.runtime.image_id(reference) != image_id:
            raise RuntimeError("container source record does not match the pulled image ID")
        if expected_files:
            command = (
                'for path in "$@"; do [ -e "/$path" ] || { '
                'echo "missing expected source file: $path" >&2; exit 1; }; done'
            )
            result = self.runtime._docker(
                [
                    "run",
                    "--rm",
                    "--network=none",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
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
                raise RuntimeError("container source is missing required runtime files")
        return reference, image_id

    def _base_context(self) -> Path:
        return self.context.pack_root / "private" / "runtime" / "l4d2-harbor-runtime"

    def _task_context(self, task: Left4Dead2Task) -> Path:
        return self.context.pack_root / "private" / "harbor" / task.id / "tests"

    def _labels(
        self, spec: RuntimeSpec, task_label: str, build_context: Path
    ) -> dict[str, str]:
        reference, _expected = self._source_policy(spec)
        return {
            RUNTIME_FINGERPRINT_LABEL: self._fingerprint(spec),
            RUNTIME_SOURCE_LABEL: reference,
            RUNTIME_TASK_LABEL: task_label,
            RUNTIME_ID_LABEL: RUNTIME_ID,
            RUNTIME_BUILD_LABEL: self._tree_fingerprint(build_context),
        }

    def _build(
        self,
        *,
        tag: str,
        context: Path,
        labels: dict[str, str],
        timeout: float,
    ) -> tuple[str, str]:
        arguments = ["build", "--platform=linux/amd64", "--pull=false", "--tag", tag]
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(context / "Dockerfile"), str(context)))
        try:
            result = self.runtime._docker(arguments, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as error:
            self._build_failed(str(error))
        log = result.stdout + result.stderr
        if result.returncode != 0:
            self._build_failed(log)
        return self.runtime.image_id(tag), log

    def _build_failed(self, log: str) -> NoReturn:
        # Operation errors are public API data; detailed build output can
        # contain private paths and belongs only in restricted local state.
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
                "Left 4 Dead 2 build failed and its private diagnostics could not be saved"
            ) from None
        raise RuntimeError("failed to build Left 4 Dead 2 runtime image; inspect local build logs") from None

    @staticmethod
    def _artifact_identity(base_image: str, images: dict[str, str]) -> str:
        values = {"base": base_image, **images}
        digest = hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in sorted(values.items())).encode()
        ).hexdigest()
        return f"sha256:{digest}"

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: Any
    ) -> RuntimeArtifact:
        del destination
        source_reference, source_image_id = self._validate_source(spec, source)
        base_context = self._base_context()
        dockerfile = (base_context / "Dockerfile").read_text(encoding="utf-8")
        first_from = next(
            (line.split()[1] for line in dockerfile.splitlines() if line.strip().upper().startswith("FROM ")),
            "",
        )
        if first_from != source_reference:
            raise RuntimeError("shared L4D2 Dockerfile is not bound to the acquired source")
        progress(0, "building pinned Left 4 Dead 2 dedicated-server runtime")
        base_image, _base_log = self._build(
            tag=_BASE_TAG,
            context=base_context,
            labels=self._labels(spec, BASE_TASK_LABEL, base_context),
            timeout=14_400,
        )
        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            progress(int(index * 90 / total), f"building verifier image for {task.id}")
            context = self._task_context(task)
            task_from = next(
                (
                    line.split()[1]
                    for line in (context / "Dockerfile").read_text(encoding="utf-8").splitlines()
                    if line.strip().upper().startswith("FROM ")
                ),
                "",
            )
            if task_from != _BASE_TAG:
                raise RuntimeError(f"task verifier is not bound to the shared runtime: {task.id}")
            tag = f"rhenium-left-4-dead-2:{task.id}-{self._fingerprint(spec)[:12]}"
            image_id, _log = self._build(
                tag=tag,
                context=context,
                labels=self._labels(spec, task.id, context),
                timeout=1800,
            )
            images[task.id] = image_id
        progress(100, "Left 4 Dead 2 evaluator images ready")
        return RuntimeArtifact(
            runtime_key=f"{_PLUGIN_ID}/{spec.id}",
            fingerprint=self._fingerprint(spec),
            kind="docker-images",
            identity=self._artifact_identity(base_image, images),
            metadata={
                "baseImage": base_image,
                "images": images,
                "network": "none",
                "runtime": RUNTIME_ID,
                "sourceImage": source_reference,
                "sourceImageId": source_image_id,
            },
        )

    def _artifact_images(
        self, spec: RuntimeSpec, artifact: RuntimeArtifact
    ) -> tuple[str, dict[str, str]]:
        if artifact.runtime_key != f"{_PLUGIN_ID}/{spec.id}":
            raise ValueError("runtime artifact has the wrong runtime key")
        if artifact.fingerprint != self._fingerprint(spec) or artifact.kind != "docker-images":
            raise ValueError("runtime artifact is stale or has the wrong kind")
        base_image = artifact.metadata.get("baseImage")
        images = artifact.metadata.get("images")
        task_ids = {task.id for task in self.catalog.tasks}
        if not isinstance(base_image, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", base_image) is None:
            raise ValueError("runtime artifact has an invalid base image")
        if not isinstance(images, dict) or set(images) != task_ids or any(
            not isinstance(key, str) or not isinstance(value, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None for key, value in images.items()
        ):
            raise ValueError("runtime artifact has an incomplete verifier image set")
        typed_images = dict(images)
        if len({base_image, *typed_images.values()}) != len(typed_images) + 1:
            raise ValueError("runtime artifact reuses an image across distinct verifier roles")
        if artifact.identity != self._artifact_identity(base_image, typed_images):
            raise ValueError("runtime artifact identity does not match its images")
        return base_image, typed_images

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            base_image, images = self._artifact_images(spec, artifact)
            expected = {
                base_image: self._labels(spec, BASE_TASK_LABEL, self._base_context()),
                **{
                    image_id: self._labels(spec, task.id, self._task_context(task))
                    for task in self.catalog.tasks
                    for image_id in (images[task.id],)
                },
            }
            for image_id, labels in expected.items():
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
        base_image, images = self._artifact_images(spec, artifact)
        owned = [(BASE_TASK_LABEL, base_image, self._base_context())]
        owned.extend(
            (task.id, images[task.id], self._task_context(task)) for task in self.catalog.tasks
        )
        for task_label, image_id, context in owned:
            if self.runtime.image_id(image_id) != image_id:
                raise RuntimeError(f"refusing to prune a mutable image: {task_label}")
            labels = self.runtime.image_labels(image_id)
            expected = self._labels(spec, task_label, context)
            if any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"refusing to prune an unowned image: {task_label}")
        for task_label, image_id, _context in reversed(owned):
            removed = self.runtime._docker(["image", "rm", image_id], timeout=120)
            if removed.returncode != 0:
                raise RuntimeError(f"failed to prune evaluator image: {task_label}")
