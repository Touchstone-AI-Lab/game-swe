from __future__ import annotations

import json
from typing import Any

import pytest
from rhenium_authoring.cleanroom import CleanRoomSynthesizer
from rhenium_authoring.game_adapters import game_spec
from rhenium_authoring.gates import LeakageError, validate_public_candidate
from rhenium_authoring.models import (
    AuthoredPrompt,
    BehaviorCapsule,
    CompositeCandidate,
    DefectInjection,
    DefectInjections,
    GeneratedProject,
    LegacySynthInterfaceContract,
    SynthesisBundle,
    SynthInterfaceContract,
)


class RecordingModel:
    def __init__(self, output: Any):
        self.output = output
        self.calls: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []

    def complete(self, output: type[Any], *, role: str, payload: dict[str, object]) -> Any:
        del output, role
        self.calls.append(payload)
        return self.output

    def on_event(self, event: dict[str, object]) -> None:
        self.events.append(event)


def test_prompt_author_omits_oracles_and_repairs_counts_and_task_ids(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    responses = [
        AuthoredPrompt(markdown="Two bugs need fixing."),
        AuthoredPrompt(markdown=f"Please solve {dst_bundle.candidate.id}."),
        AuthoredPrompt(markdown="Players report repeated deliveries. Preserve working behavior."),
    ]
    requests: list[dict[str, object]] = []

    class PromptModel:
        def complete(self, output: type[Any], *, role: str, payload: dict[str, object]) -> AuthoredPrompt:
            del output, role
            requests.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

    candidate = dst_bundle.candidate.model_copy(
        update={
            "capsules": tuple(
                c.model_copy(update={"test_oracles": ("PRIVATE_ORACLE_MARKER",)})
                for c in dst_bundle.candidate.capsules
            ),
        }
    )
    synth = CleanRoomSynthesizer(PromptModel())  # type: ignore[arg-type]
    prompt = synth.author_prompt(candidate, dst_interface_contract)
    assert prompt.markdown.startswith("Players report")
    assert len(requests) == 3
    assert "PRIVATE_ORACLE_MARKER" not in json.dumps(requests)
    assert "validation_feedback" in requests[1]
    assert "candidate" not in requests[0]


def test_fixed_generator_crosses_only_behavior_barrier(
    dst_bundle: Any, dst_interface_contract: SynthInterfaceContract
) -> None:
    client = RecordingModel(dst_bundle.fixed)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    synthesizer.generate_fixed(dst_bundle.candidate, dst_interface_contract)
    serialized = str(client.calls)
    assert "github.com" not in serialized
    assert "private-mod" not in serialized
    assert "historical patch" not in serialized
    assert "A queued delivery" in serialized


def test_interface_designer_uses_only_capsules_and_trusted_guidance(
    dst_bundle: Any, dst_interface_contract: SynthInterfaceContract
) -> None:
    client = RecordingModel(dst_interface_contract)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    assert synthesizer.design_interface(dst_bundle.candidate) == dst_interface_contract
    payload = client.calls[0]
    assert set(payload) == {"candidate", "instructions"}
    assert "private-mod" not in str(payload)
    assert "historical patch" not in str(payload)


def test_interface_designer_rejects_incomplete_capsule_mapping(
    dst_bundle: Any, dst_interface_contract: SynthInterfaceContract
) -> None:
    bad_contract = dst_interface_contract.model_copy(update={"capsule_entrypoints": {}})
    synthesizer = CleanRoomSynthesizer(RecordingModel(bad_contract))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="identity"):
        synthesizer.design_interface(dst_bundle.candidate)


@pytest.mark.parametrize(
    "field,value",
    [
        ("project_files", ["../escape.lua"]),
        ("capsule_entrypoints", {"one": ["missing"], "two": ["missing"]}),
        ("unknown", True),
    ],
)
def test_interface_contract_rejects_unsafe_or_unknown_references(
    dst_interface_contract: SynthInterfaceContract, field: str, value: Any
) -> None:
    payload = dst_interface_contract.model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValueError):
        SynthInterfaceContract.model_validate(payload)


