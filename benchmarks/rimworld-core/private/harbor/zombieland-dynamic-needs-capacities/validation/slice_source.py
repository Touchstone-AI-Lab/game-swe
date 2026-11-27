"""Reproduce the reviewed source slice from a local, exact upstream Patches.cs.

No network, dependency resolution, compilation or in-pack output. Usage:
  python slice_source.py base /isolated/upstream/Source/Patches.cs /tmp/Patches.cs
The input SHA-256 must match the pinned upstream, not an edited candidate.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def derive(raw: bytes, variant: str) -> bytes:
    manifest = json.loads(Path(__file__).with_name("source-derivation.json").read_text())
    expected = manifest["variants"][variant]
    if hashlib.sha256(raw).hexdigest() != expected["upstreamSha256"]:
        raise ValueError("upstream source hash mismatch")
    text = raw.decode("utf-8-sig", errors="strict")
    blocks = []
    for start, end in manifest["ranges"]:
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError("ambiguous source slice boundary")
        blocks.append(text[text.index(start):text.index(end, text.index(start))])
    if [hashlib.sha256(block.encode()).hexdigest() for block in blocks] != expected["blockSha256"]:
        raise ValueError("production block hash mismatch")
    output = (manifest["header"] + "".join(blocks) + "    }\n}\n").encode()
    if hashlib.sha256(output).hexdigest() != expected["derivedSha256"]:
        raise ValueError("derived source hash mismatch")
    return output


if __name__ == "__main__":
    variant, source, destination = sys.argv[1:]
    output = Path(destination).resolve()
    pack = Path(__file__).resolve().parents[4]
    if output.is_relative_to(pack):
        raise ValueError("generated output must be outside the benchmark pack")
    data = derive(Path(source).read_bytes(), variant)
    with output.open("xb") as stream:
        stream.write(data)
