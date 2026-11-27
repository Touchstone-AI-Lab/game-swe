from __future__ import annotations

import json
from importlib.resources import files


def render_test_script(case_ids: tuple[str, ...]) -> str:
    if not case_ids or len(set(case_ids)) != len(case_ids) or any(not value for value in case_ids):
        raise ValueError("trusted Stardew runner requires unique nonempty case IDs")
    template = files("rhenium_authoring").joinpath("assets/stardew-test.sh.in").read_text()
    return template.replace("__EXPECTED_COUNT__", str(len(case_ids))).replace(
        "__EXPECTED_NAMES__", json.dumps(case_ids, ensure_ascii=True),
    )
