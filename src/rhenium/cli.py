from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
from collections.abc import MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import qrcode
import typer
import uvicorn

from .api import create_app
from .cli_agent_runner import AGENT_PROVIDERS, CLI_AGENT_PROVIDERS
from .config import Settings
from .hub import BenchmarkHub

app = typer.Typer(
    no_args_is_help=True,
    help="Run game-engineering benchmarks discovered by the Rhenium Hub.",
)
auth_app = typer.Typer(no_args_is_help=True, help="Manage licensed content provider sessions.")
runtime_app = typer.Typer(no_args_is_help=True, help="Prepare and manage licensed runtimes.")
evaluation_host_app = typer.Typer(no_args_is_help=True, help="Inspect disposable evaluation host providers.")
app.add_typer(auth_app, name="auth")
app.add_typer(runtime_app, name="runtime")
app.add_typer(evaluation_host_app, name="evaluation-host")


def _hub() -> BenchmarkHub:
    return BenchmarkHub(Settings.load())


def _print(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _progress(value: int, phase: str) -> None:
    typer.echo(f"[{value:3d}%] {phase}", err=True)


def _load_dotenv(path: Path, environment: MutableMapping[str, str] = os.environ) -> None:
    """Export simple KEY=value lines from .env without overriding variables already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            words = shlex.split(line, comments=True)
        except ValueError:
            continue
        if words[:1] == ["export"]:
            words = words[1:]
        if len(words) != 1 or "=" not in words[0]:
            continue
        name, value = words[0].split("=", 1)
        if name.isidentifier():
            environment.setdefault(name, value)


@evaluation_host_app.command("list")
def evaluation_host_list() -> None:
    """List installed disposable evaluation host providers."""
    _print({"providers": _hub().list_evaluation_hosts()})


@evaluation_host_app.command("doctor")
def evaluation_host_doctor(provider_id: str) -> None:
    """Run a provider-owned read-only readiness check."""
    try:
        _print(_hub().evaluation_host_doctor(provider_id))
    except KeyError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error


def _qr(value: str) -> str:
    code = qrcode.QRCode(border=1)
    code.add_data(value)
    code.make(fit=True)
    matrix = code.get_matrix()
    lines: list[str] = []
    for row in range(0, len(matrix), 2):
        upper = matrix[row]
        lower = matrix[row + 1] if row + 1 < len(matrix) else [False] * len(upper)
        lines.append(
            "".join(
                "█" if top and bottom else "▀" if top else "▄" if bottom else " "
                for top, bottom in zip(upper, lower, strict=True)
            )
        )
    return "\n".join(lines)


@auth_app.command("list")
def auth_list() -> None:
    """List installed auth providers and configured sessions."""
    _print({"providers": _hub().auth.provider_list()})


@auth_app.command("status")
def auth_status() -> None:
    """List configured provider sessions without exposing secrets."""
    _print({"sessions": _hub().auth.list_sessions()})


@auth_app.command("login")
def auth_login(
    provider: str,
    account: Annotated[str, typer.Option("--account")] = "default",
) -> None:
    """Log in interactively and store a reusable provider session."""

    shown = 0

    def challenge(item: object) -> None:
        # A provider replaces an expired or completed challenge with a new one, and the
        # terminal keeps every code that scrolled past, so say which one to scan.
        nonlocal shown
        uri = str(getattr(item, "uri", ""))
        message = str(getattr(item, "message", "Scan this QR code"))
        shown += 1
        if shown > 1:
            typer.echo(
                "Scan the newest code below; every code further up has expired.",
                err=True,
            )
        typer.echo(message, err=True)
        typer.echo(_qr(uri), err=True)

    try:
        _print(_hub().auth.login(provider, account, challenge=challenge, progress=_progress))
    except (OSError, RuntimeError, ValueError) as error:
        # A failed sign-in is an ordinary outcome here, not a defect to dump a traceback for:
        # a code can expire before it is scanned, and the provider owns the reason text.
        _print({"status": "failed", "providerId": provider, "accountAlias": account,
                "reason": str(error)})
        typer.echo(f"Sign-in did not complete. Run 'rhenium auth login {provider}' again.", err=True)
        raise typer.Exit(2) from error


@auth_app.command("logout")
def auth_logout(
    provider: str,
    account: Annotated[str, typer.Option("--account")] = "default",
) -> None:
    """Delete one local provider session; remote Steam devices are not revoked."""
    _print(_hub().auth.logout(provider, account))


@runtime_app.command("list")
def runtime_list(game: Annotated[str | None, typer.Option("--game")] = None) -> None:
    """List managed runtime specifications and local artifact state."""
    _print({"runtimes": _hub().runtime_manager.list(game)})


@runtime_app.command("doctor")
def runtime_doctor(runtime_key: str) -> None:
    """Check host prerequisites without installing system packages."""
    _print(_hub().runtime_manager.doctor(runtime_key))


@runtime_app.command("prepare")
def runtime_prepare(
    runtime_key: str,
    account: Annotated[str, typer.Option("--account")] = "default",
) -> None:
    """Explicitly download, build, and verify a licensed runtime."""
    from .core.runtime import RuntimeActionRequired

    try:
        result = _hub().runtime_manager.prepare(runtime_key, account_alias=account, progress=_progress)
    except RuntimeActionRequired as error:
        _print(
            {
                "status": "action_required",
                "kind": error.kind,
                "message": str(error),
                "details": error.details,
            }
        )
        raise typer.Exit(2) from error
    _print(result)


@runtime_app.command("verify")
def runtime_verify(runtime_key: str) -> None:
    """Verify an existing runtime without rebuilding it."""
    _print(_hub().runtime_manager.verify(runtime_key))


@runtime_app.command("prune")
def runtime_prune(runtime_key: str, yes: Annotated[bool, typer.Option("--yes")] = False) -> None:
    """Delete a downloaded source cache and its evaluator artifact."""
    if not yes and not typer.confirm(f"Delete restricted runtime {runtime_key}?"):
        raise typer.Abort()
    _print(_hub().runtime_manager.prune(runtime_key))


@app.command("games")
def list_games() -> None:
    """List installed game plugins."""
    _print({"games": _hub().list_games()})


@app.command("packs")
def list_packs(game: Annotated[str | None, typer.Option("--game")] = None) -> None:
    """List discovered benchmark packs."""
    _print({"packs": _hub().list_packs(game_id=game)})


@app.command("tasks")
def list_tasks(
    language: Annotated[str, typer.Option("--language", "-l")] = "en",
    game: Annotated[str | None, typer.Option("--game")] = None,
    pack: Annotated[str | None, typer.Option("--pack")] = None,
) -> None:
    """List tasks across all discovered packs."""
    _print({"tasks": _hub().list_tasks(language=language, game_id=game, pack_id=pack)})


@app.command()
def run(
    task_key: str,
    submission_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    profile: Annotated[str, typer.Option("--profile")] = "full",
    security_mode: Annotated[str, typer.Option("--security-mode")] = "honest",
    host_provider: Annotated[str | None, typer.Option("--host-provider")] = None,
    host_image: Annotated[str | None, typer.Option("--host-image")] = None,
) -> None:
    """Evaluate one implementation by canonical game/pack/task key."""
    try:
        result = _hub().evaluate_task(
            task_key,
            submission_dir,
            profile=profile,
            security_mode=security_mode,
            host_provider=host_provider,
            host_image=host_image,
        )
    except (RuntimeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    _print(result)
    raise typer.Exit(0 if result["status"] == "passed" else 1)


@app.command("register-attempt", hidden=True)
def register_attempt(
    task_key: str,
    attempt_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    mode: str = "strict",
) -> None:
    """Bind an isolated directory to a canonical task without exposing its key."""
    _print(_hub().register_attempt(task_key, attempt_dir, mode))


@app.command("prepare-attempt", hidden=True)
def prepare_attempt(
    task_key: str,
    attempt_dir: Path,
    score_command: Annotated[Path, typer.Option("--score-command")],
    mode: Annotated[str, typer.Option("--mode")] = "strict",
) -> None:
    """Materialize and anonymously register a plugin-owned public exam bundle."""
    try:
        result = _hub().prepare_attempt(task_key, attempt_dir, mode, score_command)
    except KeyError as error:
        raise typer.BadParameter(f"unknown task key: {task_key}") from error
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    _print(result)


@app.command("run-attempt")
def run_attempt(
    submission_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    profile: Annotated[str, typer.Option("--profile")] = "full",
    security_mode: Annotated[str, typer.Option("--security-mode")] = "honest",
    host_provider: Annotated[str | None, typer.Option("--host-provider")] = None,
    host_image: Annotated[str | None, typer.Option("--host-image")] = None,
) -> None:
    """Evaluate a registered anonymous attempt."""
    try:
        result = _hub().evaluate_attempt(
            submission_dir,
            profile=profile,
            security_mode=security_mode,
            host_provider=host_provider,
            host_image=host_image,
        )
    except (RuntimeError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    _print(result)
    raise typer.Exit(0 if result["status"] == "passed" else 1)


@app.command("run-model")
def run_model(
    task_key: str,
    profile: Annotated[str, typer.Option("--profile")] = "full",
    security_mode: Annotated[str, typer.Option("--security-mode")] = "honest",
    host_provider: Annotated[str | None, typer.Option("--host-provider")] = None,
    host_image: Annotated[str | None, typer.Option("--host-image")] = None,
) -> None:
    """Ask the configured model to implement one canonical task."""
    result = _hub().evaluate_model(
        task_key,
        profile=profile,
        security_mode=security_mode,
        host_provider=host_provider,
        host_image=host_image,
    )
    _print(result)
    raise typer.Exit(0 if result["evaluation"]["status"] == "passed" else 1)


@app.command("solve-attempt")
def solve_attempt(
    submission_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    profile: Annotated[str, typer.Option("--profile")] = "full",
    security_mode: Annotated[str, typer.Option("--security-mode")] = "honest",
    host_provider: Annotated[str | None, typer.Option("--host-provider")] = None,
    host_image: Annotated[str | None, typer.Option("--host-image")] = None,
) -> None:
    """Solve a registered anonymous attempt and evaluate it once."""

    def progress(value: int, phase: str) -> None:
        typer.echo(f"[{value:3d}%] {phase}", err=True)

    result = _hub().solve_attempt(
        submission_dir,
        profile=profile,
        progress=progress,
        security_mode=security_mode,
        host_provider=host_provider,
        host_image=host_image,
    )
    _print(result)
    raise typer.Exit(0 if result["evaluation"]["status"] == "passed" else 1)


@app.command("benchmark")
def benchmark(
    selector: Annotated[str, typer.Argument(help="A game, game/pack, or game/pack/task.")],
    provider: Annotated[
        str, typer.Option("--provider", help="api (mini-swe-agent), codex, or claude.")
    ] = "api",
    attempts_dir: Annotated[
        Path | None,
        typer.Option("--attempts-dir", file_okay=False, help="Parent of the attempt directories."),
    ] = None,
    profile: Annotated[str, typer.Option("--profile")] = "full",
    security_mode: Annotated[str, typer.Option("--security-mode")] = "honest",
    host_provider: Annotated[str | None, typer.Option("--host-provider")] = None,
    host_image: Annotated[str | None, typer.Option("--host-image")] = None,
) -> None:
    """Let an agent solve every matching task in its own anonymous attempt; score each once."""
    if provider not in AGENT_PROVIDERS:
        raise typer.BadParameter("must be api, codex, or claude", param_hint="--provider")
    _load_dotenv(Path(os.environ.get("RHENIUM_ROOT", Path.cwd())) / ".env")
    if provider in CLI_AGENT_PROVIDERS and shutil.which(provider) is None:
        typer.echo(f"{provider} is not installed or is not on PATH", err=True)
        raise typer.Exit(2)
    if provider == "api":
        os.environ.setdefault("RHENIUM_MODEL_ENABLED", "true")
    hub = _hub()
    try:
        task_keys = hub.select_task_keys(selector)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    attempts_root = (attempts_dir or Path.home() / "Projects" / "rhenium-attempts").expanduser()
    attempts_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for index, task_key in enumerate(task_keys, start=1):
        typer.echo(f"== [{index}/{len(task_keys)}] {task_key} ({provider})", err=True)
        attempt = attempts_root / f"attempt-{secrets.token_hex(6)}-{datetime.now():%Y%m%d-%H%M%S}"
        entry: dict[str, Any] = {"taskKey": task_key, "attempt": str(attempt)}
        try:
            hub.prepare_attempt(task_key, attempt, "strict", None)
            result = hub.run_agent_attempt(
                attempt,
                provider,
                profile,
                _progress,
                security_mode=security_mode,
                host_provider=host_provider,
                host_image=host_image,
            )
        except (OSError, RuntimeError, ValueError) as error:
            entry.update(status="error", error=str(error))
        else:
            evaluation = result["evaluation"]
            entry.update(
                status=evaluation["status"],
                score=evaluation["score"],
                runId=evaluation["id"],
                agentExit=result["exitStatus"],
            )
        typer.echo(f"   {entry['status']}  score={entry.get('score', '-')}", err=True)
        results.append(entry)

    passed = sum(entry["status"] == "passed" for entry in results)
    _print(
        {
            "selector": selector,
            "provider": provider,
            "passed": passed,
            "total": len(results),
            "tasks": results,
        }
    )
    raise typer.Exit(0 if passed == len(results) else 1)


@app.command()
def report(
    game: Annotated[str | None, typer.Option("--game")] = None,
    pack: Annotated[str | None, typer.Option("--pack")] = None,
) -> None:
    """Print aggregate results, optionally filtered by game and pack."""
    _print(_hub().report(game_id=game, pack_id=pack))


@app.command()
def web(
    host: str = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 4317,
    reload: bool = False,
) -> None:
    """Start the local API and single-page benchmark UI."""
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise typer.BadParameter("the Hub UI is local-only; choose localhost, 127.0.0.1, or ::1")
    uvicorn.run(create_app(management_enabled=True), host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
