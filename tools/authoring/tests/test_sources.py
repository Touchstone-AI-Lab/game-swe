from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from rhenium_authoring.models import HistoricalFix, SourceProject
from rhenium_authoring.sources.base import GAME_SEARCH_QUERIES, is_runtime_source, validate_fix_source
from rhenium_authoring.sources.curseforge import CurseForgeSource
from rhenium_authoring.sources.github import GitHubSource
from rhenium_authoring.sources.http import SafeHttpClient
from rhenium_authoring.sources.modrinth import ModrinthSource


def test_github_discovers_allowlisted_repo_and_historical_fix() -> None:
    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/search/repositories":
            return _json(
                {
                    "items": [
                        {
                            "html_url": "https://github.com/example/mod",
                            "full_name": "example/mod",
                            "default_branch": "main",
                            "license": {"spdx_id": "MIT"},
                        },
                        {
                            "html_url": "https://github.com/example/closed",
                            "full_name": "example/closed",
                            "default_branch": "main",
                            "license": {"spdx_id": "NOASSERTION"},
                        },
                    ]
                }
            )
        if path == "/repos/example/mod":
            return _json({"html_url": "https://github.com/example/mod", "license": {"spdx_id": "MIT"}})
        if path == "/search/issues":
            page = int(request.url.params["page"])
            requested_pages.append(page)
            if page == 1:
                return _json(
                    {
                        "items": [
                            {"number": index, "title": "Update translations", "body": ""}
                            for index in range(30)
                        ]
                    }
                )
            return _json(
                {
                    "items": [
                        {
                            "number": 7,
                            "title": "Fix queue",
                            "body": "Retries repeat.",
                            "user": {"login": "maintainer"},
                        }
                    ]
                }
            )
        if path == "/repos/example/mod/pulls/7":
            return _json(
                {
                    "base": {"sha": "d" * 40},
                    "head": {"sha": "b" * 40},
                    "merge_commit_sha": "c" * 40,
                    "merged_at": "2026-01-01T00:00:00Z",
                    "draft": False,
                }
            )
        if path == "/repos/example/mod/commits/" + "c" * 40:
            return _json(
                {
                    "sha": "c" * 40,
                    "parents": [{"sha": "a" * 40}],
                    "files": [
                        {"filename": "mod.lua", "patch": "@@ -1 +1 @@\n-old\n+new"},
                        {"filename": "README.md", "patch": "@@ -1 +1 @@\n-doc\n+new doc"},
                    ],
                }
            )
        if path == "/repos/example/mod/contents/mod.lua":
            revision = request.url.params["ref"]
            source = "return 'old'\n" if revision == "a" * 40 else "return 'new'\n"
            return _json(
                {
                    "encoding": "base64",
                    "content": base64.b64encode(source.encode()).decode(),
                }
            )
        return httpx.Response(404)

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    source = GitHubSource("not-real", client=client)
    projects = source.discover("dst", 10)
    assert [project.external_id for project in projects] == ["example/mod"]
    fixes = source.historical_fixes(projects[0], 2)
    assert requested_pages == [1, 2]
    assert len(fixes) == 1
    assert fixes[0].base_sha == "a" * 40
    assert fixes[0].fixed_sha == "c" * 40
    assert fixes[0].changed_files == ("mod.lua",)
    assert fixes[0].base_files == {"mod.lua": "return 'old'\n"}
    assert fixes[0].fixed_files == {"mod.lua": "return 'new'\n"}


@pytest.mark.parametrize(
    "game,path,eligible",
    [
        ("dst", "docker/Dockerfile", False),
        ("dst", "docker/dst_admin_docker.sh", False),
        ("dst", "docker/README.md", False),
        ("dst", "docs/example.lua", False),
        ("dst", "tests/suite.lua", False),
        ("dst", "modmain.lua", True),
        ("garrys-mod", "gamemode/init.lua", True),
        ("isaac-rebirth", "main.lua", True),
        ("stardew-valley", "Automate/ModEntry.cs", True),
        ("stardew-valley", "Automate/manifest.json", False),
        ("minecraft", "main.lua", False),
        ("minecraft", "src/main/java/dev/example/ExamplePlugin.java", True),
        ("minecraft", "src/main/kotlin/dev/example/ExamplePlugin.kt", False),
        ("minecraft", "src/test/java/dev/example/ExampleTest.java", False),
        ("minecraft", "buildSrc/src/main/java/Conventions.java", False),
        ("minecraft", "build/generated/sources/Stub.java", False),
        ("minecraft", "target/classes/Stub.java", False),
        ("minecraft", "gradle/plugins/Convention.java", False),
        ("minecraft", "src/main/resources/plugin.yml", False),
        ("dst", "../modmain.lua", False),
        ("unknown-game", "main.lua", False),
    ],
)
def test_runtime_source_filter(game: str, path: str, eligible: bool) -> None:
    assert is_runtime_source(game, path) is eligible


