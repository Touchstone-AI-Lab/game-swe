from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

from rhenium.core.plugin import BenchmarkContext

# ``PalServer.exe`` is only a launcher: it spawns the real shipping server as a
# child process, so terminating it leaves an orphaned server holding the UE4SS
# mods directory. The shipping binary is therefore preferred.
_WINDOWS_SERVER_BINARIES = (
    Path("Pal/Binaries/Win64/PalServer-Win64-Shipping.exe"),
    Path("Pal/Binaries/Win64/PalServer-Win64-Shipping-Cmd.exe"),
    Path("PalServer.exe"),
)


def _default_palworld_root() -> Path | None:
    configured = os.environ.get("RHENIUM_PLUGIN_PALWORLD_ROOT")
    if configured:
        return Path(configured).expanduser()
    if platform.system() != "Windows":
        # Pocketpair documents server-side mods for the Windows dedicated server
        # only, so no other host is probed automatically.
        return None
    for candidate in (
        Path("C:/Program Files (x86)/Steam/steamapps/common/PalServer"),
        Path.home() / "Steam/steamapps/common/PalServer",
    ):
        if candidate.exists():
            return candidate
    return None


@dataclass(frozen=True)
class PalworldRuntimeConfig:
    pack_root: Path
    palworld_root: Path | None = None
    server_binary: Path | None = None
    context: BenchmarkContext | None = None

    @classmethod
    def load(cls, context: BenchmarkContext) -> PalworldRuntimeConfig:
        configured_binary = os.environ.get("RHENIUM_PLUGIN_PALWORLD_SERVER_BIN")
        return cls(
            pack_root=context.pack_root,
            context=context,
            palworld_root=_default_palworld_root(),
            server_binary=Path(configured_binary).expanduser() if configured_binary else None,
        )

    def candidate_binaries(self) -> tuple[Path, ...]:
        if self.server_binary:
            return (self.server_binary,)
        if not self.palworld_root:
            return ()
        return tuple(self.palworld_root / relative for relative in _WINDOWS_SERVER_BINARIES)
