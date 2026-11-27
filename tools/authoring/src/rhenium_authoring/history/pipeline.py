"""Project-history authoring pipeline (Minecraft Paper plugins first).

Stages per candidate, each checkpointed under
``.rhenium/authoring/runs/<run>/candidates/<id>/``:

1. walk repository history for landed fixes (``discovery``);
2. check out base and fixed trees, infer and prove the build (no model);
3. triage: can the fixed behaviour be observed on a headless server?
4. author: exam, live-server suite, seed data and case contracts, with
   static, compile and exam-leakage checks inside the tool loop;
5. independent review of fairness and leakage;
6. engine controls on the real server: starter, reference (three runs), an
   alternative written without seeing the fix, a target-negative, a
   compat-negative and a tamper control;
7. publication into ``benchmarks/minecraft-history`` with study controls.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, HttpUrl

from ..model_client import ModelClient
from ..models import CandidateStatus, RunMode, RunStatus, SourceKind, SourceProject
from ..pipeline import used_fix_keys
from ..sources.github import GitHubSource
from ..state import AuthoringStore
from . import prompts
from .agent import AgentExhausted, RepositoryTools, run_agent
from .checkout import CheckoutError, RepositoryCheckout
from .discovery import HistoryDiscovery
from .engine import ControlOutcome, HistoryEngine, hunk_reverts, tamper
from .leaks import exam_leaks
from .minecraft_build import BuildRejected, DockerProbe, infer_build, load_core_script, reference_tree
from .minecraft_checks import compile_findings, static_findings
from .minecraft_pack import PACK_DIRECTORY, HistoryTask, add_task, initialize_pack
from .models import AuthoredTask, BuildProbe, HistoryFix, ReviewVerdict, SourcePatch, TriageDecision
from .study_controls import controls_markdown, write_study_controls

SUPPORTED_GAMES = frozenset({"minecraft"})


def _accepted(verdict: ReviewVerdict) -> bool:
    """The reviewer's own approval decides; its convention notes are kept on record.

    The reviewer lists every convention a case relies on, including ones it found
    stated in the exam or already produced by the repository, and is instructed to
    withhold approval when a case depends on one that is not.
    """
    return verdict.approved and verdict.derivable_from_exam


class CandidateRejected(Exception):
    """A candidate stops here; the message is the recorded reason."""


def _save(path: Path, value: BaseModel | dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


class HistoryPipeline:
    def __init__(
        self,
        project_root: Path,
        store: AuthoringStore,
        client: ModelClient,
        github: GitHubSource,
        *,
        reviewer: ModelClient | None = None,
        engine_account: str | None = None,
        mode: RunMode = RunMode.REVIEW,
        max_turns: int = 40,
        repair_rounds: int = 3,
        on_event: Callable[[dict[str, object]], None] | None = None,
        excluded_fix_keys: set[str] | None = None,
    ):
        self.project_root = project_root.resolve()
        self.store = store
        self.client = client
        self.reviewer = reviewer or client
        self.github = github
        self.mode = mode
        self.max_turns = max_turns
        self.repair_rounds = repair_rounds
        self.on_event = on_event or (lambda _event: None)
        self.excluded_fix_keys = set(excluded_fix_keys or ())
        self.checkout = RepositoryCheckout(
            github._client, self.project_root / ".rhenium" / "authoring" / "repos"
        )
        self.engine = HistoryEngine(self.project_root, prepare_account=engine_account)
        self.probe = DockerProbe(self.project_root)
        materialize = load_core_script(self.project_root, "scripts/materialize.py", "history_defaults")
        self.frozen_defaults: tuple[str, ...] = tuple(materialize.DEFAULT_FROZEN_PATHS)

    # -- run ------------------------------------------------------------------

    def run(
        self,
        *,
        game_id: str,
        repositories: list[str],
        discover: int,
        per_repository: int,
        target: int,
        pages_per_run: int,
        workers: int,
        seeds: list[str] | None = None,
    ) -> str:
        """Walk history (or take the ``owner/repo@sha`` seeds) and author up to ``target`` tasks."""
        if game_id not in SUPPORTED_GAMES:
            raise ValueError(f"project-history mode supports {sorted(SUPPORTED_GAMES)}")
        run_id = self.store.create_run(self.mode)
        run_root = self.project_root / ".rhenium" / "authoring" / "runs" / run_id
        run_root.mkdir(parents=True)
        run_root.chmod(0o700)
        started = time.monotonic()
        discovery = HistoryDiscovery(
            self.github, self.store, pages_per_run=pages_per_run, on_event=self.on_event
        )
        self.store.update_run(run_id, RunStatus.HARVESTING)
        fixes: list[HistoryFix] = []
        excluded = set(used_fix_keys(self.project_root)) | self.excluded_fix_keys
        try:
            seeded = self._seeded(game_id, seeds or [], discovery)
            fixes.extend(seeded)
            walked = [] if seeds else self._repositories(game_id, repositories, discover, discovery)
            for repository, url, license_id in walked:
                for fix in discovery.fixes(
                    repository, url, license_id, game_id, limit=per_repository, exclude=excluded
                ):
                    fixes.append(fix)
                    excluded.add(fix.key)
                    self._event({"stage": "history-fix", "candidate": fix.candidate_id, "origin": fix.origin})
            _save(run_root / "history-fixes.json", [fix.model_dump(mode="json") for fix in fixes])
            self.store.update_run(run_id, RunStatus.SYNTHESIZING)
            validated: list[str] = []

            def work(fix: HistoryFix) -> CandidateStatus:
                if len(validated) >= target:
                    return CandidateStatus.DISCOVERED
                status = self.candidate(run_id, run_root, fix)
                if status in (CandidateStatus.VALIDATED, CandidateStatus.PUBLISHED):
                    validated.append(fix.candidate_id)
                return status

            with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
                statuses = list(pool.map(work, fixes))
            summary = {
                "fixes": len(fixes),
                "discovery": asdict(discovery.stats),
                "statuses": {status.value: statuses.count(status) for status in set(statuses)},
                "validated": validated,
                "seconds": round(time.monotonic() - started, 1),
            }
            _save(run_root / "history-summary.json", summary)
            final = (
                RunStatus.ACTION_REQUIRED
                if CandidateStatus.ACTION_REQUIRED in statuses
                else RunStatus.AWAITING_REVIEW
                if self.mode == RunMode.REVIEW
                else RunStatus.COMPLETE
            )
            self.store.update_run(run_id, final)
        except Exception as error:
            self.store.update_run(run_id, RunStatus.FAILED, str(error)[:500])
            raise
        return run_id

    def _seeded(self, game_id: str, seeds: list[str], discovery: HistoryDiscovery) -> list[HistoryFix]:
        fixes: list[HistoryFix] = []
        for seed in seeds:
            name, _, sha = seed.partition("@")
            url = HttpUrl(f"https://github.com/{name}")
            project = SourceProject(
                source=SourceKind.GITHUB, external_id=name, game_id=game_id, project_url=url, source_url=url
            )
            try:
                canonical = self.github.canonical_project(project)
            except (ValueError, RuntimeError):
                discovery.stats.reject("repository licence or metadata unusable")
                continue
            fix = discovery.seed(name, str(canonical.source_url), str(canonical.license_spdx), game_id, sha)
            if fix is not None:
                fixes.append(fix)
                self._event({"stage": "history-fix", "candidate": fix.candidate_id, "origin": "seed"})
        return fixes

    def _repositories(
        self, game_id: str, explicit: list[str], limit: int, discovery: HistoryDiscovery
    ) -> list[tuple[str, str, str]]:
        projects: list[SourceProject] = []
        for name in explicit:
            url = HttpUrl(f"https://github.com/{name}")
            projects.append(
                SourceProject(
                    source=SourceKind.GITHUB,
                    external_id=name,
                    game_id=game_id,
                    project_url=url,
                    source_url=url,
                )
            )
        if not explicit:
            projects = self.github.discover(game_id, limit)
        found: list[tuple[str, str, str]] = []
        for project in projects:
            try:
                canonical = self.github.canonical_project(project)
                repository = self.github.repository_name(str(canonical.source_url))
                payload = self.github.http.get_json(f"/repos/{repository}")
                branch = str(payload.get("default_branch") or "HEAD")
                if not discovery.plugin_layout(repository, branch):
                    discovery.stats.reject("not a Java plugin layout")
                    continue
            except (ValueError, RuntimeError):
                discovery.stats.reject("repository licence or metadata unusable")
                continue
            found.append((repository, str(canonical.source_url), str(canonical.license_spdx)))
        return found

    # -- one candidate ----------------------------------------------------------

    def candidate(self, run_id: str, run_root: Path, fix: HistoryFix) -> CandidateStatus:
        try:
            return self._candidate_outcome(run_id, run_root, fix)
        finally:
            self.probe.release(fix.candidate_id)

    def _candidate_outcome(self, run_id: str, run_root: Path, fix: HistoryFix) -> CandidateStatus:
        cid = fix.candidate_id
        root = run_root / "candidates" / cid
        root.mkdir(parents=True, exist_ok=True)
        _save(root / "fix.json", fix)
        record: dict[str, Any] = {"fix": fix.key, "timings": {}}
        self._put(run_id, fix, CandidateStatus.DISCOVERED, record)
        try:
            status = self._candidate(run_id, root, fix, record)
        except CandidateRejected as error:
            self._put(run_id, fix, CandidateStatus.REJECTED, record, str(error))
            return CandidateStatus.REJECTED
        except AgentExhausted as error:
            self._put(run_id, fix, CandidateStatus.REJECTED, record, str(error))
            return CandidateStatus.REJECTED
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
            self._put(run_id, fix, CandidateStatus.REJECTED, record, f"{type(error).__name__}: {error}"[:500])
            return CandidateStatus.REJECTED
        return status

    def _timed(self, record: dict[str, Any], stage: str, started: float) -> None:
        record["timings"][stage] = round(time.monotonic() - started, 1)

    def _candidate(self, run_id: str, root: Path, fix: HistoryFix, record: dict[str, Any]) -> CandidateStatus:
        cid = fix.candidate_id
        started = time.monotonic()
        try:
            base = self.checkout.tree(fix.repository, fix.base_sha)
            fixed = self.checkout.tree(fix.repository, fix.fixed_sha)
        except CheckoutError as error:
            raise CandidateRejected(f"checkout: {error}") from None
        try:
            guess = infer_build(base, core_defaults=self.frozen_defaults)
            reference = root / "reference"
            applied = reference_tree(base, fixed, fix.changed_files, reference)
            probe = self.probe.probe(cid, base, reference, applied, guess, root / "logs")
        except BuildRejected as error:
            raise CandidateRejected(f"build: {error}") from None
        _save(root / "probe.json", probe)
        _save(root / "applied.json", applied)
        self._timed(record, "build", started)

        started = time.monotonic()
        examples = examples_tree(self.project_root, root / "examples", fix.repository)
        tools = RepositoryTools({"base": base, "reference": reference, "examples": examples}, fix.patch)
        facts = self._facts(fix, probe, applied)
        triage = run_agent(
            self.client,
            TriageDecision,
            role="triage",
            brief={"instructions": list(prompts.TRIAGE), "candidate": facts},
            tools=tools,
            max_turns=min(self.max_turns, 20),
            transcript=root / "transcripts" / "triage.json",
        )
        _save(root / "triage.json", triage)
        self._timed(record, "triage", started)
        if not triage.reproducible:
            raise CandidateRejected(f"triage: {triage.reason[:300]}")

        started = time.monotonic()
        authored = self._author(root, fix, probe, triage, tools, facts, feedback=None)
        self._timed(record, "author", started)
        authored = self._review_loop(root, fix, probe, triage, tools, facts, authored, record)

        return self._validate(
            run_id,
            root,
            HistoryTask(fix, probe, triage, authored, base, reference, applied),
            tools,
            facts,
            record,
        )

    def resume(self, run_id: str, root: Path, *, from_review: bool = False) -> CandidateStatus:
        """Rerun a candidate from its engine controls (or its review), reusing every checkpoint."""
        task, _outcomes = load_candidate(self.project_root, root, require_validation=False)
        fix = task.fix
        record: dict[str, Any] = {"fix": fix.key, "timings": {}, "resumed": True}
        examples = examples_tree(self.project_root, root / "examples", fix.repository)
        tools = RepositoryTools(
            {"base": task.base_tree, "reference": task.reference_tree, "examples": examples}, fix.patch
        )
        facts = self._facts(fix, task.probe, task.applied)
        try:
            if from_review:
                authored = self._review_loop(
                    root, fix, task.probe, task.triage, tools, facts, task.authored, record
                )
                task = HistoryTask(
                    fix, task.probe, task.triage, authored, task.base_tree, task.reference_tree, task.applied
                )
            return self._validate(run_id, root, task, tools, facts, record)
        except (CandidateRejected, AgentExhausted) as error:
            self._put(run_id, fix, CandidateStatus.REJECTED, record, str(error))
            return CandidateStatus.REJECTED
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
            self._put(run_id, fix, CandidateStatus.REJECTED, record, f"{type(error).__name__}: {error}"[:500])
            return CandidateStatus.REJECTED
        finally:
            self.probe.release(fix.candidate_id)

    def _validate(
        self,
        run_id: str,
        root: Path,
        task: HistoryTask,
        tools: RepositoryTools,
        facts: dict[str, object],
        record: dict[str, Any],
    ) -> CandidateStatus:
        fix, probe, triage, authored = task.fix, task.probe, task.triage, task.authored
        base, reference, applied = task.base_tree, task.reference_tree, task.applied
        started = time.monotonic()
        outcomes = self._controls(root, task, tools, facts, record)
        self._timed(record, "engine", started)
        _save(root / "validation.json", [outcome.record() for outcome in outcomes])
        final = self._load_authored(root)
        if final != authored:
            # The engine repair loop changed the suite or exam: the published version
            # must itself have passed review, so review it once more (no revision).
            verdict = self._review(root, facts, final, tools, "review-final")
            if not _accepted(verdict):
                raise CandidateRejected("review: the engine-repaired task was not approved")
        task = HistoryTask(fix, probe, triage, final, base, reference, applied)
        record["controls"] = {outcome.label: outcome.admissible for outcome in outcomes}
        status = CandidateStatus.VALIDATED
        self._put(run_id, fix, status, record)
        if self.mode == RunMode.YOLO:
            self.publish_task(root, task, outcomes)
            status = CandidateStatus.PUBLISHED
            self._put(run_id, fix, status, record)
        return status

    # -- model roles --------------------------------------------------------------

    def _facts(self, fix: HistoryFix, probe: BuildProbe, applied: list[str]) -> dict[str, object]:
        return {
            "plugin_name": probe.plugin_name,
            "build": {"tool": probe.tool, "assemble": probe.assemble, "artifact": probe.artifact},
            "upstream_unit_cases": len(probe.unit_cases),
            "fix_title": fix.title,
            "fix_description": fix.description[:6000],
            "fix_message": fix.commit_message[:4000],
            "changed_main_files": applied,
            "frozen_paths": list(probe.frozen_paths),
        }

    def _author_check(self, fix: HistoryFix, root: Path) -> Callable[[AuthoredTask], list[str]]:
        def check(task: AuthoredTask) -> list[str]:
            problems = static_findings(task) + exam_leaks(task.exam, fix)
            if not problems:
                compiled = compile_findings(task, root / "logs" / "base-plugin.jar")
                problems = compiled or []
            return problems

        return check

    def _author(
        self,
        root: Path,
        fix: HistoryFix,
        probe: BuildProbe,
        triage: TriageDecision,
        tools: RepositoryTools,
        facts: dict[str, object],
        *,
        feedback: dict[str, object] | None,
    ) -> AuthoredTask:
        brief: dict[str, object] = {
            "instructions": list(prompts.AUTHOR),
            "candidate": facts,
            "triage": triage.model_dump(mode="json"),
        }
        if feedback is not None:
            brief["revise"] = feedback
        round_name = "author" if feedback is None else f"author-{int(time.time())}"
        authored = run_agent(
            self.client,
            AuthoredTask,
            role="author",
            brief=brief,
            tools=tools,
            max_turns=self.max_turns,
            check=self._author_check(fix, root),
            transcript=root / "transcripts" / f"{round_name}.json",
        )
        _save(root / "authored.json", authored)
        return authored

    def _load_authored(self, root: Path) -> AuthoredTask:
        return AuthoredTask.model_validate_json((root / "authored.json").read_text(encoding="utf-8"))

    def _review_loop(
        self,
        root: Path,
        fix: HistoryFix,
        probe: BuildProbe,
        triage: TriageDecision,
        tools: RepositoryTools,
        facts: dict[str, object],
        authored: AuthoredTask,
        record: dict[str, Any],
    ) -> AuthoredTask:
        for attempt in range(2):
            verdict = self._review(root, facts, authored, tools, f"review-{attempt}")
            record["review_rounds"] = attempt + 1
            if _accepted(verdict):
                return authored
            if attempt == 1:
                break
            authored = self._author(
                root,
                fix,
                probe,
                triage,
                tools,
                facts,
                feedback={
                    "previous": authored.model_dump(mode="json"),
                    "review_findings": list(verdict.findings),
                    "unpublished_conventions": list(verdict.unpublished_conventions),
                    "instruction": "Start from 'previous' and revise the exam and suite so every finding "
                    "is resolved; re-read only what the findings require and finish within a few turns.",
                },
            )
        raise CandidateRejected("review: the task was not approved after one revision")

    def _review(
        self, root: Path, facts: dict[str, object], authored: AuthoredTask, tools: RepositoryTools, name: str
    ) -> ReviewVerdict:
        verdict = run_agent(
            self.reviewer,
            ReviewVerdict,
            role="review",
            brief={
                "instructions": list(prompts.REVIEW),
                "candidate": facts,
                "exam": authored.exam,
                "suite": authored.suite,
                "seed": authored.seed,
                "cases": [case.model_dump(mode="json") for case in authored.cases],
            },
            tools=tools,
            max_turns=min(self.max_turns, 16),
            transcript=root / "transcripts" / f"{name}.json",
        )
        _save(root / f"{name}.json", verdict)
        return verdict

    # -- engine controls ------------------------------------------------------------

    def _controls(
        self,
        root: Path,
        task: HistoryTask,
        tools: RepositoryTools,
        facts: dict[str, object],
        record: dict[str, Any],
    ) -> list[ControlOutcome]:
        outcomes: list[ControlOutcome] = []
        for round_index in range(self.repair_rounds + 1):
            hub, key = self.engine.open(root, task)
            if hub is None:
                raise CandidateRejected(f"engine: {key}")
            starter = self.engine.run(
                hub, key, root, task, label="starter", kind="starter", base=task.base_tree
            )
            reference = self.engine.run(
                hub, key, root, task, label="reference-1", kind="reference", base=task.reference_tree
            )
            if starter.admissible and reference.admissible:
                outcomes = [starter, reference]
                break
            if round_index == self.repair_rounds:
                raise CandidateRejected(f"engine: starter {starter.reason}; reference {reference.reason}")
            authored = self._author(
                root,
                task.fix,
                task.probe,
                task.triage,
                tools,
                facts,
                feedback={
                    "previous": task.authored.model_dump(mode="json"),
                    "engine": {
                        "starter": {"expected": "fails exactly the target cases", **starter.record()},
                        "reference": {"expected": "passes every case", **reference.record()},
                        "server_log_tail": self.engine.log_tail(root, "reference-1"),
                    },
                    "instruction": "Start from 'previous' and fix the suite, seed or case roles so the "
                    "starter fails exactly the target cases and the reference passes every case. Change "
                    "only what the engine evidence requires; re-read only what you need and finish within "
                    "a few turns.",
                },
            )
            task = HistoryTask(
                task.fix, task.probe, task.triage, authored, task.base_tree, task.reference_tree, task.applied
            )
        hub, key = self.engine.open(root, task)
        if hub is None:
            raise CandidateRejected(f"engine: {key}")
        for index in (2, 3):
            repeat = self.engine.run(
                hub, key, root, task, label=f"reference-{index}", kind="reference", base=task.reference_tree
            )
            outcomes.append(repeat)
            if not repeat.admissible:
                raise CandidateRejected(f"engine: reference is not stable ({repeat.reason})")
        outcomes.append(self._alternative(root, task, hub, key))
        outcomes.append(self._target_negative(root, task, hub, key))
        compat = self._compat_negative(root, task, hub, key)
        if compat is not None:
            outcomes.append(compat)
        changes = tamper(task.reference_tree, task.probe.frozen_paths)
        tampered = self.engine.run(
            hub, key, root, task, label="tamper", kind="tamper", base=task.reference_tree, changes=changes
        )
        outcomes.append(tampered)
        if not tampered.admissible:
            raise CandidateRejected(
                f"engine: tampering with frozen files changed the verdict ({tampered.reason})"
            )
        return outcomes

    def _patch_check(self, task: HistoryTask, tree: Path) -> Callable[[SourcePatch], list[str]]:
        """Compile a proposed patch (applied over ``tree``'s files) before engine time is spent."""
        tag = self.probe.ensure_base_image(task.fix.candidate_id, task.base_tree, task.probe)

        def check(patch: SourcePatch) -> list[str]:
            if tag is None:
                return []
            files = dict(patch.files)
            if tree != task.base_tree:
                # Controls over the reference: the image holds the base tree, so the
                # reference's changed files travel with the patch.
                files = {**{p: (tree / p).read_text(encoding="utf-8") for p in task.applied}, **files}
            return self.probe.compile_findings(tag, task.probe, files)

        return check

    def _alternative(self, root: Path, task: HistoryTask, hub: Any, key: str) -> ControlOutcome:
        saved = root / "alternative.json"
        exam_digest = hashlib.sha256(task.authored.exam.encode()).hexdigest()
        marker = root / "alternative-exam.sha256"
        if saved.is_file() and marker.is_file() and marker.read_text().strip() == exam_digest:
            # A resumed candidate re-checks its earlier admissible alternative first.
            earlier = SourcePatch.model_validate_json(saved.read_text(encoding="utf-8"))
            outcome = self.engine.run(
                hub,
                key,
                root,
                task,
                label="alternative-saved",
                kind="alternative",
                base=task.base_tree,
                changes=dict(earlier.files),
            )
            if outcome.admissible:
                return outcome
        tools = RepositoryTools({"base": task.base_tree})
        feedback: dict[str, object] | None = None
        for attempt in range(2):
            brief: dict[str, object] = {"instructions": list(prompts.ALTERNATIVE), "exam": task.authored.exam}
            if feedback is not None:
                brief["previous_attempt"] = feedback
            patch = run_agent(
                self.client,
                SourcePatch,
                role="alternative",
                brief=brief,
                tools=tools,
                max_turns=self.max_turns,
                check=self._patch_check(task, task.base_tree),
                transcript=root / "transcripts" / f"alternative-{attempt}.json",
            )
            _save(root / f"alternative-{attempt}.json", patch)
            outcome = self.engine.run(
                hub,
                key,
                root,
                task,
                label=f"alternative-{attempt}",
                kind="alternative",
                base=task.base_tree,
                changes=dict(patch.files),
            )
            if outcome.admissible:
                _save(root / "alternative.json", patch)
                marker.write_text(exam_digest + "\n", encoding="utf-8")
                return outcome
            feedback = {
                "files": sorted(patch.files),
                "failed_cases": outcome.failed,
                "messages": outcome.messages,
                "reason": outcome.reason,
            }
        raise CandidateRejected("engine: no independently written alternative passed the task")

    def _target_negative(self, root: Path, task: HistoryTask, hub: Any, key: str) -> ControlOutcome:
        variants = hunk_reverts(task.base_tree, task.reference_tree, task.applied, limit=3)
        for index, variant in enumerate(variants):
            outcome = self.engine.run(
                hub,
                key,
                root,
                task,
                label=f"target-negative-{index}",
                kind="target-negative",
                base=task.reference_tree,
                changes=dict(variant),
            )
            if outcome.admissible:
                _save(root / "target-negative.json", {"files": variant, "origin": "reverted hunk"})
                return outcome
        # Reverting one hunk alone often does not compile (the fix refactors) or is not
        # observable; a model then writes a plausible partial fix of the reference.
        tools = RepositoryTools({"reference": task.reference_tree, "base": task.base_tree}, task.fix.patch)
        preserved = [case.case for case in task.authored.cases if case.role == "preserved"]
        feedback: dict[str, object] | None = None
        for attempt in range(2):
            brief: dict[str, object] = {
                "instructions": list(prompts.TARGET_NEGATIVE),
                "exam": task.authored.exam,
                "target_cases": sorted(task.authored.target_cases),
                "preserved_cases": preserved,
                "suite": task.authored.suite,
            }
            if feedback is not None:
                brief["previous_attempt"] = feedback
            patch = run_agent(
                self.client,
                SourcePatch,
                role="target-negative",
                brief=brief,
                tools=tools,
                max_turns=min(self.max_turns, 24),
                check=self._patch_check(task, task.reference_tree),
                transcript=root / "transcripts" / f"target-negative-{attempt}.json",
            )
            outcome = self.engine.run(
                hub,
                key,
                root,
                task,
                label=f"target-negative-model-{attempt}",
                kind="target-negative",
                base=task.reference_tree,
                changes=dict(patch.files),
            )
            if outcome.admissible:
                _save(
                    root / "target-negative.json",
                    {"files": patch.files, "origin": "model partial fix", "rationale": patch.rationale},
                )
                return outcome
            feedback = {
                "files": sorted(patch.files),
                "failed_cases": outcome.failed,
                "messages": outcome.messages,
                "reason": outcome.reason,
                "complete": outcome.complete,
            }
        raise CandidateRejected("engine: no target-negative control fails only target cases")

    def _compat_negative(self, root: Path, task: HistoryTask, hub: Any, key: str) -> ControlOutcome | None:
        preserved = [case.case for case in task.authored.cases if case.role == "preserved"]
        if not preserved:
            return None
        tools = RepositoryTools({"reference": task.reference_tree})
        try:
            patch = run_agent(
                self.client,
                SourcePatch,
                role="compat-negative",
                brief={
                    "instructions": list(prompts.COMPAT_NEGATIVE),
                    "exam": task.authored.exam,
                    "target_cases": sorted(task.authored.target_cases),
                    "preserved_cases": preserved,
                    "suite": task.authored.suite,
                },
                tools=tools,
                max_turns=min(self.max_turns, 20),
                check=self._patch_check(task, task.reference_tree),
                transcript=root / "transcripts" / "compat-negative.json",
            )
        except AgentExhausted:
            return None
        outcome = self.engine.run(
            hub,
            key,
            root,
            task,
            label="compat-negative",
            kind="compat-negative",
            base=task.reference_tree,
            changes=dict(patch.files),
        )
        if outcome.admissible:
            _save(root / "compat-negative.json", patch)
            return outcome
        return None  # optional: the task then only lacks joint-analysis qualification

    # -- publication ------------------------------------------------------------------

    def publish_task(self, root: Path, task: HistoryTask, outcomes: list[ControlOutcome]) -> None:
        pack = self.project_root / "benchmarks" / PACK_DIRECTORY
        initialize_pack(pack, self.project_root)
        task.controls_markdown = controls_markdown(task, outcomes)
        add_task(pack, task)
        write_study_controls(pack, root, task, outcomes)

    def _put(
        self,
        run_id: str,
        fix: HistoryFix,
        status: CandidateStatus,
        record: dict[str, Any],
        reason: str | None = None,
    ) -> None:
        self.store.put_candidate(run_id, fix.candidate_id, fix.game_id, status, record, reason=reason)
        self._event(
            {
                "stage": "history-candidate",
                "candidate": fix.candidate_id,
                "status": status.value,
                "reason": reason,
            }
        )

    def _event(self, event: dict[str, object]) -> None:
        self.on_event(event)


NOTES_ASSET = Path(__file__).with_name("assets") / "harness-notes.md"


def examples_tree(project_root: Path, destination: Path, repository: str) -> Path:
    """Maintainer knowledge for the author: harness API, lessons, other repositories' suites.

    Suites of the candidate's own repository are left out, so a hand-authored
    task never hands its own hidden suite to the task being generated.
    """
    import shutil

    core = project_root / "benchmarks" / "minecraft-core"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    shutil.copyfile(NOTES_ASSET, destination / "README.md")
    harness = core / "private" / "harbor" / "harness" / "gcb-harness" / "src" / "main" / "java"
    shutil.copytree(harness, destination / "harness", ignore=shutil.ignore_patterns("__pycache__"))
    catalog = json.loads((core / "catalog.json").read_text(encoding="utf-8"))
    own = f"https://github.com/{repository}".casefold()
    for task in catalog.get("tasks", []):
        upstream = str((task.get("upstream") or {}).get("repository", "")).rstrip("/").casefold()
        if upstream == own:
            continue
        source = core / "private" / "harbor" / str(task["id"])
        target = destination / "suites" / str(task["id"])
        if (source / "tests" / "suite").is_dir():
            shutil.copytree(source / "tests" / "suite", target / "suite")
        notes = (source / "NOTES.md").read_text(encoding="utf-8") if (source / "NOTES.md").is_file() else ""
        design = notes.split("## Live-server design", 1)
        if len(design) == 2:
            target.mkdir(parents=True, exist_ok=True)
            design_text = "## Live-server design" + design[1]
            (target / "live-server-design.md").write_text(design_text, encoding="utf-8")
    return destination


def load_candidate(
    project_root: Path, root: Path, *, require_validation: bool = True
) -> tuple[HistoryTask, list[ControlOutcome]]:
    """Rebuild a candidate from its checkpoints (publication, or resume before validation)."""
    fix = HistoryFix.model_validate_json((root / "fix.json").read_text(encoding="utf-8"))
    probe = BuildProbe.model_validate_json((root / "probe.json").read_text(encoding="utf-8"))
    triage = TriageDecision.model_validate_json((root / "triage.json").read_text(encoding="utf-8"))
    authored = AuthoredTask.model_validate_json((root / "authored.json").read_text(encoding="utf-8"))
    applied = json.loads((root / "applied.json").read_text(encoding="utf-8"))
    validation = root / "validation.json"
    outcomes = (
        [ControlOutcome(**item) for item in json.loads(validation.read_text(encoding="utf-8"))]
        if require_validation or validation.is_file()
        else []
    )
    checkout = project_root / ".rhenium" / "authoring" / "repos"
    owner, name = fix.repository.split("/", 1)
    base = checkout / owner.casefold() / name.casefold() / fix.base_sha / "tree"
    if not base.is_dir() or not (root / "reference").is_dir():
        raise FileNotFoundError("the candidate's checkouts are missing; rerun it")
    return HistoryTask(fix, probe, triage, authored, base, root / "reference", list(applied)), outcomes
