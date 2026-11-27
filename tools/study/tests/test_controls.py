from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_study import controls
from rhenium_study.clausemap import ClauseMap
from rhenium_study.inventory import TASKS, task_for
from rhenium_study.paths import StudyPaths

CLAUSE_MAP = ClauseMap.model_validate(
    {
        "task": "game/pack/task",
        "task_version": "1.0.0",
        "exam": "exams/task.md",
        "cases": [
            {"id": "case:target", "role": "target", "clauses": ["#1"]},
            {"id": "case:guard", "role": "preserved", "clauses": ["keep"]},
            {"id": "case:sentinel", "role": "runtime-sentinel"},
        ],
        "clauses": [
            {"id": "#1", "anchor": "a", "status": "asserted"},
            {"id": "keep", "anchor": "b", "status": "asserted"},
        ],
    }
)
PASS = {"complete": True, "passed": True}
FAIL = {"complete": True, "passed": False}


@pytest.mark.parametrize(
    "kind,table,result,ok",
    [
        ("reference", {"case:target": "P", "case:guard": "P", "case:sentinel": "P"}, PASS, True),
        ("alternative", {"case:target": "P", "case:guard": "U", "case:sentinel": "P"}, PASS, False),
        ("starter", {"case:target": "F", "case:guard": "P", "case:sentinel": "P"}, FAIL, True),
        ("starter", {"case:target": "F", "case:guard": "F", "case:sentinel": "P"}, FAIL, False),
        ("starter", {"case:target": "P", "case:guard": "P", "case:sentinel": "P"}, PASS, False),
        ("target-negative", {"case:target": "F", "case:guard": "P", "case:sentinel": "P"}, FAIL, True),
        ("target-negative", {"case:target": "F", "case:guard": "F", "case:sentinel": "P"}, FAIL, False),
        ("compat-negative", {"case:target": "P", "case:guard": "F", "case:sentinel": "P"}, FAIL, True),
        ("compat-negative", {"case:target": "F", "case:guard": "F", "case:sentinel": "P"}, FAIL, False),
        ("compat-negative", {"case:target": "P", "case:guard": "P", "case:sentinel": "P"}, PASS, False),
        ("compat-negative", {"case:target": "U", "case:guard": "F", "case:sentinel": "P"}, FAIL, False),
    ],
)
def test_each_control_kind_has_one_admissible_outcome(
    kind: controls.ControlKind, table: dict[str, str], result: dict[str, object], ok: bool
) -> None:
    assert (controls.verdict(kind, CLAUSE_MAP, table, result) == []) is ok