@pytest.mark.parametrize(
    "game,filenames,native",
    [
        ("dst", ["Mod/modmain.lua", "src/DontStarveInjector/GameLua.cpp"], True),
        ("dst", ["modmain.lua", "include/config.hpp"], True),
        ("garrys-mod", ["lua/autorun/server.lua", "module/gm_example.rs"], True),
        ("isaac-rebirth", ["main.lua", "Patcher/Program.cs"], True),
        ("stardew-valley", ["Automate/ModEntry.cs", "Automate/manifest.json"], False),
        ("stardew-valley", ["Automate/ModEntry.cs", "native/hook.c"], True),
        ("dst", ["modmain.lua", "README.md", "tools/pack.py"], False),
        ("minecraft", ["src/main/java/dev/Plugin.java", "src/main/resources/plugin.yml"], False),
        ("minecraft", ["src/main/java/dev/Plugin.java", "src/main/kotlin/dev/Ext.kt"], True),
        ("minecraft", ["src/main/java/dev/Plugin.java", "bridge/Bridge.cs"], True),
        ("minecraft", ["src/main/java/dev/Plugin.java", "scripts/hook.lua"], True),
        ("minecraft", ["src/main/java/dev/Plugin.java", "native/jni.c"], True),
        ("dst", ["modmain.lua", "loader/Loader.java"], True),
    ],
)
def test_fixes_that_also_change_native_code_are_recognised(
    game: str, filenames: list[str], native: bool
) -> None:
    from rhenium_authoring.sources.base import changes_native_code

    assert changes_native_code(game, filenames) is native


def test_github_skips_a_fix_whose_behavior_lives_in_native_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/example/injector":
            return _json(
                {
                    "html_url": "https://github.com/example/injector",
                    "full_name": "example/injector",
                    "default_branch": "main",
                    "license": {"spdx_id": "MIT"},
                }
            )
        if path == "/search/issues":
            page = int(request.url.params["page"])
            return _json(
                {
                    "items": [
                        {"number": 7, "title": "Fix GC step leak", "body": "", "user": {"login": "dev"}}
                    ]
                    if page == 1
                    else []
                }
            )
        if path == "/repos/example/injector/pulls/7":
            return _json(
                {
                    "merged_at": "2026-01-01T00:00:00Z",
                    "draft": False,
                    "merge_commit_sha": "c" * 40,
                    "body": "",
                }
            )
        if path == "/repos/example/injector/commits/" + "c" * 40:
            return _json(
                {
                    "sha": "c" * 40,
                    "parents": [{"sha": "a" * 40}],
                    "files": [
                        {"filename": "Mod/modmain.lua", "patch": "@@ -1 +1 @@\n-old\n+new"},
                        {"filename": "src/gc.cpp", "patch": "@@ -1 +1 @@\n-old\n+new"},
                    ],
                }
            )
        return httpx.Response(404)

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    source = GitHubSource("not-real", client=client)
    project = SourceProject(
        source="github",
        external_id="example/injector",
        game_id="dst",
        project_url="https://github.com/example/injector",
        source_url="https://github.com/example/injector",
        license_spdx="MIT",
    )
    assert source.historical_fixes(project, 2) == []


