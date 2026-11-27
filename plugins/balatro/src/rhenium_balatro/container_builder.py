"""Explicitly prepare an immutable, licensed, reviewed Linux execution artifact."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeProgress, RuntimeSpec

from . import container_host as host
from .files import reject_links
from .linux_control import SMOKE_REQUIRED, smoke_files
from .linux_managed_v2 import RUNTIME_ID as NATIVE_ID
from .linux_managed_v2 import BalatroLinuxRuntimeBuilderV2
from .linux_runtime import SOURCE, fingerprint, identity, validate_source
from .linux_runtime import sha as file_hash
from .linux_session import LinuxSessionHost, legacy_tree_hash
from .native_assets import file_sha, json_write_new, verified_assets
from .protocol import classify_poc_result


def native_spec(context: BenchmarkContext) -> RuntimeSpec:
    values = json.loads((context.pack_root / "runtimes.json").read_text())["runtimes"]
    return RuntimeSpec.model_validate(next(value for value in values if value["id"] == NATIVE_ID))


class BalatroContainerBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext) -> None:
        self.context = context

    @staticmethod
    def valid_spec(spec: RuntimeSpec) -> bool:
        return (spec.id == host.RUNTIME_ID and spec.provider == "steam" and spec.restricted
                and spec.host_platforms == ("linux-x64",) and spec.source == SOURCE)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        available = (self.valid_spec(spec) and platform.system() == "Linux"
                     and platform.machine() in {"x86_64", "amd64"}
                     and "microsoft" not in platform.release().lower()
                     and shutil.which("docker") is not None)
        if available:
            try:
                result = subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                                        capture_output=True, text=True, timeout=30, check=False)
                available = result.returncode == 0 and result.stdout.strip() == "linux"
            except (OSError, subprocess.SubprocessError):
                available = False
        return {"available": available, "untrustedSandbox": False,
                "scope": "source-reviewed-linux-container", "display": "owned rendered X display",
                "reason": "" if available else "Linux x86_64, Docker and the exact source are required"}

    def prepare(
        self, spec: RuntimeSpec, source: Path, destination: Path, *, progress: RuntimeProgress,
    ) -> RuntimeArtifact:
        if not self.doctor(spec)["available"]:
            raise ValueError("Controlled Linux container prerequisites are unavailable")
        # Independently enforce expectedFiles and sha256; core and Steam do not enforce them.
        probe = self.context.pack_root / "runtimes.json"
        probe_values = json.loads(probe.read_text())["runtimes"]
        probe_spec = RuntimeSpec.model_validate(next(v for v in probe_values
                                                   if v["id"] == "balatro-linux-17459173-probe-v1"))
        game = validate_source(probe_spec, source)
        reject_links(destination)
        owner = uuid.uuid4().hex
        root = destination / ("preparation-" + owner)
        root.mkdir(parents=True, mode=0o700)
        (root / "operator-state").mkdir(mode=0o700)
        (root / "plugin-cache").mkdir(mode=0o700)
        staged_source = root / "provider-input"
        staged_source.mkdir(mode=0o700)
        shutil.copyfile(game, staged_source / "Balatro.exe")
        validate_source(probe_spec, staged_source)
        context = root / "build-context"
        source_recipe = host.build_context(context)
        tag = "rhenium-balatro-reviewed:" + owner
        iid = root / "image-id"
        progress(10, "building owned Linux dependencies; no licensed game enters the image")
        with (root / "image-build.log").open("xb") as log:
            subprocess.run(["docker", "build", "--iidfile", str(iid), "--tag", tag,
                            "--label", host.LABEL + "=" + owner,
                            "--label", "org.rhenium.balatro.recipe=" + source_recipe,
                            str(context)], stdout=log, stderr=log, timeout=1800, check=True)
        image = iid.read_text().strip()
        details = host.inspect_image(image)
        if details is None or host.image_labels(details).get(host.LABEL) != owner:
            raise ValueError("Prepared image identity or ownership mismatch")
        progress(45, "preparing pinned game and original loader bytes in the owned cache")
        result = host.run_worker(
            image, {"operation": "prepare", "image": image,
                    "context": self.context.model_dump(mode="json"), "root": str(root),
                    "source": str(staged_source)}, root / "prepare-operation",
            readonly=(self.context.pack_root, staged_source), writable=(root,), prepare=True,
        )
        native = RuntimeArtifact.model_validate(result["artifact"])
        builder = BalatroLinuxRuntimeBuilderV2(self.context)
        if not builder.verify(native_spec(self.context), native)["available"]:
            raise ValueError("Prepared native game bytes do not match the fixed recipe")
        progress(75, "running the six original smoke assertions with a rendered game window")
        from .linux_process import game_process_guard

        game_process_guard(None)
        result = host.run_worker(
            image, {"operation": "smoke", "image": image,
                    "context": self.context.model_dump(mode="json"), "root": str(root),
                    "native": native.model_dump(mode="json")}, root / "smoke-operation",
            readonly=(self.context.pack_root,), writable=(root,),
        )
        record = {"schema_version": 1, "runtime_key": host.RUNTIME_KEY,
                  "fingerprint": fingerprint(spec), "recipe": source_recipe,
                  "image_id": image, "owner": owner, "native": native.model_dump(mode="json"),
                  "kernel": platform.release(), "smoke": result["binding"],
                  "smoke_sha256": result["smoke_sha256"]}
        json_write_new(root / host.RECORD, record)
        artifact = RuntimeArtifact(runtime_key=host.RUNTIME_KEY, fingerprint=fingerprint(spec),
                                   kind=host.KIND, identity="sha256:" + identity(record),
                                   location=str(root), metadata=record)
        if not self.verify(spec, artifact)["available"]:
            raise ValueError("Prepared runtime or smoke identity mismatch")
        progress(100, "controlled native Linux runtime and complete smoke verified")
        return artifact

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        available = False
        try:
            root, record = host.load_record(artifact)
            native = RuntimeArtifact.model_validate(record["native"])
            details = host.inspect_image(record["image_id"])
            labels = host.image_labels(details) if details is not None else {}
            binding = record["smoke"]
            marker = Path(binding["smoke_marker"])
            reject_links(marker)
            smoke = json.loads(marker.read_text())
            expected = {"environment": binding["environment"], "harness": binding["harness"],
                        "task": legacy_tree_hash(smoke_files()), "candidate": None}
            assets_sha = file_sha(self.context.pack_root / "private/native-v1/assets.json")
            native_builder = BalatroLinuxRuntimeBuilderV2(self.context)
            available = (
                self.valid_spec(spec) and record["schema_version"] == 1
                and record["runtime_key"] == host.RUNTIME_KEY
                and record["fingerprint"] == artifact.fingerprint == fingerprint(spec)
                and record["recipe"] == host.recipe() and record["kernel"] == platform.release()
                and Path(native.location or "").resolve().is_relative_to((root / "native-v2").resolve())
                and details is not None and labels.get(host.LABEL) == record["owner"]
                and labels.get("org.rhenium.balatro.recipe") == record["recipe"]
                and marker.resolve().is_relative_to((root / "operator-state/linux/operations").resolve())
                and binding["artifact"] == record["native"]
                and binding == json.loads((root / "operator-state/linux-binding-v1.json").read_text())
                and binding["assets_sha256"] == assets_sha
                and binding["harness"] == LinuxSessionHost.harness_identity()
                and file_hash(marker) == record["smoke_sha256"]
                and smoke["fingerprints"] == expected and smoke["operation"] == "smoke"
                and smoke["assets_sha256"] == binding["assets_sha256"]
                and smoke["artifact_identity"] == native.identity
                and classify_poc_result(smoke["evaluation"], SMOKE_REQUIRED, expected, 1)["passed"] is True
                and native_builder.verify(native_spec(self.context), native)["available"]
            )
            if available:
                verified_assets(self.context.pack_root, binding["assets_sha256"])
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, StopIteration,
                subprocess.SubprocessError):
            available = False
        return {"available": available, "untrustedSandbox": False,
                "scope": "source-reviewed-linux-container",
                "reason": "" if available else "Container, native content or complete smoke is unavailable"}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        if spec.id != host.RUNTIME_ID:
            raise ValueError("Refuse another runtime")
        _, record = host.load_record(artifact)
        details = host.inspect_image(record["image_id"])
        if details is None:
            return
        if host.image_labels(details).get(host.LABEL) != record["owner"]:
            raise ValueError("Refuse an image not owned by this artifact")
        subprocess.run(["docker", "image", "rm", record["image_id"]], capture_output=True,
                       timeout=120, check=True)
