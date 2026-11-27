"""Evaluator of the construct pack (catalog ``rhenium-dst-v2``).

This is the evaluator the ten construct tasks were validated against before the
repair pack replaced them in ``benchmarks/dst``, restored unchanged apart from
its names and the construct pack's own runtime key. It scores static checks, the
sandboxed plain-Lua suite (``lua_runner``), the implementation-depth gate, the
regex integration contracts and the dedicated-server suite. The repair
evaluator in ``evaluator.py`` dispatches construct tasks here.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
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

from .analyzer import ModAnalyzer, strip_lua_comments
from .construct_catalog import DstConstructTask, IntegrationCheck
from .container import CONSTRUCT_RUNTIME_KEY, DstContainerRuntime, read_container_evaluation
from .runtime import DstRuntimeConfig

_SERVER_LOCK = threading.Lock()
_BEHAVIOR_TIMEOUT_SECONDS = 8
_SERVER_MARKER = "@@RHENIUM_SERVER@@"
_SERVER_SUITE_MODULE = "scripts/rhenium_server_test.lua"
# The scoring copy's modmain.lua becomes a wrapper that imports the candidate's own main chunk
# from this file and then registers the suite, so a main chunk may end in, or leave early
# through, a top-level ``return`` without cutting the suite off.
_CANDIDATE_MAIN = "rhenium_candidate_modmain.lua"
# DST's bundled json.encode escapes single quotes as \', which is not JSON, so any failure
# message such as "attempt to index local 'self'" made the whole result unparseable. The
# injected loader therefore encodes its fixed payload shape with standard JSON escaping.
_SERVER_PAYLOAD_ENCODER = r"""
local __rhenium_gsub = GLOBAL.string.gsub
local __rhenium_format = GLOBAL.string.format
local __rhenium_byte = GLOBAL.string.byte
local __rhenium_concat = GLOBAL.table.concat
local function __rhenium_json_escape(character)
    if character == '"' then
        return '\\"'
    elseif character == "\\" then
        return "\\\\"
    end
    return __rhenium_format("\\u%04x", __rhenium_byte(character))
end
local function __rhenium_json_string(value)
    local escaped = __rhenium_gsub(value, '[%c"\\]', __rhenium_json_escape)
    return '"' .. escaped .. '"'
end
local function __rhenium_encode_payload(payload)
    local encoded = {}
    for index, case in GLOBAL.ipairs(payload.cases) do
        encoded[index] = '{"name":' .. __rhenium_json_string(case.name)
            .. ',"passed":' .. (case.passed and "true" or "false")
            .. ',"message":' .. __rhenium_json_string(case.message) .. "}"
    end
    return '{"status":' .. __rhenium_json_string(payload.status)
        .. ',"cases":[' .. __rhenium_concat(encoded, ",") .. "]}"
