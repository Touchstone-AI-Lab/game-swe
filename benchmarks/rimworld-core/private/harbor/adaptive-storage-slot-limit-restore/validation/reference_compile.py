"""Compile fresh controls using an existing pinned SDK; never install or launch a game."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Authoring entry points must not create bytecode caches in pack/source directories.
sys.dont_write_bytecode = True

from materialize_control import materialize  # noqa: E402
from rhenium_rimworld.safe_files import ensure_directory_nofollow, write_owner_file  # noqa: E402

SDK_VERSION = "8.0.422"


def compile_controls(state: Path, dotnet: str | None, controls: list[str]) -> int:
    task = Path(__file__).resolve().parent.parent
    pack = task.parents[2]
    state = state.absolute()
    resolved = state.resolve()
    if resolved.is_relative_to(pack) or pack.is_relative_to(resolved):
        raise ValueError("compile state must be outside the benchmark pack")
    if state.exists() or state.is_symlink():
        raise ValueError("compile state already exists; old assemblies cannot be reused")
    ensure_directory_nofollow(state)
    report: dict[str, Any] = {
        "compileValidated": False, "engineValidated": False,
        "requiredSdk": SDK_VERSION, "commands": [], "controls": [],
    }

    def save() -> None:
        write_owner_file(state / "compile.json", (json.dumps(report, indent=2) + "\n").encode())

    executable = shutil.which(dotnet or "dotnet")
    if executable is None:
        report.update(status="unavailable", reason="No existing dotnet executable was found")
        save()
        return 2
    executable = str(Path(executable).resolve(strict=True))
    report["toolchain"] = {"executable": executable,
                           "sha256": hashlib.sha256(Path(executable).read_bytes()).hexdigest()}
    env = os.environ.copy()
    env.update(DOTNET_CLI_HOME=str(state / "dotnet-home"), DOTNET_NOLOGO="1",
               DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1", DOTNET_CLI_TELEMETRY_OPTOUT="1",
               NUGET_PACKAGES=str(state / "nuget"), MSBUILDDISABLENODEREUSE="1")

    def run(args: list[str], label: str) -> subprocess.CompletedProcess[str]:
        command = [executable, *args]
        result = subprocess.run(command, cwd=state, env=env, text=True,
                                capture_output=True, check=False, timeout=600)
        write_owner_file(state / (label + ".log"), (result.stdout + result.stderr).encode())
        report["commands"].append({"command": command, "exitCode": result.returncode, "log": label + ".log"})
        return result

    try:
        version = run(["--version"], "sdk-version")
        if version.returncode != 0 or version.stdout.strip() != SDK_VERSION:
            report.update(status="unavailable", reason="Existing SDK does not match the pinned SDK")
            save()
            return 2
        if run(["--info"], "sdk-info").returncode != 0:
            report.update(status="unavailable", reason="Existing SDK identity probe failed")
            save()
            return 2
        for control in controls:
            output = materialize(task, control, state / "materializations")
            record: dict[str, Any] = {"id": control, "status": "not-run", "assemblies": {}}
            record["materialization"] = str(output)
            record["materializationPlanSha256"] = hashlib.sha256(
                (output / "private-plan.json").read_bytes()
            ).hexdigest()
            report["controls"].append(record)
            candidate = output / "candidate/AdaptiveStorage"
            adapter = output / "adapter"
            properties = ["-p:ImportDirectoryBuildProps=false", "-p:ImportDirectoryBuildTargets=false"]
            for role, project, extra, assembly in [
                ("candidate", adapter / "Submission.csproj", f"-p:SubmissionRoot={candidate}",
                 "AdaptiveStorage.dll"),
                ("verifier", adapter / "Harness/Harness.csproj",
                 f"-p:CandidateAssembly={output / 'build/candidate/AdaptiveStorage.dll'}",
                 "RheniumRimWorldVerifier.dll"),
            ]:
                settings = [*properties, extra, f"-p:BaseIntermediateOutputPath={output / 'obj' / role}/",
                            f"-p:OutputPath={output / 'build' / role}/"]
                restore = run(["restore", str(project), "--locked-mode",
                               "--source", "https://api.nuget.org/v3/index.json",
                               "--packages", str(state / "nuget"),
                               *settings], f"{control}-{role}-restore")
                if restore.returncode != 0:
                    record.update(status="restore-failed", role=role)
                    break
                build = run(["build", str(project), "--configuration", "Release", "--no-restore",
                             *settings], f"{control}-{role}-build")
                if build.returncode != 0:
                    record.update(status="compile-failed", role=role)
                    break
                artifact = output / "build" / role / assembly
                record["assemblies"][role] = hashlib.sha256(artifact.read_bytes()).hexdigest()
            else:
                record["status"] = "compile-validated"
        report["compileValidated"] = bool(report["controls"]) and all(
            item["status"] == "compile-validated" for item in report["controls"]
        )
        report["status"] = "compile-validated" if report["compileValidated"] else "failed"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report.update(status="failed", reason=type(error).__name__)
    save()
    return 0 if report["compileValidated"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("--dotnet", help="existing dotnet executable; SDK must be exactly 8.0.422")
    parser.add_argument("--controls", nargs="+", default=["base", "oracle", "nop"])
    args = parser.parse_args()
    raise SystemExit(compile_controls(args.state, args.dotnet, args.controls))
