from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_slay_the_spire.catalog import SlayTheSpireCatalog
from rhenium_slay_the_spire.evaluator import SlayTheSpireEvaluator
from rhenium_slay_the_spire.native import (
    NATIVE_RUNTIME_ID,
    NATIVE_RUNTIME_KEY,
    NativeDocker,
    SlayTheSpireNativeRuntimeBuilder,
    task_config,
)
from spire_fixtures import PACK, catalog_task, write_pack

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeCatalog, RuntimeSpec

NATIVE_TASK = "basemod-phase-transitions-r1"
VERIFIER_IMAGE = "sha256:" + "b" * 64
JAR_BYTES = b"licensed game stand-in"
JAR_SHA256 = hashlib.sha256(JAR_BYTES).hexdigest()
DEPOT = {"kind": "steam-depots", "appId": 646570, "depots": [{"id": 646571, "manifest": "1"}]}

FAKE_PREPARE = f"""
import argparse, json
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--game-jar", type=Path)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
assert args.game_jar.read_bytes() == {JAR_BYTES!r}
args.output.mkdir(parents=True)
print("PREPARE build_sdk_offline.py", flush=True)
agent = "sha256:" + "c" * 64
rows = [{{"task": "{NATIVE_TASK}", "agent_image": agent, "verifier_image": "{VERIFIER_IMAGE}"}}]
receipt = {{"game_sha256": "{JAR_SHA256}", "recipe_manifest_sha256": "r", "tasks": rows}}
(args.output / "preparation.json").write_text(json.dumps(receipt))
"""

TASK_TOML = f"""schema_version = "1.4"
artifacts = [{{source = "/app/mod/src/main/java"}}]
[environment]
docker_image = "sha256:{"c" * 64}"
workdir = "/app/mod"
network_mode = "no-network"
[verifier]
timeout_sec = 1200
environment_mode = "separate"
[verifier.environment]
docker_image = "sha256:{"d" * 64}"
workdir = "/tests"
network_mode = "no-network"
cpus = 2
memory_mb = 4608
"""


