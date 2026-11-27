"""Download and safely unpack a repository tree at one exact commit.

The tree is fetched once per (repository, commit) through GitHub's tarball
endpoint and cached under the authoring state directory. Extraction refuses
links, device files, absolute paths and escaping names, and drops what the
verifier's submission-shape gate would reject in a starter (compiled classes
and archives other than build-tool wrapper jars, build output, IDE and CI
folders).
"""

from __future__ import annotations

import io
import json
import shutil
import tarfile
from pathlib import Path, PurePosixPath

import httpx

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_TREE_BYTES = 128 * 1024 * 1024
MAX_TREE_FILES = 20_000
_WRAPPER_JARS = frozenset({"gradle/wrapper/gradle-wrapper.jar", ".mvn/wrapper/maven-wrapper.jar"})
_DROPPED_TOP_LEVEL = frozenset({".github", ".gitlab", ".idea", ".vscode", ".circleci", "wiki"})
_DROPPED_ANYWHERE = frozenset({".git", "build", "target", ".gradle", "out", "node_modules"})
_DROPPED_SUFFIXES = frozenset({".class", ".jar", ".zip", ".war", ".ear"})


class CheckoutError(RuntimeError):
    """The tree cannot be used as a starter; the message is safe to record."""


def kept(relative: PurePosixPath) -> bool:
    """Whether a path inside the unpacked tree is kept in the starter."""
    parts = relative.parts
    if not parts or parts[0] in _DROPPED_TOP_LEVEL:
        return False
    if any(part in _DROPPED_ANYWHERE for part in parts[:-1]):
        return False
    if relative.suffix.casefold() in _DROPPED_SUFFIXES:
        return any(relative.as_posix().endswith(jar) for jar in _WRAPPER_JARS)
    return True


def unpack(archive: bytes, destination: Path) -> dict[str, int]:
    """Unpack a GitHub tarball (one top-level folder) into ``destination``."""
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise CheckoutError("repository archive exceeds the size limit")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    files = 0
    total = 0
    dropped = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            for member in bundle:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts:
                    raise CheckoutError("repository archive contains an escaping path")
                if len(name.parts) < 2:
                    continue  # the archive's top-level folder itself
                relative = PurePosixPath(*name.parts[1:])
                if member.isdir():
                    continue
                if not member.isfile():
                    # Symbolic and hard links, devices and FIFOs never enter a starter.
                    dropped += 1
                    continue
                if not kept(relative):
                    dropped += 1
                    continue
                files += 1
                total += member.size
                if files > MAX_TREE_FILES or total > MAX_TREE_BYTES:
                    raise CheckoutError("repository tree exceeds the size limit")
                source = bundle.extractfile(member)
                if source is None:
                    continue
                target = destination.joinpath(*relative.parts)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise CheckoutError("repository archive contains an escaping path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    except tarfile.TarError as error:
        raise CheckoutError("repository archive is not a valid tarball") from error
    if files == 0:
        raise CheckoutError("repository archive is empty")
    return {"files": files, "bytes": total, "dropped": dropped}


class RepositoryCheckout:
    """Tarball cache: ``<root>/<owner>/<repo>/<sha>/tree``."""

    def __init__(self, client: httpx.Client, root: Path):
        self.client = client
        self.root = root

    def tree(self, repository: str, sha: str) -> Path:
        owner, name = repository.split("/", 1)
        folder = self.root / owner.casefold() / name.casefold() / sha
        tree = folder / "tree"
        marker = folder / "checkout.json"
        if marker.is_file() and tree.is_dir():
            return tree
        folder.mkdir(parents=True, exist_ok=True)
        try:
            response = self.client.get(
                f"/repos/{repository}/tarball/{sha}", follow_redirects=True, timeout=300
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise CheckoutError(
                f"repository archive request failed (HTTP {error.response.status_code})"
            ) from None
        except httpx.HTTPError:
            raise CheckoutError("repository archive request failed (transport error)") from None
        summary = unpack(response.content, tree)
        marker.write_text(json.dumps({"repository": repository, "sha": sha, **summary}) + "\n")
        return tree
