from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

MAX_SUBMISSION_FILE_BYTES = 4 * 1024 * 1024
LUA_MEMORY_BYTES = 64 * 1024 * 1024
CPU_SECONDS = 8


class RunnerInputError(ValueError):
    """Raised when a submission or private suite cannot be evaluated safely."""


def _deny_python_attributes(_obj: object, attribute: object, _is_setting: bool) -> object:
    raise AttributeError(f"Python attribute access is disabled: {attribute!s}")


def _submission_reader(submission: Path) -> Callable[[object], str]:
    try:
        root = submission.resolve(strict=True)
    except OSError as error:
        raise RunnerInputError("submission directory does not exist") from error
    if not root.is_dir():
        raise RunnerInputError("submission must be a directory")

    def read_submission_source(relative: object) -> str:
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise RunnerInputError("submission path must be a normalized relative POSIX path")
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
        if candidate.stat().st_size > MAX_SUBMISSION_FILE_BYTES:
            raise RunnerInputError(f"submission Lua file is too large: {relative}")
        try:
            return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise RunnerInputError(f"submission Lua file is not valid UTF-8: {relative}") from error

    return read_submission_source


_BEHAVIOR_BOOTSTRAP = r"""
local native_load = load
local read_source = read_submission_source
local native_debug = debug
local native_clock = os and os.clock
local native_getmetatable = getmetatable

if native_debug ~= nil and native_debug.sethook ~= nil and native_clock ~= nil then
    local deadline = native_clock() + __TIME_LIMIT__
    native_debug.sethook(function()
        if native_clock() > deadline then
            error("submission exceeded its time limit", 0)
        end
    end, "", 1000000)
end

local function copy_table(source)
    local target = {}
    for key, value in pairs(source) do target[key] = value end
    return target
end

local function safe_getmetatable(value)
    if type(value) ~= "table" then return nil end
    return native_getmetatable(value)
end

local safe_globals = {
    assert = assert,
    error = error,
    getmetatable = safe_getmetatable,
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
        environment[key] = type(value) == "table" and copy_table(value) or value
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
    if chunk == nil then error(load_error, 2) end
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


_SERVER_BOOTSTRAP = r"""
local native_load = load
local read_source = read_submission_source
local native_debug = debug
local native_clock = os and os.clock
local native_getmetatable = getmetatable

if native_debug ~= nil and native_debug.sethook ~= nil and native_clock ~= nil then
    local deadline = native_clock() + __TIME_LIMIT__
    native_debug.sethook(function()
        if native_clock() > deadline then
            error("submission exceeded its time limit", 0)
        end
    end, "", 1000000)
end

local function copy_table(source)
    local target = {}
    for key, value in pairs(source) do target[key] = value end
    return target
end

local function safe_getmetatable(value)
    if type(value) ~= "table" then return nil end
    return native_getmetatable(value)
end

local base = {
    assert = assert,
    error = error,
    getmetatable = safe_getmetatable,
    ipairs = ipairs,
    next = next,
    pairs = pairs,
    pcall = pcall,
    print = function(...) end,
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
    os = {
        clock = function() return 100 end,
        time = function() return 100 end,
        difftime = os and os.difftime or function(a, b) return a - b end,
    },
}

local function install_ue4ss(environment)
    local fake_object = {}
    setmetatable(fake_object, {
        __index = function(_, key)
            if key == "IsValid" then return function() return true end end
            if key == "get" then return function() return fake_object end end
            if key == "Log" then return function() return nil end end
            return function() return fake_object end
        end,
    })
    local world = { IsValid = function() return true end }
    local kismet = { IsDedicatedServer = function() return true end }
    local helpers = {
        GetWorld = function() return world end,
        GetKismetSystemLibrary = function() return kismet end,
        GetGameInstance = function() return fake_object end,
        GetPlayerController = function() return fake_object end,
    }
    environment.UEHelpers = helpers
    environment.FindFirstOf = function() return fake_object end
    environment.StaticFindObject = function() return fake_object end
    environment.NotifyOnNewObject = function(_path, _callback) return 1 end
    environment.RegisterHook = function(_path, _callback) return 1, 2 end
    environment.UnregisterHook = function(...) return true end
    environment.RegisterConsoleCommandGlobalHandler = function(_name, _callback) return 1 end
    environment.RegisterConsoleCommandHandler = environment.RegisterConsoleCommandGlobalHandler
    environment.UnregisterConsoleCommandGlobalHandler = function(...) return true end
    environment.ExecuteInGameThread = function(callback) return callback() end
    environment.ExecuteWithDelay = function(_delay, callback) return callback() end
    environment.ExecuteAsync = function(callback) return callback() end
    environment.LoopAsync = function(_delay, _callback)
        return { Cancel = function() return true end }
    end
    return helpers, world
end

local candidate = {}
for key, value in pairs(base) do
    candidate[key] = type(value) == "table" and copy_table(value) or value
end
local candidate_helpers = install_ue4ss(candidate)
candidate._G = candidate

