from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from rhenium_palworld.catalog import (
    IntegrationCheck,
    LocalizedText,
    PalworldCatalog,
    PatternGroup,
)
from rhenium_palworld.evaluator import DedicatedServerRunner, PalworldEvaluator
from rhenium_palworld.runtime import PalworldRuntimeConfig

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "palworld"


def _check(result: dict[str, object], check_id: str) -> dict[str, object]:
    checks = result["checks"]
    assert isinstance(checks, list)
    return next(check for check in checks if isinstance(check, dict) and check["id"] == check_id)


def _runner_command(submission: Path, hidden_test: Path) -> tuple[list[str], dict[str, str]]:
    source_root = Path(__file__).parents[1] / "src"
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.pathsep.join((str(source_root), existing)) if existing else str(source_root)
    )
    return (
        [
            sys.executable,
            "-m",
            "rhenium_palworld.lua_runner",
            "--submission",
            str(submission),
            "--test",
            str(hidden_test),
        ],
        environment,
    )


def test_core_profile_is_always_incomplete(tmp_path: Path) -> None:
    catalog = PalworldCatalog.load(DATASET)
    evaluator = PalworldEvaluator(PalworldRuntimeConfig(pack_root=DATASET))
    submission = tmp_path / "submission"
    submission.mkdir()

    assert len(catalog.tasks) == 10
    result = evaluator.evaluate(submission, catalog.tasks[0], profile="core")

    assert result["passed"] is False
    assert result["complete"] is False
    assert result["available_maximum"] == 100.0
    assert result["score"] <= 60.0
    assert _check(result, "headless-server")["status"] == "skipped"
    assert _check(result, "headless-server")["maximum"] == 40.0


def test_unknown_profile_is_rejected(tmp_path: Path) -> None:
    task = PalworldCatalog.load(DATASET).tasks[0]
    submission = tmp_path / "submission"
    submission.mkdir()

    with pytest.raises(ValueError, match="unsupported Palworld evaluation profile"):
        PalworldEvaluator(PalworldRuntimeConfig(pack_root=DATASET)).evaluate(
            submission, task, profile="quick"
        )


def test_empty_submission_never_passes(tmp_path: Path) -> None:
    task = PalworldCatalog.load(DATASET).tasks[0]
    submission = tmp_path / "empty"
    submission.mkdir()

    result = PalworldEvaluator(PalworldRuntimeConfig(pack_root=DATASET)).evaluate(
        submission, task, profile="core"
    )

    assert result["passed"] is False
    assert result["score"] < 100.0
    assert _check(result, "required-files")["status"] == "failed"
    assert _check(result, "lua-syntax")["status"] == "failed"
    assert _check(result, "hidden-behavior")["status"] == "failed"


def test_integration_patterns_inside_comments_do_not_count(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "scripts").mkdir(parents=True)
    source = submission / "scripts/main.lua"
    source.write_text(
        '-- RegisterConsoleCommandGlobalHandler("rhenium_supply", on_claim)\n', encoding="utf-8"
    )
    integration = IntegrationCheck(
        id="console-registration",
        label=LocalizedText(en="Console registration", zh="控制台注册"),
        weight=15,
        glob="**/*.lua",
        groups=[
            PatternGroup(
                name="registration",
                any_of=[
                    r'RegisterConsoleCommandGlobalHandler\s*\(\s*["\']rhenium_supply["\']\s*,\s*on_claim\s*\)'
                ],
            )
        ],
    )

    forged = PalworldEvaluator._evaluate_integration_check(submission, integration)
    source.write_text(
        'RegisterConsoleCommandGlobalHandler("rhenium_supply", on_claim)\n', encoding="utf-8"
    )
    real = PalworldEvaluator._evaluate_integration_check(submission, integration)

    assert forged.status == "failed"
    assert forged.score == 0.0
    assert real.status == "passed"
    assert real.score == 15.0


def test_manifest_integration_check_reads_non_lua_sources(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    manifest = submission / "Info.json"
    integration = IntegrationCheck(
        id="package-manifest",
        label=LocalizedText(en="Package manifest", zh="包清单"),
        weight=15,
        glob="Info.json",
        groups=[
            PatternGroup(name="lua rule", any_of=[r'"Type"\s*:\s*"Lua"']),
            PatternGroup(name="server rule", any_of=[r'"IsServer"\s*:\s*true']),
        ],
    )

    manifest.write_text(
        json.dumps({"PackageName": "Client", "InstallRule": [{"Type": "Lua"}]}) + "\n",
        encoding="utf-8",
    )
    client_only = PalworldEvaluator._evaluate_integration_check(submission, integration)
    manifest.write_text(
        json.dumps(
            {"PackageName": "Server", "InstallRule": [{"Type": "Lua", "IsServer": True}]}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    server_capable = PalworldEvaluator._evaluate_integration_check(submission, integration)

    assert client_only.status == "failed"
    assert server_capable.status == "passed"
    assert server_capable.details["files"] == ["Info.json"]


def test_server_result_parser_requires_one_nonce_bound_payload() -> None:
    nonce = "abc123"
    payload = json.dumps(
        {"status": "passed", "cases": [{"name": "server state", "passed": True, "message": "ok"}]}
    )
    other = json.dumps(
        {"status": "failed", "cases": [{"name": "server state", "passed": False, "message": "no"}]}
    )
    parsed = DedicatedServerRunner._parse_assertion_result(
        f"prefix @@RHENIUM_SERVER@@{nonce}:{payload}\n", nonce
    )
    echoed = DedicatedServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@{nonce}:{payload}\n@@RHENIUM_SERVER@@{nonce}:{payload}\n", nonce
    )
    missing = DedicatedServerRunner._parse_assertion_result("unrelated\n", nonce)
    conflicting = DedicatedServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@{nonce}:{payload}\n@@RHENIUM_SERVER@@{nonce}:{other}\n", nonce
    )
    unsigned = DedicatedServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@deadbeef:{payload}\n", nonce
    )

    assert parsed["status"] == "passed"
    assert parsed["cases"][0]["name"] == "server state"
    assert echoed["status"] == "passed"
    assert missing["status"] == "error"
    assert conflicting["status"] == "error"
    assert unsigned["status"] == "error"


