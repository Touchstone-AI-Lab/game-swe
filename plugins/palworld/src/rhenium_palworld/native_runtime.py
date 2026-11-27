from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

import rhenium
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog, RuntimeSpec

PLUGIN_VERSION = "0.7.0"
RUNTIME_ID = "palworld-linux-25247047-native-2397c7b"
RUNTIME_KEY = f"palworld/{RUNTIME_ID}"
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")
LABEL = "org.rhenium.palworld"
SERVER_BINARY = "Pal/Binaries/Linux/PalServer-Linux-Shipping"
SOURCE_HASHES = {
    SERVER_BINARY: "8d5c5cb6277a46713df2ad329d7b6887068b39fa98fcf84b8a5dfa3a00caa666",
    "linux64/steamclient.so": "1a99f39637a505ce2dbfec697dafa118c2d1b8df7dea1412557e2d5ad0a2c7d4",
}
EXPECTED_FILES = [SERVER_BINARY, "linux64/steamclient.so", "Pal/Content/Paks"]


def host_supported() -> bool:
    return platform.system() == "Linux" and platform.machine().lower() in {"x86_64", "amd64"}


def runtime_spec(pack: Path) -> RuntimeSpec:
    catalog = RuntimeCatalog.load(pack, "runtimes.json")
    return next(item for item in catalog.runtimes if item.id == RUNTIME_ID)


def recipe_digest() -> str:
    package = Path(__file__).parent
    core = Path(rhenium.__file__).parent
    roots = [("plugin", package), ("core", core / "core")]
    values = [("core/__init__.py", (core / "__init__.py").read_bytes())]
    for prefix, root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                values.append((prefix + "/" + path.relative_to(root).as_posix(), path.read_bytes()))
    return hashlib.sha256(
        b"".join(name.encode() + b"\0" + hashlib.sha256(data).digest() for name, data in sorted(values))
    ).hexdigest()


def fingerprint(spec: RuntimeSpec) -> str:
    return spec.fingerprint(plugin_id="palworld", plugin_version=PLUGIN_VERSION)


def artifact_image(spec: RuntimeSpec, artifact: RuntimeArtifact) -> str:
    if not isinstance(artifact, RuntimeArtifact):
        raise ValueError("Palworld runtime artifact must use the core artifact contract")
    image = artifact.metadata.get("imageId")
    if (
        spec.id != RUNTIME_ID
        or artifact.runtime_key != RUNTIME_KEY
        or artifact.fingerprint != fingerprint(spec)
        or artifact.kind != "docker-image"
        or not isinstance(image, str)
        or not IMAGE_ID.fullmatch(image)
        or artifact.identity != image
        or artifact.metadata.get("recipeSha256") != recipe_digest()
        or artifact.metadata.get("sourceSha256") != SOURCE_HASHES
    ):
        raise ValueError("Palworld runtime artifact is stale or has invalid identity")
    return image


class NativeDocker:
    def __init__(self, docker: str | None = None):
        self.docker = docker if docker is not None else shutil.which("docker") or ""

    def run(self, arguments: list[str], *, timeout: float = 300) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise RuntimeError("Docker CLI is not installed")
        return subprocess.run(
            [self.docker, *arguments],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
        )

    def inspect_image(self, image: str, *, missing_ok: bool = False) -> dict[str, Any] | None:
        inspected = self.run(["image", "inspect", image])
        if inspected.returncode:
            if missing_ok and "No such image" in inspected.stderr:
                return None
            raise RuntimeError("Palworld runtime image is unavailable")
        rows = json.loads(inspected.stdout)
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise RuntimeError("invalid Palworld image metadata")
        return rows[0]

    def owned_image(
        self, spec: RuntimeSpec, artifact: RuntimeArtifact, *, missing_ok: bool = False
    ) -> str | None:
        image = artifact_image(spec, artifact)
        row = self.inspect_image(image, missing_ok=missing_ok)
        if row is None:
            return None
        config = row.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            row.get("Id") != image
            or row.get("Os") != "linux"
            or row.get("Architecture") != "amd64"
            or not isinstance(labels, dict)
            or labels.get(f"{LABEL}.fingerprint") != fingerprint(spec)
            or labels.get(f"{LABEL}.recipe") != recipe_digest()
        ):
            raise ValueError("Palworld runtime image identity or ownership does not match")
        return image

    def cleanup(self, name: str, nonce: str) -> None:
        found = self.run(["container", "inspect", name, "--format", "{{json .Config.Labels}}"])
        if found.returncode:
            return
        labels = json.loads(found.stdout)
        if not isinstance(labels, dict) or labels.get(f"{LABEL}.operation") != nonce:
            raise RuntimeError("refusing to remove an unowned Palworld container")
        if self.run(["container", "rm", "--force", name]).returncode:
            raise RuntimeError("failed to remove owned Palworld container")


