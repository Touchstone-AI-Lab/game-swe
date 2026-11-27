"""Read-only source/index checks, with a new immutable local output record."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from rhenium_balatro.native_assets import file_sha, json_write_new


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def audit(repository: Path, controller: Path, original: Path) -> dict[str, Any]:
    freeze = json.loads((controller / "scale10-final-freeze-v02-v1.json").read_bytes())
    if file_sha(controller / "scale10-final-freeze-v02-v1.json") != (
        "0a329c56fa5175a6afa56ca5177c8779cb71ecbffbf0e871943d697c8b763039"
    ):
        raise ValueError("original freeze changed")
    for name, expected in freeze["files"].items():
        if file_sha(controller / name) != expected:
            raise ValueError("frozen authored source changed: " + name)
    staged = git(repository, "diff", "--cached", "--name-only").splitlines()
    if len(staged) != 76 or any(not (n.startswith("benchmarks/balatro/") or n == "docs/games/balatro.md")
                                for n in staged):
        raise ValueError("pre-existing staged scope changed")
    objects = {}
    for name in staged:
        entry = git(repository, "ls-files", "--stage", "--", name).split()
        data = (repository / name).read_bytes()
        oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if entry[1] != oid:
            raise ValueError("pre-existing staged file bytes changed: " + name)
        objects[name] = {"git_oid": oid, "sha256": hashlib.sha256(data).hexdigest()}
    if git(repository, "rev-parse", "HEAD") != "a518348d92ec590d355d0c8e7b8bc351a2360f59":
        raise ValueError("staging HEAD changed")
    if git(original, "rev-parse", "HEAD") != "2df2a057b09cf147de52df6dcbc2d427615330b6":
        raise ValueError("original repository HEAD changed")
    if git(original, "status", "--porcelain"):
        raise ValueError("original read-only repository dirty")
    return {"frozen_poc_source_count": len(freeze["files"]), "staged_files_unchanged": objects,
            "staging_head": git(repository, "rev-parse", "HEAD"),
            "original_head": git(original, "rev-parse", "HEAD"), "original_clean": True,
            "source_freeze_sha256": file_sha(controller / "scale10-final-freeze-v02-v1.json"),
            "no_game_started": True}


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.repository, args.controller, args.original)
    json_write_new(args.output, value)
    print(json.dumps({"passed": True, "frozen_sources": value["frozen_poc_source_count"],
                      "staged_files": len(value["staged_files_unchanged"])}))


if __name__ == "__main__":
    main()
