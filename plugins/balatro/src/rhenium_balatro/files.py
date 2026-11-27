"""Bounded file handling for reviewed submissions; this is not an OS sandbox."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILE_BYTES = 512 * 1024
MAX_SUBMISSION_BYTES = 2 * 1024 * 1024


def relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or not path.parts or path.is_absolute() or value != path.as_posix()
            or any(part in {".", ".."} for part in path.parts)
            or len(path.parts) > 16 or not re.fullmatch(r"[A-Za-z0-9_./-]+", value)):
        raise ValueError("invalid asset path")
    for part in path.parts:
        if part.endswith(".") or part.split(".")[0].upper() in {
            "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            raise ValueError("invalid asset path")
    return value


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError("linked paths are not accepted")


def asset(root: Path, name: str) -> Path:
    candidate = root / relative_path(name)
    reject_links(candidate)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError("asset escapes root")
    return candidate


def read_file(root: Path, name: str) -> bytes:
    path = asset(root, name)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
        raise ValueError("invalid asset size or type")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    after = path.stat()
    reject_links(path)
    if len(data) > MAX_FILE_BYTES or (before.st_ino, before.st_mtime_ns, before.st_size) != (
        after.st_ino, after.st_mtime_ns, after.st_size
    ):
        raise ValueError("asset changed while reading")
    return data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_digest(files: dict[str, str]) -> str:
    return digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())


def read_json(root: Path, name: str) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(read_file(root, name), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def empty_destination(destination: Path) -> None:
    reject_links(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)


def validate_state(pack: Path, state: Path) -> None:
    reject_links(state)
    if state.resolve().is_relative_to(pack.resolve()):
        raise ValueError("generated state must be outside the benchmark pack")


def write_new(root: Path, name: str, data: bytes) -> None:
    target = asset(root, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
