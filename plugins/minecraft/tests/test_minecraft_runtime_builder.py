from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pack_fixtures import sample_pack_fixture  # noqa: F401
from rhenium_minecraft.catalog import MinecraftCatalog
from rhenium_minecraft.container import BASE_TAG, EULA_FILE, SERVER_JAR
from rhenium_minecraft.runtime_builder import MinecraftRuntimeBuilder, eula_accepted
from rhenium_official_download.provider import OfficialDownloadSource

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeActionRequired, RuntimeCatalog, RuntimeSpec

JAR_BYTES = b"not really a jar"


def builder_and_spec(pack: Path, tmp_path: Path) -> tuple[MinecraftRuntimeBuilder, RuntimeSpec]:
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
    return MinecraftRuntimeBuilder(context, MinecraftCatalog.load(pack)), spec


def write_source(root: Path, *, jar: bytes = JAR_BYTES) -> Path:
    """The provider cache: only the downloaded jar, never an EULA file."""
    root.mkdir(parents=True, exist_ok=True)
    (root / SERVER_JAR).write_bytes(jar)
    return root


def accept_eula(builder: MinecraftRuntimeBuilder, text: str = "eula=true\n") -> Path:
    """The operator's explicit step: Rhenium itself never writes this record."""
    builder.eula_record.parent.mkdir(parents=True, exist_ok=True)
    builder.eula_record.write_text(text, encoding="utf-8")
    return builder.eula_record


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
            images[identity] = identity
            for index, value in enumerate(arguments):
                if value == "--tag":
                    images[arguments[index + 1]] = identity
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
    accept_eula(builder)
    commands: list[list[str]] = []
    images: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    builder.runtime._docker = fake_docker_factory(commands, images, labels)  # type: ignore[method-assign]

    artifact = builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)
    builds = [args for args in commands if args[0] == "build"]
    assert len(builds) == 2  # base + one task
    assert builds[0][builds[0].index("--tag") + 1] == BASE_TAG
    assert all("--network=none" not in args for args in builds)
    assert artifact.metadata["sourceSha256"] == hashlib.sha256(JAR_BYTES).hexdigest()
    assert set(artifact.metadata["images"]) == {"sample-count-command"}
    assert artifact.runtime_key == "minecraft/paper-1.21.11-132"
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
    removed = [args[2] for args in commands if args[:2] == ["image", "rm"]]
    # The base is removed through the tags that still name it, never by a bare ID.
    assert removed == [first, BASE_TAG, builder.own_base_tag(spec)]


def test_an_image_built_from_an_older_suite_is_stale(sample_pack: Path, tmp_path: Path) -> None:
    """The fingerprint ignores tests/, so verify and task_image compare the build context."""
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    images: dict[str, str] = {}
    builder.runtime._docker = fake_docker_factory([], images, {})  # type: ignore[method-assign]
    source = write_source(tmp_path / "source")
    accept_eula(builder)
    artifact = builder.prepare(spec, source, tmp_path / "a", progress=lambda *_: None)
    task = builder.catalog.tasks[0]
    image = artifact.metadata["images"][task.id]
    assert builder.task_image(spec, artifact, task) == image

    suite = sample_pack / "private/harbor/sample-count-command/tests/suite/SampleSuite.java"
    suite.write_text(suite.read_text(encoding="utf-8") + "// a case added after prepare\n", encoding="utf-8")
    assert builder._fingerprint(spec) == artifact.fingerprint  # the record still looks current
    verification = builder.verify(spec, artifact)
    assert verification["available"] is False
    assert "sample-count-command was built from a different build context" in verification["reason"]
    with pytest.raises(RuntimeError, match="different build context"):
        builder.task_image(spec, artifact, task)

    del images[image]
    with pytest.raises(RuntimeError, match="sample-count-command is unavailable in Docker"):
        builder.task_image(spec, artifact, task)
    assert "unavailable in Docker" in builder.verify(spec, artifact)["reason"]


def test_every_base_keeps_a_tag_of_its_own(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    source = write_source(tmp_path / "source")
    accept_eula(builder)
    commands: list[list[str]] = []
    images: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    builder.runtime._docker = fake_docker_factory(commands, images, labels)  # type: ignore[method-assign]
    artifact = builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)
    own = builder.own_base_tag(spec)
    assert own.startswith(f"rhenium-minecraft:shared-base-{spec.id}-")
    base_build = next(args for args in commands if args[0] == "build")
    tags = [base_build[i + 1] for i, value in enumerate(base_build) if value == "--tag"]
    assert tags == [BASE_TAG, own]
    assert images[own] == artifact.metadata["baseImage"]
    other = spec.model_copy(update={"id": "paper-1.21.11-132-construct"})
    assert builder.own_base_tag(other) != own
    # Another runtime moved the shared tag: prune leaves it alone and removes the own tag.
    images[BASE_TAG] = "sha256:" + "f" * 64
    commands.clear()
    builder.prune(spec, artifact)
    removed = [args[2] for args in commands if args[:2] == ["image", "rm"]]
    assert BASE_TAG not in removed and removed[-1] == own


