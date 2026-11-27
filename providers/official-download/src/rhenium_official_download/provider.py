"""Acquire the exact files of an official, non-Steam distribution over HTTPS.

A runtime catalog names every file by exact HTTPS URL, file name, size and
SHA-256. ``acquire`` downloads them only during an explicit ``runtime prepare``,
keeps a file only when its size and digest match the pin, and treats any other
cache content as something for the operator to inspect, never to overwrite.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import SplitResult, urljoin, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from rhenium.core.auth import (
    AuthProvider,
    AuthProviderDescriptor,
    AuthSession,
    ChallengeCallback,
    ProgressCallback,
)

__all__ = ["DownloadFile", "OfficialDownloadProvider", "OfficialDownloadSource"]

VERSION = "0.1.0"
USER_AGENT = f"rhenium-official-download/{VERSION}"
_HOST = re.compile(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,199}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5
_CHUNK = 1 << 20
_PARTIAL_SUFFIX = ".partial"
_CACHE_MISMATCH = (
    "official-download cache is partial or does not match the pinned files; inspect it and "
    "prune the runtime before retrying (the provider never overwrites a cache)"
)


def _exact_https(value: str, *, allow_query: bool) -> SplitResult:
    """Parse an HTTPS URL that names its host exactly: no credentials, port or fragment."""
    if not value.isascii() or any(character.isspace() or ord(character) < 0x21 for character in value):
        raise ValueError("URL must be printable ASCII without whitespace")
    parts = urlsplit(value)
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or parts.netloc != host
        or _HOST.fullmatch(host) is None
        or not parts.path.startswith("/")
        or parts.fragment
        or (parts.query and not allow_query)
    ):
        raise ValueError("URL must be https://<lowercase-host>/<path> with no credentials or port")
    return parts


class DownloadFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    url: str
    sha256: str
    size: int = Field(gt=0, le=1 << 36)

    @model_validator(mode="after")
    def pinned_exactly(self) -> DownloadFile:
        if _NAME.fullmatch(self.name) is None:
            raise ValueError("file name must be a plain name without a path")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be 64 lowercase hexadecimal digits")
        _exact_https(self.url, allow_query=False)
        return self

    @property
    def host(self) -> str:
        return urlsplit(self.url).hostname or ""


class OfficialDownloadSource(BaseModel):
    """The ``official-download`` source schema of ``RuntimeSpec.source``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["official-download"]
    files: tuple[DownloadFile, ...] = Field(min_length=1)
    redirectHosts: tuple[str, ...] = ()
    # Passed through for the consuming runtime builder, which must enforce them itself.
    expectedFiles: tuple[str, ...] = ()
    sha256: str | None = None

    @model_validator(mode="after")
    def unique_names_and_hosts(self) -> OfficialDownloadSource:
        names = [item.name.casefold() for item in self.files]
        if len(names) != len(set(names)):
            raise ValueError("file names must be unique")
        if len(self.redirectHosts) != len(set(self.redirectHosts)) or any(
            _HOST.fullmatch(host) is None for host in self.redirectHosts
        ):
            raise ValueError("redirectHosts must be unique lowercase host names")
        return self


