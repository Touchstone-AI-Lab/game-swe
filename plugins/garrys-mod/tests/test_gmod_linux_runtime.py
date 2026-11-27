from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from rhenium_garrys_mod.addons import linux_process, runtime
from rhenium_garrys_mod.addons.catalog import GmodCatalog
from rhenium_garrys_mod.addons.contracts import GmodPackRuntimeContract
from rhenium_garrys_mod.addons.installation import (
    GmodInstallationError,
    create_directory_junction,
    linux_server_binary,
    remove_directory_junction,
)
from rhenium_garrys_mod.addons.process import GmodProcessError
from rhenium_garrys_mod.addons.runtime import GmodRuntimeConfig
from rhenium_garrys_mod.addons.server_runner import GmodDedicatedServerRunner, _environment

from rhenium.core.plugin import BenchmarkContext


def _catalog(linux_build: str | None = "23150012") -> GmodCatalog:
    contract = GmodPackRuntimeContract(
        app_id=4020,
        branch="stable",
        build_id="23150012",
        platform="windows-x86_64",
        linux_build_id=linux_build,
    )
    return GmodCatalog.model_construct(runtime=contract)


def _context(root: Path) -> BenchmarkContext:
    return BenchmarkContext(
        project_root=root, pack_root=root, state_dir=root / "state", cache_dir=root / "cache"
    )


def _install(root: Path, build: str = "23150012") -> None:
    (root / "steamapps").mkdir(parents=True)
    (root / "steamapps/appmanifest_4020.acf").write_text(f'"buildid" "{build}"\n')
    binary = root / "srcds_linux"
    binary.write_bytes(b"\x7fELF\x01\x01" + bytes(12) + b"\x03\x00")
    binary.chmod(0o755)


def test_linux_runtime_requires_explicit_root_and_catalog_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "x86_64")
    monkeypatch.delenv("RHENIUM_PLUGIN_GMOD_SERVER_ROOT", raising=False)
    assert GmodRuntimeConfig.load(_context(tmp_path), _catalog()).server_root is None
    monkeypatch.setenv("RHENIUM_PLUGIN_GMOD_SERVER_ROOT", str(tmp_path / "server"))
    config = GmodRuntimeConfig.load(_context(tmp_path), _catalog())
    assert config.platform == "linux-x86_64"
    assert config.pinned_build == "23150012"
    assert config.server_root == tmp_path / "server"
    assert GmodRuntimeConfig.load(_context(tmp_path), _catalog(None)).server_root is None
    monkeypatch.setattr(runtime.platform, "machine", lambda: "aarch64")
    assert GmodRuntimeConfig.load(_context(tmp_path), _catalog()).server_root is None


def test_windows_runtime_pin_is_not_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.setenv("RHENIUM_PLUGIN_GMOD_SERVER_ROOT", str(tmp_path / "server"))
    config = GmodRuntimeConfig.load(_context(tmp_path), _catalog("12345"))
    assert config.platform == "windows-x86_64"
    assert config.pinned_build == "23150012"


