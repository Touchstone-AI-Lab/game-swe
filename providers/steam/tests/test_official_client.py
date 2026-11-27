from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_steam.official_client import (
    LINUX_RUNTIMES,
    OfficialClientBootstrap,
    OfficialClientError,
)

LOGIN_USERS = '"users"\n{\n\t"76561190000000000"\n\t{\n\t\t"AccountName"\t\t"alice"\n'
LOGIN_USERS += '\t\t"RememberPassword"\t\t"1"\n\t\t"WantsOfflineMode"\t\t"0"\n'
LOGIN_USERS += '\t\t"SkipOfflineModeWarning"\t\t"0"\n\t}\n}\n'
LIBRARY_FOLDERS = '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"/home/azureuser"\n'
LIBRARY_FOLDERS += '\t\t"apps"\n\t\t{\n\t\t\t"250900"\t\t"615390763"\n\t\t}\n\t}\n}\n'


class FakeDocker:
    """Stand in for the Docker CLI and for the client running inside the container."""

    def __init__(self, *, sign_in_after: int = 2) -> None:
        self.calls: list[list[str]] = []
        self.client_home: Path | None = None
        self.session_dir: Path | None = None
        self.running = False
        self.ticks = 0
        self.sign_in_after = sign_in_after
        self.show_qr_at = 1
        self.clear_qr_at = 0

    def __call__(self, arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        self.calls.append(arguments)
        command = arguments[1]
        if command == "run":
            for index, value in enumerate(arguments):
                if value == "--mount" and "target=/home/azureuser/.steam" in arguments[index + 1]:
                    self.client_home = Path(arguments[index + 1].split("source=")[1].split(",")[0])
                if value == "--mount" and "target=/shots" in arguments[index + 1]:
                    self.session_dir = Path(arguments[index + 1].split("source=")[1].split(",")[0])
            assert self.client_home and self.session_dir
            (self.client_home / "debian-installation/config").mkdir(parents=True, exist_ok=True)
            self.running = True
            return self._ok("container")
        if command == "inspect":
            return self._ok("true" if self.running else "false")
        if command == "exec":
            if "-shutdown" in arguments:
                self.running = False
            return self._ok("")
        if command == "image":
            return self._ok("sha256:" + "a" * 64)
        return self._ok("")

    def tick(self, _seconds: float) -> None:
        """Advance the simulated client: show a QR code, then complete the sign-in."""
        self.ticks += 1
        assert self.session_dir is not None and self.client_home is not None
        if self.ticks == self.show_qr_at:
            (self.session_dir / "qr.txt").write_text("https://s.team/q/1/abc123", encoding="utf-8")
        if self.ticks == self.clear_qr_at:
            (self.session_dir / "qr.txt").write_text("", encoding="utf-8")
        if self.ticks == self.sign_in_after:
            logins = self.client_home / "debian-installation/config/loginusers.vdf"
            logins.write_text(LOGIN_USERS, encoding="utf-8")

    @staticmethod
    def _ok(stdout: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout, "")


def _bootstrap(docker: FakeDocker, **kwargs: Any) -> OfficialClientBootstrap:
    return OfficialClientBootstrap(
        docker="docker",
        apparmor_profile="steam-test-profile",
        runner=docker,
        sleep=docker.tick,
        clock=lambda: float(docker.ticks),
        **kwargs,
    )


def test_bootstrap_shows_a_qr_code_then_enables_offline_mode(tmp_path: Path) -> None:
    docker = FakeDocker()
    client_home = tmp_path / "official-client"
    challenges: list[str] = []

    metadata = _bootstrap(docker).bootstrap(
        client_home,
        challenge=lambda item: challenges.append(item.uri),
        progress=lambda _value, _phase: None,
        login_timeout=30.0,
        settle_timeout=30.0,
    )

    assert challenges == ["https://s.team/q/1/abc123"]
    assert metadata == {"state": "ready", "offlineMode": True}
    logins = (client_home / "debian-installation/config/loginusers.vdf").read_text(encoding="utf-8")
    assert '"WantsOfflineMode"\t\t"1"' in logins
    assert '"SkipOfflineModeWarning"\t\t"1"' in logins
    assert docker.calls[-1][:3] == ["docker", "rm", "--force"]
    run = next(call for call in docker.calls if call[:2] == ["docker", "run"])
    # Steam's runtime needs nested user/mount namespaces; keep capabilities dropped and use
    # the explicitly selected AppArmor profile rather than disabling AppArmor entirely.
    assert "--cap-drop=ALL" in run
    assert "--security-opt=no-new-privileges:true" in run
    assert "seccomp=unconfined" in run
    assert "apparmor=steam-test-profile" in run


def test_bootstrap_reuses_a_client_that_is_already_signed_in(tmp_path: Path) -> None:
    docker = FakeDocker()
    client_home = tmp_path / "official-client"
    logins = client_home / "debian-installation/config/loginusers.vdf"
    logins.parent.mkdir(parents=True)
    logins.write_text(LOGIN_USERS, encoding="utf-8")

    metadata = _bootstrap(docker).bootstrap(
        client_home,
        challenge=lambda _item: None,
        progress=lambda _value, _phase: None,
        login_timeout=30.0,
        settle_timeout=30.0,
    )

    assert metadata == {"state": "ready", "offlineMode": True}
    assert docker.calls == []
    assert '"WantsOfflineMode"\t\t"1"' in logins.read_text(encoding="utf-8")


def test_bootstrap_reports_the_client_download_before_the_first_qr(tmp_path: Path) -> None:
    docker = FakeDocker(sign_in_after=4)
    docker.show_qr_at = 3
    bootstrap = OfficialClientBootstrap(
        docker="docker",
        runner=docker,
        sleep=docker.tick,
        # One simulated minute per poll, so the download report is due immediately.
        clock=lambda: docker.ticks * 60.0,
    )
    phases: list[str] = []

    bootstrap.bootstrap(
        tmp_path / "official-client",
        challenge=lambda _item: None,
        progress=lambda _value, phase: phases.append(phase),
        login_timeout=3600.0,
        settle_timeout=600.0,
    )

    assert any("still downloading itself" in phase for phase in phases)


def test_bootstrap_reports_that_the_qr_code_was_scanned(tmp_path: Path) -> None:
    docker = FakeDocker(sign_in_after=6)
    docker.clear_qr_at = 2
    bootstrap = OfficialClientBootstrap(
        docker="docker",
        runner=docker,
        sleep=docker.tick,
        clock=lambda: docker.ticks * 60.0,
    )
    phases: list[str] = []

    bootstrap.bootstrap(
        tmp_path / "official-client",
        challenge=lambda _item: None,
        progress=lambda _value, phase: phases.append(phase),
        login_timeout=3600.0,
        settle_timeout=600.0,
    )

    assert any("waiting for the client to finish signing in" in phase for phase in phases)


def test_stage_linux_runtimes_installs_the_pinned_depots_once(tmp_path: Path) -> None:
    client_home = tmp_path / "official-client"
    requested: list[dict[str, Any]] = []

    def download(destination: Path, source: dict[str, Any]) -> None:
        requested.append(source)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "run").write_text("#!/bin/sh\necho scout\n", encoding="utf-8")
        (destination / "notes.txt").write_text("not executable", encoding="utf-8")
        (destination / "pressure-vessel").write_bytes(b"\x7fELF\x02\x01payload")
        for entry in destination.iterdir():
            entry.chmod(0o644)

    bootstrap = OfficialClientBootstrap(docker="docker")
    staged = bootstrap.stage_linux_runtimes(client_home, download, progress=lambda _v, _p: None)

    steamapps = client_home / "debian-installation/steamapps"
    assert staged is True
    # Scout starts every native Linux game and itself runs inside soldier.
    assert [source["appId"] for source in requested] == [1070560, 1391110]
    for runtime in LINUX_RUNTIMES:
        manifest = (steamapps / f"appmanifest_{runtime.app}.acf").read_text(encoding="utf-8")
        target = steamapps / "common" / runtime.directory
        assert '"StateFlags"\t\t"4"' in manifest
        assert runtime.manifest in manifest
        assert runtime.build in manifest
        # Depot downloads arrive without execute bits, which the entry points need.
        assert target.joinpath("run").stat().st_mode & 0o111
        assert target.joinpath("pressure-vessel").stat().st_mode & 0o111
        assert not target.joinpath("notes.txt").stat().st_mode & 0o111

    assert bootstrap.stage_linux_runtimes(client_home, download, progress=lambda _v, _p: None)
    assert len(requested) == 2


