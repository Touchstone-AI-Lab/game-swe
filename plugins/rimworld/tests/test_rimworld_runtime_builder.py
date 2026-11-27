from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from rhenium_rimworld.catalog import RimWorldCatalog
from rhenium_rimworld.evaluator import (
    IMAGE_ROLES,
    RUNTIME_BUILD_LABEL,
    RUNTIME_FINGERPRINT_LABEL,
    RUNTIME_ID_LABEL,
    RUNTIME_ROLE_LABEL,
    RUNTIME_RUBRIC_LABEL,
    RUNTIME_SOURCE_LABEL,
    RUNTIME_SOURCE_TREE_LABEL,
    RUNTIME_TASK_LABEL,
    RUNTIME_TASK_SOURCE_LABEL,
    RimWorldRuntime,
)
from rhenium_rimworld.runtime_builder import RimWorldRuntimeBuilder

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog, RuntimeSpec

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "rimworld-core"


def _context(tmp_path: Path, pack: Path = PACK) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def _spec() -> RuntimeSpec:
    return RuntimeCatalog.load(PACK, "runtimes.json").runtimes[0]


def _source(tmp_path: Path, spec: RuntimeSpec, version: str = "1.6.4871 rev-test") -> Path:
    source = tmp_path / "source"
    source.mkdir(parents=True)
    for raw in spec.source["expectedFiles"]:
        relative = str(raw)
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(version if relative == "Version.txt" else "fixture", encoding="utf-8")
    (source / "RimWorldLinux").chmod(0o755)
    return source


def _destination(tmp_path: Path, spec: RuntimeSpec) -> Path:
    return _context(tmp_path).cache_dir / "runtimes" / "rimworld" / spec.id


class FakeDocker:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.builds: list[list[str]] = []
        self.removed: list[str] = []
        self.images: dict[str, str] = {}
        self.labels: dict[str, dict[str, str]] = {}
        self.context_files: list[set[str]] = []
        self.daemon_error = False
        self.image_os = "linux"
        self.image_arch = "amd64"

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
        if arguments[0] == "info":
            return self._completed(
                arguments, stdout='"27.0" "Docker Linux" "linux" "amd64"\n'
            )
        if arguments[:2] == ["image", "inspect"]:
            if self.daemon_error:
                return self._completed(arguments, 1, stderr="daemon permission denied")
            reference = arguments[2]
            output_format = arguments[-1]
            if reference in self.images and output_format == "{{.Id}}":
                return self._completed(arguments, stdout=self.images[reference] + "\n")
            if reference in self.labels and output_format == "{{json .Config.Labels}}":
                return self._completed(arguments, stdout=json.dumps(self.labels[reference]))
            if (
                reference in self.images
                and output_format == "{{json .Os}} {{json .Architecture}}"
            ):
                return self._completed(
                    arguments,
                    stdout=json.dumps(self.image_os) + " " + json.dumps(self.image_arch),
                )
            return self._completed(arguments, returncode=1, stderr="No such image")
        if arguments[0] == "build":
            self.builds.append(arguments)
            context = Path(arguments[-1])
            self.context_files.append(
                {
                    path.relative_to(context).as_posix()
                    for path in context.rglob("*")
                    if path.is_file()
                }
            )
            tag = arguments[arguments.index("--tag") + 1]
            labels: dict[str, str] = {}
            for index, value in enumerate(arguments):
                if value == "--label":
                    key, label_value = arguments[index + 1].split("=", 1)
                    labels[key] = label_value
            image_id = "sha256:" + hashlib.sha256(tag.encode()).hexdigest()
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


def _builder(
    tmp_path: Path, fake: FakeDocker, pack: Path = PACK
) -> RimWorldRuntimeBuilder:
    builder = RimWorldRuntimeBuilder(_context(tmp_path, pack), RimWorldCatalog.load(pack))
    builder.runtime._docker = fake  # type: ignore[method-assign]
    builder.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    return builder


