from __future__ import annotations

import hashlib
import os
import stat
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class UnsafePathError(ValueError):
    """A path crossed a symbolic link or contained an unsupported object."""


@dataclass(frozen=True)
class TreeEntry:
    relative: str
    mode: int
    size: int
    is_dir: bool


def normalized_relative(raw: str) -> PurePosixPath:
    value = PurePosixPath(raw)
    if (
        not raw
        or value.is_absolute()
        or ".." in value.parts
        or raw != value.as_posix()
        or value.as_posix() == "."
    ):
        raise UnsafePathError("path must be a normalized relative POSIX path")
    return value


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW


def _file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW


def _absolute_parts(path: Path) -> tuple[str, ...]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute():
        raise UnsafePathError("path must be absolute")
    return tuple(part for part in absolute.parts if part != absolute.anchor)


def open_directory_nofollow(path: Path) -> int:
    """Open every path component with O_NOFOLLOW and return the leaf descriptor."""

    current = os.open(path.anchor or "/", _directory_flags())
    try:
        for part in _absolute_parts(path):
            child = os.open(part, _directory_flags(), dir_fd=current)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def ensure_directory_nofollow(path: Path, mode: int = 0o700) -> None:
    """Create a directory without following an existing ancestor or leaf symlink."""

    current = os.open(path.anchor or "/", _directory_flags())
    try:
        for part in _absolute_parts(path):
            try:
                child = os.open(part, _directory_flags(), dir_fd=current)
            except FileNotFoundError:
                os.mkdir(part, mode=mode, dir_fd=current)
                child = os.open(part, _directory_flags(), dir_fd=current)
            os.close(current)
            current = child
        os.fchmod(current, mode)
    finally:
        os.close(current)


def _open_relative_dir(root_fd: int, parts: tuple[str, ...]) -> int:
    current = os.dup(root_fd)
    try:
        for part in parts:
            child = os.open(part, _directory_flags(), dir_fd=current)
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def _read_fd(fd: int, *, maximum: int | None) -> bytes:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise UnsafePathError("source must be a non-linked regular file")
    if maximum is not None and before.st_size > maximum:
        raise UnsafePathError("source file exceeds the permitted size")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if maximum is not None and total > maximum:
            raise UnsafePathError("source file exceeds the permitted size")
    after = os.fstat(fd)
    stable = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if not stable or total != after.st_size:
        raise UnsafePathError("source file changed while it was being snapshotted")
    return b"".join(chunks)


def _hash_fd(fd: int, *, maximum: int | None) -> str:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise UnsafePathError("source must be a non-linked regular file")
    if maximum is not None and before.st_size > maximum:
        raise UnsafePathError("source file exceeds the permitted size")
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
        if maximum is not None and total > maximum:
            raise UnsafePathError("source file exceeds the permitted size")
    after = os.fstat(fd)
    stable = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if not stable or total != after.st_size:
        raise UnsafePathError("source file changed while it was being hashed")
    return digest.hexdigest()


def secure_read_bytes(root: Path, relative: str, *, maximum: int | None = None) -> bytes:
    path = normalized_relative(relative)
    root_fd = open_directory_nofollow(root)
    parent_fd = -1
    file_fd = -1
    try:
        parent_fd = _open_relative_dir(root_fd, tuple(path.parts[:-1]))
        file_fd = os.open(path.name, _file_flags(), dir_fd=parent_fd)
        return _read_fd(file_fd, maximum=maximum)
    except (NotADirectoryError, OSError) as error:
        raise UnsafePathError(f"unsafe or unreadable file: {relative}") from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
        os.close(root_fd)


def secure_file_mode(root: Path, relative: str) -> int:
    """Return a regular file's mode after opening it without following links."""

    path = normalized_relative(relative)
    root_fd = open_directory_nofollow(root)
    parent_fd = -1
    file_fd = -1
    try:
        parent_fd = _open_relative_dir(root_fd, tuple(path.parts[:-1]))
        file_fd = os.open(path.name, _file_flags(), dir_fd=parent_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise UnsafePathError("source must be a non-linked regular file")
        return stat.S_IMODE(info.st_mode)
    except (NotADirectoryError, OSError) as error:
        raise UnsafePathError(f"unsafe or unreadable file: {relative}") from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
        os.close(root_fd)


def secure_file_sha256(
    root: Path, relative: str, *, maximum: int | None = None
) -> str:
    path = normalized_relative(relative)
    root_fd = open_directory_nofollow(root)
    parent_fd = -1
    file_fd = -1
    try:
        parent_fd = _open_relative_dir(root_fd, tuple(path.parts[:-1]))
        file_fd = os.open(path.name, _file_flags(), dir_fd=parent_fd)
        return _hash_fd(file_fd, maximum=maximum)
    except (NotADirectoryError, OSError) as error:
        raise UnsafePathError(f"unsafe or unreadable file: {relative}") from error
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
        os.close(root_fd)


def _inventory(
    fd: int,
    prefix: PurePosixPath,
    entries: list[TreeEntry],
    *,
    maximum_entries: int | None,
    maximum_bytes: int | None,
    totals: list[int],
) -> None:
    for name in sorted(os.listdir(fd)):
        if name in {".", ".."} or "/" in name or "\x00" in name:
            raise UnsafePathError("directory contains an invalid entry name")
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        totals[0] += 1
        if maximum_entries is not None and totals[0] > maximum_entries:
            raise UnsafePathError("tree contains too many entries")
        relative = (prefix / name).as_posix()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            raise UnsafePathError(f"tree contains a symbolic link: {relative}")
        if stat.S_ISDIR(info.st_mode):
            entries.append(TreeEntry(relative, mode, 0, True))
            child = os.open(name, _directory_flags(), dir_fd=fd)
            try:
                _inventory(
                    child,
                    prefix / name,
                    entries,
                    maximum_entries=maximum_entries,
                    maximum_bytes=maximum_bytes,
                    totals=totals,
                )
            finally:
                os.close(child)
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise UnsafePathError(f"tree contains an unsupported file: {relative}")
        totals[1] += info.st_size
        if maximum_bytes is not None and totals[1] > maximum_bytes:
            raise UnsafePathError("tree contains too many bytes")
        entries.append(TreeEntry(relative, mode, info.st_size, False))


def secure_inventory(
    root: Path,
    *,
    maximum_entries: int | None = None,
    maximum_bytes: int | None = None,
) -> tuple[TreeEntry, ...]:
    try:
        root_fd = open_directory_nofollow(root)
    except (NotADirectoryError, OSError) as error:
        raise UnsafePathError("tree root must be a real directory") from error
    try:
        entries: list[TreeEntry] = []
        _inventory(
            root_fd,
            PurePosixPath(),
            entries,
            maximum_entries=maximum_entries,
            maximum_bytes=maximum_bytes,
            totals=[0, 0],
        )
        return tuple(entries)
    finally:
        os.close(root_fd)


def _safe_output_mode(mode: int) -> int:
    return 0o755 if mode & 0o111 else 0o644


def _write_new_file(path: Path, data: bytes, mode: int) -> None:
    parent_fd = open_directory_nofollow(path.parent)
    fd = -1
    try:
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW,
            mode,
            dir_fd=parent_fd,
        )
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, mode)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_fd)