def test_stage_linux_runtimes_records_them_in_the_library_index(tmp_path: Path) -> None:
    client_home = tmp_path / "official-client"
    steamapps = client_home / "debian-installation/steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "libraryfolders.vdf").write_text(LIBRARY_FOLDERS, encoding="utf-8")

    def download(destination: Path, _source: dict[str, Any]) -> None:
        (destination / "run").write_text("#!/bin/sh\n", encoding="utf-8")

    OfficialClientBootstrap(docker="docker").stage_linux_runtimes(
        client_home, download, progress=lambda _v, _p: None
    )

    library = (steamapps / "libraryfolders.vdf").read_text(encoding="utf-8")
    for runtime in LINUX_RUNTIMES:
        assert f'\t\t\t"{runtime.app}"\t\t"{runtime.size}"' in library
    # An app the client installed itself stays in the index.
    assert '"250900"\t\t"615390763"' in library
    assert library.endswith("\t}\n}\n")


def test_stage_linux_runtimes_reports_an_empty_download(tmp_path: Path) -> None:
    bootstrap = OfficialClientBootstrap(docker="docker")

    staged = bootstrap.stage_linux_runtimes(
        tmp_path / "official-client",
        lambda destination, _source: destination.mkdir(parents=True, exist_ok=True),
        progress=lambda _v, _p: None,
    )

    assert staged is False


