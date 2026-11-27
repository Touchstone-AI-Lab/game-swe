from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_isaac_authored_task_assets_match_pr2_baseline() -> None:
    frozen = [
        ROOT / "benchmarks/isaac-core/exams/isaac-exodus-release-regressions.md",
        ROOT / "benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/environment/exodus",
        ROOT / "benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/tests",
        ROOT / "benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/solution",
        ROOT / "benchmarks/isaac-core/private/harbor/isaac-exodus-release-regressions/validation",
    ]
    files: list[Path] = []
    for candidate in frozen:
        files.extend([candidate] if candidate.is_file() else candidate.rglob("*"))
    digest = hashlib.sha256()
    for candidate in sorted((path for path in files if path.is_file()), key=lambda path: path.as_posix()):
        relative = candidate.relative_to(ROOT).as_posix()
        digest.update(relative.encode() + b"\0" + hashlib.sha256(candidate.read_bytes()).digest())

    assert digest.hexdigest() == "9a50aba82fc81b9df13075280a8323bd30484c6f6f35bc1520c5a613632913ef"


def test_core_metadata_has_no_dst_or_lua_runtime_dependency() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = "\n".join(metadata["project"]["dependencies"]).lower()

    assert metadata["project"]["version"] == "0.6.0"
    assert "lupa" not in dependencies
    assert "tree-sitter-lua" not in dependencies
    assert "rhenium-dst" not in dependencies
    assert "rhenium-gmod" not in dependencies
    assert "rhenium_gmod" not in dependencies
    assert "rhenium-isaac-rebirth" not in dependencies
    assert "rhenium-garrys-mod" not in dependencies
    assert "rhenium-left-4-dead-2" not in dependencies
    assert "rhenium-rimworld" not in dependencies
    assert "rhenium-mindustry" not in dependencies
    assert "rhenium-minecraft" not in dependencies
    assert "rhenium-slay-the-spire" not in dependencies
    assert "rhenium-slay-the-spire" not in dependencies
    assert "rhenium-palworld" not in dependencies
    assert "rhenium-container" not in dependencies
    assert "rhenium-official-download" not in dependencies
    assert "entry-points" not in metadata["project"]


