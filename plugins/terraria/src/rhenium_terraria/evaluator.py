from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import (
    TerrariaCatalog,
    TerrariaTask,
    expected_case_names,
    expected_engine_case_names,
)

SOURCE_RUNTIME_ID = "dotnet-8.0.419-source-projection"
SOURCE_RUNTIME_KEY = f"terraria/{SOURCE_RUNTIME_ID}"
ENGINE_RUNTIME_ID = "tmodloader-2026.07.3.0-server"
ENGINE_RUNTIME_KEY = f"terraria/{ENGINE_RUNTIME_ID}"
# Compatibility aliases for the original source-projection-only plugin API.
RUNTIME_ID = SOURCE_RUNTIME_ID
RUNTIME_KEY = SOURCE_RUNTIME_KEY
GAME_VERSION = "1.4.4.9"
TMODLOADER_API = "1.4.4 stable API"
TMODLOADER_VERSION = "2026.7.3.0"
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
# Control operations (create, copy, remove, inspect) wait for a congested daemon on a
# shared host; the verifier processes themselves keep their own limits.
_DOCKER_TIMEOUT = 300
_ENGINE_REPORT_MARKER = "GCB_TERRARIA_REPORT_V1="
_MAX_ENGINE_REPORT_BYTES = 262_144
_FORBIDDEN_SUFFIXES = {".dll", ".exe", ".pdb", ".so", ".tmod", ".zip", ".7z", ".tar", ".gz"}
_FORBIDDEN_DIRECTORIES = {".git", "bin", "obj"}


