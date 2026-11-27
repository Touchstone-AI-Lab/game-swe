from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub

from .game_adapters import game_spec
from .models import SynthesisBundle, ValidationCheck, ValidationReport
from .publisher import PackPublisher

# Only these evaluators emit per-case runtime.caseOutcomes receipts. Auditing
# exact case identity elsewhere would fail every honest control for a receipt
# the scorer never produces, so other games are judged by assertion counts.
EXACT_CASE_GAMES = frozenset({"stardew-valley", "left-4-dead-2", "minecraft"})


class HubEngineValidator:
    """Run base, fixed, and single-defect controls through the public Hub contract."""

    def __init__(self, project_root: Path, *, prepare_account: str | None = None):
        self.project_root = project_root.resolve()
        self.publisher = PackPublisher(self.project_root)
        # Explicit opt-in (the operator names the account on the command line):
        # prepare not-ready synth runtimes inside the isolated validation Hub
        # instead of stopping at ACTION_REQUIRED. Never logs in: a missing
        # session still surfaces as an operator action.
        self.prepare_account = prepare_account
        self.operator_hub = self.project_root / ".rhenium" / "hub"

    def validate(self, run_root: Path, bundle: SynthesisBundle) -> ValidationReport:
        stage_parent = run_root / "validation-packs" / bundle.candidate.id
        if stage_parent.exists():
            shutil.rmtree(stage_parent)
        stage_parent.mkdir(parents=True)
        pack = self.publisher.stage(bundle, stage_parent)
        manifest = pack / "benchmark.json"
        # Loading only a staged pack into the operator's Hub would archive its
        # unrelated tasks during catalog sync. Keep authoring validation state
        # separate, including runtime preparation records reused by resume.
        state = run_root.resolve() / "validation-state" / bundle.candidate.id
        cache_dir = state / "cache"
        if self.prepare_account is not None:
            cache_dir = self._seed_prepare_state(state) or cache_dir
        settings = Settings(
            root=self.project_root,
            state_dir=state,
            cache_dir=cache_dir,
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(pack,),
            web_dist=None,
        )
        hub = BenchmarkHub(settings=settings, manifest_paths=(manifest,))
        if self.prepare_account is not None:
            failure = self._prepare_runtimes(hub, bundle.candidate.game_id)
            if failure is not None:
                return _unavailable(bundle, failure)
        task_key = f"{bundle.candidate.game_id}/synth/{bundle.candidate.id}"
        if task_key not in hub.task_keys:
            reason = next(
                (
                    issue.get("message", "synthetic pack failed to load")
                    for issue in hub.discovery_errors
                    if issue.get("kind") == "pack"
                ),
                "synthetic pack failed to load",
            )
            return _unavailable(bundle, reason)

        evaluations: dict[str, dict[str, Any]] = {}
        inputs: list[tuple[str, dict[str, str]]] = [
            ("combined-base", bundle.base.files),
            ("gold", bundle.fixed.files),
            *[(f"ablation:{key}", value) for key, value in sorted(bundle.base.ablations.items())],
        ]
        try:
            with tempfile.TemporaryDirectory(
                prefix="engine-inputs-", dir=run_root
            ) as raw_submissions:
                submissions = Path(raw_submissions)
                for label, source_files in inputs:
                    submission = submissions / _safe_label(label)
                    self._write_submission(submission, bundle.candidate.game_id, source_files)
                    run = hub.evaluate_task(task_key, submission, profile="full")
                    result = run["result"]
                    evaluations[label] = result
                    # The evaluator's temporary directory is gone by now; keep
                    # the server/build log of every control for diagnosis.
                    _persist_runtime_log(
                        run_root / "candidates" / bundle.candidate.id, label, _run_log(state, run)
                    )
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            return _unavailable(bundle, _safe_runtime_error(error))

        return self.validate_controls(bundle, evaluations)

    def _seed_prepare_state(self, state: Path) -> Path | None:
        """Copy operator auth sessions into the isolated Hub and share its cache.

        The isolated database keeps staged catalog loading away from the
        operator Hub (whose copy would archive unrelated tasks); the session
        rows are what explicit in-run preparation needs to consume the
        provider source. The operator acquisition cache is reused so licensed
        depots are not re-downloaded per candidate. Returns the cache
        directory to use, or None to keep the isolated default.
        """
        state.mkdir(parents=True, exist_ok=True)
        state.chmod(0o700)
        operator_db = self.operator_hub / "state.sqlite"
        seeded = state / "state.sqlite"
        # A validation attempt made without an engine account leaves an
        # isolated database with no auth sessions; re-seed it too, or the
        # explicit preparation would fail asking for a login that exists.
        if operator_db.is_file() and (not seeded.exists() or not _has_auth_sessions(seeded)):
            shutil.copy2(operator_db, seeded)
            seeded.chmod(0o600)
        operator_cache = self.operator_hub / "cache"
        return operator_cache if operator_cache.is_dir() else None

    def _prepare_runtimes(self, hub: BenchmarkHub, game_id: str) -> str | None:
        """Explicitly prepare every runtime of the game; a safe reason on failure.

        The isolated database is seeded from the operator's Hub, so a runtime
        can look ready while its artifact only carries evaluator images for the
        operator's packs, never for the staged candidate. Preparation is
        idempotent for builders that cache their images, so it always runs.
        """
        from rhenium.core.runtime import RuntimeActionRequired

        account = self.prepare_account
        assert account is not None
        for runtime in hub.runtime_manager.list(game_id):
            try:
                hub.runtime_manager.prepare(str(runtime["key"]), account_alias=account)
            except RuntimeActionRequired:
                return (
                    "runtime preparation requires an interactive operator step; "
                    "prepare it explicitly and resume"
                )
            except (RuntimeError, ValueError, OSError, KeyError):
                return "explicit runtime preparation failed; prepare it manually and resume"
        return None

    @staticmethod
    def validate_controls(
        bundle: SynthesisBundle, evaluations: dict[str, dict[str, Any]],
    ) -> ValidationReport:
        """Audit complete full-profile control receipts using the authoring contract."""
        expected_controls = {"combined-base", "gold", *(
            f"ablation:{key}" for key in bundle.base.ablations
        )}
        if set(evaluations) != expected_controls:
            return _unavailable(bundle, "required engine control receipts are missing or unexpected")
        checks: list[ValidationCheck] = []
        if any(_runtime_unavailable(result) for result in evaluations.values()):
            return _unavailable(
                bundle,
                "required real-game runtime is unavailable; prepare or configure it and resume",
            )

        base = evaluations["combined-base"]
        gold = evaluations["gold"]
        expected_total = len(bundle.verifier.case_ids)
        expected_base_failures = len(
            {
                case
                for cases in bundle.verifier.capsule_cases.values()
                for case in cases
            }
        )
        base_counts = _assertion_counts(base)
        gold_counts = _assertion_counts(gold)
        required_outcomes = bundle.candidate.game_id in EXACT_CASE_GAMES
        all_cases = set(bundle.verifier.case_ids)
        base_failed_cases = {case for values in bundle.verifier.capsule_cases.values() for case in values}
        base_failed = bool(
            base.get("complete") is True
            and base.get("passed") is False
            and base_counts == (expected_total - expected_base_failures, expected_base_failures)
            and _cases_match(base, all_cases, base_failed_cases, required=required_outcomes)
        )
        gold_passed = bool(
            gold.get("complete") is True
            and gold.get("passed") is True
            and gold_counts == (expected_total, 0)
            and _cases_match(gold, all_cases, set(), required=required_outcomes)
        )
        checks.extend(
            (
                _control_check(
                    "combined-base",
                    base_failed,
                    "combined synthetic base completed and failed as expected",
                    "combined synthetic base did not produce the required failing control",
                    base,
                    base_failed_cases,
                ),
                _control_check(
                    "gold",
                    gold_passed,
                    "clean-room gold completed and passed every assertion",
                    "clean-room gold did not pass the complete evaluator",
                    gold,
                    set(),
                ),
            )
        )
        ablations_passed = True
        for capsule_id in sorted(bundle.base.ablations):
            result = evaluations[f"ablation:{capsule_id}"]
            expected_failures = len(bundle.verifier.capsule_cases[capsule_id])
            counts = _assertion_counts(result)
            passed = bool(
                result.get("complete") is True
                and result.get("passed") is False
                and counts == (expected_total - expected_failures, expected_failures)
                and _cases_match(result, all_cases, set(bundle.verifier.capsule_cases[capsule_id]),
                                 required=required_outcomes)
            )
            ablations_passed = ablations_passed and passed
            checks.append(
                _control_check(
                    f"ablation-{capsule_id}",
                    passed,
                    "single-defect control completed and failed as expected",
                    "single-defect control did not produce an isolated complete failure",
                    result,
                    set(bundle.verifier.capsule_cases[capsule_id]),
                )
            )
        passed = base_failed and gold_passed and ablations_passed
        all_complete = all(result.get("complete") is True for result in evaluations.values())
        return ValidationReport(
            candidate_id=bundle.candidate.id,
            complete=all_complete,
            passed=passed,
            base_failed=base_failed,
            gold_passed=gold_passed,
            engine_backed=all_complete,
            checks=tuple(checks),
        )

    @staticmethod
    def _write_submission(root: Path, game_id: str, source_files: dict[str, str]) -> None:
        from .artifacts import write_file_tree

        spec = game_spec(game_id)
        destination = root if game_id == "dst" else root / spec.starter_directory
        write_file_tree(destination, source_files)


