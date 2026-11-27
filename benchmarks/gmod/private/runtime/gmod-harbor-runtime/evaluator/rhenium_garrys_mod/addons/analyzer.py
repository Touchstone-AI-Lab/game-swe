from __future__ import annotations

from pathlib import Path
from typing import Any

from .lua.analysis import LuaAnalyzer
from .submission import validate_submission_tree


class GmodAddonAnalyzer:
    """Public structure and Lua 5.1-subset syntax diagnostics."""

    def __init__(self) -> None:
        self.lua = LuaAnalyzer()

    def analyze(self, root: Path) -> dict[str, Any]:
        addon_error = ""
        addon: dict[str, Any] = {}
        try:
            tree = validate_submission_tree(root)
            addon = tree.addon
        except (OSError, ValueError) as error:
            addon_error = str(error)
            # Do not hand an invalid tree to the shared analyzer: it may otherwise
            # inspect a path outside the attempt through a rejected link.
            return {
                "valid": False,
                "lua_files": [],
                "syntax_errors": [],
                "addon": {},
                "addon_error": addon_error,
            }
        result = self.lua.analyze(tree.root)
        # The shared analyzer's DST modinfo requirement is intentionally replaced here.
        result["valid"] = bool(result["lua_files"]) and not result["syntax_errors"] and not addon_error
        result["addon"] = addon
        result["addon_error"] = addon_error
        return result
