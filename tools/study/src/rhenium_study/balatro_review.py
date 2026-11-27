"""Automated source review of Balatro submissions, the step before they may run.

The Balatro runtime executes a submission inside the game's Lua state, next to the
observer mod that reports results, in a networkless container that is not a sandbox.
Its plugin therefore runs only bytes whose seal an operator has recorded after reading
them (``rhenium_balatro.container_operator review``). This module lets a study record
that seal without a person reading every file: a deterministic policy scans each sealed
file, and only a submission with no finding is sealed. Anything the policy flags is left
for the operator to read, so the policy can only withhold a seal, never grant one that
reading would have refused for a reason it checks.

The policy looks for what a source review looked for: file, process, network and
dynamic-code capabilities, and references to the observer, the guard and the BalatroBot
harness. It parses Lua's comments and strings, so a word in a comment is not a finding.
It is a guard for honest submissions, not a sandbox: deliberately obfuscated code can
reach a capability it does not name, and it cannot tell whether code special-cases a
scoring scene or writes game state to fake a result. Those judgements still need a
person when they matter.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import controls

POLICY = "balatro-static-review-v1"
REPORT = "auto-review.json"
SEALED = "sealed"
NEEDS_OPERATOR = "operator-review-required"

# Free names that grant a capability an honest mod does not need.
DENIED_GLOBALS: dict[str, str] = {
    "io": "file access",
    "debug": "the debug library",
    "package": "module loader state",
    "require": "module loading",
    "module": "module loading",
    "load": "dynamic code",
    "loadstring": "dynamic code",
    "loadfile": "dynamic code",
    "dofile": "dynamic code",
    "setfenv": "environment replacement",
    "getfenv": "environment access",
    "_G": "the global table",
    "_ENV": "the global environment",
    "newproxy": "userdata proxies",
    "collectgarbage": "collector control",
    "jit": "LuaJIT control",
    "ffi": "native calls",
    "socket": "network access",
    "NFS": "native file access",
    "nativefs": "native file access",
    "lovely": "mod loader internals",
}
# ``os`` is allowed only for reading the clock.
OS_READ_ONLY = frozenset({"time", "clock", "date", "difftime"})
# ``love`` is allowed only for its timer and math modules; the observer hooks the rest.
LOVE_ALLOWED = frozenset({"timer", "math"})
# Field names that reach a capability or the observer whatever table holds them.
DENIED_FIELDS: dict[str, str] = {
    "dump": "bytecode dump",
    "getenv": "the process environment",
    "popen": "process creation",
    "NFS": "native file access",
    "setup_run": "a function the observer wraps",
}
# Names of the observer, guard and BalatroBot harness.
HARNESS_PREFIXES = ("BB_", "POC_")
HARNESS_STRINGS = (
    "poc.runtime",
    "poc.quit",
    "poc_control",
    "poc_guard",
    "poc_nonce",
    "poc_save_dir",
    "poc_run_dir",
    "poc_probe_only",
    "lovely_mod_dir",
    "bb_dispatcher",
    "bb_server",
    "balatrobot",
    "isolation.txt",
    "guard-error",
)
ALLOWED_SUFFIXES = frozenset({".lua", ".json"})

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(
    r"0[xX][0-9A-Fa-f]*(?:\.[0-9A-Fa-f]*)?(?:[pP][+-]?\d+)?|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
)
_LONG_OPEN = re.compile(r"\[(=*)\[")
_PUNCT = ("...", "..", "==", "~=", "<=", ">=", "::", "//", "<<", ">>")


class LexError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


@dataclass(frozen=True)
class Token:
    kind: str  # "name", "string", "number" or "punct"
    value: str
    line: int


def tokenize(text: str) -> list[Token]:
    """Lua 5.1/LuaJIT tokens without comments; string values keep their escapes undecoded."""
    tokens: list[Token] = []
    index, line, size = 0, 1, len(text)
    while index < size:
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char in " \t\r\f\v":
            index += 1
            continue
        if text.startswith("--", index):
            opened = _LONG_OPEN.match(text, index + 2)
            if opened:
                close = "]" + opened.group(1) + "]"
                end = text.find(close, opened.end())
                if end < 0:
                    raise LexError(line, "unterminated long comment")
                line += text.count("\n", index, end)
                index = end + len(close)
            else:
                end = text.find("\n", index)
                index = size if end < 0 else end
            continue
        opened = _LONG_OPEN.match(text, index)
        if opened:
            close = "]" + opened.group(1) + "]"
            end = text.find(close, opened.end())
            if end < 0:
                raise LexError(line, "unterminated long string")
            tokens.append(Token("string", text[opened.end() : end], line))
            line += text.count("\n", index, end)
            index = end + len(close)
            continue
        if char in "'\"":
            cursor = index + 1
            while True:
                if cursor >= size or text[cursor] == "\n":
                    raise LexError(line, "unterminated string")
                if text[cursor] == "\\":
                    cursor += 2
                elif text[cursor] == char:
                    break
                else:
                    cursor += 1
            value = text[index + 1 : cursor]
            tokens.append(Token("string", value, line))
            line += value.count("\n")
            index = cursor + 1
            continue
        if char.isdigit() or (char == "." and index + 1 < size and text[index + 1].isdigit()):
            number = _NUMBER.match(text, index)
            if number is None:  # pragma: no cover - the class above always matches a digit
                raise LexError(line, "malformed number")
            tokens.append(Token("number", number.group(0), line))
            index = number.end()
            continue
        name = _NAME.match(text, index)
        if name:
            tokens.append(Token("name", name.group(0), line))
            index = name.end()
            continue
        punct = next((p for p in _PUNCT if text.startswith(p, index)), char)
        tokens.append(Token("punct", punct, line))
        index += len(punct)
    return tokens


def _is(token: Token | None, kind: str, value: str | None = None) -> bool:
    return token is not None and token.kind == kind and (value is None or token.value == value)


def _at(tokens: list[Token], index: int) -> Token | None:
    return tokens[index] if 0 <= index < len(tokens) else None


def _loads_sealed_file(tokens: list[Token], index: int, files: frozenset[str]) -> bool:
    """``SMODS.load_file('<sealed file>' ...)`` with a plain literal path; ``index`` is ``load_file``."""
    if not (_is(_at(tokens, index - 1), "punct", ".") and _is(_at(tokens, index - 2), "name", "SMODS")):
        return False
    before = _at(tokens, index - 3)
    if _is(before, "punct", ".") or _is(before, "punct", ":"):
        return False
    path = _at(tokens, index + 2)
    if not (_is(_at(tokens, index + 1), "punct", "(") and path is not None and path.kind == "string"):
        return False
    if not (_is(_at(tokens, index + 3), "punct", ",") or _is(_at(tokens, index + 3), "punct", ")")):
        return False
    return "\\" not in path.value and path.value in files


def _string_findings(value: str) -> Iterator[str]:
    lowered = value.lower()
    for marker in HARNESS_STRINGS:
        if marker in lowered:
            yield f"names the harness ({marker})"


def scan_lua(text: str, files: frozenset[str]) -> list[tuple[int, str, str]]:
    """Findings in one Lua file as ``(line, rule, detail)``; ``files`` are the sealed names."""
    tokens = tokenize(text)
    found: list[tuple[int, str, str]] = []
    for index, token in enumerate(tokens):
        if token.kind == "string":
            found += [(token.line, "harness", detail) for detail in _string_findings(token.value)]
            continue
        if token.kind != "name":
            continue
        name = token.value
        if name.startswith(HARNESS_PREFIXES) or name.lower() == "balatrobot":
            found.append((token.line, "harness", f"names the harness ({name})"))
        previous = _at(tokens, index - 1)
        if _is(previous, "punct", ".") or _is(previous, "punct", ":"):
            if name in DENIED_FIELDS:
                found.append((token.line, "capability", f"field {name}: {DENIED_FIELDS[name]}"))
            elif name == "load_file" and not _loads_sealed_file(tokens, index, files):
                found.append(
                    (token.line, "dynamic-code", "load_file of anything but a sealed file named literally")
                )
            continue
        following, member = _at(tokens, index + 1), _at(tokens, index + 2)
        dotted = _is(following, "punct", ".") and member is not None and member.kind == "name"
        if name in DENIED_GLOBALS:
            found.append((token.line, "capability", f"{name}: {DENIED_GLOBALS[name]}"))
        elif name == "os" and not (
            (dotted and member is not None and member.value in OS_READ_ONLY)
            # A truth test (`if os and os.time then`) does not hand the table on.
            or _is(following, "name", "and")
            or _is(following, "name", "then")
        ):
            found.append((token.line, "capability", "os beyond reading the clock"))
        elif name == "love" and not (dotted and member is not None and member.value in LOVE_ALLOWED):
            found.append((token.line, "capability", "love beyond its timer and math modules"))
        elif name in {"string", "SMODS"} and _is(following, "punct", "["):
            found.append((token.line, "dynamic-code", f"computed field of {name}"))
        elif name == "getmetatable" and _is(following, "punct", "(") and _is(member, "string"):
            found.append((token.line, "capability", "the string metatable"))
    return found


def _json_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)


def scan_tree(root: Path) -> dict[str, Any]:
    """Scan every file under the mod root ``root`` (a submission's ``starter``)."""
    entries: list[tuple[str, Path]] = []
    findings: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            findings.append({"file": name, "line": None, "rule": "file", "detail": "symbolic link"})
        elif path.is_file():
            entries.append((name, path))
    names = frozenset(name for name, _ in entries)
    files = []
    for name, path in entries:
        data = path.read_bytes()
        record: dict[str, Any] = {"name": name, "sha256": hashlib.sha256(data).hexdigest(), "lines": None}
        files.append(record)

        def add(line: int | None, rule: str, detail: str, file: str = name) -> None:
            findings.append({"file": file, "line": line, "rule": rule, "detail": detail})

        if path.suffix not in ALLOWED_SUFFIXES:
            add(None, "file", f"file type {path.suffix or '(none)'} is not reviewed by the policy")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            add(None, "file", "not UTF-8 text")
            continue
        record["lines"] = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        if path.suffix == ".json":
            try:
                parsed = json.loads(text)
            except ValueError as error:
                add(None, "file", f"not valid JSON: {error}")
                continue
            for value in _json_strings(parsed):
                for detail in _string_findings(value):
                    add(None, "harness", detail)
            continue
        try:
            for line, rule, detail in scan_lua(text, names):
                add(line, rule, detail)
        except LexError as error:
            add(error.line, "file", f"not parsed: {error}")
    return {"policy": POLICY, "files": files, "findings": findings}


Operator = Callable[[str, Path, str, list[str]], dict[str, Any]]
Evaluator = Callable[[str, Path], dict[str, Any]]
RESULTS = ("result-1.json", "result-2.json")


def artifact_identity(artifact: Path) -> str:
    """The identity of the prepared runtime artifact named by a ``runtime verify`` output.

    The plugin keeps each seal in the artifact's own operator state, so a seal recorded on
    one preparation does not exist on the next one.
    """
    data = json.loads(artifact.read_text(encoding="utf-8-sig"))
    inner = data.get("artifact", data) if isinstance(data, dict) else None
    identity = inner.get("identity") if isinstance(inner, dict) else None
    if not isinstance(identity, str) or not identity:
        raise ValueError(f"{artifact} names no runtime artifact identity")
    return identity


def container_operator(pack: Path, state: Path, cache: Path, artifact: Path) -> Operator:
    """The plugin's own inspection and review command for the prepared Linux container."""

    def call(operation: str, submission: Path, task: str, extra: list[str]) -> dict[str, Any]:
        command = [
            sys.executable,
            "-m",
            "rhenium_balatro.container_operator",
            operation,
            "--pack",
            str(pack),
            "--state",
            str(state),
            "--cache",
            str(cache),
            "--artifact",
            str(artifact),
            "--submission",
            str(submission),
            "--task",
            task,
            *extra,
        ]
        done = subprocess.run(
            command, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=2400
        )
        if done.returncode != 0:
            tail = (done.stderr.strip().splitlines() or ["no output"])[-1][:300]
            raise RuntimeError(f"container_operator {operation} failed for {task}: {tail}")
        lines = done.stdout.strip().splitlines()
        if not lines:
            raise RuntimeError(f"container_operator {operation} printed nothing for {task}")
        value = json.loads(lines[-1])
        if not isinstance(value, dict):
            raise RuntimeError(f"container_operator {operation} printed no JSON object for {task}")
        return value

    return call


def rhenium_run() -> Evaluator:
    """``rhenium run <task> <submission> --profile full``, the evaluator a kit uses."""

    def call(task: str, submission: Path) -> dict[str, Any]:
        done = subprocess.run(
            [sys.executable, "-m", "rhenium.cli", "run", task, str(submission), "--profile", "full"],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        try:
            value = json.loads(done.stdout)
        except ValueError:
            return {"stdout": "", "stderrTail": done.stderr[-2000:], "exitCode": done.returncode}
        return value if isinstance(value, dict) else {}

    return call


def kit_manifest(kit: Path, study_id: str, config_digest: str) -> dict[str, Any]:
    manifest = json.loads((kit / "manifest.json").read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("the kit manifest is not a JSON object")
    if manifest.get("studyId") != study_id or manifest.get("configDigest") != config_digest:
        raise ValueError("the kit was exported for a different study configuration")
    return manifest


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def review_attempt(kit: Path, entry: dict[str, Any], operator: Operator, artifact: str) -> dict[str, Any]:
    """Scan one frozen submission, then seal it through the plugin only if nothing was found.

    ``artifact`` is the identity of the runtime artifact the operator seals on.
    """
    submission = kit / entry["submission"]
    if controls.tree_digest(submission) != entry["submissionDigest"]:
        raise ValueError(f"{entry['attemptId']}: the frozen submission does not match its digest")
    task = str(entry["task"]).rsplit("/", 1)[-1]
    scan = scan_tree(submission / "starter")
    inspected = operator("inspect", submission, task, [])
    seal = inspected.get("submissionSha256")
    scanned = sorted(f["name"] for f in scan["files"])
    if not isinstance(seal, str) or sorted(inspected.get("files") or []) != scanned:
        raise ValueError(f"{entry['attemptId']}: the plugin sealed other files than the policy scanned")
    decision = NEEDS_OPERATOR if scan["findings"] else SEALED
    if decision == SEALED:
        operator("review", submission, task, ["--source-reviewed", "--reviewed-sha", seal])
    if controls.tree_digest(submission) != entry["submissionDigest"]:
        raise ValueError(f"{entry['attemptId']}: the submission changed during review")
    report = {
        "attemptId": entry["attemptId"],
        "task": entry["task"],
        "submissionDigest": entry["submissionDigest"],
        "submissionSha256": seal,
        "artifactIdentity": artifact,
        **scan,
        "decision": decision,
        "reviewedAt": _now(),
    }
    target = kit / "attempts" / entry["attemptId"] / REPORT
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _balatro_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in manifest["attempts"] if str(entry["task"]).startswith("balatro/")]


def _sealed(report: dict[str, Any], entry: dict[str, Any], artifact: str | None = None) -> bool:
    """Whether the report seals this submission, on the given artifact when one is named."""
    return (
        report.get("decision") == SEALED
        and report.get("submissionDigest") == entry["submissionDigest"]
        and (artifact is None or report.get("artifactIdentity") == artifact)
    )


def review_kit(
    kit: Path, manifest: dict[str, Any], operator: Operator, artifact: str
) -> list[dict[str, Any]]:
    """Review every Balatro attempt of a kit on the artifact with identity ``artifact``.

    An attempt already sealed by the policy on that artifact is kept, and so is one that
    has a result. An unevaluated attempt sealed on another artifact, such as the one a halt
    replaced, is reviewed again, since its seal does not exist on this one.
    """
    reports = []
    for entry in _balatro_entries(manifest):
        folder = kit / "attempts" / entry["attemptId"]
        previous = folder / REPORT
        if previous.is_file():
            report = json.loads(previous.read_text(encoding="utf-8"))
            evaluated = any((folder / name).exists() for name in RESULTS)
            if _sealed(report, entry, None if evaluated else artifact):
                reports.append(report)
                continue
        reports.append(review_attempt(kit, entry, operator, artifact))
    return reports


def evaluate_sealed(
    kit: Path, manifest: dict[str, Any], evaluator: Evaluator, artifact: str
) -> list[dict[str, Any]]:
    """Evaluate each attempt sealed on ``artifact`` once, one at a time, in manifest order.

    An attempt with a result is skipped, and nothing is ever retried: an incomplete run
    halts the runtime artifact, so the batch stops there for the operator to diagnose.
    """
    runs = []
    for entry in _balatro_entries(manifest):
        folder = kit / "attempts" / entry["attemptId"]
        report_path = folder / REPORT
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not _sealed(report, entry, artifact):
            continue
        if any((folder / name).exists() for name in RESULTS):
            continue
        output = evaluator(str(entry["task"]), kit / entry["submission"])
        (folder / "result-1.json").write_text(json.dumps(output, ensure_ascii=False) + "\n", encoding="utf-8")
        raw = output.get("result")
        result: dict[str, Any] = raw if isinstance(raw, dict) else {}
        complete = result.get("complete") is True
        runs.append(
            {
                "attemptId": entry["attemptId"],
                "complete": complete,
                "passed": bool(result.get("passed")) if complete else None,
            }
        )
        if not complete:
            break
    return runs
