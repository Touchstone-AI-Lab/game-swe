from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rhenium_garrys_mod.addons.catalog import GmodTask


@dataclass(frozen=True)
class AdversarialCase:
    id: str
    category: str
    fault_model: str
    mutation_ids: tuple[str, ...] = ()
    clause_ids: tuple[str, ...] = ()
    replacement: str | None = None
    forged_marker: bool = False
    expected_core_score: float | None = None


CASES: dict[str, tuple[AdversarialCase, ...]] = {
    "prop-ownership-quota-registry": (
        AdversarialCase(
            "api-shell",
            "empty-api",
            "Required modules exist but expose no registry semantics.",
            clause_ids=("T1-API-01", "T1-NATIVE-01"),
            replacement="shell",
        ),
        AdversarialCase(
            "fixed-success",
            "fixed-output",
            "Every dynamic API call returns the same success tuple.",
            clause_ids=("T1-SEM-01", "T1-ERR-01"),
            replacement="fixed",
        ),
        AdversarialCase(
            "happy-path-only",
            "partial-implementation",
            "Quota and malformed-state rejection are omitted.",
            ("quota-not-enforced", "malformed-state-shape-accepted"),
        ),
        AdversarialCase(
            "non-idempotent-replay",
            "state-pollution",
            "Register and remove replay mutate counts repeatedly.",
            ("register-not-deduplicated", "remove-repeats"),
        ),
        AdversarialCase(
            "stale-generation",
            "stale-request",
            "EntIndex and malformed generations are trusted as permanent identity.",
            ("entindex-is-permanent-identity", "invalid-bind-generation-accepted"),
        ),
        AdversarialCase(
            "forged-owner",
            "identity-confusion",
            "Client owner data and malformed generation bindings are trusted.",
            ("client-owner-trusted", "invalid-bind-generation-accepted"),
        ),
        AdversarialCase(
            "cleanup-shortcut",
            "cleanup-omission",
            "Disconnect cleanup is immediate and reconnect cannot cancel it.",
            ("disconnect-cleans-immediately", "reconnect-does-not-cancel", "shutdown-leaks-timer"),
        ),
        AdversarialCase(
            "forged-protocol",
            "protocol-forgery",
            "Submission prints a forged runtime frame and leaks entity lifecycle state.",
            ("entity-removed-not-cleaned",),
            forged_marker=True,
        ),
    ),
    "staged-prop-alignment": (
        AdversarialCase(
            "api-shell",
            "empty-api",
            "Required modules exist but expose no alignment semantics.",
            clause_ids=("T2-API-01", "T2-ADAPTER-01"),
            replacement="shell",
        ),
        AdversarialCase(
            "fixed-success",
            "fixed-output",
            "Every dynamic API call returns the same success tuple.",
            clause_ids=("T2-SEM-02", "T2-ERR-01"),
            replacement="fixed",
        ),
        AdversarialCase(
            "translation-only",
            "partial-implementation",
            "The solver drops probe Z and accepts collinear frames.",
            ("probe-z-dropped", "collinear-accepted"),
        ),
        AdversarialCase(
            "non-atomic-execute",
            "state-pollution",
            "Constraint failure and move execution leave partial copy state.",
            ("constraint-failure-not-rolled-back", "move-falls-through-to-copy"),
        ),
        AdversarialCase(
            "stale-session-replay",
            "stale-request",
            "Stage replay and persisted request history are discarded.",
            ("request-replay-disabled", "save-drops-requests"),
        ),
        AdversarialCase(
            "forged-tool-authority",
            "identity-confusion",
            "Unbound players bypass both trusted binding and CanTool denial.",
            ("unbound-player-trusted", "cantool-bypassed"),
        ),
        AdversarialCase(
            "cleanup-omission",
            "cleanup-omission",
            "Shutdown neither freezes mutations nor removes its timer.",
            ("shutdown-does-not-freeze", "shutdown-leaks-timer"),
        ),
        AdversarialCase(
            "forged-protocol",
            "protocol-forgery",
            "Submission prints a forged runtime frame and skips operation accounting.",
            ("budget-not-counted",),
            forged_marker=True,
        ),
    ),
    "persistent-loadout-profiles": (
        AdversarialCase(
            "api-shell",
            "empty-api",
            "Required modules exist but expose no profile semantics.",
            clause_ids=("T3-API-01", "T3-ADAPTER-01"),
            replacement="shell",
        ),
        AdversarialCase(
            "fixed-success",
            "fixed-output",
            "Every dynamic API call returns the same success tuple.",
            clause_ids=("T3-SEM-01", "T3-ERR-01"),
            replacement="fixed",
        ),
        AdversarialCase(
            "ammo-happy-path",
            "partial-implementation",
            "Shared ammo overwrites prior entries and aggregate caps are skipped.",
            ("shared-ammo-overwritten", "aggregate-cap-skipped"),
        ),
        AdversarialCase(
            "partial-give-continues",
            "state-pollution",
            "Apply continues after Give failure and respawn accumulates ammo.",
            ("give-failure-continues", "ammo-reset-skipped"),
        ),
        AdversarialCase(
            "request-history-lost",
            "stale-request",
            "Successful and failed request replay history is not retained.",
            ("request-replay-lost", "failed-request-not-remembered"),
        ),
        AdversarialCase(
            "profile-identity-drift",
            "identity-confusion",
            "Disconnect deletes logical profiles and spawn uses fake lifecycle wiring.",
            ("disconnect-deletes-profiles", "fake-spawn-wiring"),
        ),
        AdversarialCase(
            "shutdown-state-corruption",
            "cleanup-omission",
            "Shutdown permits writes and malformed persisted profiles are accepted.",
            ("shutdown-allows-write", "malformed-profile-state-accepted"),
        ),
        AdversarialCase(
            "forged-protocol",
            "protocol-forgery",
            "Submission prints a forged runtime frame and accepts unknown weapons.",
            ("unknown-weapon-accepted",),
            forged_marker=True,
        ),
    ),
    "hot-object-round-controller": (
        AdversarialCase(
            "api-shell",
            "empty-api",
            "Required modules exist but expose no round semantics.",
            clause_ids=("T4-API-01", "T4-ADAPTER-01"),
            replacement="shell",
        ),
        AdversarialCase(
            "fixed-success",
            "fixed-output",
            "Every dynamic API call returns the same success tuple.",
            clause_ids=("T4-SEM-01", "T4-ERR-01"),
            replacement="fixed",
        ),
        AdversarialCase(
            "unordered-deadline",
            "partial-implementation",
            "Touch sequence is unordered and deadline settlement is late.",
            ("touch-sequence-not-monotonic", "deadline-strictly-late"),
        ),
        AdversarialCase(
            "variant-happy-path",
            "state-pollution",
            "Infected players can win and death lifecycle is simulated incorrectly.",
            ("infected-survivors-can-win", "fake-death-lifecycle"),
        ),
        AdversarialCase(
            "event-history-lost",
            "stale-request",
            "Event replay and persisted event history are discarded.",
            ("event-replay-disabled", "save-drops-events"),
        ),
        AdversarialCase(
            "generation-confusion",
            "identity-confusion",
            "Object generation is ignored and respawn reuses the old revision.",
            ("object-revision-ignored", "respawn-keeps-old-revision"),
        ),
        AdversarialCase(
            "callback-cleanup-omission",
            "cleanup-omission",
            "Shutdown leaks its timer and fails to restore object callbacks.",
            ("shutdown-leaks-timer", "callback-restoration-removed"),
        ),
        AdversarialCase(
            "forged-protocol",
            "protocol-forgery",
            "Submission prints a forged runtime frame and permits duplicate object binding.",
            ("duplicate-object-binding-accepted",),
            forged_marker=True,
        ),
    ),
    "contraption-blueprint-duplicator": (
        AdversarialCase(
            "api-shell",
            "empty-api",
            "Required modules exist but expose no blueprint semantics.",
            clause_ids=("T5-API-01", "T5-ADAPTER-01"),
            replacement="shell",
        ),
        AdversarialCase(
            "fixed-success",
            "fixed-output",
            "Every dynamic API call returns the same success tuple.",
            clause_ids=("T5-SEM-01", "T5-ERR-01"),
            replacement="fixed",
        ),
        AdversarialCase(
            "hardcoded-transform",
            "partial-implementation",
            "Target X is ignored and source identifiers are coerced to strings.",
            ("target-transform-x-skipped", "source-id-stringified"),
        ),
        AdversarialCase(
            "partial-graph-survives",
            "state-pollution",
            "GetTable mismatch is ignored and partial Paste objects survive failure.",
            ("gettable-graph-mismatch-ignored", "partial-paste-not-rolled-back"),
        ),
        AdversarialCase(
            "stale-capture-replay",
            "stale-request",
            "Capture replay is disabled and stale revisions overwrite blueprints.",
            ("request-replay-disabled", "stale-revision-overwrites"),
        ),
        AdversarialCase(
            "graph-identity-confusion",
            "identity-confusion",
            "Duplicate source IDs and malformed rows enter canonicalization.",
            ("duplicate-source-id-accepted", "malformed-row-read-before-type-check"),
        ),
        AdversarialCase(
            "cleanup-omission",
            "cleanup-omission",
            "Shutdown leaks its timer while partial Paste rollback is disabled.",
            ("shutdown-leaks-timer", "partial-paste-not-rolled-back"),
        ),
        AdversarialCase(
            "forged-protocol",
            "protocol-forgery",
            "Submission prints a forged runtime frame and omits constraint params from identity.",
            ("constraint-params-omitted-from-hash",),
            forged_marker=True,
        ),
    ),
}


