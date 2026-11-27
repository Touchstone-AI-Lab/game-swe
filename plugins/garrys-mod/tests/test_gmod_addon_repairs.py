from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog, GarrysModTask, expected_case_count
from rhenium_garrys_mod.darkrp.evaluator import GarrysModEvaluator, GarrysModRuntime
from rhenium_garrys_mod.plugin import GarrysModBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "gmod-addon-repairs"
DARKRP = ROOT / "benchmarks" / "darkrp-core"
HARBOR = PACK / "private" / "harbor"
TASK_IDS = {
    "advdupe2-paste-regressions",
    "cfw-contraption-regressions",
    "starfallex-library-regressions",
    "wiremod-e2-library-regressions",
    "wiremod-gates-chips-regressions",
}
_CASE = re.compile(r'^[ \t]*\{(?:\s|--[^\n]*)*name\s*=\s*"((?:[^"\\]|\\.)*)"', re.M)
_GROUP = re.compile(r"^([A-Z]{1,2}):")
_ROLE_PREFIXES = ("sentinel:", "preserved:")


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def _task(task_id: str) -> GarrysModTask:
    return next(task for task in GarrysModCatalog.load(PACK).tasks if task.id == task_id)


def test_catalog_exposes_the_validated_addon_repair_tasks() -> None:
    catalog = GarrysModCatalog.load(PACK)

    assert catalog.id == "gmod-addon-repairs"
    assert catalog.game == "garrys-mod"
    assert {task.id for task in catalog.tasks} == TASK_IDS
    for task in catalog.tasks:
        assert task.task_kind == "debugging"
        assert task.source_kind == "addon"
        assert task.clean_room_synthetic is False
        assert task.starter_directory is not None
        assert task.container_destination == f"/app/{task.starter_name}"
        assert all(path.startswith(f"{task.starter_name}/") for path in task.required_files)
        assert expected_case_count(PACK, task) >= 6


