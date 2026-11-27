from __future__ import annotations

import hashlib
import io
import json
import platform
import socket
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest
from rhenium_stardew_valley import native
from rhenium_stardew_valley.catalog import StardewCatalog
from rhenium_stardew_valley.native import (
    NATIVE_ID,
    StardewNativeBuilder,
    _extract_zip,
    evaluate_native,
    process_environment,
    read_verdict,
    require_native_launcher,
    run_process,
    sandbox_profile,
)
from rhenium_stardew_valley.plugin import StardewValleyBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeActionRequired, RuntimeArtifact, RuntimeSpec
from rhenium.util import hash_tree

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks/stardew-core"


def _builder(tmp_path: Path) -> tuple[StardewNativeBuilder, RuntimeSpec]:
    context = BenchmarkContext(
        project_root=ROOT, pack_root=PACK, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )
    builder = StardewNativeBuilder(context, StardewCatalog.load(PACK))
    return builder, RuntimeSpec(
        id=NATIVE_ID, name="Native test", version="test", provider="local-files", source={}
    )


def test_native_is_opt_in_and_never_changes_existing_full_profile(tmp_path: Path) -> None:
    builder, spec = _builder(tmp_path)
    task = builder.catalog.tasks[0]
    plugin = StardewValleyBenchmarkPlugin()
    assert [profile.id for profile in plugin.evaluation_profiles(task)] == ["core", "full"]
    synthetic = task.model_copy(update={"clean_room_synthetic": True})
    profile = plugin.evaluation_profiles(synthetic)[-1]
    assert profile.id == "macos" and profile.complete_eligible is False
    assert plugin.default_profile(synthetic) == "full"
    assert isinstance(plugin.create_runtime_builder(builder.context, spec), StardewNativeBuilder)
    result = evaluate_native(builder.context, synthetic, tmp_path, None)
    assert result["complete"] is False and result["passed"] is False
    assert result["runtime"]["engineComplete"] is False


def test_native_doctor_never_installs_on_other_platforms(tmp_path: Path, monkeypatch: Any) -> None:
    builder, spec = _builder(tmp_path)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert builder.doctor(spec)["available"] is False
    with pytest.raises(RuntimeError, match="no installer"):
        builder.prepare(spec, tmp_path, tmp_path / "output", progress=lambda *_: None)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("source_config", [{"expectedFiles": ["../outside"]}, {"sha256": "incorrect"}])
def test_native_prepare_validates_declared_source_contract_before_download(
    tmp_path: Path,
    monkeypatch: Any,
    source_config: dict[str, Any],
) -> None:
    builder, spec = _builder(tmp_path)
    builder.catalog = builder.catalog.model_copy(
        update={
            "tasks": [builder.catalog.tasks[0].model_copy(update={"clean_room_synthetic": True})],
        }
    )
    monkeypatch.setattr(builder, "doctor", lambda _: {"available": True})
    source = tmp_path / "source"
    (source / "MacOS").mkdir(parents=True)
    (source / "Resources/Content").mkdir(parents=True)
    (source / "MacOS/Stardew Valley.dll").write_bytes(b"fake")
    (source / "MacOS/Stardew Valley").write_bytes(b"fake")
    with pytest.raises(ValueError):
        builder.prepare(
            spec.model_copy(update={"source": source_config}),
            source,
            tmp_path / "output",
            progress=lambda *_: None,
        )
    assert not (tmp_path / "output").exists()


