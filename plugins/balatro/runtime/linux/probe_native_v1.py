"""Bounded real-engine capability probe, consuming an already prepared artifact."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any

from rhenium_balatro.linux_process import NativeProcess
from rhenium_balatro.linux_runtime import BalatroLinuxProbeBuilder, identity, sha
from rhenium_balatro.native_assets import json_write_new

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeSpec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--windows-powershell", type=Path)
    parser.add_argument("--audio-backend", choices=("null",))
    parser.add_argument(
        "--mode",
        choices=(
            "isolation",
            "play",
            "start-diagnosis",
            "window-diagnosis",
            "timing-diagnosis",
            "update-diagnosis",
        ),
        required=True,
    )
    args = parser.parse_args()
    if not args.state.is_absolute() or args.state.is_symlink():
        raise ValueError("An absolute, dedicated state directory is required")
    artifact = RuntimeArtifact.model_validate(json.loads(args.prepared.read_text())["artifact"])
    specs = json.loads((args.pack / "runtimes.json").read_text())["runtimes"]
    spec = RuntimeSpec.model_validate(
        next(item for item in specs if artifact.runtime_key.endswith("/" + item["id"]))
    )
    context = BenchmarkContext(
        project_root=args.pack.parents[1],
        pack_root=args.pack,
        state_dir=args.state,
        cache_dir=args.state / "cache",
    )
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    directory = args.state / "engine-v1" / run_id
    from rhenium_balatro import linux_process

    sources = {
        "probe_native_v1.py": sha(Path(__file__)),
        "linux_process.py": sha(Path(linux_process.__file__)),
    }
    extra_mods = {}
    diagnostic_mode = args.mode in {
        "start-diagnosis",
        "window-diagnosis",
        "timing-diagnosis",
        "update-diagnosis",
    }
    if diagnostic_mode:
        name = "start_diagnostic_v2" if args.mode == "window-diagnosis" else "start_diagnostic_v1"
        if args.mode == "timing-diagnosis":
            name = "start_diagnostic_v3"
        if args.mode == "update-diagnosis":
            name = "start_diagnostic_v4"
        extra_mods[name] = Path(__file__).parent / name
    if args.mode == "window-diagnosis":
        extra_mods["window_profile_v1"] = Path(__file__).parent / "window_profile_v1"
    for name, source in extra_mods.items():
        for file in source.iterdir():
            if file.is_file():
                sources[f"{name}/{file.name}"] = sha(file)
    process = NativeProcess(
        builder=BalatroLinuxProbeBuilder(context),
        spec=spec,
        artifact=artifact,
        directory=directory,
        probe=args.mode == "isolation",
        windows_powershell=args.windows_powershell,
        extra_mods=extra_mods,
        audio_backend=args.audio_backend,
    )
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "mode": args.mode,
        "complete": False,
        "passed": False,
        "checks": [],
        "artifact_identity": artifact.identity,
        "audio_backend": args.audio_backend or "default",
        "source_sha256": sources,
        "harness_sha256": identity(sources),
        "task_bindings_changed": False,
    }
    try:
        client = process.start()
        if args.mode == "isolation":
            result["checks"] = ["early_guard", "private_save_mod_appdata", "physical_nonce"]
        else:
            assert client is not None
            client.call("health")
            client.call("rpc.discover")
            client.wait(lambda state: state["state"] == "MENU")
            if args.mode == "window-diagnosis":
                window = client.action("poc.window_profile")
                json_write_new(directory / "window-profile.json", window)
                if window["after"] != {
                    **window["after"],
                    "width": 1280,
                    "height": 720,
                    "fullscreen": False,
                    "visible": True,
                }:
                    raise RuntimeError("The declared visible window profile was not applied")
            if diagnostic_mode:
                json_write_new(directory / "diagnostic-before.json", client.call("poc.start_diagnostic"))
            state = client.action("start", {"deck": "RED", "stake": "WHITE", "seed": "POC2026A"})
            if state.get("seed") != "POC2026A":
                raise RuntimeError("Real seeded start response mismatch")
            client.wait(lambda state: state["state"] == "BLIND_SELECT")
            client.action("select")
            before = client.wait(lambda state: state["state"] == "SELECTING_HAND")
            client.action("play", {"cards": [0]})
            after = client.wait(lambda state: state["state"] in {"SELECTING_HAND", "ROUND_EVAL"}, timeout=40)
            if after["round"]["hands_played"] != before["round"]["hands_played"] + 1:
                raise RuntimeError("Real hand counter did not advance exactly once")
            json_write_new(directory / "play-evidence.json", {"before": before, "after": after})
            result["checks"] = ["health", "discovery", "isolated_visible_loopback", "fixed_seed", "real_play"]
        result.update(complete=True, passed=True)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        result["failure_class"] = "environment_or_harness_incomplete"
    finally:
        if diagnostic_mode and process.client is not None:
            try:
                json_write_new(
                    directory / "diagnostic-after.json",
                    process.client.call("poc.start_diagnostic", timeout=3),
                )
            except Exception as error:
                result["diagnostic_query_error"] = type(error).__name__
        result["cleanup"] = process.close()
        if not result["cleanup"]["normal_exit"] or not result["cleanup"]["protected_unchanged"]:
            result.update(complete=False, passed=False)
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        # A prelaunch failure still receives its own exclusive receipt, not a reused run.
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        json_write_new(directory / "probe-result.json", result)
    print(
        json.dumps(
            {
                "result": str(directory / "probe-result.json"),
                "complete": result["complete"],
                "passed": result["passed"],
                "error": result.get("error"),
            }
        )
    )
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
