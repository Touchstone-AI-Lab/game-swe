"""Visible Linux process adapter; inspected code only, not an untrusted sandbox."""

from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import linux_window
from .files import reject_links
from .linux_runtime import BalatroLinuxProbeBuilder, tree
from .native_assets import json_write_new
from .review import candidate_identity

if TYPE_CHECKING:
    from .linux_assets.legacy.poc.rpc import Client


def arm_parent_death(parent: int) -> None:
    """Owned Linux child must not outlive an unexpectedly terminated controller."""
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG, child only.
        raise OSError(ctypes.get_errno(), "Cannot arm owned child parent-death signal")
    if os.getppid() != parent:
        os.kill(os.getpid(), signal.SIGKILL)


def child_environment(
    root: Path, directory: Path, nonce: str, port: int, probe: bool, audio_backend: str | None = None
) -> dict[str, str]:
    if audio_backend not in {None, "null"}:
        raise ValueError("Unsupported process audio backend")
    app = root / "squashfs-root"
    for name in ("home", "tmp", "appdata/Balatro", "config", "cache"):
        (directory / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "DISPLAY": ":0",
        "HOME": str(directory / "home"),
        "TMPDIR": str(directory / "tmp"),
        "XDG_DATA_HOME": str(directory / "appdata"),
        "APPDATA": str(directory / "appdata"),
        "XDG_CONFIG_HOME": str(directory / "config"),
        "XDG_CACHE_HOME": str(directory / "cache"),
        "XDG_DATA_DIRS": f"{app}/share:/usr/local/share:/usr/share",
        "LD_LIBRARY_PATH": str(app / "lib"),
        "LD_PRELOAD": str(root / "liblovely.so"),
        "LUA_PATH": f"{app}/share/luajit-2.1.0-beta3/?.lua;{app}/share/lua/5.1/?.lua",
        "LUA_CPATH": f"{app}/lib/lua/5.1/?.so",
        "LOVELY_MOD_DIR": str(directory / "Mods"),
        "POC_SAVE_DIR": str(directory / "appdata/Balatro"),
        "POC_RUN_DIR": str(directory),
        "POC_NONCE": nonce,
        "POC_PROBE_ONLY": "1" if probe else "0",
        "BALATROBOT_HOST": "127.0.0.1",
        "BALATROBOT_PORT": str(port),
        "BALATROBOT_GAMESPEED": "1",
        "BALATROBOT_ANIMATION_FPS": "60",
        "BALATROBOT_FAST": "0",
        "BALATROBOT_HEADLESS": "0",
        "NO_PROXY": "127.0.0.1,localhost",
    }
    pulse = Path("/mnt/wslg/PulseServer")
    if audio_backend == "null":
        env.update(
            ALSOFT_DRIVERS="null",
            ALSOFT_LOGLEVEL="3",
            ALSOFT_LOGFILE=str(directory / "openal-diagnostic.log"),
        )
    elif pulse.is_socket():
        env["PULSE_SERVER"] = f"unix:{pulse}"
    return env


def game_process_guard(windows_powershell: Path | None) -> None:
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if (entry / "comm").read_text().strip() in {"love", "Balatro", "Balatro.exe", "AppRun"}:
                raise RuntimeError("An existing game process is running; leave it untouched")
        except (FileNotFoundError, ProcessLookupError):
            continue
    if "microsoft" in platform.release().lower():
        if windows_powershell is None or not windows_powershell.is_file():
            raise RuntimeError("WSL execution requires the explicit read-only Windows process guard")
        interop = Path(os.environ.get("WSL_INTEROP", ""))
        if not interop.is_absolute() or interop.parent != Path("/run/WSL") or not interop.is_socket():
            raise RuntimeError("Cannot validate the WSL interoperability channel for the process guard")
        result = subprocess.run(
            [
                str(windows_powershell),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "@(Get-Process Balatro -ErrorAction SilentlyContinue).Count",
            ],
            env={"PATH": "/usr/bin:/bin", "WSL_INTEROP": str(interop)},
            capture_output=True,
            timeout=15,
            check=True,
        )
        if result.stdout.decode("utf-8").strip() != "0":
            raise RuntimeError("An existing Windows game process is running; leave it untouched")


