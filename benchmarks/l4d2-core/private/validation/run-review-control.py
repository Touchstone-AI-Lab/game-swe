"""Run an authored maintenance control against an existing offline L4D2 image.

Never use this entry point for model attempts. It creates fresh evidence and
does not modify previous attempts or install/update a game runtime.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    files = sorted(path.rglob("*"), key=lambda p: p.relative_to(path).as_posix()) if path.is_dir() else [path]
    for item in files:
        if item.is_file():
            name = item.relative_to(path).as_posix() if path.is_dir() else item.name
            checksum.update(name.encode() + b"\0" + item.read_bytes() + b"\0")
    return checksum.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task")
    parser.add_argument("candidate")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--runtime", default="gcb-l4d2-sourcemod-verifier:23990100-sm1.12.7246")
    parser.add_argument("--group", help="Optional focused diagnostic, never a full pass")
    args = parser.parse_args()
    pack = Path(__file__).resolve().parents[2]
    catalog = json.loads((pack / "catalog.json").read_text(encoding="utf-8"))
    entry = next(t for t in catalog["tasks"] if t["id"] == args.task)
    task = pack / "private/harbor" / args.task
    root = args.output_root.resolve()
    if root.is_relative_to(pack):
        parser.error("generated evidence must be outside the entire benchmark pack")
    run = root / f"{args.task}-{args.candidate}-{time.time_ns()}"
    run.mkdir(parents=True)
    source = run / "source" / entry["starter_name"]
    builder = task / "validation/build-review-controls.py"
    if builder.is_file():
        subprocess.run([sys.executable, str(builder), args.candidate, str(run / "source")], check=True)
    else:
        spec = importlib.util.spec_from_file_location("control_candidate", task / "validation/candidates.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.materialize(task, args.candidate, source)
    tests = run / "tests"
    shutil.copytree(task / "tests", tests)
    components = {
        name: digest(task / name)
        for name in (
            "instruction.md",
            "task.toml",
            "environment",
            "tests",
            "solution",
            "validation/case-contracts.tsv",
        )
    }
    image = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", args.runtime], text=True
    ).strip()
    volume = None
    if os.name == "nt":
        # Docker Desktop bind mounts make thousands of compiler/stat operations
        # expensive. Copy the frozen inputs once into a dedicated Linux volume;
        # the actual verifier still receives both source and tests read-only.
        volume = "gcb-review-" + uuid.uuid4().hex
        subprocess.run(["docker", "volume", "create", volume], check=True, capture_output=True)
        helper = subprocess.check_output(
            [
                "docker",
                "create",
                "--pull=never",
                "--network=none",
                "--entrypoint",
                "sleep",
                "--mount",
                f"type=volume,source={volume},target=/payload",
                image,
                "infinity",
            ],
            text=True,
        ).strip()
        try:
            subprocess.run(
                ["docker", "cp", str(source), f"{helper}:/payload/source"], check=True, capture_output=True
            )
            subprocess.run(
                ["docker", "cp", str(tests), f"{helper}:/payload/tests"], check=True, capture_output=True
            )
        except BaseException:
            subprocess.run(["docker", "rm", "-f", helper], check=True, capture_output=True)
            subprocess.run(["docker", "volume", "rm", volume], check=True, capture_output=True)
            raise
        else:
            subprocess.run(["docker", "rm", "-f", helper], check=True, capture_output=True)
        source_mount = (
            f"type=volume,source={volume},volume-subpath=source,"
            f"target={entry['container_destination']},readonly"
        )
        tests_mount = f"type=volume,source={volume},volume-subpath=tests,target=/tests,readonly"
    else:
        source_mount = f"type=bind,source={source},target={entry['container_destination']},readonly"
        tests_mount = f"type=bind,source={tests},target=/tests,readonly"
    command = [
        "docker",
        "create",
        "--pull=never",
        "--network=none",
        "--cpus=4",
        "--memory=6g",
        "--entrypoint",
        "bash",
        "--mount",
        source_mount,
        "--mount",
        tests_mount,
    ]
    if args.group:
        command.extend(["-e", f"GCB_ONLY_GROUP={args.group}"])
    command.extend(
        [
            image,
            "-c",
            "mkdir -p /logs/verifier && chmod 700 /logs /logs/verifier && python3 -u /tests/verify.py",
        ]
    )
    container = None
    try:
        container = subprocess.check_output(command, text=True).strip()
        timed_out = False
        try:
            result = subprocess.run(
                ["docker", "start", "-a", container],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3000,
            )
        except subprocess.TimeoutExpired as error:
            timed_out = True

            def decoded(value: str | bytes | None) -> str:
                return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""

            result = subprocess.CompletedProcess(error.cmd, 124, decoded(error.stdout), decoded(error.stderr))
        output = result.stdout + result.stderr
        (run / "verifier.log").write_text(output, encoding="utf-8")
        copied = subprocess.run(
            ["docker", "cp", f"{container}:/logs/verifier", str(run / "logs")], capture_output=True
        )
        cases = [
            {"case": name, "status": status, "detail": detail}
            for status, name, detail in re.findall(r"^(PASS|FAIL) ([^:]+): (.*)$", output, re.MULTILINE)
        ]
        with (task / "validation/case-contracts.tsv").open(encoding="utf-8", newline="") as stream:
            expected = {row["case"] for row in csv.DictReader(stream, delimiter="\t")}
        observed = [case["case"] for case in cases]
        complete = (
            not args.group
            and not timed_out
            and len(observed) == len(expected)
            and set(observed) == expected
            and result.returncode in (0, 1)
        )
        receipt = {
            "task": args.task,
            "candidate": args.candidate,
            "profile": "focused" if args.group else "full",
            "expected_full_cases": len(expected),
            "complete_full_case_set": complete,
            "timed_out": timed_out,
            "group": args.group,
            "exit_code": result.returncode,
            "component_hashes": components,
            "hash_algorithm": "sha256-relpath-nul-content-nul-posix-lexical-v1",
            "contract": hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest(),
            "runtime_image_id": image,
            "source_hash": digest(source),
            "tests_hash": digest(tests),
            "input_transport": "readonly-linux-volume" if volume else "readonly-bind",
            "cases": cases,
            "passed": sum(c["status"] == "PASS" for c in cases),
            "total": len(cases),
            "verifier_log_sha256": hashlib.sha256((run / "verifier.log").read_bytes()).hexdigest(),
            "logs_copied": copied.returncode == 0,
            "server_log_hashes": {
                p.relative_to(run / "logs").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((run / "logs").rglob("server*.log"))
            },
        }
        (run / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(
            f"CONTROL {args.task} {args.candidate}: {receipt['passed']}/{receipt['total']}, "
            f"exit={result.returncode}, evidence={run}"
        )
        for case in cases:
            if case["status"] == "FAIL":
                print(f"FAIL {case['case']}: {case['detail']}")
        if not cases:
            print(output[-6000:])
        # A zero exit alone must never certify an incomplete full run.
        if not args.group and not complete:
            return 2
        return result.returncode
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], check=True, capture_output=True)
        if volume:
            subprocess.run(["docker", "volume", "rm", volume], check=True, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
