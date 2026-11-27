"""Prepare the nine admitted real-game tasks from pinned tools and a licensed game JAR."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# Importing the sibling helper must not create state under the benchmark pack.
sys.dont_write_bytecode = True
from prepare_tasks import validate_inputs  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def preflight(runtime: Path, game: Path, output: Path) -> list[dict[str, str]]:
    if sys.version_info < (3, 12) or platform.system() != "Linux":
        raise ValueError("Run with Python 3.12+ on Linux or WSL")
    if output.exists():
        raise FileExistsError("Use a fresh output directory; previous logs are preserved")
    if output.is_relative_to(runtime.parents[3]):
        raise ValueError("The output directory must be outside the repository")
    expected = read_json(runtime / "game-input.json")["expected_sha256"]["desktop-1.0.jar"]
    with game.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError("Game JAR differs from game-input.json; supply the pinned licensed build")
    return validate_inputs(runtime)


def pull_tools(runtime: Path) -> tuple[str, str]:
    lock = read_json(runtime / "public-tools-image.json")
    reference = lock["image"]
    if not re.fullmatch(r"ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", reference):
        raise ValueError("The public tools image must use a complete GHCR reference pinned by digest")
    if lock["platform"] != "linux/amd64":
        raise ValueError("Only the measured linux/amd64 runtime is supported")
    subprocess.run(["docker", "pull", "--platform", lock["platform"], reference], check=True)
    details = json.loads(subprocess.check_output(["docker", "image", "inspect", reference], text=True))[0]
    if reference not in details.get("RepoDigests", []):
        raise ValueError("Docker did not report the pinned repository digest")
    if (details["Os"], details["Architecture"]) != ("linux", "amd64"):
        raise ValueError("Unexpected tools image platform")
    # The classic image store reports the configuration digest as the image ID; the containerd
    # image store reports the manifest digest pinned in the reference, which content-addresses
    # that configuration. Any other ID is a different image.
    if details["Id"] not in {lock["image_id"], reference.rsplit("@", 1)[1]}:
        raise ValueError("Unexpected tools image configuration digest")
    return reference, details["Id"]


def prepare(runtime: Path, game: Path, output: Path, *, build_tools: bool = False) -> Path:
    game, output = game.resolve(), output.resolve()
    tasks = preflight(runtime, game, output)
    info = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"], text=True))
    if info["OSType"] != "linux" or info["Architecture"] not in {"x86_64", "amd64"}:
        raise ValueError("Use a Linux x86-64 Docker engine")
    output.mkdir(parents=True)
    scripts, lock = runtime / "scripts", runtime / "deps/portable"
    workspace, maven = output / "runtime", output / "maven"

    def run(name: str, *arguments: str | Path) -> None:
        print(f"PREPARE {name}", flush=True)
        subprocess.run([sys.executable, str(scripts / name), *map(str, arguments)], check=True)

    if build_tools:
        run("fetch_locked_runtime_packages.py", "--lock-dir", lock, "--output", output / "packages")
        run("prepare_portable_tools_context.py", "--lock-dir", lock, "--packages", output / "packages",
            "--archive", output / "tools.tar.gz")
        run("build_portable_tools.py", output / "tools.tar.gz", "--evidence-dir", output / "build-logs")
        tools_id = (output / "build-logs/portable-tools-image-id.txt").read_text().strip()
        tools_source = "locally-built-from-locked-recipe"
    else:
        tools_source, tools_id = pull_tools(runtime)
    run("fetch_locked_maven.py", "--lock", lock / "maven-artifacts.json",
        "--repository", maven / "repository", "--cache", output.parent / "public-maven-cache")
    run("prepare_sdk_sources.py", "--lock", lock / "source-lock.json", "--workspace", workspace)
    run("build_sdk_offline.py", "--workspace", workspace, "--maven-cache", maven,
        "--game-jar", game, "--tools-image", tools_id)
    run("prepare_rebuilt_base_context.py", "--workspace", workspace, "--maven-cache", maven)
    run("build_rebuilt_runtime.py", "--workspace", workspace)
    foundation = output / "downfall-foundation"
    run("fetch_downfall_resources.py", "--recipe", runtime / "deps/downfall-foundation",
        "--output", foundation)
    run("rebuild_downfall_foundation.py", "--foundation", foundation, "--workspace", workspace)
    subprocess.run([
        sys.executable, str(runtime / "prepare_tasks.py"), "--runtime-workspace", str(workspace),
        "--output", str(output / "task-copies"),
        "--runtime-map", str(workspace / "additional-runtime-map.json"),
    ], check=True)
    images = read_json(workspace / "qualified-task-images.json")
    if sorted(row["task"] for row in images) != sorted(row["id"] for row in tasks):
        raise ValueError("Preparation did not produce every frozen native task")
    receipt = {
        "restricted_local_only": True,
        "public_tools_source": tools_source,
        "tools_image_id": tools_id,
        "recipe_manifest_sha256": hashlib.sha256((runtime / "recipe-manifest.json").read_bytes()).hexdigest(),
        "game_sha256": read_json(workspace / "sdk-build-receipt.json")["artifacts"]["desktop-1.0.jar"],
        "tasks": images,
    }
    (output / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    prepared = output / "task-copies/prepared"
    print(f"READY: {len(images)} native tasks in {prepared}", flush=True)
    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-jar", type=Path, required=True, help="Your pinned licensed desktop-1.0.jar")
    parser.add_argument("--output", type=Path, required=True, help="Fresh private directory outside the repo")
    parser.add_argument("--build-tools", action="store_true", help="Build the locked tools recipe locally")
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parent, args.game_jar, args.output, build_tools=args.build_tools)


if __name__ == "__main__":
    main()
