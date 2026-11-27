from __future__ import annotations

import os
import re
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from rhenium.core.auth import (
    AuthProvider,
    AuthProviderDescriptor,
    AuthSession,
    ChallengeCallback,
    ProgressCallback,
)


class LocalSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    path: str
    include: list[str] = Field(min_length=1)
    expectedFiles: list[str] = Field(default_factory=list)
    sha256: str | None = None


_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand(value: str) -> str:
    """Resolve ${VARIABLE} placeholders in a source path.

    A shared runtime catalog cannot name an operator's directory, so a catalog may point at
    one through the environment instead of hard-coding a path from one machine.
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        resolved = os.environ.get(name, "").strip()
        if not resolved:
            raise ValueError(f"local source path needs {name} in the environment")
        return resolved

    return _PLACEHOLDER.sub(replace, value)


class LocalFilesProvider(AuthProvider):
    descriptor = AuthProviderDescriptor(
        id="local-files",
        name="Operator-owned local files",
        version="0.1.0",
        capabilities=("local-only", "explicit-snapshot"),
    )

    def login(
        self,
        account_alias: str,
        *,
        challenge: ChallengeCallback,
        progress: ProgressCallback,
    ) -> AuthSession:
        del challenge
        progress(
            100, "local snapshots require no credentials; ownership remains the operator's responsibility"
        )
        return AuthSession(provider_id=self.id, account_alias=account_alias, principal="local", secret={})

    def validate(self, session: AuthSession) -> AuthSession:
        if session.provider_id != self.id or session.secret:
            raise ValueError("invalid local-files session")
        return session

    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: ProgressCallback,
    ) -> AuthSession:
        self.validate(session)
        try:
            spec = LocalSource.model_validate(source)
        except ValueError:
            raise ValueError("invalid local-files source") from None
        root = Path(_expand(spec.path))
        if spec.kind != "local-files" or not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ValueError("local source must be an existing absolute directory")
        root = root.resolve()
        target = destination.resolve()
        if target.is_relative_to(root) or root.is_relative_to(target):
            raise ValueError("local source and acquisition cache must not overlap")
        names = spec.include
        if (
            len(names) != len(set(names))
            or any(
                not name
                or name == "."
                or PurePosixPath(name).is_absolute()
                or ".." in PurePosixPath(name).parts
                or PurePosixPath(name).as_posix() != name
                or "\\" in name
                for name in names
            )
            or any(a != b and PurePosixPath(a).is_relative_to(b) for a in names for b in names)
        ):
            raise ValueError("include must contain unique non-overlapping relative paths")
        # Validate the complete selection before copying. Never follow symlinks or
        # special files out of the explicitly selected installation.
        selected: dict[str, Path] = {}
        selected_directories: set[str] = set()
        for name in names:
            item = root / name
            if any(parent.is_symlink() for parent in item.parents if parent.is_relative_to(root)):
                raise ValueError("local source contains a symbolic link")
            selected_directories.update(
                parent.relative_to(root).as_posix()
                for parent in item.parents
                if parent != root and parent.is_relative_to(root)
            )
            for path in [item, *item.rglob("*")]:
                mode = path.lstat().st_mode
                if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    raise ValueError("local source contains a symbolic link or special file")
                if path.is_file():
                    selected[path.relative_to(root).as_posix()] = path
                else:
                    selected_directories.add(path.relative_to(root).as_posix())
        if destination.is_symlink():
            raise ValueError("local acquisition cache must not be a symbolic link")
        if destination.exists() and any(destination.iterdir()):
            cached = list(destination.rglob("*"))
            if any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in cached):
                raise ValueError("local acquisition cache contains unsafe entries")
            files = {path.relative_to(destination).as_posix(): path for path in cached if path.is_file()}
            directories = {path.relative_to(destination).as_posix() for path in cached if path.is_dir()}
            if (
                directories == selected_directories
                and set(files) == set(selected)
                and all(
                    files[name].read_bytes() == original.read_bytes() for name, original in selected.items()
                )
            ):
                progress(100, "reusing unchanged local source snapshot")
                return session
            raise ValueError(
                "local acquisition cache differs from source; inspect and prune it before retrying"
            )
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        for index, name in enumerate(names, 1):
            item = root / name
            (destination / name).parent.mkdir(parents=True, exist_ok=True)
            if item.is_dir():
                shutil.copytree(item, destination / name, symlinks=True)
            else:
                shutil.copy2(item, destination / name, follow_symlinks=False)
            if index == len(names) or index % max(1, len(names) // 10) == 0:
                progress(int(index * 100 / len(names)), "copying selected local source files")
        # Fail closed if the source changed to a symlink during acquisition.
        if any(path.is_symlink() for path in destination.rglob("*")):
            raise ValueError("local source changed during acquisition")
        return session