def write_native_pack(root: Path) -> Path:
    pack = write_pack(root, [catalog_task()])
    native = {**catalog_task(NATIVE_TASK), "required_files": ["project/pom.xml"]}
    catalog = json.loads((pack / "catalog.json").read_text(encoding="utf-8"))
    catalog["tasks"].append(native)
    (pack / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    harbor = pack / "private" / "harbor" / NATIVE_TASK
    project = harbor / "environment" / "project"
    (project / "src" / "main" / "java").mkdir(parents=True)
    (project / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    (project / "src" / "main" / "java" / "Mod.java").write_text("class Mod {}\n", encoding="utf-8")
    (harbor / "environment" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    exam = "# Native regressions\n\nRepair the mod.\n"
    (pack / "exams" / f"{NATIVE_TASK}.md").write_text(exam, encoding="utf-8")
    (harbor / "instruction.md").write_text(exam, encoding="utf-8")
    (harbor / "task.toml").write_text(TASK_TOML, encoding="utf-8")
    (harbor / "tests").mkdir()
    (harbor / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (harbor / "solution" / "after").mkdir(parents=True)
    (harbor / "solution" / "solve.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    runtime = pack / "private" / "native-runtime"
    runtime.mkdir(parents=True)
    (runtime / "prepare.py").write_text(FAKE_PREPARE, encoding="utf-8")
    (runtime / "game-input.json").write_text(
        json.dumps(
            {
                "provider": "steam",
                "source": {**DEPOT, "expectedFiles": ["desktop-1.0.jar"]},
                "expected_sha256": {"desktop-1.0.jar": JAR_SHA256},
            }
        ),
        encoding="utf-8",
    )
    runtimes = json.loads((pack / "runtimes.json").read_text(encoding="utf-8"))
    runtimes["runtimes"].append(
        {
            "id": NATIVE_RUNTIME_ID,
            "name": "native",
            "version": "Steam build 1",
            "provider": "steam",
            "restricted": True,
            "host_platforms": ["linux-x64"],
            "source": {
                **DEPOT,
                "expectedFiles": ["desktop-1.0.jar"],
                "sha256": {"desktop-1.0.jar": JAR_SHA256},
            },
        }
    )
    runtimes["task_bindings"][NATIVE_TASK] = [NATIVE_RUNTIME_ID]
    (pack / "runtimes.json").write_text(json.dumps(runtimes), encoding="utf-8")
    return pack


class FakeDocker(NativeDocker):
    def __init__(self, result: dict[str, Any] | None = None, build_exit: int = 0, run_exit: int = 0):
        self.images = {VERIFIER_IMAGE}
        self.commands: list[list[str]] = []
        self.result = result
        self.build_exit = build_exit
        self.run_exit = run_exit
        self.removed: list[str] = []

    def run(self, arguments: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        del timeout
        self.commands.append(arguments)
        if arguments[:2] == ["image", "inspect"]:
            found = arguments[2] in self.images
            return subprocess.CompletedProcess(
                arguments, 0 if found else 1, arguments[2] if found else "", ""
            )
        if arguments[:2] == ["image", "rm"]:
            self.images.discard(arguments[2])
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[0] == "version":
            return subprocess.CompletedProcess(arguments, 0, "29.0\n", "")
        if arguments[0] == "run":
            return subprocess.CompletedProcess(arguments, self.run_exit, "", "")
        if arguments[0] == "cp":
            verifier = Path(arguments[2])
            verifier.mkdir()
            (verifier / "build-exit.txt").write_text(f"{self.build_exit}\n")
            if self.result is not None:
                (verifier / "result.json").write_text(json.dumps(self.result))
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[:2] == ["rm", "-f"]:
            self.removed.append(arguments[2])
            return subprocess.CompletedProcess(arguments, 0, "", "")
        raise AssertionError(arguments)


def context_for(pack: Path, tmp_path: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=pack.parents[1],
        pack_root=pack,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )


def native_spec(pack: Path) -> RuntimeSpec:
    return next(
        spec for spec in RuntimeCatalog.load(pack, "runtimes.json").runtimes if spec.id == NATIVE_RUNTIME_ID
    )


def prepared(
    tmp_path: Path,
) -> tuple[Path, SlayTheSpireNativeRuntimeBuilder, RuntimeSpec, RuntimeArtifact, FakeDocker]:
    pack = write_native_pack(tmp_path / "repo" / "benchmarks" / "pack")
    docker = FakeDocker()
    builder = SlayTheSpireNativeRuntimeBuilder(
        context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack), docker
    )
    spec = native_spec(pack)
    source = tmp_path / "source"
    source.mkdir()
    (source / "desktop-1.0.jar").write_bytes(JAR_BYTES)
    progress: list[tuple[int, str]] = []
    artifact = builder.prepare(spec, source, tmp_path / "out", progress=lambda v, p: progress.append((v, p)))
    assert progress[-1][0] == 100
    return pack, builder, spec, artifact, docker


def test_prepare_records_the_verifier_image_and_limits_and_verify_accepts_it(tmp_path: Path) -> None:
    _pack, builder, spec, artifact, docker = prepared(tmp_path)
    entry = artifact.metadata["tasks"][NATIVE_TASK]
    assert entry == {
        "verifierImage": VERIFIER_IMAGE,
        "artifact": "/app/mod/src/main/java",
        "artifactRelative": "src/main/java",
        "cpus": 2.0,
        "memoryMb": 4608,
        "timeoutSec": 1200.0,
    }
    assert artifact.runtime_key == NATIVE_RUNTIME_KEY and artifact.metadata["gameSha256"] == JAR_SHA256
    assert builder.verify(spec, artifact)["available"] is True
    docker.images.clear()
    assert builder.verify(spec, artifact)["available"] is False
    docker.images.add(VERIFIER_IMAGE)
    builder.prune(spec, artifact)
    assert VERIFIER_IMAGE not in docker.images


def test_prepare_refuses_game_bytes_that_differ_from_the_pinned_build(tmp_path: Path) -> None:
    pack = write_native_pack(tmp_path / "repo" / "benchmarks" / "pack")
    builder = SlayTheSpireNativeRuntimeBuilder(
        context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack), FakeDocker()
    )
    source = tmp_path / "source"
    source.mkdir()
    (source / "desktop-1.0.jar").write_bytes(b"another build")
    with pytest.raises(RuntimeError, match="does not match the pinned build"):
        builder.prepare(native_spec(pack), source, tmp_path / "out", progress=lambda *_: None)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"provider": "container"}, "restricted Steam provider"),
        ({"source": {**DEPOT, "depots": [{"id": 646571, "manifest": "2"}]}}, "depots does not match"),
        (
            {
                "source": {
                    **DEPOT,
                    "expectedFiles": ["desktop-1.0.jar"],
                    "sha256": {"desktop-1.0.jar": "0" * 64},
                }
            },
            "digest",
        ),
    ],
)
def test_sources_other_than_the_recorded_depot_are_refused(
    tmp_path: Path, change: dict[str, Any], message: str
) -> None:
    pack = write_native_pack(tmp_path / "repo" / "benchmarks" / "pack")
    builder = SlayTheSpireNativeRuntimeBuilder(
        context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack), FakeDocker()
    )
    spec = native_spec(pack).model_copy(update=change)
    assert builder.doctor(spec)["available"] is False
    with pytest.raises(ValueError, match=message):
        builder._source_policy(spec)


