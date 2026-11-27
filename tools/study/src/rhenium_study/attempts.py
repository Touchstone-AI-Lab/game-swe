"""One scheduled attempt: prepare, generate once, freeze, evaluate, classify."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import time
from collections.abc import Collection
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import classify, controls
from .clausemap import ClauseMap
from .e1config import ModelCondition, StudyConfig
from .exclusions import refuse_excluded
from .hubs import interprocess_lock, open_hub, starter_lock
from .inventory import task_for
from .observations import case_table, observed_cases
from .paths import StudyPaths
from .usage import token_usage

# Outcome of a generated attempt whose evaluation runs on another host; it enters no
# result until `e1 import-evaluations` scores it.
PENDING = "pending-evaluation"
# mini-swe-agent exit status written by the agent runner's repeated-action guard.
REPEATED_ACTION_EXIT = "RepeatedActionLoop"
# Plugins whose agent system prompt offers a public, answer-free source check.
_PUBLIC_CHECK_PLUGINS = ("dst", "palworld")
# Container bookkeeping is instant on an idle daemon but can stall for minutes on a
# shared host that is flushing image layers.
_DOCKER_TIMEOUT = 300


@dataclass(frozen=True)
class Scheduled:
    attempt_id: str
    model: str
    task: str
    repeat: int
    order: int


def schedule(config: StudyConfig) -> list[Scheduled]:
    """Every (model, task, repeat), shuffled once with the frozen seed."""
    cells = [
        (model.id, task, repeat)
        for repeat in range(1, config.repeats + 1)
        for task in config.tasks
        for model in config.models
    ]
    random.Random(config.schedule_seed).shuffle(cells)
    return [
        Scheduled(f"{model}--{task.rsplit('/', 1)[1]}--r{repeat}", model, task, repeat, order)
        for order, (model, task, repeat) in enumerate(cells, start=1)
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


GENERATION_STARTS = 3
VOID_BACKOFF_SECONDS = 120
MODEL_RETRY_ATTEMPTS = 30
EVALUATION_VOIDS = 3
EVALUATION_VOID_BACKOFF_SECONDS = 300


class _GenerationSetupError(RuntimeError):
    """The isolated generation environment could not be assembled."""


def _docker(
    arguments: list[str], *, timeout: float, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments], check=False, capture_output=True, text=True, timeout=timeout, env=env
    )


def _setup(arguments: list[str], problem: str) -> None:
    """Run one step that assembles the generation environment; any failure is a setup failure."""
    try:
        completed = _docker(arguments, timeout=300)
    except subprocess.TimeoutExpired:
        raise _GenerationSetupError(f"{problem} (docker did not answer)") from None
    if completed.returncode:
        # Docker ends a failed run with a usage hint; the error is the line before it.
        lines = [
            line
            for line in completed.stderr.splitlines()
            if line.strip() and not line.startswith("Run 'docker")
        ]
        raise _GenerationSetupError(f"{problem}: {(lines or ['no error output'])[-1][-300:]}")


def _cleanup(arguments: list[str]) -> list[str]:
    """Remove an attempt's own container or network; a stalled daemon must not void a
    finished generation, so a failure is returned for the record instead of raised."""
    try:
        completed = _docker(arguments, timeout=_DOCKER_TIMEOUT)
    except subprocess.TimeoutExpired:
        return [f"docker {' '.join(arguments)}: timed out after {_DOCKER_TIMEOUT} s"]
    if completed.returncode != 0 and not any(gone in completed.stderr for gone in ("No such", "not found")):
        return [f"docker {' '.join(arguments)}: {completed.stderr.strip()[-200:]}"]
    return []


def remove_leftovers(attempt_id: str) -> list[str]:
    """Remove the containers and networks an earlier start of the same attempt left behind.

    They are found by the attempt label, not by name: a congested daemon can still be
    removing a failed start's proxy when the next start begins, which is also why every
    start takes fresh names.
    """
    label = f"label=io.rhenium.study.attempt={attempt_id}"
    failures: list[str] = []
    for kind, listing in (
        ("container", ["ps", "--all", "--quiet"]),
        ("network", ["network", "ls", "--quiet"]),
    ):
        try:
            listed = _docker([*listing, "--filter", label], timeout=_DOCKER_TIMEOUT)
        except subprocess.TimeoutExpired:
            failures.append(f"listing leftover {kind}s timed out after {_DOCKER_TIMEOUT} s")
            continue
        found = listed.stdout.split()
        if found:
            failures += _cleanup(
                ["rm", "--force", *found] if kind == "container" else ["network", "rm", *found]
            )
    return failures


def build_agent_image(tag: str) -> str:
    """Build the pinned agent image from the packaged recipe and return its image ID."""
    recipe = files("rhenium_study").joinpath("assets/agent.Dockerfile").read_text(encoding="utf-8")
    built = subprocess.run(
        ["docker", "build", "--tag", tag, "-"],
        input=recipe,
        check=False,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if built.returncode != 0:
        raise RuntimeError("agent image build failed: " + built.stderr[-2000:])
    return _docker(["image", "inspect", tag, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT).stdout.strip()


def public_check_python_path(game: str) -> str:
    """Module path for the agent's shell commands, empty for games without a public check.

    The DST and Palworld prompts tell the agent to run `python -m rhenium_<game>.public_check`;
    the agent's shell does not inherit the runner's environment, so that command only works
    when its module path is passed on explicitly. Other games' shells stay unchanged.
    """
    if game not in _PUBLIC_CHECK_PLUGINS:
        return ""
    return f"/opt/rhenium/plugins/{game}:/opt/rhenium/src:/opt/rhenium/site-packages"


def _generate(
    paths: StudyPaths,
    config: StudyConfig,
    model: ModelCondition,
    workspace: Path,
    out: Path,
    name: str,
    game: str = "",
) -> dict[str, Any]:
    """The single generation: an isolated container whose only exit is the model endpoint."""
    assets = Path(str(files("rhenium_study").joinpath("assets")))
    site = paths.project_root / ".devenv/state/venv/lib/python3.12/site-packages"
    # The DST and Palworld system prompts name `python -m rhenium_<game>.public_check`;
    # keep those runnable inside the container.
    public_checks = {name: paths.project_root / f"plugins/{name}/src" for name in _PUBLIC_CHECK_PLUGINS}
    # The proxy's container name is its DNS name inside the network, and a DNS label
    # holds at most 63 characters: derive short names instead of embedding the attempt id.
    start_token = os.urandom(4).hex()
    network, proxy, agent = container_names(name, start_token)
    label = f"io.rhenium.study.attempt={name}"
    image = _docker(
        ["image", "inspect", config.agent_image, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
    ).stdout.strip()
    if not image:
        raise RuntimeError(f"agent image {config.agent_image} is not built")
    condition = {
        "litellm_model": model.litellm_model,
        "base_url": model.base_url,
        "extra_body": model.extra_body,
        "prompt_caching": model.prompt_caching,
        "max_output_tokens": model.max_output_tokens,
        "thinking": model.thinking,
        "output_config": model.output_config,
        "omit_params": list(model.omit_params),
        "stream_responses": model.stream_responses,
        **config.budget.model_dump(),
    }
    plugin_paths = [f"/opt/rhenium/plugins/{name}" for name in public_checks]
    python_path = ":".join(["/opt/rhenium/src", *plugin_paths, "/opt/rhenium/site-packages"])
    command_python_path = public_check_python_path(game)
    started = _now()
    exit_code: int | None = None
    failure: str | None = None
    setup_failed = False
    cleanup_failures: list[str] = []
    try:
        cleanup_failures += remove_leftovers(name)
        # Docker's default address pools hold about thirty networks; every attempt brings
        # its own /28 so the number of parallel lanes is not bounded by them.
        for salt in range(8):
            try:
                _setup(
                    [
                        "network",
                        "create",
                        "--internal",
                        "--label",
                        label,
                        "--subnet",
                        _subnet(f"{name}#{start_token}", salt),
                        network,
                    ],
                    "the isolated network could not be created",
                )
                break
            except _GenerationSetupError:
                if salt == 7:
                    raise
        _setup(
            [
                "run",
                "--detach",
                "--rm",
                "--name",
                proxy,
                "--label",
                label,
                "--network",
                network,
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--read-only",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--mount",
                f"type=bind,source={assets / 'egress_proxy.py'},target=/opt/study/egress_proxy.py,readonly",
                "--mount",
                f"type=bind,source={out},target=/out",
                image,
                "python",
                "/opt/study/egress_proxy.py",
                model.endpoint_host,
                "/out/egress.jsonl",
            ],
            "the egress proxy could not be started",
        )
        _setup(
            ["network", "connect", "bridge", proxy],
            "the egress proxy could not be connected to the endpoint network",
        )
        environment = {
            **os.environ,
            "RHENIUM_MODEL_API_KEY": model.api_key_file.read_text().strip(),
            "RHENIUM_STUDY_CONDITION": json.dumps(condition),
        }
        completed = _docker(
            [
                "run",
                "--rm",
                "--init",
                "--name",
                agent,
                "--label",
                label,
                "--network",
                network,
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,exec,nosuid,size=4g",
                "--pids-limit=512",
                "--memory=8g",
                "--cpus=4",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--mount",
                f"type=bind,source={paths.project_root / 'src'},target=/opt/rhenium/src,readonly",
                *(
                    argument
                    for name, source in public_checks.items()
                    for argument in (
                        "--mount",
                        f"type=bind,source={source},target=/opt/rhenium/plugins/{name},readonly",
                    )
                ),
                "--mount",
                f"type=bind,source={site},target=/opt/rhenium/site-packages,readonly",
                "--mount",
                f"type=bind,source={assets / 'agent_runner.py'},target=/opt/study/agent_runner.py,readonly",
                "--mount",
                f"type=bind,source={out / 'prompt.json'},target=/opt/study/prompt.json,readonly",
                "--mount",
                f"type=bind,source={workspace},target=/work/attempt",
                "--mount",
                f"type=bind,source={out},target=/opt/study/out",
                "--workdir",
                "/work/attempt",
                "--env",
                "RHENIUM_MODEL_API_KEY",
                "--env",
                "RHENIUM_STUDY_CONDITION",
                "--env",
                f"RHENIUM_STUDY_COMMAND_PYTHONPATH={command_python_path}",
                "--env",
                f"HTTPS_PROXY=http://{proxy}:8888",
                "--env",
                f"HTTP_PROXY=http://{proxy}:8888",
                "--env",
                f"https_proxy=http://{proxy}:8888",
                "--env",
                f"http_proxy=http://{proxy}:8888",
                "--env",
                "HOME=/tmp",
                "--env",
                "MSWEA_GLOBAL_CONFIG_DIR=/tmp/mswea",
                "--env",
                "MSWEA_SILENT_STARTUP=1",
                # A provider throttling burst must not end a generation after ten tries
                # (about five minutes); thirty tries wait out roughly twenty-five.
                "--env",
                f"MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT={MODEL_RETRY_ATTEMPTS}",
                "--env",
                "LITELLM_LOCAL_MODEL_COST_MAP=True",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--env",
                f"PYTHONPATH={python_path}",
                image,
                "python",
                "/opt/study/agent_runner.py",
                "/work/attempt",
                "/opt/study/prompt.json",
                "/opt/study/out",
            ],
            timeout=config.budget.wall_time_limit_seconds + 1800,
            env=environment,
        )
        (out / "agent.log").write_text((completed.stdout + completed.stderr)[-400_000:], encoding="utf-8")
        exit_code = completed.returncode
    except _GenerationSetupError as error:
        failure, setup_failed = str(error), True
    except subprocess.TimeoutExpired as expired:
        cleanup_failures += _cleanup(["rm", "--force", agent])
        failure = "generation exceeded the container wall-clock limit"
        partial = "".join(
            part.decode("utf-8", "replace") if isinstance(part, bytes) else part or ""
            for part in (expired.stdout, expired.stderr)
        )
        (out / "agent.log").write_text(partial[-400_000:], encoding="utf-8")
    finally:
        cleanup_failures += _cleanup(["rm", "--force", proxy])
        cleanup_failures += _cleanup(["network", "rm", network])
    return {
        "cleanupFailures": cleanup_failures,
        "agentImageId": image,
        "startedAt": started,
        "finishedAt": _now(),
        "containerExit": exit_code,
        "containerFailure": failure,
        "setupFailed": setup_failed,
    }


def container_names(attempt_id: str, start_token: str) -> tuple[str, str, str]:
    """Network, proxy and agent names for one generation start, each a valid DNS label."""
    suffix = hashlib.sha256(f"{attempt_id}#{start_token}".encode()).hexdigest()[:16]
    return f"study-net-{suffix}", f"study-proxy-{suffix}", f"study-agent-{suffix}"


def _subnet(attempt_id: str, salt: int) -> str:
    """A /28 inside 10.96.0.0/12, chosen by hash; a collision is retried with another salt."""
    digest = hashlib.sha256(f"{attempt_id}#{salt}".encode()).digest()
    return f"10.{96 + digest[0] % 16}.{digest[1]}.{digest[2] & 0xF0}/28"


def endpoint_reached(agent_out: Path) -> bool:
    """Whether the egress proxy ever let a connection through to the model endpoint."""
    log = agent_out / "egress.jsonl"
    if not log.is_file():
        return False
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("event") == "allowed":
            return True
    return False


def _read_model_report(agent_out: Path) -> dict[str, Any]:
    path = agent_out / "model.json"
    loaded = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return loaded if isinstance(loaded, dict) else {}


_STEP = re.compile(r"mini-swe-agent step (\d+)")


def model_answered(agent_out: Path) -> bool:
    """Whether a model request ever returned: the agent only begins step 2 after step 1's answer."""
    log = agent_out / "agent.log"
    if not log.is_file():
        return False
    text = log.read_text(encoding="utf-8", errors="replace")
    return any(int(step) >= 2 for step in _STEP.findall(text))


