import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rhenium_balatro.linux_control import SMOKE_REQUIRED, require_smoke


def fixture() -> tuple[Any, dict[str, Any]]:
    # Parser fixtures only. These synthetic records never count as engine evidence.
    expected = {"environment": "env", "harness": "harness", "task": "task", "candidate": None}
    host = SimpleNamespace(
        fingerprints=lambda *_: expected,
        assets_sha256="assets",
        artifact=SimpleNamespace(identity="artifact"),
    )
    raw = {
        "complete": True,
        "passed": True,
        "classification": "pass",
        "not_executed": [],
        "checks": [
            {"id": name, "observed": True, "expected": True, "passed": True} for name in SMOKE_REQUIRED
        ],
        "processes": [
            {
                "run_id": "unit-fixture",
                "fingerprints": expected,
                "cleanup": {"normal_exit": True, "protected_unchanged": True},
            }
        ],
    }
    record = {
        "operation": "smoke",
        "fingerprints": expected,
        "assets_sha256": "assets",
        "artifact_identity": "artifact",
        "evaluation": raw,
    }
    return host, record


@pytest.mark.parametrize("defect", ["environment", "case", "cleanup", "bare_passed"])
def test_existing_smoke_file_and_pass_flag_are_insufficient(tmp_path: Path, defect: str) -> None:
    host, source = fixture()
    record = copy.deepcopy(source)
    if defect == "environment":
        record["fingerprints"]["environment"] = "different-environment"
    elif defect == "case":
        record["evaluation"]["checks"].pop()
    elif defect == "cleanup":
        record["evaluation"]["processes"][0]["cleanup"]["normal_exit"] = False
    else:
        record["evaluation"] = {"passed": True}
    path = tmp_path / "smoke.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="complete smoke"):
        require_smoke(host, path)


def test_matching_complete_smoke_is_revalidated(tmp_path: Path) -> None:
    host, record = fixture()
    path = tmp_path / "smoke.json"
    path.write_text(json.dumps(record))
    require_smoke(host, path)
