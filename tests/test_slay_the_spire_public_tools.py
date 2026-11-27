"""Public image identity and preflight failures must precede licensed builds."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import runpy
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import ModuleType

import pytest

RUNTIME = Path(__file__).parents[1] / "benchmarks/slay-the-spire-core/private/native-runtime"
REFERENCE = "ghcr.io/example/sts-tools@sha256:" + "a" * 64
IMAGE_ID = "sha256:" + "b" * 64


@pytest.fixture
def preparer(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(RUNTIME))
    spec = importlib.util.spec_from_file_location("sts_public_tools", RUNTIME / "prepare.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    return module


def fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    pack = tmp_path / "clone/benchmarks/example"
    runtime = pack / "private/native-runtime"
    runtime.mkdir(parents=True)
    game = tmp_path / "game.jar"
    game.write_bytes(b"synthetic licensed input for unit testing")
    (runtime / "game-input.json").write_text(json.dumps({
        "expected_sha256": {"desktop-1.0.jar": hashlib.sha256(game.read_bytes()).hexdigest()},
    }))
    recipe = runtime / "recipe.py"
    recipe.write_bytes(b"frozen recipe")
    (runtime / "recipe-manifest.json").write_text(json.dumps({
        "files": {"recipe.py": hashlib.sha256(recipe.read_bytes()).hexdigest()},
    }))
    task = pack / "private/harbor/downfall-example"
    task.mkdir(parents=True)
    source = task / "resource.png"
    source.write_bytes(b"materialized resource bytes")
    metadata = pack / "validation/native-engine"
    (metadata / "downfall-example").mkdir(parents=True)
    (metadata / "tasks.json").write_text(json.dumps([{"id": "downfall-example"}]))
    (metadata / "downfall-example/frozen-manifest.json").write_text(json.dumps({
        "files": {"resource.png": hashlib.sha256(source.read_bytes()).hexdigest()},
    }))
    (runtime / "public-tools-image.json").write_text(json.dumps({
        "image": REFERENCE, "image_id": IMAGE_ID, "platform": "linux/amd64",
    }))
    return runtime, game, tmp_path / "scratch"


@pytest.mark.parametrize("failure", ["game", "recipe", "lfs", "inside", "existing"])
def test_preflight_rejects_invalid_inputs_before_docker(
    preparer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    runtime, game, output = fixture_inputs(tmp_path)
    if failure == "game":
        game.write_bytes(b"wrong version")
    elif failure == "recipe":
        (runtime / "recipe.py").write_text("changed")
    elif failure == "lfs":
        (runtime.parent / "harbor/downfall-example/resource.png").write_bytes(
            b"version https://git-lfs.github.com/spec/v1\n"
        )
    elif failure == "inside":
        output = runtime.parents[3] / "scratch"
    else:
        output.mkdir()

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Invalid input reached Docker")

    monkeypatch.setattr(preparer.subprocess, "check_output", forbidden)
    monkeypatch.setattr(preparer.subprocess, "run", forbidden)
    with pytest.raises((ValueError, FileExistsError)):
        preparer.prepare(runtime, game, output)
    assert output.exists() == (failure == "existing")


@pytest.mark.parametrize(
    "failure", [None, "containerd", "tag", "repository", "config", "platform", "download"],
)
def test_pull_requires_published_digest_and_expected_configuration(
    preparer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None,
) -> None:
    runtime, _, _ = fixture_inputs(tmp_path)
    lock_path = runtime / "public-tools-image.json"
    if failure == "tag":
        lock = json.loads(lock_path.read_text())
        lock["image"] = "ghcr.io/example/sts-tools:latest"
        lock_path.write_text(json.dumps(lock))
    # The containerd image store reports the pinned manifest digest as the image ID.
    manifest_digest = REFERENCE.rsplit("@", 1)[1]
    image_ids = {"config": "sha256:" + "c" * 64, "containerd": manifest_digest}
    details = {
        "RepoDigests": [] if failure == "repository" else [REFERENCE],
        "Id": image_ids.get(failure or "", IMAGE_ID),
        "Os": "linux", "Architecture": "arm64" if failure == "platform" else "amd64",
    }
    calls: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        assert check
        calls.append(command)
        if failure == "download":
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(preparer.subprocess, "run", fake_run)
    monkeypatch.setattr(preparer.subprocess, "check_output", lambda *a, **kw: json.dumps([details]))
    if failure is None:
        assert preparer.pull_tools(runtime) == (REFERENCE, IMAGE_ID)
    elif failure == "containerd":
        assert preparer.pull_tools(runtime) == (REFERENCE, manifest_digest)
    else:
        with pytest.raises((ValueError, subprocess.CalledProcessError)):
            preparer.pull_tools(runtime)
    assert calls == ([] if failure == "tag" else [
        ["docker", "pull", "--platform", "linux/amd64", REFERENCE],
    ])


@pytest.mark.parametrize("corrupt", [False, True])
def test_package_rebuild_uses_snapshot_and_keeps_original_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corrupt: bool,
) -> None:
    lock, output = tmp_path / "locks", tmp_path / "packages"
    lock.mkdir()
    payload = b"synthetic deb payload"
    digest = hashlib.sha512(payload).hexdigest()
    filename = "example_1.0_amd64.deb"
    (lock / "runtime-package-lock.json").write_text(json.dumps({"snapshot_utc": "20260921T000000Z"}))
    (lock / "package-uris.txt").write_text(
        f"'http://archive.ubuntu.com/ubuntu/pool/main/e/example/{filename}' "
        f"{filename} {len(payload)} SHA512:{digest}\n"
    )
    urls: list[str] = []

    def fetch(url: str, *, timeout: int) -> io.BytesIO:
        urls.append(url)
        assert timeout > 0
        return io.BytesIO(b"x" * len(payload) if corrupt else payload)

    monkeypatch.setattr(urllib.request, "urlopen", fetch)
    monkeypatch.setattr(sys, "argv", [
        "fetch_locked_runtime_packages.py", "--lock-dir", str(lock), "--output", str(output),
    ])
    script = str(RUNTIME / "scripts/fetch_locked_runtime_packages.py")
    if corrupt:
        with pytest.raises(AssertionError):
            runpy.run_path(script, run_name="__main__")
        assert not (output / filename).exists()
        assert not (output / "packages-receipt.json").exists()
    else:
        runpy.run_path(script, run_name="__main__")
        assert (output / filename).read_bytes() == payload
        receipt = json.loads((output / "packages-receipt.json").read_text())
        assert receipt[0]["sha512"] == digest
    assert urls == [f"https://snapshot.ubuntu.com/ubuntu/20260921T000000Z/pool/main/e/example/{filename}"]