def never_started(generation: dict[str, Any], model_report: dict[str, Any], agent_out: Path) -> bool:
    """A generation start that produced no generation: the model never answered.

    The endpoint may have been reached and still refused every request (a rate limit or an
    unavailable model); nothing was sampled, so starting again does not give the model a
    second try.
    """
    if generation.get("setupFailed"):
        return True
    return bool(model_report.get("error")) and not (endpoint_reached(agent_out) and model_answered(agent_out))


# Provider errors that say the endpoint did not serve the request. They end a generation for
# reasons independent of the model's work, so the generation is restarted from the starter.
PROVIDER_UNAVAILABLE = frozenset(
    {
        "RateLimitError",
        "ServiceUnavailableError",
        "APIConnectionError",
        "InternalServerError",
        "BadGatewayError",
        "Timeout",
    }
)


def provider_interrupted(model_report: dict[str, Any], agent_out: Path) -> bool:
    """Whether the model answered and the provider then stopped serving the generation."""
    return str(model_report.get("error") or "") in PROVIDER_UNAVAILABLE and model_answered(agent_out)


_CONTEXT_MARKERS = ("context window", "context length", "maximum context", "context_length", "上下文窗口")


def context_exhausted(model_report: dict[str, Any]) -> bool:
    """Whether the generation ended because the conversation outgrew the model's context.

    The frozen scaffold keeps the whole conversation, so this is how its budget runs
    out for that model: the tree it left behind is a finished candidate and is scored.
    """
    if not model_report.get("error"):
        return False
    text = f"{model_report.get('error')} {model_report.get('message')}".casefold()
    return "contextwindowexceeded" in text or any(marker in text for marker in _CONTEXT_MARKERS)


