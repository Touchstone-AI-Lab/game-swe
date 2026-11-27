import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from rhenium_terraria.catalog import TerrariaCatalog
from rhenium_terraria.evaluator import (
    ENGINE_RUNTIME_ID,
    RUNTIME_ID,
    RUNTIME_KEY,
)
from rhenium_terraria.runtime_builder import (
    TerrariaEngineRuntimeBuilder,
    TerrariaRuntimeBuilder,
)

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog, RuntimeSpec

PACK_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "terraria-core"
SOURCE_IMAGE = (
    "mcr.microsoft.com/dotnet/sdk:8.0.419-bookworm-slim@"
    "sha256:dd09bcce84d9130e7f3e85c83a8ce9709e1d95e45c48c722a0d7923b38d8024c"
)


def _builder(tmp_path: Path) -> TerrariaRuntimeBuilder:
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return TerrariaRuntimeBuilder(context, TerrariaCatalog.load(PACK_ROOT))


def _spec() -> RuntimeSpec:
    return RuntimeSpec(
        id=RUNTIME_ID,
        name="test",
        version="8.0.419",
        provider="container",
        source={
            "kind": "container-image",
            "image": SOURCE_IMAGE,
            "expectedFiles": ["usr/share/dotnet/dotnet"],
        },
    )


def _engine_builder(tmp_path: Path) -> TerrariaEngineRuntimeBuilder:
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=PACK_ROOT,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return TerrariaEngineRuntimeBuilder(context, TerrariaCatalog.load(PACK_ROOT))


def _engine_spec() -> RuntimeSpec:
    return next(
        spec
        for spec in RuntimeCatalog.load(PACK_ROOT, "runtimes.json").runtimes
        if spec.id == ENGINE_RUNTIME_ID
    )


def test_runtime_catalog_binds_every_task() -> None:
    runtimes = RuntimeCatalog.load(PACK_ROOT, "runtimes.json")
    tasks = TerrariaCatalog.load(PACK_ROOT).tasks
    assert RUNTIME_ID == "dotnet-8.0.419-source-projection"
    assert f"terraria/{RUNTIME_ID}" == RUNTIME_KEY
    assert runtimes.runtimes[0].provider == "container"
    assert runtimes.runtimes[1].id == ENGINE_RUNTIME_ID
    assert runtimes.runtimes[1].provider == "local-files"
    assert runtimes.runtimes[1].source["sha256"] == (
        "6f51610f4b0f167d1620d0e8c83264ba14e047421e97d9f8053eb40e3d764e1a"
    )
    assert set(runtimes.task_bindings) == {task.id for task in tasks}
    assert all(
        binding == (RUNTIME_ID, ENGINE_RUNTIME_ID)
        for binding in runtimes.task_bindings.values()
    )


def test_runtime_source_requires_digest_pinned_image(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    assert builder._source_policy(_spec()) == (SOURCE_IMAGE, ("usr/share/dotnet/dotnet",))
    bad = _spec().model_copy(update={"source": {"image": "mcr.microsoft.com/dotnet/sdk:8.0"}})
    with pytest.raises(ValueError, match="digest-pinned"):
        builder._source_policy(bad)


def test_prepare_builds_task_image_from_recorded_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = _builder(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    image_id = "sha256:" + "a" * 64
    digest = SOURCE_IMAGE.partition("@")[2]
    (source / "image.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "image": SOURCE_IMAGE,
                "imageId": image_id,
                "repoDigests": ["mcr.microsoft.com/dotnet/sdk@" + digest],
            }
        ),
        encoding="utf-8",
    )
    commands: list[list[str]] = []

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(args)
        output = ""
        if args[:2] == ["image", "inspect"]:
            reference = args[2]
            output = (
                image_id
                if reference == SOURCE_IMAGE
                else "sha256:" + format(abs(hash(reference)), "064x")[-64:]
            )
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(builder.runtime, "_docker", fake_docker)
    artifact = builder.prepare(
        _spec(), source, tmp_path / "artifact", progress=lambda _value, _phase: None
    )

    builds = [args for args in commands if args and args[0] == "build"]
    assert len(builds) == len(TerrariaCatalog.load(PACK_ROOT).tasks)
    assert all("--pull=false" in build for build in builds)
    assert all(str(PACK_ROOT / "private" / "harbor") in build[-1] for build in builds)
    assert artifact.runtime_key == RUNTIME_KEY
    assert artifact.metadata["sourceImage"] == SOURCE_IMAGE
    assert set(artifact.metadata["images"]) == {
        task.id for task in TerrariaCatalog.load(PACK_ROOT).tasks
    }


def test_engine_source_contract_and_safe_archive_extraction(tmp_path: Path) -> None:
    builder = _engine_builder(tmp_path)
    assert builder._source_digest(_engine_spec()) == (
        "6f51610f4b0f167d1620d0e8c83264ba14e047421e97d9f8053eb40e3d764e1a"
    )

    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("Content/", b"")
        bundle.writestr("Content/probe.txt", b"real engine")
    destination = tmp_path / "runtime"
    builder._extract_archive(archive, destination)
    assert (destination / "Content" / "probe.txt").read_bytes() == b"real engine"

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as bundle:
        bundle.writestr("../escape.txt", b"no")
    with pytest.raises(RuntimeError, match="unsafe path"):
        builder._extract_archive(unsafe, tmp_path / "unsafe-runtime")

    windows_escape = tmp_path / "windows-escape.zip"
    with zipfile.ZipFile(windows_escape, "w") as bundle:
        bundle.writestr(r"..\escape.txt", b"no")
    with pytest.raises(RuntimeError, match="unsafe path"):
        builder._extract_archive(windows_escape, tmp_path / "windows-unsafe-runtime")
