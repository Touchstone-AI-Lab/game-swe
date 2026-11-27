from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import GmodCatalog, GmodTask


class PublicExamError(ValueError):
    pass


@dataclass(frozen=True)
class PublicExamAsset:
    path: Path
    content: bytes
    text: str


def path_uses_link_or_junction(root: Path, relative: PurePosixPath) -> bool:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or (
            hasattr(os.path, "isjunction") and os.path.isjunction(current)
        ):
            return True
    return False


def load_public_exam(
    task: GmodTask,
    *,
    catalog_id: str,
    pack_root: Path,
    private_markers: tuple[str, ...] = (),
) -> PublicExamAsset:
    try:
        root = pack_root.resolve(strict=True)
    except OSError as error:
        raise PublicExamError(f"GMod pack root is unavailable: {pack_root}") from error
    logical = PurePosixPath(task.public_exam.path)
    expected = PurePosixPath("exams") / f"{task.id}.md"
    if logical != expected:
        raise PublicExamError(f"public exam for {task.id} is not pack-owned")
    if path_uses_link_or_junction(root, logical):
        raise PublicExamError(f"public exam must not use a symlink or junction: {logical}")
    try:
        candidate = (root / Path(*logical.parts)).resolve(strict=True)
        exams_root = (root / "exams").resolve(strict=True)
    except OSError as error:
        raise PublicExamError(f"canonical public exam is missing: {logical}") from error
    if not candidate.is_relative_to(exams_root) or not candidate.is_file():
        raise PublicExamError(f"canonical public exam is missing or escaped the pack: {logical}")
    content = candidate.read_bytes()
    if hashlib.sha256(content).hexdigest() != task.public_exam.sha256:
        raise PublicExamError(f"canonical public exam digest drifted for {task.id}")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PublicExamError(f"canonical public exam is not UTF-8 for {task.id}") from error

    headings = [
        heading.rstrip("\r")
        for heading in re.findall(r"^# ([^#].*)$", text, flags=re.MULTILINE)
    ]
    if headings != [task.title.en]:
        raise PublicExamError(f"canonical public exam title does not match catalog for {task.id}")
    missing_files = [relative for relative in task.required_files if relative not in text]
    if missing_files:
        raise PublicExamError(f"canonical public exam omits required files for {task.id}: {missing_files}")
    for attribute in ("core_module", "server_module"):
        module = getattr(task, attribute)
        if module not in text:
            raise PublicExamError(f"canonical public exam omits {attribute} for {task.id}: {module}")
    for label, entries in (
        ("interface", task.public_exam.interfaces),
        ("contract evidence", task.public_exam.contract_evidence),
        ("acceptance evidence", task.public_exam.acceptance_evidence),
    ):
        missing = [entry for entry in entries if entry not in text]
        if missing:
            raise PublicExamError(f"canonical public exam omits {label} for {task.id}: {missing}")

    forbidden = tuple(
        dict.fromkeys(
            (
                task.id,
                catalog_id,
                task.public_exam.path,
                "private/",
                "mutations.json",
                "table-registry",
                "array-registry",
                "suiteId",
                "runtimeNamespace",
                "nonce",
                *private_markers,
            )
        )
    )
    leaks = [marker for marker in forbidden if marker and marker in text]
    if leaks:
        raise PublicExamError(f"canonical public exam leaks private identity for {task.id}: {leaks}")
    return PublicExamAsset(path=candidate, content=content, text=text)


def validate_catalog_exams(
    catalog: GmodCatalog,
    *,
    pack_root: Path,
    private_markers: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, PublicExamAsset]:
    markers = private_markers or {}
    result = {
        task.id: load_public_exam(
            task,
            catalog_id=catalog.id,
            pack_root=pack_root,
            private_markers=markers.get(task.id, ()),
        )
        for task in catalog.tasks
    }
    if len({asset.path for asset in result.values()}) != len(result):
        raise PublicExamError("GMod tasks resolved to the same canonical public exam")
    return result