class OfficialDownloadProvider(AuthProvider):
    """Downloads pinned official distributions; there is no credential to store.

    ``login`` creates an empty session because runtime preparation always resolves an
    auth provider. Nothing is sent except a plain GET with a fixed User-Agent: no
    Authorization header, cookie or token. Redirects are followed one hop at a time
    and only to HTTPS hosts that the source declares. ``transport`` exists for tests.
    """

    descriptor = AuthProviderDescriptor(
        id="official-download",
        name="Pinned official download",
        version=VERSION,
        capabilities=("https", "sha256-pinned", "no-credentials"),
    )

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport

    # -- credentials ------------------------------------------------------------
    def login(
        self,
        account_alias: str,
        *,
        challenge: ChallengeCallback,
        progress: ProgressCallback,
    ) -> AuthSession:
        del challenge
        progress(100, "official downloads need no credentials; files are fetched only by runtime prepare")
        return AuthSession(
            provider_id=self.id, account_alias=account_alias, principal="anonymous", secret={}
        )

    def validate(self, session: AuthSession) -> AuthSession:
        if session.provider_id != self.id or session.secret:
            raise ValueError("invalid official-download session")
        return session

    # -- acquisition ------------------------------------------------------------
    @staticmethod
    def _source(source: dict[str, Any]) -> OfficialDownloadSource:
        try:
            return OfficialDownloadSource.model_validate(source)
        except ValidationError as error:
            fields = sorted(
                {".".join(str(part) for part in item["loc"]) or "source" for item in error.errors()}
            )
            raise ValueError(f"invalid official-download source: {', '.join(fields)}") from None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(_CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _cached(self, spec: OfficialDownloadSource, destination: Path) -> bool:
        """True for a cache holding exactly the pinned files, False for an empty one.

        Anything else (a leftover partial download, a missing, extra or changed file)
        fails closed: the provider never deletes or overwrites a cache it did not
        just write itself.
        """
        if destination.is_symlink():
            raise ValueError("official-download cache must not be a symbolic link")
        if not destination.exists():
            return False
        if not destination.is_dir():
            raise ValueError("official-download cache is not a directory")
        entries = {entry.name: entry for entry in destination.iterdir()}
        if not entries:
            return False
        pinned = {item.name: item for item in spec.files}
        if set(entries) != set(pinned):
            raise ValueError(_CACHE_MISMATCH)
        for name, entry in entries.items():
            status = entry.lstat()
            if (
                not stat.S_ISREG(status.st_mode)
                or status.st_size != pinned[name].size
                or self._sha256(entry) != pinned[name].sha256
            ):
                raise ValueError(_CACHE_MISMATCH)
        return True

    @staticmethod
    def _redirect(current: str, location: str | None, allowed: frozenset[str]) -> str:
        if not location:
            raise RuntimeError("redirect without a location")
        try:
            target = _exact_https(urljoin(current, location), allow_query=True)
        except ValueError:
            raise RuntimeError("redirect leaves HTTPS or names credentials or a port") from None
        if (target.hostname or "") not in allowed:
            raise RuntimeError(f"redirect to undeclared host {target.hostname or '?'}")
        return target.geturl()

    @contextmanager
    def _client(self) -> Iterator[httpx.Client]:
        with httpx.Client(
            transport=self._transport,
            # Proxy settings from the environment would bypass an injected test transport.
            trust_env=self._transport is None,
            follow_redirects=False,
            timeout=httpx.Timeout(60.0, connect=30.0),
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
        ) as client:
            yield client

    def _download(
        self,
        client: httpx.Client,
        item: DownloadFile,
        allowed: frozenset[str],
        target: Path,
        created: list[Path],
        report: ProgressCallback,
    ) -> None:
        """Stream one pinned file into a new partial file, verifying size and digest."""
        url = item.url
        for _hop in range(_MAX_REDIRECTS + 1):
            with client.stream("GET", url) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    url = self._redirect(url, response.headers.get("location"), allowed)
                    continue
                if response.status_code != 200:
                    raise RuntimeError(f"server answered HTTP {response.status_code}")
                encoding = response.headers.get("content-encoding", "identity").strip().lower()
                if encoding != "identity":
                    raise RuntimeError(f"unexpected content encoding {encoding}")
                length = response.headers.get("content-length")
                if length is not None and length.strip() != str(item.size):
                    raise RuntimeError("Content-Length does not match the pinned size")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
                try:
                    descriptor = os.open(target, flags, 0o600)
                except FileExistsError:
                    # Another acquisition is writing the same cache: leave its file alone.
                    raise ValueError(_CACHE_MISMATCH) from None
                created.append(target)
                digest = hashlib.sha256()
                received = 0
                with os.fdopen(descriptor, "wb") as stream:
                    for chunk in response.iter_bytes(_CHUNK):
                        received += len(chunk)
                        if received > item.size:
                            raise RuntimeError("download is larger than the pinned size")
                        digest.update(chunk)
                        stream.write(chunk)
                        report(received, f"downloading {item.name}")
                    stream.flush()
                    os.fsync(stream.fileno())
                if received != item.size:
                    raise RuntimeError("download is shorter than the pinned size")
                if digest.hexdigest() != item.sha256:
                    raise RuntimeError("SHA-256 does not match the pinned digest")
                return
        raise RuntimeError("too many redirects")

    @staticmethod
    def _publish(partial: Path, final: Path) -> None:
        """Give a verified partial file its final name without replacing anything."""
        try:
            os.link(partial, final)
        except FileExistsError:
            raise ValueError(_CACHE_MISMATCH) from None
        except OSError:
            # A file system without hard links: rename, after checking nothing is there.
            if os.path.lexists(final):
                raise ValueError(_CACHE_MISMATCH) from None
            os.rename(partial, final)
            return
        partial.unlink()

    def acquire(
        self,
        source: dict[str, Any],
        session: AuthSession,
        destination: Path,
        *,
        progress: ProgressCallback,
    ) -> AuthSession:
        self.validate(session)
        spec = self._source(source)
        if self._cached(spec, destination):
            progress(100, "reusing verified official download cache")
            return session
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        total = sum(item.size for item in spec.files)
        done = 0
        last = -1

        def report(received: int, phase: str) -> None:
            nonlocal last
            percent = min(99, (done + received) * 100 // total)
            if percent != last:
                last = percent
                progress(percent, phase)

        created: list[Path] = []
        published: list[Path] = []
        try:
            with self._client() as client:
                for item in spec.files:
                    allowed = frozenset({item.host, *spec.redirectHosts})
                    partial = destination / f".{item.name}{_PARTIAL_SUFFIX}"
                    try:
                        self._download(client, item, allowed, partial, created, report)
                    except httpx.HTTPError as error:
                        # The message of an httpx error can quote a signed redirect URL.
                        raise RuntimeError(
                            f"official download of {item.name} from {item.host} failed: "
                            f"{type(error).__name__}"
                        ) from None
                    except RuntimeError as error:
                        raise RuntimeError(
                            f"official download of {item.name} from {item.host} failed: {error}"
                        ) from None
                    done += item.size
            for item in spec.files:
                final = destination / item.name
                self._publish(destination / f".{item.name}{_PARTIAL_SUFFIX}", final)
                published.append(final)
        except BaseException:
            for path in (*created, *published):
                path.unlink(missing_ok=True)
            raise
        if not self._cached(spec, destination):
            raise ValueError(_CACHE_MISMATCH)
        progress(100, "official download verified")
        return session
