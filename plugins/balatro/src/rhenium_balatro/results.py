"""Allowlisted anonymous results: never forward arbitrary game/helper strings."""

from __future__ import annotations

import math
import re
from typing import Any

CATEGORIES = {"complete_pass", "behavior_failure", "incomplete"}
REASONS = {"runtime_action_required", "unsupported_profile", "invalid_submission", "protocol_failure",
           "environment_failure", "cleanup_failure", "not_all_cases_executed", "behavior_mismatch", "none",
           "submission_review_required"}


def incomplete(reason: str) -> dict[str, Any]:
    if reason not in REASONS:
        reason = "protocol_failure"
    return {"score": 0.0, "complete": False, "passed": False, "category": "incomplete",
            "reason": reason, "checks": [{"name": "evaluation", "passed": False, "detail": reason}],
            "runtime_log": ""}


def anonymous_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return incomplete("protocol_failure")
    # Hub response and nested evaluator result use the same defensive projection.
    result: dict[str, Any] = {}
    for key in ("runId", "id"):
        identifier = value.get(key)
        if isinstance(identifier, str) and re.fullmatch(r"(?:run-)?[a-f0-9-]{16,64}", identifier):
            result[key] = identifier
    submission_hash = value.get("submissionSha256")
    if isinstance(submission_hash, str) and re.fullmatch(r"[a-f0-9]{64}", submission_hash):
        result["submissionSha256"] = submission_hash
    status = value.get("status")
    if isinstance(status, str) and status in {"passed", "failed", "error", "completed"}:
        result["status"] = status
    if isinstance(value.get("result"), dict):
        result["result"] = anonymous_result(value["result"])
        if result.get("status") == "passed" and result["result"].get("passed") is not True:
            result["status"] = "failed"
        return result
    for key in ("complete", "passed"):
        result[key] = value.get(key) is True
    if not result["complete"]:
        result["passed"] = False
    score = value.get("score")
    result["score"] = (float(score) if isinstance(score, (int, float)) and not isinstance(score, bool)
                       and math.isfinite(score)
                       and 0 <= score <= 1 else 0.0)
    category = value.get("category")
    result["category"] = category if isinstance(category, str) and category in CATEGORIES else "incomplete"
    reason = value.get("reason")
    result["reason"] = reason if isinstance(reason, str) and reason in REASONS else "protocol_failure"
    if (result["category"] == "incomplete" or result["reason"] == "protocol_failure"
            or (result["passed"] and result["category"] != "complete_pass")
            or (not result["passed"] and result["category"] == "complete_pass")):
        result.update(complete=False, passed=False, score=0.0, category="incomplete")
    checks = value.get("checks", [])
    if isinstance(checks, list):
        result["checks"] = [
            {"name": f"check-{index}", "passed": check.get("passed") is True}
            for index, check in enumerate(checks[:256], 1) if isinstance(check, dict)
        ]
    return result
