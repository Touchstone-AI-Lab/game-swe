from __future__ import annotations

from collections.abc import Iterator

import pytest
from pydantic import HttpUrl
from rhenium_authoring.models import (
    AuthoredPrompt,
    BehaviorCapsule,
    CompositeCandidate,
    DefectiveProject,
    DefectReport,
    GeneratedProject,
    HistoricalFix,
    ReviewDecision,
    SynthesisBundle,
    SynthInterfaceContract,
    ValidationReport,
    VerifierBundle,
)


@pytest.fixture
def dst_bundle() -> SynthesisBundle:
    capsules = (
        BehaviorCapsule(
            capsule_id="behavior-aaaaaaaaaaaaaaaa",
            game_id="dst",
            observed_symptoms=("A queued delivery is repeated after reconnect.",),
            expected_behaviors=("A request is delivered at most once.",),
            public_game_apis=("AddModRPCHandler",),
            test_oracles=("Repeat one request and observe one delivery.",),
        ),
        BehaviorCapsule(
            capsule_id="behavior-bbbbbbbbbbbbbbbb",
            game_id="dst",
            observed_symptoms=("A failed delivery consumes capacity.",),
            expected_behaviors=("Failed delivery restores capacity.",),
            public_game_apis=("SpawnPrefab",),
            test_oracles=("Fail delivery and observe unchanged capacity.",),
        ),
    )
    candidate = CompositeCandidate(
        id="synthetic-cccccccccccccccc", game_id="dst", capsules=capsules
    )
    fixed_files = {
        "modinfo.lua": 'name = "Neutral Relay"\napi_version = 10\ndst_compatible = true\n',
        "modmain.lua": "modimport('scripts/relay.lua')\n",
        "scripts/relay.lua": "local M = {}\nfunction M.once() return true end\nreturn M\n",
        "scripts/capacity.lua": "local M = {}\nfunction M.restore() return true end\nreturn M\n",
    }
    base_files = {
        **fixed_files,
        "scripts/relay.lua": "local M = {}\nfunction M.once() return false end\nreturn M\n",
        "scripts/capacity.lua": "local M = {}\nfunction M.restore() return false end\nreturn M\n",
    }
    fixes = tuple(
        HistoricalFix(
            id=f"github-pr-{index}",
            game_id="dst",
            repository_url=HttpUrl("https://github.com/example/private-mod"),
            license_spdx="MIT",
            base_sha=str(index) * 40,
            fixed_sha=str(index + 2) * 40,
            issue_text=f"Historical report {index}",
            patch=f"historical patch {index}",
            changed_files=(f"private/path{index}.lua",),
        )
        for index in (1, 2)
    )
    return SynthesisBundle(
        candidate=candidate,
        fixed=GeneratedProject(project_name="neutral-relay", files=fixed_files),
        base=DefectiveProject(
            files=base_files,
            defects=(
                DefectReport(
                    capsule_id=capsules[0].capsule_id,
                    symptom=capsules[0].observed_symptoms[0],
                    affected_files=("scripts/relay.lua",),
                ),
                DefectReport(
                    capsule_id=capsules[1].capsule_id,
                    symptom=capsules[1].observed_symptoms[0],
                    affected_files=("scripts/capacity.lua",),
                ),
            ),
            ablations={
                capsules[0].capsule_id: {
                    **fixed_files,
                    "scripts/relay.lua": base_files["scripts/relay.lua"],
                },
                capsules[1].capsule_id: {
                    **fixed_files,
                    "scripts/capacity.lua": base_files["scripts/capacity.lua"],
                },
            },
        ),
        verifier=VerifierBundle(
            files={"hidden.lua": "return function() end\n", "server.lua": "return function() end\n"},
            case_ids=("sentinel", "once", "capacity"),
            capsule_cases={
                capsules[0].capsule_id: ("once",),
                capsules[1].capsule_id: ("capacity",),
            },
        ),
        prompt=AuthoredPrompt(markdown="# Anonymous reports\n\nRepair the reported behavior."),
        review=ReviewDecision(approved=True, rationale="No copied expression or contract gap."),
        provenance=fixes,
    )


