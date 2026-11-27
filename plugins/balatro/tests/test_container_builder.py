from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from rhenium_balatro import container_host as host
from rhenium_balatro.container_builder import BalatroContainerBuilder
from rhenium_balatro.linux_control import SMOKE_REQUIRED
from rhenium_balatro.linux_managed_v2 import BalatroLinuxRuntimeBuilderV2
from rhenium_balatro.linux_runtime import SOURCE, fingerprint, identity, sha
from rhenium_balatro.native_assets import json_write_new

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec

IMAGE = "sha256:" + "1" * 64


@pytest.fixture
def prepared(tmp_path: Path) -> tuple[BalatroContainerBuilder, RuntimeSpec, RuntimeArtifact]:
    pack = tmp_path / "pack"
    (pack / "private/native-v1").mkdir(parents=True)
    (pack / "private/native-v1/assets.json").write_text("{}")
    context = BenchmarkContext(project_root=tmp_path, pack_root=pack,
                               state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")
    spec = RuntimeSpec(id=host.RUNTIME_ID, name="unit", version="unit", provider="steam",
                       restricted=True, host_platforms=("linux-x64",), source=SOURCE)
    root = tmp_path / "owned"
    marker = root / "operator-state/linux/operations/smoke/engine-result.json"
    native = RuntimeArtifact(runtime_key="balatro/balatro-linux-17459173-controlled-v2",
                             fingerprint="native", kind="unit", identity="sha256:unit",
                             location=str(root / "native-v2/derived-tree-v2"))
    binding = {"environment": "environment", "harness": "harness",
               "smoke_marker": str(marker), "artifact": native.model_dump(mode="json"),
               "assets_sha256": sha(pack / "private/native-v1/assets.json")}
    expected = {"environment": "environment", "harness": "harness", "task": "task", "candidate": None}
    raw = {"complete": True, "passed": True, "classification": "pass", "not_executed": [],
           "processes": [{"run_id": "unit", "fingerprints": expected,
                          "cleanup": {"normal_exit": True, "protected_unchanged": True}}],
           "checks": [{"id": case, "passed": True, "observed": True, "expected": True}
                      for case in SMOKE_REQUIRED]}
    json_write_new(marker, {"operation": "smoke", "fingerprints": expected,
                            "assets_sha256": binding["assets_sha256"],
                            "artifact_identity": native.identity, "evaluation": raw})
    json_write_new(root / "operator-state/linux-binding-v1.json", binding)
    record = {"schema_version": 1, "runtime_key": host.RUNTIME_KEY,
              "fingerprint": fingerprint(spec), "recipe": "recipe", "kernel": platform.release(),
              "image_id": IMAGE, "owner": "owner", "native": native.model_dump(mode="json"),
              "smoke": binding, "smoke_sha256": sha(marker)}
    json_write_new(root / host.RECORD, record)
    artifact = RuntimeArtifact(runtime_key=host.RUNTIME_KEY, fingerprint=fingerprint(spec), kind=host.KIND,
                               identity="sha256:" + identity(record), location=str(root), metadata=record)
    return BalatroContainerBuilder(context), spec, artifact


@pytest.mark.parametrize("mutation", [
    "none", "missing_image", "owner", "image_recipe", "source_recipe", "kernel", "native",
    "smoke_bytes", "smoke_cases", "smoke_cleanup", "binding",
])
def test_verification_rechecks_complete_artifact_without_writes(
    prepared: tuple[BalatroContainerBuilder, RuntimeSpec, RuntimeArtifact], mutation: str,
) -> None:
    builder, spec, artifact = prepared
    root = Path(artifact.location or "")
    record = artifact.metadata
    marker = Path(record["smoke"]["smoke_marker"])
    if mutation.startswith("smoke_"):
        smoke = json.loads(marker.read_text())
        if mutation == "smoke_cases":
            smoke["evaluation"]["checks"].pop()
        elif mutation == "smoke_cleanup":
            smoke["evaluation"]["processes"][0]["cleanup"]["normal_exit"] = False
        marker.write_text(json.dumps(smoke) + " ")
        if mutation != "smoke_bytes":
            record["smoke_sha256"] = sha(marker)
    if mutation == "binding":
        (root / "operator-state/linux-binding-v1.json").write_text("{}")
    if mutation == "kernel":
        record["kernel"] = "another-kernel"
    (root / host.RECORD).write_text(json.dumps(record))
    artifact = artifact.model_copy(update={"identity": "sha256:" + identity(record), "metadata": record})
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    image: dict[str, Any] | None = {"Config": {"Labels": {
        host.LABEL: "different" if mutation == "owner" else "owner",
        "org.rhenium.balatro.recipe": "different" if mutation == "image_recipe" else "recipe",
    }}}
    if mutation == "missing_image":
        image = None
    with (
        patch.object(host, "inspect_image", return_value=image),
        patch.object(host, "recipe", return_value="different" if mutation == "source_recipe" else "recipe"),
        patch("rhenium_balatro.container_builder.legacy_tree_hash", return_value="task"),
        patch("rhenium_balatro.container_builder.LinuxSessionHost.harness_identity", return_value="harness"),
        patch("rhenium_balatro.container_builder.native_spec", return_value=spec),
        patch("rhenium_balatro.container_builder.verified_assets", return_value={}),
        patch.object(BalatroLinuxRuntimeBuilderV2, "verify",
                     return_value={"available": mutation != "native"}),
    ):
        assert builder.verify(spec, artifact)["available"] is (mutation == "none")
    assert before == {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_prune_removes_only_exact_owned_image_and_is_idempotent(
    prepared: tuple[BalatroContainerBuilder, RuntimeSpec, RuntimeArtifact],
) -> None:
    builder, spec, artifact = prepared
    with (
        patch.object(host, "inspect_image", return_value={"Config": {"Labels": {host.LABEL: "owner"}}}),
        patch("subprocess.run") as run,
    ):
        builder.prune(spec, artifact)
    assert run.call_args.args[0] == ["docker", "image", "rm", IMAGE]
    with patch.object(host, "inspect_image", return_value=None), patch("subprocess.run") as run:
        builder.prune(spec, artifact)
    run.assert_not_called()
    with (
        patch.object(host, "inspect_image", return_value={"Config": {"Labels": {host.LABEL: "other"}}}),
        patch("subprocess.run") as run,
        pytest.raises(ValueError, match="not owned"),
    ):
        builder.prune(spec, artifact)
    run.assert_not_called()
