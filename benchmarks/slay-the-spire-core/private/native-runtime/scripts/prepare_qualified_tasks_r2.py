"""Rebuild execution copies of frozen qualified tasks on a locally reconstructed runtime."""

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--tasks", type=Path, required=True)
parser.add_argument("--prepared-dir", type=Path, required=True)
parser.add_argument("--runtime-map", type=Path, help="Optional old-verifier-image to reconstructed-image map")
args = parser.parse_args()
workspace = args.workspace.resolve()
source = args.tasks.resolve()
destination = args.prepared_dir.resolve()
assert not destination.exists(), "Use a fresh preparation directory"
runtime = (workspace / "reproduced-runtime-image-id.txt").read_text().strip()
assert (
    runtime
    == subprocess.check_output(
        ["docker", "image", "inspect", runtime, "--format", "{{.Id}}"], text=True
    ).strip()
)
runtime_map = {"sha256:233e1d8f96e8368fa753bdcb6730de724f482e865beb2241a05b412fcfe6c350": runtime}
if args.runtime_map:
    extra = json.loads(args.runtime_map.read_text())
    assert isinstance(extra, dict) and not set(extra).intersection(runtime_map)
    runtime_map.update(extra)
for identifier in runtime_map.values():
    assert (
        identifier
        == subprocess.check_output(
            ["docker", "image", "inspect", identifier, "--format", "{{.Id}}"], text=True
        ).strip()
    )
original = {
    p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in source.rglob("*")
    if p.is_file()
}
assert original and not any(p.is_symlink() for p in source.rglob("*"))
shutil.copytree(source, destination)
logs = workspace / "build-logs"
logs.mkdir(exist_ok=True)
rows = []
for task in sorted(destination.iterdir()):
    if not (task / "task.toml").is_file():
        continue
    config = tomllib.loads((task / "task.toml").read_text())
    old_runtime = config["verifier"]["environment"]["docker_image"]
    assert old_runtime in runtime_map, "Missing reconstructed runtime for " + task.name
    parent_runtime = runtime_map[old_runtime]
    recipe = task / "environment/Dockerfile"
    text = recipe.read_text()
    assert text.splitlines()[0] == "FROM " + old_runtime
    recipe.write_text(text.replace("FROM " + old_runtime, "FROM " + parent_runtime, 1))
    context = io.BytesIO()
    with tarfile.open(fileobj=context, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for file in sorted((task / "environment").rglob("*")):
            if file.is_file():
                data = file.read_bytes()
                entry = tarfile.TarInfo(file.relative_to(task / "environment").as_posix())
                entry.size, entry.mode, entry.mtime = len(data), 0o644, 1700000000
                archive.addfile(entry, io.BytesIO(data))
    tag = "codex-qualified-" + task.name + ":local"
    with (logs / (task.name + ".log")).open("w") as log:
        subprocess.run(
            ["docker", "build", "--network=none", "--memory=1536m", "--memory-swap=1536m", "-t", tag, "-"],
            input=context.getvalue(),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    image = subprocess.check_output(
        ["docker", "image", "inspect", tag, "--format", "{{.Id}}"], text=True
    ).strip()
    text = (task / "task.toml").read_text()
    for section, identifier in [("environment", image), ("verifier.environment", parent_runtime)]:
        pattern = r"(\[" + re.escape(section) + r'\]\s*\ndocker_image = )"[^"]+"'
        def replace_image(match: re.Match[str], value: str = identifier) -> str:
            return match[1] + '"' + value + '"'

        text, count = re.subn(pattern, replace_image, text, count=1)
        assert count == 1, section
    (task / "task.toml").write_text(text)
    for file in task.rglob("*"):
        if not file.is_file() or file.relative_to(task).as_posix() in ["environment/Dockerfile", "task.toml"]:
            continue
        key = file.relative_to(destination).as_posix()
        assert hashlib.sha256(file.read_bytes()).hexdigest() == original[key], key
    rows.append(
        {"task": task.name, "path": str(task), "agent_image": image, "verifier_image": parent_runtime}
    )
    print(json.dumps(rows[-1]), flush=True)
assert rows
assert original == {
    p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in source.rglob("*")
    if p.is_file()
}
(workspace / "qualified-task-images.json").write_text(json.dumps(rows, indent=2))
