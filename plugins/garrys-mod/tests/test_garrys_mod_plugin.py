from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog, expected_case_count
from rhenium_garrys_mod.darkrp.evaluator import GarrysModEvaluator
from rhenium_garrys_mod.plugin import GarrysModBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "darkrp-core"
TASK_IDS = {
    "darkrp-release-regressions-v3",
    "darkrp-live-server-regressions",
    "darkrp-door-economy-regressions",
    "darkrp-core-library-regressions",
    "darkrp-registration-regressions",
    "darkrp-money-regressions",
    "darkrp-persistence-regressions",
}


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def test_catalog_exposes_the_three_validated_tasks() -> None:
    catalog = GarrysModCatalog.load(PACK)

    assert catalog.game == "garrys-mod"
    assert {task.id for task in catalog.tasks} == TASK_IDS
    assert {task.task_kind for task in catalog.tasks} == {"debugging"}
    assert all(task.source_mod == "DarkRP" for task in catalog.tasks)
    assert all(task.authored_prompt.startswith("# DarkRP") for task in catalog.tasks)


def test_every_task_declares_exactly_one_expected_case_count() -> None:
    catalog = GarrysModCatalog.load(PACK)

    for task in catalog.tasks:
        assert expected_case_count(PACK, task) >= 8


def test_materialized_attempt_carries_source_but_no_private_assets(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    catalog = plugin.load_catalog(PACK, "catalog.json")
    task = next(task for task in catalog.tasks if task.id == "darkrp-live-server-regressions")
    destination = tmp_path / "attempt"
    destination.mkdir()

    plugin.materialize_attempt(task, destination, _context(tmp_path))

    assert (destination / "darkrp" / "gamemode" / "init.lua").is_file()
    assert (destination / "EXAM.md").is_file()
    assert not (destination / "tests").exists()
    assert not (destination / "solution").exists()
    assert "/app/darkrp" not in (destination / "EXAM.md").read_text(encoding="utf-8")


def test_exam_never_states_the_defect_count_or_a_diagnosis(tmp_path: Path) -> None:
    del tmp_path
    for task_id in TASK_IDS:
        exam = (PACK / "exams" / f"{task_id}.md").read_text(encoding="utf-8")
        lowered = exam.lower()
        assert "defect group" not in lowered
        assert "root cause" not in lowered


def test_verdict_trust_check_rejects_forged_or_duplicated_markers() -> None:
    good_markers = {
        "audit_nonce_match": True,
        "audit_complete": True,
        "audit_line_count": 2,
        "audit_complete_line_count": 1,
        "audit_case_count": 2,
        "audit_duplicate_cases": 0,
        "harness_unchanged": True,
        "clean_exit": True,
        "debug_log": False,
        "no_failures_verdict": 1,
        "failures_written": 0,
        "empty_results": 0,
        "skipped_results": 0,
    }
    cases = [
        {"id": "one", "status": "passed"},
        {"id": "two", "status": "passed"},
    ]
    verdict = {
        "schema": 2,
        "collector": "gcb-patched-gluatest-runner-v2",
        "expected": 2,
        "passed": 2,
        "failed": 0,
        "reward": 1,
        "complete": True,
        "markers": good_markers,
        "cases": cases,
        "fatal": None,
    }
    trusted = GarrysModEvaluator._verdict_is_trustworthy
    assert trusted(verdict, ("one", "two"))

    forged = {**verdict, "markers": {**good_markers, "audit_line_count": 3}}
    assert not trusted(forged, ("one", "two"))

    silent = {**verdict, "markers": {**good_markers, "audit_nonce_match": False}}
    assert not trusted(silent, ("one", "two"))

    duplicated = {**verdict, "cases": [cases[0], cases[0]]}
    assert not trusted(duplicated, ("one", "two"))

    terminated = {**verdict, "complete": False, "fatal": "INVALID_RUNTIME_TERMINATED"}
    assert not trusted(terminated, ("one", "two"))


def test_static_check_rejects_the_mutable_result_hook_attack(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    catalog = GarrysModCatalog.load(PACK)
    task = next(task for task in catalog.tasks if task.id == "darkrp-live-server-regressions")
    submission = tmp_path / "submission"
    plugin.materialize_starter(task, submission, _context(tmp_path))

    safe, _check = GarrysModEvaluator._static_check(submission, task)
    assert safe

    init = submission / "darkrp" / "gamemode" / "init.lua"
    init.write_text(
        init.read_text(encoding="utf-8")
        + '\nhook.Add("GLuaTest_LogTestResult", "forge", function(result) '
        + "result.success = true end)\n",
        encoding="utf-8",
    )
    safe, check = GarrysModEvaluator._static_check(submission, task)
    assert not safe
    assert check["message"] == "submission attempts to alter the private result harness"


def test_verifier_case_list_matches_its_suite_exactly() -> None:
    """The verifier grades by case name, so drift between the two silently fails a
    correct submission. This caught a real mismatch: a case was renamed in the suite
    while the verifier kept the old name, and a passing oracle scored zero."""
    import re

    for task_id in TASK_IDS:
        tests = PACK / "private" / "harbor" / task_id / "tests"
        verifier = (tests / "test.sh").read_text(encoding="utf-8")
        suite = (tests / "suite.lua").read_text(encoding="utf-8")

        block = re.search(r"EXPECTED_CASES=\((.*?)\n\)", verifier, re.S)
        assert block is not None, f"{task_id} verifier declares no case list"
        listed = re.findall(r'^\s*"(.*)"\s*$', block.group(1), re.M)
        declared = re.findall(r'^EXPECTED=([0-9]+)$', verifier, re.M)

        # Only a table constructor that OPENS a line declares a case. A bare
        # `name = "..."` also occurs inside test data -- a suite that feeds DarkRP a
        # malformed declaration writes `{ name = "..." }` as the fixture -- and
        # counting those as cases makes this guard fire on a correct suite. The
        # comment branch is needed because a case may carry a leading `-- comment`
        # between the brace and the name.
        suite_names = re.findall(
            r'^[ \t]*\{(?:\s|--[^\n]*)*name\s*=\s*"((?:[^"\\]|\\.)*)"', suite, re.M
        )
        assert listed == suite_names, f"{task_id}: verifier case list has drifted from the suite"
        assert declared == [str(len(suite_names))], f"{task_id}: EXPECTED does not match the suite"


def test_every_graded_defect_group_is_publicly_reported() -> None:
    """A defect the prompt never reports cannot be fixed by a submission that does
    everything it was asked, so grading one is unfair and makes a full score
    unreachable. This caught a real gap before it shipped: a task was extended from
    eight defect groups to eleven -- suite, EXPECTED and the per-defect matrix all
    followed -- but instruction.md was not, so three groups were graded silently.

    Case names carry their group letter ("A: ...", "AA: ..."); a case with no letter
    prefix is a sentinel or a positive control and belongs to no group.
    """
    import re

    for task_id in TASK_IDS:
        task = PACK / "private" / "harbor" / task_id
        instruction = (task / "instruction.md").read_text(encoding="utf-8")
        suite = (task / "tests" / "suite.lua").read_text(encoding="utf-8")

        reports = set(re.findall(r"\*\*\[#(\d+)\]\*\*", instruction))
        names = re.findall(
            r'^[ \t]*\{(?:\s|--[^\n]*)*name\s*=\s*"((?:[^"\\]|\\.)*)"', suite, re.M
        )
        groups = {m.group(1) for n in names if (m := re.match(r"([A-Z]{1,2}):", n))}

        assert reports, f"{task_id}: instruction.md carries no numbered reports"
        assert len(reports) == len(groups), (
            f"{task_id}: {len(reports)} public reports but {len(groups)} graded defect "
            f"groups ({''.join(sorted(groups))}) -- every graded group needs a report"
        )


def test_every_verifier_uses_the_same_private_runner_collector() -> None:
    collector_hashes: set[str] = set()
    for task_id in TASK_IDS:
        tests = PACK / "private" / "harbor" / task_id / "tests"
        collector = (tests / "trusted_collector.py").read_bytes()
        collector_hashes.add(hashlib.sha256(collector).hexdigest())
        verifier = (tests / "test.sh").read_text(encoding="utf-8")
        assert "trusted_collector.py patch" in verifier
        assert "TIMEOUT=2" in verifier
        assert "@@GCB_NONCE@@" not in (tests / "suite.lua").read_text(encoding="utf-8")
    assert len(collector_hashes) == 1


def test_private_runner_patch_covers_mutable_gluatest_extension_hooks() -> None:
    collector = (
        PACK
        / "private"
        / "harbor"
        / "darkrp-door-economy-regressions"
        / "tests"
        / "trusted_collector.py"
    ).read_text(encoding="utf-8")
    disabled_hooks = {
        "GLuaTest_StartedTestRun",
        "GLuaTest_AddTestPaths",
        "GLuaTest_RunTestFiles",
        "GLuaTest_TestGroupLoaded",
        "GLuaTest_CreateExpect",
        "GLuaTest_EnvCreated",
        "GLuaTest_AsyncEnvCreated",
        "GLuaTest_CaseStateCreated",
        "GLuaTest_CanRunTestCase",
        "GLuaTest_CreateStub",
        "GLuaTest_MakeColors",
        "GLuaTest_MakeLogHelpers",
        "GLuaTest_MakeResultLogger",
    }
    assert all(hook_name in collector for hook_name in disabled_hooks)
    assert 'hook.Run( "GLuaTest_Finished", testGroups, publicResults, duration )' in collector
    assert 'hook.Run( "GLuaTest_Finished", testGroups, self.results, duration )' in collector
    assert "GCB_AUDIT_RESULTS[ #GCB_AUDIT_RESULTS + 1 ]" in collector


def _run_collector(
    tmp_path: Path,
    *,
    cases: list[dict[str, str]],
    status: int,
    terminal_lines: list[str],
    duplicate_audit: bool = False,
) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    task_tests = (
        PACK / "private" / "harbor" / "darkrp-door-economy-regressions" / "tests"
    )
    collector = task_tests / "trusted_collector.py"
    nonce = "0123456789abcdef0123456789abcdef0123456789abcdef"
    audit_lines = [
        f"[GCB_AUDIT_CASE_V2] {nonce} {json.dumps(case, separators=(',', ':'))}"
        for case in cases
    ]
    complete_line = f"[GCB_AUDIT_COMPLETE_V2] {nonce} gcb-patched-gluatest-runner-v2"
    lines = [*audit_lines, complete_line, *terminal_lines]
    if duplicate_audit:
        lines.append(audit_lines[0])

    server_log = tmp_path / "server.log"
    server_log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean_exit = tmp_path / "clean-exit.txt"
    clean_exit.write_text("true\n", encoding="utf-8")
    harness = tmp_path / "harness"
    harness.mkdir(parents=True)
    runner = harness / "runner.lua"
    runner.write_text("trusted patched runner\n", encoding="utf-8")
    harness_digest = hashlib.sha256()
    harness_digest.update(b"runner.lua\0")
    harness_digest.update(runner.read_bytes())
    harness_digest.update(b"\0")
    result = tmp_path / "result.json"
    reward = tmp_path / "reward.txt"
    command = [
        sys.executable,
        str(collector),
        "collect",
        "--server-log",
        str(server_log),
        "--clean-exit",
        str(clean_exit),
        "--debug-log",
        str(tmp_path / "debug.log"),
        "--harness-root",
        str(harness),
        "--harness-sha256",
        harness_digest.hexdigest(),
        "--status",
        str(status),
        "--nonce",
        nonce,
        "--result",
        str(result),
        "--reward",
        str(reward),
    ]
    for case in cases:
        command.extend(("--case", case["id"]))
    subprocess.run(command, check=True, capture_output=True, text=True)
    loaded = json.loads(result.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_private_audit_ignores_finished_hook_summary_mutation(tmp_path: Path) -> None:
    result = _run_collector(
        tmp_path,
        cases=[{"id": "one", "status": "failed"}, {"id": "two", "status": "passed"}],
        status=1,
        terminal_lines=[
            "1 test failures detected, writing to log..",
            "[GLuaTest] | PASS: 2",
            "[GLuaTest] | FAIL: 0",
        ],
    )

    assert result["complete"] is True
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["reward"] == 0


def test_private_audit_rejects_duplicate_output_and_abnormal_exit(tmp_path: Path) -> None:
    cases = [{"id": "one", "status": "passed"}, {"id": "two", "status": "passed"}]
    duplicated = _run_collector(
        tmp_path / "duplicate",
        cases=cases,
        status=1,
        terminal_lines=["No test failures detected"],
        duplicate_audit=True,
    )
    assert duplicated["complete"] is False
    assert duplicated["fatal"] == "INVALID_SUITE_CASE_SET"

    terminated = _run_collector(
        tmp_path / "terminated",
        cases=cases,
        status=2,
        terminal_lines=["No test failures detected"],
    )
    assert terminated["complete"] is False
    assert terminated["fatal"] == "INVALID_RUNTIME_TERMINATED"

    skipped = _run_collector(
        tmp_path / "skipped",
        cases=[
            {"id": "one", "status": "passed"},
            {"id": "two", "status": "skipped"},
        ],
        status=0,
        terminal_lines=["No test failures detected"],
    )
    assert skipped["complete"] is False
    assert skipped["fatal"] == "INVALID_INCOMPLETE_RESULTS"


def test_submission_sync_does_not_require_chown(tmp_path: Path) -> None:
    """The evaluator container drops all capabilities. `rsync -a` implies -o/-g, whose
    chown then fails with EPERM on every path; rsync exits 23 and `set -e` kills the run
    before any test executes. This was caught only by running the plugin end to end."""
    from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog
    from rhenium_garrys_mod.darkrp.evaluator import GarrysModRuntime

    catalog = GarrysModCatalog.load(PACK)
    runtime = GarrysModRuntime(_context(tmp_path), catalog)
    task = next(task for task in catalog.tasks if task.id == "darkrp-live-server-regressions")

    import subprocess

    recorded: list[list[str]] = []

    def capture(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        recorded.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    runtime._docker = capture  # type: ignore[method-assign]
    runtime.run(task, tmp_path, tmp_path / "logs", "sha256:deadbeef")

    assert recorded, "the evaluator did not invoke docker"
    command = recorded[0][-1]
    assert "rsync -rlptD --delete" in command
    assert "rsync -a" not in command
    assert "--cap-drop=ALL" in recorded[0]
    assert "--network=none" in recorded[0]
    # Only the capabilities the dedicated-server entrypoint needs to stage its own
    # game tree are added back; anything broader would weaken the sandbox.
    added = {a.split("=", 1)[1] for a in recorded[0] if a.startswith("--cap-add=")}
    assert added == {"CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID", "SETGID", "SETUID"}


def test_verifier_log_directory_is_writable_by_a_capability_dropped_container(
    tmp_path: Path,
) -> None:
    """The container drops all capabilities, so its root has no CAP_DAC_OVERRIDE and
    cannot create a directory inside a bind mount owned by the host user. Without this
    the verifier's first `mkdir -p /logs/verifier` fails and nothing runs at all."""
    import subprocess

    from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog
    from rhenium_garrys_mod.darkrp.evaluator import GarrysModRuntime

    catalog = GarrysModCatalog.load(PACK)
    runtime = GarrysModRuntime(_context(tmp_path), catalog)
    task = next(task for task in catalog.tasks if task.id == "darkrp-live-server-regressions")

    def capture(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        return subprocess.CompletedProcess(arguments, 0, "", "")

    runtime._docker = capture  # type: ignore[method-assign]
    logs = tmp_path / "logs"
    logs.mkdir()
    runtime.run(task, tmp_path, logs, "sha256:deadbeef")

    verifier = logs / "verifier"
    assert verifier.is_dir()
    assert verifier.stat().st_mode & 0o777 == 0o777


def test_case_outcomes_are_reported_only_for_an_exact_case_set() -> None:
    expected = ("sentinel: loaded", "A: first", "A: second")
    verdict = {
        "cases": [
            {"id": "sentinel: loaded", "status": "passed"},
            {"id": "A: first", "status": "failed"},
            {"id": "A: second", "status": "passed"},
        ]
    }
    outcomes = GarrysModEvaluator._case_outcomes

    assert outcomes(verdict, expected, 2) == {
        "sentinel: loaded": True, "A: first": False, "A: second": True,
    }
    assert outcomes(verdict, expected, 3) == {}, "passed count must match the audited statuses"
    assert outcomes(verdict, (*expected, "B: missing"), 2) == {}
    assert outcomes({"cases": [*verdict["cases"], verdict["cases"][0]]}, expected, 2) == {}
    assert outcomes({"cases": [{"id": 7, "status": "passed"}]}, expected, 1) == {}
    assert outcomes(None, expected, 0) == {}
    skipped = {"cases": [{"id": name, "status": "skipped"} for name in expected]}
    assert outcomes(skipped, expected, 0) == dict.fromkeys(expected, False)


def test_clean_room_synth_pack_is_served_by_the_gluatest_task_model(tmp_path: Path) -> None:
    from rhenium_garrys_mod.plugin import GarrysModBenchmarkPlugin

    pack = tmp_path / "garrys-mod-synth"
    pack.mkdir()
    (pack / "catalog.json").write_text('{"id": "garrys-mod-clean-room-synth"}', encoding="utf-8")
    assert GarrysModBenchmarkPlugin._catalog_id(pack) == "garrys-mod-clean-room-synth"
    (pack / "catalog.json").write_text('{"id": "somebody-elses-pack"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported Garry's Mod catalog"):
        GarrysModBenchmarkPlugin._catalog_id(pack)
