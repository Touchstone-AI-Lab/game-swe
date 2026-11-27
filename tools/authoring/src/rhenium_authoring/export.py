from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


def export_training_data(run_root: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    candidates = run_root / "candidates"
    if not candidates.is_dir():
        raise ValueError("authoring run has no materialized candidates")
    for candidate in sorted(path for path in candidates.iterdir() if path.is_dir()):
        validation_path = candidate / "validation.json"
        if not validation_path.is_file():
            continue
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if not (
            validation.get("passed") is True
            and validation.get("complete") is True
            and validation.get("engine_backed") is True
        ):
            continue
        archive = destination / f"{candidate.name}-base.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            for path in sorted((candidate / "base").rglob("*")):
                if path.is_file() and not path.is_symlink():
                    output.add(path, arcname=path.relative_to(candidate / "base"), recursive=False)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = json.loads((candidate / "clean-room.json").read_text(encoding="utf-8"))
        records.append(
            {
                "instance_id": candidate.name,
                "game_id": manifest["game_id"],
                "pack_id": "synth",
                "problem_statement": (candidate / "problem.md").read_text(encoding="utf-8"),
                "base_archive": archive.name,
                "base_archive_sha256": digest,
                "gold_patch": (candidate / "gold.patch").read_text(encoding="utf-8"),
                "clean_room_synthetic": True,
                "validation": validation,
            }
        )
    output_path = destination / "swe-like.jsonl"
    output_path.write_text(
        "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return output_path
