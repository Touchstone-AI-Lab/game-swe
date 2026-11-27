"""Reproduce the pinned public Downfall resource archive directly from Git blobs."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--existing-repo", type=Path)
    args = parser.parse_args()
    recipe = args.recipe.resolve()
    output = args.output.resolve()
    assert not output.exists(), "Use a fresh output directory"
    lock = json.loads((recipe / "source-lock.json").read_text())
    receipt_path = recipe / "receipt.json"
    assert sha256(receipt_path) == lock["foundation_receipt_sha256"]
    receipt = json.loads(receipt_path.read_text())
    assert lock["commit"] == receipt["commit"]
    descriptor = (recipe / "ModTheSpire.json").read_bytes()
    assert hashlib.sha256(descriptor).hexdigest() == receipt["resource_files"]["ModTheSpire.json"]
    output.mkdir(parents=True)
    source = args.existing_repo.resolve() if args.existing_repo else output / "source.git"
    if args.existing_repo:
        assert source.is_dir()
    else:
        subprocess.run(["git", "init", "--bare", str(source)], check=True)
        subprocess.run(
            ["git", "-C", str(source), "fetch", "--depth=1", lock["url"], lock["commit"]], check=True
        )
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", lock["commit"] + "^{commit}"], text=True
    ).strip()
    assert commit == lock["commit"]
    context = output / "runtime-context"
    context.mkdir()
    partial = context / "resources.partial.tar"
    total = 0
    with subprocess.Popen(
        ["git", "-C", str(source), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as child:
        assert child.stdin is not None and child.stdout is not None
        with tarfile.open(partial, "w", format=tarfile.GNU_FORMAT) as archive:
            for name, expected in receipt["resource_files"].items():
                relative = PurePosixPath(name)
                assert not relative.is_absolute() and ".." not in relative.parts
                assert "\n" not in name and "\r" not in name and "\\" not in name
                assert relative.suffix.lower() not in {
                    ".class",
                    ".jar",
                    ".exe",
                    ".dll",
                    ".so",
                    ".env",
                    ".lnk",
                }
                if name == "ModTheSpire.json":
                    data = descriptor
                else:
                    child.stdin.write((commit + ":src/main/resources/" + name + "\n").encode())
                    child.stdin.flush()
                    header = child.stdout.readline().split()
                    assert len(header) == 3 and header[1] == b"blob", name
                    size = int(header[2])
                    data = child.stdout.read(size)
                    assert len(data) == size and child.stdout.read(1) == b"\n"
                transform = lock.get("resource_transforms", {}).get(name)
                if transform:
                    assert transform["kind"] == "checkout-crlf"
                    assert hashlib.sha256(data).hexdigest() == transform["git_blob_sha256"], name
                    data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                assert hashlib.sha256(data).hexdigest() == expected, name
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode, entry.mtime = len(data), 0o644, 1700000000
                archive.addfile(entry, io.BytesIO(data))
                total += 1
        child.stdin.close()
        assert child.wait() == 0
    digest = sha256(partial)
    assert digest == receipt["files"]["runtime-context/resources.tar"]
    partial.rename(context / "resources.tar")
    shutil.copyfile(receipt_path, output / "receipt.json")
    (output / "reconstruction.json").write_text(
        json.dumps(
            {
                "validated": True,
                "commit": commit,
                "resource_files": total,
                "archive_sha256": digest,
                "source": "Pinned Git objects; no working-tree filters or generated binaries",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"validated": True, "resource_files": total, "archive_sha256": digest}))


if __name__ == "__main__":
    main()
