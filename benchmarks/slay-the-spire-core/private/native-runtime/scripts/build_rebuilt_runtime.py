"""Build the reproduced licensed runtime locally; never push it to a registry."""

import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", type=Path, required=True)
args = parser.parse_args()
workspace = args.workspace.resolve()
receipt = json.loads((workspace / "sdk-build-receipt.json").read_text())


def image_id(ref: str) -> str:
    return subprocess.check_output(
        ["docker", "image", "inspect", ref, "--format", "{{.Id}}"], text=True
    ).strip()


assert image_id(receipt["tools_image"]) == receipt["tools_image"], "Tools image is unavailable"
tag = "codex-sts-reproduced-base:dev"
log_path = workspace / "build-logs/reproduced-runtime.log"
with (workspace / "rebuilt-runtime-context.tar").open("rb") as context, log_path.open("w") as log:
    subprocess.run(
        ["docker", "build", "--network=none", "--memory=512m", "--memory-swap=512m", "-t", tag, "-"],
        stdin=context,
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
    )
identifier = image_id(tag)
(workspace / "reproduced-runtime-image-id.txt").write_text(identifier + "\n")
print(identifier, flush=True)
