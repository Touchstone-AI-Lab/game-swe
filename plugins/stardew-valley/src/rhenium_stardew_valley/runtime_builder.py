from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from rhenium.core.plugin import BenchmarkContext
from rhenium.core.runtime import RuntimeArtifact, RuntimeBuilder, RuntimeSpec

from .catalog import StardewCatalog
from .evaluator import _DOCKER_TIMEOUT, BUILD_CONTEXT_LABEL, StardewRuntime


class StardewRuntimeBuilder(RuntimeBuilder):
    def __init__(self, context: BenchmarkContext, catalog: StardewCatalog):
        self.context = context
        self.catalog = catalog
        self.runtime = StardewRuntime(context, catalog)

    def doctor(self, spec: RuntimeSpec) -> dict[str, Any]:
        del spec
        return self.runtime.status()

    def prepare(
        self,
        spec: RuntimeSpec,
        source: Path,
        destination: Path,
        *,
        progress: Any,
    ) -> RuntimeArtifact:
        del destination
        game = source
        if not (game / "Stardew Valley.dll").is_file() or not (game / "Content").is_dir():
            raise RuntimeError("Steam acquisition did not produce the pinned Stardew Linux depot")
        images: dict[str, str] = {}
        total = len(self.catalog.tasks)
        for index, task in enumerate(self.catalog.tasks, 1):
            progress(int((index - 1) * 100 / total), f"building evaluator image for {task.id}")
            _tag, _log = self.runtime.ensure_image(task, game_dir=game)
            images[task.id] = self.runtime.image_id(task)
        identity = hashlib.sha256(
            "\n".join(f"{key}={value}" for key, value in sorted(images.items())).encode()
        ).hexdigest()
        fingerprint = spec.fingerprint(plugin_id="stardew-valley", plugin_version="0.6.0")
        progress(100, "Stardew evaluator images ready")
        return RuntimeArtifact(
            runtime_key=f"stardew-valley/{spec.id}",
            fingerprint=fingerprint,
            kind="docker-images",
            identity=f"sha256:{identity}",
            metadata={"images": images, "network": "none"},
        )

    def verify(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> dict[str, Any]:
        del spec
        images = artifact.metadata.get("images", {})
        if not isinstance(images, dict) or set(images) != {task.id for task in self.catalog.tasks}:
            return {"available": False, "reason": "runtime artifact has an incomplete image set"}
        for task_id, image_id in images.items():
            result = self.runtime._docker(
                ["image", "inspect", str(image_id), "--format", "{{.Id}}"], timeout=_DOCKER_TIMEOUT
            )
            if result.returncode != 0 or result.stdout.strip() != image_id:
                return {"available": False, "reason": f"evaluator image is missing: {task_id}"}
        for task in self.catalog.tasks:
            label = self.runtime._docker(
                [
                    "image", "inspect", str(images[task.id]), "--format",
                    f'{{{{index .Config.Labels "{BUILD_CONTEXT_LABEL}"}}}}',
                ],
                timeout=_DOCKER_TIMEOUT,
            )
            if label.stdout.strip() != self.runtime.build_context_digest(task):
                return {
                    "available": False,
                    "reason": f"evaluator image was built from different task inputs: {task.id}",
                }
        return {"available": True, "imageCount": len(images), "network": "none"}

    def prune(self, spec: RuntimeSpec, artifact: RuntimeArtifact) -> None:
        del spec
        images = artifact.metadata.get("images", {})
        if isinstance(images, dict):
            for image_id in set(map(str, images.values())):
                self.runtime._docker(["image", "rm", image_id], timeout=_DOCKER_TIMEOUT)

