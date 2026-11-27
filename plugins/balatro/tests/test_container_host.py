from __future__ import annotations

import json
import subprocess
from inspect import signature
from pathlib import Path
from unittest.mock import patch

import pytest
from rhenium_balatro import container_host as host
from rhenium_balatro.container_builder import BalatroContainerBuilder
from rhenium_balatro.linux_bridge import invoke
from rhenium_balatro.linux_evaluator import BalatroLinuxEvaluator
from rhenium_balatro.linux_runtime import SOURCE

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeSpec

IMAGE = "sha256:" + "1" * 64


def context(tmp_path: Path) -> BenchmarkContext:
    pack = tmp_path / "pack"
    pack.mkdir()
    return BenchmarkContext(project_root=tmp_path, pack_root=pack,
                            state_dir=tmp_path / "state", cache_dir=tmp_path / "cache")


def spec() -> RuntimeSpec:
    return RuntimeSpec(id=host.RUNTIME_ID, name="unit", version="unit", provider="steam",
                       restricted=True, host_platforms=("linux-x64",), source=SOURCE)


def test_doctor_only_reads_daemon_and_does_not_prepare(tmp_path: Path) -> None:
    builder = BalatroContainerBuilder(context(tmp_path))
    with (
        patch("platform.system", return_value="Linux"),
        patch("platform.machine", return_value="x86_64"),
        patch("platform.release", return_value="unit-native-linux"),
        patch("shutil.which", return_value="/fake/docker"),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "linux\n", "")) as run,
    ):
        assert builder.doctor(spec())["available"]
    assert run.call_args.args[0] == ["docker", "info", "--format", "{{.OSType}}"]
    assert not builder.context.state_dir.exists() and not builder.context.cache_dir.exists()
    assert not builder.valid_spec(spec().model_copy(update={"source": {**SOURCE, "appId": 1}}))


def test_inspection_requires_exact_image_id() -> None:
    with pytest.raises(ValueError, match="immutable image"):
        host.inspect_image("mutable:latest")
    with (
        patch("subprocess.run", return_value=subprocess.CompletedProcess(
            [], 0, json.dumps([{"Id": "sha256:" + "2" * 64}]), ""
        )),
        pytest.raises(ValueError, match="another image"),
    ):
        host.inspect_image(IMAGE)


def test_inspection_distinguishes_missing_image_from_daemon_failure() -> None:
    with patch("subprocess.run", return_value=subprocess.CompletedProcess(
        [], 1, "", "Error: No such image: unit"
    )):
        assert host.inspect_image(IMAGE) is None
    with (
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "Cannot connect")),
        pytest.raises(RuntimeError, match="daemon"),
    ):
        host.inspect_image(IMAGE)


@pytest.mark.parametrize("data", [{}, {"Config": {}}, {"Config": {"Labels": None}}])
def test_unowned_image_configuration_is_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="unavailable"):
        host.image_labels(data)


@pytest.mark.parametrize("prepare", [False, True])
def test_worker_network_mounts_and_identity(tmp_path: Path, prepare: bool) -> None:
    source = tmp_path / "source"
    source.mkdir()
    work = tmp_path / "work"

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert command[:2] == ["docker", "run"]
        entry = (host.ASSETS / "Dockerfile").read_text().split("ENTRYPOINT ", 1)[1]
        container_deadline = float(json.loads(entry)[3])
        native_deadline = float(signature(invoke).parameters["timeout"].default)
        assert native_deadline + 20 < container_deadline < float(str(kwargs["timeout"])) - 10
        assert command[command.index("--network") + 1] == ("bridge" if prepare else "none")
        assert "--read-only" in command and "--cap-drop=ALL" in command
        assert "--security-opt=no-new-privileges" in command
        assert not any("docker.sock" in token or token == "--privileged" for token in command)
        payload = kwargs["input"]
        assert isinstance(payload, bytes)
        message = json.loads(payload)
        assert message["image"] == IMAGE
        Path(message["response"]).write_text(json.dumps({
            "nonce": message["nonce"], "image": IMAGE, "result": {"verified": True},
            "pid_namespace": "pid:[123]",
        }))
        return subprocess.CompletedProcess(command, 0)

    with patch("subprocess.run", side_effect=run):
        result = host.run_worker(IMAGE, {"operation": "unit", "image": "forged"}, work,
                                 readonly=(source,), writable=(work,), prepare=prepare)
    assert result == {"verified": True}


def test_worker_rejects_response_for_another_nonce(tmp_path: Path) -> None:
    work = tmp_path / "work"

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if command[:2] == ["docker", "run"]:
            payload = kwargs["input"]
            assert isinstance(payload, bytes)
            message = json.loads(payload)
            Path(message["response"]).write_text(json.dumps({"nonce": "wrong", "image": IMAGE}))
        return subprocess.CompletedProcess(command, 0)

    with (
        patch("subprocess.run", side_effect=run) as call,
        pytest.raises(ValueError, match="identity mismatch"),
    ):
        host.run_worker(IMAGE, {}, work, readonly=(), writable=(work,))
    cleanup = call.call_args.args[0]
    assert cleanup[:3] == ["docker", "rm", "--force"]
    assert cleanup[3].startswith("rhenium-balatro-")


def test_only_the_owned_inner_native_runtime_is_accepted(tmp_path: Path) -> None:
    value = context(tmp_path)
    with pytest.raises(ValueError, match="inner native"):
        BalatroLinuxEvaluator.with_prepared_context(value, "other/runtime")
