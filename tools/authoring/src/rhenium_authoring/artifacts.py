from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath

from rhenium.util import hash_tree

from .models import CleanRoomManifest, SynthesisBundle, ValidationReport


def write_file_tree(root: Path, files: dict[str, str]) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for raw, content in sorted(files.items()):
        relative = PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts or raw != relative.as_posix():
            raise ValueError("generated file path is unsafe")
        destination = (root / raw).resolve()
        if not destination.is_relative_to(root):
            raise ValueError("generated file escaped its artifact root")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def gold_patch(base: dict[str, str], fixed: dict[str, str]) -> str:
    sections: list[str] = []
    for name in sorted(set(base) | set(fixed)):
        before = base.get(name, "").splitlines(keepends=True)
        after = fixed.get(name, "").splitlines(keepends=True)
        if before == after:
            continue
        diff = difflib.unified_diff(
            before,
            after,
            fromfile=f"a/{name}" if name in base else "/dev/null",
            tofile=f"b/{name}" if name in fixed else "/dev/null",
        )
        sections.extend(diff)
    if not sections:
        raise ValueError("synthetic base and fixed project are identical")
    return "".join(sections)


def source_digest(bundle: SynthesisBundle) -> str:
    payload = [
        {
            "repository": str(fix.repository_url),
            "base": fix.base_sha,
            "fixed": fix.fixed_sha,
            "patch_sha256": hashlib.sha256(fix.patch.encode()).hexdigest(),
            "base_context_sha256": hashlib.sha256(
                json.dumps(fix.base_files, sort_keys=True).encode()
            ).hexdigest(),
            "fixed_context_sha256": hashlib.sha256(
                json.dumps(fix.fixed_files, sort_keys=True).encode()
            ).hexdigest(),
        }
        for fix in bundle.provenance
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def materialize_bundle(
    run_root: Path,
    bundle: SynthesisBundle,
    validation: ValidationReport | None = None,
) -> Path:
    candidate_root = run_root / "candidates" / bundle.candidate.id
    if candidate_root.exists():
        raise FileExistsError(candidate_root)
    base = candidate_root / "base"
    fixed = candidate_root / "fixed"
    tests = candidate_root / "tests"
    write_file_tree(base, bundle.base.files)
    write_file_tree(fixed, bundle.fixed.files)
    write_file_tree(tests, bundle.verifier.files)
    for capsule_id, files in sorted(bundle.base.ablations.items()):
        write_file_tree(candidate_root / "ablations" / capsule_id, files)
    patch = gold_patch(bundle.base.files, bundle.fixed.files)
    (candidate_root / "problem.md").write_text(bundle.prompt.markdown.rstrip() + "\n", encoding="utf-8")
    (candidate_root / "gold.patch").write_text(patch, encoding="utf-8")
    private = candidate_root / "private"
    private.mkdir()
    (private / "provenance.json").write_text(
        json.dumps(
            [fix.model_dump(mode="json") for fix in bundle.provenance],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (private / "bundle.json").write_text(
        bundle.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    manifest = CleanRoomManifest(
        candidate_id=bundle.candidate.id,
        game_id=bundle.candidate.game_id,
        source_digest=source_digest(bundle),
        base_digest=f"sha256:{hash_tree(base)}",
        fixed_digest=f"sha256:{hash_tree(fixed)}",
    )
    (candidate_root / "clean-room.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (candidate_root / "review.json").write_text(
        bundle.review.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    if validation is not None:
        (candidate_root / "validation.json").write_text(
            validation.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return candidate_root


def write_validation(candidate_root: Path, validation: ValidationReport) -> None:
    (candidate_root / "validation.json").write_text(
        validation.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
