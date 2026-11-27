from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

IMAGE = "gcb-gmod-addons-verifier:23150012"

_SCRIPT = """
import json, sys
from pathlib import Path
from rhenium.core.plugin import BenchmarkContext
from rhenium_garrys_mod.addons.catalog import GmodCatalog
from rhenium_garrys_mod.addons.evaluator import GmodEvaluator
pack = Path("/pack")
catalog = GmodCatalog.load(pack, "catalog.json")
task = next(item for item in catalog.tasks if item.id == sys.argv[1])
state = Path("/opt/gmod/state")
context = BenchmarkContext(
    project_root=pack, pack_root=pack, state_dir=state / "pack", cache_dir=state / "cache"
)
result = GmodEvaluator(context, catalog).evaluate(Path("/submission"), task, profile="full")
print("@@RHENIUM_STUDY_RESULT@@" + json.dumps(result, ensure_ascii=False, default=str))
"""


def image_id() -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is not installed")
    image = subprocess.run(
        [docker, "image", "inspect", IMAGE, "--format", "{{.Id}}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if image.returncode != 0 or not image.stdout.strip():
        raise RuntimeError(f"{IMAGE} is not built; run gmod-harbor-runtime/build-image.sh")
    return image.stdout.strip()


def evaluate(pack_root: Path, task_id: str, submission: Path, *, timeout: float = 1800) -> dict[str, Any]:
    """Full-profile Addons evaluation inside the local pinned-server image.

    The Addons pack has no managed runtime: its native runner needs a 32-bit
    loader this host lacks. The image carries the operator-retained build and a
    byte-for-byte copy of the plugin evaluator; the container has no network and
    sees the pack and the submission read-only.
    """
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker CLI is not installed")
    image = image_id()
    completed = subprocess.run(
        [
            docker,
            "run",
            "--rm",
            "--network=none",
            "--security-opt=no-new-privileges:true",
            "--pids-limit=1024",
            "--memory=12g",
            "--cpus=6",
            "--mount",
            f"type=bind,source={pack_root.resolve()},target=/pack,readonly",
            "--mount",
            f"type=bind,source={submission.resolve()},target=/submission,readonly",
            image,
            "python3",
            "-c",
            _SCRIPT,
            task_id,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith("@@RHENIUM_STUDY_RESULT@@"):
            result = json.loads(line.removeprefix("@@RHENIUM_STUDY_RESULT@@"))
            if isinstance(result, dict):
                return {**result, "studyImageId": image}
    raise RuntimeError(
        "Addons evaluation produced no result: " + (completed.stderr or completed.stdout)[-2000:]
    )
