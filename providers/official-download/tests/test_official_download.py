from __future__ import annotations

import hashlib
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from rhenium_official_download.provider import USER_AGENT, OfficialDownloadProvider

from rhenium.core.auth import AuthSession

SERVER = b"pinned official server bytes" * 64
PLUGIN = b"second pinned file"
URL = "https://downloads.example.org/releases/v1/server.jar"
MIRROR = "objects.example-cdn.net"


def pin(name: str, url: str, data: bytes) -> dict[str, Any]:
    return {"name": name, "url": url, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def source(*files: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"kind": "official-download", "files": list(files or [pin("server.jar", URL, SERVER)]), **extra}


Handler = Callable[[httpx.Request], httpx.Response]


class Server:
    """A fake HTTPS origin: no socket, no network, every request recorded."""

    def __init__(self, routes: dict[str, Handler | bytes]):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes.get(str(request.url))
        if route is None:
            return httpx.Response(404)
        if isinstance(route, bytes):
            return httpx.Response(200, content=route)
        return route(request)


def redirect(location: str, status: int = 302) -> Handler:
    return lambda _request: httpx.Response(status, headers={"location": location})


def streamed(body: bytes, headers: dict[str, str] | None = None) -> Handler:
    """A chunked response: no Content-Length unless one is given explicitly."""
    return lambda _request: httpx.Response(200, content=iter([body]), headers=headers)


def acquire(
    server: Server, destination: Path, spec: dict[str, Any] | None = None
) -> list[tuple[int, str]]:
    provider = OfficialDownloadProvider(transport=httpx.MockTransport(server))
    session = provider.login("default", challenge=lambda _item: None, progress=lambda *_: None)
    events: list[tuple[int, str]] = []
    provider.acquire(
        spec or source(), session, destination, progress=lambda value, phase: events.append((value, phase))
    )
    return events


def test_login_is_credential_free_and_validation_rejects_secrets() -> None:
    provider = OfficialDownloadProvider()
    session = provider.login("default", challenge=lambda _item: None, progress=lambda *_: None)
    assert session.secret == {} and session.principal == "anonymous"
    assert provider.validate(session) == session
    with pytest.raises(ValueError, match="invalid official-download session"):
        provider.validate(session.model_copy(update={"secret": {"token": "x"}}))
    with pytest.raises(ValueError, match="invalid official-download session"):
        provider.validate(
            AuthSession(provider_id="steam", account_alias="default", principal="x", secret={})
        )


def test_download_writes_exactly_the_pinned_file(tmp_path: Path) -> None:
    server = Server({URL: SERVER})
    cache = tmp_path / "cache"
    events = acquire(server, cache)
    assert sorted(path.name for path in cache.iterdir()) == ["server.jar"]
    assert (cache / "server.jar").read_bytes() == SERVER
    assert stat.S_IMODE((cache / "server.jar").stat().st_mode) == 0o600
    assert events[-1] == (100, "official download verified")
    assert all(0 <= value <= 100 for value, _phase in events)
    (request,) = server.requests
    assert request.method == "GET"
    assert request.headers["user-agent"] == USER_AGENT
    assert "authorization" not in request.headers and "cookie" not in request.headers


def test_unchanged_cache_is_reused_without_a_request(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    acquire(Server({URL: SERVER}), cache)
    offline = Server({})
    events = acquire(offline, cache)
    assert offline.requests == []
    assert events == [(100, "reusing verified official download cache")]
    assert (cache / "server.jar").read_bytes() == SERVER


def test_empty_cache_directory_created_by_core_is_filled(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    acquire(Server({URL: SERVER}), cache)
    assert (cache / "server.jar").read_bytes() == SERVER


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"x" * len(SERVER), "SHA-256 does not match"),
        (SERVER[:-1], "shorter than the pinned size"),
        (SERVER + b"!", "larger than the pinned size"),
    ],
)
def test_mismatched_download_fails_closed_and_leaves_the_cache_empty(
    tmp_path: Path, body: bytes, message: str
) -> None:
    cache = tmp_path / "cache"
    # No Content-Length, so the streamed body itself has to be checked.
    with pytest.raises(RuntimeError, match=message):
        acquire(Server({URL: streamed(body)}), cache)
    assert list(cache.iterdir()) == []
    acquire(Server({URL: SERVER}), cache)
    assert (cache / "server.jar").read_bytes() == SERVER


