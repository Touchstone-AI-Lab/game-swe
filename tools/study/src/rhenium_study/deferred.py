"""Deferred evaluation: attempts generated here, evaluated on a host that has the engine.

Some engines only run on another host (Palworld's dedicated server under UE4SS needs
Windows). Their attempts are generated here under the frozen study conditions and
recorded as pending; ``export`` packs every pending submission with the exact
evaluation command, and ``import_results`` scores the returned evaluator outputs with
the same classification, retry rule and verdict as a local evaluation. Only the host
that ran the evaluator differs, and it is recorded on each execution.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Collection
from pathlib import Path
from typing import Any

from . import aggregate, classify, controls
from .attempts import PENDING, _now, _verdict, _write
from .clausemap import ClauseMap
from .e1config import StudyConfig
from .exclusions import refuse_excluded
from .inventory import task_for
from .observations import case_table, observed_cases
from .paths import StudyPaths

MANIFEST = "manifest.json"
KIT_VERSION = 1
# Evaluator outputs the kit writes per attempt, in the order they were produced.
RESULT_NAMES = ("result-1.json", "result-2.json")


def _study_root(paths: StudyPaths, config: StudyConfig) -> Path:
    return paths.e1_study(config.study_id)


def pending(paths: StudyPaths, config: StudyConfig, *, excluded: Collection[str]) -> list[dict[str, Any]]:
    records = aggregate.attempt_records(_study_root(paths, config), excluded=excluded)
    return [record for record in records if record.get("outcome") == PENDING]


def export(
    paths: StudyPaths, config: StudyConfig, config_digest: str, out: Path, *, excluded: Collection[str]
) -> dict[str, Any]:
    """Write an evaluation kit for every pending attempt into ``out`` (must not exist).

    Attempts of excluded tasks are left out.
    """
    if out.exists():
        raise ValueError(f"{out} already exists; export into a new directory")
    entries = []
    for record in pending(paths, config, excluded=excluded):
        source = _study_root(paths, config) / "attempts" / record["attempt_id"] / "submission"
        if controls.tree_digest(source) != record["submissionDigest"]:
            raise ValueError(f"{record['attempt_id']}: frozen submission does not match its digest")
        target = out / "attempts" / record["attempt_id"] / "submission"
        shutil.copytree(source, target, symlinks=True)
        entries.append(
            {
                "attemptId": record["attempt_id"],
                "task": record["task"],
                "submissionDigest": record["submissionDigest"],
                "submission": f"attempts/{record['attempt_id']}/submission",
            }
        )
    if not entries:
        raise ValueError("no attempt is pending evaluation")
    manifest = {
        "kitVersion": KIT_VERSION,
        "studyId": config.study_id,
        "configDigest": config_digest,
        "snapshotCommit": config.snapshot_commit,
        "profile": "full",
        "createdAt": _now(),
        "attempts": entries,
    }
    _write(out / MANIFEST, manifest)
    kit = Path(__file__).parent / "assets" / "deferred-kit"
    for name in ("README.md", "evaluate.ps1", "evaluate.sh"):
        text = (kit / name).read_text(encoding="utf-8")
        text = text.replace("{{STUDY_ID}}", config.study_id).replace("{{SNAPSHOT}}", config.snapshot_commit)
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    (out / "evaluate.sh").chmod(0o755)
    return {"out": str(out), "attempts": len(entries)}


def _read_json(path: Path) -> dict[str, Any]:
    # PowerShell 5 writes UTF-8 with a byte-order mark.
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: not a JSON object")
    return value


def import_results(
    paths: StudyPaths,
    config: StudyConfig,
    config_digest: str,
    kit: Path,
    host: str,
    *,
    excluded: Collection[str],
) -> list[dict[str, Any]]:
    """Score returned evaluator outputs into their pending attempts.

    ``kit`` is the returned kit directory: its manifest names each attempt, and
    ``attempts/<id>/result-N.json`` holds the stdout of ``rhenium run``. As locally,
    the first valid (resolved or failed) execution is final and only an invalid or
    unattributed one may be followed by a second. A kit holding an attempt of an
    excluded task is refused before anything is written.
    """
    if not host.strip():
        raise ValueError("name the evaluation host")
    manifest = _read_json(kit / MANIFEST)
    if manifest.get("studyId") != config.study_id or manifest.get("configDigest") != config_digest:
        raise ValueError("the kit was exported for a different study configuration")
    for entry in manifest["attempts"]:
        refuse_excluded(entry["task"], entry["attemptId"], excluded)
    imported = []
    for entry in manifest["attempts"]:
        root = _study_root(paths, config) / "attempts" / entry["attemptId"]
        final = root / "attempt.json"
        record = json.loads(final.read_text(encoding="utf-8"))
        if record.get("outcome") != PENDING:
            continue  # already scored; an import never overwrites a result
        if record["submissionDigest"] != entry["submissionDigest"] or record["task"] != entry["task"]:
            raise ValueError(f"{entry['attemptId']}: manifest does not match the recorded attempt")
        outputs = [
            kit / "attempts" / entry["attemptId"] / name
            for name in RESULT_NAMES
            if (kit / "attempts" / entry["attemptId"] / name).is_file()
        ]
        if not outputs:
            continue  # not evaluated yet; it stays pending
        task = task_for(record["task"])
        clause_map = ClauseMap.load(paths.study_controls(task.pack_dir, task.task) / "clause-map.json")
        executions: list[dict[str, Any]] = []
        for index, output in enumerate(outputs, start=1):
            try:
                run = _read_json(output)
            except ValueError:
                # `rhenium run` prints nothing on stdout when the evaluator cannot run.
                run = {}
            result: dict[str, Any] = run["result"] if isinstance(run.get("result"), dict) else {}
            if run and run.get("taskKey") != record["task"]:
                raise ValueError(f"{output}: evaluated a different task")
            execution: dict[str, Any] = {
                "index": index,
                "startedAt": run.get("createdAt"),
                "finishedAt": run.get("updatedAt"),
                "runId": run.get("id"),
                "logPath": None,
                "submissionDigest": record["submissionDigest"],
                "runtimeIdentity": f"deferred-host={host}",
                "evaluationHost": host,
                "result": result,
                "evaluatorError": None if result else "the returned output carries no evaluator result",
            }
            table = case_table(result, clause_map.case_ids())
            outcome, reason = classify.classify_execution(execution, table)
            execution.update(
                {
                    "cases": table,
                    "reached": sorted(observed_cases(result)),
                    "outcome": outcome,
                    "reason": reason,
                }
            )
            _write(root / "executions" / f"{index}.json", execution)
            executions.append(execution)
            if outcome in {"resolved", "failed"}:
                break
        record.update(
            {
                "executions": [
                    {k: e[k] for k in ("index", "outcome", "reason", "runId", "runtimeIdentity")}
                    for e in executions
                ],
                **_verdict(clause_map, executions[-1]),
                "evaluationHost": host,
                "importedAt": _now(),
            }
        )
        _write(final, record)
        imported.append({"attemptId": entry["attemptId"], "outcome": record["outcome"]})
    return imported
