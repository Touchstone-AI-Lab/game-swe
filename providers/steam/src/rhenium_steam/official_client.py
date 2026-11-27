"""Headless bootstrap of the official Steam client for DRM-protected runtimes.

Licensed depots are acquired with the Steam helper, but a game that keeps Steam DRM also needs
a logged-in official Steam client that can start it with no network. That client cannot be
produced from the helper session: it authenticates as its own Steam device, so it needs its own
QR scan. This module runs it headlessly in a disposable container and keeps the resulting client
state beside the provider session, where it is as secret-bearing as the refresh token itself.
"""

from __future__ import annotations

import contextlib
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any, NamedTuple

from rhenium.core.auth import AuthChallenge

# The image bakes in the operator's uid/gid (see steam-client.Dockerfile), so the tag has to
# carry them too -- otherwise two accounts sharing one Docker daemon silently overwrite each
# other's image and the second one inherits a home directory it cannot write.
IMAGE_NAME = "rhenium-steam-client"
IMAGE_VERSION = "0.1.0"
IMAGE_TAG = f"{IMAGE_NAME}:{IMAGE_VERSION}-uid{os.getuid()}-gid{os.getgid()}"
CLIENT_HOME = "/home/azureuser"
CLIENT_INSTALLATION = "debian-installation"
# Steam Linux Runtime, staged from pinned depots. Every native Linux game starts through
# scout, and scout itself runs inside soldier ("require_tool_appid" in its tool manifest).
# The client downloads both only while it launches such a game, which an offline evaluation
# cannot do, so they are acquired from their depots instead.


class LinuxRuntime(NamedTuple):
    app: str
    depot: str
    manifest: str
    build: str
    size: int
    directory: str
    name: str

    @property
    def source(self) -> dict[str, Any]:
        return {
            "kind": "steam-depots",
            "appId": int(self.app),
            "os": "linux",
            "depots": [{"id": int(self.depot), "manifest": self.manifest}],
        }


LINUX_RUNTIMES = (
    LinuxRuntime(
        app="1070560",
        depot="1070561",
        manifest="4956520704156364317",
        build="23825428",
        size=222685392,
        directory="SteamLinuxRuntime",
        name="Steam Linux Runtime 1.0 (scout)",
    ),
    LinuxRuntime(
        app="1391110",
        depot="1391111",
        manifest="2977690073285208032",
        build="24599738",
        size=676965917,
        directory="SteamLinuxRuntime_soldier",
        name="Steam Linux Runtime 2.0 (soldier)",
    ),
)
# How often to report that the client is still downloading itself before its first QR code.
DOWNLOAD_REPORT_SECONDS = 60.0
_QR_PATTERN = re.compile(r"^https://s\.team/q/[0-9A-Za-z/_%-]+$")
_LOGIN_MARKER = '"AccountName"'

CommandRunner = Callable[[list[str], float], "subprocess.CompletedProcess[str]"]


class OfficialClientError(RuntimeError):
    """The official Steam client bootstrap could not complete."""


def _current_apparmor_profile() -> str:
    """Reuse a named host profile so restricted hosts can allow nested user namespaces."""
    try:
        label = Path("/proc/self/attr/current").read_text(encoding="utf-8").strip()
    except OSError:
        return "unconfined"
    match = re.fullmatch(r"(.+?) \((?:unconfined|enforce|complain|kill)\)", label)
    if match and match.group(1) != "unconfined":
        return match.group(1)
    return "unconfined"