def _prepare(
    tmp_path: Path,
) -> tuple[RimWorldRuntimeBuilder, RuntimeSpec, FakeDocker, RuntimeArtifact]:
    spec = _spec()
    fake = FakeDocker()
    builder = _builder(tmp_path, fake)
    artifact = builder.prepare(
        spec,
        _source(tmp_path, spec),
        _destination(tmp_path, spec),
        progress=lambda _value, _phase: None,
    )
    return builder, spec, fake, artifact


def test_prepare_stages_only_reviewed_inputs_and_binds_role_images(tmp_path: Path) -> None:
    spec = _spec()
    fake = FakeDocker()
    builder = _builder(tmp_path, fake)
    source = _source(tmp_path, spec)
    (source / "unrelated-steam-cache.txt").write_text("must not be staged", encoding="utf-8")
    artifact = builder.prepare(
        spec,
        source,
        _destination(tmp_path, spec),
        progress=lambda _value, _phase: None,
    )

    assert len(fake.builds) == len(IMAGE_ROLES) * len(builder.catalog.tasks)
    assert artifact.kind == "docker-image-roles"
    task_images = artifact.metadata["images"][builder.catalog.tasks[0].id]
    assert set(task_images) == set(IMAGE_ROLES)
    assert all(value.startswith("sha256:") for value in task_images.values())
    assert set(artifact.metadata["images"]) == {task.id for task in builder.catalog.tasks}
    assert set(artifact.metadata["evidence"]) == {task.id for task in builder.catalog.tasks}
    assert len({
        item["adapter"] for item in artifact.metadata["evidence"].values()
    }) == len(builder.catalog.tasks)
    assert len({
        item["rubric"] for item in artifact.metadata["evidence"].values()
    }) == len(builder.catalog.tasks)
    assert len({
        item["taskSource"] for item in artifact.metadata["evidence"].values()
    }) == len(builder.catalog.tasks)
    assert all("unrelated-steam-cache.txt" not in files for files in fake.context_files)
    assert all("tests/assertions.json" not in files for files in fake.context_files)
    assert all(
        "tests/Harness/GeneratedAssertions.cs" in files for files in fake.context_files
    )
    assert all(str(_destination(tmp_path, spec)) in arguments[-1] for arguments in fake.builds)
    for arguments in fake.builds:
        joined = "\n".join(arguments)
        assert RUNTIME_FINGERPRINT_LABEL in joined
        assert RUNTIME_SOURCE_LABEL in joined
        assert RUNTIME_TASK_LABEL in joined
        assert RUNTIME_ID_LABEL in joined
        assert RUNTIME_BUILD_LABEL in joined
        assert RUNTIME_ROLE_LABEL in joined
        assert RUNTIME_RUBRIC_LABEL in joined
        assert RUNTIME_SOURCE_TREE_LABEL in joined
        assert RUNTIME_TASK_SOURCE_LABEL in joined

    for index, task in enumerate(builder.catalog.tasks):
        staged = fake.context_files[index * len(IMAGE_ROLES)]
        assert task.mod_metadata_path in staged
        # Declared runtime definitions are staged; nothing else under ModMetadata is.
        assert set(task.runtime_data_files) <= set(staged)
        assert not any(
            path.startswith("tests/ModMetadata/")
            and path not in {
                task.mod_metadata_path,
                "tests/ModMetadata/Verifier/About.xml",
                *task.runtime_data_files,
            }
            for path in staged
        )


def test_container_log_options_are_accepted_by_docker() -> None:
    """The local driver rejects a single rotated file unless compression is off."""
    from rhenium_rimworld.evaluator import RimWorldRuntime

    arguments = RimWorldRuntime._sandbox_arguments(user="1000:1000")
    assert "--log-opt=max-file=1" in arguments
    assert "--log-opt=compress=false" in arguments
    # nproc counts every task of the uid on the host, so only the cgroup limit is used.
    assert "--pids-limit=512" in arguments
    assert not any(argument.startswith("nproc=") for argument in arguments)


