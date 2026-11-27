from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from . import controls, exclusions
from .clausemap import ClauseMap
from .e1config import StudyConfig
from .exclusions import Exclusions
from .hubs import seed_runtime_records
from .inventory import TASKS, task_for
from .observations import observed_cases
from .paths import StudyPaths

app = typer.Typer(no_args_is_help=True, add_completion=False)
e0 = typer.Typer(no_args_is_help=True, help="Contract admission: clause maps and control runs.")
e1 = typer.Typer(no_args_is_help=True, help="The frozen model-by-task study.")
e2 = typer.Typer(no_args_is_help=True, help="Interventions on observed integration failures.")
app.add_typer(e0, name="e0")
app.add_typer(e1, name="e1")
app.add_typer(e2, name="e2")


def _echo(value: object) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


@app.command()
def tasks() -> None:
    """List the registered study inventory."""
    _echo([{"key": task.key, "kind": task.kind, "sourceFamily": task.source_family} for task in TASKS])


@app.command()
def seed(
    operator_database: Annotated[
        Path, typer.Option(help="Operator Hub state.sqlite to read runtime records from.")
    ],
) -> None:
    """Copy prepared-runtime records (never provider sessions) into the study Hub."""
    _echo({"seeded": seed_runtime_records(StudyPaths.load(), operator_database)})


@e0.command()
def probe(task_key: str, control: str = "reference") -> None:
    """Run one implicit control without a clause map and print the observed case IDs."""
    paths = StudyPaths.load()
    task = task_for(task_key)
    spec = next(item for item in controls.IMPLICIT if item.control == control)
    from .hubs import open_hub

    open_hub(paths)
    submission = controls.materialize(task, spec, paths, controls.starter_workspace(task, paths))
    result = controls.evaluate(task, submission, paths)["result"]
    _echo(
        {
            "task": task.key,
            "control": control,
            "score": result.get("score"),
            "complete": result.get("complete"),
            "passed": result.get("passed"),
            "cases": observed_cases(result),
        }
    )