def test_bootstrap_fails_closed_when_the_operator_never_signs_in(tmp_path: Path) -> None:
    docker = FakeDocker(sign_in_after=100)

    with pytest.raises(OfficialClientError, match="not authorized"):
        _bootstrap(docker).bootstrap(
            tmp_path / "official-client",
            challenge=lambda _item: None,
            progress=lambda _value, _phase: None,
            login_timeout=5.0,
            settle_timeout=5.0,
        )
    assert docker.calls[-1][:3] == ["docker", "rm", "--force"]


def test_availability_reports_unsupported_hosts(monkeypatch: Any) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    assert OfficialClientBootstrap(docker="").availability() == {
        "available": False,
        "reason": "Docker CLI is not installed",
    }

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    result = OfficialClientBootstrap(docker="docker").availability()
    assert result["available"] is False
    assert "Linux x86_64" in result["reason"]


def test_stage_copies_client_state_and_rejects_incomplete_state(tmp_path: Path) -> None:
    client_home = tmp_path / "official-client"
    (client_home / "debian-installation/config").mkdir(parents=True)
    destination = tmp_path / "source"
    destination.mkdir()

    with pytest.raises(OfficialClientError, match="incomplete"):
        OfficialClientBootstrap.stage(client_home, destination)

    (client_home / "debian-installation/config/loginusers.vdf").write_text(
        LOGIN_USERS, encoding="utf-8"
    )
    staged = OfficialClientBootstrap.stage(client_home, destination)

    assert staged == destination / ".official-client" / "steam-home"
    assert (staged / "debian-installation/config/loginusers.vdf").is_file()
