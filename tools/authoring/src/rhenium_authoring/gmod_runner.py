from __future__ import annotations

import shlex
from importlib.resources import files


def render_test_script(case_ids: tuple[str, ...]) -> str:
    """Render the trusted GLuaTest shell runner for one synthetic Garry's Mod task.

    The flow is the reviewed DarkRP runner: only the expected case names vary, and
    they are shell-quoted so a generated name can never become shell syntax.
    """
    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("trusted Garry's Mod runner requires unique nonempty case IDs")
    if any(not value.strip() or not value.isprintable() for value in case_ids):
        raise ValueError("trusted Garry's Mod runner requires printable single-line case IDs")
    template = files("rhenium_authoring").joinpath("assets/gmod-test.sh.in").read_text()
    names = "\n".join(f"  {shlex.quote(value)}" for value in case_ids)
    return template.replace("__EXPECTED_COUNT__", str(len(case_ids))).replace("__EXPECTED_NAMES__", names)
