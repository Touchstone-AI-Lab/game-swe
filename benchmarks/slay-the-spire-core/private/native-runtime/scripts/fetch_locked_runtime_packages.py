"""Download the exact runtime package closure, verifying apt-signed index hashes.

No system package installation is performed. Output may be placed on another disk.
"""

import argparse
import concurrent.futures
import hashlib
import json
import re
import shlex
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--lock-dir", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
snapshot = json.loads((args.lock_dir / "runtime-package-lock.json").read_text())["snapshot_utc"]
if not isinstance(snapshot, str) or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", snapshot):
    raise ValueError("Expected a fixed Ubuntu snapshot timestamp")
args.output.mkdir(parents=True, exist_ok=True)


def checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(line: str) -> dict[str, str | int]:
    url, filename, size, hash_spec = shlex.split(line)
    algorithm, expected = hash_spec.lower().split(":", 1)
    assert algorithm in {"sha256", "sha512"}, algorithm
    assert Path(filename).name == filename and filename.endswith(".deb"), filename
    parsed = urllib.parse.urlsplit(url)
    assert parsed.hostname in {"archive.ubuntu.com", "security.ubuntu.com"}, parsed.hostname
    assert parsed.path.startswith("/ubuntu/pool/") and not parsed.query and not parsed.fragment
    # The live archive removes superseded .debs. Keep the original signed-index
    # hashes, but fetch the same bytes from the immutable historical archive.
    url = f"https://snapshot.ubuntu.com/ubuntu/{snapshot}/" + parsed.path.removeprefix("/ubuntu/")
    target = args.output / filename
    valid = target.exists() and target.stat().st_size == int(size) and checksum(target, algorithm) == expected
    if not valid:
        temporary = target.with_suffix(".deb.part")
        with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as destination:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                destination.write(chunk)
        assert temporary.stat().st_size == int(size), filename
        assert checksum(temporary, algorithm) == expected, filename
        temporary.replace(target)
    print("VERIFIED", filename, flush=True)
    return {
        "filename": filename,
        "url": url,
        "bytes": int(size),
        algorithm: expected,
        "sha256": checksum(target, "sha256"),
    }


lines = [line for line in (args.lock_dir / "package-uris.txt").read_text().splitlines() if line.strip()]
filenames = [shlex.split(line)[1] for line in lines]
if len(set(filenames)) != len(filenames):
    raise ValueError("Package lock contains duplicate output filenames")
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    receipt = list(executor.map(fetch, lines))
(args.output / "packages-receipt.json").write_text(json.dumps(receipt, indent=2))
print("Verified package bytes:", sum(int(item["bytes"]) for item in receipt), flush=True)
