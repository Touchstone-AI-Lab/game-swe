"""Probe boundaries, with fake Docker only: no account, display or network."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


@pytest.fixture
def probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    path = Path(__file__).parents[1] / 'probes/interactive_client_v1/control.py'
    spec = importlib.util.spec_from_file_location('steam_interactive_probe_v1', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    (tmp_path / 'evidence').mkdir()
    (tmp_path / 'evidence/preparation-result.json').write_text(json.dumps({
        'status': 'image_built', 'image_id': 'sha256:' + '1' * 64,
    }))
    return module


def owned_container() -> dict[str, Any]:
    return {
        'Config': {'Labels': {'org.rhenium.probe': 'steam-interactive-v1-20261031'},
                   'User': '1000:1000'},
        'HostConfig': {'Privileged': False, 'CapDrop': ['ALL'], 'CapAdd': None,
                       'SecurityOpt': ['no-new-privileges'], 'Devices': [],
                       'NetworkMode': 'bridge'},
        'Image': 'sha256:' + '1' * 64, 'Mounts': [],
        'State': {'Running': False, 'Status': 'exited', 'ExitCode': 1,
                  'OOMKilled': False, 'StartedAt': 'start', 'FinishedAt': 'end'},
    }


def test_launch_has_only_approved_mounts_and_no_privilege_relaxation(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake(*args: str, **kwargs: Any) -> str:
        calls.append(args)
        return json.dumps([owned_container()]) if args[0] == 'inspect' else 'container-id'

    monkeypatch.setattr(probe, 'docker', fake)
    probe.start()
    run = next(args for args in calls if args[0] == 'run')
    assert '--privileged' not in run and 'seccomp=unconfined' not in run
    assert '--device' not in run and '--cap-add' not in run
    assert run[run.index('--cap-drop') + 1] == 'ALL'
    assert run[run.index('--security-opt') + 1] == 'no-new-privileges'
    mounts = [run[i + 1] for i, arg in enumerate(run) if arg == '--mount']
    assert mounts == [
        f'type=bind,src={probe.ROOT / "home"},dst=/home/steamprobe',
        'type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix,readonly',
    ]
    assert run[-1] == 'sha256:' + '1' * 64


def test_ambiguous_start_cannot_be_resent(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unavailable(*args: str, **kwargs: Any) -> str:
        nonlocal calls
        calls += 1
        raise TimeoutError('unknown completion')

    monkeypatch.setattr(probe, 'docker', unavailable)
    with pytest.raises(TimeoutError):
        probe.start()
    with pytest.raises(FileExistsError):
        probe.start()
    assert calls == 1


def test_refuses_unowned_container(probe: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    obj = owned_container()
    obj['Config']['Labels'] = {}
    monkeypatch.setattr(probe, 'docker', lambda *args: json.dumps([obj]))
    with pytest.raises(RuntimeError, match='unowned'):
        probe.stop()


def test_failed_start_is_not_successful_shutdown(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(probe, 'docker', lambda *args: json.dumps([owned_container()]))
    result = probe.stop()
    assert not result['normal_shutdown_confirmed']
    assert result['shutdown_ipc_result'] is None
    assert result['authenticated'] == 'not_validated'


def test_status_never_reads_client_logs_or_command_lines(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    obj = owned_container()
    obj['State']['Running'] = True
    calls: list[tuple[str, ...]] = []

    def fake(*args: str, **kwargs: Any) -> str:
        calls.append(args)
        return json.dumps([obj]) if args[0] == 'inspect' else 'PID COMMAND\n101 steam\n102 steamwebhelper'

    monkeypatch.setattr(probe, 'docker', fake)
    result = probe.status()
    assert calls == [('inspect', probe.NAME), ('top', probe.NAME, '-eo', 'pid,comm')]
    assert result['process_names'] == ['steam', 'steamwebhelper']
    assert result['authenticated'] == 'not_validated'


def test_launcher_has_no_credential_capture_path() -> None:
    recipe = Path(__file__).parents[1] / 'probes/interactive_client_v1'
    shell = (recipe / 'launch.sh').read_text()
    dockerfile = (recipe / 'Dockerfile').read_text()
    assert '>/dev/null 2>&1' in shell
    assert '[[ $# == 0 ' in shell
    for forbidden in ('xdotool', 'imagemagick', 'zbar-tools', 'xvfb', 'steam-client-session.sh'):
        assert forbidden not in shell.lower() and forbidden not in dockerfile.lower()


def test_cli_session_retains_foreground_supervision_after_launch(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    actions: list[str] = []

    def launch() -> dict[str, str]:
        actions.append('launch')
        return {'container_id': 'fake'}

    def supervise() -> dict[str, str]:
        actions.append('bounded_foreground_wait')
        return {'authenticated': 'not_validated'}

    monkeypatch.setattr(probe, 'start', launch)
    monkeypatch.setattr(probe, 'supervise', supervise)
    assert probe.start_session() == {'authenticated': 'not_validated'}
    assert actions == ['launch', 'bounded_foreground_wait']


def test_supervision_preserves_failed_exit_and_uses_deadline(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[str, ...], int | None]] = []

    def fake(*args: str, **kwargs: Any) -> str:
        calls.append((args, kwargs.get('timeout')))
        return '255' if args[0] == 'wait' else json.dumps([owned_container()])

    monkeypatch.setattr(probe, 'docker', fake)
    result = probe.supervise()
    assert (('wait', probe.NAME), 900) in calls
    assert result['wait_exit_code'] == 255
    assert result['authenticated'] == 'not_validated'
    assert not result['deadline_exceeded']


@pytest.mark.skipif(shutil.which('awk') is None, reason='Linux shell probe requires awk')
def test_diagnostic_emits_only_fixed_classes_and_deduplicates() -> None:
    path = Path(__file__).parents[1] / 'probes/interactive_client_v1/diagnostic-launch-v2.sh'
    match = re.search(r"  awk '([\s\S]+)'\n", path.read_text())
    assert match is not None
    secret = 'synthetic-password-do-not-output'
    raw = (f'ERROR token={secret} url=https://example.invalid/private\n'
           f'Operation not permitted account={secret}\n') * 100
    output = subprocess.run(['awk', match.group(1)], input=raw, text=True,
                            capture_output=True, check=True, timeout=5).stdout
    assert output.splitlines() == ['class=error_message', 'class=operation_not_permitted']
    assert secret not in output and 'https:' not in output


def test_supervision_deadline_requests_owned_shutdown(
    probe: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped: list[bool] = []

    def fake(*args: str, **kwargs: Any) -> str:
        if args[0] == 'wait':
            raise subprocess.TimeoutExpired('docker wait', 900)
        return json.dumps([owned_container()])

    def stop() -> dict[str, Any]:
        stopped.append(True)
        return {'authenticated': 'not_validated', 'normal_shutdown_confirmed': False}

    monkeypatch.setattr(probe, 'docker', fake)
    monkeypatch.setattr(probe, 'stop', stop)
    result = probe.supervise()
    assert stopped == [True] and result['deadline_exceeded']
    assert not result['normal_shutdown_confirmed']


@pytest.mark.parametrize('seconds', [0, -1, 2701])
def test_rejects_unbounded_supervision(probe: ModuleType, seconds: int) -> None:
    with pytest.raises(ValueError, match='bounded'):
        probe.supervise(seconds)


@pytest.fixture
def namespace_probe(probe: ModuleType, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setitem(sys.modules, 'control', probe)
    path = Path(__file__).parents[1] / 'probes/interactive_client_v1/namespace_probe_v4.py'
    spec = importlib.util.spec_from_file_location('steam_namespace_probe_v4', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_namespace_proposal_requires_exact_permission_receipt(
    namespace_probe: ModuleType, tmp_path: Path,
) -> None:
    path = tmp_path / 'approval.json'
    value = {'approved': False, 'seccomp': 'unconfined', 'maximum_attempts': 1, 'maximum_seconds': 900}
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='Explicit'):
        namespace_probe.require_approval(path)
    value['approved'] = True
    path.write_text(json.dumps(value))
    assert namespace_probe.require_approval(path) == value


def test_namespace_proposal_keeps_other_permission_boundaries(namespace_probe: ModuleType) -> None:
    args = namespace_probe.launch_args(Path('/owned'), Path('/recipe/start.sh'), 'owned-probe', 'sha256:test')
    opts = [args[i + 1] for i, arg in enumerate(args) if arg == '--security-opt']
    assert opts == ['no-new-privileges', 'seccomp=unconfined']
    assert args[args.index('--user') + 1] == '1000:1000'
    assert args[args.index('--cap-drop') + 1] == 'ALL'
    assert not {'--privileged', '--cap-add', '--device'} & set(args)
    mounts = [args[i + 1] for i, arg in enumerate(args) if arg == '--mount']
    assert len(mounts) == 3
    assert mounts[0] == 'type=bind,src=/owned/home,dst=/home/steamprobe'
    assert all(m.endswith(',readonly') for m in mounts[1:])
    assert all('docker.sock' not in m for m in mounts)


@pytest.fixture
def shm_probe(namespace_probe: ModuleType, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setitem(sys.modules, 'namespace_probe_v4', namespace_probe)
    path = Path(__file__).parents[1] / 'probes/interactive_client_v1/shm_probe_v5.py'
    spec = importlib.util.spec_from_file_location('steam_shm_probe_v5', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_memory_comparison_changes_only_capacity(
    shm_probe: ModuleType, namespace_probe: ModuleType,
) -> None:
    inputs = (Path('/owned'), Path('/recipe/start.sh'), 'owned-probe', 'sha256:test')
    previous = namespace_probe.launch_args(*inputs)
    current = list(shm_probe.launch_args(*inputs))
    i = current.index('--shm-size')
    assert current[i + 1] == '1g'
    del current[i:i + 2]
    assert tuple(current) == previous


def test_prior_namespace_approval_does_not_authorize_another_launch(
    shm_probe: ModuleType, tmp_path: Path,
) -> None:
    path = tmp_path / 'approval.json'
    value = {'approved': True, 'seccomp': 'unconfined', 'maximum_attempts': 1, 'maximum_seconds': 900}
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match='Explicit'):
        shm_probe.require_approval(path)
    value['shm_size_bytes'] = 1073741824
    path.write_text(json.dumps(value))
    assert shm_probe.require_approval(path) == value


@pytest.mark.parametrize('field,value', [('approved', False), ('maximum_attempts', 2),
                                       ('maximum_seconds', 1800), ('shm_size_bytes', 2147483648)])
def test_shared_memory_comparison_rejects_expanded_approval(
    shm_probe: ModuleType, tmp_path: Path, field: str, value: object,
) -> None:
    decision: dict[str, object] = {'approved': True, 'seccomp': 'unconfined',
                                 'maximum_attempts': 1, 'maximum_seconds': 900,
                                 'shm_size_bytes': 1073741824}
    decision[field] = value
    path = tmp_path / 'approval.json'
    path.write_text(json.dumps(decision))
    with pytest.raises(RuntimeError, match='Explicit'):
        shm_probe.require_approval(path)
