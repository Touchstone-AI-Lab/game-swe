"""Bounded loopback tests using LuaSocket exported by the fixed real LÖVE library.

No game, Steam account or game-state callbacks are loaded.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import socket
import threading
import time
from pathlib import Path
from typing import Any


def receive(listener: socket.socket, mode: str, done: threading.Event,
            received: bytearray, errors: list[str]) -> None:
    try:
        with listener.accept()[0] as peer:
            peer.settimeout(4)
            if mode == "deadline":
                done.wait(3)
                return
            while data := peer.recv(65536):
                received.extend(data)
    except Exception as error:
        errors.append(type(error).__name__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lib = args.artifact / "squashfs-root/lib"
    lua = ctypes.CDLL(str(lib / "libluajit-5.1.so.2"), mode=ctypes.RTLD_GLOBAL)
    love = ctypes.CDLL(str(lib / "liblove-11.5.so"))
    lua.luaL_newstate.restype = ctypes.c_void_p
    for name in ("luaL_openlibs", "lua_close"):
        getattr(lua, name).argtypes = [ctypes.c_void_p]
    lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lua.lua_tolstring.restype = ctypes.c_char_p
    lua.lua_setfield.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
    lua.lua_getfield.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
    love.luaopen_socket_core.argtypes = [ctypes.c_void_p]
    replacement = Path(__file__).parents[2] / "src/rhenium_balatro/linux_transport_v1/send_raw.lua"
    function = replacement.read_text()
    cases: list[dict[str, Any]] = []
    for mode, size in (("small", 1024), ("partial", 1024 * 1024), ("deadline", 8 * 1024 * 1024)):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(4)
        received = bytearray()
        errors: list[str] = []
        done = threading.Event()

        thread = threading.Thread(target=receive, args=(listener, mode, done, received, errors), daemon=True)
        thread.start()
        state = lua.luaL_newstate()
        started = time.monotonic()
        try:
            lua.luaL_openlibs(state)
            love.luaopen_socket_core(state)
            lua.lua_setfield(state, -10002, b"socket")
            code = f"""
local ffi = require('ffi')
ffi.cdef[[int setsockopt(int, int, int, const void *, unsigned int);]]
local client = assert(socket.tcp())
client:settimeout(2)
assert(client:connect('127.0.0.1', {listener.getsockname()[1]}))
local buffer = ffi.new('int[1]', 4096)
assert(ffi.C.setsockopt(client:getfd(), {socket.SOL_SOCKET}, {socket.SO_SNDBUF},
  buffer, ffi.sizeof(buffer)) == 0)
assert(client:settimeout(0))
local methods = getmetatable(client).__index
local original = methods.send
local calls, partials = 0, 0
local function pack(...) return {{n=select('#', ...), ...}} end
methods.send = function(self, ...)
  local result = pack(original(self, ...))
  calls = calls + 1
  if result[2] == 'timeout' then partials = partials + 1 end
  return unpack(result, 1, result.n)
end
BB_SERVER = {{client_socket=client}}
sendDebugMessage = function() end
{function}
local body = string.rep('x', {size})
local response = 'HTTP/1.1 200 OK\\r\\nContent-Length: ' .. #body .. '\\r\\n\\r\\n' .. body
local ok = send_raw(response)
methods.send = original
client:close()
OUT = string.format('{{"success":%s,"calls":%d,"partials":%d}}', tostring(ok), calls, partials)
"""
            status = lua.luaL_loadstring(state, code.encode())
            if status == 0:
                status = lua.lua_pcall(state, 0, 0, 0)
            if status:
                raise RuntimeError(lua.lua_tolstring(state, -1, None).decode())
            lua.lua_getfield(state, -10002, b"OUT")
            result = json.loads(lua.lua_tolstring(state, -1, None).decode())
        finally:
            lua.lua_close(state)
            done.set()
            thread.join(timeout=5)
            listener.close()
        elapsed = time.monotonic() - started
        expected = f"HTTP/1.1 200 OK\r\nContent-Length: {size}\r\n\r\n".encode() + b"x" * size
        passed = (
            not errors
            and not thread.is_alive()
            and elapsed < 3
            and (not result["success"] if mode == "deadline" else result["success"] and received == expected)
            and (mode == "small" or result["partials"] > 0)
        )
        cases.append(
            {
                "case": mode,
                **result,
                "passed": passed,
                "elapsed_seconds": round(elapsed, 4),
                "received_bytes": len(received),
                "received_sha256": hashlib.sha256(received).hexdigest(),
                "reader_errors": errors,
            }
        )
    report = {
        "kind": "fixed_real_luasocket_loopback_no_game",
        "cases": cases,
        "passed": all(c["passed"] for c in cases),
        "replacement_sha256": hashlib.sha256(replacement.read_bytes()).hexdigest(),
        "libraries": {
            n: hashlib.sha256((lib / n).read_bytes()).hexdigest()
            for n in ("libluajit-5.1.so.2", "liblove-11.5.so")
        },
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
