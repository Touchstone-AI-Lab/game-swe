from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import tree_sitter_lua
from tree_sitter import Language, Parser

LUA_LANGUAGE = Language(tree_sitter_lua.language())


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


def strip_lua_comments(text: str) -> str:
    """Remove Lua comments while preserving byte offsets and line breaks."""
    return _strip_lua_nodes(text, {"comment"})


def strip_lua_non_code(text: str) -> str:
    """Remove comments and string literals for structure-only diagnostics."""
    return _strip_lua_nodes(text, {"comment", "string"})


class ModAnalyzer:
    """Non-secret structure and syntax diagnostics for a submitted DST mod."""

    def __init__(self) -> None:
        self.parser = Parser(LUA_LANGUAGE)

    def analyze(self, root: Path) -> dict[str, Any]:
        lua_files = sorted(root.rglob("*.lua")) if root.is_dir() else []
        syntax_errors: list[dict[str, Any]] = []
        counters = {
            "recipes": 0,
            "prefab_hooks": 0,
            "components": 0,
            "events": 0,
            "rpc_handlers": 0,
            "replicas": 0,
            "network_variables": 0,
            "actions": 0,
            "assets": 0,
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
            counters["recipes"] += len(re.findall(r"\bAddRecipe(?:2)?\s*\(", structural))
            counters["prefab_hooks"] += len(
                re.findall(r"\bAddPrefabPostInit\s*\(", structural)
            )
            counters["components"] += len(
                re.findall(r"\b(?:AddComponent|AddComponentPostInit)\s*\(", structural)
            )
            counters["events"] += len(
                re.findall(r":(?:ListenForEvent|RemoveEventCallback)\s*\(", structural)
            )
            counters["rpc_handlers"] += len(
                re.findall(r"\bAdd(?:Shard)?ModRPCHandler\s*\(", structural)
            )
            counters["replicas"] += len(
                re.findall(r"\bAddReplicableComponent\s*\(", structural)
            )
            counters["network_variables"] += len(
                re.findall(
                    r"\bnet_(?:bool|byte|tinybyte|smallbyte|shortint|ushortint|int|uint|float|hash|string|entity|bytearray|smallbytearray)\s*\(",
                    structural,
                )
            )
            counters["actions"] += len(
                re.findall(
                    r"\b(?:AddAction|AddComponentAction|AddStategraphActionHandler)\s*\(",
                    structural,
                )
            )
            counters["assets"] += len(re.findall(r"\bAsset\s*\(", structural))

        modinfo = self._read_modinfo(root / "modinfo.lua")
        resources = self._resources(root) if root.is_dir() else {}
        return {
            "valid": bool(lua_files)
            and (root / "modinfo.lua").is_file()
            and (root / "modmain.lua").is_file()
            and not syntax_errors,
            "lua_files": len(lua_files),
            "lines": lines_total,
            "code_lines": code_lines,
            "syntax_errors": syntax_errors,
            "counters": counters,
            "resources": resources,
            "modinfo": modinfo,
            "category": self._classify(counters),
            "server_compatible": modinfo.get("client_only_mod") is not True,
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
    def _read_modinfo(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        text = strip_lua_comments(path.read_text(encoding="utf-8", errors="replace"))
        result: dict[str, Any] = {}
        for key in (
            "client_only_mod",
            "server_only_mod",
            "all_clients_require_mod",
            "dst_compatible",
        ):
            match = re.search(rf"(?m)^\s*{key}\s*=\s*(true|false)\b", text)
            result[key] = match.group(1) == "true" if match else None
        for key in ("name", "version", "author"):
            match = re.search(rf"(?m)^\s*{key}\s*=\s*[\"']([^\"']*)[\"']", text)
            result[key] = match.group(1) if match else None
        return result

    @staticmethod
    def _resources(root: Path) -> dict[str, int]:
        resources = {"tex": 0, "xml": 0, "anim_zip": 0, "audio": 0, "other_zip": 0}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix == ".tex":
                resources["tex"] += 1
            elif suffix == ".xml":
                resources["xml"] += 1
            elif suffix == ".zip":
                try:
                    with zipfile.ZipFile(path) as archive:
                        names = archive.namelist()
                    key = (
                        "anim_zip"
                        if any(name.endswith((".anim", ".build", ".bank")) for name in names)
                        else "other_zip"
                    )
                except zipfile.BadZipFile:
                    key = "other_zip"
                resources[key] += 1
            elif suffix in {".fsb", ".fev", ".ogg", ".wav"}:
                resources["audio"] += 1
        return resources

    @staticmethod
    def _classify(counters: dict[str, int]) -> str:
        if counters["rpc_handlers"] or counters["network_variables"] or counters["replicas"]:
            return "networking"
        if counters["actions"]:
            return "actions"
        if counters["components"] or counters["events"] or counters["prefab_hooks"]:
            return "stateful-components"
        if counters["recipes"]:
            return "recipes"
        return "other"
