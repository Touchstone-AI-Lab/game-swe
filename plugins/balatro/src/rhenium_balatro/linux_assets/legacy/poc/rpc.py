from __future__ import annotations

import http.client
import json
import time
from collections.abc import Callable
from typing import Any


class RPCError(RuntimeError):
    pass


class TransportError(RPCError):
    """An action may have executed. Never automatically retry it."""


class ProtocolError(RPCError):
    pass


class RemoteError(RPCError):
    def __init__(self, message: str, *, response: dict | None = None):
        super().__init__(message)
        # Populated only after HTTP, JSON-RPC version and request-id validation.
        # Existing callers still receive the same exception and message.
        self.response = response
        self.request = None


def validate_envelope(status: int, body: bytes, request_id: int) -> dict[str, Any]:
    if status != 200:
        raise ProtocolError(f"HTTP status {status}")
    try:
        def reject_constant(value):
            raise ValueError('Nonfinite JSON number')
        value = json.loads(body, parse_constant=reject_constant)
    except (ValueError, UnicodeDecodeError) as e:
        raise ProtocolError("Invalid JSON response") from e
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
        raise ProtocolError("Missing JSON-RPC 2.0 envelope")
    if type(value.get("id")) is not int or value["id"] != request_id:
        raise ProtocolError("Response id mismatch")
    if "error" in value:
        error = value["error"]
        if not isinstance(error, dict) or type(error.get("code")) is not int or not isinstance(error.get("message"), str):
            raise ProtocolError("Malformed RPC error")
        raise RemoteError(f"RPC {error['code']}: {error['message']}", response=value)
    if not isinstance(value.get("result"), dict):
        raise ProtocolError("Missing object result")
    return value["result"]


def validate_result(method: str, result: dict[str, Any]) -> None:
    if method == "health" and result.get("status") != "ok":
        raise ProtocolError("Health is not ok")
    if method == "rpc.discover" and (not isinstance(result.get("openrpc"), str) or not isinstance(result.get("methods"), list)):
        raise ProtocolError("Missing OpenRPC definition")
    if method in {"gamestate", "start", "select", "play", "discard", "cash_out", "next_round", "add", "use", "sell"}:
        if not isinstance(result.get("state"), str):
            raise ProtocolError(f"{method}: missing state")
    if method in {'save', 'load'} and (result.get('success') is not True or not isinstance(result.get('path'), str)):
        raise ProtocolError(f'{method}: missing successful file result')
    if method == "poc.runtime":
        for key in ("save_dir", "mod_dir", "steamodded", "game_version", "nonce"):
            if not isinstance(result.get(key), str):
                raise ProtocolError(f"runtime missing {key}")


class Client:
    def __init__(self, port: int, timeout: float = 25, record: Callable | None = None):
        self.port, self.timeout, self.record = port, timeout, record
        self.request_id = 0

    def call(self, method: str, params: dict | None = None, *, timeout: float | None = None) -> dict:
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}}
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout or self.timeout)
        started = time.monotonic()
        try:
            connection.request("POST", "/", json.dumps(request), {"Content-Type": "application/json"})
            response = connection.getresponse()
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ProtocolError("Oversize RPC response")
            result = validate_envelope(response.status, body, self.request_id)
            validate_result(method, result)
        except (OSError, http.client.HTTPException) as e:
            if self.record:
                self.record({"request": request, "transport_error": str(e), "duration": time.monotonic() - started})
            raise TransportError(f"{method}: {type(e).__name__}: {e}") from e
        except RPCError as e:
            if isinstance(e, RemoteError):
                e.request = request
            if self.record:
                entry = {"request": request, "rpc_error": str(e), "duration": time.monotonic() - started}
                if isinstance(e, RemoteError): entry['rpc_response'] = e.response
                self.record(entry)
            raise
        finally:
            connection.close()
        if self.record:
            self.record({"request": request, "result": result, "duration": time.monotonic() - started})
        return result

    def wait(self, predicate: Callable[[dict], bool], *, method: str = "gamestate", timeout: float = 30, retry_connection: bool = False) -> dict:
        deadline = time.monotonic() + timeout
        last: object = None
        while time.monotonic() < deadline:
            try:
                last = self.call(method, timeout=min(2.0, max(.01, deadline - time.monotonic())))
                if predicate(last):
                    return last
            except TransportError as e:
                if not retry_connection:
                    raise
                last = str(e)
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
        raise TransportError(f"Bounded wait expired for {method}; last={last}")

    def action(self, method: str, params: dict | None = None) -> dict:
        before = self.call("gamestate")
        try:
            return self.call(method, params)
        except TransportError:
            # Read-only reconciliation; an uncertain mutation is NEVER resent.
            try:
                after: object = self.call("gamestate", timeout=3)
            except RPCError as e:
                after = {"unavailable": str(e)}
            if self.record:
                self.record({"ambiguous_action": method, "before": before, "after": after, "retried": False})
            raise
