"""Trusted bridge to the existing native assertion runner in a disposable image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rhenium_palworld.evaluator import DedicatedServerRunner
from rhenium_palworld.runtime import PalworldRuntimeConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    runner = DedicatedServerRunner(
        PalworldRuntimeConfig(
            pack_root=Path("/tmp"), palworld_root=Path("/server"), server_binary=Path("/server/run-native")
        )
    )
    result = runner.run_assertions(Path("/submission"), Path("/assertions.lua"), timeout=args.timeout)
    result["log"] = str(result.get("log", ""))[-2_000_000:]
    print("@@RHENIUM_PALWORLD_WORKER@@" + args.nonce + ":" + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
