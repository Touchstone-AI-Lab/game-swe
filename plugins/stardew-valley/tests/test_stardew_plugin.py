from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_stardew_valley.catalog import StardewCatalog, StardewTask
from rhenium_stardew_valley.evaluator import (
    SUBMISSION_SYNC_OPTIONS,
    StardewEvaluator,
    StardewRuntime,
)
from rhenium_stardew_valley.plugin import StardewValleyBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "stardew-core"
TASK_COUNT = 11
REPAIR_TASK_COUNT = 9
GENERATION_TASKS = ("stardew-summon-horse-anywhere", "stardew-auto-workshop")


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


REPAIR_TASK = "stardew-automate-zero-stack-output"
GENERATION_TASK = "stardew-summon-horse-anywhere"


def test_catalog_exposes_nine_repair_and_two_generation_tasks() -> None:
    catalog = StardewCatalog.load(PACK)

    assert catalog.game == "stardew-valley"
    assert catalog.version == "1.5.0"
    assert len(catalog.tasks) == TASK_COUNT
    assert sum(task.task_kind == "debugging" for task in catalog.tasks) == REPAIR_TASK_COUNT
    assert tuple(task.id for task in catalog.tasks if task.task_kind == "generation") == GENERATION_TASKS
    assert not any(task.clean_room_synthetic for task in catalog.tasks)
    for task in catalog.tasks:
        expected = "mod" if task.task_kind == "generation" else "StardewMods"
        assert task.starter_name == expected, task.id
    repair = next(task for task in catalog.tasks if task.id == REPAIR_TASK)
    assert repair.difficulty == "medium"
    assert repair.source_mod == "Automate"
    assert repair.authored_prompt.startswith("# ")
    summon = next(task for task in catalog.tasks if task.id == GENERATION_TASK)
    assert summon.difficulty == "medium"
    assert summon.source_mod == "Horse Flute Anywhere"
    assert summon.authored_prompt.startswith("# Write a mod: summon your horse anywhere")


def test_catalog_rejects_an_unknown_task_kind() -> None:
    catalog = StardewCatalog.load(PACK)
    data = catalog.tasks[0].model_dump()
    data["task_kind"] = "construct"

    with pytest.raises(ValueError, match="task_kind"):
        StardewTask.model_validate(data)


def test_generation_task_must_keep_required_files_below_its_mod_project() -> None:
    catalog = StardewCatalog.load(PACK)
    data = next(task for task in catalog.tasks if task.id == GENERATION_TASK).model_dump()
    data["required_files"] = ["StardewMods/SummonAnywhere/ModEntry.cs"]

    with pytest.raises(ValueError, match="below mod/"):
        StardewTask.model_validate(data)


@pytest.mark.parametrize(
    ("task_id", "from_scratch", "mode"),
    [(REPAIR_TASK, False, "SMAPI mod repair"), (GENERATION_TASK, True, "new SMAPI mod")],
)
def test_public_task_and_agent_prompt_follow_the_task_kind(
    task_id: str, from_scratch: bool, mode: str
) -> None:
    plugin = StardewValleyBenchmarkPlugin()
    catalog = plugin.load_catalog(PACK, "catalog.json")
    task = next(task for task in catalog.tasks if task.id == task_id)

    public = plugin.public_task(task)

    assert public["fromScratch"] is from_scratch
    assert public["taskKind"] == ("generation" if from_scratch else "debugging")
    assert f"Stardew Valley {mode} benchmark" in plugin.agent_system_prompt(task)


@pytest.mark.parametrize(
    ("task_id", "starter_file", "from_scratch"),
    [
        (REPAIR_TASK, "StardewMods/Automate/Framework/MachineGroup.cs", False),
        (GENERATION_TASK, "mod/SummonAnywhere/ModEntry.cs", True),
    ],
)
def test_materialized_attempt_contains_public_source_but_no_private_assets(
    tmp_path: Path, task_id: str, starter_file: str, from_scratch: bool
) -> None:
    plugin = StardewValleyBenchmarkPlugin()
    catalog = plugin.load_catalog(PACK, "catalog.json")
    task = next(task for task in catalog.tasks if task.id == task_id)
    destination = tmp_path / "attempt"
    destination.mkdir()

    plugin.materialize_attempt(task, destination, _context(tmp_path))

    assert (destination / starter_file).is_file()
    assert (destination / "EXAM.md").is_file()
    marker = json.loads((destination / "task.json").read_text(encoding="utf-8"))
    assert marker["fromScratch"] is from_scratch
    assert not (destination / "tests").exists()
    assert not (destination / "solution").exists()
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert str(PACK) not in public_text
    assert task.id not in public_text