def test_prepare_makes_the_staged_launcher_executable(tmp_path: Path) -> None:
    """Depot downloads arrive without POSIX modes; the image needs a runnable launcher."""
    spec = _spec()
    builder = _builder(tmp_path, FakeDocker())
    source = _source(tmp_path / "plain", spec)
    (source / "RimWorldLinux").chmod(0o644)
    destination = _destination(tmp_path, spec)

    context = tmp_path / "build-context"
    context.mkdir()
    builder._stage_build_context(builder.catalog.tasks[0], source, context)

    staged = context / "game-files" / "RimWorldLinux"
    assert staged.is_file()
    assert staged.stat().st_mode & 0o111
    del builder, destination


def test_prepare_rejects_wrong_types_versions_and_symlinks(tmp_path: Path) -> None:
    spec = _spec()
    builder = _builder(tmp_path, FakeDocker())
    wrong = _source(tmp_path / "wrong", spec, "1.6.4850 rev-test")
    with pytest.raises(RuntimeError, match="not RimWorld 1.6.4871"):
        builder.prepare(spec, wrong, _destination(tmp_path, spec), progress=lambda _a, _b: None)

    # A Steam depot carries no POSIX mode, which is how the real acquisition arrives.
    source = _source(tmp_path / "mode", spec)
    os.chmod(source / "RimWorldLinux", 0o644)
    builder.prepare(spec, source, _destination(tmp_path, spec), progress=lambda _a, _b: None)

    source = _source(tmp_path / "symlink", spec)
    (source / "Version.txt").unlink()
    (source / "Version.txt").symlink_to(tmp_path / "outside-version")
    with pytest.raises(RuntimeError, match="missing expected"):
        builder.prepare(spec, source, _destination(tmp_path, spec), progress=lambda _a, _b: None)

    source = _source(tmp_path / "type", spec)
    (source / "UnityPlayer.so").unlink()
    (source / "UnityPlayer.so").mkdir()
    with pytest.raises(RuntimeError, match="missing expected"):
        builder.prepare(spec, source, _destination(tmp_path, spec), progress=lambda _a, _b: None)


def test_prepare_validates_declared_source_sha256(tmp_path: Path) -> None:
    spec = _spec()
    source_data = dict(spec.source)
    source_data["sha256"] = {"Version.txt": "0" * 64}
    pinned = spec.model_copy(update={"source": source_data})
    builder = _builder(tmp_path, FakeDocker())

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        builder.prepare(
            pinned,
            _source(tmp_path, pinned),
            _destination(tmp_path, pinned),
            progress=lambda _a, _b: None,
        )


def test_verify_rejects_artifact_and_label_mismatch(tmp_path: Path) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    assert builder.verify(spec, artifact)["available"] is True

    stale = artifact.model_copy(update={"fingerprint": "stale"})
    assert builder.verify(spec, stale)["available"] is False

    first_task = builder.catalog.tasks[0].id
    first_image = artifact.metadata["images"][first_task]["evaluator"]
    fake.labels[first_image][RUNTIME_TASK_LABEL] = "rimworld/other/task"
    result = builder.verify(spec, artifact)
    assert result["available"] is False
    assert "labels do not match" in str(result["reason"])

    fake.labels[first_image][RUNTIME_TASK_LABEL] = f"rimworld/core/{first_task}"
    fake.image_arch = "arm64"
    result = builder.verify(spec, artifact)
    assert result["available"] is False
    assert "not Linux x86_64" in str(result["reason"])