class NativeServerRunner:
    def __init__(self, context: BenchmarkContext):
        self.context = context
        self.docker = NativeDocker()

    def run_assertions(
        self, submission: Path, server_test: Path, artifact: RuntimeArtifact, timeout: int = 180
    ) -> dict[str, Any]:
        diagnostics = ""
        try:
            if not host_supported():
                raise ValueError("Palworld managed evaluation requires a Linux x86_64 host")
            spec = runtime_spec(self.context.pack_root)
            image = self.docker.owned_image(spec, artifact)
            root = self.context.cache_dir / "native-evaluations"
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if root.is_symlink():
                raise ValueError("unsafe Palworld evaluation cache")
            with tempfile.TemporaryDirectory(prefix="run-", dir=root) as temporary:
                state = Path(temporary)
                if submission.is_symlink():
                    raise ValueError("submission root must not be a symbolic link")
                for path in submission.rglob("*"):
                    if path.is_symlink() or not (path.is_file() or path.is_dir()):
                        raise ValueError("submission contains a symbolic link or special file")
                snapshot = state / "submission"
                shutil.copytree(submission, snapshot, symlinks=True)
                if any(path.is_symlink() for path in snapshot.rglob("*")):
                    raise ValueError("submission changed during snapshot")
                suite = state / "assertions.lua"
                shutil.copy2(server_test, suite)
                # Only these read-only bind mounts cross into the disposable game
                # container. No state directory, credential or Docker socket is mounted.
                snapshot.chmod(0o755)
                for path in snapshot.rglob("*"):
                    path.chmod(0o755 if path.is_dir() else 0o644)
                suite.chmod(0o644)
                nonce = uuid.uuid4().hex
                name = f"rhenium-palworld-{nonce}"
                command = [
                    "run",
                    "--pull=never",
                    "--name",
                    name,
                    "--network=none",
                    "--cpus=8",
                    "--memory=16g",
                    "--pids-limit=1024",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
                    "--user=1001:1001",
                    "--label",
                    f"{LABEL}.operation={nonce}",
                    "--mount",
                    f"type=bind,source={snapshot.resolve()},target=/submission,readonly",
                    "--mount",
                    f"type=bind,source={suite.resolve()},target=/assertions.lua,readonly",
                    str(image),
                    "--nonce",
                    nonce,
                    "--timeout",
                    str(timeout),
                ]
                try:
                    completed = self.docker.run(command, timeout=timeout + 120)
                finally:
                    self.docker.cleanup(name, nonce)
                diagnostics = completed.stdout + completed.stderr
                marker = "@@RHENIUM_PALWORLD_WORKER@@" + nonce + ":"
                payloads = [
                    line[len(marker) :] for line in completed.stdout.splitlines() if line.startswith(marker)
                ]
                if completed.returncode or len(payloads) != 1:
                    raise RuntimeError("Palworld container did not return one complete worker result")
                value = json.loads(payloads[0])
                if (
                    not isinstance(value, dict)
                    or not isinstance(value.get("status"), str)
                    or value.get("status") not in {"passed", "failed", "error", "unavailable"}
                    or not isinstance(value.get("cases"), list)
                ):
                    raise ValueError("invalid Palworld worker result")
                expected = re.findall(r'\bctx\s*:\s*case\s*\(\s*"([^"\n]+)"', suite.read_text())
                cases = value["cases"]
                if any(
                    not isinstance(case, dict)
                    or not isinstance(case.get("name"), str)
                    or type(case.get("passed")) is not bool
                    for case in cases
                ):
                    raise ValueError("invalid Palworld worker case record")
                if value["status"] in {"passed", "failed"} and (
                    not expected
                    or len(cases) != len(expected)
                    or {case.get("name") for case in cases if isinstance(case, dict)} != set(expected)
                ):
                    raise ValueError("Palworld worker omitted required engine assertions")
                if value["status"] == "passed" and not all(case["passed"] for case in cases):
                    raise ValueError("Palworld worker status contradicts its case results")
                return value
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, StopIteration) as error:
            try:
                logs = self.context.cache_dir / "native-diagnostics"
                if logs.is_symlink():
                    raise OSError("unsafe diagnostics directory")
                logs.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(
                    logs / f"run-{uuid.uuid4().hex}.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(descriptor, "w") as stream:
                    stream.write((str(error) + "\n" + diagnostics)[-2_000_000:])
            except OSError:
                pass
            return {
                "status": "error",
                "message": "prepared Palworld runtime execution failed; inspect private runtime diagnostics",
                "cases": [],
                "log": "",
            }
