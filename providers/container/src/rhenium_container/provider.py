from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rhenium.core.auth import (
    AuthProvider,
    AuthProviderDescriptor,
    AuthSession,
    ChallengeCallback,
    ProgressCallback,
)

_DIGEST_PREFIX = "sha256:"


class ContainerImageProvider(AuthProvider):
    """Acquires a digest-pinned, publicly readable container image.

    Unlike the Steam provider there is no licence to check and no credential to
    store: the image this serves is public, so ``login`` mints an anonymous session
    rather than prompting. It exists because runtime preparation always resolves an
    auth provider, and a public runtime still needs one.

    The security property this does enforce is pinning. ``acquire`` refuses any
    reference that is not ``name@sha256:<64 hex>``, and re-checks the digest that
    the daemon reports after the pull, so a moved tag cannot silently change what a
    benchmark runs against. The cache record also binds that reference to Docker's
    immutable local image ID for the consuming runtime builder to re-check.
    """

    descriptor = AuthProviderDescriptor(
        id="container",
        name="Public container image",
        version="0.1.0",
        capabilities=("docker", "public", "digest-pinned"),
    )

    def __init__(self, docker: str | None = None):
        self._docker = docker or shutil.which("docker") or ""

    # -- credentials ------------------------------------------------------------
    def login(
        self,
        account_alias: str,
        *,
        challenge: ChallengeCallback,
        progress: ProgressCallback,
    ) -> AuthSession:
        del challenge
        progress(100, "public images need no credentials")
        return AuthSession(
            provider_id=self.descriptor.id,
            account_alias=account_alias,
            principal="anonymous",
            secret={},
            metadata={"public": True},
        )

    def validate(self, session: AuthSession) -> AuthSession:
        return session

    # -- acquisition ------------------------------------------------------------
    def _run(self, arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        if not self._docker:
            raise RuntimeError("Docker CLI is not installed")
        return subprocess.run(
            [self._docker, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    @staticmethod
    def _pinned_reference(source: dict[str, Any]) -> str:
        if str(source.get("kind")) != "container-image":
            raise ValueError("container provider only serves container-image sources")
        reference = str(source.get("image") or "")
        name, separator, digest = reference.partition("@")
        if not name or separator != "@" or not digest.startswith(_DIGEST_PREFIX):
            raise ValueError("container image must be pinned as name@sha256:<digest>")
        hexadecimal = digest[len(_DIGEST_PREFIX) :]
        if len(hexadecimal) != 64 or any(character not in "0123456789abcdef" for character in hexadecimal):
            raise ValueError("container image digest is malformed")
        return reference

    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: ProgressCallback,
    ) -> AuthSession:
        reference = self._pinned_reference(source)
        progress(10, f"pulling {reference}")
        pull = self._run(["pull", reference], timeout=3600)
        if pull.returncode != 0:
            raise RuntimeError(f"failed to pull {reference}\n{(pull.stdout + pull.stderr)[-4000:]}")
        progress(80, "verifying the pulled digest")
        inspect = self._run(
            ["image", "inspect", reference, "--format", "{{json .RepoDigests}}"], timeout=60
        )
        if inspect.returncode != 0:
            raise RuntimeError(f"pulled image is not present: {reference}")
        digests = json.loads(inspect.stdout or "[]")
        if not isinstance(digests, list) or not any(
            str(entry).endswith(reference.partition("@")[2]) for entry in digests
        ):
            raise RuntimeError("pulled image does not carry the pinned digest")
        identity = self._run(
            ["image", "inspect", reference, "--format", "{{.Id}}"], timeout=60
        )
        image_id = identity.stdout.strip()
        if identity.returncode != 0 or not self._docker_id(image_id):
            raise RuntimeError("pulled image does not have a valid immutable image ID")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "image.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "image": reference,
                    "imageId": image_id,
                    "repoDigests": digests,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        progress(100, "image ready")
        return session

    @staticmethod
    def _docker_id(value: str) -> bool:
        if not value.startswith(_DIGEST_PREFIX):
            return False
        hexadecimal = value[len(_DIGEST_PREFIX) :]
        return len(hexadecimal) == 64 and all(
            character in "0123456789abcdef" for character in hexadecimal
        )
