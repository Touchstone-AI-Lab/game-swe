from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import TypeAdapter

from .cleanroom import CleanRoomSynthesizer
from .config import AuthoringSecrets, find_project_root
from .engine import HubEngineValidator
from .export import export_training_data
from .model_client import ModelClient
from .models import (
    CandidateStatus,
    HistoricalFix,
    RunMode,
    RunStatus,
    SynthesisBundle,
    ValidationReport,
)
from .pipeline import AuthoringPipeline, AuthoringRunError, used_fix_keys
from .publisher import PackPublisher
from .sources import CurseForgeSource, GitHubSource, ModrinthSource
from .sources.base import SourceAdapter
from .state import AuthoringStore

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
review_app = typer.Typer(no_args_is_help=True)
app.add_typer(review_app, name="review")


@app.command("macos-prepare")
def macos_prepare(
    run_id: str,
    candidate_id: str,
    game_dir: Annotated[Path, typer.Option("--game-dir")],
) -> None:
    """Explicitly copy a local Stardew install and prepare native maintenance diagnostics."""
    from .macos import prepare_macos

    root, _store = _context()
    try:
        result = prepare_macos(
            root,
            run_id,
            candidate_id,
            game_dir,
            progress=lambda value, phase: typer.echo(f"{value}% {phase}", err=True),
        )
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        typer.echo(f"macOS preparation unavailable: {error}", err=True)
        raise typer.Exit(1) from None
    typer.echo(json.dumps(result, indent=2, default=str))
    if result.get("status") == "action_required":
        raise typer.Exit(2)
    if result.get("status") != "completed":
        raise typer.Exit(1)


@app.command("macos-check")
def macos_check(run_id: str, candidate_id: str) -> None:
    """Run native C# suite diagnostics; never approve or publish a candidate."""
    from .macos import check_macos

    root, _store = _context()
    try:
        result = check_macos(root, run_id, candidate_id)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        typer.echo(f"macOS diagnostic unavailable: {error}", err=True)
        raise typer.Exit(1) from None
    typer.echo(json.dumps(result, indent=2, default=str))
    # This command is diagnostic-only and is never a successful scoring command.
    raise typer.Exit(2)


def _context() -> tuple[Path, AuthoringStore]:
    root = find_project_root()
    store = AuthoringStore(root / ".rhenium" / "authoring" / "authoring.sqlite")
    return root, store


@contextmanager
def _synthesizer(
    secrets: AuthoringSecrets,
    verifier_check_command: Path | None = None,
    project_check_command: Path | None = None,
    stage_attempts: int = 3,
) -> Iterator[CleanRoomSynthesizer]:
    def progress(event: dict[str, object]) -> None:
        typer.echo(json.dumps(event, ensure_ascii=False), err=True)

    with ExitStack() as clients:
        client = ModelClient(secrets.model, on_event=progress)
        clients.callback(client.close)
        reviewer = None
        if secrets.model.review_api_key is not None:
            reviewer = ModelClient(
                secrets.model.model_copy(
                    update={"api_key": secrets.model.review_api_key, "review_api_key": None}
                ),
                on_event=progress,
            )
            clients.callback(reviewer.close)
        checker = None
        if verifier_check_command is not None:
            from .preflight import CommandVerifierCheck

            checker = CommandVerifierCheck(
                verifier_check_command,
                find_project_root() / ".rhenium/authoring/preflight",
            )
        project_checker = None
        if project_check_command is not None:
            from .preflight import CommandVerifierCheck

            project_checker = CommandVerifierCheck(
                project_check_command,
                find_project_root() / ".rhenium/authoring/project-preflight",
            )
        yield CleanRoomSynthesizer(
            client,
            reviewer=reviewer,
            verifier_check=checker,
            project_check=project_checker.check_files if project_checker is not None else None,
            stage_attempts=stage_attempts,
        )


