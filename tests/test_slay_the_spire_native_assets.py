"""Frozen native task integrity and recorded author controls."""
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest

PACK = Path(__file__).parents[1] / "benchmarks/slay-the-spire-core"
VALIDATION = PACK / "validation/native-engine"
TASKS = (
    "basemod-dynamic-descriptions-r2", "stslib-block-ledger-r1", "mts-enum-identity-r2",
    "stslib-icon-layout-r1", "downfall-stasis-lifecycle-r1",
    "basemod-phase-transitions-r1", "downfall-socket-flow-r2",
)


@pytest.mark.parametrize("task", TASKS)
def test_native_task_bytes_match_measured_manifest(task: str) -> None:
    source = PACK / "private/harbor" / task
    manifest = json.loads((VALIDATION / task / "frozen-manifest.json").read_text())
    actual = {
        path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source.rglob("*") if path.is_file()
    }
    assert actual == manifest["files"]
    assert (PACK / "exams" / f"{task}.md").read_bytes() == (source / "instruction.md").read_bytes()
    assert not any(path.is_symlink() for path in source.rglob("*"))
    assert not any(Path(name).suffix.lower() in {".jar", ".class", ".env", ".dll", ".so"} for name in actual)
    settings = tomllib.loads((source / "task.toml").read_text())
    assert settings["environment"]["network_mode"] == "no-network"
    assert settings["verifier"]["environment_mode"] == "separate"
    assert settings["verifier"]["environment"]["network_mode"] == "no-network"


@pytest.mark.parametrize("task", TASKS)
def test_native_controls_and_fairness_reviews_are_recorded(task: str) -> None:
    controls = json.loads((VALIDATION / task / "author-controls.json").read_text())
    if task in {"basemod-phase-transitions-r1", "downfall-socket-flow-r2"}:
        fairness = VALIDATION / task / "fairness-review.md"
        assert hashlib.sha256(fairness.read_bytes()).hexdigest() == controls["fairness_review_sha256"]
    matrix = {row["variant"]: row for row in controls["matrix_results"]}
    for name in ("gold", "alternative"):
        assert matrix[name]["passed"] == matrix[name]["expected"]
        assert not matrix[name]["failed_case_ids"]
    assert matrix["base"]["passed"] < matrix["base"]["expected"]
    gates = {row["agent"]: row for row in controls["formal_controls"]}
    assert gates["nop"]["reward"] == 0 and gates["oracle"]["reward"] == 1
    assert gates["oracle"]["passed"] == gates["oracle"]["expected"]


def test_native_tasks_bind_the_steam_runtime_that_pins_the_recorded_game() -> None:
    catalog = json.loads((PACK / "catalog.json").read_text())
    assert catalog["version"] == "1.8.0" and len(catalog["tasks"]) == 9
    retired = {"downfall-socket-flow-r2", "mts-enum-identity-r2"}
    revisions = {
        "downfall-socket-flow-r3", "mts-enum-identity-r3",
        "mts-load-order-regressions-r2", "mts-mod-identity-regressions-r2",
    }
    active = set(TASKS) - retired | revisions
    assert active <= {row["id"] for row in catalog["tasks"]}
    loader_retired = {
        "mts-load-order-regressions", "mts-mod-identity-regressions", "mts-loader-internals-regressions",
    }
    assert not (retired | loader_retired) & {row["id"] for row in catalog["tasks"]}
    runtimes = json.loads((PACK / "runtimes.json").read_text())
    native = next(spec for spec in runtimes["runtimes"] if spec["provider"] == "steam")
    assert native["version"] == "Steam build 10180494; catalog 1.7.0"
    assert set(runtimes["task_bindings"]) == active
    prepared = json.loads((VALIDATION / "tasks.json").read_text())
    assert {row["id"] for row in prepared} == set(runtimes["task_bindings"])
    assert all(ids == [native["id"]] for ids in runtimes["task_bindings"].values())
    runtime = PACK / "private/native-runtime"
    manifest = json.loads((runtime / "recipe-manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((runtime / name).read_bytes()).hexdigest() == digest
    game = json.loads((runtime / "game-input.json").read_text())
    assert game["restricted"] and game["source"]["appId"] == 646570
    assert {key: native["source"][key] for key in ("kind", "appId", "depots")} == {
        key: game["source"][key] for key in ("kind", "appId", "depots")
    }
    assert native["source"]["sha256"] == game["expected_sha256"]


def test_downfall_resource_recipe_pins_public_source_without_bundling_archive() -> None:
    recipe = PACK / "private/native-runtime/deps/downfall-foundation"
    lock = json.loads((recipe / "source-lock.json").read_text())
    receipt_path = recipe / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert lock["foundation_receipt_sha256"] == hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    assert lock["commit"] == receipt["commit"] == "030ff7d4a7419a3e21c3075661550b1b479f3502"
    assert lock["url"] == "https://github.com/mikemayhemdev/DownfallSTS.git"
    assert len(receipt["resource_files"]) == 8104
    assert set(lock["resource_transforms"]) <= set(receipt["resource_files"])
    assert all(row["kind"] == "checkout-crlf" for row in lock["resource_transforms"].values())
    metadata_digest = hashlib.sha256((recipe / "ModTheSpire.json").read_bytes()).hexdigest()
    assert metadata_digest == receipt["resource_files"]["ModTheSpire.json"]
    assert not any(path.suffix in {".tar", ".jar", ".class", ".env"} for path in recipe.rglob("*"))
