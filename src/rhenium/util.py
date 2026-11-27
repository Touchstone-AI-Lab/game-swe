from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from datetime import datetime
from operator import itemgetter
from pathlib import Path
from typing import Any


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=_json_default)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value)!r}")


def hash_tree(root: Path) -> str:
    """Return the SHA-256 content digest of the regular files below ``root``.

    Each file contributes its POSIX path relative to ``root``, a NUL byte, its
    bytes and a NUL byte, in ``pathlib`` path order. Files below a top-level
    ``.git`` directory and a top-level ``.DS_Store`` are excluded.

    The digest is persisted as task starter hashes and runtime artifact
    identities, so it must stay byte-identical to the original definition::

        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            relative = path.relative_to(root).as_posix()
            ...

    evaluated on Python 3.12: symlinked directories are listed but not
    descended into, symlinks to files are followed, and broken or looping
    symlinks are ignored. :func:`_tree_files` reproduces that traversal with
    ``os.scandir`` and plain strings, which avoids the ``pathlib`` overhead of
    ``relative_to`` and of sorting ``Path`` objects.
    """
    digest = hashlib.sha256()
    for _key, relative, path in _tree_files(root):
        if relative.startswith(".git/") or relative == ".DS_Store":
            continue
        digest.update(relative.encode() + b"\0")
        with open(path, "rb", buffering=0) as handle:
            digest.update(handle.read())
        digest.update(b"\0")
    return digest.hexdigest()


# Errors that ``Path.is_file()`` reports as "not a file" instead of raising
# (``pathlib._IGNORED_ERRNOS`` and ``pathlib._IGNORED_WINERRORS`` in Python 3.12).
_IS_FILE_IGNORED_ERRNOS = frozenset({errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP})
_IS_FILE_IGNORED_WINERRORS = frozenset({21, 123, 1921})
# ``PurePath`` ordering compares ``str(path).split(sep)``, lower-cased when the
# platform path flavour is case-insensitive.
_CASE_SENSITIVE_PATHS = os.path.normcase("Aa") == "Aa"

_TreeFile = tuple[list[str], str, str]


def _is_file(path: str) -> bool:
    """Return exactly what ``Path(path).is_file()`` returns, or raise what it raises."""
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError as error:
        if (
            getattr(error, "errno", None) in _IS_FILE_IGNORED_ERRNOS
            or getattr(error, "winerror", None) in _IS_FILE_IGNORED_WINERRORS
        ):
            return False
        raise
    except ValueError:
        return False


def _tree_files(root: Path) -> list[_TreeFile]:
    """Return ``(sort key, POSIX relative path, path string)`` for every file.

    This mirrors ``sorted(p for p in root.rglob("*") if p.is_file())`` on
    Python 3.12, including the order of ``stat`` calls: ``rglob`` lists the
    entries of ``root`` and then, following ``Path.walk()`` (top-down, without
    following symlinks), the entries of each subdirectory when its parent is
    walked. A directory that cannot be opened is skipped, as ``rglob`` does.
    An error while reading an opened directory propagates: ``rglob`` lists
    every directory twice and only ``Path.walk()``'s listing lets that error
    escape, so skipping it would silently drop files from the digest.
    """
    files: list[_TreeFile] = []
    if not root.is_dir():
        return files

    # Path strings are built the way ``Path._make_child_relpath`` builds them.
    root_text = str(root)
    if len(root.parts) > (1 if root.anchor else 0):
        root_prefix = root_text + os.sep
    elif root_text != ".":
        root_prefix = root_text
    else:
        root_prefix = ""

    def scan(directory: str, path_prefix: str, relative_prefix: str) -> list[tuple[str, str]]:
        """Record the files of one directory and return its real subdirectories."""
        try:
            iterator = os.scandir(directory)
        except OSError:
            return []
        with iterator:
            entries = list(iterator)
        subdirectories: list[tuple[str, str]] = []
        for entry in entries:
            path = path_prefix + entry.name
            relative = relative_prefix + entry.name
            try:
                is_directory = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_directory = False
            if is_directory:
                subdirectories.append((path, relative))
            if _is_file(path):
                key = relative if _CASE_SENSITIVE_PATHS else relative.lower()
                files.append((key.split("/"), relative, path))
        return subdirectories

    pending = [scan(root_text, root_prefix, "")]
    while pending:
        children = pending.pop()
        expanded = [scan(path, path + os.sep, relative + "/") for path, relative in children]
        pending.extend(reversed(expanded))

    # ``list.sort`` is stable, so equal keys keep the ``rglob`` order as ``sorted`` did.
    files.sort(key=itemgetter(0))
    return files
