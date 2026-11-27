from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from collections import Counter
from typing import Any

from .assertions import AssertionCase, AssertionManifest

# Public compatibility aliases for callers that construct legacy R4 protocol-v2
# evidence. Collection and validation below always bind to the loaded manifest.
ADAPTER = "rhenium-rimworld-observer-v2"
COLLECTOR = "rhenium-rimworld-supervisor-v2"
OBSERVATION_SCHEMA = 2
VERDICT_SCHEMA = 2

_EVALUATION_ID = re.compile(r"^evaluation-[0-9a-f]{24}$")
_NONCE = re.compile(r"^[0-9a-f]{48}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_ID = _SHA256
_EMPTY_SHA256 = f"sha256:{hashlib.sha256(b'').hexdigest()}"
_TASK_KEY = re.compile(
    r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$"
)

_OBSERVATION_FIELDS = {
    "schema",
    "adapter",
    "evaluationId",
    "nonce",
    "taskKey",
    "realGame",
    "gameVersion",
    "unityVersion",
    "terminalMarker",
    "fatal",
    "cases",
}
_OBSERVATION_CASE_FIELDS = {
    "id",
    "error",
    "facts",
    "scalars",
    "outputs",
}
_FACT_FIELDS = {"name", "value"}
_SCALAR_FIELDS = {"name", "value", "bits"}
_OUTPUT_FIELDS = {"channel", "entries"}
_MATERIAL_FIELDS = {"defName", "count"}
_VERDICT_CASE_FIELDS = {"id", "status", "message"}
_VERDICT_FIELDS = {
    "schema",
    "collector",
    "evaluationId",
    "nonce",
    "taskKey",
    "complete",
    "expected",
    "passed",
    "failed",
    "reward",
    "fatal",
    "engine",
    "identity",
    "cases",
}
_ENGINE_FIELDS = {
    "processStatus",
    "realGame",
    "gameVersion",
    "unityVersion",
    "terminalCount",
}
_IDENTITY_FIELDS = {
    "catalog",
    "rubric",
    "submission",
    "candidateAssembly",
    "adapterAssembly",
    "runtimeFingerprint",
    "runtimeArtifact",
    "builderImage",
    "evaluatorImage",
    "buildEvidence",
    "adapterEvidence",
    "sourceEvidence",
}
class EvidenceError(ValueError):
    """Private runtime evidence failed strict structural or identity validation."""


def _reject_constant(value: str) -> None:
    raise EvidenceError(f"non-finite JSON value is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_object(raw: bytes, *, maximum: int = 1_000_000) -> dict[str, Any]:
    if len(raw) > maximum:
        raise EvidenceError("JSON evidence exceeds the size limit")
    try:
        text = raw.decode("utf-8", errors="strict")
        loaded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError("JSON evidence is malformed") from error
    if not isinstance(loaded, dict):
        raise EvidenceError("JSON evidence must be an object")
    return loaded


def _exact_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise EvidenceError(f"{label} has missing or unknown fields")


def _plain_int(value: Any, label: str) -> int:
    if type(value) is not int:
        raise EvidenceError(f"{label} must be an integer")
    return value


def _plain_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise EvidenceError(f"{label} must be a boolean")
    return value


def _plain_number(value: Any, label: str) -> float:
    if type(value) not in {int, float}:
        raise EvidenceError(f"{label} must be a finite number")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise EvidenceError(f"{label} must be a finite number") from error
    if not math.isfinite(converted):
        raise EvidenceError(f"{label} must be a finite number")
    return converted


def _bounded_string(value: Any, label: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise EvidenceError(f"{label} must be a bounded non-empty string")
    return value


def _validate_identity(identity: dict[str, Any]) -> None:
    _exact_fields(identity, _IDENTITY_FIELDS, "evaluation identity")
    for field in _IDENTITY_FIELDS:
        value = _bounded_string(identity.get(field), f"identity.{field}", maximum=256)
        pattern = _IMAGE_ID if field in {"builderImage", "evaluatorImage"} else _SHA256
        if pattern.fullmatch(value) is None:
            raise EvidenceError(f"identity.{field} is malformed")


def _validated_observation_cases(
    value: Any, assertions: AssertionManifest
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise EvidenceError("observation cases must be an array")
    cases: list[dict[str, Any]] = []
    for raw_case in value:
        if not isinstance(raw_case, dict):
            raise EvidenceError("observation case entries must be objects")
        _exact_fields(raw_case, _OBSERVATION_CASE_FIELDS, "observation case")
        case_id = _bounded_string(raw_case.get("id"), "case.id", maximum=160)
        error = raw_case.get("error")
        if not isinstance(error, str) or len(error) > 4096:
            raise EvidenceError("case.error must be a bounded string")
        facts_raw = raw_case.get("facts")
        if not isinstance(facts_raw, list):
            raise EvidenceError("case.facts must be an array")
        facts: list[dict[str, str]] = []
        fact_names: set[str] = set()
        for raw_fact in facts_raw:
            if not isinstance(raw_fact, dict):
                raise EvidenceError("case fact entries must be objects")
            _exact_fields(raw_fact, _FACT_FIELDS, "case fact")
            name = _bounded_string(raw_fact.get("name"), "fact.name", maximum=80)
            fact_value = _bounded_string(
                raw_fact.get("value"), "fact.value", maximum=160
            )
            if name in fact_names:
                raise EvidenceError("case fact names must be unique")
            fact_names.add(name)
            facts.append({"name": name, "value": fact_value})
        scalars_raw = raw_case.get("scalars")
        if not isinstance(scalars_raw, list):
            raise EvidenceError("case.scalars must be an array")
        scalars: list[dict[str, Any]] = []
        scalar_names: set[str] = set()
        for raw_scalar in scalars_raw:
            if not isinstance(raw_scalar, dict):
                raise EvidenceError("case scalar entries must be objects")
            _exact_fields(raw_scalar, _SCALAR_FIELDS, "case scalar")
            name = _bounded_string(raw_scalar.get("name"), "scalar.name", maximum=80)
            scalar_value = _plain_number(raw_scalar.get("value"), "scalar.value")
            bits = _bounded_string(raw_scalar.get("bits"), "scalar.bits", maximum=8)
            try:
                packed = struct.pack("<f", scalar_value)
            except (OverflowError, struct.error) as error_value:
                raise EvidenceError(
                    "observation number is outside the float32 range"
                ) from error_value
            actual_bits = f"{struct.unpack('<I', packed)[0]:08x}"
            if re.fullmatch(r"[0-9a-f]{8}", bits) is None or bits != actual_bits:
                raise EvidenceError("scalar float32 bits do not match its value")
            if name in scalar_names:
                raise EvidenceError("case scalar names must be unique")
            scalar_names.add(name)
            scalars.append({"name": name, "value": scalar_value, "bits": bits})
        outputs_raw = raw_case.get("outputs")
        if not isinstance(outputs_raw, list):
            raise EvidenceError("case.outputs must be an array")
        outputs: list[dict[str, Any]] = []
        channels: set[str] = set()
        for raw_output in outputs_raw:
            if not isinstance(raw_output, dict):
                raise EvidenceError("case output entries must be objects")
            _exact_fields(raw_output, _OUTPUT_FIELDS, "case output")
            channel = _bounded_string(raw_output.get("channel"), "output.channel", maximum=40)
            if channel in channels:
                raise EvidenceError("case output channels must be unique")
            channels.add(channel)
            entries_raw = raw_output.get("entries")
            if not isinstance(entries_raw, list):
                raise EvidenceError("output.entries must be an array")
            entries: list[dict[str, Any]] = []
            material_names: set[str] = set()
            for raw_entry in entries_raw:
                if not isinstance(raw_entry, dict):
                    raise EvidenceError("material entries must be objects")
                _exact_fields(raw_entry, _MATERIAL_FIELDS, "material entry")
                def_name = _bounded_string(
                    raw_entry.get("defName"), "material.defName", maximum=160
                )
                if def_name in material_names:
                    raise EvidenceError("material entries must be unique")
                material_names.add(def_name)
                count = _plain_int(raw_entry.get("count"), "material.count")
                if count <= 0:
                    raise EvidenceError("material.count must be positive")
                entries.append({"defName": def_name, "count": count})
            outputs.append({"channel": channel, "entries": entries})
        assertion = assertions.by_id.get(case_id)
        if error:
            if facts or scalars or outputs:
                raise EvidenceError("errored cases must not contain observations")
        elif assertion is not None and scalar_names != set(assertion.scalars):
            raise EvidenceError("case scalar observations do not match the manifest")
        cases.append(
            {
                "id": case_id,
                "error": error,
                "facts": facts,
                "scalars": scalars,
                "outputs": outputs,
            }
        )
    return cases


def _validated_verdict_cases(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise EvidenceError("verdict cases must be an array")
    result: list[dict[str, str]] = []
    for raw_case in value:
        if not isinstance(raw_case, dict):
            raise EvidenceError("verdict case entries must be objects")
        _exact_fields(raw_case, _VERDICT_CASE_FIELDS, "verdict case")
        case_id = _bounded_string(raw_case.get("id"), "case.id", maximum=160)
        status = raw_case.get("status")
        if status not in {"passed", "failed"}:
            raise EvidenceError("case.status must be passed or failed")
        message = raw_case.get("message")
        if not isinstance(message, str) or len(message) > 4096:
            raise EvidenceError("case.message must be a bounded string")
        result.append({"id": case_id, "status": status, "message": message})
    return result


def _output_map(case: dict[str, Any]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for output in case["outputs"]:
        result[output["channel"]] = {
            entry["defName"]: entry["count"] for entry in output["entries"]
        }
    return result


def _fact_map(case: dict[str, Any]) -> dict[str, str]:
    return {fact["name"]: fact["value"] for fact in case["facts"]}


def _expected_output(assertion: AssertionCase) -> dict[str, dict[str, int]]:
    return {
        output.channel: {entry.def_name: entry.count for entry in output.entries}
        for output in assertion.expected.outputs
    }


def _expected_facts(assertion: AssertionCase) -> dict[str, str]:
    return {fact.name: fact.value for fact in assertion.expected.facts}


def rubric_hash(assertions: AssertionManifest) -> str:
    return assertions.rubric_hash()


def _case_matches(case: dict[str, Any], assertion: AssertionCase) -> bool:
    return (
        not case["error"]
        and _fact_map(case) == _expected_facts(assertion)
        and _output_map(case) == _expected_output(assertion)
    )


def _grade_case(case: dict[str, Any], assertion: AssertionCase) -> dict[str, str]:
    if case["error"]:
        return {
            "id": case["id"],
            "status": "failed",
            "message": "the candidate operation returned an error",
        }
    passed = _case_matches(case, assertion)
    return {
        "id": case["id"],
        "status": "passed" if passed else "failed",
        "message": (
            "observations matched the private contract"
            if passed
            else "observations did not match the private contract"
        ),
    }


def collect_observations(
    raw: bytes,
    *,
    assertions: AssertionManifest,
    evaluation_id: str,
    nonce: str,
    task_key: str,
    process_status: int,
    player_log: str,
    identity: dict[str, str],
) -> dict[str, Any]:
    if _EVALUATION_ID.fullmatch(evaluation_id) is None:
        raise EvidenceError("evaluation ID is malformed")
    if _NONCE.fullmatch(nonce) is None:
        raise EvidenceError("evaluation nonce is malformed")
    if _TASK_KEY.fullmatch(task_key) is None:
        raise EvidenceError("canonical task key is malformed")
    if assertions.task_key != task_key:
        raise EvidenceError("assertion manifest task identity does not match")
    _validate_identity(identity)
    if identity.get("rubric") != assertions.rubric_hash():
        raise EvidenceError("evaluation rubric identity does not match")
    expected_cases = assertions.case_names

    observation = strict_json_object(raw)
    _exact_fields(observation, _OBSERVATION_FIELDS, "observation")
    if (
        _plain_int(observation.get("schema"), "observation.schema")
        != assertions.schema_version
        or observation.get("adapter") != assertions.adapter
        or observation.get("evaluationId") != evaluation_id
        or observation.get("nonce") != nonce
        or observation.get("taskKey") != task_key
    ):
        raise EvidenceError("observation identity does not match the evaluation")
    real_game = _plain_bool(observation.get("realGame"), "observation.realGame")
    game_version = _bounded_string(
        observation.get("gameVersion"), "gameVersion", maximum=200
    )
    unity_version = _bounded_string(
        observation.get("unityVersion"), "unityVersion", maximum=100
    )
    terminal = _bounded_string(
        observation.get("terminalMarker"), "terminalMarker", maximum=200
    )
    expected_terminal = f"RIMWORLD_OBSERVATIONS_COMPLETE:{nonce}"
    fatal = observation.get("fatal")
    if not isinstance(fatal, str) or len(fatal) > 4096:
        raise EvidenceError("observation.fatal must be a bounded string")
    observed_cases = _validated_observation_cases(observation.get("cases"), assertions)
    observed_names = [case["id"] for case in observed_cases]
    terminal_count = player_log.count(f"[GCB_RIMWORLD] {expected_terminal}")
    valid_case_set = (
        Counter(observed_names) == Counter(expected_cases)
        and len(observed_cases) == len(expected_cases)
    )
    observed_by_id = {case["id"]: case for case in observed_cases}
    valid_gates = valid_case_set and all(
        _case_matches(observed_by_id[assertion.id], assertion)
        for assertion in assertions.cases
        if assertion.gate
    )
    complete = bool(
        process_status == 0
        and real_game
        and game_version.split()[0] == "1.6.4871"
        and unity_version == "2022.3.35f1"
        and terminal == expected_terminal
        and terminal_count == 1
        and not fatal
        and valid_case_set
        and valid_gates
    )
    cases = (
        [_grade_case(case, assertions.by_id[case["id"]]) for case in observed_cases]
        if complete
        else []
    )
    passed_count = sum(case["status"] == "passed" for case in cases)
    failed_count = sum(case["status"] == "failed" for case in cases)
    reward = int(complete and failed_count == 0 and passed_count == len(expected_cases))
    internal_fatal = None if complete else "INVALID_RUNTIME_EVIDENCE"
    return {
        "schema": assertions.schema_version,
        "collector": assertions.collector,
        "evaluationId": evaluation_id,
        "nonce": nonce,
        "taskKey": task_key,
        "complete": complete,
        "expected": len(expected_cases),
        "passed": passed_count,
        "failed": failed_count,
        "reward": reward,
        "fatal": internal_fatal,
        "engine": {
            "processStatus": process_status,
            "realGame": real_game,
            "gameVersion": game_version,
            "unityVersion": unity_version,
            "terminalCount": terminal_count,
        },
        "identity": dict(identity),
        "cases": cases,
    }


def incomplete_verdict(
    *,
    assertions: AssertionManifest,
    evaluation_id: str,
    nonce: str,
    task_key: str,
    fatal: str,
    identity: dict[str, str],
    process_status: int = -1,
) -> dict[str, Any]:
    _validate_identity(identity)
    if assertions.task_key != task_key:
        raise EvidenceError("assertion manifest task identity does not match")
    if identity.get("rubric") != assertions.rubric_hash():
        raise EvidenceError("evaluation rubric identity does not match")
    return {
        "schema": assertions.schema_version,
        "collector": assertions.collector,
        "evaluationId": evaluation_id,
        "nonce": nonce,
        "taskKey": task_key,
        "complete": False,
        "expected": len(assertions.cases),
        "passed": 0,
        "failed": 0,
        "reward": 0,
        "fatal": fatal,
        "engine": {
            "processStatus": process_status,
            "realGame": False,
            "gameVersion": "unavailable",
            "unityVersion": "unavailable",
            "terminalCount": 0,
        },
        "identity": dict(identity),
        "cases": [],
    }


def validate_private_verdict(
    raw: bytes, assertions: AssertionManifest
) -> dict[str, Any]:
    verdict = strict_json_object(raw)
    _exact_fields(verdict, _VERDICT_FIELDS, "verdict")
    if (
        _plain_int(verdict.get("schema"), "verdict.schema")
        != assertions.schema_version
        or verdict.get("collector") != assertions.collector
    ):
        raise EvidenceError("verdict schema or collector is invalid")
    evaluation_id = _bounded_string(
        verdict.get("evaluationId"), "evaluationId", maximum=64
    )
    nonce = _bounded_string(verdict.get("nonce"), "nonce", maximum=64)
    task_key = _bounded_string(verdict.get("taskKey"), "taskKey", maximum=255)
    if (
        _EVALUATION_ID.fullmatch(evaluation_id) is None
        or _NONCE.fullmatch(nonce) is None
        or _TASK_KEY.fullmatch(task_key) is None
        or task_key != assertions.task_key
    ):
        raise EvidenceError("verdict identity is malformed")
    complete = _plain_bool(verdict.get("complete"), "verdict.complete")
    expected = _plain_int(verdict.get("expected"), "verdict.expected")
    passed = _plain_int(verdict.get("passed"), "verdict.passed")
    failed = _plain_int(verdict.get("failed"), "verdict.failed")
    reward = _plain_int(verdict.get("reward"), "verdict.reward")
    if any(value < 0 or value > 10_000 for value in (expected, passed, failed)):
        raise EvidenceError("verdict counts are outside the permitted range")
    fatal = verdict.get("fatal")
    if fatal is not None and (
        not isinstance(fatal, str) or not fatal or len(fatal) > 128
    ):
        raise EvidenceError("verdict fatal category is invalid")
    engine = verdict.get("engine")
    identity = verdict.get("identity")
    if not isinstance(engine, dict) or not isinstance(identity, dict):
        raise EvidenceError("verdict engine and identity must be objects")
    _exact_fields(engine, _ENGINE_FIELDS, "engine evidence")
    _plain_int(engine.get("processStatus"), "engine.processStatus")
    _plain_bool(engine.get("realGame"), "engine.realGame")
    _bounded_string(engine.get("gameVersion"), "engine.gameVersion", maximum=200)
    _bounded_string(engine.get("unityVersion"), "engine.unityVersion", maximum=100)
    _plain_int(engine.get("terminalCount"), "engine.terminalCount")
    _validate_identity(identity)
    if identity.get("rubric") != assertions.rubric_hash():
        raise EvidenceError("verdict rubric identity does not match")
    cases = _validated_verdict_cases(verdict.get("cases"))
    expected_cases = assertions.case_names
    observed = [case["id"] for case in cases]
    exact_cases = (
        Counter(observed) == Counter(expected_cases) and len(cases) == len(expected_cases)
    )
    computed_passed = sum(case["status"] == "passed" for case in cases)
    computed_failed = sum(case["status"] == "failed" for case in cases)
    if expected != len(expected_cases) or reward not in {0, 1}:
        raise EvidenceError("verdict expected count or reward is invalid")
    if complete:
        if (
            fatal is not None
            or not exact_cases
            or passed != computed_passed
            or failed != computed_failed
            or passed + failed != expected
            or reward != int(failed == 0)
            or engine.get("processStatus") != 0
            or engine.get("realGame") is not True
            or engine.get("terminalCount") != 1
            or not str(engine.get("gameVersion")).startswith("1.6.4871 ")
            or engine.get("unityVersion") != "2022.3.35f1"
            or any(identity.get(field) == _EMPTY_SHA256 for field in _IDENTITY_FIELDS)
        ):
            raise EvidenceError("complete verdict fields are contradictory")
    elif passed != 0 or failed != 0 or reward != 0 or fatal is None or cases:
        raise EvidenceError("incomplete verdict fields are contradictory")
    return verdict


def encode_private_verdict(verdict: dict[str, Any]) -> bytes:
    return (
        json.dumps(verdict, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