# An evaluator whose container was never created observed nothing about the submission.
_EVALUATOR_NOT_STARTED = (
    re.compile(r"Command '\[[^\]]*docker', 'create',.*?\]' timed out after \d+ seconds", re.S),
    re.compile(r"could not create the isolated"),
)
# RimWorld verifies its prepared runtime against the current pack before it creates any
# container, and reports a mismatch only as an evidence-integrity failure; the plugin's
# private failure record for that evaluation names the cause exactly.
_RIMWORLD_EVALUATIONS = ("packs", "rimworld", "core", "evaluations")
_RIMWORLD_RUNTIME_UNVERIFIED = "RuntimeError: runtime artifact verification failed"


def _rimworld_runtime_unverified(result: dict[str, Any], paths: StudyPaths) -> bool:
    evaluation = result.get("evaluationId")
    if not isinstance(evaluation, str) or not re.fullmatch(r"evaluation-[0-9a-f]{24}", evaluation):
        return False
    record = paths.state_dir.joinpath(*_RIMWORLD_EVALUATIONS, evaluation, "failure.private.txt")
    if record.is_symlink() or not record.is_file():
        return False
    return record.read_text(encoding="utf-8", errors="replace").strip() == _RIMWORLD_RUNTIME_UNVERIFIED


def evaluator_never_started(execution: dict[str, Any], paths: StudyPaths) -> bool:
    """Whether a non-valid execution failed before its evaluator container existed.

    The evidence is the evaluator's own record: a ``docker create`` that timed out or a
    plugin reporting that its isolated verifier could not be created, in the Hub run's
    runtime log or in the result, or RimWorld's private record that its prepared runtime
    failed verification. Nothing about the submission was observed, so the execution is
    voided rather than counted.
    """
    if execution.get("outcome") not in {"unattributed", "invalid"}:
        return False
    raw = execution.get("result")
    result: dict[str, Any] = raw if isinstance(raw, dict) else {}
    if _rimworld_runtime_unverified(result, paths):
        return True
    texts = [str(execution.get("evaluatorError") or "")]
    runtime = result.get("runtime")
    if isinstance(runtime, dict):
        texts.append(str(runtime.get("message") or ""))
    for check in result.get("checks") or []:
        if isinstance(check, dict):
            texts.append(str(check.get("message") or ""))
    run_id = execution.get("runId")
    if isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        log = paths.state_dir / "runs" / run_id / "runtime.log"
        if log.is_file():
            texts.append(log.read_text(encoding="utf-8", errors="replace"))
    text = "\n".join(texts)
    return any(pattern.search(text) for pattern in _EVALUATOR_NOT_STARTED)


