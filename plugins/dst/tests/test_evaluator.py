from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from rhenium_dst.catalog import DstCatalog, DstTask
from rhenium_dst.evaluator import DedicatedServerRunner, DstEvaluator, modoverrides
from rhenium_dst.runtime import DstRuntimeConfig

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "dst"


def _task() -> DstTask:
    return DstCatalog.load(DATASET).tasks[0]


def _starter(tmp_path: Path, task: DstTask) -> Path:
    submission = tmp_path / "submission"
    shutil.copytree(DATASET / "private" / "harbor" / task.id / "environment" / "mod", submission / "mod")
    return submission


def _check(result: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(check for check in result["checks"] if check["id"] == check_id)


def _payload(names: list[str], failed: tuple[str, ...] = ()) -> str:
    cases = [{"name": name, "passed": name not in failed, "message": "ok"} for name in names]
    status = "failed" if failed else "passed"
    return json.dumps({"status": status, "cases": cases})


def test_server_result_parser_requires_one_nonce_bound_payload() -> None:
    nonce = "abc123"
    payload = _payload(["server state"])
    parsed = DedicatedServerRunner._parse_assertion_result(
        f"prefix @@RHENIUM_SERVER@@{nonce}:{payload}\n", nonce, ("server state",)
    )
    missing = DedicatedServerRunner._parse_assertion_result("unrelated\n", nonce, ("server state",))
    duplicate = DedicatedServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@{nonce}:{payload}\n@@RHENIUM_SERVER@@{nonce}:{payload}\n",
        nonce,
        ("server state",),
    )
    forged = DedicatedServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@other:{payload}\n", nonce, ("server state",)
    )

    assert parsed["status"] == "passed"
    assert parsed["cases"][0]["name"] == "server state"
    assert missing["status"] == "error"
    assert duplicate["status"] == "error"
    assert forged["status"] == "error"


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
def test_server_result_parser_binds_reported_cases_to_the_frozen_set(
    names: list[str], accepted: bool
) -> None:
    nonce = "abc123"
    log = f"@@RHENIUM_SERVER@@{nonce}:{_payload(names)}\n"

    bound = DedicatedServerRunner._parse_assertion_result(log, nonce, ("first", "second"))

    assert (bound["status"] == "passed") is accepted
    if not accepted:
        assert bound["status"] == "error" and bound["cases"] == []


def test_inconsistent_payload_status_is_rejected() -> None:
    nonce = "abc123"
    lying = json.dumps(
        {"status": "passed", "cases": [{"name": "only", "passed": False, "message": "boom"}]}
    )
    result = DedicatedServerRunner._parse_assertion_result(
        f"@@RHENIUM_SERVER@@{nonce}:{lying}\n", nonce, ("only",)
    )
    assert result["status"] == "error"


def test_modoverrides_enable_the_mod_with_the_operator_options() -> None:
    rendered = modoverrides(
        "rhenium_abc",
        {"SMARTUNWRAP": True, "spawn_fireflies": "always", "level": 3, "rate": 1.5, "off": False},
    )
    assert '["rhenium_abc"]' in rendered
    assert "enabled = true" in rendered
    assert "SMARTUNWRAP = true," in rendered
    assert 'spawn_fireflies = "always",' in rendered
    assert "level = 3," in rendered and "rate = 1.5," in rendered and "off = false," in rendered
    assert "configuration_options" not in modoverrides("rhenium_abc", {})
    with pytest.raises(ValueError, match="quotes"):
        modoverrides("rhenium_abc", {"bad": 'x"'})


