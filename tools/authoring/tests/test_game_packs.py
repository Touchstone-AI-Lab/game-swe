from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_authoring.models import (
    CompositeCandidate,
    DefectiveProject,
    DefectReport,
    GeneratedProject,
    SynthesisBundle,
    VerifierBundle,
)
from rhenium_authoring.publisher import PackPublisher
from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog
from rhenium_isaac_rebirth.catalog import IsaacCatalog
from rhenium_minecraft.catalog import MinecraftCatalog, task_manifest
from rhenium_stardew_valley.catalog import StardewCatalog

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("game_id", "project_files", "verifier_files", "catalog_type"),
    [
        (
            "stardew-valley",
            {
                "Directory.Build.props": "<Project />\n",
                "Synthetic.sln": "\n",
                "NeutralMod/NeutralMod.csproj": "<Project />\n",
                "NeutralMod/manifest.json": "{}\n",
            },
            {
                "tests/test.sh": "EXPECTED=2\n",
                "tests/TaskSuite.cs": "internal sealed class TaskSuite {}\n",
            },
            StardewCatalog,
        ),
        (
            "garrys-mod",
            {
                "gamemode/init.lua": "return true\n",
                "gamemode/cl_init.lua": "return true\n",
            },
            {
                "tests/test.sh": "EXPECTED=2\n",
                "tests/suite.lua": "return true\n",
            },
            GarrysModCatalog,
        ),
        (
            "isaac-rebirth",
            {"main.lua": "return true\n", "metadata.xml": "<metadata />\n"},
            {
                "tests/test.sh": (
                    "expected=35\nexpected_cases=(\n"
                    + "\n".join(f"case_{index}" for index in range(35))
                    + "\n)\n"
                ),
                "tests/suite.lua": "return true\n",
                "tests/Dockerfile": "ARG PRIVATE_IMAGE\nFROM ${PRIVATE_IMAGE}\n",
            },
            IsaacCatalog,
        ),
    ],
)
def test_stage_pack_matches_each_plugin_catalog(
    tmp_path: Path,
    dst_bundle: SynthesisBundle,
    game_id: str,
    project_files: dict[str, str],
    verifier_files: dict[str, str],
    catalog_type: type[object],
) -> None:
    bundle = _bundle_for(dst_bundle, game_id, project_files, verifier_files)
    pack = PackPublisher(ROOT).stage(bundle, tmp_path)
    catalog = catalog_type.load(pack, "catalog.json")  # type: ignore[attr-defined]
    assert catalog.tasks[0].clean_room_synthetic is True  # type: ignore[attr-defined]