def test_runtime_catalog_binds_every_task_to_the_addon_runtime_only() -> None:
    runtimes = json.loads((PACK / "runtimes.json").read_text(encoding="utf-8"))
    darkrp = json.loads((DARKRP / "runtimes.json").read_text(encoding="utf-8"))

    assert [spec["id"] for spec in runtimes["runtimes"]] == ["gmod-gluatest-addons"]
    assert runtimes["runtimes"][0]["source"] == darkrp["runtimes"][0]["source"]
    assert runtimes["task_bindings"] == {
        task_id: ["gmod-gluatest-addons"] for task_id in sorted(TASK_IDS)
    }


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_task_package_keeps_upstream_provenance_and_licence(task_id: str) -> None:
    task = _task(task_id)
    root = HARBOR / task_id
    config = tomllib.loads((root / "task.toml").read_text(encoding="utf-8"))
    metadata = config["metadata"]

    assert metadata["source_repo"].startswith("https://github.com/")
    assert metadata["base_commit"] == task.source_commit
    assert re.fullmatch(r"[0-9a-f]{40}", metadata["base_commit"])
    assert metadata["reverted_fixes"]
    assert metadata["gold_patch_origin"] == "composed-from-upstream-fixes"
    assert config["verifier"]["network_mode"] == "no-network"
    assert config["environment"]["network_mode"] == "no-network"
    starter = root / "environment" / task.starter_name
    licences = [path for path in starter.iterdir() if path.name.upper().startswith("LICENSE")]
    assert licences, f"{task_id}: the vendored tree lost its upstream licence"
    exam = PACK / "exams" / f"{task_id}.md"
    assert exam.read_bytes() == (root / "instruction.md").read_bytes()


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_starter_and_reference_pass_the_static_preflight(task_id: str, tmp_path: Path) -> None:
    """The reference is the starter with solution/after copied over it; both must pass
    the harness scan against the shipped starter, or a correct repair scores zero."""
    task = _task(task_id)
    root = HARBOR / task_id
    baseline = root / "environment" / task.starter_name
    reference = tmp_path / "reference"
    shutil.copytree(baseline, reference / task.starter_name)
    shutil.copytree(root / "solution" / "after", reference / task.starter_name, dirs_exist_ok=True)
    starter = tmp_path / "starter"
    shutil.copytree(baseline, starter / task.starter_name)
    for submission in (starter, reference):
        safe, check = GarrysModEvaluator._static_check(submission, task, baseline)
        assert safe, (submission.name, check)


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_starter_and_reference_carry_no_collectable_tests_or_harness_names(
    task_id: str,
) -> None:
    task = _task(task_id)
    root = HARBOR / task_id
    starter = root / "environment" / task.starter_name
    reference = root / "solution" / "after"
    for tree in (starter, reference):
        lua = tree / "lua"
        assert not (lua / "tests").exists(), f"{tree}: GLuaTest would collect lua/tests"
        assert not (lua / "gluatest").exists()
        assert not any(path.is_symlink() for path in tree.rglob("*"))
        assert not any(
            path.suffix.lower() in {".dll", ".so", ".dylib"} for path in tree.rglob("*")
        )
    assert not GarrysModEvaluator._contains_harness_tampering(starter, starter)
    dockerfile = (root / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.rstrip().endswith(
        f"COPY {task.starter_name} {task.container_destination}"
    )
    assert "FROM ghcr.io/cfc-servers/gluatest/x86-64@sha256:" in dockerfile
    solve = (root / "solution" / "solve.sh").read_text(encoding="utf-8")
    assert f"/solution/after/. {task.container_destination}/" in solve


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_reference_overlay_reproduces_the_gold_patch_files(task_id: str) -> None:
    task = _task(task_id)
    root = HARBOR / task_id
    starter = root / "environment" / task.starter_name
    reference = root / "solution" / "after"
    patch = (root / "solution" / "gold.patch").read_text(encoding="utf-8")
    patched = set(re.findall(r"^\+\+\+ b/(\S+)", patch, re.M))
    removed = set(re.findall(r"^--- a/(\S+)\n\+\+\+ /dev/null", patch, re.M))
    overlay = {
        path.relative_to(reference).as_posix() for path in reference.rglob("*") if path.is_file()
    }
    assert patched - {"/dev/null"} == overlay
    changed = {
        relative
        for relative in overlay
        if not (starter / relative).is_file()
        or (starter / relative).read_bytes() != (reference / relative).read_bytes()
    }
    assert changed == overlay, f"{task_id}: the reference overlay carries unchanged files"
    assert not removed, f"{task_id}: an overlay cannot express a file deletion"


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_verifier_case_list_matches_its_suite_exactly(task_id: str) -> None:
    tests = HARBOR / task_id / "tests"
    verifier = (tests / "test.sh").read_text(encoding="utf-8")
    suite = (tests / "suite.lua").read_text(encoding="utf-8")
    block = re.search(r"EXPECTED_CASES=\((.*?)\n\)", verifier, re.S)
    assert block is not None
    listed = re.findall(r'^\s*"(.*)"\s*$', block.group(1), re.M)
    declared = re.findall(r"^EXPECTED=([0-9]+)$", verifier, re.M)
    names = _CASE.findall(suite)

    assert listed == names
    assert declared == [str(len(names))]
    assert f"ADDON={_task(task_id).starter_name}" in verifier
    assert "GAMEMODE=sandbox" in verifier
    assert "TIMEOUT=2" in verifier
    sentinels = [name for name in names if name.startswith("sentinel:")]
    preserved = [name for name in names if name.startswith("preserved:")]
    targets = [name for name in names if _GROUP.match(name)]
    assert len(sentinels) == 1
    assert len(preserved) >= 2
    assert len(sentinels) + len(preserved) + len(targets) == len(names)


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_every_graded_group_is_publicly_reported(task_id: str) -> None:
    root = HARBOR / task_id
    instruction = (root / "instruction.md").read_text(encoding="utf-8")
    suite = (root / "tests" / "suite.lua").read_text(encoding="utf-8")
    reports = re.findall(r"^> \*\*\[([A-Z]{1,2})\]\*\*", instruction, re.M)
    groups = {match.group(1) for name in _CASE.findall(suite) if (match := _GROUP.match(name))}

    assert reports, f"{task_id}: the exam carries no lettered reports"
    assert len(reports) == len(set(reports))
    assert set(reports) == groups


@pytest.mark.parametrize("task_id", sorted(TASK_IDS))
def test_exam_never_leaks_fix_provenance_or_the_defect_count(task_id: str) -> None:
    exam = (PACK / "exams" / f"{task_id}.md").read_text(encoding="utf-8")
    config = tomllib.loads((HARBOR / task_id / "task.toml").read_text(encoding="utf-8"))
    lowered = exam.lower()
    for fix in config["metadata"]["reverted_fixes"].split(","):
        assert fix.strip()[:7] not in lowered
    assert "defect group" not in lowered
    assert "root cause" not in lowered
    assert "gold.patch" not in lowered
    assert "/tests" in exam
    assert f"/app/{_task(task_id).starter_name}" in exam


def test_every_verifier_shares_the_darkrp_private_runner_collector() -> None:
    reference = (
        DARKRP / "private" / "harbor" / "darkrp-money-regressions" / "tests" / "trusted_collector.py"
    ).read_bytes()
    for task_id in TASK_IDS:
        collector = (HARBOR / task_id / "tests" / "trusted_collector.py").read_bytes()
        assert hashlib.sha256(collector).digest() == hashlib.sha256(reference).digest()
        verifier = (HARBOR / task_id / "tests" / "test.sh").read_text(encoding="utf-8")
        assert "trusted_collector.py patch" in verifier


def test_materialized_attempt_carries_the_addon_but_no_private_assets(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    catalog = plugin.load_catalog(PACK, "catalog.json")
    for task in catalog.tasks:
        assert isinstance(task, GarrysModTask)
        destination = tmp_path / task.id
        destination.mkdir()
        plugin.materialize_attempt(task, destination, _context(tmp_path))

        assert (destination / task.starter_name / "lua").is_dir()
        exam = (destination / "EXAM.md").read_text(encoding="utf-8")
        assert f"/app/{task.starter_name}" not in exam
        assert f"`{task.starter_name}`" in exam
        assert not (destination / "tests").exists()
        assert not (destination / "solution").exists()
        assert "addon repair benchmark" in plugin.agent_system_prompt(task)
        public = plugin.public_task(task)
        assert public["sourceCommit"] == task.source_commit
        assert public["fromScratch"] is False


def test_static_check_accepts_the_starter_and_rejects_harness_shadowing(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    task = GarrysModCatalog.load(PACK).tasks[0]
    submission = tmp_path / "submission"
    plugin.materialize_starter(task, submission, _context(tmp_path))
    baseline = HARBOR / task.id / "environment" / task.starter_name

    safe, check = GarrysModEvaluator._static_check(submission, task, baseline)
    assert safe, check
    assert check["message"] == "submission contains the required GLua addon tree"

    for reserved in ("tests/extra", "gluatest/runner", "GLuaTest/extensions"):
        shadow = submission / task.starter_name / "lua" / reserved
        shadow.mkdir(parents=True)
        (shadow / "x.lua").write_text("return {}\n", encoding="utf-8")
        safe, check = GarrysModEvaluator._static_check(submission, task, baseline)
        assert not safe
        assert check["message"] == "submission attempts to alter the private result harness"
        top = submission / task.starter_name / "lua" / reserved.split("/")[0]
        for path in sorted(top.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        top.rmdir()

    autorun = submission / task.starter_name / "lua" / "autorun" / "server"
    autorun.mkdir(parents=True, exist_ok=True)
    forged = autorun / "zz_forge.lua"
    forged.write_text(
        'hook.Add("GLuaTest_LogTestResult", "forge", function(r) r.success = true end)\n',
        encoding="utf-8",
    )
    safe, check = GarrysModEvaluator._static_check(submission, task, baseline)
    assert not safe
    forged.write_text("done = function() end\n", encoding="utf-8")
    safe, _check = GarrysModEvaluator._static_check(submission, task, baseline)
    assert not safe
    forged.unlink()
    (submission / task.starter_name / "lua").rename(submission / task.starter_name / "code")
    safe, check = GarrysModEvaluator._static_check(submission, task, baseline)
    assert not safe
    assert check["message"] == "submission is missing the addon tree or contains symbolic links"


def test_tamper_scan_exempts_only_verbatim_upstream_lines(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline" / "addon"
    submission = tmp_path / "submission" / "addon"
    for tree in (baseline, submission):
        (tree / "lua").mkdir(parents=True)
    upstream = "local function walk(t, done)\n\tdone = done or {}\n\treturn done\nend\n"
    (baseline / "lua" / "debug.lua").write_text(upstream, encoding="utf-8")
    (submission / "lua" / "debug.lua").write_text(upstream, encoding="utf-8")
    scan = GarrysModEvaluator._contains_harness_tampering

    assert scan(submission, None)
    assert not scan(submission, baseline)
    (submission / "lua" / "debug.lua").write_text(
        upstream + "done = function() end\n", encoding="utf-8"
    )
    assert scan(submission, baseline)
    (submission / "lua" / "debug.lua").write_text(upstream, encoding="utf-8")
    (submission / "lua" / "other.lua").write_text("\tdone = done or {}\n", encoding="utf-8")
    assert scan(submission, baseline), "an upstream line only exempts its own file"


def test_addon_tasks_use_their_own_runtime_key_and_destination(tmp_path: Path) -> None:
    catalog = GarrysModCatalog.load(PACK)
    task = catalog.tasks[0]
    evaluator = GarrysModEvaluator(_context(tmp_path), catalog)
    evaluator.runtime.status = lambda: {"available": True}  # type: ignore[method-assign]
    submission = tmp_path / "submission"
    GarrysModBenchmarkPlugin().materialize_starter(task, submission, _context(tmp_path))

    darkrp_only = RuntimeArtifact(
        runtime_key="garrys-mod/gmod-gluatest-darkrp",
        fingerprint="f",
        kind="docker-images",
        identity="sha256:x",
        metadata={"images": {task.id: "sha256:deadbeef"}},
    )
    result = evaluator.evaluate(
        submission, task, runtimes={"garrys-mod/gmod-gluatest-darkrp": darkrp_only}
    )
    assert result["complete"] is False
    assert "garrys-mod/gmod-gluatest-addons" in result["runtime_log"]

    recorded: list[list[str]] = []

    def capture(arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        recorded.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    runtime = GarrysModRuntime(_context(tmp_path), catalog)
    runtime._docker = capture  # type: ignore[method-assign]
    logs = tmp_path / "logs"
    logs.mkdir()
    runtime.run(task, submission, logs, "sha256:deadbeef")
    command = recorded[0][-1]
    assert (
        f"rsync -rlptD --delete /submission/{task.starter_name}/ /app/{task.starter_name}/"
        in command
    )
    assert "--network=none" in recorded[0]


def test_addon_task_model_requires_a_named_tree() -> None:
    task = GarrysModCatalog.load(PACK).tasks[0]
    data = task.model_dump()
    with pytest.raises(ValueError, match="must name its starter directory"):
        GarrysModTask.model_validate({**data, "starter_directory": None})
    with pytest.raises(ValueError, match="clean-room"):
        GarrysModTask.model_validate({**data, "clean_room_synthetic": True})
    with pytest.raises(ValueError, match="only addon tasks"):
        GarrysModTask.model_validate({**data, "source_kind": "gamemode"})
