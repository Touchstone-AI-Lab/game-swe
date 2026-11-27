from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyzer import ModAnalyzer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run public DST mod syntax diagnostics")
    parser.add_argument("submission", nargs="?", type=Path, default=Path.cwd())
    arguments = parser.parse_args(argv)
    result = ModAnalyzer().analyze(arguments.submission.resolve())
    public = {
        "valid": result["valid"],
        "luaFiles": result["lua_files"],
        "syntaxErrors": result["syntax_errors"],
        "category": result["category"],
        "counters": result["counters"],
    }
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0 if public["valid"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
