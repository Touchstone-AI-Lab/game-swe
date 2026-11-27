"""Version and fail-closed scoring checks for the authorized enum r3 revision."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PACK = Path(__file__).parents[1] / "benchmarks/slay-the-spire-core"
VALIDATION = PACK / "validation/native-engine"
OLD = "mts-enum-identity-r2"
NEW = "mts-enum-identity-r3"
ENGINE = "gl=true,listener=com.megacrit.cardcrawl.core.CardCrawlGame,self=true,menu=true,frames=3"
# The execution vehicle is the only reviewed change: r2's standalone loader runner is
# replaced by an in-game observer mod, its driver launches the game, and the scorer
# additionally requires in-game engine evidence. The verifier limit grows for fifteen game
# launches, and the agent image bounds Maven's heap so automatic preparation can build it.
REMOVED = {"tests/Runner.java"}
ADDED = {"tests/observer/Observer.java", "tests/observer/ModTheSpire.json"}
CHANGED = {"tests/run_probe.py", "tests/score.py", "tests/test.sh", "task.toml", "environment/Dockerfile"}


def files(task: str) -> dict[str, str]:
    root = PACK / "private/harbor" / task
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def scorer() -> ModuleType:
    path = PACK / "private/harbor" / NEW / "tests/score.py"
    # Importing from this read-only pack would write a bytecode cache into it.
    module = ModuleType("enum_revision_score")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def cases() -> list[dict[str, Any]]:
    path = PACK / "private/harbor" / NEW / "tests/cases.json"
    loaded: list[dict[str, Any]] = json.loads(path.read_text())
    return loaded


def report(values: dict[str, str] | None = None, *, engine: str = ENGINE) -> dict[str, Any]:
    rows = []
    for case in cases():
        value = (values or {}).get(case["id"], case["value"])
        observation = (
            f"ENUM_ENGINE nonce|id={case['id']},{engine}\n"
            f"ENUM_OBSERVATION nonce|id={case['id']},loaded=true,value={value},error=none\n"
        )
        rows.append({"id": case["id"], "exit": 0, "timeout": False, "observation": observation})
    return {"nonce": "nonce", "fixture_build_exit": 0, "cases": rows}


def score(document: dict[str, Any], exit_code: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = scorer().score(json.dumps(document), "nonce", exit_code)
    return result


def test_revision_keeps_the_exam_assertions_fixtures_and_task_sources() -> None:
    old = json.loads((VALIDATION / OLD / "frozen-manifest.json").read_text())["files"]
    new = json.loads((VALIDATION / NEW / "frozen-manifest.json").read_text())
    actual = files(NEW)
    assert actual == new["files"]
    assert new["supersedes"] == OLD
    assert new["previous_manifest_sha256"] == hashlib.sha256(
        (VALIDATION / OLD / "frozen-manifest.json").read_bytes()
    ).hexdigest()
    assert set(old) - set(actual) == REMOVED
    assert set(actual) - set(old) == ADDED
    assert {name for name in set(old) & set(actual) if old[name] != actual[name]} == CHANGED
    assert (PACK / "exams" / f"{NEW}.md").read_bytes() == (PACK / "exams" / f"{OLD}.md").read_bytes()
    assert (PACK / "private/harbor" / NEW / "instruction.md").read_bytes() == (
        PACK / "exams" / f"{NEW}.md"
    ).read_bytes()
    assert len(cases()) == 15


def test_revision_changes_only_the_verifier_limit_in_the_task_configuration() -> None:
    import tomllib

    before = tomllib.loads((PACK / "private/harbor" / OLD / "task.toml").read_text())
    after = tomllib.loads((PACK / "private/harbor" / NEW / "task.toml").read_text())
    assert after["verifier"].pop("timeout_sec") > before["verifier"].pop("timeout_sec")
    assert after == before


def test_agent_image_recipe_only_bounds_the_maven_heap() -> None:
    before = (PACK / "private/harbor" / OLD / "environment/Dockerfile").read_text()
    after = (PACK / "private/harbor" / NEW / "environment/Dockerfile").read_text()
    assert after == before.replace("RUN mvn -B -o", "RUN MAVEN_OPTS=-Xmx512m mvn -B -o", 1) != before


def test_complete_in_game_observations_can_pass() -> None:
    result = score(report())
    assert result["complete"] and result["reward"] == 1 and result["passed"] == 15


def test_the_recorded_starter_values_fail_exactly_the_intended_cases() -> None:
    controls = json.loads((VALIDATION / NEW / "author-controls.json").read_text())
    base = next(row for row in controls["matrix_results"] if row["variant"] == "base")
    wrong = {name: "wrong" for name in base["failed_case_ids"]}
    result = score(report(wrong))
    assert result["complete"] and result["reward"] == 0
    assert sorted(row["id"] for row in result["cases"] if not row["passed"]) == base["failed_case_ids"]


@pytest.mark.parametrize("engine", [
    ENGINE.replace("gl=true", "gl=false"),
    ENGINE.replace("menu=true", "menu=false"),
    ENGINE.replace("self=true", "self=false"),
    ENGINE.replace("com.megacrit.cardcrawl.core.CardCrawlGame", "enumobserver.Fake"),
    "gl=true",
])
def test_an_observation_without_launched_game_evidence_is_incomplete(engine: str) -> None:
    result = score(report(engine=engine))
    assert not result["complete"] and result["reward"] == 0 and result["passed"] == 0


@pytest.mark.parametrize("corruption", ["nonce", "exit", "timeout", "order", "missing", "duplicate", "build"])
def test_invalid_or_incomplete_evidence_never_passes(corruption: str) -> None:
    document = report()
    exit_code = 0
    rows = document["cases"]
    if corruption == "nonce":
        rows[3]["observation"] = rows[3]["observation"].replace("nonce|", "other|")
    elif corruption == "exit":
        exit_code = 1
    elif corruption == "timeout":
        rows[0].update(exit=124, timeout=True)
    elif corruption == "order":
        rows[0], rows[1] = rows[1], rows[0]
    elif corruption == "missing":
        rows[5]["observation"] = rows[5]["observation"].split("\n", 1)[0] + "\n"
    elif corruption == "duplicate":
        rows[2]["observation"] += rows[2]["observation"]
    else:
        document["fixture_build_exit"] = 1
    result = score(document, exit_code)
    assert not result["complete"] and result["reward"] == 0


def test_git_preserves_the_revised_snapshot_bytes_on_clean_checkouts() -> None:
    source = PACK / "private/harbor" / NEW
    path = source / "solution/after/src/main/java/com/evacipated/cardcrawl/modthespire/Patcher.java"
    raw = path.read_bytes()
    assert b"\r\n" in raw
    relative = path.relative_to(PACK.parents[1]).as_posix()
    filtered = subprocess.check_output(
        ["git", "hash-object", f"--path={relative}", str(path)], cwd=PACK.parents[1], text=True
    ).strip()
    expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    assert filtered == expected, "Git attributes must not normalize the frozen upstream bytes"


@pytest.mark.parametrize("name", ["pom.xml", ".editorconfig", "mvnw.cmd"])
def test_the_starter_keeps_r2s_stored_crlf_bytes(name: str) -> None:
    # The upstream snapshot's own `text=auto` governs this tree; r3 stores the same raw
    # blobs as r2 so that a clean checkout reproduces the manifest-bound bytes.
    old = PACK / "private/harbor" / OLD / "environment/project" / name
    new = PACK / "private/harbor" / NEW / "environment/project" / name
    raw = new.read_bytes()
    assert b"\r\n" in raw and raw == old.read_bytes()
    staged = {
        path: subprocess.check_output(
            ["git", "ls-files", "-s", "--", path.relative_to(PACK.parents[1]).as_posix()],
            cwd=PACK.parents[1], text=True,
        ).split()[1]
        for path in (old, new)
    }
    assert staged[old] == staged[new] == hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
