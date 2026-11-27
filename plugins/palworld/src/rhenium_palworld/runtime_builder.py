from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import rhenium
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeProgress, RuntimeSpec

from .native_runtime import (
    EXPECTED_FILES,
    IMAGE_ID,
    LABEL,
    RUNTIME_ID,
    RUNTIME_KEY,
    SOURCE_HASHES,
    NativeDocker,
    fingerprint,
    recipe_digest,
)


class PalworldRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext):
        self.context = context
        self.docker = NativeDocker()

    @staticmethod
    def source_policy(spec: RuntimeSpec) -> None:
        # Provider schemas/Steam manifest acceptance stay provider-owned. The
        # game builder enforces only its generic required-file/content policy.
        if (
            spec.id != RUNTIME_ID
            or spec.provider != "steam"
            or not spec.restricted
            or spec.source.get("kind") != "steam-depots"
            or spec.source.get("expectedFiles") != EXPECTED_FILES
            or spec.source.get("sha256") != SOURCE_HASHES
        ):
            raise ValueError("Palworld runtime requires its exact pinned Linux source policy")

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        try:
            self.source_policy(spec)
            result = self.docker.run(["info", "--format", "{{.OSType}}/{{.Architecture}}"])
            available = result.returncode == 0 and result.stdout.strip() in {"linux/x86_64", "linux/amd64"}
            return {
                "available": available,
                "platform": "linux-x64",
                "networkDuringPreparation": True,
                "reason": "" if available else "Linux x86_64 Docker daemon required",
            }
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return {"available": False, "reason": "Linux x86_64 Docker daemon required"}

    def _source(self, spec: RuntimeSpec, source: Path) -> Path:
        self.source_policy(spec)
        root = source
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Palworld acquired installation is missing or unsafe")
        for path in root.rglob("*"):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise ValueError("Palworld source contains a link or special file")
        for name in EXPECTED_FILES:
            if not (root / name).exists():
                raise ValueError("Palworld source is missing a required file")
        for name, expected in SOURCE_HASHES.items():
            with (root / name).open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise ValueError("Palworld source checksum does not match the runtime catalog")
        return root

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: RuntimeProgress
    ) -> RuntimeArtifact:
        try:
            return self._prepare(spec, source, destination, progress=progress)
        except OSError:
            # Operation errors are public. Filesystem exceptions include private
            # acquired-source and artifact paths in their default messages.
            raise RuntimeError(
                "Palworld runtime preparation could not access local inputs or artifact storage"
            ) from None

    def _prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: RuntimeProgress
    ) -> RuntimeArtifact:
        installation = self._source(spec, source)
        if destination.is_symlink():
            raise ValueError("unsafe Palworld artifact directory")
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        progress(5, "staging the pinned native Linux build inputs")
        with tempfile.TemporaryDirectory(prefix="build-", dir=destination) as temporary:
            context = Path(temporary)
            recipe = Path(__file__).with_name("native")
            shutil.copytree(recipe, context / "recipe", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copy2(recipe / "Dockerfile", context / "Dockerfile")
            (context / "recipe/source-policy.json").write_text(json.dumps({"sha256": SOURCE_HASHES}))
            shutil.copytree(installation, context / "installation")
            core = Path(rhenium.__file__).parent
            code = context / "code/rhenium"
            code.mkdir(parents=True)
            shutil.copy2(core / "__init__.py", code / "__init__.py")
            shutil.copytree(
                core / "core", code / "core", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
            shutil.copytree(
                Path(__file__).parent,
                context / "code/rhenium_palworld",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            iidfile = context / "image-id"
            arguments = [
                "build",
                "--platform=linux/amd64",
                "--network=host",
                "--build-arg",
                "HTTP_PROXY",
                "--build-arg",
                "HTTPS_PROXY",
                "--label",
                f"{LABEL}.fingerprint={fingerprint(spec)}",
                "--label",
                f"{LABEL}.recipe={recipe_digest()}",
                "--iidfile",
                str(iidfile),
                str(context),
            ]
            progress(15, "building native UE4SS and the local evaluator image")
            try:
                built = self.docker.run(arguments, timeout=14400)
            except (OSError, RuntimeError, subprocess.SubprocessError):
                raise RuntimeError("Palworld image build could not complete") from None
            log = destination / f"build-{uuid.uuid4().hex}.log"
            descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write((built.stdout + built.stderr)[-4_000_000:])
            if (
                built.returncode
                or not iidfile.is_file()
                or not IMAGE_ID.fullmatch(iidfile.read_text().strip())
            ):
                raise RuntimeError("Palworld image build failed; inspect private runtime build diagnostics")
            image = iidfile.read_text().strip()
        progress(95, "checking immutable runtime image identity")
        artifact = RuntimeArtifact(
            runtime_key=RUNTIME_KEY,
            fingerprint=fingerprint(spec),
            kind="docker-image",
            identity=image,
            metadata={
                "imageId": image,
                "recipeSha256": recipe_digest(),
                "sourceSha256": SOURCE_HASHES,
                "network": "none",
            },
        )
        if self.docker.owned_image(spec, artifact) != image:
            raise RuntimeError("Palworld build returned an unowned image")
        progress(100, "native Linux evaluator image built")
        return artifact

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            self.source_policy(spec)
            image = self.docker.owned_image(spec, artifact)
            nonce = uuid.uuid4().hex
            name = f"rhenium-palworld-verify-{nonce}"
            try:
                result = self.docker.run(
                    [
                        "run",
                        "--pull=never",
                        "--rm",
                        "--name",
                        name,
                        "--label",
                        f"{LABEL}.operation={nonce}",
                        "--network=none",
                        "--read-only",
                        "--cap-drop=ALL",
                        "--security-opt=no-new-privileges:true",
                        "--user=1001:1001",
                        "--entrypoint",
                        "python3",
                        str(image),
                        "/opt/recipe/verify.py",
                    ]
                )
            finally:
                self.docker.cleanup(name, nonce)
            observed = json.loads(result.stdout)
            if result.returncode or not isinstance(observed, dict) or observed.get("available") is not True:
                raise ValueError("runtime file verification failed")
            return {"available": True, "identity": image, "platform": "linux-x64", "network": "none"}
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            return {"available": False, "reason": "Palworld runtime identity or file verification failed"}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        self.source_policy(spec)
        image = self.docker.owned_image(spec, artifact, missing_ok=True)
        if image is not None and self.docker.run(["image", "rm", image]).returncode:
            raise RuntimeError("failed to prune the owned Palworld runtime image")
