import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SOURCE = Path(__file__).parents[1] / "runtime/linux/rpc_read_diagnostic_v1.py"
SPEC = importlib.util.spec_from_file_location("rpc_read_diagnostic_v1", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_observer_keeps_original_bytes_call_arguments_and_bounded_metadata() -> None:
    diagnostic = MODULE.ReadDiagnostic(limit=1)
    response = SimpleNamespace(length=100, status=200)
    data = b'{"truncated":'
    original = Mock(return_value=data)
    wrapped = diagnostic.wrap_read(original)
    assert wrapped(response, 1000) is data
    original.assert_called_once_with(response, 1000)
    assert diagnostic.rows[0]["short_read"] and diagnostic.rows[0]["received_bytes"] == len(data)
    wrapped(response, amt=1000)
    assert len(diagnostic.rows) == 1 and diagnostic.dropped == 1
    assert "truncated" not in str(diagnostic.rows)


def test_observer_preserves_return_and_exception_identity_without_retries() -> None:
    diagnostic = MODULE.ReadDiagnostic()
    value = object()
    original = Mock(return_value=value)
    assert diagnostic.wrap_envelope(original)(200, b"{}", 42) is value
    original.assert_called_once_with(200, b"{}", 42)
    error = RuntimeError("original exception")
    raising = Mock(side_effect=error)
    with pytest.raises(RuntimeError) as caught:
        diagnostic.wrap_envelope(raising)(200, b"{", 43)
    assert caught.value is error
    raising.assert_called_once_with(200, b"{", 43)
    response = SimpleNamespace(length=100, status=200)
    reader = Mock(side_effect=error)
    with pytest.raises(RuntimeError) as caught_read:
        diagnostic.wrap_read(reader)(response, 1000)
    assert caught_read.value is error
    reader.assert_called_once_with(response, 1000)
