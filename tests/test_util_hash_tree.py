"""Regression tests pinning ``rhenium.util.hash_tree`` to its original definition.

The digest is persisted as task starter hashes and runtime artifact identities,
so the optimized implementation must stay byte-identical to the original
``pathlib`` implementation (kept verbatim below as ``_reference_hash_tree``) and
must raise the same exception types where the original raised.
"""

from __future__ import annotations

import errno
import hashlib
import os
import random
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest
from pytest import MonkeyPatch

from rhenium import util
from rhenium.util import hash_tree

EMPTY_SHA256 = hashlib.sha256().hexdigest()

# Names whose plain string order differs from ``PurePath`` part order, plus
# dotfiles, unicode (composed and decomposed), and shell-hostile punctuation.
ADVERSARIAL_NAMES = (
    "a b",
    "a-b",
    "a.b",
    "a!",
    "a0",
    "a_",
    "a~",
    "A",
    "B",
    "b",
    "z",
    "ä",
    "á",
    "日本",
    "\U0001f600",
    ".hidden",
    "..double",
    "back\\slash",
    "new\nline",
    "tab\tname",
    "colon:star*",
    "#hash",
)


def _reference_hash_tree(root: Path) -> str:
    """Verbatim copy of the original ``hash_tree`` implementation."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/") or relative == ".DS_Store":
            continue
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _outcome(function: Callable[[Path], str], root: Path) -> tuple[str, object]:
    try:
        return ("digest", function(root))
    except Exception as error:  # noqa: BLE001 - the exception type is the observable result
        return ("raised", type(error))


def _assert_matches_reference(root: Path) -> tuple[str, object]:
    expected = _outcome(_reference_hash_tree, root)
    assert _outcome(hash_tree, root) == expected
    return expected


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _symlink(link: Path, target: str | Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks are unavailable here: {error}")


@contextmanager
def _mode(path: Path, mode: int) -> Iterator[None]:
    original = path.stat().st_mode & 0o7777
    path.chmod(mode)
    try:
        yield
    finally:
        path.chmod(original)


needs_posix_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="needs POSIX permission enforcement for a non-root user",
)


def _build_adversarial_tree(root: Path, outside: Path) -> None:
    for index, name in enumerate(ADVERSARIAL_NAMES):
        _write(root / name, f"top {index}".encode())
        _write(root / "nested" / name / "leaf", f"leaf {index}".encode())
        _write(root / "nested" / f"{name}.txt", f"sibling {index}".encode())
    _write(root / "a" / "b", b"a/b sorts before a-b by parts, after it as a string")
    _write(root / "a" / "b c" / "d", b"deeper")
    # Top-level .git contents and .DS_Store are skipped; everything else is kept.
    _write(root / ".git" / "HEAD", b"ref: refs/heads/main\n")
    _write(root / ".git" / "objects" / "ab" / "cdef", b"\x78\x9c\x00")
    _write(root / ".gitignore", b"*.log\n")
    _write(root / ".github" / "workflow.yml", b"on: push\n")
    _write(root / ".DS_Store", b"top-level finder metadata")
    _write(root / "nested" / ".DS_Store", b"nested finder metadata is hashed")
    _write(root / "nested" / ".git" / "config", b"nested .git is hashed")
    _write(root / "nested" / ".git" / "objects" / "x", b"nested .git object is hashed")
    _write(root / "empty-file", b"")
    _write(root / "binary.bin", bytes(range(256)) * 64)
    (root / "empty-dir").mkdir()
    (root / "nested" / "empty" / "deeper").mkdir(parents=True)
    _write(outside / "outside.txt", b"reached through a file symlink")
    _write(outside / "dir" / "hidden.txt", b"never reached: directory symlinks are not followed")


def test_matches_reference_on_adversarial_tree(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _build_adversarial_tree(root, tmp_path / "outside")

    kind, digest = _assert_matches_reference(root)

    assert kind == "digest"
    assert digest != EMPTY_SHA256


def test_names_are_adversarial_for_string_sorting() -> None:
    relatives = ["a/b", "a b", "a-b", "a.b", "a!", "A", "ä"]
    by_string = sorted(relatives)
    by_parts = [str(path) for path in sorted(Path(relative) for relative in relatives)]

    assert by_string != by_parts


def test_top_level_git_file_and_nested_git_are_hashed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / ".git", b"gitdir: ../elsewhere\n")
    _write(root / "x" / ".git" / "y", b"nested")
    _write(root / "x" / ".DS_Store", b"nested")
    _write(root / ".DS_Store", b"skipped")
    _write(root / ".git-blame-ignore-revs", b"kept")

    reference = _reference_hash_tree(root)
    (root / ".DS_Store").unlink()

    assert hash_tree(root) == reference == _reference_hash_tree(root)
    (root / ".git").unlink()
    assert hash_tree(root) != reference


def test_top_level_git_directory_and_ds_store_are_skipped(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "file.txt", b"content")
    before = hash_tree(root)

    _write(root / ".git" / "HEAD", b"ref: refs/heads/main\n")
    _write(root / ".git" / "refs" / "heads" / "main", b"0" * 40)
    _write(root / ".DS_Store", b"finder")

    assert hash_tree(root) == before == _reference_hash_tree(root)


def test_known_digest_is_stable(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "a-b", b"1")
    _write(root / "a" / "b", b"2")
    _write(root / "a.b", b"3")
    _write(root / ".git" / "HEAD", b"skipped")
    _write(root / ".DS_Store", b"skipped")
    _write(root / "x" / ".DS_Store", b"4")

    expected = hashlib.sha256(b"a/b\x002\x00a-b\x001\x00a.b\x003\x00x/.DS_Store\x004\x00").hexdigest()

    assert _reference_hash_tree(root) == expected
    assert hash_tree(root) == expected


def test_matches_reference_with_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    _build_adversarial_tree(root, outside)
    _symlink(root / "file-link", "a.b")
    _symlink(root / "nested" / "up-file-link", "../a b")
    _symlink(root / "outside-file-link", outside / "outside.txt")
    _symlink(root / "dir-link", "nested", directory=True)
    _symlink(root / "self-dir-link", ".", directory=True)
    _symlink(root / "nested" / "parent-dir-link", "..", directory=True)
    _symlink(root / "outside-dir-link", outside / "dir", directory=True)
    _symlink(root / "broken-link", "does-not-exist")
    _symlink(root / "nested" / "broken-dir-link", "missing/", directory=True)
    _symlink(root / "loop-self", "loop-self")
    _symlink(root / "loop-a", "loop-b")
    _symlink(root / "loop-b", "loop-a")
    _symlink(root / "loop-chain", "loop-a")
    _symlink(root / "link-to-link", "file-link")
    _symlink(root / "git-link", ".git", directory=True)
    _symlink(root / "ds-link", ".DS_Store")

    kind, _digest = _assert_matches_reference(root)

    assert kind == "digest"


def test_directory_symlinks_are_listed_but_not_descended(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "inside" / "file.txt", b"inside")
    _write(tmp_path / "outside" / "file.txt", b"outside")
    before = hash_tree(root)
    _symlink(root / "inside-link", "inside", directory=True)
    _symlink(root / "outside-link", tmp_path / "outside", directory=True)

    assert _assert_matches_reference(root) == ("digest", before)


def test_top_level_git_symlink_to_directory_is_not_descended(tmp_path: Path) -> None:
    root = tmp_path / "root"
    real_git = tmp_path / "real-git"
    _write(real_git / "HEAD", b"ref")
    _write(root / "file.txt", b"content")
    _symlink(root / ".git", real_git, directory=True)

    assert _assert_matches_reference(root) == ("digest", _reference_hash_tree(root))


def test_top_level_file_symlinks_named_like_skipped_entries(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(tmp_path / "target", b"target bytes")
    _write(root / "file.txt", b"content")
    _symlink(root / ".git", tmp_path / "target")
    _symlink(root / ".DS_Store", tmp_path / "target")

    kind, _digest = _assert_matches_reference(root)

    assert kind == "digest"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_special_files_are_ignored_like_reference(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "file.txt", b"content")
    os.mkfifo(root / "pipe")
    (root / "sub").mkdir()
    os.mkfifo(root / "sub" / "pipe")
    _symlink(root / "pipe-link", "pipe")

    assert _assert_matches_reference(root) == ("digest", _reference_hash_tree(root))


def test_root_variants_match_reference(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    root = tmp_path / "root"
    _build_adversarial_tree(root, tmp_path / "outside")
    expected = _reference_hash_tree(root)
    _symlink(tmp_path / "root-link", root, directory=True)
    _write(tmp_path / "plain-file", b"not a directory")

    assert hash_tree(tmp_path / "root-link") == expected == _reference_hash_tree(tmp_path / "root-link")
    assert hash_tree(root / "nested" / "..") == expected
    assert hash_tree(Path(f"{root}/./")) == expected
    assert _assert_matches_reference(root / "nested" / "..") == ("digest", expected)
    assert _assert_matches_reference(tmp_path / "missing") == ("digest", EMPTY_SHA256)
    assert _assert_matches_reference(tmp_path / "plain-file") == ("digest", EMPTY_SHA256)
    (tmp_path / "empty").mkdir()
    assert _assert_matches_reference(tmp_path / "empty") == ("digest", EMPTY_SHA256)

    monkeypatch.chdir(root)
    assert _assert_matches_reference(Path(".")) == ("digest", expected)
    assert _assert_matches_reference(Path("")) == ("digest", expected)
    monkeypatch.chdir(tmp_path)
    assert _assert_matches_reference(Path("root")) == ("digest", expected)
    assert _assert_matches_reference(Path("root/nested")) == (
        "digest",
        _reference_hash_tree(root / "nested"),
    )


@pytest.mark.skipif(os.name != "posix", reason="needs non-UTF-8 POSIX file names")
def test_non_utf8_file_name_raises_like_reference(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _write(root / "ok.txt", b"content")
    try:
        (root / os.fsdecode(b"bad-\xff-name")).write_bytes(b"x")
    except OSError as error:
        pytest.skip(f"file system rejects non-UTF-8 names: {error}")

    assert _assert_matches_reference(root) == ("raised", UnicodeEncodeError)


@needs_posix_permissions
def test_unreadable_file_raises_like_reference(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "secret", b"content")

    with _mode(root / "secret", 0o000):
        assert _assert_matches_reference(root) == ("raised", PermissionError)


@needs_posix_permissions
def test_unlistable_directory_is_skipped_like_reference(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "visible", b"content")
    _write(root / "locked" / "hidden", b"hidden")
    _write(root / "locked" / "sub" / "deeper", b"hidden")

    with _mode(root / "locked", 0o000):
        kind, digest = _assert_matches_reference(root)

    assert kind == "digest"
    _write(tmp_path / "expected" / "visible", b"content")
    assert digest == _reference_hash_tree(tmp_path / "expected")


@needs_posix_permissions
def test_listable_but_unsearchable_directory_raises_like_reference(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write(root / "visible", b"content")
    (root / "listable" / "only-a-subdirectory").mkdir(parents=True)

    with _mode(root / "listable", 0o400):
        assert _assert_matches_reference(root) == ("raised", PermissionError)


@needs_posix_permissions
def test_unsearchable_directory_inside_top_level_git_raises_like_reference(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    _write(root / "visible", b"content")
    _write(root / ".git" / "objects" / "pack", b"never hashed but still inspected")

    with _mode(root / ".git" / "objects", 0o400):
        assert _assert_matches_reference(root) == ("raised", PermissionError)


class _ListingFailsAfterFirstEntry:
    """``os.scandir`` result whose iteration raises ``EIO`` after one entry."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __enter__(self) -> _ListingFailsAfterFirstEntry:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._inner.close()

    def close(self) -> None:
        self._inner.close()

    def __iter__(self) -> Iterator[os.DirEntry[str]]:
        for index, entry in enumerate(self._inner):
            if index == 1:
                raise OSError(errno.EIO, "injected directory read failure")
            yield entry


