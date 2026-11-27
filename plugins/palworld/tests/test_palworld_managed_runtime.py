from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from rhenium_palworld.catalog import PalworldCatalog
from rhenium_palworld.evaluator import PalworldEvaluator
from rhenium_palworld.native_runtime import (
    EXPECTED_FILES,
    LABEL,
    PLUGIN_VERSION,
    RUNTIME_KEY,
    SOURCE_HASHES,
    NativeServerRunner,
    fingerprint,
    recipe_digest,
    runtime_spec,
)
from rhenium_palworld.plugin import PalworldBenchmarkPlugin
from rhenium_palworld.runtime import PalworldRuntimeConfig
from rhenium_palworld.runtime_builder import PalworldRuntimeBuilder

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec

PACK = Path(__file__).parents[3] / "benchmarks/palworld"
IMAGE = "sha256:" + "a" * 64


@pytest.fixture(autouse=True)
def fake_supported_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhenium_palworld.native_runtime.host_supported", lambda: True)


def context(root: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=PACK.parents[1], pack_root=PACK, state_dir=root / "state", cache_dir=root / "cache"
    )


def artifact(spec: RuntimeSpec | None = None) -> RuntimeArtifact:
    spec = spec or runtime_spec(PACK)
    return RuntimeArtifact(
        runtime_key=RUNTIME_KEY,
        fingerprint=fingerprint(spec),
        kind="docker-image",
        identity=IMAGE,
        metadata={
            "imageId": IMAGE,
            "recipeSha256": recipe_digest(),
            "sourceSha256": SOURCE_HASHES,
            "network": "none",
        },
    )


class FakeDocker:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail = ""
        self.operation = ""
        self.result: dict[str, Any] = {
            "status": "passed",
            "cases": [{"name": "native case", "passed": True}],
            "log": "native log",
        }

    def run(self, args: list[str], *, timeout: float = 300) -> subprocess.CompletedProcess[str]:
        del timeout
        self.calls.append(args)
        output = ""
        if args[0] == "info":
            output = "linux/x86_64"
        elif args[:2] == ["image", "inspect"]:
            if self.fail == "missing":
                return subprocess.CompletedProcess(args, 1, "", "No such image")
            labels = {
                f"{LABEL}.fingerprint": fingerprint(runtime_spec(PACK)),
                f"{LABEL}.recipe": recipe_digest(),
            }
            if self.fail == "foreign":
                labels[f"{LABEL}.fingerprint"] = "foreign"
            output = json.dumps(
                [{"Id": IMAGE, "Os": "linux", "Architecture": "amd64", "Config": {"Labels": labels}}]
            )
        elif args[0] == "build":
            if self.fail == "build":
                return subprocess.CompletedProcess(args, 1, "", "private compilation failure")
            Path(args[args.index("--iidfile") + 1]).write_text(IMAGE)
        elif args[0] == "run":
            if "--label" in args:
                self.operation = args[args.index("--label") + 1].split("=", 1)[1]
            if "--read-only" in args:
                output = json.dumps({"available": self.fail != "verify"})
            else:
                self.operation = args[args.index("--nonce") + 1]
                if self.fail == "timeout":
                    raise subprocess.TimeoutExpired(args, 1)
                marker = "@@RHENIUM_PALWORLD_WORKER@@" + self.operation + ":"
                output = marker + json.dumps(self.result) + "\n"
                if self.fail == "duplicate":
                    output += output
                elif self.fail == "nonce":
                    output = output.replace(self.operation, "foreign")
        elif args[:2] == ["container", "inspect"]:
            output = json.dumps({f"{LABEL}.operation": self.operation})
        return subprocess.CompletedProcess(args, 0, output, "")


def test_builder_registration_and_version_are_consistent(tmp_path: Path) -> None:
    plugin = PalworldBenchmarkPlugin()
    assert plugin.descriptor.version == PLUGIN_VERSION == "0.7.0"
    assert isinstance(
        plugin.create_runtime_builder(context(tmp_path), runtime_spec(PACK)), PalworldRuntimeBuilder
    )
    other = runtime_spec(PACK).model_copy(update={"id": "unrelated"})
    assert plugin.create_runtime_builder(context(tmp_path), other) is None


