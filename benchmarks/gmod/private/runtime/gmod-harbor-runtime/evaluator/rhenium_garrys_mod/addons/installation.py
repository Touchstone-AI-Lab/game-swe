from __future__ import annotations

import hashlib
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

PINNED_BUILD = "23150012"
MARKER = "@@RHENIUM_GMOD@@"
MARKER_END = "@@RHENIUM_END@@"

_MUTABLE_GAME_DIRS = {
    "addons",
    "cache",
    "cfg",
    "data",
    "download",
    "downloads",
    "logs",
    "screenshots",
    "temp",
    "workshop",
}


class GmodInstallationError(RuntimeError):
    pass


def read_build_id(server_root: Path) -> str:
    manifest = server_root / "steamapps" / "appmanifest_4020.acf"
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError as error:
        raise GmodInstallationError(f"App 4020 manifest is unavailable: {manifest}") from error
    match = re.search(r'^\s*"buildid"\s+"([0-9]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise GmodInstallationError("App 4020 manifest has no buildid")
    return match.group(1)


def metadata_tree_digest(root: Path) -> str:
    """Detect writes to a fixed Server image without hashing its multi-GiB contents."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix().lower()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise GmodInstallationError(f"server install contains a symbolic link: {relative}")
        digest.update(relative.encode("utf-8"))
        if path.is_file():
            stat = path.stat()
            digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def content_tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def clone_server_tree(source: Path, destination: Path) -> None:
    """Create a hardlinked immutable view and private copies of mutable game directories."""
    destination.mkdir(parents=True)
    for current, directories, files in os.walk(source):
        current_path = Path(current)
        relative = current_path.relative_to(source)
        if relative == Path("garrysmod"):
            directories[:] = [name for name in directories if name.lower() not in _MUTABLE_GAME_DIRS]
        target_dir = destination / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            os.link(current_path / name, target_dir / name)

    source_cfg = source / "garrysmod" / "cfg"
    destination_cfg = destination / "garrysmod" / "cfg"
    if source_cfg.is_dir():
        shutil.copytree(source_cfg, destination_cfg)
    else:
        destination_cfg.mkdir()
    for name in _MUTABLE_GAME_DIRS - {"cfg"}:
        (destination / "garrysmod" / name).mkdir(parents=True, exist_ok=True)


def linux_server_binary(root: Path) -> Path:
    """Use the pinned stable Linux ELF directly, never the updating shell wrapper."""
    binary = root / "srcds_linux"
    if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
        raise GmodInstallationError("native Linux srcds_linux executable is unavailable")
    with binary.open("rb") as handle:
        header = handle.read(20)
    if header[:6] != b"\x7fELF\x01\x01" or header[18:20] != b"\x03\x00":
        raise GmodInstallationError("native Linux server must be the stable x86 ELF executable")
    return binary


def replace_placeholders(path: Path, replacements: dict[str, str]) -> None:
    source = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        if old not in source:
            raise GmodInstallationError(f"expected placeholder is missing from {path.name}: {old}")
        source = source.replace(old, new)
    if "__RHENIUM_" in source:
        raise GmodInstallationError(f"suite injection left unresolved placeholders in {path.name}")
    path.write_text(source, encoding="utf-8")


def create_directory_junction(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if link.exists():
        if any(link.iterdir()):
            raise GmodInstallationError(f"refusing to replace non-empty data directory: {link}")
        link.rmdir()
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        link.symlink_to(target, target_is_directory=True)
        return
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if completed.returncode != 0 or not link.is_dir() or not os.path.samefile(link, target):
        raise GmodInstallationError(
            f"failed to create data directory junction: {completed.stdout} {completed.stderr}"
        )


def remove_directory_junction(link: Path, target: Path) -> None:
    if not link.exists():
        return
    if not os.path.samefile(link, target):
        raise GmodInstallationError(f"refusing to remove unexpected data link: {link}")
    if os.name == "posix":
        if not link.is_symlink():
            raise GmodInstallationError("refusing to remove a non-symbolic data link")
        link.unlink()
    else:
        link.rmdir()
    if not target.is_dir():
        raise GmodInstallationError("removing data junction unexpectedly removed its target")


def available_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def build_command(binary: Path, run_id: str, port: int) -> list[str]:
    return [
        str(binary),
        "-game",
        "garrysmod",
        "-console",
        "-nocrashdialog",
        "-noconclr",
        "-insecure",
        "-nomaster",
        "-noworkshop",
        "-disablehttp",
        "-disableluarefresh",
        "-allowquit",
        "-tickrate",
        "66",
        "+sv_lan",
        "1",
        "+sv_hibernate_think",
        "1",
        "+host_workshop_autoupdate",
        "0",
        "+maxplayers",
        "8",
        "+gamemode",
        "sandbox",
        "+hostname",
        f"Rhenium GMod {run_id}",
        "+ip",
        "127.0.0.1",
        "+hostport",
        str(port),
        "+map",
        "gm_flatgrass",
    ]