@app.command("run")
def run(
    mode: Annotated[RunMode, typer.Option("--mode")] = RunMode.REVIEW,
    sources: Annotated[str, typer.Option("--sources")] = "github,modrinth,curseforge",
    games: Annotated[str, typer.Option("--games")] = (
        "dst,stardew-valley,isaac-rebirth,garrys-mod,minecraft"
    ),
    limit: Annotated[int, typer.Option("--limit", min=2, max=100)] = 20,
    target: Annotated[int | None, typer.Option("--target", min=1, max=20)] = None,
    max_capsules: Annotated[int, typer.Option("--max-capsules", min=2, max=7)] = 7,
    engine_repair_rounds: Annotated[int, typer.Option("--engine-repair-rounds", min=0, max=3)] = 1,
    engine_account: Annotated[str | None, typer.Option("--engine-account")] = None,
    stage_attempts: Annotated[int, typer.Option("--stage-attempts", min=1, max=5)] = 3,
    candidate_attempts: Annotated[int, typer.Option("--candidate-attempts", min=1, max=3)] = 2,
    verifier_check_command: Annotated[Path | None, typer.Option("--verifier-check-command")] = None,
    project_check_command: Annotated[Path | None, typer.Option("--project-check-command")] = None,
    exclude_used_fixes: Annotated[
        bool,
        typer.Option(
            "--exclude-used-fixes/--allow-used-fixes",
            help="Skip fixes that an earlier run under .rhenium/authoring already used.",
        ),
    ] = False,
    per_repository: Annotated[
        int | None,
        typer.Option("--per-repository", min=1, max=100, help="Cap harvested fixes per repository."),
    ] = None,
) -> None:
    """Harvest historical behavior and build clean-room composite candidates.

    --target N keeps regenerating rejected candidates (one extra attempt each)
    and stops once N candidates pass complete engine validation. It works best
    with --engine-account, which explicitly prepares each candidate's synth
    runtime inside the isolated validation Hub so validation and the
    engine-feedback repair run inside this one command; a missing provider
    session still stops at action_required (never an implicit login).
    """

    root, store = _context()
    secrets = AuthoringSecrets.load(root)
    source_names = tuple(value.strip() for value in sources.split(",") if value.strip())
    game_ids = tuple(value.strip() for value in games.split(",") if value.strip())
    cache = root / ".rhenium" / "authoring" / "cache"
    github_token = (
        secrets.github.token.get_secret_value()
        if secrets.github is not None and secrets.github.token is not None
        else None
    )
    github = GitHubSource(github_token, cache_dir=cache / "github")
    modrinth = ModrinthSource(cache_dir=cache / "modrinth")
    adapters: dict[str, SourceAdapter] = {"github": github, "modrinth": modrinth}
    curseforge = None
    if "curseforge" in source_names:
        if secrets.curseforge is None:
            remaining = tuple(value for value in source_names if value != "curseforge")
            if not remaining:
                raise typer.BadParameter("[curseforge].api_key is required for CurseForge")
            typer.echo("CurseForge skipped: project-local API key is not configured", err=True)
            source_names = remaining
        else:
            curseforge = CurseForgeSource(
                secrets.curseforge.api_key.get_secret_value(), cache_dir=cache / "curseforge"
            )
            adapters["curseforge"] = curseforge
    try:
        with _synthesizer(
            secrets, verifier_check_command, project_check_command, stage_attempts
        ) as synthesizer:
            pipeline = AuthoringPipeline(
                root,
                store,
                synthesizer,
                adapters,
                github,
                validator=HubEngineValidator(root, prepare_account=engine_account),
                engine_repair_rounds=engine_repair_rounds,
                candidate_attempts=candidate_attempts,
            )
            try:
                run_id = pipeline.run(
                    mode=mode,
                    source_names=source_names,
                    game_ids=game_ids,
                    limit=limit,
                    target=target,
                    max_capsules=max_capsules,
                    excluded_fix_keys=(used_fix_keys(root) if exclude_used_fixes else frozenset()),
                    per_repository=per_repository,
                )
            except AuthoringRunError as error:
                typer.echo(str(error), err=True)
                raise typer.Exit(code=1) from None
    finally:
        github.close()
        modrinth.close()
        if curseforge is not None:
            curseforge.close()
    typer.echo(run_id)


