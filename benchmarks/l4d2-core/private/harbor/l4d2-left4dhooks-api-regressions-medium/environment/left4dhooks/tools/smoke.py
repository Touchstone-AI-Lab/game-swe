#!/usr/bin/env python3
"""Answer-free source and compiler smoke check for Left4DHooks."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTING = ROOT / "sourcemod/scripting"
COMPILER = Path(os.environ.get("SP_COMPILER", "/opt/sourcemod/addons/sourcemod/scripting/spcomp64"))
STOCK_INCLUDE = Path(os.environ.get("SM_INCLUDE", "/opt/sourcemod/addons/sourcemod/scripting/include"))
FORBIDDEN_SUFFIXES = {".smx", ".dll", ".exe", ".so", ".zip", ".7z", ".vpk", ".rej", ".orig"}


def main() -> int:
    errors: list[str] = []
    required = (
        ROOT / "LICENSE",
        SCRIPTING / "left4dhooks.sp",
        SCRIPTING / "l4dd/l4dd_natives.sp",
        SCRIPTING / "l4dd/l4dd_forwards.sp",
        SCRIPTING / "include/left4dhooks.inc",
        ROOT / "sourcemod/gamedata/left4dhooks.l4d2.txt",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"missing required source: {path.relative_to(ROOT)}")
    if not COMPILER.is_file():
        errors.append(f"missing pinned compiler: {COMPILER}")
    if (ROOT / "LICENSE").is_file() and "GNU GENERAL PUBLIC LICENSE" not in (ROOT / "LICENSE").read_text(
        encoding="utf-8", errors="replace"
    ):
        errors.append("upstream GPL license was altered")

    files = [path for path in ROOT.rglob("*") if path.is_file()]
    source_lines = 0
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            errors.append(f"{relative}: symbolic links are not allowed")
        if path.name == ".git":
            errors.append(f"{relative}: Git metadata is not allowed")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{relative}: compiled/archive artifact is not allowed")
        if path.suffix.lower() in {".sp", ".inc"}:
            payload = path.read_bytes()
            if b"\x00" in payload:
                errors.append(f"{relative}: NUL byte is not allowed in SourcePawn source")
            if b"\r" in payload.replace(b"\r\n", b""):
                errors.append(f"{relative}: lone CR line ending is not allowed")
            if b"\r\n" in payload and b"\n" in payload.replace(b"\r\n", b""):
                errors.append(f"{relative}: mixed LF/CRLF line endings are not allowed")
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{relative}: source must be valid UTF-8")
                text = payload.decode("utf-8", errors="replace")
            if "@@GCB_SM@@" in text or "__GCB_NONCE__" in text:
                errors.append(f"{relative}: reserved verifier marker")
            source_lines += len(text.splitlines())
    if source_lines < 30_000:
        errors.append(f"source snapshot is incomplete: {source_lines} SourcePawn lines")

    if not errors:
        with tempfile.TemporaryDirectory(prefix="gcb-spcomp-") as output:
            command = [
                str(COMPILER),
                "-i",
                str(STOCK_INCLUDE),
                "-i",
                str(SCRIPTING / "include"),
                "-o",
                str(Path(output) / "left4dhooks.smx"),
                str(SCRIPTING / "left4dhooks.sp"),
            ]
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            if completed.returncode:
                errors.append(f"left4dhooks.sp: compiler failed\n{completed.stdout}{completed.stderr}")

    if errors:
        print("SMOKE FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"SMOKE PASS: {source_lines} SourcePawn lines; left4dhooks.sp compiles with SourceMod 1.12.0.7246")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
