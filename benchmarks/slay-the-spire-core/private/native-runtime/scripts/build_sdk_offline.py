"""Rebuild the three SDK jars using pinned source archives and reconstructed Maven cache.

Run on Linux/WSL. All licensed artifacts stay in the explicitly supplied private workspace.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--maven-cache", type=Path, required=True)
parser.add_argument("--game-jar", type=Path, required=True)
parser.add_argument("--tools-image", required=True)
args = parser.parse_args()
assert os.name == "posix", "Run this container preparation step in Linux or WSL"
tools_image_id = subprocess.check_output(
    ["docker", "image", "inspect", args.tools_image, "--format", "{{.Id}}"], text=True
).strip()
assert tools_image_id.startswith("sha256:")
workspace = args.workspace.resolve()
lib = workspace / "lib"
logs = workspace / "build-logs"
lib.mkdir(exist_ok=True)
logs.mkdir(exist_ok=True)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


game_hash = "cfad868ac8d65a88e71a0bf096fb09f78811e553effe0787c5309a655e081673"
assert sha(args.game_jar) == game_hash, "Game build differs from the validated input"
game_copy = lib / "desktop-1.0.jar"
if game_copy.exists():
    assert sha(game_copy) == game_hash
else:
    shutil.copyfile(args.game_jar, game_copy)
steps = [
    ("ModTheSpire", "target/ModTheSpire.jar", []),
    ("BaseMod", "mod/target/BaseMod.jar", ["-pl", "mod", "-am"]),
    ("StSLib", "target/StSLib.jar", []),
]
script = """set -euo pipefail
name=$1; output=$2; shift 2
mkdir /build
tar -xf "/inputs/$name.tar.gz" -C /build
cd "/build/$name"
mvn -B -o clean test package "$@" > "/output/$name.log" 2>&1
cp "$output" "/opt/sts/lib/$name.jar"
"""
for name, jar, extra in steps:
    print("OFFLINE BUILD", name, flush=True)
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory=1024m",
            "--memory-swap=1024m",
            "-e",
            "MAVEN_OPTS=-Xmx512m",
            "-v",
            str(workspace / "archives") + ":/inputs:ro",
            "-v",
            str(lib) + ":/opt/sts/lib",
            "-v",
            str(logs) + ":/output",
            "-v",
            str(args.maven_cache.resolve()) + ":/root/.m2",
            tools_image_id,
            "bash",
            "-c",
            script,
            "_",
            name,
            jar,
            *extra,
        ],
        check=True,
    )
receipt = {
    "restricted_local_only": True,
    "tools_image": tools_image_id,
    "sources": json.loads((workspace / "source-lock.json").read_text()),
    "artifacts": {path.name: sha(path) for path in sorted(lib.glob("*.jar"))},
}
(workspace / "sdk-build-receipt.json").write_text(json.dumps(receipt, indent=2))
print("SDK REBUILD COMPLETE", flush=True)
