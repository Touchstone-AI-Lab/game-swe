from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from rhenium_balatro.evaluator import BalatroEvaluator

from rhenium.api import create_app
from rhenium.config import Settings
from rhenium.hub import BenchmarkHub

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "benchmarks/balatro"


def test_balatro_api_profiles_health_and_untrusted_no_fallback(tmp_path: Path) -> None:
    project = tmp_path / "project"
    state = project / "state"
    settings = Settings(root=project, state_dir=state, cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}", benchmark_paths=(PACK,), web_dist=None)
    hub = BenchmarkHub(settings, manifest_paths=(PACK / "benchmark.json",))
    app = create_app(settings, hub=hub)
    key = hub.task_keys[0]
    with TestClient(app) as client, patch.object(app.state.jobs, "start") as start:
        listing = client.get("/api/tasks", params={"game": "balatro", "pack": "core"})
        assert listing.status_code == 200 and len(listing.json()["tasks"]) == 10
        assert listing.json()["tasks"][0]["profiles"][-1]["complete_eligible"] is True
        health = client.get("/api/health")
        assert health.status_code == 200
        assert client.post(f"/api/games/balatro/packs/core/tasks/{key.split('/')[-1]}/runs",
                           params={"profile": "invalid"}).status_code == 400
        start.assert_not_called()  # No model job is launched by this test.
    attempt = tmp_path / "attempt"
    hub.prepare_attempt(key, attempt, "strict", tmp_path / "score-wrapper")
    with patch.object(BalatroEvaluator, "evaluate", side_effect=AssertionError("local fallback")) as local:
        result = hub.evaluate_attempt(attempt, security_mode="untrusted",
                                      host_provider="missing", host_image="sha256:missing")
        local.assert_not_called()
    assert result["result"]["complete"] is False and result["result"]["passed"] is False
    assert key not in str(result)
