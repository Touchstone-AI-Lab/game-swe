"""Walk a repository's real history for landed fixes, deeper on every run.

Two sources are read page by page: the repository's closed pull requests (the
REST list endpoint, not search, so it is not capped at 1000 results and does
not spend the search quota) and the default branch's commits, which also finds
fixes pushed without a pull request. A per-repository cursor in the authoring
database makes the next run continue where this one stopped.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from pydantic import HttpUrl, ValidationError

from ..sources.base import changes_native_code, is_runtime_source
from ..sources.github import _FIX_LANGUAGE, GitHubSource, _object_list
from ..state import AuthoringStore
from .models import HistoryFix

PAGE_SIZE = 100
# Build inputs the verifier restores from the starter. A fix that edits one of
# them cannot be the reference: the verifier would revert part of it.
_FROZEN_NAMES = frozenset(
    {
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "gradle.properties",
        "gradlew",
        "gradlew.bat",
        "pom.xml",
        "mvnw",
        "mvnw.cmd",
    }
)
_PLUGIN_METADATA = re.compile(r"^(?:[^/]+/){0,2}src/main/resources/(?:paper-)?plugin\.yml$")
_BUILD_FILE = re.compile(r"^(?:[^/]+/){0,2}(?:pom\.xml|build\.gradle(?:\.kts)?)$")
_SQUASH_REFERENCE = re.compile(r"\(#\d+\)\s*$")


@dataclass
class DiscoveryStats:
    """Counts of what the walk saw and why candidates were dropped."""

    pages: int = 0
    seen: int = 0
    accepted: int = 0
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1


def touches_frozen_build(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return bool(parts) and (parts[-1] in _FROZEN_NAMES or "gradle" in parts[:-1] or ".mvn" in parts)


class HistoryDiscovery:
    def __init__(
        self,
        github: GitHubSource,
        store: AuthoringStore,
        *,
        pages_per_run: int = 3,
        max_changed_lines: int = 150,
        on_event: Callable[[dict[str, object]], None] | None = None,
    ):
        self.github = github
        self.store = store
        self.pages_per_run = pages_per_run
        self.max_changed_lines = max_changed_lines
        self.on_event = on_event or (lambda _event: None)
        self.stats = DiscoveryStats()

    # -- repositories -------------------------------------------------------

    def plugin_layout(self, repository: str, branch: str) -> bool:
        """Whether the default branch looks like a Java Paper/Bukkit plugin build.

        One recursive tree request covers multi-module layouts (the plugin in
        ``spigot/`` or ``<Name>/``) that a fixed marker path misses.
        """
        payload = self.github.http.get_json(
            f"/repos/{repository}/git/trees/{branch}", params={"recursive": 1}
        )
        paths = [
            str(item.get("path"))
            for item in _object_list(payload, "tree")
            if item.get("type") == "blob" and isinstance(item.get("path"), str)
        ]
        has_metadata = any(_PLUGIN_METADATA.fullmatch(path) for path in paths)
        has_build = any(_BUILD_FILE.fullmatch(path) for path in paths)
        java = sum(path.endswith(".java") for path in paths)
        kotlin = sum(path.endswith(".kt") for path in paths)
        truncated = isinstance(payload, dict) and payload.get("truncated") is True
        return has_metadata and has_build and (java > kotlin or truncated)

    # -- fixes ---------------------------------------------------------------

    def fixes(
        self,
        repository: str,
        repository_url: str,
        license_spdx: str,
        game_id: str,
        *,
        limit: int,
        exclude: set[str],
    ) -> Iterator[HistoryFix]:
        found = 0
        seen_shas: set[str] = set()
        for source in ("pulls", "commits"):
            if found >= limit:
                return
            for item in self._walk(repository, source):
                self.stats.seen += 1
                candidate = self._candidate(item, source)
                if candidate is None:
                    continue
                fixed_sha, title, description, message, number = candidate
                key = f"{repository_url.rstrip('/').casefold()}@{fixed_sha}"
                if fixed_sha in seen_shas or key in exclude:
                    self.stats.reject("already used or seen")
                    continue
                seen_shas.add(fixed_sha)
                fix = self._fix(
                    repository,
                    repository_url,
                    license_spdx,
                    game_id,
                    fixed_sha=fixed_sha,
                    origin="pull" if source == "pulls" else "commit",
                    number=number,
                    title=title,
                    description=description,
                    message=message,
                )
                if fix is None:
                    continue
                self.stats.accepted += 1
                found += 1
                yield fix
                if found >= limit:
                    return

    def seed(
        self, repository: str, repository_url: str, license_spdx: str, game_id: str, fixed_sha: str
    ) -> HistoryFix | None:
        """One named landed commit, with the same filters as the history walk."""
        try:
            commit = self.github.http.get_json(f"/repos/{repository}/commits/{fixed_sha}")
        except RuntimeError:
            self.stats.reject("commit unavailable")
            return None
        body = commit.get("commit") if isinstance(commit, dict) else None
        message = str(body.get("message") or "") if isinstance(body, dict) else ""
        title, _, rest = message.partition("\n")
        return self._fix(
            repository,
            repository_url,
            license_spdx,
            game_id,
            fixed_sha=str(commit.get("sha") or fixed_sha) if isinstance(commit, dict) else fixed_sha,
            origin="commit",
            number=None,
            title=title.strip() or fixed_sha[:12],
            description="",
            message=rest.strip(),
        )

    def _walk(self, repository: str, source: str) -> Iterator[dict[str, Any]]:
        page, exhausted = self.store.history_cursor(repository, source)
        if exhausted:
            return
        for _ in range(self.pages_per_run):
            path = f"/repos/{repository}/pulls" if source == "pulls" else f"/repos/{repository}/commits"
            params: dict[str, str | int] = {"per_page": PAGE_SIZE, "page": page}
            if source == "pulls":
                params.update({"state": "closed", "sort": "created", "direction": "desc"})
            try:
                items = _object_list(self.github.http.get_json(path, params=params), None)
            except RuntimeError:
                self.on_event({"stage": "history-walk", "repository": repository, "status": "failed"})
                return
            self.stats.pages += 1
            done = len(items) < PAGE_SIZE
            yield from items
            # Advanced only once the whole page was consumed: a run that stops
            # mid-page (its per-repository limit reached) re-reads that page next
            # time, cheaply, because every response is ETag-cached.
            self.store.advance_history_cursor(repository, source, page + 1, exhausted=done)
            if done:
                return
            page += 1

    def _candidate(self, item: dict[str, Any], source: str) -> tuple[str, str, str, str, int | None] | None:
        if source == "pulls":
            user = item.get("user")
            login = user.get("login") if isinstance(user, dict) else ""
            title, body = item.get("title"), item.get("body") or ""
            sha, number = item.get("merge_commit_sha"), item.get("number")
            if item.get("merged_at") is None or item.get("draft") is True:
                self.stats.reject("not merged")
                return None
            if isinstance(login, str) and login.casefold().endswith("[bot]"):
                self.stats.reject("bot author")
                return None
            if not isinstance(title, str) or not isinstance(sha, str) or not isinstance(number, int):
                return None
            if not _FIX_LANGUAGE.search(f"{title}\n{body}"):
                self.stats.reject("not described as a fix")
                return None
            return sha, title, str(body), "", number
        commit = item.get("commit")
        message = commit.get("message") if isinstance(commit, dict) else None
        sha, parents = item.get("sha"), _object_list(item, "parents")
        author = item.get("author")
        login = author.get("login") if isinstance(author, dict) else ""
        if not isinstance(message, str) or not isinstance(sha, str) or len(parents) != 1:
            return None
        if isinstance(login, str) and login.casefold().endswith("[bot]"):
            self.stats.reject("bot author")
            return None
        title, _, rest = message.partition("\n")
        if _SQUASH_REFERENCE.search(title):
            # A squash-merged pull request, already covered by the pull source.
            self.stats.reject("squash of a pull request")
            return None
        if not _FIX_LANGUAGE.search(message):
            self.stats.reject("not described as a fix")
            return None
        return sha, title.strip() or sha[:12], "", rest.strip(), None

    def _fix(
        self,
        repository: str,
        repository_url: str,
        license_spdx: str,
        game_id: str,
        *,
        fixed_sha: str,
        origin: str,
        number: int | None,
        title: str,
        description: str,
        message: str,
    ) -> HistoryFix | None:
        if re.fullmatch(r"[0-9a-f]{40}", fixed_sha) is None:
            return None
        try:
            commit = self.github.http.get_json(f"/repos/{repository}/commits/{fixed_sha}")
        except RuntimeError:
            self.stats.reject("commit unavailable")
            return None
        parents = _object_list(commit, "parents")
        files = _object_list(commit, "files")
        if not isinstance(commit, dict) or commit.get("sha") != fixed_sha or not parents:
            return None
        base_sha = parents[0].get("sha")
        if len(files) >= 100:
            self.stats.reject("too many changed files")
            return None
        names = [str(value.get("filename")) for value in files if isinstance(value.get("filename"), str)]
        if changes_native_code(game_id, names):
            self.stats.reject("changes foreign-language code")
            return None
        if any(touches_frozen_build(name) for name in names):
            self.stats.reject("changes frozen build files")
            return None
        runtime = [name for name in names if is_runtime_source(game_id, name)]
        if not runtime:
            self.stats.reject("no plugin source change")
            return None
        lines = sum(
            int(value.get("additions") or 0) + int(value.get("deletions") or 0)
            for value in files
            if value.get("filename") in runtime
        )
        if lines > self.max_changed_lines:
            self.stats.reject("fix too large")
            return None
        patches = [
            f"diff --git a/{value['filename']} b/{value['filename']}\n{value['patch']}"
            for value in files
            if isinstance(value.get("patch"), str) and value.get("filename") in names
        ]
        commit_body = commit.get("commit")
        full_message = commit_body.get("message") if isinstance(commit_body, dict) else ""
        try:
            return HistoryFix(
                game_id=game_id,
                repository=repository,
                repository_url=HttpUrl(repository_url),
                license_spdx=license_spdx,
                base_sha=str(base_sha),
                fixed_sha=fixed_sha,
                origin=origin,  # type: ignore[arg-type]
                pull_number=number,
                title=title[:512],
                description=description[:65_536],
                commit_message=(message or str(full_message or ""))[:65_536],
                changed_files=tuple(names),
                patch="\n".join(patches)[: 512 * 1024] or "(no textual patch)",
                changed_lines=max(lines, 1),
            )
        except ValidationError:
            self.stats.reject("invalid fix record")
            return None
