from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = "MINDUSTRY_RESULT "
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java", required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--map", default="Fortress")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--rubric", type=Path, required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="mindustry-benchmark-") as raw_root:
        root = Path(raw_root)
        mods = root / "config" / "mods"
        mods.mkdir(parents=True)
        shutil.copy2(args.candidate, mods / "candidate.jar")
        shutil.copy2(args.tests, mods / "test-runner.jar")
        try:
            completed = subprocess.run(
                [args.java, "-jar", str(args.server.resolve())],
                cwd=root,
                input=f"host {args.map}\n",
                capture_output=True,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            log = completed.stdout + completed.stderr
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout or ""
            stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr or ""
            print(stdout + stderr, file=sys.stderr)
            print(json.dumps({"passed": False, "error": "server-timeout"}))
            return 1

    clean = ANSI.sub("", log)
    payloads = [
        line.split(MARKER, 1)[1].strip()
        for line in clean.splitlines()
        if MARKER in line
    ]
    if len(payloads) != 1:
        print(clean, file=sys.stderr)
        print(json.dumps({"passed": False, "error": "invalid-result-count", "count": len(payloads)}))
        return 1
    try:
        result = json.loads(payloads[0])
    except json.JSONDecodeError:
        print(clean, file=sys.stderr)
        print(json.dumps({"passed": False, "error": "malformed-result"}))
        return 1
    rubric_data = json.loads(args.rubric.read_text(encoding="utf-8"))
    rubric = {item["name"]: item for item in rubric_data["cases"]}
    if sum(int(item["maximum"]) for item in rubric.values()) != 70:
        print(json.dumps({"passed": False, "error": "invalid-rubric-total"}))
        return 1
    runtime_score = 0
    seen: set[str] = set()
    for case in result.get("cases", []):
        name = case.get("name")
        item = rubric.get(name)
        if item is None or name in seen:
            print(json.dumps({"passed": False, "error": "unmapped-case", "case": name}))
            return 1
        seen.add(name)
        case["category"] = item["category"]
        case["maximum"] = int(item["maximum"])
        case["score"] = int(item["maximum"]) if case.get("passed") is True else 0
        runtime_score += int(case["score"])
    missing = sorted(set(rubric) - seen)
    if missing:
        print(json.dumps({"passed": False, "error": "missing-cases", "cases": missing}))
        return 1
    result["runtime_score"] = runtime_score
    result["runtime_maximum"] = 70
    result["total_score"] = 30 + runtime_score
    result["total_maximum"] = 100
    result["complete"] = True
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if isinstance(result, dict) and result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