def test_linux_status_rejects_wrong_build_binary_and_missing_install(tmp_path: Path) -> None:
    root = tmp_path / "server"
    config = GmodRuntimeConfig(tmp_path, root, tmp_path / "runs", "23150012", "stable", 4020, "linux-x86_64")
    assert not GmodDedicatedServerRunner(config).status()["available"]
    _install(root)
    assert GmodDedicatedServerRunner(config).status()["available"]
    assert not GmodDedicatedServerRunner(replace(config, pinned_build="1")).status()["available"]
    (root / "srcds_linux").write_bytes(b"MZ-not-linux")
    assert not GmodDedicatedServerRunner(config).status()["available"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX link and executable permission semantics")
def test_linux_binary_rejects_symlink_and_non_executable(tmp_path: Path) -> None:
    _install(tmp_path)
    binary = tmp_path / "srcds_linux"
    binary.chmod(0o644)
    with pytest.raises(GmodInstallationError):
        linux_server_binary(tmp_path)
    binary.rename(tmp_path / "elsewhere")
    binary.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(GmodInstallationError):
        linux_server_binary(tmp_path)


@pytest.mark.skipif(os.name != "posix", reason="native Linux data-link behavior")
def test_data_link_cleanup_preserves_target_and_rejects_replacement(tmp_path: Path) -> None:
    target, link = tmp_path / "data", tmp_path / "link"
    create_directory_junction(link, target)
    (target / "state.txt").write_text("persistent")
    assert (link / "state.txt").read_text() == "persistent"
    with pytest.raises(GmodInstallationError):
        remove_directory_junction(link, tmp_path)
    remove_directory_junction(link, target)
    assert not link.exists()
    assert (target / "state.txt").read_text() == "persistent"


def test_linux_environment_excludes_credentials_and_injected_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STEAM_REFRESH_TOKEN", "fake-do-not-inherit")
    monkeypatch.setenv("LD_PRELOAD", "untrusted.so")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/untrusted")
    monkeypatch.setenv("HOME", "/personal")
    environment = _environment(tmp_path / "temp", tmp_path / "server")
    assert "STEAM_REFRESH_TOKEN" not in environment and "LD_PRELOAD" not in environment
    assert environment["HOME"] == str(tmp_path / "temp")
    assert environment["LD_LIBRARY_PATH"] == f"{tmp_path / 'server/bin'}:{tmp_path / 'server'}"


@pytest.mark.skipif(sys.platform != "linux", reason="requires real Linux process groups and procfs")
def test_linux_process_success_and_timeout_cleanup(tmp_path: Path) -> None:
    completed = linux_process.run_process_group(
        [sys.executable, "-c", "print('engine protocol probe')"],
        cwd=tmp_path,
        environment={},
        timeout=5,
    )
    assert completed.exit_code == 0 and "engine protocol probe" in completed.output
    assert not completed.forced_termination and completed.job_active_processes == 0
    stalled = linux_process.run_process_group(
        [sys.executable, "-c", "import os,time; os.fork(); time.sleep(60)"],
        cwd=tmp_path,
        environment={},
        timeout=0.3,
    )
    assert stalled.timed_out and stalled.forced_termination
    assert not linux_process.process_group_members(stalled.process_id)
    assert stalled.job_active_processes == 0


@pytest.mark.skipif(sys.platform != "linux", reason="requires real Linux process groups and procfs")
def test_linux_process_output_overflow_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linux_process, "MAX_OUTPUT_BYTES", 1024)
    with pytest.raises(GmodProcessError, match="bounded limit"):
        linux_process.run_process_group(
            [sys.executable, "-c", "import time; print('x'*4096, flush=True); time.sleep(60)"],
            cwd=tmp_path,
            environment={},
            timeout=5,
        )


@pytest.mark.skipif(sys.platform != "linux", reason="requires real Linux process groups and procfs")
def test_linux_process_rejects_lingering_child(tmp_path: Path) -> None:
    result = linux_process.run_process_group(
        [sys.executable, "-c", "import os,time; pid=os.fork(); time.sleep(60) if pid==0 else None"],
        cwd=tmp_path,
        environment={},
        timeout=0.4,
    )
    assert result.forced_termination and result.job_active_processes == 0
    assert not linux_process.process_group_members(result.process_id)


@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux console collection")
def test_linux_process_collects_console_without_stdout_forwarding(tmp_path: Path) -> None:
    log = tmp_path / "console.log"
    result = linux_process.run_process_group(
        [sys.executable, "-c", "from pathlib import Path; Path('console.log').write_text('phase result')"],
        cwd=tmp_path, environment={}, timeout=5, console_log=log,
    )
    assert "phase result" in result.output and result.exit_code == 0
    with pytest.raises(GmodProcessError, match="fresh"):
        linux_process.run_process_group(
            [sys.executable, "-c", "pass"], cwd=tmp_path, environment={}, timeout=5, console_log=log,
        )


@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux console collection")
def test_linux_console_rejects_missing_linked_or_oversized_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = tmp_path / "console.log"
    with pytest.raises(GmodProcessError, match="missing"):
        linux_process.read_console(log)
    external = tmp_path / "external"
    external.write_text("do not accept")
    log.symlink_to(external)
    with pytest.raises(GmodProcessError, match="regular file"):
        linux_process.read_console(log)
    log.unlink()
    os.link(external, log)
    with pytest.raises(GmodProcessError, match="regular file"):
        linux_process.read_console(log)
    log.unlink()
    monkeypatch.setattr(linux_process, "MAX_OUTPUT_BYTES", 4)
    log.write_text("too large")
    with pytest.raises(GmodProcessError, match="bounded limit"):
        linux_process.read_console(log)
