from __future__ import annotations

import shlex
from importlib.resources import files

# Case names become Java string literals in @GcbCase("...") and JSON strings in
# task.json; quotes and backslashes would need escaping in both, so they are
# rejected instead of escaped differently per consumer.
_FORBIDDEN_CHARACTERS = frozenset('"\\')


def validate_case_ids(case_ids: tuple[str, ...]) -> None:
    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("trusted Minecraft runner requires unique nonempty case IDs")
    if any(not value.strip() or value != value.strip() or not value.isprintable() for value in case_ids):
        raise ValueError("trusted Minecraft runner requires printable single-line trimmed case IDs")
    if any(_FORBIDDEN_CHARACTERS.intersection(value) for value in case_ids):
        raise ValueError("trusted Minecraft runner rejects case IDs containing quotes or backslashes")


def render_test_script(case_ids: tuple[str, ...]) -> str:
    """Render the trusted shell runner for one synthetic Minecraft task.

    The flow is the reviewed minecraft-core harness runner: only the expected case
    names vary, and they are shell-quoted so a generated name can never become
    shell syntax. The runner cross-checks the frozen tests/task.json against these
    names before delegating to the trusted verify.py in the verifier image.
    """
    validate_case_ids(case_ids)
    template = files("rhenium_authoring").joinpath("assets/minecraft-test.sh.in").read_text()
    names = "\n".join(f"  {shlex.quote(value)}" for value in case_ids)
    return template.replace("__EXPECTED_COUNT__", str(len(case_ids))).replace("__EXPECTED_NAMES__", names)
