#!/usr/bin/env python3
"""Public source/entrypoint smoke check; contains no benchmark assertions."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "LICENSE",
    "vscripts/director_base_addon.nut",
    "vscripts/LinGe/VSLib.nut",
    "vscripts/LinGe/Base.nut",
    "vscripts/LinGe/HUD.nut",
    "vscripts/LinGe/Hint.nut",
    "vscripts/LinGe/RewardHP.nut",
)
ENTRY_INCLUDES = (
    'IncludeScript("LinGe/VSLib")',
    'IncludeScript("LinGe/Base")',
    'IncludeScript("LinGe/HUD")',
    'IncludeScript("LinGe/Hint")',
    'IncludeScript("LinGe/RewardHP")',
)


def scan_squirrel(source: str) -> list[str]:
    errors: list[str] = []
    stack: list[tuple[str, int]] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    state = "code"
    quote = ""
    line = 1
    index = 0
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if char == "\n":
            line += 1
        if state == "line-comment":
            if char == "\n":
                state = "code"
        elif state == "block-comment":
            if char == "*" and following == "/":
                state = "code"
                index += 1
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == quote:
                state = "code"
        elif state == "raw-string":
            if char == '"' and following == '"':
                index += 1
            elif char == '"':
                state = "code"
        elif char == "/" and following == "/":
            state = "line-comment"
            index += 1
        elif char == "/" and following == "*":
            state = "block-comment"
            index += 1
        elif char in {'"', "'"}:
            state = "raw-string" if char == '"' and index > 0 and source[index - 1] == "@" else "string"
            quote = char
        elif char in "([{":
            stack.append((char, line))
        elif char in ")]}":
            if not stack or stack[-1][0] != pairs[char]:
                errors.append(f"line {line}: unmatched {char}")
            else:
                stack.pop()
        index += 1
    if state == "block-comment":
        errors.append("unterminated block comment")
    elif state in {"string", "raw-string"}:
        errors.append(f"line {line}: unterminated string")
    errors.extend(f"line {opened}: unclosed {token}" for token, opened in stack)
    return errors


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            failures.append(f"missing regular file: {relative}")

    license_path = ROOT / "LICENSE"
    if license_path.is_file():
        license_text = license_path.read_text(encoding="utf-8", errors="replace")
        if "MIT License" not in license_text or "Copyright (c) 2021 LinGe" not in license_text:
            failures.append("upstream MIT attribution is missing")

    entrypoint = ROOT / "vscripts/director_base_addon.nut"
    if entrypoint.is_file():
        entry_text = entrypoint.read_text(encoding="utf-8", errors="replace")
        for include in ENTRY_INCLUDES:
            if include not in entry_text:
                failures.append(f"addon entrypoint lost {include}")

    checked = 0
    for path in sorted((ROOT / "vscripts").rglob("*.nut")):
        checked += 1
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            failures.append(f"{path.relative_to(ROOT)}: not UTF-8: {error}")
            continue
        failures.extend(
            f"{path.relative_to(ROOT)}: {message}" for message in scan_squirrel(source)
        )

    if failures:
        print("SMOKE_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"SMOKE_PASSED required={len(REQUIRED)} squirrel_files={checked}")
    print("This public smoke checks source shape only; behavioral cases remain private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
