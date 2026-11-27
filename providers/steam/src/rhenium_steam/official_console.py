"""Opt-in controlled Steam-client preparation; never used during evaluation.

An operator-approved private profile binds an existing independent client home,
image, client bytes, and exact source. No password, refresh-token extraction,
arbitrary console input, host port, or account-state copy is supported.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit

from rhenium.core.auth import AuthSession, ProgressCallback
from rhenium.core.runtime import RuntimeActionRequired

from .cef_stdio import CEF, PIPE

BACKEND = "official-console-v1"
CONTAINER_HOME = Path("/home/steamprobe")
LOGIN = """new Promise(resolve=>{
 let handle;let ended=false;
 const finish=v=>{if(ended)return;ended=true;clearTimeout(timer);
   queueMicrotask(()=>handle?.unregister());resolve(v)};
 const timer=setTimeout(()=>finish({received:false}),25000);
 handle=SteamClient.User.RegisterForLoginStateChange((ignored,state,result)=>{
   if(Number(state)===5&&Number(result)===1)
     finish({received:true,state:Number(state),result:Number(result)});
 });
})"""


def sha(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, indent=2)


def source_identity(source: dict[str, Any]) -> tuple[int, int, str]:
    if source.get("kind") != "steam-depots" or source.get("officialClient"):
        raise ValueError("Console preparation supports depot sources without client-state staging")
    app = source.get("appId")
    depots = source.get("depots")
    if type(app) is not int or not 0 < app < 2**32 or not isinstance(depots, list) or len(depots) != 1:
        raise ValueError("One exact app/depot is required for this controlled backend")
    depot, manifest = depots[0].get("id"), depots[0].get("manifest")
    if (
        type(depot) is not int
        or not 0 < depot < 2**32
        or not isinstance(manifest, str)
        or not re.fullmatch(r"[1-9][0-9]{0,19}", manifest)
        or int(manifest) >= 2**64
    ):
        raise ValueError("Exact depot identity is invalid")
    files, hashes = source.get("expectedFiles"), source.get("sha256")
    if not isinstance(files, list) or not files or not isinstance(hashes, dict) or set(files) != set(hashes):
        raise ValueError("Every expected source file needs an explicit SHA-256")
    for name in files:
        relative_path(name)
        if not re.fullmatch(r"[a-f0-9]{64}", str(hashes[name])):
            raise ValueError("Invalid source checksum")
    return app, depot, manifest


def relative_path(name: str) -> Path:
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe provider-relative path")
    return path


def verify_files(root: Path, source: dict[str, Any]) -> dict[str, str]:
    source_identity(source)
    if root.is_symlink():
        raise ValueError("Symlinked source root")
    result = {}
    for name in source["expectedFiles"]:
        path = root / relative_path(name)
        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve())
            or sha(path) != source["sha256"][name]
        ):
            raise ValueError("Provider source failed its expected-file identity")
        result[name] = sha(path)
    return result


def loopback_ready(tcp: str, tcp6: str) -> bool:
    found = False
    for text in (tcp, tcp6):
        for line in text.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 4 or parts[3] != "0A":
                continue
            address, port = parts[1].split(":")
            if int(port, 16) != 8080:
                continue
            if address not in {"0100007F", "00000000000000000000000001000000"}:
                raise RuntimeError("CEF listener is not loopback-only")
            found = True
    return found


def require_host() -> None:
    if sys.platform != "linux" or os.getuid() != 1000 or os.getgid() != 1000:
        raise RuntimeError("This reviewed profile requires Linux uid/gid 1000")


class Profile:
    def __init__(self, path: Path, expected: str | None = None):
        require_host()
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_mode & 0o077
            or path.stat().st_size > 65536
        ):
            raise ValueError("Private operator profile must be an absolute mode-0600 file")
        if path.stat().st_uid != os.getuid():
            raise ValueError("Operator profile is not owned by the preparation user")
        self.path, self.digest = path, sha(path)
        if expected is not None and self.digest != expected:
            raise ValueError("Operator profile changed after session registration")
        self.data = json.loads(path.read_text())
        approval = self.data["approval"]
        if (
            self.data.get("schema") != 1
            or approval.get("approved") is not True
            or approval.get("cef_control") is not True
            or approval.get("loopback_only") is not True
            or approval.get("maximum_process_seconds") != 1800
            or approval.get("host_ports_published") is not False
            or approval.get("new_authentication_allowed") is not False
        ):
            raise ValueError("An explicit bounded CEF preparation approval is required")
        self.identifier = str(uuid.UUID(self.data["id"]))
        state = Path(os.environ.get("RHENIUM_STATE_DIR", "")).resolve()
        self.home, self.root = Path(self.data["home"]), path.parent
        if (
            not self.home.is_absolute()
            or not self.home.resolve().is_relative_to(state)
            or not path.resolve().is_relative_to(state)
            or self.home.is_symlink()
        ):
            raise ValueError("Official client state must remain in the selected private state directory")
        self.image = self.data["image_id"]
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", self.image):
            raise ValueError("An existing immutable approved image is required")
        self.env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.root),
            "DOCKER_HOST": "unix:///var/run/docker.sock",
        }
        self.check_client()

    def check_client(self) -> None:
        if not self.data["client_files"]:
            raise ValueError("Client identity must be recorded")
        for name, expected in self.data["client_files"].items():
            path = self.home / relative_path(name)
            if not path.resolve().is_relative_to(self.home.resolve()) or sha(path) != expected:
                raise ValueError("Reviewed official-client bytes changed")

    def session(self, alias: str) -> AuthSession:
        return AuthSession(
            provider_id="steam",
            account_alias=alias,
            principal=f"official-client-profile:{self.identifier}",
            secret={"backend": BACKEND, "profile": str(self.path), "profileSha256": self.digest},
            metadata={
                "backend": BACKEND,
                "scope": "controlled-linux-preparation",
                "principalKind": "opaque-client-profile-not-steam-account-id",
                "helperRefreshTokenImported": False,
                "credentialsRemainInOfficialClientHome": True,
            },
        )


class Client:
    def __init__(self, profile: Profile):
        self.profile = profile
        self.attempt = profile.root / "attempts" / uuid.uuid4().hex
        self.name = "rhenium-steam-prepare-" + self.attempt.name[:20]
        self.channel: CEF | None = None
        self.created = False
        self.launch_requested = False
        self.started = time.monotonic()
        self.deadline = self.started + 1800
        self.lock: Any = None
        self.stage = "preflight"
        self.error_count = 0
        self.listener_families: dict[str, bool] = {}

    def docker(self, *args: str, timeout: int = 30) -> str:
        result = subprocess.run(
            ["docker", *args],
            env=self.profile.env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            self.error_count += 1
            operation = "lifecycle"
            if args[0] == "exec" and len(args) > 2:
                operation = {"cat": "listener_query", "curl": "cef_target_list"}.get(args[2], "exec")
            reason = "unspecified"
            if "Resource temporarily unavailable" in result.stderr:
                reason = "resource_temporarily_unavailable"
            elif "is not running" in result.stderr:
                reason = "container_not_running"
            if self.attempt.is_dir() and self.error_count <= 32:
                write_new(
                    self.attempt / f"docker-error-{self.error_count}.json",
                    {
                        "stage": self.stage,
                        "operation": operation,
                        "exitCode": result.returncode,
                        "reasonCategory": reason,
                        "stdoutBytes": len(result.stdout.encode()),
                        "stderrBytes": len(result.stderr.encode()),
                        "listeners": self.listener_families,
                        "rawOutputRetained": False,
                    },
                )
            raise RuntimeError(f"Owned preparation {operation} failed (exit {result.returncode})")
        return result.stdout.strip()

    def inspect(self, *, policy: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = json.loads(self.docker("inspect", self.name))[0]
        if value["Config"].get("Labels", {}).get("org.rhenium.steam.preparation") != self.profile.identifier:
            raise RuntimeError("Refusing an unowned preparation process")
        if not policy:
            return value
        host = value["HostConfig"]
        if (
            value["Image"] != self.profile.image
            or value["Config"]["User"] != "1000:1000"
            or host.get("PortBindings")
            or host["Privileged"]
            or host["ShmSize"] != 1073741824
            or host["Memory"] != 3221225472
            or host["NanoCpus"] != 2000000000
            or host["PidsLimit"] != 512
            or host["NetworkMode"] != "bridge"
            or host.get("CapDrop") != ["ALL"]
            or set(host["SecurityOpt"]) != {"no-new-privileges", "seccomp=unconfined"}
        ):
            raise RuntimeError("Preparation container policy differs from the approved profile")
        mounts = {m["Destination"]: (str(Path(m["Source"]).resolve()), m["RW"]) for m in value["Mounts"]}
        expected_mounts = {
            "/home/steamprobe": (str(self.profile.home.resolve()), True),
            "/tmp/.X11-unix": (str(Path("/tmp/.X11-unix").resolve()), False),
            "/opt/steam-probe/namespace.sh": (
                str(Path(__file__).with_name("interactive-launch-v1.sh").resolve()),
                False,
            ),
        }
        if mounts != expected_mounts or host.get("Devices") or host.get("CapAdd"):
            raise RuntimeError("Unexpected mount or capability in the preparation process")
        return value

    def guard(self) -> bool:
        if time.monotonic() >= self.deadline - 90 or not self.inspect()["State"]["Running"]:
            raise RuntimeError("Owned preparation process is unavailable or near its deadline")
        self.stage = "listener_query"
        tcp = self.docker("exec", self.name, "cat", "/proc/net/tcp")
        tcp6 = self.docker("exec", self.name, "cat", "/proc/net/tcp6")
        ipv4, ipv6 = loopback_ready(tcp, ""), loopback_ready("", tcp6)
        self.listener_families = {"ipv4Loopback": ipv4, "ipv6Loopback": ipv6}
        return ipv4 or ipv6

    def __enter__(self) -> Client:
        import fcntl

        self.lock = (self.profile.root / "preparation.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for label in ("org.rhenium.probe", "org.rhenium.steam.preparation"):
                if self.docker("ps", "-q", "--filter", f"label={label}"):
                    raise RuntimeError("Another owned Steam preparation is running")
            self.attempt.mkdir(parents=True, exist_ok=False, mode=0o700)
            script = Path(__file__).with_name("interactive-launch-v1.sh")
            write_new(
                self.attempt / "launch-request.json",
                {
                    "profileSha256": self.profile.digest,
                    "imageId": self.profile.image,
                    "maximumSeconds": 1800,
                    "controllerSha256": sha(Path(__file__)),
                    "scriptSha256": sha(script),
                    "requestedUtc": dt.datetime.now(dt.UTC).isoformat(),
                },
            )
            self.launch_requested = True
            self.docker(
                "run",
                "--detach",
                "--name",
                self.name,
                "--label",
                f"org.rhenium.steam.preparation={self.profile.identifier}",
                "--user",
                "1000:1000",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--security-opt",
                "seccomp=unconfined",
                "--shm-size",
                "1g",
                "--pids-limit",
                "512",
                "--memory",
                "3g",
                "--cpus",
                "2",
                "--network",
                "bridge",
                "--mount",
                f"type=bind,src={self.profile.home},dst=/home/steamprobe",
                "--mount",
                "type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly",
                "--mount",
                f"type=bind,src={script},dst=/opt/steam-probe/namespace.sh,readonly",
                "--env",
                "HOME=/home/steamprobe",
                "--env",
                "DISPLAY=:0",
                "--env",
                "XDG_RUNTIME_DIR=/tmp/steam-probe-runtime",
                "--env",
                "LIBGL_ALWAYS_SOFTWARE=1",
                "--env",
                "GDK_BACKEND=x11",
                "--env",
                "SDL_VIDEODRIVER=x11",
                "--env",
                "GTK_A11Y=none",
                "--entrypoint",
                "/bin/bash",
                self.profile.image,
                "/opt/steam-probe/namespace.sh",
            )
            self.created = True
            self.inspect()
            ready_deadline = time.monotonic() + 150
            while time.monotonic() < ready_deadline:
                if not self.guard():
                    time.sleep(1)
                    continue
                self.stage = "cef_target_list"
                raw = self.docker(
                    "exec",
                    self.name,
                    "curl",
                    "--noproxy",
                    "*",
                    "--silent",
                    "--fail",
                    "--max-time",
                    "5",
                    "--max-filesize",
                    "262144",
                    "http://127.0.0.1:8080/json/list",
                )
                targets = json.loads(raw)
                if not isinstance(targets, list) or len(targets) > 32:
                    raise RuntimeError("Invalid bounded CEF target response")
                if any("login" in str(t.get("title", "")).lower() for t in targets):
                    raise RuntimeActionRequired(
                        "steam-client-login", "Existing independent sign-in is unavailable"
                    )
                matches = [t for t in targets if t.get("title") in {"SP", "SharedJSContext"}]
                if not matches:
                    time.sleep(1)
                    continue
                if len(matches) != 1:
                    raise RuntimeError("Native client context is ambiguous")
                endpoint = urlsplit(matches[0]["webSocketDebuggerUrl"])
                if (
                    endpoint.scheme != "ws"
                    or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
                    or endpoint.port != 8080
                    or endpoint.username
                    or endpoint.password
                    or endpoint.query
                    or endpoint.fragment
                ):
                    raise RuntimeError("Unsafe CEF endpoint")
                self.channel = CEF(
                    endpoint.path,
                    command=["docker", "exec", "-i", self.name, "/bin/bash", "-c", PIPE],
                    env=self.profile.env,
                    timeout=30,
                )
                self.stage = "authentication_callback"
                state = self.channel.evaluate(LOGIN, await_promise=True)
                if state != {"received": True, "state": 5, "result": 1}:
                    raise RuntimeActionRequired(
                        "steam-client-login", "Cached official-client sign-in was not confirmed"
                    )
                write_new(self.attempt / "authentication.json", {"state": state, "accountFieldsRead": False})
                return self
            raise RuntimeError("Native client readiness was not confirmed within its bound")
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        try:
            if self.channel is not None:
                self.channel.close()
                self.channel = None
            if self.launch_requested and not self.created:
                names = self.docker("ps", "-a", "--filter", f"name=^/{self.name}$", "--format", "{{.Names}}")
                self.created = names == self.name
            if not self.created:
                return
            obj = self.inspect(policy=False)
            ipc: int | str | None = None
            if obj["State"]["Running"]:
                try:
                    ipc = subprocess.run(
                        [
                            "docker",
                            "exec",
                            self.name,
                            "/home/steamprobe/.steam/debian-installation/steam.sh",
                            "-shutdown",
                        ],
                        env=self.profile.env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=30,
                        check=False,
                    ).returncode
                except subprocess.TimeoutExpired:
                    ipc = "timeout"
            until = time.monotonic() + 30
            while self.inspect(policy=False)["State"]["Running"] and time.monotonic() < until:
                time.sleep(1)
            forced = self.inspect(policy=False)["State"]["Running"]
            if forced:
                self.docker("stop", "--time", "15", self.name, timeout=25)
            state = self.inspect(policy=False)["State"]
            normal = ipc == 0 and not forced and state["ExitCode"] == 0
            write_new(
                self.attempt / "shutdown.json",
                {
                    "normal": normal,
                    "forced": forced,
                    "ipcResult": ipc,
                    "exitCode": state["ExitCode"],
                    "oomKilled": state["OOMKilled"],
                    "elapsedSeconds": round(time.monotonic() - self.started, 3),
                },
            )
            self.created = False
            self.profile.check_client()
            if not normal:
                raise RuntimeError("Preparation did not exit normally; evidence is incomplete")
        finally:
            if self.lock is not None:
                self.lock.close()
                self.lock = None

    def __exit__(
        self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()


def login(profile_path: Path, alias: str, progress: ProgressCallback) -> AuthSession:
    profile = Profile(profile_path)
    progress(5, "validating the existing independent official-client login")
    with Client(profile):
        pass
    progress(100, "existing client login validated; no credentials imported")
    return profile.session(alias)


def validate(session: AuthSession) -> AuthSession:
    profile = Profile(Path(session.secret["profile"]), session.secret["profileSha256"])
    with Client(profile):
        pass
    return profile.session(session.account_alias)


def completion_source(signal: Any, home: Path, source: dict[str, Any]) -> Path:
    app, depot, manifest = source_identity(source)
    if (
        not isinstance(signal, dict)
        or signal.get("phase") != "complete"
        or signal.get("count") != 1
        or signal.get("echoes") != 1
        or signal.get("failures") != 0
        or signal.get("manifest") != manifest
        or not isinstance(signal.get("path"), str)
    ):
        raise RuntimeError("Fixed-depot completion identity was not confirmed")
    # This fixed Linux client reports the native base with a backslash-separated
    # depot suffix. Normalize separators before, never after, traversal checks.
    relative = Path(signal["path"].replace("\\", "/")).relative_to(CONTAINER_HOME)
    if ".." in relative.parts or relative.parts[-4:] != (
        "steamapps",
        "content",
        f"app_{app}",
        f"depot_{depot}",
    ):
        raise RuntimeError("Steam returned an unexpected depot location")
    root = home / relative
    if not root.resolve().is_relative_to(home.resolve()):
        raise RuntimeError("Acquired depot escaped the independent home")
    verify_files(root, source)
    return root


def acquisition_script(source: dict[str, Any]) -> str:
    app, depot, manifest = source_identity(source)
    command = f"download_depot {app} {depot} {manifest}"
    # Only numeric validated source IDs are interpolated; no caller-supplied JS/console input.
    return r"""(()=>{
      if(window.__rheniumPreparation)throw new Error('Already attempted');
      const state={phase:'waiting',count:0,echoes:0,failures:0,manifest:null,path:null};
      window.__rheniumPreparation=state;
      let handle;
      const finish=()=>{clearTimeout(timer);queueMicrotask(()=>handle?.unregister())};
      const timer=setTimeout(()=>{state.phase='observer_timeout';finish()},1500000);
      handle=SteamClient.Console.RegisterForSpewOutput(event=>{
        if(typeof event.spew!=='string'||event.spew.length>4096)return;
        for(const text of event.spew.split('\n')){
          if(text.trim()===COMMAND){state.echoes++;continue;}
          if(state.echoes!==1)continue;
          const match=text.trim().match(/^Depot download complete : "([^"]+)" \(manifest ([0-9]+)\)\s*$/);
          if(match){state.count++;state.manifest=match[2];
            state.path=match[1].startsWith('/home/steamprobe/')?match[1]:null;
            state.phase='complete';finish();
          }else if(text.trim().startsWith('Depot download failed :')){
            state.failures++;state.phase='download_failed';finish();
          }
        }
      });
      SteamClient.Console.ExecCommand(COMMAND);
      return {issued:true};
    })()""".replace("COMMAND", json.dumps(command))


def completed_attempt(
    profile: Profile,
    source: dict[str, Any],
    request: Any,
) -> tuple[Path, dict[str, Any]]:
    if not isinstance(request, dict) or not re.fullmatch(r"[a-f0-9]{32}", str(request.get("attempt", ""))):
        raise RuntimeError("Earlier acquisition is unresolved; never resend automatically")
    expected = {
        "sourceSha256": fingerprint(source),
        "profileId": profile.identifier,
        "attempt": request["attempt"],
        "source": source,
    }
    if request != expected:
        raise RuntimeError("Recorded acquisition identity differs; never resend automatically")
    attempt = profile.root / "attempts" / request["attempt"]
    records = {}
    names = ("depot-request.json", "issue-response.json", "depot-completion.json", "shutdown.json")
    try:
        for name in names:
            path = attempt / name
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(profile.root.resolve())
                or path.stat().st_size > 65536
            ):
                raise ValueError("Unsafe preparation receipt")
            records[name] = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "Earlier acquisition is unresolved; completion evidence is missing or invalid"
        ) from error
    cleanup = records["shutdown.json"]
    if (
        records["depot-request.json"] != expected
        or records["issue-response.json"] != {"issued": True}
        or cleanup.get("normal") is not True
        or cleanup.get("forced") is not False
        or cleanup.get("exitCode") != 0
        or cleanup.get("ipcResult") != 0
    ):
        raise RuntimeError(
            "Earlier acquisition is unresolved; complete response and normal exit are required"
        )
    root = completion_source(records["depot-completion.json"], profile.home, source)
    receipt = {
        **expected,
        "commandCount": 1,
        "completionSha256": sha(attempt / "depot-completion.json"),
        "shutdownSha256": sha(attempt / "shutdown.json"),
    }
    return root, receipt


def publish_source(
    profile: Profile, source: dict[str, Any], request: Any, destination: Path, *, reconciled: bool
) -> None:
    root, receipt = completed_attempt(profile, source, request)
    for name in source["expectedFiles"]:
        target = destination / relative_path(name)
        if target.exists():
            if target.is_symlink() or sha(target) != source["sha256"][name]:
                raise RuntimeError("Existing partial source bytes differ; preserve them for review")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with (root / name).open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst)
    receipt.update(files=verify_files(destination, source), reconciledFromRecordedCompletion=reconciled)
    write_new(destination / "official-console-source-v1.json", receipt)


def acquire(
    source: dict[str, Any], session: AuthSession, destination: Path, progress: ProgressCallback
) -> AuthSession:
    profile = Profile(Path(session.secret["profile"]), session.secret["profileSha256"])
    source_identity(source)
    if fingerprint(source) != profile.data["allowed_source_sha256"]:
        raise ValueError("Source is outside the explicit operator preparation scope")
    if destination.is_symlink():
        raise ValueError("Unsafe provider destination")
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / "official-console-source-v1.json"
    pending = destination / "official-console-request-v1.json"
    if marker.is_symlink() or pending.is_symlink():
        raise ValueError("Unsafe provider receipt path")
    from . import official_cache

    if (destination / official_cache.NAME).exists():
        official_cache.verify(profile, source, destination)
        progress(100, "verified explicit prior-cache reuse; failed attempt preserved; no command resent")
        return session
    if marker.is_file():
        receipt = json.loads(marker.read_text())
        if (
            receipt.get("sourceSha256") != fingerprint(source)
            or receipt.get("profileId") != profile.identifier
        ):
            raise ValueError("Provider source-cache identity changed")
        verify_files(destination, source)
        _, proof = completed_attempt(profile, source, json.loads(pending.read_text()))
        if any(receipt.get(key) != value for key, value in proof.items()):
            raise ValueError("Provider source-cache provenance changed")
        progress(100, "verified provider-owned exact source cache")
        return session
    if pending.exists():
        publish_source(profile, source, json.loads(pending.read_text()), destination, reconciled=True)
        progress(100, "verified completed acquisition receipts and files; no download command resent")
        return session
    with Client(profile) as client:
        assert client.channel is not None
        client.guard()
        request = {
            "sourceSha256": fingerprint(source),
            "profileId": profile.identifier,
            "attempt": client.attempt.name,
            "source": source,
        }
        write_new(pending, request)
        write_new(client.attempt / "depot-request.json", request)
        response = client.channel.evaluate(acquisition_script(source))
        write_new(client.attempt / "issue-response.json", response)
        if response != {"issued": True}:
            raise RuntimeError("Acquisition request was not acknowledged; do not resend")
        progress(10, "acquiring the exact depot through the signed-in official client")
        signal: Any = None
        while time.monotonic() < client.deadline - 120:
            client.guard()
            signal = client.channel.evaluate("window.__rheniumPreparation")
            if not isinstance(signal, dict) or signal.get("phase") != "waiting":
                break
            time.sleep(1)
        write_new(client.attempt / "depot-completion.json", signal)
        completion_source(signal, profile.home, source)
    # This marker is written only after official completion, file checks AND normal exit.
    publish_source(profile, source, request, destination, reconciled=False)
    progress(100, "pinned source verified and official client exited normally")
    return profile.session(session.account_alias)
