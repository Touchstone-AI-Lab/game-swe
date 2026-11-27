from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import tree_sitter_lua
from tree_sitter import Language, Parser

LUA_LANGUAGE = Language(tree_sitter_lua.language())

_PACKAGE_MANIFEST = "Info.json"
_ENTRY_POINT = "scripts/main.lua"


def _strip_lua_nodes(text: str, node_types: set[str]) -> str:
    raw = text.encode("utf-8")
    tree = Parser(LUA_LANGUAGE).parse(raw)
    stripped = bytearray(raw)
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(node.children)
        if node.type not in node_types:
            continue
        for index in range(node.start_byte, node.end_byte):
            if stripped[index] not in {10, 13}:
                stripped[index] = 32
    return stripped.decode("utf-8", errors="replace")


def has_exact_case_file(root: Path, relative: str) -> bool:
    """Report whether ``relative`` exists under ``root`` with the exact case.

    Windows and macOS resolve paths case-insensitively, so a plain ``is_file``
    would accept ``Scripts/Main.lua`` for the contract's ``scripts/main.lua``
    and let a submission pass on the scoring host while failing everywhere
    else. Every path segment is therefore matched against a real listing.
    """
    current = root
    for part in PurePosixPath(relative).parts:
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return current.is_file()


def strip_lua_comments(text: str) -> str:
    """Remove Lua comments while preserving byte offsets and line breaks."""
    return _strip_lua_nodes(text, {"comment"})


def strip_lua_non_code(text: str) -> str:
    """Remove comments and string literals for structure-only diagnostics."""
    return _strip_lua_nodes(text, {"comment", "string"})


class ModAnalyzer:
    """Non-secret structure and syntax diagnostics for a submitted UE4SS Lua mod."""

    def __init__(self) -> None:
        self.parser = Parser(LUA_LANGUAGE)

    def analyze(self, root: Path) -> dict[str, Any]:
        lua_files = sorted(root.rglob("*.lua")) if root.is_dir() else []
        syntax_errors: list[dict[str, Any]] = []
        counters = {
            "hooks": 0,
            "hook_removals": 0,
            "object_notifications": 0,
            "console_commands": 0,
            "lifecycle_hooks": 0,
            "game_thread_calls": 0,
            "async_tasks": 0,
            "object_lookups": 0,
            "custom_events": 0,
            "key_binds": 0,
        }
        lines_total = 0
        code_lines = 0
        for path in lua_files:
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            lines_total += len(text.splitlines())
            uncommented = strip_lua_comments(text)
            structural = strip_lua_non_code(text)
            code_lines += sum(bool(line.strip()) for line in uncommented.splitlines())
            tree = self.parser.parse(raw)
            if tree.root_node.has_error:
                syntax_errors.append(
                    {"file": relative, "line": self._first_error_line(tree.root_node)}
                )
            counters["hooks"] += len(re.findall(r"\bRegisterHook\s*\(", structural))
            counters["hook_removals"] += len(re.findall(r"\bUnregisterHook\s*\(", structural))
            counters["object_notifications"] += len(
                re.findall(r"\bNotifyOnNewObject\s*\(", structural)
            )
            counters["console_commands"] += len(
                re.findall(r"\bRegisterConsoleCommand(?:Global)?Handler\s*\(", structural)
            )
            counters["lifecycle_hooks"] += len(
                re.findall(
                    r"\bRegister(?:LoadMap|InitGameState|BeginPlay)(?:Pre|Post)Hook\s*\(",
                    structural,
                )
            )
            counters["game_thread_calls"] += len(
                re.findall(r"\bExecuteInGameThread\s*\(", structural)
            )
            counters["async_tasks"] += len(
                re.findall(r"\b(?:ExecuteAsync|ExecuteWithDelay|LoopAsync)\s*\(", structural)
            )
            counters["object_lookups"] += len(
                re.findall(
                    r"\b(?:FindFirstOf|FindAllOf|FindObjects?|StaticFindObject)\s*\(",
                    structural,
                )
            )
            counters["custom_events"] += len(re.findall(r"\bRegisterCustomEvent\s*\(", structural))
            counters["key_binds"] += len(re.findall(r"\bRegisterKeyBind\s*\(", structural))

        package = self._read_package_info(root / _PACKAGE_MANIFEST)
        resources = self._resources(root) if root.is_dir() else {}
        return {
            "valid": bool(lua_files)
            and has_exact_case_file(root, _PACKAGE_MANIFEST)
            and has_exact_case_file(root, _ENTRY_POINT)
            and not syntax_errors,
            "lua_files": len(lua_files),
            "lines": lines_total,
            "code_lines": code_lines,
            "syntax_errors": syntax_errors,
            "counters": counters,
            "resources": resources,
            "package": package,
            "category": self._classify(counters),
            "server_compatible": package.get("server_install_rules") not in (None, 0),
        }

    @staticmethod
    def _first_error_line(node: Any) -> int:
        if node.type == "ERROR" or node.is_missing:
            return int(node.start_point[0]) + 1
        for child in node.children:
            result = ModAnalyzer._first_error_line(child)
            if result:
                return result
        return 1

    @staticmethod
    def _read_package_info(path: Path) -> dict[str, Any]:
        """Read the public fields of a Palworld ``Info.json`` package manifest."""
        if not path.is_file():
            return {}
        try:
            document = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return {"malformed": True}
        if not isinstance(document, dict):
            return {"malformed": True}
        rules = document.get("InstallRule")
        rules = rules if isinstance(rules, list) else []
        lua_rules = [
            rule
            for rule in rules
            if isinstance(rule, dict) and str(rule.get("Type", "")).lower() == "lua"
        ]
        server_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("IsServer") is True]
        return {
            "malformed": False,
            "package_name": document.get("PackageName")
            if isinstance(document.get("PackageName"), str)
            else None,
            "version": document.get("Version") if isinstance(document.get("Version"), str) else None,
            "debug_mode": document.get("DebugMode") if isinstance(document.get("DebugMode"), bool) else None,
            "install_rules": len(rules),
            "lua_install_rules": len(lua_rules),
            "server_install_rules": len(server_rules),
        }

    @staticmethod
    def _resources(root: Path) -> dict[str, int]:
        resources = {"pak": 0, "utoc": 0, "ucas": 0, "json": 0, "native": 0}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix == ".pak":
                resources["pak"] += 1
            elif suffix == ".utoc":
                resources["utoc"] += 1
            elif suffix == ".ucas":
                resources["ucas"] += 1
            elif suffix == ".json":
                resources["json"] += 1
            elif suffix in {".dll", ".so"}:
                resources["native"] += 1
        return resources

    @staticmethod
    def _classify(counters: dict[str, int]) -> str:
        if counters["console_commands"]:
            return "server-commands"
        if counters["hooks"] or counters["object_notifications"] or counters["lifecycle_hooks"]:
            return "engine-hooks"
        if counters["async_tasks"] or counters["game_thread_calls"]:
            return "scheduling"
        if counters["object_lookups"]:
            return "object-lookups"
        return "other"
