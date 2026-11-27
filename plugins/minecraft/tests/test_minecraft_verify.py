from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from pack_fixtures import PACK

VERIFY = PACK / "private" / "harbor" / "harness" / "verify.py"


@pytest.fixture(scope="module")
def verify() -> ModuleType:
    spec = importlib.util.spec_from_file_location("minecraft_verify", VERIFY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_payload_extraction_requires_exactly_one_marker(verify: ModuleType) -> None:
    log = '\x1b[32m[12:00:00 INFO]: MINECRAFT_RESULT {"a":1}\x1b[0m\nplain line\n'
    assert verify.extract_payloads(log) == ['{"a":1}']
    forged = log + '[12:00:01 INFO]: [Candidate] MINECRAFT_RESULT {"a":2}\n'
    assert len(verify.extract_payloads(forged)) == 2
    assert verify.extract_payloads("nothing here") == []


def test_junit_reports_are_parsed_per_case(verify: ModuleType, tmp_path: Path) -> None:
    gradle = tmp_path / "TEST-dev.sample.CounterTest.xml"
    gradle.write_text(
        """<?xml version="1.0"?>
<testsuite name="dev.sample.CounterTest" tests="4">
  <testcase name="counts" classname="dev.sample.CounterTest"/>
  <testcase name="fails" classname="dev.sample.CounterTest">
    <failure message="expected 2">trace</failure>
  </testcase>
  <testcase name="errors" classname="dev.sample.CounterTest"><error type="NPE"/></testcase>
  <testcase name="skipped" classname="dev.sample.CounterTest"><skipped/></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    duplicate = tmp_path / "TEST-again.xml"
    duplicate.write_text(
        '<testsuite><testcase name="counts" classname="dev.sample.CounterTest"/></testsuite>',
        encoding="utf-8",
    )
    cases, duplicates = verify.parse_junit_reports([gradle])
    outcomes = {case["name"]: (case["passed"], case["message"]) for case in cases}
    assert outcomes["dev.sample.CounterTest.counts"] == (True, "ok")
    assert outcomes["dev.sample.CounterTest.fails"] == (False, "expected 2")
    assert outcomes["dev.sample.CounterTest.errors"] == (False, "NPE")
    assert "dev.sample.CounterTest.skipped" not in outcomes and duplicates == []
    cases, duplicates = verify.parse_junit_reports([gradle, duplicate])
    assert duplicates == ["dev.sample.CounterTest.counts"]
    assert all(case["name"] != "dev.sample.CounterTest.counts" for case in cases)


def test_case_set_check(verify: ModuleType) -> None:
    observed = [{"name": "a", "passed": True}, {"name": "b", "passed": False}]
    assert verify.check_case_set(observed, ["a", "b"]) is None
    assert "missing" in verify.check_case_set(observed, ["a", "b", "c"])
    assert "unexpected" in verify.check_case_set(observed, ["a"])
    assert "duplicate" in verify.check_case_set(observed + [{"name": "a", "passed": True}], ["a", "b"])


def test_shape_validation(verify: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Main.java").write_text("class Main {}\n")
    assert verify.validate_shape(root, ["src/Main.java"]) == []
    (root / "Evil.jar").write_bytes(b"PK")
    (root / "build").mkdir()
    (root / "build" / "Fine.jar").write_bytes(b"PK")
    problems = verify.validate_shape(root, ["src/Main.java", "missing.txt"])
    assert any("Evil.jar" in p for p in problems) and not any("Fine.jar" in p for p in problems)
    assert any("missing.txt" in p for p in problems)


def test_frozen_paths_are_restored_from_the_starter(verify: ModuleType, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    frozen = tmp_path / "frozen"
    (workspace / "src" / "test").mkdir(parents=True)
    (workspace / "src" / "test" / "Tampered.java").write_text("tampered")
    (workspace / "build.gradle.kts").write_text("tampered")
    (workspace / "pom.xml").write_text("added by the submission")
    (frozen / "src" / "test").mkdir(parents=True)
    (frozen / "src" / "test" / "Upstream.java").write_text("upstream")
    (frozen / "build.gradle.kts").write_text("upstream build")
    restored = verify.restore_frozen_paths(workspace, frozen, ["build.gradle.kts", "pom.xml", "src/test"])
    assert restored == ["build.gradle.kts", "src/test"]
    assert (workspace / "build.gradle.kts").read_text() == "upstream build"
    assert not (workspace / "pom.xml").exists()
    assert not (workspace / "src" / "test" / "Tampered.java").exists()
    assert (workspace / "src" / "test" / "Upstream.java").read_text() == "upstream"


def test_grader_plugin_yml_depends_on_harness_and_candidate(verify: ModuleType) -> None:
    text = verify.grader_plugin_yml("Sample")
    assert "depend: [GcbHarness, Sample]" in text
    assert "main: io.gamecodebench.grader.GraderPlugin" in text
    assert verify.plugin_yml_name("name: 'Sample'\nmain: x\n") == "Sample"
    assert verify.plugin_yml_name("main: x\n") is None


def test_shape_allows_wrapper_bootstrap_jars(verify: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    (root / "gradle" / "wrapper").mkdir(parents=True)
    (root / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"PK")
    assert verify.validate_shape(root, []) == []
    (root / "gradle" / "other.jar").write_bytes(b"PK")
    assert any("other.jar" in p for p in verify.validate_shape(root, []))


def test_seed_plugin_data_copies_data_folders_and_rejects_jars(verify: ModuleType, tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    (seed / "Sample").mkdir(parents=True)
    (seed / "Sample" / "config.yml").write_text("a: 1\n", encoding="utf-8")
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    assert verify.seed_plugin_data(tmp_path / "missing", plugins) == []
    assert verify.seed_plugin_data(seed, plugins) == ["Sample"]
    assert (plugins / "Sample" / "config.yml").read_text(encoding="utf-8") == "a: 1\n"
    (seed / "Sample" / "extra.jar").write_bytes(b"PK")
    with pytest.raises(verify.EnvironmentFailure):
        verify.seed_plugin_data(seed, plugins)
