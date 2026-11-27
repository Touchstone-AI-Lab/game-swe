from __future__ import annotations

import hashlib
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import (
    RuntimeActionRequired,
    RuntimeArtifact,
    RuntimeBuilder,
    RuntimeSpec,
)

from .catalog import IsaacCatalog
from .evaluator import DEFAULT_APPARMOR_PROFILE, VERIFIER_IMAGE, IsaacRuntime

CLIENT_INSTALLATION = "debian-installation"
CLIENT_HOME = "/home/azureuser"
ISAAC_APP = "250900"
ISAAC_APP_NAME = "The Binding of Isaac: Rebirth"
ISAAC_INSTALL_DIRECTORY = "The Binding of Isaac Rebirth"
ISAAC_DATA_DIRECTORY = "/home/azureuser/.local/share/binding of isaac afterbirth+"
PROFILE_IMAGE = "gcb-isaac-private-runtime:abp-v1.06.t1-profile"
# Creating, copying from and removing the profile container, and inspecting images, is
# bookkeeping, which a congested shared daemon can stretch to minutes; the evaluator gives the
# same operations 300 seconds.
_BOOKKEEPING_TIMEOUT = 300
_STATE_COPY_TIMEOUT = 3600
PROFILE_MARKER = re.compile(
    r"^\[GCB_PROFILE\] (?:steam_client_not_started|game_process_missing_after_launch|"
    r"options_ini_missing|profile_created|script_exit=\d+ line=\d+)$"
)
# Boots the pinned game once so it writes its own fresh options.ini. This single run is
# online because the game's DRM needs an app ownership ticket that only a signed-in client
# can fetch; the ticket is cached, and every later start, evaluation included, is offline.
PROFILE_SCRIPT = f"""
set -uo pipefail
trap 'profile_status=$?; echo "[GCB_PROFILE] script_exit=${{profile_status}} line=${{LINENO}}"' EXIT
export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 SDL_VIDEODRIVER=x11 GDK_BACKEND=x11
export XDG_RUNTIME_DIR=/tmp/steam-runtime-profile
install -d -m 0700 "$XDG_RUNTIME_DIR"
installation="$HOME/.steam/debian-installation"
steam="$installation/steam.sh"
data="{ISAAC_DATA_DIRECTORY}"
# The game's DRM asks Steam for an ownership ticket the client can only obtain online, so
# this one run signs in for real. The client caches the ticket, and every later start of
# the game, preparation's own and every evaluation, is offline.
sed -i 's/"WantsOfflineMode"\t\t"1"/"WantsOfflineMode"\t\t"0"/; \
  s/"SkipOfflineModeWarning"\t\t"1"/"SkipOfflineModeWarning"\t\t"0"/' \
  "$installation/config/loginusers.vdf"
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
for _ in $(seq 1 30); do xdotool getmouselocation >/dev/null 2>&1 && break; sleep 1; done
openbox >/tmp/openbox.log 2>&1 &
dbus-run-session -- "$steam" -silent -cef-disable-gpu -cef-force-opaque-backgrounds \
  >/tmp/steam.log 2>&1 &
for _ in $(seq 1 90); do pgrep -x steam >/dev/null 2>&1 && break; sleep 1; done
pgrep -x steam >/dev/null 2>&1 || {{ echo "[GCB_PROFILE] steam_client_not_started"; exit 20; }}
# A launch request sent right after the client comes up never starts the game: the client
# accepts it, registers a compatibility-tool session and then stalls it while it still logs
# on, registers the Steam Linux Runtime tools and checks for its own updates. Later requests
# for the same app are ignored while that session exists. So wait for the logon and the
# tool registrations, let the client settle, and only then send a single launch request.
connection="$installation/logs/connection_log.txt"
compat="$installation/logs/compat_log.txt"
for _ in $(seq 1 120); do
  grep -q "RecvMsgClientLogOnResponse() : processing complete" "$connection" 2>/dev/null && break
  sleep 1
done
for _ in $(seq 1 90); do
  grep -q "Posting tool registration callback 1070560" "$compat" 2>/dev/null \
    && grep -q "Posting tool registration callback 1391110" "$compat" 2>/dev/null && break
  sleep 1
done
sleep 60
"$steam" -applaunch {ISAAC_APP} >>/tmp/applaunch.log 2>&1 || true
for _ in $(seq 1 120); do pgrep -x isaac.x64 >/dev/null 2>&1 && break; sleep 1; done
if ! pgrep -x isaac.x64 >/dev/null 2>&1; then
  echo "the game has not started 120 s after the launch request; sending it once more"
  sleep 60
  "$steam" -applaunch {ISAAC_APP} >>/tmp/applaunch.log 2>&1 || true
  for _ in $(seq 1 120); do pgrep -x isaac.x64 >/dev/null 2>&1 && break; sleep 1; done
fi
pgrep -x isaac.x64 >/dev/null 2>&1 || echo "[GCB_PROFILE] game_process_missing_after_launch"
for _ in $(seq 1 240); do [ -f "$data/options.ini" ] && break; sleep 2; done
pkill -TERM -x isaac.x64 >/dev/null 2>&1 || true
sleep 3
"$steam" -shutdown >/dev/null 2>&1 || true
sleep 5
# Leave the client the way every later start expects to find it.
sed -i 's/"WantsOfflineMode"\t\t"0"/"WantsOfflineMode"\t\t"1"/; \
  s/"SkipOfflineModeWarning"\t\t"0"/"SkipOfflineModeWarning"\t\t"1"/' \
  "$installation/config/loginusers.vdf"
if [ ! -f "$data/options.ini" ]; then
  # Keep private Steam/session logs out of the operation error surfaced to the user.
  echo "[GCB_PROFILE] options_ini_missing"
  exit 21
fi
echo "[GCB_PROFILE] profile_created"
"""


