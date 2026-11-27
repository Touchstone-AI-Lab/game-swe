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
from rhenium.core.runtime import RuntimeActionRequired, RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import MinecraftCatalog, MinecraftTask
from .container import (
    _DOCKER_TIMEOUT,
    BASE_IMAGE_REFERENCE,
    BASE_TAG,
    BASE_TASK_LABEL,
    EULA_FILE,
    PAPER_BUILD,
    PAPER_VERSION,
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID_LABEL,
    RUNTIME_IDS,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_TASK_LABEL,
    SERVER_JAR,
    MinecraftContainerRuntime,
    runtime_key,
)

_PLUGIN_ID = "minecraft"
_PLUGIN_VERSION = "0.6.0"
_EULA_URL = "https://aka.ms/MinecraftEULA"
_EULA_ACCEPTED = re.compile(r"^\s*eula\s*=\s*true\s*$", re.IGNORECASE)


def eula_accepted(path: Path) -> bool:
    """Whether an operator-written eula.txt accepts the Minecraft EULA.

    Comment lines are ignored; the acceptance line is the one Paper itself writes.
    Rhenium only ever reads this file: writing it is the operator's decision.
    """
    if not path.is_file() or path.is_symlink():
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("#"):
            continue
        if _EULA_ACCEPTED.match(line):
            return True
    return False


