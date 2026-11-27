from __future__ import annotations

from typing import Any


def token_usage(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Provider-reported usage summed over every model call of one trajectory."""
    totals = {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "cached_prompt_tokens": 0,
        "calls_without_usage": 0,
    }
    first: float | None = None
    last: float | None = None
    messages = trajectory.get("messages")
    for message in messages if isinstance(messages, list) else []:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        extra = message.get("extra")
        if not isinstance(extra, dict):
            continue
        totals["calls"] += 1
        stamp = extra.get("timestamp")
        if isinstance(stamp, int | float):
            first = stamp if first is None else min(first, stamp)
            last = stamp if last is None else max(last, stamp)
        response = extra.get("response")
        usage = response.get("usage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            totals["calls_without_usage"] += 1
            continue
        totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict):
            totals["reasoning_tokens"] += int(details.get("reasoning_tokens") or 0)
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, dict):
            totals["cached_prompt_tokens"] += int(prompt_details.get("cached_tokens") or 0)
    return {
        **totals,
        "first_call_at": first,
        "last_call_at": last,
        "cost_source": "provider token counts; no price table applied",
    }
