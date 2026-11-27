import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from rhenium_balatro import linux_window
from rhenium_balatro.linux_process import NativeProcess


def test_profile_applies_only_to_explicit_derived_runtime() -> None:
    assert linux_window.enabled(SimpleNamespace(runtime_key=linux_window.KEY))
    assert not linux_window.enabled(
        SimpleNamespace(runtime_key="balatro/balatro-linux-17459173-controlled-v1")
    )
    assert not linux_window.enabled(SimpleNamespace())


def test_resource_closure_and_bytes_are_inputs(tmp_path: Path) -> None:
    for name in ("window.lua", "window.json"):
        (tmp_path / name).write_bytes((linux_window.ROOT / name).read_bytes())
    before = linux_window.resources(tmp_path)
    (tmp_path / "window.lua").write_bytes(b"changed authored source")
    assert linux_window.resources(tmp_path) != before
    (tmp_path / "unreviewed.lua").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="closure"):
        linux_window.resources(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("width", 1280),
        ("height", 720),
        ("visible", False),
        ("fullscreen", True),
        ("vsync", 1),
        ("renderer", {}),
        ("schema", "other"),
    ],
)
def test_real_window_mismatch_is_rejected(tmp_path: Path, field: str, value: object) -> None:
    observation = {
        "schema": "visible-window-profile-v2",
        "width": 800,
        "height": 600,
        "fullscreen": False,
        "visible": True,
        "vsync": 0,
        "renderer": {k: "unit" for k in ("name", "version", "vendor", "device")},
    }
    path = tmp_path / "observation.json"
    path.write_text(json.dumps(observation))
    assert linux_window.read_observation(path) == observation
    observation[field] = value
    path.write_text(json.dumps(observation))
    with pytest.raises(ValueError, match="Actual owned window"):
        linux_window.read_observation(path)


def test_window_resource_drift_stops_before_launch(tmp_path: Path) -> None:
    builder = Mock()
    builder.verify.return_value = {"available": True}
    process = NativeProcess(
        builder=builder,
        spec=None,
        artifact=SimpleNamespace(location=str(tmp_path), runtime_key=linux_window.KEY),
        directory=tmp_path / "fresh",
    )
    with (
        patch.object(linux_window, "resources", return_value={"window.lua": "changed"}),
        patch("subprocess.Popen") as launch,
    ):
        with pytest.raises(RuntimeError, match="window configuration changed"):
            process.start()
        launch.assert_not_called()
    assert not (tmp_path / "fresh").exists()
