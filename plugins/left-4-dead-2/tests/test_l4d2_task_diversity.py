"""Detect exact renamed-task duplication; semantic independence also needs review."""
from __future__ import annotations

import hashlib
from pathlib import Path

from rhenium_left_4_dead_2.catalog import Left4Dead2Catalog

PACK = Path(__file__).parents[3] / "benchmarks/l4d2-core"


def _content(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def test_tasks_have_distinct_production_repairs_and_behavior_suites() -> None:
    repairs_seen: dict[tuple[str, ...], str] = {}
    suites_seen: dict[tuple[str, ...], str] = {}
    for task in Left4Dead2Catalog.load(PACK).tasks:
        root = PACK / "private/harbor" / task.id
        after = root / "solution/after"
        if (after / task.starter_name).is_dir():
            after /= task.starter_name
        repaired = []
        for path in after.rglob("*"):
            if path.suffix not in {".sp", ".inc", ".nut"}:
                continue
            original = root / "environment" / task.starter_name / path.relative_to(after)
            # References must repair supplied mod code, not an unprovided sidecar.
            assert original.is_file(), (task.id, path)
            if _content(path) != _content(original):
                repaired.append(hashlib.sha256(_content(path)).hexdigest())
        # Ignore filenames: renaming an identical oracle into another mod folder
        # must not turn it into an independent task.
        repair_key = tuple(sorted(repaired))
        assert repair_key, task.id
        assert repair_key not in repairs_seen, (task.id, repairs_seen.get(repair_key))
        repairs_seen[repair_key] = task.id

        suites = [path for path in (root / "tests").glob("suite*") if path.suffix in {".sp", ".nut"}]
        # The Mutant Tanks reward fixture supplements its main production suite.
        suites += list((root / "tests").glob("*_suite.sp"))
        suite_key = tuple(sorted(hashlib.sha256(_content(path)).hexdigest() for path in suites))
        assert suite_key, task.id
        assert suite_key not in suites_seen, (task.id, suites_seen.get(suite_key))
        suites_seen[suite_key] = task.id