def _paper_repository_handler(marker_status: int) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/example/plugin":
            return _json(
                {
                    "html_url": "https://github.com/example/plugin",
                    "full_name": "example/plugin",
                    "default_branch": "main",
                    "license": {"spdx_id": "MIT"},
                }
            )
        if path == "/repos/example/plugin/contents/src/main/resources/plugin.yml":
            return httpx.Response(marker_status, json={"type": "file", "name": "plugin.yml"})
        if path == "/repos/example/plugin/contents/src/main/resources/paper-plugin.yml":
            return httpx.Response(404)
        if path == "/search/issues":
            page = int(request.url.params["page"])
            return _json(
                {
                    "items": [
                        {"number": 3, "title": "Fix reload crash", "body": "", "user": {"login": "dev"}}
                    ]
                    if page == 1
                    else []
                }
            )
        if path == "/repos/example/plugin/pulls/3":
            return _json(
                {
                    "merged_at": "2026-01-01T00:00:00Z",
                    "draft": False,
                    "merge_commit_sha": "c" * 40,
                    "body": "",
                }
            )
        if path == "/repos/example/plugin/commits/" + "c" * 40:
            return _json(
                {
                    "sha": "c" * 40,
                    "parents": [{"sha": "a" * 40}],
                    "files": [
                        {
                            "filename": "src/main/java/dev/example/Plugin.java",
                            "patch": "@@ -1 +1 @@\n-old\n+new",
                        },
                    ],
                }
            )
        if path.startswith("/repos/example/plugin/contents/src/main/java/"):
            revision = request.url.params["ref"]
            source = "class Old {}\n" if revision == "a" * 40 else "class New {}\n"
            return _json({"encoding": "base64", "content": base64.b64encode(source.encode()).decode()})
        return httpx.Response(404)

    return handler


@pytest.mark.parametrize(("marker_status", "expected"), [(200, 1), (404, 0)])
def test_github_mines_minecraft_only_from_paper_plugin_repositories(
    marker_status: int, expected: int
) -> None:
    client = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(_paper_repository_handler(marker_status)),
    )
    source = GitHubSource("not-real", client=client)
    project = SourceProject(
        source="github",
        external_id="example/plugin",
        game_id="minecraft",
        project_url="https://github.com/example/plugin",
        source_url="https://github.com/example/plugin",
        license_spdx="MIT",
    )
    fixes = source.historical_fixes(project, 2)
    assert len(fixes) == expected
    if fixes:
        assert fixes[0].changed_files == ("src/main/java/dev/example/Plugin.java",)


def test_modrinth_searches_the_plugin_project_type_for_minecraft() -> None:
    facets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/search":
            facets.append(request.url.params["facets"])
            return _json({"hits": [{"project_id": "one"}]})
        return _json(
            {
                "id": "one",
                "slug": "neutral",
                "source_url": "https://github.com/example/plugin",
                "license": {"id": "MIT"},
            }
        )

    client = httpx.Client(base_url="https://api.modrinth.com/v2", transport=httpx.MockTransport(handler))
    projects = ModrinthSource(client).discover("minecraft", 5)
    assert facets == ['[["project_type:plugin"]]']
    assert str(projects[0].project_url) == "https://modrinth.com/plugin/neutral"
    ModrinthSource(client).discover("dst", 5)
    assert facets[-1] == '[["project_type:mod"]]'


def test_seeded_infrastructure_and_doc_fixes_are_rejected() -> None:
    fix = HistoricalFix.model_validate(
        {
            "id": "github-pr-1",
            "game_id": "dst",
            "repository_url": "https://github.com/example/server-admin",
            "license_spdx": "MIT",
            "base_sha": "a" * 40,
            "fixed_sha": "b" * 40,
            "issue_text": "Fix Docker builds",
            "patch": "-old\n+new",
            "changed_files": ["docker/Dockerfile", "docker/README.md"],
        }
    )
    with pytest.raises(ValueError, match="mod implementation"):
        validate_fix_source(fix)


def test_github_repository_parser_rejects_non_https_or_subpaths() -> None:
    assert GitHubSource.repository_name("https://github.com/example/mod.git") == "example/mod"
    for value in (
        "http://github.com/example/mod",
        "https://gitlab.com/example/mod",
        "https://github.com/a/b/issues",
    ):
        try:
            GitHubSource.repository_name(value)
        except ValueError:
            pass
        else:
            raise AssertionError(value)


def test_modrinth_discovers_only_allowlisted_github_sources() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/search":
            return _json({"hits": [{"project_id": "one"}, {"project_id": "two"}]})
        if request.url.path == "/v2/project/one":
            return _json(
                {
                    "id": "one",
                    "slug": "neutral",
                    "source_url": "https://github.com/example/mod",
                    "license": {"id": "MIT"},
                }
            )
        return _json(
            {
                "id": "two",
                "slug": "closed",
                "source_url": "https://github.com/example/closed",
                "license": {"id": "LicenseRef-Custom"},
            }
        )

    client = httpx.Client(base_url="https://api.modrinth.com/v2", transport=httpx.MockTransport(handler))
    projects = ModrinthSource(client).discover("dst", 10)
    assert [project.external_id for project in projects] == ["one"]