@pytest.fixture
def dst_interface_contract(dst_bundle: SynthesisBundle) -> SynthInterfaceContract:
    return SynthInterfaceContract.model_validate(
        {
            "schema_version": 2,
            "game_id": "dst",
            "project_name": dst_bundle.fixed.project_name,
            "loader_identity": "neutral-relay",
            "metadata_files": {},
            "project_files": list(dst_bundle.fixed.files),
            "modules": [
                {
                    "path": "scripts/relay.lua",
                    "identifier": "relay",
                    "loading": "Load the relay module and use its returned public API.",
                },
                {
                    "path": "scripts/capacity.lua",
                    "identifier": "capacity",
                    "loading": "Load the capacity module and use its returned public API.",
                },
            ],
            "entrypoints": [
                {
                    "id": "deliver-once",
                    "module_identifier": "relay",
                    "trigger": "relay.once()",
                    "signature": "relay.once()",
                    "return_type": "boolean",
                    "return_schema": "true for a successful single delivery, false otherwise",
                    "observation_channel": "return-value",
                    "inputs": [],
                    "observable_outcomes": ["The delivery succeeds at most once."],
                },
                {
                    "id": "restore-capacity",
                    "module_identifier": "capacity",
                    "trigger": "capacity.restore()",
                    "signature": "capacity.restore()",
                    "return_type": "boolean",
                    "return_schema": "true when failed delivery capacity is restored, false otherwise",
                    "observation_channel": "return-value",
                    "inputs": [],
                    "observable_outcomes": ["Failed delivery restores capacity."],
                },
            ],
            "capsule_entrypoints": {
                dst_bundle.candidate.capsules[0].capsule_id: ["deliver-once"],
                dst_bundle.candidate.capsules[1].capsule_id: ["restore-capacity"],
            },
        }
    )


MINECRAFT_PLUGIN_YML = (
    "name: NeutralRelay\n"
    "main: neutral.relay.RelayPlugin\n"
    "version: 0.1.0\n"
    "api-version: '1.21'\n"
)
MINECRAFT_CASE_IDS = ("plugin is enabled", "delivers once", "restores capacity")


def minecraft_suite(case_ids: tuple[str, ...] = MINECRAFT_CASE_IDS) -> str:
    """A minimal GcbSuite declaring exactly the given case IDs."""
    methods = "\n".join(
        f'    @GcbCase("{name}")\n    public void case{index}() {{\n'
        "        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(\"NeutralRelay\"), "
        "\"enabled\");\n"
        "    }\n"
        for index, name in enumerate(case_ids)
    )
    return (
        "package io.gamecodebench.suite;\n\n"
        "import io.gamecodebench.harness.GcbAssert;\n"
        "import io.gamecodebench.harness.GcbCase;\n"
        "import io.gamecodebench.harness.GcbSuite;\n"
        "import org.bukkit.Bukkit;\n\n"
        "public final class TaskSuite implements GcbSuite {\n"
        f"{methods}"
        "}\n"
    )


