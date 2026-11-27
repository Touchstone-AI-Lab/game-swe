#!/usr/bin/env python3
"""Harbor verifier for one Garry's Mod Addons generation task.

This is a thin wrapper, not a second evaluator: it runs the repository's own
``rhenium_garrys_mod`` Addons evaluator (vendored byte-for-byte into the verifier
runtime image) at the ``full`` profile against the pinned native Linux Dedicated
Server. The Harbor reward is therefore exactly the Rhenium full-profile verdict:
1 only when every level, every server group and every declared phase ran to
completion and the submission passed.

Everything fails closed. A missing or mismatched server, an incomplete run, an
evaluator crash, or malformed output all yield reward 0.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# The native runner hard-links server files into its per-phase views, so its
# state has to live on the same filesystem as the server installation.
STATE_ROOT = Path("/opt/gmod/state")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _evaluate(submission: Path, pack: Path) -> dict[str, Any]:
    from rhenium_garrys_mod.addons.catalog import GmodCatalog
    from rhenium_garrys_mod.addons.evaluator import GmodEvaluator

    from rhenium.core.plugin import BenchmarkContext

    catalog = GmodCatalog.load(pack, "catalog.json")
    if len(catalog.tasks) != 1:
        raise ValueError("a Harbor verifier pack must describe exactly one task")
    context = BenchmarkContext(
        project_root=pack,
        pack_root=pack,
        state_dir=STATE_ROOT / "pack",
        cache_dir=STATE_ROOT / "cache",
    )
    evaluator = GmodEvaluator(context, catalog)
    status = evaluator.runtime_status()
    if not status.get("available"):
        raise RuntimeError("the pinned Dedicated Server is unavailable in this image")
    result = evaluator.evaluate(submission, catalog.tasks[0], profile="full")
    if not isinstance(result, dict):
        raise TypeError("evaluator returned a non-object result")
    return result


def _public_summary(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("checks")
    summary_checks = []
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict):
                summary_checks.append(
                    {
                        "id": check.get("id"),
                        "status": check.get("status"),
                        "score": check.get("score"),
                        "maximum": check.get("maximum"),
                    }
                )
    evidence = result.get("evidence")
    return {
        "score": result.get("score"),
        "complete": result.get("complete"),
        "passed": result.get("passed"),
        "real_gmod_server_ran": result.get("complete") is True,
        "server_build": evidence.get("serverBuild") if isinstance(evidence, dict) else None,
        "checks": summary_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    args = parser.parse_args()

    reward = 0
    try:
        result = _evaluate(args.submission, args.pack)
        summary = _public_summary(result)
        if result.get("complete") is True and result.get("passed") is True:
            reward = 1
    except Exception:  # noqa: BLE001 - every failure must fail closed with reward 0
        summary = {
            "score": 0.0,
            "complete": False,
            "passed": False,
            "real_gmod_server_ran": False,
            "error": traceback.format_exc(limit=4),
        }

    summary["reward"] = reward
    _write(args.logs / "result.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    _write(args.logs / "reward.txt", f"{reward}\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if reward == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
