import hashlib
import subprocess
from pathlib import Path

import pytest
from rhenium_mindustry.construct_catalog import MindustryConstructCatalog
from rhenium_mindustry.construct_evaluator import RUNTIME_ID, RUNTIME_KEY
from rhenium_mindustry.construct_runtime_builder import BASE_IMAGE, MindustryConstructRuntimeBuilder

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog, RuntimeSpec


def test_runtime_identity() -> None:
    assert RUNTIME_ID == "mindustry"
    assert RUNTIME_KEY == "mindustry/mindustry"


def test_runtime_catalog_binds_every_mindustry_task() -> None:
    pack = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    catalog = RuntimeCatalog.load(pack, "runtimes.json")
    assert len(catalog.runtimes) == 1
    assert catalog.runtimes[0].id == RUNTIME_ID
    assert catalog.runtimes[0].provider == "official-download"
    assert set(catalog.task_bindings) == {task.id for task in MindustryConstructCatalog.load(pack).tasks}
    assert all(binding == (RUNTIME_ID,) for binding in catalog.task_bindings.values())


def _builder(tmp_path: Path) -> MindustryConstructRuntimeBuilder:
    pack = Path(__file__).resolve().parents[3] / "benchmarks" / "mindustry-construct"
    context = BenchmarkContext(
        project_root=tmp_path,
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    return MindustryConstructRuntimeBuilder(context, MindustryConstructCatalog.load(pack))


def _spec(digest: str) -> RuntimeSpec:
    return RuntimeSpec(
        id=RUNTIME_ID,
        name="Mindustry test",
        version="v159.7",
        provider="official-download",
        source={"expectedFiles": ["server-release.jar"], "sha256": digest},
    )


def test_runtime_source_hash_is_enforced(tmp_path: Path) -> None:
    acquired = tmp_path / "acquired"
    acquired.mkdir()
    (acquired / "server-release.jar").write_bytes(b"server")
    digest = hashlib.sha256(b"server").hexdigest()
    builder = _builder(tmp_path)
    spec = _spec(digest)

    assert builder._check_source(spec, acquired) == digest

    undeclared = spec.model_copy(update={"source": {"sha256": digest}})
    with pytest.raises(ValueError, match="required files"):
        builder._check_source(undeclared, acquired)

    (acquired / "server-release.jar").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="SHA-256 does not match"):
        builder._check_source(spec, acquired)

    (acquired / "server-release.jar").unlink()
    with pytest.raises(RuntimeError, match="source is missing"):
        builder._check_source(spec, acquired)


def test_runtime_source_is_not_stored_in_the_pack(tmp_path: Path) -> None:
    """The licensed-free but 19 MB server jar is operator-owned, not a committed pack asset."""
    builder = _builder(tmp_path)

    assert builder.dockerfile.is_file()
    assert not (builder.runtime_root / "server-release.jar").exists()
    assert not (builder.runtime_root / "config").exists()


def test_prepare_builds_from_acquired_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "server-release.jar").write_bytes(b"server")
    spec = _spec(hashlib.sha256(b"server").hexdigest())
    builder = _builder(tmp_path)
    commands: list[list[str]] = []

    def fake_docker(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(args)
        output = "sha256:" + "a" * 64 if args[:2] == ["image", "inspect"] else ""
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr(builder.runtime, "_docker", fake_docker)
    artifact = builder.prepare(spec, source, tmp_path / "artifact", progress=lambda _value, _phase: None)

    # The pack owns the Dockerfile; the acquired jar is only the build context.
    assert commands[0][-1] == str(source)
    assert commands[0][commands[0].index("-f") + 1] == str(builder.dockerfile)
    assert commands[0][commands[0].index("-t") + 1] == "mindustry:159.7"
    assert len(artifact.metadata["images"]) == 10
    assert artifact.metadata["gameVersion"] == "159.7"
    assert all("--network=none" not in args for args in commands[1:] if args[0] == "build")


def test_every_task_image_builds_on_the_prepared_base(tmp_path: Path) -> None:
    """A task image must not name a tag that preparation never builds (such as mindustry:latest)."""
    builder = _builder(tmp_path)

    for task in builder.catalog.tasks:
        dockerfile = builder.context.pack_root / "private" / "harbor" / task.id / "environment" / "Dockerfile"
        bases = [
            line.split()[1]
            for line in dockerfile.read_text(encoding="utf-8").splitlines()
            if line.upper().startswith("FROM ")
        ]
        assert bases == [BASE_IMAGE], task.id
