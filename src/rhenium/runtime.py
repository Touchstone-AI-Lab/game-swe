from __future__ import annotations

import platform
import shutil
import threading
from dataclasses import dataclass
from typing import Any

from .auth import AuthManager
from .config import Settings
from .core.auth import AuthProvider
from .core.plugin import BenchmarkContext, BenchmarkPlugin
from .core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec
from .database import Database
from .models import RuntimeRecord
from .util import json_loads


@dataclass(frozen=True)
class RuntimeBinding:
    key: str
    game_id: str
    spec: RuntimeSpec
    plugin: BenchmarkPlugin
    context: BenchmarkContext
    builder: RuntimeBuilder


class RuntimeManager:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        auth: AuthManager,
        providers: dict[str, AuthProvider],
    ) -> None:
        self.settings = settings
        self.database = database
        self.auth = auth
        self.providers = providers
        self.bindings: dict[str, RuntimeBinding] = {}
        self.task_bindings: dict[str, tuple[str, ...]] = {}
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @staticmethod
    def host_platform() -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(
            machine, machine
        )
        return f"{system}-{architecture}"

    def register(
        self,
        *,
        game_id: str,
        plugin: BenchmarkPlugin,
        context: BenchmarkContext,
        spec: RuntimeSpec,
        tasks: tuple[str, ...],
    ) -> None:
        key = f"{game_id}/{spec.id}"
        builder = plugin.create_runtime_builder(context, spec)
        if builder is None:
            raise ValueError(f"plugin {plugin.id} does not provide runtime builder {spec.id}")
        proposed = RuntimeBinding(key, game_id, spec, plugin, context, builder)
        existing = self.bindings.get(key)
        if existing is not None and (
            existing.spec != proposed.spec or existing.plugin.id != proposed.plugin.id
        ):
            raise ValueError(f"conflicting runtime definition: {key}")
        self.bindings[key] = proposed
        for task_key in tasks:
            current = self.task_bindings.get(task_key, ())
            if key not in current:
                self.task_bindings[task_key] = (*current, key)

    def _binding(self, runtime_key: str) -> RuntimeBinding:
        try:
            return self.bindings[runtime_key]
        except KeyError as error:
            raise KeyError(f"unknown runtime: {runtime_key}") from error

    def _fingerprint(self, binding: RuntimeBinding) -> str:
        return binding.spec.fingerprint(
            plugin_id=binding.plugin.id,
            plugin_version=binding.plugin.descriptor.version,
        )

    def _lock(self, runtime_key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(runtime_key, threading.Lock())

    def _record(self, runtime_key: str) -> RuntimeRecord | None:
        with self.database.session_factory() as session:
            return session.get(RuntimeRecord, runtime_key)

    def _artifact(self, row: RuntimeRecord | None) -> RuntimeArtifact | None:
        if row is None or row.status != "ready":
            return None
        try:
            return RuntimeArtifact.model_validate(json_loads(row.artifact_json, {}))
        except (TypeError, ValueError):
            return None

    def list(self, game_id: str | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for key, binding in sorted(self.bindings.items()):
            if game_id and binding.game_id != game_id:
                continue
            row = self._record(key)
            fingerprint = self._fingerprint(binding)
            artifact = self._artifact(row)
            ready = bool(row and row.fingerprint == fingerprint and artifact)
            result.append(
                {
                    "key": key,
                    "gameId": binding.game_id,
                    "id": binding.spec.id,
                    "name": binding.spec.name,
                    "version": binding.spec.version,
                    "provider": binding.spec.provider,
                    "restricted": binding.spec.restricted,
                    "hostPlatforms": binding.spec.host_platforms,
                    "hostPlatform": self.host_platform(),
                    "hostSupported": not binding.spec.host_platforms
                    or self.host_platform() in binding.spec.host_platforms,
                    "status": "ready" if ready else row.status if row else "missing",
                    "ready": ready,
                    "fingerprint": fingerprint,
                    "artifact": artifact.model_dump(mode="json") if ready and artifact else None,
                    "error": row.error if row else None,
                }
            )
        return result

    def doctor(self, runtime_key: str) -> dict[str, Any]:
        binding = self._binding(runtime_key)
        host = self.host_platform()
        return {
            "key": runtime_key,
            "providerInstalled": binding.spec.provider in self.providers,
            "builder": binding.builder.doctor(binding.spec),
            "hostPlatforms": binding.spec.host_platforms,
            "hostPlatform": host,
            "hostSupported": not binding.spec.host_platforms or host in binding.spec.host_platforms,
        }

    def prepare(
        self,
        runtime_key: str,
        *,
        account_alias: str = "default",
        progress: Any = None,
    ) -> dict[str, Any]:
        progress = progress or (lambda _value, _phase: None)
        binding = self._binding(runtime_key)
        host = self.host_platform()
        if binding.spec.host_platforms and host not in binding.spec.host_platforms:
            supported = ", ".join(binding.spec.host_platforms)
            raise RuntimeError(f"runtime {runtime_key} does not support host {host}; choose: {supported}")
        provider = self.providers.get(binding.spec.provider)
        if provider is None:
            raise RuntimeError(f"auth provider is not installed: {binding.spec.provider}")
        fingerprint = self._fingerprint(binding)
        with self._lock(runtime_key):
            current = self._record(runtime_key)
            current_artifact = self._artifact(current)
            if current and current.fingerprint == fingerprint and current_artifact:
                verified = binding.builder.verify(binding.spec, current_artifact)
                if bool(verified.get("available", False)):
                    return self.status(runtime_key)

            with self.database.session_factory() as database_session:
                row = database_session.get(RuntimeRecord, runtime_key)
                if row is None:
                    row = RuntimeRecord(
                        runtime_key=runtime_key,
                        fingerprint=fingerprint,
                        provider_id=binding.spec.provider,
                        account_alias=account_alias,
                    )
                    database_session.add(row)
                row.fingerprint = fingerprint
                row.provider_id = binding.spec.provider
                row.account_alias = account_alias
                row.status = "preparing"
                row.error = None
                database_session.commit()

            session_value = self.auth.session(binding.spec.provider, account_alias)
            source = self.settings.cache_dir / "providers" / binding.spec.provider / fingerprint
            artifact_root = self.settings.cache_dir / "runtimes" / binding.game_id / binding.spec.id
            source.mkdir(parents=True, exist_ok=True)
            artifact_root.mkdir(parents=True, exist_ok=True)
            try:
                progress(5, "acquiring licensed runtime source")
                refreshed = provider.acquire(
                    binding.spec.source,
                    session_value,
                    source,
                    progress=lambda value, phase: progress(5 + int(value * 0.55), phase),
                )
                self.auth.save(refreshed)
                progress(65, "building evaluator artifact")
                artifact = binding.builder.prepare(
                    binding.spec,
                    source,
                    artifact_root,
                    progress=lambda value, phase: progress(65 + int(value * 0.3), phase),
                )
                if artifact.runtime_key != runtime_key or artifact.fingerprint != fingerprint:
                    raise ValueError("runtime builder returned an artifact with invalid identity")
                verified = binding.builder.verify(binding.spec, artifact)
                if not bool(verified.get("available", False)):
                    raise RuntimeError(str(verified.get("reason") or "runtime verification failed"))
                with self.database.session_factory() as database_session:
                    row = database_session.get(RuntimeRecord, runtime_key)
                    assert row is not None
                    row.status = "ready"
                    row.artifact_json = artifact.model_dump_json()
                    row.error = None
                    database_session.commit()
                progress(100, "runtime ready")
                return self.status(runtime_key)
            except Exception as error:
                with self.database.session_factory() as database_session:
                    row = database_session.get(RuntimeRecord, runtime_key)
                    assert row is not None
                    row.status = "failed"
                    row.error = str(error)
                    database_session.commit()
                raise

    def status(self, runtime_key: str) -> dict[str, Any]:
        binding = self._binding(runtime_key)
        item = next(value for value in self.list(binding.game_id) if value["key"] == runtime_key)
        if item["ready"]:
            artifact = RuntimeArtifact.model_validate(item["artifact"])
            verification = binding.builder.verify(binding.spec, artifact)
            if not bool(verification.get("available", False)):
                return {**item, "ready": False, "status": "unavailable", "verification": verification}
            return {**item, "verification": verification}
        return item

    def artifacts_for_task(self, task_key: str, *, required: bool) -> dict[str, RuntimeArtifact]:
        result: dict[str, RuntimeArtifact] = {}
        for runtime_key in self.task_bindings.get(task_key, ()):
            row = self._record(runtime_key)
            binding = self._binding(runtime_key)
            artifact = self._artifact(row)
            if row is None or row.fingerprint != self._fingerprint(binding) or artifact is None:
                if required:
                    raise RuntimeError(
                        f"runtime {runtime_key} is not prepared; run rhenium runtime prepare {runtime_key}"
                    )
                continue
            result[runtime_key] = artifact
        return result

    def verify(self, runtime_key: str) -> dict[str, Any]:
        return self.status(runtime_key)

    def prune(self, runtime_key: str) -> dict[str, Any]:
        binding = self._binding(runtime_key)
        with self._lock(runtime_key):
            row = self._record(runtime_key)
            artifact = self._artifact(row)
            if artifact is not None:
                binding.builder.prune(binding.spec, artifact)
            fingerprint = self._fingerprint(binding)
            source = self.settings.cache_dir / "providers" / binding.spec.provider / fingerprint
            artifact_root = self.settings.cache_dir / "runtimes" / binding.game_id / binding.spec.id
            for candidate in (source, artifact_root):
                if candidate.exists():
                    shutil.rmtree(candidate)
            with self.database.session_factory() as session:
                stored = session.get(RuntimeRecord, runtime_key)
                if stored is not None:
                    session.delete(stored)
                    session.commit()
        return {"key": runtime_key, "status": "pruned"}
