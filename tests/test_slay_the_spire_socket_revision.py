"""Version and fail-closed scoring checks for the authorized socket revision."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

PACK = Path(__file__).parents[1] / "benchmarks/slay-the-spire-core"
OLD = "downfall-socket-flow-r2"
NEW = "downfall-socket-flow-r3"


def scorer() -> ModuleType:
    path = PACK / "private/harbor" / NEW / "tests/score.py"
    # Importing from this read-only pack would write a bytecode cache into it.
    module = ModuleType("socket_revision_score")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def observations(module: ModuleType) -> str:
    lines = ["nonce|engine,gl=true"]
    for name, case in module.CASES.items():
        fields = ",".join(f"{key}={value}" for key, value in case["expected"].items())
        lines.append(f"nonce|case,id={name},{fields}")
    return "\n".join([*lines, "nonce|completed=true"])


def test_new_revision_preserves_every_previous_file_except_reviewed_verifier_changes() -> None:
    old = json.loads((PACK / "validation/native-engine" / OLD / "frozen-manifest.json").read_text())
    new = json.loads((PACK / "validation/native-engine" / NEW / "frozen-manifest.json").read_text())
    actual = {
        path.relative_to(PACK / "private/harbor" / NEW).as_posix():
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (PACK / "private/harbor" / NEW).rglob("*") if path.is_file()
    }
    assert actual == new["files"]
    assert set(old["files"]) == set(actual)
    assert {name for name, digest in actual.items() if digest != old["files"][name]} == {
        "tests/Probe.java", "tests/expectations.json", "tests/test.sh",
    }
    assert (PACK / "exams" / f"{NEW}.md").read_bytes() == (
        PACK / "exams" / f"{OLD}.md"
    ).read_bytes()
    shell = PACK / "private/harbor" / NEW / "tests/test.sh"
    assert shell.read_text().replace(
        "# Invoked by the EXIT trap installed below.\n# shellcheck disable=SC2329\n", ""
    ) == (PACK / "private/harbor" / OLD / "tests/test.sh").read_text()
    before = json.loads((PACK / "private/harbor" / OLD / "tests/expectations.json").read_text())
    after = json.loads((PACK / "private/harbor" / NEW / "tests/expectations.json").read_text())
    assert before["failures"] == after["failures"]
    for name, case in after["cases"].items():
        expected = dict(case["expected"])
        assert expected.pop("phase").isdigit()
        assert expected == before["cases"][name]["expected"]


def test_complete_authentic_observations_can_pass() -> None:
    module = scorer()
    result = module.score(observations(module), "nonce", 0)
    assert result["complete"] and result["reward"] == 1 and result["passed"] == 13


def test_git_preserves_the_revised_snapshot_bytes_on_clean_checkouts() -> None:
    source = PACK / "private/harbor" / NEW
    path = source / "environment/project/src/main/java/guardian/GuardianMod.java"
    raw = path.read_bytes()
    assert b"\r\n" in raw
    relative = path.relative_to(PACK.parents[1]).as_posix()
    filtered = subprocess.check_output(
        ["git", "hash-object", f"--path={relative}", str(path)], cwd=PACK.parents[1], text=True
    ).strip()
    expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    assert filtered == expected, "Git attributes must not normalize the frozen upstream bytes"


def test_unchanged_deck_after_a_missed_cancel_click_cannot_pass() -> None:
    module = scorer()
    text = observations(module)
    lines = [line.replace("phase=5", "phase=1") if "id=cancel-gem-mouse," in line else line
             for line in text.splitlines()]
    result = module.score("\n".join(lines), "nonce", 0)
    assert result["complete"] and result["reward"] == 0 and result["passed"] == 12


@pytest.mark.parametrize("corruption", ["nonce", "duplicate", "missing", "exit", "gl"])
def test_invalid_or_incomplete_engine_evidence_never_passes(corruption: str) -> None:
    module = scorer()
    text = observations(module)
    exit_code = 0
    if corruption == "nonce":
        text = text.replace("nonce|", "other|")
    elif corruption == "duplicate":
        text = "nonce|engine,gl=true\n" + text
    elif corruption == "missing":
        text = text.replace("nonce|completed=true", "")
    elif corruption == "exit":
        exit_code = 124
    else:
        text = text.replace("gl=true", "gl=false")
    result = module.score(text, "nonce", exit_code)
    assert result["reward"] == 0
