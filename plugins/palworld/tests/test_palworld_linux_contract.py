from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rhenium_palworld.catalog import PalworldCatalog

from rhenium.core.runtime import RuntimeCatalog

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks/palworld"
RUNTIME = ROOT / "plugins/palworld/runtime/linux"


def test_native_linux_runtime_is_managed_pinned_and_covers_current_tasks() -> None:
    inventory = RuntimeCatalog.load(PACK, "runtimes.json")
    catalog = PalworldCatalog.load(PACK)
    assert len(inventory.runtimes) == 1
    runtime = inventory.runtimes[0]
    assert runtime.host_platforms == ("linux-x64",)
    assert runtime.provider == "steam" and runtime.restricted
    assert runtime.source["kind"] == "steam-depots"
    assert runtime.source["depots"] == [
        {"id": 1006, "manifest": "4559160656493359681"},
        {"id": 2394012, "manifest": "7031055933861146620"},
    ]
    assert inventory.task_bindings == {task.id: (runtime.id,) for task in catalog.tasks}
    # All tasks use the registered managed runtime.
    manifest = json.loads((PACK / "benchmark.json").read_text())
    assert manifest["runtime_catalog"] == "runtimes.json"


def test_checked_in_launcher_matches_the_real_engine_control_pin() -> None:
    pins = json.loads((RUNTIME / "pins.json").read_text())
    assert len(pins) == 7
    assert hashlib.sha256((RUNTIME / "run-native").read_bytes()).hexdigest() == pins["run-native"]
    assert hashlib.sha256((RUNTIME / "uehelpers-world.patch").read_bytes()).hexdigest() == (
        "eab5b07c71ca537a1621e729ac7aebc4ae32150cda32632531b9aba1fcf1d8e7"
    )
