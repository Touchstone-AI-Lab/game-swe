"""Rebuild a local Downfall resource layer on the operator's reconstructed SDK."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--foundation", type=Path, required=True,
        help="Directory with receipt.json and runtime-context/resources.tar",
    )
    parser.add_argument(
        "--workspace", type=Path, required=True,
        help="Previously reconstructed private SDK/runtime workspace",
    )
    args = parser.parse_args()
    foundation, workspace = args.foundation.resolve(), args.workspace.resolve()
    record = json.loads((foundation / "receipt.json").read_text())
    resources = foundation / "runtime-context/resources.tar"
    digest = hashlib.sha256()
    with resources.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    assert digest.hexdigest() == record["files"]["runtime-context/resources.tar"]
    observed: dict[str, str] = {}
    with tarfile.open(resources) as archive:
        for entry in archive:
            assert entry.isfile() and not entry.issym() and not entry.islnk()
            assert entry.name not in observed
            member = archive.extractfile(entry)
            assert member is not None
            observed[entry.name] = hashlib.sha256(member.read()).hexdigest()
    assert observed == record["resource_files"]
    base = (workspace / "reproduced-runtime-image-id.txt").read_text().strip()
    assert subprocess.check_output(
        ["docker", "image", "inspect", base, "--format", "{{.Id}}"], text=True
    ).strip() == base
    recipe = f"""FROM {base}
ADD resources.tar /opt/sts/downfall-resources/
RUN test ! -e /opt/sts/lib/Downfall.jar
WORKDIR /app/downfall
""".encode()
    logs = workspace / "build-logs"
    logs.mkdir(exist_ok=True)
    logpath = logs / "reproduced-downfall-foundation.log"
    assert not logpath.exists()
    tag = "codex-sts-reproduced-downfall:dev"
    with logpath.open("w") as log, subprocess.Popen(
        ["docker", "build", "--network=none", "--memory=768m", "--memory-swap=768m", "-t", tag, "-"],
        stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
    ) as child:
        assert child.stdin is not None
        with tarfile.open(fileobj=child.stdin, mode="w|", format=tarfile.GNU_FORMAT) as context:
            entry = tarfile.TarInfo("Dockerfile")
            entry.size, entry.mode, entry.mtime = len(recipe), 0o644, 1700000000
            context.addfile(entry, io.BytesIO(recipe))
            context.add(resources, arcname="resources.tar", recursive=False)
        child.stdin.close()
        assert child.wait() == 0
    image = subprocess.check_output(
        ["docker", "image", "inspect", tag, "--format", "{{.Id}}"], text=True
    ).strip()
    runtime_map = {
        "sha256:9f737c92646e7d4735f81a69af53b1e5a0fe2e225c4f13b758232de6e511b750": image,
    }
    output = workspace / "additional-runtime-map.json"
    assert not output.exists()
    output.write_text(json.dumps(runtime_map, indent=2))
    receipt = {
        "image": image, "base": base, "public_resources_sha256": digest.hexdigest(),
        "resource_entries": len(observed), "runtime_map": runtime_map,
    }
    (workspace / "downfall-foundation-reproduction.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