@pytest.mark.parametrize("task_id", [REPAIR_TASK, GENERATION_TASK])
def test_core_profile_is_incomplete_without_invoking_docker(tmp_path: Path, task_id: str) -> None:
    catalog = StardewCatalog.load(PACK)
    task = next(task for task in catalog.tasks if task.id == task_id)
    plugin = StardewValleyBenchmarkPlugin()
    submission = tmp_path / "submission"
    submission.mkdir()
    plugin.materialize_starter(task, submission, _context(tmp_path))
    evaluator = StardewEvaluator(_context(tmp_path), catalog)

    result = evaluator.evaluate(submission, task, profile="core")

    assert result["score"] == 10.0
    assert result["complete"] is False
    assert result["passed"] is False
    assert result["checks"][1]["status"] == "skipped"


@pytest.mark.parametrize("task_id", [REPAIR_TASK, GENERATION_TASK])
def test_full_profile_fails_closed_when_runtime_is_unavailable(
    tmp_path: Path, monkeypatch: Any, task_id: str
) -> None:
    catalog = StardewCatalog.load(PACK)
    task = next(task for task in catalog.tasks if task.id == task_id)
    plugin = StardewValleyBenchmarkPlugin()
    submission = tmp_path / "submission"
    submission.mkdir()
    plugin.materialize_starter(task, submission, _context(tmp_path))
    evaluator = StardewEvaluator(_context(tmp_path), catalog)
    evaluator.runtime.docker = str(tmp_path / "missing-docker")

    result = evaluator.evaluate(submission, task, profile="full")

    assert result["complete"] is False
    assert result["passed"] is False
    assert result["runtime"]["status"] == "unavailable"


