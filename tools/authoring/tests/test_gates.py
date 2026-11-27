from __future__ import annotations

from typing import Any

import pytest
from rhenium_authoring.gates import LeakageError, validate_public_candidate


@pytest.mark.parametrize(
    "text",
    [
        "@Override public void onEnable() {}",
        "@EventHandler public void onJoin(PlayerJoinEvent event) {}",
        '@GcbCase("plugin is enabled") public void enabled() {}',
        "/** @param sender the console sender @return true when handled */",
        "{@code deliverOnce()} and {@link JavaPlugin}",
    ],
)
def test_java_annotations_and_javadoc_tags_are_not_social_handles(dst_bundle: Any, text: str) -> None:
    validate_public_candidate(dst_bundle.provenance, [text], [])


@pytest.mark.parametrize("text", ["Reported by @maintainer", "thanks @some_dev for the fix"])
def test_lowercase_handles_are_still_rejected(dst_bundle: Any, text: str) -> None:
    with pytest.raises(LeakageError, match="identifier"):
        validate_public_candidate(dst_bundle.provenance, [text], [])


def test_jvm_layout_paths_do_not_poison_identity_terms(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(
        update={
            "game_id": "minecraft",
            "repository_url": "https://github.com/example/clockworkrelay",
            "changed_files": (
                "src/main/java/com/example/clockworkrelay/listener/RelayListener.java",
                "src/main/java/com/example/clockworkrelay/command/RelayCommand.java",
                "src/main/resources/plugin.yml",
                "build.gradle.kts",
            ),
        }
    )
    validate_public_candidate(
        (fix,),
        [
            "A listener registered from the plugin main class handles the command; "
            "resources hold plugin.yml and the build.gradle.kts stays frozen."
        ],
        [],
    )
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["Ported from clockworkrelay."], [])
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((fix,), ["See RelayListener for details."], [])


def test_minecraft_public_vocabulary_is_allowed_only_for_minecraft(dst_bundle: Any) -> None:
    changed = ("src/main/java/acme/JavaPlugin.java", "src/main/java/acme/CommandSender.java")
    minecraft_fix = dst_bundle.provenance[0].model_copy(
        update={"game_id": "minecraft", "changed_files": changed}
    )
    text = ["The JavaPlugin registers a CommandSender reply through Bukkit."]
    validate_public_candidate((minecraft_fix,), text, [])
    lua_fix = dst_bundle.provenance[0].model_copy(update={"changed_files": changed})
    with pytest.raises(LeakageError, match="identity"):
        validate_public_candidate((lua_fix,), text, [])


def test_java_keywords_are_not_identity_terms(dst_bundle: Any) -> None:
    fix = dst_bundle.provenance[0].model_copy(
        update={"repository_url": "https://github.com/example/implements"}
    )
    validate_public_candidate((fix,), ["public final class TaskSuite implements GcbSuite {}"], [])


def test_plain_english_package_directories_are_not_identity_terms() -> None:
    from rhenium_authoring.gates import _sensitive_terms
    from rhenium_authoring.models import HistoricalFix

    fix = HistoricalFix(
        id="seed-one",
        game_id="minecraft",
        repository_url="https://github.com/example/ExampleInventories",
        license_spdx="MIT",
        base_sha="a" * 40,
        fixed_sha="b" * 40,
        issue_text="x",
        patch="--- a/x\n+++ b/x\n",
        changed_files=("src/main/java/org/example/share/Sharables.java",),
    )
    terms = _sensitive_terms((fix,))
    assert "share" not in terms
    assert "sharables" in terms and "exampleinventories" in terms
