#!/usr/bin/env python3
"""Validate and freeze the L4D2 Harbor task contracts."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    ROOT / "benchmarks/l4d2-core/private/harbor/l4d2-competitive-release-regressions-easy",
    ROOT / "benchmarks/l4d2-core/private/harbor/l4d2-left4dhooks-api-regressions-medium",
    ROOT / "benchmarks/l4d2-core/private/harbor/l4d2-linge-release-regressions-hard-v3",
    ROOT / "benchmarks/l4d2-core/private/harbor/l4d2-infected-bots-release-regressions-medium",
    ROOT / "benchmarks/l4d2-core/private/harbor/l4d2-mutant-tanks-release-regressions-hard",
)


def canonical_payload(path: Path) -> bytes:
    """Return checkout-stable bytes while preserving non-UTF-8 assets verbatim."""
    payload = path.read_bytes()
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return payload.replace(b"\r\n", b"\n")


def digest_file(path: Path) -> str:
    return hashlib.sha256(canonical_payload(path)).hexdigest()


def is_generated_or_vcs(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return (
        any(part in {"__pycache__", ".git"} for part in relative.parts)
        or path.suffix.lower() in {".pyc", ".pyo"}
    )


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    files = (
        item
        for item in root.rglob("*")
        if item.is_file() and not is_generated_or_vcs(item, root)
    )
    for path in sorted(
        files,
        key=lambda item: item.relative_to(root).as_posix().encode("utf-8"),
    ):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        payload = canonical_payload(path)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def expected_count(task_text: str) -> int:
    for key in ("expected_private_cases", "expected_server_cases"):
        match = re.search(rf"^{key}\s*=\s*(\d+)\s*$", task_text, re.MULTILINE)
        if match:
            return int(match.group(1))
    raise ValueError("task metadata has no expected case count")


def freeze(task: Path) -> None:
    contracts = task / "validation/case-contracts.tsv"
    if not contracts.is_file():
        raise ValueError(f"{task.name}: missing validation/case-contracts.tsv")
    with contracts.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    names = [row["case"] for row in rows]
    if len(names) != len(set(names)):
        raise ValueError(f"{task.name}: duplicate case contract")
    task_text = (task / "task.toml").read_text(encoding="utf-8")
    count = expected_count(task_text)
    if len(names) != count:
        raise ValueError(f"{task.name}: metadata expects {count}, contract has {len(names)}")
    test_sources = (
        path
        for path in (task / "tests").rglob("*")
        if path.is_file()
        and not is_generated_or_vcs(path, task / "tests")
        and path.suffix.lower() in {".py", ".sp", ".nut"}
    )
    tests_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(
            test_sources,
            key=lambda item: item.relative_to(task / "tests")
            .as_posix()
            .encode("utf-8"),
        )
    )
    missing = [name for name in names if name not in tests_text]
    if missing:
        raise ValueError(f"{task.name}: contracted cases absent from tests: {missing}")

    component_hashes = {
        "instruction_sha256": digest_file(task / "instruction.md"),
        "task_sha256": digest_file(task / "task.toml"),
        "tests_tree_sha256": digest_tree(task / "tests"),
        "environment_tree_sha256": digest_tree(task / "environment"),
        "solution_tree_sha256": digest_tree(task / "solution"),
        "case_contracts_sha256": digest_file(contracts),
        "case_count": str(count),
    }
    aggregate = hashlib.sha256()
    for key, value in component_hashes.items():
        aggregate.update(f"{key}\t{value}\n".encode())
    component_hashes["aggregate_contract_sha256"] = aggregate.hexdigest()
    output = task / "validation/contract-hashes.tsv"
    output.write_text(
        "component\tvalue\n"
        + "".join(f"{key}\t{value}\n" for key, value in component_hashes.items()),
        encoding="utf-8",
        newline="\n",
    )
    print(f"{task.name}: {count} cases; {component_hashes['aggregate_contract_sha256']}")


def main() -> int:
    for task in TASKS:
        freeze(task)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
