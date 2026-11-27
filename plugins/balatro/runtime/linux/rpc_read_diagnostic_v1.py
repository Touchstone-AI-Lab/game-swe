"""Bounded metadata-only observers; preserve original I/O and validation semantics."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any


class ReadDiagnostic:
    def __init__(self, limit: int = 512) -> None:
        self.limit = limit
        self.rows: list[dict[str, Any]] = []
        self.dropped = 0
        self.observer_errors = 0

    def wrap_read(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def observed(response: Any, *args: Any, **kwargs: Any) -> Any:
            declared = response.length
            value = original(response, *args, **kwargs)
            try:
                requested = args[0] if args else kwargs.get("amt")
                row = {
                    "status": response.status,
                    "declared_remaining_before": declared,
                    "received_bytes": len(value),
                    "remaining_after": response.length,
                    "body_sha256": hashlib.sha256(value).hexdigest(),
                    "short_read": declared is not None
                    and (requested is None or requested >= declared)
                    and len(value) < declared,
                }
                if len(self.rows) < self.limit:
                    self.rows.append(row)
                else:
                    self.dropped += 1
            except Exception:
                self.observer_errors += 1
            return value

        return observed

    def wrap_envelope(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def observed(status: int, body: bytes, request_id: int) -> Any:
            row = self.rows[-1] if self.rows else None
            if row is not None:
                row["request_id"] = request_id
            try:
                return original(status, body, request_id)
            except BaseException as error:
                if row is not None:
                    row["error_type"] = type(error).__name__
                    row["cause_type"] = type(error.__cause__).__name__
                    row["parse_position"] = getattr(error.__cause__, "pos", None)
                raise

        return observed