def test_fixed_generator_rejects_unshared_loading_layout(
    dst_bundle: Any, dst_interface_contract: SynthInterfaceContract
) -> None:
    wrong = dst_bundle.fixed.model_copy(update={"files": {"modmain.lua": "return true"}})
    synthesizer = CleanRoomSynthesizer(RecordingModel(wrong))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="shared interface project files"):
        synthesizer.generate_fixed(dst_bundle.candidate, dst_interface_contract)


@pytest.mark.parametrize(
    "game,required_guidance",
    [
        ("dst", ("load_submission", "context:case", "must not return a function")),
        ("stardew-valley", ("IGcbSuite", "IEnumerable<GcbCase>", "GCB_MODE=run-suite", "Name, Passed")),
    ],
)
def test_verifier_request_receives_trusted_runner_interface(
    dst_bundle: Any,
    dst_interface_contract: SynthInterfaceContract,
    game: str,
    required_guidance: tuple[str, ...],
) -> None:
    client = RecordingModel(dst_bundle.verifier)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    synthesizer.generate_verifier(
        dst_bundle.candidate, dst_interface_contract, game_spec(game).verifier_contract
    )
    payload = client.calls[0]
    assert payload["interface_contract"] == dst_interface_contract.model_dump(mode="json")
    assert "fixed_project" not in payload
    assert all(value in str(payload["instructions"]) for value in required_guidance)


def test_stardew_design_request_includes_build_and_live_trigger_contract(
    dst_bundle: Any, dst_interface_contract: SynthInterfaceContract
) -> None:
    client = RecordingModel(dst_interface_contract)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    synthesizer.design_interface(dst_bundle.candidate, game_spec("stardew-valley").generation_contract)
    instructions = str(client.calls[0]["instructions"])
    assert "MonoGame.Framework.dll" in instructions
    assert "AppendTargetFrameworkToOutputPath=false" in instructions
    assert "CopyToOutputDirectory=PreserveNewest" in instructions
    assert "ModEntry.Entry" in instructions
    assert "same path used by the registered live trigger" in instructions
    assert "ModRegistry.GetApi(loader_identity)" in instructions
    assert "non-generic" in instructions
    assert "StardewModdingAPI.Utilities.SDate" in instructions


