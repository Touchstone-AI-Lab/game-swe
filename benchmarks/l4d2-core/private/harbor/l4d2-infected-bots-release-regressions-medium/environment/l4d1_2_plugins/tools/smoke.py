#!/usr/bin/env python3
from __future__ import annotations

import os
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get("SP_COMPILER", "/opt/sourcemod/addons/sourcemod/scripting/spcomp64"))
SM_INCLUDE = Path(os.environ.get("SM_INCLUDE", "/opt/sourcemod/addons/sourcemod/scripting/include"))
ALLOWED_SUFFIXES = {".cfg", ".inc", ".md", ".py", ".sp", ".txt"}
ALLOWED_UNSUFFIXED = {"LICENSE", "third_party/LEFT4DHOOKS-LICENSE", "third_party/MULTICOLORS-LICENSE"}
IMMUTABLE_HASHES = {
    "LICENSE": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    "UPSTREAM.md": "b0bdafab025ba906e9f3a756850c7631f2cde1b81cd2e33379cd953beb591825",
    "third_party/LEFT4DHOOKS-LICENSE": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    "third_party/MULTICOLORS-LICENSE": "589ed823e9a84c56feb95ac58e7cf384626b9cbf4fda2a907bc36e103de1bad2",
}
CREDENTIAL_PATTERNS = (
    re.compile(r"(?i)\bOPENAI_API_KEY\s*="),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
)
NETWORK_SOURCE_PATTERNS = (
    re.compile(r'(?im)^\s*#\s*(?:try)?include\s*[<"]\s*(?:socket|steamworks|ripext|curl|system2)(?:\.inc)?\s*[>"]'),
    re.compile(r"(?i)\b(?:SocketCreate|SocketConnect|SteamWorks_[A-Za-z0-9_]+|HTTPClient|HTTPRequest|Curl_[A-Za-z0-9_]+|System2_[A-Za-z0-9_]+)\b"),
)


def canonical_sha256(path: Path) -> str:
    payload = path.read_bytes()
    try:
        payload = payload.decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(payload).hexdigest()


def executable_source(source: str) -> str:
    return re.sub(
        r'''(?s)/\*.*?\*/|//[^\r\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' ''',
        " ",
        source,
    )


def compile_source(source: Path, output: Path, includes: list[Path]) -> None:
    command = [str(COMPILER)]
    for include in includes:
        command.extend(("-i", str(include)))
    command.extend(("-o", str(output), str(source)))
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise SystemExit(completed.stdout + completed.stderr)
    print(f"compiled {source.relative_to(ROOT)}")


def main() -> None:
    if not COMPILER.is_file():
        raise SystemExit(f"SourcePawn compiler not found: {COMPILER}")
    errors: list[str] = []
    target_source_lines = 0
    spawn_source_lines = 0
    for path in ROOT.rglob("*"):
        logical = path.relative_to(ROOT).as_posix()
        if path.is_symlink():
            errors.append(f"symbolic link is not allowed: {logical}")
            continue
        if path.name == ".git":
            errors.append(f"Git metadata is not allowed: {logical}")
        if path.is_dir():
            continue
        if not path.is_file():
            errors.append(f"non-regular filesystem entry is not allowed: {logical}")
            continue
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES and logical not in ALLOWED_UNSUFFIXED:
            errors.append(f"non-source/package artifact is not allowed: {logical}")
        payload = path.read_bytes()
        try:
            decoded = payload.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"public-source files must be UTF-8 text: {logical}")
            decoded = ""
        if "\x00" in decoded:
            errors.append(f"NUL bytes are not allowed in public-source text: {logical}")
        if suffix == ".py" and logical != "tools/smoke.py":
            errors.append(f"additional executable Python helpers are not allowed: {logical}")
        if logical != "tools/smoke.py" and any(pattern.search(decoded) for pattern in CREDENTIAL_PATTERNS):
            errors.append(f"credential-like material is not allowed: {logical}")
        if suffix in {".sp", ".inc"} and any(
            pattern.search(executable_source(decoded)) for pattern in NETWORK_SOURCE_PATTERNS
        ):
            errors.append(f"executable network-client code is not allowed: {logical}")
        if suffix in {".sp", ".inc"}:
            lines = len(decoded.splitlines())
            if logical.startswith("l4dinfectedbots/"):
                target_source_lines += lines
            elif logical.startswith("spawn_infected_nolimit/"):
                spawn_source_lines += lines
    for relative, expected in IMMUTABLE_HASHES.items():
        immutable = ROOT / relative
        if not immutable.is_file():
            errors.append(f"required frozen provenance file is missing: {relative}")
        elif canonical_sha256(immutable) != expected:
            errors.append(f"frozen license/provenance text was modified: {relative}")
    if target_source_lines < 5_200 or spawn_source_lines < 700:
        errors.append(
            "project-owned source tree was replaced or truncated: "
            f"target_lines={target_source_lines} spawn_lines={spawn_source_lines}"
        )
    if errors:
        raise SystemExit("public package check failed:\n- " + "\n- ".join(errors))
    left4dhooks = ROOT / "third_party/include/left4dhooks_bundle"
    multicolors = ROOT / "third_party/include"
    spawn_include = ROOT / "spawn_infected_nolimit/scripting/include"
    target_include = ROOT / "l4dinfectedbots/scripting/include"
    with tempfile.TemporaryDirectory(prefix="infectedbots-smoke-") as directory:
        out = Path(directory)
        compile_source(
            ROOT / "spawn_infected_nolimit/scripting/spawn_infected_nolimit.sp",
            out / "spawn_infected_nolimit.smx",
            [SM_INCLUDE, left4dhooks],
        )
        compile_source(
            ROOT / "l4dinfectedbots/scripting/l4dinfectedbots.sp",
            out / "l4dinfectedbots.smx",
            [SM_INCLUDE, left4dhooks, multicolors, spawn_include, target_include],
        )
    print("public compile smoke passed")


if __name__ == "__main__":
    main()