@pytest.mark.parametrize("failing", ["", "sub", "sub/deeper"])
@pytest.mark.parametrize("stage", ["open", "read"])
def test_directory_listing_errors_match_reference(
    tmp_path: Path, monkeypatch: MonkeyPatch, failing: str, stage: str
) -> None:
    root = tmp_path / "root"
    for directory in ("", "sub", "sub/deeper"):
        for name in ("a", "b", "c"):
            _write(root / directory / name, f"{directory}/{name}".encode())
    failing_path = os.fspath(root / failing) if failing else os.fspath(root)
    real_scandir = os.scandir

    def scandir(path: Any = ".") -> Any:
        if os.fspath(path) != failing_path:
            return real_scandir(path)
        if stage == "open":
            raise OSError(errno.EIO, "injected directory open failure")
        return _ListingFailsAfterFirstEntry(real_scandir(path))

    monkeypatch.setattr(os, "scandir", scandir)

    # ``rglob`` skips a directory it cannot open, but ``Path.walk()`` lets a
    # read error on an opened directory escape instead of hashing a partial tree.
    expected_kind = "digest" if stage == "open" else "raised"
    assert _assert_matches_reference(root)[0] == expected_kind


@pytest.mark.parametrize("seed", range(12))
def test_matches_reference_on_random_trees(tmp_path: Path, seed: int) -> None:
    generator = random.Random(seed)
    alphabet = ["a", "A", "b", " ", "-", ".", "!", "_", "0", "~", "ä", "Ä"]
    root = tmp_path / "root"
    root.mkdir()
    directories = [root]
    for index in range(generator.randint(20, 80)):
        parent = generator.choice(directories)
        name = "".join(generator.choice(alphabet) for _ in range(generator.randint(1, 4)))
        if name in {".", ".."}:
            name = f"{name}x"
        target = parent / name
        if target.exists() or target.is_symlink():
            continue
        choice = generator.random()
        if choice < 0.35:
            target.mkdir()
            directories.append(target)
        elif choice < 0.9:
            target.write_bytes(f"{seed}:{index}".encode() * generator.randint(0, 5))
        else:
            other = generator.choice(directories)
            _symlink(target, os.path.relpath(other, parent), directory=True)
    if generator.random() < 0.5 and not (root / ".git").exists():
        _write(root / ".git" / "objects" / "file", b"skipped")
    if generator.random() < 0.5 and not (root / ".DS_Store").exists():
        _write(root / ".DS_Store", b"skipped")

    kind, _digest = _assert_matches_reference(root)

    assert kind == "digest"


def test_case_insensitive_ordering_matches_windows_path_order(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "case-probe").write_bytes(b"")
    if (root / "CASE-PROBE").exists():
        pytest.skip("file system is case-insensitive")
    (root / "case-probe").unlink()
    names = ["B", "a", "A", "b-c", "B.c", "b", "Ä", "ä", "Z", "y"]
    for name in names:
        _write(root / name, name.encode())
        for top in ("Dir", "dir"):
            _write(root / top / f"{name}.txt", name.encode())
            for middle in ("Sub", "sub"):
                _write(root / top / middle / name / "leaf", name.encode())

    # ``sorted`` of Windows paths is stable, so ties keep ``rglob`` order, as the
    # original implementation behaves on a case-insensitive platform.
    expected = [
        path.as_posix()
        for path in sorted(
            PureWindowsPath(item.relative_to(root).as_posix()) for item in root.rglob("*") if item.is_file()
        )
    ]
    monkeypatch.setattr(util, "_CASE_SENSITIVE_PATHS", False)

    assert [relative for _key, relative, _path in util._tree_files(root)] == expected
