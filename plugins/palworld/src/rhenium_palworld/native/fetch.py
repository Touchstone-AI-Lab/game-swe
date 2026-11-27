"""Fetch checksum-pinned compiler inputs during explicit image preparation."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path


def extract(url: str, digest: str, target: Path, *, strip_root: bool = True) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "source.tar.gz"
        with urllib.request.urlopen(url, timeout=180) as response, archive.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise RuntimeError("compiler input checksum mismatch")
        unpacked = Path(temporary) / "tree"
        with tarfile.open(archive) as handle:
            handle.extractall(unpacked, filter="data")
        if strip_root:
            roots = list(unpacked.iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise RuntimeError("unexpected compiler archive layout")
            unpacked = roots[0]
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(unpacked, target, dirs_exist_ok=True)


def main() -> None:
    extract(
        "https://codeload.github.com/BlackBookOfficial/ue4ss-linux-palworld/tar.gz/"
        "2397c7b1ce2841fd6526b8d8110cd008c90a6316",
        "1e4fe405257d6c6ec2e63546feae35c47407d4528d0f4f83bd7d5b83975e5591",
        Path("/source"),
    )
    for dependency in json.loads(Path("/recipe/dependencies.json").read_text()):
        extract(dependency["url"], dependency["sha256"], Path("/deps") / dependency["name"])
    for origin, target in [
        ("zycore", "/deps/zydis/dependencies/zycore"),
        ("distorm", "/deps/funchook/distorm"),
    ]:
        shutil.copytree(Path("/deps") / origin, target, dirs_exist_ok=True)
    # Fixed FetchContent source directories skip PATCH_COMMAND. Apply the
    # upstream fmt macro guard explicitly, exactly as its normal fetch does.
    subprocess.run(
        [
            "cmake",
            "-DPATCH_SCRIPT_DIR=/source/deps/third/fmt",
            "-P",
            "/source/deps/third/fmt/patch_fmt.cmake",
        ],
        cwd="/deps/fmt",
        check=True,
    )
    extract(
        "https://github.com/BlackBookOfficial/ue4ss-linux-palworld/releases/download/"
        "v1.0.2-palworld-linux/ue4ss-linux-palworld-v1.0.2-palworld-linux.tar.gz",
        "9c472b62a633877acddf2dcaf61826583f0d50b2c4e11723c71da5a4ea81abd9",
        Path("/loader"),
        strip_root=False,
    )


if __name__ == "__main__":
    main()
