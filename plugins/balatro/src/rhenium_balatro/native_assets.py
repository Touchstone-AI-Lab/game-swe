"""Pack-local authored assets and fixed external controller identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .files import asset, content_digest, digest, read_file, read_json, reject_links

ASSETS = "private/native-v1/assets.json"


def file_sha(path: Path) -> str:
    reject_links(path)
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def adapter_identity() -> str:
    root = Path(__file__).resolve().parent
    return content_digest({p.name: file_sha(p) for p in sorted(root.glob("*.py"))})


def verified_assets(pack: Path, expected_sha: str) -> dict[str, Any]:
    if digest(read_file(pack, ASSETS)) != expected_sha:
        raise ValueError("private asset descriptor changed")
    data = read_json(pack, ASSETS)
    root = asset(pack, "private/native-v1")
    actual = set()
    for subtree in ("fixtures", "controls"):
        for path in (root / subtree).rglob("*"):
            reject_links(path)
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
    if actual != set(data["files"]):
        raise ValueError("private authored file closure changed")
    for name, expected in data["files"].items():
        if digest(read_file(root, name)) != expected:
            raise ValueError("private authored asset changed")
    return data


def verify_controller(root: Path, assets: dict[str, Any]) -> None:
    # Checks precede imports and therefore all external controller execution.
    for name, expected in assets["controller_files"].items():
        if file_sha(asset(root, name)) != expected:
            raise ValueError("fixed controller source changed")
    for name, key in (("dependency-bytes-v2.json", "pin_sha256"),
                      (".state/protected-before.json", "protected_baseline_sha256"),
                      ("scale10-final-freeze-v02-v1.json", "source_freeze_sha256")):
        if file_sha(asset(root, name)) != assets[key]:
            raise ValueError("fixed baseline changed")


def json_write_new(path: Path, value: Any) -> None:
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
