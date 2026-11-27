from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeSpec(RuntimeModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    restricted: bool = True
    host_platforms: tuple[str, ...] = ()
    source: dict[str, Any]

    def fingerprint(self, *, plugin_id: str, plugin_version: str) -> str:
        payload = {
            "plugin": plugin_id,
            "pluginVersion": plugin_version,
            "runtime": self.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class RuntimeCatalog(RuntimeModel):
    schema_version: int = 1
    runtimes: tuple[RuntimeSpec, ...]
    task_bindings: dict[str, tuple[str, ...]]

    @model_validator(mode="after")
    def references_known_unique_runtimes(self) -> Self:
        runtime_ids = [item.id for item in self.runtimes]
        if len(runtime_ids) != len(set(runtime_ids)):
            raise ValueError("runtime IDs must be unique")
        known = set(runtime_ids)
        for task_id, bindings in self.task_bindings.items():
            if not task_id or not bindings or not set(bindings).issubset(known):
                raise ValueError(f"invalid runtime binding for task: {task_id}")
        return self

    @classmethod
    def load(cls, pack_root: Path, relative: str) -> Self:
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or relative != path.as_posix():
            raise ValueError("runtime catalog must be a normalized relative POSIX path")
        root = pack_root.resolve()
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError(f"runtime catalog is missing: {relative}")
        return cls.model_validate_json(candidate.read_text(encoding="utf-8"))


class RuntimeArtifact(RuntimeModel):
    runtime_key: str
    fingerprint: str
    kind: str
    identity: str
    location: str | None = None
    metadata: dict[str, Any] = {}


class RuntimeActionRequired(RuntimeError):
    def __init__(self, kind: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.kind = kind
        self.details = details or {}


RuntimeProgress = Callable[[int, str], None]


class RuntimeBuilder(ABC):
    """Game-owned transformation from licensed source to evaluator artifact."""

    @abstractmethod
    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        """Report host capabilities without changing system state."""

    @abstractmethod
    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: RuntimeProgress,
    ) -> RuntimeArtifact:
        """Build and verify a local, non-redistributable runtime artifact."""

    @abstractmethod
    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        """Verify an existing artifact without rebuilding it."""

    @abstractmethod
    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        """Delete external resources owned by an artifact."""
