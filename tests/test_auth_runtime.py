from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rhenium.api import create_app
from rhenium.core.auth import AuthChallenge, AuthProvider, AuthProviderDescriptor, AuthSession
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeCatalog, RuntimeSpec
from rhenium.hub import BenchmarkHub
from rhenium.operations import OperationManager
from tests.conftest import FixturePlugin, write_fixture_pack

# An upper bound only: the poll exits as soon as the operation finishes. Ten seconds was not
# enough for the background login thread on a heavily loaded self-hosted CI runner.
_OPERATION_TIMEOUT_SECONDS = 60.0
_OPERATION_POLL_INTERVAL_SECONDS = 0.05


class FakeProvider(AuthProvider):
    descriptor = AuthProviderDescriptor(
        id="fake-auth", name="Fake auth", version="1.0.0", capabilities=("qr",)
    )

    def login(self, account_alias: str, *, challenge: Any, progress: Any) -> AuthSession:
        challenge(AuthChallenge(kind="qr", uri="fake://challenge", message="scan"))
        progress(50, "waiting")
        return AuthSession(
            provider_id=self.id,
            account_alias=account_alias,
            principal="fixture-user",
            secret={"refreshToken": "must-never-leak"},
        )

    def validate(self, session: AuthSession) -> AuthSession:
        return session

    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: Any,
    ) -> AuthSession:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "licensed.bin").write_text(str(source["build"]), encoding="utf-8")
        progress(100, "downloaded")
        return session


class FakeBuilder(RuntimeBuilder):
    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        return {"available": True, "version": spec.version}

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        assert (source / "licensed.bin").read_text(encoding="utf-8") == "fixture-1"
        destination.mkdir(parents=True, exist_ok=True)
        marker = destination / "ready"
        marker.write_text("ok", encoding="utf-8")
        progress(100, "ready")
        return RuntimeArtifact(
            runtime_key=f"fixture/{spec.id}",
            fingerprint=spec.fingerprint(plugin_id="fixture", plugin_version="0.5.0"),
            kind="directory",
            identity="fixture-artifact",
            location=str(marker),
        )

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        del spec
        return {"available": bool(artifact.location and Path(artifact.location).is_file())}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        del spec, artifact


class ManagedFixturePlugin(FixturePlugin):
    def create_runtime_builder(
        self, context: BenchmarkContext, spec: RuntimeSpec
    ) -> RuntimeBuilder | None:
        del context
        return FakeBuilder() if spec.id == "fixture-1" else None


def managed_hub(settings: Any, host_platforms: tuple[str, ...] = ()) -> BenchmarkHub:
    manifest = write_fixture_pack(settings.benchmark_paths[0])
    pack = manifest.parent
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["runtime_catalog"] = "runtimes.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    (pack / "runtimes.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "runtimes": [
                    {
                        "id": "fixture-1",
                        "name": "Fixture runtime",
                        "version": "1",
                        "provider": "fake-auth",
                        "source": {"build": "fixture-1"},
                        "host_platforms": list(host_platforms),
                    }
                ],
                "task_bindings": {"shared-task": ["fixture-1"]},
            }
        ),
        encoding="utf-8",
    )
    plugin = ManagedFixturePlugin()
    provider = FakeProvider()
    return BenchmarkHub(
        settings,
        plugins={plugin.id: plugin},
        auth_providers={provider.id: provider},
        manifest_paths=(manifest,),
    )


def test_auth_secret_is_stored_but_never_returned(settings: Any) -> None:
    hub = managed_hub(settings)
    result = hub.auth.login("fake-auth")
    serialized = json.dumps({"result": result, "providers": hub.auth.provider_list()})

    assert result["principal"] == "fixture-user"
    assert "must-never-leak" not in serialized
    assert hub.auth.session("fake-auth").secret["refreshToken"] == "must-never-leak"


@pytest.mark.parametrize("active,history,include_active,bound,expected", [
    (True, False, True, True, True),
    (False, True, True, True, False),
    (True, True, False, True, False),
    (True, False, True, False, False),
    (True, True, True, False, True),
])
def test_pack_readiness_uses_required_runtimes_and_preserves_history(
    settings: Any, monkeypatch: pytest.MonkeyPatch, active: bool, history: bool,
    include_active: bool, bound: bool, expected: bool,
) -> None:
    hub = managed_hub(settings)
    key, loaded = next(iter(hub.benchmarks.items()))
    assert loaded.runtime_catalog is not None
    catalog = loaded.runtime_catalog
    legacy = catalog.runtimes[0].model_copy(update={"id": "fixture-history"})
    hub.benchmarks[key] = replace(loaded, runtime_catalog=RuntimeCatalog(
        runtimes=(*catalog.runtimes, legacy), task_bindings=catalog.task_bindings if bound else {},
    ))
    rows: list[dict[str, Any]] = [{"id": "fixture-history", "ready": history}]
    if include_active:
        rows.append({"id": "fixture-1", "ready": active})
    monkeypatch.setattr(hub.runtime_manager, "list", lambda _game: rows)
    pack = hub.list_packs()[0]
    assert pack["runtime"]["available"] is expected
    assert pack["runtime"]["runtimes"] == rows


def test_full_evaluation_requires_explicit_runtime_prepare(settings: Any, tmp_path: Path) -> None:
    hub = managed_hub(settings)
    submission = tmp_path / "submission"
    submission.mkdir()
    (submission / "answer.txt").write_text("fixture-ok\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="rhenium runtime prepare fixture/fixture-1"):
        hub.evaluate_task("fixture/core/shared-task", submission, profile="full")

    hub.auth.login("fake-auth")
    prepared = hub.runtime_manager.prepare("fixture/fixture-1")
    assert prepared["ready"] is True
    assert hub.evaluate_task("fixture/core/shared-task", submission, profile="full")["status"] == "passed"
    assert hub.runtime_manager.prune("fixture/fixture-1")["status"] == "pruned"


def test_loopback_api_surfaces_qr_operation_without_secret(settings: Any) -> None:
    hub = managed_hub(settings)
    with TestClient(create_app(settings, hub=hub)) as client:
        started = client.post(
            "/api/auth/providers/fake-auth/login", json={"account": "default"}
        ).json()
        result: dict[str, Any] = started
        deadline = time.monotonic() + _OPERATION_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            result = client.get(f"/api/operations/{started['id']}").json()
            if result["status"] in {"completed", "failed"}:
                break
            time.sleep(_OPERATION_POLL_INTERVAL_SECONDS)

    assert result["status"] == "completed"
    assert "must-never-leak" not in json.dumps(result)



def test_windows_host_is_not_delegated_to_a_worker(
    settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = managed_hub(settings, host_platforms=("linux-x64",))
    hub.auth.login("fake-auth")
    monkeypatch.setattr("rhenium.runtime.platform.system", lambda: "Windows")
    monkeypatch.setattr("rhenium.runtime.platform.machine", lambda: "AMD64")

    with pytest.raises(RuntimeError, match="does not support host windows-x64; choose: linux-x64"):
        hub.runtime_manager.prepare("fixture/fixture-1")
    assert not (settings.cache_dir / "providers").exists()


def test_worker_api_and_operation_are_removed(settings: Any) -> None:
    hub = managed_hub(settings)
    with TestClient(create_app(settings, hub=hub)) as client:
        assert client.get("/api/workers").status_code in {404, 405}
        assert client.post("/api/workers/wsl2/setup").status_code in {404, 405}
    with pytest.raises(ValueError, match="unsupported operation kind: worker_setup"):
        OperationManager(hub).start("worker_setup", "wsl2")
