"""Public dependency downloads retry transport failures without relaxing pins."""
from __future__ import annotations

import hashlib
import io
import json
import runpy
import sys
import time
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / (
    "benchmarks/slay-the-spire-core/private/native-runtime/scripts/fetch_locked_maven.py"
)
RELATIVE = "example/library/1/library-1.jar"
CONTENT = b"fake public dependency"


def invoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({
        "repository_ids": ["central"], "artifacts": [{
            "path": RELATIVE, "sha256": hashlib.sha256(CONTENT).hexdigest(),
            "bytes": len(CONTENT), "repository_ids": ["central"],
        }],
    }))
    monkeypatch.setattr(sys, "argv", [
        str(SCRIPT), "--lock", str(lock), "--repository", str(tmp_path / "repository"),
        "--cache", str(tmp_path / "cache"),
    ])
    runpy.run_path(str(SCRIPT), run_name="__main__")


def test_transport_retry_stores_only_verified_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    waits: list[float] = []

    def urlopen(url: str, *, timeout: int) -> io.BytesIO:
        calls.append(url)
        assert timeout == 30
        if len(calls) < 3:
            raise urllib.error.URLError("temporary TLS handshake failure")
        return io.BytesIO(CONTENT)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", waits.append)
    invoke(tmp_path, monkeypatch)
    assert len(calls) == 3 and waits == [1, 2]
    assert (tmp_path / "cache" / RELATIVE).read_bytes() == CONTENT
    assert (tmp_path / "repository" / RELATIVE).read_bytes() == CONTENT


def test_verified_cache_needs_no_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cached = tmp_path / "cache" / RELATIVE
    cached.parent.mkdir(parents=True)
    cached.write_bytes(CONTENT)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a pinned public cache hit must not download again")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    invoke(tmp_path, monkeypatch)
    assert (tmp_path / "repository" / RELATIVE).read_bytes() == CONTENT


def test_corrupt_cache_is_replaced_only_after_verified_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = tmp_path / "cache" / RELATIVE
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"corrupt")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(CONTENT))
    invoke(tmp_path, monkeypatch)
    assert cached.read_bytes() == CONTENT


def test_hash_mismatch_fails_without_populating_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"X" * len(CONTENT)))
    with pytest.raises(AssertionError):
        invoke(tmp_path, monkeypatch)
    assert not (tmp_path / "cache" / RELATIVE).exists()
    assert not (tmp_path / "repository" / RELATIVE).exists()


def test_retry_exhaustion_is_bounded_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    waits: list[float] = []

    def unavailable(*args: object, **kwargs: object) -> None:
        calls.append(1)
        raise urllib.error.URLError("unavailable")

    monkeypatch.setattr(urllib.request, "urlopen", unavailable)
    monkeypatch.setattr(time, "sleep", waits.append)
    with pytest.raises(urllib.error.URLError):
        invoke(tmp_path, monkeypatch)
    assert len(calls) == 6 and waits == [1, 2, 4, 8, 8]
    assert not (tmp_path / "cache" / RELATIVE).exists()


def test_permanent_http_error_is_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise urllib.error.HTTPError("https://repo.maven.apache.org", 404, "not found", Message(), None)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a permanent HTTP error must fail immediately")

    monkeypatch.setattr(urllib.request, "urlopen", unavailable)
    monkeypatch.setattr(time, "sleep", forbidden)
    with pytest.raises(urllib.error.HTTPError):
        invoke(tmp_path, monkeypatch)
