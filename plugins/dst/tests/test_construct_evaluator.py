"""Evaluator tests of the construct pack, restored from the pre-repair plugin.

Construct tasks reach the restored construct evaluator through DstEvaluator,
which dispatches on the task's catalog model.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from rhenium_dst.construct_catalog import DstConstructCatalog, IntegrationCheck, PatternGroup
from rhenium_dst.construct_evaluator import ConstructServerRunner, DstConstructEvaluator
from rhenium_dst.evaluator import DstEvaluator
from rhenium_dst.runtime import DstRuntimeConfig

from rhenium.core.catalog import LocalizedText
from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "dst-construct"


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
            "rhenium_dst.lua_runner",
            "--submission",
            str(submission),
            "--test",
            str(hidden_test),
        ],
        environment,
    )


def test_core_profile_is_always_incomplete(tmp_path: Path) -> None:
    catalog = DstConstructCatalog.load(DATASET)
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=DATASET))
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


def test_empty_submission_never_passes(tmp_path: Path) -> None:
    task = DstConstructCatalog.load(DATASET).tasks[0]
    submission = tmp_path / "empty"
    submission.mkdir()

    result = DstEvaluator(DstRuntimeConfig(pack_root=DATASET)).evaluate(
        submission, task, profile="core"
    )

    assert result["passed"] is False
    assert result["score"] < 100.0
    assert _check(result, "required-files")["status"] == "failed"
    assert _check(result, "lua-syntax")["status"] == "failed"
    assert _check(result, "hidden-behavior")["status"] == "failed"


def test_integration_patterns_inside_comments_do_not_count(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    submission.mkdir()
    source = submission / "modmain.lua"
    source.write_text('-- AddModRPCHandler("rhenium", "claim", on_claim)\n', encoding="utf-8")
    integration = IntegrationCheck(
        id="rpc-registration",
        label=LocalizedText(en="RPC registration", zh="RPC 注册"),
        weight=15,
        glob="**/*.lua",
        groups=[
            PatternGroup(
                name="registration",
                any_of=[
                    r'AddModRPCHandler\s*\(\s*["\']rhenium["\']\s*,\s*["\']claim["\']\s*,\s*on_claim\s*\)'
                ],
            )
        ],
    )

    forged = DstConstructEvaluator._evaluate_integration_check(submission, integration)
    source.write_text('AddModRPCHandler("rhenium", "claim", on_claim)\n', encoding="utf-8")
    real = DstConstructEvaluator._evaluate_integration_check(submission, integration)

    assert forged.status == "failed"
    assert forged.score == 0.0
    assert real.status == "passed"
    assert real.score == 15.0


def test_server_result_parser_requires_one_nonce_bound_payload() -> None:
    nonce = "abc123"
    payload = json.dumps(
        {"status": "passed", "cases": [{"name": "server state", "passed": True, "message": "ok"}]}
    )
    parsed = ConstructServerRunner._parse_assertion_result(
        f"prefix @@RHENIUM_SERVER@@{nonce}:{payload}\n", nonce
    )
    missing = ConstructServerRunner._parse_assertion_result("unrelated\n", nonce)
    duplicate = ConstructServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@{nonce}:{payload}\n@@RHENIUM_SERVER@@{nonce}:{payload}\n", nonce
    )

    assert parsed["status"] == "passed"
    assert parsed["cases"][0]["name"] == "server state"
    assert missing["status"] == "error"
    assert duplicate["status"] == "error"


@pytest.mark.parametrize(
    "names,accepted",
    [
        (["first", "second"], True),
        (["second", "first"], True),
        (["first"], False),
        (["first", "second", "extra"], False),
        (["first", "not a catalog case"], False),
        (["first", "first"], False),
    ],
)
def test_server_result_parser_binds_reported_cases_to_the_declared_set(
    names: list[str], accepted: bool
) -> None:
    nonce = "abc123"
    payload = json.dumps(
        {"status": "passed", "cases": [{"name": name, "passed": True, "message": "ok"} for name in names]}
    )
    log = f"@@RHENIUM_SERVER@@{nonce}:{payload}\n"

    bound = ConstructServerRunner._parse_assertion_result(log, nonce, ("first", "second"))
    unbound = ConstructServerRunner._parse_assertion_result(log, nonce)

    assert (bound["status"] == "passed") is accepted
    if not accepted:
        assert bound["status"] == "error" and bound["cases"] == []
    # A task without declared names keeps the previous permissive behavior.
    assert unbound["status"] == "passed"


def test_every_core_task_declares_the_case_names_its_suites_define() -> None:
    import re

    pack = Path(__file__).parents[3] / "benchmarks" / "dst-construct"
    catalog = DstConstructCatalog.load(pack)
    assert catalog.tasks
    for task in catalog.tasks:
        hidden = re.findall(r'^run\("([^"]+)"', (pack / task.hidden_test).read_text(encoding="utf-8"), re.M)
        server = re.findall(r'ctx:case\("([^"]+)"', (pack / task.server_test).read_text(encoding="utf-8"))
        assert list(task.hidden_cases) == hidden and hidden
        assert list(task.server_cases) == server and server


def test_hidden_behavior_result_is_rejected_when_its_case_set_drifts(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    (pack / "hidden").mkdir(parents=True)
    (pack / "hidden" / "suite.lua").write_text(
        "return { cases = { { name = 'renamed', passed = true, message = 'ok' } } }\n", encoding="utf-8"
    )
    submission = tmp_path / "submission"
    submission.mkdir()
    real = DstConstructCatalog.load(Path(__file__).parents[3] / "benchmarks" / "dst-construct").tasks[0]
    evaluator = DstConstructEvaluator(DstRuntimeConfig(pack_root=pack))

    drifted = evaluator._run_behavior_tests(
        submission, real.model_copy(update={"hidden_test": "hidden/suite.lua", "hidden_cases": ("declared",)})
    )
    matching = evaluator._run_behavior_tests(
        submission, real.model_copy(update={"hidden_test": "hidden/suite.lua", "hidden_cases": ("renamed",)})
    )

    assert drifted["status"] == "error" and drifted["cases"] == []
    assert matching["status"] == "passed"


def test_server_suite_is_injected_only_into_temporary_copy(tmp_path: Path) -> None:
    original = tmp_path / "original"
    copied = tmp_path / "copied"
    original.mkdir()
    (original / "modmain.lua").write_text("local value = 1\n", encoding="utf-8")
    copied.mkdir()
    (copied / "modmain.lua").write_text("local value = 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    error = ConstructServerRunner._inject_assertion_suite(copied, suite, "nonce")

    assert error is None
    assert (original / "modmain.lua").read_text(encoding="utf-8") == "local value = 1\n"
    injected = (copied / "modmain.lua").read_text(encoding="utf-8")
    assert "@@RHENIUM_SERVER@@nonce" in injected
    assert 'modimport("rhenium_candidate_modmain.lua")' in injected
    assert (copied / "rhenium_candidate_modmain.lua").read_text(encoding="utf-8") == "local value = 1\n"
    assert (copied / "scripts/rhenium_server_test.lua").is_file()


@pytest.mark.parametrize("reserved", ["rhenium_candidate_modmain.lua", "scripts/rhenium_server_test.lua"])
def test_server_suite_injection_refuses_a_reserved_path(tmp_path: Path, reserved: str) -> None:
    mod = tmp_path / "mod"
    (mod / "scripts").mkdir(parents=True)
    (mod / "modmain.lua").write_text("local value = 1\n", encoding="utf-8")
    (mod / reserved).write_text("return 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    error = ConstructServerRunner._inject_assertion_suite(mod, suite, "nonce")

    assert error is not None and "reserved assertion path" in error and reserved in error
    assert (mod / "modmain.lua").read_text(encoding="utf-8") == "local value = 1\n"


_LOADER_HOST = r"""
GLOBAL = _G
print = function(line) python_print(line) end
package.preload["rhenium_server_test"] = function()
    return function(ctx)
        ctx:case("passes", function() end)
        ctx:case("quoted failure", function()
            error("attempt to index local 'self' (a nil value)", 0)
        end)
        ctx:case('escaped "double" and \\ backslash', function()
            error("line one\nline\ttwo\1", 0)
        end)
    end
