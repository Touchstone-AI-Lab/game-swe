from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rhenium.config import Settings
from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask
from rhenium.core.plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    PluginDescriptor,
)
from rhenium.core.runtime import RuntimeArtifact
from rhenium.hub import BenchmarkHub


class FixtureEvaluator:
    def __init__(self, context: BenchmarkContext, calls: list[tuple[str, str]]):
        self.context = context
        self.calls = calls

    def runtime_status(self) -> dict[str, Any]:
        return {"id": "fixture-local", "available": True}

    def evaluate(
        self,
        submission: Path,
        task: BenchmarkTask,
        profile: str = "full",
        runtimes: dict[str, RuntimeArtifact] | None = None,
    ) -> dict[str, Any]:
        del runtimes
        self.calls.append((task.id, profile))
        answer = submission / "answer.txt"
        matches = (
            answer.is_file()
            and answer.read_text(encoding="utf-8")
            == (self.context.pack_root / "expected.txt").read_text(encoding="utf-8")
        )
        complete = profile == "full"
        passed = complete and matches
        return {
            "score": 100.0 if passed else 25.0 if answer.is_file() else 0.0,
            "complete": complete,
            "passed": passed,
            "checks": [
                {
                    "id": "fixture-contract",
                    "status": "passed" if passed else "skipped" if not complete else "failed",
                }
            ],
            "runtime": {"status": "passed" if passed else "skipped"},
            "runtime_log": f"fixture profile={profile}\n",
        }


class FixturePlugin(BenchmarkPlugin):
    def __init__(self, plugin_id: str = "fixture", game_id: str = "fixture"):
        self.descriptor = PluginDescriptor(
            id=plugin_id,
            game_id=game_id,
            name=f"{game_id.title()} fixture",
            version="0.5.0",
            capabilities=("deterministic",),
        )
        self.calls: list[tuple[str, str]] = []
        self.contexts: list[BenchmarkContext] = []

    def load_catalog(self, pack_root: Path, catalog_path: str) -> BenchmarkCatalog:
        root = pack_root.resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("fixture catalog is missing")
        catalog = BenchmarkCatalog.model_validate_json(path.read_text(encoding="utf-8"))
        if catalog.game != self.game_id:
            raise ValueError("fixture catalog targets the wrong game")
        return catalog

    def create_evaluator(self, context: BenchmarkContext) -> EvaluationBackend:
        self.contexts.append(context)
        return FixtureEvaluator(context, self.calls)


def write_fixture_pack(
    benchmark_root: Path,
    *,
    plugin_id: str = "fixture",
    game_id: str = "fixture",
    pack_id: str = "core",
    task_id: str = "shared-task",
    directory: str | None = None,
) -> Path:
    pack = benchmark_root / (directory or f"{game_id}-{pack_id}")
    pack.mkdir(parents=True)
    (pack / "benchmark.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "pack_id": pack_id,
                "plugin": plugin_id,
                "catalog": "catalog.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    catalog = {
        "id": f"{game_id}-{pack_id}-v1",
        "version": "1.0.0",
        "game": game_id,
        "name": {"en": "Fixture pack", "zh": "测试包"},
        "description": {"en": "Fixture description", "zh": "测试说明"},
        "tasks": [
            {
                "id": task_id,
                "difficulty": "test",
                "title": {"en": "Write an answer", "zh": "写出答案"},
                "summary": {"en": "Create one text file.", "zh": "创建一个文本文件。"},
                "brief": {"en": "Write the requested answer.", "zh": "写入要求的答案。"},
                "requirements": {"en": ["Create answer.txt."], "zh": ["创建 answer.txt。"]},
                "api_usage": {"en": ["Use UTF-8 text."], "zh": ["使用 UTF-8 文本。"]},
                "acceptance": {"en": ["The answer is exact."], "zh": ["答案完全一致。"]},
                "domains": ["contract"],
                "estimated_minutes": 1,
                "required_files": ["answer.txt"],
            }
        ],
    }
    (pack / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (pack / "expected.txt").write_text("fixture-ok\n", encoding="utf-8")
    return pack / "benchmark.json"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    state = tmp_path / "state"
    return Settings(
        root=tmp_path,
        state_dir=state,
        cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}",
        benchmark_paths=(tmp_path / "benchmarks",),
        web_dist=None,
    )


@pytest.fixture
def fixture_plugin() -> FixturePlugin:
    return FixturePlugin()


@pytest.fixture
def fixture_manifest(settings: Settings) -> Path:
    return write_fixture_pack(settings.benchmark_paths[0])


@pytest.fixture
def hub(
    settings: Settings,
    fixture_plugin: FixturePlugin,
    fixture_manifest: Path,
) -> BenchmarkHub:
    return BenchmarkHub(
        settings,
        plugins={fixture_plugin.id: fixture_plugin},
        manifest_paths=(fixture_manifest,),
    )


@pytest.fixture
def sample_mod(tmp_path: Path) -> Path:
    root = tmp_path / "sample-mod"
    root.mkdir()
    (root / "modinfo.lua").write_text(
        'name = "Static Sword"\napi_version = 10\ndst_compatible = true\n'
        "all_clients_require_mod = true\nclient_only_mod = false\n",
        encoding="utf-8",
    )
    (root / "modmain.lua").write_text(
        'local DAMAGE = 68\nAddPrefabPostInit("spear", function(inst)\n'
        '    inst:AddTag("rhenium_sword")\nend)\n',
        encoding="utf-8",
    )
    return root