def owned_loopback_listener(pid: int, port: int) -> dict[str, Any]:
    listeners = []
    for name in ("tcp", "tcp6"):
        for row in (Path("/proc/net") / name).read_text().splitlines()[1:]:
            fields = row.split()
            address, raw_port = fields[1].split(":")
            if int(raw_port, 16) == port and fields[3] == "0A":
                listeners.append((name, address, fields[9]))
    if len(listeners) != 1 or listeners[0][:2] != ("tcp", "0100007F"):
        raise RuntimeError("RPC listener is not uniquely bound to IPv4 loopback")
    owned = {str(path.readlink()) for path in (Path("/proc") / str(pid) / "fd").iterdir()}
    if f"socket:[{listeners[0][2]}]" not in owned:
        raise RuntimeError("RPC listener is not owned by this game process")
    return {"address": "127.0.0.1", "pid": pid, "port": port}


class NativeProcess:
    def __init__(
        self,
        *,
        builder: BalatroLinuxProbeBuilder,
        spec: Any,
        artifact: Any,
        directory: Path,
        probe: bool = False,
        extra_mods: dict[str, Path] | None = None,
        windows_powershell: Path | None = None,
        audio_backend: str | None = None,
        candidate_sha256: str | None = None,
    ) -> None:
        reject_links(directory)
        if not directory.is_absolute() or directory.exists():
            raise ValueError("A fresh absolute process directory is required")
        self.builder, self.spec, self.artifact = builder, spec, artifact
        self.root = Path(artifact.location)
        self.directory, self.probe = directory, probe
        self.extra_mods = extra_mods or {}
        self.windows_powershell = windows_powershell
        self.audio_backend = audio_backend
        self.candidate_sha256 = candidate_sha256
        self.window_files = linux_window.resources() if linux_window.enabled(artifact) and not probe else None
        self.nonce = uuid.uuid4().hex
        self.process: subprocess.Popen[bytes] | None = None
        self.client: Client | None = None
        self.log: Any = None
        self.metadata: dict[str, Any] = {}
        self.staged: dict[str, Any] = {}
        self.started = time.monotonic()
        self.timings: dict[str, Any] = {}
        self.owns_directory = False
        self.closed: dict[str, Any] | None = None

    def record(self, value: dict[str, Any]) -> None:
        with (self.directory / "rpc.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value) + "\n")

    def verify_inputs(self) -> None:
        if self.window_files is not None and linux_window.resources() != self.window_files:
            raise RuntimeError("Owned window configuration changed")
        if not self.builder.verify(self.spec, self.artifact)["available"]:
            raise RuntimeError("Managed runtime bytes or recipe identity changed")

    def start(self) -> Client | None:
        self.verify_inputs()
        game_process_guard(self.windows_powershell)
        self.directory.mkdir(parents=True, mode=0o700)  # No reuse of a prior process directory.
        self.owns_directory = True
        mods = self.directory / "Mods"
        mods.mkdir()
        sources = {"poc_guard": self.root / "authored-mods/poc_guard"}
        if not self.probe:
            sources.update(
                {
                    "smods-stable": self.root / "mods/smods",
                    "balatrobot": self.root / "mods/bot",
                    "poc_control": self.root / "authored-mods/poc_control",
                }
            )
            if self.window_files is not None:
                sources["poc_window"] = linux_window.ROOT
            for name, path in self.extra_mods.items():
                if Path(name).name != name or name in sources or name in {".", ".."}:
                    raise ValueError("Invalid or duplicate mod staging name")
                sources[name] = path
        for name, path in sources.items():
            expected = tree(path)
            shutil.copytree(path, mods / name)
            if tree(mods / name) != expected:
                raise RuntimeError("Staged bytes differ from their inspected source")
            self.staged[name] = expected
        if (
            self.candidate_sha256 is not None
            and candidate_identity(mods / "candidate")[1] != self.candidate_sha256
        ):
            raise ValueError("Staged candidate differs from the reviewed submission")
        self.verify_inputs()  # Recheck immutable components immediately before loading.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = child_environment(self.root, self.directory, self.nonce, port, self.probe, self.audio_backend)
        # AppRun's fixed paths are explicit: preload only the actual LÖVE executable,
        # not its shell/readlink helpers. No host Lua search paths are inherited.
        command = [str(self.root / "squashfs-root/bin/love"), "--fused", str(self.root / "game/Balatro.exe")]
        self.timings["prepare_seconds"] = time.monotonic() - self.started
        startup = time.monotonic()
        self.log = (self.directory / "process.log").open("xb")
        parent = os.getpid()
        self.process = subprocess.Popen(
            command,
            cwd=self.directory,
            env=env,
            stdout=self.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=lambda: arm_parent_death(parent),
        )
        self.metadata = {
            "pid": self.process.pid,
            "nonce": self.nonce,
            "command": command,
            "port": port,
            "artifact_identity": self.artifact.identity,
            "environment_keys": sorted(env),
            "probe": self.probe,
            "audio_backend": self.audio_backend or "default",
            "save_dir": env["POC_SAVE_DIR"],
            "mod_dir": str(mods),
        }
        json_write_new(self.directory / "run.json", self.metadata)
        if self.probe:
            if self.process.wait(timeout=30) != 0:
                raise RuntimeError("Native isolation probe did not exit successfully")
        else:
            from .linux_assets.legacy.poc.rpc import Client

            self.client = Client(port, record=self.record)
            self.client.wait(
                lambda result: result.get("status") == "ok",
                method="health",
                timeout=45,
                retry_connection=True,
            )
            observed = self.client.call("poc.runtime")
            if (
                observed["nonce"] != self.nonce
                or observed["steam_active"]
                or not observed["visible"]
                or Path(observed["save_dir"]) != self.directory / "appdata/Balatro"
                or Path(observed["mod_dir"]) != mods
            ):
                raise RuntimeError("Native runtime identity, visibility, Steam or isolation check failed")
            listener = owned_loopback_listener(self.process.pid, port)
            self.metadata["observed_runtime"] = observed
            if self.window_files is not None:
                window = self.directory / "appdata/Balatro/window-profile-v2.json"
                deadline = time.monotonic() + 3
                while not window.is_file() and time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError("Game exited before window initialization")
                    time.sleep(0.05)
                self.metadata["window_profile"] = linux_window.read_observation(window)
                json_write_new(self.directory / "observed-window.json", self.metadata["window_profile"])
            json_write_new(
                self.directory / "observed-runtime.json", {"runtime": observed, "listener": listener}
            )
        lines = (self.directory / "isolation.txt").read_text().splitlines()
        if (
            lines[:3] != [env["POC_SAVE_DIR"], str(mods), env["APPDATA"]]
            or lines[-1] != self.nonce
            or (self.directory / "appdata/Balatro/poc-isolation-probe.txt").read_text() != self.nonce
        ):
            raise RuntimeError("Physical isolation evidence mismatch")
        self.timings["startup_seconds"] = time.monotonic() - startup
        return self.client

    def close(self) -> dict[str, Any]:
        if self.closed is not None:
            return self.closed
        exit_started = time.monotonic()
        forced, quit_error = False, None
        if self.process is not None and self.process.poll() is None:
            try:
                if self.client is not None:
                    self.client.call("poc.quit", timeout=3)  # Exactly one mutation.
                self.process.wait(timeout=15)
            except Exception as error:
                quit_error = type(error).__name__
                forced = True
                if self.process.poll() is None:
                    with suppress(ProcessLookupError):
                        os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=5)
        if self.log is not None:
            self.log.close()
        protected, protection_error = True, None
        try:
            self.verify_inputs()
            for name, expected in self.staged.items():
                if tree(self.directory / "Mods" / name) != expected:
                    raise RuntimeError("Staged input bytes changed")
        except Exception as error:
            protected, protection_error = False, type(error).__name__
        self.timings["exit_seconds"] = time.monotonic() - exit_started
        result = {
            "normal_exit": self.process is not None and self.process.returncode == 0 and not forced,
            "exit_code": self.process.returncode if self.process is not None else None,
            "forced": forced,
            "quit_error": quit_error,
            "protected_unchanged": protected,
            "protection_error": protection_error,
            "timings": self.timings,
            "directory_bytes": sum(
                path.stat().st_size for path in self.directory.rglob("*") if path.is_file()
            ),
        }
        self.closed = result
        if self.owns_directory:
            json_write_new(self.directory / "cleanup.json", result)
        return result