def test_the_real_pack_runtime_pins_the_recorded_steam_depot_and_binds_every_native_task(
    tmp_path: Path,
) -> None:
    catalog = SlayTheSpireCatalog.load(PACK)
    builder = SlayTheSpireNativeRuntimeBuilder(context_for(PACK, tmp_path), catalog, FakeDocker())
    spec = native_spec(PACK)
    record = json.loads((PACK / "private/native-runtime/game-input.json").read_text(encoding="utf-8"))
    assert builder._source_policy(spec) == record["expected_sha256"]["desktop-1.0.jar"]
    bindings = RuntimeCatalog.load(PACK, "runtimes.json").task_bindings
    assert {task for task, ids in bindings.items() if ids == (NATIVE_RUNTIME_ID,)} == {
        task.id for task in catalog.tasks if task.game_backed
    }


def test_the_enum_r3_task_is_prepared_and_run_from_its_own_harbor_limits(tmp_path: Path) -> None:
    catalog = SlayTheSpireCatalog.load(PACK)
    builder = SlayTheSpireNativeRuntimeBuilder(context_for(PACK, tmp_path), catalog, FakeDocker())
    prepared_ids = {task.id for task in builder.tasks}
    assert "mts-enum-identity-r3" in prepared_ids and "mts-enum-identity-r2" not in prepared_ids
    enum = next(task for task in catalog.tasks if task.id == "mts-enum-identity-r3")
    config = task_config(PACK, enum)
    assert config["artifact"] == "/app/modthespire/src/main/java"
    assert config["artifactRelative"] == "src/main/java"
    assert config["cpus"] == 2.0 and config["memoryMb"] == 4608
    # Fifteen bounded game launches follow the offline build inside one verifier.
    assert config["timeoutSec"] == 2700.0


def evaluate(
    tmp_path: Path, result: dict[str, Any] | None, build_exit: int = 0, prepared_runtime: bool = True,
    run_exit: int = 0,
) -> dict[str, Any]:
    pack, _builder, _spec, artifact, _docker = prepared(tmp_path)
    evaluator = SlayTheSpireEvaluator(context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack))
    evaluator.native = docker = FakeDocker(result, build_exit, run_exit)
    task = next(task for task in evaluator.catalog.tasks if task.native_runtime)
    submission = tmp_path / "submission"
    (submission / "project" / "src" / "main" / "java").mkdir(parents=True)
    (submission / "project" / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    runtimes = {NATIVE_RUNTIME_KEY: artifact} if prepared_runtime else {}
    report = evaluator.evaluate(submission, task, "full", runtimes)
    run = next((command for command in docker.commands if command[0] == "run"), None)
    if run is not None:
        assert "--network" in run and run[run.index("--network") + 1] == "none"
        assert "--pull=never" in run
        assert "JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2" in run
        assert docker.removed == [run[run.index("--name") + 1]]
    return report


def verifier_result(passed: int, expected: int = 3, complete: bool = True) -> dict[str, Any]:
    cases = [{"id": f"case-{i}", "passed": i < passed} for i in range(expected)]
    return {
        "complete": complete,
        "passed": passed,
        "failed": expected - passed,
        "expected": expected,
        "reward": int(complete and passed == expected),
        "cases": cases,
    }


def test_a_complete_all_passing_native_run_scores_full_marks(tmp_path: Path) -> None:
    report = evaluate(tmp_path, verifier_result(3))
    assert report["passed"] is True and report["complete"] is True and report["score"] == 100.0
    assert report["runtime"]["caseOutcomes"] == {"case-0": True, "case-1": True, "case-2": True}


def test_a_complete_partial_native_run_fails_without_suite_points(tmp_path: Path) -> None:
    report = evaluate(tmp_path, verifier_result(1))
    assert report["complete"] is True and report["passed"] is False and report["score"] == 10.0
    assert report["checks"][-1]["message"] == "1/3 native engine cases passed"


def test_an_unsuccessful_verifier_exit_cannot_pass(tmp_path: Path) -> None:
    report = evaluate(tmp_path, verifier_result(3), run_exit=1)
    assert report["complete"] is False and report["passed"] is False


@pytest.mark.parametrize(
    ("result", "build_exit"),
    [(verifier_result(3, complete=False), 0), (verifier_result(3), 1), (None, 0)],
)
def test_a_reward_alone_never_counts_without_a_complete_build_and_observation(
    tmp_path: Path, result: dict[str, Any] | None, build_exit: int
) -> None:
    report = evaluate(tmp_path, result, build_exit)
    assert report["complete"] is False and report["passed"] is False


def test_an_unprepared_native_runtime_is_incomplete_and_names_the_prepare_command(tmp_path: Path) -> None:
    report = evaluate(tmp_path, verifier_result(3), prepared_runtime=False)
    assert report["complete"] is False and report["runtime"]["status"] == "unavailable"
    assert NATIVE_RUNTIME_KEY in report["runtime_log"]


def test_preparation_inside_the_repository_is_refused(tmp_path: Path) -> None:
    pack = write_native_pack(tmp_path / "repo" / "benchmarks" / "pack")
    builder = SlayTheSpireNativeRuntimeBuilder(
        context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack), FakeDocker()
    )
    source = tmp_path / "source"
    source.mkdir()
    (source / "desktop-1.0.jar").write_bytes(JAR_BYTES)
    with pytest.raises(RuntimeError, match="outside the clone"):
        builder.prepare(
            native_spec(pack), source, tmp_path / "repo" / ".rhenium" / "cache", progress=lambda *_: None
        )


