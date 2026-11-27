from __future__ import annotations

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


class LuaAnalyzer:
    """Game-neutral Lua 5.1-subset source and syntax diagnostics."""

    def __init__(self) -> None:
        self.parser = Parser(LUA_LANGUAGE)

    @staticmethod
    def files(root: Path) -> list[Path]:
        return sorted(root.rglob("*.lua")) if root.is_dir() else []

    def analyze(self, root: Path, files: list[Path] | None = None) -> dict[str, Any]:
        lua_files = self.files(root) if files is None else files
        syntax_errors: list[dict[str, Any]] = []
        lines_total = 0
        code_lines = 0
        for path in lua_files:
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            lines_total += len(text.splitlines())
            uncommented = strip_lua_comments(text)
            code_lines += sum(bool(line.strip()) for line in uncommented.splitlines())
            tree = self.parser.parse(raw)
            if tree.root_node.has_error:
                syntax_errors.append({"file": relative, "line": self.first_error_line(tree.root_node)})
        return {
            "valid": bool(lua_files) and not syntax_errors,
            "lua_files": len(lua_files),
            "lines": lines_total,
            "code_lines": code_lines,
            "syntax_errors": syntax_errors,
        }

    @staticmethod
    def first_error_line(node: Any) -> int:
        if node.type == "ERROR" or node.is_missing:
            return int(node.start_point[0]) + 1
        for child in node.children:
            result = LuaAnalyzer.first_error_line(child)
            if result:
                return result
        return 1
