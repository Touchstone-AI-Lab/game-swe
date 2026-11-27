from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any

from rhenium.util import hash_tree

from .artifacts import write_file_tree
from .game_adapters import GameAuthoringSpec, game_spec
from .models import CleanRoomManifest, PublicationRecord, SynthesisBundle, ValidationReport

_EXPECTED = re.compile(r"^EXPECTED=([0-9]+)$", re.MULTILINE)
_ISAAC_EXPECTED = re.compile(r"^expected=([0-9]+)$", re.MULTILINE)
_PLUGIN_NAME_LINE = re.compile(r"^name:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?\s*$", re.MULTILINE)
_MINECRAFT_CORE = "minecraft-core"
_MINECRAFT_HARNESS = f"{_MINECRAFT_CORE}/private/harbor/harness"
_MINECRAFT_VERIFIER_BASE = "gcb-minecraft-paper-verifier:1.21.11-132"
# Mirrors DEFAULT_FROZEN_PATHS of the Minecraft plugin catalog: tests/task.json
# must equal the plugin's task_manifest() byte for byte, so the defaults are
# spelled out here rather than imported from the optional plugin distribution.
_MINECRAFT_FROZEN_PATHS = (
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "gradle",
    "gradlew",
    "gradlew.bat",
    "pom.xml",
    ".mvn",
    "mvnw",
    "mvnw.cmd",
    "src/test",
)
# Trusted files no model-authored verifier may replace, shared by every game
# plus the ones a game's trusted assets add.
_PROTECTED_ASSETS = frozenset(
    {
        "tests/trusted_collector.py",
        "environment/Dockerfile",
        "environment/agent-constraints.txt",
        "scripts/private-runtime.Dockerfile",
    }
)
_GAME_PROTECTED_ASSETS: dict[str, frozenset[str]] = {
    "minecraft": frozenset(
        {
            "tests/Dockerfile",
            "tests/verify.py",
            "tests/task.json",
            "solution/solve.sh",
            "scripts/javac-build.sh",
        }
    ),
}


