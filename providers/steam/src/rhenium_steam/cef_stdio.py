"""Internal bounded CDP framing; callers must validate their owned container endpoint."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import select
import struct
import subprocess
import time
from typing import Any

LIMIT = 262144
PIPE = """set -eu
exec 3<>/dev/tcp/127.0.0.1/8080
cat <&3 &
reader=$!
trap 'kill "$reader" 2>/dev/null || true' EXIT
cat >&3
"""


class CEFError(RuntimeError):
    pass


def frame(payload: bytes, opcode: int = 1) -> bytes:
    if len(payload) > LIMIT:
        raise CEFError("Message exceeds the bounded size")
    mask = os.urandom(4)
    size = len(payload)
    header = bytes([0x80 | opcode])
    if size < 126:
        header += bytes([0x80 | size])
    elif size <= 65535:
        header += bytes([0x80 | 126]) + struct.pack("!H", size)
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", size)
    return header + mask + bytes(value ^ mask[i % 4] for i, value in enumerate(payload))


def validate_upgrade(header: bytes, key: str) -> None:
    lines = header.decode("ascii").split("\r\n")
    if not lines[0].startswith("HTTP/1.1 101 "):
        raise CEFError("WebSocket upgrade rejected")
    fields = {k.lower(): v.strip() for line in lines[1:] if ":" in line for k, v in [line.split(":", 1)]}
    nonce = (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
    expected = base64.b64encode(hashlib.sha1(nonce).digest()).decode()
    if (
        fields.get("sec-websocket-accept") != expected
        or fields.get("upgrade", "").lower() != "websocket"
        or "upgrade" not in fields.get("connection", "").lower()
    ):
        raise CEFError("WebSocket upgrade identity mismatch")


class CEF:
    def __init__(self, path: str, *, command: list[str], env: dict[str, str], timeout: float = 15):
        if not re.fullmatch(r"/devtools/page/[A-Za-z0-9_-]{1,128}", path):
            raise CEFError("Invalid owned page endpoint")
        if not 0 < timeout <= 30:
            raise CEFError("Unbounded request timeout")
        self.timeout = timeout
        self.sequence = 0
        self.buffer = bytearray()
        # The provider checks ownership, policy and actual loopback listeners first.
        self.process = subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:8080\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        try:
            self.write(request.encode())
            deadline = time.monotonic() + timeout
            while b"\r\n\r\n" not in self.buffer:
                self.pull(deadline)
                if len(self.buffer) > 8192:
                    raise CEFError("Oversized handshake")
            header, rest = bytes(self.buffer).split(b"\r\n\r\n", 1)
            self.buffer = bytearray(rest)
            validate_upgrade(header, key)
        except Exception:
            self.close()
            raise

    def write(self, data: bytes) -> None:
        if self.process.stdin is None:
            raise CEFError("Closed transport")
        offset = 0
        while offset < len(data):
            written = self.process.stdin.write(data[offset:])
            if not written:
                raise CEFError("Transport write incomplete")
            offset += written
        self.process.stdin.flush()

    def pull(self, deadline: float) -> None:
        assert self.process.stdout is not None
        wait = deadline - time.monotonic()
        if wait <= 0 or not select.select([self.process.stdout], [], [], wait)[0]:
            raise CEFError("Response deadline exceeded; do not resend a mutation")
        data = os.read(self.process.stdout.fileno(), 65536)
        if not data:
            raise CEFError("Transport closed without completion")
        self.buffer.extend(data)
        if len(self.buffer) > LIMIT + 8192:
            raise CEFError("Response exceeds bounded size")

    def take(self, count: int, deadline: float) -> bytes:
        while len(self.buffer) < count:
            self.pull(deadline)
        value = bytes(self.buffer[:count])
        del self.buffer[:count]
        return value

    def receive(self, deadline: float) -> bytes:
        parts = bytearray()
        started = False
        while True:
            first, second = self.take(2, deadline)
            opcode = first & 15
            if first & 0x70 or second & 0x80:
                raise CEFError("Unsupported server frame")
            size = second & 127
            if size == 126:
                size = struct.unpack("!H", self.take(2, deadline))[0]
            elif size == 127:
                size = struct.unpack("!Q", self.take(8, deadline))[0]
            if size > LIMIT or len(parts) + size > LIMIT:
                raise CEFError("Message exceeds bounded size")
            payload = self.take(size, deadline)
            if opcode == 9:
                if not first & 0x80 or size > 125:
                    raise CEFError("Invalid ping frame")
                self.write(frame(payload, 10))
                continue
            if opcode not in {0, 1}:
                raise CEFError("Unexpected or closed WebSocket frame")
            if (opcode == 0 and not started) or (opcode == 1 and started):
                raise CEFError("Invalid continuation sequence")
            started = True
            parts.extend(payload)
            if first & 0x80:
                return bytes(parts)

    def evaluate(self, expression: str, *, await_promise: bool = False) -> Any:
        self.sequence += 1
        request = {
            "id": self.sequence,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
                "silent": True,
            },
        }
        self.write(frame(json.dumps(request).encode()))
        deadline = time.monotonic() + self.timeout
        for _ in range(100):
            message = json.loads(self.receive(deadline))
            if message.get("id") != self.sequence:
                continue
            result = message.get("result", {})
            if "error" in message or "exceptionDetails" in result:
                raise CEFError("CEF evaluation failed; details suppressed")
            return result.get("result", {}).get("value")
        raise CEFError("Response identity not confirmed")

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=3)
        if self.process.stdout is not None:
            self.process.stdout.close()