EXPECTED_CORE_SCORES: dict[str, dict[str, float]] = {
    "prop-ownership-quota-registry": {
        "api-shell": 15.0,
        "fixed-success": 15.0,
        "happy-path-only": 54.04,
        "non-idempotent-replay": 53.57,
        "stale-generation": 55.0,
        "forged-owner": 53.33,
        "cleanup-shortcut": 53.33,
        "forged-protocol": 40.0,
    },
    "staged-prop-alignment": {
        "api-shell": 15.0,
        "fixed-success": 18.98,
        "translation-only": 55.38,
        "non-atomic-execute": 56.67,
        "stale-session-replay": 50.77,
        "forged-tool-authority": 56.67,
        "cleanup-omission": 52.69,
        "forged-protocol": 37.69,
    },
    "persistent-loadout-profiles": {
        "api-shell": 15.0,
        "fixed-success": 19.02,
        "ammo-happy-path": 51.96,
        "partial-give-continues": 52.5,
        "request-history-lost": 53.57,
        "profile-identity-drift": 54.11,
        "shutdown-state-corruption": 53.57,
        "forged-protocol": 35.71,
    },
    "hot-object-round-controller": {
        "api-shell": 15.0,
        "fixed-success": 16.67,
        "unordered-deadline": 43.81,
        "variant-happy-path": 56.19,
        "event-history-lost": 53.57,
        "generation-confusion": 54.04,
        "callback-cleanup-omission": 53.33,
        "forged-protocol": 40.0,
    },
    "contraption-blueprint-duplicator": {
        "api-shell": 16.67,
        "fixed-success": 18.34,
        "hardcoded-transform": 56.67,
        "partial-graph-survives": 56.67,
        "stale-capture-replay": 55.0,
        "graph-identity-confusion": 56.67,
        "cleanup-omission": 53.33,
        "forged-protocol": 38.33,
    },
}