class MinecraftRuntimeBuilder(RuntimeBuilder):
    """Builds the pinned Paper base image and one verifier image per task.

    The official-download provider acquires the pinned Paper jar; the operator's
    own acceptance of the Minecraft EULA is a separate file in this pack's local
    state (``eula_record``) that Rhenium reads but never writes. The pack only
    holds the Dockerfile, the bootstrap scripts and the harness sources. The base
    image bootstraps Paper once with network (paperclip downloads the Mojang
    server); evaluation runs offline.
    """

    def __init__(self, context: BenchmarkContext, catalog: MinecraftCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = MinecraftContainerRuntime()

    @property
    def runtime_root(self) -> Path:
        return self.context.pack_root / "private" / "runtime"

    @property
    def harness_root(self) -> Path:
        return self.context.pack_root / "private" / "harbor" / "harness" / "gcb-harness"

    @property
    def eula_record(self) -> Path:
        """Where the operator records accepting the Minecraft EULA for this pack's runtime."""
        return self.context.state_dir / EULA_FILE

    @staticmethod
    def _fingerprint(spec: RuntimeSpec) -> str:
        return spec.fingerprint(plugin_id=_PLUGIN_ID, plugin_version=_PLUGIN_VERSION)

    @classmethod
    def own_base_tag(cls, spec: RuntimeSpec) -> str:
        """A base-image tag only this runtime and fingerprint use.

        Every Minecraft pack builds its base under the shared ``BASE_TAG`` that the
        task Dockerfiles start from, so that tag moves to whichever runtime was
        prepared last. Docker's containerd image store drops an image as soon as no
        tag names it, so each prepared base also keeps a tag of its own.
        """
        return f"rhenium-minecraft:{BASE_TASK_LABEL}-{spec.id}-{cls._fingerprint(spec)[:12]}"

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
    def _pinned_digest(spec: RuntimeSpec) -> str:
        if spec.id not in RUNTIME_IDS:
            raise ValueError("unsupported Minecraft runtime id")
        if spec.source.get("expectedFiles") != [SERVER_JAR]:
            raise ValueError("Minecraft runtime source must declare exactly the server jar")
        digest = spec.source.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Minecraft runtime requires a pinned server SHA-256")
        return digest

    def _eula_missing(self) -> str:
        return (
            f"the Minecraft EULA ({_EULA_URL}) is accepted only by the operator, never by Rhenium; "
            f"after reading it, record your acceptance by writing eula=true to {self.eula_record}"
        )

    def _check_source(self, spec: RuntimeSpec, root: Path) -> str:
        """Verify the acquired jar against the pin and require the operator's EULA acceptance."""
        expected = self._pinned_digest(spec)
        jar = root / SERVER_JAR
        if jar.is_symlink() or not jar.is_file():
            raise RuntimeError(f"Minecraft runtime source is missing: {SERVER_JAR}")
        digest = hashlib.sha256(jar.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError("Paper server SHA-256 does not match the runtime catalog")
        if not eula_accepted(self.eula_record):
            raise RuntimeActionRequired(
                "accept-eula",
                f"Paper runs the Minecraft server: {self._eula_missing()}, then run the same "
                "rhenium runtime prepare command again",
                {"file": str(self.eula_record), "expected": "eula=true", "eula": _EULA_URL},
            )
        return digest

    @staticmethod
    def _first_from(dockerfile: Path) -> str:
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
            return {**report, "available": False, "reason": "Minecraft runtime Dockerfile is missing"}
        if self._first_from(dockerfile) != BASE_IMAGE_REFERENCE:
            return {**report, "available": False, "reason": "runtime Dockerfile is not digest-pinned"}
        if not (self.harness_root / "build.sh").is_file():
            return {**report, "available": False, "reason": "GcbHarness sources are missing"}
        report["eulaRecord"] = str(self.eula_record)
        report["eulaAccepted"] = eula_accepted(self.eula_record)
        if not report["eulaAccepted"]:
            report["reason"] = self._eula_missing()
        return report

    def _task_context(self, task: MinecraftTask) -> Path:
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
        self,
        *,
        tag: str,
        context: Path,
        dockerfile: Path,
        labels: dict[str, str],
        timeout: float,
        own_tag: str | None = None,
    ) -> str:
        arguments = ["build", "--platform=linux/amd64", "--pull=false", "--tag", tag]
        if own_tag is not None:
            arguments.extend(("--tag", own_tag))
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(dockerfile), str(context)))
        try:
            result = self.runtime._docker(arguments, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as error:
            self._build_failed(str(error))
        if result.returncode != 0:
            self._build_failed(result.stdout + result.stderr)
        # The own tag cannot have been moved by another runtime in the meantime.
        return self.runtime.image_id(own_tag or tag)

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
                "Minecraft runtime build failed and its private diagnostics could not be saved"
            ) from None
        raise RuntimeError("failed to build Minecraft runtime image; inspect local build logs") from None

    @staticmethod
    def _artifact_identity(base_image: str, images: dict[str, str]) -> str:
        values = {"base": base_image, **images}
        digest = hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in sorted(values.items())).encode()
        ).hexdigest()
        return f"sha256:{digest}"

    def _stage_base_context(self, source: Path, staging: Path) -> None:
        """Assemble the base build context: pack assets, the acquired jar and the operator's EULA file."""
        shutil.copyfile(source / SERVER_JAR, staging / SERVER_JAR)
        # The operator's own acceptance, copied unchanged; bootstrap.sh checks it again.
        shutil.copyfile(self.eula_record, staging / EULA_FILE)
        shutil.copytree(self.runtime_root, staging / "runtime")
        shutil.copytree(self.harness_root, staging / "gcb-harness")
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
            raise RuntimeError("shared Minecraft Dockerfile is not bound to the pinned JDK image")
        base_fingerprint = self._base_build_fingerprint(source_digest)
        progress(0, f"building pinned Paper {PAPER_VERSION} build {PAPER_BUILD} runtime")
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="minecraft-runtime-", dir=self.context.cache_dir
        ) as raw_staging:
            staging = Path(raw_staging)
            self._stage_base_context(source, staging)
            base_image = self._build(
                tag=BASE_TAG,
                own_tag=self.own_base_tag(spec),
                context=staging,
                dockerfile=staging / "runtime" / "Dockerfile",
                labels=self._labels(spec, BASE_TASK_LABEL, base_fingerprint, source_digest),
                timeout=7200,
            )
        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            progress(int(index * 90 / total), f"building verifier image for {task.id}")
            context = self._task_context(task)
            if self._first_from(context / "Dockerfile") != BASE_TAG:
                raise RuntimeError(f"task verifier is not bound to the shared runtime: {task.id}")
            tag = f"rhenium-minecraft:{task.id}-{self._fingerprint(spec)[:12]}"
            images[task.id] = self._build(
                tag=tag,
                context=context,
                dockerfile=context / "Dockerfile",
                labels=self._labels(spec, task.id, self._tree_fingerprint(context), source_digest),
                timeout=3600,
            )
        progress(100, "Minecraft evaluator images ready")
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
                "paperVersion": PAPER_VERSION,
                "paperBuild": PAPER_BUILD,
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
        if not isinstance(base_image, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", base_image) is None:
            raise ValueError("runtime artifact has an invalid base image")
        if (
            not isinstance(images, dict)
            or set(images) != task_ids
            or any(
                not isinstance(key, str)
                or not isinstance(value, str)
                or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
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

    def _check_image(self, task_label: str, image_id: str, labels: dict[str, str]) -> None:
        """Fail unless Docker still has ``image_id`` and it carries exactly ``labels``."""
        try:
            observed_id = self.runtime.image_id(image_id)
        except RuntimeError as error:
            raise RuntimeError(f"verifier image for {task_label} is unavailable in Docker") from error
        if observed_id != image_id:
            raise RuntimeError("runtime artifact contains a mutable image identity")
        observed = self.runtime.image_labels(image_id)
        if observed.get(RUNTIME_BUILD_LABEL) != labels[RUNTIME_BUILD_LABEL]:
            raise RuntimeError(
                f"verifier image for {task_label} was built from a different build context "
                "than the pack now holds; prepare the runtime again"
            )
        if any(observed.get(key) != value for key, value in labels.items()):
            raise RuntimeError("runtime artifact image labels do not match")

    def task_image(self, spec: RuntimeSpec, artifact: RuntimeArtifact, task: MinecraftTask) -> str:
        """The verifier image ID for ``task``, checked against the pack as it is now.

        The runtime fingerprint covers ``runtimes.json`` and the plugin version, not
        each task's private ``tests/`` build context, so a record stays ready after a
        task's suite or frozen case set changes. Evaluation calls this before it runs
        the image, so an image built from an older suite, or one Docker no longer
        has, fails closed instead of grading the submission against outdated cases.
        """
        _base_image, images, source_digest = self._artifact_images(spec, artifact)
        if not eula_accepted(self.eula_record):
            raise RuntimeError(self._eula_missing())
        image_id = images.get(task.id)
        if image_id is None:
            raise ValueError(f"runtime artifact has no verifier image for {task.id}")
        context = self._tree_fingerprint(self._task_context(task))
        self._check_image(task.id, image_id, self._labels(spec, task.id, context, source_digest))
        return image_id

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            base_image, images, source_digest = self._artifact_images(spec, artifact)
            if not eula_accepted(self.eula_record):
                # The images hold the Mojang server; run it only while the acceptance stands.
                raise RuntimeError(self._eula_missing())
            for label, image_id, labels in self._expected_labels(spec, base_image, images, source_digest):
                self._check_image(label, image_id, labels)
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
            references = [image_id]
            if task_label == BASE_TASK_LABEL:
                # The base carries its own tag and, while it was the last Minecraft base
                # prepared, the shared tag. Removing it by ID is refused while two tags
                # name it, so remove each tag that still names this image; a shared tag
                # that has moved to another runtime's base is left alone.
                references = [
                    reference
                    for reference in (BASE_TAG, self.own_base_tag(spec))
                    if self._names(reference, image_id)
                ] or [image_id]
            for reference in references:
                removed = self.runtime._docker(["image", "rm", reference], timeout=_DOCKER_TIMEOUT)
                if removed.returncode != 0:
                    raise RuntimeError(f"failed to prune evaluator image: {task_label}")

    def _names(self, reference: str, image_id: str) -> bool:
        try:
            return self.runtime.image_id(reference) == image_id
        except RuntimeError:
            return False
