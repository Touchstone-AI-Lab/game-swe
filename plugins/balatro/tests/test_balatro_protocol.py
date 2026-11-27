from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from rhenium_balatro.evaluator import classify_native
from rhenium_balatro.protocol import MAX_RESPONSE_BYTES, PROTOCOL, classify_poc_result, decode_response

FP = {key: str(index) * 64 for index, key in enumerate(("environment", "harness", "task", "candidate"))}


def response(passed: bool) -> dict[str, Any]:
    return {"complete": True, "passed": passed, "not_executed": [],
            "classification": "pass" if passed else "behavior_mismatch",
            "processes": [{"run_id": "one", "fingerprints": FP,
                           "cleanup": {"normal_exit": True, "protected_unchanged": True}}],
            "checks": [{"id": "private-case", "observed": 1 if passed else 0,
                        "expected": 1, "passed": passed}]}


@pytest.mark.parametrize("passed", [True, False])
def test_complete_behavior_classification(passed: bool) -> None:
    result = classify_poc_result(response(passed), ("private-case",), FP, 1)
    assert result["complete"] is True
    assert result["passed"] is passed
    assert result["category"] == ("complete_pass" if passed else "behavior_failure")
    assert "private-case" not in json.dumps(result)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "timeout", "cleanup", "fingerprint",
                                    "nan", "forged", "not_executed", "early_exit", "process_count"])
def test_malformed_or_incomplete_never_passes(mutation: str) -> None:
    raw = copy.deepcopy(response(True))
    if mutation == "missing":
        raw["checks"] = []
    elif mutation == "duplicate":
        raw["checks"] *= 2
    elif mutation == "timeout":
        raw["error"] = "timeout"
    elif mutation == "cleanup":
        raw["processes"][0]["cleanup"]["normal_exit"] = False
    elif mutation == "fingerprint":
        raw["processes"][0]["fingerprints"]["candidate"] = "changed"
    elif mutation == "nan":
        raw["checks"][0]["observed"] = float("nan")
    elif mutation == "forged":
        raw["checks"][0]["observed"] = 0
    elif mutation == "not_executed":
        raw["not_executed"] = ["private-case"]
    elif mutation == "early_exit":
        raw["complete"] = False
    else:
        raw["processes"] = []
    result = classify_poc_result(raw, ("private-case",), FP, 1)
    assert result["complete"] is False and result["passed"] is False


def envelope() -> dict[str, Any]:
    return {"protocol": PROTOCOL, "request_id": "request", "nonce": "nonce",
            "submission_sha256": "f" * 64, "result": response(True)}


@pytest.mark.parametrize("key", ["protocol", "request_id", "nonce", "submission_sha256"])
def test_response_identity_is_required(key: str) -> None:
    value = envelope()
    value[key] = "wrong"
    with pytest.raises(ValueError):
        decode_response(json.dumps(value).encode(), "request", "nonce", "f" * 64)


@pytest.mark.parametrize("value", [b"{}", b"not-json", b'{"protocol":1,"protocol":2}',
                                 b"[]", b" " * (MAX_RESPONSE_BYTES + 1)],
                         ids=["empty-object", "not-json", "duplicate", "array", "oversize"])
def test_bad_response_is_rejected(value: bytes) -> None:
    with pytest.raises(ValueError):
        decode_response(value, "request", "nonce", "f" * 64)


def test_valid_bounded_response() -> None:
    value = envelope()
    assert decode_response(json.dumps(value).encode(), "request", "nonce", "f" * 64) == value["result"]


@pytest.mark.parametrize("change", [None, "environment", "candidate", "task", "harness",
                                    "process_count", "postcheck", "unreviewed"])
def test_native_response_cannot_self_declare_expected_identity(change: str | None) -> None:
    assets = {"environment": FP["environment"], "harness": FP["harness"],
              "tasks": {"exercise": {"task_sha256": FP["task"], "required": ["private-case"],
                                      "expected_processes": 1}},
              "controls": {"exercise": {"reviewed": {"seal_sha256": "submission",
                                                      "candidate_sha256": FP["candidate"]}}}}
    raw = copy.deepcopy(response(True))
    raw["platform_inputs_unchanged"] = True
    value: dict[str, Any] = {"evaluation": raw, "fingerprints": dict(FP), "runtime_count": 1}
    if change in FP:
        value["fingerprints"][change] = "different"
        raw["processes"][0]["fingerprints"][change] = "different"
    elif change == "process_count":
        value["runtime_count"] = 2
    elif change == "postcheck":
        raw["platform_inputs_unchanged"] = False
    result = classify_native(value, assets, "exercise",
                             "unreviewed" if change == "unreviewed" else "submission")
    assert result["passed"] is (change is None)
    assert result["complete"] is (change is None)
