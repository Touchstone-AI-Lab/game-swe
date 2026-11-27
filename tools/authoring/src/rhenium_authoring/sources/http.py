from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx


def _retry_pause(headers: httpx.Headers) -> float:
    """Seconds to wait before retrying a rate-limited request (bounded)."""
    retry_after = headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), 120.0)
    reset = headers.get("x-ratelimit-reset")
    if reset and reset.isdigit():
        return min(max(float(reset) - time.time(), 1.0) + 1.0, 120.0)
    return 0.0


class SafeHttpClient:
    """Small JSON client whose errors never include headers or response bodies."""

    def __init__(self, client: httpx.Client, cache_dir: Path | None = None):
        self.client = client
        self.cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_dir.chmod(0o700)

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> Any:
        cache_path = self._cache_path(path, params)
        cached = self._read_cache(cache_path) if cache_path is not None else None
        headers = (
            {"If-None-Match": str(cached["etag"])} if cached is not None and cached.get("etag") else None
        )
        last_detail = ""
        pause = 0.0
        for attempt in range(5):
            if attempt:
                time.sleep(pause or 2**attempt)
            try:
                response = self.client.get(path, params=params, headers=headers)
                if response.status_code == 304 and cached is not None:
                    return cached["payload"]
                response.raise_for_status()
                value = response.json()
            except httpx.HTTPStatusError as error:
                code = error.response.status_code
                last_detail = f" (HTTP {code})"
                if code in (429, 403) or code >= 500:
                    # 403/429 cover GitHub rate limiting; wait for the window the
                    # server names (search resets every minute) before retrying.
                    pause = _retry_pause(error.response.headers)
                    continue
                break
            except httpx.HTTPError:
                last_detail = " (transport error)"
                continue
            except ValueError:
                last_detail = " (invalid JSON)"
                break
            else:
                if cache_path is not None:
                    self._write_cache(cache_path, response.headers.get("etag"), value)
                return value
        raise RuntimeError(f"source API request failed{last_detail}") from None

    def _cache_path(self, path: str, params: dict[str, str | int] | None) -> Path | None:
        if self.cache_dir is None:
            return None
        key = json.dumps([path, sorted((params or {}).items())], separators=(",", ":"))
        return self.cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    @staticmethod
    def _read_cache(path: Path) -> dict[str, Any] | None:
        if not path.is_file() or path.is_symlink():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) and "payload" in value else None

    @staticmethod
    def _write_cache(path: Path, etag: str | None, payload: Any) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"etag": etag, "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, path)
