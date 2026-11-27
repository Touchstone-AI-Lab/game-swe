from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import (
    GLUATEST_RUNTIME_IDS,
    GarrysModCatalog,
    GarrysModTask,
    expected_case_count,
)

RUNTIME_ID = "gmod-gluatest-darkrp"
RUNTIME_KEY = f"garrys-mod/{RUNTIME_ID}"
SYNTH_RUNTIME_KEY = "garrys-mod/gmod-gluatest-synth"
RUNTIME_FINGERPRINT_LABEL = "io.rhenium.runtime.fingerprint"
RUNTIME_SOURCE_LABEL = "io.rhenium.runtime.source"
RUNTIME_TASK_LABEL = "io.rhenium.runtime.task"
RUNTIME_ID_LABEL = "io.rhenium.runtime.id"
RUNTIME_BUILD_LABEL = "io.rhenium.runtime.build-context"
RESULT_COLLECTOR = "gcb-patched-gluatest-runner-v2"
_EXPECTED_CASE_BLOCK = re.compile(r"EXPECTED_CASES=\((.*?)\n\)", re.DOTALL)
# Docker bookkeeping is instant on an idle daemon but can stall for minutes while a
# shared host flushes image layers; a stall must not turn into an incomplete verdict.
_DOCKER_TIMEOUT = 300
_EXPECTED_CASE = re.compile(r'^\s*"(.*)"\s*$', re.MULTILINE)
_HARNESS_TOKENS = (
    "gluatest",
    "gcb_audit",
    "gcb_run",
    "gluatest_clean_exit",
    "gluatest_failures",
)
_HARNESS_GLOBAL_ASSIGNMENT = re.compile(
    r"^\s*(?:_G\.)?(?:MsgC|MsgN|expect|stub|done|hook\.Run|util\.TableToJSON)\s*=",
    re.MULTILINE,
)
_NATIVE_MODULE_SUFFIXES = {".dll", ".dylib", ".so"}
# An addon's lua/ directory is mounted straight onto the server's Lua search path, so an
# addon submission could shadow the private harness (lua/gluatest/...) or add cases that
# GLuaTest collects (lua/tests/...). Neither path belongs to any shipped addon tree.
_ADDON_RESERVED_LUA_DIRECTORIES = frozenset({"gluatest", "tests"})


def runtime_id_for_catalog(catalog_id: str) -> str:
    """The runtime ID a GLuaTest pack is bound to (DarkRP's for unknown catalogs)."""
    return GLUATEST_RUNTIME_IDS.get(catalog_id, RUNTIME_ID)


