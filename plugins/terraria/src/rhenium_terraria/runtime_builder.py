from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import TerrariaCatalog, TerrariaTask
from .evaluator import (
    _DOCKER_TIMEOUT,
    ENGINE_RUNTIME_ID,
    ENGINE_RUNTIME_KEY,
    SOURCE_RUNTIME_ID,
    SOURCE_RUNTIME_KEY,
    TMODLOADER_VERSION,
    TerrariaEngineRuntime,
    TerrariaRuntime,
)

_PLUGIN_ID = "terraria"
_PLUGIN_VERSION = "0.7.0"
_LABEL_PREFIX = "org.gamecodebench.terraria"
_FINGERPRINT_LABEL = f"{_LABEL_PREFIX}.fingerprint"
_SOURCE_LABEL = f"{_LABEL_PREFIX}.source"
_TASK_LABEL = f"{_LABEL_PREFIX}.task"
_CONTEXT_LABEL = f"{_LABEL_PREFIX}.context"
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


class TerrariaSourceProjectionRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: TerrariaCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = TerrariaRuntime(context, catalog)

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=_PLUGIN_ID, plugin_version=_PLUGIN_VERSION)

    @staticmethod
    def _tree_fingerprint(root: Path) -> str:
        digest = hashlib.sha256()
        for candidate in sorted(
            root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
        ):
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
        if not isinstance(reference, str) or re.search(
            r"@sha256:[0-9a-f]{64}$", reference
        ) is None:
            raise ValueError("Terraria runtime source must use a digest-pinned image")
        raw_expected = spec.source.get("expectedFiles", [])
        if not isinstance(raw_expected, list) or any(
            not isinstance(value, str) for value in raw_expected
        ):
            raise ValueError("Terraria runtime expectedFiles must be a list of paths")
        expected: list[str] = []
        for value in raw_expected:
            path = PurePosixPath(value)
            if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
                raise ValueError("Terraria runtime expectedFiles paths must be normalized")
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
        if not isinstance(image_id, str) or _IMAGE_ID.fullmatch(image_id) is None:
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
            checked = self.runtime._docker(
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
                timeout=_DOCKER_TIMEOUT,
            )
            if checked.returncode != 0:
                raise RuntimeError("container source is missing required runtime files")
        return reference, image_id

    def _task_context(self, task: TerrariaTask) -> Path:
        return (
            self.context.pack_root / "private" / "harbor" / task.id / "environment"
        ).resolve()

    def _labels(self, spec: RuntimeSpec, task: TerrariaTask) -> dict[str, str]:
        source, _expected = self._source_policy(spec)
        return {
            _FINGERPRINT_LABEL: self._fingerprint(spec),
            _SOURCE_LABEL: source,
            _TASK_LABEL: task.id,
            _CONTEXT_LABEL: self._tree_fingerprint(self._task_context(task)),
        }

    @staticmethod
    def _identity(images: dict[str, str]) -> str:
        encoded = "\n".join(
            f"{task_id}={image_id}" for task_id, image_id in sorted(images.items())
        ).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        if spec.id != SOURCE_RUNTIME_ID:
            return {"available": False, "reason": f"unsupported Terraria runtime: {spec.id}"}
        try:
            self._source_policy(spec)
        except ValueError as error:
            return {"available": False, "reason": str(error)}
        return self.runtime.status()

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        del destination
        if spec.id != SOURCE_RUNTIME_ID:
            raise ValueError(f"unsupported Terraria runtime: {spec.id}")
        source_reference, source_image_id = self._validate_source(spec, source)
        if not self.runtime.docker:
            raise RuntimeError("Docker CLI is not installed")

        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            progress(
                int((index - 1) * 100 / total),
                f"building evaluator image for {task.id}",
            )
            context = self._task_context(task)
            dockerfile = context / "Dockerfile"
            if not dockerfile.is_file():
                raise RuntimeError(f"Terraria Dockerfile is missing for {task.id}: {dockerfile}")
            first_from = next(
                (
                    line.split()[1]
                    for line in dockerfile.read_text(encoding="utf-8").splitlines()
                    if line.strip().upper().startswith("FROM ")
                ),
                "",
            )
            if first_from != source_reference:
                raise RuntimeError(f"task Dockerfile is not pinned to the acquired source: {task.id}")
            labels = self._labels(spec, task)
            tag = f"rhenium-terraria:{task.id}-{self._fingerprint(spec)[:12]}"
            arguments = ["build", "--pull=false", "--tag", tag]
            for key, value in labels.items():
                arguments.extend(("--label", f"{key}={value}"))
            arguments.extend(("--file", str(dockerfile), str(context)))
            built = self.runtime._docker(arguments, timeout=1800)
            if built.returncode != 0:
                message = built.stderr.strip() or built.stdout.strip()
                raise RuntimeError(
                    f"failed to build Terraria evaluator image for {task.id}: {message}"
                )
            images[task.id] = self.runtime.image_id(tag)

        progress(100, "Terraria source-projection evaluator images ready")
        return RuntimeArtifact(
            runtime_key=SOURCE_RUNTIME_KEY,
            fingerprint=self._fingerprint(spec),
            kind="docker-images",
            identity=self._identity(images),
            metadata={
                "images": images,
                "network": "none",
                "evaluationBoundary": "offline production-source projection",
                "sourceImage": source_reference,
                "sourceImageId": source_image_id,
            },
        )

    def _artifact_images(
        self, spec: RuntimeSpec, artifact: RuntimeArtifact
    ) -> dict[str, str]:
        if artifact.runtime_key != SOURCE_RUNTIME_KEY:
            raise ValueError("runtime artifact has the wrong key")
        if artifact.fingerprint != self._fingerprint(spec) or artifact.kind != "docker-images":
            raise ValueError("runtime artifact is stale or has the wrong kind")
        images = artifact.metadata.get("images")
        expected = {task.id for task in self.catalog.tasks}
        if not isinstance(images, dict) or set(images) != expected or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or _IMAGE_ID.fullmatch(value) is None
            for key, value in images.items()
        ):
            raise ValueError("runtime artifact has an incomplete image set")
        typed = dict(images)
        if len(set(typed.values())) != len(typed):
            raise ValueError("runtime artifact reuses an image for distinct tasks")
        if artifact.identity != self._identity(typed):
            raise ValueError("runtime artifact identity does not match its images")
        return typed

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            images = self._artifact_images(spec, artifact)
            for task in self.catalog.tasks:
                image_id = images[task.id]
                if self.runtime.image_id(image_id) != image_id:
                    raise RuntimeError("runtime artifact contains a mutable image identity")
                observed = self.runtime.image_labels(image_id)
                expected = self._labels(spec, task)
                if any(observed.get(key) != value for key, value in expected.items()):
                    raise RuntimeError(f"runtime image labels do not match: {task.id}")
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
        for task in self.catalog.tasks:
            image_id = images[task.id]
            if self.runtime.image_id(image_id) != image_id:
                raise RuntimeError(f"refusing to prune a mutable image: {task.id}")
            labels = self.runtime.image_labels(image_id)
            expected = self._labels(spec, task)
            if any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeError(f"refusing to prune an unowned image: {task.id}")
        for task in reversed(self.catalog.tasks):
            removed = self.runtime._docker(["image", "rm", images[task.id]], timeout=_DOCKER_TIMEOUT)
            if removed.returncode != 0:
                raise RuntimeError(f"failed to prune Terraria image: {task.id}")


