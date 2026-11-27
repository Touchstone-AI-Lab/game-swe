"""Use the fixed public LÖVE LuaJIT library for unit-only wrapper semantics."""

import argparse
import ctypes
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    libraries = {p.resolve() for p in (args.artifact / "squashfs-root/lib").glob("libluajit*.so*")}
    assert len(libraries) == 1
    library = libraries.pop()
    assert library.is_relative_to(args.artifact.resolve())
    lua = ctypes.CDLL(str(library))
    lua.luaL_newstate.restype = ctypes.c_void_p
    lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lua.lua_tolstring.restype = ctypes.c_char_p
    lua.lua_close.argtypes = [ctypes.c_void_p]
    root = Path(__file__).parent
    cases = []
    for version in range(1, 5):
        diagnostic = root / f"start_diagnostic_v{version}/diagnostic.lua"
        code = (
            "DIAGNOSTIC_PATH="
            + json.dumps(str(diagnostic))
            + "\n"
            + (root / "diagnostic_unit_v1.lua").read_text()
        ).encode()
        state = lua.luaL_newstate()
        try:
            lua.luaL_openlibs(state)
            status = lua.luaL_loadstring(state, code)
            if status == 0:
                status = lua.lua_pcall(state, 0, 0, 0)
            message = lua.lua_tolstring(state, -1, None).decode() if status else None
            cases.append(
                {
                    "version": version,
                    "passed": status == 0,
                    "error": message,
                    "diagnostic_sha256": hashlib.sha256(diagnostic.read_bytes()).hexdigest(),
                }
            )
        finally:
            lua.lua_close(state)
    result = {
        "kind": "unit_only_no_game_loaded",
        "cases": cases,
        "passed": all(c["passed"] for c in cases),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
