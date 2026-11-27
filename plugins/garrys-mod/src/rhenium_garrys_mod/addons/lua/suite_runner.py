from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import Any

_MAX_SUBMISSION_FILE_BYTES = 4 * 1024 * 1024
_LUA_MEMORY_BYTES = 64 * 1024 * 1024
_PROCESS_MEMORY_BYTES = 384 * 1024 * 1024
_CPU_SECONDS = 5

_SANDBOX_BOOTSTRAP = r"""
local native_load = load
local read_source = read_submission_source

local function copy_table(source)
    local target = {}
    for key, value in pairs(source) do
        target[key] = value
    end
    return target
end

local safe_globals = {
    assert = assert,
    error = error,
    getmetatable = getmetatable,
    ipairs = ipairs,
    next = next,
    pairs = pairs,
    pcall = pcall,
    rawequal = rawequal,
    rawget = rawget,
    rawlen = rawlen,
    rawset = rawset,
    select = select,
    setmetatable = setmetatable,
    tonumber = tonumber,
    tostring = tostring,
    type = type,
    xpcall = xpcall,
    math = copy_table(math),
    string = copy_table(string),
    table = copy_table(table),
    utf8 = utf8 and copy_table(utf8) or nil,
}

local forbidden_bindings = {
    collectgarbage = true,
    debug = true,
    dofile = true,
    io = true,
    jit = true,
    load = true,
    loadfile = true,
    module = true,
    os = true,
    package = true,
    python = true,
    require = true,
}

local function load_submission_impl(relative, bindings)
    local source = read_source(relative)
    local environment = {}
    for key, value in pairs(safe_globals) do
        if type(value) == "table" then
            environment[key] = copy_table(value)
        else
            environment[key] = value
        end
    end
    if bindings ~= nil then
        assert(type(bindings) == "table", "submission bindings must be a table")
        for key, value in pairs(bindings) do
            assert(type(key) == "string", "submission binding names must be strings")
            assert(not forbidden_bindings[key], "forbidden submission binding: " .. key)
            environment[key] = value
        end
    end
    environment._G = environment
    local chunk, load_error = native_load(source, "@submission/" .. relative, "t", environment)
    if chunk == nil then
        error(load_error, 2)
    end
    return chunk()
end

load_submission = load_submission_impl
read_submission_source = nil

collectgarbage = nil
debug = nil
dofile = nil
io = nil
jit = nil
load = nil
loadfile = nil
module = nil
os = nil
package = nil
python = nil
require = nil
"""


class RunnerInputError(ValueError):
    pass


def _apply_process_limits() -> None:
    """Apply best-effort OS limits in addition to Lua's allocator limit."""
    try:
        import resource
    except ImportError:  # pragma: no cover - resource is present on supported server platforms
        return

    def lower_soft_limit(kind: int, wanted: int) -> None:
        soft, hard = resource.getrlimit(kind)  # type: ignore[attr-defined, unused-ignore]
        new_soft = (
            wanted
            if hard == resource.RLIM_INFINITY  # type: ignore[attr-defined, unused-ignore]
            else min(wanted, hard)
        )
        if soft != resource.RLIM_INFINITY:  # type: ignore[attr-defined, unused-ignore]
            new_soft = min(new_soft, soft)
        resource.setrlimit(kind, (new_soft, hard))  # type: ignore[attr-defined, unused-ignore]

    for name, value in (
        ("RLIMIT_AS", _PROCESS_MEMORY_BYTES),
        ("RLIMIT_DATA", _PROCESS_MEMORY_BYTES),
        ("RLIMIT_FSIZE", 1024 * 1024),
        ("RLIMIT_NOFILE", 32),
        # A CPU-limit kill must not write the private suite's memory to the
        # host core-dump store, and dumping would delay the bounded exit.
        ("RLIMIT_CORE", 0),
    ):
        kind = getattr(resource, name, None)
        if kind is None:
            continue
        with suppress(OSError, ValueError):
            lower_soft_limit(kind, value)

    cpu_kind = getattr(resource, "RLIMIT_CPU", None)
    if cpu_kind is not None:
        try:
            soft, hard = resource.getrlimit(cpu_kind)  # type: ignore[attr-defined, unused-ignore]
            wanted_soft = _CPU_SECONDS
            wanted_hard = _CPU_SECONDS + 1
            if hard != resource.RLIM_INFINITY:  # type: ignore[attr-defined, unused-ignore]
                wanted_soft = min(wanted_soft, hard)
                wanted_hard = min(wanted_hard, hard)
            if soft != resource.RLIM_INFINITY:  # type: ignore[attr-defined, unused-ignore]
                wanted_soft = min(wanted_soft, soft)
            resource.setrlimit(  # type: ignore[attr-defined, unused-ignore]
                cpu_kind, (wanted_soft, wanted_hard)
            )
        except (OSError, ValueError):
            pass

    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.alarm(_CPU_SECONDS + 2)  # type: ignore[attr-defined, unused-ignore]