class TerrariaRuntime:
    def __init__(self, context: BenchmarkContext, catalog: TerrariaCatalog):
        self.context = context
        self.catalog = catalog
        self.docker = shutil.which("docker") or ""

    def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise RuntimeError("Docker CLI is not installed")
        return subprocess.run(
            [self.docker, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def image_id(self, reference: str) -> str:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
        )
        image_id = result.stdout.strip()
        if result.returncode != 0 or _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError(f"Terraria runtime image is unavailable: {reference}")
        return image_id

    def image_labels(self, reference: str) -> dict[str, str]:
        result = self._docker(
            ["image", "inspect", reference, "--format", "{{json .Config.Labels}}"],
            timeout=_DOCKER_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Terraria runtime image is unavailable: {reference}")
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("Terraria runtime image labels are invalid") from error
        if parsed is None:
            return {}
        if not isinstance(parsed, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in parsed.items()
        ):
            raise RuntimeError("Terraria runtime image labels are invalid")
        return parsed

    def status(self) -> dict[str, Any]:
        base = {
            "id": "terraria-docker",
            "runtime": RUNTIME_ID,
            "gameVersion": GAME_VERSION,
            "tModLoaderApi": TMODLOADER_API,
            "evaluationBoundary": "offline production-source projection",
            "network": "none",
        }
        if not self.docker:
            return {**base, "available": False, "reason": "Docker CLI is not installed"}
        try:
            result = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=_DOCKER_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as error:
            return {**base, "available": False, "reason": str(error)}
        if result.returncode != 0:
            return {**base, "available": False, "reason": "Docker daemon is unavailable"}
        return {
            **base,
            "available": True,
            "reason": None,
            "dockerVersion": result.stdout.strip(),
            "imagesRequired": len(self.catalog.tasks),
        }

    def run(
        self,
        task: TerrariaTask,
        submission: Path,
        logs: Path,
        image_id: str,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError("Terraria evaluation requires an immutable image ID")
        task_root = self.context.pack_root / "private" / "harbor" / task.id
        tests = (task_root / "tests").resolve()
        submission = submission.resolve()
        logs = logs.resolve()
        logs.mkdir(parents=True, exist_ok=True)

        arguments = [
            "create",
            "--pull=never",
            "--network=none",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--mount",
            f"type=bind,source={submission},target=/solution,readonly",
            "--mount",
            f"type=bind,source={tests},target=/tests,readonly",
            image_id,
            "bash",
            "-c",
            "set -euo pipefail; install -d -m 0755 /logs /logs/verifier; "
            "cp -R /solution/. /workspace/; exec bash /tests/test.sh",
        ]
        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            raise RuntimeError("could not create the isolated Terraria verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=1200)
            copied = self._docker(["cp", f"{container_id}:/logs/.", str(logs)], timeout=_DOCKER_TIMEOUT)
            if copied.returncode != 0:
                raise RuntimeError("could not collect the Terraria verifier reports")
            if any(path.is_symlink() for path in logs.rglob("*")):
                raise RuntimeError("Terraria verifier reports contain a symbolic link")
            return process, f"image={image_id}\nnetwork=none\n"
        finally:
            with suppress(OSError, subprocess.SubprocessError):
                self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)


class TerrariaEngineRuntime(TerrariaRuntime):
    def status(self) -> dict[str, Any]:
        status = super().status()
        return {
            **status,
            "runtime": ENGINE_RUNTIME_ID,
            "gameVersion": GAME_VERSION,
            "tModLoaderVersion": TMODLOADER_VERSION,
            "evaluationBoundary": "real tModLoader dedicated-server process",
        }

    def run_image(
        self,
        image_id: str,
        reports: Path,
        submission: Path | None = None,
        *,
        timeout: float = 1800,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError("Terraria engine evaluation requires an immutable image ID")
        reports = reports.resolve()
        reports.mkdir(parents=True, exist_ok=True)
        if reports.is_symlink() or any(reports.iterdir()):
            raise RuntimeError("Terraria engine report destination must be an empty directory")

        arguments = [
            "create",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cpus=4",
            "--memory=8g",
            "--pids-limit=1024",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--tmpfs",
            "/tmp:rw,exec,nosuid,size=256m,uid=10001,gid=10001,mode=1777",
            "--tmpfs",
            "/workspace:rw,exec,nosuid,size=2g,uid=10001,gid=10001,mode=0755",
            "--tmpfs",
            "/state:rw,exec,nosuid,size=1g,uid=10001,gid=10001,mode=0755",
            "--tmpfs",
            "/reports:rw,noexec,nosuid,size=16m,uid=10001,gid=10001,mode=0755",
            "--tmpfs",
            (
                "/opt/tmodloader/tModLoader-Logs:rw,noexec,nosuid,size=64m,"
                "uid=10001,gid=10001,mode=0755"
            ),
            "--env",
            "GCB_TERRARIA_REPORT=/reports/engine-report.json",
        ]
        if submission is not None:
            arguments.extend(
                (
                    "--mount",
                    f"type=bind,source={submission.resolve()},target=/solution,readonly",
                )
            )
        arguments.append(image_id)

        created = self._docker(arguments, timeout=_DOCKER_TIMEOUT)
        container_id = created.stdout.strip()
        if created.returncode != 0 or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
            raise RuntimeError("could not create the isolated Terraria engine verifier")
        try:
            process = self._docker(["start", "--attach", container_id], timeout=timeout)
            self._collect_report(process.stdout or "", reports)
            if any(path.is_symlink() for path in reports.rglob("*")):
                raise RuntimeError("Terraria engine reports contain a symbolic link")
            return process, (
                f"image={image_id}\nnetwork=none\n"
                f"game=Terraria-{GAME_VERSION}\n"
                f"tModLoader={TMODLOADER_VERSION}\n"
            )
        finally:
            with suppress(OSError, subprocess.SubprocessError):
                self._docker(["rm", "--force", container_id], timeout=_DOCKER_TIMEOUT)

    @staticmethod
    def _collect_report(output: str, reports: Path) -> None:
        encoded = [
            line.removeprefix(_ENGINE_REPORT_MARKER)
            for line in output.splitlines()
            if line.startswith(_ENGINE_REPORT_MARKER)
        ]
        if not encoded:
            return
        if len(encoded) != 1:
            raise RuntimeError("Terraria engine verifier emitted multiple reports")
        try:
            payload = base64.b64decode(encoded[0], validate=True)
        except (binascii.Error, ValueError) as error:
            raise RuntimeError("Terraria engine verifier emitted an invalid report") from error
        if len(payload) > _MAX_ENGINE_REPORT_BYTES:
            raise RuntimeError("Terraria engine verifier report exceeds the size limit")
        report_path = reports / "engine-report.json"
        with report_path.open("xb") as handle:
            handle.write(payload)


class TerrariaEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: TerrariaCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = TerrariaRuntime(context, catalog)
        self.engine_runtime = TerrariaEngineRuntime(context, catalog)

    def runtime_status(self) -> dict[str, Any]:
        source = self.runtime.status()
        engine = self.engine_runtime.status()
        return {
            "id": "terraria-layered-docker",
            "available": source.get("available") is True and engine.get("available") is True,
            "reason": source.get("reason") or engine.get("reason"),
            "network": "none",
            "gameVersion": GAME_VERSION,
            "tModLoaderVersion": TMODLOADER_VERSION,
            "layers": {"sourceProjection": source, "realEngine": engine},
        }

    @staticmethod
    def _static_check(submission: Path, task: TerrariaTask) -> tuple[bool, dict[str, Any]]:
        safe = submission.is_dir() and not submission.is_symlink()
        if safe:
            safe = not any(path.is_symlink() for path in submission.rglob("*"))
        if safe:
            safe = all((submission / relative).is_file() for relative in task.required_files)
        if safe:
            safe = not any(
                any(part in _FORBIDDEN_DIRECTORIES for part in path.relative_to(submission).parts)
                or (path.is_file() and path.suffix.lower() in _FORBIDDEN_SUFFIXES)
                for path in submission.rglob("*")
            )
        return safe, {
            "id": "submission-shape",
            "status": "passed" if safe else "failed",
            "score": 10.0 if safe else 0.0,
            "maximum": 10.0,
            "message": (
                "submission contains the required source-only files"
                if safe
                else "submission is missing required source or contains forbidden files"
            ),
        }

    @staticmethod
    def _artifact_image(
        task: TerrariaTask,
        runtimes: dict[str, RuntimeArtifact] | None,
        runtime_key: str,
    ) -> str:
        if not runtimes or runtime_key not in runtimes:
            raise RuntimeError(f"prepared Terraria runtime is required: {runtime_key}")
        artifact = runtimes[runtime_key]
        if artifact.runtime_key != runtime_key:
            raise RuntimeError(f"prepared Terraria runtime has the wrong identity: {runtime_key}")
        images = artifact.metadata.get("images")
        if not isinstance(images, dict) or task.id not in images:
            raise RuntimeError(
                f"prepared Terraria runtime is missing task image: {runtime_key}/{task.id}"
            )
        image_id = images[task.id]
        if not isinstance(image_id, str) or _IMAGE_ID.fullmatch(image_id) is None:
            raise RuntimeError(f"prepared Terraria image identity is invalid: {runtime_key}")
        return image_id

    @staticmethod
    def _case_records(output: str) -> list[tuple[str, bool]]:
        records: list[tuple[str, bool]] = []
        for line in output.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(value, dict)
                and isinstance(value.get("name"), str)
                and isinstance(value.get("passed"), bool)
            ):
                records.append((value["name"], value["passed"]))
        return records

    @staticmethod
    def _skipped_check(check_id: str, maximum: float, message: str) -> dict[str, Any]:
        return {
            "id": check_id,
            "status": "skipped",
            "score": 0.0,
            "maximum": maximum,
            "message": message,
        }

    def _source_check(
        self,
        submission: Path,
        task: TerrariaTask,
        runtimes: dict[str, RuntimeArtifact] | None,
    ) -> tuple[dict[str, Any], bool, bool, str]:
        try:
            image_id = self._artifact_image(task, runtimes, SOURCE_RUNTIME_KEY)
        except RuntimeError as error:
            return (
                {
                    "id": "private-source-projection-verifier",
                    "status": "incomplete",
                    "score": 0.0,
                    "maximum": 60.0,
                    "message": str(error),
                },
                False,
                False,
                "",
            )

        try:
            with tempfile.TemporaryDirectory(prefix="rhenium-terraria-source-") as temp:
                logs = Path(temp) / "logs"
                process, runtime_log = self.runtime.run(task, submission, logs, image_id)
                reward_path = logs / "verifier" / "reward.txt"
                verifier_log = logs / "verifier" / "verifier.log"
                reward = (
                    reward_path.read_text(encoding="utf-8").strip()
                    if reward_path.is_file()
                    else ""
                )
                # test.sh tees the verifier stream to both stdout and this log.
                # Prefer the durable log when present so each case is counted once.
                output = (
                    verifier_log.read_text(encoding="utf-8", errors="replace")
                    if verifier_log.is_file()
                    else (process.stdout or "") + (process.stderr or "")
                )
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            return (
                {
                    "id": "private-source-projection-verifier",
                    "status": "incomplete",
                    "score": 0.0,
                    "maximum": 60.0,
                    "message": f"source-projection verifier could not complete: {error}",
                },
                False,
                False,
                "",
            )

        expected = expected_case_names(self.context.pack_root, task)
        records = self._case_records(output)
        exact_cases = tuple(name for name, _passed in records) == expected
        all_passed = exact_cases and all(passed for _name, passed in records)
        reward_consistent = reward == ("1" if all_passed else "0")
        complete = process.returncode == 0 and exact_cases and reward_consistent
        passed = complete and all_passed
        check: dict[str, Any] = {
            "id": "private-source-projection-verifier",
            "status": "passed" if passed else "failed" if complete else "incomplete",
            "score": 60.0 if passed else 0.0,
            "maximum": 60.0,
            "message": (
                f"all {len(expected)} source-projection cases passed"
                if passed
                else f"all {len(expected)} source-projection cases ran with failures"
                if complete
                else "source-projection verifier did not produce a complete exact case set"
            ),
        }
        if complete:
            check["details"] = {"cases": [{"name": name, "passed": ok} for name, ok in records]}
        return check, complete, passed, runtime_log

    def _engine_check(
        self,
        submission: Path,
        task: TerrariaTask,
        runtimes: dict[str, RuntimeArtifact] | None,
    ) -> tuple[dict[str, Any], bool, bool, str]:
        try:
            image_id = self._artifact_image(task, runtimes, ENGINE_RUNTIME_KEY)
        except RuntimeError as error:
            return (
                {
                    "id": "private-real-tmodloader-verifier",
                    "status": "incomplete",
                    "score": 0.0,
                    "maximum": 30.0,
                    "message": str(error),
                },
                False,
                False,
                "",
            )

        try:
            with tempfile.TemporaryDirectory(prefix="rhenium-terraria-engine-") as temp:
                reports = Path(temp) / "reports"
                process, runtime_log = self.engine_runtime.run_image(
                    image_id, reports, submission=submission
                )
                report_path = reports / "engine-report.json"
                if (
                    not report_path.is_file()
                    or report_path.is_symlink()
                    or report_path.stat().st_size > _MAX_ENGINE_REPORT_BYTES
                ):
                    raise RuntimeError("real tModLoader verifier did not produce a safe report")
                report = json.loads(report_path.read_text(encoding="utf-8"))
        except (
            OSError,
            RuntimeError,
            json.JSONDecodeError,
            subprocess.SubprocessError,
        ) as error:
            return (
                {
                    "id": "private-real-tmodloader-verifier",
                    "status": "incomplete",
                    "score": 0.0,
                    "maximum": 30.0,
                    "message": f"real tModLoader verifier could not complete: {error}",
                },
                False,
                False,
                "",
            )

        expected = expected_engine_case_names(self.context.pack_root, task)
        raw_cases = report.get("cases") if isinstance(report, dict) else None
        records: list[tuple[str, str]] = []
        valid_cases = True
        if not isinstance(raw_cases, list):
            valid_cases = False
        else:
            for case in raw_cases:
                if (
                    not isinstance(case, dict)
                    or not isinstance(case.get("name"), str)
                    or case.get("status") not in {"passed", "failed"}
                    or not (case.get("error") is None or isinstance(case.get("error"), str))
                ):
                    valid_cases = False
                    break
                records.append((case["name"], case["status"]))

        exact_cases = valid_cases and tuple(name for name, _status in records) == expected
        all_passed = exact_cases and all(status == "passed" for _name, status in records)
        expected_dedicated = task.engine_mode == "dedicated-server"
        envelope_valid = (
            isinstance(report, dict)
            and report.get("schemaVersion") == 1
            and report.get("complete") is True
            and report.get("passed") is all_passed
            and report.get("terrariaVersion") == f"v{GAME_VERSION}"
            and report.get("tModLoaderVersion") == TMODLOADER_VERSION
            and report.get("dedicatedServer") is expected_dedicated
            and exact_cases
        )
        exit_valid = process.returncode == (0 if all_passed else 90)
        complete = envelope_valid and exit_valid
        passed = complete and all_passed
        check: dict[str, Any] = {
            "id": "private-real-tmodloader-verifier",
            "status": "passed" if passed else "failed" if complete else "incomplete",
            "score": 30.0 if passed else 0.0,
            "maximum": 30.0,
            "message": (
                f"all {len(expected)} real tModLoader cases passed"
                if passed
                else f"all {len(expected)} real tModLoader cases ran with failures"
                if complete
                else "real tModLoader verifier report was incomplete or inconsistent"
            ),
        }
        if complete:
            check["details"] = {
                "cases": [{"name": name, "passed": status == "passed"} for name, status in records]
            }
        return check, complete, passed, runtime_log

    def evaluate(
        self,
        submission: Path,
        task: TerrariaTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Terraria evaluation profile: {profile}")
        static_ok, static_check = self._static_check(submission, task)
        if not static_ok:
            return {
                "taskId": task.id,
                "profile": profile,
                "score": static_check["score"],
                "maximum": 100.0,
                "complete": False,
                "passed": False,
                "checks": [
                    static_check,
                    self._skipped_check(
                        "private-source-projection-verifier",
                        60.0,
                        "source verification skipped because submission shape is invalid",
                    ),
                    self._skipped_check(
                        "private-real-tmodloader-verifier",
                        30.0,
                        "real-engine verification skipped because submission shape is invalid",
                    ),
                ],
            }

        source_check, source_complete, source_passed, source_log = self._source_check(
            submission, task, runtimes
        )
        if profile == "core":
            engine_check = self._skipped_check(
                "private-real-tmodloader-verifier",
                30.0,
                "real tModLoader execution is omitted by the core diagnostic profile",
            )
            return {
                "taskId": task.id,
                "profile": profile,
                "score": static_check["score"] + source_check["score"],
                "maximum": 100.0,
                "complete": False,
                "passed": False,
                "checks": [static_check, source_check, engine_check],
                "runtime_log": source_log,
            }

        engine_check, engine_complete, engine_passed, engine_log = self._engine_check(
            submission, task, runtimes
        )
        complete = source_complete and engine_complete
        passed = static_ok and source_passed and engine_passed and complete
        return {
            "taskId": task.id,
            "profile": profile,
            "score": static_check["score"] + source_check["score"] + engine_check["score"],
            "maximum": 100.0,
            "complete": complete,
            "passed": passed,
            "checks": [static_check, source_check, engine_check],
            "runtime_log": source_log + engine_log,
        }
