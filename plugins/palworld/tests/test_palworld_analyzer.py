from __future__ import annotations

import json
from pathlib import Path

import pytest
from rhenium_palworld.analyzer import ModAnalyzer, strip_lua_comments


@pytest.fixture
def sample_mod(tmp_path: Path) -> Path:
    root = tmp_path / "sample-mod"
    (root / "scripts").mkdir(parents=True)
    (root / "Info.json").write_text(
        json.dumps(
            {
                "PackageName": "RheniumSample",
                "Version": "1.0.0",
                "DebugMode": False,
                "InstallRule": [
                    {"Type": "Lua", "Targets": ["./scripts"], "IsServer": True},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "scripts/main.lua").write_text(
        'local UEHelpers = require("UEHelpers")\n'
        "local pre, post = RegisterHook(\n"
        '    "/Script/Engine.PlayerController:ServerAcknowledgePossession",\n'
        "    function(Context)\n"
        "        local Controller = Context:get()\n"
        "        if Controller ~= nil and Controller:IsValid() then\n"
        "            RheniumService = Controller\n"
        "        end\n"
        "    end)\n"
        'UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)\n',
        encoding="utf-8",
    )
    return root


def test_analyzer_reports_structure_and_server_package(sample_mod: Path) -> None:
    analysis = ModAnalyzer().analyze(sample_mod)

    assert analysis["valid"] is True
    assert analysis["server_compatible"] is True
    assert analysis["category"] == "engine-hooks"
    assert analysis["counters"]["hooks"] == 1
    assert analysis["counters"]["hook_removals"] == 1
    assert analysis["lua_files"] == 1
    assert analysis["code_lines"] >= 9
    assert analysis["package"]["package_name"] == "RheniumSample"
    assert analysis["package"]["lua_install_rules"] == 1
    assert "mutation_targets" not in analysis


def test_analyzer_rejects_lua_syntax_errors(sample_mod: Path) -> None:
    (sample_mod / "scripts/broken.lua").write_text("local value = function(\n", encoding="utf-8")

    analysis = ModAnalyzer().analyze(sample_mod)

    assert analysis["valid"] is False
    assert analysis["syntax_errors"][0]["file"] == "scripts/broken.lua"


def test_analyzer_requires_the_ue4ss_entry_point(sample_mod: Path) -> None:
    (sample_mod / "scripts/main.lua").rename(sample_mod / "scripts/Main.lua")

    analysis = ModAnalyzer().analyze(sample_mod)

    assert analysis["valid"] is False
    assert analysis["syntax_errors"] == []


def test_analyzer_flags_a_client_only_package(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/main.lua").write_text("local value = 1\n", encoding="utf-8")
    (tmp_path / "Info.json").write_text(
        json.dumps({"PackageName": "ClientOnly", "InstallRule": [{"Type": "Lua"}]}) + "\n",
        encoding="utf-8",
    )

    analysis = ModAnalyzer().analyze(tmp_path)

    assert analysis["server_compatible"] is False
    assert analysis["package"]["server_install_rules"] == 0


def test_analyzer_counts_console_and_scheduling_contracts(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "Info.json").write_text('{"PackageName": "Counters"}\n', encoding="utf-8")
    (tmp_path / "scripts/main.lua").write_text(
        'RegisterConsoleCommandGlobalHandler("rhenium_supply", function(Cmd, Parts, Ar) return true end)\n'
        'NotifyOnNewObject("PalPlayerCharacter", function(Character) end)\n'
        "LoopAsync(1000, function() return false end)\n"
        "ExecuteInGameThread(function() end)\n"
        'local target = FindFirstOf("PalPlayerController")\n',
        encoding="utf-8",
    )

    analysis = ModAnalyzer().analyze(tmp_path)

    assert analysis["category"] == "server-commands"
    assert analysis["counters"]["console_commands"] == 1
    assert analysis["counters"]["object_notifications"] == 1
    assert analysis["counters"]["async_tasks"] == 1
    assert analysis["counters"]["game_thread_calls"] == 1
    assert analysis["counters"]["object_lookups"] == 1


def test_comment_stripping_prevents_documentation_from_counting(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "Info.json").write_text('{"PackageName": "Comments"}\n', encoding="utf-8")
    (tmp_path / "scripts/main.lua").write_text(
        '--[[ RegisterConsoleCommandGlobalHandler("fake", function() end) ]]\n'
        'local documentation = "NotifyOnNewObject(\\"fake\\", function() end)"\n'
        'RegisterHook("/Script/Engine.PlayerController:ClientRestart", function() end)\n',
        encoding="utf-8",
    )

    analysis = ModAnalyzer().analyze(tmp_path)

    assert analysis["counters"]["console_commands"] == 0
    assert analysis["counters"]["object_notifications"] == 0
    assert analysis["counters"]["hooks"] == 1
    assert "RegisterHook" not in strip_lua_comments("-- RegisterHook()")