@e0.command()
def baseline(task_keys: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Execute the unchanged starter and the reference of each selected task (no clause map needed)."""
    paths = StudyPaths.load()
    for key in _selected(task_keys or []):
        task = task_for(key)
        for spec in controls.IMPLICIT:
            execution = controls.execute(task, spec, paths, reuse=True)
            result = execution["result"]
            typer.echo(
                json.dumps(
                    {
                        "task": key,
                        "control": spec.control,
                        "score": result.get("score"),
                        "complete": result.get("complete"),
                        "passed": result.get("passed"),
                        "cases": len(observed_cases(result)),
                        "reused": execution["reused"],
                        "error": execution["evaluatorError"],
                    },
                    ensure_ascii=False,
                )
            )


@e0.command()
def draft_maps(task_keys: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Write draft clause maps under the study data directory from the recorded baseline."""
    from . import mapgen

    paths = StudyPaths.load()
    for key in _selected(task_keys or []):
        task = task_for(key)
        tables = {}
        for control in ("starter", "reference"):
            stored = controls.record_dir(task, paths) / f"{control}.execution.json"
            tables[control] = observed_cases(json.loads(stored.read_text(encoding="utf-8"))["result"])
        output = paths.data_root / "e0" / "map-drafts" / task.game / task.pack / f"{task.task}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                mapgen.draft(task, paths, tables["starter"], tables["reference"]),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        typer.echo(str(output))


def _selected(task_keys: list[str]) -> list[str]:
    return task_keys or [task.key for task in TASKS]


@e0.command()
def run(
    task_keys: Annotated[list[str] | None, typer.Argument()] = None,
    only: Annotated[str | None, typer.Option(help="Run a single control id.")] = None,
    reuse: Annotated[bool, typer.Option(help="Reuse an identical earlier execution.")] = True,
) -> None:
    """Run every declared control of the selected tasks and record the outcomes."""
    paths = StudyPaths.load()
    summary = []
    for key in _selected(task_keys or []):
        task = task_for(key)
        directory = paths.study_controls(task.pack_dir, task.task)
        clause_map = ClauseMap.load(directory / "clause-map.json")
        for spec in controls.load_manifest(directory):
            if only is not None and spec.control != only:
                continue
            record = controls.run_control(task, spec, paths, clause_map, reuse=reuse)
            row = {
                "task": key,
                "control": spec.control,
                "kind": spec.kind,
                "score": record["score"],
                "complete": record["complete"],
                "passed": record["passed"],
                "problems": record["problems"],
            }
            typer.echo(json.dumps(row, ensure_ascii=False))
            summary.append(row)
    raise typer.Exit(1 if any(row["problems"] for row in summary) else 0)


@e0.command()
def check_maps(task_keys: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Validate that every selected task has a well-formed clause map and manifest."""
    paths = StudyPaths.load()
    problems = []
    for key in _selected(task_keys or []):
        task = task_for(key)
        directory = paths.study_controls(task.pack_dir, task.task)
        try:
            clause_map = ClauseMap.load(directory / "clause-map.json")
            if clause_map.task != key:
                raise ValueError("clause map names a different task")
            controls.load_manifest(directory)
        except (OSError, ValueError) as error:
            problems.append({"task": key, "problem": str(error)[:400]})
    _echo({"checked": len(_selected(task_keys or [])), "problems": problems})
    raise typer.Exit(1 if problems else 0)


@e0.command()
def flag(task_keys: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Mark cases a strict-reading alternative does not pass as over-constrained.

    The flag is derived from recorded engine evidence only. A case is flagged
    when any ``alternative-strict-reading*`` control of the task observed it as
    failed or could not observe it; assertions themselves are never edited.
    """
    paths = StudyPaths.load()
    for key in _selected(task_keys or []):
        task = task_for(key)
        directory = paths.study_controls(task.pack_dir, task.task)
        path = directory / "clause-map.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        rejected: set[str] = set()
        for spec in controls.load_manifest(directory):
            if not spec.control.startswith("alternative-strict-reading"):
                continue
            record = controls.record_dir(task, paths) / f"{spec.control}.json"
            if record.is_file():
                cases = json.loads(record.read_text(encoding="utf-8"))["cases"]
                rejected |= {case for case, seen in cases.items() if seen != "P"}
        for case in document["cases"]:
            if case["id"] in rejected:
                case["over_constrained"] = True
            else:
                case.pop("over_constrained", None)
        ClauseMap.model_validate(document)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        typer.echo(json.dumps({"task": key, "overConstrained": sorted(rejected)}, ensure_ascii=False))


@e0.command(name="report")
def e0_report() -> None:
    """Decide admission from clause maps and control records and write the E0 report."""
    from . import admission

    paths = StudyPaths.load()
    summary = admission.report(paths)
    out = paths.data_root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "E0-admission.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "E0.md").write_text(admission.markdown(summary), encoding="utf-8")
    _echo({key: summary[key] for key in ("registered", "admitted", "compatibilityQualified", "excluded")})


def _config(path: Path) -> tuple[StudyConfig, str, Exclusions]:
    """The frozen study configuration, its digest and its checked task exclusions."""
    study, digest = StudyConfig.load(path)
    paths = StudyPaths.load()
    try:
        excluded = exclusions.load(paths, study, digest)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--config") from None
    return study, digest, excluded


def _refuse_excluded(study: StudyConfig, excluded: Exclusions, attempt_ids: list[str]) -> None:
    """Refuse the named attempts if any is of an excluded task, before acting on one of them."""
    root = StudyPaths.load().e1_study(study.study_id) / "attempts"
    for attempt_id in attempt_ids:
        path = root / attempt_id / "attempt.json"
        if not path.is_file():
            continue  # the command itself reports a missing attempt
        task = json.loads(path.read_text(encoding="utf-8"))["task"]
        try:
            exclusions.refuse_excluded(task, attempt_id, excluded.tasks)
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--attempt") from None


@e1.command()
def image(config: Annotated[Path, typer.Option()]) -> None:
    """Build the pinned agent image named by the study configuration."""
    from . import attempts

    study, _digest, _excluded = _config(config)
    _echo({"image": study.agent_image, "imageId": attempts.build_agent_image(study.agent_image)})


@e1.command()
def plan(config: Annotated[Path, typer.Option()]) -> None:
    """Print the frozen schedule and what its declared task exclusions leave of it."""
    from . import attempts

    study, digest, excluded = _config(config)
    items = attempts.schedule(study)
    remaining = [item for item in items if item.task not in excluded.tasks]
    _echo(
        {
            "configDigest": digest,
            "attempts": len(items),
            "excludedTasks": len(excluded.tasks),
            "excludedAttempts": len(items) - len(remaining),
            "remainingAttempts": len(remaining),
            "first": [item.attempt_id for item in remaining[:6]],
        }
    )


@e1.command(name="run")
def run_attempts(
    config: Annotated[Path, typer.Option()],
    lane: Annotated[int, typer.Option(help="This lane's index, starting at 0.")] = 0,
    lanes: Annotated[int, typer.Option(help="Total parallel lanes.")] = 1,
    limit: Annotated[int | None, typer.Option(help="Stop after this many new attempts.")] = None,
    only: Annotated[str | None, typer.Option(help="Run one attempt id (smoke tests).")] = None,
) -> None:
    """Run this lane's share of the schedule; finished attempts are never repeated.

    Attempts of excluded tasks are skipped; every other attempt keeps its schedule
    order and therefore its lane.
    """
    from . import attempts

    study, digest, excluded = _config(config)
    paths = StudyPaths.load()
    harness = attempts.harness_revision(paths)
    if harness["dirty"]:
        # A record must name the code that produced it; local edits would make it unreproducible.
        raise typer.BadParameter("src/, plugins/ or tools/study has uncommitted changes; commit before a run")
    done = 0
    for item in attempts.schedule(study):
        if only is not None and item.attempt_id != only:
            continue
        if only is None and item.order % lanes != lane:
            continue
        if item.task in excluded.tasks:
            if only is not None:
                raise typer.BadParameter(f"{only} is an attempt of an excluded task", param_hint="--only")
            continue
        if (paths.data_root / f"STOP.{study.study_id}").exists():
            typer.echo("stop file present; leaving the remaining schedule untouched")
            break
        record = attempts.run_attempt(paths, study, digest, item, harness)
        typer.echo(
            json.dumps(
                {
                    key: record[key]
                    for key in (
                        "attempt_id",
                        "outcome",
                        "score",
                        "targetOutcome",
                        "preservedOutcome",
                        "jointOutcome",
                    )
                }
            )
        )
        done += 1
        if limit is not None and done >= limit:
            break


@e1.command()
def rescore(config: Annotated[Path, typer.Option()], attempt: Annotated[str, typer.Option()]) -> None:
    """Score an attempt that ended by context exhaustion and was recorded unscored."""
    from . import attempts

    study, _digest, excluded = _config(config)
    _refuse_excluded(study, excluded, [attempt])
    record = attempts.rescore(StudyPaths.load(), study, attempt, excluded=excluded.tasks)
    _echo({key: record[key] for key in ("attempt_id", "outcome", "targetOutcome", "preservedOutcome")})


@e1.command()
def reevaluate(
    config: Annotated[Path, typer.Option()],
    attempt: Annotated[list[str] | None, typer.Option(help="Limit to these attempt IDs.")] = None,
) -> None:
    """Void executions whose evaluator container was never created, and evaluate again."""
    from . import aggregate, attempts

    study, _digest, excluded = _config(config)
    paths = StudyPaths.load()
    root = paths.data_root / "e1" / study.study_id
    _refuse_excluded(study, excluded, attempt or [])
    selected = attempt or [
        record["attempt_id"] for record in aggregate.attempt_records(root, excluded=excluded.tasks)
    ]
    for attempt_id in selected:
        record = attempts.reevaluate(paths, study, attempt_id, excluded=excluded.tasks)
        if record is not None:
            typer.echo(
                json.dumps(
                    {
                        "attempt_id": attempt_id,
                        "outcome": record["outcome"],
                        "voidedExecutions": len(record["voidedExecutions"]),
                    }
                )
            )


@e1.command(name="export-deferred")
def export_deferred(
    config: Annotated[Path, typer.Option()],
    out: Annotated[Path, typer.Option(help="A new directory for the evaluation kit.")],
) -> None:
    """Pack every attempt pending evaluation on another host into an evaluation kit."""
    from . import deferred

    study, digest, excluded = _config(config)
    _echo(deferred.export(StudyPaths.load(), study, digest, out, excluded=excluded.tasks))


@e1.command(name="import-evaluations")
def import_evaluations(
    config: Annotated[Path, typer.Option()],
    kit: Annotated[Path, typer.Option(help="The returned evaluation kit directory.")],
    host: Annotated[str, typer.Option(help="The evaluation host and engine build, as reported.")],
) -> None:
    """Score a returned evaluation kit into its pending attempts."""
    from . import deferred

    study, digest, excluded = _config(config)
    imported = deferred.import_results(StudyPaths.load(), study, digest, kit, host, excluded=excluded.tasks)
    _echo({"imported": imported, "count": len(imported)})


@e1.command(name="review-balatro")
def review_balatro(
    config: Annotated[Path, typer.Option()],
    kit: Annotated[Path, typer.Option(help="An evaluation kit written by e1 export-deferred.")],
    pack: Annotated[Path, typer.Option(help="The Balatro pack directory (benchmarks/balatro).")],
    state: Annotated[Path, typer.Option(help="The Balatro operator state directory.")],
    cache: Annotated[Path, typer.Option(help="The Balatro operator cache directory.")],
    artifact: Annotated[Path, typer.Option(help="The prepared runtime artifact (runtime verify output).")],
    evaluate: Annotated[
        bool, typer.Option(help="Then evaluate each sealed attempt once, stopping at an incomplete run.")
    ] = False,
) -> None:
    """Seal each Balatro submission of a kit that the static review policy clears.

    A submission with any finding is left unsealed for the operator to read. Exits 2 when
    one is left, and 4 when an evaluation was incomplete (its artifact is then halted).
    """
    from . import balatro_review

    study, digest, _excluded = _config(config)
    try:
        manifest = balatro_review.kit_manifest(kit, study.study_id, digest)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--kit") from None
    try:
        identity = balatro_review.artifact_identity(artifact)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--artifact") from None
    operator = balatro_review.container_operator(pack, state, cache, artifact)
    reports = balatro_review.review_kit(kit, manifest, operator, identity)
    summary: dict[str, object] = {
        "policy": balatro_review.POLICY,
        "sealed": [r["attemptId"] for r in reports if r["decision"] == balatro_review.SEALED],
        "operatorReviewRequired": [
            {"attemptId": r["attemptId"], "findings": r["findings"]}
            for r in reports
            if r["decision"] != balatro_review.SEALED
        ],
    }
    runs: list[dict[str, object]] = []
    if evaluate:
        runs = list(balatro_review.evaluate_sealed(kit, manifest, balatro_review.rhenium_run(), identity))
        summary["evaluated"] = runs
    _echo(summary)
    if any(run["complete"] is not True for run in runs):
        raise typer.Exit(4)
    if summary["operatorReviewRequired"]:
        raise typer.Exit(2)


@e1.command(name="adjudicate")
def adjudicate_command(config: Annotated[Path, typer.Option()]) -> None:
    """Close unattributed attempts that a declared rule can decide from trusted verifier logs."""
    from . import adjudicate, aggregate

    study, _digest, excluded = _config(config)
    paths = StudyPaths.load()
    root = paths.data_root / "e1" / study.study_id
    records = aggregate.load_ledger(root, excluded=excluded.tasks, adjudicated=False)
    decisions = adjudicate.adjudicate(records, paths.state_dir)
    ruled = {item["attempt_id"] for item in decisions}
    decisions += [
        item for item in adjudicate.manual_decisions(root, records) if item["attempt_id"] not in ruled
    ]
    adjudicate.write(root, decisions)
    _echo({"decisions": len(decisions), "attempts": [item["attempt_id"] for item in decisions]})


@e1.command()
def report(config: Annotated[Path, typer.Option()]) -> None:
    """Aggregate the ledger (task-balanced, game-balanced, joint outcomes, usage)."""
    from . import aggregate

    study, _digest, excluded = _config(config)
    paths = StudyPaths.load()
    root = paths.data_root / "e1" / study.study_id
    summary = aggregate.summarize(aggregate.load_ledger(root, excluded=excluded.tasks), study.repeats)
    summary["pendingEvaluation"] = aggregate.pending_evaluation(root, excluded=excluded.tasks)
    summary["exclusions"] = excluded.public()
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _echo(summary["summary"])


@e2.command()
def select(config: Annotated[Path, typer.Option()]) -> None:
    """Apply the frozen selection rule to the finished ledger."""
    from . import aggregate
    from . import e2 as interventions

    study, _digest, excluded = _config(config)
    paths = StudyPaths.load()
    records = aggregate.load_ledger(paths.data_root / "e1" / study.study_id, excluded=excluded.tasks)
    selection = interventions.select(records, study)
    out = paths.data_root / "e2" / study.study_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _echo(selection)


@e2.command()
def replay(
    config: Annotated[Path, typer.Option()],
    attempt: Annotated[str, typer.Option()],
    patch: Annotated[
        Path | None, typer.Option(help="Intervention patch (patch -p1 from the submission root).")
    ] = None,
) -> None:
    """Replay a frozen submission, unchanged or with one intervention, in the same fixtures."""
    from . import e2 as interventions

    study, _digest, excluded = _config(config)
    _refuse_excluded(study, excluded, [attempt])
    _echo(interventions.replay(StudyPaths.load(), study, attempt, patch, excluded=excluded.tasks))


@app.command(name="paper-export")
def paper_export(
    config: Annotated[Path, typer.Option()],
    out: Annotated[Path, typer.Option(help="Directory for the sanitized JSON exports.")],
    model: Annotated[
        list[str] | None, typer.Option(help="Report only these model condition ids (repeatable).")
    ] = None,
) -> None:
    """Write sanitized E0/E1/E2 result files for the manuscript artifact."""
    from . import paper_export as exporter

    study, digest, excluded = _config(config)
    written = exporter.export(StudyPaths.load(), study, digest, out, tuple(model or ()), exclusions=excluded)
    _echo([str(path) for path in written])
