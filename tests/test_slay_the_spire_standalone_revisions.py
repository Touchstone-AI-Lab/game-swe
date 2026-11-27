"""Version and fail-closed scoring checks for the real-game r2 revisions of standalone
ModTheSpire tasks. mts-loader-internals-regressions is retired without one: its starter cannot
launch the game."""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PACK = Path(__file__).parents[1] / "benchmarks/slay-the-spire-core"
HARBOR = PACK / "private/harbor"
VALIDATION = PACK / "validation/native-engine"
# Old task -> number of private JUnit cases its r1 verifier declared.
TASKS = {
    "mts-load-order-regressions": 9,
    "mts-mod-identity-regressions": 7,
}
ENGINE = "gl=true,listener=com.megacrit.cardcrawl.core.CardCrawlGame,self=true,menu=true,frames=3"
STAND_INS = (
    "com/megacrit/cardcrawl/core/CardCrawlGame.java",
    "com/megacrit/cardcrawl/desktop/DesktopLauncher.java",
)
# Reviewed r2 files that do not come byte-for-byte from r1.
NEW_FILES = {
    "environment/Dockerfile", "task.toml", "tests/test.sh", "tests/score.py", "tests/expectations.json",
    "tests/build-template.tar.gz", "tests/observer/Observer.java", "tests/observer/ModTheSpire.json",
}


def files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def scorer(task: str) -> ModuleType:
    path = HARBOR / f"{task}-r2" / "tests/score.py"
    # Importing from this read-only pack would write a bytecode cache into it.
    module = ModuleType(f"standalone_{task.replace('-', '_')}_score")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def observations(task: str, statuses: dict[str, str] | None = None, *, engine: str = ENGINE) -> str:
    cases = json.loads((HARBOR / f"{task}-r2" / "tests/expectations.json").read_text())["cases"]
    lines = [f"SUITE_ENGINE nonce|{engine}"]
    for name in cases:
        lines.append(f"SUITE_CASE nonce|id={name},status={(statuses or {}).get(name, 'SUCCESSFUL')}")
    lines.append(f"SUITE_DONE nonce|tests={len(cases)}")
    return "\n".join(lines) + "\n"


