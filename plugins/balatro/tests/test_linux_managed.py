import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from rhenium_balatro import linux_managed as managed
from rhenium_balatro import linux_runtime as probe
from rhenium_balatro.linux_bridge import child_environment, serial_lock

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec


def fixture(tmp_path: Path) -> tuple[managed.BalatroLinuxRuntimeBuilder, RuntimeSpec, Path, Path]:
    pack = tmp_path / "pack"
    pack.mkdir()
    old = RuntimeSpec(
        id=probe.RUNTIME_ID,
        name="unit inputs",
        version="unit",
        provider="steam",
        restricted=True,
        host_platforms=("linux-x64",),
        source=probe.SOURCE,
    )
    (pack / "runtimes.json").write_text(json.dumps({"runtimes": [old.model_dump(mode="json")]}))
    context = BenchmarkContext(
        project_root=tmp_path, pack_root=pack, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )
    spec = old.model_copy(update={"id": managed.RUNTIME_ID, "name": "unit controlled"})
    original = tmp_path / "runtimes" / probe.RUNTIME_ID
    (original / "probe-tree-v1").mkdir(parents=True)
    (original / "probe-tree-v1/unit.lua").write_bytes(b"pinned unit fixture; not a game")
    (original / "probe-artifact-v1.json").write_text(
        json.dumps({"identity": "sha256:unit", "recipe": "unit"})
    )
    return managed.BalatroLinuxRuntimeBuilder(context), spec, original, original.parent / managed.RUNTIME_ID


def fake_verify(_self: Any, _spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, bool]:
    assert artifact.location is not None
    return {
        "available": (Path(artifact.location) / "unit.lua").read_bytes() == b"pinned unit fixture; not a game"
    }


def test_owned_copy_preserves_original_and_verifies_inner_bytes(tmp_path: Path) -> None:
    builder, spec, original, destination = fixture(tmp_path)
    with (
        patch.object(probe.platform, "system", return_value="Linux"),
        patch.object(probe.platform, "machine", return_value="x86_64"),
        patch.object(managed, "validate_source") as validate,
        patch.object(managed, "recipe", return_value="unit-recipe"),
        patch.object(probe.BalatroLinuxProbeBuilder, "verify", fake_verify),
    ):
        artifact = builder.prepare(spec, tmp_path / "provider-source", destination, progress=lambda *_: None)
        validate.assert_called_once()
        assert builder.verify(spec, artifact)["available"]
        assert artifact.location is not None
        assert Path(artifact.location).is_relative_to(destination)
        (Path(artifact.location) / "unit.lua").write_bytes(b"drift")
        assert not builder.verify(spec, artifact)["available"]
        builder.prune(spec, artifact)  # Core owns deletion; no shared-resource removal.
    assert (original / "probe-tree-v1/unit.lua").read_bytes() == b"pinned unit fixture; not a game"
    assert original.exists() and destination.exists()


def test_existing_input_drift_is_not_rebuilt_or_repinned(tmp_path: Path) -> None:
    builder, spec, original, destination = fixture(tmp_path)
    with (
        patch.object(probe.platform, "system", return_value="Linux"),
        patch.object(probe.platform, "machine", return_value="x86_64"),
        patch.object(managed, "validate_source"),
        patch.object(probe.BalatroLinuxProbeBuilder, "verify", return_value={"available": False}),
        patch.object(probe.BalatroLinuxProbeBuilder, "prepare") as prepare,
    ):
        with pytest.raises(ValueError, match="drifted"):
            builder.prepare(spec, tmp_path / "provider-source", destination, progress=lambda *_: None)
        prepare.assert_not_called()
    assert original.exists() and not destination.exists()


@pytest.mark.skipif(__import__("sys").platform != "linux", reason="Linux lock semantics")
def test_serial_lock_and_minimum_controller_environment(tmp_path: Path) -> None:
    state = tmp_path / "state"
    with serial_lock(state), pytest.raises(BlockingIOError), serial_lock(state):
        pytest.fail("second controller acquired the same serial lock")
    with patch.dict(
        "os.environ",
        {
            "STEAM_TOKEN": "unit-secret",
            "GH_TOKEN": "unit-secret",
            "PYTHONPATH": "/unreviewed",
            "LD_PRELOAD": "/unreviewed",
        },
    ):
        env = child_environment(tmp_path)
    assert not {"STEAM_TOKEN", "GH_TOKEN", "LD_PRELOAD"} & set(env)
    assert "/unreviewed" not in env["PYTHONPATH"]
    assert env["PYTHONDONTWRITEBYTECODE"] == env["PYTHONNOUSERSITE"] == "1"
