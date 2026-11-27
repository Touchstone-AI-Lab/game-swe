from __future__ import annotations

import base64
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from pydantic import HttpUrl

from rhenium_authoring.models import HistoricalFix, SourceKind, SourceProject

from .base import (
    GAME_REPOSITORY_MARKERS,
    GAME_SEARCH_QUERIES,
    LICENSE_ALLOWLIST,
    SUPPORTED_GAMES,
    changes_native_code,
    is_runtime_source,
    validate_fix_source,
)
from .http import SafeHttpClient

_GITHUB_REPOSITORY = re.compile(r"^/([^/]+)/([^/]+?)(?:\.git)?/?$")
_FIX_LANGUAGE = re.compile(
    r"\b(?:bug|crash|error|fix(?:e[ds])?|incorrect|prevent|regression|resolve[ds]?)\b",
    re.IGNORECASE,
)


class GitHubSource:
    def __init__(
        self,
        token: str | None,
        client: httpx.Client | None = None,
        cache_dir: Path | None = None,
    ):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "rhenium-authoring/0.1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._owned = client is None
        self._client = client or httpx.Client(base_url="https://api.github.com", headers=headers, timeout=30)
        self.http = SafeHttpClient(self._client, cache_dir)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    @staticmethod
    def repository_name(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
            raise ValueError("source URL is not an HTTPS GitHub repository")
        match = _GITHUB_REPOSITORY.fullmatch(parsed.path)
        if match is None:
            raise ValueError("source URL is not a GitHub repository root")
        return f"{match.group(1)}/{match.group(2)}"

    def discover(self, game_id: str, limit: int) -> list[SourceProject]:
        if game_id not in SUPPORTED_GAMES:
            return []
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in GAME_SEARCH_QUERIES[game_id]:
            if len(items) >= limit:
                break
            try:
                payload = self.http.get_json(
                    "/search/repositories",
                    params={"q": query, "per_page": min(limit, 100), "sort": "stars"},
                )
            except RuntimeError:
                if not items:
                    raise
                continue  # one exhausted or failing query must not drop the others
            for raw in _object_list(payload, "items"):
                full_name = raw.get("full_name")
                license_value = raw.get("license")
                license_id = license_value.get("spdx_id") if isinstance(license_value, dict) else None
                # Only allowlisted repositories count towards the limit, so a
                # query full of copyleft projects does not end discovery early.
                if (
                    isinstance(full_name, str)
                    and full_name.casefold() not in seen
                    and license_id in LICENSE_ALLOWLIST
                ):
                    seen.add(full_name.casefold())
                    items.append(raw)
        projects: list[SourceProject] = []
        for raw in items[:limit]:
            license_value = raw.get("license")
            license_id = license_value.get("spdx_id") if isinstance(license_value, dict) else None
            html_url = raw.get("html_url")
            full_name = raw.get("full_name")
            default_branch = raw.get("default_branch")
            if (
                not isinstance(html_url, str)
                or not html_url
                or not isinstance(full_name, str)
                or not full_name
            ):
                continue
            projects.append(
                SourceProject(
                    source=SourceKind.GITHUB,
                    external_id=full_name,
                    game_id=game_id,
                    project_url=HttpUrl(html_url),
                    source_url=HttpUrl(html_url),
                    license_spdx=license_id,
                    immutable_ref=default_branch if isinstance(default_branch, str) else None,
                )
            )
        return projects

    def canonical_project(self, project: SourceProject) -> SourceProject:
        source_url = str(project.source_url or project.project_url)
        repository = self.repository_name(source_url)
        payload = self.http.get_json(f"/repos/{repository}")
        license_value = payload.get("license")
        license_id = license_value.get("spdx_id") if isinstance(license_value, dict) else None
        if license_id not in LICENSE_ALLOWLIST:
            raise ValueError("repository license is not in the authoring allowlist")
        html_url = payload.get("html_url")
        if not isinstance(html_url, str) or not html_url:
            raise RuntimeError("GitHub repository response omitted html_url")
        return SourceProject(
            source=project.source,
            external_id=repository,
            game_id=project.game_id,
            project_url=project.project_url,
            source_url=HttpUrl(html_url),
            license_spdx=license_id,
            immutable_ref=None,
        )

    def historical_fixes(self, project: SourceProject, limit: int) -> list[HistoricalFix]:
        try:
            canonical = self.canonical_project(project)
        except ValueError:
            # Search hits outside the licence allowlist yield nothing; they
            # must not end the harvest for every other repository.
            return []
        repository = self.repository_name(str(canonical.source_url))
        markers = GAME_REPOSITORY_MARKERS.get(canonical.game_id, ())
        if markers and not self._has_marker(repository, markers):
            # Search terms also match forks, launchers and unrelated tooling;
            # only a repository laid out as a mod/plugin of this game is mined.
            return []
        fixes: list[HistoricalFix] = []
        for item in self._merged_pulls(repository, limit):
            number = item.get("number")
            if not isinstance(number, int):
                continue
            title = item.get("title")
            body = item.get("body") or ""
            user = item.get("user")
            login = user.get("login") if isinstance(user, dict) else ""
            if (
                not isinstance(title, str)
                or not _FIX_LANGUAGE.search(f"{title}\n{body}")
                or (isinstance(login, str) and login.casefold().endswith("[bot]"))
            ):
                continue
            pull = self.http.get_json(f"/repos/{repository}/pulls/{number}")
            if pull.get("merged_at") is None or pull.get("draft") is True:
                continue
            fixed_sha = pull.get("merge_commit_sha")
            if not isinstance(fixed_sha, str) or re.fullmatch(r"[0-9a-f]{40}", fixed_sha) is None:
                continue
            commit = self.http.get_json(f"/repos/{repository}/commits/{fixed_sha}", params={"per_page": 100})
            parents = _object_list(commit, "parents")
            if not isinstance(commit, dict) or commit.get("sha") != fixed_sha or not parents:
                continue
            base_sha = parents[0].get("sha")
            # Use the landed commit's first-parent diff, not a mutable PR base ref.
            files_payload = _object_list(commit, "files")
            if len(files_payload) >= 100:
                continue  # reject potentially truncated commit evidence
            all_filenames = [value.get("filename") for value in _object_list(files_payload, None)]
            if changes_native_code(
                canonical.game_id, [name for name in all_filenames if isinstance(name, str)]
            ):
                continue  # the described behavior lives in native code, not in the mod
            body = body or pull.get("body") or ""
            patches: list[str] = []
            filenames: list[str] = []
            for file_value in _object_list(files_payload, None):
                filename = file_value.get("filename")
                patch = file_value.get("patch")
                if (
                    isinstance(filename, str)
                    and is_runtime_source(canonical.game_id, filename)
                    and isinstance(patch, str)
                    and patch.strip()
                ):
                    filenames.append(filename)
                    patches.append(f"diff --git a/{filename} b/{filename}\n{patch}")
            if not (
                isinstance(base_sha, str)
                and isinstance(fixed_sha, str)
                and isinstance(title, str)
                and patches
            ):
                continue
            try:
                base_files = self._changed_file_context(repository, filenames, base_sha)
                fixed_files = self._changed_file_context(repository, filenames, fixed_sha)
            except ValueError:
                continue  # oversized change context: skip this fix, keep harvesting
            fix = HistoricalFix(
                id=f"github-pr-{number}",
                game_id=canonical.game_id,
                repository_url=HttpUrl(str(canonical.source_url)),
                license_spdx=str(canonical.license_spdx),
                base_sha=base_sha,
                fixed_sha=fixed_sha,
                issue_text=f"{title}\n\n{body}".strip(),
                patch="\n".join(patches),
                changed_files=tuple(filenames),
                base_files=base_files,
                fixed_files=fixed_files,
            )
            try:
                validate_fix_source(fix)
            except ValueError:
                continue  # unsupported licence or no implementation change in context
            fixes.append(fix)
            if len(fixes) >= limit:
                break
        return fixes

    def _merged_pulls(self, repository: str, limit: int) -> Iterator[dict[str, Any]]:
        page_size = min(max(limit * 10, 30), 100)
        for page in range(1, 4):
            search = self.http.get_json(
                "/search/issues",
                params={
                    "q": f"repo:{repository} is:pr is:merged",
                    "sort": "updated",
                    "order": "desc",
                    "per_page": page_size,
                    "page": page,
                },
            )
            items = _object_list(search, "items")
            yield from items
            if len(items) < page_size:
                break

    def _has_marker(self, repository: str, markers: tuple[str, ...]) -> bool:
        """Whether the default branch holds one of the game's marker files."""
        for marker in markers:
            path = f"/repos/{repository}/contents/{quote(marker, safe='/')}"
            try:
                response = self._client.get(path)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                raise RuntimeError("Git repository marker request failed") from None
            if isinstance(payload, dict) and payload.get("type") == "file":
                return True
        return False

    def _changed_file_context(self, repository: str, filenames: list[str], revision: str) -> dict[str, str]:
        result: dict[str, str] = {}
        total = 0
        for filename in filenames:
            path = f"/repos/{repository}/contents/{quote(filename, safe='/')}"
            try:
                response = self._client.get(path, params={"ref": revision})
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                raise RuntimeError("Git source context request failed") from None
            if not isinstance(payload, dict) or payload.get("encoding") != "base64":
                continue
            encoded = payload.get("content")
            if not isinstance(encoded, str):
                continue
            try:
                compact = "".join(encoded.split())
                content = base64.b64decode(compact, validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
            total += len(content.encode())
            if total > 512 * 1024:
                raise ValueError("GitHub changed-file source context exceeds 512 KiB")
            result[filename] = content
        return result


def _object_list(payload: Any, key: str | None) -> list[dict[str, Any]]:
    value = payload.get(key) if key is not None and isinstance(payload, dict) else payload
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _nested_string(value: dict[str, Any], *keys: str) -> str | None:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, str) else None
