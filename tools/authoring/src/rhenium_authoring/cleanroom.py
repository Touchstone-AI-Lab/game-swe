from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Sequence

from .game_adapters import GameAuthoringSpec, game_spec
from .gmod_runner import render_test_script as _render_gmod_runner
from .minecraft_runner import render_test_script as _render_minecraft_runner
from .model_client import ModelClient
from .models import (
    AuthoredPrompt,
    BehaviorCapsule,
    CompositeCandidate,
    DefectInjections,
    DefectiveProject,
    DefectReport,
    GeneratedProject,
    HistoricalFix,
    ReviewDecision,
    SynthInterfaceContract,
    VerifierBundle,
)
from .stardew_runner import render_test_script as _render_stardew_runner
from .verifier_checks import VerifierScriptError, validate_verifier_scripts

# Games whose shell runner the operator renders from the structured case IDs;
# the model authors only the behavioral suite named by the game spec.
_TRUSTED_RUNNERS: dict[str, Callable[[tuple[str, ...]], str]] = {
    "stardew-valley": _render_stardew_runner,
    "garrys-mod": _render_gmod_runner,
    "minecraft": _render_minecraft_runner,
}
_GENERIC_GET_API = re.compile(r"\bGetApi\s*<\s*(?:object|System\.Object)\s*>")
_GCB_CASE = re.compile(r'@GcbCase\s*\(\s*(?:value\s*=\s*)?"([^"\\]*)"')
_GCB_SUITE_CLASS = re.compile(
    r"\bpublic\s+(?:final\s+)?class\s+TaskSuite\b[^{]*\bimplements\b[^{]*\bGcbSuite\b"
)


