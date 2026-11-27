from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import ModelSecrets

T = TypeVar("T", bound=BaseModel)

MAX_TOKENS_CEILING = 131_072
_RETRYABLE_STATUS = frozenset({409, 429})
_BACKOFF_CAP_SECONDS = 16.0
_RETRY_AFTER_CAP_SECONDS = 60.0


class _Truncated(Exception):
    """The endpoint stopped at max_tokens before the answer finished."""


class ModelClient:
    """Strict JSON client for isolated roles over OpenAI or Anthropic protocols."""

    def __init__(
        self,
        secrets: ModelSecrets,
        client: httpx.Client | None = None,
        max_attempts: int = 3,
        transport_attempts: int | None = None,
        on_event: Callable[[dict[str, object]], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] | None = None,
    ):
        self.secrets = secrets
        self.max_attempts = max_attempts
        # A single-attempt client (model-check, tests) never waits on transport errors
        # either; otherwise rate limits and cold starts get the documented five tries.
        self.transport_attempts = (
            transport_attempts
            if transport_attempts is not None
            else (5 if max_attempts > 1 else 1)
        )
        self.on_event = on_event or (lambda _event: None)
        self._sleep = sleep
        self._jitter = jitter or (lambda: random.uniform(0.0, 1.0))
        # Opt-in diagnostics: answers that fail structured parsing are saved (0600)
        # under this directory. Unset, no model text is ever written anywhere.
        debug = os.environ.get("RHENIUM_AUTHORING_DEBUG_DIR")
        self._debug_dir = Path(debug) if debug else None
        self._owned = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(secrets.timeout_seconds, connect=30, pool=30),
            verify=secrets.verify_tls,
        )

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def complete(
        self,
        output: type[T],
        *,
        role: str,
        payload: dict[str, object],
        history: list[dict[str, str]] | None = None,
        pipeline: str = "clean-room",
        salvage: Callable[[str], str | None] | None = None,
    ) -> T:
        """One structured answer; ``history`` carries earlier turns of a tool loop.

        Each history entry is an ``assistant`` answer or a ``user`` observation,
        appended after the payload in order, so a role can inspect a repository
        over several turns while every answer is still schema-validated.
        ``salvage`` may rewrite an answer that does not parse (for example an
        endpoint's native tool-call markup) into JSON; the result is validated
        against the same schema.
        """
        schema = output.model_json_schema()
        system = (
            f"You are the isolated {role} stage in a {pipeline} benchmark pipeline. "
            "Return one JSON object only. Never add markdown fences. Conform exactly "
            f"to this JSON Schema: {json.dumps(schema, ensure_ascii=False)}"
        )
        messages = [
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        ]
        for turn in history or []:
            if turn.get("role") not in {"assistant", "user"} or not isinstance(turn.get("content"), str):
                raise ValueError("history turns are assistant or user text")
            messages.append({"role": turn["role"], "content": turn["content"]})
        request: dict[str, object] = {
            "model": self.secrets.model,
            "max_tokens": self.secrets.max_tokens,
            "messages": messages,
        }
        headers = {"Authorization": f"Bearer {self.secrets.api_key.get_secret_value()}"}
        base_url = self.secrets.base_url.rstrip("/")
        if self.secrets.protocol == "anthropic":
            request["system"] = system
            headers["anthropic-version"] = "2023-06-01"
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            endpoint = f"{base_url}/messages"
        else:
            request["reasoning_effort"] = self.secrets.reasoning_effort
            messages.insert(0, {"role": "system", "content": system})
            endpoint = f"{base_url}/chat/completions"

        request_max_tokens = self.secrets.max_tokens
        escalated = False
        attempt = 0
        content_failures = 0
        transport_failures = 0
        while True:
            attempt += 1
            request["max_tokens"] = request_max_tokens
            self.on_event({"stage": role, "attempt": attempt, "status": "requesting"})
            transport_error = False
            retry_after: float | None = None
            content: object = None
            try:
                response = self._client.post(endpoint, headers=headers, json=request)
                response.raise_for_status()
                value = response.json()
                reasoning: object = None
                if self.secrets.protocol == "openai":
                    choice = value["choices"][0]
                    finish_reason = choice.get("finish_reason")
                    if finish_reason == "length":
                        raise _Truncated
                    if finish_reason is not None and finish_reason != "stop":
                        raise ValueError("incomplete or non-text OpenAI response")
                    message = choice["message"]
                    content = message["content"]
                    # A thinking model's reasoning stream is never parsed and never
                    # logged; only its size reaches the receipts below.
                    reasoning = message.get("reasoning_content")
                else:
                    content = _anthropic_content(value)
                if not isinstance(content, str):
                    raise ValueError
                try:
                    parsed = output.model_validate_json(_json_content(content))
                except (ValueError, ValidationError):
                    repaired = salvage(content) if salvage is not None else None
                    if repaired is None:
                        raise
                    parsed = output.model_validate_json(repaired)
                event: dict[str, object] = {
                    "stage": role,
                    "attempt": attempt,
                    "status": "received",
                    "model": value.get("model"),
                    "output_characters": len(content),
                }
                if isinstance(reasoning, str):
                    event["reasoning_characters"] = len(reasoning)
                event.update(_usage_receipts(value))
                self.on_event(event)
                return parsed
            except _Truncated:
                escalation = None if escalated else _escalated_max_tokens(request_max_tokens)
                if escalation is not None:
                    escalated = True
                    self.on_event(
                        {
                            "stage": role,
                            "attempt": attempt,
                            "status": "failed",
                            "reason": "truncated",
                            "max_tokens": request_max_tokens,
                            "escalated_to": escalation,
                        }
                    )
                    request_max_tokens = escalation
                    continue
                self.on_event(
                    {
                        "stage": role,
                        "attempt": attempt,
                        "status": "failed",
                        "reason": "truncated",
                        "max_tokens": request_max_tokens,
                    }
                )
                raise RuntimeError(
                    f"model {role} stage failed after {attempt} attempts "
                    "(response truncated by max_tokens; raise [model].max_tokens)"
                ) from None
            except httpx.HTTPStatusError as error:
                code = error.response.status_code
                last_error = f"HTTP {code}"
                if code in _RETRYABLE_STATUS or code >= 500:
                    transport_error = True
                    retry_after = _retry_after_seconds(error.response)
                else:
                    # 400/401/403/404 never get better on retry; fail fast and safely.
                    self.on_event(
                        {"stage": role, "attempt": attempt, "status": "failed", "reason": last_error}
                    )
                    raise RuntimeError(
                        f"model {role} stage failed after {attempt} attempts ({last_error})"
                    ) from None
            except httpx.ReadTimeout:
                last_error = "model response timeout"
                transport_error = True
            except httpx.ConnectTimeout:
                last_error = "connection timeout"
                transport_error = True
            except httpx.TimeoutException:
                last_error = "request transport timeout"
                transport_error = True
            except httpx.HTTPError:
                last_error = "connection or TLS failure"
                transport_error = True
            except (KeyError, IndexError, TypeError, ValueError, ValidationError):
                last_error = "invalid structured response"
                self._save_invalid(role, content)
            self.on_event({"stage": role, "attempt": attempt, "status": "failed", "reason": last_error})
            if transport_error:
                transport_failures += 1
                if transport_failures >= self.transport_attempts:
                    raise RuntimeError(
                        f"model {role} stage failed after {attempt} attempts ({last_error})"
                    ) from None
                delay = _retry_delay(transport_failures, retry_after, self._jitter)
                self.on_event(
                    {
                        "stage": role,
                        "attempt": attempt,
                        "status": "backoff",
                        "reason": last_error,
                        "delay_seconds": round(delay, 3),
                    }
                )
                self._sleep(delay)
            else:
                content_failures += 1
                if content_failures >= self.max_attempts:
                    raise RuntimeError(
                        f"model {role} stage failed after {attempt} attempts ({last_error})"
                    ) from None


    def _save_invalid(self, role: str, content: object) -> None:
        if self._debug_dir is None or not isinstance(content, str):
            return
        self._debug_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self._debug_dir / f"{role}-{time.time_ns()}.txt"
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)


