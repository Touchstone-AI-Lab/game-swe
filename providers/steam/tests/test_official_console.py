from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rhenium_steam import official_console as console
from rhenium_steam.provider import SteamAuthProvider

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Linux private-profile filesystem semantics")


def source() -> dict[str, Any]:
    return {
        "kind": "steam-depots",
        "appId": 123,
        "buildId": 456,
        "os": "windows",
        "depots": [{"id": 789, "manifest": "3512319404653808464"}],
        "expectedFiles": ["game.bin"],
        "sha256": {"game.bin": hashlib.sha256(b"unit-game").hexdigest()},
    }


@pytest.fixture
def profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> console.Profile:
    monkeypatch.setattr(console, "require_host", lambda: None)
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path))
    home = tmp_path / "home"
    home.mkdir()
    (home / "client.bin").write_bytes(b"unit-client")
    path = tmp_path / "profile.json"
    value = {
        "schema": 1,
        "id": str(uuid.uuid4()),
        "home": str(home),
        "image_id": "sha256:" + "a" * 64,
        "client_files": {"client.bin": console.sha(home / "client.bin")},
        "allowed_source_sha256": console.fingerprint(source()),
        "approval": {
            "approved": True,
            "cef_control": True,
            "loopback_only": True,
            "maximum_process_seconds": 1800,
            "host_ports_published": False,
            "new_authentication_allowed": False,
        },
    }
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return console.Profile(path)


@pytest.mark.parametrize(
    "key,value",
    [("appId", "1;bad"), ("appId", True), ("expectedFiles", ["../escape"]), ("officialClient", True)],
)
def test_source_is_a_bounded_depot_policy(key: str, value: Any) -> None:
    with pytest.raises(ValueError):
        console.source_identity({**source(), key: value})


def test_manifest_remains_an_exact_uint64_string() -> None:
    value = source()
    assert console.source_identity(value) == (123, 789, "3512319404653808464")
    value["depots"] = [{"id": 789, "manifest": 3512319404653808464}]
    with pytest.raises(ValueError):
        console.source_identity(value)


def test_profile_client_and_profile_bytes_are_bound(profile: console.Profile) -> None:
    (profile.home / "client.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes changed"):
        profile.check_client()
    with pytest.raises(ValueError, match="profile changed"):
        console.Profile(profile.path, "0" * 64)


def test_completion_path_identity_and_real_file_hash(profile: console.Profile) -> None:
    root = profile.home / ".steam/debian-installation/ubuntu12_32/steamapps/content/app_123/depot_789"
    root.mkdir(parents=True)
    (root / "game.bin").write_bytes(b"unit-game")
    signal: dict[str, Any] = {
        "phase": "complete",
        "count": 1,
        "echoes": 1,
        "failures": 0,
        "manifest": "3512319404653808464",
        "path": "/home/steamprobe/" + root.relative_to(profile.home).as_posix(),
    }
    assert console.completion_source(signal, profile.home, source()) == root
    mixed = signal["path"].replace("/steamapps/", "\\steamapps\\").replace("/content/", "\\content\\")
    assert console.completion_source({**signal, "path": mixed}, profile.home, source()) == root
    with pytest.raises(RuntimeError):
        console.completion_source(
            {**signal, "path": "/home/steamprobe/x\\..\\steamapps/content/app_123/depot_789"},
            profile.home,
            source(),
        )
    for key, value in [
        ("phase", "waiting"),
        ("count", 2),
        ("failures", 1),
        ("manifest", "wrong"),
        ("path", "/outside/steamapps/content/app_123/depot_789"),
    ]:
        with pytest.raises((RuntimeError, ValueError)):
            console.completion_source({**signal, key: value}, profile.home, source())
    (root / "game.bin").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="identity"):
        console.completion_source(signal, profile.home, source())


def test_loopback_rejection_happens_before_api_access() -> None:
    header = "  sl  local_address rem_address st\n"
    assert console.loopback_ready(header + "0: 0100007F:1F90 00000000:0000 0A\n", header)
    with pytest.raises(RuntimeError, match="loopback"):
        console.loopback_ready(header + "0: 00000000:1F90 00000000:0000 0A\n", header)


