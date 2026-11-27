#!/usr/bin/env python3
"""Patch GLuaTest's mutable result hook and collect its private audit report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

COLLECTOR = "gcb-patched-gluatest-runner-v2"
RUNNER_RESULTS = "TestRunner.results = {}\n"
OLD_ADD_RESULT = '''function TestRunner:AddResult( result )
    hook.Run( "GLuaTest_LogTestResult", result )
    table.insert( self.results, result )

    LogTestResult( result )
    if result.success == false then LogTestFailureDetails( result ) end
end'''
OLD_COMPLETE = '''function TestRunner:Complete( testGroups )
    local duration = SysTime() - self.startTime

    hook.Run( "GLuaTest_Finished", testGroups, self.results, duration )

    -- Some logs may be printed after our completion message, we need to wait a bit
    timer.Simple( 0.1, function()
        LogTestsComplete( testGroups, self.results, duration )
    end )
end'''


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"pinned GLuaTest {label} does not match the reviewed source")
    return text.replace(old, new, 1)


def _harness_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.lua"), key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def patch_runner(path: Path, nonce: str) -> None:
    if re.fullmatch(r"[0-9a-f]{48}", nonce) is None:
        raise ValueError("audit nonce must be 24 random bytes encoded as lowercase hex")

    text = path.read_text(encoding="utf-8")
    declaration = f'''TestRunner.results = {{}}

-- GameCodeBench private audit state. This table is populated before any public
-- GLuaTest result hook runs and is never passed to a submission-visible hook.
local GCB_AUDIT_NONCE = "{nonce}"
local GCB_AUDIT_RESULTS = {{}}
local GCB_AUDIT_LOG = MsgN
local GCB_AUDIT_JSON = util.TableToJSON
'''
    add_result = '''function TestRunner:AddResult( result )
    local auditStatus = result.success == true and "passed"
        or result.success == false and "failed"
        or result.empty and "empty"
        or result.skipped and "skipped"
        or "invalid"
    GCB_AUDIT_RESULTS[ #GCB_AUDIT_RESULTS + 1 ] = {
        id = result.case.name,
        status = auditStatus
    }
    GCB_AUDIT_LOG( "[GCB_AUDIT_CASE_V2] " .. GCB_AUDIT_NONCE .. " "
        .. GCB_AUDIT_JSON( GCB_AUDIT_RESULTS[ #GCB_AUDIT_RESULTS ] ) )

    table.insert( self.results, result )
    LogTestResult( result )
    if result.success == false then LogTestFailureDetails( result ) end

    -- Extensions retain a notification, but receive a detached public view only
    -- after the authoritative result has been recorded and logged.
    hook.Run( "GLuaTest_LogTestResult", {
        case = { name = result.case.name },
        success = result.success,
        empty = result.empty,
        skipped = result.skipped
    } )
end'''
    complete = f'''function TestRunner:Complete( testGroups )
    local duration = SysTime() - self.startTime
    -- Do not expose self.results: GLuaTest prints its summary after this hook, so
    -- mutating the live table here used to rewrite the authoritative transcript.
    local publicResults = {{}}
    for index, audit in ipairs( GCB_AUDIT_RESULTS ) do
        publicResults[ index ] = {{
            case = {{ name = audit.id }},
            success = audit.status == "passed",
            empty = audit.status == "empty",
            skipped = audit.status == "skipped"
        }}
    end
    hook.Run( "GLuaTest_Finished", testGroups, publicResults, duration )
    GCB_AUDIT_LOG( "[GCB_AUDIT_COMPLETE_V2] " .. GCB_AUDIT_NONCE
        .. " {COLLECTOR}" )

    -- Some logs may be printed after our completion message, we need to wait a bit
    timer.Simple( 0.1, function()
        LogTestsComplete( testGroups, self.results, duration )
    end )
end'''
    text = _replace_once(text, RUNNER_RESULTS, declaration, "result declaration")
    text = _replace_once(text, OLD_ADD_RESULT, add_result, "AddResult implementation")
    text = _replace_once(text, OLD_COMPLETE, complete, "Complete implementation")
    text = _replace_once(
        text,
        '    hook.Run( "GLuaTest_StartedTestRun", testGroups )',
        "    -- Private evaluation does not expose mutable test groups to extensions.",
        "StartedTestRun hook",
    )
    path.write_text(text, encoding="utf-8")

    root = path.parent.parent
    line_replacements = {
        root / "init.lua": (
            '    hook.Run( "GLuaTest_AddTestPaths", testPaths )',
            '    hook.Run( "GLuaTest_RunTestFiles", testFiles )',
        ),
        root / "loader.lua": ('    hook.Run( "GLuaTest_TestGroupLoaded", group, testGroup )',),
        root / "expectations" / "expect.lua": (
            '    hook.Run( "GLuaTest_CreateExpect", expect )',
        ),
        root / "runner" / "helpers.lua": (
            '    hook.Run( "GLuaTest_EnvCreated", testTools, meta, cleanup )',
            '    hook.Run( "GLuaTest_AsyncEnvCreated", asyncEnv, meta, cleanup )',
            '    hook.Run( "GLuaTest_CaseStateCreated", state, meta, testGroupState )',
        ),
        root / "stubs" / "stub_maker.lua": (
            '        hook.Run( "GLuaTest_CreateStub", stubTbl, meta, tbl, key )',
        ),
        root / "runner" / "colors.lua": ('hook.Run( "GLuaTest_MakeColors", colors )',),
        root / "runner" / "log_helpers.lua": (
            'hook.Run( "GLuaTest_MakeLogHelpers", LogHelpers )',
        ),
        root / "runner" / "logger.lua": (
            'hook.Run( "GLuaTest_MakeResultLogger", ResultLogger )',
        ),
    }
    replacement = "-- GameCodeBench disables this mutable extension hook during private evaluation."
    for target, needles in line_replacements.items():
        source = target.read_text(encoding="utf-8")
        for needle in needles:
            source = _replace_once(source, needle, replacement, f"{target.name} extension hook")
        target.write_text(source, encoding="utf-8")

    case_runner = root / "runner" / "test_case_runner.lua"
    source = case_runner.read_text(encoding="utf-8")
    source = _replace_once(
        source,
        '''        local canRun = hook.Run( "GLuaTest_CanRunTestCase", TestGroupRunner.group, case )
        if canRun == nil then canRun = true end
        if not canRun then return false end''',
        "        -- Private cases cannot be skipped by submission-installed hooks.",
        "CanRunTestCase hook",
    )
    case_runner.write_text(source, encoding="utf-8")
    print(_harness_sha256(root))


def _count_line(text: str, value: str) -> int:
    return sum(line == value for line in text.splitlines())


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def collect(args: argparse.Namespace) -> None:
    expected_cases: list[str] = args.case
    expected_count = len(expected_cases)
    fatal: str | None = None
    audit_cases: list[dict[str, Any]] = []

    log = re.sub(r"\x1b\[[0-9;]*m", "", _read_text(args.server_log))
    case_prefix = f"[GCB_AUDIT_CASE_V2] {args.nonce} "
    audit_lines = [line for line in log.splitlines() if line.startswith(case_prefix)]
    complete_line = f"[GCB_AUDIT_COMPLETE_V2] {args.nonce} {COLLECTOR}"
    complete_lines = [line for line in log.splitlines() if line == complete_line]
    for line in audit_lines:
        try:
            loaded = json.loads(line[len(case_prefix) :])
            if not (
                isinstance(loaded, dict)
                and isinstance(loaded.get("id"), str)
                and loaded.get("status")
                in {"passed", "failed", "empty", "skipped", "invalid"}
            ):
                fatal = "INVALID_AUDIT_REPORT"
                continue
            audit_cases.append({"id": loaded["id"], "status": loaded["status"]})
        except json.JSONDecodeError:
            fatal = "INVALID_AUDIT_REPORT"

    ids = [case["id"] for case in audit_cases]
    duplicate_count = sum(count - 1 for count in Counter(ids).values() if count > 1)
    case_set_matches = Counter(ids) == Counter(expected_cases)
    nonce_matches = bool(audit_lines) and len(complete_lines) == 1
    collector_matches = len(complete_lines) == 1
    audit_complete = len(complete_lines) == 1
    harness_unchanged = _harness_sha256(args.harness_root) == args.harness_sha256
    clean_exit = _read_text(args.clean_exit).strip() == "true"
    debug_log = args.debug_log.is_file() and args.debug_log.stat().st_size > 0

    no_failures = _count_line(log, "No test failures detected")
    failures_written = sum(
        "test failures detected, writing to log" in line for line in log.splitlines()
    )

    passed = sum(case["status"] == "passed" for case in audit_cases)
    assertion_failures = sum(case["status"] == "failed" for case in audit_cases)
    empty = sum(case["status"] == "empty" for case in audit_cases)
    skipped = sum(case["status"] == "skipped" for case in audit_cases)
    invalid_results = sum(case["status"] == "invalid" for case in audit_cases)
    failed = expected_count - passed if case_set_matches else 0

    if args.status == 124 or args.status >= 128 or args.status not in {0, 1}:
        fatal = fatal or "INVALID_RUNTIME_TERMINATED"
    elif not harness_unchanged:
        fatal = fatal or "INVALID_RUNNER_MODIFIED"
    elif debug_log:
        fatal = fatal or "INVALID_RUNTIME_CRASHED"
    elif not clean_exit:
        fatal = fatal or "INVALID_RUN_DID_NOT_EXIT_CLEANLY"
    elif not collector_matches or not nonce_matches or not audit_complete:
        fatal = fatal or "INVALID_AUDIT_REPORT"
    elif duplicate_count or not case_set_matches or len(audit_cases) != expected_count:
        fatal = fatal or "INVALID_SUITE_CASE_SET"
    elif invalid_results:
        fatal = fatal or "INVALID_AUDIT_RESULT"
    elif empty or skipped:
        fatal = fatal or "INVALID_INCOMPLETE_RESULTS"
    elif (
        assertion_failures > 0
        and failures_written != 1
        or assertion_failures == 0
        and failures_written != 0
    ):
        fatal = fatal or "INVALID_FAILURE_REPORT"
    elif assertion_failures == 0 and no_failures != 1:
        fatal = fatal or "INVALID_TERMINAL_VERDICT"

    complete = fatal is None
    reward = int(complete and passed == expected_count and failed == 0 and empty == 0 and skipped == 0)
    result = {
        "schema": 2,
        "collector": COLLECTOR,
        "expected": expected_count,
        "passed": passed if case_set_matches else 0,
        "failed": failed,
        "reward": reward,
        "complete": complete,
        "fatal": fatal,
        "entrypoint_status": args.status,
        "markers": {
            "audit_nonce_match": nonce_matches,
            "audit_complete": audit_complete,
            "audit_line_count": len(audit_lines),
            "audit_complete_line_count": len(complete_lines),
            "audit_case_count": len(audit_cases),
            "audit_duplicate_cases": duplicate_count,
            "harness_unchanged": harness_unchanged,
            "clean_exit": clean_exit,
            "debug_log": debug_log,
            "no_failures_verdict": no_failures,
            "failures_written": failures_written,
            "empty_results": empty,
            "skipped_results": skipped,
        },
        "cases": audit_cases,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.reward.write_text(f"{reward}\n", encoding="utf-8")
    print(
        f"entrypoint_exit={args.status} passed={result['passed']} failed={failed} "
        f"expected={expected_count} reward={reward} {fatal or ''}".rstrip()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    patch = subparsers.add_parser("patch")
    patch.add_argument("runner", type=Path)
    patch.add_argument("nonce")

    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--server-log", type=Path, required=True)
    collect_parser.add_argument("--clean-exit", type=Path, required=True)
    collect_parser.add_argument("--debug-log", type=Path, required=True)
    collect_parser.add_argument("--harness-root", type=Path, required=True)
    collect_parser.add_argument("--harness-sha256", required=True)
    collect_parser.add_argument("--status", type=int, required=True)
    collect_parser.add_argument("--nonce", required=True)
    collect_parser.add_argument("--result", type=Path, required=True)
    collect_parser.add_argument("--reward", type=Path, required=True)
    collect_parser.add_argument("--case", action="append", default=[])

    args = parser.parse_args()
    if args.command == "patch":
        patch_runner(args.runner, args.nonce)
    else:
        collect(args)


if __name__ == "__main__":
    main()