class RecordingRuntime(StardewRuntime):
    def __init__(self, context: BenchmarkContext, catalog: StardewCatalog):
        super().__init__(context, catalog)
        self.arguments: list[str] = []

    def ensure_image(self, task: StardewTask, *, game_dir: Path) -> tuple[str, str]:
        del game_dir
        return self.image_tag(task), ""

    def image_id(self, task: StardewTask) -> str:
        del task
        return "sha256:test-image"

    def _docker(
        self,
        arguments: list[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        if arguments[0] == "create":
            self.arguments = arguments
            return subprocess.CompletedProcess(arguments, 0, "a" * 64, "")
        return subprocess.CompletedProcess(arguments, 0, "", "")


@pytest.mark.parametrize("task_id", [REPAIR_TASK, GENERATION_TASK])
def test_runtime_container_is_networkless_and_receives_no_model_secret(
    tmp_path: Path, task_id: str
) -> None:
    catalog = StardewCatalog.load(PACK)
    task = next(task for task in catalog.tasks if task.id == task_id)
    runtime = RecordingRuntime(_context(tmp_path), catalog)
    submission = tmp_path / "submission"
    logs = tmp_path / "logs"
    submission.mkdir()
    logs.mkdir()

    runtime.run(task, submission, logs)

    command = " ".join(runtime.arguments)
    assert "--network=none" in runtime.arguments
    assert "no-new-privileges:true" in command
    assert "--no-owner --no-group" in command
    assert "target=/logs" not in command
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in command
    assert "ANTHROPIC_API_KEY" not in command


def test_docker_control_plane_calls_tolerate_a_busy_daemon(tmp_path: Path) -> None:
    from rhenium_stardew_valley.evaluator import _DOCKER_TIMEOUT

    catalog = StardewCatalog.load(PACK)
    task = next(task for task in catalog.tasks if task.id == REPAIR_TASK)
    timeouts: dict[str, float] = {}

    class TimedRuntime(RecordingRuntime):
        def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
            timeouts.setdefault(arguments[0], timeout)
            return super()._docker(arguments, timeout=timeout)

    runtime = TimedRuntime(_context(tmp_path), catalog)
    runtime.docker = "docker"
    (tmp_path / "logs").mkdir()
    runtime.status()
    runtime.run(task, tmp_path / "submission", tmp_path / "logs")

    assert _DOCKER_TIMEOUT >= 300
    for command in ("info", "create", "cp", "rm"):
        assert timeouts[command] == _DOCKER_TIMEOUT, command
    # The game run itself keeps the task's own, longer budget.
    assert timeouts["start"] > _DOCKER_TIMEOUT


def test_submission_sync_preserves_offline_restore_state(tmp_path: Path) -> None:
    rsync = shutil.which("rsync")
    if rsync is None:
        pytest.skip("rsync is unavailable")
    image_tree = tmp_path / "app/StardewMods/Automate"
    (image_tree / "obj").mkdir(parents=True)
    (image_tree / "obj/project.assets.json").write_text("{}", encoding="utf-8")
    (image_tree / "bin/Release").mkdir(parents=True)
    (image_tree / "bin/Release/Automate.dll").write_text("image build", encoding="utf-8")
    (image_tree / "Stale.cs").write_text("// removed by the submission", encoding="utf-8")
    submitted = tmp_path / "submission/StardewMods/Automate"
    submitted.mkdir(parents=True)
    (submitted / "ModEntry.cs").write_text("// submitted", encoding="utf-8")
    (submitted / "bin").mkdir()
    (submitted / "bin/Injected.dll").write_text("submitted binary", encoding="utf-8")

    subprocess.run(
        [
            rsync,
            *SUBMISSION_SYNC_OPTIONS,
            f"{tmp_path / 'submission/StardewMods'}/",
            f"{tmp_path / 'app/StardewMods'}/",
        ],
        check=True,
    )

    assert (image_tree / "obj/project.assets.json").is_file()
    assert (image_tree / "bin/Release/Automate.dll").read_text(encoding="utf-8") == "image build"
    assert not (image_tree / "bin/Injected.dll").exists()
    assert not (image_tree / "Stale.cs").exists()
    assert (image_tree / "ModEntry.cs").read_text(encoding="utf-8") == "// submitted"


@pytest.mark.parametrize(
    ("task_id", "clean_room_synthetic", "starter"),
    [
        ("stardew-automate-minifridge-storage", False, ("StardewMods", "/app/StardewMods")),
        # Generation tasks start from a standalone mod project below mod/.
        (GENERATION_TASK, False, ("mod", "/app/mod")),
        # Clean-room synthetic packs ship a standalone mod project below mod/ as well.
        ("stardew-cp-release-regressions", True, ("mod", "/app/mod")),
    ],
)
def test_runtime_command_syncs_submissions_with_restore_state_exclusions(
    tmp_path: Path, task_id: str, clean_room_synthetic: bool, starter: tuple[str, str]
) -> None:
    catalog = StardewCatalog.load(PACK)
    task = next(task for task in catalog.tasks if task.id == task_id)
    if clean_room_synthetic:
        task = task.model_copy(update={"clean_room_synthetic": True})
    assert (task.starter_name, task.container_destination) == starter
    runtime = RecordingRuntime(_context(tmp_path), catalog)
    submission = tmp_path / "submission"
    logs = tmp_path / "logs"
    submission.mkdir()
    logs.mkdir()

    runtime.run(task, submission, logs)

    script = runtime.arguments[-1]
    expected = (
        f"rsync {' '.join(SUBMISSION_SYNC_OPTIONS)} "
        f"/submission/{task.starter_name}/ {task.container_destination}/;"
    )
    assert expected in script


def test_generated_log_names_are_preserved_without_following_symlinks(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    (logs / "verifier").mkdir(parents=True)
    (logs / "verifier/harness-build.log").write_text("error CS1503: invalid generated API usage")
    secret = tmp_path / "secret"
    secret.write_text("must-not-read")
    (logs / "verifier/leak.log").symlink_to(secret)
    result = StardewEvaluator._read_runtime_log(logs, subprocess.CompletedProcess([], 1, "", ""))
    assert "CS1503" in result
    assert "must-not-read" not in result


@pytest.mark.parametrize("failure", ["start", "cp", "rm"])
def test_runtime_failure_still_removes_only_owned_container(tmp_path: Path, failure: str) -> None:
    catalog = StardewCatalog.load(PACK)
    calls: list[list[str]] = []

    class FailingRuntime(RecordingRuntime):
        def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
            calls.append(arguments)
            if arguments[0] == failure:
                if failure == "start":
                    raise subprocess.TimeoutExpired("docker start", timeout)
                return subprocess.CompletedProcess(arguments, 1, "", "failure")
            return super()._docker(arguments, timeout=timeout)

    runtime = FailingRuntime(_context(tmp_path), catalog)
    with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        runtime.run(catalog.tasks[0], tmp_path / "submission", tmp_path / "logs")
    assert calls[-1] == ["rm", "--force", "a" * 64]


def test_runtime_rejects_invalid_container_identity_before_cleanup(tmp_path: Path) -> None:
    catalog = StardewCatalog.load(PACK)
    calls: list[list[str]] = []

    class InvalidRuntime(RecordingRuntime):
        def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
            calls.append(arguments)
            return subprocess.CompletedProcess(arguments, 0, "untrusted-container-name", "")

    with pytest.raises(RuntimeError, match="could not create"):
        InvalidRuntime(_context(tmp_path), catalog).run(
            catalog.tasks[0], tmp_path / "submission", tmp_path / "logs",
        )
    assert len(calls) == 1 and calls[0][0] == "create"


@pytest.mark.parametrize("link", ["verifier", "verifier/smapi.log"])
def test_runtime_never_copies_smapi_log_through_untrusted_symlink(tmp_path: Path, link: str) -> None:
    catalog = StardewCatalog.load(PACK)
    logs = tmp_path / "logs"
    logs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    calls: list[list[str]] = []

    class SymlinkRuntime(RecordingRuntime):
        def _docker(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
            calls.append(arguments)
            if arguments[:2] == ["cp", "a" * 64 + ":/logs/."]:
                target = logs / link
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside)
            return super()._docker(arguments, timeout=timeout)

    with pytest.raises(RuntimeError, match="symbolic link"):
        SymlinkRuntime(_context(tmp_path), catalog).run(catalog.tasks[0], tmp_path / "submission", logs)
    assert sum(args[0] == "cp" for args in calls) == 1
    assert calls[-1] == ["rm", "--force", "a" * 64]
    assert list(outside.iterdir()) == []


def test_wait_predicate_exception_fails_the_case_in_every_harness_copy() -> None:
    harbor = Path(__file__).parents[3] / "benchmarks/stardew-core/private/harbor"
    canonical = harbor / "harness/GcbHarness/Framework/SuiteRunner.cs"
    source = canonical.read_text(encoding="utf-8")
    copies = sorted(harbor.rglob("SuiteRunner.cs"))
    assert len(copies) > 1
    for copy in copies:
        assert copy.read_bytes() == canonical.read_bytes(), copy

    # The guard fails the case only when the predicate helper reports "not
    # satisfied"; an exception must therefore never be reported as satisfied.
    assert "case GcbWait.WaitUntil wu when !SafePredicate(wu, out string? predError):" in source
    assert "this.FinishCase(passed: false, error: predError);" in source
    catch_block = source[source.index("wait-until predicate threw") :]
    catch_block = catch_block[: catch_block.index("private bool StartNextCase")]
    assert "return false;" in catch_block and "return true" not in catch_block


def test_image_reuse_and_verify_are_bound_to_the_task_build_inputs(tmp_path: Path) -> None:
    from rhenium_stardew_valley.evaluator import BUILD_CONTEXT_LABEL, StardewRuntime
    from rhenium_stardew_valley.runtime_builder import StardewRuntimeBuilder

    from rhenium.core.runtime import RuntimeArtifact

    catalog = StardewCatalog.load(PACK)
    context = _context(tmp_path)
    runtime = StardewRuntime(context, catalog)
    task = catalog.tasks[0]
    current = runtime.build_context_digest(task)
    assert current.startswith("sha256:") and current == runtime.build_context_digest(task)
    labels = {"stale": "sha256:" + "0" * 64, "fresh": current}
    state = {"label": "stale"}

    def docker(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        assert arguments[:2] == ["image", "inspect"]
        if BUILD_CONTEXT_LABEL in arguments[-1]:
            return subprocess.CompletedProcess(arguments, 0, labels[state["label"]] + "\n", "")
        return subprocess.CompletedProcess(arguments, 0, arguments[2] + "\n", "")

    runtime._docker = docker  # type: ignore[method-assign]
    assert runtime.image_exists(task) is False, "a stale image under the same tag must be rebuilt"
    state["label"] = "fresh"
    assert runtime.image_exists(task) is True

    builder = StardewRuntimeBuilder(context, catalog)
    builder.runtime._docker = docker  # type: ignore[method-assign]
    images = {item.id: "sha256:" + f"{index:064x}" for index, item in enumerate(catalog.tasks)}
    artifact = RuntimeArtifact(runtime_key="stardew-valley/x", fingerprint="f", kind="docker-images",
                               identity="i", metadata={"images": images})
    spec: Any = None
    # every task shares the fake label, so only a task whose own digest equals it verifies
    verdict = builder.verify(spec, artifact)
    assert verdict["available"] is False and "different task inputs" in verdict["reason"]