def test_suite_loader_is_prepended_to_the_temporary_copy_only(tmp_path: Path) -> None:
    original = tmp_path / "original"
    copied = tmp_path / "copied"
    for root in (original, copied):
        root.mkdir()
        (root / "modmain.lua").write_text("\ufefflocal value = 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    assert DedicatedServerRunner._inject_assertion_suite(copied, suite, "nonce") is None

    assert (original / "modmain.lua").read_text(encoding="utf-8") == "\ufefflocal value = 1\n"
    injected = (copied / "modmain.lua").read_text(encoding="utf-8")
    assert injected.startswith("\ufeffdo -- Injected into the temporary scoring copy only.")
    assert injected.endswith("end\nlocal value = 1\n")
    assert "@@RHENIUM_SERVER@@nonce" in injected
    assert (copied / "scripts/rhenium_server_test.lua").read_bytes() == suite.read_bytes()


def test_suite_loader_refuses_a_submission_that_occupies_the_reserved_path(tmp_path: Path) -> None:
    mod = tmp_path / "mod"
    (mod / "scripts").mkdir(parents=True)
    (mod / "modmain.lua").write_text("local value = 1\n", encoding="utf-8")
    (mod / "scripts" / "rhenium_server_test.lua").write_text("return 1\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")

    error = DedicatedServerRunner._inject_assertion_suite(mod, suite, "nonce")
    assert error is not None and "reserved assertion path" in error


_LOADER_HOST = r"""
GLOBAL = _G
modname = "rhenium_probe"
print = function(line) python_print(line) end
package.preload["rhenium_server_test"] = function()
    return function(ctx)
        assert(ctx.modname == "rhenium_probe")
        ctx:case("passes", function() end)
        ctx:case("quoted failure", function()
            error("attempt to index local 'self' (a nil value)", 0)
        end)
        ctx:after(2, function()
            ctx:case('escaped "double" and \\ backslash', function()
                error("line one\nline\ttwo\1", 0)
            end)
            ctx:after(1, function()
                ctx:case("nested step", function() end)
            end)
        end)
    end
end
local pending = {}
function AddPrefabPostInit(name, callback)
    rhenium_world_callback = callback
end
function rhenium_boot_world()
    local world = { ismastersim = true }
    function world:DoTaskInTime(delay, callback) pending[#pending + 1] = callback end
    rhenium_world_callback(world)
    local index = 1
    while pending[index] do
        pending[index]()
        index = index + 1
    end
end
"""


def test_injected_loader_runs_async_steps_and_emits_standard_json(tmp_path: Path) -> None:
    # The dedicated server runs Lua 5.1, so exercise the loader under Lua 5.1.
    lupa = pytest.importorskip("lupa.lua51")
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "modmain.lua").write_text("GLOBAL.setfenv(1, GLOBAL)\nlocal HEADLESS = true\n", encoding="utf-8")
    suite = tmp_path / "suite.lua"
    suite.write_text("return function(ctx) end\n", encoding="utf-8")
    nonce = "0123abcd"
    assert DedicatedServerRunner._inject_assertion_suite(mod, suite, nonce) is None
    printed: list[str] = []
    runtime = lupa.LuaRuntime(register_eval=False)
    runtime.globals().python_print = printed.append
    runtime.execute(_LOADER_HOST)

    runtime.execute((mod / "modmain.lua").read_text(encoding="utf-8"))
    runtime.globals().rhenium_boot_world()
    expected = ("passes", "quoted failure", 'escaped "double" and \\ backslash', "nested step")
    result = DedicatedServerRunner._parse_assertion_result("\n".join(printed) + "\n", nonce, expected)

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
        {"name": "nested step", "passed": True, "message": "ok"},
    ]


def _fake_server(
    monkeypatch: pytest.MonkeyPatch, evaluator: DstEvaluator, result: dict[str, Any]
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def run_assertions(mod_root: Path, server_test: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"mod_root": mod_root, "server_test": server_test, **kwargs})
        return {**result, "log": "fake server log\n"}

    monkeypatch.setattr(evaluator.server, "run_assertions", run_assertions)
    return calls


def test_complete_run_reports_case_outcomes_and_binary_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = _task()
    submission = _starter(tmp_path, task)
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=DATASET))
    names = list(task.server_cases)
    failing = names[-1]
    calls = _fake_server(
        monkeypatch,
        evaluator,
        {
            "status": "failed",
            "message": "One or more headless server assertions failed",
            "cases": [{"name": name, "passed": name != failing, "message": "ok"} for name in names],
        },
    )

    result = evaluator.evaluate(submission, task, profile="full")

    assert calls[0]["mod_root"] == submission.resolve() / "mod"
    assert calls[0]["expected_cases"] == task.server_cases
    assert calls[0]["mod_options"] == task.mod_options
    assert result["complete"] is True and result["passed"] is False
    assert result["score"] == 10.0
    assert result["runtime"]["caseOutcomes"] == {name: name != failing for name in names}
    assert result["runtime"]["failedAssertions"] == 1
    assert _check(result, "headless-server")["status"] == "failed"
    assert _check(result, "submission-shape")["status"] == "passed"


