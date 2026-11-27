from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from rhenium_balatro.linux_process import (
    NativeProcess,
    arm_parent_death,
    child_environment,
    game_process_guard,
)


def test_child_environment_does_not_inherit_host_credentials_or_lua_paths(tmp_path: Path) -> None:
    with patch.dict(
        "os.environ",
        {
            "STEAM_TOKEN": "fake-secret",
            "LD_PRELOAD": "unreviewed.so",
            "LUA_PATH": "unreviewed",
            "BALATROBOT_FAST": "1",
        },
    ):
        env = child_environment(tmp_path / "artifact", tmp_path / "run", "unit-nonce", 12345, False)
    assert "STEAM_TOKEN" not in env
    assert env["BALATROBOT_FAST"] == env["BALATROBOT_HEADLESS"] == "0"
    assert env["BALATROBOT_GAMESPEED"] == "1"
    assert env["LD_PRELOAD"] == str(tmp_path / "artifact/liblovely.so")
    assert "unreviewed" not in " ".join(env.values())
    assert env["APPDATA"] == env["XDG_DATA_HOME"] == str(tmp_path / "run/appdata")
    assert env["POC_SAVE_DIR"] == str(tmp_path / "run/appdata/Balatro")


def test_wsl_requires_an_explicit_windows_process_guard() -> None:
    with (
        patch("pathlib.Path.iterdir", return_value=iter(())),
        patch("platform.release", return_value="5.15-microsoft-standard-WSL2"),
        pytest.raises(RuntimeError, match="explicit read-only Windows"),
    ):
        game_process_guard(None)


def test_null_audio_is_process_local_and_does_not_select_the_host_server(tmp_path: Path) -> None:
    env = child_environment(tmp_path / "artifact", tmp_path / "run", "nonce", 12345, False, "null")
    assert env["ALSOFT_DRIVERS"] == "null"
    assert "PULSE_SERVER" not in env
    assert env["ALSOFT_LOGFILE"] == str(tmp_path / "run/openal-diagnostic.log")
    assert env["BALATROBOT_FAST"] == env["BALATROBOT_HEADLESS"] == "0"
    with pytest.raises(ValueError, match="Unsupported"):
        child_environment(tmp_path, tmp_path / "bad", "nonce", 12345, False, "unreviewed")


def test_process_rejects_existing_directory_and_never_writes_unowned_cleanup(tmp_path: Path) -> None:
    builder = Mock()
    builder.verify.return_value = {"available": True}
    artifact = SimpleNamespace(location=str(tmp_path / "artifact"))
    with pytest.raises(ValueError, match="fresh absolute"):
        NativeProcess(builder=builder, spec=None, artifact=artifact, directory=tmp_path)
    target = tmp_path / "reserved"
    process = NativeProcess(builder=builder, spec=None, artifact=artifact, directory=target)
    target.mkdir()  # Another owner won the race; this process never started.
    marker = target / "preserve.txt"
    marker.write_text("preserve")
    first = process.close()
    assert process.close() is first
    assert not first["normal_exit"] and not (target / "cleanup.json").exists()
    assert marker.read_text() == "preserve"


def test_dependency_drift_stops_before_staging_or_launch(tmp_path: Path) -> None:
    builder = Mock()
    builder.verify.return_value = {"available": False}
    target = tmp_path / "new-run"
    process = NativeProcess(
        builder=builder,
        spec=None,
        artifact=SimpleNamespace(location=str(tmp_path / "artifact")),
        directory=target,
    )
    with patch("subprocess.Popen") as launch, pytest.raises(RuntimeError, match="bytes or recipe"):
        process.start()
    launch.assert_not_called()
    assert not target.exists()


def test_changed_candidate_is_rejected_before_any_engine_execution(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    for relative in ("authored-mods/poc_guard", "authored-mods/poc_control", "mods/smods", "mods/bot"):
        directory = artifact / relative
        directory.mkdir(parents=True)
        (directory / "unit.lua").write_text("-- inert unit fixture")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "unit.lua").write_text("-- changed after review")
    builder = Mock()
    builder.verify.return_value = {"available": True}
    process = NativeProcess(
        builder=builder,
        spec=None,
        artifact=SimpleNamespace(location=str(artifact)),
        directory=tmp_path / "run",
        extra_mods={"candidate": candidate},
        candidate_sha256="0" * 64,
    )
    with (
        patch("rhenium_balatro.linux_process.game_process_guard"),
        patch("subprocess.Popen") as launch,
        pytest.raises(ValueError, match="reviewed submission"),
    ):
        process.start()
    launch.assert_not_called()
    assert not process.close()["normal_exit"]


@pytest.mark.parametrize("parent_changed", (False, True))
def test_parent_death_signal_and_preexec_parent_race(parent_changed: bool) -> None:
    import signal

    libc = Mock()
    libc.prctl.return_value = 0
    with (
        patch("ctypes.CDLL", return_value=libc),
        patch("os.getppid", return_value=88 if parent_changed else 77),
        patch("os.getpid", return_value=99),
        patch("os.kill") as kill,
    ):
        arm_parent_death(77)
    libc.prctl.assert_called_once_with(1, signal.SIGKILL, 0, 0, 0)
    if parent_changed:
        kill.assert_called_once_with(99, signal.SIGKILL)
    else:
        kill.assert_not_called()
