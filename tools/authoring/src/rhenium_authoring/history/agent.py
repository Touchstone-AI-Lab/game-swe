"""A bounded, read-only repository agent on top of the structured model client.

Each turn the model returns one JSON action: inspect the checked-out trees
(``list_dir``, ``read_file``, ``grep``), read the upstream fix (``show_fix``,
only for roles allowed to see it) or ``finish`` with the role's final object.
Tools never execute code, never reach the network and never leave the trees
they were given. Old observations are elided so the transcript stays bounded,
and an optional check turns a rejected answer into one more observation.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from ..model_client import ModelClient
from ..models import StrictModel

_TEXT_SUFFIXES = frozenset(
    {
        ".java",
        ".yml",
        ".yaml",
        ".xml",
        ".gradle",
        ".kts",
        ".properties",
        ".md",
        ".json",
        ".txt",
        ".toml",
        ".conf",
        ".cfg",
        ".sql",
        ".lang",
        ".html",
    }
)
MAX_READ_LINES = 250
MAX_OBSERVATION = 16_000
MAX_GREP_MATCHES = 60
KEEP_RECENT_OBSERVATIONS = 8


class AgentStep(StrictModel):
    tool: Literal["list_dir", "read_file", "grep", "show_fix", "finish"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    note: str = Field(default="", max_length=2000)


_NATIVE_NAME = re.compile(r"invoke\s+name=\"([a-z_]+)\"")
_NATIVE_PARAMETER = re.compile(
    r"parameter\s+name=\"([A-Za-z_]+)\"(?:\s+string=\"(true|false)\")?\s*>(.*?)</[^>]*parameter>", re.DOTALL
)


def native_tool_call(content: str) -> str | None:
    """Translate an endpoint's native tool-call markup into an ``AgentStep`` JSON.

    Some thinking endpoints answer with their own ``<...invoke name="tool">``
    markup instead of (or after) the requested JSON, sometimes mixing the two.
    The first invocation is taken. Well-formed parameters become arguments (an
    ``arguments`` parameter holds a JSON object); otherwise the first complete
    JSON object after the tool name is the arguments.
    """
    match = _NATIVE_NAME.search(content)
    if match is None:
        return None
    rest = content[match.end() :]
    arguments: dict[str, Any] = {}
    for name, is_string, raw in _NATIVE_PARAMETER.findall(rest):
        value: Any = raw.strip()
        if is_string != "true":
            with contextlib.suppress(ValueError):
                value = json.loads(value)
        if name == "arguments" and isinstance(value, dict):
            arguments.update(value)
        else:
            arguments[name] = value
    if not arguments:
        decoder = json.JSONDecoder()
        for index, character in enumerate(rest):
            if character != "{":
                continue
            try:
                value, _end = decoder.raw_decode(rest, index)
            except ValueError:
                continue
            if isinstance(value, dict):
                arguments = value
                break
    return json.dumps({"tool": match.group(1), "arguments": arguments})


class AgentExhausted(RuntimeError):
    """The role used its whole turn budget without an accepted answer."""


class RepositoryTools:
    """Read-only views of named trees (for example ``base`` and ``reference``)."""

    def __init__(self, trees: dict[str, Path], fix_patch: str | None = None):
        self.trees = {name: path.resolve() for name, path in trees.items()}
        self.fix_patch = fix_patch

    def describe(self) -> list[dict[str, str]]:
        names = ", ".join(sorted(self.trees))
        tools = [
            {"tool": "list_dir", "arguments": f'{{"tree": one of {names}, "path": "relative/dir" or ""}}'},
            {
                "tool": "read_file",
                "arguments": (
                    f'{{"tree": ..., "path": "relative/file", "start": 1, "lines": <= {MAX_READ_LINES}}}'
                ),
            },
            {
                "tool": "grep",
                "arguments": '{"tree": ..., "pattern": "Python regular expression", "path": "optional dir"}',
            },
        ]
        if self.fix_patch is not None:
            tools.append({"tool": "show_fix", "arguments": "{} - the landed upstream fix as a unified diff"})
        tools.append({"tool": "finish", "arguments": "the final object, exactly matching final_schema"})
        return tools

    def _resolve(self, arguments: dict[str, Any], *, directory: bool) -> tuple[Path, Path]:
        tree_name = str(arguments.get("tree") or next(iter(self.trees)))
        if tree_name not in self.trees:
            raise ValueError(f"unknown tree {tree_name!r}; use one of {sorted(self.trees)}")
        root = self.trees[tree_name]
        raw = str(arguments.get("path") or "").strip().lstrip("/")
        relative = PurePosixPath(raw) if raw else PurePosixPath(".")
        if ".." in relative.parts:
            raise ValueError("paths must stay inside the tree")
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or target.is_symlink():
            raise ValueError("paths must stay inside the tree")
        if directory and not target.is_dir():
            raise ValueError(f"{raw or '.'} is not a directory")
        if not directory and not target.is_file():
            raise ValueError(f"{raw} is not a file")
        return root, target

    def call(self, step: AgentStep) -> str:
        try:
            if step.tool == "list_dir":
                return self._list(step.arguments)
            if step.tool == "read_file":
                return self._read(step.arguments)
            if step.tool == "grep":
                return self._grep(step.arguments)
            if step.tool == "show_fix":
                if self.fix_patch is None:
                    return "error: show_fix is not available to this role"
                return _clip(self.fix_patch)
        except (ValueError, re.error, OSError) as error:
            return f"error: {error}"
        return "error: unknown tool"

    def _list(self, arguments: dict[str, Any]) -> str:
        root, target = self._resolve(arguments, directory=True)
        entries = []
        for child in sorted(target.iterdir())[:400]:
            if child.is_symlink():
                continue
            entries.append(child.name + ("/" if child.is_dir() else ""))
        prefix = target.relative_to(root).as_posix()
        return f"{prefix}:\n" + "\n".join(entries)

    def _read(self, arguments: dict[str, Any]) -> str:
        root, target = self._resolve(arguments, directory=False)
        start = max(int(arguments.get("start") or 1), 1)
        count = min(max(int(arguments.get("lines") or MAX_READ_LINES), 1), MAX_READ_LINES)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        window = lines[start - 1 : start - 1 + count]
        body = "\n".join(f"{start + index:5d}  {line}" for index, line in enumerate(window))
        return _clip(f"{target.relative_to(root).as_posix()} ({len(lines)} lines)\n{body}")

    def _grep(self, arguments: dict[str, Any]) -> str:
        root, target = self._resolve(arguments, directory=True)
        pattern = re.compile(str(arguments.get("pattern") or ""))
        matches: list[str] = []
        for path in sorted(target.rglob("*")):
            if path.is_symlink() or not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
                continue
            if path.stat().st_size > 1_000_000:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line):
                    matches.append(f"{path.relative_to(root).as_posix()}:{number}: {line.strip()[:200]}")
                    if len(matches) >= MAX_GREP_MATCHES:
                        return "\n".join(matches) + "\n(more matches omitted; narrow the pattern)"
        return "\n".join(matches) or "no matches"


def _clip(text: str) -> str:
    if len(text) <= MAX_OBSERVATION:
        return text
    return text[:MAX_OBSERVATION] + "\n(truncated; read a narrower window)"


def _elide(history: list[dict[str, str]]) -> None:
    """Replace old observations and old large answers with short placeholders.

    The most recent observations stay verbatim, and so do the two most recent
    large answers (a rejected ``finish`` the model is about to correct).
    """
    observations = [index for index, turn in enumerate(history) if turn["role"] == "user"]
    for index in observations[:-KEEP_RECENT_OBSERVATIONS]:
        if not history[index]["content"].startswith("(elided"):
            history[index] = {"role": "user", "content": "(elided earlier observation; re-read if needed)"}
    large = [
        index
        for index, turn in enumerate(history)
        if turn["role"] == "assistant" and len(turn["content"]) > 4000
    ]
    for index in large[:-2]:
        history[index] = {
            "role": "assistant",
            "content": '{"tool": "note", "note": "(elided earlier answer)"}',
        }


def run_agent[T: BaseModel](
    client: ModelClient,
    output: type[T],
    *,
    role: str,
    brief: dict[str, object],
    tools: RepositoryTools,
    max_turns: int = 30,
    check: Callable[[T], list[str]] | None = None,
    transcript: Path | None = None,
) -> T:
    """Drive one role to an accepted final object or raise ``AgentExhausted``."""
    payload: dict[str, object] = {
        **brief,
        "protocol": {
            "instructions": (
                "Work in turns. Each answer is one JSON object {tool, arguments, note}. Inspect the "
                "repository with the tools until you understand the behaviour, then answer with tool "
                "finish whose arguments are the final object. Keep notes short. Paths are relative to "
                "the tree root. Observations older than the last few are elided; re-read when needed."
            ),
            "tools": tools.describe(),
            "turn_budget": max_turns,
            "final_schema": output.model_json_schema(),
        },
    }
    history: list[dict[str, str]] = []
    # The last turns are kept for answering: a rejected finish comes back as an
    # observation and needs turns left to be corrected.
    reserve = max(3, max_turns // 5)
    closed = False
    for turn in range(1, max_turns + 1):
        if turn == max_turns:
            history.append({"role": "user", "content": "Turn budget exhausted: answer now with tool finish."})
        elif turn == max_turns - reserve + 1 and not any(
            '"tool":"finish"' in item["content"].replace(" ", "")
            for item in history
            if item["role"] == "assistant"
        ):
            history.append(
                {
                    "role": "user",
                    "content": f"Only {reserve} turns are left. Stop exploring and answer with tool "
                    "finish now; a rejected answer is returned to you for correction.",
                }
            )
        if turn >= max_turns - reserve + 1:
            # Tools stop executing in the reserve; only answers (and their corrections) count.
            closed = True
        step = client.complete(
            AgentStep,
            role=role,
            payload=payload,
            history=history,
            pipeline="project-history",
            salvage=native_tool_call,
        )
        history.append({"role": "assistant", "content": step.model_dump_json()})
        if step.tool == "finish":
            try:
                final = output.model_validate(step.arguments)
            except ValidationError as error:
                problems = [
                    f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors()[:12]
                ]
                observation = "finish rejected by the schema: " + "; ".join(problems)
            else:
                problems = check(final) if check is not None else []
                if not problems:
                    _save(transcript, history)
                    return final
                observation = "finish rejected: " + "\n".join(problems)[:MAX_OBSERVATION]
        elif closed:
            observation = "Exploration is closed: answer with tool finish now."
        else:
            observation = tools.call(step)
        history.append({"role": "user", "content": observation})
        _elide(history)
        _save(transcript, history)
    raise AgentExhausted(f"{role} used its {max_turns}-turn budget without an accepted answer")


def _save(path: Path | None, history: list[dict[str, str]]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    path.chmod(0o600)
