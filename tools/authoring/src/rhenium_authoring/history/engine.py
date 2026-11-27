"""Engine-backed controls for a history candidate, judged like E0 admission.

A one-task pack is staged in the ``minecraft-core`` layout and loaded into an
isolated Hub (never the operator's). Every control is a full-profile
evaluation on the real server through the public ``evaluate_task`` contract.
The expectations are the admission rules of ``tools/study``: the unchanged
starter fails exactly the target cases, the reference, an independent
alternative and a tampered reference pass, a target-negative fails only target
cases and a compat-negative keeps every target while breaking a preserved one.
"""

from __future__ import annotations

import difflib
import fcntl
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub

from ..engine import HubEngineValidator, _persist_runtime_log, _run_log, _safe_label
from .minecraft_pack import PACK_ID, HistoryTask, stage

_IGNORED = shutil.ignore_patterns("build", "target", ".gradle", "out", ".git")


@dataclass
class ControlOutcome:
    label: str
    kind: str
    admissible: bool
    reason: str
    complete: bool
    passed: bool
    score: float | None
    failed: list[str] = field(default_factory=list)
    messages: dict[str, str] = field(default_factory=dict)

    def record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "kind": self.kind,
            "admissible": self.admissible,
            "reason": self.reason,
            "complete": self.complete,
            "passed": self.passed,
            "score": self.score,
            "failed": self.failed,
            "messages": self.messages,
        }


def judge(
    kind: str, result: dict[str, Any], *, cases: set[str], targets: set[str], preserved: set[str]
) -> tuple[bool, str, list[str]]:
    """Admissibility of one control, with the failed case names."""
    runtime = result.get("runtime")
    outcomes = runtime.get("caseOutcomes") if isinstance(runtime, dict) else None
    complete = result.get("complete") is True
    passed = result.get("passed") is True
    if not complete or not isinstance(outcomes, dict):
        return False, "the evaluation did not observe every case", []
    if set(outcomes) != cases:
        return False, "the observed case set differs from the frozen cases", []
    failed = sorted(name for name, ok in outcomes.items() if ok is not True)
    if kind in {"reference", "alternative", "tamper"}:
        ok = passed and not failed
        return ok, "passes every case" if ok else f"fails {failed}", failed
    if kind == "starter":
        ok = not passed and set(failed) == targets
        missing = sorted(targets - set(failed))
        extra = sorted(set(failed) - targets)
        reason = (
            "fails exactly the target cases"
            if ok
            else f"target cases passing: {missing}; others failing: {extra}"
        )
        return ok, reason, failed
    if kind == "target-negative":
        ok = bool(failed) and set(failed) <= targets
        return ok, "fails only target cases" if ok else f"fails {failed}", failed
    if kind == "compat-negative":
        broken_targets = set(failed) & targets
        ok = not broken_targets and bool(set(failed) & preserved)
        return ok, "breaks a preserved case, keeps every target" if ok else f"fails {failed}", failed
    raise ValueError(f"unknown control kind {kind}")


def case_messages(result: dict[str, Any]) -> dict[str, str]:
    runtime = result.get("runtime")
    messages: dict[str, str] = {}
    for key in ("cases", "unitCases"):
        values = runtime.get(key) if isinstance(runtime, dict) else None
        for case in values if isinstance(values, list) else []:
            if isinstance(case, dict) and case.get("passed") is False and isinstance(case.get("name"), str):
                messages[case["name"]] = str(case.get("message") or "")[:400]
    return messages


def hunk_reverts(base: Path, reference: Path, applied: list[str], limit: int = 6) -> list[dict[str, str]]:
    """Reference variants that each undo exactly one hunk of the upstream fix."""
    variants: list[dict[str, str]] = []
    for relative in applied:
        old = (base / relative).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        new = (reference / relative).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        groups = [
            op
            for op in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes()
            if op[0] != "equal"
        ]
        if len(groups) == 1 and len(applied) == 1:
            continue  # reverting the only hunk is the starter itself
        for tag, i1, i2, j1, j2 in groups:
            del tag
            variants.append({relative: "".join(new[:j1] + old[i1:i2] + new[j2:])})
            if len(variants) >= limit:
                return variants
    return variants


def tamper(tree: Path, frozen: tuple[str, ...]) -> dict[str, str | None]:
    """Edits to frozen paths that the verifier must undo: broken build files, one test deleted."""
    changes: dict[str, str | None] = {}
    for relative in frozen:
        path = tree / relative
        if path.is_file() and path.name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            changes[relative] = (
                path.read_text(encoding="utf-8", errors="replace") + "\nTHIS IS NOT A BUILD FILE\n"
            )
    tests = sorted(tree.glob("**/src/test/**/*.java"))
    if tests:
        changes[tests[0].relative_to(tree).as_posix()] = None
    return changes


