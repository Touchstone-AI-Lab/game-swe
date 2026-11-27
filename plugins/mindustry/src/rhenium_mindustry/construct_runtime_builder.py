"""Runtime builder of the restored construct pack (``mindustry/mindustry``).

It builds the base image ``mindustry:159.7`` from the pack's own Dockerfile with
the acquired server jar as the build context, then one evaluator image per task.
The repair runtime builder lives in :mod:`.runtime_builder`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .construct_catalog import MindustryConstructCatalog
from .construct_evaluator import GAME_VERSION, RUNTIME_ID, RUNTIME_KEY, MindustryConstructRuntime

SERVER_JAR = "server-release.jar"
BASE_IMAGE = f"mindustry:{GAME_VERSION}"
# The Docker daemon may be shared and congested; image bookkeeping gets room.
_DOCKER_TIMEOUT = 300


class MindustryConstructRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: MindustryConstructCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = MindustryConstructRuntime(context, catalog)

    @property
    def runtime_root(self) -> Path:
        """The pack's own runtime assets. The server jar is acquired by its provider, never kept here."""
        return (self.context.pack_root / "private" / "runtime").resolve()

    @property
    def dockerfile(self) -> Path:
        return self.runtime_root / "Dockerfile"

    @staticmethod
    def _pinned_digest(spec: RuntimeSpec) -> str:
        if spec.source.get("expectedFiles") != [SERVER_JAR]:
            raise ValueError("Mindustry runtime source must declare its required files")
        expected = spec.source.get("sha256")
        if not isinstance(expected, str) or len(expected) != 64 or any(
            character not in "0123456789abcdef" for character in expected
        ):
            raise ValueError("Mindustry runtime requires a pinned server SHA-256")
        return expected

    def _check_source(self, spec: RuntimeSpec, root: Path) -> str:
        """Verify the acquired server jar against the pinned catalog digest."""
        expected = self._pinned_digest(spec)
        if not self.dockerfile.is_file():
            raise RuntimeError(f"Mindustry runtime Dockerfile is missing: {self.dockerfile}")
        jar = root / SERVER_JAR
        if not jar.is_file():
            raise RuntimeError(f"Mindustry runtime source is missing: {SERVER_JAR}")
        digest = hashlib.sha256(jar.read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError("Mindustry server SHA-256 does not match the runtime catalog")
        return digest

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        if spec.id != RUNTIME_ID:
            return {
                "available": False,
                "reason": f"unsupported Mindustry runtime: {spec.id}",
            }

        runtime_root = self.runtime_root
        if not self.dockerfile.is_file():
            return {
                "available": False,
                "reason": f"Mindustry runtime Dockerfile is missing: {self.dockerfile}",
            }

        try:
            self._pinned_digest(spec)
        except (OSError, RuntimeError, ValueError) as error:
            return {"available": False, "reason": str(error)}
        status = self.runtime.status()
        return {
            **status,
            "runtimeRoot": str(runtime_root),
        }

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        del destination

        if spec.id != RUNTIME_ID:
            raise ValueError(f"unsupported Mindustry runtime: {spec.id}")

        source_digest = self._check_source(spec, source)
        if not self.runtime.docker:
            raise RuntimeError("Docker CLI is not installed")

        # The Dockerfile is a pack asset; the acquired jar is the build context.
        base = self.runtime._docker(
            [
                "build", "--pull=false", "--network=none", "-f",
                str(self.dockerfile), "-t", BASE_IMAGE, str(source),
            ],
            timeout=1800,
        )
        if base.returncode != 0:
            message = base.stderr.strip() or base.stdout.strip()
            raise RuntimeError(f"failed to build Mindustry base image: {message}")

        images: dict[str, str] = {}
        total = len(self.catalog.tasks)

        for index, task in enumerate(self.catalog.tasks, 1):
            progress(
                int((index - 1) * 100 / total),
                f"building evaluator image for {task.id}",
            )

            task_root = (
                self.context.pack_root
                / "private"
                / "harbor"
                / task.id
            ).resolve()

            dockerfile = task_root / "environment" / "Dockerfile"
            environment_root = task_root / "environment"

            if not dockerfile.is_file():
                raise RuntimeError(
                    f"Mindustry Dockerfile is missing for {task.id}: {dockerfile}"
                )

            tag = f"rhenium-mindustry-{task.id}:{GAME_VERSION}"

            build = self.runtime._docker(
                [
                    "build",
                    "--pull=false",
                    "-f",
                    str(dockerfile),
                    "-t",
                    tag,
                    str(environment_root),
                ],
                timeout=1800,
            )

            if build.returncode != 0:
                message = build.stderr.strip() or build.stdout.strip()
                raise RuntimeError(
                    f"failed to build Mindustry evaluator image for "
                    f"{task.id}: {message}"
                )

            inspect = self.runtime._docker(
                [
                    "image",
                    "inspect",
                    tag,
                    "--format",
                    "{{.Id}}",
                ],
                timeout=_DOCKER_TIMEOUT,
            )

            image_id = inspect.stdout.strip()

            if inspect.returncode != 0 or not image_id.startswith("sha256:"):
                raise RuntimeError(
                    f"Mindustry evaluator image has no immutable identity: "
                    f"{task.id}"
                )

            images[task.id] = image_id

        identity = hashlib.sha256(
            "\n".join(
                f"{key}={value}"
                for key, value in sorted(images.items())
            ).encode()
        ).hexdigest()

        fingerprint = spec.fingerprint(
            plugin_id="mindustry",
            plugin_version="0.6.0",
        )

        progress(100, "Mindustry evaluator images ready")

        return RuntimeArtifact(
            runtime_key=RUNTIME_KEY,
            fingerprint=fingerprint,
            kind="docker-images",
            identity=f"sha256:{identity}",
            metadata={
                "images": images,
                "network": "none",
                "gameVersion": GAME_VERSION,
                "sourceSha256": source_digest,
            },
        )

    def verify(
        self,
        spec: RuntimeSpec,
        artifact: RuntimeArtifact,
    ) -> dict[str, Any]:
        if spec.id != RUNTIME_ID:
            return {
                "available": False,
                "reason": "unsupported Mindustry runtime",
            }

        if not self.dockerfile.is_file():
            return {
                "available": False,
                "reason": f"Mindustry runtime Dockerfile is missing: {self.dockerfile}",
            }

        try:
            digest = self._pinned_digest(spec)
        except (OSError, RuntimeError, ValueError) as error:
            return {"available": False, "reason": str(error)}
        if artifact.metadata.get("sourceSha256") != digest:
            return {"available": False, "reason": "Mindustry runtime source identity changed"}

        images = artifact.metadata.get("images")

        if not isinstance(images, dict):
            return {
                "available": False,
                "reason": "Mindustry runtime image set is invalid",
            }

        expected = {task.id for task in self.catalog.tasks}

        if set(images) != expected:
            return {
                "available": False,
                "reason": "Mindustry runtime image set is incomplete",
            }

        for task_id, image_id in images.items():
            result = self.runtime._docker(
                [
                    "image",
                    "inspect",
                    str(image_id),
                    "--format",
                    "{{.Id}}",
                ],
                timeout=_DOCKER_TIMEOUT,
            )

            if result.returncode != 0:
                return {
                    "available": False,
                    "reason": f"Mindustry image is missing: {task_id}",
                }

            if result.stdout.strip() != image_id:
                return {
                    "available": False,
                    "reason": f"Mindustry image identity changed: {task_id}",
                }

        return {
            "available": True,
            "imageCount": len(images),
            "network": "none",
            "runtimeRoot": "private/runtime",
        }

    def prune(
        self,
        spec: RuntimeSpec,
        artifact: RuntimeArtifact,
    ) -> None:
        del spec

        images = artifact.metadata.get("images")

        if not isinstance(images, dict):
            return

        for image_id in set(map(str, images.values())):
            self.runtime._docker(
                ["image", "rm", image_id],
                timeout=_DOCKER_TIMEOUT,
            )