def test_manifest_adds_declared_controls_and_rejects_bad_rows(tmp_path: Path) -> None:
    assert [spec.control for spec in controls.load_manifest(tmp_path)] == ["starter", "reference"]
    (tmp_path / "manifest.tsv").write_text(
        "control\tkind\tbase\toverlay\troot\tnote\n"
        "alt-a\talternative\tstarter\ttree:alt-a\t.\tdifferent data structure\n"
        "guard-break\tcompat-negative\treference\tpatch:guard-break.patch\tmod\t\n",
        encoding="utf-8",
    )
    specs = controls.load_manifest(tmp_path)
    assert [(spec.control, spec.kind, spec.overlay, spec.root) for spec in specs[2:]] == [
        ("alt-a", "alternative", "tree:alt-a", "."),
        ("guard-break", "compat-negative", "patch:guard-break.patch", "mod"),
    ]
    (tmp_path / "manifest.tsv").write_text(
        "control\tkind\tbase\toverlay\troot\tnote\nreference\treference\treference\t-\t.\t\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        controls.load_manifest(tmp_path)


def test_oracle_paths_are_relocated_without_touching_lookalikes() -> None:
    script = (
        'cd /app/exodus\npatch -p1 < /solution/gold.patch\ncp "/app" /application /tmp/app /opt/solution-x\n'
        "cp /solution/A.java /workspace/mindustry/src/A.java /workspaces\n"
    )
    relocated = controls._SOLUTION_TOKEN.sub(
        "/S", controls._WORKSPACE_TOKEN.sub("/A", controls._APP_TOKEN.sub("/A", script))
    )
    assert relocated == (
        'cd /A/exodus\npatch -p1 < /S/gold.patch\ncp "/A" /application /tmp/app /opt/solution-x\n'
        "cp /S/A.java /A/mindustry/src/A.java /workspaces\n"
    )


@pytest.mark.parametrize("form", ["directory", "file", "escape"])
def test_reference_overlay_copies_the_reference_to_its_hub_path(tmp_path: Path, form: str) -> None:
    from rhenium_study.inventory import StudyTask

    paths = StudyPaths(project_root=tmp_path / "repo", data_root=tmp_path / "data")
    solution = paths.pack_root("pack") / "private/harbor/task/solution"
    (solution / "after/src").mkdir(parents=True)
    (solution / "after/src/Fix.java").write_text("fixed")
    (solution / "reference.lua").write_text("reference")
    # A Harbor oracle that would write elsewhere; the overlay must not run it.
    (solution / "solve.sh").write_text("cp -R /solution/after/. /app/elsewhere/\n")
    app = tmp_path / "app"
    (app / "project/src").mkdir(parents=True)
    (app / "project/src/Fix.java").write_text("broken")
    (app / "mod").mkdir()
    (app / "mod/main.lua").write_text("")
    overlay = {
        "directory": ("after", "project"),
        "file": ("reference.lua", "mod/main.lua"),
        "escape": ("../../outside", "project"),
    }[form]
    task = StudyTask("game", "pack", "task", "repair", "family", "pack", overlay[1].split("/")[0], True,
                     reference_overlay=overlay)
    if form == "escape":
        with pytest.raises(ValueError, match="escapes"):
            controls._apply_reference(task, paths, app)
        return
    controls._apply_reference(task, paths, app)
    assert not (app / "elsewhere").exists()
    if form == "directory":
        assert (app / "project/src/Fix.java").read_text() == "fixed"
    else:
        assert (app / "mod/main.lua").read_text() == "reference"


def test_inventory_tasks_exist_with_an_oracle_and_a_clause_map() -> None:
    assert len({task.key for task in TASKS}) == len(TASKS)
    assert {task.kind for task in TASKS} <= {"construct", "repair"}
    paths = StudyPaths(project_root=Path(__file__).parents[3], data_root=Path("/nonexistent"))
    for task in TASKS:
        pack = paths.pack_root(task.pack_dir)
        manifest = json.loads((pack / "benchmark.json").read_text(encoding="utf-8"))
        assert manifest["pack_id"] == task.pack, task.key
        catalog = json.loads((pack / manifest["catalog"]).read_text(encoding="utf-8"))
        assert task.task in {entry["id"] for entry in catalog["tasks"]}, task.key
        solution = pack / "private/harbor" / task.task / "solution"
        if task.reference_tree is not None:
            source, target = task.reference_tree
            assert (pack / source).is_dir(), task.key
            assert target == task.app_subdir, task.key
        elif task.reference_overlay is not None:
            source, target = task.reference_overlay
            assert (solution / source).exists(), task.key
            assert target.split("/")[0] == task.app_subdir, task.key
        elif (solution / "solve.sh").is_file():
            oracle = (solution / "solve.sh").read_text(encoding="utf-8")
            assert any(f"{root}/{task.app_subdir}" in oracle for root in ("/app", "/workspace")), task.key
        else:
            assert (solution / "after" / task.app_subdir).is_dir(), task.key
        assert (paths.study_controls(task.pack_dir, task.task) / "clause-map.json").is_file(), task.key
    with pytest.raises(ValueError):
        task_for("dst/core/not-a-task")


def test_reference_tree_copies_a_pack_directory_over_the_starter(tmp_path: Path) -> None:
    from rhenium_study.inventory import StudyTask

    paths = StudyPaths(project_root=tmp_path, data_root=tmp_path / "data")
    gold = paths.pack_root("pack") / "private/frozen/gold"
    gold.mkdir(parents=True)
    (gold / "main.lua").write_text("reference\n")
    app = tmp_path / "app"
    (app / "starter").mkdir(parents=True)
    (app / "starter/main.lua").write_text("starter\n")
    (app / "starter/manifest.json").write_text("{}\n")
    task = StudyTask(
        "game", "core", "task", "repair", "family", "pack", "starter", True,
        reference_tree=("private/frozen/gold", "starter"),
    )

    controls._apply_reference(task, paths, app)

    assert (app / "starter/main.lua").read_text() == "reference\n"
    assert (app / "starter/manifest.json").read_text() == "{}\n"


def test_reference_tree_outside_the_pack_is_refused(tmp_path: Path) -> None:
    from rhenium_study.inventory import StudyTask

    paths = StudyPaths(project_root=tmp_path, data_root=tmp_path / "data")
    (tmp_path / "outside").mkdir()
    (tmp_path / "app/starter").mkdir(parents=True)
    task = StudyTask(
        "game", "core", "task", "repair", "family", "pack", "starter", True,
        reference_tree=("../../outside", "starter"),
    )
    with pytest.raises(ValueError, match="escapes"):
        controls._apply_reference(task, paths, tmp_path / "app")


def test_pack_overlay_copies_a_frozen_pack_control_and_stays_inside_the_pack(tmp_path: Path) -> None:
    from rhenium_study.inventory import StudyTask

    paths = StudyPaths(project_root=tmp_path, data_root=tmp_path / "data")
    frozen = paths.pack_root("pack") / "private/frozen/M01"
    frozen.mkdir(parents=True)
    (frozen / "main.lua").write_text("mutant\n")
    workspace = tmp_path / "workspace"
    (workspace / "starter").mkdir(parents=True)
    (workspace / "starter/main.lua").write_text("starter\n")
    task = StudyTask("game", "core", "task", "repair", "family", "pack", "starter", True)
    (paths.study_controls("pack", "task")).mkdir(parents=True)
    paths.locks.mkdir(parents=True)
    spec = controls.ControlSpec(
        "M01", "target-negative", "starter", "pack:private/frozen/M01", "starter"
    )

    submission = controls.materialize(task, spec, paths, workspace)

    assert (submission / "starter/main.lua").read_text() == "mutant\n"
    escaping = controls.ControlSpec("M02", "target-negative", "starter", "pack:../../outside", "starter")
    with pytest.raises(ValueError, match="escapes"):
        controls.materialize(task, escaping, paths, workspace)


def _balatro_controls(task: str) -> tuple[Path, dict[str, object]]:
    root = Path(__file__).parents[3]
    pack = root / "benchmarks/balatro"
    assets = json.loads((pack / "private/native-v1/assets.json").read_text(encoding="utf-8"))
    return pack / "private/study-controls" / task, assets["tasks"][task]


def test_balatro_inventory_covers_each_catalog_task_with_the_hub_layout() -> None:
    root = Path(__file__).parents[3]
    catalog = json.loads((root / "benchmarks/balatro/catalog.json").read_text(encoding="utf-8"))
    registered = [task for task in TASKS if task.game == "balatro"]
    assert {task.task for task in registered} == {task["id"] for task in catalog["tasks"]}
    assert all(task.kind == "repair" and task.pack == "core" for task in registered)
    assert all(task.pack_dir == "balatro" for task in registered)
    assert all(task.app_subdir == "starter" and task.submission_is_app for task in registered)


# The evaluator reports these two scenarios' checks in another order than the frozen list.
_BALATRO_REORDERED = {"durable-charge-v2", "shop-price-coherence-v2"}


@pytest.mark.parametrize(
    "task", [task.task for task in TASKS if task.game == "balatro"]
)
def test_balatro_clause_map_names_every_evaluator_position_once(task: str) -> None:
    directory, frozen = _balatro_controls(task)
    root = Path(__file__).parents[3]
    catalog = json.loads((root / "benchmarks/balatro/catalog.json").read_text(encoding="utf-8"))
    clause_map = ClauseMap.load(directory / "clause-map.json")
    required = frozen["required"]
    assert isinstance(required, list)
    assert clause_map.task == f"balatro/core/{task}"
    assert clause_map.task_version == catalog["version"]
    assert [case.id for case in clause_map.cases] == [
        f"position:{index}" for index in range(1, len(required) + 1)
    ]
    names = [case.note for case in clause_map.cases]
    assert sorted(names) == sorted(required)
    if task not in _BALATRO_REORDERED:
        assert names == required


@pytest.mark.parametrize(
    "task", [task.task for task in TASKS if task.game == "balatro"]
)
def test_balatro_manifest_has_the_controls_admission_needs(task: str) -> None:
    directory, _frozen = _balatro_controls(task)
    specs = controls.load_manifest(directory)
    kinds = {spec.kind for spec in specs}
    assert {"starter", "reference", "target-negative", "alternative"} <= kinds
    assert all(spec.root == "starter" for spec in specs if spec.overlay != "-")


def test_study_data_must_live_outside_the_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).parents[3]
    monkeypatch.setenv("RHENIUM_STUDY_DIR", str(root / "study-data"))
    with pytest.raises(ValueError, match="outside"):
        StudyPaths.load(root)


