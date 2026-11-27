"""Versioned, bounded sidecar result validation; no process launching here."""

from __future__ import annotations

import json
import math
from typing import Any

from .results import incomplete

PROTOCOL = "rhenium-balatro-sidecar-v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def decode_response(data: bytes, request_id: str, nonce: str, submission_sha256: str) -> dict[str, Any]:
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("sidecar response exceeds limit")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate response key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        del value
        raise ValueError("nonfinite response value")

    response = json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)
    if (not isinstance(response, dict) or set(response) != {
        "protocol", "request_id", "nonce", "submission_sha256", "result"
    } or response["protocol"] != PROTOCOL or response["request_id"] != request_id
            or response["nonce"] != nonce or response["submission_sha256"] != submission_sha256
            or not isinstance(response["result"], dict)):
        raise ValueError("sidecar identity or envelope mismatch")
    return response["result"]


def classify_poc_result(
    raw: dict[str, Any], required: tuple[str, ...], expected_fingerprints: dict[str, str],
    expected_processes: int,
) -> dict[str, Any]:
    """Recheck completeness/cleanup; never trust a bare passed flag or gamestate."""
    if not required or len(set(required)) != len(required) or expected_processes < 1:
        raise ValueError("invalid private requirements")
    if set(expected_fingerprints) != {"environment", "harness", "task", "candidate"}:
        raise ValueError("incomplete fingerprint binding")
    if raw.get("error") or raw.get("cleanup_error"):
        return incomplete("environment_failure")
    processes = raw.get("processes")
    if not isinstance(processes, list) or len(processes) != expected_processes:
        return incomplete("cleanup_failure")
    run_ids: set[str] = set()
    for process in processes:
        if not isinstance(process, dict):
            return incomplete("protocol_failure")
        identity = process.get("run_id")
        cleanup = process.get("cleanup")
        if (not isinstance(identity, str) or not identity or identity in run_ids
                or process.get("fingerprints") != expected_fingerprints):
            return incomplete("environment_failure")
        run_ids.add(identity)
        if (not isinstance(cleanup, dict) or cleanup.get("normal_exit") is not True
                or cleanup.get("protected_unchanged") is not True):
            return incomplete("cleanup_failure")
    checks = raw.get("checks")
    if not isinstance(checks, list) or len(checks) != len(required) or raw.get("complete") is not True:
        return incomplete("not_all_cases_executed")
    ids: set[str] = set()
    outcomes: list[bool] = []
    for check in checks:
        if not isinstance(check, dict):
            return incomplete("protocol_failure")
        case = check.get("id")
        if (not isinstance(case, str) or case in ids or case not in required
                or type(check.get("passed")) is not bool
                or "observed" not in check or "expected" not in check):
            return incomplete("not_all_cases_executed")
        ids.add(case)
        try:
            json.dumps((check["observed"], check["expected"]), allow_nan=False)
        except (ValueError, TypeError):
            return incomplete("protocol_failure")
        matched = check["observed"] == check["expected"]
        if check["passed"] != matched:
            return incomplete("protocol_failure")
        outcomes.append(matched)
    passed = all(outcomes)
    if (ids != set(required) or raw.get("not_executed") != [] or raw.get("passed") is not passed
            or raw.get("classification") != ("pass" if passed else "behavior_mismatch")):
        return incomplete("protocol_failure")
    score = sum(outcomes) / len(outcomes)
    if not math.isfinite(score):
        return incomplete("protocol_failure")
    return {"score": score, "complete": True, "passed": passed,
            "category": "complete_pass" if passed else "behavior_failure",
            "reason": "none" if passed else "behavior_mismatch",
            "checks": [{"name": f"check-{index}", "passed": outcome}
                       for index, outcome in enumerate(outcomes, 1)], "runtime_log": ""}
