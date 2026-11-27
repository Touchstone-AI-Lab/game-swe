from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .analyzer import ModAnalyzer, has_exact_case_file, strip_lua_comments
from .catalog import IntegrationCheck, PalworldTask
from .native_runtime import RUNTIME_KEY, NativeServerRunner
from .runtime import PalworldRuntimeConfig

_SERVER_LOCK = threading.Lock()
_BEHAVIOR_TIMEOUT_SECONDS = 8
_SERVER_MARKER = "@@RHENIUM_SERVER@@"
_SERVER_SUITE_MODULE = "scripts/rhenium_server_test.lua"
_SERVER_RESULT_FILE = "rhenium_result.txt"
_SERVER_ENTRY_POINT = "scripts/main.lua"
# The submitted entry point moves here in the scoring copy and runs unchanged from its own
# file; appending the loader to it instead broke any entry point ending in a top-level return.
_SUBMITTED_ENTRY_POINT = "scripts/rhenium_submission_main.lua"
_SERVER_ENTRY_TEMPLATE = """-- Injected into the temporary scoring copy only: the submitted entry point runs
-- unchanged from its own file, then the assertion loader below starts.
local __rhenium_submitted = assert(loadfile([==[__SUBMITTED_PATH__]==]))
__rhenium_submitted()
"""
_MOD_REGISTRY = "mods.txt"
# UE4SS starts Lua mods before the dedicated server has a valid UWorld, so the
# suite polls for world readiness instead of firing once after a fixed delay.
_SUITE_POLL_MS = 2000
_SUITE_MAX_ATTEMPTS = 60
_SUITE_SETTLE_TICKS = 3

_SERVER_LOADER_TEMPLATE = '''

-- Injected into the temporary scoring copy only.
local __rhenium_suite_ok, __rhenium_suite = pcall(require, "rhenium_server_test")
local __rhenium_helpers_ok, __rhenium_helpers = pcall(require, "UEHelpers")
local __rhenium_marker = "__MARKER__"
local __rhenium_result_path = [==[__RESULT_PATH__]==]
local __rhenium_emitted = false

local function __rhenium_escape(value)
    local text = tostring(value)
    text = text:gsub("\\\\", "\\\\\\\\")
    text = text:gsub('"', '\\\\"')
    text = text:gsub("%c", function(character)
        return string.format("\\\\u%04x", string.byte(character))
    end)
    return text
end

local function __rhenium_encode(status, cases)
    local parts = {}
    for index = 1, #cases do
        local case = cases[index]
        parts[#parts + 1] = string.format(
            '{"name":"%s","passed":%s,"message":"%s"}',
            __rhenium_escape(case.name),
            case.passed and "true" or "false",
            __rhenium_escape(case.message)
        )
    end
    return string.format(
        '{"status":"%s","cases":[%s]}', status, table.concat(parts, ",")
    )
end

local function __rhenium_emit(status, cases)
    local line = __rhenium_marker .. __rhenium_encode(status, cases)
    print(line .. "\\n")
    local handle = io.open(__rhenium_result_path, "w")
    if handle ~= nil then
        handle:write(line .. "\\n")
        handle:close()
    end
end

local function __rhenium_run()
    if __rhenium_emitted then
        return
    end
    __rhenium_emitted = true
    local cases = {}
    local context = {}
    if __rhenium_helpers_ok and __rhenium_helpers ~= nil then
        context.helpers = __rhenium_helpers
        local world_ok, world = pcall(__rhenium_helpers.GetWorld)
        context.world = world_ok and world or nil
    end
    function context:case(name, body)
        local ok, message = pcall(body)
        cases[#cases + 1] = {
            name = tostring(name),
            passed = ok,
            message = ok and "ok" or tostring(message),
        }
    end
    if not __rhenium_suite_ok or type(__rhenium_suite) ~= "function" then
        cases[#cases + 1] = {
            name = "suite execution",
            passed = false,
            message = tostring(__rhenium_suite),
        }
    else
        local ok, message = pcall(__rhenium_suite, context)
        if not ok then
            cases[#cases + 1] = {
                name = "suite execution",
                passed = false,
                message = tostring(message),
            }
        end
    end
    local passed = #cases > 0
    for index = 1, #cases do
        passed = passed and cases[index].passed
    end
    __rhenium_emit(passed and "passed" or "failed", cases)
end

local __rhenium_attempts = 0
local __rhenium_ready_ticks = 0
local __rhenium_scheduled = false
local __rhenium_schedule

-- The dedicated server publishes a valid UWorld several seconds after UE4SS
-- starts Lua mods, so the suite waits for readiness before it asserts.
local function __rhenium_world_ready()
    if not __rhenium_helpers_ok or __rhenium_helpers == nil then
        return true
    end
    local world_ok, world = pcall(__rhenium_helpers.GetWorld)
    if not world_ok or world == nil then
        return false
    end
    local valid_ok, valid = pcall(function()
        return world:IsValid()
    end)
    return valid_ok and valid == true
end

local function __rhenium_tick()
    if __rhenium_emitted then
        return
    end
    __rhenium_attempts = __rhenium_attempts + 1
    if __rhenium_world_ready() then
        __rhenium_ready_ticks = __rhenium_ready_ticks + 1
    else
        __rhenium_ready_ticks = 0
    end
    -- The submission mounts its own service once the world appears, so the
    -- suite lets the world settle before it asserts anything.
    if __rhenium_ready_ticks >= __SETTLE_TICKS__ or __rhenium_attempts >= __MAX_ATTEMPTS__ then
        __rhenium_run()
        return
    end
    __rhenium_scheduled = false
    __rhenium_schedule()
end

__rhenium_schedule = function()
    if __rhenium_scheduled or __rhenium_emitted then
        return
    end
    __rhenium_scheduled = true
    ExecuteWithDelay(__DELAY_MS__, function()
        ExecuteInGameThread(__rhenium_tick)
    end)
end

RegisterInitGameStatePostHook(function()
    __rhenium_schedule()
end)
__rhenium_schedule()
'''