def test_content_length_and_encoding_must_match_the_pin(tmp_path: Path) -> None:
    long = streamed(SERVER, {"content-length": str(len(SERVER) + 1)})
    with pytest.raises(RuntimeError, match="Content-Length"):
        acquire(Server({URL: long}), tmp_path / "a")
    gzip = streamed(SERVER, {"content-encoding": "gzip"})
    with pytest.raises(RuntimeError, match="content encoding"):
        acquire(Server({URL: gzip}), tmp_path / "b")


def test_redirect_to_a_declared_host_is_followed(tmp_path: Path) -> None:
    signed = f"https://{MIRROR}/asset/1?X-Signature=secret-token"
    server = Server({URL: redirect(signed), signed: SERVER})
    acquire(server, tmp_path / "cache", source(redirectHosts=[MIRROR]))
    assert [str(request.url) for request in server.requests] == [URL, signed]
    assert (tmp_path / "cache" / "server.jar").read_bytes() == SERVER


def test_relative_redirect_on_the_declared_host_is_followed(tmp_path: Path) -> None:
    moved = "https://downloads.example.org/releases/v1/server-final.jar"
    server = Server({URL: redirect("server-final.jar", 301), moved: SERVER})
    acquire(server, tmp_path / "cache")
    assert (tmp_path / "cache" / "server.jar").read_bytes() == SERVER


@pytest.mark.parametrize(
    ("location", "message"),
    [
        (f"https://{MIRROR}/asset/1", "undeclared host objects.example-cdn.net"),
        ("https://evil.example.com/server.jar", "undeclared host evil.example.com"),
        ("http://downloads.example.org/releases/v1/server.jar", "leaves HTTPS"),
        ("https://user:pass@downloads.example.org/server.jar", "leaves HTTPS"),
        ("https://downloads.example.org:8443/server.jar", "leaves HTTPS"),
    ],
)
def test_redirect_off_the_declared_hosts_fails_closed(tmp_path: Path, location: str, message: str) -> None:
    server = Server({URL: redirect(location), location: SERVER})
    with pytest.raises(RuntimeError, match=message):
        acquire(server, tmp_path / "cache")
    assert len(server.requests) == 1  # the undeclared target is never contacted
    assert list((tmp_path / "cache").iterdir()) == []


def test_redirect_loops_are_bounded(tmp_path: Path) -> None:
    server = Server({URL: redirect(URL)})
    with pytest.raises(RuntimeError, match="too many redirects"):
        acquire(server, tmp_path / "cache")
    assert len(server.requests) == 6


def test_errors_never_quote_a_signed_redirect_url(tmp_path: Path) -> None:
    signed = f"https://{MIRROR}/asset/1?X-Signature=secret-token"

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    failing: tuple[Handler, ...] = (lambda _request: httpx.Response(500), broken)
    for target in failing:
        server = Server({URL: redirect(signed), signed: target})
        with pytest.raises(RuntimeError) as info:
            acquire(server, tmp_path / "cache", source(redirectHosts=[MIRROR]))
        assert "secret-token" not in str(info.value)
        assert str(info.value).startswith("official download of server.jar from downloads.example.org")


def test_http_error_status_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="HTTP 404"):
        acquire(Server({}), tmp_path / "cache")


def test_partial_cache_fails_closed_and_is_not_touched(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ".server.jar.partial").write_bytes(SERVER[:10])
    server = Server({URL: SERVER})
    with pytest.raises(ValueError, match="partial or does not match"):
        acquire(server, cache)
    assert server.requests == []
    assert (cache / ".server.jar.partial").read_bytes() == SERVER[:10]
    assert not (cache / "server.jar").exists()


