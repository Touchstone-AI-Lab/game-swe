from __future__ import annotations

from pathlib import Path

import pytest
from rhenium_garrys_mod.plugin import GarrysModBenchmarkPlugin

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub
from tests.evaluation_host_helpers import FakeDisposableHost

ROOT = Path(__file__).parents[3]
# One task per evaluator: the GLuaTest container path (DarkRP) and the native App 4020
# path (the Addons construction pack). Neither may run locally in untrusted mode.
CASES = (
    (ROOT / "benchmarks" / "darkrp-core", "garrys-mod/darkrp/darkrp-money-regressions"),
    (ROOT / "benchmarks" / "gmod", "garrys-mod/addons/prop-ownership-quota-registry"),
)


@pytest.mark.parametrize(("pack", "task_key"), CASES)
def test_gmod_untrusted_evaluation_uses_common_disposable_policy(
    tmp_path: Path, pack: Path, task_key: str
) -> None:
    state = tmp_path / "state"
    provider = FakeDisposableHost()
    hub = BenchmarkHub(
        Settings(
            root=ROOT,
            state_dir=state,
            cache_dir=state / "cache",
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(pack,),
            web_dist=None,
        ),
        plugins={"garrys-mod": GarrysModBenchmarkPlugin()},
        evaluation_hosts={provider.id: provider},
        manifest_paths=(pack / "benchmark.json",),
    )
    submission = tmp_path / "submission"
    submission.mkdir()

    result = hub.evaluate_task(
        task_key,
        submission,
        security_mode="untrusted",
        host_provider=provider.id,
        host_image="sha256:trusted-image",
    )

    assert result["status"] == "passed"
    assert result["result"]["security"]["attested"] is True
    assert result["result"]["hostAttestation"]["provider"] == provider.id


@pytest.mark.parametrize(("pack", "task_key"), CASES)
def test_gmod_untrusted_evaluation_never_uses_local_fallback(
    tmp_path: Path, pack: Path, task_key: str
) -> None:
    state = tmp_path / "state"
    hub = BenchmarkHub(
        Settings(
            root=ROOT,
            state_dir=state,
            cache_dir=state / "cache",
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(pack,),
            web_dist=None,
        ),
        plugins={"garrys-mod": GarrysModBenchmarkPlugin()},
        evaluation_hosts={},
        manifest_paths=(pack / "benchmark.json",),
    )
    submission = tmp_path / "submission"
    submission.mkdir()

    result = hub.evaluate_task(
        task_key,
        submission,
        security_mode="untrusted",
    )

    assert result["status"] == "failed"
    assert result["result"]["score"] == 0
    assert result["result"]["complete"] is False
