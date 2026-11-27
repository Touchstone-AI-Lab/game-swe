"""E2: intervene on observed target-success / contract-failure attempts.

Selection follows the rule frozen in the study configuration before any E1
result exists. An intervention is a patch applied to a copy of the frozen
submission; the original and the repaired tree are replayed through the same
evaluator identity, and both records are kept whether or not the repair works.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from typing import Any

from . import controls
from .clausemap import ClauseMap
from .e1config import StudyConfig
from .exclusions import refuse_excluded
from .inventory import task_for
from .observations import case_table
from .paths import StudyPaths


def select(records: list[dict[str, Any]], config: StudyConfig) -> dict[str, Any]:
    """All target-satisfied, contract-violated attempts; stratified by source family above the cap."""
    eligible = sorted(
        (
            item
            for item in records
            if item["targetOutcome"] == "satisfied" and item["preservedOutcome"] == "violated"
        ),
        key=lambda item: item["attempt_id"],
    )
    chosen = list(eligible)
    if len(chosen) > config.e2_max_cases:
        families: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in eligible:
            families[item["sourceFamily"]].append(item)
        generator = random.Random(config.schedule_seed)
        for items in families.values():
            generator.shuffle(items)
        chosen = []
        while len(chosen) < config.e2_max_cases:
            for family in sorted(families):
                if families[family] and len(chosen) < config.e2_max_cases:
                    chosen.append(families[family].pop())
    controls_found = {}
    for item in chosen:
        match = next(
            (
                other
                for other in sorted(records, key=lambda entry: entry["attempt_id"])
                if other["task"] == item["task"] and other["jointOutcome"] == "both"
            ),
            None,
        )
        controls_found[item["attempt_id"]] = match["attempt_id"] if match else None
    return {
        "rule": config.e2_selection_rule,
        "eligible": [item["attempt_id"] for item in eligible],
        "selected": [item["attempt_id"] for item in chosen],
        "successfulControls": controls_found,
    }


def replay(
    paths: StudyPaths,
    config: StudyConfig,
    attempt_id: str,
    patch: Path | None,
    *,
    excluded: Collection[str],
) -> dict[str, Any]:
    """Evaluate the frozen submission, optionally with one intervention patch applied.

    An attempt of an excluded task is refused.
    """
    root = paths.data_root / "e1" / config.study_id / "attempts" / attempt_id
    record = json.loads((root / "attempt.json").read_text(encoding="utf-8"))
    refuse_excluded(record["task"], attempt_id, excluded)
    task = task_for(record["task"])
    label = patch.stem if patch else "original"
    work = paths.data_root / "e2" / config.study_id / attempt_id / label
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(root / "submission", work / "tree", symlinks=True)
    applied = None
    if patch is not None:
        applied = subprocess.run(
            ["patch", "-p1", "--forward", "--no-backup-if-mismatch", "-i", str(patch.resolve())],
            cwd=work / "tree",
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if applied.returncode != 0:
            raise RuntimeError(f"intervention patch did not apply: {applied.stdout[-1500:]}")
    clause_map = ClauseMap.load(paths.study_controls(task.pack_dir, task.task) / "clause-map.json")
    try:
        result, error = controls.evaluate(task, work / "tree", paths)["result"], None
    except Exception as failure:  # noqa: BLE001 - a replay that cannot run is a recorded outcome
        result, error = {}, f"{type(failure).__name__}: {failure}"
    outcome = {
        "attempt": attempt_id,
        "task": record["task"],
        "replay": label,
        "patch": str(patch) if patch else None,
        "treeDigest": controls.tree_digest(work / "tree"),
        "runtimeIdentity": controls.runtime_identity(task, paths),
        "score": result.get("score"),
        "complete": result.get("complete"),
        "passed": result.get("passed"),
        "cases": case_table(result, clause_map.case_ids()),
        "evaluatorError": error,
    }
    (work / "replay.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return outcome