def test_changed_cache_is_never_overwritten(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    acquire(Server({URL: SERVER}), cache)
    tampered = b"y" * len(SERVER)
    (cache / "server.jar").write_bytes(tampered)
    server = Server({URL: SERVER})
    with pytest.raises(ValueError, match="partial or does not match"):
        acquire(server, cache)
    assert server.requests == []
    assert (cache / "server.jar").read_bytes() == tampered
    (cache / "server.jar").write_bytes(SERVER)
    (cache / "notes.txt").write_text("operator file")
    with pytest.raises(ValueError, match="partial or does not match"):
        acquire(server, cache)
    assert (cache / "notes.txt").read_text() == "operator file"


def test_symlinked_cache_entries_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.jar"
    outside.write_bytes(SERVER)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "server.jar").symlink_to(outside)
    with pytest.raises(ValueError, match="partial or does not match"):
        acquire(Server({URL: SERVER}), cache)
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        acquire(Server({URL: SERVER}), linked)


def test_multi_file_source_is_all_or_nothing(tmp_path: Path) -> None:
    second = "https://downloads.example.org/releases/v1/plugin.jar"
    spec = source(pin("server.jar", URL, SERVER), pin("plugin.jar", second, PLUGIN))
    cache = tmp_path / "cache"
    with pytest.raises(RuntimeError, match="plugin.jar"):
        acquire(Server({URL: SERVER, second: b"tampered bytes...."}), cache, spec)
    assert list(cache.iterdir()) == []
    acquire(Server({URL: SERVER, second: PLUGIN}), cache, spec)
    assert sorted(path.name for path in cache.iterdir()) == ["plugin.jar", "server.jar"]
    (cache / "plugin.jar").unlink()
    with pytest.raises(ValueError, match="partial or does not match"):
        acquire(Server({URL: SERVER, second: PLUGIN}), cache, spec)


def test_builder_fields_are_passed_through_uninterpreted(tmp_path: Path) -> None:
    spec = source(expectedFiles=["server.jar"], sha256="0" * 64)
    acquire(Server({URL: SERVER}), tmp_path / "cache", spec)
    assert (tmp_path / "cache" / "server.jar").read_bytes() == SERVER


@pytest.mark.parametrize(
    "spec",
    [
        {"kind": "local-files", "files": [pin("server.jar", URL, SERVER)]},
        {"kind": "official-download", "files": []},
        source(pin("server.jar", "http://downloads.example.org/server.jar", SERVER)),
        source(pin("server.jar", "https://Downloads.example.org/server.jar", SERVER)),
        source(pin("server.jar", "https://user@downloads.example.org/server.jar", SERVER)),
        source(pin("server.jar", "https://downloads.example.org:443/server.jar", SERVER)),
        source(pin("server.jar", "https://downloads.example.org/server.jar?token=1", SERVER)),
        source(pin("server.jar", "https://downloads.example.org/server.jar#x", SERVER)),
        source(pin("server.jar", "https://127.0.0.1/server.jar", SERVER)),
        source(pin("../server.jar", URL, SERVER)),
        source(pin("nested/server.jar", URL, SERVER)),
        source(pin(".server.jar", URL, SERVER)),
        source(pin("server.jar", URL, SERVER), pin("Server.jar", URL, SERVER)),
        source({**pin("server.jar", URL, SERVER), "sha256": "A" * 64}),
        source({**pin("server.jar", URL, SERVER), "size": 0}),
        source({**pin("server.jar", URL, SERVER), "mirror": URL}),
        source(redirectHosts=["Objects.Example.net"]),
        source(redirectHosts=[MIRROR, MIRROR]),
        source(unknown=True),
    ],
)
def test_malformed_sources_are_rejected_before_any_request(tmp_path: Path, spec: dict[str, Any]) -> None:
    server = Server({URL: SERVER})
    with pytest.raises(ValueError, match="invalid official-download source"):
        acquire(server, tmp_path / "cache", spec)
    assert server.requests == []
    assert not (tmp_path / "cache").exists()
