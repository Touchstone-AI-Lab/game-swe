"""Validate the distributable, fully offline OS recipe without touching task images."""

import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("--evidence-dir", type=Path)
args = parser.parse_args()
work = Path(__file__).resolve().parents[1]
evidence = args.evidence_dir or work / "evidence/build"
evidence.mkdir(parents=True, exist_ok=True)
with args.archive.open("rb") as context, (evidence / "portable-tools.log").open("w") as log:
    subprocess.run(
        [
            "docker",
            "build",
            "--network=none",
            "--memory=512m",
            "--memory-swap=512m",
            "-t",
            "codex-sts-portable-tools:dev",
            "-",
        ],
        stdin=context,
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
    )
image_id = subprocess.check_output(
    ["docker", "image", "inspect", "codex-sts-portable-tools:dev", "--format", "{{.Id}}"], text=True
).strip()
(evidence / "portable-tools-image-id.txt").write_text(image_id + "\n")
print(image_id, flush=True)