@app.command("status")
def status(run_id: str) -> None:
    """Show secret-free state for one authoring run."""

    _root, store = _context()
    payload = {"run": store.run(run_id), "candidates": store.candidates(run_id)}
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command("model-check")
def model_check() -> None:
    """Verify the configured model endpoint without printing content or credentials."""

    root, _store = _context()
    secrets = AuthoringSecrets.load(root)
    events: list[dict[str, object]] = []
    client = ModelClient(secrets.model, max_attempts=1, transport_attempts=1, on_event=events.append)
    try:
        from .models import AuthoredPrompt

        try:
            client.complete(
                AuthoredPrompt,
                role="connectivity check",
                payload={"instruction": "Return a JSON object whose markdown field is hi."},
            )
        except RuntimeError as error:
            typer.echo(str(error), err=True)
            if "HTTP 400" in str(error):
                typer.echo(
                    "The endpoint rejected the request; check [model].reasoning_effort "
                    f"(currently {secrets.model.reasoning_effort!r}) and [model].max_tokens.",
                    err=True,
                )
            raise typer.Exit(code=1) from None
    finally:
        client.close()
    report: dict[str, object] = {"ok": True, "model": secrets.model.model}
    if secrets.model.protocol == "openai":
        report["reasoning_effort"] = secrets.model.reasoning_effort
    received = events[-1] if events and events[-1].get("status") == "received" else {}
    for key in ("reasoning_tokens", "completion_tokens", "reasoning_characters"):
        if key in received:
            report[key] = received[key]
    typer.echo(json.dumps(report))


@app.command("generate")
def generate(
    input_path: Annotated[Path, typer.Option("--input")],
    mode: Annotated[RunMode, typer.Option("--mode")] = RunMode.REVIEW,
    verifier_check_command: Annotated[Path | None, typer.Option("--verifier-check-command")] = None,
    project_check_command: Annotated[Path | None, typer.Option("--project-check-command")] = None,
) -> None:
    """Generate clean-room tasks from private historical-fix JSON without crawling."""

    root, store = _context()
    raw_path = input_path.expanduser()
    if raw_path.is_symlink():
        raise typer.BadParameter("historical-fix input must not be a symbolic link")
    path = raw_path.resolve()
    if not path.is_file():
        raise typer.BadParameter("historical-fix input must be a regular file")
    try:
        fixes = TypeAdapter(list[HistoricalFix]).validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise typer.BadParameter("historical-fix input is invalid") from error
    game_ids = tuple(sorted({fix.game_id for fix in fixes}))
    secrets = AuthoringSecrets.load(root)
    with _synthesizer(secrets, verifier_check_command, project_check_command) as synthesizer:
        pipeline = AuthoringPipeline(root, store, synthesizer, {}, None)
        try:
            run_id = pipeline.run(
                mode=mode,
                source_names=(),
                game_ids=game_ids,
                limit=max(2, len(fixes)),
                seed_fixes=fixes,
            )
        except AuthoringRunError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1) from None
    typer.echo(run_id)


@app.command("retry")
def retry(
    run_id: str,
    verifier_check_command: Annotated[Path | None, typer.Option("--verifier-check-command")] = None,
    project_check_command: Annotated[Path | None, typer.Option("--project-check-command")] = None,
) -> None:
    """Retry a failed run from its private persisted historical-fix input."""

    root, store = _context()
    previous = store.run(run_id)
    if previous["status"] != RunStatus.FAILED.value:
        raise typer.BadParameter("only a failed authoring run can be retried")
    fixes_path = root / ".rhenium" / "authoring" / "runs" / run_id / "historical-fixes.json"
    try:
        fixes = TypeAdapter(list[HistoricalFix]).validate_json(fixes_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise typer.BadParameter("failed run has no valid persisted input") from error
    secrets = AuthoringSecrets.load(root)
    with _synthesizer(secrets, verifier_check_command, project_check_command) as synthesizer:
        pipeline = AuthoringPipeline(root, store, synthesizer, {}, None)
        try:
            new_run_id = pipeline.run(
                mode=RunMode(str(previous["mode"])),
                source_names=(),
                game_ids=tuple(sorted({fix.game_id for fix in fixes})),
                limit=max(2, len(fixes)),
                seed_fixes=fixes,
            )
        except AuthoringRunError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1) from None
    typer.echo(new_run_id)


