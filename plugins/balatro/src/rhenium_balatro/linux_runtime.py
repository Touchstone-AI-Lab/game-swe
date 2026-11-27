"""Managed source preparation for the versioned Linux capability probe.

This builder does not yet bind benchmark tasks or claim engine validation. The
provider acquires the licensed game; this module never sees provider sessions.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeProgress, RuntimeSpec

from .native_assets import json_write_new

RUNTIME_ID = "balatro-linux-17459173-probe-v1"
RUNTIME_KEY = f"balatro/{RUNTIME_ID}"
RECIPE = Path(__file__).with_name("linux_assets")
GAME_SHA = "0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47"
SOURCE = {"kind": "steam-depots", "appId": 2379780, "buildId": 17459173, "os": "windows",
          "depots": [{"id": 2379781, "manifest": "3512319404653808464"}],
          "expectedFiles": ["Balatro.exe"], "sha256": {"Balatro.exe": GAME_SHA}}


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tree(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("runtime contains an external symbolic link")
            result[name] = {"link": path.readlink().as_posix()}
        elif path.is_file():
            result[name] = {"sha256": sha(path), "executable": bool(path.stat().st_mode & 0o111)}
        elif not path.is_dir():
            raise ValueError("runtime contains a special file")
    return result


def identity(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def recipe_identity() -> str:
    return identity({"builder": sha(Path(__file__)), "assets": tree(RECIPE)})


def fingerprint(spec: RuntimeSpec) -> str:
    from .plugin import BalatroBenchmarkPlugin

    return spec.fingerprint(plugin_id="balatro", plugin_version=BalatroBenchmarkPlugin.descriptor.version)


def validate_source(spec: RuntimeSpec, source: Path) -> Path:
    if (spec.id != RUNTIME_ID or spec.provider != "steam" or not spec.restricted
            or spec.host_platforms != ("linux-x64",) or spec.source != SOURCE):
        raise ValueError("Linux probe requires the exact reviewed Steam source policy")
    game = source / "Balatro.exe"
    if source.is_symlink() or game.is_symlink() or not game.is_file() or sha(game) != GAME_SHA:
        raise ValueError("provider-acquired game does not match the fixed source checksum")
    return game


def download(item: dict[str, Any], destination: Path) -> bytes:
    # Official fixed URLs and SHA-256 from the versioned recipe, never a submission URL.
    with urllib.request.urlopen(item["url"], timeout=60) as response:
        data = response.read(64 * 1024 * 1024 + 1)
    if len(data) > 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("pinned dependency download failed its content check")
    with destination.open("xb") as stream:
        stream.write(data)
    return data


def unpack_frozen(data: bytes, item: dict[str, Any], destination: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        prefixes = {name.split("/", 1)[0] for name in archive.namelist()}
        if len(prefixes) != 1:
            raise ValueError("unexpected dependency archive layout")
        prefix = prefixes.pop()
        for name, expected in item["files"].items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe dependency path")
            content = archive.read(f"{prefix}/{name}")
            if item.get("checkout_line_endings") == "CRLF":
                content = content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            if {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()} != expected:
                raise ValueError("dependency does not reproduce the frozen byte identity")
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(content)


class BalatroLinuxProbeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext):
        self.context = context

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        available = (platform.system() == "Linux" and platform.machine() in {"x86_64", "amd64"}
                     and spec.id == RUNTIME_ID and spec.source == SOURCE)
        return {"available": available, "platform": "linux-x64", "engineValidated": False,
                "scope": "capability-probe-only", "requiresVisibleDisplayAtExecution": True,
                "reason": "" if available else "reviewed Linux x86_64 host and exact source required"}

    def prepare(self, spec: RuntimeSpec, source: Path, destination: Path, *,
                progress: RuntimeProgress) -> RuntimeArtifact:
        if not self.doctor(spec)["available"]:
            raise ValueError("Linux probe host unavailable")
        game = validate_source(spec, source)
        if destination.is_symlink():
            raise ValueError("unsafe artifact location")
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        root = destination / "probe-tree-v1"
        root.mkdir(mode=0o700)  # Existing/partial evidence must not be overwritten.
        downloads = destination / "downloads-v1"
        downloads.mkdir(mode=0o700)
        progress(5, "validating the fixed licensed game payload")
        (root / "game").mkdir()
        shutil.copyfile(game, root / "game/Balatro.exe")
        recipe = json.loads((RECIPE / "dependencies-v1.json").read_text())
        for name, item in recipe["downloads"].items():
            progress(15, f"fetching fixed {name} bytes for the Linux probe")
            data = download(item, downloads / name)
            if name in {"smods", "bot"}:
                unpack_frozen(data, item, root / "mods" / name)
            elif name == "lovely":
                with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                    members = [m for m in archive.getmembers() if Path(m.name).name == "liblovely.so"]
                    if len(members) != 1 or not members[0].isfile():
                        raise ValueError("Lovely release has no unique library")
                    stream = archive.extractfile(members[0])
                    assert stream is not None
                    (root / "liblovely.so").write_bytes(stream.read())
            elif name == "love":
                appimage = downloads / name
                appimage.chmod(0o700)
                with (destination / "love-extract-v1.log").open("xb") as log:
                    subprocess.run([str(appimage), "--appimage-extract"], cwd=root, check=True,
                                   stdout=log, stderr=log, timeout=60, env={"PATH": "/usr/bin:/bin"})
        shutil.copytree(RECIPE / "mods", root / "authored-mods")
        contents = tree(root)
        marker: dict[str, Any] = {"schema_version": 1, "runtime_key": RUNTIME_KEY,
                  "fingerprint": fingerprint(spec),
                  "recipe": recipe_identity(), "files": contents, "identity": "sha256:" + identity(contents)}
        json_write_new(destination / "probe-artifact-v1.json", marker)
        artifact = RuntimeArtifact(runtime_key=RUNTIME_KEY, fingerprint=fingerprint(spec),
            kind="balatro-linux-probe-tree-v1", identity=marker["identity"], location=str(root),
            metadata={"recipeSha256": marker["recipe"], "engineValidated": False,
                      "sourceSha256": GAME_SHA, "scope": "capability-probe-only"})
        if not self.verify(spec, artifact)["available"]:
            raise ValueError("prepared probe artifact did not verify")
        progress(100, "probe inputs prepared; real-engine validation is still required")
        return artifact

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        try:
            root = Path(artifact.location or "")
            marker = json.loads((root.parent / "probe-artifact-v1.json").read_text())
            available = (root.is_absolute() and not root.is_symlink()
                and artifact.runtime_key == RUNTIME_KEY and artifact.fingerprint == fingerprint(spec)
                and artifact.kind == "balatro-linux-probe-tree-v1"
                and marker["recipe"] == recipe_identity() == artifact.metadata["recipeSha256"]
                and tree(root) == marker["files"]
                and artifact.identity == marker["identity"] == "sha256:" + identity(marker["files"])
                and sha(root / "game/Balatro.exe") == GAME_SHA)
        except (OSError, ValueError, KeyError):
            available = False
        return {"available": available, "engineValidated": False, "scope": "capability-probe-only"}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        # No external image/service is owned. Core removes its own selected cache.
        if artifact.runtime_key != RUNTIME_KEY or artifact.fingerprint != fingerprint(spec):
            raise ValueError("refuse unrelated artifact")
