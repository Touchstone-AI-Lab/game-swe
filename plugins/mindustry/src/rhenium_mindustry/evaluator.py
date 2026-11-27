from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

from .catalog import MindustryCatalog, MindustryTask
from .container import (
    MINDUSTRY_VERSION,
    STARTER_NAME,
    MindustryContainerRuntime,
    read_report,
    read_verifier_result,
    runtime_key,
)

_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN_SUFFIXES = frozenset({".class", ".jar", ".zip"})
_LOG_TAIL = 250_000
W_BUILD = 10.0
W_TOTAL = 100.0
W_LIVE = W_TOTAL - W_BUILD


class MindustryEvaluator:
    """Full-profile evaluation of a Mindustry game-source repair in the prepared verifier image."""

    def __init__(self, context: BenchmarkContext, catalog: MindustryCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = MindustryContainerRuntime()

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(submission: Path, task: MindustryTask) -> tuple[bool, dict[str, Any]]:
        problems: list[str] = []
        starter = submission / STARTER_NAME
        if not submission.is_dir() or submission.is_symlink():
            problems.append("submission is not a directory")
        elif not starter.is_dir() or starter.is_symlink():
            problems.append(f"submission lacks the {STARTER_NAME}/ tree")
        else:
            for candidate in starter.rglob("*"):
                relative = candidate.relative_to(submission)
                if candidate.is_symlink():
                    problems.append(f"{relative}: symbolic links are not allowed")
                    continue
                if not candidate.is_file():
                    continue
                if ".git" in relative.parts:
                    problems.append(f"{relative}: version-control metadata is not allowed")
                elif candidate.suffix.lower() in _FORBIDDEN_SUFFIXES:
                    problems.append(f"{relative}: compiled artifacts are not allowed")
            for source_root in task.build.source_roots:
                if not (starter / source_root).is_dir():
                    problems.append(f"{STARTER_NAME}/{source_root}: source root is missing")
            for required in task.required_files:
                if not (submission / required).is_file():
                    problems.append(f"{required}: required file is missing")
        ok = not problems
        return ok, {
            "id": "submission-shape",
            "status": "passed" if ok else "failed",
            "score": 0.0,
            "maximum": 0.0,
            "message": (
                "submission contains the required Mindustry source tree" if ok else "; ".join(problems[:8])
            ),
        }

    def _runtime_artifact(
        self, task: MindustryTask, runtimes: dict[str, RuntimeArtifact] | None
    ) -> tuple[str, str]:
        key = runtime_key()
        artifact = (runtimes or {}).get(key)
        images = artifact.metadata.get("images") if artifact is not None else None
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        return key, image_id

    def _read_runtime_log(self, logs: Path, process: subprocess.CompletedProcess[str]) -> str:
        parts = [(process.stdout + process.stderr)[-_LOG_TAIL:]]
        for name in ("verifier.log", "build-submission.log", "server.log"):
            candidate = logs / "verifier" / name
            if candidate.is_file():
                try:
                    text = read_report(candidate, logs)
                except ValueError:
                    continue
                parts.append(f"== {name} ==\n{text[-_LOG_TAIL:]}")
        return "\n".join(parts)

    @staticmethod
    def _cases(section: dict[str, Any], expected: tuple[str, ...]) -> tuple[bool, bool, list[dict[str, Any]]]:
        """(observed completely, all passed, cases) for the live layer."""
        cases = [
            {"name": item["name"], "passed": item["passed"], "message": str(item.get("message", ""))}
            for item in section.get("cases", [])
        ]
        names = [case["name"] for case in cases]
        complete = (
            len(names) == len(expected) and len(set(names)) == len(names) and set(names) == set(expected)
        )
        return complete, complete and all(case["passed"] for case in cases), cases

    def evaluate(
        self,
        submission: Path,
        task: Any,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(task, MindustryTask):
            raise TypeError("Mindustry evaluator received a non-Mindustry task")
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported evaluation profile: {profile}")
        shape_ok, shape_check = self._static_check(submission, task)

        def incomplete(message: str, log: str, status: str = "incomplete") -> dict[str, Any]:
            return {
                "taskId": task.id,
                "profile": profile,
                "score": 0.0,
                "maximum": W_TOTAL,
                "complete": False,
                "passed": False,
                "checks": [
                    shape_check,
                    {
                        "id": "offline-build",
                        "status": status,
                        "score": 0.0,
                        "maximum": W_BUILD,
                        "message": message,
                    },
                    {
                        "id": "live-server",
                        "status": status,
                        "score": 0.0,
                        "maximum": W_LIVE,
                        "message": message,
                    },
                ],
                "runtime": {
                    "status": status,
                    "message": message,
                    "cases": [],
                    "caseOutcomes": {},
                    "passedAssertions": 0,
                    "failedAssertions": 0,
                },
                "runtime_log": log,
            }

        if profile == "core":
            return incomplete(
                "the core profile never runs the offline build or the server", "", status="skipped"
            )
        if not shape_ok:
            return incomplete("the submission was rejected before any build", "", status="failed")
        key, image_id = self._runtime_artifact(task, runtimes)
        if not _IMAGE_ID.match(image_id):
            return incomplete(
                "managed Mindustry runtime has no verifier image for this task",
                f"run rhenium runtime prepare {key}\n",
                status="unavailable",
            )
        status = self.runtime_status()
        if not bool(status.get("available", False)):
            return incomplete(
                "pinned Mindustry container runtime is unavailable",
                str(status.get("reason") or "runtime unavailable") + "\n",
                status="unavailable",
            )
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(
                prefix="mindustry-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.runtime.run(submission, logs, image_id)
                runtime_log = identity_log + self._read_runtime_log(logs, process)
                result = read_verifier_result(logs)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            return incomplete(
                "the Mindustry verifier did not produce a trusted report", f"runtime error: {error}\n"
            )

        build = result["build"]
        build_ok = build.get("status") == "passed"
        live_complete, live_ok, live_cases = self._cases(result["live"], task.server_cases)
        complete = bool(build_ok and live_complete and result["complete"])
        passed = bool(complete and live_ok and result["passed"])
        build_score = W_BUILD if build_ok else 0.0
        live_score = W_LIVE if complete and live_ok else 0.0
        score = build_score + live_score
        case_outcomes = {case["name"]: case["passed"] for case in live_cases}
        passed_count = sum(case_outcomes.values())
        live_status = "passed" if live_complete and live_ok else "failed" if live_complete else "incomplete"
        live_problem = str(result["live"].get("problem") or "")
        checks = [
            shape_check,
            {
                "id": "offline-build",
                "status": "passed" if build_ok else "failed",
                "score": build_score,
                "maximum": W_BUILD,
                "message": (
                    f"javac build of the game sources {build.get('status')}"
                    + (f": {build.get('problem')}" if build.get("problem") else "")
                ),
            },
            {
                "id": "live-server",
                "status": live_status,
                "score": live_score,
                "maximum": W_LIVE,
                "message": (
                    f"{passed_count}/{len(task.server_cases)} real-server cases passed"
                    if live_complete
                    else "real-server cases did not complete with the frozen case set"
                    + (f": {live_problem}" if live_problem else "")
                ),
                "details": {"cases": live_cases},
            },
        ]
        return {
            "taskId": task.id,
            "profile": profile,
            "score": round(score, 2) if complete else 0.0,
            "maximum": W_TOTAL,
            "complete": complete,
            "passed": passed,
            "checks": checks,
            "runtime": {
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "cases": live_cases,
                "caseOutcomes": case_outcomes if complete else {},
                "passedAssertions": passed_count if complete else 0,
                "failedAssertions": len(case_outcomes) - passed_count if complete else 0,
                "mindustryVersion": MINDUSTRY_VERSION,
                "image": image_id,
            },
            "runtime_log": runtime_log,
        }
