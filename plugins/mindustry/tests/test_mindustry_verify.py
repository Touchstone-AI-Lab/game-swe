from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest
from mindustry_fixtures import HARNESS, load_module


@pytest.fixture(scope="module")
def verify() -> ModuleType:
    return load_module(HARNESS / "verify.py", "mindustry_verify")


def test_payload_extraction_requires_the_marker(verify: ModuleType) -> None:
    log = '\x1b[32m[12:00:00] [I] MINDUSTRY_RESULT {"a":1}\x1b[0m\nplain line\n'
    assert verify.extract_payloads(log) == ['{"a":1}']
    forged = log + 'MINDUSTRY_RESULT {"a":2}\n'
    assert len(verify.extract_payloads(forged)) == 2
    assert verify.extract_payloads("nothing here") == []


def test_envelope_requires_one_payload_nonce_and_exact_cases(verify: ModuleType) -> None:
    nonce = "n" * 32
    cases = [{"name": "b", "passed": False, "message": "x"}, {"name": "a", "passed": True, "message": "ok"}]
    good = json.dumps({"schema": 1, "nonce": nonce, "game": "159.7", "cases": cases})
    result = verify.parse_envelope([good], nonce, ["a", "b"])
    assert result["status"] == "failed"
    assert [case["name"] for case in result["cases"]] == ["a", "b"]
    assert verify.parse_envelope([good, good], nonce, ["a", "b"])["status"] == "incomplete"
    assert "nonce" in verify.parse_envelope([good], "other", ["a", "b"])["problem"]
    assert "missing" in verify.parse_envelope([good], nonce, ["a", "b", "c"])["problem"]
    assert "unexpected" in verify.parse_envelope([good], nonce, ["a"])["problem"]
    assert verify.parse_envelope(["not json"], nonce, ["a"])["status"] == "incomplete"
    fatal = json.dumps({"schema": 1, "nonce": nonce, "fatal": "case hung", "cases": []})
    assert "case hung" in verify.parse_envelope([fatal], nonce, ["a"])["problem"]
    passed = good.replace('"passed": false', '"passed": true')
    assert verify.parse_envelope([passed], nonce, ["a", "b"])["status"] == "passed"


def test_case_set_check(verify: ModuleType) -> None:
    observed = [{"name": "a", "passed": True}, {"name": "b", "passed": False}]
    assert verify.check_case_set(observed, ["a", "b"]) is None
    assert "missing" in verify.check_case_set(observed, ["a", "b", "c"])
    assert "unexpected" in verify.check_case_set(observed, ["a"])
    assert "duplicate" in verify.check_case_set(observed + [{"name": "a", "passed": True}], ["a", "b"])


def test_shape_validation(verify: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "mindustry"
    (root / "core" / "src").mkdir(parents=True)
    (root / "core" / "src" / "Main.java").write_text("class Main {}\n")
    assert verify.validate_shape(root) == []
    (root / "core" / "Evil.jar").write_bytes(b"PK")
    (root / "link").symlink_to("/etc/hostname")
    problems = verify.validate_shape(root)
    assert any("Evil.jar" in p for p in problems) and any("symbolic" in p for p in problems)


def test_source_files_cover_roots_and_extra_sources(verify: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "mindustry"
    (root / "core" / "src" / "a").mkdir(parents=True)
    (root / "core" / "src" / "a" / "A.java").write_text("class A {}\n")
    (root / "core" / "src" / "a" / "notes.txt").write_text("x\n")
    (root / "server" / "src").mkdir(parents=True)
    (root / "server" / "src" / "S.java").write_text("class S {}\n")
    (root / "annotations").mkdir()
    (root / "annotations" / "Annotations.java").write_text("class Annotations {}\n")
    build = {"sourceRoots": ["core/src", "server/src"], "extraSources": ["annotations/Annotations.java"]}
    assert verify.source_files(root, build) == [
        "annotations/Annotations.java",
        "core/src/a/A.java",
        "server/src/S.java",
    ]
    with pytest.raises(verify.SubmissionFailure, match="source root"):
        verify.source_files(root, {**build, "sourceRoots": ["missing/src"]})
    with pytest.raises(verify.SubmissionFailure, match="required source"):
        verify.source_files(root, {**build, "extraSources": ["missing.java"]})


def test_strip_ansi(verify: ModuleType) -> None:
    assert verify.strip_ansi("\x1b[1m\x1b[90mtext\x1b[0m") == "text"
