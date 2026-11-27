from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from rhenium.core.plugin import BenchmarkContext

from .catalog import GmodCatalog


@dataclass(frozen=True)
class GmodRuntimeConfig:
    dataset_dir: Path
    server_root: Path | None
    runs_root: Path
    pinned_build: str
    server_branch: str
    app_id: int
    platform: str
    timeout_seconds: float = 600.0

    @staticmethod
    def _runs_root(context: BenchmarkContext) -> Path:
        state = context.state_dir
        # Hub pack state is <state>/packs/garrys-mod/addons. GMod rejects a
        # junction-resolved data path containing an `addons` component, so the
        # native runner uses a sibling state-owned runtime root with an opaque
        # pack name. Direct evaluator contexts retain their established layout.
        if (
            state.name == "addons"
            and state.parent.name == "garrys-mod"
            and state.parent.parent.name == "packs"
        ):
            return state.parents[2] / "runtime-runs" / "gma"
        return state / "runs"

    @classmethod
    def load(cls, context: BenchmarkContext, catalog: GmodCatalog) -> GmodRuntimeConfig:
        runtime = catalog.runtime
        configured = os.environ.get("RHENIUM_PLUGIN_GMOD_SERVER_ROOT")
        server_root = None
        pinned_build = runtime.build_id
        runtime_platform: str = runtime.platform
        if sys.platform == "win32":
            default_root = Path(r"D:\GameCodeBench-runtime\gmod-server\stable")
            server_root = Path(configured).expanduser() if configured else default_root
        elif sys.platform == "linux" and platform.machine().lower() in {"x86_64", "amd64"}:
            runtime_platform = "linux-x86_64"
            if runtime.linux_build_id is not None:
                pinned_build = runtime.linux_build_id
                server_root = Path(configured).expanduser() if configured else None
        ceiling = os.environ.get("RHENIUM_PLUGIN_GMOD_GLOBAL_TIMEOUT", "600")
        return cls(
            dataset_dir=context.pack_root,
            server_root=server_root,
            runs_root=cls._runs_root(context),
            pinned_build=pinned_build,
            server_branch=runtime.branch,
            app_id=runtime.app_id,
            platform=runtime_platform,
            timeout_seconds=float(ceiling),
        )
