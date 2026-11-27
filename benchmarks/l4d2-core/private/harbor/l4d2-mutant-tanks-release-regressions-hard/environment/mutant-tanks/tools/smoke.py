#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILER = Path(os.environ.get("SP_COMPILER", "/opt/sourcemod/addons/sourcemod/scripting/spcomp64"))
SM_INCLUDE = Path(os.environ.get("SM_INCLUDE", "/opt/sourcemod/addons/sourcemod/scripting/include"))
SCRIPTING = ROOT / "addons/sourcemod/scripting"
TARGETS = (
    SCRIPTING / "mutant_tanks/mutant_tanks.sp",
    SCRIPTING / "mutant_tanks/mt_abilities.sp",
    SCRIPTING / "mutant_tanks/mt_abilities2.sp",
)
REQUIRED_SOURCES = (
    SCRIPTING / "mutant_tanks/mutant_tanks.sp",
    SCRIPTING / "mutant_tanks/mt_abilities.sp",
    SCRIPTING / "mutant_tanks/mt_abilities2.sp",
    SCRIPTING / "mutant_tanks/abilities/mt_acid.sp",
    SCRIPTING / "mutant_tanks/abilities/mt_ammo.sp",
    SCRIPTING / "mutant_tanks/abilities/mt_hypno.sp",
    SCRIPTING / "mutant_tanks/abilities2/mt_meteor.sp",
    SCRIPTING / "mutant_tanks/abilities2/mt_panic.sp",
    SCRIPTING / "mutant_tanks/abilities2/mt_warp.sp",
)
FORBIDDEN = {
    ".smx", ".dll", ".exe", ".so", ".dylib", ".a", ".lib", ".o", ".obj", ".pdb",
    ".zip", ".7z", ".rar", ".vpk", ".tar", ".gz", ".tgz", ".bz2", ".xz",
    ".bsp", ".nav", ".ain", ".mdl", ".vtx", ".vvd", ".phy", ".ani",
    ".wav", ".mp3", ".ogg", ".vtf", ".vmt", ".pcf",
}
ALLOWED_SUFFIXES = {".cfg", ".inc", ".md", ".py", ".sp", ".txt"}
ALLOWED_UNSUFFIXED = {"LICENSE"}
FORBIDDEN_MAGIC = (b"\x7fELF", b"MZ", b"FFPS", b"PK\x03\x04", b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x1f\x8b", b"\xfd7zXZ")
IMMUTABLE_HASHES = {
    "LICENSE": "8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903",
    "UPSTREAM.md": "851046a045d2c95f46e8d9a5a2f50dfc965ee1fc548dc7742e80dfc882c04fb7",
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
SPDX_GPL_PATTERN = re.compile(
    r"(?im)^\s*(?://|/\*+|\*)\s*SPDX-License-Identifier:\s*GPL-3\.0(?:-or-later|\+)?\s*(?:\*/)?\s*$"
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


def has_gpl_attribution(source: str) -> bool:
    return "GNU General Public License" in source or SPDX_GPL_PATTERN.search(source) is not None


def has_consistent_line_endings(payload: bytes) -> bool:
    without_crlf = payload.replace(b"\r\n", b"")
    has_crlf = len(without_crlf) != len(payload)
    has_bare_lf = b"\n" in without_crlf
    has_lone_cr = b"\r" in without_crlf
    return not has_lone_cr and not (has_crlf and has_bare_lf)


def main() -> int:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_symlink():
            errors.append(f"symbolic link is not allowed: {path.relative_to(ROOT)}")
        elif path.name == ".git":
            errors.append("Git metadata is not allowed")
        elif path.is_dir():
            continue
        elif path.is_file():
            logical = path.relative_to(ROOT)
            suffix = path.suffix.lower()
            logical_text = logical.as_posix()
            if (suffix not in ALLOWED_SUFFIXES and logical_text not in ALLOWED_UNSUFFIXED) or suffix in FORBIDDEN:
                errors.append(f"non-source/package artifact is not allowed: {logical}")
            payload = path.read_bytes()
            header = payload[:8]
            if any(header.startswith(magic) for magic in FORBIDDEN_MAGIC):
                errors.append(f"binary/archive file content is not allowed: {logical}")
            try:
                decoded = payload.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"public-source files must be UTF-8 text: {logical}")
                decoded = ""
            if "\x00" in decoded:
                errors.append(f"NUL bytes are not allowed in public-source text: {logical}")
            if suffix == ".py" and logical_text != "tools/smoke.py":
                errors.append(f"additional executable Python helpers are not allowed: {logical}")
            if logical_text != "tools/smoke.py" and any(
                pattern.search(decoded) for pattern in CREDENTIAL_PATTERNS
            ):
                errors.append(f"credential-like material is not allowed: {logical}")
            if path.suffix.lower() in {".sp", ".inc"}:
                if not has_consistent_line_endings(payload):
                    errors.append(f"mixed or invalid line endings are not allowed: {logical}")
                if not has_gpl_attribution(decoded):
                    errors.append(f"GPL attribution is missing: {logical}")
                if any(pattern.search(executable_source(decoded)) for pattern in NETWORK_SOURCE_PATTERNS):
                    errors.append(f"executable network-client code is not allowed: {logical}")
        else:
            errors.append(f"non-regular filesystem entry is not allowed: {path.relative_to(ROOT)}")
    for relative, expected in IMMUTABLE_HASHES.items():
        immutable = ROOT / relative
        if not immutable.is_file():
            errors.append(f"required frozen provenance file is missing: {relative}")
        elif canonical_sha256(immutable) != expected:
            errors.append(f"frozen license/provenance text was modified: {relative}")
    for required in REQUIRED_SOURCES:
        if not required.is_file():
            errors.append(f"required task source is missing: {required.relative_to(ROOT)}")
    if errors:
        print("package check failed:\n- " + "\n- ".join(errors))
        return 1
    if not COMPILER.is_file():
        print(f"compiler unavailable: {COMPILER}")
        return 1
    with tempfile.TemporaryDirectory(prefix="gcb-mutant-tanks-") as directory:
        for source in TARGETS:
            output = Path(directory) / source.with_suffix(".smx").name
            command = [
                str(COMPILER), "-i", str(SM_INCLUDE), "-i", str(SCRIPTING / "include"),
                "-i", str(SCRIPTING), "-o", str(output), str(source),
            ]
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            print(result.stdout, end="")
            print(result.stderr, end="")
            if result.returncode:
                return result.returncode
    print("public smoke passed: source-only package and all three production plugins compile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
