from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from rhenium_palworld.catalog import PalworldCatalog
from rhenium_palworld.evaluator import PalworldEvaluator
from rhenium_palworld.runtime import PalworldRuntimeConfig

pack = Path("/workspace/benchmarks/palworld")
evidence = Path("/evidence")
catalog = PalworldCatalog.load(pack)
evaluator = PalworldEvaluator(
    PalworldRuntimeConfig(
        pack_root=pack,
        palworld_root=Path("/server"),
        server_binary=Path("/server/run-native"),
    )
)
registry = Path("/server/ue4ss/Mods/mods.txt")
before = registry.read_bytes()
rows = []
shard = int(os.environ.get("CONTROL_SHARD", "0"))
shards = int(os.environ.get("CONTROL_SHARDS", "1"))
assert 0 <= shard < shards
excluded = set(os.environ.get("CONTROL_SKIP_TASKS", "").split(","))
for task_index, task in enumerate(catalog.tasks):
    if task_index % shards != shard or f"palworld/core/{task.id}" in excluded:
        continue
    expected_cases = len(re.findall(r"\bctx\s*:\s*case\s*\(", (pack / task.server_test).read_text()))
    assert expected_cases > 0
    for control in ("gold", "nop", "service-absent"):
        submission = evidence / "submissions" / task.id / control
        submission.mkdir(parents=True)
        if control == "gold":
            shutil.copytree(
                pack / "private/harbor" / task.id / "solution/reference", submission, dirs_exist_ok=True
            )
        elif control == "service-absent":
            (submission / "scripts").mkdir()
            (submission / "scripts/main.lua").write_text("local HEADLESS = true\n")
        start = time.monotonic()
        result = evaluator.evaluate(submission, task, profile="full")
        (evidence / f"{task.id}-{control}.json").write_text(json.dumps(result, indent=2))
        server = next(c for c in result["checks"] if c["id"] == "headless-server")
        row = {
            "task": f"palworld/core/{task.id}",
            "control_id": uuid.uuid4().hex,
            "control": control,
            "score": result["score"],
            "complete": result["complete"],
            "passed": result["passed"],
            "server_status": server["status"],
            "server_passed": server["details"]["passed"],
            "server_total": server["details"]["total"],
            "expected_server_total": expected_cases,
            "seconds": round(time.monotonic() - start, 2),
            "registry_restored": registry.read_bytes() == before,
            "remaining_mods": len(list(registry.parent.glob("rhenium_*"))),
        }
        rows.append(row)
        (evidence / "controls-summary.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)
        assert row["registry_restored"] and row["remaining_mods"] == 0
        if control == "gold":
            assert row["server_total"] == expected_cases, row
            assert result["complete"] and result["passed"] and result["score"] == 100, row
        elif control == "nop":
            assert not result["passed"] and not result["complete"], row
        else:
            assert row["server_total"] == expected_cases, row
            assert result["complete"] and not result["passed"], row
            assert row["server_total"] > 0 and row["server_passed"] < row["server_total"], row
print("ALL_CONTROLS_PASSED", flush=True)
