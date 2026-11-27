"""Explicit reuse of a provider cache with complete original acquisition proof.

Failed requests remain failed and immutable. This never launches a client or
reissues a command; it selects a different, fully proven prior source acquisition.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from . import official_console as console

NAME = "official-console-cache-reuse-v1.json"


def bounded_cache(path: Path) -> Path:
    root = Path(os.environ.get("RHENIUM_STATE_DIR", "")) / "cache/providers/steam"
    if not root.is_absolute() or path.parent != root or not re.fullmatch(r"[a-f0-9]{64}", path.name):
        raise ValueError("Reuse is limited to selected provider-owned source caches")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked cache path")
    return path


def read(path: Path) -> Any:
    if any(p.is_symlink() for p in (path, *path.parents)) or path.stat().st_size > 65536:
        raise ValueError("Unsafe cache proof")
    return json.loads(path.read_text())


def proof(profile: console.Profile, source: dict[str, Any], cache: Path) -> dict[str, Any]:
    bounded_cache(cache)
    console.source_identity(source)
    if console.fingerprint(source) != profile.data["allowed_source_sha256"]:
        raise ValueError("Source is outside the approved profile")
    request = read(cache / "official-console-request-v1.json")
    receipt = read(cache / "official-console-source-v1.json")
    _, expected = console.completed_attempt(profile, source, request)
    if any(receipt.get(k) != value for k, value in expected.items()):
        raise ValueError("Prior source provenance changed")
    files = console.verify_files(cache, source)
    if receipt.get("files") != files:
        raise ValueError("Prior cache file proof differs")
    return expected


def terminal_pending(profile: console.Profile, source: dict[str, Any], cache: Path) -> dict[str, str]:
    path = cache / "official-console-request-v1.json"
    if not path.exists():
        return {}
    pending = read(path)
    attempt = str(pending.get("attempt", ""))
    if not re.fullmatch(r"[a-f0-9]{32}", attempt) or pending != {
        "attempt": attempt,
        "source": source,
        "sourceSha256": console.fingerprint(source),
        "profileId": profile.identifier,
    }:
        raise ValueError("Pending source identity differs")
    shutdown_path = profile.root / "attempts" / attempt / "shutdown.json"
    shutdown = read(shutdown_path)
    if type(shutdown.get("exitCode")) is not int or type(shutdown.get("forced")) is not bool:
        raise ValueError("Pending client has no terminal exit evidence")
    return {"pendingSha256": console.sha(path), "shutdownSha256": console.sha(shutdown_path)}


def verify(profile: console.Profile, source: dict[str, Any], destination: Path) -> None:
    bounded_cache(destination)
    value = read(destination / NAME)
    if value.get("schema") != 1 or value.get("profileSha256") != profile.digest:
        raise ValueError("Cache reuse profile/version mismatch")
    prior = Path(value["priorCache"])
    if prior == destination or value.get("priorProof") != proof(profile, source, prior):
        raise ValueError("Cache reuse provenance mismatch")
    if value.get("preservedPending") != terminal_pending(profile, source, destination):
        raise ValueError("Preserved pending evidence changed")
    if console.sha(prior / "official-console-source-v1.json") != value["priorReceiptSha256"]:
        raise ValueError("Prior receipt changed")
    if console.verify_files(destination, source) != value["files"]:
        raise ValueError("Reused bytes changed")


def create(profile: console.Profile, prior: Path, destination: Path) -> None:
    bounded_cache(destination)
    if (
        prior == destination
        or (destination / NAME).exists()
        or (destination / "official-console-source-v1.json").exists()
    ):
        raise ValueError("Refuse to overwrite source evidence")
    source = read(bounded_cache(prior) / "official-console-request-v1.json")["source"]
    prior_proof = proof(profile, source, prior)
    preserved = terminal_pending(profile, source, destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in source["expectedFiles"]:
        target = destination / console.relative_path(name)
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError("Linked destination file")
        if target.exists():
            if target.is_symlink() or console.sha(target) != source["sha256"][name]:
                raise ValueError("Partial source differs; preserve it")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with (prior / name).open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst)
    console.write_new(
        destination / NAME,
        {
            "schema": 1,
            "profileSha256": profile.digest,
            "priorCache": str(prior),
            "priorProof": prior_proof,
            "priorReceiptSha256": console.sha(prior / "official-console-source-v1.json"),
            "preservedPending": preserved,
            "files": console.verify_files(destination, source),
            "newDownloadCommands": 0,
            "failedAttemptPromoted": False,
        },
    )
    verify(profile, source, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--prior-cache", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    create(console.Profile(args.profile), args.prior_cache, args.destination)
    print(json.dumps({"verified_cache_reuse": True, "new_download_commands": 0}))


if __name__ == "__main__":
    main()
