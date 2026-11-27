#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "GameCodeBench.SourceProjection.csproj"
REQUIRED = (
    ROOT / "LICENSE",
    ROOT / "Content" / "Items" / "SpaceWand.Shapes.cs",
    ROOT / "Content" / "Items" / "SpaceWand.Operations.cs",
    ROOT / "Content" / "Packets" / "SpaceWandOperation.cs",
    PROJECT,
)


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.is_file()]
    if missing:
        print("missing required source: " + ", ".join(missing), file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="improvegame-space-wand-projection-") as output:
        completed = subprocess.run(
            [
                "dotnet",
                "build",
                str(PROJECT),
                "-c",
                "Release",
                "--nologo",
                "--ignore-failed-sources",
                f"-p:BaseOutputPath={output}/bin/",
                f"-p:BaseIntermediateOutputPath={output}/obj/",
            ],
            cwd=ROOT,
            check=False,
        )
    if completed.returncode != 0:
        return completed.returncode

    print("Quality of Terraria Space Wand source projection compiled successfully.")
    print("No behavioral assertions are included in this public check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