@app.command("resume")
def resume(
    run_id: str,
    engine_account: Annotated[str | None, typer.Option("--engine-account")] = None,
    engine_repair_rounds: Annotated[int, typer.Option("--engine-repair-rounds", min=0, max=3)] = 1,
    verifier_check_command: Annotated[Path | None, typer.Option("--verifier-check-command")] = None,
    project_check_command: Annotated[Path | None, typer.Option("--project-check-command")] = None,
) -> None:
    """Resume real-engine validation after explicit runtime preparation.

    With configured model secrets, a failed complete validation gets the same
    bounded engine-feedback repair as `run`; without them resume only
    re-validates.
    """

    root, store = _context()
    try:
        secrets: AuthoringSecrets | None = AuthoringSecrets.load(root)
    except ValueError as error:
        typer.echo(f"engine-feedback repair disabled: {error}", err=True)
        secrets = None
    if secrets is None:
        pipeline = AuthoringPipeline(
            root,
            store,
            None,
            {},
            None,
            validator=HubEngineValidator(root, prepare_account=engine_account),
            engine_repair_rounds=engine_repair_rounds,
        )
        pipeline.resume(run_id)
    else:
        with _synthesizer(secrets, verifier_check_command, project_check_command) as synthesizer:
            pipeline = AuthoringPipeline(
                root,
                store,
                synthesizer,
                {},
                None,
                validator=HubEngineValidator(root, prepare_account=engine_account),
                engine_repair_rounds=engine_repair_rounds,
            )
            pipeline.resume(run_id)
    typer.echo(run_id)


@review_app.command("approve")
def approve(run_id: str, candidate_id: str) -> None:
    """Approve one validated candidate in review mode."""

    root, store = _context()
    candidate = _candidate(store, run_id, candidate_id)
    if candidate["status"] != CandidateStatus.VALIDATED.value:
        raise typer.BadParameter("only a validated candidate can be approved")
    store.put_candidate(
        run_id,
        candidate_id,
        str(candidate["game_id"]),
        CandidateStatus.APPROVED,
        dict(candidate["payload"]),
    )
    typer.echo(str(root / ".rhenium" / "authoring" / "runs" / run_id / "candidates" / candidate_id))


@review_app.command("reject")
def reject(run_id: str, candidate_id: str, reason: str = "rejected by reviewer") -> None:
    """Reject one staged candidate without deleting its private audit data."""

    _root, store = _context()
    candidate = _candidate(store, run_id, candidate_id)
    store.put_candidate(
        run_id,
        candidate_id,
        str(candidate["game_id"]),
        CandidateStatus.REJECTED,
        dict(candidate["payload"]),
        reason=reason,
    )


@app.command("publish")
def publish(run_id: str) -> None:
    """Publish approved, engine-validated review candidates."""

    root, store = _context()
    publisher = PackPublisher(root)
    published = 0
    for candidate in store.candidates(run_id):
        if candidate["status"] != CandidateStatus.APPROVED.value:
            continue
        candidate_root = (
            root / ".rhenium" / "authoring" / "runs" / run_id / "candidates" / str(candidate["id"])
        )
        bundle = SynthesisBundle.model_validate_json(
            (candidate_root / "private" / "bundle.json").read_text(encoding="utf-8")
        )
        validation = ValidationReport.model_validate_json(
            (candidate_root / "validation.json").read_text(encoding="utf-8")
        )
        record = publisher.publish(bundle, validation)
        store.put_candidate(
            run_id,
            str(candidate["id"]),
            str(candidate["game_id"]),
            CandidateStatus.PUBLISHED,
            record.model_dump(mode="json"),
        )
        published += 1
    remaining = {
        str(candidate["status"])
        for candidate in store.candidates(run_id)
        if candidate["status"]
        not in {
            CandidateStatus.PUBLISHED.value,
            CandidateStatus.REJECTED.value,
        }
    }
    store.update_run(
        run_id,
        RunStatus.AWAITING_REVIEW if remaining else RunStatus.COMPLETE,
    )
    typer.echo(str(published))


