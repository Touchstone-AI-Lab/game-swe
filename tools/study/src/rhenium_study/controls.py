from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from .clausemap import ClauseMap
from .hubs import engine_slot, open_hub, starter_lock
from .inventory import StudyTask
from .observations import case_table
from .paths import StudyPaths

ControlKind = Literal["starter", "reference", "target-negative", "compat-negative", "alternative"]
_KINDS: tuple[str, ...] = ("starter", "reference", "target-negative", "compat-negative", "alternative")
_APP_TOKEN = re.compile(r"(?<![\w./-])/app(?=[/\s\"']|$)")
_SOLUTION_TOKEN = re.compile(r"(?<![\w./-])/solution(?=[/\s\"']|$)")
# Mindustry's construct oracles write into /workspace, the Harbor workspace root.
_WORKSPACE_TOKEN = re.compile(r"(?<![\w./-])/workspace(?=[/\s\"']|$)")


@dataclass(frozen=True)
class ControlSpec:
    """One control tree: a base plus an optional overlay.

    ``overlay`` is ``-``, ``patch:<file>`` (``patch -p1`` from the submission
    root unless ``root`` names another directory below ``/app``), ``tree:<dir>``
    (copied over the submission root) or ``pack:<dir>`` (the same copy from a directory
    relative to the pack root, for a pack that freezes its own controls).
    """

    control: str
    kind: ControlKind
    base: Literal["starter", "reference"]
    overlay: str = "-"
    root: str = "."
    note: str = ""


IMPLICIT = (
    ControlSpec("starter", "starter", "starter"),
    ControlSpec("reference", "reference", "reference"),
)


def load_manifest(directory: Path) -> list[ControlSpec]:
    """Implicit starter and reference controls plus the task's declared ones."""
    specs = list(IMPLICIT)
    manifest = directory / "manifest.tsv"
    if not manifest.is_file():
        return specs
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            kind, base = row["kind"], row["base"]
            if kind not in _KINDS or base not in {"starter", "reference"}:
                raise ValueError(f"invalid control row: {row}")
            if row["control"] in {spec.control for spec in specs}:
                raise ValueError(f"duplicate control id: {row['control']}")
            specs.append(
                ControlSpec(
                    control=row["control"],
                    kind=cast(ControlKind, kind),
                    base=cast(Literal["starter", "reference"], base),
                    overlay=row.get("overlay") or "-",
                    root=row.get("root") or ".",
                    note=row.get("note") or "",
                )
            )
    return specs


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _within(parent: Path, child: Path) -> Path:
    resolved = child.resolve()
    if not resolved.is_relative_to(parent.resolve()):
        raise ValueError(f"control path escapes its directory: {child}")
    return resolved


def _apply_reference(task: StudyTask, paths: StudyPaths, app: Path) -> None:
    """Run the task's own oracle with ``/app`` and ``/solution`` relocated.

    Every pack ships ``solution/solve.sh`` for Harbor's oracle agent. Reusing it
    keeps one definition of "the reference" instead of a second, study-only one.
    """
    if task.reference_tree is not None:
        # The pack keeps its reference outside Harbor, with no oracle script to relocate.
        pack = paths.pack_root(task.pack_dir)
        source_name, target_name = task.reference_tree
        source = _within(pack, pack / source_name)
        target = _within(app, app / target_name)
        if not source.is_dir() or not target.is_dir():
            raise RuntimeError(f"no reference tree for {task.key}")
        shutil.copytree(source, target, symlinks=False, dirs_exist_ok=True)
        return
    solution = paths.pack_root(task.pack_dir) / "private" / "harbor" / task.task / "solution"
    if task.reference_overlay is not None:
        # The pack's oracle targets another layout; its reference files go to their Hub paths.
        source_name, target_name = task.reference_overlay
        source = _within(solution, solution / source_name)
        target = _within(app, app / target_name)
        if source.is_dir():
            shutil.copytree(source, target, symlinks=False, dirs_exist_ok=True)
        elif source.is_file() and target.parent.is_dir():
            shutil.copyfile(source, target)
        else:
            raise RuntimeError(f"no reference oracle for {task.key}")
        return
    if not (solution / "solve.sh").is_file():
        # RimWorld ships no oracle script: its reference is solution/after, the fixed
        # files at their workspace paths, which the pack's own control tooling copies
        # over the starter the same way.
        after = solution / "after"
        if not after.is_dir():
            raise RuntimeError(f"no reference oracle for {task.key}")
        shutil.copytree(after, app, symlinks=False, dirs_exist_ok=True)
        return
    # The oracle may delegate to helper scripts that name /app or /solution
    # themselves, so every script is relocated in a scratch copy, not only solve.sh.
    with tempfile.TemporaryDirectory(prefix="study-oracle-") as scratch:
        relocated = Path(scratch) / "solution"
        shutil.copytree(solution, relocated, symlinks=False)
        for script_path in [*relocated.rglob("*.sh"), *relocated.rglob("*.py")]:
            text = script_path.read_text(encoding="utf-8")
            script_path.write_text(
                _SOLUTION_TOKEN.sub(
                    str(relocated), _WORKSPACE_TOKEN.sub(str(app), _APP_TOKEN.sub(str(app), text))
                ),
                encoding="utf-8",
            )
        completed = subprocess.run(
            ["bash", str(relocated / "solve.sh")],
            cwd=app,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"reference oracle failed for {task.key}: {completed.stderr[-2000:]}")


