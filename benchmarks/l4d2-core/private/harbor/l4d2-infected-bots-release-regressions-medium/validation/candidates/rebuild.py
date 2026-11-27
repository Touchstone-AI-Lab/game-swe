#!/usr/bin/env python3
"""Rebuild and hash the six frozen validation candidates.

Patch application is defined on a copy of the complete task environment after
canonical UTF-8 CRLF-to-LF normalization of the patched SourcePawn file.  The
reported environment hash includes ``environment/Dockerfile``; the artifact
hash is the exact tree mounted at ``/app/l4d1_2_plugins`` during controls.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASK = HERE.parents[1]
TARGET = Path("l4d1_2_plugins/l4dinfectedbots/scripting/l4dinfectedbots.sp")
SPECS = (
    ("capacity_only", "predicate-capacity.patch"),
    ("config_only", "predicate-config.patch"),
    ("initial_timer_only", "predicate-initial.patch"),
    ("finale_only", "predicate-finale.patch"),
    ("alternative-a", "alternative-a.patch"),
    ("alternative-b", "alternative-b.patch"),
)


def canonical_payload(path: Path) -> bytes:
    payload = path.read_bytes()
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return payload.replace(b"\r\n", b"\n")


def digest_file(path: Path) -> str:
    return hashlib.sha256(canonical_payload(path)).hexdigest()


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    files = (item for item in root.rglob("*") if item.is_file())
    for path in sorted(
        files,
        key=lambda item: item.relative_to(root).as_posix().encode("utf-8"),
    ):
        relative = path.relative_to(root).as_posix().encode()
        payload = canonical_payload(path)
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def rebuild(output: Path) -> None:
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)
    print(
        "candidate\tpatch_sha256\ttarget_content_sha256\t"
        "environment_tree_sha256\tmounted_artifact_tree_sha256"
    )
    for candidate, patch_name in SPECS:
        candidate_root = output / candidate
        environment = candidate_root / "environment"
        shutil.copytree(TASK / "environment", environment)
        target = environment / TARGET
        target.write_bytes(canonical_payload(target))
        patch = HERE / patch_name
        completed = subprocess.run(
            (
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                "apply",
                "--unsafe-paths",
                "--whitespace=nowarn",
                str(patch),
            ),
            cwd=candidate_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            raise SystemExit(
                f"failed to rebuild {candidate}:\n{completed.stdout}{completed.stderr}"
            )
        print(
            f"{candidate}\t{digest_file(patch)}\t{digest_file(target)}\t"
            f"{digest_tree(environment)}\t"
            f"{digest_tree(environment / 'l4d1_2_plugins')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rebuild(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
