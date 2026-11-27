"""User-approved once-per-task remainder, reusing the unchanged full wrapper runner."""
from __future__ import annotations

import argparse
from pathlib import Path

import native_matrix_v1 as original
import native_matrix_v2 as wrapper
from rhenium_balatro.bridge import load_binding
from rhenium_balatro.native_assets import file_sha, json_write_new, verified_assets
from rhenium_balatro.review import record_review


def remaining(keys: list[str]) -> list[tuple[str, str, int]]:
    if len(keys) != 10 or len(set(keys)) != 10 or "growth-v2" not in keys:
        raise ValueError("expected frozen ten-task catalog")
    return [(key, role, 1) for key in keys if key != "growth-v2" for role in ("gold", "base")]


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    for name in ("repository", "state", "evidence", "attempts", "powershell"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    repo = args.repository.resolve()
    state = args.state.resolve() / "packs/balatro/core"
    binding = load_binding(state)
    assets = verified_assets(repo / "benchmarks/balatro", binding["assets_sha256"])
    plan = remaining(list(assets["tasks"]))
    reviews = {}
    for role in ("gold", "base"):
        selected = assets["controls"]["durable-charge-v2"][role]
        record_review(state, assets, binding["assets_sha256"], "durable-charge-v2",
                      selected["seal_sha256"], selected["candidate_sha256"], selected["seal_sha256"])
        reviews[role] = file_sha(state / "reviews" / f"durable-charge-v2-{selected['seal_sha256']}.json")
    json_write_new(args.evidence.parent / "scope-v3.json", {
        "schema_version": 3, "scope": "remaining-nine-task-gold-base-once",
        "flows": plan, "driver_sha256": file_sha(Path(__file__)),
        "adapter_sha256": binding["adapter_sha256"], "durable_explicit_reviews": reviews,
        "initial_growth_evidence_separate": True, "required_cases_unchanged": True,
    })
    prior = original.matrix

    def scoped(kind: str, keys: list[str]) -> list[tuple[str, str, int]]:
        if kind != "controls" or remaining(keys) != plan:
            raise ValueError("unexpected scope")
        return plan

    args.matrix = "controls"
    original.matrix = scoped
    try:
        wrapper.run(args)
    finally:
        original.matrix = prior


if __name__ == "__main__":
    main()
