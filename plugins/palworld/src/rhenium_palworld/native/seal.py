"""Configure and seal the private runtime during Docker build only."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path


def make_runtime_code_readable(root: Path) -> None:
    # Operator caches/installations can use umask 077. Copied source is public
    # runtime code, and must be readable by the unprivileged engine user.
    for path in [root, *root.rglob("*")]:
        path.chmod((path.stat().st_mode & 0o777) | (0o555 if path.is_dir() else 0o444))


def main() -> None:
    make_runtime_code_readable(Path("/opt/recipe"))
    make_runtime_code_readable(Path("/opt/rhenium"))
    root = Path("/server")
    # Depot downloads preserve file bytes but do not carry executable modes.
    server = root / "Pal/Binaries/Linux/PalServer-Linux-Shipping"
    server.chmod(server.stat().st_mode | 0o111)
    loader = root / "ue4ss"
    settings = loader / "UE4SS-settings.ini"
    text = settings.read_text()
    for name in ("ConsoleEnabled", "GuiConsoleEnabled", "GuiConsoleVisible", "EnableHotReloadSystem"):
        text = re.sub(rf"(?m)^{name}\s*=.*$", f"{name} = 0", text)
    text = re.sub(r"(?m)^\w+\s*=\s*$", "", text)
    text = text.replace("FExecVTableOffsetInLocalPlayer = 0x28", "FExecVTableOffsetInLocalPlayer = 40")
    settings.write_text(text)
    (loader / "Mods/mods.txt").write_text("")
    for marker in (loader / "Mods").rglob("enabled.txt"):
        marker.unlink()
    for unwanted in ("Saved", ".sentry-native"):
        path = root / "Pal" / unwanted
        if path.exists():
            shutil.rmtree(path)
    shutil.copy2("/opt/recipe/run-native", root / "run-native")
    (root / "run-native").chmod(0o755)
    client = root / "runtime-home/.steam/sdk64/steamclient.so"
    client.parent.mkdir(parents=True)
    shutil.copy2(root / "linux64/steamclient.so", client)
    names = [
        "Pal/Binaries/Linux/PalServer-Linux-Shipping",
        "ue4ss/libUE4SS.so",
        "ue4ss/UE4SS-settings.ini",
        "ue4ss/MemberVariableLayout.ini",
        "ue4ss/Mods/shared/UEHelpers/UEHelpers.lua",
        "runtime-home/.steam/sdk64/steamclient.so",
        "run-native",
    ]
    hashes = {}
    for name in names:
        with (root / name).open("rb") as stream:
            hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    policy = json.loads(Path("/opt/recipe/source-policy.json").read_text())
    for name, expected in policy["sha256"].items():
        with (root / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise RuntimeError("game source checksum mismatch during image sealing")
    (root / "rhenium-runtime.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items())
    )
    (root / "runtime-pins.json").write_text(json.dumps(hashes, indent=2) + "\n")


if __name__ == "__main__":
    main()
