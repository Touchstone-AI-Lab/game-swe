from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any

from rhenium.core.auth import (
    AuthChallenge,
    AuthProvider,
    AuthProviderDescriptor,
    AuthSession,
)

from .official_client import OfficialClientBootstrap, OfficialClientError


class SteamHelperError(RuntimeError):
    pass


class SteamHelper:
    def __init__(self) -> None:
        configured = os.environ.get("RHENIUM_STEAM_HELPER", "").strip()
        self.executable = Path(configured).expanduser() if configured else None

    @staticmethod
    def platform_id() -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        aliases = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}
        architecture = aliases.get(machine, machine)
        names = {"darwin": "osx", "windows": "win", "linux": "linux"}
        return f"{names.get(system, system)}-{architecture}"

    def resolve(self) -> Path:
        if self.executable is not None:
            candidate = self.executable.resolve()
            if not candidate.is_file():
                raise SteamHelperError(f"configured Steam helper is missing: {candidate}")
            return candidate
        discovered = shutil.which("rhenium-steam-helper")
        if discovered:
            return Path(discovered).resolve()
        platform_id = self.platform_id()
        manifest = json.loads(
            (files("rhenium_steam") / "helper-manifest.json").read_text(encoding="utf-8")
        )
        try:
            artifact = manifest["artifacts"][platform_id]
        except KeyError as error:
            raise SteamHelperError(f"Steam helper does not support {platform_id}") from error
        state = Path(
            os.environ.get("RHENIUM_STATE_DIR", Path.cwd() / ".rhenium" / "hub")
        ).expanduser()
        suffix = ".exe" if platform_id.startswith("win-") else ""
        candidate = state / "tools" / "steam" / str(manifest["version"]) / f"rhenium-steam-helper{suffix}"
        expected = str(artifact["sha256"])
        if candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest() == expected:
            return candidate.resolve()
        candidate.parent.mkdir(parents=True, exist_ok=True)
        temporary = candidate.with_suffix(candidate.suffix + ".partial")
        try:
            url = str(artifact["url"])
            gh = shutil.which("gh")
            if gh and "github.com" in urllib.parse.urlparse(url).netloc:
                asset_name = Path(urllib.parse.urlparse(url).path).name
                result = subprocess.run(
                    [
                        gh,
                        "release",
                        "download",
                        f"steam-helper-v{manifest['version']}",
                        "--repo",
                        "Touchstone-AI-Lab/GameCodeBench",
                        "--pattern",
                        asset_name,
                        "--output",
                        str(temporary),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    raise SteamHelperError(result.stderr.strip() or "GitHub release download failed")
            else:
                token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=300) as response:
                    temporary.write_bytes(response.read())
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
                raise SteamHelperError("downloaded Steam helper SHA-256 mismatch")
            temporary.replace(candidate)
            candidate.chmod(0o700)
        finally:
            if temporary.exists():
                temporary.unlink()
        return candidate.resolve()

    @staticmethod
    def _diagnosis(process: subprocess.Popen[str]) -> str:
        """The helper's own reason for failing, which otherwise reaches only its stderr."""
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            process.kill()
            process.wait(timeout=10)
        if process.stderr is None:
            return ""
        with contextlib.suppress(OSError, ValueError):
            return " ".join(process.stderr.read()[-400:].split())
        return ""

    def invoke(
        self,
        request: dict[str, Any],
        *,
        event: Callable[[dict[str, Any]], None],
        timeout: float,
    ) -> dict[str, Any]:
        executable = self.resolve()
        process = subprocess.Popen(
            [str(executable), "jsonl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.close()
        final: dict[str, Any] | None = None
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as error:
                    raise SteamHelperError("Steam helper emitted invalid JSON") from error
                if not isinstance(message, dict):
                    raise SteamHelperError("Steam helper emitted a non-object event")
                if message.get("type") == "result":
                    final = dict(message.get("value") or {})
                elif message.get("type") == "error":
                    reported = str(message.get("message") or "Steam helper failed")
                    detail = self._diagnosis(process)
                    raise SteamHelperError(f"{reported}: {detail}" if detail else reported)
                else:
                    event(message)
            returncode = process.wait(timeout=timeout)
        except Exception:
            process.kill()
            process.wait()
            raise
        if returncode != 0 or final is None:
            stderr = process.stderr.read()[-4000:] if process.stderr else ""
            raise SteamHelperError(stderr.strip() or f"Steam helper exited {returncode}")
        return final


class SteamAuthProvider(AuthProvider):
    descriptor = AuthProviderDescriptor(
        id="steam",
        name="Steam",
        version="0.1.0",
        capabilities=("qr-login", "persistent-session", "licensed-depots", "official-client"),
    )

    def __init__(self, client: OfficialClientBootstrap | None = None) -> None:
        self.helper = SteamHelper()
        self.client = client or OfficialClientBootstrap()

    @staticmethod
    def _session(
        value: dict[str, Any],
        account_alias: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AuthSession:
        principal = str(value.get("principal") or "").strip()
        refresh_token = str(value.get("refreshToken") or "").strip()
        if not principal or not refresh_token:
            raise SteamHelperError("Steam helper returned an incomplete session")
        secret = {"refreshToken": refresh_token}
        guard_data = str(value.get("guardData") or "").strip()
        if guard_data:
            secret["guardData"] = guard_data
        return AuthSession(
            provider_id="steam",
            account_alias=account_alias,
            principal=principal,
            secret=secret,
            metadata={
                "steamId": str(value.get("steamId") or ""),
                "country": str(value.get("country") or ""),
                **(metadata or {}),
            },
        )

    @staticmethod
    def client_home(account_alias: str) -> Path:
        state = Path(os.environ.get("RHENIUM_STATE_DIR", Path.cwd() / ".rhenium" / "hub")).expanduser()
        return state / "providers" / "steam" / account_alias / "official-client"

    def _bootstrap_client(
        self,
        account_alias: str,
        value: dict[str, Any],
        *,
        challenge: Any,
        progress: Any,
    ) -> dict[str, Any]:
        """Bootstrap the official client, reporting rather than failing the whole login."""
        if os.environ.get("RHENIUM_STEAM_SKIP_OFFICIAL_CLIENT", "").strip():
            return {
                "state": "skipped",
                "reason": "RHENIUM_STEAM_SKIP_OFFICIAL_CLIENT is set",
            }
        availability = self.client.availability()
        if not availability.get("available"):
            return {"state": "unavailable", "reason": str(availability.get("reason") or "")}
        home = self.client_home(account_alias)
        try:
            metadata = self.client.bootstrap(
                home,
                challenge=challenge,
                progress=lambda value, phase: progress(50 + int(value * 0.5), phase),
            )
        except (OSError, OfficialClientError, subprocess.SubprocessError) as error:
            return {"state": "failed", "reason": str(error)}
        session = self._session(value, account_alias)
        step = 90

        def report(value: int, phase: str) -> None:
            nonlocal step
            step = value
            progress(50 + int(value * 0.5), phase)

        def download(destination: Path, source: dict[str, Any]) -> None:
            # Each depot download reports its own 0-100. Keep the login's percentage on the
            # staging step it belongs to and carry the depot's own progress in the phase.
            self._acquire(
                source,
                session,
                destination,
                lambda value, phase: progress(50 + int(step * 0.5), f"{phase} ({value}%)"),
            )

        try:
            staged = self.client.stage_linux_runtimes(home, download, progress=report)
        except (OSError, OfficialClientError, SteamHelperError, subprocess.SubprocessError) as error:
            return {"path": str(home), **metadata, "steamLinuxRuntime": False, "reason": str(error)}
        return {"path": str(home), **metadata, "steamLinuxRuntime": staged}

    def login(
        self,
        account_alias: str,
        *,
        challenge: Any,
        progress: Any,
    ) -> AuthSession:
        profile = os.environ.get("RHENIUM_STEAM_OFFICIAL_PROFILE", "").strip()
        if profile:
            from . import official_console

            return official_console.login(Path(profile), account_alias, progress)

        def handle(message: dict[str, Any]) -> None:
            if message.get("type") == "challenge":
                challenge(
                    AuthChallenge(
                        kind="qr",
                        uri=str(message.get("uri") or ""),
                        expires_at=str(message.get("expiresAt") or "") or None,
                        message="Scan with the Steam Mobile app",
                    )
                )
            elif message.get("type") == "progress":
                progress(int(message.get("value") or 0), str(message.get("phase") or "Steam login"))

        try:
            value = self.helper.invoke(
                {"command": "login", "persistent": True},
                event=handle,
                timeout=600,
            )
        except SteamHelperError as error:
            # Steam replaces the QR code every few seconds and expires the sign-in session
            # with it, so the usual cause is a scan that arrived late or was never confirmed.
            raise SteamHelperError(
                f"{error}. Steam expires a QR sign-in within about a minute: run "
                "'rhenium auth login steam' again, scan the newest code, and confirm the "
                "sign-in in the Steam Mobile app"
            ) from error
        progress(50, "Steam session ready; preparing the official Steam client")
        client = self._bootstrap_client(account_alias, value, challenge=challenge, progress=progress)
        if client.get("state") == "ready":
            progress(100, "Steam session and official Steam client ready")
        else:
            progress(
                100,
                "Steam session ready; official Steam client "
                f"{client.get('state')}: {client.get('reason') or ''}".strip(),
            )
        return self._session(value, account_alias, metadata={"officialClient": client})

    def validate(self, session: AuthSession) -> AuthSession:
        if session.secret.get("backend") == "official-console-v1":
            from . import official_console

            return official_console.validate(session)
        value = self.helper.invoke(
            {
                "command": "validate",
                "principal": session.principal,
                "session": session.secret,
            },
            event=lambda _message: None,
            timeout=60,
        )
        return self._session(value, session.account_alias, metadata=self._client_metadata(session))

    @staticmethod
    def _client_metadata(session: AuthSession) -> dict[str, Any]:
        client = (session.metadata or {}).get("officialClient")
        return {"officialClient": client} if isinstance(client, dict) else {}

    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: Any,
    ) -> AuthSession:
        if session.secret.get("backend") == "official-console-v1":
            from . import official_console

            return official_console.acquire(source, session, destination, progress)
        destination.mkdir(parents=True, exist_ok=True)
        if bool(source.get("officialClient")):
            progress(2, "staging the official Steam client state")
            OfficialClientBootstrap.stage(self._require_client_home(session), destination)
        value = self._acquire(source, session, destination, progress)
        return self._session(value, session.account_alias, metadata=self._client_metadata(session))

    def _acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        progress: Any,
    ) -> dict[str, Any]:
        def handle(message: dict[str, Any]) -> None:
            if message.get("type") == "progress":
                progress(int(message.get("value") or 0), str(message.get("phase") or "Steam download"))

        return self.helper.invoke(
            {
                "command": "acquire",
                "principal": session.principal,
                "session": session.secret,
                # The official-client flag selects provider behavior and is not part of the
                # helper's depot source schema.
                "source": {key: item for key, item in source.items() if key != "officialClient"},
                "destination": str(destination.resolve()),
            },
            event=handle,
            timeout=14_400,
        )

    @staticmethod
    def _require_client_home(session: AuthSession) -> Path:
        client = (session.metadata or {}).get("officialClient")
        home = Path(str(client.get("path") or "")) if isinstance(client, dict) else Path()
        if not isinstance(client, dict) or client.get("state") != "ready" or not home.is_dir():
            reason = client.get("reason") if isinstance(client, dict) else ""
            raise SteamHelperError(
                "this runtime needs the official Steam client; run 'rhenium auth login steam' "
                "again on a Linux x86_64 host with Docker"
                + (f" ({reason})" if reason else "")
            )
        return home