end
"""


@dataclass(frozen=True)
class CheckResult:
    id: str
    status: str
    score: float
    maximum: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _case_set_mismatch(cases: list[dict[str, Any]], expected: tuple[str, ...]) -> bool:
    """Whether reported case names differ from a declared frozen case set."""
    if not expected:
        return False
    names = [str(case.get("name")) for case in cases]
    return len(set(names)) != len(names) or set(names) != set(expected)


class ConstructServerRunner:
    def __init__(self, settings: DstRuntimeConfig | Any):
        self.settings = (
            settings if isinstance(settings, DstRuntimeConfig) else DstRuntimeConfig.load(settings)
        )

    def binary(self) -> Path | None:
        if self.settings.server_binary:
            return self.settings.server_binary
        if self.settings.dst_root:
            candidate = self.settings.dst_root / "MacOS/dontstarve_dedicated_server_nullrenderer"
            if candidate.exists():
                return candidate
            candidate = self.settings.dst_root / "bin64/dontstarve_dedicated_server_nullrenderer_x64"
            if candidate.exists():
                return candidate
        return None

    def run_assertions(
        self,
        submission: Path,
        server_test: Path,
        timeout: int = 90,
        expected_cases: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        binary = self.binary()
        if not binary or not binary.is_file():
            return {
                "status": "unavailable",
                "message": "DST dedicated server was not found",
                "cases": [],
                "log": "",
            }
        mods_root = self._mods_root(binary)
        if not mods_root:
            return {
                "status": "unavailable",
                "message": "DST mods directory was not found",
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

        with _SERVER_LOCK, tempfile.TemporaryDirectory(prefix="rhenium-server-") as temp_value:
            temp = Path(temp_value)
            mod_name = f"rhenium_{uuid.uuid4().hex[:12]}"
            link = mods_root / mod_name
            storage = temp / "storage"
            master = storage / "DoNotStarveTogether/Cluster_1/Master"
            master.mkdir(parents=True)
            (master.parent / "cluster.ini").write_text(
                "[GAMEPLAY]\ngame_mode = survival\nmax_players = 1\npvp = false\n"
                "[NETWORK]\noffline_cluster = true\nlan_only_cluster = true\ncluster_name = Rhenium\n"
                "[MISC]\nconsole_enabled = true\n",
                encoding="utf-8",
            )
            (master / "server.ini").write_text(
                "[NETWORK]\nserver_port = 0\n[SHARD]\nis_master = true\n[ACCOUNT]\nencode_user_path = true\n",
                encoding="utf-8",
            )
            (master / "modoverrides.lua").write_text(
                f'return {{ ["{mod_name}"] = {{ enabled = true }} }}\n', encoding="utf-8"
            )
            try:
                shutil.copytree(submission.resolve(), link)
            except OSError as error:
                shutil.rmtree(link, ignore_errors=True)
                return {
                    "status": "unavailable",
                    "message": f"DST mods directory is not writable: {error}",
                    "cases": [],
                    "log": "",
                }
            nonce = uuid.uuid4().hex
            injection_error = self._inject_assertion_suite(link, server_test, nonce)
            if injection_error:
                shutil.rmtree(link, ignore_errors=True)
                return {
                    "status": "failed",
                    "message": injection_error,
                    "cases": [],
                    "log": "",
                }
            command = [
                str(binary),
                "-persistent_storage_root",
                str(storage),
                "-conf_dir",
                "DoNotStarveTogether",
                "-cluster",
                "Cluster_1",
                "-shard",
                "Master",
                "-skip_update_server_mods",
            ]
            process = subprocess.Popen(
                command,
                cwd=binary.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            if process.stdout:
                os.set_blocking(process.stdout.fileno(), False)
            output: list[str] = []
            deadline = time.monotonic() + timeout
            loaded = False
            suite_finished = False
            try:
                while time.monotonic() < deadline:
                    line = process.stdout.readline() if process.stdout else ""
                    if line:
                        output.append(line)
                        if "ModIndex: Load sequence finished successfully" in line:
                            loaded = True
                        if f"{_SERVER_MARKER}{nonce}:" in line:
                            suite_finished = True
                            break
                    elif process.poll() is not None:
                        break
                    else:
                        time.sleep(0.05)
            finally:
                interrupted: BaseException | None = None
                try:
                    if process.poll() is None:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            with suppress(ProcessLookupError):
                                os.killpg(process.pid, signal.SIGKILL)
                except BaseException as error:
                    interrupted = error
                    if process.poll() is None:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                finally:
                    if process.stdout:
                        output.extend(process.stdout.readlines())
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
                return self._parse_assertion_result(log, nonce, expected_cases)
            if not loaded:
                return {
                    "status": "failed",
                    "message": "Server exited or timed out before mod loading completed",
                    "cases": [],
                    "log": log,
                }
            return {
                "status": "failed",
                "message": "Headless server assertions did not finish before timeout",
                "cases": [],
                "log": log,
            }

    @staticmethod
    def _inject_assertion_suite(mod_root: Path, server_test: Path, nonce: str) -> str | None:
        modmain = mod_root / "modmain.lua"
        reserved = mod_root / _SERVER_SUITE_MODULE
        candidate_main = mod_root / _CANDIDATE_MAIN
        if not modmain.is_file():
            return "modmain.lua is required for headless server assertions"
        for name, path in ((_SERVER_SUITE_MODULE, reserved), (_CANDIDATE_MAIN, candidate_main)):
            if path.exists():
                return f"submission uses reserved assertion path: {name}"
        reserved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(server_test, reserved)
        loader = f'''-- Injected into the temporary scoring copy only.
modimport("{_CANDIDATE_MAIN}")
local __rhenium_suite = require("rhenium_server_test")
local __rhenium_pcall = GLOBAL.pcall
local __rhenium_tostring = GLOBAL.tostring
local __rhenium_ipairs = GLOBAL.ipairs
local __rhenium_print = GLOBAL.print
{_SERVER_PAYLOAD_ENCODER}
local function __rhenium_emit(payload)
    __rhenium_print("{_SERVER_MARKER}{nonce}:" .. __rhenium_encode_payload(payload))
end
AddPrefabPostInit("world", function(world)
    if not world.ismastersim then
        return
    end
    world:DoTaskInTime(1, function()
        local cases = {{}}
        local context = {{ world = world }}
        function context:case(name, body)
            local ok, message = __rhenium_pcall(body)
            cases[#cases + 1] = {{
                name = __rhenium_tostring(name),
                passed = ok,
                message = ok and "ok" or __rhenium_tostring(message),
            }}
        end
        local ok, message = __rhenium_pcall(__rhenium_suite, context)
        if not ok then
            cases[#cases + 1] = {{
                name = "suite execution",
                passed = false,
                message = __rhenium_tostring(message),
            }}
        end
        local passed = #cases > 0
        for _, case in __rhenium_ipairs(cases) do passed = passed and case.passed end
        __rhenium_emit({{ status = passed and "passed" or "failed", cases = cases }})
    end)
end)
'''
        try:
            # The candidate's bytes move unchanged, so its line numbers stay its own.
            modmain.rename(candidate_main)
            modmain.write_text(loader, encoding="utf-8")
        except OSError as error:
            return f"could not inject headless server assertions: {error}"
        return None

    @staticmethod
    def _parse_assertion_result(
        log: str, nonce: str, expected_cases: tuple[str, ...] = ()
    ) -> dict[str, Any]:
        prefix = f"{_SERVER_MARKER}{nonce}:"
        payloads: list[dict[str, Any]] = []
        for line in log.splitlines():
            if prefix not in line:
                continue
            raw = line.split(prefix, 1)[1].strip()
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
        if _case_set_mismatch(cases, expected_cases):
            return {
                "status": "error",
                "message": "Headless server suite cases do not match the task contract",
                "cases": [],
                "log": log,
            }
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
        for parent in binary.parents:
            candidate = parent / "mods"
            if candidate.is_dir():
                return candidate
        return None


class DstConstructEvaluator:
    def __init__(
        self, settings: DstRuntimeConfig | Any, container: DstContainerRuntime | None = None
    ):
        self.settings = (
            settings if isinstance(settings, DstRuntimeConfig) else DstRuntimeConfig.load(settings)
        )
        self.analyzer = ModAnalyzer()
        self.server = ConstructServerRunner(self.settings)
        self.container = container if container is not None else DstContainerRuntime()

    def runtime_status(self) -> dict[str, Any]:
        binary = self.server.binary()
        mods_root = self.server._mods_root(binary) if binary else None
        available = bool(binary and binary.is_file() and mods_root and os.access(mods_root, os.W_OK))
        return {
            "id": "dst-dedicated-server",
            "available": available,
            "binary": str(binary) if binary else None,
        }

    def evaluate(
        self,
        submission: Path,
        task: DstConstructTask,
        profile: str = "full",
        runtimes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported DST evaluation profile: {profile}")
        full_evaluation = profile == "full"
        artifact = (runtimes or {}).get(CONSTRUCT_RUNTIME_KEY)
        if full_evaluation and artifact is not None:
            return self._evaluate_in_container(submission.resolve(), task, artifact)
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
                server_result = self.server.run_assertions(
                    submission, server_test, expected_cases=task.server_cases
                )
        server_cases = server_result.get("cases", [])
        server_total = len(server_cases) if isinstance(server_cases, list) else 0
        server_passed = (
            sum(case.get("passed") is True for case in server_cases) if isinstance(server_cases, list) else 0
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

    def _evaluate_in_container(
        self, submission: Path, task: DstConstructTask, artifact: Any
    ) -> dict[str, Any]:
        """Run the whole full-profile evaluation inside the prepared task image.

        The image carries this evaluator byte-for-byte together with the pinned
        dedicated server, so the verdict is the same one a Harbor trial gets.
        Anything short of a consistent, complete report fails closed.
        """

        def incomplete(message: str, log: str) -> dict[str, Any]:
            check = CheckResult("headless-server", "unavailable", 0.0, 40.0, message)
            runtime = {"status": "unavailable", "message": message, "cases": []}
            return {
                "score": 0.0,
                "earned": 0.0,
                "available_maximum": 40.0,
                "rubric_maximum": 100.0,
                "complete": False,
                "passed": False,
                "checks": [asdict(check)],
                "runtime": runtime,
                "server": runtime,
                "runtime_log": log,
                "server_log": log,
            }

        metadata = getattr(artifact, "metadata", None)
        images = metadata.get("images") if isinstance(metadata, dict) else None
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        if not image_id:
            return incomplete(
                "managed DST runtime has no verifier image for this task",
                f"run rhenium runtime prepare {CONSTRUCT_RUNTIME_KEY}\n",
            )
        status = self.container.status()
        if not bool(status.get("available", False)):
            return incomplete(
                "pinned DST container runtime is unavailable",
                str(status.get("reason") or "runtime unavailable") + "\n",
            )
        cache_dir = self.settings.cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="dst-evaluation-", dir=cache_dir) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.container.run(submission, logs, image_id)
                if process.returncode != 0:
                    return incomplete(
                        "DST verifier container exited abnormally",
                        identity_log + (process.stdout + process.stderr)[-20_000:],
                    )
                result = read_container_evaluation(logs)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            return incomplete("DST verifier container did not produce a trusted report", f"{error}\n")
        log = identity_log + str(result.get("runtime_log", ""))
        return {**result, "runtime_log": log, "server_log": log}

    @staticmethod
    def _safe_candidate(root: Path, relative: str) -> Path | None:
        try:
            candidate = (root / relative).resolve(strict=True)
        except OSError:
            return None
        if not candidate.is_relative_to(root) or not candidate.is_file():
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
                if not resolved.is_relative_to(submission) or not resolved.is_file() or resolved in seen:
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

    def _run_behavior_tests(self, submission: Path, task: DstConstructTask) -> dict[str, Any]:
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
            os.pathsep.join((str(package_source), existing_path)) if existing_path else str(package_source)
        )
        environment["PYTHONIOENCODING"] = "utf-8"
        command = [
            sys.executable,
            "-m",
            "rhenium_dst.lua_runner",
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
        if _case_set_mismatch(normalised, task.hidden_cases):
            return {
                "status": "error",
                "cases": [],
                "message": "Hidden behavior cases do not match the task contract",
            }
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
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            matched_files.append(path.relative_to(submission).as_posix())
            chunks.append(strip_lua_comments(source))
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
            group_details.append({"name": group.name, "matched": matched, "pattern": matched_pattern})
        forbidden_matches = [pattern for pattern in check.none_of if re.search(pattern, merged, re.MULTILINE)]
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
