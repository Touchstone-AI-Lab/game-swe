from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rhenium_steam.official_client import OfficialClientBootstrap
from rhenium_steam.provider import SteamAuthProvider, SteamHelper, SteamHelperError

LOGIN_USERS = '"users"\n{\n\t"76561190000000000"\n\t{\n\t\t"AccountName"\t\t"alice"\n\t}\n}\n'


def _helper(tmp_path: Path) -> Path:
    helper = tmp_path / "helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        "request = json.loads(sys.stdin.readline())\n"
        "if request['command'] == 'login':\n"
        " print(json.dumps({'type':'challenge','uri':'fake://qr'}), flush=True)\n"
        "elif request['command'] == 'acquire':\n"
        " print(json.dumps({'type':'progress','value':5,'phase':'validated'}), flush=True)\n"
        " pathlib.Path(request['destination'], 'downloaded').write_text('ok')\n"
        " pathlib.Path(request['destination'], 'request.json').write_text(\n"
        "  json.dumps(request['source']))\n"
        "value={'principal':'alice','refreshToken':'secret','guardData':'guard'}\n"
        "print(json.dumps({'type':'result','value':value}), flush=True)\n",
        encoding="utf-8",
    )
    helper.chmod(0o700)
    return helper


class StubClient(OfficialClientBootstrap):
    """Official client bootstrap that records calls instead of starting Docker."""

    def __init__(self, *, available: bool = True, home: Path | None = None) -> None:
        super().__init__(docker="")
        self._available = available
        self._home = home
        self.bootstrapped = False

    def availability(self) -> dict[str, Any]:
        if self._available:
            return {"available": True, "reason": ""}
        return {"available": False, "reason": "Docker CLI is not installed"}

    def bootstrap(self, client_home: Path, **_: Any) -> dict[str, Any]:
        self.bootstrapped = True
        home = self._home or client_home
        (home / "debian-installation/config").mkdir(parents=True, exist_ok=True)
        (home / "debian-installation/config/loginusers.vdf").write_text(
            LOGIN_USERS, encoding="utf-8"
        )
        return {"state": "ready", "offlineMode": True, "steamLinuxRuntime": True}


def _ready_session(tmp_path: Path, monkeypatch: Any) -> tuple[SteamAuthProvider, Any]:
    monkeypatch.setenv("RHENIUM_STEAM_HELPER", str(_helper(tmp_path)))
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "state"))
    provider = SteamAuthProvider(client=StubClient())
    session = provider.login(
        "default",
        challenge=lambda _item: None,
        progress=lambda _value, _phase: None,
    )
    return provider, session


def test_helper_session_uses_jsonl_pipe_without_returning_secret(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("RHENIUM_STEAM_HELPER", str(_helper(tmp_path)))  # type: ignore[attr-defined]
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "state"))  # type: ignore[attr-defined]
    provider = SteamAuthProvider(client=StubClient())
    challenges: list[str] = []
    session = provider.login(
        "default",
        challenge=lambda item: challenges.append(item.uri),
        progress=lambda _value, _phase: None,
    )

    assert challenges == ["fake://qr"]
    assert session.principal == "alice"
    assert session.secret == {"refreshToken": "secret", "guardData": "guard"}

    destination = tmp_path / "game"
    refreshed = provider.acquire(
        {"appId": 1, "depots": []},
        session,
        destination,
        progress=lambda _value, _phase: None,
    )
    assert (destination / "downloaded").read_text(encoding="utf-8") == "ok"
    assert refreshed.secret["refreshToken"] == "secret"


def test_login_also_authorizes_the_official_client_and_keeps_it_across_refresh(
    tmp_path: Path, monkeypatch: Any
) -> None:
    provider, session = _ready_session(tmp_path, monkeypatch)

    client = session.metadata["officialClient"]
    assert client["state"] == "ready"
    assert client["path"] == str(SteamAuthProvider.client_home("default"))
    assert "officialClient" not in session.secret
    assert provider.validate(session).metadata["officialClient"] == client


