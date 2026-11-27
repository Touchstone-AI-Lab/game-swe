"""Forward proxy that tunnels HTTPS only to an explicit host allowlist.

The agent container sits on an internal Docker network with no route out; this
proxy is its only exit. Anything but ``CONNECT <allowed-host>:443`` is refused
and logged, so a run records every attempted destination.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

ALLOWED = {host.strip().lower() for host in sys.argv[1].split(",") if host.strip()}
LOG = open(sys.argv[2], "a", encoding="utf-8", buffering=1) if len(sys.argv) > 2 else sys.stderr  # noqa: SIM115


def record(event: str, target: str) -> None:
    LOG.write(json.dumps({"t": round(time.time(), 3), "event": event, "target": target}) + "\n")


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=30)
        method, target, *_ = request.split(b"\r\n", 1)[0].decode("latin-1").split(" ")
        host, _, port = target.rpartition(":")
        if method != "CONNECT" or port != "443" or host.lower() not in ALLOWED:
            record("denied", f"{method} {target}")
            writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        upstream_reader, upstream_writer = await asyncio.open_connection(host, 443)
    except Exception as error:  # noqa: BLE001 - one bad client must not stop the proxy
        record("error", type(error).__name__)
        writer.close()
        return
    record("allowed", target)
    writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
    await writer.drain()
    await asyncio.gather(pipe(reader, upstream_writer), pipe(upstream_reader, writer))


async def main() -> None:
    server = await asyncio.start_server(handle, "0.0.0.0", 8888)
    async with server:
        await server.serve_forever()


asyncio.run(main())