class GarrysModRuntime:
    """Docker-backed headless Garry's Mod dedicated server running GLuaTest."""

    def __init__(self, context: BenchmarkContext, catalog: GarrysModCatalog):
        self.context = context
        self.catalog = catalog
        self.docker = shutil.which("docker") or ""
        self.image_prefix = "rhenium-garrys-mod"

    def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise RuntimeError("Docker CLI is not installed")
        return subprocess.run(
            [self.docker, *arguments], check=False, capture_output=True, text=True, timeout=timeout
        )

    def image_tag(self, task: GarrysModTask, fingerprint: str) -> str:
        return f"{self.image_prefix}:{task.id}-{self.catalog.version}-{fingerprint[:12]}"

    def image_id(self, reference: str) -> str:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError("Garry's Mod evaluator image is unavailable")
        return result.stdout.strip()

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"], timeout=_DOCKER_TIMEOUT
        )
        if result.returncode != 0:
            raise RuntimeError("Garry's Mod evaluator image is unavailable")
        try:
            labels = json.loads(result.stdout or "null")
        except json.JSONDecodeError as error:
            raise RuntimeError("Garry's Mod evaluator image has invalid labels") from error
        if labels is None:
            return {}
        if not isinstance(labels, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in labels.items()
        ):
            raise RuntimeError("Garry's Mod evaluator image has invalid labels")
        return labels

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "id": "garrys-mod-docker",
            "runtime": runtime_id_for_catalog(self.catalog.id),
            "network": "none",
        }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            info = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            return {**base, "available": False, "reason": f"Docker daemon probe failed: {error}"}
        if info.returncode != 0:
            return {**base, "available": False, "reason": "Docker daemon is unavailable"}
        return {
            **base,
            "available": True,
            "reason": None,
            "dockerVersion": info.stdout.strip(),
            "imagesRequired": len(self.catalog.tasks),
        }

    def validate_source_image(
        self,
        reference: str,
        recorded_image_id: str,
        expected_files: tuple[str, ...],
    ) -> None:
        if self.image_id(reference) != recorded_image_id:
            raise RuntimeError("container source record does not match the pulled image ID")
        if not expected_files:
            return
        command = (
            'for path in "$@"; do [ -e "/$path" ] || { '
            'echo "missing expected source file: $path" >&2; exit 1; }; done'
        )
        result = self._docker(
            [
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--pull=never",
                "--entrypoint",
                "/bin/sh",
                reference,
                "-eu",
                "-c",
                command,
                "rhenium-source-check",
                *expected_files,
            ],
            timeout=120,
        )
        if result.returncode != 0:
            log = (result.stdout + result.stderr)[-4000:]
            raise RuntimeError(f"container source is missing required runtime files\n{log}")

    def build_context_fingerprint(self, task: GarrysModTask) -> str:
        environment = self.context.pack_root / "private" / "harbor" / task.id / "environment"
        digest = hashlib.sha256()
        for candidate in sorted(
            environment.rglob("*"), key=lambda path: path.relative_to(environment).as_posix()
        ):
            if candidate.is_symlink():
                raise RuntimeError(f"task build context contains a symbolic link: {task.id}")
            relative = candidate.relative_to(environment).as_posix().encode()
            mode = str(stat.S_IMODE(candidate.stat().st_mode)).encode()
            if candidate.is_dir():
                digest.update(b"directory\0" + relative + b"\0" + mode + b"\0")
            elif candidate.is_file():
                digest.update(b"file\0" + relative + b"\0" + mode + b"\0")
                digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            else:
                raise RuntimeError(f"task build context contains an unsupported file: {task.id}")
        return f"sha256:{digest.hexdigest()}"

    def build_image(
        self,
        task: GarrysModTask,
        *,
        source_reference: str,
        fingerprint: str,
        runtime_id: str = RUNTIME_ID,
    ) -> tuple[str, str, str]:
        """Build and label a task image from the exact provider-acquired source."""
        environment = self.context.pack_root / "private" / "harbor" / task.id / "environment"
        dockerfile = environment / "Dockerfile"
        source_stages = []
        for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
            fields = raw_line.strip().split()
            if (
                len(fields) >= 4
                and fields[0].lower() == "from"
                and fields[-2].lower() == "as"
                and fields[-1].lower() == "gmod"
            ):
                source_stages.append(fields[1])
        if source_stages != [source_reference]:
            raise RuntimeError("task Dockerfile is not bound to the acquired container source")

        tag = self.image_tag(task, fingerprint)
        labels = {
            RUNTIME_FINGERPRINT_LABEL: fingerprint,
            RUNTIME_SOURCE_LABEL: source_reference,
            RUNTIME_TASK_LABEL: task.id,
            RUNTIME_ID_LABEL: runtime_id,
            RUNTIME_BUILD_LABEL: self.build_context_fingerprint(task),
        }
        arguments = ["build", "--pull=false", "--tag", tag]
        for key, value in labels.items():
            arguments.extend(("--label", f"{key}={value}"))
        arguments.extend(("--file", str(dockerfile), str(environment)))
        result = self._docker(
            arguments,
            timeout=7200,
        )
        log = result.stdout + result.stderr
        if result.returncode != 0:
            raise RuntimeError(f"failed to build Garry's Mod evaluator image\n{log[-8000:]}")
        return tag, self.image_id(tag), log

    def run(
        self, task: GarrysModTask, submission: Path, logs: Path, image_id: str
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        tests = (self.context.pack_root / "private" / "harbor" / task.id / "tests").resolve()
        # The container drops all capabilities, so its root cannot use CAP_DAC_OVERRIDE
        # to write into a bind mount owned by the host user. Create the verifier's
        # output directory here and make it world-writable, otherwise the very first
        # `mkdir -p /logs/verifier` fails and no test ever runs.
        verifier_logs = logs / "verifier"
        verifier_logs.mkdir(parents=True, exist_ok=True)
        verifier_logs.chmod(0o777)
        logs.chmod(0o777)
        # -rlptD is -a WITHOUT -o/-g on purpose. The container drops all capabilities,
        # so preserving ownership needs CAP_CHOWN, rsync fails every chown, and its
        # exit 23 aborts the run under `set -e` before a single test executes.
        # Permissions, times, links and devices are still preserved.
        command = (
            "set -euo pipefail; "
            f"rsync -rlptD --delete /submission/{task.starter_name}/ "
            f"{task.container_destination}/; "
            "bash /tests/test.sh"
        )
        arguments = [
            "run",
            "--rm",
            "--network=none",
            "--cpus=6",
            "--memory=16g",
            "--pids-limit=1024",
            # Drop everything, then add back only what the dedicated-server entrypoint
            # genuinely needs. It rsyncs the staged gamemode into its own game tree,
            # which is owned by the image's steam user, so as root it still requires
            # CHOWN, DAC_OVERRIDE and FOWNER. With a blanket --cap-drop=ALL the
            # entrypoint's own rsync fails and no test ever runs. Network is still
            # none, the submission and tests are read-only, and no host path beyond
            # the log directory is writable.
            "--cap-drop=ALL",
            "--cap-add=CHOWN",
            "--cap-add=DAC_OVERRIDE",
            "--cap-add=FOWNER",
            "--cap-add=FSETID",
            "--cap-add=SETGID",
            "--cap-add=SETUID",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={submission},target=/submission,readonly",
            "--mount",
            f"type=bind,source={tests},target=/tests,readonly",
            "--mount",
            f"type=bind,source={logs},target=/logs",
            "--pull=never",
            image_id,
            "bash",
            "-lc",
            command,
        ]
        result = self._docker(arguments, timeout=2400)
        return result, f"image={image_id}\nnetwork=none\n"


class GarrysModEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: GarrysModCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = GarrysModRuntime(context, catalog)

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _expected_case_names(pack_root: Path, task: GarrysModTask) -> tuple[str, ...]:
        verifier = pack_root / "private" / "harbor" / task.id / "tests" / "test.sh"
        block = _EXPECTED_CASE_BLOCK.search(verifier.read_text(encoding="utf-8"))
        if block is None:
            raise ValueError("private verifier does not declare its expected cases")
        names = tuple(_EXPECTED_CASE.findall(block.group(1)))
        if len(names) != expected_case_count(pack_root, task) or len(names) != len(set(names)):
            raise ValueError("private verifier expected-case list is invalid")
        return names

    @staticmethod
    def _enclosing_lines(text: str, start: int, end: int) -> str:
        first = text.rfind("\n", 0, start) + 1
        last = text.find("\n", end)
        return text[first : len(text) if last < 0 else last]

    @staticmethod
    def _has_lines(original: str, snippet: str) -> bool:
        """Whether ``snippet`` occurs in ``original`` as whole, exact lines."""
        return bool(snippet) and f"\n{snippet}\n" in f"\n{original}\n"

    @staticmethod
    def _contains_harness_tampering(starter: Path, baseline: Path | None = None) -> bool:
        """Reject direct result-hook/native-module attacks before starting the engine.

        A match is exempt only when its exact enclosing source lines also occur in the
        same file of the shipped starter (``baseline``): vendored upstream code may use
        a harness-like name (for example a local called ``done``), while every line a
        submission introduces is still scanned. The DarkRP starters contain no match at
        all, so for them this is the unconditional scan.
        """
        for path in starter.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in _NATIVE_MODULE_SUFFIXES:
                return True
            if path.suffix.lower() != ".lua":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            original = ""
            if baseline is not None:
                candidate = baseline / path.relative_to(starter)
                if candidate.is_file() and not candidate.is_symlink():
                    original = candidate.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            original_lowered = original.lower()
            for token in _HARNESS_TOKENS:
                position = lowered.find(token)
                while position >= 0:
                    snippet = GarrysModEvaluator._enclosing_lines(
                        lowered, position, position + len(token)
                    )
                    if not GarrysModEvaluator._has_lines(original_lowered, snippet):
                        return True
                    position = lowered.find(token, position + 1)
            for match in _HARNESS_GLOBAL_ASSIGNMENT.finditer(text):
                snippet = GarrysModEvaluator._enclosing_lines(text, match.start(), match.end())
                if not GarrysModEvaluator._has_lines(original, snippet):
                    return True
        return False

    @staticmethod
    def _shadows_addon_harness(starter: Path) -> bool:
        """Reject addon files that would shadow the harness or add collected cases."""
        lua = starter / "lua"
        if not lua.is_dir():
            return False
        return any(
            child.name.lower() in _ADDON_RESERVED_LUA_DIRECTORIES for child in lua.iterdir()
        )

    @staticmethod
    def _static_check(
        submission: Path, task: GarrysModTask, baseline: Path | None = None
    ) -> tuple[bool, dict[str, Any]]:
        starter = submission / task.starter_name
        addon = task.source_kind == "addon"
        safe = starter.is_dir() and not starter.is_symlink()
        if safe:
            safe = not any(path.is_symlink() for path in submission.rglob("*"))
        if safe:
            safe = (starter / ("lua" if addon else "gamemode")).is_dir()
        if safe:
            safe = all(
                (submission / relative).is_file() and not (submission / relative).is_symlink()
                for relative in task.required_files
            )
        tampered = safe and (
            GarrysModEvaluator._contains_harness_tampering(starter, baseline)
            or (addon and GarrysModEvaluator._shadows_addon_harness(starter))
        )
        safe = safe and not tampered
        if addon:
            accepted = "submission contains the required GLua addon tree"
            missing = "submission is missing the addon tree or contains symbolic links"
        else:
            accepted = (
                "submission contains the required GLua gamemode tree"
                if task.clean_room_synthetic
                else "submission contains the DarkRP gamemode tree"
            )
            missing = "submission is missing the gamemode tree or contains symbolic links"
        return safe, {
            "id": "submission-shape",
            "status": "passed" if safe else "failed",
            "score": 10.0 if safe else 0.0,
            "maximum": 10.0,
            "message": (
                accepted
                if safe
                else "submission attempts to alter the private result harness"
                if tampered
                else missing
            ),
        }

    @staticmethod
    def _verdict_is_trustworthy(
        verdict: dict[str, Any], expected_cases: tuple[str, ...]
    ) -> bool:
        """Cross-check the post-process collector's private runner audit."""
        expected = len(expected_cases)
        markers = verdict.get("markers")
        cases = verdict.get("cases")
        if not isinstance(markers, dict) or not isinstance(cases, list):
            return False
        if (
            verdict.get("schema") != 2
            or verdict.get("collector") != RESULT_COLLECTOR
            or verdict.get("complete") is not True
            or verdict.get("fatal") is not None
            or verdict.get("expected") != expected
            or verdict.get("passed") != expected
            or verdict.get("failed") != 0
            or verdict.get("reward") != 1
        ):
            return False
        required_true = (
            "audit_nonce_match",
            "audit_complete",
            "harness_unchanged",
            "clean_exit",
        )
        if any(markers.get(name) is not True for name in required_true):
            return False
        if markers.get("debug_log") is not False:
            return False
        if (
            markers.get("audit_line_count") != expected
            or markers.get("audit_complete_line_count") != 1
            or markers.get("audit_case_count") != expected
            or markers.get("audit_duplicate_cases") != 0
            or markers.get("no_failures_verdict") != 1
            or markers.get("failures_written") != 0
            or markers.get("empty_results") != 0
            or markers.get("skipped_results") != 0
        ):
            return False
        if len(cases) != expected:
            return False
        observed: list[str] = []
        for case in cases:
            if not isinstance(case, dict) or case.get("status") != "passed":
                return False
            case_id = case.get("id")
            if not isinstance(case_id, str):
                return False
            observed.append(case_id)
        return len(observed) == len(set(observed)) and set(observed) == set(expected_cases)

    @staticmethod
    def _case_outcomes(
        verdict: Any, expected_cases: tuple[str, ...], passed_count: int | None
    ) -> dict[str, bool]:
        """Name-level outcomes of a complete run, or nothing when they are not exact.

        This is reporting only: it never changes the verdict. A case is True only
        when the private audit recorded it as passed.
        """
        cases = verdict.get("cases") if isinstance(verdict, dict) else None
        if not isinstance(cases, list):
            return {}
        outcomes: dict[str, bool] = {}
        for case in cases:
            if not isinstance(case, dict):
                return {}
            case_id, status = case.get("id"), case.get("status")
            if not isinstance(case_id, str) or not isinstance(status, str) or case_id in outcomes:
                return {}
            outcomes[case_id] = status == "passed"
        if set(outcomes) != set(expected_cases) or sum(outcomes.values()) != passed_count:
            return {}
        return outcomes

    @staticmethod
    def _read_runtime_log(logs: Path, process: subprocess.CompletedProcess[str]) -> str:
        sections = [process.stdout, process.stderr]
        for name in ("verifier/result.json", "verifier/server.log"):
            path = logs / name
            if path.is_file():
                sections.append(
                    f"\n== {name} ==\n{path.read_text(encoding='utf-8', errors='replace')}"
                )
        return "".join(sections)[-200_000:]

    def evaluate(
        self,
        submission: Path,
        task: GarrysModTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Garry's Mod evaluation profile: {profile}")
        if not isinstance(task, GarrysModTask):
            raise TypeError("Garry's Mod evaluator received a non-Garry's Mod task")

        baseline = (
            self.context.pack_root / "private" / "harbor" / task.id / "environment"
        ) / task.starter_name
        static_ok, static_check = self._static_check(submission, task, baseline)
        checks: list[dict[str, Any]] = [static_check]

        def incomplete(message: str, log: str, status: str) -> dict[str, Any]:
            checks.append(
                {
                    "id": "headless-server",
                    "status": "skipped" if status == "skipped" else "failed",
                    "score": 0.0,
                    "maximum": 90.0,
                    "message": message,
                }
            )
            return {
                "score": float(static_check["score"]),
                "complete": False,
                "passed": False,
                "checks": checks,
                "runtime": {"status": status},
                "runtime_log": log,
            }

        if profile == "core" or not static_ok:
            return incomplete(
                "headless server assertions are disabled in the core profile"
                if static_ok
                else "headless server assertions were not run for an invalid submission",
                "Garry's Mod headless runtime did not run\n",
                "skipped" if static_ok else "failed",
            )

        status = self.runtime.status()
        if not bool(status.get("available", False)):
            return incomplete(
                "pinned Garry's Mod headless runtime is unavailable",
                str(status.get("reason") or "runtime unavailable") + "\n",
                "unavailable",
            )

        runtime_key = (
            SYNTH_RUNTIME_KEY
            if task.clean_room_synthetic
            else f"garrys-mod/{runtime_id_for_catalog(self.catalog.id)}"
        )
        artifact = (runtimes or {}).get(runtime_key)
        images = artifact.metadata.get("images", {}) if artifact is not None else {}
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        if not image_id:
            return incomplete(
                "managed Garry's Mod runtime is not prepared",
                f"run rhenium runtime prepare {runtime_key}\n",
                "unavailable",
            )

        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        runtime_log = ""
        complete = False
        passed = False
        passed_count: int | None = None
        failed_count: int | None = None
        case_outcomes: dict[str, bool] = {}
        try:
            with tempfile.TemporaryDirectory(
                prefix="garrys-mod-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.runtime.run(task, submission, logs, image_id)
                runtime_log = identity_log + self._read_runtime_log(logs, process)
                result_path = logs / "verifier" / "result.json"
                reward_path = logs / "verifier" / "reward.txt"
                verdict = (
                    json.loads(result_path.read_text(encoding="utf-8"))
                    if result_path.is_file()
                    else {}
                )
                expected_cases = self._expected_case_names(self.context.pack_root, task)
                expected = len(expected_cases)
                passed_value = verdict.get("passed") if isinstance(verdict, dict) else None
                failed_value = verdict.get("failed") if isinstance(verdict, dict) else None
                passed_count = passed_value if type(passed_value) is int else None
                failed_count = failed_value if type(failed_value) is int else None
                complete = bool(
                    isinstance(verdict, dict)
                    and process.returncode == 0
                    and verdict.get("schema") == 2
                    and verdict.get("collector") == RESULT_COLLECTOR
                    and verdict.get("complete") is True
                    and passed_count is not None
                    and failed_count is not None
                    and passed_count + failed_count == expected
                    and verdict.get("fatal") is None
                )
                case_outcomes = self._case_outcomes(verdict, expected_cases, passed_count)
                reward = (
                    reward_path.read_text(encoding="utf-8").strip() if reward_path.is_file() else "0"
                )
                passed = bool(
                    complete
                    and process.returncode == 0
                    and passed_count == expected
                    and failed_count == 0
                    and reward == "1"
                    and verdict.get("reward") == 1
                    and self._verdict_is_trustworthy(verdict, expected_cases)
                )
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, TypeError) as error:
            runtime_log += f"runtime error: {error}\n"
            complete = False
            passed = False

        checks.append(
            {
                "id": "headless-server",
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "score": 90.0 if passed else 0.0,
                "maximum": 90.0,
                "message": (
                    "all headless GLuaTest assertions passed"
                    if passed
                    else "headless GLuaTest assertions failed"
                    if complete
                    else "headless GLuaTest assertions did not complete"
                ),
            }
        )
        return {
            "score": 100.0 if passed else float(static_check["score"]),
            "complete": complete,
            "passed": passed,
            "checks": checks,
            "runtime": {
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "passedAssertions": passed_count or 0,
                "failedAssertions": failed_count or 0,
                "caseOutcomes": case_outcomes if complete else {},
            },
            "runtime_log": runtime_log,
        }
