#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parents[1]
BASE = TASK / "environment" / "left4dhooks"


def canonical(path: Path) -> bytes:
    payload = path.read_bytes()
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return payload.replace(b"\r\n", b"\n")


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix().encode("utf-8")):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = canonical(path)
        digest.update(len(relative).to_bytes(4, "big")); digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big")); digest.update(payload)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    manifest = {row["candidate"]: row for row in json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))}
    if args.candidate not in manifest:
        parser.error(f"unknown candidate: {args.candidate}")
    if args.destination.exists():
        parser.error("destination already exists")
    shutil.copytree(BASE, args.destination)
    patch = HERE / f"{args.candidate}.patch"
    completed = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "apply", "--no-index", str(patch)],
        cwd=args.destination, text=True, capture_output=True,
    )
    if completed.returncode:
        raise SystemExit(completed.stdout + completed.stderr)
    actual = digest_tree(args.destination)
    expected = manifest[args.candidate]["tree_sha256"]
    if actual != expected:
        raise SystemExit(f"tree hash mismatch: expected {expected}, got {actual}")
    print(f"{args.candidate}\t{actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