def test_core_source_distribution_only_selects_publishable_core_inputs() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sdist = metadata["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert set(sdist["only-include"]) == {"src/rhenium", "README.md", "pyproject.toml", ".gitignore"}
    assert sdist["force-include"] == {"web/dist": "web/dist"}
    assert {"**/__pycache__/**", "**/*.pyc", "**/*.pyo"} <= set(sdist["exclude"])


def test_plugins_are_independent_workspace_distributions() -> None:
    core = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dst = tomllib.loads((ROOT / "plugins/dst/pyproject.toml").read_text(encoding="utf-8"))
    contract = tomllib.loads((ROOT / "plugins/contract/pyproject.toml").read_text(encoding="utf-8"))
    isaac = tomllib.loads((ROOT / "plugins/isaac-rebirth/pyproject.toml").read_text(encoding="utf-8"))
    stardew = tomllib.loads((ROOT / "plugins/stardew-valley/pyproject.toml").read_text(encoding="utf-8"))
    garrys_mod = tomllib.loads((ROOT / "plugins/garrys-mod/pyproject.toml").read_text(encoding="utf-8"))
    palworld = tomllib.loads((ROOT / "plugins/palworld/pyproject.toml").read_text(encoding="utf-8"))
    l4d2 = tomllib.loads((ROOT / "plugins/left-4-dead-2/pyproject.toml").read_text(encoding="utf-8"))
    rimworld = tomllib.loads((ROOT / "plugins/rimworld/pyproject.toml").read_text(encoding="utf-8"))
    mindustry = tomllib.loads((ROOT / "plugins/mindustry/pyproject.toml").read_text(encoding="utf-8"))
    minecraft = tomllib.loads((ROOT / "plugins/minecraft/pyproject.toml").read_text(encoding="utf-8"))
    slay_the_spire = tomllib.loads(
        (ROOT / "plugins/slay-the-spire/pyproject.toml").read_text(encoding="utf-8")
    )
    steam = tomllib.loads((ROOT / "providers/steam/pyproject.toml").read_text(encoding="utf-8"))
    container = tomllib.loads((ROOT / "providers/container/pyproject.toml").read_text(encoding="utf-8"))
    official_download = tomllib.loads(
        (ROOT / "providers/official-download/pyproject.toml").read_text(encoding="utf-8")
    )
    authoring = tomllib.loads((ROOT / "tools/authoring/pyproject.toml").read_text(encoding="utf-8"))

    assert "exclude" not in core["tool"]["uv"]["workspace"]
    assert not (ROOT / "plugins/gmod/pyproject.toml").exists()
    assert not (ROOT / "plugins/garrys-mod/src/rhenium_gmod").exists()
    assert (ROOT / "plugins/garrys-mod/src/rhenium_garrys_mod/addons").is_dir()
    assert (ROOT / "plugins/garrys-mod/src/rhenium_garrys_mod/darkrp").is_dir()
    assert core["tool"]["uv"]["workspace"]["members"] == [
        "plugins/*",
        "providers/*",
        "tools/authoring",
        "tools/study",
    ]
    assert dst["project"]["entry-points"]["rhenium.benchmarks"]["dst"].startswith("rhenium_dst.")
    assert contract["project"]["entry-points"]["rhenium.benchmarks"]["contract"].startswith(
        "rhenium_contract."
    )
    assert isaac["project"]["entry-points"]["rhenium.benchmarks"]["isaac-rebirth"].startswith(
        "rhenium_isaac_rebirth."
    )
    assert stardew["project"]["entry-points"]["rhenium.benchmarks"]["stardew-valley"].startswith(
        "rhenium_stardew_valley."
    )
    assert garrys_mod["project"]["entry-points"]["rhenium.benchmarks"]["garrys-mod"].startswith(
        "rhenium_garrys_mod."
    )
    assert list(garrys_mod["project"]["entry-points"]["rhenium.benchmarks"]) == ["garrys-mod"]
    assert rimworld["project"]["entry-points"]["rhenium.benchmarks"]["rimworld"].startswith(
        "rhenium_rimworld."
    )
    assert rimworld["project"]["dependencies"] == ["rhenium==0.6.0"]
    assert list(mindustry["project"]["entry-points"]["rhenium.benchmarks"]) == ["mindustry"]
    # Mindustry downloads its pinned official server release through the official-download provider.
    assert mindustry["project"]["dependencies"] == [
        "rhenium==0.6.0",
        "rhenium-official-download==0.1.0",
    ]
    assert list(minecraft["project"]["entry-points"]["rhenium.benchmarks"]) == ["minecraft"]
    # Minecraft downloads the pinned Paper jar the same way; the EULA stays the operator's record.
    assert minecraft["project"]["dependencies"] == [
        "rhenium==0.6.0",
        "rhenium-official-download==0.1.0",
    ]
    assert official_download["project"]["entry-points"]["rhenium.auth_providers"] == {
        "official-download": "rhenium_official_download.provider:OfficialDownloadProvider"
    }
    # The HTTP client is the provider's own dependency, not one it borrows from core.
    assert official_download["project"]["dependencies"] == ["rhenium==0.6.0", "httpx>=0.28.1"]
    assert list(slay_the_spire["project"]["entry-points"]["rhenium.benchmarks"]) == [
        "slay-the-spire"
    ]
    # ModTheSpire evaluator images build on a public digest-pinned base image, so the
    # plugin needs the container provider and no licensed-content provider.
    assert slay_the_spire["project"]["dependencies"] == [
        "rhenium==0.6.0",
        "rhenium-container==0.1.0",
    ]
    assert palworld["project"]["entry-points"]["rhenium.benchmarks"]["palworld"].startswith(
        "rhenium_palworld."
    )
    assert "rhenium==0.6.0" in palworld["project"]["dependencies"]
    assert palworld["project"]["name"] == "rhenium-palworld"
    assert stardew["project"]["dependencies"] == ["rhenium==0.6.0"]
    assert isaac["project"]["dependencies"] == ["rhenium==0.6.0"]
    assert "rhenium==0.6.0" in garrys_mod["project"]["dependencies"]
    assert "lupa>=2.4" in garrys_mod["project"]["dependencies"]
    assert "tree-sitter-lua>=0.2.0" in garrys_mod["project"]["dependencies"]
    assert garrys_mod["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/rhenium_garrys_mod"]
    assert "force-include" not in garrys_mod["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert l4d2["project"]["entry-points"]["rhenium.benchmarks"]["left-4-dead-2"].startswith(
        "rhenium_left_4_dead_2."
    )
    assert l4d2["project"]["dependencies"] == ["rhenium==0.6.0"]
    assert steam["project"]["entry-points"]["rhenium.auth_providers"]["steam"].startswith("rhenium_steam.")
    assert container["project"]["entry-points"]["rhenium.auth_providers"]["container"].startswith(
        "rhenium_container."
    )
    assert steam["project"]["dependencies"] == ["rhenium==0.6.0"]
    assert container["project"]["dependencies"] == ["rhenium==0.6.0"]
    assert authoring["project"]["scripts"] == {"rhenium-author": "rhenium_authoring.cli:app"}
    assert "rhenium==0.6.0" in authoring["project"]["dependencies"]


def test_core_source_contains_no_dst_import_or_default() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "src/rhenium").rglob("*.py"))
    )

    assert "rhenium_dst" not in source
    assert "rhenium_gmod" not in source
    assert "rhenium_isaac_rebirth" not in source
    assert "rhenium_garrys_mod" not in source
    assert "rhenium_left_4_dead_2" not in source
    assert "rhenium_rimworld" not in source
    assert "rhenium_mindustry" not in source
    assert "rhenium_minecraft" not in source
    assert "rhenium_slay_the_spire" not in source
    assert "rhenium_palworld" not in source
    assert "rhenium_container" not in source
    assert "rhenium.games.dst" not in source
    assert "benchmarks/dst" not in source
    assert "benchmarks/gmod" not in source
    assert "benchmarks/isaac-core" not in source
    assert "prop-ownership-quota-registry" not in source
    assert "staged-prop-alignment" not in source
    assert "persistent-loadout-profiles" not in source
    assert "hot-object-round-controller" not in source
    assert "contraption-blueprint-duplicator" not in source
    assert "23150012" not in source
    assert "App 4020" not in source
    assert "benchmarks/darkrp-core" not in source
    assert "benchmarks/l4d2-core" not in source
    assert "benchmarks/rimworld-core" not in source
    assert "benchmarks/mindustry-core" not in source
    assert "benchmarks/minecraft-core" not in source
    assert "benchmarks/minecraft-synth" not in source
    assert "benchmarks/minecraft-construct" not in source
    assert "benchmarks/slay-the-spire-core" not in source
    assert "benchmarks/palworld" not in source