def test_minecraft_stage_pack_matches_the_plugin_catalog_and_frozen_manifest(
    tmp_path: Path, minecraft_bundle: SynthesisBundle
) -> None:
    pack = PackPublisher(ROOT).stage(minecraft_bundle, tmp_path)
    catalog = MinecraftCatalog.load(pack, "catalog.json")
    task = catalog.tasks[0]
    assert task.clean_room_synthetic is True
    assert task.plugin_name == "NeutralRelay"
    assert task.build.tool == "javac" and task.build.artifact == "build/libs/NeutralRelay.jar"
    assert task.server_cases == minecraft_bundle.verifier.case_ids and task.unit_cases == ()
    assert task.required_files[0].startswith("plugin/src/main/")
    task_root = pack / "private/harbor" / task.id
    assert json.loads((task_root / "tests/task.json").read_text(encoding="utf-8")) == task_manifest(task)
    verifier_dockerfile = (task_root / "tests/Dockerfile").read_text(encoding="utf-8")
    assert verifier_dockerfile.startswith("# Separate verifier image")
    assert "FROM gcb-minecraft-paper-verifier:1.21.11-132\n" in verifier_dockerfile
    assert "COPY TaskSuite.java /tests/TaskSuite.java\n" in verifier_dockerfile
    assert "__WARM__" not in verifier_dockerfile and "__SUITE__" not in verifier_dockerfile
    agent_dockerfile = (task_root / "environment/Dockerfile").read_text(encoding="utf-8")
    assert "COPY plugin /app/plugin" in agent_dockerfile and "__WARM__" not in agent_dockerfile
    assert (task_root / "tests/verify.py").read_bytes() == (
        ROOT / "benchmarks/minecraft-core/private/harbor/harness/verify.py"
    ).read_bytes()
    assert (task_root / "tests/test.sh").stat().st_mode & 0o111
    assert (task_root / "solution/solve.sh").stat().st_mode & 0o111
    assert (task_root / "scripts/javac-build.sh").is_file()
    assert (task_root / "tests/starter/src/main/resources/plugin.yml").read_text(
        encoding="utf-8"
    ) == minecraft_bundle.base.files["src/main/resources/plugin.yml"]
    assert not (task_root / "tests/frozen").exists()
    # The synth runtime builder reads the pinned base assets from the pack root.
    assert (pack / "private/runtime/Dockerfile").is_file()
    assert (pack / "private/harbor/harness/gcb-harness/build.sh").is_file()
    assert not list((pack / "private/harbor/harness").rglob("__pycache__"))
    runtimes = json.loads((pack / "runtimes.json").read_text(encoding="utf-8"))
    assert [runtime["id"] for runtime in runtimes["runtimes"]] == ["paper-1.21.11-132-synth"]
    assert runtimes["task_bindings"] == {task.id: ["paper-1.21.11-132-synth"]}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda files: files.update({"build.gradle.kts": "plugins {}\n"}), "source layout"),
        (lambda files: files.update({"src/main/resources/plugin.yml": "main: neutral.relay.RelayPlugin\n"}),
         "plugin.yml name"),
    ],
)
def test_minecraft_stage_rejects_build_files_and_nameless_metadata(
    tmp_path: Path, minecraft_bundle: SynthesisBundle, mutate: object, message: str
) -> None:
    fixed = dict(minecraft_bundle.fixed.files)
    mutate(fixed)  # type: ignore[operator]
    base = {
        **minecraft_bundle.base.files,
        **{key: fixed[key] for key in fixed if key not in minecraft_bundle.fixed.files},
    }
    if "src/main/resources/plugin.yml" in fixed:
        base["src/main/resources/plugin.yml"] = fixed["src/main/resources/plugin.yml"]
    ablations = {
        key: {
            **tree,
            **{path: fixed[path] for path in fixed if path not in tree or path.endswith("plugin.yml")},
        }
        for key, tree in minecraft_bundle.base.ablations.items()
    }
    bundle = minecraft_bundle.model_copy(update={
        "fixed": minecraft_bundle.fixed.model_copy(update={"files": fixed}),
        "base": minecraft_bundle.base.model_copy(update={"files": base, "ablations": ablations}),
    })
    with pytest.raises(ValueError, match=message):
        PackPublisher(ROOT).stage(bundle, tmp_path)


def _bundle_for(
    source: SynthesisBundle,
    game_id: str,
    fixed_files: dict[str, str],
    verifier_files: dict[str, str],
) -> SynthesisBundle:
    capsules = tuple(
        capsule.model_copy(update={"game_id": game_id}) for capsule in source.candidate.capsules
    )
    candidate = CompositeCandidate(
        id=source.candidate.id,
        game_id=game_id,
        capsules=capsules,
    )
    names = list(fixed_files)
    base_files = dict(fixed_files)
    base_files[names[0]] = fixed_files[names[0]] + "-- synthetic defect one\n"
    base_files[names[1]] = fixed_files[names[1]] + "-- synthetic defect two\n"
    ablations = {
        capsules[0].capsule_id: {**fixed_files, names[0]: base_files[names[0]]},
        capsules[1].capsule_id: {**fixed_files, names[1]: base_files[names[1]]},
    }
    provenance = tuple(fix.model_copy(update={"game_id": game_id}) for fix in source.provenance)
    case_ids = (
        tuple(f"case_{index}" for index in range(35))
        if game_id == "isaac-rebirth"
        else ("case_one", "case_two")
    )
    mapped_cases = case_ids[:2]
    return source.model_copy(
        update={
            "candidate": candidate,
            "fixed": GeneratedProject(project_name="neutral-project", files=fixed_files),
            "base": DefectiveProject(
                files=base_files,
                defects=(
                    DefectReport(
                        capsule_id=capsules[0].capsule_id,
                        symptom="symptom one",
                        affected_files=(names[0],),
                    ),
                    DefectReport(
                        capsule_id=capsules[1].capsule_id,
                        symptom="symptom two",
                        affected_files=(names[1],),
                    ),
                ),
                ablations=ablations,
            ),
            "verifier": VerifierBundle(
                files=verifier_files,
                case_ids=case_ids,
                capsule_cases={
                    capsules[0].capsule_id: (mapped_cases[0],),
                    capsules[1].capsule_id: (mapped_cases[1],),
                },
            ),
            "provenance": provenance,
        }
    )
