from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "isaac-synth"
TASK_IDS = (
    "construct-config-navigation",
    "construct-config-persistence",
    "construct-hud-compositor",
    "construct-legacy-hud-lifecycle",
    "construct-option-rendering",
    "construct-room-rng",
    "construct-entity-cleanup",
    "construct-callback-transaction",
)


def _acceptance_cases(exam: str) -> list[str]:
    section = exam.split("## Acceptance cases\n", maxsplit=1)[1]
    section = section.split("\n## ", maxsplit=1)[0]
    section = section.split("\n\n", maxsplit=1)[0]
    cases = []
    for value in section.replace("\n", " ").split(","):
        case = value.strip().removesuffix(".")
        if re.fullmatch(r"[a-z0-9_]+", case):
            cases.append(case)
    return cases


def test_synth_pack_has_eight_independent_construct_specs() -> None:
    exams = sorted(path.stem for path in (PACK / "exams").glob("*.md"))
    # Task directories carry a starter; validation/ holds the pack's measured controls.
    starters = sorted(
        path.name for path in (PACK / "private/harbor").iterdir() if (path / "environment").is_dir()
    )

    assert set(exams) == set(TASK_IDS)
    assert set(starters) == set(TASK_IDS)


def test_each_spec_has_a_unique_35_case_acceptance_surface_and_clean_starter() -> None:
    for task_id in TASK_IDS:
        exam_path = PACK / "exams" / f"{task_id}.md"
        starter = PACK / "private/harbor" / task_id / "environment/mod"
        exam = exam_path.read_text(encoding="utf-8")

        cases = _acceptance_cases(exam)
        assert len(cases) == 35, task_id
        assert len(set(cases)) == 35, task_id
        assert "Afterbirth+ v1.06.T1" in " ".join(exam.split()), task_id
        assert (starter / "main.lua").read_text(encoding="utf-8").startswith(
            "local mod = RegisterMod("
        ), task_id
        metadata = ElementTree.parse(starter / "metadata.xml").getroot()
        # The starter reaches anonymous attempts, which must not name their task; the mod is
        # identified by its directory instead.
        assert metadata.findtext("id") == metadata.findtext("directory"), task_id
        assert task_id not in (starter / "metadata.xml").read_text(encoding="utf-8"), task_id
        assert sorted(path.name for path in starter.iterdir()) == ["main.lua", "metadata.xml"]


def test_synth_pack_lists_exactly_the_tasks_with_private_verifiers() -> None:
    """The pack manifest admits a construct task only once its reference and engine verifier
    exist; every admitted task binds to the construct runtime and every verifier is the shared
    single-process harness with only the mod directory names and case list changed."""
    from rhenium_isaac_rebirth.catalog import IsaacCatalog, expected_case_names

    from rhenium.core.manifest import BenchmarkManifest
    from rhenium.core.runtime import RuntimeCatalog

    manifest = BenchmarkManifest.load(PACK / "benchmark.json")
    assert (manifest.pack_id, manifest.plugin) == ("synth", "isaac-rebirth")
    catalog = IsaacCatalog.load(PACK, manifest.catalog)
    assert manifest.runtime_catalog is not None
    runtimes = RuntimeCatalog.load(PACK, manifest.runtime_catalog)
    assert [runtime.id for runtime in runtimes.runtimes] == ["afterbirth-plus-1.06.t1-synth"]
    core = RuntimeCatalog.load(ROOT / "benchmarks" / "isaac-core", "runtimes.json").runtimes[0]
    assert runtimes.runtimes[0].source == core.source
    assert runtimes.runtimes[0].version == core.version

    with_verifiers = {
        task_id
        for task_id in TASK_IDS
        if (PACK / "private/harbor" / task_id / "tests/test.sh").is_file()
        and (PACK / "private/harbor" / task_id / "solution/reference.lua").is_file()
    }
    listed = {task.id for task in catalog.tasks}
    assert listed == with_verifiers
    assert set(runtimes.task_bindings) == listed
    assert (PACK / "LICENSE").is_file()

    pattern = PACK / "private/harbor/construct-room-rng/tests"
    for task in catalog.tasks:
        assert task.clean_room_synthetic and task.difficulty == "hard" and task.expected_cases == 35
        assert task.required_files == ["mod/main.lua", "mod/metadata.xml"]
        tests = PACK / "private/harbor" / task.id / "tests"
        assert (
            tests.joinpath("run-game.sh").read_bytes() == pattern.joinpath("run-game.sh").read_bytes()
        )
        assert tests.joinpath("Dockerfile").read_bytes() == pattern.joinpath("Dockerfile").read_bytes()
        assert len(expected_case_names(PACK, task)) == 35
        # test.sh differs from the room-rng harness only in the two mod directory names and
        # the case list, so every construct task is graded by the same rules.
        harness = _normalized_harness(tests / "test.sh", task.id)
        assert harness == _normalized_harness(pattern / "test.sh", "construct-room-rng")
        suite = (tests / "suite/main.lua").read_text(encoding="utf-8")
        assert 'local json = require("json")' in suite
        assert "[GCB_RUNTIME] suite_started" in suite and "[GCB_SUMMARY]" in suite


def _normalized_harness(path: Path, task_id: str) -> str:
    text = path.read_text(encoding="utf-8")
    text = text.replace(task_id.replace("-", "_"), "TASK")
    return re.sub(r"expected_cases=\(\n.*?\n\)\n", "expected_cases=(CASES)\n", text, flags=re.DOTALL)


def test_private_case_lists_match_any_present_engine_suite() -> None:
    for task_id in TASK_IDS:
        task_root = PACK / "private/harbor" / task_id
        verifier = task_root / "tests/test.sh"
        suite = task_root / "tests/suite/main.lua"
        if not verifier.exists() and not suite.exists():
            continue
        assert verifier.is_file() and suite.is_file(), task_id

        verifier_text = verifier.read_text(encoding="utf-8")
        match = re.search(
            r"^expected_cases=\(\s*(.*?)\s*\)$",
            verifier_text,
            re.MULTILINE | re.DOTALL,
        )
        assert match is not None, task_id
        expected = match.group(1).split()
        suite_text = suite.read_text(encoding="utf-8")
        suite_cases = re.findall(r'run\("([a-z0-9_]+)"', suite_text)
        public_cases = _acceptance_cases(
            (PACK / "exams" / f"{task_id}.md").read_text(encoding="utf-8")
        )
        assert len(expected) == 35 and len(set(expected)) == 35, task_id
        assert len(suite_cases) == 35 and len(set(suite_cases)) == 35, task_id
        assert set(expected) == set(suite_cases) == set(public_cases), task_id
        assert "AddCallback(ModCallbacks.MC_POST_GAME_STARTED" in suite_text, task_id