def starter_workspace(task: StudyTask, paths: StudyPaths) -> Path:
    """The task's starter as the study Hub materializes it, shared by every study process."""
    return paths.state_dir / "packs" / task.game / task.pack / "workspaces" / task.task


def materialize(task: StudyTask, spec: ControlSpec, paths: StudyPaths, workspace: Path) -> Path:
    """Build the control tree from the starter ``workspace`` and return the directory that is submitted.

    The starter is copied under the starter lock, because any study process that
    constructs its Hub rebuilds every starter workspace.
    """
    destination = paths.controls / task.game / task.pack / task.task / spec.control
    if destination.exists():
        shutil.rmtree(destination)
    app = destination / "app"
    submission = app if task.submission_is_app else app / task.app_subdir
    submission.parent.mkdir(parents=True, exist_ok=True)
    with starter_lock(paths):
        shutil.copytree(workspace, submission, symlinks=False)
    if spec.base == "reference":
        _apply_reference(task, paths, app)
    if spec.overlay != "-":
        source_root = paths.study_controls(task.pack_dir, task.task)
        mode, _, name = spec.overlay.partition(":")
        pack = paths.pack_root(task.pack_dir)
        source = _within(pack, pack / name) if mode == "pack" else _within(source_root, source_root / name)
        target = _within(app, app / spec.root) if task.submission_is_app else submission
        if mode == "patch":
            applied = subprocess.run(
                ["patch", "-p1", "--forward", "--no-backup-if-mismatch", "-i", str(source)],
                cwd=target,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if applied.returncode != 0:
                raise RuntimeError(f"{spec.control}: patch did not apply: {applied.stdout[-1500:]}")
        elif mode in {"tree", "pack"}:
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            raise ValueError(f"unknown overlay: {spec.overlay}")
    return submission


def evaluate(task: StudyTask, submission: Path, paths: StudyPaths) -> dict[str, Any]:
    """One full-profile evaluation in one of the pack's engine slots.

    At most four evaluations of one game pack run at once across every study process on
    the host (``hubs.engine_slot``); a further one waits for a free slot.
    """
    if (task.game, task.pack) == ("garrys-mod", "addons"):
        from . import gmod_eval

        with engine_slot(paths.locks, f"{task.game}-{task.pack}"):
            return {"result": gmod_eval.evaluate(paths.pack_root(task.pack_dir), task.task, submission)}
    # Constructed before taking a slot, so a first construction never holds an engine slot.
    hub = open_hub(paths)
    with engine_slot(paths.locks, f"{task.game}-{task.pack}"):
        return hub.evaluate_task(task.key, submission, profile="full")


def verdict(
    kind: ControlKind, clause_map: ClauseMap, table: Mapping[str, str], result: dict[str, Any]
) -> list[str]:
    """Why a control did not behave as its kind requires; empty when it did."""
    target = clause_map.case_ids("target")
    preserved = clause_map.case_ids("preserved")
    failed = [case for case, seen in table.items() if seen == "F"]
    unobserved = [case for case, seen in table.items() if seen == "U"]
    problems: list[str] = []
    resolved = result.get("complete") is True and result.get("passed") is True
    if kind in {"reference", "alternative"}:
        if not resolved or failed or unobserved:
            problems.append(f"must resolve with every case passing; failed={failed} unobserved={unobserved}")
    elif kind == "starter":
        if resolved:
            problems.append("the unchanged starter resolves the task")
        broken = [case for case in preserved if table.get(case) != "P"]
        if broken:
            problems.append(f"preserved contracts have no passing baseline in the starter: {broken}")
    elif kind == "target-negative":
        if resolved or not any(case in target for case in failed):
            problems.append("must fail at least one target case")
        stray = [case for case in failed if case not in target]
        if stray:
            problems.append(f"fails cases outside the target set: {stray}")
    elif kind == "compat-negative":
        lost = [case for case in target if table.get(case) != "P"]
        if lost:
            problems.append(f"the requested target must keep working; not passing: {lost}")
        if not any(case in preserved for case in failed):
            problems.append("must violate at least one preserved contract")
    return problems


def record_dir(task: StudyTask, paths: StudyPaths) -> Path:
    return paths.e0_records / task.game / task.pack / task.task


def execute(task: StudyTask, spec: ControlSpec, paths: StudyPaths, *, reuse: bool) -> dict[str, Any]:
    """Build and evaluate one control tree; return the raw execution record.

    With ``reuse`` an earlier execution of the byte-identical tree under the same
    runtime identities is returned instead of being repeated.
    """
    open_hub(paths)
    submission = materialize(task, spec, paths, starter_workspace(task, paths))
    digest = tree_digest(submission)
    identity = runtime_identity(task, paths)
    stored = record_dir(task, paths) / f"{spec.control}.execution.json"
    if reuse and stored.is_file():
        previous = json.loads(stored.read_text(encoding="utf-8"))
        if (
            previous.get("submissionDigest") == digest
            and previous.get("runtimeIdentity") == identity
            and previous.get("evaluatorError") is None
            # An incomplete run may be a transient engine fault; only the unchanged
            # starter is expected to be incomplete, so nothing else is reused then.
            and (spec.control == "starter" or (previous.get("result") or {}).get("complete") is True)
        ):
            return {**previous, "reused": True}
    started = datetime.now(UTC)
    try:
        run = evaluate(task, submission, paths)
        result, error = run["result"], None
    except Exception as failure:  # noqa: BLE001 - a control that cannot run is a recorded outcome
        run, result, error = {}, {}, f"{type(failure).__name__}: {failure}"
    execution = {
        "task": task.key,
        "control": spec.control,
        "submissionDigest": digest,
        "runtimeIdentity": identity,
        "startedAt": started.isoformat(),
        "finishedAt": datetime.now(UTC).isoformat(),
        "runId": run.get("id"),
        "logPath": run.get("logPath") or run.get("log_path"),
        "result": result,
        "evaluatorError": error,
        "reused": False,
    }
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_text(
        json.dumps(execution, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return execution


def runtime_identity(task: StudyTask, paths: StudyPaths) -> str:
    """The immutable verifier identity a result was produced under."""
    if (task.game, task.pack) == ("garrys-mod", "addons"):
        from . import gmod_eval

        return gmod_eval.image_id()
    import sqlite3

    database = sqlite3.connect(f"file:{paths.state_dir / 'state.sqlite'}?mode=ro", uri=True)
    try:
        rows = database.execute(
            "select runtime_key, artifact_json from runtime_artifacts where runtime_key like ?",
            (f"{task.game}/%",),
        ).fetchall()
    finally:
        database.close()
    identities = []
    for key, raw in sorted(rows):
        artifact = json.loads(raw)
        images = (artifact.get("metadata") or {}).get("images") or {}
        identities.append(f"{key}={images.get(task.task) or artifact.get('identity')}")
    return ";".join(identities)


def run_control(
    task: StudyTask, spec: ControlSpec, paths: StudyPaths, clause_map: ClauseMap, *, reuse: bool = False
) -> dict[str, Any]:
    execution = execute(task, spec, paths, reuse=reuse)
    result, error = execution["result"], execution["evaluatorError"]
    run = {"id": execution["runId"], "logPath": execution["logPath"]}
    started = datetime.fromisoformat(execution["startedAt"])
    submission_digest = execution["submissionDigest"]
    table = case_table(result, clause_map.case_ids())
    record = {
        "task": task.key,
        "taskVersion": clause_map.task_version,
        "control": spec.control,
        "kind": spec.kind,
        "base": spec.base,
        "overlay": spec.overlay,
        "note": spec.note,
        "submissionDigest": submission_digest,
        "runtimeIdentity": execution["runtimeIdentity"],
        "reused": execution["reused"],
        "startedAt": started.isoformat(),
        "finishedAt": execution["finishedAt"],
        "runId": run.get("id"),
        "logPath": run.get("logPath") or run.get("log_path"),
        "score": result.get("score"),
        "complete": result.get("complete"),
        "passed": result.get("passed"),
        "cases": table,
        "problems": [error] if error else verdict(spec.kind, clause_map, table, result),
        "evaluatorError": error,
    }
    out = record_dir(task, paths)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{spec.control}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record