def _run_log(state_dir: Path, run: dict[str, Any]) -> str:
    """The runtime log the Hub wrote for one evaluation (it is not returned inline)."""
    path = state_dir / "runs" / str(run.get("id") or "") / "runtime.log"
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError:
        return ""


def _persist_runtime_log(candidate_root: Path, label: str, log: str) -> None:
    """Save one control's engine log under candidates/<id>/engine-logs, mode 0600."""
    if not log:
        return
    directory = candidate_root / "engine-logs"
    if directory.is_symlink():
        return
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"{_safe_label(label)}.log"
    path.write_text(log, encoding="utf-8")
    path.chmod(0o600)


def _has_auth_sessions(database: Path) -> bool:
    import sqlite3

    try:
        with sqlite3.connect(database) as connection:
            row = connection.execute(
                "SELECT count(*) FROM auth_sessions WHERE secret_json IS NOT NULL"
            ).fetchone()
    except sqlite3.Error:
        return False
    return bool(row and row[0])


def _unavailable(bundle: SynthesisBundle, reason: str) -> ValidationReport:
    return ValidationReport(
        candidate_id=bundle.candidate.id,
        complete=False,
        passed=False,
        base_failed=False,
        gold_passed=False,
        engine_backed=False,
        checks=(ValidationCheck(id="real-engine", status="unavailable", message=reason),),
    )


