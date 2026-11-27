from __future__ import annotations

from pathlib import Path

import httpx
from pydantic import HttpUrl

from rhenium_authoring.models import HistoricalFix, SourceKind, SourceProject

from .base import SUPPORTED_GAMES
from .http import SafeHttpClient

GAME_NAMES = {
    "dst": "Don't Starve Together",
    "stardew-valley": "Stardew Valley",
    "isaac-rebirth": "The Binding of Isaac: Rebirth",
    "garrys-mod": "Garry's Mod",
    "minecraft": "Minecraft",
}


class CurseForgeSource:
    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        cache_dir: Path | None = None,
    ):
        self._owned = client is None
        self._client = client or httpx.Client(
            base_url="https://api.curseforge.com/v1",
            headers={"x-api-key": api_key, "User-Agent": "rhenium-authoring/0.1"},
            timeout=30,
        )
        self.http = SafeHttpClient(self._client, cache_dir)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def discover(self, game_id: str, limit: int) -> list[SourceProject]:
        if game_id not in SUPPORTED_GAMES:
            return []
        game_api_id = self._game_id(GAME_NAMES[game_id])
        payload = self.http.get_json(
            "/mods/search",
            params={"gameId": game_api_id, "pageSize": min(limit, 50), "sortOrder": "desc"},
        )
        raw_projects = payload.get("data")
        if not isinstance(raw_projects, list):
            return []
        projects: list[SourceProject] = []
        for raw in raw_projects:
            if not isinstance(raw, dict):
                continue
            links = raw.get("links")
            source_url = links.get("sourceUrl") if isinstance(links, dict) else None
            website_url = links.get("websiteUrl") if isinstance(links, dict) else None
            identifier = raw.get("id")
            if (
                not isinstance(source_url, str)
                or not source_url.startswith("https://github.com/")
                or not isinstance(website_url, str)
                or not isinstance(identifier, int)
            ):
                continue
            projects.append(
                SourceProject(
                    source=SourceKind.CURSEFORGE,
                    external_id=str(identifier),
                    game_id=game_id,
                    project_url=HttpUrl(website_url),
                    source_url=HttpUrl(source_url),
                    license_spdx=None,
                    immutable_ref=None,
                )
            )
        return projects[:limit]

    def _game_id(self, expected_name: str) -> int:
        index = 0
        while index < 5000:
            payload = self.http.get_json("/games", params={"index": index, "pageSize": 50})
            games = payload.get("data")
            if not isinstance(games, list) or not games:
                break
            for game in games:
                if (
                    isinstance(game, dict)
                    and game.get("name") == expected_name
                    and isinstance(game.get("id"), int)
                ):
                    return int(game["id"])
            index += len(games)
        raise ValueError(f"CurseForge does not list supported game {expected_name}")

    def historical_fixes(self, project: SourceProject, limit: int) -> list[HistoricalFix]:
        del project, limit
        return []
