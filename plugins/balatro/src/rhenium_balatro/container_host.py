"""Owned Linux desktop container transport for reviewed Balatro submissions."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .files import reject_links
from .linux_runtime import identity, sha
from .native_assets import json_write_new

RUNTIME_ID = "balatro-linux-17459173-container-v1"
RUNTIME_KEY = "balatro/" + RUNTIME_ID
KIND = "balatro-reviewed-linux-container-v1"
ASSETS = Path(__file__).with_name("container_assets")
IMAGE_ID = re.compile(r"sha256:[a-f0-9]{64}")
LABEL = "org.rhenium.balatro.runtime-owner"
RECORD = "container-runtime-v1.json"


def source_files() -> dict[str, Path]:
    import rhenium

    core = Path(rhenium.__file__).resolve().parent
    plugin = Path(__file__).resolve().parent
    files = {"core/rhenium/__init__.py": core / "__init__.py"}
    files.update({"core/rhenium/" + p.relative_to(core).as_posix(): p
                  for p in (core / "core").rglob("*.py")})
    for path in plugin.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files["plugin/rhenium_balatro/" + path.relative_to(plugin).as_posix()] = path
    return files


def recipe() -> str:
    return identity({name: sha(path) for name, path in sorted(source_files().items())})


def build_context(destination: Path) -> str:
    destination.mkdir(parents=True)
    sources = source_files()
    snapshot = {name: sha(path) for name, path in sources.items()}
    for name, path in sources.items():
        reject_links(path)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha(target) != snapshot[name]:
            raise ValueError("Runtime source changed while creating its capsule")
    for name in ("Dockerfile", "requirements.txt"):
        shutil.copyfile(ASSETS / name, destination / name)
    expected = identity(snapshot)
    if recipe() != expected:
        raise ValueError("Runtime source changed while creating its capsule")
    return expected


def inspect_image(image: str) -> dict[str, Any] | None:
    if not IMAGE_ID.fullmatch(image):
        raise ValueError("A concrete immutable image ID is required")
    result = subprocess.run(["docker", "image", "inspect", image], capture_output=True,
                            text=True, timeout=60, check=False)
    if result.returncode != 0:
        if "no such image" in result.stderr.lower() or "no such object" in result.stderr.lower():
            return None
        raise RuntimeError("The Docker daemon could not inspect the owned image")
    rows = json.loads(result.stdout)
    if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
            or rows[0].get("Id") != image):
        raise ValueError("Docker returned another image identity")
    return dict(rows[0])


def image_labels(details: dict[str, Any]) -> dict[str, Any]:
    config = details.get("Config")
    if not isinstance(config, dict):
        raise ValueError("Image configuration is unavailable")
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise ValueError("Image ownership labels are unavailable")
    return labels


def mount(path: Path, *, readonly: bool) -> list[str]:
    reject_links(path)
    if not path.is_absolute() or not path.exists() or any(c in str(path) for c in (",", "\n", "\0")):
        raise ValueError("Container mounts require existing absolute, unlinked paths")
    return ["--mount", f"type=bind,source={path},target={path}" + (",readonly" if readonly else "")]


def run_worker(
    image: str, request: dict[str, Any], work: Path,
    *, readonly: tuple[Path, ...], writable: tuple[Path, ...], prepare: bool = False,
) -> dict[str, Any]:
    if not IMAGE_ID.fullmatch(image):
        raise ValueError("Evaluation cannot resolve a mutable image tag")
    work.mkdir(parents=True, mode=0o700)
    nonce = uuid.uuid4().hex
    message = {**request, "image": image, "nonce": nonce, "response": str(work / "response.json")}
    json_write_new(work / "request.json", message)
    name = "rhenium-balatro-" + nonce
    command = ["docker", "run", "--rm", "--init", "--name", name,
               "--network", "bridge" if prepare else "none", "--read-only",
               "--cap-drop=ALL", "--security-opt=no-new-privileges", "--memory=8g",
               "--cpus=16", "--pids-limit=256", "--user", f"{os.getuid()}:{os.getgid()}",
               "--tmpfs", "/tmp:rw,exec,nosuid,size=512m,mode=1777", "--interactive"]
    for path in readonly:
        command += mount(path, readonly=True)
    for path in writable:
        command += mount(path, readonly=False)
    command.append(image)
    try:
        with (work / "controller.log").open("xb") as log:
            result = subprocess.run(command, input=(json.dumps(message) + "\n").encode(),
                                    stdout=log, stderr=log, timeout=1890, check=False)
        if result.returncode != 0:
            raise RuntimeError("Owned container controller did not exit normally")
        response = work / "response.json"
        reject_links(response)
        data = response.read_bytes()
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Container response exceeds its bound")
        value = json.loads(data)
        if (not isinstance(value, dict) or value.get("nonce") != nonce
                or value.get("image") != image):
            raise ValueError("Container response identity mismatch")
        if "error" in value:
            raise RuntimeError("Container operation failed; inspect its private receipt")
        if not isinstance(value.get("result"), dict):
            raise ValueError("Container response has no result object")
        return dict(value["result"])
    except BaseException:
        # Only this invocation's exact, owned container; evidence directories remain intact.
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=60, check=False)
        raise


def native_context(context: BenchmarkContext, root: Path) -> BenchmarkContext:
    return BenchmarkContext(project_root=context.project_root, pack_root=context.pack_root,
                            state_dir=root / "operator-state", cache_dir=root / "plugin-cache")


def load_record(artifact: RuntimeArtifact) -> tuple[Path, dict[str, Any]]:
    root = Path(artifact.location or "")
    reject_links(root)
    if not root.is_absolute() or artifact.kind != KIND or artifact.runtime_key != RUNTIME_KEY:
        raise ValueError("Unexpected controlled container artifact")
    file = root / RECORD
    reject_links(file)
    record = json.loads(file.read_text())
    if artifact.identity != "sha256:" + identity(record) or artifact.metadata != record:
        raise ValueError("Container artifact record changed")
    return root, dict(record)
