from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Protocol

from rhenium_authoring.models import HistoricalFix, SourceProject

SUPPORTED_GAMES = frozenset({"dst", "stardew-valley", "isaac-rebirth", "garrys-mod", "minecraft"})
LICENSE_ALLOWLIST = frozenset(
    {
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "MIT",
        "Zlib",
    }
)

GAME_SEARCH_TERMS = {
    "dst": "Don't Starve Together mod",
    "stardew-valley": "Stardew Valley SMAPI mod",
    "isaac-rebirth": "Binding of Isaac Afterbirth+ mod",
    "garrys-mod": "Garry's Mod addon",
    "minecraft": "Minecraft Paper plugin",
}

# GitHub repository-search queries per game. A single free-text query finds a
# few dozen repositories; topic queries reach the long tail of plugin projects.
GAME_SEARCH_QUERIES: dict[str, tuple[str, ...]] = {
    game_id: (f"{terms} in:name,description,readme",) for game_id, terms in GAME_SEARCH_TERMS.items()
}
GAME_SEARCH_QUERIES["minecraft"] = (
    "Minecraft Paper plugin in:name,description,readme",
    "topic:paper-plugin language:Java",
    "topic:spigot-plugin language:Java",
    "topic:bukkit-plugin language:Java",
    "topic:minecraft-plugin language:Java",
    "topic:papermc language:Java",
    "topic:spigot language:Java",
    "topic:bukkit language:Java",
)

# The implementation language of each game's mod/plugin runtime. Kotlin
# plugins are not harvested for Minecraft yet: the synthetic build is javac-only.
RUNTIME_SOURCE_SUFFIXES = {
    "dst": ".lua",
    "isaac-rebirth": ".lua",
    "garrys-mod": ".lua",
    "stardew-valley": ".cs",
    "minecraft": ".java",
}

# Repository-relative files whose presence proves a repository is a mod/plugin
# project of that game. Games without markers are only filtered by search terms.
GAME_REPOSITORY_MARKERS: dict[str, tuple[str, ...]] = {
    "minecraft": ("src/main/resources/plugin.yml", "src/main/resources/paper-plugin.yml"),
}

_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".github",
        "build",
        "buildsrc",
        "docker",
        "docs",
        "documentation",
        "generated",
        "gradle",
        "target",
        "test",
        "tests",
    }
)


class SourceAdapter(Protocol):
    def discover(self, game_id: str, limit: int) -> list[SourceProject]: ...

    def historical_fixes(self, project: SourceProject, limit: int) -> list[HistoricalFix]: ...


def is_runtime_source(game_id: str, filename: str) -> bool:
    """Exclude documentation, deployment files, tests and other non-mod code."""
    path = PurePosixPath(filename)
    if path.is_absolute() or ".." in path.parts or str(path) != filename:
        return False
    if game_id not in RUNTIME_SOURCE_SUFFIXES:
        return False
    if _EXCLUDED_DIRECTORIES.intersection(part.casefold() for part in path.parts[:-1]):
        return False
    return path.suffix.casefold() == RUNTIME_SOURCE_SUFFIXES[game_id]


_NATIVE_SUFFIXES = frozenset(
    {
        ".asm",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".go",
        ".h",
        ".hh",
        ".hpp",
        ".hxx",
        ".java",
        ".kt",
        ".m",
        ".mm",
        ".rs",
        ".s",
        ".swift",
        ".zig",
    }
)


def changes_native_code(game_id: str, filenames: Iterable[str]) -> bool:
    """Whether a landed change also edits compiled code outside the game's mod language.

    Such a fix describes behavior of a native loader, injector or engine patch. Its
    issue text then carries requirements no mod-language task can implement or verify,
    even when the change also touches a few mod scripts.
    """
    mod_suffix = RUNTIME_SOURCE_SUFFIXES.get(game_id)
    if mod_suffix is None:
        raise ValueError(f"unsupported authoring game: {game_id}")
    # Every other game's implementation language is foreign too: a Java change
    # in a Lua mod, or a Lua/C# change in a Paper plugin, describes a loader.
    foreign = (_NATIVE_SUFFIXES | set(RUNTIME_SOURCE_SUFFIXES.values())) - {mod_suffix}
    return any(PurePosixPath(name).suffix.casefold() in foreign for name in filenames)


def validate_fix_source(fix: HistoricalFix) -> None:
    """Minimum eligibility gate, shared by crawled and seeded generation."""
    if fix.game_id not in SUPPORTED_GAMES or fix.license_spdx not in LICENSE_ALLOWLIST:
        raise ValueError("historical fix has an unsupported game or license")
    if fix.base_sha == fix.fixed_sha:
        raise ValueError("historical fix must have distinct base and fixed revisions")
    paths = [name for name in fix.changed_files if is_runtime_source(fix.game_id, name)]
    if not paths:
        raise ValueError("historical fix does not change game mod implementation source")
    if (fix.base_files or fix.fixed_files) and not any(
        fix.base_files.get(name) != fix.fixed_files.get(name) for name in paths
    ):
        raise ValueError("historical fix has no changed implementation in its source context")