@dataclass(frozen=True)
class CheckResult:
    id: str
    status: str
    score: float
    maximum: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class DedicatedServerRunner:
    """Runs private assertions inside a real Palworld dedicated server under UE4SS."""

    def __init__(self, settings: PalworldRuntimeConfig | Any):
        self.settings = (
            settings
            if isinstance(settings, PalworldRuntimeConfig)
            else PalworldRuntimeConfig.load(settings)
        )

    def binary(self) -> Path | None:
        for candidate in self.settings.candidate_binaries():
            if candidate.is_file():
                return candidate
        return None

    def run_assertions(
        self, submission: Path, server_test: Path, timeout: int = 180
    ) -> dict[str, Any]:
        binary = self.binary()
        if not binary or not binary.is_file():
            return {
                "status": "unavailable",
                "message": "Palworld dedicated server was not found",
                "cases": [],
                "log": "",
            }
        mods_root = self._mods_root(binary)
        if not mods_root:
            return {
                "status": "unavailable",
                "message": "UE4SS mods directory was not found next to the dedicated server",
                "cases": [],
                "log": "",
            }
        if not os.access(mods_root, os.W_OK):
            return {
                "status": "unavailable",
                "message": "UE4SS mods directory is not writable",
                "cases": [],
                "log": "",
            }
        if not server_test.is_file():
            return {
                "status": "error",
                "message": "Headless server assertion suite is unavailable",
                "cases": [],
                "log": "",
            }

        with _SERVER_LOCK, tempfile.TemporaryDirectory(prefix="rhenium-palserver-") as temp_value:
            temp = Path(temp_value)
            mod_name = f"rhenium_{uuid.uuid4().hex[:12]}"
            link = mods_root / mod_name
            registry = mods_root / _MOD_REGISTRY
            original_registry = registry.read_bytes() if registry.is_file() else None
            result_file = temp / _SERVER_RESULT_FILE
            try:
                shutil.copytree(submission.resolve(), link)
            except OSError as error:
                shutil.rmtree(link, ignore_errors=True)
                return {
                    "status": "unavailable",
                    "message": f"UE4SS mods directory is not writable: {error}",
                    "cases": [],
                    "log": "",
                }
            nonce = uuid.uuid4().hex
            injection_error = self._inject_assertion_suite(link, server_test, nonce, result_file)
            if injection_error:
                shutil.rmtree(link, ignore_errors=True)
                return {
                    "status": "failed",
                    "message": injection_error,
                    "cases": [],
                    "log": "",
                }
            registry_error = self._enable_mod(registry, mod_name)
            if registry_error:
                shutil.rmtree(link, ignore_errors=True)
                return {
                    "status": "unavailable",
                    "message": registry_error,
                    "cases": [],
                    "log": "",
                }
            ue4ss_log = self._ue4ss_log(mods_root)
            log_offset = ue4ss_log.stat().st_size if ue4ss_log and ue4ss_log.is_file() else 0
            command = [
                str(binary),
                "-log",
                f"-port={self._free_port()}",
                "-players=1",
                "-NoAsyncLoadingThread",
                "-useperfthreads",
            ]
            popen_arguments: dict[str, Any] = {
                "cwd": binary.parent,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
            }
            if hasattr(os, "setsid"):
                popen_arguments["start_new_session"] = True
            else:  # pragma: no cover - Windows-only process-group handling
                popen_arguments["creationflags"] = getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
            process = subprocess.Popen(command, **popen_arguments)
            if process.stdout and hasattr(os, "set_blocking"):
                os.set_blocking(process.stdout.fileno(), False)
            output: list[str] = []
            deadline = time.monotonic() + timeout
            suite_finished = False
            try:
                while time.monotonic() < deadline:
                    line = process.stdout.readline() if process.stdout else ""
                    if line:
                        output.append(line)
                    log_chunk, log_offset = self._read_new_log(ue4ss_log, log_offset)
                    if log_chunk:
                        output.append(log_chunk)
                    if any(f"{_SERVER_MARKER}{nonce}:" in chunk for chunk in output[-4:]):
                        suite_finished = True
                        break
                    if result_file.is_file():
                        with suppress(OSError, UnicodeError):
                            payload = result_file.read_text(encoding="utf-8", errors="replace")
                        if f"{_SERVER_MARKER}{nonce}:" in payload:
                            output.append(payload)
                            suite_finished = True
                            break
                    if not line and not log_chunk:
                        if process.poll() is not None:
                            break
                        time.sleep(0.05)
            finally:
                interrupted: BaseException | None = None
                try:
                    self._terminate(process)
                except BaseException as error:  # noqa: BLE001 - re-raised after cleanup
                    interrupted = error
                    self._kill(process)
                finally:
                    if process.stdout:
                        with suppress(OSError, ValueError):
                            output.extend(process.stdout.readlines())
                    log_chunk, log_offset = self._read_new_log(ue4ss_log, log_offset)
                    if log_chunk:
                        output.append(log_chunk)
                    self._restore_registry(registry, original_registry)
                    shutil.rmtree(link, ignore_errors=True)
                if interrupted is not None:
                    raise interrupted

            log = "".join(output)
            candidate_errors = self._candidate_error_lines(log, mod_name)
            if candidate_errors:
                return {
                    "status": "failed",
                    "message": candidate_errors[-1],
                    "cases": [],
                    "log": log,
                }
            if suite_finished:
                return self._parse_assertion_result(log, nonce)
            return {
                "status": "failed",
                "message": "Headless server assertions did not finish before timeout",
                "cases": [],
                "log": log,
            }

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    @staticmethod
    def _taskkill(pid: int, force: bool) -> None:  # pragma: no cover - Windows-only
        """Kill a Windows process together with every child it spawned.

        ``PalServer.exe`` is a launcher that starts the real shipping server as
        a child, so terminating only the direct child orphans a live server
        that still holds the UE4SS mods directory.
        """
        command = ["taskkill", "/T", "/PID", str(pid)]
        if force:
            command.insert(1, "/F")
        with suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if hasattr(os, "killpg"):
            with suppress(ProcessLookupError, OSError):
                os.killpg(process.pid, signal.SIGTERM)
        else:  # pragma: no cover - Windows-only termination
            # The headless server owns no window, so a graceful taskkill is
            # refused; the whole tree is force-killed instead. This is why the
            # documentation requires a throwaway server installation.
            DedicatedServerRunner._taskkill(process.pid, force=True)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            DedicatedServerRunner._kill(process)

    @staticmethod
    def _kill(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if hasattr(os, "killpg"):
            with suppress(ProcessLookupError, OSError):
                os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover - Windows-only termination
            DedicatedServerRunner._taskkill(process.pid, force=True)
            with suppress(OSError):
                process.kill()

    @staticmethod
    def _read_new_log(path: Path | None, offset: int) -> tuple[str, int]:
        if path is None or not path.is_file():
            return "", offset
        try:
            size = path.stat().st_size
            if size < offset:
                # UE4SS recreates its log on startup, so a shrunk file is a new one.
                offset = 0
            if size <= offset:
                return "", offset
            with path.open("rb") as handle:
                handle.seek(offset)
                chunk = handle.read()
        except OSError:
            return "", offset
        return chunk.decode("utf-8", errors="replace"), offset + len(chunk)

    @staticmethod
    def _enable_mod(registry: Path, mod_name: str) -> str | None:
        """Enable the temporary scoring mod in the UE4SS ``mods.txt`` registry."""
        try:
            existing = registry.read_text(encoding="utf-8", errors="replace") if registry.is_file() else ""
            separator = "" if not existing or existing.endswith("\n") else "\n"
            registry.write_text(f"{existing}{separator}{mod_name} : 1\n", encoding="utf-8")
        except OSError as error:
            return f"UE4SS mod registry is not writable: {error}"
        return None

    @staticmethod
    def _restore_registry(registry: Path, original: bytes | None) -> None:
        with suppress(OSError):
            registry.write_bytes(original if original is not None else b"")

    @staticmethod
    def _inject_assertion_suite(
        mod_root: Path, server_test: Path, nonce: str, result_file: Path
    ) -> str | None:
        entry_point = mod_root / _SERVER_ENTRY_POINT
        reserved = mod_root / _SERVER_SUITE_MODULE
        submitted = mod_root / _SUBMITTED_ENTRY_POINT
        if not entry_point.is_file():
            return f"{_SERVER_ENTRY_POINT} is required for headless server assertions"
        for path, relative in ((reserved, _SERVER_SUITE_MODULE), (submitted, _SUBMITTED_ENTRY_POINT)):
            if path.exists():
                return f"submission uses reserved assertion path: {relative}"
        reserved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(server_test, reserved)
        loader = (
            _SERVER_LOADER_TEMPLATE.replace("__MARKER__", f"{_SERVER_MARKER}{nonce}:")
            .replace("__RESULT_PATH__", result_file.as_posix())
            .replace("__DELAY_MS__", str(_SUITE_POLL_MS))
            .replace("__MAX_ATTEMPTS__", str(_SUITE_MAX_ATTEMPTS))
            .replace("__SETTLE_TICKS__", str(_SUITE_SETTLE_TICKS))
        )
        wrapper = _SERVER_ENTRY_TEMPLATE.replace("__SUBMITTED_PATH__", submitted.resolve().as_posix())
        try:
            entry_point.replace(submitted)
            entry_point.write_text(wrapper + loader, encoding="utf-8")
        except OSError as error:
            return f"could not inject headless server assertions: {error}"
        return None

    @staticmethod
    def _parse_assertion_result(log: str, nonce: str) -> dict[str, Any]:
        prefix = f"{_SERVER_MARKER}{nonce}:"
        payloads: list[dict[str, Any]] = []
        seen: set[str] = set()
        for line in log.splitlines():
            if prefix not in line:
                continue
            raw = line.split(prefix, 1)[1].strip()
            if raw in seen:
                continue
            seen.add(raw)
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                return {
                    "status": "error",
                    "message": "Headless server suite emitted malformed JSON",
                    "cases": [],
                    "log": log,
                }
            if isinstance(value, dict):
                payloads.append(value)
        if len(payloads) != 1:
            return {
                "status": "error",
                "message": "Headless server suite emitted an invalid number of final markers",
                "cases": [],
                "log": log,
            }
        payload = payloads[0]
        raw_cases = payload.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            return {
                "status": "error",
                "message": "Headless server suite produced no assertion cases",
                "cases": [],
                "log": log,
            }
        cases: list[dict[str, Any]] = []
        for raw_case in raw_cases:
            if not isinstance(raw_case, dict):
                return {
                    "status": "error",
                    "message": "Headless server suite produced a malformed case",
                    "cases": [],
                    "log": log,
                }
            name = raw_case.get("name")
            passed = raw_case.get("passed")
            message = raw_case.get("message", "")
            if not isinstance(name, str) or not name.strip() or not isinstance(passed, bool):
                return {
                    "status": "error",
                    "message": "Headless server suite produced a malformed case",
                    "cases": [],
                    "log": log,
                }
            cases.append(
                {
                    "name": name,
                    "passed": passed,
                    "message": message if isinstance(message, str) else str(message),
                }
            )
        actual = "passed" if all(case["passed"] for case in cases) else "failed"
        if payload.get("status") != actual:
            return {
                "status": "error",
                "message": "Headless server suite status is inconsistent",
                "cases": cases,
                "log": log,
            }
        return {
            "status": actual,
            "message": (
                f"All {len(cases)} headless server assertions passed"
                if actual == "passed"
                else "One or more headless server assertions failed"
            ),
            "cases": cases,
            "log": log,
        }

    @staticmethod
    def _candidate_error_lines(log: str, mod_name: str) -> list[str]:
        error_word = re.compile(r"\b(?:error|failed|traceback|missing)\b", re.I)
        return [
            line
            for line in log.splitlines()
            if _SERVER_MARKER not in line and mod_name in line and error_word.search(line)
        ]

    @staticmethod
    def _mods_root(binary: Path) -> Path | None:
        """Locate the UE4SS Lua ``Mods`` directory for this dedicated server."""
        relatives = (
            Path("ue4ss/Mods"),
            Path("UE4SS/Mods"),
            Path("Mods/NativeMods/UE4SS/Mods"),
            Path("Pal/Binaries/Win64/ue4ss/Mods"),
        )
        for parent in binary.parents:
            for relative in relatives:
                candidate = parent / relative
                if candidate.is_dir():
                    return candidate
        return None

    @staticmethod
    def _ue4ss_log(mods_root: Path) -> Path | None:
        """Locate ``UE4SS.log``, falling back to where UE4SS will create it.

        UE4SS ``print`` output never reaches the dedicated server's stdout, so
        this file is the primary assertion channel. On a freshly installed
        runtime it does not exist until the first launch.
        """
        for parent in (mods_root.parent, *mods_root.parents):
            candidate = parent / "UE4SS.log"
            if candidate.is_file():
                return candidate
        expected = mods_root.parent / "UE4SS.log"
        return expected if mods_root.parent.is_dir() else None


class PalworldEvaluator:
    def __init__(self, settings: PalworldRuntimeConfig | Any):
        self.settings = (
            settings
            if isinstance(settings, PalworldRuntimeConfig)
            else PalworldRuntimeConfig.load(settings)
        )
        self.analyzer = ModAnalyzer()
        self.server = DedicatedServerRunner(self.settings)

    def runtime_status(self) -> dict[str, Any]:
        if self.settings.context is not None:
            return {
                "id": RUNTIME_KEY, "available": False, "managed": True,
                "requiresPreparedArtifact": True,
                "prepareCommand": f"rhenium runtime prepare {RUNTIME_KEY}",
            }
        binary = self.server.binary()
        mods_root = DedicatedServerRunner._mods_root(binary) if binary else None
        available = bool(binary and binary.is_file() and mods_root and os.access(mods_root, os.W_OK))
        return {
            "id": "palworld-dedicated-server",
            "available": available,
            "binary": str(binary) if binary else None,
        }

    def evaluate(
        self,
        submission: Path,
        task: PalworldTask,
        profile: str = "full",
        runtimes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Palworld evaluation profile: {profile}")
        full_evaluation = profile == "full"
        submission = submission.resolve()
        try:
            analysis = self.analyzer.analyze(submission)
        except (OSError, ValueError) as error:
            analysis = {
                "valid": False,
                "lua_files": 0,
                "lines": 0,
                "syntax_errors": [{"file": "", "line": 0, "message": str(error)}],
            }

        checks: list[CheckResult] = []

        required_details = self._required_file_details(submission, task.required_files)
        structure_ok = not required_details["missing"] and not required_details["unsafe"]
        checks.append(
            CheckResult(
                id="required-files",
                status="passed" if structure_ok else "failed",
                score=5.0 if structure_ok else 0.0,
                maximum=5.0,
                message=(
                    f"All {len(task.required_files)} required files are present"
                    if structure_ok
                    else "One or more required files are missing or unsafe"
                ),
                details=required_details,
            )
        )

        lua_files = self._safe_lua_files(submission)
        syntax_errors = list(analysis.get("syntax_errors", []))
        syntax_ok = bool(lua_files) and not syntax_errors
        checks.append(
            CheckResult(
                id="lua-syntax",
                status="passed" if syntax_ok else "failed",
                score=5.0 if syntax_ok else 0.0,
                maximum=5.0,
                message=(
                    f"All {len(lua_files)} Lua files parse successfully"
                    if syntax_ok
                    else "Lua source is missing or contains syntax errors"
                ),
                details={"files": len(lua_files), "errors": syntax_errors},
            )
        )

        behavior_result = self._run_behavior_tests(submission, task)
        behavior_cases = behavior_result.get("cases", [])
        behavior_total = len(behavior_cases)
        behavior_passed = sum(case.get("passed") is True for case in behavior_cases)
        behavior_ok = (
            behavior_result.get("status") == "passed"
            and behavior_total > 0
            and behavior_passed == behavior_total
        )
        behavior_score = (
            round(30.0 * behavior_passed / behavior_total, 2)
            if behavior_total and behavior_result.get("status") in {"passed", "failed"}
            else 0.0
        )
        checks.append(
            CheckResult(
                id="hidden-behavior",
                status="passed" if behavior_ok else "failed",
                score=behavior_score,
                maximum=30.0,
                message=(
                    f"All {behavior_total} hidden behavior cases passed"
                    if behavior_ok
                    else str(
                        behavior_result.get(
                            "message",
                            f"Hidden behavior cases passed: {behavior_passed}/{behavior_total}",
                        )
                    )
                ),
                details={
                    "passed": behavior_passed,
                    "total": behavior_total,
                    "cases": behavior_cases,
                    "runner_status": behavior_result.get("status", "error"),
                },
            )
        )

        implementation_lines, line_files = self._implementation_lines(lua_files)
        depth_ok = implementation_lines >= task.minimum_lua_lines
        checks.append(
            CheckResult(
                id="implementation-depth",
                status="passed" if depth_ok else "failed",
                score=5.0 if depth_ok else 0.0,
                maximum=5.0,
                message=(
                    f"Implementation has {implementation_lines} non-comment Lua lines "
                    f"(minimum {task.minimum_lua_lines})"
                ),
                details={
                    "lines": implementation_lines,
                    "minimum": task.minimum_lua_lines,
                    "files": line_files,
                },
            )
        )

        checks.extend(
            self._evaluate_integration_check(submission, integration)
            for integration in task.integration_checks
        )

        server_result: dict[str, Any] = {
            "status": "skipped",
            "message": "Headless dedicated-server assertions disabled",
            "cases": [],
            "log": "",
        }
        if full_evaluation:
            dataset_root = self.settings.pack_root.resolve()
            server_test = (dataset_root / task.server_test).resolve()
            if not server_test.is_relative_to(dataset_root):
                server_result = {
                    "status": "error",
                    "message": "Headless server assertion path is unsafe",
                    "cases": [],
                    "log": "",
                }
            else:
                if self.settings.context is not None:
                    artifact = (runtimes or {}).get(RUNTIME_KEY)
                    if artifact is None:
                        server_result = {
                            "status": "unavailable", "cases": [], "log": "",
                            "message": f"Runtime is not prepared; run rhenium runtime prepare {RUNTIME_KEY}",
                        }
                    else:
                        server_result = NativeServerRunner(self.settings.context).run_assertions(
                            submission, server_test, artifact
                        )
                else:
                    server_result = self.server.run_assertions(submission, server_test)
        server_cases = server_result.get("cases", [])
        server_total = len(server_cases) if isinstance(server_cases, list) else 0
        server_passed = (
            sum(case.get("passed") is True for case in server_cases)
            if isinstance(server_cases, list)
            else 0
        )
        server_score = round(40.0 * server_passed / server_total, 2) if server_total else 0.0
        checks.append(
            CheckResult(
                "headless-server",
                str(server_result.get("status", "failed")),
                server_score,
                40.0,
                str(server_result.get("message", "Headless dedicated-server assertions failed")),
                {
                    "passed": server_passed,
                    "total": server_total,
                    "cases": server_cases if isinstance(server_cases, list) else [],
                    "runner_status": server_result.get("status", "error"),
                },
            )
        )

        available_maximum = sum(check.maximum for check in checks)
        earned = sum(check.score for check in checks)
        score = round(earned / available_maximum * 100, 2) if available_maximum else 0.0
        complete = bool(
            full_evaluation
            and server_total > 0
            and server_result.get("status") in {"passed", "failed"}
        )
        passed = complete and bool(checks) and all(check.status == "passed" for check in checks)
        return {
            "score": score,
            "earned": round(earned, 2),
            "available_maximum": round(available_maximum, 2),
            "rubric_maximum": 100.0,
            "complete": complete,
            "passed": passed,
            "checks": [asdict(check) for check in checks],
            "analysis": analysis,
            "runtime": {key: value for key, value in server_result.items() if key != "log"},
            "server": {key: value for key, value in server_result.items() if key != "log"},
            "runtime_log": str(server_result.get("log", "")),
            "server_log": str(server_result.get("log", "")),
        }

    @staticmethod
    def _safe_candidate(root: Path, relative: str) -> Path | None:
        try:
            candidate = (root / relative).resolve(strict=True)
        except OSError:
            return None
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        # Required paths are part of the authored contract, so a case-insensitive
        # host must not accept a differently cased file the mod loader on
        # another host would miss.
        if not has_exact_case_file(root, Path(relative).as_posix()):
            return None
        return candidate

    @classmethod
    def _required_file_details(cls, submission: Path, required: list[str]) -> dict[str, Any]:
        present: list[str] = []
        missing: list[str] = []
        unsafe: list[str] = []
        for relative in required:
            logical = Path(relative)
            if logical.is_absolute() or ".." in logical.parts:
                unsafe.append(relative)
                continue
            candidate = cls._safe_candidate(submission, relative)
            if candidate is None:
                unresolved = submission / relative
                if unresolved.is_symlink():
                    unsafe.append(relative)
                else:
                    missing.append(relative)
            else:
                present.append(relative)
        return {"present": present, "missing": missing, "unsafe": unsafe}

    @staticmethod
    def _safe_lua_files(submission: Path) -> list[Path]:
        if not submission.is_dir():
            return []
        files: list[Path] = []
        seen: set[Path] = set()
        try:
            candidates = submission.rglob("*.lua")
            for path in candidates:
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    continue
                if (
                    not resolved.is_relative_to(submission)
                    or not resolved.is_file()
                    or resolved in seen
                ):
                    continue
                seen.add(resolved)
                files.append(path)
        except OSError:
            return []
        return sorted(files, key=lambda path: path.relative_to(submission).as_posix())

    @staticmethod
    def _implementation_lines(lua_files: list[Path]) -> tuple[int, dict[str, int]]:
        by_file: dict[str, int] = {}
        total = 0
        if not lua_files:
            return total, by_file
        common_root = Path(os.path.commonpath([str(path.parent) for path in lua_files]))
        for path in lua_files:
            try:
                uncommented = strip_lua_comments(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            count = sum(bool(line.strip()) for line in uncommented.splitlines())
            try:
                label = path.relative_to(common_root).as_posix()
            except ValueError:
                label = path.name
            by_file[label] = count
            total += count
        return total, by_file

    def _run_behavior_tests(self, submission: Path, task: PalworldTask) -> dict[str, Any]:
        dataset_root = self.settings.pack_root.resolve()
        hidden_test = (dataset_root / task.hidden_test).resolve()
        if not hidden_test.is_relative_to(dataset_root) or not hidden_test.is_file():
            return {
                "status": "error",
                "cases": [],
                "message": "Hidden behavior test is unavailable",
            }

        package_source = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        existing_path = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            os.pathsep.join((str(package_source), existing_path))
            if existing_path
            else str(package_source)
        )
        environment["PYTHONIOENCODING"] = "utf-8"
        command = [
            sys.executable,
            "-m",
            "rhenium_palworld.lua_runner",
            "--submission",
            str(submission),
            "--test",
            str(hidden_test),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=_BEHAVIOR_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "cases": [],
                "message": "Hidden behavior test timed out",
            }
        try:
            payload = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError):
            return {
                "status": "error",
                "cases": [],
                "message": "Hidden behavior test runner failed",
            }
        if not isinstance(payload, dict):
            return {
                "status": "error",
                "cases": [],
                "message": "Hidden behavior test runner returned invalid output",
            }
        cases = payload.get("cases")
        if not isinstance(cases, list) or not cases:
            return {
                "status": "error",
                "cases": [],
                "message": "Hidden behavior test produced no cases",
            }
        normalised: list[dict[str, Any]] = []
        for index, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                return {
                    "status": "error",
                    "cases": [],
                    "message": "Hidden behavior test returned malformed cases",
                }
            name = case.get("name")
            passed = case.get("passed")
            message = case.get("message", "")
            if not isinstance(name, str) or not name.strip() or not isinstance(passed, bool):
                return {
                    "status": "error",
                    "cases": [],
                    "message": f"Hidden behavior case {index} is malformed",
                }
            normalised.append(
                {
                    "name": name,
                    "passed": passed,
                    "message": message if isinstance(message, str) else str(message),
                }
            )
        declared_status = payload.get("status")
        actual_status = "passed" if all(case["passed"] for case in normalised) else "failed"
        if completed.returncode != 0 or declared_status not in {"passed", "failed"}:
            return {
                "status": "error",
                "cases": normalised,
                "message": "Hidden behavior test runner failed",
            }
        if declared_status != actual_status:
            return {
                "status": "error",
                "cases": normalised,
                "message": "Hidden behavior test runner returned inconsistent results",
            }
        return {
            "status": actual_status,
            "cases": normalised,
            "message": (
                "All hidden behavior cases passed"
                if actual_status == "passed"
                else "One or more hidden behavior cases failed"
            ),
        }

    @staticmethod
    def _readable_source(path: Path) -> str | None:
        """Return comment-free Lua, or raw text for manifest files such as ``Info.json``."""
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return strip_lua_comments(source) if path.suffix.lower() == ".lua" else source

    @classmethod
    def _evaluate_integration_check(cls, submission: Path, check: IntegrationCheck) -> CheckResult:
        matched_files: list[str] = []
        chunks: list[str] = []
        try:
            candidates = sorted(
                submission.glob(check.glob),
                key=lambda path: path.relative_to(submission).as_posix(),
            )
        except (OSError, ValueError):
            candidates = []
        seen: set[Path] = set()
        for path in candidates:
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_relative_to(submission) or not resolved.is_file() or resolved in seen:
                continue
            seen.add(resolved)
            source = cls._readable_source(path)
            if source is None:
                continue
            matched_files.append(path.relative_to(submission).as_posix())
            chunks.append(source)
        merged = "\n".join(chunks)

        group_details: list[dict[str, Any]] = []
        groups_ok = True
        for group in check.groups:
            matched_pattern = next(
                (pattern for pattern in group.any_of if re.search(pattern, merged, re.MULTILINE)),
                None,
            )
            matched = matched_pattern is not None
            groups_ok = groups_ok and matched
            group_details.append(
                {"name": group.name, "matched": matched, "pattern": matched_pattern}
            )
        forbidden_matches = [
            pattern for pattern in check.none_of if re.search(pattern, merged, re.MULTILINE)
        ]
        passed = bool(matched_files) and groups_ok and not forbidden_matches
        maximum = float(check.weight)
        return CheckResult(
            id=check.id,
            status="passed" if passed else "failed",
            score=maximum if passed else 0.0,
            maximum=maximum,
            message=(
                "All integration contracts are satisfied"
                if passed
                else "Integration contract patterns are incomplete or forbidden patterns matched"
            ),
            details={
                "label": check.label.model_dump(mode="json"),
                "glob": check.glob,
                "files": matched_files,
                "groups": group_details,
                "forbidden_matches": forbidden_matches,
            },
        )
