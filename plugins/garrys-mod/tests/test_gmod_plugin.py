from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from rhenium_garrys_mod.addons.catalog import GmodCatalog
from rhenium_garrys_mod.addons.evaluator import GmodEvaluator
from rhenium_garrys_mod.addons.server_runner import _environment
from rhenium_garrys_mod.addons.submission import (
    GmodSubmissionError,
    validate_submission_tree,
)
from rhenium_garrys_mod.darkrp.catalog import GarrysModCatalog
from rhenium_garrys_mod.darkrp.evaluator import GarrysModEvaluator
from rhenium_garrys_mod.plugin import RUNTIME_IDS, GarrysModBenchmarkPlugin

from rhenium.config import Settings
from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeSpec
from rhenium.hub import BenchmarkHub

ROOT = Path(__file__).parents[3]
# The clean-room Addons construction pack (native App 4020 runner).
PACK = ROOT / "benchmarks" / "gmod"
DARKRP = ROOT / "benchmarks" / "darkrp-core"
ADDONS = ROOT / "benchmarks" / "gmod-addon-repairs"


def _settings(tmp_path: Path) -> Settings:
    state = tmp_path / "state"
    return Settings(
        root=ROOT,
        state_dir=state,
        cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}",
        benchmark_paths=(ROOT / "benchmarks",),
        web_dist=None,
    )


def _hub(tmp_path: Path) -> BenchmarkHub:
    return BenchmarkHub(
        _settings(tmp_path),
        plugins={"garrys-mod": GarrysModBenchmarkPlugin()},
        manifest_paths=(DARKRP / "benchmark.json", ADDONS / "benchmark.json"),
    )


def test_one_plugin_serves_the_darkrp_and_addon_repair_packs(tmp_path: Path) -> None:
    hub = _hub(tmp_path)

    assert [game["id"] for game in hub.list_games()] == ["garrys-mod"]
    assert {item["key"] for item in hub.list_packs()} == {
        "garrys-mod/darkrp",
        "garrys-mod/addon-repairs",
    }
    assert len(hub.list_tasks(game_id="garrys-mod", pack_id="darkrp")) == 7
    addon_tasks = GarrysModCatalog.load(ADDONS).tasks
    assert len(hub.list_tasks(game_id="garrys-mod", pack_id="addon-repairs")) == len(
        addon_tasks
    )
    assert len(addon_tasks) >= 5
    assert hub.health()["ok"] is True


