from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog
from rhenium_garrys_mod.darkrp.evaluator import (
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID_LABEL,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_TASK_LABEL,
)
from rhenium_garrys_mod.darkrp.runtime_builder import GarrysModRuntimeBuilder

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog, RuntimeSpec

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "darkrp-core"
SOURCE_IMAGE_ID = "sha256:" + "a" * 64
STALE_IMAGE_ID = "sha256:" + "f" * 64


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def _spec() -> RuntimeSpec:
    return RuntimeCatalog.load(PACK, "runtimes.json").runtimes[0]


def _write_source(
    root: Path,
    spec: RuntimeSpec,
    *,
    reference: str | None = None,
    image_id: str = SOURCE_IMAGE_ID,
) -> Path:
    source = root / "source"
    source.mkdir()
    expected_reference = str(spec.source["image"])
    selected = reference or expected_reference
    (source / "image.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "image": selected,
                "imageId": image_id,
                "repoDigests": [selected],
            }
        ),
        encoding="utf-8",
    )
    return source


class FakeDocker:
    def __init__(self, source_reference: str, *, source_files_available: bool = True):
        self.source_reference = source_reference
        self.source_files_available = source_files_available
        self.calls: list[list[str]] = []
        self.builds: list[list[str]] = []
        self.removed: list[str] = []
        self.images: dict[str, str] = {}
        self.labels: dict[str, dict[str, str]] = {}

    @staticmethod
    def _completed(
        arguments: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)

    def __call__(
        self, arguments: list[str], *, timeout: float
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        self.calls.append(arguments)
        if arguments[:2] == ["image", "inspect"]:
            reference = arguments[2]
            output_format = arguments[-1]
            if reference == self.source_reference and output_format == "{{.Id}}":
                return self._completed(arguments, stdout=SOURCE_IMAGE_ID + "\n")
            if reference in self.images and output_format == "{{.Id}}":
                return self._completed(arguments, stdout=self.images[reference] + "\n")
            if reference in self.labels and output_format == "{{json .Config.Labels}}":
                return self._completed(arguments, stdout=json.dumps(self.labels[reference]))
            # Simulate an arbitrary image already carrying the old predictable tag.
            if reference.startswith("rhenium-garrys-mod:") and output_format == "{{.Id}}":
                return self._completed(arguments, stdout=STALE_IMAGE_ID + "\n")
            return self._completed(arguments, returncode=1, stderr="No such image")
        if arguments[0] == "run":
            if self.source_files_available:
                return self._completed(arguments)
            return self._completed(arguments, returncode=1, stderr="missing expected file")
        if arguments[0] == "build":
            self.builds.append(arguments)
            tag = arguments[arguments.index("--tag") + 1]
            labels: dict[str, str] = {}
            for index, value in enumerate(arguments):
                if value == "--label":
                    key, label_value = arguments[index + 1].split("=", 1)
                    labels[key] = label_value
            task_id = labels[RUNTIME_TASK_LABEL]
            image_id = "sha256:" + hashlib.sha256(f"fresh:{task_id}".encode()).hexdigest()
            self.images[tag] = image_id
            self.images[image_id] = image_id
            self.labels[image_id] = labels
            return self._completed(arguments, stdout="built")
        if arguments[:2] == ["image", "rm"]:
            image_id = arguments[2]
            if image_id not in self.labels:
                return self._completed(arguments, returncode=1, stderr="No such image")
            self.removed.append(image_id)
            self.labels.pop(image_id)
            for reference, current in list(self.images.items()):
                if reference == image_id or current == image_id:
                    self.images.pop(reference)
            return self._completed(arguments)
        raise AssertionError(f"unexpected Docker command: {arguments}")


def _builder(tmp_path: Path, fake: FakeDocker) -> GarrysModRuntimeBuilder:
    builder = GarrysModRuntimeBuilder(_context(tmp_path), GarrysModCatalog.load(PACK))
    builder.runtime._docker = fake  # type: ignore[method-assign]
    return builder


def _prepare(
    tmp_path: Path, *, source_files_available: bool = True
) -> tuple[GarrysModRuntimeBuilder, RuntimeSpec, FakeDocker, RuntimeArtifact]:
    spec = _spec()
    reference = str(spec.source["image"])
    fake = FakeDocker(reference, source_files_available=source_files_available)
    builder = _builder(tmp_path, fake)
    artifact = builder.prepare(
        spec,
        _write_source(tmp_path, spec),
        tmp_path / "artifact",
        progress=lambda _value, _phase: None,
    )
    return builder, spec, fake, artifact


def test_prepare_binds_the_source_validates_files_and_rebuilds_stale_tags(
    tmp_path: Path,
) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    fingerprint = builder._fingerprint(spec)

    assert len(fake.builds) == len(builder.catalog.tasks)
    assert set(artifact.metadata["images"].values()) != {STALE_IMAGE_ID}
    source_checks = [arguments for arguments in fake.calls if arguments[0] == "run"]
    assert len(source_checks) == 1
    assert "--network=none" in source_checks[0]
    assert "--pull=never" in source_checks[0]
    assert tuple(spec.source["expectedFiles"]) == tuple(source_checks[0][-1:])
    for arguments in fake.builds:
        joined = "\n".join(arguments)
        assert f"{RUNTIME_FINGERPRINT_LABEL}={fingerprint}" in joined
        assert f"{RUNTIME_SOURCE_LABEL}={spec.source['image']}" in joined
        assert f"{RUNTIME_ID_LABEL}=gmod-gluatest-darkrp" in joined
        assert f"{RUNTIME_BUILD_LABEL}=sha256:" in joined


def test_prepare_rejects_a_source_record_for_another_image(tmp_path: Path) -> None:
    spec = _spec()
    reference = str(spec.source["image"])
    fake = FakeDocker(reference)
    builder = _builder(tmp_path, fake)

    with pytest.raises(RuntimeError, match="does not match the runtime source"):
        builder.prepare(
            spec,
            _write_source(tmp_path, spec, reference="example.invalid/image@sha256:" + "b" * 64),
            tmp_path / "artifact",
            progress=lambda _value, _phase: None,
        )

    assert fake.calls == []


def test_prepare_rejects_a_source_missing_declared_files(tmp_path: Path) -> None:
    spec = _spec()
    reference = str(spec.source["image"])
    fake = FakeDocker(reference, source_files_available=False)
    builder = _builder(tmp_path, fake)

    with pytest.raises(RuntimeError, match="missing required runtime files"):
        builder.prepare(
            spec,
            _write_source(tmp_path, spec),
            tmp_path / "artifact",
            progress=lambda _value, _phase: None,
        )

    assert fake.builds == []


def test_prepare_rejects_a_source_record_with_the_wrong_local_image_id(tmp_path: Path) -> None:
    spec = _spec()
    reference = str(spec.source["image"])
    fake = FakeDocker(reference)
    builder = _builder(tmp_path, fake)

    with pytest.raises(RuntimeError, match="does not match the pulled image ID"):
        builder.prepare(
            spec,
            _write_source(tmp_path, spec, image_id="sha256:" + "d" * 64),
            tmp_path / "artifact",
            progress=lambda _value, _phase: None,
        )

    assert fake.builds == []


def test_verify_requires_immutable_ids_and_matching_ownership_labels(tmp_path: Path) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    assert builder.verify(spec, artifact)["available"] is True

    first_image = next(iter(artifact.metadata["images"].values()))
    fake.labels[first_image][RUNTIME_SOURCE_LABEL] = "example.invalid/other@sha256:" + "c" * 64
    result = builder.verify(spec, artifact)

    assert result["available"] is False
    assert "labels do not match" in str(result["reason"])


def test_verify_rejects_a_mutable_tag_even_when_it_resolves_to_an_owned_image(
    tmp_path: Path,
) -> None:
    builder, spec, _fake, artifact = _prepare(tmp_path)
    images = dict(artifact.metadata["images"])
    first_task = builder.catalog.tasks[0]
    images[first_task.id] = builder.runtime.image_tag(first_task, builder._fingerprint(spec))
    metadata = {**artifact.metadata, "images": images}
    mutable = artifact.model_copy(
        update={"metadata": metadata, "identity": builder._artifact_identity(images)}
    )

    result = builder.verify(spec, mutable)

    assert result["available"] is False
    assert "mutable identity" in str(result["reason"])


def test_prune_removes_only_owned_immutable_ids_and_is_idempotent(tmp_path: Path) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    expected = set(artifact.metadata["images"].values())

    builder.prune(spec, artifact)
    assert set(fake.removed) == expected

    builder.prune(spec, artifact)
    assert set(fake.removed) == expected


def test_prune_refuses_an_unowned_image_before_removing_anything(tmp_path: Path) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    last_image = next(reversed(artifact.metadata["images"].values()))
    fake.labels[last_image][RUNTIME_TASK_LABEL] = "another-task"

    with pytest.raises(RuntimeError, match="refusing to prune an unowned evaluator image"):
        builder.prune(spec, artifact)

    assert fake.removed == []