def score(task: str, text: str, exit_code: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = scorer(task).score(text, "nonce", exit_code)
    return result


@pytest.mark.parametrize("task", TASKS)
def test_revision_keeps_the_exam_starter_reference_and_suite_byte_identical(task: str) -> None:
    old, new = HARBOR / task, HARBOR / f"{task}-r2"
    before, after = files(old), files(new)
    renamed = {
        name.replace("environment/modthespire/", "environment/project/", 1): digest
        for name, digest in before.items()
        if name.startswith("environment/modthespire/")
    }
    kept = {
        name: digest for name, digest in before.items()
        if name.startswith(("solution/", "tests/")) and name.endswith((".java", ".sh"))
        and name != "tests/test.sh"
    }
    kept["instruction.md"] = before["instruction.md"]
    assert set(after) == set(renamed) | set(kept) | NEW_FILES
    assert {name: after[name] for name in renamed} == renamed
    assert {name: after[name] for name in kept} == kept
    exam = (PACK / "exams" / f"{task}.md").read_bytes()
    assert (PACK / "exams" / f"{task}-r2.md").read_bytes() == exam == (new / "instruction.md").read_bytes()
    template = HARBOR / "mts-enum-identity-r2/tests/build-template.tar.gz"
    assert (new / "tests/build-template.tar.gz").read_bytes() == template.read_bytes()
    manifest = json.loads((VALIDATION / f"{task}-r2" / "frozen-manifest.json").read_text())
    assert manifest["files"] == after and manifest["supersedes"] == task


@pytest.mark.parametrize("task", TASKS)
def test_the_suite_and_its_case_list_are_exactly_what_r1_ran(task: str) -> None:
    old_shell = (HARBOR / task / "tests/test.sh").read_text()
    staged = re.search(r'^cp ((?:/tests/\S+\.java ?)+) "\$SUITE/"$', old_shell, re.M)
    assert staged is not None
    suite = [Path(item).name for item in staged.group(1).split()]
    expectations = json.loads((HARBOR / f"{task}-r2" / "tests/expectations.json").read_text())
    assert expectations["suite"] == suite
    assert len(expectations["cases"]) == len(set(expectations["cases"])) == TASKS[task]
    assert re.search(rf"^EXPECTED={TASKS[task]}$", old_shell, re.M)
    shell = (HARBOR / f"{task}-r2" / "tests/test.sh").read_text()
    assert f"SUITE_FILES=({' '.join(suite)})" in shell
    assert f"STAND_INS=({' '.join(STAND_INS)})" in shell
    for name in STAND_INS:
        assert (HARBOR / f"{task}-r2" / "environment/project/src/main/java" / name).is_file()


@pytest.mark.parametrize("task", TASKS)
def test_the_native_task_configuration_runs_offline_on_the_steam_runtime(task: str) -> None:
    config = tomllib.loads((HARBOR / f"{task}-r2" / "task.toml").read_text())
    assert config["artifacts"] == [{"source": "/app/modthespire/src/main/java"}]
    assert config["environment"]["workdir"] == "/app/modthespire"
    assert config["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["environment"]["network_mode"] == "no-network"
    assert config["verifier"]["environment_mode"] == "separate"
    runtime = "sha256:233e1d8f96e8368fa753bdcb6730de724f482e865beb2241a05b412fcfe6c350"
    assert config["verifier"]["environment"]["docker_image"] == runtime
    assert (HARBOR / f"{task}-r2" / "environment/Dockerfile").read_text().splitlines()[0] == "FROM " + runtime


@pytest.mark.parametrize("task", TASKS)
def test_complete_in_game_suite_observations_can_pass(task: str) -> None:
    result = score(task, observations(task))
    assert result["complete"] and result["reward"] == 1 and result["passed"] == TASKS[task]


@pytest.mark.parametrize("task", TASKS)
def test_a_failed_case_is_a_complete_failure(task: str) -> None:
    cases = json.loads((HARBOR / f"{task}-r2" / "tests/expectations.json").read_text())["cases"]
    result = score(task, observations(task, {cases[0]: "FAILED"}))
    assert result["complete"] and result["reward"] == 0 and result["passed"] == TASKS[task] - 1


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("corruption", [
    "nonce", "exit", "engine-gl", "engine-menu", "engine-self", "missing", "duplicate", "skipped", "aborted",
    "container", "unfinished", "empty",
])
def test_invalid_or_incomplete_evidence_never_passes(task: str, corruption: str) -> None:
    text = observations(task)
    exit_code = 0
    lines = text.splitlines()
    if corruption == "nonce":
        lines[2] = lines[2].replace("nonce|", "other|")
    elif corruption == "exit":
        exit_code = 124
    elif corruption.startswith("engine-"):
        field = corruption.split("-", 1)[1]
        lines[0] = lines[0].replace(f"{field}=true", f"{field}=false")
    elif corruption == "missing":
        del lines[1]
        lines[-1] = f"SUITE_DONE nonce|tests={len(lines) - 2}"
    elif corruption == "duplicate":
        lines.insert(2, lines[1])
    elif corruption in {"skipped", "aborted"}:
        lines[1] = lines[1].replace("SUCCESSFUL", corruption.upper())
    elif corruption == "container":
        lines.insert(1, "SUITE_CONTAINER nonce|id=[engine:junit-jupiter],status=FAILED")
    elif corruption == "unfinished":
        del lines[-1]
    else:
        lines = []
    result = score(task, "\n".join(lines) + "\n", exit_code)
    assert not result["complete"] and result["reward"] == 0 and result["passed"] == 0
