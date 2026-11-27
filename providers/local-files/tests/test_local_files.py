from __future__ import annotations

from pathlib import Path

import pytest
from rhenium_local_files.provider import LocalFilesProvider


def _acquire(root: Path, target: Path, include: list[str]) -> None:
    provider = LocalFilesProvider()
    session = provider.login("default", challenge=lambda _: None, progress=lambda *_: None)
    assert session.secret == {}
    provider.acquire(
        {"kind": "local-files", "path": str(root), "include": include},
        session,
        target,
        progress=lambda *_: None,
    )


def test_explicit_selection_and_retry_preserve_user_files(tmp_path: Path) -> None:
    source, cache = tmp_path / "source", tmp_path / "cache"
    (source / "nested").mkdir(parents=True)
    (source / "nested/game.dll").write_bytes(b"fake assembly")
    (source / "personal-save").write_bytes(b"do not copy")
    _acquire(source, cache, ["nested/game.dll"])
    _acquire(source, cache, ["nested/game.dll"])
    assert (cache / "nested/game.dll").read_bytes() == b"fake assembly"
    assert not (cache / "personal-save").exists()
    assert (source / "personal-save").read_bytes() == b"do not copy"
    (source / "nested/game.dll").write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs"):
        _acquire(source, cache, ["nested/game.dll"])
    assert (cache / "nested/game.dll").read_bytes() == b"fake assembly"


@pytest.mark.parametrize("include", [["../secret"], ["/etc"], ["."], ["a", "a"], ["a", "a/b"]])
def test_rejects_unsafe_and_overlapping_selection(tmp_path: Path, include: list[str]) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError):
        _acquire(source, tmp_path / "cache", include)


def test_rejects_symlink_including_selected_ancestor(tmp_path: Path) -> None:
    source, outside = tmp_path / "source", tmp_path / "outside"
    source.mkdir()
    outside.mkdir()
    (outside / "secret").write_text("private")
    (source / "linked").symlink_to(outside, target_is_directory=True)
    for selected in (["linked"], ["linked/secret"]):
        with pytest.raises(ValueError, match="symbolic link"):
            _acquire(source, tmp_path / "cache", selected)
    assert not (tmp_path / "cache").exists()


def test_rejects_source_cache_overlap(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("data")
    with pytest.raises(ValueError, match="overlap"):
        _acquire(tmp_path, tmp_path / "cache", ["file"])


def test_cached_empty_directories_must_match_the_selection(tmp_path: Path) -> None:
    source, cache = tmp_path / "source", tmp_path / "cache"
    (source / "empty").mkdir(parents=True)
    _acquire(source, cache, ["empty"])
    _acquire(source, cache, ["empty"])
    (cache / "unrelated").mkdir()
    with pytest.raises(ValueError, match="differs"):
        _acquire(source, cache, ["empty"])
    assert (cache / "unrelated").is_dir()


def test_source_path_resolves_an_environment_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, cache = tmp_path / "source", tmp_path / "cache"
    source.mkdir()
    (source / "server.jar").write_bytes(b"fake server")
    monkeypatch.setenv("RHENIUM_TEST_SERVER_DIR", str(source))

    _acquire(Path("${RHENIUM_TEST_SERVER_DIR}"), cache, ["server.jar"])

    assert (cache / "server.jar").read_bytes() == b"fake server"


def test_unset_environment_placeholder_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RHENIUM_TEST_SERVER_DIR", raising=False)

    with pytest.raises(ValueError, match="RHENIUM_TEST_SERVER_DIR in the environment"):
        _acquire(Path("${RHENIUM_TEST_SERVER_DIR}"), tmp_path / "cache", ["server.jar"])
    assert not (tmp_path / "cache").exists()