class CleanRoomSynthesizer:
    def __init__(
        self, client: ModelClient, reviewer: ModelClient | None = None,
        *, verifier_check: Callable[[VerifierBundle], Sequence[str]] | None = None,
        project_check: Callable[[dict[str, str]], Sequence[str]] | None = None,
        stage_attempts: int = 3,
    ):
        if stage_attempts < 1 or stage_attempts > 5:
            raise ValueError("stage attempts must be between 1 and 5")
        self.client = client
        self.reviewer = reviewer if reviewer is not None else client
        self.verifier_check = verifier_check
        self.project_check = project_check
        self.stage_attempts = stage_attempts

    def extract(self, fix: HistoricalFix, *, feedback: Sequence[str] = ()) -> BehaviorCapsule:
        digest = hashlib.sha256(f"{fix.game_id}\0{fix.base_sha}\0{fix.fixed_sha}".encode()).hexdigest()[:16]
        capsule_id = f"behavior-{digest}"
        payload: dict[str, object] = {
                "required_capsule_id": capsule_id,
                "game_id": fix.game_id,
                "issue_report": fix.issue_text,
                "historical_patch": fix.patch,
                "base_changed_files": fix.base_files,
                "fixed_changed_files": fix.fixed_files,
                "instructions": [
                    "Extract observable behavior, not implementation expression.",
                    "Do not quote code, paths, project names, people, URLs, issue IDs, or commit IDs.",
                    "Name only public game APIs required to express or verify behavior.",
                    "Every test oracle must follow from the issue or patch behavior.",
                    "State numerical bounds only when supported by source behavior. Distinguish "
                    "the observed boundary fix from claims of arbitrary integer support; omit "
                    "unknown input domains rather than inventing ranges, clamps or maximum values.",
                ],
            }
        if feedback:
            payload["validation_feedback"] = list(feedback)
        capsule = self.client.complete(
            BehaviorCapsule, role="behavior fact extractor", payload=payload,
        )
        if capsule.capsule_id != capsule_id or capsule.game_id != fix.game_id:
            raise ValueError("fact extractor changed the required clean-room identity")
        return capsule

    @staticmethod
    def compose(
        capsules: Sequence[BehaviorCapsule], max_capsules: int = 7
    ) -> list[CompositeCandidate]:
        if max_capsules < 2 or max_capsules > 7:
            raise ValueError("composite size must be between 2 and 7 capsules")
        by_game: dict[str, list[BehaviorCapsule]] = {}
        for capsule in capsules:
            by_game.setdefault(capsule.game_id, []).append(capsule)
        composites: list[CompositeCandidate] = []
        for game_id, values in sorted(by_game.items()):
            ordered = sorted(values, key=lambda value: value.capsule_id)
            offset = 0
            while len(ordered) - offset >= 2:
                remaining = len(ordered) - offset
                size = min(max_capsules, remaining)
                if remaining - size == 1:
                    size -= 1
                group = ordered[offset : offset + size]
                offset += size
                digest = hashlib.sha256("\0".join(item.capsule_id for item in group).encode()).hexdigest()[
                    :16
                ]
                composites.append(
                    CompositeCandidate(id=f"synthetic-{digest}", game_id=game_id, capsules=tuple(group))
                )
        return composites

    def design_interface(
        self,
        candidate: CompositeCandidate,
        game_contract: Sequence[str] = (),
        *,
        feedback: Sequence[str] = (),
    ) -> SynthInterfaceContract:
        payload: dict[str, object] = {
                "candidate": _barrier_payload(candidate),
                "instructions": [
                    "Design a small public loading and behavior contract; do not write implementation code. "
                    "Exact declarative metadata such as a JSON loader manifest belongs in metadata_files.",
                    "Choose neutral project names, required files and exact module/load identifiers.",
                    "Fix loader_identity and all serialized metadata_files now. Implementer and verifier "
                    "must use those exact values, including the loader's case-sensitive identifier.",
                    "For each public entrypoint give an exact callable signature or game event/RPC trigger, "
                    "typed inputs and observable outputs/state changes.",
                    "Specify an exact signature, return_type, return_schema and observation_channel. "
                    "The return schema must cover every returned field, scalar meaning or invariant string "
                    "format, so a verifier needs no guessed formatter, log text, Loaded flag or LastX field.",
                    "Map every capsule to the public entrypoints used to reproduce its behavior.",
                    "Every capsule needs an actual registered live game trigger or neutral console "
                    "command with specified arguments and observable output, not a hypothetical "
                    "menu lookup or a disconnected helper. Specify how ModEntry registers it.",
                    "Implementer and verifier will receive this same contract independently; "
                    "neither may invent a different API, module name or loading convention.",
                    "Use public gameplay behavior justified by the capsules, never hidden implementation "
                    "fields or algorithm details. Do not include source identities or repair hints.",
                    *game_contract,
                ],
            }
        if feedback:
            payload["validation_feedback"] = list(feedback)
        contract = self.client.complete(
            SynthInterfaceContract,
            role="clean-room public-interface designer",
            payload=payload,
        )
        if contract.game_id != candidate.game_id or set(contract.capsule_entrypoints) != {
            capsule.capsule_id for capsule in candidate.capsules
        }:
            raise ValueError("interface designer changed the required clean-room identity")
        return contract

    def generate_fixed(
        self,
        candidate: CompositeCandidate,
        interface_contract: SynthInterfaceContract,
        game_contract: Sequence[str] = (),
        *,
        feedback: Sequence[str] = (),
    ) -> GeneratedProject:
        payload: dict[str, object] = {
            "candidate": _barrier_payload(candidate),
            "interface_contract": interface_contract.model_dump(mode="json"),
            "license_policy": "Apache-2.0; the publisher supplies LICENSE separately",
            "instructions": [
                "Create a new, anonymous game mod from scratch.",
                "Implement every behavior using only the listed public game APIs.",
                "Do not imitate or mention any upstream project.",
                "Do not create a license file, copyright notice, URL, or source attribution.",
                "Use neutral invented names and include build/load metadata required by the game.",
                "Implement the shared interface contract exactly, including names, loading, inputs "
                "and observable outcomes; keep private implementation details behind that contract.",
                "Copy every metadata_files value byte-for-byte into its declared project file. "
                "Match loader_identity, entrypoint signatures and exact return schemas; do not "
                "substitute logs or undeclared fields for the promised public return values.",
                *game_contract,
            ],
        }
        if feedback:
            # Engine-repair findings: aggregated receipts only, never verifier
            # content or case IDs (the implementer must not see the verifier).
            payload["validation_feedback"] = list(feedback)
        last_error = "generated fixed project failed compiler checks after three attempts"
        for _attempt in range(self.stage_attempts):
            fixed = self.client.complete(
                GeneratedProject, role="clean-room fixed-project implementer", payload=payload,
            )
            findings: list[str] = []
            if fixed.project_name != interface_contract.project_name:
                findings.append("Keep the shared project name exactly as the interface contract declares")
                last_error = "fixed implementer changed the shared project name"
            if not set(interface_contract.project_files) <= set(fixed.files):
                findings.append("Return every shared interface project file; none may be omitted")
                last_error = "fixed implementer omitted shared interface project files"
            if any(
                fixed.files.get(path) != content
                for path, content in interface_contract.metadata_files.items()
            ):
                findings.append(
                    "Copy every metadata_files value byte-for-byte; the shared load "
                    "metadata is frozen and must not be edited"
                )
                last_error = "fixed implementer changed exact shared load metadata"
            static_findings = _project_static_findings(game_spec(candidate.game_id), fixed.files)
            if static_findings:
                findings.extend(static_findings)
                last_error = "fixed implementer violated the game's project layout or source rules"
            if not findings and self.project_check is not None:
                findings = list(self.project_check(fixed.files))
                if findings:
                    last_error = "generated fixed project failed compiler checks after three attempts"
            if not findings:
                return fixed
            self.client.on_event({"stage": "clean-room fixed-project implementer", "status": "repairing",
                                "findings": findings})
            payload["validation_feedback"] = findings
            payload["previous_project"] = fixed.model_dump(mode="json")
        raise ValueError(last_error)

    def generate_verifier(
        self,
        candidate: CompositeCandidate,
        interface_contract: SynthInterfaceContract,
        game_contract: Sequence[str] = (),
        *, feedback: Sequence[str] = (), case_contract: VerifierBundle | None = None,
    ) -> VerifierBundle:
        spec = game_spec(candidate.game_id)
        required_files = set(spec.verifier_requirements)
        model_files = set(spec.generated_verifier_requirements)
        payload: dict[str, object] = {
            "candidate": _barrier_payload(candidate),
            "interface_contract": interface_contract.model_dump(mode="json"),
            "instructions": [
                "Create deterministic real-engine behavioral assertions.",
                "capsule_cases maps only FAIL_TO_PASS cases: each listed case must fail when "
                "that capsule's defect is present and pass after it is repaired. Preserve "
                "PASS_TO_PASS cases (normal inputs, default zoom, other unaffected behavior) "
                "in case_ids but never in capsule_cases. Keep mappings disjoint.",
                "Use only public behavior; never assert an internal implementation detail.",
                "Use precisely the shared interface module identifiers, triggers and inputs. "
                "Do not assume any other exports or internal fields; the implementation is unseen.",
                "Include a sentinel proving the mod and verifier actually ran.",
                "Check module loading using the real game's or loader's public registry. "
                "Do not invent a Loaded property or other undeclared instrumentation on the "
                "submission, and never generate replacement submission files inside tests.",
                *(
                    (
                        "For Stardew use NON-GENERIC Helper.ModRegistry.GetApi(loader_identity) for "
                        "the raw API; inspect exactly the shared public signatures and return_schema. "
                        "Do not use GetApi<object>() (SMAPI requires an interface for generic "
                        "GetApi<T>). Do not replace return values with guessed log formats or "
                        "static fields.",
                    )
                    if candidate.game_id == "stardew-valley"
                    else ()
                ),
                "Return only the required verifier files listed below. Do not return project "
                "files, manifests, or implementation replacements alongside the suite.",
                "Shell scripts must pass Bash syntax and ShellCheck without suppression "
                "directives. Separate assignments and export statements so failures propagate.",
                *game_contract,
            ],
            "required_verifier_files": sorted(model_files),
        }
        expected = {capsule.capsule_id for capsule in candidate.capsules}
        if feedback:
            payload["validation_feedback"] = list(feedback)
        if case_contract is not None:
            payload["required_case_contract"] = {
                "case_ids": case_contract.case_ids, "capsule_cases": case_contract.capsule_cases,
                "policy": "Preserve these cases and regression mappings; do not weaken or drop assertions.",
            }
        for _attempt in range(self.stage_attempts):
            model_verifier = self.client.complete(
                VerifierBundle, role="independent behavioral verifier author", payload=payload
            )
            verifier = model_verifier
            findings: list[str] = []
            runner = _TRUSTED_RUNNERS.get(candidate.game_id)
            if runner is not None and spec.trusted_shell_runner is not None:
                if set(verifier.files) != model_files:
                    findings.append(
                        f"Return only {', '.join(sorted(model_files))}; "
                        "the operator supplies the shell runner"
                    )
                else:
                    findings.extend(_suite_static_findings(spec, verifier))
                    try:
                        rendered = runner(verifier.case_ids)
                    except ValueError as error:
                        findings.append(str(error))
                    else:
                        verifier = verifier.model_copy(update={"files": {
                            **verifier.files, spec.trusted_shell_runner: rendered,
                        }})
            if set(verifier.capsule_cases) != expected:
                findings.append("capsule_cases must cover every capsule exactly")
            if candidate.game_id != "isaac-rebirth" and set(verifier.files) != required_files:
                findings.append(
                    "Return exactly required_verifier_files; no replacement mod source or metadata"
                )
            if case_contract is not None and (
                verifier.case_ids != case_contract.case_ids
                or verifier.capsule_cases != case_contract.capsule_cases
            ):
                findings.append("Preserve required_case_contract case IDs/order and capsule_cases exactly")
            try:
                validate_verifier_scripts(verifier.files)
            except VerifierScriptError as error:
                findings.extend(error.findings)
            if not findings and self.verifier_check is not None:
                findings.extend(self.verifier_check(verifier))
            if not findings:
                return verifier
            self.client.on_event(
                {
                    "stage": "independent behavioral verifier author",
                    "status": "repairing",
                    "findings": findings,
                }
            )
            payload["validation_feedback"] = findings
            # This role can see its own prior output, never the independently
            # generated implementation or source-mod expression.
            payload["previous_verifier"] = model_verifier.model_dump(mode="json")
        raise ValueError("generated verifier failed boundary, shell or compiler checks after three attempts")

    def inject_defects(
        self,
        candidate: CompositeCandidate,
        fixed: GeneratedProject,
        interface_contract: SynthInterfaceContract,
        verifier: VerifierBundle | None = None,
        feedback: Sequence[str] = (),
    ) -> DefectiveProject:
        findings = list(feedback)
        spec = game_spec(candidate.game_id)
        for _attempt in range(self.stage_attempts):
            defective = self._inject_defects(candidate, fixed, interface_contract, verifier, findings)
            findings = []
            for label, files in [("combined-base", defective.files), *sorted(defective.ablations.items())]:
                findings.extend(
                    f"{label}: {value}" for value in _project_static_findings(spec, files)
                )
                if self.project_check is not None:
                    findings.extend(f"{label}: {value}" for value in self.project_check(files))
            if not findings:
                return defective
            self.client.on_event({"stage": "synthetic historical-defect injector", "status": "repairing",
                                "findings": findings})
        raise ValueError("generated defect controls failed compiler checks after three attempts")

    def _inject_defects(
        self, candidate: CompositeCandidate, fixed: GeneratedProject,
        interface_contract: SynthInterfaceContract, verifier: VerifierBundle | None,
        feedback: Sequence[str],
    ) -> DefectiveProject:
        injections = self.client.complete(
            DefectInjections,
            role="synthetic historical-defect injector",
            payload={
                "candidate": _barrier_payload(candidate),
                "fixed_project": fixed.model_dump(mode="json"),
                "interface_contract": interface_contract.model_dump(mode="json"),
                "reproduction_tests": verifier.model_dump(mode="json") if verifier is not None else None,
                "validation_feedback": list(feedback),
                "instructions": [
                    "Introduce exactly one independently observable defect per capsule.",
                    "Keep all unrelated behavior unchanged.",
                    "Preserve the shared public interface names, signatures and loading metadata; "
                    "inject behavioral defects, never missing exports or broken boot code.",
                    "For each capsule return only replacements: a mapping from existing implementation "
                    "file paths to complete replacement contents. Do not repeat unchanged files or "
                    "return full project trees. The orchestrator assembles base and ablations exactly.",
                    "Do not change any shared metadata file. Keep the replacements for different "
                    "capsules in separate implementation files.",
                    "Do not add comments or names that reveal a fix.",
                    "Use the declared defect symptoms only; do not inject unrelated failures or "
                    "change normal-input behavior that must remain PASS_TO_PASS.",
                    "Every capsule_cases regression must actually fail on the corresponding "
                    "single-defect version. Use the supplied reproduction tests to check that "
                    "the historical fault manifests (for example a too-small fallback reference "
                    "must be smaller than the test age). Do not copy test IDs, tests, or result "
                    "instrumentation into the implementation; preserve the general failure mechanism.",
                    "Runtime defects must still compile and boot. In particular, checked overflow "
                    "of a const expression is a compile error; use a runtime operand when modeling "
                    "an overflow, and keep it confined to the intended behavioral branch.",
                ],
            },
        )
        expected = {capsule.capsule_id for capsule in candidate.capsules}
        if {defect.capsule_id for defect in injections.injections} != expected:
            raise ValueError("defect injector did not implement every capsule exactly")
        base_files = dict(fixed.files)
        ablations: dict[str, dict[str, str]] = {}
        reports: list[DefectReport] = []
        affected: set[str] = set()
        for defect in injections.injections:
            paths = set(defect.replacements)
            if not paths <= set(fixed.files) or paths.intersection(interface_contract.metadata_files):
                raise ValueError("defect injector changed missing files or shared metadata")
            if any(value == fixed.files[path] for path, value in defect.replacements.items()):
                raise ValueError("defect injector returned unchanged replacement content")
            if affected.intersection(paths):
                raise ValueError("synthetic defects overlap the same generated file")
            affected.update(paths)
            base_files.update(defect.replacements)
            ablations[defect.capsule_id] = {**fixed.files, **defect.replacements}
            reports.append(
                DefectReport(
                    capsule_id=defect.capsule_id,
                    symptom=defect.symptom,
                    affected_files=tuple(sorted(paths)),
                )
            )
        return DefectiveProject(files=base_files, defects=tuple(reports), ablations=ablations)

    def author_prompt(
        self, candidate: CompositeCandidate, interface_contract: SynthInterfaceContract
    ) -> AuthoredPrompt:
        payload: dict[str, object] = {
            "game_id": candidate.game_id,
            "behaviors": [
                {
                    "observed_symptoms": capsule.observed_symptoms,
                    "expected_behaviors": capsule.expected_behaviors,
                }
                for capsule in candidate.capsules
            ],
            "interface_contract": interface_contract.model_dump(mode="json"),
            "instructions": [
                "Write a SWE-like debugging task using only user-observable symptoms.",
                "Do not reveal defect count, source identity, file locations, root causes, or fixes.",
                "Phrase reports as observations a player can reproduce. Do not describe internal "
                "guards, fallback branches, which API the current code calls, or diagnose what "
                "conversion step it ignores, even if those details occur in the supplied notes.",
                "Keep exact observable return formats from the public contract. Omit undefined "
                "input cases rather than inventing additional crash-safety or validation requirements.",
                "Describe reproduction using the shared public triggers and inputs when helpful; "
                "do not enumerate the internal module/file mapping or capsule IDs.",
                "State that existing working behavior must remain unchanged.",
                "State that private tests run in the pinned real game without network access.",
            ],
        }
        for _attempt in range(3):
            prompt = self.client.complete(AuthoredPrompt, role="symptom-only issue author", payload=payload)
            text = prompt.markdown.casefold()
            reveals_count = re.search(
                r"\b(?:one|two|three|four|five|six|seven|eight|nine|[0-9]+)\s+(?:bugs?|defects?)\b"
                r"|\bbug report\s+[0-9]+\b",
                text,
            )
            reveals_id = candidate.id.casefold() in text or candidate.id.rsplit("-", 1)[-1].casefold() in text
            if not reveals_count and not reveals_id:
                return prompt
            payload["validation_feedback"] = [
                "Remove explicit defect counts and numbered Bug report headings. "
                "Do not print the task/capsule ID or the private loader ID. "
                "Describe observed symptoms under descriptive headings without diagnosing causes."
            ]
        raise ValueError("prompt repeatedly disclosed defect counts or private identifiers")

    def review(
        self,
        fixes: Sequence[HistoricalFix],
        candidate: CompositeCandidate,
        fixed: GeneratedProject,
        defective: DefectiveProject,
        verifier: VerifierBundle,
        prompt: AuthoredPrompt,
        interface_contract: SynthInterfaceContract | None = None,
    ) -> ReviewDecision:
        return self.reviewer.complete(
            ReviewDecision,
            role="independent clean-room and contract reviewer",
            payload={
                "private_sources": [
                    {
                        "issue": fix.issue_text,
                        "patch": fix.patch,
                        "changed_files": fix.changed_files,
                        "base_changed_files": fix.base_files,
                        "fixed_changed_files": fix.fixed_files,
                    }
                    for fix in fixes
                ],
                "public_candidate": {
                    "contract": _barrier_payload(candidate),
                    "interface_contract": (
                        interface_contract.model_dump(mode="json") if interface_contract is not None else None
                    ),
                    "fixed": fixed.model_dump(mode="json"),
                    "base": defective.model_dump(mode="json"),
                    "verifier": verifier.model_dump(mode="json"),
                    "prompt": prompt.model_dump(mode="json"),
                },
                "trusted_game_context": list(game_spec(candidate.game_id).verifier_contract),
                "instructions": [
                    "Artifact roles: `fixed` is the clean-room reference implementation and is "
                    "the only tree that must satisfy the whole behavior contract. `base` is the "
                    "INTENTIONALLY defective starter handed to solvers: it must contain exactly "
                    "the declared defects (base.defects) and is expected to fail their mapped "
                    "cases, and base.ablations are the single-defect control trees. Never reject "
                    "because base or an ablation is defective; reject when fixed is wrong, when "
                    "a declared defect is missing or unrelated breakage was added, or when the "
                    "verifier cannot tell those trees apart.",
                    "Division of labor: after your review the real game engine runs the "
                    "complete two-way validation (fixed must pass every case, base and each "
                    "ablation must fail exactly their mapped cases) with an evidence-driven "
                    "repair loop, and a candidate that fails it is never published. Do not "
                    "reject for a suspected runtime outcome you cannot establish from the text "
                    "alone, such as whether a case really fails on an ablation, whether a "
                    "runtime-provided module resolves, or whether a fixture loads. Reject only "
                    "what the engine cannot catch or what is certain statically: leakage or "
                    "copied expression, assertions the behavior contract does not justify, "
                    "tests coupled to implementation internals, a fixed tree that plainly "
                    "contradicts the public contract, a missing declared defect, or unrelated "
                    "breakage. In particular, a disagreement between fixed and the verifier "
                    "about a runtime result (fixed would fail a case, a case would pass on its "
                    "ablation, a format or fixture mismatch between the two) is engine-decidable: "
                    "set approved to true and state the concern in the rationale, so the engine "
                    "run and its repair loop resolve it with real evidence.",
                    "Reject copied expression, identity leakage, or repair-location hints.",
                    "Reject every assertion not justified by the behavior contract.",
                    "Reject tests coupled to the generated implementation rather than real behavior.",
                    "Use trusted_game_context to check fixture setup and loader lifecycle timing. "
                    + _runner_division_note(game_spec(candidate.game_id)),
                    "Compare loader_identity and metadata_files with fixed/base manifest values. "
                    "Check every reflected method/property against the exact public interface and "
                    "actual fixed code; reject invented Loaded/LastOutput fields or observation formats.",
                    "capsule_cases contains FAIL_TO_PASS cases only: every listed case must fail "
                    "on that single-defect ablation and pass on fixed. Sentinels, ordinary-input "
                    "regressions and unaffected paths must stay out of those mappings and pass everywhere.",
                    "Evaluate boundary arithmetic directly, including fractional negative positions "
                    "when allowed: truncating intermediate world coordinates before floor can make "
                    "a claimed gold implementation wrong. Reject such contract violations even when "
                    "the generated tests omit them.",
                ],
            },
        )