@pytest.fixture
def minecraft_bundle(dst_bundle: SynthesisBundle) -> SynthesisBundle:
    from rhenium_authoring.minecraft_runner import render_test_script

    capsules = tuple(
        capsule.model_copy(update={"game_id": "minecraft", "public_game_apis": ("org.bukkit.Bukkit",)})
        for capsule in dst_bundle.candidate.capsules
    )
    candidate = CompositeCandidate(id=dst_bundle.candidate.id, game_id="minecraft", capsules=capsules)
    fixed_files = {
        "src/main/resources/plugin.yml": MINECRAFT_PLUGIN_YML,
        "src/main/java/neutral/relay/RelayPlugin.java": (
            "package neutral.relay;\n\n"
            "public final class RelayPlugin extends org.bukkit.plugin.java.JavaPlugin {\n"
            "    public boolean deliverOnce() { return Delivery.once(); }\n"
            "    public int restoreCapacity() { return Capacity.restore(); }\n"
            "}\n"
        ),
        "src/main/java/neutral/relay/Delivery.java": (
            "package neutral.relay;\n\nfinal class Delivery {\n"
            "    static boolean once() { return true; }\n}\n"
        ),
        "src/main/java/neutral/relay/Capacity.java": (
            "package neutral.relay;\n\nfinal class Capacity {\n"
            "    static int restore() { return 1; }\n}\n"
        ),
    }
    base_files = {
        **fixed_files,
        "src/main/java/neutral/relay/Delivery.java": fixed_files[
            "src/main/java/neutral/relay/Delivery.java"
        ].replace("return true", "return false"),
        "src/main/java/neutral/relay/Capacity.java": fixed_files[
            "src/main/java/neutral/relay/Capacity.java"
        ].replace("return 1", "return 0"),
    }
    provenance = tuple(
        fix.model_copy(
            update={"game_id": "minecraft", "changed_files": (f"src/main/java/upstream/Path{index}.java",)}
        )
        for index, fix in enumerate(dst_bundle.provenance, 1)
    )
    return dst_bundle.model_copy(
        update={
            "candidate": candidate,
            "fixed": GeneratedProject(project_name="neutral-relay", files=fixed_files),
            "base": DefectiveProject(
                files=base_files,
                defects=(
                    DefectReport(
                        capsule_id=capsules[0].capsule_id,
                        symptom=capsules[0].observed_symptoms[0],
                        affected_files=("src/main/java/neutral/relay/Delivery.java",),
                    ),
                    DefectReport(
                        capsule_id=capsules[1].capsule_id,
                        symptom=capsules[1].observed_symptoms[0],
                        affected_files=("src/main/java/neutral/relay/Capacity.java",),
                    ),
                ),
                ablations={
                    capsules[0].capsule_id: {
                        **fixed_files,
                        "src/main/java/neutral/relay/Delivery.java": base_files[
                            "src/main/java/neutral/relay/Delivery.java"
                        ],
                    },
                    capsules[1].capsule_id: {
                        **fixed_files,
                        "src/main/java/neutral/relay/Capacity.java": base_files[
                            "src/main/java/neutral/relay/Capacity.java"
                        ],
                    },
                },
            ),
            "verifier": VerifierBundle(
                files={
                    "tests/TaskSuite.java": minecraft_suite(),
                    "tests/test.sh": render_test_script(MINECRAFT_CASE_IDS),
                },
                case_ids=MINECRAFT_CASE_IDS,
                capsule_cases={
                    capsules[0].capsule_id: ("delivers once",),
                    capsules[1].capsule_id: ("restores capacity",),
                },
            ),
            "provenance": provenance,
        }
    )


@pytest.fixture
def minecraft_interface_contract(minecraft_bundle: SynthesisBundle) -> SynthInterfaceContract:
    capsules = minecraft_bundle.candidate.capsules
    return SynthInterfaceContract.model_validate(
        {
            "schema_version": 2,
            "game_id": "minecraft",
            "project_name": minecraft_bundle.fixed.project_name,
            "loader_identity": "NeutralRelay",
            "metadata_files": {"src/main/resources/plugin.yml": MINECRAFT_PLUGIN_YML},
            "project_files": list(minecraft_bundle.fixed.files),
            "modules": [
                {
                    "path": "src/main/java/neutral/relay/RelayPlugin.java",
                    "identifier": "NeutralRelay",
                    "loading": "Bukkit.getPluginManager().getPlugin(\"NeutralRelay\") after enable.",
                }
            ],
            "entrypoints": [
                {
                    "id": "deliver-once",
                    "module_identifier": "NeutralRelay",
                    "trigger": "public boolean deliverOnce() on the plugin main class",
                    "signature": "public boolean deliverOnce()",
                    "return_type": "boolean",
                    "return_schema": "true for a successful single delivery, false otherwise",
                    "observation_channel": "return-value",
                    "inputs": [],
                    "observable_outcomes": ["The delivery succeeds at most once."],
                },
                {
                    "id": "restore-capacity",
                    "module_identifier": "NeutralRelay",
                    "trigger": "public int restoreCapacity() on the plugin main class",
                    "signature": "public int restoreCapacity()",
                    "return_type": "int",
                    "return_schema": "the number of restored capacity units, at least 1 after a failure",
                    "observation_channel": "return-value",
                    "inputs": [],
                    "observable_outcomes": ["Failed delivery restores capacity."],
                },
            ],
            "capsule_entrypoints": {
                capsules[0].capsule_id: ["deliver-once"],
                capsules[1].capsule_id: ["restore-capacity"],
            },
        }
    )


@pytest.fixture
def passing_validation(dst_bundle: SynthesisBundle) -> ValidationReport:
    return ValidationReport(
        candidate_id=dst_bundle.candidate.id,
        complete=True,
        passed=True,
        base_failed=True,
        gold_passed=True,
        engine_backed=True,
    )


@pytest.fixture(autouse=True)
def _stable_umask() -> Iterator[None]:
    yield