def _score(
    paths: StudyPaths,
    task: Any,
    clause_map: ClauseMap,
    submission: Path,
    submission_digest: str,
    root: Path,
    *,
    skip: bool = False,
    counted: list[dict[str, Any]] | None = None,
    voided: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate a frozen submission: one execution, plus one retry only if it was not valid.

    A generation ended by a provider, scaffold or harness error is not a finished
    candidate; with ``skip`` its partial tree is not scored. An execution whose evaluator
    container was never created is voided, kept under ``executions/voided/`` and run
    again after a pause, at most ``EVALUATION_VOIDS`` times; it does not use up the retry.
    ``counted`` and ``voided`` resume an attempt that was already scored.
    """
    executions: list[dict[str, Any]] = list(counted or [])
    voided_starts: list[dict[str, Any]] = list(voided or [])
    index = max((int(item["index"]) for item in [*executions, *voided_starts]), default=0)
    while not skip and len(executions) < 2:
        if executions and executions[-1]["outcome"] in {"resolved", "failed"}:
            break  # the first valid result is final; only invalid/unattributed gets the one retry
        index += 1
        started = _now()
        try:
            run = controls.evaluate(task, submission, paths)
            result, error = run["result"], None
        except Exception as failure:  # noqa: BLE001 - an evaluator that cannot run is a recorded outcome
            run, result, error = {}, {}, f"{type(failure).__name__}: {failure}"
        execution = {
            "index": index,
            "startedAt": started,
            "finishedAt": _now(),
            "runId": run.get("id"),
            "logPath": run.get("logPath") or run.get("log_path"),
            "submissionDigest": submission_digest,
            "runtimeIdentity": controls.runtime_identity(task, paths),
            "result": result,
            "evaluatorError": error,
        }
        table = case_table(result, clause_map.case_ids())
        outcome, reason = classify.classify_execution(execution, table)
        execution.update(
            {"cases": table, "reached": sorted(observed_cases(result)), "outcome": outcome, "reason": reason}
        )
        if len(voided_starts) < EVALUATION_VOIDS and evaluator_never_started(execution, paths):
            _write(root / "executions" / "voided" / f"{index}.json", execution)
            voided_starts.append(_void_summary(execution))
            time.sleep(EVALUATION_VOID_BACKOFF_SECONDS)
            continue
        _write(root / "executions" / f"{index}.json", execution)
        executions.append(execution)
    summary = [
        {k: e[k] for k in ("index", "outcome", "reason", "runId", "runtimeIdentity")} for e in executions
    ]
    return {"executions": executions, "summary": summary, "voided": voided_starts}


def _void_summary(execution: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": execution["index"],
        "runId": execution.get("runId"),
        "startedAt": execution.get("startedAt"),
        "outcome": execution.get("outcome"),
        "reason": "the evaluator container was never created; nothing was observed",
    }


def reevaluate(
    paths: StudyPaths, config: StudyConfig, attempt_id: str, *, excluded: Collection[str]
) -> dict[str, Any] | None:
    """Void recorded executions whose evaluator never started, and evaluate again.

    Only the frozen submission is evaluated; nothing is generated again. Executions with
    any observation keep counting, so the retry rule is unchanged. Returns ``None`` when
    the attempt has nothing to void. An attempt of an excluded task is refused.
    """
    root = paths.data_root / "e1" / config.study_id / "attempts" / attempt_id
    final = root / "attempt.json"
    record = json.loads(final.read_text(encoding="utf-8"))
    refuse_excluded(record["task"], attempt_id, excluded)
    if record.get("outcome") not in {"unattributed", "invalid"} or not record.get("executions"):
        return None
    submission = root / "submission"
    if controls.tree_digest(submission) != record["submissionDigest"]:
        raise ValueError("the frozen submission no longer matches its recorded digest")
    loaded = [
        json.loads((root / "executions" / f"{item['index']}.json").read_text(encoding="utf-8"))
        for item in record["executions"]
    ]
    voided = list(record.get("voidedExecutions") or [])
    counted: list[dict[str, Any]] = []
    for execution in loaded:
        if len(voided) < EVALUATION_VOIDS and evaluator_never_started(execution, paths):
            source = root / "executions" / f"{execution['index']}.json"
            target = root / "executions" / "voided" / source.name
            target.parent.mkdir(exist_ok=True)
            source.replace(target)
            voided.append(_void_summary(execution))
        else:
            counted.append(execution)
    if len(counted) == len(loaded):
        return None
    task = task_for(record["task"])
    clause_map = ClauseMap.load(paths.study_controls(task.pack_dir, task.task) / "clause-map.json")
    scored = _score(
        paths, task, clause_map, submission, record["submissionDigest"], root, counted=counted, voided=voided
    )
    record.update(
        {
            "executions": scored["summary"],
            **_verdict(clause_map, scored["executions"][-1]),
            "voidedExecutions": scored["voided"],
            "reevaluatedAt": _now(),
        }
    )
    _write(final, record)
    return record


def _verdict(clause_map: ClauseMap, selected: dict[str, Any]) -> dict[str, Any]:
    """The outcome fields of an attempt record, read from its selected execution."""
    table = selected["cases"]
    # The study's obligation sets are the audited ones; the native verdict is kept beside them.
    target = classify.set_outcome(clause_map.case_ids("target", audited=True), table)
    preserved = classify.set_outcome(clause_map.case_ids("preserved", audited=True), table)
    return {
        "selectedExecution": selected["index"],
        "outcome": selected["outcome"],
        "auditedOutcome": classify.audited_outcome(
            selected["outcome"], clause_map.case_ids(audited=True), table
        ),
        "overConstrainedCases": [case.id for case in clause_map.cases if case.over_constrained],
        "outcomeReason": selected["reason"],
        "score": selected["result"].get("score"),
        "complete": selected["result"].get("complete"),
        "passed": selected["result"].get("passed"),
        "cases": table,
        "targetOutcome": target,
        "preservedOutcome": preserved,
        "jointOutcome": classify.joint_outcome(target, preserved),
    }


def rescore(
    paths: StudyPaths, config: StudyConfig, attempt_id: str, *, excluded: Collection[str]
) -> dict[str, Any]:
    """Score the frozen submission of an attempt that was recorded without an evaluation.

    Only for a generation that ended by exhausting the model's context and was recorded
    before that was recognized as a termination. Nothing is generated again. An attempt
    of an excluded task is refused.
    """
    root = paths.data_root / "e1" / config.study_id / "attempts" / attempt_id
    final = root / "attempt.json"
    record = json.loads(final.read_text(encoding="utf-8"))
    refuse_excluded(record["task"], attempt_id, excluded)
    generation = record.get("generation") or {}
    if record.get("executions") or not context_exhausted(generation):
        raise ValueError("only an unscored attempt that ended by context exhaustion can be rescored")
    submission = root / "submission"
    if controls.tree_digest(submission) != record["submissionDigest"]:
        raise ValueError("the frozen submission no longer matches its recorded digest")
    task = task_for(record["task"])
    clause_map = ClauseMap.load(paths.study_controls(task.pack_dir, task.task) / "clause-map.json")
    scored = _score(paths, task, clause_map, submission, record["submissionDigest"], root)
    record.update(
        {
            "generation": {**generation, "terminationReason": "context-window-exhausted"},
            "executions": scored["summary"],
            **_verdict(clause_map, scored["executions"][-1]),
            "voidedExecutions": scored["voided"],
            "rescoredAt": _now(),
        }
    )
    _write(final, record)
    return record


_HARNESS_PATHS = ("src", "plugins", "tools/study")


def harness_revision(paths: StudyPaths) -> dict[str, Any]:
    """The commit of the code that generates and scores, and whether it has local edits."""

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(paths.project_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()[-200:]}")
        return completed.stdout.strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--", *_HARNESS_PATHS)),
    }


def _restore_starter(paths: StudyPaths, item: Scheduled, workspace: Path, starter_digest: str) -> None:
    shutil.rmtree(workspace)
    with interprocess_lock(paths.locks / "attempt-prepare.lock"):
        hub = open_hub(paths)
        with starter_lock(paths):
            hub.prepare_attempt(item.task, workspace, "strict", paths.project_root / "scripts" / "score-exam")
        hub.database.engine.dispose()
    if controls.tree_digest(workspace) != starter_digest:
        raise RuntimeError(f"the restored starter of {item.attempt_id} differs from the first one")


def run_attempt(
    paths: StudyPaths,
    config: StudyConfig,
    config_digest: str,
    item: Scheduled,
    harness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = paths.data_root / "e1" / config.study_id / "attempts" / item.attempt_id
    final = root / "attempt.json"
    if final.is_file():
        record = json.loads(final.read_text(encoding="utf-8"))
        recorded = record.get("configDigest")
        if recorded is not None and recorded != config_digest:
            raise ValueError(
                f"{item.attempt_id} was recorded under another configuration; use a new study id instead"
            )
        return record
    if root.exists():
        shutil.rmtree(root)  # an interrupted attempt left no terminal record; it never counted
    task = task_for(item.task)
    model = next(entry for entry in config.models if entry.id == item.model)
    workspace, agent_out = root / "workspace", root / "agent"
    agent_out.mkdir(parents=True, mode=0o700)

    with interprocess_lock(paths.locks / "attempt-prepare.lock"):
        # This process's Hub; the preparation holds the starter lock so it never reads a
        # starter that another study process is rebuilding.
        hub = open_hub(paths)
        with starter_lock(paths):
            hub.prepare_attempt(item.task, workspace, "strict", paths.project_root / "scripts" / "score-exam")
        _key, loaded, hub_task = hub._loaded_task(item.task)
        # The same two strings BenchmarkHub.solve_attempt gives the model.
        prompt = {
            "requirement": loaded.plugin.task_prompt(hub_task),
            "systemPrompt": (
                f"{loaded.plugin.agent_system_prompt(hub_task)} "
                "The benchmark platform will run the private evaluator exactly once after you submit. "
                "Do not invoke score-exam, run-attempt, or any benchmark scorer yourself."
            ),
        }
        hub.database.engine.dispose()
    _write(agent_out / "prompt.json", prompt)
    prompt_digest = hashlib.sha256(
        (prompt["systemPrompt"] + "\0" + prompt["requirement"]).encode("utf-8")
    ).hexdigest()
    starter_digest = controls.tree_digest(workspace)

    voided: list[dict[str, Any]] = []
    for start in range(1, GENERATION_STARTS + 1):
        generation = _generate(paths, config, model, workspace, agent_out, item.attempt_id, task.game)
        model_report = _read_model_report(agent_out)
        interrupted = provider_interrupted(model_report, agent_out)
        if not interrupted and not never_started(generation, model_report, agent_out):
            break
        if generation.get("setupFailed") and start == GENERATION_STARTS:
            # The harness, not the model, failed: leave no record so the attempt runs again.
            shutil.rmtree(root)
            raise RuntimeError(
                f"generation environment could not be assembled: {generation['containerFailure']}"
            )
        if start == GENERATION_STARTS:
            break
        if interrupted:
            # The provider stopped serving a generation that had begun: start it again from the
            # unchanged starter, so the new generation sees exactly what the first one saw.
            _restore_starter(paths, item, workspace, starter_digest)
        elif controls.tree_digest(workspace) != starter_digest:
            break
        # Keep the evidence of the voided start, then start again.
        voided.append(
            {
                **generation,
                "error": model_report.get("error"),
                "start": start,
                "kind": "provider-interrupted" if interrupted else "never-answered",
            }
        )
        kept = root / "voided" / str(start)
        kept.parent.mkdir(exist_ok=True)
        shutil.move(agent_out, kept)
        agent_out.mkdir(mode=0o700)
        _write(agent_out / "prompt.json", prompt)
        time.sleep(VOID_BACKOFF_SECONDS * start)
    exhausted = context_exhausted(model_report)
    generation_failed = (bool(model_report.get("error")) and not exhausted) or bool(
        generation.get("setupFailed")
    )
    trajectory_path = agent_out / "trajectory.json"
    usage = token_usage(json.loads(trajectory_path.read_text())) if trajectory_path.is_file() else {}

    submission = root / "submission"
    shutil.copytree(workspace, submission, symlinks=True)
    submission_digest = controls.tree_digest(submission)

    directory = paths.study_controls(task.pack_dir, task.task)
    clause_map = ClauseMap.load(directory / "clause-map.json")
    # A generation the repeated-action guard ended is failed without evaluation (budget rule).
    looped = not generation_failed and model_report.get("exitStatus") == REPEATED_ACTION_EXIT
    deferred = task.game in config.deferred_evaluation and not generation_failed and not looped
    scored = _score(
        paths,
        task,
        clause_map,
        submission,
        submission_digest,
        root,
        skip=generation_failed or deferred or looped,
    )
    if scored["executions"]:
        verdict = _verdict(clause_map, scored["executions"][-1])
    elif deferred:
        verdict = _verdict(
            clause_map,
            {
                "index": None,
                "outcome": PENDING,
                "reason": "evaluation deferred to a host that runs this game's engine",
                "result": {},
                "cases": case_table({}, clause_map.case_ids()),
            },
        )
        verdict["auditedOutcome"] = PENDING
    elif looped:
        verdict = _verdict(
            clause_map,
            {
                "index": None,
                "outcome": "failed",
                "reason": (
                    f"the model issued the same commands {config.budget.repeated_action_limit} times in a "
                    "row; "
                    "the generation was stopped and counted as failed without evaluation"
                ),
                "result": {},
                "cases": case_table({}, clause_map.case_ids()),
            },
        )
        verdict["auditedOutcome"] = "failed"
    else:
        reached = endpoint_reached(agent_out) and model_answered(agent_out)
        verdict = _verdict(
            clause_map,
            {
                "index": None,
                "outcome": "invalid",
                "reason": (
                    "the generation ended with a provider or scaffold error after the model was reached"
                    if reached
                    else f"the model never answered in {GENERATION_STARTS} generation starts"
                ),
                "result": {},
                "cases": case_table({}, clause_map.case_ids()),
            },
        )
    record = {
        **asdict(item),
        "studyId": config.study_id,
        "configDigest": config_digest,
        "snapshotCommit": config.snapshot_commit,
        "harness": harness,
        "taskVersion": clause_map.task_version,
        "kind": task.kind,
        "sourceFamily": task.source_family,
        "scaffold": config.scaffold,
        "modelCondition": model.model_dump(mode="json", exclude={"api_key_file"}),
        "budget": config.budget.model_dump(),
        "promptDigest": prompt_digest,
        "starterDigest": starter_digest,
        "submissionDigest": submission_digest,
        "submissionChanged": submission_digest != starter_digest,
        "generation": {
            **generation,
            "terminationReason": (
                "context-window-exhausted" if exhausted else "repeated-action-loop" if looped else None
            ),
            **{
                k: model_report.get(k)
                for k in (
                    "steps",
                    "exitStatus",
                    "changedFiles",
                    "durationSeconds",
                    "error",
                    "message",
                    "framework",
                )
            },
        },
        "usage": usage,
        "voidedGenerationStarts": voided,
        "executions": scored["summary"],
        "voidedExecutions": scored["voided"],
        **verdict,
        "adjudication": "automatic",
        "recordedAt": _now(),
    }
    _write(final, record)
    return record
