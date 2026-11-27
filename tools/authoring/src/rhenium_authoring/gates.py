from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import PurePosixPath
from urllib.parse import urlparse

from .models import HistoricalFix

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\s]", re.UNICODE)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{4,}")
_PUBLIC_IDENTIFIER_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    # Social handles are lowercase; Java annotations (@Override, @EventHandler,
    # @GcbCase) start with an uppercase letter and Javadoc block tags are a
    # small fixed vocabulary, so both stay usable in generated Java sources.
    re.compile(
        r"(?<![A-Za-z0-9_])@(?!(?i:param|return|throws|see|since|deprecated|link|code|"
        r"inheritdoc|implnote|implspec|apinote|serial|value|literal)(?![A-Za-z0-9_-]))"
        r"[a-z][A-Za-z0-9_-]{2,}"
    ),
    re.compile(r"(?<![A-Za-z0-9_])#[0-9]{2,}\b"),
    re.compile(r"\b[0-9a-f]{40,64}\b", re.IGNORECASE),
)
_LANGUAGE_WORDS = {
    "false",
    "function",
    "internal",
    "namespace",
    "private",
    "protected",
    "public",
    "return",
    "server",
    "static",
    "string",
    "true",
    # Java keywords and literals.
    "abstract",
    "boolean",
    "break",
    "byte",
    "case",
    "catch",
    "char",
    "class",
    "const",
    "continue",
    "default",
    "double",
    "else",
    "enum",
    "extends",
    "final",
    "finally",
    "float",
    "goto",
    "implements",
    "import",
    "instanceof",
    "int",
    "interface",
    "long",
    "native",
    "new",
    "null",
    "package",
    "permits",
    "record",
    "sealed",
    "short",
    "strictfp",
    "super",
    "switch",
    "synchronized",
    "this",
    "throw",
    "throws",
    "transient",
    "try",
    "var",
    "void",
    "volatile",
    "while",
    "yield",
}
# These names describe source layout, not the identity of a mod. Apply this
# exception only to path components; a repository bearing the same name is
# still source-identifying.
# Generic source-layout vocabulary: single common words that describe how a
# mod project is laid out (or mirror the game's own public namespaces), not
# which project it is. Distinctive top-level project directories and file
# stems stay sensitive.
_CONVENTIONAL_DIRECTORIES = {
    "api",
    "assets",
    "buildings",
    "bukkit",
    "characters",
    "client",
    "command",
    "commands",
    "common",
    "components",
    "config",
    "data",
    "docs",
    "event",
    "events",
    "fields",
    "framework",
    "gamemode",
    "handlers",
    "helpers",
    "i18n",
    "integrations",
    "items",
    "java",
    "kotlin",
    "lib",
    "listener",
    "listeners",
    "lookups",
    "machines",
    "menus",
    "migrations",
    "minecraft",
    "models",
    "objects",
    "paper",
    "patches",
    "plugin",
    "plugins",
    "prefabs",
    "resources",
    "scripts",
    "server",
    "spigot",
    "src",
    "storage",
    "summary",
    "terrainfeatures",
    "test",
    "testing",
    "tests",
    "tiles",
    "tokens",
    "utils",
    "world",
}
# Single common words that name engine or programming concepts rather than a
# project. They are generic only as path-derived words; a repository or fix
# identifier that happens to equal one of them stays sensitive.
_GENERIC_PATH_WORDS = {
    "addons",
    "anchor",
    "anchors",
    "autorun",
    "base",
    "biome",
    "biomes",
    "block",
    "blocks",
    "border",
    "borders",
    "cache",
    "caches",
    "chunk",
    "chunks",
    "class",
    "classes",
    "command",
    "commands",
    "common",
    "compat",
    "compatibility",
    "compiler",
    "config",
    "configs",
    "configuration",
    "convert",
    "cooldown",
    "cooldowns",
    "core",
    "data",
    "destination",
    "destinations",
    "dimension",
    "dimensions",
    "display",
    "dynamic",
    "economy",
    "effects",
    "entities",
    "entity",
    "event",
    "events",
    "gamemodes",
    "gates",
    "generator",
    "generators",
    "gui",
    "handler",
    "handlers",
    "health",
    "helper",
    "helpers",
    "hook",
    "hooks",
    "impl",
    "integration",
    "integrations",
    "internal",
    "inventory",
    "item",
    "items",
    "key",
    "keys",
    "listener",
    "listeners",
    "locale",
    "locales",
    "location",
    "locations",
    "main",
    "manager",
    "managers",
    "materials",
    "menu",
    "menus",
    "message",
    "messages",
    "model",
    "models",
    "modules",
    "option",
    "options",
    "particle",
    "particles",
    "permission",
    "permissions",
    "placeholder",
    "placeholders",
    "platform",
    "platforms",
    "player",
    "players",
    "profile",
    "profiles",
    "protection",
    "protections",
    "queue",
    "queues",
    "random",
    "reason",
    "reasons",
    "region",
    "regions",
    "resource",
    "resources",
    "safe",
    "safety",
    "scheduler",
    "search",
    "service",
    "services",
    "share",
    "shared",
    "shares",
    "sharing",
    "sound",
    "sounds",
    "spawn",
    "spawns",
    "stools",
    "storage",
    "store",
    "stores",
    "structure",
    "structures",
    "task",
    "tasks",
    "teleport",
    "teleportation",
    "timer",
    "timers",
    "tool",
    "tools",
    "unsafe",
    "util",
    "utils",
    "vector",
    "vgui",
    "weapon",
    "weapons",
    "world",
    "worlds",
}