def test_prune_never_deletes_an_artifact_location_outside_core_cache(tmp_path: Path) -> None:
    _pack, builder, spec, artifact, _docker = prepared(tmp_path)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    marker = unrelated / "keep.txt"
    marker.write_text("keep")
    builder.prune(spec, artifact.model_copy(update={"location": str(unrelated)}))
    assert marker.read_text() == "keep"


def test_prepare_deadline_applies_to_a_silent_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rhenium_slay_the_spire import native

    pack = write_native_pack(tmp_path / "repo" / "benchmarks" / "pack")
    script = pack / "private/native-runtime/prepare.py"
    script.write_text("import time\ntime.sleep(30)\n")
    source = tmp_path / "source"
    source.mkdir()
    (source / "desktop-1.0.jar").write_bytes(JAR_BYTES)
    monkeypatch.setattr(native, "_PREPARE_TIMEOUT", 0.1)
    builder = SlayTheSpireNativeRuntimeBuilder(
        context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack), FakeDocker()
    )
    with pytest.raises(RuntimeError, match="private preparation diagnostics") as error:
        builder.prepare(native_spec(pack), source, tmp_path / "out", progress=lambda *_: None)
    assert str(pack) not in str(error.value) and str(source) not in str(error.value)
    assert "TimeoutExpired" in (tmp_path / "out/prepare.log").read_text()


def test_prepare_keeps_recipe_output_and_paths_out_of_public_errors(tmp_path: Path) -> None:
    pack = write_native_pack(tmp_path / "repo" / "benchmarks" / "pack")
    private_detail = str(tmp_path / "private-operator-source")
    (pack / "private/native-runtime/prepare.py").write_text(
        f"print({private_detail!r}, flush=True)\nraise SystemExit(1)\n"
    )
    source = tmp_path / "source"
    source.mkdir()
    (source / "desktop-1.0.jar").write_bytes(JAR_BYTES)
    builder = SlayTheSpireNativeRuntimeBuilder(
        context_for(pack, tmp_path), SlayTheSpireCatalog.load(pack), FakeDocker()
    )
    with pytest.raises(RuntimeError, match="private preparation diagnostics") as error:
        builder.prepare(native_spec(pack), source, tmp_path / "out", progress=lambda *_: None)
    assert private_detail not in str(error.value) and str(tmp_path / "out") not in str(error.value)
    log = tmp_path / "out/prepare.log"
    assert private_detail in log.read_text() and log.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("malformation", ["duplicate", "contradiction", "string-bool", "bad-count"])
def test_malformed_native_case_results_fail_closed(tmp_path: Path, malformation: str) -> None:
    result = verifier_result(3)
    if malformation == "duplicate":
        result["cases"][1]["id"] = result["cases"][0]["id"]
    elif malformation == "contradiction":
        result["cases"][1]["passed"] = False
    elif malformation == "string-bool":
        result["cases"][1]["passed"] = "true"
    else:
        result["expected"] = "invalid"
    report = evaluate(tmp_path, result)
    assert report["complete"] is False and report["passed"] is False
