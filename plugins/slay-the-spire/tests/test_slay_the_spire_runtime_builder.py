from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from rhenium_slay_the_spire.catalog import SlayTheSpireCatalog
from rhenium_slay_the_spire.container import RUNTIME_TASK_LABEL
from rhenium_slay_the_spire.runtime_builder import SlayTheSpireRuntimeBuilder
from spire_fixtures import BASE_IMAGE, sample_pack_fixture  # noqa: F401

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeCatalog, RuntimeSpec

SOURCE_IMAGE_ID = "sha256:" + "a" * 64


def builder_and_spec(pack: Path, tmp_path: Path) -> tuple[SlayTheSpireRuntimeBuilder, RuntimeSpec]:
    context = BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    spec = RuntimeCatalog.load(pack, "runtimes.json").runtimes[0]
    return SlayTheSpireRuntimeBuilder(context, SlayTheSpireCatalog.load(pack)), spec


def write_source(root: Path, *, image: str = BASE_IMAGE, image_id: str = SOURCE_IMAGE_ID) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "image.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "image": image,
                "imageId": image_id,
                "repoDigests": [image],
            }
        ),
        encoding="utf-8",
    )
    return root


def fake_docker_factory(
    commands: list[list[str]], images: dict[str, str], labels: dict[str, dict[str, str]]
) -> Callable[..., subprocess.CompletedProcess[str]]:
    images.setdefault(BASE_IMAGE, SOURCE_IMAGE_ID)

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
        if arguments[0] in {"run", "version"} or arguments[:2] == ["image", "rm"]:
            return subprocess.CompletedProcess(arguments, 0, "", "")
        raise AssertionError(arguments)

    return docker


def test_prepare_verify_and_prune_own_labelled_immutable_images(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    commands: list[list[str]] = []
    images: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    builder.runtime._docker = fake_docker_factory(commands, images, labels)  # type: ignore[method-assign]

    artifact = builder.prepare(
        spec, write_source(tmp_path / "source"), tmp_path / "artifact", progress=lambda *_: None
    )
    builds = [args for args in commands if args[0] == "build"]
    assert len(builds) == 1  # one image per catalog task
    assert "--pull=false" in builds[0]
    assert artifact.metadata["sourceImage"] == BASE_IMAGE
    assert artifact.metadata["sourceImageId"] == SOURCE_IMAGE_ID
    assert set(artifact.metadata["images"]) == {"sample-regressions"}
    assert artifact.runtime_key == "slay-the-spire/modthespire-jdk8-maven"
    # The expectedFiles probe runs in the pinned source image with no network.
    probe = next(args for args in commands if args[0] == "run")
    assert "--network=none" in probe and "--read-only" in probe and BASE_IMAGE in probe

    assert builder.verify(spec, artifact)["available"] is True
    only_image = next(iter(artifact.metadata["images"].values()))
    labels[only_image][RUNTIME_TASK_LABEL] = "foreign-task"
    assert builder.verify(spec, artifact)["available"] is False
    with pytest.raises(RuntimeError, match="unowned"):
        builder.prune(spec, artifact)
    labels[only_image][RUNTIME_TASK_LABEL] = "sample-regressions"
    builder.prune(spec, artifact)
    assert [args for args in commands if args[:2] == ["image", "rm"]]


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"schemaVersion": 2}, "unsupported schema"),
        ({"schemaVersion": 1, "image": "other@sha256:" + "b" * 64}, "does not match"),
        ({"schemaVersion": 1, "image": BASE_IMAGE, "imageId": "nope"}, "immutable image ID"),
        (
            {"schemaVersion": 1, "image": BASE_IMAGE, "imageId": SOURCE_IMAGE_ID, "repoDigests": []},
            "pinned digest",
        ),
    ],
)
def test_prepare_rejects_an_untrustworthy_provider_record(
    sample_pack: Path, tmp_path: Path, record: dict[str, object], message: str
) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    source = tmp_path / "bad"
    source.mkdir()
    payload = {"repoDigests": [BASE_IMAGE], **record}
    (source / "image.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match=message):
        builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)


def test_prepare_requires_the_dockerfile_to_use_the_acquired_source(
    sample_pack: Path, tmp_path: Path
) -> None:
    dockerfile = sample_pack / "private/harbor/sample-regressions/environment/Dockerfile"
    dockerfile.write_text("FROM maven:3.9-eclipse-temurin-8\n", encoding="utf-8")
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="not bound to the acquired container source"):
        builder.prepare(spec, write_source(tmp_path / "source"), tmp_path / "a", progress=lambda *_: None)


def test_unpinned_or_malformed_sources_are_refused(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    with pytest.raises(ValueError, match="digest-pinned"):
        builder._source_policy(spec.model_copy(update={"source": {"image": "maven:3.9"}}))
    with pytest.raises(ValueError, match="does not declare an image"):
        builder._source_policy(spec.model_copy(update={"source": {}}))
    with pytest.raises(ValueError, match="normalized and relative"):
        builder._source_policy(
            spec.model_copy(update={"source": {"image": BASE_IMAGE, "expectedFiles": ["/etc/x"]}})
        )


def test_doctor_reports_the_pinned_source_and_task_count(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    report = builder.doctor(spec)
    assert report["available"] is True
    assert report["sourceImage"] == BASE_IMAGE and report["taskCount"] == 1


def test_build_context_fingerprint_tracks_the_environment_tree(sample_pack: Path, tmp_path: Path) -> None:
    builder, _spec = builder_and_spec(sample_pack, tmp_path)
    (task,) = builder.catalog.tasks
    before = builder.runtime.build_context_fingerprint(task)
    starter = sample_pack / "private/harbor/sample-regressions/environment/modthespire"
    (starter / "pom.xml").write_text("<project><!-- edited --></project>\n", encoding="utf-8")
    assert builder.runtime.build_context_fingerprint(task) != before
