"""Validate frozen inputs, then prepare disposable native Harbor execution copies."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def validate_inputs(runtime: Path) -> list[dict[str, str]]:
    """Check recipes and measured task bytes before downloading or building anything."""
    pack = runtime.parents[1]
    metadata = pack / "validation/native-engine"
    recipe = json.loads((runtime / "recipe-manifest.json").read_text())
    for name, digest in recipe["files"].items():
        if hashlib.sha256((runtime / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Runtime recipe changed: {name}")
    tasks: list[dict[str, str]] = json.loads((metadata / "tasks.json").read_text())
    for row in tasks:
        source = pack / "private/harbor" / row["id"]
        manifest = json.loads((metadata / row["id"] / "frozen-manifest.json").read_text())
        actual = {
            path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source.rglob("*") if path.is_file()
        }
        if actual != manifest["files"] or any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError(f"Frozen task changed: {row['id']}; materialize Git LFS files before preparing")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime-map", type=Path, help="Additional locally rebuilt runtime image map")
    args = parser.parse_args()
    runtime = Path(__file__).resolve().parent
    pack = runtime.parents[1]
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Use a fresh output directory")
    tasks = validate_inputs(runtime)
    extra_args: list[str] = []
    if args.runtime_map is not None:
        extra_args = ["--runtime-map", str(args.runtime_map.resolve())]
    elif any(row["id"].startswith("downfall-") for row in tasks):
        raise ValueError("Prepare the Downfall resource layer and supply --runtime-map")
    canonical = output / "canonical"
    canonical.mkdir(parents=True)
    for row in tasks:
        shutil.copytree(pack / "private/harbor" / row["id"], canonical / row["id"])
    subprocess.run(
        [sys.executable, str(runtime / "scripts/prepare_qualified_tasks_r2.py"),
         "--workspace", str(args.runtime_workspace.resolve()),
         "--tasks", str(canonical), "--prepared-dir", str(output / "prepared"), *extra_args],
        check=True,
    )


if __name__ == "__main__":
    main()
