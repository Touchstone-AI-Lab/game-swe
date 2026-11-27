#!/usr/bin/env python3
"""Rebuild a frozen validation candidate from the broken source snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASK = HERE.parents[1]
BASE = TASK / "environment/mutant-tanks"


def canonical_payload(path: Path) -> bytes:
    payload = path.read_bytes()
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return payload.replace(b"\r\n", b"\n")


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = canonical_payload(path)
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    with (HERE / "manifest.tsv").open(encoding="utf-8", newline="") as handle:
        rows = {row["candidate"]: row for row in csv.DictReader(handle, delimiter="\t")}
    if args.candidate not in rows:
        parser.error(f"unknown candidate: {args.candidate}")
    if args.destination.exists():
        parser.error(f"destination already exists: {args.destination}")

    row = rows[args.candidate]
    patch = HERE / f"{args.candidate}.patch"
    patch_hash = hashlib.sha256(patch.read_bytes()).hexdigest()
    if patch_hash != row["patch_sha256"]:
        raise SystemExit(f"patch hash mismatch: {patch_hash}")

    shutil.copytree(BASE, args.destination)
    apply_command = ["git", "-c", "core.autocrlf=false", "apply", "--no-index"]
    subprocess.run([*apply_command, "--check", str(patch)], cwd=args.destination, check=True)
    subprocess.run([*apply_command, str(patch)], cwd=args.destination, check=True)
    tree_hash = digest_tree(args.destination)
    if tree_hash != row["applied_tree_sha256"]:
        raise SystemExit(f"applied tree hash mismatch: {tree_hash}")
    print(f"{args.candidate}: {tree_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
