"""Reconstruct the exact public Maven cache from a checksum lock; no installation."""

import argparse
import concurrent.futures
import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TypedDict

parser = argparse.ArgumentParser()
parser.add_argument("--lock", type=Path, required=True)
parser.add_argument("--repository", type=Path, required=True)
parser.add_argument("--cache", type=Path, help="Reusable checksum-verified public artifacts")
args = parser.parse_args()
lock = json.loads(args.lock.read_text())
assert lock["repository_ids"] == ["central"]
args.repository.mkdir(parents=True, exist_ok=True)


class Artifact(TypedDict):
    path: str
    sha256: str
    bytes: int
    repository_ids: list[str]


def verified(path: Path, item: Artifact) -> bool:
    return (
        path.is_file() and path.stat().st_size == item["bytes"]
        and hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    )


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".maven-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def download(url: str) -> bytes:
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code < 500 and error.code != 429:
                raise
            if attempt == 5:
                raise
            time.sleep(min(2 ** attempt, 8))
    raise AssertionError("unreachable download attempt")


def fetch(item: Artifact) -> None:
    relative = Path(item["path"])
    assert not relative.is_absolute() and ".." not in relative.parts
    target = args.repository / relative
    if verified(target, item):
        return
    cached = args.cache / relative if args.cache is not None else None
    if cached is not None and verified(cached, item):
        content = cached.read_bytes()
    else:
        url = "https://repo.maven.apache.org/maven2/" + urllib.parse.quote(item["path"], safe="/")
        content = download(url)
    assert len(content) == item["bytes"], relative
    assert hashlib.sha256(content).hexdigest() == item["sha256"], relative
    atomic_write(target, content)
    if cached is not None:
        atomic_write(cached, content)


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    list(executor.map(fetch, lock["artifacts"]))
tracking: dict[Path, list[str]] = {}
for item in lock["artifacts"]:
    relative = Path(item["path"])
    tracking.setdefault(relative.parent, []).extend(
        relative.name + ">" + repo + "=\n" for repo in item["repository_ids"]
    )
for parent, lines in tracking.items():
    (args.repository / parent / "_remote.repositories").write_text("".join(sorted(lines)), newline="\n")
for item in lock.get("metadata", []):
    content = item["content"].encode()
    assert hashlib.sha256(content).hexdigest() == item["sha256"], item["path"]
    path = args.repository / item["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
print(
    json.dumps(
        {
            "verified_artifacts": len(lock["artifacts"]),
            "metadata_files": len(lock.get("metadata", [])),
            "repository": str(args.repository),
        }
    )
)