def test_darkrp_public_summaries_do_not_expand_the_private_problem_map() -> None:
    catalog = json.loads((ROOT / "benchmarks/darkrp-core/catalog.json").read_text(encoding="utf-8"))

    for task in catalog["tasks"]:
        assert task["summary"] == task["brief"]
        assert len(task["source_commit"]) == 40


def test_darkrp_harbor_tasks_share_bounded_build_inputs_and_dynamic_egress() -> None:
    task_root = ROOT / "benchmarks/darkrp-core/private/harbor"
    task_dirs = sorted(path for path in task_root.iterdir() if (path / "task.toml").is_file())
    dockerfiles = {(task / "environment/Dockerfile").read_text(encoding="utf-8") for task in task_dirs}
    constraints = {(task / "environment/agent-constraints.txt").read_bytes() for task in task_dirs}

    assert len(task_dirs) == 8
    assert len(dockerfiles) == 1
    assert len(constraints) == 1
    dockerfile = dockerfiles.pop()
    assert "snapshot.debian.org/archive/debian/20260830T000000Z" in dockerfile
    assert "ghcr.io/astral-sh/uv@sha256:" in dockerfile
    assert "curl -LsSf" not in dockerfile
    assert ":latest" not in dockerfile

    for task in task_dirs:
        metadata = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
        assert metadata["agent"]["network_mode"] == "allowlist"
        assert metadata["agent"]["allowed_hosts"] == []
