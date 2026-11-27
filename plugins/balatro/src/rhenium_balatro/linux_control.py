"""Real-engine operations using the frozen task evaluator; no acquisition here."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .files import read_json
from .linux_runtime import sha
from .linux_session import LinuxSessionHost
from .native_assets import json_write_new
from .protocol import classify_poc_result
from .review import candidate_identity, candidate_reviewed
from .sidecar import load_task

SMOKE_REQUIRED = ("health", "discovery", "menu", "seed", "state", "real_play")


def smoke_files() -> dict[str, Any]:
    file = Path(__file__)
    return {file.name: {"size": file.stat().st_size, "sha256": sha(file)}}


def smoke_scenario(client: Any, checks: list[dict[str, Any]]) -> None:
    from .linux_assets.legacy.poc.checks import check

    check(checks, "health", client.call("health").get("status"), "ok")
    discovered = client.call("rpc.discover")
    methods = {item["name"] for item in discovered["methods"]}
    check(
        checks,
        "discovery",
        {"health", "gamestate", "start", "select", "play", "save", "load"} <= methods,
        True,
    )
    state = client.wait(lambda value: value["state"] == "MENU")
    check(checks, "menu", state["state"], "MENU")
    response = client.action("start", {"deck": "RED", "stake": "WHITE", "seed": "POC2026A"})
    check(checks, "seed", response.get("seed"), "POC2026A")
    client.wait(lambda value: value["state"] == "BLIND_SELECT")
    client.action("select")
    before = client.wait(lambda value: value["state"] == "SELECTING_HAND")
    check(checks, "state", before["state"], "SELECTING_HAND")
    client.action("play", {"cards": [0]})
    after = client.wait(lambda value: value["state"] in {"SELECTING_HAND", "ROUND_EVAL"}, timeout=40)
    check(checks, "real_play", after["round"]["hands_played"] - before["round"]["hands_played"], 1)


def require_smoke(host: LinuxSessionHost, path: Path) -> None:
    evidence = read_json(path.parent, path.name)
    expected = host.fingerprints(smoke_files(), None)
    raw = evidence.get("evaluation")
    if (
        not isinstance(raw, dict)
        or evidence.get("operation") != "smoke"
        or evidence.get("fingerprints") != expected
        or evidence.get("assets_sha256") != host.assets_sha256
        or evidence.get("artifact_identity") != host.artifact.identity
        or classify_poc_result(raw, SMOKE_REQUIRED, expected, 1)["passed"] is not True
    ):
        raise ValueError("A complete smoke for these exact execution inputs is required")


def execute(
    host: LinuxSessionHost,
    *,
    operation: str,
    output: Path,
    task_key: str = "",
    candidate: Path | None = None,
    smoke: Path | None = None,
) -> dict[str, Any]:
    if output.exists():
        raise ValueError("Refuse to overwrite operation evidence")
    if operation == "evaluate":
        if candidate is None or smoke is None:
            raise ValueError("Sealed reviewed candidate and matching smoke are required")
        require_smoke(host, smoke)
        seal, candidate_hash = candidate_identity(candidate)
        scoped = {**host.assets, "environment": host.environment, "harness": host.harness}
        if not candidate_reviewed(
            host.review_state, scoped, host.assets_sha256, task_key, seal, candidate_hash
        ):
            raise ValueError("Submission is outside the source-reviewed maintenance set")
    elif operation != "smoke":
        raise ValueError("Unsupported Linux operation")
    evaluator = host.install()
    if operation == "smoke":
        task_key = "probe-linux-smoke-v1"
        scenario = SimpleNamespace(REQUIRED=SMOKE_REQUIRED, evaluate=smoke_scenario)
        task = SimpleNamespace(
            key=task_key, session_api=False, mods={}, files=smoke_files, scenario=lambda: scenario
        )
        count = 1
    else:
        task = load_task(host.pack, task_key, host.assets)
        count = host.assets["tasks"][task_key]["expected_processes"]
    evaluator.TASKS[task_key] = task
    before = host.fingerprints(task.files(), candidate)
    if operation == "evaluate" and before["task"] != host.assets["tasks"][task_key]["task_sha256"]:
        raise ValueError("Frozen task fingerprint mismatch")
    raw = evaluator.run(task_key, candidate, output.parent.name)
    host.verify()
    if before != host.fingerprints(task.files(), candidate):
        raise ValueError("Inputs changed during evaluation")
    raw["platform_inputs_unchanged"] = True
    classified = classify_poc_result(raw, tuple(task.scenario().REQUIRED), before, count)
    result = {
        "schema_version": 1,
        "operation": operation,
        "evaluation": raw,
        "classification": classified,
        "fingerprints": before,
        "runtime_count": len(host.runtimes),
        "assets_sha256": host.assets_sha256,
        "artifact_identity": host.artifact.identity,
        "preflight_seconds": host.preflight_seconds,
    }
    json_write_new(output, result)
    return result