local module_cache = {}
candidate.require = function(name)
    assert(type(name) == "string" and name ~= "", "module name must be a string")
    if name == "UEHelpers" then return candidate_helpers end
    if module_cache[name] ~= nil then return module_cache[name] end
    assert(not name:find("..", 1, true), "unsafe module path")
    local logical = name:gsub("%.", "/")
    local candidates = { logical .. ".lua" }
    if logical:sub(1, 8) ~= "scripts/" then
        candidates[#candidates + 1] = "scripts/" .. logical .. ".lua"
    end
    local source = nil
    local relative = nil
    for _, path in ipairs(candidates) do
        local ok, value = pcall(read_source, path)
        if ok then source, relative = value, path; break end
    end
    if source == nil then error("submission module is missing: " .. name, 2) end
    local chunk, load_error = native_load(source, "@submission/" .. relative, "t", candidate)
    if chunk == nil then error(load_error, 2) end
    local value = chunk()
    if value == nil then value = true end
    module_cache[name] = value
    return value
end

function run_mock_server(main_relative, server_source)
    local main_source = read_source(main_relative)
    local main_chunk, main_load_error = native_load(
        main_source, "@submission/" .. main_relative, "t", candidate)
    if main_chunk == nil then
        return { status = "error", error = tostring(main_load_error), cases = {} }
    end
    local main_ok, main_error = pcall(main_chunk)
    if not main_ok then
        return { status = "error", error = tostring(main_error), cases = {} }
    end

    local trusted = {}
    for key, value in pairs(base) do
        trusted[key] = type(value) == "table" and copy_table(value) or value
    end
    local trusted_helpers, trusted_world = install_ue4ss(trusted)
    trusted.RheniumService = candidate.RheniumService
    trusted._G = trusted

    local suite_chunk, suite_load_error = native_load(server_source, "@private/server.lua", "t", trusted)
    if suite_chunk == nil then
        return { status = "error", error = tostring(suite_load_error), cases = {} }
    end
    local suite_ok, suite_or_error = pcall(suite_chunk)
    if not suite_ok or type(suite_or_error) ~= "function" then
        return {
            status = "error",
            error = suite_ok and "server suite did not return a function" or tostring(suite_or_error),
            cases = {},
        }
    end

    local cases = {}
    local context = { helpers = trusted_helpers, world = trusted_world }
    function context:case(name, body)
        local ok, message = pcall(body)
        cases[#cases + 1] = {
            name = name,
            passed = ok,
            message = ok and "ok" or tostring(message),
        }
    end
    local run_ok, run_error = pcall(suite_or_error, context)
    if not run_ok then
        return { status = "error", error = tostring(run_error), cases = cases }
    end
    local passed = #cases > 0
    for _, case in ipairs(cases) do
        if not case.passed then passed = false end
    end
    return { status = passed and "passed" or "failed", cases = cases }
end
"""


def _case_value(case: Any, key: str) -> Any:
    try:
        return case[key]
    except (KeyError, TypeError):
        return None


def _normalise_cases(result: Any, suite_name: str) -> list[dict[str, Any]]:
    try:
        raw_cases = result["cases"]
    except (KeyError, TypeError) as error:
        raise RunnerInputError(f"{suite_name} did not return a case table") from error
    if raw_cases is None:
        raise RunnerInputError(f"{suite_name} did not return a case table")

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
            raise RunnerInputError(f"{suite_name} case {index} has no valid name")
        if not isinstance(passed, bool):
            raise RunnerInputError(f"{suite_name} case {index} has no boolean result")
        cases.append(
            {
                "name": name,
                "passed": passed,
                "message": "" if message is None else str(message),
            }
        )
        index += 1
    if not cases:
        raise RunnerInputError(f"{suite_name} returned no cases")
    return cases


def _runtime() -> Any:
    try:
        from lupa.lua54 import LuaRuntime  # type: ignore[import-untyped]
    except ImportError as error:
        raise RunnerInputError("lupa is unavailable") from error
    return LuaRuntime(
        encoding="utf-8",
        register_eval=False,
        register_builtins=False,
        attribute_filter=_deny_python_attributes,
        max_memory=LUA_MEMORY_BYTES,
    )


def run_behavior(submission: Path, suite: Path) -> dict[str, Any]:
    try:
        source = suite.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RunnerInputError("behavior suite is unavailable") from error
    runtime = _runtime()
    runtime.globals()["read_submission_source"] = _submission_reader(submission)
    runtime.execute(_BEHAVIOR_BOOTSTRAP.replace("__TIME_LIMIT__", str(CPU_SECONDS)))
    result = runtime.execute(source)
    cases = _normalise_cases(result, "behavior suite")
    return {
        "status": "passed" if all(case["passed"] for case in cases) else "failed",
        "cases": cases,
        "lua_runtime_version": str(runtime.eval("_VERSION")),
    }


def run_mock_server(submission: Path, suite: Path) -> dict[str, Any]:
    try:
        source = suite.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as source_error:
        raise RunnerInputError("server-contract suite is unavailable") from source_error
    runtime = _runtime()
    runtime.globals()["read_submission_source"] = _submission_reader(submission)
    runtime.execute(_SERVER_BOOTSTRAP.replace("__TIME_LIMIT__", str(CPU_SECONDS)))
    try:
        result = runtime.globals()["run_mock_server"]("scripts/main.lua", source)
    except (RunnerInputError, RuntimeError) as runner_error:
        return {"status": "error", "cases": [], "error": str(runner_error)}
    status = _case_value(result, "status")
    error = _case_value(result, "error")
    try:
        cases = _normalise_cases(result, "server-contract suite")
    except RunnerInputError:
        if status != "error":
            raise
        cases = []
    return {
        "status": status if isinstance(status, str) else "error",
        "cases": cases,
        "error": "" if error is None else str(error),
    }


def dump_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
