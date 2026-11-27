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
    ROOT / "Common" / "IO" / "BitBuffer128.cs",
    ROOT / "Common" / "IO" / "LengthCompressor.cs",
    ROOT / "Common" / "IO" / "StringCompressor.cs",
    ROOT / "Common" / "IO" / "ValueReader.cs",
    ROOT / "Common" / "IO" / "ValueWriter.cs",
    ROOT / "Common" / "IO" / "NetCompression.NetIO.cs",
    PROJECT,
)


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.is_file()]
    if missing:
        print("missing required source: " + ", ".join(missing), file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="magic-storage-projection-") as output:
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

    print("Magic Storage production source projection compiled successfully.")
    print("No behavioral assertions are included in this public check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