def test_server_suite_is_injected_only_into_temporary_copy(tmp_path: Path) -> None:
    original = tmp_path / "original"
    copied = tmp_path / "copied"
    for root in (original, copied):
        (root / "scripts").mkdir(parents=True)
        (root / "scripts/main.lua").write_text("local value = 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    error = DedicatedServerRunner._inject_assertion_suite(
        copied, suite, "nonce", tmp_path / "rhenium_result.txt"
    )

    assert error is None
    assert (original / "scripts/main.lua").read_text(encoding="utf-8") == "local value = 1\n"
    injected = (copied / "scripts/main.lua").read_text(encoding="utf-8")
    assert "@@RHENIUM_SERVER@@nonce" in injected
    assert (copied / "scripts/rhenium_server_test.lua").is_file()
    submitted = (copied / "scripts/rhenium_submission_main.lua").read_text(encoding="utf-8")
    assert submitted == "local value = 1\n"


def _run_injected_entry_point(tmp_path: Path, main_lua: str) -> tuple[Path, Exception | None]:
    lupa = pytest.importorskip("lupa")
    mod = tmp_path / "mod"
    (mod / "scripts").mkdir(parents=True)
    (mod / "scripts/main.lua").write_text(main_lua, encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text(
        'return function(ctx) ctx:case("service", function() assert(RheniumService.ok) end) end\n',
        encoding="utf-8",
    )
    result = tmp_path / "rhenium_result.txt"
    assert DedicatedServerRunner._inject_assertion_suite(mod, suite, "nonce", result) is None
    runtime = lupa.LuaRuntime(unpack_returned_tuples=True)
    scripts = (mod / "scripts").as_posix()
    runtime.execute(f'package.path = [==[{scripts}/?.lua]==] .. ";" .. package.path')
    # UE4SS schedules the loader later; running the callbacks at once exercises the same path.
    runtime.execute(
        "function ExecuteWithDelay(ms, fn) fn() end function ExecuteInGameThread(fn) fn() end "
        "function RegisterInitGameStatePostHook(fn) end"
    )
    try:
        runtime.execute(f"dofile([==[{scripts}/main.lua]==])")
    except Exception as error:  # noqa: BLE001 - the Lua error is the observation
        return result, error
    return result, None


def test_injected_entry_point_keeps_a_top_level_return_valid(tmp_path: Path) -> None:
    result, error = _run_injected_entry_point(
        tmp_path, "RheniumService = { ok = true }\nreturn { cleanup = function() end }\n"
    )
    assert error is None
    assert '"status":"passed"' in result.read_text(encoding="utf-8")


def test_a_submission_that_does_not_load_still_stops_the_assertions(tmp_path: Path) -> None:
    result, error = _run_injected_entry_point(tmp_path, "RheniumService = { ok = true\n")
    assert error is not None
    assert not result.exists()


def test_server_suite_injection_rejects_a_reserved_path(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "scripts").mkdir(parents=True)
    (submission / "scripts/main.lua").write_text("local value = 1\n", encoding="utf-8")
    (submission / "scripts/rhenium_server_test.lua").write_text("return 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    error = DedicatedServerRunner._inject_assertion_suite(
        submission, suite, "nonce", tmp_path / "rhenium_result.txt"
    )

    assert error is not None
    assert "reserved assertion path" in error


def test_server_suite_injection_rejects_the_reserved_entry_point_path(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "scripts").mkdir(parents=True)
    (submission / "scripts/main.lua").write_text("local value = 1\n", encoding="utf-8")
    (submission / "scripts/rhenium_submission_main.lua").write_text("return 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    error = DedicatedServerRunner._inject_assertion_suite(
        submission, suite, "nonce", tmp_path / "rhenium_result.txt"
    )

    assert error is not None and "rhenium_submission_main.lua" in error


def test_mod_registry_is_restored_after_a_scoring_run(tmp_path: Path) -> None:
    registry = tmp_path / "mods.txt"
    registry.write_text("OperatorMod : 1\n", encoding="utf-8")
    original = registry.read_bytes()

    assert DedicatedServerRunner._enable_mod(registry, "rhenium_probe") is None
    enabled = registry.read_text(encoding="utf-8")
    DedicatedServerRunner._restore_registry(registry, original)

    assert enabled.splitlines() == ["OperatorMod : 1", "rhenium_probe : 1"]
    assert registry.read_bytes() == original


def test_real_headless_server_executes_nonce_bound_assertion_when_available(tmp_path: Path) -> None:
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=DATASET,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = PalworldEvaluator(PalworldRuntimeConfig.load(context))
    runner = evaluator.server
    if not evaluator.runtime_status()["available"]:
        pytest.skip("Palworld dedicated server or its UE4SS mods directory is unavailable")
    submission = tmp_path / "headless-mod"
    (submission / "scripts").mkdir(parents=True)
    (submission / "Info.json").write_text(
        json.dumps(
            {
                "PackageName": "RheniumRunnerProbe",
                "Version": "1.0.0",
                "InstallRule": [{"Type": "Lua", "Targets": ["./scripts"], "IsServer": True}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (submission / "scripts/main.lua").write_text("local HEADLESS = true\n", encoding="utf-8")
    suite = tmp_path / "server-suite.lua"
    suite.write_text(
        "return function(ctx)\n"
        "  ctx:case('dedicated server world exists', function()\n"
        "    local helpers = assert(ctx.helpers)\n"
        # Palworld's shipping build strips UGameplayStatics::IsDedicatedServer.
        "    assert(helpers.GetKismetSystemLibrary():IsDedicatedServer(helpers.GetWorld()))\n"
        "  end)\n"
        "end\n",
        encoding="utf-8",
    )

    result = runner.run_assertions(submission, suite, timeout=240)

    assert result["status"] == "passed", result.get("log", result)
    assert result["cases"] == [
        {"name": "dedicated server world exists", "passed": True, "message": "ok"}
    ]


def test_lua_runner_rejects_submission_path_escape(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    (tmp_path / "outside.lua").write_text("return {secret = true}\n", encoding="utf-8")
    hidden = tmp_path / "escape-test.lua"
    hidden.write_text(
        "local ok, message = pcall(load_submission, '../outside.lua')\n"
        "return { cases = { { name = 'path escape', passed = not ok, "
        "message = tostring(message) } } }\n",
        encoding="utf-8",
    )
    command, environment = _runner_command(submission, hidden)

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=environment,
        timeout=8,
        check=False,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["status"] == "passed"
    assert payload["cases"][0]["name"] == "path escape"
    assert payload["cases"][0]["passed"] is True
    assert "relative Lua files" in payload["cases"][0]["message"]


def test_lua_runner_denies_engine_globals_to_the_core_module(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "scripts").mkdir(parents=True)
    (submission / "scripts/core.lua").write_text(
        "return { has_os = os ~= nil, has_require = require ~= nil, has_io = io ~= nil }\n",
        encoding="utf-8",
    )
    hidden = tmp_path / "globals-test.lua"
    hidden.write_text(
        "local module = load_submission('scripts/core.lua')\n"
        "local clean = not module.has_os and not module.has_require and not module.has_io\n"
        "return { cases = { { name = 'sandbox', passed = clean, message = '' } } }\n",
        encoding="utf-8",
    )
    command, environment = _runner_command(submission, hidden)

    completed = subprocess.run(
        command, capture_output=True, text=True, env=environment, timeout=8, check=False
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["cases"] == [{"name": "sandbox", "passed": True, "message": ""}]


def test_lua_runner_terminates_infinite_submission(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "loop.lua").write_text("while true do end\n", encoding="utf-8")
    hidden = tmp_path / "timeout-test.lua"
    hidden.write_text(
        "load_submission('loop.lua')\n"
        "return { cases = { { name = 'unreachable', passed = true, message = '' } } }\n",
        encoding="utf-8",
    )
    command, environment = _runner_command(submission, hidden)
    started = time.monotonic()

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=environment,
        timeout=8,
        check=False,
    )

    assert completed.returncode != 0
    assert time.monotonic() - started < 8


def test_evaluator_fails_closed_when_behavior_runner_times_out(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    task = PalworldCatalog.load(DATASET).tasks[0]
    command = [sys.executable, "-m", "rhenium_palworld.lua_runner"]
    with patch(
        "rhenium_palworld.evaluator.subprocess.run",
        side_effect=subprocess.TimeoutExpired(command, timeout=8),
    ):
        result = PalworldEvaluator(PalworldRuntimeConfig(pack_root=DATASET)).evaluate(
            submission, task, profile="core"
        )
    behavior = _check(result, "hidden-behavior")
    assert result["passed"] is False
    assert behavior["status"] == "failed"
    assert isinstance(behavior["details"], dict)
    assert behavior["details"]["runner_status"] == "timeout"


def test_runtime_status_is_unavailable_without_a_configured_server() -> None:
    status = PalworldEvaluator(PalworldRuntimeConfig(pack_root=DATASET)).runtime_status()

    assert status["id"] == "palworld-dedicated-server"
    assert status["available"] is False
    assert status["binary"] is None
