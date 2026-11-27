from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_authoring.models import ValidationReport
from rhenium_authoring.publisher import PackPublisher


def test_publisher_refuses_a_dst_synth_pack_the_plugin_cannot_load(
    tmp_path: Path, dst_bundle: object, passing_validation: ValidationReport
) -> None:
    (tmp_path / "benchmarks").mkdir()
    with pytest.raises(ValueError, match="only upstream repair tasks"):
        PackPublisher(tmp_path).publish(dst_bundle, passing_validation)  # type: ignore[arg-type]
    assert not (tmp_path / "benchmarks" / "dst-synth").exists()


def test_publisher_rejects_non_engine_validation(
    tmp_path: Path, dst_bundle: object
) -> None:
    (tmp_path / "benchmarks").mkdir()
    validation = ValidationReport(
        candidate_id="synthetic-cccccccccccccccc",
        complete=False,
        passed=False,
        base_failed=False,
        gold_passed=False,
        engine_backed=False,
    )
    with pytest.raises(ValueError, match="real-engine"):
        PackPublisher(tmp_path).publish(dst_bundle, validation)  # type: ignore[arg-type]


def test_publisher_creates_a_loadable_minecraft_synth_pack(
    tmp_path: Path, minecraft_bundle: object, passing_validation: ValidationReport
) -> None:
    import shutil

    from rhenium_minecraft.catalog import MinecraftCatalog, task_manifest

    root = Path(__file__).resolve().parents[3]
    core = tmp_path / "benchmarks" / "minecraft-core"
    shutil.copytree(root / "benchmarks/minecraft-core/private/runtime", core / "private/runtime")
    shutil.copytree(
        root / "benchmarks/minecraft-core/private/harbor/harness", core / "private/harbor/harness"
    )
    shutil.copyfile(root / "benchmarks/minecraft-core/runtimes.json", core / "runtimes.json")
    publisher = PackPublisher(tmp_path)
    record = publisher.publish(minecraft_bundle, passing_validation)  # type: ignore[arg-type]
    assert record.task_key == "minecraft/synth/synthetic-cccccccccccccccc"
    pack = tmp_path / "benchmarks" / "minecraft-synth"
    catalog = MinecraftCatalog.load(pack, "catalog.json")
    task = catalog.tasks[0]
    assert task.clean_room_synthetic is True and task.plugin_name == "NeutralRelay"
    assert json.loads((pack / "benchmark.json").read_text(encoding="utf-8"))["plugin"] == "minecraft"
    task_root = pack / "private/harbor" / task.id
    assert json.loads((task_root / "tests/task.json").read_text(encoding="utf-8")) == task_manifest(task)
    assert (task_root / "environment/plugin/src/main/resources/plugin.yml").is_file()
    assert (task_root / "solution/after/src/main/java/neutral/relay/Delivery.java").is_file()
    assert "return true" in (task_root / "solution/gold.patch").read_text(encoding="utf-8")


def test_publisher_rejects_minecraft_verifier_that_replaces_trusted_assets(
    tmp_path: Path, minecraft_bundle: object, passing_validation: ValidationReport
) -> None:
    from rhenium_authoring.models import VerifierBundle

    bundle = minecraft_bundle  # type: ignore[assignment]
    for path in ("tests/task.json", "tests/verify.py", "tests/Dockerfile", "tests/starter/plugin.yml"):
        verifier = VerifierBundle(
            files={**bundle.verifier.files, path: "{}\n"},  # type: ignore[attr-defined]
            case_ids=bundle.verifier.case_ids,  # type: ignore[attr-defined]
            capsule_cases=bundle.verifier.capsule_cases,  # type: ignore[attr-defined]
        )
        wrong = bundle.model_copy(update={"verifier": verifier})  # type: ignore[attr-defined]
        with pytest.raises(ValueError, match="trusted authoring asset"):
            PackPublisher(tmp_path).stage(wrong, tmp_path / path.replace("/", "-"))
