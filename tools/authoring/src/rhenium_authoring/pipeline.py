from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from .artifacts import materialize_bundle, write_validation
from .cleanroom import CleanRoomSynthesizer
from .engine import HubEngineValidator
from .engine_feedback import EngineRepairPlan, plan_engine_repair
from .game_adapters import GameAuthoringSpec, game_spec
from .gates import LeakageError, validate_defect_paths, validate_public_candidate
from .models import (
    BehaviorCapsule,
    CandidateStatus,
    CompositeCandidate,
    DefectiveProject,
    GeneratedProject,
    HistoricalFix,
    RunMode,
    RunStatus,
    SourceProject,
    SynthesisBundle,
    SynthInterfaceContract,
    ValidationReport,
    VerifierBundle,
)
from .publisher import PackPublisher
from .sources.base import SourceAdapter, validate_fix_source
from .sources.github import GitHubSource
from .state import AuthoringStore


class AuthoringPipeline:
    def __init__(
        self,
        project_root: Path,
        store: AuthoringStore,
        synthesizer: CleanRoomSynthesizer | None,
        sources: dict[str, SourceAdapter],
        github: GitHubSource | None,
        validator: HubEngineValidator | None = None,
        publisher: PackPublisher | None = None,
        engine_repair_rounds: int = 1,
        candidate_attempts: int = 2,
    ):
        if engine_repair_rounds < 0 or engine_repair_rounds > 3:
            raise ValueError("engine repair rounds must be between 0 and 3")
        if candidate_attempts < 1 or candidate_attempts > 3:
            raise ValueError("candidate attempts must be between 1 and 3")
        self.project_root = project_root.resolve()
        self.store = store
        self.synthesizer = synthesizer
        self.sources = sources
        self.github = github
        self.validator = validator or HubEngineValidator(self.project_root)
        self.publisher = publisher or PackPublisher(self.project_root)
        self.engine_repair_rounds = engine_repair_rounds
        self._review_notes: dict[str, str] = {}
        self.candidate_attempts = candidate_attempts

    def run(
        self,
        *,
        mode: RunMode,
        source_names: Sequence[str],
        game_ids: Sequence[str],
        limit: int,
        seed_fixes: Sequence[HistoricalFix] | None = None,
        target: int | None = None,
        max_capsules: int = 7,
        excluded_fix_keys: frozenset[str] = frozenset(),
        per_repository: int | None = None,
    ) -> str:
        if limit < 2 or limit > 100:
            raise ValueError("authoring limit must be between 2 and 100")
        if target is not None:
            if target < 1 or target > 20:
                raise ValueError("authoring target must be between 1 and 20")
            # Composition groups up to seven capsules per candidate, so give
            # the harvest enough distinct fixes to yield `target` candidates.
            limit = min(100, max(limit, 4 * target))
        if self.synthesizer is None:
            raise RuntimeError("authoring synthesis service is unavailable")
        if seed_fixes is None and self.github is None:
            raise RuntimeError("authoring acquisition service is unavailable")
        synthesizer = self.synthesizer
        for game_id in game_ids:
            game_spec(game_id)
        if seed_fixes is None:
            unknown_sources = set(source_names) - set(self.sources)
            if unknown_sources:
                raise ValueError("unknown authoring source")
        elif len(seed_fixes) < 2 or len(seed_fixes) > 100:
            raise ValueError("seeded authoring requires between 2 and 100 historical fixes")
        run_id = self.store.create_run(mode)
        run_root = self.project_root / ".rhenium" / "authoring" / "runs" / run_id
        run_root.mkdir(parents=True, exist_ok=False)
        run_root.chmod(0o700)
        try:
            if seed_fixes is None:
                self.store.update_run(run_id, RunStatus.HARVESTING)
                fixes = self._harvest(source_names, game_ids, limit, excluded_fix_keys, per_repository)
            else:
                fixes = list(seed_fixes)
            for fix in fixes:
                validate_fix_source(fix)
            fixes_path = run_root / "historical-fixes.json"
            fixes_path.write_text(
                json.dumps(
                    [fix.model_dump(mode="json") for fix in fixes],
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            fixes_path.chmod(0o600)
            self.store.update_run(run_id, RunStatus.SYNTHESIZING)
            capsules = []
            eligible_fixes: list[HistoricalFix] = []
            for fix in fixes:
                capsule = self._extract_capsule(synthesizer, fix)
                if capsule is None:
                    # The capsule kept quoting source identity; dropping the fix
                    # fails closed without ending the run for the other sources.
                    continue
                _checkpoint(run_root / "checkpoints" / "capsules", capsule.capsule_id, capsule)
                capsules.append(capsule)
                eligible_fixes.append(fix)
            fixes_by_capsule = {
                capsule.capsule_id: fix for capsule, fix in zip(capsules, eligible_fixes, strict=True)
            }
            composites = synthesizer.compose(capsules, max_capsules)
            if not composites:
                raise RuntimeError("harvest produced no game with at least two eligible fixes")

            any_action_required = False
            validated_count = 0
            already_validated = self.store.validated_candidate_ids()
            for candidate in composites:
                if target is not None and validated_count >= target:
                    break
                if candidate.id in already_validated:
                    # This exact capsule composition already produced a
                    # validated task in an earlier run; regenerating it would
                    # only duplicate those behaviors.
                    continue
                selected_fixes = tuple(fixes_by_capsule[capsule.capsule_id] for capsule in candidate.capsules)
                self.store.put_candidate(
                    run_id,
                    candidate.id,
                    candidate.game_id,
                    CandidateStatus.EXTRACTED,
                    candidate.model_dump(mode="json"),
                )
                checkpoints = run_root / "checkpoints" / candidate.id
                attempts = 1 if target is None else self.candidate_attempts
                status = CandidateStatus.REJECTED
                self._review_notes.pop(candidate.id, None)
                for attempt in range(1, attempts + 1):
                    if attempt > 1:
                        # Keep the failed attempt's private artifacts for
                        # diagnosis before regenerating from the same capsules.
                        rotated = checkpoints.with_name(f"{candidate.id}-attempt{attempt - 1}")
                        if checkpoints.exists() and not rotated.exists():
                            checkpoints.rename(rotated)
                    try:
                        status = self._author_candidate(
                            run_id,
                            run_root,
                            mode,
                            synthesizer,
                            candidate,
                            selected_fixes,
                            checkpoints,
                            prior_review=self._gated_review_note(candidate, selected_fixes),
                        )
                    except (LeakageError, RuntimeError, ValueError) as error:
                        # A model stage or clean-room guard that gives up on
                        # this candidate must not end the run: reject it (the
                        # target loop may regenerate) and move on.
                        status = CandidateStatus.REJECTED
                        self.store.put_candidate(
                            run_id,
                            candidate.id,
                            candidate.game_id,
                            CandidateStatus.REJECTED,
                            candidate.model_dump(mode="json"),
                            reason=_safe_error(error),
                        )
                    if status != CandidateStatus.REJECTED:
                        break
                if status == CandidateStatus.ACTION_REQUIRED:
                    any_action_required = True
                elif status in (CandidateStatus.VALIDATED, CandidateStatus.PUBLISHED):
                    validated_count += 1
            final = (
                RunStatus.ACTION_REQUIRED
                if any_action_required
                else RunStatus.AWAITING_REVIEW
                if mode == RunMode.REVIEW
                else RunStatus.COMPLETE
            )
            self.store.update_run(run_id, final)
        except Exception as error:
            message = _safe_error(error)
            self.store.update_run(run_id, RunStatus.FAILED, message)
            raise AuthoringRunError(run_id, message) from None
        return run_id

    @staticmethod
    def _extract_capsule(synthesizer: CleanRoomSynthesizer, fix: HistoricalFix) -> BehaviorCapsule | None:
        """Extract one de-identified capsule, retrying leaks; None when impossible."""
        feedback: tuple[str, ...] = ()
        for _attempt in range(3):
            try:
                capsule = synthesizer.extract(fix, feedback=feedback)
            except ValueError:
                # The extractor invented a different capsule or game identity.
                feedback = (
                    "Return exactly the required_capsule_id and game_id given "
                    "in the payload; do not invent different identifiers.",
                )
                continue
            try:
                validate_public_candidate(
                    (fix,),
                    (
                        *capsule.observed_symptoms,
                        *capsule.expected_behaviors,
                        *capsule.compatibility_constraints,
                        *capsule.test_oracles,
                    ),
                    capsule.public_game_apis,
                )
            except LeakageError:
                # Generic remediation only; the leaked terms are never repeated.
                feedback = (
                    "The previous capsule quoted identity terms from the source "
                    "material. Restate observable behavior with fully neutral "
                    "wording: no project or mod names, file paths, authors, "
                    "URLs, issue numbers, or other source identifiers.",
                )
                continue
            return capsule
        return None

    def _gated_review_note(
        self, candidate: CompositeCandidate, selected_fixes: tuple[HistoricalFix, ...]
    ) -> tuple[str, ...]:
        """The previous attempt's review rationale, if it is safe to share.

        The reviewer sees the private sources, so its words cross the
        clean-room barrier only after passing the same leakage gate as any
        public text; a rationale that trips the gate is withheld entirely.
        """
        note = self._review_notes.get(candidate.id)
        if not note:
            return ()
        try:
            validate_public_candidate(
                selected_fixes,
                (note,),
                (api for capsule in candidate.capsules for api in capsule.public_game_apis),
            )
        except LeakageError:
            return ()
        return ("An independent reviewer rejected the previous attempt at this task: " + note,)

    def _author_candidate(
        self,
        run_id: str,
        run_root: Path,
        mode: RunMode,
        synthesizer: CleanRoomSynthesizer,
        candidate: CompositeCandidate,
        selected_fixes: tuple[HistoricalFix, ...],
        checkpoints: Path,
        prior_review: tuple[str, ...] = (),
    ) -> CandidateStatus:
        """Generate, gate, review, and engine-validate one composite candidate."""
        spec = game_spec(candidate.game_id)
        required_files = (*spec.project_requirements, *spec.interface_requirements)
        interface_feedback: tuple[str, ...] = ()
        for interface_attempt in range(3):
            interface_contract = synthesizer.design_interface(
                candidate,
                (
                    *spec.generation_contract,
                    f"Required project-relative files: {', '.join(required_files)}.",
                    "Keep independently defective behaviors in separate implementation files "
                    "so their single-defect controls do not overlap file paths.",
                ),
                feedback=interface_feedback,
            )
            _checkpoint(checkpoints, "interface", interface_contract)
            if not set(required_files) <= set(interface_contract.project_files):
                raise RuntimeError("shared interface omitted required game project files")
            # Project paths are relative to the starter root; a leading starter
            # directory is only legitimate where the game requires it (gmod).
            starter_prefix = f"{spec.starter_directory}/"
            if not any(path.startswith(starter_prefix) for path in required_files) and any(
                path.startswith(starter_prefix) for path in interface_contract.project_files
            ):
                raise RuntimeError("shared interface paths must be relative to the mod root")
            try:
                validate_public_candidate(
                    selected_fixes,
                    (interface_contract.model_dump_json(),),
                    (api for capsule in candidate.capsules for api in capsule.public_game_apis),
                )
            except LeakageError:
                if interface_attempt == 2:
                    raise
                # Generic remediation only; the leaked terms are never repeated.
                interface_feedback = (
                    "The previous contract used identifier or file names taken "
                    "from the private source material. Invent fresh neutral "
                    "names for every module, file, entrypoint and concept; do "
                    "not reuse source class or file names even when they "
                    "describe the behavior naturally.",
                )
                continue
            break
        fixed_contract, verifier_contract = _stage_contracts(spec)
        fixed = synthesizer.generate_fixed(
            candidate, interface_contract, fixed_contract, feedback=prior_review
        )
        _checkpoint(checkpoints, "fixed", fixed)
        verifier = synthesizer.generate_verifier(
            candidate, interface_contract, verifier_contract, feedback=prior_review
        )
        _checkpoint(checkpoints, "verifier", verifier)
        base = synthesizer.inject_defects(candidate, fixed, interface_contract, verifier, prior_review)
        _checkpoint(checkpoints, "base", base)
        prompt = synthesizer.author_prompt(candidate, interface_contract)
        _checkpoint(checkpoints, "prompt", prompt)

        candidate_root = run_root / "candidates" / candidate.id
        review_approved = False
        validation: ValidationReport | None = None
        repair_rounds_used = 0
        last_plan = None
        for repair_round in range(self.engine_repair_rounds + 1):
            suffix = f"-repair{repair_round}" if repair_round else ""
            # Leakage gates and the independent review re-run on every
            # repair round; a repaired candidate never skips them.
            validate_defect_paths(
                (path for defect in base.defects for path in defect.affected_files),
                base.files,
            )
            validate_public_candidate(
                selected_fixes,
                (
                    prompt.markdown,
                    *fixed.files.values(),
                    *base.files.values(),
                    *verifier.files.values(),
                ),
                (api for capsule in candidate.capsules for api in capsule.public_game_apis),
            )
            review = synthesizer.review(
                selected_fixes,
                candidate,
                fixed,
                base,
                verifier,
                prompt,
                interface_contract,
            )
            _checkpoint(checkpoints, f"review{suffix}", review)
            review_approved = bool(review.approved)
            if not review_approved:
                self._review_notes[candidate.id] = review.rationale
                break
            bundle = SynthesisBundle(
                candidate=candidate,
                fixed=fixed,
                base=base,
                verifier=verifier,
                prompt=prompt,
                review=review,
                provenance=selected_fixes,
                interface_contract=interface_contract,
            )
            if candidate_root.exists():
                shutil.rmtree(candidate_root)
            candidate_root = materialize_bundle(run_root, bundle)
            self.store.put_candidate(
                run_id,
                candidate.id,
                candidate.game_id,
                CandidateStatus.GENERATED,
                {"artifact": candidate_root.relative_to(run_root).as_posix()},
            )
            self.store.update_run(run_id, RunStatus.VALIDATING)
            validation = self.validator.validate(run_root, bundle)
            write_validation(candidate_root, validation)
            _checkpoint(checkpoints, f"validation{suffix}", validation)
            if validation.passed:
                break
            plan = plan_engine_repair(bundle, validation, last_plan)
            if plan is None or repair_round >= self.engine_repair_rounds:
                break
            last_plan = plan
            repair_rounds_used += 1
            fixed, verifier, base = _apply_engine_repair(
                synthesizer,
                candidate,
                interface_contract,
                fixed,
                verifier,
                base,
                plan,
                checkpoints,
                f"-repair{repair_round + 1}",
            )
        if not review_approved:
            self.store.put_candidate(
                run_id,
                candidate.id,
                candidate.game_id,
                CandidateStatus.REJECTED,
                candidate.model_dump(mode="json"),
                reason="independent clean-room review rejected the candidate",
            )
            return CandidateStatus.REJECTED
        assert validation is not None
        if not validation.passed:
            action_required = any(check.status == "unavailable" for check in validation.checks)
            reason = "candidate did not complete two-way real-engine validation"
            if repair_rounds_used:
                reason += f" after {repair_rounds_used} engine repair round(s)"
            self.store.put_candidate(
                run_id,
                candidate.id,
                candidate.game_id,
                CandidateStatus.ACTION_REQUIRED if action_required else CandidateStatus.REJECTED,
                {"artifact": candidate_root.relative_to(run_root).as_posix()},
                reason=reason,
            )
            return CandidateStatus.ACTION_REQUIRED if action_required else CandidateStatus.REJECTED
        self.store.put_candidate(
            run_id,
            candidate.id,
            candidate.game_id,
            CandidateStatus.VALIDATED,
            {"artifact": candidate_root.relative_to(run_root).as_posix()},
        )
        if mode == RunMode.YOLO:
            self.store.update_run(run_id, RunStatus.PUBLISHING)
            publication = self.publisher.publish(bundle, validation)
            self.store.put_candidate(
                run_id,
                candidate.id,
                candidate.game_id,
                CandidateStatus.PUBLISHED,
                publication.model_dump(mode="json"),
            )
            return CandidateStatus.PUBLISHED
        return CandidateStatus.VALIDATED

    def resume(self, run_id: str) -> None:
        run = self.store.run(run_id)
        if run["status"] != RunStatus.ACTION_REQUIRED.value:
            raise ValueError("only an action-required run can be resumed")
        run_root = self.project_root / ".rhenium" / "authoring" / "runs" / run_id
        mode = RunMode(str(run["mode"]))
        self.store.update_run(run_id, RunStatus.VALIDATING)
        try:
            self._resume_candidates(run_id, run_root, mode)
        except Exception as error:
            message = _safe_error(error)
            # Keep the run resumable: validation still requires operator action.
            self.store.update_run(run_id, RunStatus.ACTION_REQUIRED, message)
            raise AuthoringRunError(run_id, message) from None

    def _resume_candidates(self, run_id: str, run_root: Path, mode: RunMode) -> None:
        still_waiting = False
        for candidate in self.store.candidates(run_id):
            if candidate["status"] != CandidateStatus.ACTION_REQUIRED.value:
                continue
            candidate_root = run_root / "candidates" / str(candidate["id"])
            bundle = SynthesisBundle.model_validate_json(
                (candidate_root / "private" / "bundle.json").read_text(encoding="utf-8")
            )
            checkpoints = run_root / "checkpoints" / bundle.candidate.id
            repair_rounds_used = 0
            review_rejected = False
            last_plan = None
            for repair_round in range(self.engine_repair_rounds + 1):
                validation = self.validator.validate(run_root, bundle)
                write_validation(candidate_root, validation)
                _checkpoint(checkpoints, f"validation-resume{repair_round}", validation)
                if validation.passed:
                    break
                # Engine-feedback repair works on resume only when the model
                # service is configured and the stored bundle carries a
                # current-schema interface contract; otherwise resume just
                # re-validates.
                if (
                    self.synthesizer is None
                    or not isinstance(bundle.interface_contract, SynthInterfaceContract)
                    or repair_round >= self.engine_repair_rounds
                ):
                    break
                plan = plan_engine_repair(bundle, validation, last_plan)
                if plan is None:
                    break
                last_plan = plan
                repair_rounds_used += 1
                suffix = f"-resume-repair{repair_rounds_used}"
                try:
                    fixed, verifier, base = _apply_engine_repair(
                        self.synthesizer,
                        bundle.candidate,
                        bundle.interface_contract,
                        bundle.fixed,
                        bundle.verifier,
                        bundle.base,
                        plan,
                        checkpoints,
                        suffix,
                    )
                except (ValueError, RuntimeError):
                    # A repair generation that cannot satisfy the clean-room
                    # guards abandons the repair; the engine verdict stands.
                    break
                # A repaired candidate never skips the leakage gates or the
                # independent review.
                validate_defect_paths(
                    (path for defect in base.defects for path in defect.affected_files),
                    base.files,
                )
                validate_public_candidate(
                    bundle.provenance,
                    (
                        bundle.prompt.markdown,
                        *fixed.files.values(),
                        *base.files.values(),
                        *verifier.files.values(),
                    ),
                    (api for capsule in bundle.candidate.capsules for api in capsule.public_game_apis),
                )
                review = self.synthesizer.review(
                    bundle.provenance,
                    bundle.candidate,
                    fixed,
                    base,
                    verifier,
                    bundle.prompt,
                    bundle.interface_contract,
                )
                _checkpoint(checkpoints, f"review{suffix}", review)
                if not review.approved:
                    review_rejected = True
                    break
                bundle = SynthesisBundle(
                    candidate=bundle.candidate,
                    fixed=fixed,
                    base=base,
                    verifier=verifier,
                    prompt=bundle.prompt,
                    review=review,
                    provenance=bundle.provenance,
                    interface_contract=bundle.interface_contract,
                )
                if candidate_root.exists():
                    shutil.rmtree(candidate_root)
                candidate_root = materialize_bundle(run_root, bundle)
            if review_rejected:
                self.store.put_candidate(
                    run_id,
                    bundle.candidate.id,
                    bundle.candidate.game_id,
                    CandidateStatus.REJECTED,
                    {"artifact": candidate_root.relative_to(run_root).as_posix()},
                    reason="independent clean-room review rejected the engine-repaired candidate",
                )
                continue
            if not validation.passed:
                unavailable = any(check.status == "unavailable" for check in validation.checks)
                still_waiting = still_waiting or unavailable
                reason = "candidate did not complete two-way real-engine validation"
                if repair_rounds_used:
                    reason += f" after {repair_rounds_used} engine repair round(s)"
                self.store.put_candidate(
                    run_id,
                    bundle.candidate.id,
                    bundle.candidate.game_id,
                    CandidateStatus.ACTION_REQUIRED if unavailable else CandidateStatus.REJECTED,
                    {"artifact": candidate_root.relative_to(run_root).as_posix()},
                    reason=reason,
                )
                continue
            self.store.put_candidate(
                run_id,
                bundle.candidate.id,
                bundle.candidate.game_id,
                CandidateStatus.VALIDATED,
                {"artifact": candidate_root.relative_to(run_root).as_posix()},
            )
            if mode == RunMode.YOLO:
                self.store.update_run(run_id, RunStatus.PUBLISHING)
                publication = self.publisher.publish(bundle, validation)
                self.store.put_candidate(
                    run_id,
                    bundle.candidate.id,
                    bundle.candidate.game_id,
                    CandidateStatus.PUBLISHED,
                    publication.model_dump(mode="json"),
                )
        final = (
            RunStatus.ACTION_REQUIRED
            if still_waiting
            else RunStatus.AWAITING_REVIEW
            if mode == RunMode.REVIEW
            else RunStatus.COMPLETE
        )
        self.store.update_run(run_id, final)

    def _harvest(
        self,
        source_names: Sequence[str],
        game_ids: Sequence[str],
        limit: int,
        excluded_fix_keys: frozenset[str] = frozenset(),
        per_repository: int | None = None,
    ) -> list[HistoricalFix]:
        projects: dict[tuple[str, str], SourceProject] = {}
        if self.github is None:
            raise RuntimeError("GitHub historical-fix source is unavailable")
        github = self.github
        for game_id in game_ids:
            for source_name in source_names:
                for project in self.sources[source_name].discover(game_id, limit):
                    source_url = str(project.source_url or "")
                    if not source_url:
                        continue
                    try:
                        repository = github.repository_name(source_url)
                    except ValueError:
                        continue
                    projects[(game_id, repository.casefold())] = project
        fixes: list[HistoricalFix] = []
        failures = 0
        # Quotas are per game: a shared cap let one prolific game exhaust the
        # budget before later games' repositories were ever visited.
        harvested = {game_id: 0 for game_id in game_ids}
        for project in projects.values():
            room = limit - harvested.get(project.game_id, 0)
            if room <= 0:
                continue
            try:
                found = github.historical_fixes(project, limit)
            except RuntimeError:
                # One repository's API failure must not end the harvest;
                # a run with no material still fails closed downstream.
                failures += 1
                continue
            # Fixes that an earlier run already turned into candidates are
            # skipped so consecutive runs draw fresh material.
            fresh = [fix for fix in found if fix_key(fix) not in excluded_fix_keys]
            # One prolific repository would otherwise dominate the harvest and
            # every composite candidate built from it.
            accepted = fresh[: min(room, per_repository) if per_repository else room]
            fixes.extend(accepted)
            harvested[project.game_id] = harvested.get(project.game_id, 0) + len(accepted)
        if not fixes and failures and failures >= len(projects):
            raise RuntimeError("every harvest source request failed")
        if not fixes:
            raise RuntimeError("no fresh historical fixes were harvested from the selected sources")
        return fixes


def fix_key(fix: HistoricalFix) -> str:
    """Identity of one historical fix across runs: repository and fixed commit."""
    return f"{str(fix.repository_url).rstrip('/').casefold()}@{fix.fixed_sha.casefold()}"


def used_fix_keys(project_root: Path) -> frozenset[str]:
    """Keys of every fix that an earlier authoring run persisted as its input."""
    keys: set[str] = set()
    runs = project_root / ".rhenium" / "authoring" / "runs"
    if not runs.is_dir():
        return frozenset()
    # Project-history runs record their fixes in history-fixes.json with the same keys.
    records = [*runs.glob("*/historical-fixes.json"), *runs.glob("*/history-fixes.json")]
    for record in sorted(records):
        try:
            payload = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for raw in payload:
            if (
                isinstance(raw, dict)
                and isinstance(raw.get("repository_url"), str)
                and isinstance(raw.get("fixed_sha"), str)
            ):
                keys.add(f"{raw['repository_url'].rstrip('/').casefold()}@{raw['fixed_sha'].casefold()}")
    return frozenset(keys)


def _shrunk_contract(verifier: VerifierBundle, drop_cases: tuple[str, ...]) -> VerifierBundle:
    """The frozen case contract minus engine-proven unfailable cases."""
    dropped = set(drop_cases)
    return VerifierBundle(
        files=verifier.files,
        case_ids=tuple(case for case in verifier.case_ids if case not in dropped),
        capsule_cases={
            capsule_id: tuple(case for case in cases if case not in dropped)
            for capsule_id, cases in verifier.capsule_cases.items()
        },
    )


def _stage_contracts(spec: GameAuthoringSpec) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The fixed-implementer and verifier generation contracts for one game."""
    required_files = (*spec.project_requirements, *spec.interface_requirements)
    fixed_contract = (
        *spec.generation_contract,
        f"Required project-relative files: {', '.join(required_files)}.",
    )
    verifier_contract = (
        *spec.generation_contract,
        *spec.verifier_contract,
        "Verifier file paths are relative to the private task root.",
        f"Required model-authored verifier files: {', '.join(spec.generated_verifier_requirements)}.",
        "The materialized shell verifier must declare its exact expected case count.",
    )
    return fixed_contract, verifier_contract


def _apply_engine_repair(
    synthesizer: CleanRoomSynthesizer,
    candidate: CompositeCandidate,
    interface_contract: SynthInterfaceContract,
    fixed: GeneratedProject,
    verifier: VerifierBundle,
    base: DefectiveProject,
    plan: EngineRepairPlan,
    checkpoints: Path,
    suffix: str,
) -> tuple[GeneratedProject, VerifierBundle, DefectiveProject]:
    """Regenerate the role that owns a failed engine control and checkpoint it."""
    fixed_contract, verifier_contract = _stage_contracts(game_spec(candidate.game_id))
    if plan.target == "fixed":
        fixed = synthesizer.generate_fixed(
            candidate,
            interface_contract,
            fixed_contract,
            feedback=plan.findings,
        )
        _checkpoint(checkpoints, f"fixed{suffix}", fixed)
        # A changed implementation invalidates the injected defects, so they
        # are regenerated from the new fixed project.
        base = synthesizer.inject_defects(candidate, fixed, interface_contract, verifier)
        _checkpoint(checkpoints, f"base{suffix}", base)
    elif plan.target == "verifier":
        contract = _shrunk_contract(verifier, plan.drop_cases) if plan.drop_cases else verifier
        verifier = synthesizer.generate_verifier(
            candidate,
            interface_contract,
            verifier_contract,
            feedback=plan.findings,
            case_contract=contract,
        )
        _checkpoint(checkpoints, f"verifier{suffix}", verifier)
    else:
        base = synthesizer.inject_defects(
            candidate,
            fixed,
            interface_contract,
            verifier,
            plan.findings,
        )
        _checkpoint(checkpoints, f"base{suffix}", base)
    return fixed, verifier, base


def _checkpoint(root: Path, stage: str, output: BaseModel) -> None:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.parent.chmod(0o700)
    root.chmod(0o700)
    path = root / f"{stage}.json"
    path.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _safe_error(error: Exception) -> str:
    if isinstance(error, (RuntimeError, LeakageError)) or type(error) is ValueError:
        return str(error)[:500]
    return "authoring pipeline failed; inspect the private run diagnostics"


class AuthoringRunError(RuntimeError):
    def __init__(self, run_id: str, message: str):
        self.run_id = run_id
        self.message = message
        super().__init__(f"authoring run {run_id} failed: {message}")
