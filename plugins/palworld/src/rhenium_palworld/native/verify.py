"""Read-only file/architecture verification inside the prepared local image."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath


def verify() -> None:
    root = Path("/server")
    pins = json.loads((root / "runtime-pins.json").read_text())
    if not isinstance(pins, dict) or len(pins) != 7:
        raise RuntimeError("invalid sealed runtime manifest")
    for name, digest in pins.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or name != path.as_posix():
            raise RuntimeError("unsafe runtime manifest path")
        with (root / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise RuntimeError("sealed runtime checksum mismatch")
    for name in ("Pal/Binaries/Linux/PalServer-Linux-Shipping", "ue4ss/libUE4SS.so"):
        with (root / name).open("rb") as stream:
            header = stream.read(20)
        if header[:5] != b"\x7fELF\x02" or header[18:20] != b"\x3e\x00":
            raise RuntimeError("native Linux x86_64 ELF required")
    print(json.dumps({"available": True, "files": len(pins), "platform": "linux-x64"}))


if __name__ == "__main__":
    verify()
