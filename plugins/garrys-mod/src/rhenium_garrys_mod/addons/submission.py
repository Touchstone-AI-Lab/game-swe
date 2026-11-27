from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


class GmodSubmissionError(ValueError):
    pass


_PUBLIC_SUPPORT_FILES = {
    ".rhenium-game",
    "AGENTS.md",
    "CLAUDE.md",
    "EXAM.md",
    "PROMPT.md",
    "TASK.md",
    "task.json",
}


@dataclass(frozen=True)
class GmodSubmissionTree:
    root: Path
    files: tuple[PurePosixPath, ...]
    digest: str
    addon: dict[str, Any]


def _is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or bool(
        hasattr(os.path, "isjunction") and os.path.isjunction(path)
    )


def _addon_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GmodSubmissionError("addon.json must be valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise GmodSubmissionError("addon.json must contain an object")
    title = value.get("title")
    addon_type = value.get("type")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise GmodSubmissionError("addon.json title must be a non-blank string")
    if addon_type != "servercontent":
        raise GmodSubmissionError("addon.json type must be servercontent")
    ignore = value.get("ignore")
    if ignore is not None and (
        not isinstance(ignore, list)
        or any(not isinstance(item, str) or not item.strip() for item in ignore)
    ):
        raise GmodSubmissionError("addon.json ignore must be a list of non-blank strings")
    return value


def validate_submission_tree(
    root: Path,
    *,
    required_files: tuple[str, ...] | list[str] = (),
) -> GmodSubmissionTree:
    """Validate the exact tree used by analysis, hashing, and server installation.

    A submission may contain ``addon.json``, public attempt guidance, and regular
    ``.lua`` files below ``lua/``. Links, junctions, other file types, and escaped
    required paths are rejected before any evaluator executes candidate code.
    """

    raw = root.expanduser()
    if _is_link_or_junction(raw):
        raise GmodSubmissionError("submission root must not be a link or junction")
    try:
        resolved = raw.resolve(strict=True)
    except OSError as error:
        raise GmodSubmissionError("submission root is unavailable") from error
    if not resolved.is_dir():
        raise GmodSubmissionError("submission root must be a directory")

    logical_files: list[PurePosixPath] = []
    for current, directories, files in os.walk(resolved, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in tuple(directories):
            child = current_path / name
            if _is_link_or_junction(child):
                raise GmodSubmissionError(
                    "submission must not contain links or junctions: "
                    f"{child.relative_to(resolved).as_posix()}"
                )
        for name in files:
            child = current_path / name
            relative = PurePosixPath(child.relative_to(resolved).as_posix())
            if _is_link_or_junction(child) or not child.is_file():
                raise GmodSubmissionError(f"submission file is unsafe: {relative}")
            if relative.as_posix() == "addon.json" or relative.as_posix() in _PUBLIC_SUPPORT_FILES:
                pass
            elif not relative.is_relative_to(PurePosixPath("lua")) or child.suffix.lower() != ".lua":
                raise GmodSubmissionError(f"unsupported submission file: {relative}")
            logical_files.append(relative)

    logical_files.sort(key=lambda item: item.as_posix())
    available = {item.as_posix() for item in logical_files}
    for raw_required in required_files:
        logical = PurePosixPath(raw_required)
        if (
            not raw_required
            or "\\" in raw_required
            or logical.is_absolute()
            or ".." in logical.parts
            or logical.as_posix() != raw_required
        ):
            raise GmodSubmissionError(f"required path is unsafe: {raw_required}")
        if raw_required not in available:
            raise GmodSubmissionError(f"required file is missing: {raw_required}")

    if "addon.json" not in available:
        raise GmodSubmissionError("required file is missing: addon.json")
    addon = _addon_manifest(resolved / "addon.json")
    digest = hashlib.sha256()
    for logical in logical_files:
        digest.update(logical.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update((resolved / Path(*logical.parts)).read_bytes())
        digest.update(b"\0")
    return GmodSubmissionTree(resolved, tuple(logical_files), digest.hexdigest(), addon)


def copy_submission_tree(tree: GmodSubmissionTree, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for logical in tree.files:
        source = tree.root / Path(*logical.parts)
        target = destination / Path(*logical.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
