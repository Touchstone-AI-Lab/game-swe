from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

from rhenium.core.plugin import BenchmarkContext


def _default_dst_root() -> Path | None:
    configured = os.environ.get("RHENIUM_PLUGIN_DST_ROOT")
    if configured:
        return Path(configured).expanduser()
    if platform.system() == "Darwin":
        root = (
            Path.home()
            / "Library/Application Support/Steam/steamapps/common/Don't Starve Together"
            / "dontstarve_steam.app/Contents"
        )
        return root if root.exists() else None
    root = Path.home() / ".steam/steam/steamapps/common/Don't Starve Together"
    return root if root.exists() else None


@dataclass(frozen=True)
class DstRuntimeConfig:
    pack_root: Path
    dst_root: Path | None = None
    server_binary: Path | None = None
    cache_dir: Path | None = None

    @classmethod
    def load(cls, context: BenchmarkContext) -> DstRuntimeConfig:
        configured_binary = os.environ.get("RHENIUM_PLUGIN_DST_SERVER_BIN")
        return cls(
            pack_root=context.pack_root,
            dst_root=_default_dst_root(),
            server_binary=Path(configured_binary).expanduser() if configured_binary else None,
            cache_dir=context.cache_dir,
        )
