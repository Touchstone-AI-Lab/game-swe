"""Versioned controlled native runtime, preserving the original probe artifact.

Preparation owns its copy of exact acquired inputs. Read-only verify establishes
content identity; a separate current-environment smoke is required for scoring.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from rhenium.core.runtime import RuntimeArtifact, RuntimeProgress, RuntimeSpec

from .files import reject_links
from .linux_runtime import (
    RUNTIME_ID as PROBE_ID,
)
from .linux_runtime import (
    RUNTIME_KEY as PROBE_KEY,
)
from .linux_runtime import (
    SOURCE,
    BalatroLinuxProbeBuilder,
    fingerprint,
    identity,
    recipe_identity,
    sha,
    validate_source,
)
from .native_assets import json_write_new

RUNTIME_ID = "balatro-linux-17459173-controlled-v1"
RUNTIME_KEY = "balatro/" + RUNTIME_ID
PROFILE = {
    "schema_version": 1,
    "scope": "source-reviewed-native-linux",
    "visible": True,
    "gamespeed": 1,
    "fast": False,
    "headless": False,
    "audio_backend": "null",
    "untrusted_sandbox": False,
}


def recipe() -> str:
    return identity(
        {"builder": sha(Path(__file__)), "fixed_inputs_recipe": recipe_identity(), "profile": PROFILE}
    )


class BalatroLinuxRuntimeBuilder(BalatroLinuxProbeBuilder):
    def probe_spec(self) -> RuntimeSpec:
        values = json.loads((self.context.pack_root / "runtimes.json").read_text())["runtimes"]
        return RuntimeSpec.model_validate(next(value for value in values if value["id"] == PROBE_ID))

    @staticmethod
    def valid_spec(spec: RuntimeSpec) -> bool:
        return (
            spec.id == RUNTIME_ID
            and spec.provider == "steam"
            and spec.restricted
            and spec.host_platforms == ("linux-x64",)
            and spec.source == SOURCE
        )

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        report = super().doctor(self.probe_spec())
        available = self.valid_spec(spec) and report["available"]
        return {
            "available": available,
            "platform": "linux-x64",
            "scope": PROFILE["scope"],
            "requiresMatchingSmoke": True,
            "untrustedSandbox": False,
            "requiresVisibleDisplayAtExecution": True,
            "reason": "" if available else "Exact source and Linux x86_64 host required",
        }

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: RuntimeProgress
    ) -> RuntimeArtifact:
        if not self.doctor(spec)["available"]:
            raise ValueError("Controlled Linux runtime policy mismatch")
        probe_spec = self.probe_spec()
        validate_source(probe_spec, source)
        reject_links(destination)
        inputs = destination / "inputs"
        if inputs.exists() or (destination / "runtime-artifact-v1.json").exists():
            raise ValueError("Refuse to overwrite existing runtime evidence")
        original = destination.parent / PROBE_ID
        original_marker = original / "probe-artifact-v1.json"
        legacy_builder = BalatroLinuxProbeBuilder(self.context)
        if original_marker.exists():
            # Reuse validated fixed bytes, not a mutable installation or a new pin.
            reject_links(original_marker)
            marker = json.loads(original_marker.read_text())
            old = RuntimeArtifact(
                runtime_key=PROBE_KEY,
                fingerprint=fingerprint(probe_spec),
                kind="balatro-linux-probe-tree-v1",
                identity=marker["identity"],
                location=str(original / "probe-tree-v1"),
                metadata={"recipeSha256": marker["recipe"]},
            )
            if not legacy_builder.verify(probe_spec, old)["available"]:
                raise ValueError("Existing fixed probe inputs drifted; stop preparation")
            progress(20, "copying verified existing fixed inputs into this runtime's owned cache")
            inputs.mkdir(parents=True)
            shutil.copytree(original / "probe-tree-v1", inputs / "probe-tree-v1", symlinks=True)
            json_write_new(inputs / "probe-artifact-v1.json", marker)
            inner = old.model_copy(update={"location": str(inputs / "probe-tree-v1")})
        else:
            inner = legacy_builder.prepare(probe_spec, source, inputs, progress=progress)
        if not legacy_builder.verify(probe_spec, inner)["available"]:
            raise ValueError("Prepared fixed inputs do not verify")
        record = {
            "schema_version": 1,
            "runtime_key": RUNTIME_KEY,
            "fingerprint": fingerprint(spec),
            "inner": inner.model_dump(mode="json"),
            "probe_spec": probe_spec.model_dump(mode="json"),
            "profile": PROFILE,
            "recipe": recipe(),
        }
        json_write_new(destination / "runtime-artifact-v1.json", record)
        artifact = RuntimeArtifact(
            runtime_key=RUNTIME_KEY,
            fingerprint=fingerprint(spec),
            kind="balatro-controlled-linux-tree-v1",
            identity="sha256:" + identity(record),
            location=inner.location,
            metadata={
                "scope": PROFILE["scope"],
                "executionProfile": PROFILE,
                "requiresMatchingSmoke": True,
                "recipeSha256": recipe(),
            },
        )
        if not self.verify(spec, artifact)["available"]:
            raise ValueError("Prepared controlled runtime does not verify")
        progress(100, "fixed runtime prepared; current-host smoke is required before scoring")
        return artifact

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        available = False
        try:
            root = Path(artifact.location or "")
            reject_links(root)
            record = json.loads((root.parent.parent / "runtime-artifact-v1.json").read_text())
            inner = RuntimeArtifact.model_validate(record["inner"])
            probe_spec = RuntimeSpec.model_validate(record["probe_spec"])
            available = (
                self.valid_spec(spec)
                and artifact.runtime_key == RUNTIME_KEY
                and artifact.fingerprint == record["fingerprint"] == fingerprint(spec)
                and artifact.kind == "balatro-controlled-linux-tree-v1"
                and artifact.identity == "sha256:" + identity(record)
                and artifact.location == inner.location
                and root.parent.name == "inputs"
                and record["runtime_key"] == RUNTIME_KEY
                and record["profile"] == PROFILE
                and artifact.metadata["executionProfile"] == PROFILE
                and record["recipe"] == artifact.metadata["recipeSha256"] == recipe()
                and probe_spec == self.probe_spec()
                and BalatroLinuxProbeBuilder(self.context).verify(probe_spec, inner)["available"]
            )
        except (OSError, ValueError, KeyError, StopIteration):
            available = False
        return {
            "available": available,
            "scope": PROFILE["scope"],
            "requiresMatchingSmoke": True,
            "untrustedSandbox": False,
            "reason": "" if available else "Controlled runtime identity mismatch",
        }

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        # Core removes only this runtime's selected cache; the original probe stays.
        if (
            not self.valid_spec(spec)
            or artifact.runtime_key != RUNTIME_KEY
            or artifact.fingerprint != fingerprint(spec)
        ):
            raise ValueError("Refuse unrelated artifact")
