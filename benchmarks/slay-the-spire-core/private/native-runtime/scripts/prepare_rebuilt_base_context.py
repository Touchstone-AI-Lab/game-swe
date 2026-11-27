"""Create a local-only runtime context from rebuilt SDKs and locked public cache."""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--maven-cache", type=Path, required=True)
args = parser.parse_args()
workspace = args.workspace.resolve()
receipt = json.loads((workspace / "sdk-build-receipt.json").read_text())
tools_image = receipt["tools_image"]
assert re.fullmatch(r"sha256:[0-9a-f]{64}", tools_image), "Expected an immutable local tools image ID"
context = workspace / "runtime-context"
context.mkdir(exist_ok=True)
with tarfile.open(context / "dependencies.tar", "w", format=tarfile.GNU_FORMAT) as archive:
    for name in ["desktop-1.0.jar", "ModTheSpire.jar", "BaseMod.jar", "StSLib.jar"]:
        path = workspace / "lib" / name
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        assert digest.hexdigest() == receipt["artifacts"][name], name
        archive.add(path, arcname=name)
resources = workspace / "sources/PackmasterCharacter/src/main/resources"
with tarfile.open(context / "resources.tar", "w", format=tarfile.GNU_FORMAT) as archive:
    for path in sorted(resources.rglob("*")):
        if path.is_file():
            assert not path.is_symlink() and path.suffix.lower() not in {".java", ".class", ".jar"}, path
            archive.add(path, arcname=path.relative_to(resources).as_posix())
repository = args.maven_cache.resolve() / "repository"
assert not any("packmaster" in path.name.lower() for path in repository.rglob("*"))
with tarfile.open(context / "maven-cache.tar", "w", format=tarfile.GNU_FORMAT) as archive:
    archive.add(repository, arcname=".m2/repository")
(context / "runtime-inputs.json").write_text(json.dumps(receipt, indent=2))
dockerfile = f"""# LOCAL ONLY: contains the user's licensed game. Never push this image.
FROM {tools_image}
ADD dependencies.tar /opt/sts/lib/
ADD resources.tar /opt/sts/packmaster-resources/
ADD maven-cache.tar /root/
COPY runtime-inputs.json /opt/sts/provenance/runtime-inputs.json
RUN test ! -e /opt/sts/lib/ThePackmaster.jar
WORKDIR /app/packmaster
"""
(context / "Dockerfile").write_text(dockerfile, newline="\n")
with tarfile.open(workspace / "rebuilt-runtime-context.tar", "w", format=tarfile.GNU_FORMAT) as archive:
    for path in sorted(context.iterdir()):
        archive.add(path, arcname=path.name)
print(workspace / "rebuilt-runtime-context.tar")
