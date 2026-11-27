"""Approved transport derivation, with immutable v1 inputs and portable resource identity."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rhenium.core.runtime import RuntimeArtifact, RuntimeProgress, RuntimeSpec

from .files import reject_links
from .linux_managed import PROFILE, BalatroLinuxRuntimeBuilder
from .linux_runtime import (
    RECIPE,
    SOURCE,
    BalatroLinuxProbeBuilder,
    fingerprint,
    identity,
    sha,
    tree,
    validate_source,
)
from .linux_runtime import (
    RUNTIME_ID as PROBE_ID,
)
from .linux_runtime import (
    RUNTIME_KEY as PROBE_KEY,
)
from .native_assets import json_write_new

RUNTIME_ID = "balatro-linux-17459173-controlled-v2"
RUNTIME_KEY = "balatro/" + RUNTIME_ID
TRANSPORT = Path(__file__).with_name("linux_transport_v1")
SERVER = "mods/bot/src/lua/core/server.lua"
ORIGINAL_SHA = "668c10439162949e10dbf3f67d85a8d349d32cc0a58a32bb5dbf1e8bde47e928"
DERIVED_SHA = "e58590bf9507887be409b083ffe40a5f2ad14671a169f28faddf4cf2113b0e2f"
REPLACEMENT_SHA = "816874dedcd933d44a8854451215f27458294df8f8cf1db3562386f4aa4d5250"


def resource_bytes(root: Path) -> dict[str, str]:
    """Interpreter resources are byte inputs, not executable programs.

    Runtime tree verification below still includes every actual executable bit.
    Resource closure and bytes remain checked; no new file is ignored.
    """
    values = tree(root)
    if any("link" in value for value in values.values()):
        raise ValueError("Linked recipe resources are not accepted")
    return {name: value["sha256"] for name, value in values.items()}


def recipe() -> str:
    return identity(
        {
            "builder": sha(Path(__file__)),
            "fixed_builder": sha(Path(__file__).with_name("linux_runtime.py")),
            "parent_builder": sha(Path(__file__).with_name("linux_managed.py")),
            "resources": resource_bytes(RECIPE),
            "transport": resource_bytes(TRANSPORT),
            "profile": PROFILE,
            "resource_mode_policy": "byte-inputs-v2; runtime executable bits retained",
        }
    )


def derived_server(original: bytes) -> bytes:
    import hashlib

    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA:
        raise ValueError("Original Bot server differs from the approved input")
    replacement = TRANSPORT / "send_raw.lua"
    if sha(replacement) != REPLACEMENT_SHA:
        raise ValueError("Transport replacement differs from the approved proposal")
    start = original.index(b"local function send_raw(")
    end = original.index(b"\r\nend", start) + len(b"\r\nend")
    function = replacement.read_bytes().replace(b"\r\n", b"\n")
    function = function[function.index(b"local function send_raw(") :].strip().replace(b"\n", b"\r\n")
    result = original[:start] + function + original[end:]
    if hashlib.sha256(result).hexdigest() != DERIVED_SHA:
        raise ValueError("Derived transport bytes differ from the approved proposal")
    return result


class BalatroLinuxRuntimeBuilderV2(BalatroLinuxRuntimeBuilder):
    @staticmethod
    def valid_spec(spec: RuntimeSpec) -> bool:
        return (
            spec.id == RUNTIME_ID
            and spec.provider == "steam"
            and spec.restricted
            and spec.host_platforms == ("linux-x64",)
            and spec.source == SOURCE
        )

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: RuntimeProgress
    ) -> RuntimeArtifact:
        if not self.doctor(spec)["available"]:
            raise ValueError("Controlled v2 runtime policy mismatch")
        probe_spec = self.probe_spec()
        validate_source(probe_spec, source)
        reject_links(destination)
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Refuse to overwrite prior runtime evidence")
        legacy = BalatroLinuxProbeBuilder(self.context)
        original = destination.parent / PROBE_ID
        marker_path = original / "probe-artifact-v1.json"
        if marker_path.exists():
            reject_links(marker_path)
            marker = json.loads(marker_path.read_text())
            base = RuntimeArtifact(
                runtime_key=PROBE_KEY,
                fingerprint=fingerprint(probe_spec),
                kind="balatro-linux-probe-tree-v1",
                identity=marker["identity"],
                location=str(original / "probe-tree-v1"),
                metadata={"recipeSha256": marker["recipe"]},
            )
            if not legacy.verify(probe_spec, base)["available"]:
                raise ValueError("Existing fixed inputs drifted; refuse rebuild or repin")
        else:
            # Explicit preparation only, using the existing fixed recipe and provider source.
            base = legacy.prepare(probe_spec, source, destination / "original-inputs", progress=progress)
            marker_path = Path(base.location or "").parent / "probe-artifact-v1.json"
            marker = json.loads(marker_path.read_text())
        base_root = Path(base.location or "")
        reject_links(base_root)
        before = tree(base_root)
        if before != marker["files"] or base.identity != "sha256:" + identity(before):
            raise ValueError("Fixed input content identity changed")
        changed = derived_server((base_root / SERVER).read_bytes())
        root = destination / "derived-tree-v2"
        progress(30, "copying verified fixed inputs; applying approved transport derivation only")
        shutil.copytree(base_root, root, symlinks=True)
        (root / SERVER).write_bytes(changed)
        after = tree(root)
        expected = {**before, SERVER: {**before[SERVER], "sha256": DERIVED_SHA}}
        if after != expected or tree(base_root) != before:
            raise ValueError("Unexpected change outside the approved transport function")
        record = {
            "schema_version": 2,
            "runtime_key": RUNTIME_KEY,
            "fingerprint": fingerprint(spec),
            "recipe": recipe(),
            "profile": PROFILE,
            "original_identity": base.identity,
            "original_marker_sha256": sha(marker_path),
            "original_files": before,
            "files": after,
            "transport": {
                "path": SERVER,
                "original_sha256": ORIGINAL_SHA,
                "derived_sha256": DERIVED_SHA,
                "replacement_sha256": REPLACEMENT_SHA,
            },
        }
        json_write_new(destination / "runtime-artifact-v2.json", record)
        artifact = RuntimeArtifact(
            runtime_key=RUNTIME_KEY,
            fingerprint=fingerprint(spec),
            kind="balatro-controlled-linux-tree-v2",
            identity="sha256:" + identity(record),
            location=str(root),
            metadata={
                "scope": PROFILE["scope"],
                "executionProfile": PROFILE,
                "requiresMatchingSmoke": True,
                "recipeSha256": recipe(),
                "transport": record["transport"],
            },
        )
        if not self.verify(spec, artifact)["available"]:
            raise ValueError("Derived runtime verification failed")
        progress(100, "versioned derived runtime prepared; new current-host smoke required")
        return artifact

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        available = False
        try:
            root = Path(artifact.location or "")
            reject_links(root)
            record = json.loads((root.parent / "runtime-artifact-v2.json").read_text())
            original = record["original_files"]
            expected = {**original, SERVER: {**original[SERVER], "sha256": DERIVED_SHA}}
            available = (
                root.is_absolute()
                and root.name == "derived-tree-v2"
                and self.valid_spec(spec)
                and artifact.runtime_key == record["runtime_key"] == RUNTIME_KEY
                and artifact.fingerprint == record["fingerprint"] == fingerprint(spec)
                and artifact.kind == "balatro-controlled-linux-tree-v2"
                and artifact.identity == "sha256:" + identity(record)
                and record["schema_version"] == 2
                and record["profile"] == artifact.metadata["executionProfile"] == PROFILE
                and record["recipe"] == artifact.metadata["recipeSha256"] == recipe()
                and record["transport"] == artifact.metadata["transport"]
                and original[SERVER]["sha256"] == ORIGINAL_SHA
                and record["original_identity"] == "sha256:" + identity(original)
                and tree(root) == record["files"] == expected
            )
        except (OSError, ValueError, KeyError, TypeError):
            available = False
        return {
            "available": available,
            "scope": PROFILE["scope"],
            "requiresMatchingSmoke": True,
            "untrustedSandbox": False,
            "reason": "" if available else "Derived runtime identity mismatch",
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        if (
            not self.valid_spec(spec)
            or artifact.runtime_key != RUNTIME_KEY
            or artifact.fingerprint != fingerprint(spec)
        ):
            raise ValueError("Refuse unrelated artifact")