def _submission_reader(submission: Path) -> Any:
    try:
        root = submission.resolve(strict=True)
    except OSError as error:
        raise RunnerInputError("submission directory does not exist") from error
    if not root.is_dir():
        raise RunnerInputError("submission must be a directory")

    def read_submission_source(relative: object) -> str:
        if not isinstance(relative, str):
            raise RunnerInputError("submission path must be a string")
        if not relative or "\\" in relative:
            raise RunnerInputError("submission path must be normalized relative POSIX path")
        logical = PurePosixPath(relative)
        if (
            logical.is_absolute()
            or ".." in logical.parts
            or logical.as_posix() != relative
            or logical.suffix.lower() != ".lua"
        ):
            raise RunnerInputError("only relative Lua files inside the submission may be loaded")
        try:
            candidate = (root / Path(*logical.parts)).resolve(strict=True)
        except OSError as error:
            raise RunnerInputError(f"submission Lua file is missing: {relative}") from error
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise RunnerInputError("submission path escapes the submission directory")
        try:
            size = candidate.stat().st_size
        except OSError as error:
            raise RunnerInputError(f"submission Lua file cannot be read: {relative}") from error
        if size > _MAX_SUBMISSION_FILE_BYTES:
            raise RunnerInputError(f"submission Lua file is too large: {relative}")
        try:
            return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise RunnerInputError(f"submission Lua file is not valid UTF-8: {relative}") from error

    return read_submission_source


def _deny_python_attributes(_obj: object, attribute: object, _is_setting: bool) -> object:
    raise AttributeError(f"Python attribute access is disabled: {attribute!s}")


def _case_value(case: Any, key: str) -> Any:
    try:
        return case[key]
    except (KeyError, TypeError):
        return None


def _normalise_cases(result: Any) -> list[dict[str, Any]]:
    if result is None:
        raise RunnerInputError("hidden test did not return a result table")
    try:
        raw_cases = result["cases"]
    except (KeyError, TypeError) as error:
        raise RunnerInputError("hidden test result must contain cases") from error
    if raw_cases is None:
        raise RunnerInputError("hidden test result must contain cases")

    cases: list[dict[str, Any]] = []
    index = 1
    while True:
        try:
            raw_case = raw_cases[index]
        except (KeyError, TypeError):
            raw_case = None
        if raw_case is None:
            break
        name = _case_value(raw_case, "name")
        passed = _case_value(raw_case, "passed")
        message = _case_value(raw_case, "message")
        if not isinstance(name, str) or not name.strip():
            raise RunnerInputError(f"hidden behavior case {index} has no valid name")
        if not isinstance(passed, bool):
            raise RunnerInputError(f"hidden behavior case {index} has no boolean passed value")
        if message is None:
            message = ""
        if not isinstance(message, str):
            message = str(message)
        cases.append({"name": name, "passed": passed, "message": message})
        index += 1
    if not cases:
        raise RunnerInputError("hidden test returned no behavior cases")
    return cases


def run(submission: Path, hidden_test: Path) -> dict[str, Any]:
    try:
        hidden_source = hidden_test.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RunnerInputError("hidden test is unavailable") from error

    try:
        from lupa import LuaRuntime  # type: ignore[import-untyped]
    except ImportError as error:  # pragma: no cover - exercised by evaluator error handling
        raise RunnerInputError("lupa is unavailable") from error

    runtime = LuaRuntime(
        encoding="utf-8",
        register_eval=False,
        register_builtins=False,
        attribute_filter=_deny_python_attributes,
        max_memory=_LUA_MEMORY_BYTES,
    )
    deadline = time.monotonic() + _CPU_SECONDS

    def watchdog() -> None:
        if time.monotonic() >= deadline:
            raise TimeoutError("Lua instruction deadline exceeded")

    runtime.globals()["_rhenium_watchdog"] = watchdog
    runtime.execute(
        "local watchdog = _rhenium_watchdog; "
        "debug.sethook(function() watchdog() end, '', 10000); "
        "_rhenium_watchdog = nil"
    )
    runtime.globals()["read_submission_source"] = _submission_reader(submission)
    runtime.execute(_SANDBOX_BOOTSTRAP)
    result = runtime.execute(hidden_source)
    cases = _normalise_cases(result)
    return {
        "status": "passed" if all(case["passed"] for case in cases) else "failed",
        "cases": cases,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Rhenium hidden Lua behavior test")
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True, dest="hidden_test")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    _apply_process_limits()
    try:
        payload = run(arguments.submission, arguments.hidden_test)
        exit_code = 0
    except BaseException as error:
        payload = {"status": "error", "cases": [], "error": str(error) or type(error).__name__}
        exit_code = 1
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
