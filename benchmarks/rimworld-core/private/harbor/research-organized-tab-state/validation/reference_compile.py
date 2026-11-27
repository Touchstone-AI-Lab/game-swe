"""Materialize this task's eight controls outside the repository; optionally compile them."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

# Authoring entry points must not create bytecode caches in pack/source directories.
sys.dont_write_bytecode = True

from rhenium_rimworld.assertions import generated_dispatch_source, load_assertion_manifest  # noqa: E402
from rhenium_rimworld.catalog import RimWorldCatalog  # noqa: E402
from rhenium_rimworld.safe_files import (  # noqa: E402
    ensure_directory_nofollow,
    secure_read_bytes,
    secure_tree_hash,
    write_owner_file,
)
from rhenium_rimworld.supervisor import strict_json_object  # noqa: E402

TASK_ID = "research-organized-tab-state"
TASK_ROOT = f"private/harbor/{TASK_ID}"
SDK_VERSION = "8.0.422"
CONTROL_NAMES = (
    "base", "oracle", "nop", "no-resize", "default-flags", "open-window-only",
    "stale-view", "closed-window-only",
)
PRODUCTION_SOURCE = "Source/ResearchOrganizedMain.cs"
COMMAND_TIMEOUT_SECONDS = 600


def _encode(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def _inputs(pack: Path) -> dict[str, bytes]:
    manifest = strict_json_object(
        secure_read_bytes(pack, f"{TASK_ROOT}/validation/input-manifest.json")
    )
    if manifest["schemaVersion"] != 2:
        raise ValueError("unsupported authoring input manifest")
    inputs: dict[str, bytes] = {}
    for relative, expected in manifest["files"].items():
        contents = secure_read_bytes(pack, relative, maximum=2_000_000)
        if hashlib.sha256(contents).hexdigest() != expected:
            raise ValueError(f"authoring input hash mismatch: {relative}")
        inputs[relative] = contents
    return inputs


def _mutate(contents: bytes, control: str) -> bytes:
    if control == "no-resize":
        before = b"                RebuildTabInfoVisibility(tabInfoVisibility);"
        after = b"                // Negative control: omit rebuilding native indexed flags."
    elif control == "default-flags":
        before = (b"values[tab.index] = snapshot.TryGetValue(tab, out bool visible) "
                  b"? visible : tab.visibleByDefault;")
        after = b"values[tab.index] = tab.visibleByDefault;"
    elif control == "open-window-only":
        before = (b"var window = MainButtonDefOf.Research?.TabWindow as MainTabWindow_Research\n"
                  b"                             ?? Find.WindowStack?"
                  b".WindowOfType<MainTabWindow_Research>();")
        after = b"var window = Find.WindowStack?.WindowOfType<MainTabWindow_Research>();"
    elif control == "stale-view":
        before = b"                researchWindowCurTabField.SetValue(window, null);"
        after = b"                // Negative control: retain the stale native view width."
    elif control == "closed-window-only":
        before = b"if (!(researchWindowTabsField.GetValue(window) is System.Collections.IList tabs)) return;"
        after = before + b"\n                if (window.IsOpen) return;"
    else:
        raise ValueError("unknown negative control")
    if contents.count(before) != 1:
        raise ValueError("negative control anchor is ambiguous")
    return contents.replace(before, after, 1)


def _control(inputs: dict[str, bytes], state: Path, name: str) -> dict[str, Any]:
    side = "environment" if name in {"base", "nop"} else "solution/after"
    prefix = f"{TASK_ROOT}/{side}/ResearchOrganized/"
    output = state / "controls" / name / "ResearchOrganized"
    for relative, contents in inputs.items():
        if relative.startswith(prefix):
            local = relative.removeprefix(prefix)
            if local == PRODUCTION_SOURCE and name not in {"base", "oracle", "nop"}:
                contents = _mutate(contents, name)
            write_owner_file(output / local, contents)
    return {
        "control": name, "materializationId": uuid.uuid4().hex,
        "candidateSource": secure_tree_hash(output),
        "compileValidated": False, "engineValidated": False,
    }


def materialize_controls(pack: Path, state: Path) -> dict[str, Any]:
    """Write the eight independent control trees and the build adapter outside the repository."""
    repository = next(parent for parent in pack.parents if (parent / "AGENTS.md").is_file())
    resolved = state.resolve()
    if resolved.is_relative_to(repository) or repository.is_relative_to(resolved):
        raise ValueError("authoring state must be outside the repository")
    if state.exists() or state.is_symlink():
        raise ValueError("authoring state already exists")
    inputs = _inputs(pack)
    catalog = RimWorldCatalog.load(pack)
    if TASK_ID not in {task.id for task in catalog.tasks}:
        raise ValueError("task is not registered in this pack")
    assertions = load_assertion_manifest(pack, TASK_ID)
    ensure_directory_nofollow(state)
    prefix = f"{TASK_ROOT}/tests/"
    for relative, contents in inputs.items():
        if relative.startswith(prefix) and relative != prefix + "assertions.json":
            write_owner_file(state / "adapter" / relative.removeprefix(prefix), contents)
    write_owner_file(state / "adapter/Harness/GeneratedAssertions.cs", generated_dispatch_source(assertions))
    controls = [_control(inputs, state, name) for name in CONTROL_NAMES]
    report: dict[str, Any] = {
        "schemaVersion": 2, "status": "materialized",
        "compileValidated": False, "engineValidated": False,
        "caseCount": len(assertions.cases), "taskKey": assertions.task_key,
        "catalogVersion": catalog.version, "controls": controls,
    }
    write_owner_file(state / "materialization.json", _encode(report))
    return report


def _run(executable: str, arguments: list[str], state: Path, label: str) -> int:
    environment = os.environ | {
        "DOTNET_CLI_HOME": str(state / "dotnet-home"), "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
        "NUGET_PACKAGES": str(state / "nuget"), "MSBUILDDISABLENODEREUSE": "1",
    }
    with (state / (label + ".log")).open("wb") as log:
        try:
            process = subprocess.run([executable, *arguments], cwd=state, env=environment,
                                     stdout=log, stderr=subprocess.STDOUT, check=False,
                                     timeout=COMMAND_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return 124
    return process.returncode


def _compile_control(executable: str, state: Path, control: dict[str, Any]) -> None:
    name = str(control["control"])
    output = state / "build" / name
    roles = (
        ("candidate", "Submission.csproj", "SubmissionRoot",
         state / "controls" / name / "ResearchOrganized", "ResearchOrganized.dll"),
        ("verifier", "Harness/Harness.csproj", "CandidateAssembly",
         output / "candidate/ResearchOrganized.dll", "RheniumRimWorldVerifier.dll"),
    )
    for role, project, property_name, property_value, assembly in roles:
        settings = ["-p:ImportDirectoryBuildProps=false", "-p:ImportDirectoryBuildTargets=false",
                    f"-p:{property_name}={property_value}",
                    f"-p:BaseIntermediateOutputPath={state / 'obj' / name / role}/",
                    f"-p:OutputPath={output / role}/"]
        for operation in ("restore", "build"):
            flags = ["--locked-mode", "--source", "https://api.nuget.org/v3/index.json"]
            if operation == "build":
                flags = ["--configuration", "Release", "--no-restore"]
            arguments = [operation, str(state / "adapter" / project), *flags, *settings]
            label = f"{name}-{role}-{operation}"
            exit_code = _run(executable, arguments, state, label)
            control["commands"].append({"arguments": arguments, "exitCode": exit_code, "log": label + ".log"})
            if exit_code != 0:
                control.update(status="failed", failedRole=role, failedOperation=operation)
                return
        raw = (output / role / assembly).read_bytes()
        control["assemblies"][role] = hashlib.sha256(raw).hexdigest()
    control.update(status="compile-validated", compileValidated=True)


def _reset_compile_evidence(report: dict[str, Any]) -> None:
    report.update(status="not-run", compileValidated=False, engineValidated=False)
    report.pop("reason", None)
    for control in report["controls"]:
        control.update(status="not-run", compileValidated=False, engineValidated=False,
                       commands=[], assemblies={})
        control.pop("failedRole", None)
        control.pop("failedOperation", None)


def compile_controls(state: Path, report: dict[str, Any], dotnet: str | None) -> int:
    """Record only this invocation's compilation evidence; never launch a game."""
    _reset_compile_evidence(report)
    try:
        executable = shutil.which(dotnet or "dotnet")
        if executable is None or _run(executable, ["--version"], state, "sdk-version") != 0:
            report.update(status="unavailable", reason="pinned SDK unavailable")
        elif (state / "sdk-version.log").read_text().strip() != SDK_VERSION:
            report.update(status="unavailable", reason="SDK version mismatch")
        else:
            for control in report["controls"]:
                _compile_control(executable, state, control)
                if not control["compileValidated"]:
                    break
            report["compileValidated"] = bool(report["controls"]) and all(
                item["compileValidated"] for item in report["controls"]
            )
            report["status"] = "compile-validated" if report["compileValidated"] else "failed"
    except (OSError, subprocess.SubprocessError) as error:
        report.update(status="failed", reason=type(error).__name__)
    report["requiredSdk"] = SDK_VERSION
    write_owner_file(state / "compile.json", _encode(report))
    return 0 if report["compileValidated"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("--compile", dest="should_compile", action="store_true")
    parser.add_argument("--dotnet")
    args = parser.parse_args()
    materialized = materialize_controls(Path(__file__).resolve().parents[4], args.state.absolute())
    if args.should_compile:
        raise SystemExit(compile_controls(args.state.absolute(), materialized, args.dotnet))