def test_verify_rejects_artifact_from_stale_pack_inputs(tmp_path: Path) -> None:
    copied_pack = tmp_path / "pack"
    shutil.copytree(PACK, copied_pack)
    spec = RuntimeCatalog.load(copied_pack, "runtimes.json").runtimes[0]
    fake = FakeDocker()
    builder = _builder(tmp_path, fake, copied_pack)
    artifact = builder.prepare(
        spec,
        _source(tmp_path, spec),
        _destination(tmp_path, spec),
        progress=lambda _value, _phase: None,
    )
    support = copied_pack / "private" / "harbor" / builder.catalog.tasks[0].id
    support = support / "tests" / "Support.cs"
    support.write_text(support.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = builder.verify(spec, artifact)
    assert result["available"] is False
    assert "current pack inputs" in str(result["reason"])


def test_verify_rejects_artifact_from_stale_private_assertions(tmp_path: Path) -> None:
    copied_pack = tmp_path / "pack"
    shutil.copytree(PACK, copied_pack)
    spec = RuntimeCatalog.load(copied_pack, "runtimes.json").runtimes[0]
    fake = FakeDocker()
    builder = _builder(tmp_path, fake, copied_pack)
    artifact = builder.prepare(
        spec,
        _source(tmp_path, spec),
        _destination(tmp_path, spec),
        progress=lambda _value, _phase: None,
    )
    assertions = copied_pack / "private" / "harbor" / builder.catalog.tasks[0].id
    assertions = assertions / "tests" / "assertions.json"
    payload = json.loads(assertions.read_text(encoding="utf-8"))
    payload["cases"][2]["expected"]["outputs"][0]["entries"][0]["count"] += 1
    assertions.write_text(json.dumps(payload), encoding="utf-8")

    result = builder.verify(spec, artifact)
    assert result["available"] is False
    assert "current pack inputs" in str(result["reason"])


def test_verify_rejects_artifact_from_stale_task_source(tmp_path: Path) -> None:
    copied_pack = tmp_path / "pack"
    shutil.copytree(PACK, copied_pack)
    spec = RuntimeCatalog.load(copied_pack, "runtimes.json").runtimes[0]
    fake = FakeDocker()
    builder = _builder(tmp_path, fake, copied_pack)
    artifact = builder.prepare(
        spec,
        _source(tmp_path, spec),
        _destination(tmp_path, spec),
        progress=lambda _value, _phase: None,
    )
    task = builder.catalog.tasks[1]
    source = copied_pack / "private" / "harbor" / task.id / "environment"
    source = source / task.required_files[0]
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    result = builder.verify(spec, artifact)
    assert result["available"] is False
    assert "current task evidence" in str(result["reason"])


def test_prune_prevalidates_all_ownership_and_distinguishes_daemon_errors(
    tmp_path: Path,
) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    task_id = builder.catalog.tasks[0].id
    evaluator_image = artifact.metadata["images"][task_id]["evaluator"]
    fake.labels[evaluator_image][RUNTIME_SOURCE_LABEL] = "steam:other"
    with pytest.raises(RuntimeError, match="unowned"):
        builder.prune(spec, artifact)
    assert fake.removed == []

    fake.labels[evaluator_image][RUNTIME_SOURCE_LABEL] = artifact.metadata["sourceIdentity"]
    fake.daemon_error = True
    with pytest.raises(RuntimeError, match="Docker daemon"):
        builder.prune(spec, artifact)
    assert fake.removed == []


def test_prune_is_idempotent_for_owned_or_missing_role_images(tmp_path: Path) -> None:
    builder, spec, fake, artifact = _prepare(tmp_path)
    expected = {
        image
        for task_images in artifact.metadata["images"].values()
        for image in task_images.values()
    }
    builder.prune(spec, artifact)
    assert set(fake.removed) == expected
    builder.prune(spec, artifact)
    assert set(fake.removed) == expected


def test_doctor_requires_linux_x86_64_daemon_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = RimWorldRuntime(_context(tmp_path), RimWorldCatalog.load(PACK))
    fake = FakeDocker()
    runtime.docker = "/fake/docker"
    runtime._docker = fake  # type: ignore[method-assign]
    monkeypatch.setattr("rhenium_rimworld.evaluator.platform.system", lambda: "Linux")
    monkeypatch.setattr("rhenium_rimworld.evaluator.platform.machine", lambda: "x86_64")

    status = runtime.status()
    assert status["available"] is True
    assert status["engineLaunchValidated"] is False