class PackPublisher:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.benchmarks = self.project_root / "benchmarks"
        self.lock_path = self.project_root / ".rhenium" / "authoring" / "publish.lock"

    def publish(self, bundle: SynthesisBundle, validation: ValidationReport) -> PublicationRecord:
        if not bundle.review.approved:
            raise ValueError("independent clean-room review rejected the candidate")
        if not (
            validation.candidate_id == bundle.candidate.id
            and validation.passed
            and validation.complete
            and validation.base_failed
            and validation.gold_passed
            and validation.engine_backed
        ):
            raise ValueError("candidate lacks complete two-way real-engine validation")
        spec = game_spec(bundle.candidate.game_id)
        if spec.game_id == "dst":
            raise ValueError(
                "the DST plugin loads only upstream repair tasks and cannot load a synthetic pack"
            )
        self._validate_required_files(spec, bundle)
        with self._lock():
            version = self._publish_locked(spec, bundle)
        return PublicationRecord(
            candidate_id=bundle.candidate.id,
            task_key=f"{spec.game_id}/synth/{bundle.candidate.id}",
            catalog_version=version,
        )

    def stage(self, bundle: SynthesisBundle, destination: Path) -> Path:
        """Build a complete temporary pack for pre-publication engine validation."""

        spec = game_spec(bundle.candidate.game_id)
        self._validate_required_files(spec, bundle)
        target = destination.resolve() / spec.pack_directory
        if target.exists():
            raise FileExistsError(target)
        self._initialize_pack(target, spec)
        self._append(target, spec, bundle)
        return target

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _publish_locked(self, spec: GameAuthoringSpec, bundle: SynthesisBundle) -> str:
        target = self.benchmarks / spec.pack_directory
        if not target.exists():
            with tempfile.TemporaryDirectory(
                prefix=f".{spec.pack_directory}-", dir=self.benchmarks
            ) as raw_stage:
                stage = Path(raw_stage) / spec.pack_directory
                self._initialize_pack(stage, spec)
                version = self._append(stage, spec, bundle)
                os.replace(stage, target)
                return version
        if not target.is_dir() or target.is_symlink():
            raise ValueError("synthetic pack target is unsafe")
        if any(path.is_symlink() for path in target.rglob("*")):
            raise ValueError("synthetic pack contains a symbolic link")
        with tempfile.TemporaryDirectory(
            prefix=f".{spec.pack_directory}-update-", dir=self.benchmarks
        ) as raw_stage:
            transaction = Path(raw_stage)
            stage = transaction / spec.pack_directory
            backup = transaction / f"{spec.pack_directory}.backup"
            shutil.copytree(target, stage)
            version = self._append(stage, spec, bundle)
            os.replace(target, backup)
            try:
                os.replace(stage, target)
            except BaseException:
                os.replace(backup, target)
                raise
            return version

    def _initialize_pack(self, root: Path, spec: GameAuthoringSpec) -> None:
        root.mkdir(parents=True)
        (root / "benchmark.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "pack_id": "synth",
                    "plugin": spec.plugin_id,
                    "catalog": "catalog.json",
                    **({"runtime_catalog": "runtimes.json"} if spec.runtime_id else {}),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "catalog.json").write_text(
            json.dumps(
                {
                    "id": f"{spec.game_id}-clean-room-synth",
                    "version": "0.0.0",
                    "game": spec.game_id,
                    "name": {
                        "en": f"{spec.game_id} clean-room synthetic repairs",
                        "zh": f"{spec.game_id} clean-room synthetic repairs",
                    },
                    "description": {
                        "en": "Clean-room synthetic composite debugging tasks with real-engine validation.",
                        "zh": "经过真实引擎验证的 clean-room synthetic 复合调试任务。",
                    },
                    "tasks": [],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        license_text = files("rhenium_authoring").joinpath("assets/Apache-2.0.txt").read_text()
        (root / "LICENSE").write_text(license_text, encoding="utf-8")
        if spec.runtime_id:
            runtime = self._runtime_catalog(spec)
            (root / "runtimes.json").write_text(
                json.dumps(runtime, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        self._install_pack_assets(root, spec)

    def _install_pack_assets(self, root: Path, spec: GameAuthoringSpec) -> None:
        """Pack-level trusted assets the game's runtime builder reads from the pack root."""
        if spec.game_id == "minecraft":
            core = self.benchmarks / _MINECRAFT_CORE
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            # The synth runtime builds the pinned Paper base image from the
            # pack's own private/runtime and private/harbor/harness trees.
            shutil.copytree(core / "private/runtime", root / "private/runtime", ignore=ignore)
            shutil.copytree(
                core / "private/harbor/harness", root / "private/harbor/harness", ignore=ignore
            )

    def _append(self, root: Path, spec: GameAuthoringSpec, bundle: SynthesisBundle) -> str:
        catalog_path = root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(catalog, dict) or not isinstance(catalog.get("tasks"), list):
            raise ValueError("synthetic catalog is invalid")
        if any(task.get("id") == bundle.candidate.id for task in catalog["tasks"]):
            raise ValueError("synthetic task ID is already published")

        task_stage = root / ".authoring-stage" / bundle.candidate.id
        task_target = root / "private" / "harbor" / bundle.candidate.id
        if task_stage.exists() or task_target.exists():
            raise ValueError("synthetic task asset target already exists")
        self._materialize_task(task_stage, spec, bundle)
        task_target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(task_stage, task_target)
        stage_parent = root / ".authoring-stage"
        if stage_parent.is_dir() and not any(stage_parent.iterdir()):
            stage_parent.rmdir()

        exam = root / "exams" / f"{bundle.candidate.id}.md"
        exam.parent.mkdir(parents=True, exist_ok=True)
        exam.write_text(bundle.prompt.markdown.rstrip() + "\n", encoding="utf-8")
        catalog["tasks"].append(self._catalog_task(spec, bundle))
        version = _next_minor(str(catalog.get("version", "0.0.0")))
        catalog["version"] = version
        temporary = catalog_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, catalog_path)
        if spec.runtime_id:
            runtimes_path = root / "runtimes.json"
            runtimes = json.loads(runtimes_path.read_text(encoding="utf-8"))
            runtimes.setdefault("task_bindings", {})[bundle.candidate.id] = [spec.runtime_id]
            temporary_runtime = runtimes_path.with_suffix(".json.tmp")
            temporary_runtime.write_text(
                json.dumps(runtimes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            os.replace(temporary_runtime, runtimes_path)
        return version

    def _materialize_task(
        self, root: Path, spec: GameAuthoringSpec, bundle: SynthesisBundle
    ) -> None:
        starter = root / "environment" / spec.starter_directory
        write_file_tree(starter, bundle.base.files)
        write_file_tree(root, bundle.verifier.files)
        self._install_trusted_assets(root, spec, bundle)
        write_file_tree(root / "solution" / "after", bundle.fixed.files)
        from .artifacts import gold_patch, source_digest

        (root / "solution").mkdir(exist_ok=True)
        (root / "solution" / "gold.patch").write_text(
            gold_patch(bundle.base.files, bundle.fixed.files), encoding="utf-8"
        )
        manifest = CleanRoomManifest(
            candidate_id=bundle.candidate.id,
            game_id=bundle.candidate.game_id,
            source_digest=source_digest(bundle),
            base_digest=f"sha256:{hash_tree(starter)}",
            fixed_digest=f"sha256:{hash_tree(root / 'solution' / 'after')}",
        )
        (root / "clean-room.json").write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        provenance = {
            "schema_version": 1,
            "clean_room_synthetic": True,
            "source_digest": source_digest(bundle),
            "sources": [
                {
                    "repository_url": str(fix.repository_url),
                    "license_spdx": fix.license_spdx,
                    "base_sha": fix.base_sha,
                    "fixed_sha": fix.fixed_sha,
                    "patch_sha256": hashlib.sha256(fix.patch.encode()).hexdigest(),
                    "base_context_sha256": hashlib.sha256(
                        json.dumps(fix.base_files, sort_keys=True).encode()
                    ).hexdigest(),
                    "fixed_context_sha256": hashlib.sha256(
                        json.dumps(fix.fixed_files, sort_keys=True).encode()
                    ).hexdigest(),
                }
                for fix in bundle.provenance
            ],
        }
        (root / "provenance.json").write_text(
            json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (root / "task.toml").write_text(
            'schema_version = "1.1"\n\n'
            "[task]\n"
            f'name = "gamecodebench/{bundle.candidate.id}"\n'
            'description = "Clean-room synthetic composite debugging task."\n'
            'authors = ["Rhenium clean-room authoring pipeline"]\n\n'
            "[metadata]\n"
            'category = "programming"\n'
            'tags = ["game-modding", "clean-room-synthetic", "composite", "bug-fix"]\n\n'
            "[verifier]\n"
            'network_mode = "no-network"\n',
            encoding="utf-8",
        )

    def _install_trusted_assets(
        self, root: Path, spec: GameAuthoringSpec, bundle: SynthesisBundle
    ) -> None:
        if spec.game_id == "stardew-valley":
            dockerfile_asset = files("rhenium_authoring").joinpath("assets/stardew.Dockerfile")
            (root / "environment").mkdir(exist_ok=True)
            (root / "environment" / "Dockerfile").write_text(
                dockerfile_asset.read_text(), encoding="utf-8"
            )
            harness = (
                self.benchmarks
                / "stardew-core/private/harbor/stardew-automate-zero-stack-output"
                / "environment/gcb-harness"
            )
            shutil.copytree(harness, root / "environment/gcb-harness")
        elif spec.game_id == "garrys-mod":
            trusted = (
                self.benchmarks
                / "darkrp-core/private/harbor/darkrp-release-regressions-v3"
            )
            (root / "environment").mkdir(exist_ok=True)
            trusted_dockerfile = (trusted / "environment/Dockerfile").read_text(encoding="utf-8")
            expected = "COPY darkrp /app/darkrp"
            if trusted_dockerfile.count(expected) != 1:
                raise ValueError("trusted Garry's Mod Dockerfile template changed")
            (root / "environment/Dockerfile").write_text(
                trusted_dockerfile.replace(expected, "COPY gamemode /app/darkrp"),
                encoding="utf-8",
            )
            shutil.copy2(
                trusted / "environment/agent-constraints.txt",
                root / "environment/agent-constraints.txt",
            )
            (root / "tests").mkdir(exist_ok=True)
            shutil.copy2(
                trusted / "tests/trusted_collector.py", root / "tests/trusted_collector.py"
            )
        elif spec.game_id == "isaac-rebirth":
            trusted = (
                self.benchmarks
                / "isaac-core/private/harbor/isaac-exodus-release-regressions"
                / "scripts/private-runtime.Dockerfile"
            )
            (root / "scripts").mkdir(exist_ok=True)
            shutil.copy2(trusted, root / "scripts/private-runtime.Dockerfile")
        elif spec.game_id == "minecraft":
            self._install_minecraft_assets(root, bundle)

    def _install_minecraft_assets(self, root: Path, bundle: SynthesisBundle) -> None:
        """The files materialize.py derives for a javac task, from the same templates."""
        harness = self.benchmarks / _MINECRAFT_HARNESS
        (root / "environment").mkdir(exist_ok=True)
        agent = (harness / "agent.Dockerfile.tmpl").read_text(encoding="utf-8")
        if agent.count("__WARM__\n") != 1:
            raise ValueError("trusted Minecraft agent Dockerfile template changed")
        # javac tasks warm no dependency cache; the placeholder line is dropped.
        (root / "environment/Dockerfile").write_text(
            agent.replace("__WARM__\n", ""), encoding="utf-8"
        )
        tests = root / "tests"
        tests.mkdir(exist_ok=True)
        verifier = (harness / "verifier.Dockerfile.tmpl").read_text(encoding="utf-8")
        if verifier.count("__WARM__\n") != 1 or verifier.count("__SUITE__\n") != 1:
            raise ValueError("trusted Minecraft verifier Dockerfile template changed")
        rendered = verifier.replace("__WARM__\n", "").replace(
            "__SUITE__\n", "COPY TaskSuite.java /tests/TaskSuite.java\n"
        )
        if not any(
            line.split()[:2] == ["FROM", _MINECRAFT_VERIFIER_BASE]
            for line in rendered.splitlines()
        ):
            raise ValueError("trusted Minecraft verifier template is not bound to the pinned base")
        (tests / "Dockerfile").write_text(rendered, encoding="utf-8")
        # The template copies tests/starter into the verifier image, as
        # materialize.py mirrors the starter tree for repository tasks; a javac
        # task restores nothing from it, but the build context must hold it.
        write_file_tree(tests / "starter", bundle.base.files)
        shutil.copy2(harness / "verify.py", tests / "verify.py")
        manifest = self._minecraft_manifest(bundle)
        (tests / "task.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        (root / "solution").mkdir(exist_ok=True)
        shutil.copy2(harness / "solve.sh", root / "solution/solve.sh")
        (root / "solution/solve.sh").chmod(0o755)
        (tests / "test.sh").chmod(0o755)
        # Reference copy of the trusted dependency-free build the verifier image
        # runs from /opt/gcb/javac-build.sh; the image copy is what executes.
        (root / "scripts").mkdir(exist_ok=True)
        shutil.copy2(
            self.benchmarks / _MINECRAFT_CORE / "private/runtime/javac-build.sh",
            root / "scripts/javac-build.sh",
        )

    @staticmethod
    def _minecraft_plugin_name(bundle: SynthesisBundle) -> str:
        """The plugin.yml registry name shared by the contract and both trees."""
        metadata = bundle.fixed.files.get("src/main/resources/plugin.yml", "")
        match = _PLUGIN_NAME_LINE.search(metadata)
        if match is None:
            raise ValueError("Minecraft synthetic project must declare plugin.yml name")
        name = match.group(1)
        contract = bundle.interface_contract
        if contract is not None and getattr(contract, "loader_identity", name) != name:
            raise ValueError("Minecraft plugin.yml name does not match the shared loader identity")
        return name

    def _minecraft_manifest(self, bundle: SynthesisBundle) -> dict[str, Any]:
        """tests/task.json in exactly the shape the Minecraft plugin freezes."""
        name = self._minecraft_plugin_name(bundle)
        return {
            "schemaVersion": 1,
            "taskId": bundle.candidate.id,
            "pluginName": name,
            "build": {
                "tool": "javac",
                "wrapper": True,
                "toolVersion": None,
                "module": None,
                "assemble": "",
                "test": None,
                "artifact": f"build/libs/{name}.jar",
                "javaRelease": 21,
                "frozenPaths": list(_MINECRAFT_FROZEN_PATHS),
            },
            "unitCases": [],
            "serverCases": list(bundle.verifier.case_ids),
            "hiddenUnitOverlay": False,
        }

    def _catalog_task(self, spec: GameAuthoringSpec, bundle: SynthesisBundle) -> dict[str, Any]:
        required = [
            f"{spec.starter_directory}/{name}"
            for name in sorted(bundle.base.files)
        ]
        common: dict[str, Any] = {
            "id": bundle.candidate.id,
            "difficulty": "hard",
            "title": {"en": "Anonymous release regressions", "zh": "匿名发布版本回归"},
            "summary": {
                "en": "Diagnose and repair every reported regression.",
                "zh": "诊断并修复全部报告的回归问题。",
            },
            "brief": {
                "en": "Repair the reported behavior while preserving unaffected paths.",
                "zh": "修复报告的行为，同时保持未受影响路径不变。",
            },
            "requirements": {
                "en": ["Fix root causes and preserve every unaffected behavior."],
                "zh": ["修复根因并保持所有未受影响行为。"],
            },
            "api_usage": {
                "en": ["Use only the pinned game's public mod APIs."],
                "zh": ["仅使用固定游戏版本的公开模组 API。"],
            },
            "acceptance": {
                "en": ["Every private real-engine assertion must pass without network access."],
                "zh": ["所有私有真实引擎断言必须在无网络环境中通过。"],
            },
            "domains": ["clean-room-synthetic", "composite-debugging", "real-game-runtime"],
            "estimated_minutes": 180,
            "required_files": required,
            "clean_room_synthetic": True,
        }
        if spec.game_id == "stardew-valley":
            common.update(
                task_kind="debugging",
                source_mod="Clean-room synthetic",
                game_version="1.6.15",
                smapi_version="4.1.10",
            )
        elif spec.game_id == "garrys-mod":
            common.update(
                task_kind="debugging",
                source_mod="Clean-room synthetic",
                source_commit="0" * 40,
            )
        elif spec.game_id == "isaac-rebirth":
            test_text = bundle.verifier.files["tests/test.sh"]
            match = _ISAAC_EXPECTED.search(test_text)
            if match is None:
                raise ValueError("Isaac verifier must declare expected=<count>")
            if int(match.group(1)) != 35:
                raise ValueError("Isaac synthetic verifier must preserve the 35-case runtime contract")
            names_match = re.search(
                r"^expected_cases=\(\n(?P<body>.*?)^\)$",
                test_text,
                re.MULTILINE | re.DOTALL,
            )
            names = (
                tuple(
                    line.strip()
                    for line in names_match.group("body").splitlines()
                    if line.strip()
                )
                if names_match is not None
                else ()
            )
            if len(names) != 35 or set(names) != set(bundle.verifier.case_ids):
                raise ValueError("Isaac verifier case names do not match its structured contract")
            common.update(
                source_mod="Clean-room synthetic",
                game_version="Afterbirth+ v1.06.T1",
                game_build="Steam App 250900 build 22878971",
                expected_cases=int(match.group(1)),
            )
        elif spec.game_id == "minecraft":
            name = self._minecraft_plugin_name(bundle)
            common.update(
                task_kind="repository-debugging",
                plugin_name=name,
                build={
                    "tool": "javac",
                    "assemble": "",
                    "test": None,
                    "artifact": f"build/libs/{name}.jar",
                },
                unit_cases=[],
                server_cases=list(bundle.verifier.case_ids),
                hidden_unit_overlay=False,
            )
        else:
            apis = [api for capsule in bundle.candidate.capsules for api in capsule.public_game_apis]
            patterns = [re.escape(api) for api in apis] or ["Add(?:PrefabPostInit|ModRPCHandler)"]
            lua_files = [name for name in sorted(bundle.base.files) if name.endswith(".lua")]
            common.update(
                core_module=lua_files[0],
                hidden_test=f"private/harbor/{bundle.candidate.id}/hidden.lua",
                server_test=f"private/harbor/{bundle.candidate.id}/server.lua",
                minimum_lua_lines=100,
                integration_checks=[
                    {
                        "id": "synthetic-game-api",
                        "label": {"en": "Required game integration", "zh": "必需游戏集成"},
                        "weight": 15,
                        "groups": [{"name": "public API", "any_of": patterns}],
                        "none_of": ["TODO", "IMPLEMENT\\s+ME"],
                    }
                ],
            )
            common["required_files"] = sorted(bundle.base.files)
        return common

    def _runtime_catalog(self, spec: GameAuthoringSpec) -> dict[str, Any]:
        source_pack = {
            "stardew-valley": "stardew-core",
            "isaac-rebirth": "isaac-core",
            "garrys-mod": "darkrp-core",
            "minecraft": _MINECRAFT_CORE,
        }[spec.game_id]
        source = json.loads(
            (self.benchmarks / source_pack / "runtimes.json").read_text(encoding="utf-8")
        )
        if len(source.get("runtimes", [])) != 1:
            raise ValueError("source runtime catalog must contain exactly one runtime")
        source["runtimes"][0]["id"] = spec.runtime_id
        source["task_bindings"] = {}
        return source

    @staticmethod
    def _validate_required_files(spec: GameAuthoringSpec, bundle: SynthesisBundle) -> None:
        missing_project = set(spec.project_requirements) - set(bundle.base.files)
        missing_fixed = set(spec.project_requirements) - set(bundle.fixed.files)
        missing_verifier = set(spec.verifier_requirements) - set(bundle.verifier.files)
        if missing_project or missing_fixed or missing_verifier:
            raise ValueError("candidate is missing required game authoring files")
        if set(bundle.base.files) != set(bundle.fixed.files):
            raise ValueError("clean-room base and fixed trees must contain the same files")
        verifier_paths = set(bundle.verifier.files)
        if spec.game_id == "dst":
            if any("/" in name for name in verifier_paths):
                raise ValueError("DST verifier files must stay at the private task root")
        elif any(not name.startswith("tests/") for name in verifier_paths):
            raise ValueError("generated verifier files must stay below the private tests directory")
        protected = _PROTECTED_ASSETS | _GAME_PROTECTED_ASSETS.get(spec.game_id, frozenset())
        if verifier_paths & protected or any(
            name.startswith("tests/starter/") for name in verifier_paths
        ):
            raise ValueError("generated verifier attempted to replace a trusted authoring asset")
        if spec.trusted_shell_runner is not None:
            test_text = bundle.verifier.files[spec.trusted_shell_runner]
            match = _EXPECTED.search(test_text)
            if match is None:
                raise ValueError("verifier must declare EXPECTED=<count>")
            if int(match.group(1)) != len(bundle.verifier.case_ids):
                raise ValueError("verifier expected count does not match its structured case IDs")
        if spec.project_path_prefixes:
            for tree in (bundle.base.files, bundle.fixed.files, *bundle.base.ablations.values()):
                if any(not path.startswith(spec.project_path_prefixes) for path in tree):
                    raise ValueError("synthetic project contains files outside the game's source layout")
        if spec.game_id == "stardew-valley":
            if not any(name.endswith(".csproj") for name in bundle.base.files):
                raise ValueError("Stardew synthetic project must include a C# project")
            if not any(name.endswith("manifest.json") for name in bundle.base.files):
                raise ValueError("Stardew synthetic project must include a SMAPI manifest")
        if spec.game_id == "isaac-rebirth":
            dockerfile = bundle.verifier.files["tests/Dockerfile"]
            if "ARG PRIVATE_IMAGE" not in dockerfile or "FROM ${PRIVATE_IMAGE}" not in dockerfile:
                raise ValueError("Isaac verifier must inherit the trusted private runtime argument")
        if spec.game_id == "minecraft":
            PackPublisher._minecraft_plugin_name(bundle)
            for tree in (bundle.base.files, bundle.fixed.files, *bundle.base.ablations.values()):
                if not any(
                    path.startswith("src/main/java/") and path.endswith(".java") for path in tree
                ):
                    raise ValueError("Minecraft synthetic project must include Java sources")


def _next_minor(raw: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", raw)
    if match is None:
        raise ValueError("catalog version is not semantic")
    major, minor, _patch = (int(value) for value in match.groups())
    return "1.0.0" if major == 0 else f"{major}.{minor + 1}.0"
