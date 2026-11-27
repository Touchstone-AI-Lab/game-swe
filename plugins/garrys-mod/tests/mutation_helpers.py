from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def load_matrix(pack: Path, task_id: str) -> list[dict[str, Any]]:
    path = pack / "private" / "tasks" / task_id / "mutations.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutations = value.get("mutations") if isinstance(value, dict) else None
    if not isinstance(mutations, list) or not mutations:
        raise ValueError(f"mutation matrix is empty for {task_id}")
    return mutations


def materialize_mutation(
    pack: Path,
    task_id: str,
    mutation: dict[str, Any],
    destination: Path,
) -> None:
    task_root = pack / "private" / "tasks" / task_id
    manifest = json.loads((task_root / "mutations.json").read_text(encoding="utf-8"))
    source = (task_root / str(manifest["base"])).resolve(strict=True)
    if not source.is_relative_to(task_root.resolve(strict=True)):
        raise ValueError("mutation base escaped task-private directory")
    shutil.copytree(source, destination)
    target = (destination / str(mutation["file"])).resolve(strict=True)
    if not target.is_relative_to(destination.resolve()):
        raise ValueError("mutation target escaped destination")
    text = target.read_text(encoding="utf-8")
    replacements = mutation.get("replacements") or [
        {"old": mutation.get("old"), "new": mutation.get("new")}
    ]
    for replacement in replacements:
        old = replacement.get("old")
        new = replacement.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or text.count(old) != 1:
            raise ValueError(f"mutation {mutation.get('id')} does not match exactly once")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
