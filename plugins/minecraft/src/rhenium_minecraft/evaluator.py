from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog

from .catalog import CATALOG_RUNTIME_IDS, MinecraftCatalog, MinecraftTask
from .container import (
    PAPER_BUILD,
    PAPER_VERSION,
    STARTER_NAME,
    MinecraftContainerRuntime,
    read_report,
    read_verifier_result,
    runtime_key,
)
from .runtime_builder import MinecraftRuntimeBuilder

_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_FORBIDDEN_SUFFIXES = frozenset({".class", ".jar", ".zip"})
# Build-tool wrappers ship a bootstrap jar; both are frozen paths restored by the verifier.
_WRAPPER_JARS = frozenset({"gradle/wrapper/gradle-wrapper.jar", ".mvn/wrapper/maven-wrapper.jar"})
_BUILD_DIRECTORIES = frozenset({"build", "target", ".gradle", "out"})
_LOG_TAIL = 250_000
W_BUILD = 10.0
W_UNIT = 30.0
W_TOTAL = 100.0


class MinecraftEvaluator:
    """Full-profile evaluation of a Paper plugin repair in the prepared verifier image."""

    def __init__(self, context: BenchmarkContext, catalog: MinecraftCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = MinecraftContainerRuntime()

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime.status()

    @staticmethod
    def _static_check(submission: Path, task: MinecraftTask) -> tuple[bool, dict[str, Any]]:
        problems: list[str] = []
        starter = submission / STARTER_NAME
        if not submission.is_dir() or submission.is_symlink():
            problems.append("submission is not a directory")
        elif not starter.is_dir() or starter.is_symlink():
            problems.append(f"submission lacks the {STARTER_NAME}/ tree")
        else:
            for candidate in submission.rglob("*"):
                relative = candidate.relative_to(submission)
                if candidate.is_symlink():
                    problems.append(f"{relative}: symbolic links are not allowed")
                    continue
                if not candidate.is_file():
                    continue
                parts = relative.parts
                in_build_output = any(part in _BUILD_DIRECTORIES for part in parts[:-1])
                if ".git" in parts:
                    problems.append(f"{relative}: version-control metadata is not allowed")
                elif (
                    candidate.suffix.lower() in _FORBIDDEN_SUFFIXES
                    and not in_build_output
                    and "/".join(parts[1:]) not in _WRAPPER_JARS
                ):
                    problems.append(f"{relative}: compiled artifacts outside build output")
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
                "submission contains the required plugin source tree" if ok else "; ".join(problems[:8])
            ),
        }

    def _runtime_artifact(
        self, task: MinecraftTask, runtimes: dict[str, RuntimeArtifact] | None
    ) -> tuple[str, RuntimeArtifact | None, str]:
        key = runtime_key(CATALOG_RUNTIME_IDS[self.catalog.id])
        artifact = (runtimes or {}).get(key)
        images = artifact.metadata.get("images") if artifact is not None else None
        image_id = str(images.get(task.id) or "") if isinstance(images, dict) else ""
        return key, artifact, image_id

    def _current_image(self, task: MinecraftTask, artifact: RuntimeArtifact) -> str:
        """The task's verifier image, re-checked against the pack's current ``tests/`` tree."""
        runtime_id = CATALOG_RUNTIME_IDS[self.catalog.id]
        catalog = RuntimeCatalog.load(self.context.pack_root, "runtimes.json")
        spec = next((item for item in catalog.runtimes if item.id == runtime_id), None)
        if spec is None:
            raise ValueError(f"runtime catalog does not declare {runtime_id}")
        builder = MinecraftRuntimeBuilder(self.context, self.catalog)
        builder.runtime = self.runtime
        return builder.task_image(spec, artifact, task)

    def _read_runtime_log(self, logs: Path, process: subprocess.CompletedProcess[str]) -> str:
        parts = [(process.stdout + process.stderr)[-_LOG_TAIL:]]
        for name in ("verifier.log", "build-submission.log", "unit.log", "server.log"):
            candidate = logs / "verifier" / name
            if candidate.is_file():
                try:
                    text = read_report(candidate, logs)
                except ValueError:
                    continue
                parts.append(f"== {name} ==\n{text[-_LOG_TAIL:]}")
        return "\n".join(parts)

    @staticmethod
    def _layer(section: dict[str, Any], expected: tuple[str, ...]) -> tuple[bool, bool, list[dict[str, Any]]]:
        """(observed completely, all passed, cases) for one verifier layer."""
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
        if not isinstance(task, MinecraftTask):
            raise TypeError("Minecraft evaluator received a non-Minecraft task")
        if profile not in {"core", "full"}:
            raise ValueError(f"unsupported evaluation profile: {profile}")
        shape_ok, shape_check = self._static_check(submission, task)
        w_unit = W_UNIT if task.unit_cases else 0.0
        w_live = W_TOTAL - W_BUILD - w_unit

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
                        "id": "upstream-tests",
                        "status": "skipped" if not task.unit_cases else status,
                        "score": 0.0,
                        "maximum": w_unit,
                        "message": message,
                    },
                    {
                        "id": "live-server",
                        "status": status,
                        "score": 0.0,
                        "maximum": w_live,
                        "message": message,
                    },
                ],
                "runtime": {
                    "status": status,
                    "message": message,
                    "cases": [],
                    "unitCases": [],
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
        key, artifact, image_id = self._runtime_artifact(task, runtimes)
        if artifact is None or not _IMAGE_ID.match(image_id):
            return incomplete(
                "managed Minecraft runtime has no verifier image for this task",
                f"run rhenium runtime prepare {key}\n",
                status="unavailable",
            )
        status = self.runtime_status()
        if not bool(status.get("available", False)):
            return incomplete(
                "pinned Minecraft container runtime is unavailable",
                str(status.get("reason") or "runtime unavailable") + "\n",
                status="unavailable",
            )
        try:
            image_id = self._current_image(task, artifact)
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            return incomplete(
                "managed Minecraft runtime does not match this task's current verifier",
                f"{error}\nrun rhenium runtime prepare {key}\n",
                status="unavailable",
            )
        self.context.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(
                prefix="minecraft-evaluation-", dir=self.context.cache_dir
            ) as raw_run:
                logs = Path(raw_run) / "logs"
                logs.mkdir()
                process, identity_log = self.runtime.run(submission, logs, image_id)
                runtime_log = identity_log + self._read_runtime_log(logs, process)
                result = read_verifier_result(logs)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
            return incomplete(
                "the Minecraft verifier did not produce a trusted report", f"runtime error: {error}\n"
            )

        build = result["build"]
        build_ok = build.get("status") == "passed"
        unit_complete, unit_ok, unit_cases = self._layer(result["unit"], task.unit_cases)
        if not task.unit_cases:
            unit_complete, unit_ok, unit_cases = True, True, []
        live_complete, live_ok, live_cases = self._layer(result["live"], task.server_cases)
        complete = bool(build_ok and unit_complete and live_complete and result["complete"])
        passed = bool(complete and unit_ok and live_ok and result["passed"])
        unit_score = w_unit if complete and unit_ok else 0.0
        live_score = w_live if complete and live_ok else 0.0
        build_score = W_BUILD if build_ok else 0.0
        score = build_score + unit_score + live_score if complete else build_score
        case_outcomes = {case["name"]: case["passed"] for case in [*unit_cases, *live_cases]}
        passed_count = sum(case_outcomes.values())

        def layer_status(observed: bool, ok: bool) -> str:
            return "passed" if observed and ok else "failed" if observed else "incomplete"

        checks = [
            shape_check,
            {
                "id": "offline-build",
                "status": "passed" if build_ok else "failed",
                "score": build_score,
                "maximum": W_BUILD,
                "message": f"{task.build.tool} build {build.get('status')}",
                "details": {"tool": task.build.tool, "artifact": task.build.artifact},
            },
            {
                "id": "upstream-tests",
                "status": "skipped" if not task.unit_cases else layer_status(unit_complete, unit_ok),
                "score": unit_score,
                "maximum": w_unit,
                "message": (
                    "the task declares no upstream unit tests"
                    if not task.unit_cases
                    else f"{sum(case['passed'] for case in unit_cases)}/{len(task.unit_cases)} "
                    "upstream unit cases passed"
                ),
                "details": {"cases": unit_cases},
            },
            {
                "id": "live-server",
                "status": layer_status(live_complete, live_ok),
                "score": live_score,
                "maximum": w_live,
                "message": (
                    f"{sum(case['passed'] for case in live_cases)}/{len(task.server_cases)} "
                    "real-server cases passed"
                    if live_complete
                    else "real-server cases did not complete with the frozen case set"
                ),
                "details": {"cases": live_cases},
            },
        ]
        return {
            "taskId": task.id,
            "profile": profile,
            "score": round(score, 2),
            "maximum": W_TOTAL,
            "complete": complete,
            "passed": passed,
            "checks": checks,
            "runtime": {
                "status": "passed" if passed else "failed" if complete else "incomplete",
                "cases": live_cases,
                "unitCases": unit_cases,
                "caseOutcomes": case_outcomes if complete else {},
                "passedAssertions": passed_count if complete else 0,
                "failedAssertions": len(case_outcomes) - passed_count if complete else 0,
                "paperVersion": PAPER_VERSION,
                "paperBuild": PAPER_BUILD,
                "image": image_id,
            },
            "runtime_log": runtime_log,
        }