def test_login_progress_stays_monotonic_while_the_runtime_depots_download(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RHENIUM_STEAM_HELPER", str(_helper(tmp_path)))
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "state"))
    steps: list[tuple[int, str]] = []

    SteamAuthProvider(client=StubClient()).login(
        "default",
        challenge=lambda _item: None,
        progress=lambda value, phase: steps.append((value, phase)),
    )

    values = [value for value, _ in steps]
    assert values == sorted(values)
    # A depot's own percentage belongs in the phase, not in the login's percentage.
    assert [phase for _, phase in steps if "(5%)" in phase] == ["validated (5%)"] * 2


def test_login_records_why_the_official_client_was_not_prepared(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RHENIUM_STEAM_HELPER", str(_helper(tmp_path)))
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "state"))
    client = StubClient(available=False)
    phases: list[str] = []

    session = SteamAuthProvider(client=client).login(
        "default",
        challenge=lambda _item: None,
        progress=lambda _value, phase: phases.append(phase),
    )

    assert client.bootstrapped is False
    assert session.metadata["officialClient"] == {
        "state": "unavailable",
        "reason": "Docker CLI is not installed",
    }
    assert session.secret["refreshToken"] == "secret"
    assert any("official Steam client unavailable" in phase for phase in phases)


def test_acquire_stages_the_official_client_without_leaking_the_flag_to_the_helper(
    tmp_path: Path, monkeypatch: Any
) -> None:
    provider, session = _ready_session(tmp_path, monkeypatch)
    destination = tmp_path / "source"

    provider.acquire(
        {"appId": 250900, "depots": [], "officialClient": True},
        session,
        destination,
        progress=lambda _value, _phase: None,
    )

    staged = destination / ".official-client" / "steam-home"
    assert (staged / "debian-installation/config/loginusers.vdf").is_file()
    assert json.loads((destination / "request.json").read_text(encoding="utf-8")) == {
        "appId": 250900,
        "depots": [],
    }


def test_acquire_fails_closed_when_the_official_client_is_missing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RHENIUM_STEAM_HELPER", str(_helper(tmp_path)))
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "state"))
    client = StubClient(available=False)
    provider = SteamAuthProvider(client=client)
    session = provider.login(
        "default", challenge=lambda _item: None, progress=lambda _value, _phase: None
    )

    with pytest.raises(SteamHelperError, match="official Steam client"):
        provider.acquire(
            {"appId": 250900, "depots": [], "officialClient": True},
            session,
            tmp_path / "source",
            progress=lambda _value, _phase: None,
        )


def test_platform_matrix_includes_windows_linux_and_macos(monkeypatch: object) -> None:
    combinations = {
        ("Windows", "AMD64"): "win-x64",
        ("Linux", "x86_64"): "linux-x64",
        ("Darwin", "arm64"): "osx-arm64",
    }
    for (system, machine), expected in combinations.items():
        monkeypatch.setattr("platform.system", lambda value=system: value)  # type: ignore[attr-defined]
        monkeypatch.setattr("platform.machine", lambda value=machine: value)  # type: ignore[attr-defined]
        assert SteamHelper.platform_id() == expected


def _failing_helper(tmp_path: Path) -> Path:
    """A helper that reports a failed sign-in the way the real one does."""
    helper = tmp_path / "failing-helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "sys.stdin.readline()\n"
        "print('Failed to poll status with result FileNotFound.', file=sys.stderr, flush=True)\n"
        "print(json.dumps({'type':'error','message':'Steam QR login failed'}), flush=True)\n",
        encoding="utf-8",
    )
    helper.chmod(0o700)
    return helper


def test_failed_login_reports_the_helper_reason_and_how_to_retry(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RHENIUM_STEAM_HELPER", str(_failing_helper(tmp_path)))
    monkeypatch.setenv("RHENIUM_STATE_DIR", str(tmp_path / "state"))

    with pytest.raises(SteamHelperError) as error:
        SteamAuthProvider(client=StubClient()).login(
            "default", challenge=lambda _item: None, progress=lambda _value, _phase: None
        )

    message = str(error.value)
    assert "Steam QR login failed" in message
    # The helper's own diagnosis otherwise reaches only its stderr log.
    assert "FileNotFound" in message
    assert "scan the newest code" in message