class HistoryEngine:
    def __init__(self, project_root: Path, *, prepare_account: str | None):
        self.project_root = project_root.resolve()
        self.validator = HubEngineValidator(self.project_root, prepare_account=prepare_account)

    def open(self, candidate_root: Path, task: HistoryTask) -> tuple[BenchmarkHub | None, str]:
        """Stage and load the one-task pack; returns (hub, task key) or (None, reason)."""
        staging = candidate_root / "validation-pack"
        pack = stage(staging, self.project_root, task)
        state = candidate_root / "validation-state"
        cache_dir = state / "cache"
        if self.validator.prepare_account is not None:
            cache_dir = self.validator._seed_prepare_state(state) or cache_dir
        settings = Settings(
            root=self.project_root,
            state_dir=state,
            cache_dir=cache_dir,
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(pack,),
            web_dist=None,
        )
        hub = BenchmarkHub(settings=settings, manifest_paths=(pack / "benchmark.json",))
        if self.validator.prepare_account is not None:
            failure = self._prepare(hub, task.fix.game_id)
            if failure is not None:
                return None, failure
        task_key = f"{task.fix.game_id}/{PACK_ID}/{task.task_id}"
        if task_key not in hub.task_keys:
            reasons = [str(issue.get("message", "")) for issue in hub.discovery_errors]
            return None, "staged pack failed to load: " + "; ".join(reasons)[:400]
        return hub, task_key

    @contextmanager
    def _runtime_lock(self) -> Iterator[None]:
        """One runtime preparation at a time, across workers and concurrent runs.

        Every candidate prepares the same runtime key in its own isolated Hub and
        rebuilds the shared verifier base image; concurrent builds of one tag race.
        """
        path = self.project_root / ".rhenium" / "authoring" / "locks" / "runtime-prepare.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _prepare(self, hub: BenchmarkHub, game_id: str) -> str | None:
        from rhenium.core.runtime import RuntimeActionRequired

        account = self.validator.prepare_account
        assert account is not None
        with self._runtime_lock():
            for runtime in hub.runtime_manager.list(game_id):
                try:
                    hub.runtime_manager.prepare(str(runtime["key"]), account_alias=account)
                except RuntimeActionRequired as error:
                    return f"runtime preparation needs an operator step: {str(error)[:300]}"
                except (RuntimeError, ValueError, OSError, KeyError) as error:
                    return f"runtime preparation failed: {type(error).__name__}: {str(error)[-400:]}"
        return None

    def run(
        self,
        hub: BenchmarkHub,
        task_key: str,
        candidate_root: Path,
        task: HistoryTask,
        *,
        label: str,
        kind: str,
        base: Path,
        changes: dict[str, str | None] | None = None,
    ) -> ControlOutcome:
        """Evaluate ``base`` with ``changes`` applied (``None`` deletes a file)."""
        with tempfile.TemporaryDirectory(prefix="history-control-", dir=candidate_root) as raw:
            submission = Path(raw) / "submission"
            plugin = submission / "plugin"
            shutil.copytree(base, plugin, symlinks=False, ignore=_IGNORED)
            for relative, text in (changes or {}).items():
                target = plugin / relative
                if text is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding="utf-8")
            run = hub.evaluate_task(task_key, submission, profile="full")
            result = run["result"]
        _persist_runtime_log(candidate_root, label, _run_log(hub.settings.state_dir, run))
        cases = {*task.probe.unit_cases, *task.authored.server_cases}
        targets = set(task.authored.target_cases)
        sentinels = {case.case for case in task.authored.cases if case.role == "sentinel"}
        admissible, reason, failed = judge(
            kind, result, cases=cases, targets=targets, preserved=cases - targets - sentinels
        )
        score = result.get("score")
        return ControlOutcome(
            label=label,
            kind=kind,
            admissible=admissible,
            reason=reason,
            complete=result.get("complete") is True,
            passed=result.get("passed") is True,
            score=float(score) if isinstance(score, int | float) else None,
            failed=failed,
            messages=case_messages(result),
        )

    @staticmethod
    def log_tail(candidate_root: Path, label: str, limit: int = 4000) -> str:
        path = candidate_root / "engine-logs" / f"{_safe_label(label)}.log"
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-limit:]
        except OSError:
            return ""