def _directory_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


# Steam account IDs are the low 32 bits of a SteamID64 in the individual-account universe.
_STEAM_ID64_BASE = 76561197960265728


def _account_steam_id(steam_home: Path) -> str:
    """The SteamID64 of the signed-in account, taken from its client user directory."""
    userdata = steam_home / CLIENT_INSTALLATION / "userdata"
    accounts = (
        [entry.name for entry in userdata.iterdir() if entry.name.isdigit()]
        if userdata.is_dir()
        else []
    )
    if len(accounts) != 1:
        raise RuntimeError("the staged Steam client does not hold exactly one signed-in account")
    return str(_STEAM_ID64_BASE + int(accounts[0]))


def _install_record(spec: RuntimeSpec, size: int, owner: str) -> str:
    """Render the client's installed-app record for the depots staged by this builder.

    The client only launches an app it considers installed. Depots acquired by the provider
    carry no such record, so an offline launch fails with AppError_18 until it is written.
    """
    build = re.sub(r"\D", "", str(spec.version)) or "0"
    depots = spec.source.get("depots")
    if not isinstance(depots, list) or not depots:
        raise RuntimeError("Isaac runtime source declares no depots")
    lines = [
        '"AppState"',
        "{",
        f'\t"appid"\t\t"{ISAAC_APP}"',
        '\t"universe"\t\t"1"',
        f'\t"name"\t\t"{ISAAC_APP_NAME}"',
        # StateFlags 4 is "fully installed", which also stops the offline client from
        # trying to update the app it cannot reach.
        '\t"StateFlags"\t\t"4"',
        f'\t"installdir"\t\t"{ISAAC_INSTALL_DIRECTORY}"',
        f'\t"buildid"\t\t"{build}"',
        f'\t"TargetBuildID"\t\t"{build}"',
        f'\t"SizeOnDisk"\t\t"{size}"',
        '\t"StagingSize"\t\t"0"',
        # The offline client refuses to launch an app whose recorded owner is not the
        # account it is signed in as.
        f'\t"LastOwner"\t\t"{owner}"',
        '\t"AutoUpdateBehavior"\t\t"1"',
        '\t"AllowOtherDownloadsWhileRunning"\t\t"0"',
        '\t"ScheduledAutoUpdate"\t\t"0"',
        '\t"UpdateResult"\t\t"0"',
        '\t"InstalledDepots"',
        "\t{",
    ]
    for depot in depots:
        lines.extend(
            [
                f'\t\t"{depot["id"]}"',
                "\t\t{",
                f'\t\t\t"manifest"\t\t"{depot["manifest"]}"',
                "\t\t}",
            ]
        )
    lines.extend(["\t}", '\t"UserConfig"', "\t{", "\t}", '\t"MountedConfig"', "\t{", "\t}", "}", ""])
    return "\n".join(lines)


