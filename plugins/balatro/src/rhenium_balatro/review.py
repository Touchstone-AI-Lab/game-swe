"""Explicit operator source-review records; never infer trust from a filename."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .files import MAX_SUBMISSION_BYTES, content_digest, digest, read_file, read_json, reject_links
from .native_assets import adapter_identity, json_write_new


def candidate_identity(directory: Path) -> tuple[str, str]:
    """Return the submission seal and the existing PoC size/hash tree identity."""
    files: dict[str, dict[str, Any]] = {}
    reject_links(directory)
    for path in sorted(directory.rglob("*")):
        reject_links(path)
        if path.is_file():
            name = path.relative_to(directory).as_posix()
            data = read_file(directory, name)
            files[name] = {"size": len(data), "sha256": digest(data)}
        elif not path.is_dir():
            raise ValueError("unsupported candidate entry")
    if not files or sum(f["size"] for f in files.values()) > MAX_SUBMISSION_BYTES:
        raise ValueError("invalid candidate size")
    return (content_digest({name: f["sha256"] for name, f in files.items()}),
            digest(json.dumps(files, sort_keys=True).encode()))


def review_identity(assets: dict[str, Any], assets_sha: str, key: str,
                    submission_sha: str, candidate_sha: str) -> dict[str, Any]:
    if key not in assets["tasks"]:
        raise ValueError("unknown reviewed task")
    return {"schema_version": 2, "scope": "operator-source-reviewed-honest",
            "task": key, "task_sha256": assets["tasks"][key]["task_sha256"],
            "environment": assets["environment"], "harness": assets["harness"],
            "adapter_sha256": adapter_identity(), "assets_sha256": assets_sha,
            "submission_sha256": submission_sha, "candidate_sha256": candidate_sha}


def record_review(state: Path, assets: dict[str, Any], assets_sha: str, key: str,
                  submission_sha: str, candidate_sha: str, reviewed_sha: str) -> dict[str, Any]:
    if reviewed_sha != submission_sha:
        raise ValueError("submission changed since operator source review")
    identity = review_identity(assets, assets_sha, key, submission_sha, candidate_sha)
    record = {**identity, "recorded_utc": datetime.now(UTC).isoformat()}
    target = state / "reviews" / f"{key}-{submission_sha}.json"
    if target.exists():
        previous = read_json(target.parent, target.name)
        if ({k: previous.get(k) for k in identity} != identity
                or set(previous) != {*identity, "recorded_utc"}):
            raise ValueError("existing review is stale; use fresh state")
        return previous
    json_write_new(target, record)
    return record


def candidate_reviewed(state: Path, assets: dict[str, Any], assets_sha: str, key: str,
                       submission_sha: str, candidate_sha: str) -> bool:
    identity = review_identity(assets, assets_sha, key, submission_sha, candidate_sha)
    path = state / "reviews" / f"{key}-{submission_sha}.json"
    if path.exists():
        record = read_json(path.parent, path.name)
        return ({k: record.get(k) for k in identity} == identity
                and set(record) == {*identity, "recorded_utc"})
    # The original scoped, source-reviewed maintenance set remains authorized.
    return any(c["seal_sha256"] == submission_sha and c["candidate_sha256"] == candidate_sha
               for c in assets["controls"][key].values())
