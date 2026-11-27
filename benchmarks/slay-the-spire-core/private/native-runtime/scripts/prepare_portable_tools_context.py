"""Create an offline tools-image context from checksum-verified Ubuntu packages."""

import argparse
import hashlib
import json
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--packages", type=Path, required=True)
parser.add_argument("--archive", type=Path, required=True)
parser.add_argument("--lock-dir", type=Path)
args = parser.parse_args()
work = Path(__file__).resolve().parents[1]
lock_dir = args.lock_dir or work / "deps/portable"
receipt = json.loads((args.packages / "packages-receipt.json").read_text())
assert len(receipt) == len((lock_dir / "package-closure.txt").read_text().splitlines())
hashes = []
with tarfile.open(args.archive, "w:gz", format=tarfile.GNU_FORMAT) as archive:
    for name in ["Dockerfile", "runtime-packages.tsv"]:
        archive.add(lock_dir / name, arcname=name)
    for item in receipt:
        path = args.packages / item["filename"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], path
        hashes.append(f"{item['sha256']}  {item['filename']}\n")
        archive.add(path, arcname="packages/" + item["filename"])
    checksum_path = args.packages / "packages.sha256"
    checksum_path.write_text("".join(hashes), newline="\n")
    archive.add(checksum_path, arcname="packages/packages.sha256")
print(args.archive)
