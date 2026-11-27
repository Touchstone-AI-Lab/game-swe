"""The javac preflight's image classpath cache must survive a TMPDIR on another device.

``_export_from_image`` publishes the export with ``os.replace``, which cannot move a
directory across filesystems. Staging therefore has to live beside the cache, which
means the cache's parent must exist before the staging directory is created.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "checks" / "_javac_check.py"
CONTAINER = "a" * 64
MANIFEST = (
    "/opt/paper/versions/1.21.11/paper-1.21.11.jar\n"
    "/opt/paper/libraries/com/google/guava/guava/33.jar\n"
)


@pytest.fixture
def check_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("javac_check_cache", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_docker_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
    """Stand in for `docker create|cp|rm`, materialising whatever `cp` was asked for."""
    action = command[1]
    if action == "create":
        return SimpleNamespace(returncode=0, stdout=CONTAINER + "\n", stderr="")
    if action == "rm":
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    assert action == "cp"
    source = command[2].split(":", 1)[1]
    target = Path(command[3])
    target.parent.mkdir(parents=True, exist_ok=True)
    if source == "/opt/gcb/classpath.txt":
        target.write_text(MANIFEST, encoding="utf-8")
    elif source == "/opt/paper/libraries":
        # `docker cp` of a directory writes its contents into the target.
        jar = target / "com/google/guava/guava/33.jar"
        jar.parent.mkdir(parents=True, exist_ok=True)
        jar.write_bytes(b"jar")
    else:
        target.write_bytes(b"jar")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_export_stages_beside_the_cache_and_publishes_it(
    check_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A cache root that does not exist yet: the regression staged in TMPDIR here.
    cache_root = tmp_path / "state" / "authoring" / "minecraft-classpath"
    monkeypatch.setenv(check_module.CACHE_VARIABLE, str(cache_root))
    monkeypatch.setattr(check_module.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(check_module.subprocess, "run", _fake_docker_run)

    staged_in: list[Path | None] = []
    real_mkdtemp = tempfile.mkdtemp

    def recording_mkdtemp(*args: Any, **kwargs: Any) -> str:
        directory = kwargs.get("dir")
        staged_in.append(Path(directory) if directory is not None else None)
        return real_mkdtemp(*args, **kwargs)

    monkeypatch.setattr(check_module.tempfile, "mkdtemp", recording_mkdtemp)

    cache = check_module._export_from_image("gcb-minecraft-paper-verifier:test")

    assert staged_in == [cache_root], "staging must sit inside the cache root, not TMPDIR"
    assert cache.parent == cache_root
    assert (cache / "classpath.txt").read_text(encoding="utf-8") == MANIFEST
    assert (cache / "opt/paper/libraries/com/google/guava/guava/33.jar").is_file()
    assert (cache / "opt/gcb/harness/gcb-harness.jar").is_file()


def test_a_complete_cache_is_reused_without_docker(
    check_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_root = tmp_path / "minecraft-classpath"
    monkeypatch.setenv(check_module.CACHE_VARIABLE, str(cache_root))
    monkeypatch.setattr(check_module.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(check_module.subprocess, "run", _fake_docker_run)
    first = check_module._export_from_image("gcb-minecraft-paper-verifier:test")

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a complete cache must not shell out to docker again")

    monkeypatch.setattr(check_module.subprocess, "run", refuse)
    assert check_module._export_from_image("gcb-minecraft-paper-verifier:test") == first


def test_export_fails_closed_when_docker_is_absent(
    check_module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(check_module.CACHE_VARIABLE, str(tmp_path / "cache"))
    monkeypatch.setattr(check_module.shutil, "which", lambda _name: None)
    with pytest.raises(check_module.CheckUnavailable):
        check_module._export_from_image("gcb-minecraft-paper-verifier:test")