def test_all_cases_passing_scores_one_hundred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task()
    submission = _starter(tmp_path, task)
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=DATASET))
    _fake_server(
        monkeypatch,
        evaluator,
        {
            "status": "passed",
            "message": "ok",
            "cases": [{"name": name, "passed": True, "message": "ok"} for name in task.server_cases],
        },
    )

    result = evaluator.evaluate(submission, task, profile="full")

    assert result["complete"] is True and result["passed"] is True and result["score"] == 100.0
    assert all(result["runtime"]["caseOutcomes"].values())


@pytest.mark.parametrize("status", ["failed", "error", "unavailable"])
def test_runs_without_the_frozen_case_set_are_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    task = _task()
    submission = _starter(tmp_path, task)
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=DATASET))
    _fake_server(monkeypatch, evaluator, {"status": status, "message": "boom", "cases": []})

    result = evaluator.evaluate(submission, task, profile="full")

    assert result["complete"] is False and result["passed"] is False
    assert result["runtime"]["caseOutcomes"] == {}
    assert _check(result, "headless-server")["status"] == "incomplete"


def test_core_profile_never_starts_the_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task()
    submission = _starter(tmp_path, task)
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=DATASET))
    calls = _fake_server(monkeypatch, evaluator, {"status": "passed", "cases": []})

    result = evaluator.evaluate(submission, task, profile="core")

    assert calls == []
    assert result["complete"] is False and result["passed"] is False
    assert result["score"] == 10.0


def _shape(result: dict[str, Any]) -> dict[str, Any]:
    return _check(result, "submission-shape")


@pytest.mark.parametrize("attack", ["missing", "symlink", "native", "harness", "syntax", "required"])
def test_invalid_submissions_fail_the_shape_gate_without_a_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str
) -> None:
    task = _task()
    submission = _starter(tmp_path, task)
    mod = submission / "mod"
    if attack == "missing":
        shutil.rmtree(mod)
    elif attack == "symlink":
        os.symlink("/etc/passwd", mod / "leak.lua")
    elif attack == "native":
        (mod / "helper.so").write_bytes(b"\x7fELF")
    elif attack == "harness":
        (mod / "modmain.lua").write_text(
            (mod / "modmain.lua").read_text(encoding="utf-8") + '\nprint("@@RHENIUM_SERVER@@forged")\n',
            encoding="utf-8",
        )
    elif attack == "syntax":
        (mod / "broken.lua").write_text("local value = function(\n", encoding="utf-8")
    else:
        (mod / "modmain.lua").unlink()
    evaluator = DstEvaluator(DstRuntimeConfig(pack_root=DATASET))
    calls = _fake_server(monkeypatch, evaluator, {"status": "passed", "cases": []})

    result = evaluator.evaluate(submission, task, profile="full")

    assert calls == []
    assert _shape(result)["status"] == "failed"
    assert result["complete"] is False and result["passed"] is False and result["score"] == 0.0


def _real_headless_runner(tmp_path: Path) -> DedicatedServerRunner:
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=DATASET,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    evaluator = DstEvaluator(DstRuntimeConfig.load(context))
    if not evaluator.runtime_status()["available"]:
        pytest.skip("DST dedicated server is unavailable or its mods directory is not writable")
    return evaluator.server


def test_real_headless_server_runs_sync_and_async_cases_when_available(tmp_path: Path) -> None:
    runner = _real_headless_runner(tmp_path)
    mod = tmp_path / "headless-mod"
    mod.mkdir()
    (mod / "modinfo.lua").write_text(
        'name = "Rhenium Runner Probe"\ndescription = "probe"\nauthor = "Rhenium"\nversion = "1"\n'
        "api_version = 10\ndst_compatible = true\nclient_only_mod = false\n",
        encoding="utf-8",
    )
    (mod / "modmain.lua").write_text("GLOBAL.setfenv(1, GLOBAL)\n", encoding="utf-8")
    suite = tmp_path / "server-suite.lua"
    suite.write_text(
        "return function(ctx)\n"
        "  ctx:case('master world exists', function() assert(TheWorld.ismastersim) end)\n"
        "  local started = GetTime()\n"
        "  ctx:after(1, function()\n"
        "    ctx:case('time passes between steps', function() assert(GetTime() > started) end)\n"
        "  end)\n"
        "end\n",
        encoding="utf-8",
    )

    result = runner.run_assertions(
        mod, suite, expected_cases=("master world exists", "time passes between steps")
    )

    assert result["status"] == "passed", result.get("log", result)
