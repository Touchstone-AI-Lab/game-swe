"""Versioned, owned-process video settings; no gameplay or host configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .files import reject_links
from .linux_runtime import sha

ROOT = Path(__file__).with_name("linux_window_v2")
KEY = "balatro/balatro-linux-17459173-controlled-v2"
PROFILE = "visible-window800x600-null-audio-gs1-fast0-headless0-v2"


def enabled(artifact: Any) -> bool:
    return getattr(artifact, "runtime_key", None) == KEY


def resources(root: Path = ROOT) -> dict[str, str]:
    reject_links(root)
    files = list(root.rglob("*"))
    if {p.relative_to(root).as_posix() for p in files} != {"window.lua", "window.json"}:
        raise ValueError("Owned window resource closure changed")
    for path in files:
        reject_links(path)
        if not path.is_file():
            raise ValueError("Window resources must be ordinary files")
    return {p.name: sha(p) for p in files}


def read_observation(path: Path) -> dict[str, Any]:
    reject_links(path)
    if path.stat().st_size > 8192:
        raise ValueError("Oversized window observation")
    value = json.loads(path.read_text())
    if (
        value.get("schema") != "visible-window-profile-v2"
        or value.get("width") != 800
        or value.get("height") != 600
        or value.get("fullscreen") is not False
        or value.get("visible") is not True
        or value.get("vsync") != 0
        or not isinstance(value.get("renderer"), dict)
        or not all(isinstance(value["renderer"].get(k), str) for k in ("name", "version", "vendor", "device"))
    ):
        raise ValueError("Actual owned window does not match the execution profile")
    return value
