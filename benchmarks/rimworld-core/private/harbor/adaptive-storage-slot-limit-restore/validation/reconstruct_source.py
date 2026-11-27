"""Reproduce the fixed 1.6 source selection; never write into a benchmark pack."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Authoring entry points must not create bytecode caches in pack/source directories.
sys.dont_write_bytecode = True

from rhenium_rimworld.safe_files import (  # noqa: E402
    ensure_directory_nofollow,
    secure_read_bytes,
    write_owner_file,
)
from rhenium_rimworld.supervisor import strict_json_object  # noqa: E402


def reconstruct(upstream: Path, destination: Path, variant: str) -> None:
    task = Path(__file__).resolve().parent.parent
    pack = task.parents[2]
    destination = destination.absolute()
    resolved = destination.resolve()
    if resolved.is_relative_to(pack) or pack.is_relative_to(resolved):
        raise ValueError("destination must be outside the benchmark pack")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination already exists")
    if variant not in {"base", "oracle"}:
        raise ValueError("variant must be base or oracle")
    plan = strict_json_object(secure_read_bytes(task, "validation/source-derivation.json"))
    content: dict[str, bytes] = {}
    for item in plan["files"]:
        raw = secure_read_bytes(upstream, item["path"])
        if hashlib.sha256(raw).hexdigest() != item["upstreamSha256"]:
            raise ValueError("upstream input hash mismatch")
        for adaptation in item.get("adaptations", []):
            old, new = adaptation["replaceOnce"].encode(), adaptation["with"].encode()
            if raw.count(old) != 1:
                raise ValueError("mechanical adaptation must occur exactly once")
            raw = raw.replace(old, new, 1)
        if item["origin"] == "historical-behavior-reconstruction":
            old, new = plan["replaceOnce"].encode(), plan["with"].encode()
            if raw.count(old) != 1:
                raise ValueError("historical transition must occur exactly once")
            if variant == "base":
                raw = raw.replace(old, new, 1)
        expected = item["baseSha256" if variant == "base" else "targetSha256"]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("reconstruction output hash mismatch")
        content[item["path"]] = raw
    license_bytes = secure_read_bytes(upstream, "LICENSE")
    if hashlib.sha256(license_bytes).hexdigest() != plan["licenseSha256"]:
        raise ValueError("license hash mismatch")
    content["LICENSE"] = license_bytes
    dependencies = strict_json_object(secure_read_bytes(task, "validation/dependencies.json"))
    for notice in dependencies["additionalNotices"]:
        raw = secure_read_bytes(task / "environment/AdaptiveStorage", notice["path"])
        if hashlib.sha256(raw).hexdigest() != notice["sha256"]:
            raise ValueError("notice hash mismatch")
        content[notice["path"]] = raw
    # Validate every byte before creating any output; no-follow helpers reject links.
    ensure_directory_nofollow(destination)
    for relative, raw in content.items():
        write_owner_file(destination / "AdaptiveStorage" / relative, raw)
    write_owner_file(destination / "reconstruction.json", (
        json.dumps({"variant": variant, "sourceCommit": plan["sourceCommit"],
                    "compileValidated": False, "engineValidated": False}, indent=2) + "\n"
    ).encode())


if __name__ == "__main__":
    source, output, selected = sys.argv[1:]
    reconstruct(Path(source), Path(output), selected)