def test_artifact_verification_checks_content_and_prune_ignores_supplied_path(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    builder, spec = _builder(tmp_path)
    root = tmp_path / "artifact"
    root.mkdir()
    (root / "compiler-image.txt").write_text("sha256:fake-image")
    (root / "save-name.txt").write_text("fixture")
    (root / "config/StardewValley/Saves/fixture").mkdir(parents=True)
    (root / "config/StardewValley/Saves/fixture/SaveGameInfo").write_text("fake save")
    game = root / "game/Contents/MacOS"
    game.mkdir(parents=True)
    (game / "StardewModdingAPI").touch(mode=0o700)
    (game / "Stardew Valley.dll").write_bytes(b"fake assembly")
    (game.parent / "Resources/Content").mkdir(parents=True)
    monkeypatch.setattr(native, "GAME_SHA256", hashlib.sha256(b"fake assembly").hexdigest())
    artifact = RuntimeArtifact(
        runtime_key=f"stardew-valley/{NATIVE_ID}",
        fingerprint=spec.fingerprint(plugin_id="stardew-valley", plugin_version="0.6.0"),
        kind="macos-diagnostic",
        identity=f"sha256:{hash_tree(root)}",
        location=str(root),
        metadata={"compilerImage": "sha256:fake-image"},
    )
    monkeypatch.setattr(
        builder.compiler,
        "_docker",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "sha256:fake-image\n", ""),
    )
    assert builder.verify(spec, artifact)["available"] is True
    (root / "save-name.txt").write_text("tampered")
    assert builder.verify(spec, artifact)["available"] is False
    builder.prune(spec, artifact)
    assert (root / "save-name.txt").read_text() == "tampered"


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "boolean-count", "fatal", "case-type"])
def test_verdict_rejects_partial_forged_or_inconsistent_results(tmp_path: Path, mutation: str) -> None:
    payload: dict[str, Any] = {
        "cases": [{"Name": "a", "Passed": True}, {"Name": "b", "Passed": False}],
        "passed": 1,
        "failed": 1,
        "fatal": None,
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(payload))
    assert read_verdict(path, ("a", "b"))["engineComplete"] is True
    if mutation == "missing":
        payload["cases"].pop()
    elif mutation == "duplicate":
        payload["cases"][1]["Name"] = "a"
    elif mutation == "extra":
        payload["cases"][1]["Name"] = "extra"
    elif mutation == "boolean-count":
        payload["passed"] = True
    elif mutation == "fatal":
        payload["fatal"] = "startup failed"
    else:
        payload["cases"][0]["Passed"] = 1
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        read_verdict(path, ("a", "b"))


def test_dependency_zip_cannot_escape(tmp_path: Path) -> None:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("../outside", "invalid")
    with zipfile.ZipFile(data) as archive, pytest.raises(ValueError):
        _extract_zip(archive, tmp_path / "target")
    assert not (tmp_path / "outside").exists()


def test_removed_native_apphost_requires_operator_action(tmp_path: Path) -> None:
    with pytest.raises(RuntimeActionRequired) as raised:
        require_native_launcher(tmp_path, -9)
    assert raised.value.kind == "macos-native-launcher-removed"
    assert raised.value.details["exitCode"] == -9
    assert list(tmp_path.iterdir()) == []


def test_child_environment_and_policy_exclude_credentials(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "fake-secret")
    monkeypatch.setenv("BASH_ENV", "/outside/startup.sh")
    env = process_environment(tmp_path, tmp_path / "sdk")
    assert "fake-secret" not in json.dumps(env)
    assert "BASH_ENV" not in env and "HOME" not in env
    assert env["XDG_CONFIG_HOME"] == str(tmp_path / "config")
    policy = sandbox_profile(tmp_path, ())
    assert "(deny default)" in policy and "(deny network*)" in policy
    assert '(subpath "/Users")' not in policy


@pytest.mark.skipif(platform.system() != "Darwin", reason="requires actual macOS sandbox-exec")
def test_real_seatbelt_blocks_outside_file_access_and_direct_network(tmp_path: Path) -> None:
    private = tmp_path / "private.txt"
    private.write_text("fake-private-data")
    work = tmp_path / "work"
    work.mkdir()
    inside = work / "inside.txt"
    inside.write_text("readable")
    positive = run_process(["/bin/cat", str(inside)], work, work / "sdk", work / "positive.log")
    assert positive.returncode == 0 and positive.stdout == "readable"
    result = run_process(["/bin/cat", str(private)], work, work / "sdk", work / "read.log")
    assert result.returncode != 0 and "fake-private-data" not in result.stdout
    result = run_process(
        ["/bin/sh", "-c", 'printf bad > "$1"', "sh", str(private)], work, work / "sdk", work / "write.log"
    )
    assert result.returncode != 0 and private.read_text() == "fake-private-data"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        # The endpoint is demonstrably reachable outside Seatbelt. Inside it,
        # connect must fail, not merely time out waiting for an HTTP response.
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            accepted, _address = listener.accept()
            accepted.close()
        result = run_process(
            ["/usr/bin/curl", "--noproxy", "*", "--max-time", "2", f"http://127.0.0.1:{port}"],
            work,
            work / "sdk",
            work / "network.log",
        )
        assert result.returncode == 7
