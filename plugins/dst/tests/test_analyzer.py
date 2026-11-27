from __future__ import annotations

from pathlib import Path

from rhenium_dst.analyzer import ModAnalyzer, strip_lua_comments


def test_analyzer_reports_structure_and_server_integration(sample_mod: Path) -> None:
    analysis = ModAnalyzer().analyze(sample_mod)

    assert analysis["valid"] is True
    assert analysis["server_compatible"] is True
    assert analysis["category"] == "stateful-components"
    assert analysis["counters"]["prefab_hooks"] == 1
    assert analysis["lua_files"] == 2
    assert analysis["code_lines"] >= 7
    assert "mutation_targets" not in analysis


def test_analyzer_rejects_lua_syntax_errors(sample_mod: Path) -> None:
    (sample_mod / "broken.lua").write_text("local value = function(\n", encoding="utf-8")

    analysis = ModAnalyzer().analyze(sample_mod)

    assert analysis["valid"] is False
    assert analysis["syntax_errors"][0]["file"] == "broken.lua"


def test_analyzer_counts_network_and_action_contracts(tmp_path: Path) -> None:
    (tmp_path / "modinfo.lua").write_text(
        'name = "Network"\napi_version = 10\ndst_compatible = true\n', encoding="utf-8"
    )
    (tmp_path / "modmain.lua").write_text(
        'AddReplicableComponent("registry")\n'
        'AddModRPCHandler("forge", "request", function(player) end)\n'
        'AddAction("FORGE_ACT", "Act", function(act) return true end)\n'
        'local active = net_bool(inst.GUID, "forge.active", "forgedirty")\n',
        encoding="utf-8",
    )

    analysis = ModAnalyzer().analyze(tmp_path)

    assert analysis["category"] == "networking"
    assert analysis["counters"]["replicas"] == 1
    assert analysis["counters"]["rpc_handlers"] == 1
    assert analysis["counters"]["network_variables"] == 1
    assert analysis["counters"]["actions"] == 1


def test_comment_stripping_prevents_documentation_from_counting(tmp_path: Path) -> None:
    (tmp_path / "modinfo.lua").write_text(
        'name = "Comments"\napi_version = 10\ndst_compatible = true\n', encoding="utf-8"
    )
    (tmp_path / "modmain.lua").write_text(
        '--[[ AddModRPCHandler("fake", "fake", function() end) ]]\n'
        'local documentation = "AddReplicableComponent(\\"fake\\")"\n'
        'AddComponentPostInit("container", function(self) end)\n',
        encoding="utf-8",
    )

    analysis = ModAnalyzer().analyze(tmp_path)

    assert analysis["counters"]["rpc_handlers"] == 0
    assert analysis["counters"]["replicas"] == 0
    assert analysis["counters"]["components"] == 1
    assert "AddModRPCHandler" not in strip_lua_comments("-- AddModRPCHandler()")