def test_prepare_rejects_digest_mismatch_and_requires_eula(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    commands: list[list[str]] = []
    builder.runtime._docker = fake_docker_factory(commands, {}, {})  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="SHA-256"):
        builder.prepare(
            spec, write_source(tmp_path / "bad", jar=b"other"), tmp_path / "a", progress=lambda *_: None
        )
    source = write_source(tmp_path / "source")
    # An eula.txt that arrived with the download is not the operator's acceptance.
    (source / EULA_FILE).write_text("eula=true\n", encoding="utf-8")
    for recorded in (None, "eula=false\n", "# eula=true\n"):
        if recorded is not None:
            accept_eula(builder, recorded)
        with pytest.raises(RuntimeActionRequired) as info:
            builder.prepare(spec, source, tmp_path / "a", progress=lambda *_: None)
        assert info.value.kind == "accept-eula"
        assert info.value.details == {
            "file": str(builder.eula_record),
            "expected": "eula=true",
            "eula": "https://aka.ms/MinecraftEULA",
        }
        assert "never by Rhenium" in str(info.value)
    assert builder.eula_record.read_text(encoding="utf-8") == "# eula=true\n"
    assert commands == []  # nothing is built without the operator's acceptance
    with pytest.raises(RuntimeError, match="missing"):
        builder.prepare(spec, tmp_path / "nowhere", tmp_path / "a", progress=lambda *_: None)


def test_prepare_and_doctor_never_write_the_eula_record(
    sample_pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    monkeypatch.setattr(builder.runtime, "status", lambda: {"available": True, "reason": None})
    with pytest.raises(RuntimeActionRequired):
        builder.prepare(spec, write_source(tmp_path / "source"), tmp_path / "a", progress=lambda *_: None)
    assert builder.doctor(spec)["eulaAccepted"] is False
    assert not builder.eula_record.exists()


def test_base_context_carries_the_operator_record_unchanged(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    record = "#By changing the setting below to TRUE you accept the EULA.\neula=true\n"
    accept_eula(builder, record)
    staged: dict[str, bytes] = {}
    inner = fake_docker_factory([], {}, {})

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if arguments[0] == "build" and not staged:
            context = Path(arguments[-1])
            staged.update({path.name: path.read_bytes() for path in context.iterdir() if path.is_file()})
        return inner(arguments, timeout=timeout)

    builder.runtime._docker = docker  # type: ignore[method-assign]
    builder.prepare(spec, write_source(tmp_path / "source"), tmp_path / "a", progress=lambda *_: None)
    assert staged == {SERVER_JAR: JAR_BYTES, EULA_FILE: record.encode()}


def test_withdrawn_acceptance_makes_the_artifact_unavailable(sample_pack: Path, tmp_path: Path) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    builder.runtime._docker = fake_docker_factory([], {}, {})  # type: ignore[method-assign]
    accept_eula(builder)
    source = write_source(tmp_path / "source")
    artifact = builder.prepare(spec, source, tmp_path / "a", progress=lambda *_: None)
    assert builder.verify(spec, artifact)["available"] is True
    builder.eula_record.unlink()
    verification = builder.verify(spec, artifact)
    assert verification["available"] is False and "never by Rhenium" in verification["reason"]
    with pytest.raises(RuntimeError, match="record your acceptance"):
        builder.task_image(spec, artifact, builder.catalog.tasks[0])


@pytest.mark.parametrize(
    ("text", "accepted"),
    [
        ("eula=true\n", True),
        ("# comment\nEULA = TRUE\n", True),
        ("eula=false\n", False),
        ("# eula=true\n", False),
        ("", False),
    ],
)
def test_eula_acceptance_parsing(tmp_path: Path, text: str, accepted: bool) -> None:
    path = tmp_path / "eula.txt"
    path.write_text(text, encoding="utf-8")
    assert eula_accepted(path) is accepted


def test_doctor_reports_operator_prerequisites(
    sample_pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder, spec = builder_and_spec(sample_pack, tmp_path)
    monkeypatch.setattr(builder.runtime, "status", lambda: {"available": True, "reason": None})
    report = builder.doctor(spec)
    assert report["eulaAccepted"] is False
    assert report["eulaRecord"] == str(tmp_path / "state" / EULA_FILE)
    assert str(builder.eula_record) in report["reason"]
    accept_eula(builder)
    report = builder.doctor(spec)
    assert report["eulaAccepted"] is True and report["reason"] is None


@pytest.mark.parametrize("pack", ["minecraft-core", "minecraft-construct"])
def test_pack_runtime_is_the_pinned_official_paper_download(pack: str) -> None:
    root = Path(__file__).resolve().parents[3] / "benchmarks" / pack
    (spec,) = RuntimeCatalog.load(root, "runtimes.json").runtimes
    assert spec.provider == "official-download"
    source = OfficialDownloadSource.model_validate(spec.source)
    (download,) = source.files
    digest = MinecraftRuntimeBuilder._pinned_digest(spec)
    assert download.name == SERVER_JAR and download.sha256 == digest
    assert download.url == f"https://fill-data.papermc.io/v1/objects/{digest}/{SERVER_JAR}"
    assert download.size == 54846016 and source.redirectHosts == ()
    assert spec.source["expectedFiles"] == [SERVER_JAR]


def test_runtime_source_is_not_stored_in_the_pack() -> None:
    pack = Path(__file__).resolve().parents[3] / "benchmarks" / "minecraft-core"
    assert not list(pack.rglob(SERVER_JAR))
    # Only build-tool wrapper bootstrap jars vendored with upstream starters may exist.
    assert {p.name for p in pack.rglob("*.jar")} <= {"gradle-wrapper.jar", "maven-wrapper.jar"}
