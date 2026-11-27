#!/usr/bin/env python3
"""Run one deterministic maintainer control using an already prepared runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from candidates import materialize


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    paths = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    for item in paths:
        name = item.relative_to(path).as_posix() if path.is_dir() else item.name
        checksum.update(name.encode() + b"\0" + item.read_bytes() + b"\0")
    return checksum.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--runtime", default="gcb-l4d2-sourcemod-verifier:23990100-sm1.12.7246")
    args = parser.parse_args()
    task = Path(__file__).resolve().parents[1]
    output_root = args.output_root.resolve()
    if output_root.is_relative_to(task):
        raise ValueError("generated control state must be outside the benchmark task")
    run = output_root / f"{task.name}-{args.candidate}-{time.time_ns()}"
    run.mkdir(parents=True)
    source, tests = run / "source", run / "tests"
    materialize(task, args.candidate, source)
    shutil.copytree(task / "tests", tests)
    components = {name: digest(task / name) for name in (
        "instruction.md", "task.toml", "environment", "tests", "solution", "validation/case-contracts.tsv",
    )}
    contract = hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest()
    image = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", args.runtime], text=True,
    ).strip()
    command = [
        "docker", "create", "--pull=never", "--network=none", "--entrypoint", "bash",
        "--mount", f"type=bind,source={source},target=/app/linge-hud,readonly",
        "--mount", f"type=bind,source={tests},target=/tests,readonly",
        image, "-c", "mkdir -p /logs/verifier && chmod 700 /logs /logs/verifier && python3 -u /tests/verify.py",
    ]
    container = subprocess.check_output(command, text=True).strip()
    try:
        result = subprocess.run(
            ["docker", "start", "-a", container], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=240,
        )
        output = result.stdout + result.stderr
        (run / "verifier.log").write_text(output, encoding="utf-8")
        subprocess.run(["docker", "cp", f"{container}:/logs/verifier", str(run / "logs")],
                       check=True, capture_output=True)
        cases = [{"case": name, "status": status, "detail": detail} for status, name, detail in
                 re.findall(r"^(PASS|FAIL) ([^:]+): (.*)$", output, re.MULTILINE)]
        receipt = {
            "task": task.name, "candidate": args.candidate, "exit_code": result.returncode,
            "contract": contract, "component_hashes": components, "runtime_image_id": image,
            "source_hash": digest(source), "tests_hash": digest(tests), "cases": cases,
            "passed": sum(case["status"] == "PASS" for case in cases), "total": len(cases),
            "verifier_log_sha256": hashlib.sha256((run / "verifier.log").read_bytes()).hexdigest(),
            "server_log_sha256": hashlib.sha256((run / "logs/server.log").read_bytes()).hexdigest()
                if (run / "logs/server.log").exists() else None,
        }
        (run / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(output)
        print(f"CONTROL {args.candidate}: {receipt['passed']}/{receipt['total']}, exit={result.returncode}, evidence={run}")
        return result.returncode
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=True, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
