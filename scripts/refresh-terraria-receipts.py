#!/usr/bin/env python3
"""Regenerate canonical Terraria oracle diffs and SHA-256 receipts.

The source projections are text snapshots. Normalize checkout CRLF to LF so a
Windows author and the Linux verifier record the same artifact identity.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARBOR = ROOT / "benchmarks" / "terraria-core" / "private" / "harbor"


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def oracle_diff(task: Path) -> str:
    environments = [item for item in (task / "environment").iterdir() if item.is_dir()]
    if len(environments) != 1:
        raise ValueError(f"{task.name}: expected one source projection directory")
    source = environments[0]
    after = task / "solution" / "after"
    sections: list[str] = []
    for target in sorted(after.rglob("*")):
        if not target.is_file():
            continue
        original = source / target.relative_to(after)
        if not original.is_file():
            raise ValueError(f"{task.name}: oracle adds unpaired file {target.relative_to(after)}")
        before_bytes, after_bytes = canonical(original), canonical(target)
        if before_bytes == after_bytes:
            continue
        a = original.relative_to(ROOT).as_posix()
        b = target.relative_to(ROOT).as_posix()
        with tempfile.TemporaryDirectory(prefix="terraria-oracle-diff-") as raw:
            temporary = Path(raw)
            left, right = temporary / "before", temporary / "after"
            left.write_bytes(before_bytes)
            right.write_bytes(after_bytes)
            result = subprocess.run(
                ["git", "diff", "--no-index", "--no-ext-diff", "--", str(left), str(right)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        if result.returncode != 1:
            raise ValueError(f"{task.name}: could not generate {target.relative_to(after)} diff")
        lines = result.stdout.splitlines(keepends=True)
        if len(lines) < 4 or not lines[0].startswith("diff --git "):
            raise ValueError(f"{task.name}: unexpected git diff format")
        lines[0] = f"diff --git a/{a} b/{b}\n"
        for index, line in enumerate(lines):
            if line.startswith("--- "):
                lines[index] = f"--- a/{a}\n"
            elif line.startswith("+++ "):
                lines[index] = f"+++ b/{b}\n"
        sections.append("".join(lines))
    return "".join(sections)


def hashes(task: Path) -> str:
    receipt = task / "validation" / "content-sha256.txt"
    lines: list[str] = []
    listed: set[str] = set()
    for line in receipt.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            lines.append(line)
            continue
        _old, relative = line.split("  ", 1)
        listed.add(relative)
        path = task / relative
        if not path.is_file():
            raise ValueError(f"{task.name}: missing receipt target {relative}")
        lines.append(f"{hashlib.sha256(canonical(path)).hexdigest()}  {relative}")
    engine_files = [task / "engine-rubric.json"]
    engine_files.extend(sorted((task / "engine").rglob("*")))
    for path in engine_files:
        if not path.is_file():
            continue
        relative = path.relative_to(task).as_posix()
        if relative in listed:
            continue
        lines.append(f"{hashlib.sha256(canonical(path)).hexdigest()}  {relative}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", nargs="+", help="Task directory names under Terraria harbor")
    arguments = parser.parse_args()
    for name in arguments.tasks:
        task = HARBOR / name
        if not task.is_dir() or task.parent != HARBOR:
            raise ValueError(f"unknown Terraria task: {name}")
        patch = task / "validation" / "oracle.patch"
        patch.write_text(oracle_diff(task), encoding="utf-8", newline="\n")
        receipt = task / "validation" / "content-sha256.txt"
        receipt.write_text(hashes(task), encoding="utf-8", newline="\n")
        print(f"refreshed {name}")


if __name__ == "__main__":
    main()