def _runner_division_note(spec: GameAuthoringSpec) -> str:
    if spec.model_authored_verifier and spec.trusted_shell_runner is not None:
        return (
            f"The materialized verifier includes the operator-rendered {spec.trusted_shell_runner}; "
            f"the model-authored component is {', '.join(spec.model_authored_verifier)}."
        )
    return "Every verifier file is model-authored and runs under the trusted evaluator."


def _project_static_findings(spec: GameAuthoringSpec, files: dict[str, str]) -> list[str]:
    """Layout and source rules that need no compiler: stray roots and banned constructs."""
    findings: list[str] = []
    if spec.project_path_prefixes:
        stray = sorted(path for path in files if not path.startswith(spec.project_path_prefixes))
        if stray:
            findings.append(
                f"Keep every project file below {' or '.join(spec.project_path_prefixes)}; "
                f"remove or move: {', '.join(stray[:8])}"
            )
    findings.extend(_lint_sources(spec, files))
    return findings


def _lint_sources(spec: GameAuthoringSpec, files: dict[str, str]) -> list[str]:
    findings: list[str] = []
    for path, content in sorted(files.items()):
        for pattern, message in spec.source_lint:
            if re.search(pattern, content):
                findings.append(f"{path}: {message}")
    return findings


def _suite_static_findings(spec: GameAuthoringSpec, verifier: VerifierBundle) -> list[str]:
    """Static checks on the model-authored suite before the trusted runner is rendered."""
    findings: list[str] = []
    if spec.game_id == "stardew-valley" and _GENERIC_GET_API.search(
        verifier.files["tests/TaskSuite.cs"]
    ):
        findings.append("SMAPI rejects GetApi<object>(); use non-generic GetApi(id)")
    if spec.game_id == "minecraft":
        source = verifier.files["tests/TaskSuite.java"]
        if _GCB_SUITE_CLASS.search(source) is None:
            findings.append(
                "tests/TaskSuite.java must declare public class TaskSuite implements GcbSuite"
            )
        declared = Counter(_GCB_CASE.findall(source))
        expected = Counter(verifier.case_ids)
        missing = sorted(expected - declared)
        extra = sorted(declared - expected)
        if missing:
            findings.append(
                "Declare one @GcbCase(\"<case id>\") method for every case_ids entry; "
                f"missing: {', '.join(missing[:8])}"
            )
        if extra:
            findings.append(
                "Every @GcbCase name must appear exactly once and equal a case_ids entry; "
                f"undeclared or duplicated: {', '.join(extra[:8])}"
            )
    findings.extend(_lint_sources(spec, verifier.files))
    return findings


def _barrier_payload(candidate: CompositeCandidate) -> dict[str, object]:
    """The only source-derived data allowed across the clean-room barrier."""

    return json.loads(candidate.model_dump_json())