def test_curseforge_resolves_game_id_and_requires_github_source_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/games":
            return _json({"data": [{"id": 77, "name": "Stardew Valley"}]})
        return _json(
            {
                "data": [
                    {
                        "id": 5,
                        "links": {
                            "websiteUrl": "https://curseforge.com/projects/neutral",
                            "sourceUrl": "https://github.com/example/mod",
                        },
                    },
                    {
                        "id": 6,
                        "links": {
                            "websiteUrl": "https://curseforge.com/projects/binary",
                            "sourceUrl": "https://example.invalid/download.zip",
                        },
                    },
                ]
            }
        )

    client = httpx.Client(base_url="https://api.curseforge.com/v1", transport=httpx.MockTransport(handler))
    projects = CurseForgeSource("not-real", client).discover("stardew-valley", 10)
    assert [project.external_id for project in projects] == ["5"]


def test_source_cache_revalidates_with_etag(tmp_path: Path) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if request.headers.get("if-none-match") == '"revision-1"':
            return httpx.Response(304)
        return httpx.Response(200, json={"value": 7}, headers={"etag": '"revision-1"'})

    client = httpx.Client(base_url="https://api.example.invalid", transport=httpx.MockTransport(handler))
    cache = tmp_path / "cache"
    source = SafeHttpClient(client, cache)
    assert source.get_json("/data", params={"limit": 1}) == {"value": 7}
    assert source.get_json("/data", params={"limit": 1}) == {"value": 7}
    assert requests == 2
    assert cache.stat().st_mode & 0o777 == 0o700


def _json(value: object) -> httpx.Response:
    return httpx.Response(
        200,
        content=json.dumps(value).encode(),
        headers={"content-type": "application/json"},
    )


def test_github_yields_nothing_for_a_repository_outside_the_licence_allowlist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/example/gpl-mod":
            return _json(
                {
                    "html_url": "https://github.com/example/gpl-mod",
                    "full_name": "example/gpl-mod",
                    "default_branch": "main",
                    "license": {"spdx_id": "GPL-3.0"},
                }
            )
        raise AssertionError(f"unexpected request {request.url.path}")

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    source = GitHubSource("not-real", client=client)
    project = SourceProject(
        source="github",
        external_id="example/gpl-mod",
        game_id="dst",
        project_url="https://github.com/example/gpl-mod",
        source_url="https://github.com/example/gpl-mod",
        license_spdx="MIT",
    )
    # A search hit outside the allowlist yields nothing; the harvest continues elsewhere.
    assert source.historical_fixes(project, 2) == []


def test_http_client_waits_for_the_rate_limit_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from rhenium_authoring.sources.http import SafeHttpClient, _retry_pause

    calls: list[int] = []
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(403, headers={"retry-after": "7"}, json={"message": "rate limited"})
        return _json({"ok": True})

    monkeypatch.setattr("rhenium_authoring.sources.http.time.sleep", lambda seconds: slept.append(seconds))
    client = SafeHttpClient(
        httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    )
    assert client.get_json("/search/issues", params={"q": "x"}) == {"ok": True}
    assert slept == [7.0]
    assert _retry_pause(httpx.Headers({"retry-after": "900"})) == 120.0
    assert _retry_pause(httpx.Headers({})) == 0.0


def test_github_discovery_unions_every_query_for_the_game() -> None:
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/repositories"
        query = request.url.params["q"]
        queries.append(query)
        index = len(queries)
        return _json(
            {
                "items": [
                    {
                        "full_name": f"example/copyleft-{index}",
                        "html_url": f"https://github.com/example/copyleft-{index}",
                        "default_branch": "main",
                        "license": {"spdx_id": "GPL-3.0"},
                    },
                    {
                        "full_name": "example/shared",
                        "html_url": "https://github.com/example/shared",
                        "default_branch": "main",
                        "license": {"spdx_id": "MIT"},
                    },
                    {
                        "full_name": f"example/only-{index}",
                        "html_url": f"https://github.com/example/only-{index}",
                        "default_branch": "main",
                        "license": {"spdx_id": "MIT"},
                    },
                ]
            }
        )

    client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    source = GitHubSource("not-real", client=client)
    # Three allowlisted repositories take two queries: copyleft hits never count.
    projects = source.discover("minecraft", 3)
    names = [project.external_id for project in projects]
    assert names == ["example/shared", "example/only-1", "example/only-2"]
    assert queries == list(GAME_SEARCH_QUERIES["minecraft"][:2])
    assert source.discover("dst", 50)[0].external_id == "example/shared"
