from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_isaac_rebirth.catalog import IsaacCatalog, IsaacTask, expected_case_names
from rhenium_isaac_rebirth.evaluator import IsaacEvaluator, IsaacRuntime
from rhenium_isaac_rebirth.plugin import IsaacRebirthBenchmarkPlugin

from rhenium.core.plugin import BenchmarkContext

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "isaac-core"
SYNTH_PACK = ROOT / "benchmarks" / "isaac-synth"


def _context(tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


BASELINE = "isaac-exodus-release-regressions"
SHARED_VERIFIER = PACK / "private/verifiers/exodus-v2"
SUPPLEMENTARY = PACK / "private/supplementary-regressions"
COMPOSITE_REFERENCE_SHA256 = "ee5753ae7da0c9308f5e76c43674553d06c7200b7a3e891e66e7bd95ae1d93c6"


def _patch_hunks(patch: str) -> list[list[tuple[str, str]]]:
    """Every hunk of a unified diff as (kind, line) pairs, kind being " ", "-" or "+"."""
    hunks: list[list[tuple[str, str]]] = []
    for line in patch.splitlines(keepends=True):
        if line.startswith("@@"):
            hunks.append([])
        elif not hunks or line.startswith(("---", "+++", "diff ", "index ")):
            continue
        elif line[:1] in ("-", "+", " "):
            hunks[-1].append((line[:1], line[1:]))
        else:
            hunks[-1].append((" ", line))
    return hunks


def _sides(hunk: list[tuple[str, str]], margin: int | None = None) -> tuple[str, str]:
    """(before, after) text of a hunk, keeping at most ``margin`` context lines on each side."""
    if margin is not None:
        changed = [index for index, (kind, _) in enumerate(hunk) if kind != " "]
        hunk = hunk[max(changed[0] - margin, 0) : changed[-1] + margin + 1]
    before = "".join(line for kind, line in hunk if kind != "+")
    after = "".join(line for kind, line in hunk if kind != "-")
    return before, after


def _apply(text: str, patch: str, reverse: bool = False) -> str:
    for hunk in _patch_hunks(patch):
        before, after = _sides(hunk)
        old, new = (after, before) if reverse else (before, after)
        assert text.count(old) == 1, "patch hunk has no unique exact location"
        text = text.replace(old, new)
    return text


def _supplementary_reports() -> dict[str, str]:
    text = (SUPPLEMENTARY / "reports.md").read_text(encoding="utf-8")
    return {
        block[len("> **[#") : block.index("]")]: block.strip("\n")
        for block in text.split("\n\n")
        if block.startswith("> **[#EX-")
    }


def test_catalog_exposes_the_baseline_and_derived_exodus_tasks() -> None:
    catalog = IsaacCatalog.load(PACK)

    assert catalog.game == "isaac-rebirth"
    assert catalog.version == "5.0.0"
    assert len(catalog.tasks) == 10
    ids = [task.id for task in catalog.tasks]
    assert ids[0] == BASELINE
    assert len(set(ids)) == len(ids)
    for task in catalog.tasks:
        assert task.id.startswith("isaac-exodus-")
        assert task.source_mod == "Exodus"
        assert not task.clean_room_synthetic
        assert task.difficulty in {"easy", "medium", "hard"}
        assert len(expected_case_names(PACK, task)) == task.expected_cases
        assert task.authored_prompt.startswith("# Exodus: bug reports")
    assert catalog.tasks[0].difficulty == "hard"
    assert catalog.tasks[0].expected_cases == 35 and catalog.tasks[0].verifier is None
    for task in catalog.tasks[1:]:
        assert task.verifier == "exodus-v2"
        assert task.expected_cases == 54


def test_derived_starters_are_the_fixed_tree_with_reverted_and_supplementary_regressions() -> None:
    """Derived starters differ from the baseline's broken tree only in main.lua and share every
    other file byte for byte. Their exams quote the baseline exam and the supplementary reports
    verbatim; the starter carries exactly the supplementary regressions its exam reports, and
    starter plus gold.patch is the composite reference tree."""
    catalog = IsaacCatalog.load(PACK)
    baseline_root = PACK / "private/harbor" / BASELINE / "environment/exodus"
    baseline_exam = (PACK / "exams" / f"{BASELINE}.md").read_text(encoding="utf-8")
    first = PACK / "private/harbor" / catalog.tasks[1].id
    reference = _apply(
        (first / "environment/exodus/main.lua").read_text(encoding="utf-8"),
        (first / "solution/gold.patch").read_text(encoding="utf-8"),
    )
    # The composite reference tree: the baseline starter plus its gold.patch (applied there with
    # --ignore-whitespace), recorded by digest because that patch does not apply byte-exactly.
    assert hashlib.sha256(reference.encode("utf-8")).hexdigest() == COMPOSITE_REFERENCE_SHA256
    supplementary = _supplementary_reports()
    assert supplementary, "the supplementary report pool is empty"
    for report in supplementary:
        # Every supplementary patch applies to the reference tree and reverses cleanly.
        patch = (SUPPLEMENTARY / f"{report}.patch").read_text(encoding="utf-8")
        assert _apply(_apply(reference, patch), patch, reverse=True) == reference
    for task in catalog.tasks[1:]:
        root = PACK / "private/harbor" / task.id / "environment/exodus"
        for path in baseline_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(baseline_root)
            assert (root / relative).is_file(), f"{task.id} is missing {relative}"
            if relative.as_posix() != "main.lua":
                assert (root / relative).read_bytes() == path.read_bytes(), f"{task.id} altered {relative}"
        starter = (root / "main.lua").read_text(encoding="utf-8")
        assert starter != (baseline_root / "main.lua").read_text(encoding="utf-8")
        gold_patch = (PACK / "private/harbor" / task.id / "solution/gold.patch").read_text(encoding="utf-8")
        assert _apply(starter, gold_patch) == reference, f"{task.id} gold.patch does not reach the reference"
        blocks = [block for block in task.authored_prompt.split("\n\n") if block.startswith("> **[#EX-")]
        reported = {block[len("> **[#") : block.index("]")] for block in blocks}
        added = reported & set(supplementary)
        assert 0 < len(reported - added) < 20, f"{task.id} exam should be a strict subset of the reports"
        for block in blocks:
            assert block in baseline_exam or block in supplementary.values(), (
                f"{task.id} exam block is not verbatim from the baseline exam or the supplementary reports"
            )
        for report in supplementary:
            # One line of context around each changed block tells the regressed and the
            # repaired text apart even where a nearby reverted report changed wider context.
            sides = [_sides(hunk, margin=1) for hunk in _patch_hunks(
                (SUPPLEMENTARY / f"{report}.patch").read_text(encoding="utf-8"))]
            regressed = all(after in starter for _, after in sides)
            repaired = all(before in starter for before, _ in sides)
            assert regressed != repaired, f"{task.id} starter is ambiguous about {report}"
            assert regressed == (report in added), f"{task.id} starter and exam disagree on {report}"
        assert task.id not in task.authored_prompt
        # Every derived task ships measured real-game controls next to its predictions: the
        # base fails exactly the predicted cases with reward 0, the gold passes every case.
        controls = PACK / "private/harbor" / task.id / "validation/controls.tsv"
        rows = [line.split("\t") for line in controls.read_text(encoding="utf-8").splitlines()]
        header, measured = rows[0], {row[0]: row for row in rows[1:] if row[1] == "measured"}
        assert header[:3] == ["control", "status", "failing_cases"]
        assert set(measured) == {"base", "gold"}, f"{task.id} lacks measured controls"
        base, gold = measured["base"], measured["gold"]
        total = str(task.expected_cases)
        # columns: failing_cases, passed, failed, reward, processes, fatals, matches_prediction
        assert base[2] != "-" and int(base[3]) + int(base[4]) == task.expected_cases, f"{task.id} base cases"
        assert base[5:] == ["0", "3/3", "0", "yes"], f"{task.id} base control"
        assert gold[2:] == ["-", total, "0", "1", "3/3", "0", "yes"], f"{task.id} gold control"


def _core_catalog_json(mutate: Any) -> str:
    import json

    data = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    mutate(data)
    return json.dumps(data)


def test_core_catalog_rejects_a_missing_baseline() -> None:
    def drop_baseline(data: Any) -> None:
        data["tasks"] = [task for task in data["tasks"] if task["id"] != BASELINE]

    with pytest.raises(ValueError, match="baseline"):
        IsaacCatalog.model_validate_json(_core_catalog_json(drop_baseline))


def test_core_catalog_rejects_duplicate_task_ids() -> None:
    def duplicate(data: Any) -> None:
        data["tasks"].append(dict(data["tasks"][1]))

    with pytest.raises(ValueError, match="unique"):
        IsaacCatalog.model_validate_json(_core_catalog_json(duplicate))


def test_core_catalog_rejects_synthetic_foreign_or_unknown_difficulty_tasks() -> None:
    def synthetic(data: Any) -> None:
        data["tasks"][1]["clean_room_synthetic"] = True
        data["tasks"][1]["source_mod"] = "Clean-room synthetic"
        data["tasks"][1]["required_files"] = ["mod/main.lua", "mod/metadata.xml"]
        data["tasks"][1].pop("verifier", None)

    with pytest.raises(ValueError, match="real-game Exodus"):
        IsaacCatalog.model_validate_json(_core_catalog_json(synthetic))

    def foreign_id(data: Any) -> None:
        data["tasks"][1]["id"] = "isaac-other-mod-task"

    with pytest.raises(ValueError, match="derive from the validated Exodus tree"):
        IsaacCatalog.model_validate_json(_core_catalog_json(foreign_id))

    def bad_difficulty(data: Any) -> None:
        data["tasks"][1]["difficulty"] = "brutal"

    with pytest.raises(ValueError, match="easy, medium, or hard"):
        IsaacCatalog.model_validate_json(_core_catalog_json(bad_difficulty))


def test_catalog_requires_deterministic_mod_data(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    task_root = pack / "private/harbor/isaac-exodus-release-regressions"
    (task_root / "environment").mkdir(parents=True)
    (pack / "exams").mkdir(parents=True)
    (pack / "catalog.json").write_bytes((PACK / "catalog.json").read_bytes())
    (pack / "exams/isaac-exodus-release-regressions.md").write_bytes(
        (PACK / "exams/isaac-exodus-release-regressions.md").read_bytes()
    )
    for relative in ("environment/exodus", "tests", "scripts"):
        source = task_root / relative
        source.mkdir(parents=True, exist_ok=True)
    (task_root / "environment/exodus/main.lua").touch()
    (task_root / "environment/exodus/metadata.xml").touch()
    (task_root / "tests/test.sh").write_text(
        (PACK / "private/harbor/isaac-exodus-release-regressions/tests/test.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (task_root / "scripts/private-runtime.Dockerfile").touch()
    (task_root / "environment/exodus/save1.dat").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="save2.dat"):
        IsaacCatalog.load(pack)


def test_materialized_attempt_contains_source_but_no_private_assets(tmp_path: Path) -> None:
    plugin = IsaacRebirthBenchmarkPlugin()
    catalog = plugin.load_catalog(PACK, "catalog.json")
    task = catalog.tasks[0]
    destination = tmp_path / "attempt"

    plugin.materialize_attempt(task, destination, _context(tmp_path))

    assert (destination / "exodus/main.lua").is_file()
    assert (destination / "exodus/metadata.xml").is_file()
    assert (destination / "EXAM.md").is_file()
    assert (destination / "AGENTS.md").is_file()
    assert (destination / "exodus/save1.dat").read_text(encoding="utf-8").strip() == "[]"
    assert (destination / "exodus/save2.dat").read_text(encoding="utf-8").strip() == '{"Register":[]}'
    assert not (destination / "tests").exists()
    assert not (destination / "solution").exists()
    assert not (destination / "validation").exists()
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert str(PACK) not in public_text
    assert task.id not in public_text
    assert "/app/exodus" not in public_text


def test_core_profile_is_incomplete_without_invoking_docker(tmp_path: Path) -> None:
    catalog = IsaacCatalog.load(PACK)
    task = catalog.tasks[0]
    plugin = IsaacRebirthBenchmarkPlugin()
    submission = tmp_path / "submission"
    plugin.materialize_starter(task, submission, _context(tmp_path))
    evaluator = IsaacEvaluator(_context(tmp_path), catalog)

    result = evaluator.evaluate(submission, task, profile="core")

    assert result["score"] == 10.0
    assert result["complete"] is False
    assert result["passed"] is False
    assert result["checks"][1]["status"] == "skipped"


def test_full_profile_fails_closed_when_runtime_is_unavailable(tmp_path: Path, monkeypatch: Any) -> None:
    catalog = IsaacCatalog.load(PACK)
    task = catalog.tasks[0]
    plugin = IsaacRebirthBenchmarkPlugin()
    submission = tmp_path / "submission"
    plugin.materialize_starter(task, submission, _context(tmp_path))
    evaluator = IsaacEvaluator(_context(tmp_path), catalog)
    evaluator.runtime.docker = str(tmp_path / "missing-docker")

    result = evaluator.evaluate(submission, task, profile="full")

    assert result["complete"] is False
    assert result["passed"] is False
    assert result["runtime"]["status"] == "unavailable"


class RecordingRuntime(IsaacRuntime):
    def __init__(self, context: BenchmarkContext):
        super().__init__(context)
        self.calls: list[list[str]] = []

    def image_id(self) -> str:
        return "sha256:test-image"

    def _docker(
        self,
        arguments: list[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        del timeout
        self.calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, "", "")


def test_runtime_container_is_networkless_and_receives_no_model_secret(tmp_path: Path) -> None:
    runtime = RecordingRuntime(_context(tmp_path))
    submission = tmp_path / "submission"
    logs = tmp_path / "logs"
    (submission / "exodus").mkdir(parents=True)

    runtime.run(submission, logs)

    command = " ".join(runtime.calls[0])
    assert runtime.calls[0][runtime.calls[0].index("--network") + 1] == "none"
    assert runtime.calls[0][runtime.calls[0].index("--pull") + 1] == "never"
    assert "apparmor=gcb-isaac-steam" in runtime.calls[0]
    assert "seccomp=unconfined" in runtime.calls[0]
    assert "dst=/app/exodus,readonly" in command
    assert "sha256:test-image" in runtime.calls[0]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in command
    assert "ANTHROPIC_API_KEY" not in command


def test_only_derived_tasks_mount_their_launch_harness(tmp_path: Path) -> None:
    catalog = IsaacCatalog.load(PACK)
    evaluator = IsaacEvaluator(_context(tmp_path), catalog)
    baseline, derived = catalog.tasks[0], catalog.tasks[1:]

    # The frozen task keeps the run-game.sh baked into the image it was admitted with.
    assert baseline.id == BASELINE
    assert evaluator.harness(baseline) is None
    for task in derived:
        harness = evaluator.harness(task)
        assert harness == (PACK / "private/harbor" / task.id / "tests/run-game.sh").resolve()

    runtime = RecordingRuntime(_context(tmp_path))
    submission = tmp_path / "submission"
    (submission / "exodus").mkdir(parents=True)
    harness = evaluator.harness(derived[0])
    assert harness is not None
    runtime.run(submission, tmp_path / "logs", harness=harness)
    runtime.run(submission, tmp_path / "logs")

    mounted = f"type=bind,src={harness},dst=/tests/run-game.sh,readonly"
    assert mounted in runtime.calls[0]
    assert runtime.calls[0].index(mounted) < runtime.calls[0].index("sha256:test-image")
    assert not any("dst=/tests/run-game.sh" in argument for argument in runtime.calls[2])


def test_the_shared_verifier_extends_the_frozen_suites() -> None:
    """The shared verifier keeps the frozen James and secret-room suites byte for byte and every
    frozen main-suite case name; its test.sh differs from the frozen one only in the case list
    and the counts."""
    frozen = PACK / "private/harbor" / BASELINE / "tests"
    for part in ("secret-suite", "james-suite"):
        for name in ("main.lua", "metadata.xml"):
            assert (SHARED_VERIFIER / part / name).read_bytes() == (frozen / part / name).read_bytes()
    frozen_metadata = (frozen / "suite/metadata.xml").read_bytes()
    assert (SHARED_VERIFIER / "suite/metadata.xml").read_bytes() == frozen_metadata
    catalog = IsaacCatalog.load(PACK)
    frozen_cases = expected_case_names(PACK, catalog.tasks[0])
    shared_cases = expected_case_names(PACK, catalog.tasks[1])
    assert set(frozen_cases) <= set(shared_cases)
    assert len(set(shared_cases)) == len(shared_cases)
    suite = (SHARED_VERIFIER / "suite/main.lua").read_text(encoding="utf-8")
    for case in set(shared_cases) - {"runtime_sentinel_secret", "runtime_sentinel_james", "blue_moon",
                                     "apocryphon_stats", "james_book_of_secrets_positive"}:
        assert f'record("{case}"' in suite, case
    frozen_test = (frozen / "test.sh").read_text(encoding="utf-8").splitlines()
    shared_test = (SHARED_VERIFIER / "test.sh").read_text(encoding="utf-8").splitlines()
    added = [line.strip() for line in shared_test if line not in frozen_test]
    removed = [line.strip() for line in frozen_test if line not in shared_test]
    assert removed == [
        "expected=35",
        "main_summaries=$(grep -c '\\[GCB_SUMMARY\\] passed=30 failed=0 total=30' "
        "\"$main_log\" 2>/dev/null || true)",
    ]
    extra = [line for line in added if not line.startswith(("expected=", "main_summaries="))]
    assert set(extra) == set(shared_cases) - set(frozen_cases)


def test_derived_launch_harness_changes_only_the_launch() -> None:
    """Every derived task runs the shared verifier's test.sh with one shared launch script."""
    frozen = PACK / "private/harbor" / BASELINE / "tests"
    catalog = IsaacCatalog.load(PACK)
    copies = {task.id: PACK / "private/harbor" / task.id / "tests" for task in catalog.tasks[1:]}
    harnesses = {path.joinpath("run-game.sh").read_bytes() for path in copies.values()}
    assert len(harnesses) == 1
    harness = harnesses.pop().decode("utf-8")
    for tests in copies.values():
        assert tests.joinpath("test.sh").read_bytes() == (SHARED_VERIFIER / "test.sh").read_bytes()
        assert os.access(tests / "run-game.sh", os.X_OK)
    original = frozen.joinpath("run-game.sh").read_text(encoding="utf-8")
    # Same environment, same client flags and the same exit codes and markers per phase.
    for fragment in (
        "export LIBGL_ALWAYS_SOFTWARE=1",
        "-silent -offline -cef-disable-gpu -cef-force-opaque-backgrounds -no-cef-sandbox",
        'echo "GCB_RUNTIME_INVALID steam_start_timeout" | tee -a "$runtime_log"\n  exit 10',
        'echo "GCB_RUNTIME_INVALID game_start_timeout" | tee -a "$runtime_log"\n  exit 11',
        'echo "GCB_RUNTIME_INVALID suite_start_timeout" | tee -a "$runtime_log"\n  exit 12',
        'echo "GCB_RUNTIME_INVALID suite_finish_timeout" | tee -a "$runtime_log"\nexit 13',
    ):
        assert fragment in harness
        assert fragment in original
    # From the key presses on, only the two wall-clock budgets differ.
    tail = harness[harness.index("send_game_key() {") :]
    frozen_tail = original[original.index("send_game_key() {") :]
    assert tail.replace("seq 1 60", "seq 1 20").replace("seq 1 900", "seq 1 180") == frozen_tail


DERIVED = "isaac-exodus-mixed-triage"


def _minimal_pack(tmp_path: Path, task_ids: tuple[str, ...], mutate: Any = None) -> Path:
    """A pack holding only the named catalog entries and the small files the loader reads."""
    import json

    pack = tmp_path / "pack"
    data = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))
    data["tasks"] = [task for task in data["tasks"] if task["id"] in task_ids]
    if mutate is not None:
        mutate(data)
    (pack / "exams").mkdir(parents=True)
    (pack / "catalog.json").write_text(json.dumps(data), encoding="utf-8")
    for task_id in task_ids:
        source = PACK / "private/harbor" / task_id
        task_root = pack / "private/harbor" / task_id
        for relative in ("environment/exodus", "tests", "scripts"):
            (task_root / relative).mkdir(parents=True)
        (pack / "exams" / f"{task_id}.md").write_bytes((PACK / "exams" / f"{task_id}.md").read_bytes())
        for name in ("main.lua", "metadata.xml"):
            (task_root / "environment/exodus" / name).touch()
        for name in ("save1.dat", "save2.dat"):
            (task_root / "environment/exodus" / name).write_bytes(
                (source / "environment/exodus" / name).read_bytes()
            )
        (task_root / "tests/test.sh").write_bytes((source / "tests/test.sh").read_bytes())
        (task_root / "scripts/private-runtime.Dockerfile").touch()
    return pack


def _shared_verifier(pack: Path, name: str, test_sh: bytes) -> Path:
    root = pack / "private/verifiers" / name
    for part in ("suite", "secret-suite", "james-suite"):
        (root / part).mkdir(parents=True)
        (root / part / "main.lua").write_text("-- suite\n", encoding="utf-8")
        (root / part / "metadata.xml").write_text("<metadata/>\n", encoding="utf-8")
    (root / "test.sh").write_bytes(test_sh)
    return root


def _use_demo_verifier(data: Any) -> None:
    for task in data["tasks"]:
        if task["id"] == DERIVED:
            task["verifier"] = "demo"


def test_a_derived_task_runs_its_shared_verifier_instead_of_the_image_suites(tmp_path: Path) -> None:
    pack = _minimal_pack(tmp_path, (BASELINE, DERIVED), _use_demo_verifier)
    test_sh = (pack / "private/harbor" / DERIVED / "tests/test.sh").read_bytes()
    shared = _shared_verifier(pack, "demo", test_sh)
    catalog = IsaacCatalog.load(pack)
    context = BenchmarkContext(
        project_root=ROOT, pack_root=pack, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )
    evaluator = IsaacEvaluator(context, catalog)
    baseline, derived = catalog.tasks
    assert evaluator.verifier(baseline) is None
    assert evaluator.verifier(derived) == shared.resolve()

    runtime = RecordingRuntime(context)
    submission = tmp_path / "submission"
    (submission / "exodus").mkdir(parents=True)
    runtime.run(submission, tmp_path / "logs", verifier=evaluator.verifier(derived))
    runtime.run(submission, tmp_path / "logs")

    command = runtime.calls[0]
    for part in ("test.sh", "suite", "secret-suite", "james-suite"):
        mounted = f"type=bind,src={(shared / part).resolve()},dst=/tests/{part},readonly"
        assert mounted in command
        assert command.index(mounted) < command.index("sha256:test-image")
    # Without a shared verifier the image's own test.sh and suites run.
    replaced = ("dst=/tests/test.sh", "dst=/tests/suite")
    assert not any(target in argument for argument in runtime.calls[2] for target in replaced)


def test_a_shared_verifier_must_be_complete_and_run_the_task_case_list(tmp_path: Path) -> None:
    pack = _minimal_pack(tmp_path, (BASELINE, DERIVED), _use_demo_verifier)
    with pytest.raises(ValueError, match="shared verifier is missing"):
        IsaacCatalog.load(pack)

    test_sh = (pack / "private/harbor" / DERIVED / "tests/test.sh").read_bytes()
    shared = _shared_verifier(pack, "demo", test_sh + b"# drift\n")
    with pytest.raises(ValueError, match="differs from shared verifier"):
        IsaacCatalog.load(pack)

    (shared / "test.sh").write_bytes(test_sh)
    (shared / "james-suite/main.lua").unlink()
    with pytest.raises(ValueError, match="james-suite/main.lua"):
        IsaacCatalog.load(pack)


def test_the_baseline_and_synthetic_tasks_cannot_name_a_shared_verifier() -> None:
    import json

    def baseline_verifier(data: Any) -> None:
        data["tasks"][0]["verifier"] = "demo"

    with pytest.raises(ValueError, match="baked into its image"):
        IsaacCatalog.model_validate_json(_core_catalog_json(baseline_verifier))

    synthetic = json.loads((SYNTH_PACK / "catalog.json").read_text(encoding="utf-8"))["tasks"][0]
    with pytest.raises(ValueError, match="own verifier image"):
        IsaacTask.model_validate({**synthetic, "verifier": "demo"})


def test_harness_report_keeps_only_harness_markers_and_status(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    (logs / "verifier").mkdir(parents=True)
    (logs / "verifier" / "runtime.log").write_text(
        "steam.sh[42]: Running Steam on ubuntu 24.04 64-bit\n"
        "GCB_RUNTIME_NOTE launch_request_ignored request=1\n"
        "GCB_ISAAC_STARTED\n"
        "GCB_RUNTIME_INVALID suite_finish_timeout\n",
        encoding="utf-8",
    )
    process = subprocess.CompletedProcess(
        [], 0, "noise\nruntime_exit=13 secret_exit=0 james_exit=0 main_exit=13 INVALID_RUNTIME\n", ""
    )

    report = IsaacEvaluator._harness_report(logs, process)

    assert report.splitlines() == [
        "GCB_RUNTIME_NOTE launch_request_ignored request=1",
        "GCB_ISAAC_STARTED",
        "GCB_RUNTIME_INVALID suite_finish_timeout",
        "runtime_exit=13 secret_exit=0 james_exit=0 main_exit=13 INVALID_RUNTIME",
    ]
    assert "Running Steam" not in report
    empty = subprocess.CompletedProcess([], 0, "", "")
    assert IsaacEvaluator._harness_report(tmp_path / "missing", empty) == ""


class TimeoutRuntime(RecordingRuntime):
    def _docker(
        self,
        arguments: list[str],
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(arguments)
        if arguments[0] == "run" and "/tests/test.sh" in arguments:
            raise subprocess.TimeoutExpired(arguments, timeout)
        return subprocess.CompletedProcess(arguments, 0, "", "")


def test_runtime_removes_timed_out_container(tmp_path: Path) -> None:
    runtime = TimeoutRuntime(_context(tmp_path))
    submission = tmp_path / "submission"
    (submission / "exodus").mkdir(parents=True)

    with pytest.raises(subprocess.TimeoutExpired):
        runtime.run(submission, tmp_path / "logs")

    cleanup = runtime.calls[-1]
    assert cleanup[:2] == ["rm", "--force"]
    assert cleanup[2].startswith("rhenium-isaac-")


def _write_runtime_evidence(logs: Path, task_names: tuple[str, ...], reward: str | None) -> None:
    verifier = logs / "verifier"
    verifier.mkdir(parents=True)
    events = "".join(f"[GCB_CASE] PASS {name} ok\n" for name in task_names)
    summaries = "".join("[GCB_SUMMARY] passed=1 failed=0 total=1\n" for _ in range(3))
    (verifier / "game.log").write_text(events + summaries, encoding="utf-8")
    if reward is not None:
        (verifier / "reward.txt").write_text(reward + "\n", encoding="utf-8")


def test_runtime_evidence_requires_all_cases_processes_and_reward(tmp_path: Path) -> None:
    catalog = IsaacCatalog.load(PACK)
    task = catalog.tasks[0]
    evaluator = IsaacEvaluator(_context(tmp_path), catalog)
    names = expected_case_names(PACK, task)
    process = subprocess.CompletedProcess(
        [],
        0,
        "runtime_exit=0 secret_exit=0 james_exit=0 main_exit=0 passed=35 failed=0\n",
        "",
    )
    logs = tmp_path / "complete"
    _write_runtime_evidence(logs, names, "1")

    complete, passed, passed_count, failed_count, _ = evaluator._runtime_evidence(logs, process, task)

    assert (complete, passed, passed_count, failed_count) == (True, True, 35, 0)

    missing_reward = tmp_path / "missing-reward"
    _write_runtime_evidence(missing_reward, names, None)
    complete, passed, _, _, _ = evaluator._runtime_evidence(missing_reward, process, task)
    assert complete is False
    assert passed is False


def _write_construct_evidence(logs: Path, names: tuple[str, ...], failing: set[str]) -> None:
    verifier = logs / "verifier"
    verifier.mkdir(parents=True)
    events = "".join(
        f"[GCB_CASE] {'FAIL' if name in failing else 'PASS'} {name} detail\n" for name in names
    )
    summary = f"[GCB_SUMMARY] passed={len(names) - len(failing)} failed={len(failing)} total={len(names)}\n"
    (verifier / "game.log").write_text(events + summary, encoding="utf-8")
    (verifier / "reward.txt").write_text("1\n" if not failing else "0\n", encoding="utf-8")


def test_construct_runtime_evidence_expects_one_process_and_no_sentinels(tmp_path: Path) -> None:
    """A construct verifier is one game process with one suite; its complete run has one
    summary, the closing status line of its test.sh, and no runtime sentinel cases."""
    catalog = IsaacCatalog.load(SYNTH_PACK)
    task = catalog.tasks[0]
    assert task.clean_room_synthetic
    context = BenchmarkContext(
        project_root=ROOT, pack_root=SYNTH_PACK, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )
    evaluator = IsaacEvaluator(context, catalog)
    names = expected_case_names(SYNTH_PACK, task)
    status = (
        "runtime_exit=0 passed=35 failed=0 expected=35 summaries=1 fatals=0 "
        "case_occurrences_ok=1 cases=a=1,\n"
    )
    process = subprocess.CompletedProcess([], 0, status, "")

    passing = tmp_path / "passing"
    _write_construct_evidence(passing, names, set())
    complete, passed, passed_count, failed_count, evidence = evaluator._runtime_evidence(
        passing, process, task
    )
    assert (complete, passed, passed_count, failed_count) == (True, True, 35, 0)
    assert evidence.startswith("processes=1/1 ") and "summaries=1/1" in evidence

    failing = tmp_path / "failing"
    _write_construct_evidence(failing, names, {names[3]})
    failed_status = subprocess.CompletedProcess(
        [], 0, status.replace("passed=35 failed=0", "passed=34 failed=1"), ""
    )
    complete, passed, passed_count, failed_count, _ = evaluator._runtime_evidence(
        failing, failed_status, task
    )
    assert (complete, passed, passed_count, failed_count) == (True, False, 34, 1)

    # The Exodus three-process status line never completes a construct task, and a run
    # that did not reach test.sh's closing line is incomplete rather than failed.
    for stdout in (
        "runtime_exit=0 secret_exit=0 james_exit=0 main_exit=0 passed=35 failed=0\n",
        "runtime_exit=13 passed=35 failed=0 INVALID_RUNTIME\n",
        "",
    ):
        complete, passed, _, _, _ = evaluator._runtime_evidence(
            passing, subprocess.CompletedProcess([], 0, stdout, ""), task
        )
        assert (complete, passed) == (False, False), stdout

    # Only construct tasks use the one-process protocol.
    exodus = IsaacCatalog.load(PACK).tasks[0]
    complete, passed, _, _, _ = IsaacEvaluator(_context(tmp_path), IsaacCatalog.load(PACK))._runtime_evidence(
        passing, process, exodus
    )
    assert (complete, passed) == (False, False)


def test_construct_tasks_use_the_image_launch_script_and_mount_the_mod_starter(tmp_path: Path) -> None:
    catalog = IsaacCatalog.load(SYNTH_PACK)
    task = catalog.tasks[0]
    context = BenchmarkContext(
        project_root=ROOT, pack_root=SYNTH_PACK, state_dir=tmp_path / "state", cache_dir=tmp_path / "cache"
    )
    evaluator = IsaacEvaluator(context, catalog)
    assert evaluator.harness(task) is None

    runtime = RecordingRuntime(context)
    submission = tmp_path / "submission"
    (submission / "mod").mkdir(parents=True)
    runtime.run(submission, tmp_path / "logs", "sha256:construct-image", task.starter_name)
    command = " ".join(runtime.calls[0])
    assert f"type=bind,src={(submission / 'mod').resolve()},dst=/app/exodus,readonly" in command
    assert "dst=/tests/run-game.sh" not in command
    assert runtime.calls[0][runtime.calls[0].index("--network") + 1] == "none"


def test_case_report_keeps_name_level_outcomes_and_only_verifier_markers(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    verifier = logs / "verifier"
    verifier.mkdir(parents=True)
    (verifier / "game.log").write_text(
        "engine noise that is not a marker\n"
        "[GCB_CASE] PASS alpha_case ok\n"
        "[GCB_CASE] FAIL beta_case expected 3 got 2\n"
        "[GCB_SUMMARY] passed=1 failed=1 total=2\n",
        encoding="utf-8",
    )

    outcomes, markers = IsaacEvaluator._case_report(logs)

    assert outcomes == {"alpha_case": True, "beta_case": False}
    assert "engine noise" not in markers and "[GCB_SUMMARY]" in markers
    assert IsaacEvaluator._case_report(tmp_path / "missing") == ({}, "")


def test_construct_task_public_metadata_marks_from_scratch() -> None:
    import json

    raw = json.loads((PACK / "catalog.json").read_text(encoding="utf-8"))["tasks"][0]
    raw.update(
        id="isaac-synth-demo",
        source_mod="Clean-room synthetic",
        clean_room_synthetic=True,
        required_files=["mod/main.lua", "mod/metadata.xml"],
    )
    task = IsaacTask.model_validate(raw)
    assert task.starter_name == "mod"

    plugin = IsaacRebirthBenchmarkPlugin()
    public = plugin.public_task(task)
    assert public["fromScratch"] is True
    assert public["taskKind"] == "construct"
    assert public["cleanRoomSynthetic"] is True
    assert "sourceMod" not in public

    baseline = IsaacCatalog.load(PACK).tasks[0]
    baseline_public = plugin.public_task(baseline)
    assert baseline_public["fromScratch"] is False
    assert baseline_public["taskKind"] == "debugging"
    assert baseline_public.get("sourceMod") == "Exodus"
