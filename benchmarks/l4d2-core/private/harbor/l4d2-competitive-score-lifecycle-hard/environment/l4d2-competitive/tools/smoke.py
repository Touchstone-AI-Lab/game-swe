#!/usr/bin/env python3
"""Answer-free source and compiler smoke check for the agent workspace."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTING = ROOT / "addons/sourcemod/scripting"
COMPILER = Path(os.environ.get("SP_COMPILER", "/opt/sourcemod/addons/sourcemod/scripting/spcomp64"))
STOCK_INCLUDE = Path(os.environ.get("SM_INCLUDE", "/opt/sourcemod/addons/sourcemod/scripting/include"))
TARGETS = (
    "l4d2_hybrid_scoremod_zone.sp",
    "l4d2lib.sp",
)
FORBIDDEN_SUFFIXES = {".smx", ".dll", ".exe", ".so", ".zip", ".7z", ".vpk"}


def main() -> int:
    errors: list[str] = []
    if not COMPILER.is_file():
        errors.append(f"missing pinned compiler: {COMPILER}")
    if not (ROOT / "LICENSE").is_file() or "GNU GENERAL PUBLIC LICENSE" not in (ROOT / "LICENSE").read_text(
        encoding="utf-8", errors="replace"
    ):
        errors.append("upstream GPL license is missing")

    files = [path for path in ROOT.rglob("*") if path.is_file()]
    sourcepawn = [path for path in files if path.suffix == ".sp"]
    includes = [path for path in files if path.suffix == ".inc"]
    if len(sourcepawn) < 300 or len(includes) < 50:
        errors.append(f"source snapshot is incomplete: sp={len(sourcepawn)} inc={len(includes)}")
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            errors.append(f"{relative}: symbolic links are not allowed")
        if path.name == ".git":
            errors.append(f"{relative}: Git metadata is not allowed")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{relative}: compiled/archive artifact is not allowed")

    if not errors:
        with tempfile.TemporaryDirectory(prefix="gcb-spcomp-") as output:
            for target in TARGETS:
                source = SCRIPTING / target
                if not source.is_file():
                    errors.append(f"missing target source: {target}")
                    continue
                command = [
                    str(COMPILER),
                    "-i",
                    str(STOCK_INCLUDE),
                    "-i",
                    str(SCRIPTING / "include"),
                    "-o",
                    str(Path(output) / f"{source.stem}.smx"),
                    str(source),
                ]
                completed = subprocess.run(command, text=True, capture_output=True, check=False)
                if completed.returncode:
                    errors.append(f"{target}: compiler failed\n{completed.stdout}{completed.stderr}")

    if errors:
        print("SMOKE FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"SMOKE PASS: {len(sourcepawn)} SourcePawn files; score plugin and L4D2Lib compile with SourceMod 1.12.0.7246")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
