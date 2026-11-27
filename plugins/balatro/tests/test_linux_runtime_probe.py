from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from rhenium_balatro import linux_runtime as runtime
from rhenium_balatro.plugin import BalatroBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeSpec


def spec() -> RuntimeSpec:
    return RuntimeSpec(id=runtime.RUNTIME_ID, name="unit probe", version="test", provider="steam",
                       restricted=True, host_platforms=("linux-x64",), source=runtime.SOURCE)


def test_probe_builder_has_no_task_binding_and_doctor_is_read_only(tmp_path: Path) -> None:
    context = BenchmarkContext(project_root=tmp_path, pack_root=tmp_path / "pack",
                               state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")
    builder = BalatroBenchmarkPlugin().create_runtime_builder(context, spec())
    assert isinstance(builder, runtime.BalatroLinuxProbeBuilder)
    with patch.object(runtime.platform, "system", return_value="Linux"), \
            patch.object(runtime.platform, "machine", return_value="x86_64"):
        report = builder.doctor(spec())
    assert report["available"] and not report["engineValidated"]
    assert list(tmp_path.iterdir()) == []
    assert BalatroBenchmarkPlugin().create_runtime_builder(
        context, spec().model_copy(update={"id": "other"}),
    ) is None


def test_wrong_source_and_changed_game_fail_before_execution(tmp_path: Path) -> None:
    (tmp_path / "Balatro.exe").write_bytes(b"local unit-test input, not a game")
    with pytest.raises(ValueError, match="source checksum"):
        runtime.validate_source(spec(), tmp_path)
    changed = spec().model_copy(update={"source": {**runtime.SOURCE, "appId": 123}})
    with pytest.raises(ValueError, match="exact reviewed"):
        runtime.validate_source(changed, tmp_path)


def test_checkout_conversion_must_match_existing_frozen_bytes(tmp_path: Path) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("commit/mod.lua", b"return 1\n")
    content = b"return 1\r\n"
    item = {"checkout_line_endings": "CRLF", "files": {
        "mod.lua": {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()},
    }}
    runtime.unpack_frozen(archive.getvalue(), item, tmp_path / "good")
    assert (tmp_path / "good/mod.lua").read_bytes() == content
    wrong = {**item, "checkout_line_endings": "LF"}
    with pytest.raises(ValueError, match="frozen byte"):
        runtime.unpack_frozen(archive.getvalue(), wrong, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_artifact_identity_catches_byte_drift(tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.write_bytes(b"first")
    before = runtime.identity(runtime.tree(tmp_path))
    target.write_bytes(b"later")
    assert runtime.identity(runtime.tree(tmp_path)) != before