def _safe_runtime_error(error: Exception) -> str:
    text = str(error)
    if "runtime" in text.casefold() and "prepare" in text.casefold():
        return "required managed runtime is not prepared; prepare it explicitly and resume"
    return "real-engine validation failed before producing complete evidence"


def _safe_label(value: str) -> str:
    return value.replace(":", "-").replace("/", "-")


def _control_check(
    check_id: str,
    passed: bool,
    ok_message: str,
    fail_message: str,
    result: dict[str, Any],
    expected_failing: set[str],
) -> ValidationCheck:
    """Attach numeric and case-identity evidence from a control receipt."""
    outcomes = _observed_outcomes(result)
    return ValidationCheck(
        id=check_id,
        status="passed" if passed else "failed",
        message=ok_message if passed else fail_message,
        observed_complete=result.get("complete") is True,
        observed_passed=result.get("passed") is True,
        observed_counts=_assertion_counts(result),
        expected_failing_cases=tuple(sorted(expected_failing)),
        observed_failing_cases=None
        if outcomes is None
        else tuple(sorted(name for name, case_passed in outcomes.items() if not case_passed)),
        observed_case_ids=None if outcomes is None else tuple(sorted(outcomes)),
        observed_messages=_observed_messages(result),
    )


def _observed_messages(result: dict[str, Any]) -> tuple[str, ...] | None:
    runtime = result.get("runtime")
    cases = runtime.get("cases") if isinstance(runtime, dict) else None
    if not isinstance(cases, list):
        return None
    messages: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or case.get("passed") is not False:
            continue
        message = case.get("message")
        if isinstance(message, str) and message.strip():
            text = message.strip()[:240]
            if text not in messages:
                messages.append(text)
        if len(messages) >= 5:
            break
    return tuple(messages) or None


def _observed_outcomes(result: dict[str, Any]) -> dict[str, bool] | None:
    runtime = result.get("runtime")
    outcomes = runtime.get("caseOutcomes") if isinstance(runtime, dict) else None
    if not isinstance(outcomes, dict):
        return None
    if not all(
        isinstance(name, str) and type(value) is bool for name, value in outcomes.items()
    ):
        return None
    return outcomes


def _assertion_counts(result: dict[str, Any]) -> tuple[int, int] | None:
    runtime = result.get("runtime")
    if isinstance(runtime, dict):
        passed = runtime.get("passedAssertions")
        failed = runtime.get("failedAssertions")
        if type(passed) is int and type(failed) is int:
            return passed, failed
        cases = runtime.get("cases")
        if isinstance(cases, list) and all(isinstance(case, dict) for case in cases):
            return (
                sum(case.get("passed") is True for case in cases),
                sum(case.get("passed") is False for case in cases),
            )
    return None


def _cases_match(
    result: dict[str, Any], expected: set[str], failed: set[str], *, required: bool,
) -> bool:
    runtime = result.get("runtime")
    outcomes = runtime.get("caseOutcomes") if isinstance(runtime, dict) else None
    if outcomes is None:
        return not required
    return bool(isinstance(outcomes, dict) and set(outcomes) == expected
                and all(type(value) is bool for value in outcomes.values())
                and {name for name, passed in outcomes.items() if not passed} == failed)


def _runtime_unavailable(result: dict[str, Any]) -> bool:
    runtime = result.get("runtime")
    return bool(
        result.get("complete") is not True
        and isinstance(runtime, dict)
        and runtime.get("status") in {"unavailable", "skipped"}
    )
