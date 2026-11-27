from __future__ import annotations

from pathlib import Path

from rhenium_dst.plugin import DstBenchmarkPlugin

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub
from tests.evaluation_host_helpers import FakeDisposableHost

ROOT = Path(__file__).parents[3]
PACK = ROOT / "benchmarks" / "dst"


def test_dst_untrusted_evaluation_uses_common_disposable_host_policy(tmp_path: Path) -> None:
    state = tmp_path / "state"
    provider = FakeDisposableHost()
    hub = BenchmarkHub(
        Settings(
            root=ROOT,
            state_dir=state,
            cache_dir=state / "cache",
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(PACK,),
            web_dist=None,
        ),
        plugins={"dst": DstBenchmarkPlugin()},
        evaluation_hosts={provider.id: provider},
        manifest_paths=(PACK / "benchmark.json",),
    )
    submission = tmp_path / "submission"
    submission.mkdir()

    result = hub.evaluate_task(
        "dst/core/dst-fixed-bundle-regressions",
        submission,
        security_mode="untrusted",
        host_provider=provider.id,
        host_image="sha256:trusted-image",
    )

    assert result["status"] == "passed"
    assert result["result"]["security"]["attested"] is True
    assert result["result"]["hostAttestation"]["provider"] == provider.id


def test_dst_untrusted_evaluation_without_host_fails_closed(tmp_path: Path) -> None:
    state = tmp_path / "state"
    hub = BenchmarkHub(
        Settings(
            root=ROOT,
            state_dir=state,
            cache_dir=state / "cache",
            database_url=f"sqlite:///{state / 'state.sqlite'}",
            benchmark_paths=(PACK,),
            web_dist=None,
        ),
        plugins={"dst": DstBenchmarkPlugin()},
        evaluation_hosts={},
        manifest_paths=(PACK / "benchmark.json",),
    )
    submission = tmp_path / "submission"
    submission.mkdir()

    result = hub.evaluate_task(
        "dst/core/dst-fixed-bundle-regressions",
        submission,
        security_mode="untrusted",
    )

    assert result["status"] == "failed"
    assert result["result"]["score"] == 0
    assert result["result"]["complete"] is False
