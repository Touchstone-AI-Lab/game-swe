from __future__ import annotations

import argparse
import json
import re
import traceback
from pathlib import Path, PurePosixPath
from typing import Any

from lua_runner import RunnerInputError, dump_result, run_behavior, run_mock_server


def _safe_file(root: Path, relative: str) -> Path | None:
    logical = PurePosixPath(relative)
    if not relative or logical.is_absolute() or ".." in logical.parts or logical.as_posix() != relative:
        return None
    try:
        candidate = (root / Path(*logical.parts)).resolve(strict=True)
    except OSError:
        return None
    return candidate if candidate.is_relative_to(root) and candidate.is_file() else None


def _strip_lua_comments(source: str) -> str:
    """Remove Lua comments while preserving strings and line positions."""

    output: list[str] = []
    index = 0
    length = len(source)
    quote: str | None = None
    while index < length:
        char = source[index]
        if quote is not None:
            output.append(char)
            if char == "\\" and index + 1 < length:
                index += 1
                output.append(source[index])
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            output.append(char)
            index += 1
            continue
        if source.startswith("--", index):
            long_match = re.match(r"--\[(=*)\[", source[index:])
            if long_match:
                marker = "]" + long_match.group(1) + "]"
                end = source.find(marker, index + long_match.end())
                end = length if end < 0 else end + len(marker)
                segment = source[index:end]
                output.extend("\n" if value == "\n" else " " for value in segment)
                index = end
                continue
            end = source.find("\n", index)
            end = length if end < 0 else end
            output.extend(" " for _ in source[index:end])
            index = end
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _syntax_case(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    lua_files: list[Path] = []
    for candidate in sorted(root.rglob("*.lua")):
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            errors.append(f"unreadable Lua file: {candidate}")
            continue
        if not resolved.is_relative_to(root) or not resolved.is_file():
            errors.append(f"unsafe Lua file: {candidate}")
            continue
        lua_files.append(resolved)

    if not lua_files:
        errors.append("submission contains no Lua files")
    if not errors:
        try:
            from lupa.lua54 import LuaRuntime  # type: ignore[import-untyped]

            runtime = LuaRuntime(encoding="utf-8", register_eval=False, register_builtins=False)
            compile_lua = runtime.eval(
                "function(source, name) local fn, err = load(source, name, 't', {}); "
                "return fn ~= nil, err end"
            )
            for path in lua_files:
                source = path.read_text(encoding="utf-8")
                ok, message = compile_lua(source, "@" + path.relative_to(root).as_posix())
                if not ok:
                    errors.append(str(message))
        except (OSError, UnicodeError, RuntimeError) as error:
            errors.append(str(error))
    return {
        "name": "all Lua source parses under Lua 5.4",
        "passed": not errors,
        "message": f"{len(lua_files)} Lua files" if not errors else "; ".join(errors),
    }


def _manifest_case(root: Path) -> dict[str, Any]:
    path = _safe_file(root, "Info.json")
    error = ""
    if path is None:
        error = "Info.json is missing or unsafe"
    else:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            rules = document.get("InstallRule") if isinstance(document, dict) else None
            valid_rule = isinstance(rules, list) and any(
                isinstance(rule, dict)
                and str(rule.get("Type", "")).lower() == "lua"
                and rule.get("IsServer") is True
                for rule in rules
            )
            if not isinstance(document, dict):
                error = "Info.json must contain an object"
            elif not isinstance(document.get("PackageName"), str) or not document["PackageName"].strip():
                error = "Info.json needs a non-empty PackageName"
            elif not isinstance(document.get("Version"), str) or not document["Version"].strip():
                error = "Info.json needs a non-empty Version"
            elif not valid_rule:
                error = "Info.json needs one Lua InstallRule with IsServer=true"
        except (OSError, UnicodeError, json.JSONDecodeError) as exception:
            error = str(exception)
    return {
        "name": "Palworld server Lua package manifest is valid",
        "passed": not error,
        "message": error if error else "ok",
    }


def _required_file_case(root: Path, required: list[str]) -> dict[str, Any]:
    missing = [relative for relative in required if _safe_file(root, relative) is None]
    return {
        "name": "all required mod files are present",
        "passed": not missing,
        "message": "ok" if not missing else "missing or unsafe: " + ", ".join(missing),
    }


def _implementation_case(root: Path, minimum: int) -> dict[str, Any]:
    total = 0
    for candidate in sorted(root.rglob("*.lua")):
        try:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                continue
            cleaned = _strip_lua_comments(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            continue
        total += sum(1 for line in cleaned.splitlines() if line.strip())
    return {
        "name": "implementation depth matches the authored task",
        "passed": total >= minimum,
        "message": f"{total} non-comment Lua lines; minimum {minimum}",
    }


def _integration_cases(root: Path, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check in checks:
        sources: list[str] = []
        glob = str(check.get("glob", "**/*.lua"))
        for candidate in sorted(root.glob(glob)):
            try:
                resolved = candidate.resolve(strict=True)
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    continue
                source = resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            sources.append(source if resolved.suffix.lower() != ".lua" else _strip_lua_comments(source))
        joined = "\n".join(sources)
        missing_groups: list[str] = []
        for group in check.get("groups", []):
            patterns = group.get("any_of", [])
            if not any(re.search(str(pattern), joined, re.MULTILINE) for pattern in patterns):
                missing_groups.append(str(group.get("name", "unnamed")))
        forbidden = [
            str(pattern)
            for pattern in check.get("none_of", [])
            if re.search(str(pattern), joined, re.MULTILINE)
        ]
        passed = bool(sources) and not missing_groups and not forbidden
        details: list[str] = []
        if not sources:
            details.append(f"no files matched {glob}")
        if missing_groups:
            details.append("missing groups: " + ", ".join(missing_groups))
        if forbidden:
            details.append("forbidden patterns: " + ", ".join(forbidden))
        results.append(
            {
                "name": "integration contract: " + str(check.get("id", "unknown")),
                "passed": passed,
                "message": "ok" if passed else "; ".join(details),
            }
        )
    return results


def verify(
    submission: Path,
    spec_path: Path,
    behavior_path: Path,
    server_path: Path,
) -> dict[str, Any]:
    root = submission.resolve(strict=True)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = [
        _required_file_case(root, list(spec["required_files"])),
        _syntax_case(root),
        _manifest_case(root),
        _implementation_case(root, int(spec["minimum_lua_lines"])),
    ]
    cases.extend(_integration_cases(root, list(spec["integration_checks"])))

    behavior = run_behavior(root, behavior_path)
    cases.extend(
        {
            "name": "core behavior: " + case["name"],
            "passed": case["passed"],
            "message": case["message"],
        }
        for case in behavior["cases"]
    )

    server = run_mock_server(root, server_path)
    cases.extend(
        {
            "name": "simulated UE4SS: " + case["name"],
            "passed": case["passed"],
            "message": case["message"],
        }
        for case in server["cases"]
    )
    if server.get("status") == "error":
        cases.append(
            {
                "name": "simulated UE4SS suite completed",
                "passed": False,
                "message": str(server.get("error") or "unknown runner error"),
            }
        )
    passed = bool(cases) and all(case["passed"] for case in cases)
    return {
        "status": "passed" if passed else "failed",
        "passed": sum(case["passed"] for case in cases),
        "failed": sum(not case["passed"] for case in cases),
        "cases": cases,
        "verification_profile": "lua-5.4-plus-simulated-ue4ss",
        "lua_runtime_version": behavior.get("lua_runtime_version", "unknown"),
        "real_palworld_server_ran": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify one Palworld Harbor task submission")
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--behavior", type=Path, required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    arguments.logs.mkdir(parents=True, exist_ok=True)
    result_path = arguments.logs / "result.json"
    reward_path = arguments.logs / "reward.txt"
    try:
        payload = verify(
            arguments.submission,
            arguments.spec,
            arguments.behavior,
            arguments.server,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, RunnerInputError) as error:
        payload = {
            "status": "error",
            "passed": 0,
            "failed": 1,
            "error": str(error) or type(error).__name__,
            "cases": [],
            "verification_profile": "lua-5.4-plus-simulated-ue4ss",
            "lua_runtime_version": "unknown",
            "real_palworld_server_ran": False,
        }
    except BaseException as error:  # fail closed and retain a diagnostic for task authors
        payload = {
            "status": "error",
            "passed": 0,
            "failed": 1,
            "error": str(error) or type(error).__name__,
            "traceback": traceback.format_exc(),
            "cases": [],
            "verification_profile": "lua-5.4-plus-simulated-ue4ss",
            "lua_runtime_version": "unknown",
            "real_palworld_server_ran": False,
        }
    result_path.write_text(dump_result(payload), encoding="utf-8")
    reward = 1 if payload.get("status") == "passed" else 0
    reward_path.write_text(f"{reward}\n", encoding="utf-8")
    print(
        f"status={payload.get('status')} passed={payload.get('passed', 0)} failed={payload.get('failed', 0)}"
    )
    for case in payload.get("cases", []):
        label = "PASS" if case.get("passed") else "FAIL"
        print(f"[{label}] {case.get('name')}: {case.get('message', '')}")
    if payload.get("error"):
        print(f"[ERROR] {payload['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