_ENGINE_ARCHIVE = "tModLoader.zip"
_PUBLICIZER_PACKAGE = "krafs.publicizer.2.2.1.nupkg"
_PUBLICIZER_SHA256 = "f411bf4ff10b039fbc09e4fcd1a20615e26fa08a5475c8f995ba2477535fa283"
_ENGINE_BASE_IMAGE = f"rhenium-terraria-engine-base:v{TMODLOADER_VERSION}"
_ENGINE_PROBE_IMAGE = f"rhenium-terraria-engine-probe:v{TMODLOADER_VERSION}"
_ENGINE_SDK_IMAGE = (
    "mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim@"
    "sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c"
)
_ENGINE_LABEL_PREFIX = "org.gamecodebench.terraria.engine"
_ENGINE_FINGERPRINT_LABEL = f"{_ENGINE_LABEL_PREFIX}.fingerprint"
_ENGINE_SOURCE_LABEL = f"{_ENGINE_LABEL_PREFIX}.source"
_ENGINE_TASK_LABEL = f"{_ENGINE_LABEL_PREFIX}.task"
_ENGINE_CONTEXT_LABEL = f"{_ENGINE_LABEL_PREFIX}.context"
_ENGINE_BASE_TASK = "__base__"
_ENGINE_PROBE_TASK = "__probe__"


class TerrariaEngineRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: TerrariaCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = TerrariaEngineRuntime(context, catalog)

    @property
    def runtime_root(self) -> Path:
        return (self.context.pack_root / "private" / "runtime").resolve()

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=_PLUGIN_ID, plugin_version=_PLUGIN_VERSION)

    @staticmethod
    def _tree_fingerprint(root: Path) -> str:
        return TerrariaSourceProjectionRuntimeBuilder._tree_fingerprint(root)

    @staticmethod
    def _source_digest(spec: RuntimeSpec) -> str:
        if spec.id != ENGINE_RUNTIME_ID:
            raise ValueError(f"unsupported Terraria engine runtime: {spec.id}")
        if spec.source.get("expectedFiles") != [_ENGINE_ARCHIVE, _PUBLICIZER_PACKAGE]:
            raise ValueError(
                "Terraria engine source must declare tModLoader.zip and Krafs.Publicizer"
            )
        digest = spec.source.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Terraria engine runtime requires a pinned archive SHA-256")
        return digest

    def _check_source(self, spec: RuntimeSpec, source: Path) -> tuple[Path, Path, str]:
        expected = self._source_digest(spec)
        archive = source / _ENGINE_ARCHIVE
        if archive.is_symlink() or not archive.is_file():
            raise RuntimeError(f"Terraria engine source is missing: {_ENGINE_ARCHIVE}")
        digest = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        observed = digest.hexdigest()
        if observed != expected:
            raise RuntimeError("tModLoader archive SHA-256 does not match the runtime catalog")
        publicizer = source / _PUBLICIZER_PACKAGE
        if publicizer.is_symlink() or not publicizer.is_file():
            raise RuntimeError(f"Terraria engine source is missing: {_PUBLICIZER_PACKAGE}")
        publicizer_digest = hashlib.sha256(publicizer.read_bytes()).hexdigest()
        if publicizer_digest != _PUBLICIZER_SHA256:
            raise RuntimeError("Krafs.Publicizer SHA-256 does not match the reviewed package")
        try:
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
                required = {
                    "tModLoader.dll",
                    "tModLoader.runtimeconfig.json",
                    "tMLMod.targets",
                    "Content/Images/Item_1101.xnb",
                    "Libraries/FNA/1.0.0/FNA.dll",
                }
                if not required.issubset(names):
                    raise RuntimeError("tModLoader archive is missing required engine files")
        except zipfile.BadZipFile as error:
            raise RuntimeError("tModLoader archive is not a valid zip file") from error
        return archive, publicizer, observed

    @staticmethod
    def _extract_archive(archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) > 100_000 or sum(item.file_size for item in entries) > 4_000_000_000:
                raise RuntimeError("tModLoader archive exceeds the extraction policy")
            for item in entries:
                normalized = item.filename[:-1] if item.is_dir() else item.filename
                relative = PurePosixPath(normalized)
                windows_relative = PureWindowsPath(normalized)
                if (
                    not normalized
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or windows_relative.is_absolute()
                    or bool(windows_relative.drive)
                    or ".." in windows_relative.parts
                    or normalized != relative.as_posix()
                ):
                    raise RuntimeError("tModLoader archive contains an unsafe path")
                mode = (item.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise RuntimeError("tModLoader archive contains a symbolic link")
                target = destination.joinpath(*relative.parts)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source_stream, target.open("wb") as target_stream:
                    shutil.copyfileobj(source_stream, target_stream)

    @staticmethod
    def _first_from(dockerfile: Path) -> str:
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            if line.strip().upper().startswith("FROM "):
                return line.split()[1]
        return ""

    def _base_context_fingerprint(self, source_digest: str) -> str:
        digest = hashlib.sha256()
        digest.update(source_digest.encode() + b"\0")
        digest.update(_PUBLICIZER_SHA256.encode() + b"\0")
        digest.update(self._tree_fingerprint(self.runtime_root).encode())
        return f"sha256:{digest.hexdigest()}"

    def _labels(
        self,
        spec: RuntimeSpec,
        task_label: str,
        context_fingerprint: str,
        source_digest: str,
    ) -> dict[str, str]:
        return {
            _ENGINE_FINGERPRINT_LABEL: self._fingerprint(spec),
            _ENGINE_SOURCE_LABEL: (
                f"local-files:{_ENGINE_ARCHIVE}:sha256:{source_digest};"
                f"{_PUBLICIZER_PACKAGE}:sha256:{_PUBLICIZER_SHA256}"
            ),
            _ENGINE_TASK_LABEL: task_label,
            _ENGINE_CONTEXT_LABEL: context_fingerprint,
        }

    def _build_image(
        self,
        *,
        tag: str,
        context: Path,
        dockerfile: Path,
        labels: dict[str, str],
        timeout: float,
    ) -> str:
        arguments = [
            "build",
            "--platform=linux/amd64",
            "--pull=false",
            "--network=none",
            "--tag",
            tag,
        ]
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(dockerfile), str(context)))
        result = self.runtime._docker(arguments, timeout=timeout)
        if result.returncode != 0:
            message = (result.stderr or result.stdout)[-20_000:].strip()
            raise RuntimeError(f"failed to build Terraria engine image: {message}")
        return self.runtime.image_id(tag)

    def _engine_context(self, task: TerrariaTask) -> Path:
        return (
            self.context.pack_root / "private" / "harbor" / task.id / "engine"
        ).resolve()

    @staticmethod
    def _artifact_identity(base: str, probe: str, images: dict[str, str]) -> str:
        values = {"base": base, "probe": probe, **images}
        encoded = "\n".join(
            f"{name}={image}" for name, image in sorted(values.items())
        ).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def _run_probe(self, image_id: str) -> dict[str, Any]:
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="terraria-engine-probe-", dir=self.context.cache_dir
        ) as raw_reports:
            reports = Path(raw_reports)
            process, _runtime_log = self.runtime.run_image(
                image_id, reports, timeout=300
            )
            report_path = reports / "engine-report.json"
            if not report_path.is_file():
                raise RuntimeError("real tModLoader probe did not produce a report")
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise RuntimeError("real tModLoader probe report is invalid") from error
            if (
                process.returncode != 0
                or not isinstance(report, dict)
                or report.get("complete") is not True
                or report.get("passed") is not True
                or report.get("terrariaVersion") != "v1.4.4.9"
                or report.get("tModLoaderVersion") != TMODLOADER_VERSION
                or report.get("dedicatedServer") is not True
            ):
                raise RuntimeError("real tModLoader dedicated-server probe failed")
            return report

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        report = {
            **self.runtime.status(),
            "runtimeRoot": str(self.runtime_root),
            "sourceDirectoryVariable": "RHENIUM_TERRARIA_TML_DIR",
        }
        try:
            self._source_digest(spec)
            if self._first_from(self.runtime_root / "Dockerfile") != _ENGINE_SDK_IMAGE:
                raise ValueError("Terraria engine Dockerfile is not SDK-digest pinned")
            if self._first_from(self.runtime_root / "TaskDockerfile") != _ENGINE_BASE_IMAGE:
                raise ValueError("Terraria task Dockerfile is not bound to the engine base")
            if not (self.runtime_root / "probe" / "GcbRuntimeProbe" / "GcbRuntimeProbe.csproj").is_file():
                raise ValueError("Terraria real-engine probe is missing")
            missing = [task.id for task in self.catalog.tasks if not self._engine_context(task).is_dir()]
            if missing:
                raise ValueError(f"Terraria engine fixtures are missing: {', '.join(missing)}")
        except (OSError, RuntimeError, ValueError) as error:
            return {**report, "available": False, "reason": str(error)}
        return report

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        del destination
        archive, publicizer, source_digest = self._check_source(spec, source)
        if not self.runtime.docker:
            raise RuntimeError("Docker CLI is not installed")
        if self._first_from(self.runtime_root / "Dockerfile") != _ENGINE_SDK_IMAGE:
            raise RuntimeError("Terraria engine Dockerfile is not SDK-digest pinned")
        if self._first_from(self.runtime_root / "TaskDockerfile") != _ENGINE_BASE_IMAGE:
            raise RuntimeError("Terraria task Dockerfile is not bound to the engine base")

        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        progress(0, f"extracting official tModLoader v{TMODLOADER_VERSION}")
        # Keep extraction near the system temporary root. tModLoader ships deep
        # NuGet-style paths that can exceed legacy Windows path limits when a
        # benchmark cache directory is nested below a long workspace path.
        with tempfile.TemporaryDirectory(prefix="rhe-tml-") as raw_staging:
            staging = Path(raw_staging)
            self._extract_archive(archive, staging / "tmodloader")
            packages = staging / "packages"
            packages.mkdir()
            shutil.copyfile(publicizer, packages / _PUBLICIZER_PACKAGE)
            shutil.copytree(self.runtime_root, staging / "runtime")
            base = self._build_image(
                tag=_ENGINE_BASE_IMAGE,
                context=staging,
                dockerfile=staging / "runtime" / "Dockerfile",
                labels=self._labels(
                    spec,
                    _ENGINE_BASE_TASK,
                    self._base_context_fingerprint(source_digest),
                    source_digest,
                ),
                timeout=3600,
            )

        task_dockerfile = self.runtime_root / "TaskDockerfile"
        progress(20, "building and booting the real tModLoader runtime probe")
        probe_context = self.runtime_root / "probe"
        probe = self._build_image(
            tag=_ENGINE_PROBE_IMAGE,
            context=probe_context,
            dockerfile=task_dockerfile,
            labels=self._labels(
                spec,
                _ENGINE_PROBE_TASK,
                self._tree_fingerprint(probe_context),
                source_digest,
            ),
            timeout=1800,
        )
        probe_report = self._run_probe(probe)

        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            progress(20 + int(index * 75 / total), f"building engine verifier for {task.id}")
            context = self._engine_context(task)
            if not context.is_dir():
                raise RuntimeError(f"Terraria engine fixture is missing: {task.id}")
            images[task.id] = self._build_image(
                tag=f"rhenium-terraria-engine:{task.id}-{self._fingerprint(spec)[:12]}",
                context=context,
                dockerfile=task_dockerfile,
                labels=self._labels(
                    spec,
                    task.id,
                    self._tree_fingerprint(context),
                    source_digest,
                ),
                timeout=1800,
            )

        progress(100, "real tModLoader task images ready")
        return RuntimeArtifact(
            runtime_key=ENGINE_RUNTIME_KEY,
            fingerprint=self._fingerprint(spec),
            kind="docker-images",
            identity=self._artifact_identity(base, probe, images),
            metadata={
                "baseImage": base,
                "probeImage": probe,
                "images": images,
                "network": "none",
                "gameVersion": "1.4.4.9",
                "tModLoaderVersion": TMODLOADER_VERSION,
                "sourceSha256": source_digest,
                "probe": probe_report,
            },
        )

    def _artifact_images(
        self, spec: RuntimeSpec, artifact: RuntimeArtifact
    ) -> tuple[str, str, dict[str, str], str]:
        if artifact.runtime_key != ENGINE_RUNTIME_KEY:
            raise ValueError("Terraria engine artifact has the wrong runtime key")
        if artifact.fingerprint != self._fingerprint(spec) or artifact.kind != "docker-images":
            raise ValueError("Terraria engine artifact is stale or has the wrong kind")
        source_digest = self._source_digest(spec)
        if artifact.metadata.get("sourceSha256") != source_digest:
            raise ValueError("Terraria engine artifact uses a different tModLoader archive")
        base = artifact.metadata.get("baseImage")
        probe = artifact.metadata.get("probeImage")
        images = artifact.metadata.get("images")
        expected = {task.id for task in self.catalog.tasks}
        if (
            not isinstance(base, str)
            or _IMAGE_ID.fullmatch(base) is None
            or not isinstance(probe, str)
            or _IMAGE_ID.fullmatch(probe) is None
            or not isinstance(images, dict)
            or set(images) != expected
            or any(
                not isinstance(value, str) or _IMAGE_ID.fullmatch(value) is None
                for value in images.values()
            )
        ):
            raise ValueError("Terraria engine artifact has an incomplete image set")
        typed = dict(images)
        if len({base, probe, *typed.values()}) != len(typed) + 2:
            raise ValueError("Terraria engine artifact reuses an image identity")
        if artifact.identity != self._artifact_identity(base, probe, typed):
            raise ValueError("Terraria engine artifact identity does not match its images")
        return base, probe, typed, source_digest

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            base, probe, images, source_digest = self._artifact_images(spec, artifact)
            expected_labels = {
                base: self._labels(
                    spec,
                    _ENGINE_BASE_TASK,
                    self._base_context_fingerprint(source_digest),
                    source_digest,
                ),
                probe: self._labels(
                    spec,
                    _ENGINE_PROBE_TASK,
                    self._tree_fingerprint(self.runtime_root / "probe"),
                    source_digest,
                ),
            }
            for task in self.catalog.tasks:
                expected_labels[images[task.id]] = self._labels(
                    spec,
                    task.id,
                    self._tree_fingerprint(self._engine_context(task)),
                    source_digest,
                )
            for image_id, labels in expected_labels.items():
                if self.runtime.image_id(image_id) != image_id:
                    raise RuntimeError("Terraria engine image identity changed")
                observed = self.runtime.image_labels(image_id)
                if any(observed.get(key) != value for key, value in labels.items()):
                    raise RuntimeError("Terraria engine image ownership labels changed")
            probe_report = self._run_probe(probe)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        return {
            "available": True,
            "imageCount": len(images) + 2,
            "network": "none",
            "gameVersion": "1.4.4.9",
            "tModLoaderVersion": TMODLOADER_VERSION,
            "realEngineProbe": probe_report,
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        base, probe, images, source_digest = self._artifact_images(spec, artifact)
        expected_tasks = {base: _ENGINE_BASE_TASK, probe: _ENGINE_PROBE_TASK}
        expected_tasks.update({images[task.id]: task.id for task in self.catalog.tasks})
        for image_id, task_label in expected_tasks.items():
            labels = self.runtime.image_labels(image_id)
            expected = self._labels(
                spec,
                task_label,
                (
                    self._base_context_fingerprint(source_digest)
                    if task_label == _ENGINE_BASE_TASK
                    else self._tree_fingerprint(self.runtime_root / "probe")
                    if task_label == _ENGINE_PROBE_TASK
                    else self._tree_fingerprint(
                        self._engine_context(
                            next(
                                task
                                for task in self.catalog.tasks
                                if task.id == task_label
                            )
                        )
                    )
                ),
                source_digest,
            )
            if any(labels.get(key) != value for key, value in expected.items()):
                raise RuntimeError("refusing to prune an unowned Terraria engine image")
        for image_id in [*reversed(list(images.values())), probe, base]:
            removed = self.runtime._docker(["image", "rm", image_id], timeout=_DOCKER_TIMEOUT)
            if removed.returncode != 0:
                raise RuntimeError("failed to prune Terraria engine image")


# Kept for downstream imports while the plugin now selects the explicit builder.
TerrariaRuntimeBuilder = TerrariaSourceProjectionRuntimeBuilder