def _register_installed_app(steam_home: Path, spec: RuntimeSpec, game_dir: Path) -> None:
    """Record the staged game so the offline client can launch it."""
    steamapps = steam_home / "debian-installation/steamapps"
    steamapps.mkdir(parents=True, exist_ok=True)
    size = _directory_size(game_dir)
    (steamapps / f"appmanifest_{ISAAC_APP}.acf").write_text(
        _install_record(spec, size, _account_steam_id(steam_home)), encoding="utf-8"
    )
    library = steamapps / "libraryfolders.vdf"
    text = library.read_text(encoding="utf-8") if library.is_file() else ""
    block = re.search(
        r'"apps"\s*\n(?P<indent>[ \t]*)\{\n(?P<body>.*?)(?P=indent)\}', text, re.DOTALL
    )
    if not block:
        return
    entries = dict(re.findall(r'"(\d+)"\s+"(\d+)"', block.group("body")))
    entries[ISAAC_APP] = str(size)
    indent = block.group("indent")
    rendered = "".join(
        f'{indent}\t"{app}"\t\t"{value}"\n' for app, value in sorted(entries.items())
    )
    library.write_text(
        text[: block.start("body")] + rendered + text[block.end("body") :], encoding="utf-8"
    )


def _discard_staged_client_update(installation: Path) -> list[str]:
    """Drop a client update the online profile run downloaded but did not apply.

    The bootstrapper stages an update as a bare package manifest (``steam_client_<platform>``,
    no extension) beside the installed ``.manifest``. On the next start it insists on finishing
    that update, which a networkless evaluation cannot do, so the client shuts down and the game
    never launches. The installed client, whose state holds the cached ticket, stays as it is.
    """
    package = installation / "package"
    removed: list[str] = []
    for path in sorted(package.glob("steam_client_*")) if package.is_dir() else []:
        if "." not in path.name and path.is_file() and not path.is_symlink():
            path.unlink()
            removed.append(path.name)
    return removed


class IsaacRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: IsaacCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = IsaacRuntime(context)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        del spec
        status = self.runtime.status(probe_image=False)
        return {
            **status,
            "clientBootstrapRequired": True,
            "requirements": [
                "licensed official Steam Client bootstrap",
                "Xvfb and Docker on Linux",
                f"AppArmor profile {DEFAULT_APPARMOR_PROFILE} on native Linux when required",
            ],
        }

    def _docker(self, arguments: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return self.runtime._docker(arguments, timeout=timeout)

    def _create_profile(self, task_root: Path, steam_home: Path, isaac_data: Path) -> None:
        """Boot the pinned game once so it writes a zero-progression profile.

        This run signs the client in for real, which is the only way to obtain the ownership
        ticket the game's DRM demands. Only options.ini and the client state are kept.
        """
        library = steam_home / "debian-installation/steamapps/common"
        # The game starts through Steam Linux Runtime 1.0 (scout), which runs inside 2.0
        # (soldier); the Steam provider stages both from their pinned depots at login.
        missing = [
            str(library / name)
            for name in ("SteamLinuxRuntime", "SteamLinuxRuntime_soldier")
            if not (library / name).is_dir()
        ]
        if missing:
            raise RuntimeActionRequired(
                "steam-client-bootstrap",
                "Run 'rhenium auth login steam' again so the Steam Linux Runtime is installed",
                {
                    "stateRoot": str(steam_home.parent),
                    "requiredFiles": missing,
                    "cloudPolicy": "disabled",
                    "progressionPolicy": "fresh-zero-progress",
                },
            )
        isaac_data.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="rhenium-isaac-profile-") as empty:
            built = self._docker(
                [
                    "build",
                    "--pull=false",
                    "--build-context",
                    f"steam_home={steam_home}",
                    "--build-context",
                    f"isaac_data={empty}",
                    "--file",
                    str(task_root / "scripts/private-runtime.Dockerfile"),
                    "--tag",
                    PROFILE_IMAGE,
                    str(task_root / "scripts"),
                ],
                timeout=7200,
            )
        if built.returncode != 0:
            raise RuntimeError(
                "failed to build the Isaac profile runtime\n" + built.stderr[-8000:]
            )
        created = self._docker(
            [
                "create",
                "--name",
                f"rhenium-isaac-profile-{uuid.uuid4().hex[:12]}",
                # Only this preparation run has network, and only so the client can fetch
                # the app ownership ticket its offline launches need.
                "--network",
                "bridge",
                "--cpus",
                "4",
                "--memory",
                "8g",
                "--shm-size",
                "1g",
                "--security-opt",
                f"apparmor={DEFAULT_APPARMOR_PROFILE}",
                "--security-opt",
                "seccomp=unconfined",
                "-e",
                "GTK_A11Y=none",
                PROFILE_IMAGE,
                "bash",
                "-lc",
                PROFILE_SCRIPT,
            ],
            timeout=_BOOKKEEPING_TIMEOUT,
        )
        container = created.stdout.strip()
        if created.returncode != 0 or not container:
            raise RuntimeError("failed to create the Isaac profile container")
        try:
            started = self._docker(["start", "--attach", container], timeout=1800)
            if started.returncode != 0:
                markers = [
                    line.strip()[-240:]
                    for output in (started.stdout or "", started.stderr or "")
                    for line in output.splitlines()
                    if PROFILE_MARKER.fullmatch(line.strip())
                ]
                details = "; ".join(markers[-8:]) or "no safe diagnostic marker was emitted"
                raise RuntimeError(
                    f"the Isaac profile run failed (exit {started.returncode}); {details}"
                )
            copied = self._docker(
                [
                    "cp",
                    f"{container}:{ISAAC_DATA_DIRECTORY}/options.ini",
                    str((isaac_data / "options.ini").resolve()),
                ],
                timeout=_BOOKKEEPING_TIMEOUT,
            )
            if copied.returncode != 0 or not (isaac_data / "options.ini").is_file():
                raise RuntimeError("the Isaac profile run did not produce options.ini")
            # The client cached the app ownership ticket during this run; without carrying
            # that state back, every later offline launch fails the game's DRM check again.
            state = self._docker(
                [
                    "cp",
                    f"{container}:{CLIENT_HOME}/.steam/{CLIENT_INSTALLATION}/.",
                    str((steam_home / CLIENT_INSTALLATION).resolve()),
                ],
                # Several gigabytes of client and runtime files; a busy disk needs far longer
                # than ten minutes to copy them out.
                timeout=_STATE_COPY_TIMEOUT,
            )
            if state.returncode != 0:
                raise RuntimeError("could not preserve the signed-in Steam client state")
        finally:
            # Everything needed was copied out above. A shared daemon can take minutes to
            # remove the container's large writable layer; a slow removal is not a failure.
            with suppress(OSError, subprocess.SubprocessError):
                self._docker(["rm", "--force", container], timeout=_BOOKKEEPING_TIMEOUT)

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        fingerprint = spec.fingerprint(plugin_id="isaac-rebirth", plugin_version="0.6.0")
        # A controlled host can adopt an already validated private image without copying
        # credentials back into the repository or Rhenium database.
        existing = ""
        if not any(task.clean_room_synthetic for task in self.catalog.tasks):
            try:
                existing = self.runtime.image_id()
            except RuntimeError:
                existing = ""
        if existing:
            return RuntimeArtifact(
                runtime_key=f"isaac-rebirth/{spec.id}",
                fingerprint=fingerprint,
                kind="docker-image",
                identity=existing,
                metadata={"network": "none", "clientBootstrap": "external-adopted"},
            )

        steam_home = destination / "steam-home"
        isaac_data = destination / "isaac-data"
        game_dir = (
            steam_home
            / "debian-installation/steamapps/common/The Binding of Isaac Rebirth"
        )
        client = steam_home / "debian-installation/steam.sh"
        options = isaac_data / "options.ini"
        acquired_client = source / ".official-client" / "steam-home"
        if not client.is_file() and acquired_client.is_dir():
            progress(5, "staging the official Steam client state")
            steam_home.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(acquired_client, steam_home, symlinks=True)
        if not client.is_file():
            destination.mkdir(parents=True, exist_ok=True)
            raise RuntimeActionRequired(
                "steam-client-bootstrap",
                "Sign in to the official Steam Client with 'rhenium auth login steam'",
                {
                    "stateRoot": str(destination),
                    "requiredFiles": [str(client), str(options)],
                    "cloudPolicy": "disabled",
                    "progressionPolicy": "fresh-zero-progress",
                },
            )
        if not game_dir.exists():
            progress(10, "staging pinned Isaac depots into the isolated Steam library")
            game_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source, game_dir, ignore=shutil.ignore_patterns(".official-client")
            )
            # Depot downloads do not carry POSIX execute bits.
            for executable in ("isaac.x64", "isaac.i386", "run-x64.sh", "run-i386.sh"):
                candidate = game_dir / executable
                if candidate.is_file():
                    candidate.chmod(0o755)
        if not (game_dir / "isaac.x64").is_file():
            raise RuntimeError("managed Steam source does not contain isaac.x64")
        _register_installed_app(steam_home, spec, game_dir)

        if any(task.clean_room_synthetic for task in self.catalog.tasks):
            # Every construct task ships the same private runtime Dockerfile; the profile
            # run is the same one the Exodus runtime needs, so it happens once per runtime.
            task_root = self.context.pack_root / "private" / "harbor" / self.catalog.tasks[0].id
            if not options.is_file():
                progress(15, "creating a zero-progression Isaac profile in the offline client")
                self._create_profile(task_root, steam_home, isaac_data)
            # The online profile run lets the client fetch its own update; also on state
            # an earlier preparation left behind.
            _discard_staged_client_update(steam_home / CLIENT_INSTALLATION)
            return self._prepare_synthetic(spec, steam_home, isaac_data, progress)

        task_root = self.context.pack_root / "private/harbor/isaac-exodus-release-regressions"
        if not options.is_file():
            progress(15, "creating a zero-progression Isaac profile in the offline client")
            self._create_profile(task_root, steam_home, isaac_data)
        _discard_staged_client_update(steam_home / CLIENT_INSTALLATION)
        progress(20, "building private Steam runtime image")
        private_image = "gcb-isaac-private-runtime:abp-v1.06.t1"
        environment = self._docker(
            [
                "build",
                "--pull=false",
                "--build-context",
                f"steam_home={steam_home}",
                "--build-context",
                f"isaac_data={isaac_data}",
                "--file",
                str(task_root / "scripts/private-runtime.Dockerfile"),
                "--tag",
                private_image,
                str(task_root / "scripts"),
            ],
            timeout=7200,
        )
        if environment.returncode != 0:
            raise RuntimeError("failed to build private Isaac runtime\n" + environment.stderr[-8000:])
        progress(70, "building networkless Isaac verifier image")
        verifier = self._docker(
            [
                "build",
                "--pull=false",
                "--tag",
                VERIFIER_IMAGE,
                str(task_root / "tests"),
            ],
            timeout=3600,
        )
        if verifier.returncode != 0:
            raise RuntimeError("failed to build Isaac verifier\n" + verifier.stderr[-8000:])
        image_id = self.runtime.image_id()
        progress(100, "Isaac verifier ready")
        return RuntimeArtifact(
            runtime_key=f"isaac-rebirth/{spec.id}",
            fingerprint=fingerprint,
            kind="docker-image",
            identity=image_id,
            metadata={
                "network": "none",
                "clientBootstrap": "managed",
                "platform": platform.system().lower(),
            },
        )

    def _prepare_synthetic(
        self,
        spec: RuntimeSpec,
        steam_home: Path,
        isaac_data: Path,
        progress: Any,
    ) -> RuntimeArtifact:
        fingerprint = spec.fingerprint(plugin_id="isaac-rebirth", plugin_version="0.6.0")
        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            task_root = self.context.pack_root / "private" / "harbor" / task.id
            private_image = f"gcb-isaac-private-runtime:{task.id}-{self.catalog.version}"
            verifier_image = f"gcb-isaac-verifier:{task.id}-{self.catalog.version}"
            progress(int((index - 1) * 100 / total), f"building Isaac runtime for {task.id}")
            environment = self._docker(
                [
                    "build",
                    "--pull=false",
                    "--build-context",
                    f"steam_home={steam_home}",
                    "--build-context",
                    f"isaac_data={isaac_data}",
                    "--file",
                    str(task_root / "scripts/private-runtime.Dockerfile"),
                    "--tag",
                    private_image,
                    str(task_root / "scripts"),
                ],
                timeout=7200,
            )
            if environment.returncode != 0:
                raise RuntimeError("failed to build private synthetic Isaac runtime")
            verifier = self._docker(
                [
                    "build",
                    "--pull=false",
                    "--network=none",
                    "--build-arg",
                    f"PRIVATE_IMAGE={private_image}",
                    "--tag",
                    verifier_image,
                    str(task_root / "tests"),
                ],
                timeout=3600,
            )
            if verifier.returncode != 0:
                raise RuntimeError("failed to build synthetic Isaac verifier")
            inspected = self._docker(
                ["image", "inspect", verifier_image, "--format", "{{.Id}}"], timeout=_BOOKKEEPING_TIMEOUT
            )
            if inspected.returncode != 0 or not inspected.stdout.strip():
                raise RuntimeError("synthetic Isaac verifier image has no immutable identity")
            images[task.id] = inspected.stdout.strip()
        identity = hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in sorted(images.items())).encode()
        ).hexdigest()
        progress(100, "synthetic Isaac verifier images ready")
        return RuntimeArtifact(
            runtime_key=f"isaac-rebirth/{spec.id}",
            fingerprint=fingerprint,
            kind="docker-images",
            identity=f"sha256:{identity}",
            metadata={"images": images, "network": "none", "clientBootstrap": "managed"},
        )

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        del spec
        if artifact.kind == "docker-images":
            images = artifact.metadata.get("images")
            if not isinstance(images, dict) or set(images) != {task.id for task in self.catalog.tasks}:
                return {"available": False, "reason": "synthetic Isaac image set is incomplete"}
            for image_id in images.values():
                result = self._docker(
                    ["image", "inspect", str(image_id), "--format", "{{.Id}}"], timeout=_BOOKKEEPING_TIMEOUT
                )
                if result.returncode != 0 or result.stdout.strip() != image_id:
                    return {"available": False, "reason": "synthetic Isaac image is missing"}
            return {"available": True, "imageCount": len(images), "network": "none"}
        result = self._docker(
            ["image", "inspect", artifact.identity, "--format", "{{.Id}}"], timeout=_BOOKKEEPING_TIMEOUT
        )
        available = result.returncode == 0 and result.stdout.strip() == artifact.identity
        return {
            "available": available,
            "reason": None if available else "immutable Isaac verifier image is missing",
            "imageId": artifact.identity,
            "network": "none",
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        del spec
        images = artifact.metadata.get("images")
        if artifact.kind == "docker-images" and isinstance(images, dict):
            for image_id in set(map(str, images.values())):
                self._docker(["image", "rm", image_id], timeout=120)
            return
        self._docker(["image", "rm", artifact.identity], timeout=120)