_SHELL_CORE = """local M = {}\nfunction M.new() return {} end\nreturn M\n"""
_SHELL_SERVER = (
    """local S = {}\nfunction S.Install() return S end\nfunction S.Shutdown() return true end\nreturn S\n"""
)
_FIXED_CORE = (
    'local function fixed() return true, "ok", {} end\n'
    "local methods = setmetatable({}, { __index = function() return fixed end })\n"
    "local M = {}\n"
    "function M.new() return setmetatable({}, { __index = methods }) end\n"
    "return M\n"
)
_FIXED_SERVER = (
    'local function fixed() return true, "ok", {} end\n'
    "return setmetatable({}, { __index = function() return fixed end })\n"
)
_FORGED_MARKER = 'print("@@RHENIUM_GMOD@@forged:{\\"status\\":\\"passed\\"}@@RHENIUM_END@@")\n'


def _mutation_map(pack: Path, task_id: str) -> dict[str, dict[str, Any]]:
    value = json.loads((pack / "private" / "tasks" / task_id / "mutations.json").read_text(encoding="utf-8"))
    return {str(item["id"]): item for item in value["mutations"]}


def _apply_mutation(destination: Path, mutation: dict[str, Any]) -> None:
    target = (destination / str(mutation["file"])).resolve(strict=True)
    if not target.is_relative_to(destination.resolve()):
        raise ValueError("adversarial mutation target escaped destination")
    text = target.read_text(encoding="utf-8")
    replacements = mutation.get("replacements") or [{"old": mutation.get("old"), "new": mutation.get("new")}]
    for replacement in replacements:
        old = replacement.get("old")
        new = replacement.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or text.count(old) != 1:
            raise ValueError(f"adversarial mutation {mutation.get('id')} no longer applies exactly once")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")