_CONVENTIONAL_FILES = {
    "cl_init.lua",
    "init.lua",
    # SMAPI requires every mod's entry class file to carry this name.
    "modentry.cs",
    "main.lua",
    "manifest.json",
    "metadata.xml",
    "modinfo.lua",
    "modmain.lua",
    "shared.lua",
    # JVM build and Paper plugin conventions.
    "build.gradle",
    "build.gradle.kts",
    "config.yml",
    "gradle.properties",
    "gradlew",
    "gradlew.bat",
    "main.java",
    "messages.yml",
    "paper-plugin.yml",
    "plugin.yml",
    "pom.xml",
    "settings.gradle",
    "settings.gradle.kts",
}

# Public engine API vocabulary every project of a game shares; it is treated
# like the capsules' declared public game APIs (allowed in public text and
# excluded from the copied-sequence comparison), never as project identity.
_GAME_PUBLIC_VOCABULARY: dict[str, tuple[str, ...]] = {
    "minecraft": (
        "org.bukkit",
        "io.papermc.paper",
        "net.kyori.adventure",
        "JavaPlugin",
        "Bukkit",
        "Plugin",
        "PluginManager",
        "CommandSender",
        "ConsoleCommandSender",
        "Command",
        "CommandExecutor",
        "TabCompleter",
        "Listener",
        "EventHandler",
        "EventPriority",
        "Event",
        "Cancellable",
        "Player",
        "Entity",
        "World",
        "Location",
        "Block",
        "Material",
        "ItemStack",
        "Inventory",
        "Component",
        "TextComponent",
        "MiniMessage",
        "NamedTextColor",
        "BukkitScheduler",
        "BukkitRunnable",
        "BukkitTask",
        "NamespacedKey",
        "PersistentDataContainer",
        "PersistentDataType",
        "FileConfiguration",
        "ConfigurationSection",
        "YamlConfiguration",
        "Override",
        "onEnable",
        "onDisable",
        "onCommand",
        "getServer",
        "getLogger",
        "getConfig",
        "getPluginManager",
        "getPlugin",
        "registerEvents",
        "getCommand",
        "setExecutor",
        "getScheduler",
        "runTaskLater",
        "runTaskTimer",
        "getName",
        "sendMessage",
        "getWorld",
        "getLocation",
        "getBlockAt",
        "getType",
        "setType",
    ),
}


class LeakageError(ValueError):
    pass


def validate_public_candidate(
    fixes: Sequence[HistoricalFix],
    public_texts: Iterable[str],
    public_game_apis: Iterable[str],
) -> None:
    public = "\n".join(public_texts)
    lowered = public.casefold()
    if any(pattern.search(public) for pattern in _PUBLIC_IDENTIFIER_PATTERNS):
        raise LeakageError("public candidate contains a URL or source-style identifier")
    allowed = {word.casefold() for api in public_game_apis for word in _WORD.findall(api)}
    for game_id in {fix.game_id for fix in fixes}:
        allowed.update(
            word.casefold() for api in _GAME_PUBLIC_VOCABULARY.get(game_id, ()) for word in _WORD.findall(api)
        )
    sensitive = _sensitive_terms(fixes) - allowed - _LANGUAGE_WORDS
    leaked = sorted(
        term for term in sensitive if re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", lowered)
    )
    if leaked:
        raise LeakageError("public candidate contains source-derived identity terms")

    source_tokens = _normalized_tokens(
        "\n".join(
            text
            for fix in fixes
            for text in (
                fix.patch,
                *fix.base_files.values(),
                *fix.fixed_files.values(),
            )
        ),
        allowed,
    )
    public_tokens = _normalized_tokens(public, allowed)
    if _shares_ngram(source_tokens, public_tokens, size=50):
        raise LeakageError("public candidate shares a 50-token source sequence")


def validate_defect_paths(defect_paths: Iterable[str], project_files: Iterable[str]) -> None:
    known = set(project_files)
    for raw in defect_paths:
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or raw != path.as_posix() or raw not in known:
            raise ValueError("defect references an unsafe or missing generated file")


def _sensitive_terms(fixes: Sequence[HistoricalFix]) -> set[str]:
    # Repository and fix identifiers are identity even when they collide with
    # layout vocabulary (a project literally named "characters" stays
    # sensitive); path-derived words drop the generic layout vocabulary, which
    # also covers words inside compound components such as "Tests.Common".
    identity_terms: set[str] = set()
    path_terms: set[str] = set()
    for fix in fixes:
        parsed = urlparse(str(fix.repository_url))
        identity_terms.update(_WORD.findall(parsed.path))
        identity_terms.update(_WORD.findall(fix.id))
        for raw in fix.changed_files:
            path = PurePosixPath(raw)
            for component in path.parts[:-1]:
                if component.casefold() not in _CONVENTIONAL_DIRECTORIES:
                    path_terms.update(_WORD.findall(component))
            if path.name.casefold() not in _CONVENTIONAL_FILES:
                path_terms.update(_WORD.findall(path.stem))
    generic = _LANGUAGE_WORDS | _CONVENTIONAL_DIRECTORIES | _GENERIC_PATH_WORDS
    return {term.casefold() for term in identity_terms if term.casefold() not in _LANGUAGE_WORDS} | {
        term.casefold() for term in path_terms if term.casefold() not in generic
    }


def _normalized_tokens(text: str, allowed: set[str]) -> tuple[str, ...]:
    values = []
    for token in _TOKEN.findall(text):
        normalized = token.casefold()
        if normalized in allowed or normalized in _LANGUAGE_WORDS:
            continue
        values.append(normalized)
    return tuple(values)


def _shares_ngram(left: tuple[str, ...], right: tuple[str, ...], size: int) -> bool:
    if len(left) < size or len(right) < size:
        return False
    left_windows = {left[index : index + size] for index in range(len(left) - size + 1)}
    return any(right[index : index + size] in left_windows for index in range(len(right) - size + 1))