@pytest.mark.parametrize("pack,kind", [("core", "repair"), ("construct", "construct")])
def test_minecraft_inventory_covers_each_catalog_task_with_the_hub_layout(pack: str, kind: str) -> None:
    root = Path(__file__).parents[3]
    pack_dir = "minecraft-core" if pack == "core" else "minecraft-construct"
    catalog = json.loads((root / "benchmarks" / pack_dir / "catalog.json").read_text())
    registered = [task for task in TASKS if task.game == "minecraft" and task.pack == pack]
    assert {task.task for task in registered} == {task["id"] for task in catalog["tasks"]}
    assert all(task.kind == kind for task in registered)
    assert all(task.app_subdir == "plugin" and task.submission_is_app for task in registered)
    assert all(task.pack_dir == pack_dir for task in registered)
    for task in registered:
        entry = next(entry for entry in catalog["tasks"] if entry["id"] == task.task)
        clause_map = ClauseMap.load(
            root / "benchmarks" / pack_dir / "private/study-controls" / task.task / "clause-map.json"
        )
        assert clause_map.task_version == catalog["version"], task.key
        assert {case.id for case in clause_map.cases if case.id.startswith("server:")} == {
            f"server:{case}" for case in entry["server_cases"]
        }, task.key
        assert {case.id for case in clause_map.cases if case.id.startswith("unit:")} == {
            f"unit:{case}" for case in entry.get("unit_cases", [])
        }, task.key
    if pack == "core":
        assert {task.source_family for task in registered} == {
            "multiverse-core", "chatty", "betterteams", "prometheus-exporter"
        }


def test_engine_slots_bound_concurrency_and_are_released(tmp_path: Path) -> None:
    from rhenium_study.hubs import engine_slot

    with (
        engine_slot(tmp_path, "game-pack", slots=2) as first,
        engine_slot(tmp_path, "game-pack", slots=2) as second,
    ):
        assert {first, second} == {0, 1}
    with engine_slot(tmp_path, "game-pack", slots=1) as again:
        assert again == 0