end
function AddPrefabPostInit(name, callback)
    rhenium_world_callbacks[#rhenium_world_callbacks + 1] = callback
end
rhenium_world_callbacks = {}
-- The game's modimport: load the named file of the mod and run it as its own chunk.
function modimport(name)
    local chunk = assert((loadstring or load)(candidate_source(name), "=" .. name))
    chunk()
end
function rhenium_boot_world()
    local world = { ismastersim = true }
    function world:DoTaskInTime(delay, callback) callback() end
    for _, callback in ipairs(rhenium_world_callbacks) do callback(world) end
end
"""


def _boot_injected_mod(tmp_path: Path, modmain: str, nonce: str) -> list[str]:
    lupa = pytest.importorskip("lupa")
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "modmain.lua").write_text(modmain, encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")
    assert ConstructServerRunner._inject_assertion_suite(mod, suite, nonce) is None
    printed: list[str] = []
    runtime = lupa.LuaRuntime(register_eval=False)
    runtime.globals().python_print = printed.append
    runtime.globals().candidate_source = lambda name: (mod / name).read_text(encoding="utf-8")
    runtime.execute(_LOADER_HOST)
    runtime.execute((mod / "modmain.lua").read_text(encoding="utf-8"))
    runtime.globals().rhenium_boot_world()
    return printed


@pytest.mark.parametrize(
    "modmain",
    [
        # A main chunk may end in a return: appending to it would not even parse.
        'AddPrefabPostInit("world", function() print("candidate world") end)\nreturn {}\n',
        # It may also leave early; the suite still has to be registered.
        'AddPrefabPostInit("world", function() print("candidate world") end)\n'
        "if GLOBAL ~= nil then return end\nerror('unreachable')\n",
    ],
)
def test_injected_server_loader_runs_after_a_main_chunk_that_returns(tmp_path: Path, modmain: str) -> None:
    nonce = "0123abcd"

    printed = _boot_injected_mod(tmp_path, modmain, nonce)

    # The candidate registers first, as it did when the loader followed its code.
    assert printed[0] == "candidate world"
    result = ConstructServerRunner._parse_assertion_result("\n".join(printed) + "\n", nonce)
    assert result["status"] == "failed", result
    assert [case["name"] for case in result["cases"]] == [
        "passes", "quoted failure", 'escaped "double" and \\ backslash',
    ]


def test_injected_server_loader_emits_standard_json_for_quoted_failures(tmp_path: Path) -> None:
    nonce = "0123abcd"
    printed = _boot_injected_mod(tmp_path, "local HEADLESS = true\n", nonce)
    result = ConstructServerRunner._parse_assertion_result("\n".join(printed) + "\n", nonce)

    assert result["status"] == "failed", result
    assert result["cases"] == [
        {"name": "passes", "passed": True, "message": "ok"},
        {
            "name": "quoted failure",
            "passed": False,
            "message": "attempt to index local 'self' (a nil value)",
        },
        {
            "name": 'escaped "double" and \\ backslash',
            "passed": False,
            "message": "line one\nline\ttwo\x01",
        },
    ]


def _real_headless_submission(tmp_path: Path) -> tuple[ConstructServerRunner, Path]:
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=DATASET,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = DstConstructEvaluator(DstRuntimeConfig.load(context))
    if not evaluator.runtime_status()["available"]:
        pytest.skip("DST dedicated server is unavailable or its mods directory is not writable")
    submission = tmp_path / "headless-mod"
    submission.mkdir()
    (submission / "modinfo.lua").write_text(
        'name = "Rhenium Runner Probe"\n'
        'description = "Headless assertion probe"\n'
        'author = "Rhenium"\nversion = "1"\napi_version = 10\n'
        "dst_compatible = true\nall_clients_require_mod = true\nclient_only_mod = false\n",
        encoding="utf-8",
    )
    (submission / "modmain.lua").write_text("local HEADLESS = true\n", encoding="utf-8")
    return evaluator.server, submission


def test_real_headless_server_executes_nonce_bound_assertion_when_available(tmp_path: Path) -> None:
    runner, submission = _real_headless_submission(tmp_path)
    suite = tmp_path / "server-suite.lua"
    suite.write_text(
        "return function(ctx)\n"
        "  ctx:case('master world exists', function()\n"
        "    assert(TheWorld ~= nil and TheWorld.ismastersim)\n"
        "  end)\n"
        "end\n",
        encoding="utf-8",
    )

    result = runner.run_assertions(submission, suite, timeout=90)

    assert result["status"] == "passed", result.get("log", result)
    assert result["cases"] == [{"name": "master world exists", "passed": True, "message": "ok"}]


def test_real_headless_server_reports_quoted_failure_messages_when_available(
    tmp_path: Path,
) -> None:
    runner, submission = _real_headless_submission(tmp_path)
    suite = tmp_path / "server-suite.lua"
    suite.write_text(
        "return function(ctx)\n"
        "  ctx:case('quoted failure', function()\n"
        "    error(\"attempt to index local 'self' (a nil value)\", 0)\n"
        "  end)\n"
        "end\n",
        encoding="utf-8",
    )

    result = runner.run_assertions(submission, suite, timeout=90)

    assert result["status"] == "failed", result.get("log", result)
    assert result["cases"] == [
        {
            "name": "quoted failure",
            "passed": False,
            "message": "attempt to index local 'self' (a nil value)",
        }
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
    assert payload["cases"] == [
        {
            "name": "path escape",
            "passed": True,
            "message": payload["cases"][0]["message"],
        }
    ]
    assert "relative Lua files" in payload["cases"][0]["message"]


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
    task = DstConstructCatalog.load(DATASET).tasks[0]
    command = [sys.executable, "-m", "rhenium_dst.lua_runner"]
    with patch(
        "rhenium_dst.construct_evaluator.subprocess.run",
        side_effect=subprocess.TimeoutExpired(command, timeout=8),
    ):
        result = DstEvaluator(DstRuntimeConfig(pack_root=DATASET)).evaluate(
            submission, task, profile="core"
        )
    behavior = _check(result, "hidden-behavior")
    assert result["passed"] is False
    assert behavior["status"] == "failed"
    assert isinstance(behavior["details"], dict)
    assert behavior["details"]["runner_status"] == "timeout"
