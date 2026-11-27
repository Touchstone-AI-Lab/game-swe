#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SUBMISSION = Path(os.environ.get("GCB_SUBMISSION", "/workspace/fargos-mutant")).resolve()
TESTS = Path(__file__).resolve().parent
FORBIDDEN_SUFFIXES = {".dll", ".exe", ".pdb", ".so", ".tmod", ".zip", ".7z", ".tar", ".gz"}
FORBIDDEN_DIRECTORIES = {".git", "bin", "obj"}
REQUIRED_SOURCE = (
    "LICENSE",
    "Common/Systems/Recipes/MiscRecipeSystem.cs",
    "Content/Items/Tiles/EnchantedTreeSheet.cs",
    "Content/Items/Tiles/EnchantedTreeTileEntity.cs",
)


class SubmissionFailure(RuntimeError):
    pass


class EnvironmentFailure(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            env={
                **os.environ,
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "DOTNET_NOLOGO": "1",
                "NUGET_XMLDOC_MODE": "skip",
            },
        )
    except subprocess.TimeoutExpired as error:
        raise EnvironmentFailure(f"command timed out: {' '.join(command)}") from error
    except OSError as error:
        raise EnvironmentFailure(f"could not execute command: {error}") from error


def validate_inputs() -> list[str]:
    if not SUBMISSION.is_dir() or SUBMISSION.is_symlink():
        raise SubmissionFailure("submission root is missing or is a symbolic link")

    missing = [relative for relative in REQUIRED_SOURCE if not (SUBMISSION / relative).is_file()]
    if missing:
        raise SubmissionFailure("missing production source: " + ", ".join(missing))

    errors: list[str] = []
    files = 0
    size = 0
    for path in SUBMISSION.rglob("*"):
        relative = path.relative_to(SUBMISSION)
        if path.is_symlink():
            errors.append(f"{relative.as_posix()}: symbolic links are not allowed")
            continue
        if path.name in FORBIDDEN_DIRECTORIES:
            errors.append(f"{relative.as_posix()}: generated/Git path is not allowed")
            continue
        if path.is_dir():
            continue
        if any(part in FORBIDDEN_DIRECTORIES for part in relative.parts):
            continue
        if not path.is_file():
            continue
        files += 1
        size += path.stat().st_size
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{relative.as_posix()}: compiled/archive artifact is not allowed")
        if path.stat().st_size > 3_000_000:
            errors.append(f"{relative.as_posix()}: file exceeds 3 MB")
    if files > 250 or size > 8_000_000:
        errors.append(f"unexpected retained source size: files={files} bytes={size}")
    if errors:
        raise SubmissionFailure("source/package checks failed:\n- " + "\n- ".join(errors))

    raw = json.loads((TESTS / "rubric.json").read_text(encoding="utf-8"))
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EnvironmentFailure("rubric has no cases")
    names = [item.get("name") for item in cases if isinstance(item, dict)]
    if len(names) != len(cases) or any(not isinstance(name, str) or not name for name in names):
        raise EnvironmentFailure("rubric case names are invalid")
    if len(names) != len(set(names)):
        raise EnvironmentFailure("rubric case names are duplicated")
    return names


def build_harness(root: Path) -> Path:
    harness = root / "harness"
    harness.mkdir()
    for name in ("ContractTests.csproj", "Program.cs", "VerifierSupport.cs"):
        shutil.copy2(TESTS / name, harness / name)

    completed = run(
        [
            "dotnet",
            "build",
            "ContractTests.csproj",
            "-c",
            "Release",
            "--nologo",
            "--ignore-failed-sources",
            f"-p:CandidateRoot={SUBMISSION}",
        ],
        cwd=harness,
        timeout=180,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SubmissionFailure("submitted production files do not compile in the source projection")

    assembly = harness / "bin" / "Release" / "net8.0" / "ContractTests.dll"
    if not assembly.is_file():
        raise EnvironmentFailure("compiled contract harness is missing")
    return assembly


def run_case(assembly: Path, name: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["dotnet", str(assembly), name],
            cwd=assembly.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
            env={
                **os.environ,
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "DOTNET_NOLOGO": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return False, "case timed out"
    except OSError as error:
        raise EnvironmentFailure(f"could not execute case {name}: {error}") from error

    ok = result.returncode == 0 and result.stdout.strip() == "PASS"
    if ok:
        return True, ""
    lines = (result.stderr or result.stdout).strip().splitlines()
    return False, " | ".join(lines[:2])[:400] if lines else f"exit {result.returncode}"


def main() -> int:
    try:
        names = validate_inputs()
        with tempfile.TemporaryDirectory(prefix="terraria-fargos-tree-") as raw:
            root = Path(raw)
            assembly = build_harness(root)
            passed = 0
            for name in names:
                ok, detail = run_case(assembly, name)
                if ok:
                    passed += 1
                payload: dict[str, object] = {"name": name, "passed": ok}
                if not ok:
                    payload["detail"] = detail
                print(json.dumps(payload, separators=(",", ":")))

            print(json.dumps({"total": len(names), "passed": passed}, separators=(",", ":")))
            if passed != len(names):
                raise SubmissionFailure(f"contract cases did not all pass: {passed}/{len(names)}")
    except EnvironmentFailure as error:
        print(f"INVALID_ENVIRONMENT: {error}")
        return 2
    except (SubmissionFailure, OSError, ValueError) as error:
        print(f"SUBMISSION_FAILED: {error}")
        return 1

    print("VERIFICATION_PASSED: all Fargo's Mutant Mod Enchanted Tree cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