@app.command("export")
def export(run_id: str) -> None:
    """Export validated candidates as anonymous SWE-like JSONL and base archives."""

    root, _store = _context()
    run_root = root / ".rhenium" / "authoring" / "runs" / run_id
    destination = root / ".rhenium" / "authoring" / "exports" / run_id
    typer.echo(str(export_training_data(run_root, destination)))


def _candidate(store: AuthoringStore, run_id: str, candidate_id: str) -> dict[str, Any]:
    try:
        return next(value for value in store.candidates(run_id) if value["id"] == candidate_id)
    except StopIteration as error:
        raise typer.BadParameter("unknown candidate") from error


history_app = typer.Typer(no_args_is_help=True)
app.add_typer(history_app, name="history")


def _published_fix_keys(root: Path) -> set[str]:
    """Upstream fixes already vendored by a published Minecraft repository pack."""
    keys: set[str] = set()
    for pack in ("minecraft-core", "minecraft-history"):
        path = root / "benchmarks" / pack / "catalog.json"
        if not path.is_file():
            continue
        for task in json.loads(path.read_text(encoding="utf-8")).get("tasks", []):
            upstream = task.get("upstream") if isinstance(task, dict) else None
            if isinstance(upstream, dict) and upstream.get("fix_commit"):
                keys.add(f"{str(upstream['repository']).rstrip('/').casefold()}@{upstream['fix_commit']}")
    return keys


@history_app.command("run")
def history_run(
    game: Annotated[str, typer.Option("--game")] = "minecraft",
    repository: Annotated[
        list[str] | None, typer.Option("--repository", help="owner/name; repeat to skip search")
    ] = None,
    discover: Annotated[int, typer.Option("--discover", min=1, max=100)] = 30,
    per_repository: Annotated[int, typer.Option("--per-repository", min=1, max=50)] = 3,
    target: Annotated[int, typer.Option("--target", min=1, max=100)] = 5,
    pages: Annotated[int, typer.Option("--pages", min=1, max=20)] = 3,
    workers: Annotated[int, typer.Option("--workers", min=1, max=8)] = 2,
    max_turns: Annotated[int, typer.Option("--max-turns", min=8, max=80)] = 40,
    repair_rounds: Annotated[int, typer.Option("--engine-repair-rounds", min=0, max=3)] = 3,
    engine_account: Annotated[str | None, typer.Option("--engine-account")] = None,
    mode: Annotated[RunMode, typer.Option("--mode")] = RunMode.REVIEW,
    include_published: Annotated[
        bool, typer.Option("--include-published", help="allow fixes an existing pack already vendors")
    ] = False,
    fix: Annotated[
        list[str] | None,
        typer.Option("--fix", help="owner/repo@sha of one landed fix; repeat; skips the walk"),
    ] = None,
) -> None:
    """Author repository tasks from real project history (starter = parent of a landed fix)."""
    from .history.pipeline import HistoryPipeline

    root, store = _context()
    secrets = AuthoringSecrets.load(root)
    token = (
        secrets.github.token.get_secret_value()
        if secrets.github is not None and secrets.github.token is not None
        else None
    )

    def progress(event: dict[str, object]) -> None:
        typer.echo(json.dumps(event, ensure_ascii=False, default=str), err=True)

    with ExitStack() as stack:
        github = GitHubSource(token, cache_dir=root / ".rhenium" / "authoring" / "cache" / "github")
        stack.callback(github.close)
        client = ModelClient(secrets.model, on_event=progress)
        stack.callback(client.close)
        reviewer = None
        if secrets.model.review_api_key is not None:
            reviewer = ModelClient(
                secrets.model.model_copy(
                    update={"api_key": secrets.model.review_api_key, "review_api_key": None}
                ),
                on_event=progress,
            )
            stack.callback(reviewer.close)
        pipeline = HistoryPipeline(
            root, store, client, github, reviewer=reviewer, engine_account=engine_account, mode=mode,
            max_turns=max_turns, repair_rounds=repair_rounds, on_event=progress,
            excluded_fix_keys=set() if include_published else _published_fix_keys(root),
        )
        run_id = pipeline.run(
            game_id=game, repositories=list(repository or []), discover=discover,
            per_repository=per_repository, target=target, pages_per_run=pages, workers=workers,
            seeds=list(fix or []),
        )
    typer.echo(json.dumps({"run_id": run_id, **store.run(run_id)}, indent=2, default=str))


