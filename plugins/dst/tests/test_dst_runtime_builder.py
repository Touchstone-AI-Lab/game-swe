from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from rhenium_dst.catalog import DstCatalog
from rhenium_dst.runtime_builder import DstRuntimeBuilder

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog, RuntimeSpec

PACK = Path(__file__).parents[3] / "benchmarks/dst"


def builder_and_spec(tmp_path: Path) -> tuple[DstRuntimeBuilder, RuntimeSpec]:
    context = BenchmarkContext(project_root=PACK.parents[1], pack_root=PACK,
                               state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")
    return (DstRuntimeBuilder(context, DstCatalog.load(PACK)),
            RuntimeCatalog.load(PACK, "runtimes.json").runtimes[0])


def test_prepare_and_verify_bind_every_role_to_immutable_owned_content(tmp_path: Path) -> None:
    builder, spec = builder_and_spec(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    reference = str(spec.source["image"])
    image_id = "sha256:" + "a" * 64
    (source / "image.json").write_text(json.dumps({
        "schemaVersion": 1, "image": reference, "imageId": image_id, "repoDigests": [reference],
    }))
    images = {reference: image_id}
    labels: dict[str, dict[str, str]] = {}
    commands: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        commands.append(arguments)
        if arguments[:2] == ["image", "inspect"]:
            content = json.dumps(labels.get(arguments[2], {})) if arguments[-1] != "{{.Id}}" else images.get(
                arguments[2], "",
            )
            return subprocess.CompletedProcess(arguments, 0, content, "")
        if arguments[0] == "run":
            assert "--network=none" in arguments and "--read-only" in arguments
            assert arguments[-1] == "usr/bin/bash"
        elif arguments[0] == "build":
            tag = arguments[arguments.index("--tag") + 1]
            identity = "sha256:" + hashlib.sha256(tag.encode()).hexdigest()
            images[tag] = images[identity] = identity
            labels[identity] = dict(arguments[i + 1].split("=", 1)
                                    for i, value in enumerate(arguments) if value == "--label")
        else:
            raise AssertionError(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    builder.runtime._docker = docker  # type: ignore[method-assign]
    artifact = builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)
    assert artifact.fingerprint == spec.fingerprint(plugin_id="dst", plugin_version="0.6.0")
    builds = [args for args in commands if args[0] == "build"]
    assert len(builds) == 1 + len(builder.catalog.tasks)  # the shared base plus one image per task
    commands.clear()
    assert builder.verify(spec, artifact)["available"]
    assert all(args[:2] == ["image", "inspect"] for args in commands)
    first = next(iter(artifact.metadata["images"].values()))
    labels[first]["io.rhenium.runtime.task"] = "foreign-task"
    assert builder.verify(spec, artifact)["available"] is False


@pytest.mark.parametrize("bad", ["missing", "tag", "duplicate", "wrong-key", "stale", "identity"])
def test_artifact_rejects_missing_mutable_reused_or_foreign_images(tmp_path: Path, bad: str) -> None:
    builder, spec = builder_and_spec(tmp_path)
    base = "sha256:" + "0" * 64
    images = {task.id: "sha256:" + hashlib.sha256(task.id.encode()).hexdigest()
              for task in builder.catalog.tasks}
    if bad == "missing":
        images.pop(next(iter(images)))
    elif bad == "tag":
        images[next(iter(images))] = "mutable:latest"
    elif bad == "duplicate":
        images[next(iter(images))] = base
    artifact = RuntimeArtifact(
        runtime_key="foreign/runtime" if bad == "wrong-key" else f"dst/{spec.id}",
        fingerprint="stale" if bad == "stale" else builder._fingerprint(spec), kind="docker-images",
        identity="incorrect" if bad == "identity" else builder._artifact_identity(base, images),
        metadata={"baseImage": base, "images": images},
    )
    with pytest.raises(ValueError):
        builder._artifact_images(spec, artifact)


def test_missing_declared_source_file_prevents_any_build(tmp_path: Path) -> None:
    builder, spec = builder_and_spec(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    reference = str(spec.source["image"])
    image_id = "sha256:" + "a" * 64
    (source / "image.json").write_text(json.dumps({
        "schemaVersion": 1, "image": reference, "imageId": image_id, "repoDigests": [reference],
    }))
    calls: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 1 if arguments[0] == "run" else 0, image_id, "")

    builder.runtime._docker = docker  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="missing required"):
        builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)
    assert not any(args[0] == "build" for args in calls)


def test_source_policy_rejects_mutable_image_and_escaping_expected_file(tmp_path: Path) -> None:
    builder, spec = builder_and_spec(tmp_path)
    with pytest.raises(ValueError, match="digest-pinned"):
        builder._source_policy(spec.model_copy(update={"source": {"image": "debian:latest"}}))
    with pytest.raises(ValueError, match="normalized"):
        builder._source_policy(spec.model_copy(update={"source": {
            **spec.source, "expectedFiles": ["../outside"],
        }}))


@pytest.mark.parametrize("timed_out", [False, True])
def test_build_failure_keeps_private_details_out_of_operation_error(tmp_path: Path, timed_out: bool) -> None:
    builder, _spec = builder_and_spec(tmp_path)
    private_detail = "/private/operator/state/secret-bearing-build-output"

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if timed_out:
            raise subprocess.TimeoutExpired(private_detail, timeout)
        return subprocess.CompletedProcess(arguments, 1, "", private_detail)

    builder.runtime._docker = docker  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="inspect local build logs") as failure:
        builder._build(tag="test", context=tmp_path, labels={}, timeout=10)
    assert private_detail not in str(failure.value)
    log = next((builder.context.cache_dir / "build-logs").glob("*.log"))
    assert private_detail in log.read_text()
    assert log.stat().st_mode & 0o777 == 0o600
