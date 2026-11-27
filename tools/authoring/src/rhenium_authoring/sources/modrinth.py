from __future__ import annotations

import json
from pathlib import Path

import httpx
from pydantic import HttpUrl

from rhenium_authoring.models import HistoricalFix, SourceKind, SourceProject

from .base import GAME_SEARCH_TERMS, LICENSE_ALLOWLIST, SUPPORTED_GAMES
from .http import SafeHttpClient


class ModrinthSource:
    def __init__(
        self, client: httpx.Client | None = None, cache_dir: Path | None = None
    ):
        self._owned = client is None
        self._client = client or httpx.Client(
            base_url="https://api.modrinth.com/v2",
            headers={"User-Agent": "rhenium-authoring/0.1"},
            timeout=30,
        )
        self.http = SafeHttpClient(self._client, cache_dir)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def discover(self, game_id: str, limit: int) -> list[SourceProject]:
        if game_id not in SUPPORTED_GAMES:
            return []
        # Paper plugins are a separate Modrinth project type; every other
        # supported game is listed as a mod.
        project_type = "plugin" if game_id == "minecraft" else "mod"
        payload = self.http.get_json(
            "/search",
            params={
                "query": GAME_SEARCH_TERMS[game_id],
                "limit": min(limit, 100),
                "facets": json.dumps([[f"project_type:{project_type}"]]),
            },
        )
        projects: list[SourceProject] = []
        hits = payload.get("hits")
        if not isinstance(hits, list):
            return []
        for hit in hits:
            if not isinstance(hit, dict) or not isinstance(hit.get("project_id"), str):
                continue
            project = self.http.get_json(f"/project/{hit['project_id']}")
            source_url = project.get("source_url")
            license_value = project.get("license")
            license_id = license_value.get("id") if isinstance(license_value, dict) else None
            slug = project.get("slug")
            if (
                not isinstance(source_url, str)
                or not source_url.startswith("https://github.com/")
                or license_id not in LICENSE_ALLOWLIST
                or not isinstance(slug, str)
            ):
                continue
            projects.append(
                SourceProject(
                    source=SourceKind.MODRINTH,
                    external_id=str(project.get("id", hit["project_id"])),
                    game_id=game_id,
                    project_url=HttpUrl(f"https://modrinth.com/{project_type}/{slug}"),
                    source_url=HttpUrl(source_url),
                    license_spdx=license_id,
                    immutable_ref=None,
                )
            )
        return projects[:limit]

    def historical_fixes(self, project: SourceProject, limit: int) -> list[HistoricalFix]:
        del project, limit
        return []