def _usage_receipts(value: object) -> dict[str, object]:
    """Numeric token counts from an OpenAI-style usage block; sizes only, never text."""
    if not isinstance(value, dict):
        return {}
    usage = value.get("usage")
    if not isinstance(usage, dict):
        return {}
    receipts: dict[str, object] = {}
    completion = usage.get("completion_tokens")
    if isinstance(completion, int):
        receipts["completion_tokens"] = completion
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict):
        reasoning = details.get("reasoning_tokens")
        if isinstance(reasoning, int):
            receipts["reasoning_tokens"] = reasoning
    return receipts


def _escalated_max_tokens(current: int, ceiling: int = MAX_TOKENS_CEILING) -> int | None:
    escalated = min(current * 2, ceiling)
    return escalated if escalated > current else None


def _retry_delay(
    transport_failures: int,
    retry_after: float | None,
    jitter: Callable[[], float],
) -> float:
    if retry_after is not None:
        return retry_after + jitter()
    return min(2.0 ** (transport_failures - 1), _BACKOFF_CAP_SECONDS) + jitter()


def _retry_after_seconds(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        value = float(header.strip())
    except ValueError:
        return None
    if 0 < value <= _RETRY_AFTER_CAP_SECONDS:
        return value
    return None


def _anthropic_content(value: object) -> str:
    if not isinstance(value, dict):
        raise ValueError("expected an Anthropic message")
    if value.get("type") != "message" or value.get("role") != "assistant":
        raise ValueError("expected an Anthropic assistant message")
    if value.get("stop_reason") not in ("end_turn", "stop_sequence"):
        raise ValueError("Anthropic message did not complete")
    blocks = value.get("content")
    if not isinstance(blocks, list):
        raise ValueError("expected Anthropic content blocks")
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("invalid Anthropic content block")
        if block.get("type") == "text":
            content = block.get("text")
            if not isinstance(content, str):
                raise ValueError("invalid Anthropic text block")
            parts.append(content)
        elif block.get("type") not in ("thinking", "redacted_thinking"):
            raise ValueError("unexpected Anthropic content block")
    if not parts:
        raise ValueError("Anthropic message contains no text")
    return "".join(parts)


def _json_content(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model response does not contain a JSON object")
    candidate = stripped[start : end + 1]
    try:
        json.loads(candidate)
    except ValueError:
        # Some thinking endpoints append their native tool-call markup (itself
        # holding braces) after the JSON answer; the answer is then the first
        # complete object, and anything after it is ignored.
        try:
            _value, finish = json.JSONDecoder().raw_decode(stripped, start)
        except ValueError:
            return candidate
        return stripped[start:finish]
    return candidate
