"""Seal only the declared starter files, without importing or executing a submission."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from .catalog import BalatroTask
from .files import (
    MAX_SUBMISSION_BYTES,
    asset,
    content_digest,
    digest,
    read_file,
    reject_links,
    write_new,
)


@dataclass(frozen=True)
class SealedSubmission:
    directory: Path
    sha256: str
    files: dict[str, str]


def snapshot(submission: Path, task: BalatroTask) -> dict[str, bytes]:
    root = asset(submission, "starter")
    if not root.is_dir():
        raise ValueError("missing starter directory")
    expected = {n.removeprefix("starter/") for n in task.editable_files + task.immutable_files}
    actual: set[str] = set()
    for path in root.rglob("*"):
        reject_links(path)
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise ValueError("unsupported submission entry")
    if expected != actual or len({n.casefold() for n in actual}) != len(actual):
        raise ValueError("submission file allowlist mismatch")
    data = {n: read_file(root, n) for n in sorted(expected)}
    if sum(len(v) for v in data.values()) > MAX_SUBMISSION_BYTES:
        raise ValueError("submission exceeds size limit")
    for name in task.immutable_files:
        if digest(data[name.removeprefix("starter/")]) != task.snapshot_files[name]:
            raise ValueError("immutable file changed")
    return data


def seal_submission(submission: Path, task: BalatroTask, state: Path) -> SealedSubmission:
    data = snapshot(submission, task)
    reject_links(state)
    if state.resolve().is_relative_to(submission.resolve()):
        raise ValueError("sealing state cannot be inside the attempt")
    state.mkdir(parents=True, exist_ok=True)
    destination = state / uuid.uuid4().hex
    destination.mkdir()
    for name, content in data.items():
        write_new(destination, name, content)
    hashes = {n: digest(v) for n, v in data.items()}
    if ({n: digest(read_file(destination, n)) for n in hashes} != hashes
            or snapshot(submission, task) != data):
        raise ValueError("submission changed during sealing")
    return SealedSubmission(destination, content_digest(hashes), hashes)


def verify_seal(sealed: SealedSubmission) -> None:
    actual: dict[str, str] = {}
    for path in sealed.directory.rglob("*"):
        reject_links(path)
        if path.is_file():
            name = path.relative_to(sealed.directory).as_posix()
            actual[name] = digest(read_file(sealed.directory, name))
    if actual != sealed.files or content_digest(actual) != sealed.sha256:
        raise ValueError("sealed submission changed")
