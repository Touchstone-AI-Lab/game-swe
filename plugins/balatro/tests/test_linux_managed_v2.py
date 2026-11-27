from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from rhenium_balatro import linux_managed_v2 as v2
from rhenium_balatro import linux_runtime as old
from rhenium_balatro.linux_layout import execution_context, pack_runtime

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeSpec


def fixture(tmp_path: Path) -> tuple[v2.BalatroLinuxRuntimeBuilderV2, RuntimeSpec, Path, Path]:
    pack = tmp_path / "pack"
    pack.mkdir()
    spec = RuntimeSpec(
        id=old.RUNTIME_ID,
        name="unit",
        version="unit",
        provider="steam",
        restricted=True,
        host_platforms=("linux-x64",),
        source=old.SOURCE,
    )
    (pack / "runtimes.json").write_text(
        json.dumps({"runtimes": [spec.model_dump(mode="json")], "task_bindings": {"unit": [v2.RUNTIME_ID]}})
    )
    context = BenchmarkContext(
        project_root=tmp_path, pack_root=pack, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )
    original = tmp_path / "runtimes" / old.RUNTIME_ID
    root = original / "probe-tree-v1"
    server = root / v2.SERVER
    server.parent.mkdir(parents=True)
    server.write_bytes(b"unit original, not a real component")
    (root / "unrelated").write_bytes(b"retained")
    files = old.tree(root)
    (original / "probe-artifact-v1.json").write_text(
        json.dumps({"recipe": "unit recipe", "files": files, "identity": "sha256:" + old.identity(files)})
    )
    return (
        v2.BalatroLinuxRuntimeBuilderV2(context),
        spec.model_copy(update={"id": v2.RUNTIME_ID}),
        root,
        original.parent / v2.RUNTIME_ID,
    )


def test_new_artifact_only_changes_approved_path_and_keeps_old_inputs(tmp_path: Path) -> None:
    builder, spec, original, destination = fixture(tmp_path)
    before = old.tree(original)
    changed = b"unit derived transport"
    with (
        patch.object(v2, "validate_source"),
        patch.object(old.BalatroLinuxProbeBuilder, "verify", return_value={"available": True}),
        patch.object(v2, "derived_server", return_value=changed),
        patch.object(v2, "ORIGINAL_SHA", before[v2.SERVER]["sha256"]),
        patch.object(v2, "DERIVED_SHA", hashlib.sha256(changed).hexdigest()),
        patch.object(old.platform, "system", return_value="Linux"),
        patch.object(old.platform, "machine", return_value="x86_64"),
    ):
        artifact = builder.prepare(spec, tmp_path / "provider", destination, progress=lambda *_: None)
        assert builder.verify(spec, artifact)["available"]
        assert old.tree(original) == before
        assert artifact.runtime_key == v2.RUNTIME_KEY
        assert artifact.location is not None
        root = Path(artifact.location)
        assert (root / "unrelated").read_bytes() == b"retained"
        (root / "unrelated").write_bytes(b"drift")
        assert not builder.verify(spec, artifact)["available"]
        with pytest.raises(ValueError, match="overwrite"):
            builder.prepare(spec, tmp_path / "provider", destination, progress=lambda *_: None)


def test_bad_old_cache_is_not_rebuilt(tmp_path: Path) -> None:
    builder, spec, _, destination = fixture(tmp_path)
    with (
        patch.object(v2, "validate_source"),
        patch.object(old.BalatroLinuxProbeBuilder, "verify", return_value={"available": False}),
        patch.object(old.BalatroLinuxProbeBuilder, "prepare") as prepare,
        patch.object(old.platform, "system", return_value="Linux"),
        patch.object(old.platform, "machine", return_value="x86_64"),
    ):
        with pytest.raises(ValueError, match="drifted"):
            builder.prepare(spec, tmp_path / "provider", destination, progress=lambda *_: None)
        prepare.assert_not_called()
    assert not destination.exists()


def test_approval_does_not_allow_different_original_component() -> None:
    with pytest.raises(ValueError, match="approved input"):
        v2.derived_server(b"unapproved source")


def test_resource_mode_is_portable_but_runtime_tree_still_detects_it(tmp_path: Path) -> None:
    file = tmp_path / "resource.lua"
    file.write_bytes(b"return true")
    file.chmod(0o600)
    resource_before, runtime_before = v2.resource_bytes(tmp_path), old.tree(tmp_path)
    file.chmod(0o700)
    assert v2.resource_bytes(tmp_path) == resource_before
    assert old.tree(tmp_path) != runtime_before
    file.write_bytes(b"return false")
    assert v2.resource_bytes(tmp_path) != resource_before


def test_versioned_state_keeps_original_halt(tmp_path: Path) -> None:
    builder, _, _, _ = fixture(tmp_path)
    context = builder.context
    context.state_dir.mkdir()
    halt = context.state_dir / "linux-halt.json"
    halt.write_bytes(b"retained old failure")
    selected = execution_context(context)
    assert selected.state_dir == context.state_dir / "linux-controlled-v2-window-v2"
    assert not selected.state_dir.exists()
    assert halt.read_bytes() == b"retained old failure"
    path = context.pack_root / "runtimes.json"
    source = json.loads(path.read_text())
    source["task_bindings"]["other"] = [old.RUNTIME_ID]
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="mixed"):
        pack_runtime(context)