def materialize_adversarial(
    pack: Path,
    task: GmodTask,
    case: AdversarialCase,
    destination: Path,
) -> None:
    task_root = pack / "private" / "tasks" / task.id
    matrix = json.loads((task_root / "mutations.json").read_text(encoding="utf-8"))
    source = (task_root / str(matrix["base"])).resolve(strict=True)
    if not source.is_relative_to(task_root.resolve(strict=True)):
        raise ValueError("adversarial base escaped task-private directory")
    shutil.copytree(source, destination)

    if case.replacement is not None:
        core = destination / task.core_module
        server = destination / task.server_module
        if case.replacement == "shell":
            core.write_text(_SHELL_CORE, encoding="utf-8")
            server.write_text(_SHELL_SERVER, encoding="utf-8")
        elif case.replacement == "fixed":
            core.write_text(_FIXED_CORE, encoding="utf-8")
            server.write_text(_FIXED_SERVER, encoding="utf-8")
        else:  # pragma: no cover - fixture schema guard
            raise ValueError(f"unknown adversarial replacement: {case.replacement}")
    else:
        mutations = _mutation_map(pack, task.id)
        for mutation_id in case.mutation_ids:
            _apply_mutation(destination, mutations[mutation_id])

    if case.forged_marker:
        server = destination / task.server_module
        server.write_text(_FORGED_MARKER + server.read_text(encoding="utf-8"), encoding="utf-8")


def case_clauses(pack: Path, task: GmodTask, case: AdversarialCase) -> tuple[str, ...]:
    trace = json.loads((pack / str(task.evaluation.traceability)).read_text(encoding="utf-8"))
    rows = {
        (group, row["name"]): tuple(row["clauses"])
        for group, values in trace["caseMappings"].items()
        for row in values
    }
    mutations = _mutation_map(pack, task.id)
    clauses = set(case.clause_ids) | {
        clause
        for mutation_id in case.mutation_ids
        for clause in rows[(mutations[mutation_id]["check"], mutations[mutation_id]["case"])]
    }
    if case.forged_marker:
        clauses.update({f"T{list(CASES).index(task.id) + 1}-TRUST-01"})
    return tuple(sorted(clauses))