def secure_copy_file(
    source_root: Path,
    relative: str,
    destination_root: Path,
    *,
    destination_relative: str | None = None,
    maximum: int | None = None,
) -> str:
    source_path = normalized_relative(relative)
    target_path = normalized_relative(destination_relative or relative)
    destination = destination_root / target_path.as_posix()
    ensure_directory_nofollow(destination.parent)
    digest, _mode = _copy_file_contents(
        source_root,
        source_path,
        destination,
        maximum=maximum,
    )
    return digest


def _copy_file_contents(
    source_root: Path,
    source_path: PurePosixPath,
    destination: Path,
    *,
    maximum: int | None,
) -> tuple[str, int]:
    source_root_fd = open_directory_nofollow(source_root)
    source_parent_fd = -1
    source_fd = -1
    destination_parent_fd = -1
    destination_fd = -1
    destination_created = False
    try:
        source_parent_fd = _open_relative_dir(
            source_root_fd, tuple(source_path.parts[:-1])
        )
        source_fd = os.open(source_path.name, _file_flags(), dir_fd=source_parent_fd)
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise UnsafePathError("source must be a non-linked regular file")
        if maximum is not None and before.st_size > maximum:
            raise UnsafePathError("source file exceeds the permitted size")
        output_mode = _safe_output_mode(stat.S_IMODE(before.st_mode))
        destination_parent_fd = open_directory_nofollow(destination.parent)
        destination_fd = os.open(
            destination.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | os.O_NOFOLLOW,
            0o600,
            dir_fd=destination_parent_fd,
        )
        destination_created = True
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            if maximum is not None and total > maximum:
                raise UnsafePathError("source file exceeds the permitted size")
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                view = view[written:]
        after = os.fstat(source_fd)
        stable = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) == (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if not stable or total != after.st_size:
            raise UnsafePathError("source file changed while it was being copied")
        os.fchmod(destination_fd, output_mode)
        return digest.hexdigest(), output_mode
    except BaseException:
        if destination_created and destination_parent_fd >= 0:
            if destination_fd >= 0:
                os.close(destination_fd)
                destination_fd = -1
            with suppress(FileNotFoundError):
                os.unlink(destination.name, dir_fd=destination_parent_fd)
        raise
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        if destination_parent_fd >= 0:
            os.close(destination_parent_fd)
        if source_fd >= 0:
            os.close(source_fd)
        if source_parent_fd >= 0:
            os.close(source_parent_fd)
        os.close(source_root_fd)


def secure_copy_tree(source: Path, destination: Path) -> str:
    entries = secure_inventory(source)
    ensure_directory_nofollow(destination)
    digest = hashlib.sha256()
    for entry in entries:
        encoded = entry.relative.encode()
        if entry.is_dir:
            ensure_directory_nofollow(destination / entry.relative)
            digest.update(b"directory\0" + encoded + b"\0")
            continue
        target = destination / entry.relative
        ensure_directory_nofollow(target.parent)
        file_digest, mode = _copy_file_contents(
            source,
            normalized_relative(entry.relative),
            target,
            maximum=None,
        )
        digest.update(b"file\0" + encoded + b"\0" + str(mode).encode() + b"\0")
        digest.update(bytes.fromhex(file_digest))
    return f"sha256:{digest.hexdigest()}"


def secure_tree_hash(root: Path) -> str:
    entries = secure_inventory(root)
    digest = hashlib.sha256()
    for entry in entries:
        encoded = entry.relative.encode()
        if entry.is_dir:
            digest.update(b"directory\0" + encoded + b"\0")
            continue
        mode = _safe_output_mode(entry.mode)
        digest.update(b"file\0" + encoded + b"\0" + str(mode).encode() + b"\0")
        digest.update(bytes.fromhex(secure_file_sha256(root, entry.relative)))
    return f"sha256:{digest.hexdigest()}"


def write_owner_file(path: Path, data: bytes) -> None:
    ensure_directory_nofollow(path.parent)
    _write_new_file(path, data, 0o600)
