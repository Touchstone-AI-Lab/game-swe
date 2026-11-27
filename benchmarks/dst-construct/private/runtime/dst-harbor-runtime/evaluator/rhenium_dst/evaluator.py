from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from .analyzer import ModAnalyzer
from .catalog import STARTER_NAME, DstTask, ModOptionValue
from .construct_catalog import DstConstructTask
from .construct_evaluator import DstConstructEvaluator
from .container import RUNTIME_KEY, DstContainerRuntime, read_container_evaluation
from .runtime import DstRuntimeConfig

_SERVER_LOCK = threading.Lock()
_SERVER_MARKER = "@@RHENIUM_SERVER@@"
_SERVER_SUITE_MODULE = "scripts/rhenium_server_test.lua"
# Server boot and world generation take 25-60 s on the pinned build; suites may
# also wait a bounded amount of simulated time between steps.
_SERVER_TIMEOUT_SECONDS = 360
# A suite may schedule follow-up steps, but never for longer than this in total.
_SUITE_BUDGET_SECONDS = 180
SHAPE_WEIGHT = 10.0
SERVER_WEIGHT = 90.0
# Strings a submitted mod has no reason to contain: they only occur in the private
# scoring harness, so a submission carrying them is trying to reach into it.
_HARNESS_TOKENS = ("@@RHENIUM_SERVER@@", "rhenium_server_test", "__rhenium_")
_NATIVE_SUFFIXES = {".dll", ".dylib", ".so"}
# DST's bundled json.encode escapes single quotes as \', which is not JSON, so any
# failure message such as "attempt to index local 'self'" made the whole result
# unparseable. The injected loader therefore encodes its fixed payload shape with
# standard JSON escaping.
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
    for index, case in __rhenium_ipairs(payload.cases) do
        encoded[index] = '{"name":' .. __rhenium_json_string(case.name)
            .. ',"passed":' .. (case.passed and "true" or "false")
            .. ',"message":' .. __rhenium_json_string(case.message) .. "}"
    end
    return '{"status":' .. __rhenium_json_string(payload.status)
        .. ',"cases":[' .. __rhenium_concat(encoded, ",") .. "]}"