@history_app.command("resume")
def history_resume(
    run_id: str,
    candidate_ids: list[str],
    engine_account: Annotated[str, typer.Option("--engine-account")] = "default",
    mode: Annotated[RunMode, typer.Option("--mode")] = RunMode.REVIEW,
    from_review: Annotated[
        bool, typer.Option("--from-review", help="review (and revise) the authored task again first")
    ] = False,
) -> None:
    """Rerun reviewed candidates from their engine controls, reusing all model checkpoints."""
    from .history.pipeline import HistoryPipeline

    root, store = _context()
    secrets = AuthoringSecrets.load(root)
    token = (
        secrets.github.token.get_secret_value()
        if secrets.github is not None and secrets.github.token is not None
        else None
    )

    def progress(event: dict[str, object]) -> None:
        typer.echo(json.dumps(event, ensure_ascii=False, default=str), err=True)

    run_root = root / ".rhenium" / "authoring" / "runs" / run_id
    with ExitStack() as stack:
        github = GitHubSource(token, cache_dir=root / ".rhenium" / "authoring" / "cache" / "github")
        stack.callback(github.close)
        client = ModelClient(secrets.model, on_event=progress)
        stack.callback(client.close)
        pipeline = HistoryPipeline(
            root, store, client, github, engine_account=engine_account, mode=mode, on_event=progress
        )
        for candidate_id in candidate_ids:
            _candidate(store, run_id, candidate_id)
            status = pipeline.resume(run_id, run_root / "candidates" / candidate_id, from_review=from_review)
            typer.echo(json.dumps({"candidate": candidate_id, "status": status.value}))


@history_app.command("publish")
def history_publish(
    run_id: str,
    candidates: Annotated[
        list[str], typer.Argument(help="CANDIDATE=TASK_ID; the task id names the defect, not the commit")
    ],
) -> None:
    """Publish validated history candidates into benchmarks/minecraft-history."""
    from .history.minecraft_pack import PACK_DIRECTORY, add_task, initialize_pack, published_task_id
    from .history.pipeline import load_candidate
    from .history.study_controls import controls_markdown, write_study_controls

    root, store = _context()
    run_root = root / ".rhenium" / "authoring" / "runs" / run_id
    pack = root / "benchmarks" / PACK_DIRECTORY
    for item in candidates:
        candidate_id, separator, requested = item.partition("=")
        if not separator:
            raise typer.BadParameter(f"{item}: give CANDIDATE=TASK_ID")
        record = _candidate(store, run_id, candidate_id)
        if record["status"] not in (
            CandidateStatus.VALIDATED.value,
            CandidateStatus.APPROVED.value,
            CandidateStatus.PUBLISHED.value,
        ):
            raise typer.BadParameter(f"{candidate_id} is {record['status']}, not validated")
        candidate_root = run_root / "candidates" / candidate_id
        task, outcomes = load_candidate(root, candidate_root)
        try:
            task.published_id = published_task_id(task.fix, requested)
        except ValueError as error:
            raise typer.BadParameter(f"{item}: {error}") from None
        initialize_pack(pack, root)
        task.controls_markdown = controls_markdown(task, outcomes)
        add_task(pack, task)
        write_study_controls(pack, candidate_root, task, outcomes)
        store.put_candidate(
            run_id, candidate_id, record["game_id"], CandidateStatus.PUBLISHED, record["payload"]
        )
        typer.echo(json.dumps({"published": f"minecraft/history/{task.task_id}", "candidate": candidate_id}))
