from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from mindustry_fixtures import PACK, sample_pack_fixture  # noqa: F401
from rhenium_mindustry.catalog import MindustryCatalog
from rhenium_mindustry.container import BASE_IMAGE_REFERENCE, BASE_TAG, SERVER_JAR
from rhenium_mindustry.runtime_builder import MindustryRuntimeBuilder
from rhenium_official_download.provider import OfficialDownloadSource

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog, RuntimeSpec

JAR_BYTES = b"not really a jar"


def builder_and_spec(pack: Path, tmp_path: Path) -> tuple[MindustryRuntimeBuilder, RuntimeSpec]:
    context = BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    runtimes = json.loads((pack / "runtimes.json").read_text(encoding="utf-8"))
    runtimes["runtimes"][0]["source"]["sha256"] = hashlib.sha256(JAR_BYTES).hexdigest()
    (pack / "runtimes.json").write_text(json.dumps(runtimes), encoding="utf-8")
    spec = RuntimeCatalog.load(pack, "runtimes.json").runtimes[0]
    return MindustryRuntimeBuilder(context, MindustryCatalog.load(pack)), spec


def write_source(root: Path, *, jar: bytes = JAR_BYTES) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / SERVER_JAR).write_bytes(jar)
    return root


def fake_docker_factory(
    commands: list[list[str]], images: dict[str, str], labels: dict[str, dict[str, str]]
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(arguments)
        if arguments[:2] == ["image", "inspect"]:
            if arguments[-1] == "{{.Id}}":
                return subprocess.CompletedProcess(arguments, 0, images.get(arguments[2], ""), "")
            return subprocess.CompletedProcess(arguments, 0, json.dumps(labels.get(arguments[2], {})), "")
        if arguments[0] == "build":
            tag = arguments[arguments.index("--tag") + 1]
            identity = "sha256:" + hashlib.sha256(tag.encode()).hexdigest()
            images[tag] = images[identity] = identity
            labels[identity] = dict(
                arguments[i + 1].split("=", 1) for i, value in enumerate(arguments) if value == "--label"
            )
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[:2] == ["image", "rm"]:
            return subprocess.CompletedProcess(arguments, 0, "", "")
        raise AssertionError(arguments)

    return docker


def test_prepare_verify_and_prune_own_immutable_labelled_images(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    source = write_source(tmp_path / "source")
    commands: list[list[str]] = []
    images: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    builder.runtime._docker = fake_docker_factory(commands, images, labels)  # type: ignore[method-assign]

    artifact = builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)
    builds = [args for args in commands if args[0] == "build"]
    assert len(builds) == 2  # base + one task
    assert builds[0][builds[0].index("--tag") + 1] == BASE_TAG
    assert artifact.metadata["sourceSha256"] == hashlib.sha256(JAR_BYTES).hexdigest()
    assert set(artifact.metadata["images"]) == {"sample-count-command"}
    assert artifact.runtime_key == "mindustry/mindustry-159.7"
    assert artifact.metadata["network"] == "none"
    assert all(
        f"io.rhenium.runtime.source=official-download:{SERVER_JAR}:sha256:" in " ".join(args)
        for args in builds
    )

    assert builder.verify(spec, artifact)["available"] is True
    first = next(iter(artifact.metadata["images"].values()))
    labels[first]["io.rhenium.runtime.task"] = "foreign-task"
    assert builder.verify(spec, artifact)["available"] is False
    with pytest.raises(RuntimeError, match="unowned"):
        builder.prune(spec, artifact)
    labels[first]["io.rhenium.runtime.task"] = "sample-count-command"
    builder.prune(spec, artifact)
    assert len([args for args in commands if args[:2] == ["image", "rm"]]) == 2


def test_verify_rejects_a_stale_artifact(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    artifact = builder.prepare(
        spec, write_source(tmp_path / "source"), tmp_path / "a", progress=lambda *_: None
    )
    suite = (
        sample_pack
        / "private/harbor/sample-count-command/tests/suite/rhenium/mindustry/grader/TaskSuite.java"
    )
    suite.write_text(suite.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
    report = builder.verify(spec, artifact)
    assert report["available"] is False and "labels" in report["reason"]
    stale = artifact.model_copy(update={"metadata": {**artifact.metadata, "images": {}}})
    assert builder.verify(spec, stale)["available"] is False


def test_prepare_rejects_digest_mismatch_and_missing_jar(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="SHA-256"):
        builder.prepare(
            spec, write_source(tmp_path / "bad", jar=b"other"), tmp_path / "a", progress=lambda *_: None
        )
    with pytest.raises(RuntimeError, match="missing"):
        builder.prepare(spec, tmp_path / "nowhere", tmp_path / "a", progress=lambda *_: None)
    with pytest.raises(ValueError, match="server jar"):
        builder.prepare(
            spec.model_copy(update={"source": {**spec.source, "expectedFiles": ["other.jar"]}}),
            write_source(tmp_path / "ok"),
            tmp_path / "a",
            progress=lambda *_: None,
        )


def test_doctor_reports_operator_prerequisites(
    sample_pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    monkeypatch.setattr(builder.runtime, "status", lambda: {"available": True, "reason": None})
    monkeypatch.delenv("RHENIUM_MINDUSTRY_SERVER_DIR", raising=False)
    report = builder.doctor(spec)
    assert report["available"] is True and report["reason"] is None
    assert "serverDirectoryVariable" not in report
    assert builder.doctor(spec.model_copy(update={"id": "other"}))["available"] is False


@pytest.mark.parametrize("pack", ["mindustry-core", "mindustry-construct"])
def test_pack_runtime_is_the_pinned_official_release_download(pack: str) -> None:
    root = Path(__file__).resolve().parents[3] / "benchmarks" / pack
    (spec,) = RuntimeCatalog.load(root, "runtimes.json").runtimes
    assert spec.provider == "official-download"
    source = OfficialDownloadSource.model_validate(spec.source)
    (download,) = source.files
    assert download.name == SERVER_JAR
    assert download.url == f"https://github.com/Anuken/Mindustry/releases/download/v159.7/{SERVER_JAR}"
    assert download.sha256 == spec.source["sha256"] == (
        "e41289c32bcf765eb50fa131e6b515d741e20f7843fb567d3aa949e7461f22ab"
    )
    assert download.size == 19158443
    # GitHub serves release assets through one signed-URL host and nothing else.
    assert source.redirectHosts == ("release-assets.githubusercontent.com",)
    assert spec.source["expectedFiles"] == [SERVER_JAR]


def test_runtime_dockerfile_is_digest_pinned_and_jar_is_not_vendored() -> None:
    dockerfile = (PACK / "private" / "runtime" / "Dockerfile").read_text(encoding="utf-8")
    first = next(line for line in dockerfile.splitlines() if line.startswith("FROM "))
    assert first.split()[1] == BASE_IMAGE_REFERENCE
    assert "@sha256:" in BASE_IMAGE_REFERENCE
    assert not list(PACK.rglob(SERVER_JAR))
    assert not [p for p in PACK.rglob("*") if p.suffix in {".jar", ".class"}]
    verifier = (PACK / "private" / "harbor" / "harness" / "verifier.Dockerfile.tmpl").read_text(
        encoding="utf-8"
    )
    assert f"FROM {BASE_TAG}" in verifier