end
"""


def _case_set_mismatch(cases: list[dict[str, Any]], expected: tuple[str, ...]) -> bool:
    """Whether reported case names differ from the declared frozen case set."""
    names = [str(case.get("name")) for case in cases]
    return len(set(names)) != len(names) or set(names) != set(expected)


def _lua_literal(value: ModOptionValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("mod option numbers must be finite")
        return repr(value)
    if any(char in value for char in "\"\\\n\r"):
        raise ValueError("mod option strings must not contain quotes or line breaks")
    return f'"{value}"'


def modoverrides(mod_name: str, options: dict[str, ModOptionValue]) -> str:
    """The server's modoverrides.lua enabling one mod with the operator's options."""
    entries = "".join(
        f"      {key} = {_lua_literal(value)},\n" for key, value in sorted(options.items())
    )
    configuration = f"    configuration_options = {{\n{entries}    }},\n" if entries else ""
    return f'return {{\n  ["{mod_name}"] = {{\n    enabled = true,\n{configuration}  }},\n}}\n'


class DedicatedServerRunner:
    """Runs one hidden suite inside the pinned dedicated server, networkless."""

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
        mod_root: Path,
        server_test: Path,
        *,
        expected_cases: tuple[str, ...],
        mod_options: dict[str, ModOptionValue] | None = None,
        timeout: int = _SERVER_TIMEOUT_SECONDS,
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
                "pause_when_empty = false\n"
                "[NETWORK]\noffline_cluster = true\nlan_only_cluster = true\ncluster_name = Rhenium\n"
                "[MISC]\nconsole_enabled = true\n",
                encoding="utf-8",
            )
            (master / "server.ini").write_text(
                "[NETWORK]\nserver_port = 0\n[SHARD]\nis_master = true\n[ACCOUNT]\nencode_user_path = true\n",
                encoding="utf-8",
            )
            try:
                (master / "modoverrides.lua").write_text(
                    modoverrides(mod_name, mod_options or {}), encoding="utf-8"
                )
            except ValueError as error:
                return {"status": "error", "message": str(error), "cases": [], "log": ""}
            try:
                shutil.copytree(mod_root.resolve(), link, symlinks=True)
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
                errors="replace",
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
                        with suppress(OSError, ValueError):
                            output.extend(process.stdout.readlines())
                    shutil.rmtree(link, ignore_errors=True)
                if interrupted is not None:
                    raise interrupted

            log = "".join(output)
            candidate_errors = self._candidate_error_lines(log, mod_name)
            if candidate_errors:
                return {
                    "status": "failed",
                    "message": "the submitted mod raised a server error: "
                    + candidate_errors[-1].replace(mod_name, "<mod>")[:400],
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
    def loader_source(nonce: str) -> str:
        """The scoring loader prepended to the temporary copy's modmain.lua.

        It runs first, in the untouched mod environment, so it captures the
        library functions it relies on before any submitted code executes and
        still works when a mod later switches its own chunk environment. The
        suite starts one second after the master world exists with ``ctx.world``
        and ``ctx.modname`` (the scoring copy's mod folder, which namespaces its
        RPCs). ``ctx:case`` records a synchronous case; ``ctx:after`` schedules a
        follow-up step on the world clock, and the payload is emitted once no
        step is pending.
        """
        return f'''do -- Injected into the temporary scoring copy only.
local __rhenium_require = GLOBAL.require
local __rhenium_pcall = GLOBAL.pcall
local __rhenium_tostring = GLOBAL.tostring
local __rhenium_ipairs = GLOBAL.ipairs
local __rhenium_type = GLOBAL.type
local __rhenium_print = GLOBAL.print
local __rhenium_budget = {_SUITE_BUDGET_SECONDS}
local __rhenium_modname = modname
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
        local pending = 0
        local scheduled = 0
        local finished = false
        local context = {{ world = world, modname = __rhenium_modname }}
        local function record(name, ok, message)
            cases[#cases + 1] = {{
                name = __rhenium_tostring(name),
                passed = ok and true or false,
                message = ok and "ok" or __rhenium_tostring(message),
            }}
        end
        local function finish()
            if finished or pending > 0 then
                return
            end
            finished = true
            local passed = #cases > 0
            for _, case in __rhenium_ipairs(cases) do passed = passed and case.passed end
            __rhenium_emit({{ status = passed and "passed" or "failed", cases = cases }})
        end
        function context:case(name, body)
            local ok, message = __rhenium_pcall(body)
            record(name, ok, message)
        end
        function context:after(seconds, body)
            if __rhenium_type(seconds) ~= "number" or seconds < 0
                or scheduled + seconds > __rhenium_budget then
                record("suite scheduling", false, "a step exceeds the suite time budget")
                return
            end
            scheduled = scheduled + seconds
            pending = pending + 1
            world:DoTaskInTime(seconds, function()
                local ok, message = __rhenium_pcall(body, context)
                if not ok then
                    record("suite step", false, message)
                end
                pending = pending - 1
                finish()
            end)
        end
        local loaded, suite = __rhenium_pcall(__rhenium_require, "rhenium_server_test")
        if not loaded or __rhenium_type(suite) ~= "function" then
            record("suite execution", false, loaded and "suite is not a function" or suite)
        else
            local ok, message = __rhenium_pcall(suite, context)
            if not ok then
                record("suite execution", false, message)
            end
        end
        finish()
    end)
end)
end
'''

    @classmethod
    def _inject_assertion_suite(cls, mod_root: Path, server_test: Path, nonce: str) -> str | None:
        modmain = mod_root / "modmain.lua"
        reserved = mod_root / _SERVER_SUITE_MODULE
        if not modmain.is_file() or modmain.is_symlink():
            return "modmain.lua is required for headless server assertions"
        if reserved.exists() or reserved.is_symlink():
            return f"submission uses reserved assertion path: {_SERVER_SUITE_MODULE}"
        try:
            original = modmain.read_text(encoding="utf-8", errors="surrogateescape")
            reserved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(server_test, reserved)
            # A leading byte-order mark or shebang must stay first for the Lua loader.
            prefix = ""
            if original.startswith("﻿"):
                prefix, original = "﻿", original[1:]
            modmain.write_text(
                prefix + cls.loader_source(nonce) + original,
                encoding="utf-8",
                errors="surrogateescape",
            )
        except OSError as error:
            return f"could not inject headless server assertions: {error}"
        return None

    @staticmethod
    def _parse_assertion_result(
        log: str, nonce: str, expected_cases: tuple[str, ...]
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
                "cases": [],
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


def _shape_check(submission: Path, task: DstTask) -> tuple[bool, dict[str, Any]]:
    """The submission-shape gate: a real mod tree, required files, parseable Lua.

    It rejects symbolic links and native modules outright, and any Lua source
    that names the private scoring harness.
    """
    starter = submission / STARTER_NAME
    problems: list[str] = []
    syntax_errors: list[dict[str, Any]] = []
    if starter.is_symlink() or not starter.is_dir():
        problems.append(f"the {STARTER_NAME}/ directory is missing")
    else:
        for path in sorted(starter.rglob("*")):
            relative = path.relative_to(submission).as_posix()
            if path.is_symlink():
                problems.append(f"symbolic link: {relative}")
            elif path.is_file() and path.suffix.lower() in _NATIVE_SUFFIXES:
                problems.append(f"native module: {relative}")
            elif path.is_file() and path.suffix.lower() == ".lua":
                text = path.read_text(encoding="utf-8", errors="replace")
                if any(token in text for token in _HARNESS_TOKENS):
                    problems.append(f"reference to the private scoring harness: {relative}")
        for relative in task.required_files:
            candidate = submission / relative
            if candidate.is_symlink() or not candidate.is_file():
                problems.append(f"required file is missing: {relative}")
        if not problems:
            analysis = ModAnalyzer().analyze(starter)
            syntax_errors = list(analysis.get("syntax_errors", []))
            if syntax_errors:
                problems.append("Lua source contains syntax errors")
    passed = not problems
    return passed, {
        "id": "submission-shape",
        "status": "passed" if passed else "failed",
        "score": SHAPE_WEIGHT if passed else 0.0,
        "maximum": SHAPE_WEIGHT,
        "message": (
            f"submission contains the {STARTER_NAME}/ tree with every required file"
            if passed
            else problems[0]
        ),
        "details": {"problems": problems[:20], "syntax_errors": syntax_errors[:20]},
    }


def _case_outcomes(cases: list[dict[str, Any]], expected: tuple[str, ...]) -> dict[str, bool]:
    """Name-level outcomes of a complete run, or nothing when they are not exact."""
    outcomes = {str(case.get("name")): case.get("passed") is True for case in cases}
    if len(outcomes) != len(cases) or set(outcomes) != set(expected):
        return {}
    return outcomes


class DstEvaluator:
    """Scores a repaired mod against the task's frozen dedicated-server suite.

    The score is 10 for the submission-shape gate plus 90 when every hidden
    server case passes; a run counts as complete only when the pinned server
    observed exactly the frozen case set.

    A task of the construct catalog is handed to the restored construct
    evaluator, which shares this evaluator's settings and container runtime.
    """

    def __init__(self, settings: DstRuntimeConfig | Any):
        self.settings = (
            settings if isinstance(settings, DstRuntimeConfig) else DstRuntimeConfig.load(settings)
        )
        self.server = DedicatedServerRunner(self.settings)
        self.container = DstContainerRuntime()
        self.construct = DstConstructEvaluator(self.settings, self.container)

    def runtime_status(self) -> dict[str, Any]:
        binary = self.server.binary()
        mods_root = self.server._mods_root(binary) if binary else None
        available = bool(binary and binary.is_file() and mods_root and os.access(mods_root, os.W_OK))
        return {
            "id": "dst-dedicated-server",
            "available": available,
            "binary": str(binary) if binary else None,
        }

    @staticmethod
    def _result(
        shape: dict[str, Any],
        server: dict[str, Any],
        task: DstTask,
        log: str,
    ) -> dict[str, Any]:
        raw_cases = server.get("cases")
        cases: list[dict[str, Any]] = raw_cases if isinstance(raw_cases, list) else []
        status = str(server.get("status", "error"))
        complete = status in {"passed", "failed"} and bool(cases)
        passed = complete and status == "passed" and shape["status"] == "passed"
        passed_count = sum(case.get("passed") is True for case in cases) if complete else 0
        outcomes = _case_outcomes(cases, task.server_cases) if complete else {}
        if complete and not outcomes:
            complete = passed = False
            passed_count = 0
        check_status = "passed" if passed else "failed" if complete else "incomplete"
        server_check = {
            "id": "headless-server",
            "status": check_status,
            "score": SERVER_WEIGHT if passed else 0.0,
            "maximum": SERVER_WEIGHT,
            "message": (
                f"all {len(task.server_cases)} dedicated-server assertions passed"
                if passed
                else f"{passed_count}/{len(task.server_cases)} dedicated-server assertions passed"
                if complete
                else str(server.get("message") or "dedicated-server assertions did not complete")
            ),
            "details": {
                "passed": passed_count,
                "total": len(task.server_cases),
                "cases": cases if complete else [],
                "runner_status": status,
            },
        }
        score = SHAPE_WEIGHT + SERVER_WEIGHT if passed else float(shape["score"])
        return {
            "score": score,
            "earned": score,
            "available_maximum": SHAPE_WEIGHT + SERVER_WEIGHT,
            "rubric_maximum": SHAPE_WEIGHT + SERVER_WEIGHT,
            "complete": complete,
            "passed": passed,
            "checks": [shape, server_check],
            "runtime": {
                "status": check_status,
                "message": server_check["message"],
                "expectedAssertions": len(task.server_cases),
                "passedAssertions": passed_count,
                "failedAssertions": len(outcomes) - passed_count if complete else 0,
                "caseOutcomes": outcomes if complete else {},
            },
            "runtime_log": log,
        }

    def evaluate(
        self,
        submission: Path,
        task: DstTask | DstConstructTask,
        profile: str = "full",
        runtimes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(task, DstConstructTask):
            return self.construct.evaluate(submission, task, profile, runtimes)
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported DST evaluation profile: {profile}")
        if not isinstance(task, DstTask):
            raise TypeError("DST evaluator received a non-DST task")
        submission = submission.resolve()
        shape_ok, shape = _shape_check(submission, task)
        if not shape_ok:
            return self._result(
                shape,
                {"status": "failed", "message": "the server was not started for an invalid submission"},
                task,
                "Don't Starve Together dedicated server did not run\n",
            )
        if profile == "core":
            return self._result(
                shape,
                {"status": "skipped", "message": "server assertions are disabled in the core profile"},
                task,
                "Don't Starve Together dedicated server did not run\n",
            )
        artifact = (runtimes or {}).get(RUNTIME_KEY)
        if artifact is not None:
            return self._evaluate_in_container(submission, task, artifact)
        dataset_root = self.settings.pack_root.resolve()
        server_test = (dataset_root / task.server_test).resolve()
        if not server_test.is_relative_to(dataset_root):
            return self._result(
                shape,
                {"status": "error", "message": "Headless server assertion path is unsafe"},
                task,
                "",
            )
        server = self.server.run_assertions(
            submission / STARTER_NAME,
            server_test,
            expected_cases=task.server_cases,
            mod_options=task.mod_options,
        )
        return self._result(shape, server, task, str(server.get("log", "")))

    def _evaluate_in_container(self, submission: Path, task: DstTask, artifact: Any) -> dict[str, Any]:
        """Run the whole full-profile evaluation inside the prepared task image.

        The image carries this evaluator byte-for-byte together with the pinned
        dedicated server, so the verdict is the same one a Harbor trial gets.
        Anything short of a consistent, complete report fails closed.
        """

        def incomplete(message: str, log: str) -> dict[str, Any]:
            _shape_ok, shape = _shape_check(submission, task)
            result = self._result(shape, {"status": "unavailable", "message": message}, task, log)
            return {**result, "score": 0.0, "earned": 0.0}

        metadata = getattr(artifact, "metadata", None)
        images = metadata.get("images") if isinstance(metadata, dict) else None
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        if not image_id:
            return incomplete(
                "managed DST runtime has no verifier image for this task",
                f"run rhenium runtime prepare {RUNTIME_KEY}\n",
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
                process, identity_log = self.container.run(submission / STARTER_NAME, logs, image_id)
                if process.returncode != 0:
                    return incomplete(
                        "DST verifier container exited abnormally",
                        identity_log + (process.stdout + process.stderr)[-20_000:],
                    )
                result = read_container_evaluation(logs)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            return incomplete("DST verifier container did not produce a trusted report", f"{error}\n")
        return {**result, "runtime_log": identity_log + str(result.get("runtime_log", ""))}