def test_stardew_interface_rejects_mismatched_loader_metadata(
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    payload = dst_interface_contract.model_dump(mode="json")
    payload.update(
        game_id="stardew-valley",
        project_files=[*payload["project_files"], "manifest.json"],
        loader_identity="Neutral.Relays",
        metadata_files={"manifest.json": json.dumps({"UniqueID": "Other.Mod", "EntryDll": "Synthetic.dll"})},
    )
    with pytest.raises(ValueError, match="UniqueID"):
        SynthInterfaceContract.model_validate(payload)
    payload["metadata_files"] = {
        "manifest.json": json.dumps({"UniqueID": "Neutral.Relays", "EntryDll": "Synthetic.dll"})
    }
    assert SynthInterfaceContract.model_validate(payload).loader_identity == "Neutral.Relays"
    payload["entrypoints"][0]["observation_channel"] = "game-state"
    with pytest.raises(ValueError, match="return observable"):
        SynthInterfaceContract.model_validate(payload)


@pytest.mark.parametrize("field", ["signature", "return_type", "return_schema", "observation_channel"])
def test_new_interface_requires_exact_entrypoint_result_contract(
    dst_interface_contract: SynthInterfaceContract,
    field: str,
) -> None:
    payload = dst_interface_contract.model_dump(mode="json")
    del payload["entrypoints"][0][field]
    with pytest.raises(ValueError):
        SynthInterfaceContract.model_validate(payload)


def test_fixed_generator_rejects_changed_exact_metadata(
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    contract = dst_interface_contract.model_copy(
        update={"metadata_files": {"modinfo.lua": dst_bundle.fixed.files["modinfo.lua"]}}
    )
    fixed = dst_bundle.fixed.model_copy(
        update={"files": {**dst_bundle.fixed.files, "modinfo.lua": 'name = "Unexpected"\n'}}
    )
    synthesizer = CleanRoomSynthesizer(RecordingModel(fixed))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exact shared load metadata"):
        synthesizer.generate_fixed(dst_bundle.candidate, contract)


def test_staged_bundle_preserves_legacy_contract_without_weakening_new_generation(
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    legacy = dst_interface_contract.model_dump(mode="json")
    for field in ("schema_version", "loader_identity", "metadata_files"):
        del legacy[field]
    for entry in legacy["entrypoints"]:
        for field in ("signature", "return_type", "return_schema", "observation_channel"):
            del entry[field]
    payload = dst_bundle.model_dump(mode="json")
    payload["interface_contract"] = legacy
    loaded = SynthesisBundle.model_validate(payload)
    assert isinstance(loaded.interface_contract, LegacySynthInterfaceContract)
    assert not isinstance(loaded.interface_contract, SynthInterfaceContract)
    with pytest.raises(ValueError):
        SynthInterfaceContract.model_validate(legacy)


def test_bundle_rejects_base_metadata_drift(
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    contract = dst_interface_contract.model_copy(
        update={"metadata_files": {"modinfo.lua": dst_bundle.fixed.files["modinfo.lua"]}}
    )
    payload = dst_bundle.model_dump(mode="json")
    payload["interface_contract"] = contract.model_dump(mode="json")
    payload["base"]["files"]["modinfo.lua"] += "-- drift\n"
    with pytest.raises(ValueError, match="exact shared load metadata"):
        SynthesisBundle.model_validate(payload)


def test_compact_defect_injections_reject_unsafe_paths_and_duplicate_capsules() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        DefectInjection(capsule_id="behavior-one", symptom="failure", replacements={"../x.lua": "x"})
    injection = DefectInjection(
        capsule_id="behavior-one", symptom="failure", replacements={"scripts/x.lua": "return false"}
    )
    with pytest.raises(ValueError, match="unique"):
        DefectInjections(injections=(injection, injection))


def test_compact_injection_preserves_full_trees_and_exact_metadata(
    dst_bundle: SynthesisBundle,
    dst_interface_contract: SynthInterfaceContract,
) -> None:
    contract = dst_interface_contract.model_copy(
        update={"metadata_files": {"modinfo.lua": dst_bundle.fixed.files["modinfo.lua"]}}
    )
    injections = DefectInjections(
        injections=tuple(
            DefectInjection(
                capsule_id=defect.capsule_id,
                symptom=defect.symptom,
                replacements={path: dst_bundle.base.files[path] for path in defect.affected_files},
            )
            for defect in dst_bundle.base.defects
        )
    )
    synthesizer = CleanRoomSynthesizer(RecordingModel(injections))  # type: ignore[arg-type]
    generated = synthesizer.inject_defects(dst_bundle.candidate, dst_bundle.fixed, contract)
    assert generated.files == dst_bundle.base.files
    assert generated.ablations == dst_bundle.base.ablations
    for tree in (generated.files, *generated.ablations.values()):
        assert set(tree) == set(dst_bundle.fixed.files)
        assert tree["modinfo.lua"] == contract.metadata_files["modinfo.lua"]


def test_composition_requires_two_capsules_per_supported_game() -> None:
    capsules = [
        BehaviorCapsule(
            capsule_id=f"behavior-{index:016x}",
            game_id="dst",
            observed_symptoms=(f"symptom {index}",),
            expected_behaviors=(f"behavior {index}",),
            test_oracles=(f"oracle {index}",),
        )
        for index in range(9)
    ]
    result = CleanRoomSynthesizer.compose(capsules)
    assert [len(candidate.capsules) for candidate in result] == [7, 2]
    assert [len(candidate.capsules) for candidate in CleanRoomSynthesizer.compose(capsules[:8])] == [
        6,
        2,
    ]


def test_leakage_gate_rejects_source_identity(dst_bundle: Any) -> None:
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate(
            dst_bundle.provenance,
            ["The implementation comes from private-mod and path1.lua."],
            [],
        )


def test_leakage_gate_allows_conventional_mod_layout(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(
        update={
            "changed_files": ("scripts/components/relay.lua", "modinfo.lua", "modmain.lua"),
        }
    )
    validate_public_candidate(
        [fix],
        ["Load modmain.lua and modinfo.lua. modimport('scripts/components/delivery.lua')"],
        [],
    )


@pytest.mark.parametrize("source_word", ["scripts", "modmain", "framework", "characters"])
def test_layout_exception_does_not_exempt_repository_identity(dst_bundle: Any, source_word: str) -> None:
    fix = dst_bundle.provenance[0].model_copy(
        update={"repository_url": f"https://github.com/example/{source_word}"}
    )
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate([fix], [f"The {source_word} project provides this behavior."], [])


def test_leakage_gate_matches_identity_boundaries(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(update={"repository_url": "https://github.com/example/harbor"})
    validate_public_candidate([fix], ["Remove a harboring creature."], [])
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate([fix], ["The HARBOR project."], [])


def test_leakage_gate_preserves_distinctive_path_identity(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(
        update={"changed_files": ("scripts/clockworkfalcon/component.lua",)}
    )
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate([fix], ["Spawn a clockworkfalcon."], [])


def test_generic_upstream_directories_do_not_block_game_namespace_names(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(
        update={"changed_files": ("Framework/Lookups/Characters/OriginalFeature.cs",)}
    )
    validate_public_candidate(
        [fix],
        ["using Microsoft.Xna.Framework; using StardewValley.Characters; // Birthday lookups"],
        [],
    )


def test_leakage_gate_still_rejects_copied_source_sequence(dst_bundle: Any) -> None:
    source = " ".join(f"value{index}" for index in range(60))
    fix = dst_bundle.provenance[0].model_copy(update={"patch": source})
    with pytest.raises(LeakageError, match="50-token"):
        validate_public_candidate([fix], [source], [])


@pytest.mark.parametrize(
    "value",
    [
        "See https://github.com/example/mod",
        "Contact maintainer@example.com",
        "Reported by @maintainer",
        "Fixes #4421",
        "commit " + "a" * 40,
    ],
)
def test_leakage_gate_rejects_public_identity_shapes(dst_bundle: Any, value: str) -> None:
    with pytest.raises(LeakageError, match="identifier"):
        validate_public_candidate(dst_bundle.provenance, [value], [])


def test_generated_paths_reject_escape() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        GeneratedProject(project_name="safe-name", files={"../escape.lua": "return true\n"})


def test_composite_rejects_cross_game_capsules() -> None:
    values = []
    for game in ("dst", "garrys-mod"):
        values.append(
            BehaviorCapsule(
                capsule_id=f"behavior-{game.replace('-', ''):0<16}"[:25],
                game_id=game,
                observed_symptoms=("symptom",),
                expected_behaviors=("behavior",),
                test_oracles=("oracle",),
            )
        )
    with pytest.raises(ValueError, match="share one game"):
        CompositeCandidate(id="synthetic-aaaaaaaaaaaaaaaa", game_id="dst", capsules=tuple(values))


def test_fixed_generator_feeds_identity_violations_back_for_repair(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    contract = dst_interface_contract.model_copy(
        update={"metadata_files": {"modinfo.lua": dst_bundle.fixed.files["modinfo.lua"]}}
    )
    wrong = dst_bundle.fixed.model_copy(
        update={"files": {**dst_bundle.fixed.files, "modinfo.lua": 'name = "Unexpected"\n'}}
    )

    class SequencedModel(RecordingModel):
        def complete(self, output: type[Any], *, role: str, payload: dict[str, object]) -> Any:
            self.calls.append(payload)
            return wrong if len(self.calls) == 1 else dst_bundle.fixed

    client = SequencedModel(None)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    result = synthesizer.generate_fixed(dst_bundle.candidate, contract)
    assert result == dst_bundle.fixed
    feedback = client.calls[1].get("validation_feedback")
    assert feedback and any("byte-for-byte" in str(item) for item in feedback)  # type: ignore[union-attr]
    assert any(event.get("status") == "repairing" for event in client.events)


def test_compose_group_size_is_operator_configurable() -> None:
    capsules = [
        BehaviorCapsule(
            capsule_id=f"behavior-{index:016x}",
            game_id="dst",
            observed_symptoms=("A repeated delivery is observed.",),
            expected_behaviors=("A request is delivered at most once.",),
            public_game_apis=("AddModRPCHandler",),
            test_oracles=("Repeat one request and observe one delivery.",),
        )
        for index in range(8)
    ]
    sizes = [len(candidate.capsules) for candidate in CleanRoomSynthesizer.compose(capsules, 3)]
    assert sizes == [3, 3, 2]
    with pytest.raises(ValueError, match="between 2 and 7"):
        CleanRoomSynthesizer.compose(capsules, 1)


def test_generic_layout_paths_do_not_poison_identity_terms(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(update={"changed_files": (
        "LookupAnything/Framework/Fields/GenericField.cs",
        "LookupAnything/Framework/Models/RecipeModel.cs",
        "LookupAnything/Framework/Lookups/TerrainFeatures/TreeSubject.cs",
        "Automate/ModEntry.cs",
        "Tests.Common/CommonTests/CommonHelperTests.cs",
    )})
    # Layout vocabulary and the SMAPI-mandated entry file name stay usable.
    validate_public_candidate(
        (fix,),
        ["ModEntry registers the console command; models and fields describe "
         "terrain features near machines. Verifier files live under tests/."],
        [],
    )
    # Compound stems from the source stay identity terms.
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["See CommonHelperTests for details."], [])
    # The distinctive project directory and file stems remain identity terms.
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["Behavior taken from LookupAnything."], [])
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["See TreeSubject for details."], [])


def test_stage_attempts_bound_the_compiler_repair_loop(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    client = RecordingModel(dst_bundle.fixed)
    synthesizer = CleanRoomSynthesizer(
        client,  # type: ignore[arg-type]
        project_check=lambda files: ["persistent compile error"],
        stage_attempts=1,
    )
    with pytest.raises(ValueError, match="after three attempts"):
        synthesizer.generate_fixed(dst_bundle.candidate, dst_interface_contract)
    assert len(client.calls) == 1
    with pytest.raises(ValueError, match="between 1 and 5"):
        CleanRoomSynthesizer(client, stage_attempts=0)  # type: ignore[arg-type]


def test_engine_vocabulary_paths_do_not_poison_identity_terms(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(update={
        "repository_url": "https://github.com/example/wirecraft",
        "changed_files": (
            "lua/entities/gmod_wire_hologram/cl_init.lua",
            "lua/wire/stools/entity.lua",
            "lua/classes/resource.lua",
        ),
    })
    validate_public_candidate(
        (fix,),
        ["Each entity class frees its resource when the weapon tool removes the entities."],
        [],
    )
    # The repository name and distinctive stems stay identity terms.
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["Ported from wirecraft."], [])
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["Spawn a gmod_wire_hologram."], [])


def test_review_request_states_that_base_is_intentionally_defective(
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract
) -> None:
    client = RecordingModel(dst_bundle.review)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    synthesizer.review(
        dst_bundle.provenance, dst_bundle.candidate, dst_bundle.fixed, dst_bundle.base,
        dst_bundle.verifier, dst_bundle.prompt, dst_interface_contract,
    )
    instructions = " ".join(client.calls[0]["instructions"])  # type: ignore[arg-type]
    assert "INTENTIONALLY defective starter" in instructions
    assert "Never reject because base or an ablation is defective" in instructions
    # Engine-decidable outcomes belong to the mandatory two-way engine validation.
    assert "Do not reject for a suspected runtime outcome" in instructions
    assert "never published" in instructions
    assert "set approved to true and state the concern in the rationale" in instructions


@pytest.mark.parametrize(
    ("suite_cases", "extra_files", "expected_finding"),
    [
        (("plugin is enabled", "delivers once"), {}, "missing: restores capacity"),
        (("plugin is enabled", "delivers once", "restores capacity", "delivers once"), {},
         "undeclared or duplicated: delivers once"),
        (("plugin is enabled", "delivers once", "restores capacity"), {"tests/test.sh": "exit 0\n"},
         "Return only tests/TaskSuite.java"),
    ],
)
def test_minecraft_verifier_static_checks_feed_back_before_the_runner_is_rendered(
    minecraft_bundle: SynthesisBundle, minecraft_interface_contract: SynthInterfaceContract,
    suite_cases: tuple[str, ...], extra_files: dict[str, str], expected_finding: str,
) -> None:
    from conftest import MINECRAFT_CASE_IDS, minecraft_suite

    good = minecraft_bundle.verifier.model_copy(
        update={"files": {"tests/TaskSuite.java": minecraft_suite(MINECRAFT_CASE_IDS)}}
    )
    bad = good.model_copy(update={"files": {
        "tests/TaskSuite.java": minecraft_suite(suite_cases), **extra_files,
    }})
    responses = [bad, good]

    class Model(RecordingModel):
        def complete(self, output: type[Any], *, role: str, payload: dict[str, object]) -> Any:
            self.calls.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

    client = Model(None)
    result = CleanRoomSynthesizer(client).generate_verifier(  # type: ignore[arg-type]
        minecraft_bundle.candidate, minecraft_interface_contract,
        game_spec("minecraft").verifier_contract, case_contract=minecraft_bundle.verifier,
    )
    assert len(client.calls) == 2
    assert client.calls[0]["required_verifier_files"] == ["tests/TaskSuite.java"]
    feedback = str(client.calls[1]["validation_feedback"])
    assert expected_finding in feedback
    assert set(result.files) == {"tests/TaskSuite.java", "tests/test.sh"}
    assert "\nEXPECTED=3\n" in result.files["tests/test.sh"]
    assert "GetApi" not in str(client.calls[0]["instructions"])


@pytest.mark.parametrize(
    ("mutation", "expected_finding"),
    [
        ({"build.gradle.kts": "plugins { java }\n"}, "Keep every project file below src/main/java/"),
        ({"src/main/java/neutral/relay/Delivery.java":
          "package neutral.relay;\nfinal class Delivery { static boolean once() { "
          "net.minecraft.server.MinecraftServer.getServer(); return true; } }\n"},
         "net.minecraft internals"),
        ({"src/main/java/neutral/relay/Delivery.java":
          "package neutral.relay;\nfinal class Delivery { static boolean once() { "
          "org.bukkit.Bukkit.shutdown(); return true; } }\n"},
         "Bukkit.shutdown"),
        ({"src/main/java/neutral/relay/Delivery.java":
          "package neutral.relay;\nfinal class Delivery { static boolean once() { "
          "System.exit(1); return true; } }\n"},
         "System.exit"),
    ],
)
def test_minecraft_fixed_project_layout_and_source_rules_are_enforced(
    minecraft_bundle: SynthesisBundle, minecraft_interface_contract: SynthInterfaceContract,
    mutation: dict[str, str], expected_finding: str,
) -> None:
    wrong = minecraft_bundle.fixed.model_copy(update={"files": {**minecraft_bundle.fixed.files, **mutation}})
    responses = [wrong, minecraft_bundle.fixed]

    class Model(RecordingModel):
        def complete(self, output: type[Any], *, role: str, payload: dict[str, object]) -> Any:
            self.calls.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

    client = Model(None)
    result = CleanRoomSynthesizer(client).generate_fixed(  # type: ignore[arg-type]
        minecraft_bundle.candidate, minecraft_interface_contract,
    )
    assert result == minecraft_bundle.fixed
    assert expected_finding in str(client.calls[1]["validation_feedback"])


def test_minecraft_defect_controls_are_linted_before_compilation(
    minecraft_bundle: SynthesisBundle, minecraft_interface_contract: SynthInterfaceContract,
) -> None:
    checks: list[dict[str, str]] = []
    poisoned = minecraft_bundle.base.files["src/main/java/neutral/relay/Delivery.java"].replace(
        "return false", "System.exit(3); return false"
    )
    responses = [
        DefectInjections(injections=(
            DefectInjection(capsule_id=minecraft_bundle.base.defects[0].capsule_id, symptom="s",
                            replacements={"src/main/java/neutral/relay/Delivery.java": poisoned}),
            DefectInjection(capsule_id=minecraft_bundle.base.defects[1].capsule_id, symptom="s",
                            replacements={"src/main/java/neutral/relay/Capacity.java":
                                          minecraft_bundle.base.files["src/main/java/neutral/relay/Capacity.java"]}),
        )),
        DefectInjections(injections=tuple(
            DefectInjection(capsule_id=report.capsule_id, symptom=report.symptom,
                            replacements={path: minecraft_bundle.base.files[path]
                                          for path in report.affected_files})
            for report in minecraft_bundle.base.defects
        )),
    ]

    class Model(RecordingModel):
        def complete(self, output: type[Any], *, role: str, payload: dict[str, object]) -> Any:
            self.calls.append(json.loads(json.dumps(payload)))
            return responses.pop(0)

    client = Model(None)
    synth = CleanRoomSynthesizer(client, project_check=lambda files: checks.append(files) or ())  # type: ignore[arg-type]
    result = synth.inject_defects(
        minecraft_bundle.candidate, minecraft_bundle.fixed, minecraft_interface_contract,
    )
    assert result == minecraft_bundle.base
    findings = str(client.calls[1]["validation_feedback"])
    assert "combined-base: src/main/java/neutral/relay/Delivery.java: System.exit" in findings
    assert len(checks) == 6


def test_minecraft_interface_requires_a_consistent_plugin_yml(
    minecraft_interface_contract: SynthInterfaceContract,
) -> None:
    from conftest import MINECRAFT_PLUGIN_YML

    payload = minecraft_interface_contract.model_dump(mode="json")

    def rejected(metadata: str, message: str, **update: Any) -> None:
        wrong = json.loads(json.dumps(payload))
        wrong["metadata_files"] = {"src/main/resources/plugin.yml": metadata}
        wrong.update(update)
        with pytest.raises(ValueError, match=message):
            SynthInterfaceContract.model_validate(wrong)

    rejected(MINECRAFT_PLUGIN_YML.replace("NeutralRelay", "OtherName"), "name must match loader_identity")
    rejected(MINECRAFT_PLUGIN_YML.replace("neutral.relay.RelayPlugin", "neutral.relay.Missing"),
             "main class must be a declared")
    rejected(MINECRAFT_PLUGIN_YML.replace("'1.21'", "'1.20'"), "api-version")
    rejected(MINECRAFT_PLUGIN_YML + "depend: [Vault]\n", "must not declare depend")
    rejected(MINECRAFT_PLUGIN_YML + "libraries:\n  - com.example:lib:1.0\n", "must not declare libraries")
    rejected(MINECRAFT_PLUGIN_YML + "load: STARTUP\n", "must not declare load")
    wrong = json.loads(json.dumps(payload))
    del wrong["metadata_files"]["src/main/resources/plugin.yml"]
    with pytest.raises(ValueError, match="requires serialized"):
        SynthInterfaceContract.model_validate(wrong)
    wrong = json.loads(json.dumps(payload))
    wrong["entrypoints"][0]["return_type"] = "void"
    with pytest.raises(ValueError, match="void"):
        SynthInterfaceContract.model_validate(wrong)
    # Quoted and unquoted scalars are both accepted; the contract itself is valid.
    accepted = json.loads(json.dumps(payload))
    accepted["metadata_files"] = {"src/main/resources/plugin.yml":
                                  MINECRAFT_PLUGIN_YML.replace("name: NeutralRelay", 'name: "NeutralRelay"')}
    assert SynthInterfaceContract.model_validate(accepted).loader_identity == "NeutralRelay"


def test_review_request_names_the_trusted_runner_division_for_each_game(
    minecraft_bundle: SynthesisBundle, minecraft_interface_contract: SynthInterfaceContract,
    dst_bundle: SynthesisBundle, dst_interface_contract: SynthInterfaceContract,
) -> None:
    client = RecordingModel(minecraft_bundle.review)
    synthesizer = CleanRoomSynthesizer(client)  # type: ignore[arg-type]
    synthesizer.review(
        minecraft_bundle.provenance, minecraft_bundle.candidate, minecraft_bundle.fixed,
        minecraft_bundle.base, minecraft_bundle.verifier, minecraft_bundle.prompt,
        minecraft_interface_contract,
    )
    instructions = " ".join(client.calls[0]["instructions"])  # type: ignore[arg-type]
    assert "operator-rendered tests/test.sh" in instructions
    assert "model-authored component is tests/TaskSuite.java" in instructions
    assert "Stardew" not in instructions
    synthesizer.review(
        dst_bundle.provenance, dst_bundle.candidate, dst_bundle.fixed, dst_bundle.base,
        dst_bundle.verifier, dst_bundle.prompt, dst_interface_contract,
    )
    assert "Every verifier file is model-authored" in " ".join(client.calls[1]["instructions"])  # type: ignore[arg-type]
