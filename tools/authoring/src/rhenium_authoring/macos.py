"""Opt-in native maintenance diagnostics, separate from publication validation."""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from rhenium.config import Settings
from rhenium.hub import BenchmarkHub
from rhenium.operations import OperationManager

from .artifacts import write_file_tree
from .models import SynthesisBundle
from .publisher import PackPublisher


def _paths(project: Path, run_id: str, candidate_id: str) -> tuple[Path, SynthesisBundle]:
    if any(re.fullmatch(r"[a-z0-9][a-z0-9-]*", value) is None for value in (run_id, candidate_id)):
        raise ValueError("invalid authoring run or candidate ID")
    run = project / ".rhenium/authoring/runs" / run_id
    candidate = run / "candidates" / candidate_id
    bundle_path = candidate / "private/bundle.json"
    if not bundle_path.resolve().is_relative_to(run.resolve()) or bundle_path.is_symlink():
        raise ValueError("invalid candidate bundle path")
    bundle = SynthesisBundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
    if bundle.candidate.id != candidate_id or bundle.candidate.game_id != "stardew-valley":
        raise ValueError("macOS diagnostics require a matching Stardew candidate")
    return run / "macos-diagnostics" / candidate_id, bundle


def _hub(project: Path, root: Path) -> BenchmarkHub:
    pack = root / "pack/stardew-synth"
    state = root / "state"
    settings = Settings(
        root=project,
        state_dir=state,
        cache_dir=state / "cache",
        database_url=f"sqlite:///{state / 'state.sqlite'}",
        benchmark_paths=(pack,),
        web_dist=None,
    )
    return BenchmarkHub(settings=settings, manifest_paths=(pack / "benchmark.json",))


def prepare_macos(
    project: Path,
    run_id: str,
    candidate_id: str,
    game_dir: Path,
    *,
    progress: Any,
) -> dict[str, Any]:
    from rhenium_stardew_valley.native import NATIVE_ID

    root, bundle = _paths(project, run_id, candidate_id)
    game = game_dir.expanduser()
    if game.is_symlink():
        raise ValueError("game installation must not be a symbolic link")
    if (game / "Contents/MacOS").is_dir():
        game = game / "Contents"
    elif game.name == "MacOS" and (game.parent / "Resources/Content").is_dir():
        game = game.parent
    game = game.resolve(strict=True)
    included = sorted(
        "MacOS/" + path.name
        for path in (game / "MacOS").iterdir()
        if (
            path.name in {"Content", "Stardew Valley", "steam_appid.txt"}
            or path.suffix in {".dll", ".dylib"}
            or path.name.endswith((".deps.json", ".runtimeconfig.json"))
        )
    )
    included.extend(["Resources/Content", "Info.plist"])
    spec = {
        "id": NATIVE_ID,
        "name": "Stardew macOS native maintenance diagnostic",
        "version": "1.6.15.24356 / SMAPI 4.1.10",
        "provider": "local-files",
        "restricted": True,
        "host_platforms": ["darwin-arm64", "darwin-x64"],
        "source": {
            "kind": "local-files",
            "path": str(game),
            "include": included,
            "expectedFiles": ["MacOS/Stardew Valley.dll", "MacOS/Stardew Valley", "Resources/Content"],
        },
    }
    pack = root / "pack/stardew-synth"
    if not pack.exists():
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        pack = PackPublisher(project).stage(bundle, root / "pack")
        (pack / "runtimes.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "runtimes": [spec],
                    "task_bindings": {candidate_id: [NATIVE_ID]},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (pack / "private/harbor" / candidate_id / "tests/native-cases.json").write_text(
            json.dumps(bundle.verifier.case_ids) + "\n", encoding="utf-8"
        )
    elif json.loads((pack / "runtimes.json").read_text())["runtimes"] != [spec]:
        raise ValueError("native diagnostic source changed; use a new authoring run")
    hub = _hub(project, root)
    hub.auth.login("local-files")
    operations = OperationManager(hub)
    operation = operations.start("runtime_prepare", f"stardew-valley/{NATIVE_ID}")
    previous = None
    while operation["status"] in {"queued", "running", "waiting_user"}:
        update = (operation["progress"], operation["phase"])
        if update != previous:
            progress(*update)
            previous = update
        time.sleep(0.25)
        operation = operations.get(operation["id"]) or operation
    return operation


def check_macos(project: Path, run_id: str, candidate_id: str) -> dict[str, Any]:
    root, bundle = _paths(project, run_id, candidate_id)
    hub = _hub(project, root)
    task_key = f"stardew-valley/synth/{candidate_id}"
    controls = [
        ("base", bundle.base.files),
        ("gold", bundle.fixed.files),
        *[(f"ablation-{key}", value) for key, value in sorted(bundle.base.ablations.items())],
    ]
    reports: dict[str, Any] = {}
    inputs = root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    check_root = Path(tempfile.mkdtemp(prefix="check-", dir=inputs))
    for label, tree in controls:
        submission = check_root / label
        write_file_tree(submission / "mod", tree)
        result = hub.evaluate_task(task_key, submission, profile="macos")
        reports[label] = result
        (root / f"{label}-result.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    report = {
        "candidate": candidate_id,
        "profile": "macos",
        "complete": False,
        "passed": False,
        "publicationEligible": False,
        "controls": reports,
    }
    (root / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report