def test_the_addons_construction_pack_keeps_its_own_subsystem(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    assert isinstance(plugin.load_catalog(PACK, "catalog.json"), GmodCatalog)
    for pack in (DARKRP, ADDONS):
        assert isinstance(plugin.load_catalog(pack, "catalog.json"), GarrysModCatalog)
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    assert isinstance(plugin.create_evaluator(context), GmodEvaluator)
    # The Addons pack uses the operator-prepared native server, never a managed runtime.
    for runtime_id in sorted(RUNTIME_IDS):
        spec = RuntimeSpec.model_validate(
            {
                "id": runtime_id,
                "name": "GLuaTest",
                "version": "1",
                "provider": "container",
                "host_platforms": ["linux-x64"],
                "source": {"kind": "container-image", "image": "example/gluatest"},
            }
        )
        assert plugin.create_runtime_builder(context, spec) is None
    assert not (PACK / "runtimes.json").exists()
    with pytest.raises(ValueError, match="missing"):
        GarrysModBenchmarkPlugin._catalog_id(ROOT / "benchmarks" / "missing-pack")


def test_each_pack_owns_a_separate_runtime_key(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    expected_ids = {"gmod-gluatest-darkrp", "gmod-gluatest-synth", "gmod-gluatest-addons"}
    assert expected_ids == RUNTIME_IDS
    source = {
        "kind": "container-image",
        "image": "ghcr.io/cfc-servers/gluatest/x86-64@sha256:"
        "23cd97d4fa9cf44fc16cabed6b973e117581769725b5735c533d10da7fe0b1fb",
    }
    for pack, own, other in (
        (DARKRP, "gmod-gluatest-darkrp", "gmod-gluatest-addons"),
        (ADDONS, "gmod-gluatest-addons", "gmod-gluatest-darkrp"),
    ):
        context = BenchmarkContext(
            project_root=ROOT,
            pack_root=pack,
            state_dir=tmp_path / "state",
            cache_dir=tmp_path / "cache",
        )

        def spec(runtime_id: str) -> RuntimeSpec:
            return RuntimeSpec.model_validate(
                {
                    "id": runtime_id,
                    "name": "GLuaTest",
                    "version": "1",
                    "provider": "container",
                    "host_platforms": ["linux-x64"],
                    "source": source,
                }
            )

        assert plugin.create_runtime_builder(context, spec(own)) is not None
        assert plugin.create_runtime_builder(context, spec(other)) is None
    darkrp_runtimes = (DARKRP / "runtimes.json").read_text(encoding="utf-8")
    addon_runtimes = (ADDONS / "runtimes.json").read_text(encoding="utf-8")
    assert '"id": "gmod-gluatest-darkrp"' in darkrp_runtimes
    assert '"id": "gmod-gluatest-addons"' in addon_runtimes
    assert "gmod-gluatest-darkrp" not in addon_runtimes


def test_attempt_contains_only_public_contract_and_guidance(tmp_path: Path) -> None:
    hub = _hub(tmp_path)
    task = GarrysModCatalog.load(ADDONS).tasks[0]
    attempt = tmp_path / "attempt"
    hub.prepare_attempt(
        f"garrys-mod/addon-repairs/{task.id}",
        attempt,
        "practice",
        ROOT / "scripts" / "score-exam",
    )

    assert {path.name for path in attempt.iterdir()} >= {
        "EXAM.md",
        "AGENTS.md",
        "CLAUDE.md",
        "PROMPT.md",
        task.starter_name,
    }
    assert not (attempt / "tests").exists()
    assert not (attempt / "solution").exists()
    assert not (attempt / task.starter_name / "lua" / "tests").exists()
    exam = (attempt / "EXAM.md").read_text(encoding="utf-8")
    assert "/app/" not in exam
    assert "/tests" not in exam


def test_anonymous_result_sanitizer_removes_private_runtime_protocol() -> None:
    plugin = GarrysModBenchmarkPlugin()
    result = plugin.sanitize_anonymous_result(
        {
            "score": 100.0,
            "runtime_log": "private raw runtime log",
            "analysis": {"privatePath": "private suite path"},
            "checks": [
                {
                    "id": "headless-server",
                    "status": "passed",
                    "details": {"cases": [{"name": "private-case-name"}]},
                }
            ],
            "runtime": {
                "error": "private/server/path",
                "run_id": "private-runtime-id",
                "submission_hash": "private-submission-hash",
                "audit": {
                    "passed": True,
                    "nonce": "private-nonce",
                    "marker_count": 1,
                    "evidence": {"assertions": ["private"]},
                    "output_tail": "private output",
                },
            },
        }
    )

    assert result == {
        "score": 100.0,
        "checks": [{"id": "headless-server", "status": "passed"}],
        "runtime": {"audit": {"passed": True}},
    }


def test_packs_are_not_modified_by_catalog_or_core_evaluation(tmp_path: Path) -> None:
    for pack, pack_id in ((DARKRP, "darkrp"), (ADDONS, "addon-repairs")):
        before = {
            path.relative_to(pack): path.read_bytes() for path in pack.rglob("*") if path.is_file()
        }
        catalog = GarrysModCatalog.load(pack)
        context = BenchmarkContext(
            project_root=ROOT,
            pack_root=pack,
            state_dir=tmp_path / pack_id / "state",
            cache_dir=tmp_path / pack_id / "cache",
        )
        task = catalog.tasks[0]
        plugin = GarrysModBenchmarkPlugin()
        submission = tmp_path / pack_id / "submission"
        plugin.materialize_starter(task, submission, context)
        direct = GarrysModEvaluator(context, catalog).evaluate(submission, task, profile="core")
        hub = _hub(tmp_path / pack_id / "hub")
        hub_result = hub.evaluate_task(
            f"garrys-mod/{pack_id}/{task.id}", submission, profile="core"
        )
        after = {
            path.relative_to(pack): path.read_bytes() for path in pack.rglob("*") if path.is_file()
        }

        assert direct["score"] == 10.0
        assert direct["complete"] is False
        assert hub_result["result"]["score"] == 10.0
        assert hub_result["status"] != "passed"
        assert after == before


def test_plugin_loads_through_the_game_neutral_hub(tmp_path: Path) -> None:
    plugin = GarrysModBenchmarkPlugin()
    hub = BenchmarkHub(
        _settings(tmp_path),
        plugins={"garrys-mod": plugin},
        manifest_paths=(PACK / "benchmark.json",),
    )

    assert plugin.descriptor.game_id == "garrys-mod"
    assert hub.task_keys == tuple(
        sorted(f"garrys-mod/addons/{task.id}" for task in GmodCatalog.load(PACK).tasks)
    )
    assert hub.health()["taskCount"] == 5
    assert hub.health()["ok"] is True


def test_one_plugin_loads_addons_darkrp_and_addon_repairs_as_independent_packs(
    tmp_path: Path,
) -> None:
    plugin = GarrysModBenchmarkPlugin()
    hub = BenchmarkHub(
        _settings(tmp_path),
        plugins={"garrys-mod": plugin},
        manifest_paths=(
            PACK / "benchmark.json",
            DARKRP / "benchmark.json",
            ADDONS / "benchmark.json",
        ),
    )

    assert [game["id"] for game in hub.list_games()] == ["garrys-mod"]
    assert {item["key"] for item in hub.list_packs()} == {
        "garrys-mod/addons",
        "garrys-mod/darkrp",
        "garrys-mod/addon-repairs",
    }
    assert len(hub.list_tasks(game_id="garrys-mod", pack_id="addons")) == 5
    assert len(hub.list_tasks(game_id="garrys-mod", pack_id="darkrp")) == 7
    assert len(hub.list_tasks(game_id="garrys-mod", pack_id="addon-repairs")) == 5
    assert hub.health()["ok"] is True


def test_hub_full_profile_uses_native_runtime_when_available(
) -> None:
    state_parent = ROOT / ".rhenium"
    state_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gmod-hub-native-", dir=state_parent) as raw:
        state = Path(raw)
        settings = Settings(
            root=ROOT,
            state_dir=state,
            cache_dir=state / "cache",
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(ROOT / "benchmarks",),
            web_dist=None,
        )
        hub = BenchmarkHub(
            settings,
            plugins={"garrys-mod": GarrysModBenchmarkPlugin()},
            manifest_paths=(PACK / "benchmark.json",),
        )
        runtime = hub.list_packs()[0]["runtime"]
        if not runtime["available"]:
            pytest.skip("pinned native GMod runtime is unavailable")
        task = GmodCatalog.load(PACK).tasks[0]
        reference = PACK / "private" / "tasks" / task.id / "references" / "table-registry"
        result = hub.evaluate_task(
            f"garrys-mod/addons/{task.id}", reference, profile="full"
        )
        hub.database.engine.dispose()

    assert result["score"] == 100.0, json.dumps(result["result"]["runtime"])
    assert result["status"] == "passed"
    assert result["result"]["complete"] is True


def test_addons_attempt_contains_only_public_contract_and_guidance(tmp_path: Path) -> None:
    hub = BenchmarkHub(
        _settings(tmp_path),
        plugins={"garrys-mod": GarrysModBenchmarkPlugin()},
        manifest_paths=(PACK / "benchmark.json",),
    )
    attempt = tmp_path / "attempt"
    hub.prepare_attempt(
        "garrys-mod/addons/prop-ownership-quota-registry",
        attempt,
        "practice",
        ROOT / "scripts" / "score-exam",
    )

    assert {path.name for path in attempt.iterdir()} >= {
        "EXAM.md",
        "AGENTS.md",
        "CLAUDE.md",
        "PROMPT.md",
    }
    public = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in attempt.rglob("*")
        if path.is_file()
    )
    task = GmodCatalog.load(PACK).tasks[0]
    assert not any(marker in public for marker in task.private_exam_markers())
    assert "private/tasks" not in public


def test_submission_policy_rejects_extra_files_and_links(tmp_path: Path) -> None:
    submission = tmp_path / "submission"
    (submission / "lua").mkdir(parents=True)
    (submission / "lua" / "main.lua").write_text("return true\n", encoding="utf-8")
    (submission / "addon.json").write_text('{"title":"x"}\n', encoding="utf-8")
    with pytest.raises(GmodSubmissionError, match="type must be servercontent"):
        validate_submission_tree(submission)

    (submission / "addon.json").write_text(
        '{"title":"x","type":"servercontent","ignore":[]}\n', encoding="utf-8"
    )
    (submission / "secret.txt").write_text("outside", encoding="utf-8")
    with pytest.raises(GmodSubmissionError, match="unsupported submission file"):
        validate_submission_tree(submission)
    (submission / "secret.txt").unlink()
    outside = tmp_path / "outside.lua"
    outside.write_text("return 'secret'\n", encoding="utf-8")
    try:
        (submission / "lua" / "linked.lua").symlink_to(outside)
    except OSError as error:
        pytest.skip(f"platform cannot create a file symlink: {error}")
    with pytest.raises(GmodSubmissionError, match="unsafe"):
        validate_submission_tree(submission)


def test_srcds_environment_is_a_secret_free_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets = {
        "OPENAI_API_KEY": "openai-secret",
        "ANTHROPIC_API_KEY": "anthropic-secret",
        "GITHUB_TOKEN": "github-secret",
        "SSH_AUTH_SOCK": "ssh-secret",
        "STEAM_PASSWORD": "steam-secret",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)
    environment = _environment(tmp_path)
    assert all(key not in environment for key in secrets)
    assert all(value not in environment.values() for value in secrets.values())
    assert environment["TEMP"] == str(tmp_path)
    assert environment["TMP"] == str(tmp_path)


def test_anonymous_result_sanitizer_removes_private_native_phase_protocol() -> None:
    plugin = GarrysModBenchmarkPlugin()
    result = plugin.sanitize_anonymous_result(
        {
            "score": 100.0,
            "runtime_log": "private raw runtime log",
            "analysis": {"privatePath": "private suite path"},
            "checks": [
                {
                    "id": "hidden-behavior",
                    "status": "passed",
                    "details": {"cases": [{"name": "private-case-name"}]},
                }
            ],
            "runtime": {
                "error": "D:/private/server/path",
                "run_id": "private-runtime-id",
                "submission_hash": "private-submission-hash",
                "phase_a": {
                    "passed": True,
                    "process_id": 1234,
                    "started_at_utc": "private-start-time",
                    "ended_at_utc": "private-end-time",
                    "command": ["private/runtime/srcds.exe"],
                    "nonce": "private-nonce",
                    "marker_count": 1,
                    "payload": {"evidenceHash": "private-hash"},
                    "evidence": {"assertions": ["private"]},
                    "output_tail": "private output",
                }
            },
        }
    )

    assert result == {
        "score": 100.0,
        "checks": [{"id": "hidden-behavior", "status": "passed"}],
        "runtime": {"phase_a": {"passed": True}},
    }


def test_addons_pack_is_not_modified_by_catalog_or_core_evaluation(
    tmp_path: Path,
) -> None:
    gmod_catalog = GmodCatalog.load(PACK)
    context = BenchmarkContext(
        project_root=ROOT,
        pack_root=PACK,
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    gmod_evaluator = GmodEvaluator(context, gmod_catalog)
    before = {
        path.relative_to(PACK): path.read_bytes()
        for path in PACK.rglob("*")
        if path.is_file()
    }
    task = gmod_catalog.tasks[0]
    reference = PACK / "private" / "tasks" / task.id / "references" / "table-registry"
    direct_result = gmod_evaluator.evaluate(reference, task, profile="core")
    hub = BenchmarkHub(
        _settings(tmp_path / "hub"),
        plugins={"garrys-mod": GarrysModBenchmarkPlugin()},
        manifest_paths=(PACK / "benchmark.json",),
    )
    attempt = tmp_path / "public-attempt"
    hub.prepare_attempt(
        f"garrys-mod/addons/{task.id}",
        attempt,
        "practice",
        ROOT / "scripts" / "score-exam",
    )
    hub_result = hub.evaluate_task(
        f"garrys-mod/addons/{task.id}", reference, profile="core"
    )
    after = {
        path.relative_to(PACK): path.read_bytes()
        for path in PACK.rglob("*")
        if path.is_file()
    }
    assert direct_result["score"] == 60.0
    assert hub_result["result"]["score"] == 60.0
    assert len(hub.list_tasks(game_id="garrys-mod", pack_id="addons")) == 5
    assert (attempt / "EXAM.md").is_file()
    assert next(iter(hub.benchmarks.values())).context.state_dir.is_relative_to(
        _settings(tmp_path / "hub").state_dir
    )
    assert after == before
