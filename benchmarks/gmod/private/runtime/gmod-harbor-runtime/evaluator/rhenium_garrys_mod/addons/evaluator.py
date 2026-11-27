from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .analyzer import GmodAddonAnalyzer
from .catalog import GmodCatalog, GmodTask
from .contracts import GmodTaskRuntimeSpec
from .runtime import GmodRuntimeConfig
from .server_runner import (
    GmodDedicatedServerRunner,
    runtime_payload_matches_contract,
    runtime_result_integrity,
)
from .submission import GmodSubmissionError, validate_submission_tree


@dataclass(frozen=True)
class Check:
    id: str
    status: str
    score: float
    maximum: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class GmodEvaluator:
    def __init__(self, context: BenchmarkContext, catalog: GmodCatalog):
        self.context = context
        self.config = GmodRuntimeConfig.load(context, catalog)
        self.catalog = catalog
        self.analyzer = GmodAddonAnalyzer()
        self.server = GmodDedicatedServerRunner(self.config)

    def runtime_status(self) -> dict[str, Any]:
        return self.server.status()

    @staticmethod
    def _required(root: Path, required: list[str]) -> dict[str, list[str]]:
        present: list[str] = []
        missing: list[str] = []
        unsafe: list[str] = []
        for relative in required:
            try:
                candidate = (root / relative).resolve(strict=True)
            except OSError:
                candidate = None
            if candidate is None:
                missing.append(relative)
            elif not candidate.is_relative_to(root) or not candidate.is_file():
                unsafe.append(relative)
            else:
                present.append(relative)
        return {"present": present, "missing": missing, "unsafe": unsafe}

    def _run_lua_suite(self, submission: Path, test: Path, timeout_seconds: float) -> dict[str, Any]:
        package_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(package_root), environment.get("PYTHONPATH", "")) if value
        )
        environment["PYTHONIOENCODING"] = "utf-8"
        command = [
            sys.executable,
            "-m",
            "rhenium_garrys_mod.addons.lua.suite_runner",
            "--submission",
            str(submission),
            "--test",
            str(test),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "cases": [], "message": "private Lua suite timed out"}
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"status": "error", "cases": [], "message": "private Lua runner failed"}
        cases = payload.get("cases") if isinstance(payload, dict) else None
        if completed.returncode != 0 or not isinstance(cases, list) or not cases:
            return {"status": "error", "cases": [], "message": "private Lua runner failed"}
        normalized: list[dict[str, Any]] = []
        names: set[str] = set()
        for item in cases:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str)
                or not isinstance(item.get("passed"), bool)
            ):
                return {"status": "error", "cases": [], "message": "private Lua cases are malformed"}
            if item["name"] in names:
                return {"status": "error", "cases": [], "message": "private Lua case names are duplicated"}
            names.add(item["name"])
            normalized.append(
                {"name": item["name"], "passed": item["passed"], "message": str(item.get("message", ""))}
            )
        actual = "passed" if all(item["passed"] for item in normalized) else "failed"
        if payload.get("status") != actual:
            return {"status": "error", "cases": normalized, "message": "private Lua status is inconsistent"}
        passed_count = sum(case["passed"] for case in normalized)
        return {
            "status": actual,
            "cases": normalized,
            "message": f"{passed_count}/{len(normalized)} cases passed",
        }

    @staticmethod
    def _require_case_order(result: dict[str, Any], expected: tuple[str, ...], label: str) -> dict[str, Any]:
        cases = result.get("cases", [])
        actual = [item.get("name") for item in cases if isinstance(item, dict)]
        if actual != list(expected):
            return {
                "status": "error",
                "cases": cases if isinstance(cases, list) else [],
                "message": f"{label} cases do not match the task contract",
                "expected": list(expected),
                "actual": actual,
            }
        return result

    @staticmethod
    def _case_check(
        identifier: str, result: dict[str, Any], maximum: float, selected: set[str] | None = None
    ) -> Check:
        cases = [item for item in result.get("cases", []) if selected is None or item.get("name") in selected]
        passed_count = sum(item.get("passed") is True for item in cases)
        total = len(cases)
        passed = result.get("status") in {"passed", "failed"} and total > 0 and passed_count == total
        score = (
            round(maximum * passed_count / total, 2)
            if total and result.get("status") in {"passed", "failed"}
            else 0.0
        )
        return Check(
            identifier,
            "passed" if passed else "failed",
            score,
            maximum,
            f"{passed_count}/{total} private behavior cases passed",
            {
                "passed": passed_count,
                "total": total,
                "cases": cases,
                "runner_status": result.get("status", "error"),
            },
        )

    def evaluate(
        self,
        submission: Path,
        task: GmodTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        del runtimes
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported Garry's Mod evaluation profile: {profile}")
        if not isinstance(task, GmodTask):
            raise TypeError("GMod evaluator received a non-GMod task")
        run_runtime = profile == "full"
        submission = submission.resolve()
        submission_tree = None
        try:
            submission_tree = validate_submission_tree(submission, required_files=tuple(task.required_files))
            analysis = self.analyzer.analyze(submission)
        except (OSError, GmodSubmissionError, ValueError) as error:
            analysis = {"valid": False, "syntax_errors": [{"message": str(error)}], "lua_files": 0}
        checks: list[Check] = []
        required = self._required(submission, task.required_files)
        structure_ok = submission_tree is not None and not required["missing"] and not required["unsafe"]
        checks.append(
            Check(
                "required-files",
                "passed" if structure_ok else "failed",
                5.0 if structure_ok else 0.0,
                5.0,
                "Required addon files are safe and present"
                if structure_ok
                else "Required addon files are missing or unsafe",
                required,
            )
        )
        syntax_errors = analysis.get("syntax_errors", [])
        syntax_ok = bool(analysis.get("lua_files")) and not syntax_errors and not analysis.get("addon_error")
        checks.append(
            Check(
                "lua-syntax",
                "passed" if syntax_ok else "failed",
                5.0 if syntax_ok else 0.0,
                5.0,
                ("Lua and addon.json parse successfully" if syntax_ok else "Lua or addon.json syntax failed"),
                {"errors": syntax_errors, "addonError": analysis.get("addon_error", "")},
            )
        )
        dataset = self.config.dataset_dir.resolve()
        evaluation = task.evaluation
        behavior = self._run_lua_suite(
            submission,
            (dataset / evaluation.hidden_suite).resolve(),
            evaluation.suite_timeout_seconds,
        )
        behavior = self._require_case_order(behavior, tuple(evaluation.hidden_cases), "hidden behavior")
        checks.append(self._case_check("hidden-behavior", behavior, 30.0))
        integration = self._run_lua_suite(
            submission,
            (dataset / evaluation.integration_suite).resolve(),
            evaluation.suite_timeout_seconds,
        )
        integration = self._require_case_order(integration, evaluation.integration_case_order, "integration")
        checks.append(
            self._case_check(
                "gmod-integration",
                integration,
                15.0,
                set(evaluation.integration_cases),
            )
        )
        checks.append(
            self._case_check(
                "lifecycle-cleanup",
                integration,
                5.0,
                set(evaluation.lifecycle_cases),
            )
        )

        runtime: dict[str, Any] = {"status": "skipped", "message": "Dedicated Server disabled"}
        runtime_spec: GmodTaskRuntimeSpec | None = None
        try:
            runtime_spec = task.runtime_spec(dataset)
        except (OSError, ValueError) as error:
            runtime = {"status": "error", "message": str(error)}
        if run_runtime and runtime_spec is not None:
            runtime = self.server.run(submission, runtime_spec)
        final_phase_name = runtime_spec.phases[-1] if runtime_spec is not None else "B"
        final_phase_key = f"phase_{final_phase_name.lower()}"
        final_phase = runtime.get(final_phase_key)
        final_payload = final_phase.get("payload") if isinstance(final_phase, dict) else None
        runtime_contract_ok = bool(
            runtime_spec
            and runtime_payload_matches_contract(
                final_payload,
                spec=runtime_spec,
                phase=final_phase_name,
            )
        )
        runtime_integrity_ok = bool(
            runtime_spec
            and runtime_result_integrity(
                runtime,
                spec=runtime_spec,
                pinned_build=self.config.pinned_build,
            )
        )
        runtime_cases = (
            final_payload.get("cases", []) if runtime_contract_ok and isinstance(final_payload, dict) else []
        )
        runtime_passed = sum(item.get("passed") is True for item in runtime_cases)
        runtime_total = len(runtime_cases)
        runtime_ok = (
            runtime_integrity_ok
            and runtime.get("status") == "passed"
            and runtime_total > 0
            and runtime_passed == runtime_total
        )
        runtime_score = (
            round(40.0 * runtime_passed / runtime_total, 2) if runtime_integrity_ok and runtime_total else 0.0
        )
        checks.append(
            Check(
                "dedicated-server",
                "passed" if runtime_ok else ("skipped" if not run_runtime else "failed"),
                runtime_score,
                40.0,
                f"{runtime_passed}/{runtime_total} real Dedicated Server groups passed",
                {
                    "passed": runtime_passed,
                    "total": runtime_total,
                    "cases": runtime_cases,
                    "runner_status": runtime.get("status", "error"),
                    "integrity_valid": runtime_integrity_ok,
                },
            )
        )
        earned = round(sum(check.score for check in checks), 2)
        complete = bool(
            run_runtime
            and isinstance(final_phase, dict)
            and runtime_integrity_ok
            and runtime.get("status") in {"passed", "failed"}
        )
        passed = complete and all(check.status == "passed" for check in checks)
        return {
            "score": earned,
            "earned": earned,
            "available_maximum": 100.0,
            "rubric_maximum": 100.0,
            "complete": complete,
            "passed": passed,
            "checks": [asdict(check) for check in checks],
            "analysis": analysis,
            "runtime": runtime,
            "runtime_log": json.dumps(runtime, ensure_ascii=False, default=str),
            "evidence": {
                "submissionHash": submission_tree.digest if submission_tree else None,
                "serverBuild": runtime.get("server_build"),
                "datasetVersion": self.catalog.version,
                "catalogVersion": self.catalog.version,
                "taskVersion": task.task_version,
            },
        }
