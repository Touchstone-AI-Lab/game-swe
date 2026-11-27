from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from .core.auth import AuthChallenge, AuthProvider, AuthSession
from .database import Database
from .models import AuthSessionRecord
from .util import json_dumps, json_loads


class AuthManager:
    def __init__(self, database: Database, providers: dict[str, AuthProvider]):
        self.database = database
        self.providers = providers

    @staticmethod
    def _key(provider_id: str, account_alias: str) -> str:
        if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", account_alias) is None:
            raise ValueError("account alias must be 1-64 letters, digits, dots, dashes, or underscores")
        return f"{provider_id}/{account_alias}"

    def provider_list(self) -> list[dict[str, Any]]:
        sessions = self.list_sessions()
        return [
            {
                **provider.descriptor.model_dump(mode="json"),
                "sessions": [item for item in sessions if item["providerId"] == provider.id],
            }
            for provider in sorted(self.providers.values(), key=lambda item: item.id)
        ]

    def list_sessions(self) -> list[dict[str, Any]]:
        with self.database.session_factory() as session:
            rows = session.scalars(
                select(AuthSessionRecord).order_by(
                    AuthSessionRecord.provider_id, AuthSessionRecord.account_alias
                )
            ).all()
            return [
                {
                    "providerId": row.provider_id,
                    "accountAlias": row.account_alias,
                    "principal": row.principal,
                    "status": row.status,
                    "metadata": json_loads(row.metadata_json, {}),
                    "configured": bool(row.secret_json),
                }
                for row in rows
            ]

    def _provider(self, provider_id: str) -> AuthProvider:
        try:
            return self.providers[provider_id]
        except KeyError as error:
            raise KeyError(f"auth provider is not installed: {provider_id}") from error

    def save(self, value: AuthSession, *, status: str = "ready") -> None:
        key = self._key(value.provider_id, value.account_alias)
        with self.database.session_factory() as session:
            row = session.get(AuthSessionRecord, key)
            if row is None:
                row = AuthSessionRecord(
                    key=key,
                    provider_id=value.provider_id,
                    account_alias=value.account_alias,
                    principal=value.principal,
                    secret_json="{}",
                )
                session.add(row)
            row.principal = value.principal
            row.status = status
            row.secret_json = json_dumps(value.secret)
            row.metadata_json = json_dumps(value.metadata)
            session.commit()

    def session(self, provider_id: str, account_alias: str = "default") -> AuthSession:
        key = self._key(provider_id, account_alias)
        with self.database.session_factory() as database_session:
            row = database_session.get(AuthSessionRecord, key)
            if row is None or not row.secret_json:
                raise RuntimeError(
                    f"{provider_id} account {account_alias!r} is not logged in; run "
                    f"rhenium auth login {provider_id} --account {account_alias}"
                )
            if row.status == "reauth_required":
                raise RuntimeError(
                    f"{provider_id} account {account_alias!r} requires login again"
                )
            return AuthSession(
                provider_id=row.provider_id,
                account_alias=row.account_alias,
                principal=row.principal,
                secret=json_loads(row.secret_json, {}),
                metadata=json_loads(row.metadata_json, {}),
            )

    def login(
        self,
        provider_id: str,
        account_alias: str = "default",
        *,
        challenge: Callable[[AuthChallenge], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
    ) -> dict[str, Any]:
        self._key(provider_id, account_alias)
        provider = self._provider(provider_id)
        value = provider.login(
            account_alias,
            challenge=challenge or (lambda _item: None),
            progress=progress or (lambda _value, _phase: None),
        )
        if value.provider_id != provider_id or value.account_alias != account_alias:
            raise ValueError("auth provider returned a session for the wrong provider or alias")
        self.save(value)
        return {
            "providerId": provider_id,
            "accountAlias": account_alias,
            "principal": value.principal,
            "status": "ready",
            "metadata": value.metadata,
        }

    def validate(self, provider_id: str, account_alias: str = "default") -> dict[str, Any]:
        provider = self._provider(provider_id)
        current = self.session(provider_id, account_alias)
        try:
            refreshed = provider.validate(current)
        except Exception:
            self.save(current, status="reauth_required")
            raise
        self.save(refreshed)
        return {
            "providerId": provider_id,
            "accountAlias": account_alias,
            "principal": refreshed.principal,
            "status": "ready",
            "metadata": refreshed.metadata,
        }

    def logout(self, provider_id: str, account_alias: str = "default") -> dict[str, Any]:
        key = self._key(provider_id, account_alias)
        with self.database.session_factory() as session:
            row = session.get(AuthSessionRecord, key)
            if row is not None:
                session.delete(row)
                session.commit()
        return {
            "providerId": provider_id,
            "accountAlias": account_alias,
            "status": "logged_out",
            "remoteRevoked": False,
        }