def test_doctor_and_verify_are_read_only_and_prune_only_owned_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = PalworldRuntimeBuilder(context(tmp_path))
    fake = FakeDocker()
    monkeypatch.setattr(builder.docker, "run", fake.run)
    spec = runtime_spec(PACK)
    assert builder.doctor(spec)["available"] is True
    assert builder.verify(spec, artifact())["available"] is True
    assert not any(args[0] in {"build", "pull"} for args in fake.calls)
    assert not tmp_path.exists() or not list(tmp_path.iterdir())
    probe = next(args for args in fake.calls if args[0] == "run")
    assert "--network=none" in probe and "--read-only" in probe
    assert "--pull=never" in probe
    builder.prune(spec, artifact())
    assert fake.calls[-1] == ["image", "rm", IMAGE]
    fake.fail = "missing"
    builder.prune(spec, artifact())  # Idempotent if already absent.
    fake.fail = "foreign"
    fake.calls.clear()
    with pytest.raises(ValueError, match="ownership"):
        builder.prune(spec, artifact())
    assert not any(args[:2] == ["image", "rm"] for args in fake.calls)


@pytest.mark.parametrize("field", ["runtime_key", "fingerprint", "kind", "identity"])
def test_artifact_identity_errors_fail_closed(
    field: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = PalworldRuntimeBuilder(context(tmp_path))
    fake = FakeDocker()
    monkeypatch.setattr(builder.docker, "run", fake.run)
    invalid = artifact().model_copy(update={field: "foreign"})
    assert builder.verify(runtime_spec(PACK), invalid)["available"] is False
    with pytest.raises(ValueError):
        builder.prune(runtime_spec(PACK), invalid)
    assert not fake.calls


def test_expected_files_and_pinned_source_checksums_are_enforced(tmp_path: Path) -> None:
    builder = PalworldRuntimeBuilder(context(tmp_path))
    spec = runtime_spec(PACK)
    installation = tmp_path / "source/installation"
    installation.mkdir(parents=True)
    with pytest.raises(ValueError, match="required file"):
        builder._source(spec, installation)
    for name in EXPECTED_FILES:
        target = installation / name
        if name == "Pal/Content/Paks":
            target.mkdir(parents=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"wrong game")
    with pytest.raises(ValueError, match="checksum"):
        builder._source(spec, installation)
    modified = copy.deepcopy(spec.source)
    modified["sha256"] = {}
    with pytest.raises(ValueError, match="source policy"):
        builder.source_policy(spec.model_copy(update={"source": modified}))


def test_prepare_consumes_acquired_source_and_returns_core_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = PalworldRuntimeBuilder(context(tmp_path))
    fake = FakeDocker()
    spec = runtime_spec(PACK)
    monkeypatch.setattr(builder.docker, "run", fake.run)
    # Small local game bytes replace only source I/O; no real account/depot/network.
    installation = tmp_path / "acquired/installation"
    installation.mkdir(parents=True)
    (installation / "game").write_bytes(b"game")
    monkeypatch.setattr(builder, "_source", lambda *_: installation)
    phases: list[int] = []
    result = builder.prepare(
        spec, installation, tmp_path / "artifact", progress=lambda n, _: phases.append(n)
    )
    assert result == artifact()
    assert phases == sorted(phases) and phases[-1] == 100
    logs = list((tmp_path / "artifact").glob("build-*.log"))
    assert len(logs) == 1 and logs[0].stat().st_mode & 0o777 == 0o600
    assert not list((tmp_path / "artifact").glob("build-*/"))
    build = next(args for args in fake.calls if args[0] == "build")
    assert "--iidfile" in build and "--platform=linux/amd64" in build


@pytest.mark.parametrize("failure_stage", ["source", "staging"])
def test_prepare_filesystem_errors_never_expose_private_paths(
    failure_stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = PalworldRuntimeBuilder(context(tmp_path))
    installation = tmp_path / "private-acquired-source"
    installation.mkdir()

    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise PermissionError(13, "Permission denied", str(installation))

    if failure_stage == "source":
        monkeypatch.setattr(builder, "_source", denied)
    else:
        monkeypatch.setattr(builder, "_source", lambda *_: installation)
        monkeypatch.setattr("rhenium_palworld.runtime_builder.shutil.copytree", denied)
    with pytest.raises(RuntimeError, match="could not access local inputs") as raised:
        builder.prepare(runtime_spec(PACK), installation, tmp_path / "artifact", progress=lambda *_: None)
    assert str(installation) not in str(raised.value)
    assert raised.value.__suppress_context__ is True


@pytest.mark.parametrize("failure", ["duplicate", "nonce", "timeout", "partial"])
def test_native_worker_failure_and_missing_assertions_cannot_pass(
    failure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = NativeServerRunner(context(tmp_path))
    fake = FakeDocker()
    monkeypatch.setattr(runner.docker, "run", fake.run)
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "file").write_text("candidate")
    suite = tmp_path / "suite.lua"
    suite.write_text('ctx:case("native case", function() end)')
    fake.fail = failure
    if failure == "partial":
        fake.result["cases"] = []
    result = runner.run_assertions(source, suite, artifact())
    assert result["status"] == "error" and result["cases"] == []
    assert any(args[:2] == ["container", "rm"] for args in fake.calls)
    assert not list((context(tmp_path).cache_dir / "native-evaluations").iterdir())


def test_native_worker_uses_only_bound_image_and_readonly_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = NativeServerRunner(context(tmp_path))
    fake = FakeDocker()
    monkeypatch.setattr(runner.docker, "run", fake.run)
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "file").write_text("candidate")
    suite = tmp_path / "suite.lua"
    suite.write_text('ctx:case("native case", function() end)')
    result = runner.run_assertions(source, suite, artifact())
    assert result["status"] == "passed" and len(result["cases"]) == 1
    command = next(args for args in fake.calls if args[0] == "run")
    assert IMAGE in command and "--network=none" in command and "--user=1001:1001" in command
    assert "--pull=never" in command
    assert "--cap-drop=ALL" in command and "--security-opt=no-new-privileges:true" in command
    mounts = [command[i + 1] for i, value in enumerate(command) if value == "--mount"]
    assert len(mounts) == 2 and all(value.endswith(",readonly") for value in mounts)
    assert not any("/var/run/docker.sock" in value for value in command)
    assert not any(args[0] in {"build", "pull"} for args in fake.calls)
    assert (source / "file").read_text() == "candidate"


def test_managed_evaluator_never_falls_back_to_environment_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = runtime_spec(PACK)
    task = PalworldCatalog.load(PACK).tasks[1]
    settings = PalworldRuntimeConfig.load(context(tmp_path))
    evaluator = PalworldEvaluator(settings)
    monkeypatch.setattr(evaluator.server, "run_assertions", lambda *_: pytest.fail("native fallback"))
    candidate = PACK / "private/harbor" / task.id / "solution/reference"
    result = evaluator.evaluate(candidate, task, profile="full", runtimes={})
    assert not result["passed"] and not result["complete"]
    assert "rhenium runtime prepare " + RUNTIME_KEY in result["server"]["message"]
    called: list[RuntimeArtifact] = []

    def run(_self: Any, _submission: Path, _suite: Path, bound: RuntimeArtifact) -> dict[str, Any]:
        called.append(bound)
        return {"status": "passed", "cases": [{"name": "real", "passed": True}], "log": ""}

    monkeypatch.setattr(NativeServerRunner, "run_assertions", run)
    result = evaluator.evaluate(candidate, task, runtimes={RUNTIME_KEY: artifact(spec)})
    assert result["passed"] and result["complete"] and called == [artifact(spec)]


def test_valid_source_hashes_are_checked_before_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rhenium_palworld import runtime_builder as module

    installation = tmp_path / "installation"
    values = {EXPECTED_FILES[0]: b"local fake engine", EXPECTED_FILES[1]: b"local fake SDK"}
    expected = {name: hashlib.sha256(value).hexdigest() for name, value in values.items()}
    monkeypatch.setattr(module, "SOURCE_HASHES", expected)
    for name, value in values.items():
        target = installation / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
    (installation / EXPECTED_FILES[2]).mkdir(parents=True)
    spec = runtime_spec(PACK)
    spec = spec.model_copy(update={"source": {**spec.source, "sha256": expected}})
    builder = PalworldRuntimeBuilder(context(tmp_path))
    assert builder._source(spec, installation) == installation
    (installation / EXPECTED_FILES[1]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        builder._source(spec, installation)


def test_unsupported_host_never_starts_an_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhenium_palworld.native_runtime.host_supported", lambda: False)
    runner = NativeServerRunner(context(tmp_path))
    monkeypatch.setattr(runner.docker, "run", lambda *_args, **_kwargs: pytest.fail("unexpected process"))
    result = runner.run_assertions(tmp_path, tmp_path / "suite.lua", artifact())
    assert result["status"] == "error" and result["cases"] == []


def test_registered_lifecycle_requires_login_reuses_and_invalidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rhenium_steam.provider import SteamAuthProvider

    from rhenium.config import Settings
    from rhenium.core.auth import AuthSession
    from rhenium.hub import BenchmarkHub

    settings = Settings(
        root=PACK.parents[1],
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
        database_url=f"sqlite:///{tmp_path}/state/state.sqlite",
        benchmark_paths=(PACK,),
        web_dist=None,
    )
    plugin = PalworldBenchmarkPlugin()
    provider = SteamAuthProvider()
    monkeypatch.setattr(
        provider, "login",
        lambda account_alias, **_: AuthSession(
            provider_id="steam", account_alias=account_alias, principal="local-test", secret={}
        ),
    )
    hub = BenchmarkHub(
        settings,
        plugins={"palworld": plugin},
        auth_providers={"steam": provider},
        manifest_paths=(PACK / "benchmark.json",),
    )
    monkeypatch.setattr(hub.runtime_manager, "host_platform", lambda: "linux-x64")
    with pytest.raises(RuntimeError, match="rhenium runtime prepare"):
        hub.runtime_manager.artifacts_for_task("palworld/core/base-containment-mincut", required=True)
    hub.runtime_manager.providers.pop("steam")
    with pytest.raises(RuntimeError, match="auth provider is not installed"):
        hub.runtime_manager.prepare(RUNTIME_KEY)
    hub.runtime_manager.providers["steam"] = provider
    monkeypatch.setattr(hub.runtime_manager, "host_platform", lambda: "windows-x64")
    with pytest.raises(RuntimeError, match="does not support host"):
        hub.runtime_manager.prepare(RUNTIME_KEY)
    monkeypatch.setattr(hub.runtime_manager, "host_platform", lambda: "linux-x64")
    with pytest.raises(RuntimeError, match="auth login steam"):
        hub.runtime_manager.prepare(RUNTIME_KEY)
    hub.auth.login("steam")
    binding = hub.runtime_manager.bindings[RUNTIME_KEY]
    calls: list[str] = []

    def acquire(_source: Any, session: Any, _destination: Path, *, progress: Any) -> Any:
        calls.append("acquire")
        progress(100, "acquired")
        return session

    def prepare(spec: RuntimeSpec, _source: Path, _destination: Path, *, progress: Any) -> RuntimeArtifact:
        calls.append("prepare")
        progress(100, "built")
        return artifact(spec)

    monkeypatch.setattr(provider, "acquire", acquire)
    monkeypatch.setattr(binding.builder, "prepare", prepare)
    monkeypatch.setattr(binding.builder, "verify", lambda *_: {"available": True})
    monkeypatch.setattr(binding.builder, "prune", lambda *_: calls.append("prune"))
    assert hub.runtime_manager.prepare(RUNTIME_KEY)["ready"] is True
    assert calls == ["acquire", "prepare"]
    assert hub.runtime_manager.prepare(RUNTIME_KEY)["ready"] is True
    assert calls == ["acquire", "prepare"]
    with monkeypatch.context() as changed:
        changed.setattr(hub.runtime_manager, "_fingerprint", lambda _: "changed-fingerprint")
        with pytest.raises(RuntimeError, match="not prepared"):
            hub.runtime_manager.artifacts_for_task("palworld/core/base-containment-mincut", required=True)
    assert hub.runtime_manager.prune(RUNTIME_KEY)["status"] == "pruned"
    assert calls[-1] == "prune"


def test_sealing_makes_private_operator_code_readable_without_world_writes(tmp_path: Path) -> None:
    from rhenium_palworld.native.seal import make_runtime_code_readable

    package = tmp_path / "package"
    package.mkdir(mode=0o700)
    nested = package / "nested"
    nested.mkdir(mode=0o700)
    module = nested / "worker.py"
    module.write_text("VALUE = 1\n")
    module.chmod(0o600)
    make_runtime_code_readable(package)
    assert package.stat().st_mode & 0o005 == 0o005
    assert nested.stat().st_mode & 0o005 == 0o005
    assert module.stat().st_mode & 0o004
    assert not module.stat().st_mode & 0o022
    assert module.read_text() == "VALUE = 1\n"


@pytest.mark.parametrize("change", [
    {"provider": "steamcmd"},
    {"restricted": False},
    {"source": {"kind": "steamcmd-app"}},
])
def test_runtime_rejects_sources_outside_the_existing_steam_depot_contract(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="source policy"):
        PalworldRuntimeBuilder.source_policy(runtime_spec(PACK).model_copy(update=change))
