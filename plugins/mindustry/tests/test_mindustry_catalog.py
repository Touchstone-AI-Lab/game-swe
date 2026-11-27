from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mindustry_fixtures import PACK, catalog_task, load_module, sample_pack_fixture, write_pack  # noqa: F401
from pydantic import ValidationError
from rhenium_mindustry.catalog import (
    HARBOR_INSTRUCTION_HEADER,
    BuildSpec,
    MindustryCatalog,
    MindustryTask,
    task_manifest,
)


def test_sample_pack_loads_and_freezes_the_case_set(sample_pack: Path) -> None:
    catalog = MindustryCatalog.load(sample_pack)
    (task,) = catalog.tasks
    assert task.server_cases[:2] == ("the server answers", "the command reports two")
    assert task.starter_name == "mindustry" and task.container_destination == "/app/mindustry"
    assert task.build.source_roots == ("core/src", "server/src")
    assert "Fix the count command" in task.authored_prompt
    manifest = json.loads(
        (sample_pack / "private/harbor" / task.id / "tests/task.json").read_text(encoding="utf-8")
    )
    assert manifest == task_manifest(task)
    assert manifest["build"]["extraSources"] == [
        "annotations/src/main/java/mindustry/annotations/Annotations.java"
    ]


def test_task_json_drift_is_rejected(sample_pack: Path) -> None:
    manifest = sample_pack / "private/harbor/sample-count-command/tests/task.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["serverCases"].append("forged")
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="drifted"):
        MindustryCatalog.load(sample_pack)


def test_missing_suite_or_reference_is_rejected(sample_pack: Path) -> None:
    suite = (
        sample_pack
        / "private/harbor/sample-count-command/tests/suite/rhenium/mindustry/grader/TaskSuite.java"
    )
    suite.unlink()
    with pytest.raises(ValueError, match="TaskSuite"):
        MindustryCatalog.load(sample_pack)


def test_empty_reference_is_rejected(sample_pack: Path) -> None:
    after = sample_pack / "private/harbor/sample-count-command/solution/after"
    for path in sorted(after.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    after.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="reference"):
        MindustryCatalog.load(sample_pack)


def test_case_contracts_must_match_and_carry_roles(sample_pack: Path) -> None:
    contracts = sample_pack / "private/harbor/sample-count-command/validation/case-contracts.tsv"
    original = contracts.read_text(encoding="utf-8")
    contracts.write_text("case\tlayer\trole\tpublic_report\nthe server answers\tserver\tsentinel\tx\n")
    with pytest.raises(ValueError, match="case contracts"):
        MindustryCatalog.load(sample_pack)
    contracts.write_text(original.replace("\tpreserved\t", "\ttarget\t"), encoding="utf-8")
    with pytest.raises(ValueError, match="preserved"):
        MindustryCatalog.load(sample_pack)
    contracts.write_text(original.replace("\tsentinel\t", "\tsmoke\t"), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown role"):
        MindustryCatalog.load(sample_pack)


def test_exam_must_match_instruction(sample_pack: Path) -> None:
    (sample_pack / "exams/sample-count-command.md").write_text("# Different\n", encoding="utf-8")
    with pytest.raises(ValueError, match="drifted from Harbor instruction"):
        MindustryCatalog.load(sample_pack)


def test_license_file_must_exist(sample_pack: Path) -> None:
    (sample_pack / "private/harbor/sample-count-command/environment/mindustry/LICENSE").unlink()
    with pytest.raises(ValueError, match="license"):
        MindustryCatalog.load(sample_pack)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda t: t.update(required_files=["core/src/mindustry/Vars.java"]), "below mindustry/"),
        (lambda t: t.update(server_cases=["a", "a"]), "unique"),
        (lambda t: t.update(server_cases=[" a"]), "whitespace"),
        (lambda t: t["upstream"].update(release_tag="v160.5"), "pinned v159.7"),
        (lambda t: t["upstream"].update(fix_commits=[]), "at least 1"),
        (lambda t: t["upstream"].update(fix_commits=["abc"]), "full lower-case"),
        (lambda t: t["upstream"].update(license_spdx="MIT"), "GPL-3.0"),
        (lambda t: t.update(build={"tool": "gradle"}), "mindustry-source"),
    ],
)
def test_task_model_rules(mutation: Callable[[dict[str, Any]], object], message: str) -> None:
    task = catalog_task("rules")
    mutation(task)
    with pytest.raises(ValidationError, match=message):
        MindustryTask.model_validate(task)


def test_build_spec_rules() -> None:
    with pytest.raises(ValidationError, match="normalized"):
        BuildSpec(tool="mindustry-source", source_roots=("../core/src",))
    with pytest.raises(ValidationError, match="unique"):
        BuildSpec(tool="mindustry-source", source_roots=("core/src", "core/src"))
    with pytest.raises(ValidationError, match="at least one"):
        BuildSpec(tool="mindustry-source", source_roots=())
    assert BuildSpec(tool="mindustry-source").java_release == 17


def test_catalog_rejects_unknown_id(tmp_path: Path) -> None:
    pack = write_pack(tmp_path / "bad", [catalog_task("x")], catalog_id="rhenium-mindustry-v1")
    with pytest.raises(ValidationError, match="catalog id"):
        MindustryCatalog.load(pack)


def test_materialize_header_matches_catalog_constant() -> None:
    module = load_module(PACK / "private" / "harbor" / "scripts" / "materialize.py", "mindustry_header")
    assert module.INSTRUCTION_HEADER == HARBOR_INSTRUCTION_HEADER
