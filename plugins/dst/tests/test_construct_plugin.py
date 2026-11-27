"""The plugin serves the construct pack next to the repair pack.

Construct tasks keep the behavior they were validated with before the repair
pack replaced them: an empty from-scratch workspace, the generated task prompt,
the authored exam in an attempt, and their own runtime key.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from rhenium_dst.catalog import DstCatalog
from rhenium_dst.construct_catalog import DstConstructCatalog, DstConstructTask
from rhenium_dst.container import CONSTRUCT_RUNTIME_KEY, RUNTIME_KEY
from rhenium_dst.plugin import DstBenchmarkPlugin
from rhenium_dst.runtime_builder import DstRuntimeBuilder

from rhenium.config import Settings
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog, RuntimeSpec
from rhenium.hub import BenchmarkHub

ROOT = Path(__file__).parents[3]
CONSTRUCT = ROOT / "benchmarks" / "dst-construct"
REPAIR = ROOT / "benchmarks" / "dst"
PREPARE = ROOT / "scripts/prepare-exam"


def _context(tmp_path: Path, pack: Path = CONSTRUCT) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT, pack_root=pack, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )


def _task() -> DstConstructTask:
    return DstConstructCatalog.load(CONSTRUCT).tasks[0]


def test_plugin_loads_each_pack_with_its_own_catalog_model() -> None:
    plugin = DstBenchmarkPlugin()
    construct = plugin.load_catalog(CONSTRUCT, "fixed-v1.json")
    repair = plugin.load_catalog(REPAIR, "catalog.json")
    assert isinstance(construct, DstConstructCatalog) and construct.id == "rhenium-dst-v2"
    assert isinstance(repair, DstCatalog) and repair.id == "dst-core"


def test_construct_starter_is_an_empty_from_scratch_workspace(tmp_path: Path) -> None:
    plugin = DstBenchmarkPlugin()
    task = _task()
    workspace = tmp_path / "workspace"

    plugin.materialize_starter(task, workspace, _context(tmp_path))

    assert sorted(path.name for path in workspace.iterdir()) == ["TASK.md", "TASK.zh-CN.md", "task.json"]
    marker = json.loads((workspace / "task.json").read_text(encoding="utf-8"))
    assert marker == {"difficulty": "hard", "submission": ".", "fromScratch": True}
    prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
    assert "## Base-game API usage contract" in prompt
    assert all(required in prompt for required in task.required_files)
    assert "原版 API 使用合同" in (workspace / "TASK.zh-CN.md").read_text(encoding="utf-8")
    assert plugin.public_task(task)["fromScratch"] is True
    assert "implement the requested mod from scratch" in plugin.agent_system_prompt(task)


def test_construct_attempt_carries_the_authored_exam(tmp_path: Path) -> None:
    plugin = DstBenchmarkPlugin()
    task = _task()
    attempt = tmp_path / "attempt"
    attempt.mkdir()

    plugin.materialize_attempt(task, attempt, _context(tmp_path))

    assert {path.name for path in attempt.iterdir()} == {"AGENTS.md", "CLAUDE.md", "EXAM.md"}
    assert (attempt / "EXAM.md").read_bytes() == (CONSTRUCT / "exams" / f"{task.id}.md").read_bytes()
    assert (attempt / "AGENTS.md").read_bytes() == (ROOT / "AGENTS.md").read_bytes()


def test_each_runtime_id_gets_a_builder_over_its_own_pack(tmp_path: Path) -> None:
    plugin = DstBenchmarkPlugin()
    construct_spec = RuntimeCatalog.load(CONSTRUCT, "runtimes.json").runtimes[0]
    repair_spec = RuntimeCatalog.load(REPAIR, "runtimes.json").runtimes[0]

    construct = plugin.create_runtime_builder(_context(tmp_path), construct_spec)
    repair = plugin.create_runtime_builder(_context(tmp_path, REPAIR), repair_spec)

    assert isinstance(construct, DstRuntimeBuilder)
    assert isinstance(construct.catalog, DstConstructCatalog) and len(construct.catalog.tasks) == 10
    assert isinstance(repair, DstRuntimeBuilder)
    assert isinstance(repair.catalog, DstCatalog) and len(repair.catalog.tasks) == 5
    foreign = construct_spec.model_copy(update={"id": "dst-dedicated-other"})
    assert plugin.create_runtime_builder(_context(tmp_path), foreign) is None


def test_construct_prepare_labels_every_image_with_its_own_runtime_id(tmp_path: Path) -> None:
    spec = RuntimeCatalog.load(CONSTRUCT, "runtimes.json").runtimes[0]
    builder = DstBenchmarkPlugin().create_runtime_builder(_context(tmp_path), spec)
    assert isinstance(builder, DstRuntimeBuilder)
    source = tmp_path / "source"
    source.mkdir()
    reference = str(spec.source["image"])
    image_id = "sha256:" + "a" * 64
    (source / "image.json").write_text(json.dumps({
        "schemaVersion": 1, "image": reference, "imageId": image_id, "repoDigests": [reference],
    }))
    images = {reference: image_id}
    labels: dict[str, dict[str, str]] = {}
    builds: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        if arguments[:2] == ["image", "inspect"]:
            content = json.dumps(labels.get(arguments[2], {})) if arguments[-1] != "{{.Id}}" else images.get(
                arguments[2], "",
            )
            return subprocess.CompletedProcess(arguments, 0, content, "")
        if arguments[0] == "build":
            builds.append(arguments)
            tag = arguments[arguments.index("--tag") + 1]
            identity = "sha256:" + hashlib.sha256(tag.encode()).hexdigest()
            images[tag] = images[identity] = identity
            labels[identity] = dict(arguments[i + 1].split("=", 1)
                                    for i, value in enumerate(arguments) if value == "--label")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    builder.runtime._docker = docker  # type: ignore[method-assign]
    artifact = builder.prepare(spec, source, tmp_path / "artifact", progress=lambda *_: None)

    assert artifact.runtime_key == CONSTRUCT_RUNTIME_KEY
    assert artifact.metadata["runtime"] == "dst-dedicated-24700372-construct"
    assert len(builds) == 11  # the shared base plus ten construct task images
    base_context = str(CONSTRUCT / "private" / "runtime" / "dst-harbor-runtime")
    assert builds[0][-1] == base_context
    base_tags = [builds[0][i + 1] for i, value in enumerate(builds[0]) if value == "--tag"]
    fingerprint = spec.fingerprint(plugin_id="dst", plugin_version="0.6.0")
    assert base_tags == [
        "gcb-dst-dedicated-verifier:24700372",
        f"rhenium-dst:shared-base-{fingerprint[:12]}",
    ]
    assert {value["io.rhenium.runtime.id"] for value in labels.values()} == {spec.id}
    assert builder.verify(spec, artifact)["available"] is True
    assert builder.doctor(spec)["runtime"] == spec.id


def test_hub_serves_both_packs_under_distinct_task_and_runtime_keys(tmp_path: Path) -> None:
    state = tmp_path / "state"
    hub = BenchmarkHub(
        Settings(
            root=ROOT,
            state_dir=state,
            cache_dir=state / "cache",
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(REPAIR, CONSTRUCT),
            web_dist=None,
        ),
        plugins={"dst": DstBenchmarkPlugin()},
        evaluation_hosts={},
        manifest_paths=(REPAIR / "benchmark.json", CONSTRUCT / "benchmark.json"),
    )

    assert hub.discovery_errors == []
    construct_keys = [key for key in hub.task_keys if key.startswith("dst/construct/")]
    repair_keys = [key for key in hub.task_keys if key.startswith("dst/core/")]
    assert len(construct_keys) == 10 and len(repair_keys) == 5
    bindings = hub.runtime_manager.task_bindings
    assert all(bindings[key] == (CONSTRUCT_RUNTIME_KEY,) for key in construct_keys)
    assert all(bindings[key] == (RUNTIME_KEY,) for key in repair_keys)


def test_prepare_exam_bundles_the_construct_exam_anonymously(tmp_path: Path) -> None:
    environment = os.environ.copy()
    for name in (
        "RHENIUM_EVALUATION_SECURITY_MODE",
        "RHENIUM_EVALUATION_HOST_PROVIDER",
        "RHENIUM_EVALUATION_HOST_IMAGE",
    ):
        environment.pop(name, None)
    state = tmp_path / "state"
    environment["RHENIUM_STATE_DIR"] = str(state)
    environment["RHENIUM_CACHE_DIR"] = str(state / "cache")
    environment["RHENIUM_DATABASE_URL"] = f"sqlite:///{state / 'state.sqlite'}"
    environment["RHENIUM_BENCHMARK_PATH"] = str(ROOT / "benchmarks")
    environment["PATH"] = f"{Path(sys.executable).parent}:{environment.get('PATH', '')}"
    attempt = tmp_path / "attempt"

    completed = subprocess.run(
        [str(PREPARE), "dst/construct/container-transfer-transaction", str(attempt), "practice"],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in attempt.iterdir()} == {"AGENTS.md", "CLAUDE.md", "EXAM.md", "PROMPT.md"}
    bundle = "\n".join(path.read_text(encoding="utf-8") for path in attempt.iterdir())
    task_ids = [task.id for task in DstConstructCatalog.load(CONSTRUCT).tasks]
    assert all(task_id not in bundle for task_id in task_ids)
    assert "dst/construct" not in bundle
    assert "Base-game API contract" in bundle
    assert "AddModRPCHandler" in bundle
    assert 'score-exam" "$PWD"' in bundle
    assert "Mode: `practice`" in bundle


def _pruning_builder(
    tmp_path: Path, shared_tag_names_base: bool
) -> tuple[DstRuntimeBuilder, RuntimeSpec, RuntimeArtifact, list[list[str]]]:
    spec = RuntimeCatalog.load(CONSTRUCT, "runtimes.json").runtimes[0]
    builder = DstBenchmarkPlugin().create_runtime_builder(_context(tmp_path), spec)
    assert isinstance(builder, DstRuntimeBuilder)
    base = "sha256:" + "b" * 64
    images = {
        task.id: "sha256:" + hashlib.sha256(task.id.encode()).hexdigest()
        for task in builder.catalog.tasks
    }
    names: dict[str, str] = {base: base, builder._own_base_tag(spec): base, **{v: v for v in images.values()}}
    names["gcb-dst-dedicated-verifier:24700372"] = base if shared_tag_names_base else "sha256:" + "c" * 64
    labels = {base: builder._labels(spec, "shared-base", builder._base_context())}
    for task in builder.catalog.tasks:
        labels[images[task.id]] = builder._labels(spec, task.id, builder._task_context(task))
    removed: list[list[str]] = []

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        if arguments[:2] == ["image", "inspect"]:
            reference = arguments[2]
            if arguments[-1] == "{{.Id}}":
                found = names.get(reference, "")
                return subprocess.CompletedProcess(arguments, 0 if found else 1, found, "")
            return subprocess.CompletedProcess(arguments, 0, json.dumps(labels.get(reference, {})), "")
        if arguments[:2] == ["image", "rm"]:
            removed.append(arguments)
            return subprocess.CompletedProcess(arguments, 0, "", "")
        raise AssertionError(arguments)

    builder.runtime._docker = docker  # type: ignore[method-assign]
    artifact = RuntimeArtifact(
        runtime_key=CONSTRUCT_RUNTIME_KEY,
        fingerprint=builder._fingerprint(spec),
        kind="docker-images",
        identity=builder._artifact_identity(base, images),
        metadata={"baseImage": base, "images": images},
    )
    return builder, spec, artifact, removed


def test_prune_removes_each_base_tag_that_still_names_the_owned_base(tmp_path: Path) -> None:
    builder, spec, artifact, removed = _pruning_builder(tmp_path, shared_tag_names_base=True)
    builder.prune(spec, artifact)
    base_removals = [args[2] for args in removed if not args[2].startswith("sha256:")]
    assert base_removals == ["gcb-dst-dedicated-verifier:24700372", builder._own_base_tag(spec)]
    assert len(removed) == 12  # ten task images by ID, then the two base tags

    builder, spec, artifact, removed = _pruning_builder(tmp_path, shared_tag_names_base=False)
    builder.prune(spec, artifact)
    # The shared tag now names another pack's base, which pruning must leave alone.
    assert [args[2] for args in removed if not args[2].startswith("sha256:")] == [
        builder._own_base_tag(spec)
    ]
