from __future__ import annotations

import threading
import uuid
from typing import Any

from sqlalchemy import select

from .core.auth import AuthChallenge
from .core.runtime import RuntimeActionRequired
from .hub import BenchmarkHub, _utc_iso
from .models import Operation
from .util import json_dumps, json_loads


def operation_dict(row: Operation) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "target": row.target,
        "status": row.status,
        "phase": row.phase,
        "progress": row.progress,
        "publicState": json_loads(row.public_state_json, {}),
        "result": json_loads(row.result_json, {}),
        "error": row.error,
        "cancelRequested": row.cancel_requested,
        "createdAt": _utc_iso(row.created_at),
        "updatedAt": _utc_iso(row.updated_at),
    }


class OperationManager:
    def __init__(self, hub: BenchmarkHub):
        self.hub = hub
        self._threads: dict[str, threading.Thread] = {}

    def _update(self, operation_id: str, **values: Any) -> None:
        with self.hub.database.session_factory() as session:
            row = session.get(Operation, operation_id)
            if row is None:
                return
            for field, value in values.items():
                setattr(row, field, value)
            session.commit()

    def _progress(self, operation_id: str, value: int, phase: str) -> None:
        self._update(
            operation_id,
            progress=max(0, min(int(value), 100)),
            phase=phase[:100],
        )

    def _challenge(self, operation_id: str, challenge: AuthChallenge) -> None:
        self._update(
            operation_id,
            status="waiting_user",
            phase=challenge.message or "scan the QR code",
            public_state_json=json_dumps(
                {"challenge": challenge.model_dump(mode="json")}
            ),
        )

    def start(self, kind: str, target: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        if kind not in {
            "auth_login",
            "runtime_prepare",
            "runtime_verify",
            "runtime_prune",
        }:
            raise ValueError(f"unsupported operation kind: {kind}")
        with self.hub.database.session_factory() as session:
            existing = session.scalar(
                select(Operation).where(
                    Operation.kind == kind,
                    Operation.target == target,
                    Operation.status.in_(("queued", "running", "waiting_user")),
                )
            )
            if existing is not None:
                return operation_dict(existing)
            row = Operation(
                id=f"operation-{uuid.uuid4().hex[:20]}",
                kind=kind,
                target=target,
                status="queued",
                public_state_json=json_dumps({"request": payload}),
            )
            session.add(row)
            session.commit()
            result = operation_dict(row)

        thread = threading.Thread(
            target=self._run,
            args=(row.id, kind, target, payload),
            name=f"rhenium-{kind}-{row.id}",
            daemon=True,
        )
        self._threads[row.id] = thread
        thread.start()
        return result

    def _run(self, operation_id: str, kind: str, target: str, payload: dict[str, Any]) -> None:
        self._update(operation_id, status="running", phase="starting", progress=1)
        try:
            account = str(payload.get("account", "default"))
            if kind == "auth_login":
                result = self.hub.auth.login(
                    target,
                    account,
                    challenge=lambda item: self._challenge(operation_id, item),
                    progress=lambda value, phase: self._progress(operation_id, value, phase),
                )
            elif kind == "runtime_prepare":
                result = self.hub.runtime_manager.prepare(
                    target,
                    account_alias=account,
                    progress=lambda value, phase: self._progress(operation_id, value, phase),
                )
            elif kind == "runtime_verify":
                result = self.hub.runtime_manager.verify(target)
            else:
                result = self.hub.runtime_manager.prune(target)
            self._update(
                operation_id,
                status="completed",
                phase="complete",
                progress=100,
                public_state_json="{}",
                result_json=json_dumps(result),
                error=None,
            )
        except RuntimeActionRequired as error:
            self._update(
                operation_id,
                status="action_required",
                phase=str(error),
                public_state_json=json_dumps(
                    {
                        "action": {
                            "kind": error.kind,
                            "message": str(error),
                            "details": error.details,
                        }
                    }
                ),
                error=None,
            )
        except Exception as error:
            self._update(
                operation_id,
                status="failed",
                phase="failed",
                error=str(error),
            )
        finally:
            self._threads.pop(operation_id, None)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.hub.database.session_factory() as session:
            rows = session.scalars(
                select(Operation).order_by(Operation.created_at.desc()).limit(max(1, min(limit, 500)))
            ).all()
            return [operation_dict(row) for row in rows]

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self.hub.database.session_factory() as session:
            row = session.get(Operation, operation_id)
            return operation_dict(row) if row else None

    def cancel(self, operation_id: str) -> dict[str, Any]:
        with self.hub.database.session_factory() as session:
            row = session.get(Operation, operation_id)
            if row is None:
                raise KeyError(operation_id)
            row.cancel_requested = True
            session.commit()
            return operation_dict(row)
