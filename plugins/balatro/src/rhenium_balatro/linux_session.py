"""Platform plumbing for the byte-identical frozen Session/RPC/scenarios.

One controller process installs one adapter. No task assertions or gameplay are
implemented here. Evaluation inputs must already be prepared and source-reviewed.
"""

from __future__ import annotations

import importlib
import json
import platform
import sys
import time
import types
import uuid
from pathlib import Path
from typing import Any

from . import linux_window
from .files import content_digest, digest, reject_links
from .linux_process import NativeProcess
from .linux_runtime import RECIPE, sha
from .native_assets import adapter_identity, verified_assets
from .review import candidate_identity


def legacy_tree_hash(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True).encode())


class LinuxSessionHost:
    def __init__(
        self,
        *,
        builder: Any,
        spec: Any,
        artifact: Any,
        pack: Path,
        assets_sha256: str,
        run_root: Path,
        windows_powershell: Path | None,
        review_state: Path | None = None,
    ) -> None:
        started = time.monotonic()
        reject_links(run_root)
        if not run_root.is_absolute() or run_root.resolve().is_relative_to(pack.resolve()):
            raise ValueError("Process state must be absolute and outside the pack")
        self.builder, self.spec, self.artifact = builder, spec, artifact
        self.pack, self.assets_sha256 = pack, assets_sha256
        self.assets = verified_assets(pack, assets_sha256)
        self.run_root, self.windows_powershell = run_root, windows_powershell
        self.review_state = review_state if review_state is not None else run_root.parent
        self.runtimes: list[NativeProcess] = []
        if not builder.verify(spec, artifact)["available"]:
            raise ValueError("Prepared artifact verification failed")
        for name in ("evaluate", "rpc", "checks"):
            if sha(RECIPE / f"legacy/poc/{name}.py") != self.assets["controller_files"][f"poc/{name}.py"]:
                raise ValueError("Frozen controller copy changed")
        self.environment = content_digest(
            {
                "artifact": artifact.identity,
                "profile": linux_window.PROFILE
                if linux_window.enabled(artifact)
                else "visible-null-audio-gs1-fast0-headless0-v1",
                "window_resources": content_digest(linux_window.resources())
                if linux_window.enabled(artifact)
                else "none",
                "machine": platform.machine(),
                "kernel": platform.release(),
                "python": platform.python_version(),
                "python_executable": sha(Path(sys.executable)),
                "distribution": sha(Path("/etc/os-release")),
                "libc": " ".join(platform.libc_ver()),
                "windows_process_guard": sha(windows_powershell)
                if windows_powershell is not None
                else "none",
            }
        )
        self.harness = self.harness_identity()
        self.preflight_seconds = time.monotonic() - started

    @staticmethod
    def harness_identity() -> str:
        files = {"adapter": adapter_identity(), "window_resources": content_digest(linux_window.resources())}
        files.update(
            {
                f"frozen/{name}": sha(RECIPE / "legacy/poc" / name)
                for name in ("evaluate.py", "rpc.py", "checks.py")
            }
        )
        return content_digest(files)

    def verify(self) -> None:
        verified_assets(self.pack, self.assets_sha256)
        if (
            self.harness_identity() != self.harness
            or not self.builder.verify(self.spec, self.artifact)["available"]
        ):
            raise ValueError("Execution inputs changed")

    def write(self, path: Path, value: Any) -> None:
        reject_links(path)
        if not any(
            r.owns_directory and path.resolve().is_relative_to(r.directory.resolve()) for r in self.runtimes
        ):
            raise ValueError("Scenario output escaped the owned process directories")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )

    def fingerprints(self, task_files: dict[str, Any], candidate: Path | None) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "harness": self.harness,
            "task": legacy_tree_hash(task_files),
            "candidate": candidate_identity(candidate)[1] if candidate is not None else None,
        }

    def install(self) -> Any:
        if any(
            name == "poc" or name.startswith("poc.") or name == "scripts" or name.startswith("scripts.")
            for name in sys.modules
        ):
            raise ValueError("Controller namespace already populated")
        host = self

        class PlatformRuntime(NativeProcess):
            def __init__(
                self,
                label: str,
                *,
                candidate: Path | None = None,
                task_mods: dict[str, Path],
                task_files: dict[str, Any],
            ) -> None:
                del label  # A label is never an acceptance input.
                prepare_started = time.monotonic()
                host.verify()
                self.run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
                self.input_fingerprints = host.fingerprints(task_files, candidate)
                mods = dict(task_mods)
                if candidate is not None:
                    if "candidate" in mods:
                        raise ValueError("Reserved candidate staging name")
                    mods["candidate"] = candidate
                super().__init__(
                    builder=host.builder,
                    spec=host.spec,
                    artifact=host.artifact,
                    directory=host.run_root / self.run_id,
                    extra_mods=mods,
                    windows_powershell=host.windows_powershell,
                    audio_backend="null",
                    candidate_sha256=self.input_fingerprints["candidate"],
                )
                self.started = prepare_started
                host.runtimes.append(self)

            def start(self) -> Any:
                client = super().start()
                self.metadata["fingerprints"] = self.input_fingerprints
                host.write(self.directory / "session-inputs.json", self.input_fingerprints)
                return client

        poc: Any = types.ModuleType("poc")
        poc.__path__ = [str(RECIPE / "legacy/poc")]
        sys.modules["poc"] = poc
        # Same exception and Client classes in both the process and frozen scenario.
        sys.modules["poc.rpc"] = importlib.import_module("rhenium_balatro.linux_assets.legacy.poc.rpc")
        runtime: Any = types.ModuleType("poc.runtime")
        runtime.Runtime, runtime.ROOT, runtime.write = PlatformRuntime, self.run_root, self.write
        sys.modules["poc.runtime"] = runtime
        task_module: Any = types.ModuleType("poc.tasks")
        task_module.TASKS, task_module.Task = {}, types.SimpleNamespace
        sys.modules["poc.tasks"] = task_module
        scripts: Any = types.ModuleType("scripts")
        scripts.__path__ = []
        audit: Any = types.ModuleType("scripts.audit")
        audit.sha, audit.write, audit.tree_hash = sha, self.write, legacy_tree_hash
        sys.modules.update({"scripts": scripts, "scripts.audit": audit})
        return importlib.import_module("poc.evaluate")
