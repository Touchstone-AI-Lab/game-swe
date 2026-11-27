from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthProviderDescriptor(AuthModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    capabilities: tuple[str, ...] = ()


class AuthChallenge(AuthModel):
    kind: str
    uri: str
    expires_at: str | None = None
    message: str = ""


class AuthSession(AuthModel):
    provider_id: str
    account_alias: str
    principal: str
    secret: dict[str, str] = Field(repr=False)
    metadata: dict[str, Any] = {}


class AuthSessionView(AuthModel):
    provider_id: str
    account_alias: str
    principal: str
    status: str
    metadata: dict[str, Any] = {}


ProgressCallback = Callable[[int, str], None]
ChallengeCallback = Callable[[AuthChallenge], None]


class AuthProvider(ABC):
    """Credentials and licensed content acquisition supplied outside core."""

    descriptor: AuthProviderDescriptor

    @property
    def id(self) -> str:
        return self.descriptor.id

    @abstractmethod
    def login(
        self,
        account_alias: str,
        *,
        challenge: ChallengeCallback,
        progress: ProgressCallback,
    ) -> AuthSession:
        """Run an interactive login and return an opaque reusable session."""

    @abstractmethod
    def validate(self, session: AuthSession) -> AuthSession:
        """Validate and optionally refresh a stored session."""

    @abstractmethod
    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: ProgressCallback,
    ) -> AuthSession:
        """Acquire a provider-specific source and return the refreshed session."""