def test_pending_request_never_launches_or_repeats(
    profile: console.Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = profile.root / "destination"
    destination.mkdir()
    (destination / "official-console-request-v1.json").write_text("{}")
    monkeypatch.setattr(console, "Client", lambda p: pytest.fail("Must not launch or resend"))
    with pytest.raises(RuntimeError, match="unresolved"):
        console.acquire(source(), profile.session("unit"), destination, lambda *_: None)


def test_marker_requires_normal_exit_and_cache_hit_never_launches(
    profile: console.Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = profile.home / "steamapps/content/app_123/depot_789"
    root.mkdir(parents=True)
    (root / "game.bin").write_bytes(b"unit-game")
    destination = profile.root / "destination"
    destination.mkdir()
    signal = {
        "phase": "complete",
        "count": 1,
        "echoes": 1,
        "failures": 0,
        "manifest": "3512319404653808464",
        "path": "/home/steamprobe/steamapps/content/app_123/depot_789",
    }
    events = []

    class Fake:
        def __init__(self, p: console.Profile) -> None:
            self.attempt = p.root / "attempts" / ("1" * 32)
            self.attempt.mkdir(parents=True)
            self.channel = self
            self.deadline = console.time.monotonic() + 1800

        def __enter__(self) -> Fake:
            return self

        def guard(self) -> bool:
            return True

        def evaluate(self, expression: str) -> dict[str, Any]:
            events.append(expression)
            return {"issued": True} if "ExecCommand" in expression else signal

        def __exit__(self, *args: object) -> None:
            assert not (destination / "official-console-source-v1.json").exists()
            events.append("normal-exit")
            console.write_new(
                self.attempt / "shutdown.json",
                {"normal": True, "forced": False, "exitCode": 0, "ipcResult": 0},
            )

    monkeypatch.setattr(console, "Client", Fake)
    session = profile.session("unit")
    console.acquire(source(), session, destination, lambda *_: None)
    assert events[-1] == "normal-exit"
    assert sum("ExecCommand" in event for event in events) == 1
    assert (destination / "official-console-source-v1.json").is_file()
    monkeypatch.setattr(console, "Client", lambda p: pytest.fail("Verified cache must not relaunch"))
    console.acquire(source(), session, destination, lambda *_: None)


def test_cleanup_checks_ownership_without_requiring_the_failed_policy(
    profile: console.Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = console.Client(profile)
    value = {"Config": {"Labels": {"org.rhenium.steam.preparation": profile.identifier}}}
    monkeypatch.setattr(client, "docker", lambda *args, **kwargs: json.dumps([value]))
    assert client.inspect(policy=False) == value
    value["Config"]["Labels"]["org.rhenium.steam.preparation"] = "someone-else"
    with pytest.raises(RuntimeError, match="unowned"):
        client.inspect(policy=False)


def test_provider_routes_opaque_backend_without_a_fabricated_helper_token(
    profile: console.Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SteamAuthProvider()
    session = profile.session("unit")
    assert "refreshToken" not in session.secret
    monkeypatch.setenv("RHENIUM_STEAM_OFFICIAL_PROFILE", str(profile.path))
    monkeypatch.setattr(console, "login", lambda path, alias, progress: session)
    monkeypatch.setattr(console, "validate", lambda value: session)
    monkeypatch.setattr(console, "acquire", lambda *args: session)
    monkeypatch.setattr(
        provider, "helper", SimpleNamespace(invoke=lambda *args, **kw: pytest.fail("helper used"))
    )
    assert provider.login("unit", challenge=lambda _: None, progress=lambda *_: None) == session
    assert provider.validate(session) == session
    assert provider.acquire(source(), session, profile.root / "out", progress=lambda *_: None) == session


@pytest.mark.parametrize("failure", [None, "missing_response", "forced", "exit_code", "ipc", "completion"])
def test_recorded_completion_recovery_requires_full_proof_and_never_relaunches(
    profile: console.Profile,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    destination = profile.root / "resume"
    destination.mkdir()
    attempt_id = "a" * 32
    attempt = profile.root / "attempts" / attempt_id
    attempt.mkdir(parents=True)
    request = {
        "sourceSha256": console.fingerprint(source()),
        "profileId": profile.identifier,
        "attempt": attempt_id,
        "source": source(),
    }
    console.write_new(destination / "official-console-request-v1.json", request)
    console.write_new(attempt / "depot-request.json", request)
    if failure != "missing_response":
        console.write_new(attempt / "issue-response.json", {"issued": True})
    cleanup = {
        "normal": True,
        "forced": failure == "forced",
        "exitCode": 1 if failure == "exit_code" else 0,
        "ipcResult": 1 if failure == "ipc" else 0,
    }
    console.write_new(attempt / "shutdown.json", cleanup)
    complete = {
        "phase": "complete",
        "count": 2 if failure == "completion" else 1,
        "echoes": 1,
        "failures": 0,
        "manifest": "3512319404653808464",
        "path": "/home/steamprobe/ubuntu12_32\\steamapps\\content\\app_123\\depot_789",
    }
    console.write_new(attempt / "depot-completion.json", complete)
    game = profile.home / "ubuntu12_32/steamapps/content/app_123/depot_789/game.bin"
    game.parent.mkdir(parents=True)
    game.write_bytes(b"unit-game")
    monkeypatch.setattr(console, "Client", lambda _: pytest.fail("Recovery must never launch or resend"))
    if failure:
        with pytest.raises((RuntimeError, ValueError)):
            console.acquire(source(), profile.session("unit"), destination, lambda *_: None)
        assert not (destination / "official-console-source-v1.json").exists()
        assert not (destination / "game.bin").exists()
    else:
        console.acquire(source(), profile.session("unit"), destination, lambda *_: None)
        marker = json.loads((destination / "official-console-source-v1.json").read_text())
        assert marker["reconciledFromRecordedCompletion"] is True
        assert marker["commandCount"] == 1
        assert (destination / "game.bin").read_bytes() == b"unit-game"


def cache_reuse_fixture(profile: console.Profile) -> tuple[Path, Path, Path]:
    prior = profile.root / "cache/providers/steam" / ("a" * 64)
    destination = prior.with_name("b" * 64)
    prior.mkdir(parents=True)
    destination.mkdir()
    for letter, cache, normal in (("a", prior, True), ("b", destination, False)):
        attempt = profile.root / "attempts" / (letter * 32)
        attempt.mkdir(parents=True)
        request = {
            "sourceSha256": console.fingerprint(source()),
            "profileId": profile.identifier,
            "attempt": attempt.name,
            "source": source(),
        }
        console.write_new(cache / "official-console-request-v1.json", request)
        console.write_new(attempt / "depot-request.json", request)
        console.write_new(attempt / "issue-response.json", {"issued": True})
        console.write_new(
            attempt / "shutdown.json",
            {"normal": normal, "forced": not normal, "exitCode": 0 if normal else 143, "ipcResult": 0},
        )
        console.write_new(
            attempt / "depot-completion.json",
            {
                "phase": "complete",
                "count": 1,
                "echoes": 1,
                "failures": 0,
                "manifest": "3512319404653808464",
                "path": "/home/steamprobe/steamapps/content/app_123/depot_789",
            },
        )
    game = profile.home / "steamapps/content/app_123/depot_789/game.bin"
    game.parent.mkdir(parents=True)
    game.write_bytes(b"unit-game")
    request = json.loads((prior / "official-console-request-v1.json").read_text())
    console.publish_source(profile, source(), request, prior, reconciled=False)
    return prior, destination, profile.root / "attempts" / ("a" * 32) / "shutdown.json"


def test_explicit_cache_reuse_keeps_failed_request_and_uses_complete_prior_proof(
    profile: console.Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rhenium_steam import official_cache

    prior, destination, _ = cache_reuse_fixture(profile)
    pending = destination / "official-console-request-v1.json"
    before = pending.read_bytes()
    monkeypatch.setattr(console, "Client", lambda _: pytest.fail("Reuse must never launch or resend"))
    official_cache.create(profile, prior, destination)
    console.acquire(source(), profile.session("unit"), destination, lambda *_: None)
    assert pending.read_bytes() == before
    assert not (destination / "official-console-source-v1.json").exists()
    receipt = json.loads((destination / official_cache.NAME).read_text())
    assert receipt["failedAttemptPromoted"] is False and receipt["newDownloadCommands"] == 0
    assert receipt["priorProof"]["attempt"] == "a" * 32


@pytest.mark.parametrize("defect", ["prior_exit", "prior_bytes", "reused_bytes", "pending", "receipt"])
def test_cache_reuse_rechecks_all_provenance_and_bytes(
    profile: console.Profile,
    defect: str,
) -> None:
    from rhenium_steam import official_cache

    prior, destination, shutdown = cache_reuse_fixture(profile)
    official_cache.create(profile, prior, destination)
    if defect == "prior_exit":
        value = json.loads(shutdown.read_text())
        value["normal"] = False
        shutdown.write_text(json.dumps(value))
    elif defect == "prior_bytes":
        (prior / "game.bin").write_bytes(b"drift")
    elif defect == "reused_bytes":
        (destination / "game.bin").write_bytes(b"drift")
    elif defect == "pending":
        (destination / "official-console-request-v1.json").write_text("{}")
    else:
        (prior / "official-console-source-v1.json").write_text("{}")
    with pytest.raises((ValueError, RuntimeError)):
        official_cache.verify(profile, source(), destination)


def test_cache_reuse_refuses_unresolved_client_and_external_paths(profile: console.Profile) -> None:
    from rhenium_steam import official_cache

    prior, destination, _ = cache_reuse_fixture(profile)
    (profile.root / "attempts" / ("b" * 32) / "shutdown.json").unlink()
    with pytest.raises(OSError):
        official_cache.create(profile, prior, destination)
    assert not (destination / "game.bin").exists()
    with pytest.raises(ValueError, match="provider-owned"):
        official_cache.bounded_cache(profile.home)
