"""Reuse v1 control scenarios/recording through the actual anonymous PowerShell wrapper."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import native_matrix_v1 as original
from rhenium_balatro.bridge import load_binding
from rhenium_balatro.native_assets import file_sha, json_write_new, verified_assets
from rhenium_balatro.review import candidate_identity, record_review
from rhenium_balatro.winjob import hidden_creation_flags


def run(args: argparse.Namespace) -> None:
    repository = args.repository.resolve()
    wrapper = repository / "scripts/score-exam.ps1"
    powershell = args.powershell.resolve(strict=True)
    platform_cli = original.cli
    state = args.state.resolve() / "packs/balatro/core"
    binding = load_binding(state)
    assets = verified_assets(repository / "benchmarks/balatro", binding["assets_sha256"])
    entry = {"schema_version": 2, "matrix": args.matrix,
        "driver_sha256": file_sha(Path(__file__)), "wrapper_sha256": file_sha(wrapper),
        "powershell_sha256": file_sha(powershell), "platform_python_sha256": file_sha(Path(sys.executable)),
        "entry": "scripts/score-exam.ps1", "security_mode": "honest",
        "targeted_review_records_required": args.matrix == "targeted"}
    json_write_new(args.evidence.parent / (args.evidence.name + "-entry-v2.json"), entry)

    def score_cli(arguments: list[str], repository: Path, environment: dict[str, str],
                  directory: Path, prefix: str) -> tuple[int, dict[str, Any]]:
        if arguments[0] == "prepare-attempt":
            return platform_cli(arguments, repository, environment, directory, prefix)
        if arguments[0] != "run-attempt" or arguments[2:] != ["--profile", "full",
                                                              "--security-mode", "honest"]:
            raise ValueError("unexpected scoring invocation")
        if file_sha(wrapper) != entry["wrapper_sha256"] or file_sha(powershell) != entry["powershell_sha256"]:
            raise ValueError("scoring entry changed")
        if args.matrix == "targeted":
            started = json.loads((directory / "started.json").read_bytes())
            selected = assets["controls"][started["task"]][started["role"]]
            seal, candidate = candidate_identity(Path(arguments[1]) / "starter")
            if (seal, candidate) != (selected["seal_sha256"], selected["candidate_sha256"]):
                raise ValueError("targeted source differs from reviewed authored control")
            record = record_review(state, assets, binding["assets_sha256"], started["task"],
                                   seal, candidate, selected["seal_sha256"])
            json_write_new(directory / "source-review-v2.json", record)
        command = [str(powershell), "-NoProfile", "-NonInteractive", "-File", str(wrapper),
                   arguments[1], "-Profile", "full", "-SecurityMode", "honest"]
        json_write_new(directory / (prefix + "-command.json"), command)
        env = {**environment, "PATH": str(Path(sys.executable).parent) + os.pathsep + environment["PATH"],
               "PATHEXT": ".EXE"}  # Explicit executable lookup; never inherit the host's extension list.
        with (directory / (prefix + ".json")).open("xb") as out, (
            directory / (prefix + ".stderr")
        ).open("xb") as err:
            result = subprocess.run(command, cwd=repository, env=env, stdout=out, stderr=err,
                                    creationflags=hidden_creation_flags(), check=False)
        try:
            value = json.loads((directory / (prefix + ".json")).read_bytes())
        except (ValueError, OSError):
            value = {}
        return result.returncode, value

    original.cli = score_cli
    try:
        original.run(args)
    finally:
        original.cli = platform_cli


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    for flag in ("repository", "state", "evidence", "attempts", "powershell"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--matrix", choices=("pilot", "controls", "targeted"), required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