class OfficialClientBootstrap:
    """Produce a logged-in, offline-capable official Steam client home directory."""

    def __init__(
        self,
        *,
        docker: str | None = None,
        apparmor_profile: str | None = None,
        runner: CommandRunner | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.docker = (shutil.which("docker") or "") if docker is None else docker
        self.apparmor_profile = (
            apparmor_profile
            or os.environ.get("RHENIUM_STEAM_APPARMOR_PROFILE", "").strip()
            or _current_apparmor_profile()
        )
        self._runner = runner or self._subprocess_runner
        self._sleep = sleep
        self._clock = clock

    @staticmethod
    def _subprocess_runner(arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(arguments, check=False, capture_output=True, text=True, timeout=timeout)

    def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if not self.docker:
            raise OfficialClientError("Docker CLI is not installed")
        return self._runner([self.docker, *arguments], timeout)

    def availability(self) -> dict[str, Any]:
        """Report whether this host can run the bootstrap, without starting anything."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        if system != "linux" or machine not in {"x86_64", "amd64"}:
            return {
                "available": False,
                "reason": "the official Steam client bootstrap requires a Linux x86_64 host",
            }
        if not self.docker:
            return {"available": False, "reason": "Docker CLI is not installed"}
        try:
            result = self._docker(["info", "--format", "{{.ServerVersion}}"], timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            return {"available": False, "reason": str(error)}
        if result.returncode != 0:
            return {"available": False, "reason": "Docker daemon is unavailable"}
        return {"available": True, "reason": "", "dockerVersion": result.stdout.strip()}

    def build_image(self) -> str:
        """Build the bootstrap image from the packaged assets and return its immutable ID."""
        assets = files("rhenium_steam") / "assets"
        with tempfile.TemporaryDirectory(prefix="rhenium-steam-client-") as context_value:
            context = Path(context_value)
            for name in ("steam-client.Dockerfile", "steam-client-session.sh"):
                (context / name).write_bytes((assets / name).read_bytes())
            (context / "steam-client-session.sh").chmod(0o755)
            result = self._docker(
                [
                    "build",
                    "--pull=false",
                    # The client home must be owned by, and its uid known to, the account the
                    # container runs as; see steam-client.Dockerfile.
                    "--build-arg",
                    f"HOST_UID={os.getuid()}",
                    "--build-arg",
                    f"HOST_GID={os.getgid()}",
                    "--file",
                    str(context / "steam-client.Dockerfile"),
                    "--tag",
                    IMAGE_TAG,
                    str(context),
                ],
                timeout=3600,
            )
        if result.returncode != 0:
            raise OfficialClientError("failed to build the Steam client image")
        identity = self._docker(["image", "inspect", IMAGE_TAG, "--format", "{{.Id}}"], timeout=30)
        if identity.returncode != 0 or not identity.stdout.strip():
            raise OfficialClientError("the Steam client image is unavailable after the build")
        return identity.stdout.strip()

    def bootstrap(
        self,
        client_home: Path,
        *,
        challenge: Callable[[AuthChallenge], None],
        progress: Callable[[int, str], None],
        login_timeout: float = 2700.0,
        settle_timeout: float = 600.0,
    ) -> dict[str, Any]:
        """Run the client until the operator has signed in, then leave it ready for offline use."""
        client_home.mkdir(parents=True, exist_ok=True)
        client_home.chmod(0o700)
        if _has_login(client_home / CLIENT_INSTALLATION / "config/loginusers.vdf"):
            # The client keeps its own long-lived sign-in, so a later helper login reuses it
            # instead of asking for a second scan. Delete the client home to sign in again.
            progress(70, "reusing the official Steam client that is already signed in")
            return self._finalize(client_home)
        session_dir = client_home.parent / "bootstrap"
        shutil.rmtree(session_dir, ignore_errors=True)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_dir.chmod(0o700)

        progress(5, "building the Steam client image")
        image_id = self.build_image()
        name = f"rhenium-steam-client-{uuid.uuid4().hex[:12]}"
        progress(20, "starting the official Steam client")
        started = self._docker(
            [
                "run",
                "--detach",
                "--rm",
                "--init",
                "--name",
                name,
                "--network=bridge",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                # The Steam runtime isolates games with bubblewrap, which the default seccomp
                # profile blocks. The client's own Chromium sandbox stays enabled.
                "--security-opt",
                "seccomp=unconfined",
                # Reuse the host process's named AppArmor profile. On hosts that restrict
                # unprivileged user namespaces, `apparmor=unconfined` can block the nested
                # user namespace Steam needs even though the host sysctl allows it. The
                # explicit override supports hosts where the current profile is unsuitable.
                "--security-opt",
                f"apparmor={self.apparmor_profile}",
                "--shm-size=1g",
                "--memory=8g",
                "--cpus=4",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--mount",
                # The client installs into $HOME/.steam, and that tree is what a game runtime
                # builder copies, so the operator's directory is mounted there directly.
                f"type=bind,source={client_home.resolve()},target={CLIENT_HOME}/.steam",
                "--mount",
                f"type=bind,source={session_dir.resolve()},target=/shots",
                "--env",
                f"HOME={CLIENT_HOME}",
                image_id,
                # No -silent: the client restarts itself after it self-updates, and a silent
                # restart leaves its sign-in window unmapped, so no QR code can be read.
                "-cef-disable-gpu",
                "-cef-force-opaque-backgrounds",
            ],
            timeout=120,
        )
        if started.returncode != 0:
            raise OfficialClientError("failed to start the Steam client container")
        try:
            self._await_login(
                client_home,
                session_dir,
                name,
                challenge=challenge,
                progress=progress,
                login_timeout=login_timeout,
            )
            progress(80, "saving the Steam client session")
            self._shutdown(name, settle_timeout)
        finally:
            with contextlib.suppress(OSError, subprocess.SubprocessError, OfficialClientError):
                self._docker(["rm", "--force", name], timeout=120)
            shutil.rmtree(session_dir, ignore_errors=True)
        metadata = self._finalize(client_home)
        progress(90, "official Steam client signed in and ready for offline use")
        return metadata

    def stage_linux_runtimes(
        self,
        client_home: Path,
        download: Callable[[Path, dict[str, Any]], None],
        *,
        progress: Callable[[int, str], None],
    ) -> bool:
        """Place the pinned Steam Linux Runtime in the client library.

        The client downloads these runtimes only while it launches a native Linux game, which
        an offline evaluation cannot do, so the depots are acquired here and recorded as
        installed. Returns whether every runtime is now present.
        """
        steamapps = client_home / CLIENT_INSTALLATION / "steamapps"
        complete = True
        for index, runtime in enumerate(LINUX_RUNTIMES):
            manifest = steamapps / f"appmanifest_{runtime.app}.acf"
            target = steamapps / "common" / runtime.directory
            if _fully_installed(manifest) and target.is_dir():
                continue
            progress(92 + index * 2, f"staging {runtime.name} ({runtime.size // 1_000_000} MB)")
            target.mkdir(parents=True, exist_ok=True)
            download(target, runtime.source)
            if not any(target.iterdir()):
                complete = False
                continue
            # Depot downloads do not carry POSIX execute bits, which the runtime entry points
            # need, so restore them from the file contents.
            _restore_execute_bits(target)
            manifest.write_text(_app_manifest(runtime), encoding="utf-8")
            _register_installed_app(steamapps, runtime)
        return complete

    def _await_login(
        self,
        client_home: Path,
        session_dir: Path,
        name: str,
        *,
        challenge: Callable[[AuthChallenge], None],
        progress: Callable[[int, str], None],
        login_timeout: float,
    ) -> None:
        logins = client_home / CLIENT_INSTALLATION / "config/loginusers.vdf"
        qr_file = session_dir / "qr.txt"
        deadline = self._clock() + login_timeout
        announced = ""
        waiting = False
        reported = self._clock()
        while self._clock() < deadline:
            if _has_login(logins):
                progress(70, "official Steam client signed in")
                return
            value = _read_text(qr_file).strip()
            if not value and self._clock() - reported >= DOWNLOAD_REPORT_SECONDS:
                reported = self._clock()
                if waiting:
                    # The QR code is gone, so it was scanned or it expired. Signing in takes
                    # another minute or two while the client loads the account.
                    progress(65, "the QR code is gone; waiting for the client to finish signing in")
                else:
                    # The client downloads itself before it can show a QR code, which takes a
                    # while on a slow link. Report movement so the wait is not read as a hang.
                    progress(
                        30,
                        "the Steam client is still downloading itself "
                        f"({_megabytes(client_home)} MB so far); its QR code follows",
                    )
            if value != announced and _QR_PATTERN.match(value):
                announced = value
                challenge(
                    AuthChallenge(
                        kind="qr",
                        uri=value,
                        message=(
                            "Scan with the Steam Mobile app to authorize the official Steam "
                            "client. This is a second, separate sign-in: the first QR code "
                            "authorized depot downloads, this one authorizes the client that "
                            "starts DRM-protected games offline."
                        ),
                    )
                )
                if not waiting:
                    waiting = True
                    progress(40, "waiting for the official Steam client QR scan")
            if not self._container_running(name):
                raise OfficialClientError(
                    "the Steam client container exited before sign-in" + self._exit_detail(name)
                )
            self._sleep(2)
        raise OfficialClientError("the official Steam client was not authorized before the timeout")

    def _exit_detail(self, name: str) -> str:
        """The container's own last words, for an exit that would otherwise be unexplained.

        The container runs with --rm, so Docker removes it the moment it exits and takes its
        logs with it. That is why this failure used to be reported with no cause at all. Read
        whatever is still readable and fold it into the error message.
        """
        try:
            logs = self._docker(["logs", "--tail", "20", name], timeout=30)
        except (OSError, subprocess.SubprocessError):
            return ""
        merged = f"{logs.stdout}\n{logs.stderr}".splitlines()
        tail = "\n".join(line for line in merged if line.strip())[-2000:]
        return f"; its last output was:\n{tail}" if tail else ""

    def _container_running(self, name: str) -> bool:
        result = self._docker(["inspect", "--format", "{{.State.Running}}", name], timeout=30)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _shutdown(self, name: str, settle_timeout: float) -> None:
        with contextlib.suppress(OSError, subprocess.SubprocessError, OfficialClientError):
            self._docker(
                ["exec", name, f"{CLIENT_HOME}/.steam/{CLIENT_INSTALLATION}/steam.sh", "-shutdown"],
                timeout=120,
            )
        deadline = self._clock() + settle_timeout
        while self._clock() < deadline:
            if not self._container_running(name):
                return
            self._sleep(2)

    @staticmethod
    def _finalize(client_home: Path) -> dict[str, Any]:
        installation = client_home / CLIENT_INSTALLATION
        for residue in ("steam.pid", "steam.pipe", "steam.token"):
            (client_home / residue).unlink(missing_ok=True)
        logins = installation / "config/loginusers.vdf"
        if not _has_login(logins):
            raise OfficialClientError("the official Steam client did not store a reusable sign-in")
        # "Go Offline" is a stored client preference; the -offline command line flag alone does
        # not stop the client from contacting Steam.
        text = logins.read_text(encoding="utf-8", errors="replace")
        for key in ("WantsOfflineMode", "SkipOfflineModeWarning"):
            text = re.sub(rf'("{key}"\s+)"0"', r'\1"1"', text)
        logins.write_text(text, encoding="utf-8")
        return {"state": "ready", "offlineMode": True}

    @staticmethod
    def stage(client_home: Path, destination: Path) -> Path:
        """Copy the client state into an acquired source tree for a game runtime builder."""
        if not _has_login(client_home / CLIENT_INSTALLATION / "config/loginusers.vdf"):
            raise OfficialClientError("the stored official Steam client state is incomplete")
        staged = destination / ".official-client" / "steam-home"
        shutil.rmtree(staged.parent, ignore_errors=True)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.parent.chmod(0o700)
        shutil.copytree(client_home, staged, symlinks=True)
        return staged


def _register_installed_app(steamapps: Path, runtime: LinuxRuntime) -> None:
    """Add a staged app to the library index the client reads when it starts.

    The client rebuilds this index from the app manifests too, but recording the app keeps
    the library consistent for a client that is never allowed to go online again.
    """
    path = steamapps / "libraryfolders.vdf"
    text = _read_text(path)
    block = re.search(
        r'"apps"\s*\n(?P<indent>[ \t]*)\{\n(?P<body>.*?)(?P=indent)\}', text, re.DOTALL
    )
    if not block:
        return
    entries = dict(re.findall(r'"(\d+)"\s+"(\d+)"', block.group("body")))
    entries[runtime.app] = str(runtime.size)
    indent = block.group("indent")
    rendered = "".join(
        f'{indent}\t"{app}"\t\t"{size}"\n' for app, size in sorted(entries.items())
    )
    path.write_text(
        text[: block.start("body")] + rendered + text[block.end("body") :],
        encoding="utf-8",
    )


def _app_manifest(runtime: LinuxRuntime) -> str:
    """Render the client's own installed-app record for a depot staged by Rhenium."""
    return "\n".join(
        [
            '"AppState"',
            "{",
            f'\t"appid"\t\t"{runtime.app}"',
            '\t"universe"\t\t"1"',
            f'\t"name"\t\t"{runtime.name}"',
            # StateFlags 4 is "fully installed", which is what stops the client from trying to
            # download the app when it starts a game with no network.
            '\t"StateFlags"\t\t"4"',
            f'\t"installdir"\t\t"{runtime.directory}"',
            f'\t"buildid"\t\t"{runtime.build}"',
            f'\t"TargetBuildID"\t\t"{runtime.build}"',
            f'\t"SizeOnDisk"\t\t"{runtime.size}"',
            '\t"AutoUpdateBehavior"\t\t"0"',
            '\t"InstalledDepots"',
            "\t{",
            f'\t\t"{runtime.depot}"',
            "\t\t{",
            f'\t\t\t"manifest"\t\t"{runtime.manifest}"',
            f'\t\t\t"size"\t\t"{runtime.size}"',
            "\t\t}",
            "\t}",
            "}",
            "",
        ]
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _has_login(logins: Path) -> bool:
    return _LOGIN_MARKER in _read_text(logins)


def _megabytes(directory: Path) -> int:
    total = 0
    for path in directory.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with contextlib.suppress(OSError):
                total += path.stat().st_size
    return total // (1024 * 1024)


def _restore_execute_bits(directory: Path) -> None:
    for path in directory.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        with contextlib.suppress(OSError):
            with path.open("rb") as handle:
                header = handle.read(4)
            if header.startswith((b"\x7fELF", b"#!")):
                path.chmod(path.stat().st_mode | 0o111)


def _fully_installed(manifest: Path) -> bool:
    return re.search(r'"StateFlags"\s+"4"', _read_text(manifest)) is not None
