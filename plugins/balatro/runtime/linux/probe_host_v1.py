"""Read-only, bounded Linux host diagnostics; never installs or starts an engine.

Run inside the Linux guest, not with Windows Python. Output is a new private JSON
file. Environment values, Docker container inventories and account state are not
collected. Passing this probe is not an engine or sandbox support claim.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COMMANDS = {
    "python": ["python3", "--version"],
    "git": ["git", "--version"],
    "docker": ["docker", "version", "--format", "{{json .Server}}"],
}


def command(args: list[str]) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
        # These three fixed read-only commands do not expose configuration or secrets.
        return {"exit_code": result.returncode, "stdout": result.stdout[:16384],
                "stderr": result.stderr[:2048], "timed_out": False,
                "elapsed_seconds": round(time.monotonic() - started, 3)}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "timed_out": True,
                "elapsed_seconds": round(time.monotonic() - started, 3)}
    except OSError:
        return {"exit_code": None, "timed_out": False, "reason": "command_unavailable"}


def classify(value: dict[str, Any]) -> dict[str, bool]:
    docker = value["commands"]["docker"]
    try:
        server = json.loads(docker.get("stdout", ""))
    except (ValueError, TypeError):
        server = None
    linux = value["system"] == "Linux" and value["machine"] in {"x86_64", "amd64"}
    daemon = (docker.get("exit_code") == 0 and isinstance(server, dict)
              and server.get("Os") == "linux" and server.get("Arch") in {"amd64", "x86_64"})
    return {"linux_x64": linux, "linux_docker": daemon,
            "visible_display_endpoint": value["x11_socket"] and value["display_present"],
            "host_prerequisites_available": linux and daemon and value["x11_socket"]
            and value["display_present"], "real_engine_validated": False}


def collect() -> dict[str, Any]:
    x11 = Path("/tmp/.X11-unix/X0")
    value: dict[str, Any] = {
        "schema_version": 1, "probe": "balatro-linux-host-v1",
        "checked_at": datetime.now(UTC).isoformat(),
        "system": platform.system(), "machine": platform.machine(),
        "kernel": platform.release(),
        "display_present": bool(os.environ.get("DISPLAY")),
        "wayland_present": bool(os.environ.get("WAYLAND_DISPLAY")),
        "wslg_present": Path("/mnt/wslg").is_dir(),
        "x11_socket": x11.exists() and stat.S_ISSOCK(x11.stat().st_mode),
        "commands": {name: command(args) for name, args in COMMANDS.items()},
        "tools": {name: shutil.which(name) is not None for name in
                  ("uv", "love", "Xvfb", "glxinfo", "shellcheck", "gh", "devenv")},
        "disk_free_bytes": shutil.disk_usage(Path.cwd()).free,
        "system_mutations": False, "engine_started": False,
    }
    value["checks"] = classify(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("run this probe with Linux Python inside the Linux host/guest")
    value = collect()
    # Exclusive creation preserves previous evidence. Parent must already exist.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    print(json.dumps(value["checks"]))
    raise SystemExit(0 if value["checks"]["host_prerequisites_available"] else 2)


if __name__ == "__main__":
    main()
