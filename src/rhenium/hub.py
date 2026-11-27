from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from . import __version__
from .auth import AuthManager
from .cli_agent_runner import CLI_AGENT_PROVIDERS, CliAgentRunner, cli_agent_model
from .config import Settings
from .core.auth import AuthProvider
from .core.catalog import BenchmarkCatalog, BenchmarkTask
from .core.evaluation import normalize_evaluation
from .core.evaluation_host import (
    DisposableEvaluationHost,
    EvaluationSecurityMode,
    HostEvaluationRequest,
    HostSecurityPolicy,
    evaluate_on_disposable_host,
    fail_closed_untrusted_evaluation,
    hash_untrusted_submission,
)
from .core.identity import PackKey, TaskKey
from .core.manifest import BenchmarkManifest, discover_manifest_paths
from .core.plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    EvaluationProfile,
    localized,
)
from .core.registry import discover_auth_providers, discover_evaluation_hosts, discover_plugins
from .core.runtime import RuntimeCatalog
from .database import Database, initialize_database
from .model_runner import ModelRunner
from .models import Attempt, Job, Run, Setting, Task, utcnow
from .runtime import RuntimeManager
from .util import hash_tree, json_dumps, json_loads


class JobCancelled(Exception):
    pass


def _utc_iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds") + "Z"


_PLATFORM_SCORING_RULE = (
    "The benchmark platform will run the private evaluator exactly once after you submit. "
    "Do not invoke score-exam, run-attempt, or any benchmark scorer yourself."
)


def run_dict(run: Run) -> dict[str, Any]:
    return {
        "id": run.id,
        "taskKey": run.task_key,
        "status": run.status,
        "phase": run.phase,
        "progress": run.progress,
        "score": run.score,
        "result": json_loads(run.result_json, {}),
        "error": run.error,
        "createdAt": _utc_iso(run.created_at),
        "updatedAt": _utc_iso(run.updated_at),
    }


def anonymous_run_dict(run: Run) -> dict[str, Any]:
    value = run_dict(run)
    value.pop("taskKey", None)
    return value


def job_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "taskKey": job.task_key,
        "kind": job.kind,
        "status": job.status,
        "phase": job.phase,
        "progress": job.progress,
        "result": json_loads(job.result_json, {}),
        "error": job.error,
        "cancelRequested": job.cancel_requested,
        "createdAt": _utc_iso(job.created_at),
        "updatedAt": _utc_iso(job.updated_at),
    }


@dataclass(frozen=True)
class LoadedBenchmark:
    key: PackKey
    manifest: BenchmarkManifest
    manifest_path: Path
    plugin: BenchmarkPlugin
    catalog: BenchmarkCatalog
    evaluator: EvaluationBackend
    context: BenchmarkContext
    runtime_catalog: RuntimeCatalog | None = None

    def task(self, local_task_id: str) -> BenchmarkTask:
        for task in self.catalog.tasks:
            if task.id == local_task_id:
                return task
        raise KeyError(str(TaskKey(self.key.game_id, self.key.pack_id, local_task_id)))


class BenchmarkHub:
    """Game-neutral orchestration over all discovered plugins and benchmark packs."""

    def __init__(
        self,
        settings: Settings | None = None,
        database: Database | None = None,
        *,
        plugins: dict[str, BenchmarkPlugin] | None = None,
        auth_providers: dict[str, AuthProvider] | None = None,
        evaluation_hosts: dict[str, DisposableEvaluationHost] | None = None,
        manifest_paths: tuple[Path, ...] | None = None,
        discovery_errors: list[dict[str, str]] | None = None,
    ) -> None:
        self.settings = settings or Settings.load()
        self.database = database or initialize_database(self.settings)
        if plugins is None:
            self.plugins, plugin_errors = discover_plugins()
        else:
            self.plugins = dict(plugins)
            plugin_errors = []
        if auth_providers is None:
            self.auth_providers, auth_errors = discover_auth_providers()
        else:
            self.auth_providers = dict(auth_providers)
            auth_errors = []
        if evaluation_hosts is None:
            self.evaluation_hosts, host_errors = discover_evaluation_hosts()
        else:
            self.evaluation_hosts = dict(evaluation_hosts)
            host_errors = []
        self.discovery_errors = [
            *plugin_errors,
            *auth_errors,
            *host_errors,
            *(discovery_errors or []),
        ]
        self.auth = AuthManager(self.database, self.auth_providers)
        self.runtime_manager = RuntimeManager(
            self.settings,
            self.database,
            self.auth,
            self.auth_providers,
        )
        self.benchmarks: dict[PackKey, LoadedBenchmark] = {}
        self.tasks: dict[TaskKey, tuple[LoadedBenchmark, BenchmarkTask]] = {}
        self.model_runner = ModelRunner()
        self.cli_agent_runner = CliAgentRunner()
        self._catalog_lock = threading.Lock()
        selected_manifests = (
            manifest_paths
            if manifest_paths is not None
            else discover_manifest_paths(self.settings.benchmark_paths)
        )
        self._load_benchmarks(selected_manifests)
        self._load_runtimes()
        self._sync_catalogs()

    @property
    def task_keys(self) -> tuple[str, ...]:
        return tuple(str(key) for key in sorted(self.tasks))

    def _issue(self, kind: str, identifier: str, message: str) -> None:
        self.discovery_errors.append({"kind": kind, "id": identifier, "message": message})

    def _load_benchmarks(self, manifest_paths: tuple[Path, ...]) -> None:
        candidates: dict[PackKey, list[LoadedBenchmark]] = {}
        for manifest_path in manifest_paths:
            label = manifest_path.as_posix()
            try:
                manifest = BenchmarkManifest.load(manifest_path)
                plugin = self.plugins.get(manifest.plugin)
                if plugin is None:
                    raise LookupError(f"required plugin is not installed: {manifest.plugin}")
                pack_root = manifest_path.resolve().parent
                catalog = plugin.load_catalog(pack_root, manifest.catalog)
                if catalog.game != plugin.game_id:
                    raise ValueError(
                        f"catalog game {catalog.game!r} does not match plugin game {plugin.game_id!r}"
                    )
                key = PackKey(plugin.game_id, manifest.pack_id)
                context = BenchmarkContext(
                    project_root=self.settings.root.resolve(),
                    pack_root=pack_root,
                    state_dir=self.settings.state_dir / "packs" / key.game_id / key.pack_id,
                    cache_dir=self.settings.cache_dir / "plugins" / key.game_id / key.pack_id,
                )
                evaluator = plugin.create_evaluator(context)
                runtime_catalog = (
                    RuntimeCatalog.load(pack_root, manifest.runtime_catalog)
                    if manifest.runtime_catalog is not None
                    else None
                )
                loaded = LoadedBenchmark(
                    key=key,
                    manifest=manifest,
                    manifest_path=manifest_path.resolve(),
                    plugin=plugin,
                    catalog=catalog,
                    evaluator=evaluator,
                    context=context,
                    runtime_catalog=runtime_catalog,
                )
                candidates.setdefault(key, []).append(loaded)
            except Exception as error:
                self._issue("pack", label, str(error))

        for key, matches in sorted(candidates.items()):
            if len(matches) != 1:
                for match in matches:
                    self._issue(
                        "pack",
                        match.manifest_path.as_posix(),
                        f"duplicate benchmark pack key: {key}",
                    )
                continue
            loaded = matches[0]
            proposed = [TaskKey(key.game_id, key.pack_id, task.id) for task in loaded.catalog.tasks]
            conflicts = [task_key for task_key in proposed if task_key in self.tasks]
            if conflicts:
                self._issue(
                    "pack",
                    loaded.manifest_path.as_posix(),
                    f"duplicate task keys: {', '.join(map(str, conflicts))}",
                )
                continue
            self.benchmarks[key] = loaded
            for task_key, task in zip(proposed, loaded.catalog.tasks, strict=True):
                self.tasks[task_key] = (loaded, task)

    def _load_runtimes(self) -> None:
        for key, loaded in sorted(self.benchmarks.items()):
            catalog = loaded.runtime_catalog
            if catalog is None:
                continue
            known_tasks = {task.id for task in loaded.catalog.tasks}
            unknown = set(catalog.task_bindings) - known_tasks
            if unknown:
                self._issue(
                    "runtime",
                    str(key),
                    f"runtime bindings reference unknown tasks: {sorted(unknown)}",
                )
                continue
            by_runtime: dict[str, list[str]] = {spec.id: [] for spec in catalog.runtimes}
            for task_id, runtime_ids in catalog.task_bindings.items():
                task_key = str(TaskKey(key.game_id, key.pack_id, task_id))
                for runtime_id in runtime_ids:
                    by_runtime[runtime_id].append(task_key)
            try:
                for spec in catalog.runtimes:
                    self.runtime_manager.register(
                        game_id=key.game_id,
                        plugin=loaded.plugin,
                        context=loaded.context,
                        spec=spec,
                        tasks=tuple(by_runtime[spec.id]),
                    )
            except Exception as error:
                self._issue("runtime", str(key), str(error))

    def _sync_catalogs(self) -> None:
        with self._catalog_lock:
            failed: set[PackKey] = set()
            for key, loaded in tuple(self.benchmarks.items()):
                try:
                    self._sync_benchmark(loaded)
                except Exception as error:
                    failed.add(key)
                    self._issue("pack", str(key), f"failed to materialize public assets: {error}")
            for key in failed:
                self.benchmarks.pop(key, None)
                for task_key in tuple(self.tasks):
                    if task_key.pack_key == key:
                        self.tasks.pop(task_key)
            current_keys = set(self.task_keys)
            with self.database.session_factory() as session:
                rows = session.scalars(select(Task)).all()
                for row in rows:
                    if row.task_key not in current_keys:
                        row.status = "archived"
                session.commit()

    def _sync_benchmark(self, loaded: LoadedBenchmark) -> None:
        workspace_root = loaded.context.state_dir / "workspaces"
        workspace_root.mkdir(parents=True, exist_ok=True)
        loaded.context.cache_dir.mkdir(parents=True, exist_ok=True)
        with self.database.session_factory() as session:
            for task in loaded.catalog.tasks:
                key = TaskKey(loaded.key.game_id, loaded.key.pack_id, task.id)
                workspace = workspace_root / task.id
                loaded.plugin.materialize_starter(task, workspace, loaded.context)
                row = session.get(Task, str(key))
                if row is None:
                    row = Task(
                        task_key=str(key),
                        game_id=key.game_id,
                        pack_id=key.pack_id,
                        local_task_id=key.task_id,
                        catalog_id=loaded.catalog.id,
                        catalog_version=loaded.catalog.version,
                        requirement=loaded.plugin.task_prompt(task),
                        workspace_path=str(workspace),
                        starter_hash=hash_tree(workspace),
                    )
                    session.add(row)
                row.game_id = key.game_id
                row.pack_id = key.pack_id
                row.local_task_id = key.task_id
                row.catalog_id = loaded.catalog.id
                row.catalog_version = loaded.catalog.version
                row.status = "ready"
                row.difficulty = task.difficulty
                row.archetype = task.domains[0] if task.domains else "systems"
                row.title = str(localized(task.title, "en"))
                row.requirement = loaded.plugin.task_prompt(task)
                row.workspace_path = str(workspace)
                row.starter_hash = hash_tree(workspace)
                row.mutation_json = "{}"
                row.rubric_json = json_dumps(
                    {
                        "catalog": loaded.catalog.id,
                        "task": task.id,
                        "version": loaded.catalog.version,
                    }
                )
            session.commit()
        self._write_public_manifest(loaded)

    def _write_public_manifest(self, loaded: LoadedBenchmark) -> Path:
        public = loaded.context.state_dir / "public"
        public.mkdir(parents=True, exist_ok=True)
        payload = {
            "gameId": loaded.key.game_id,
            "packId": loaded.key.pack_id,
            "catalog": loaded.catalog.id,
            "version": loaded.catalog.version,
            "plugin": loaded.plugin.id,
            "taskCount": len(loaded.catalog.tasks),
            "tasks": [
                {
                    "key": str(TaskKey(loaded.key.game_id, loaded.key.pack_id, task.id)),
                    "taskId": task.id,
                    **loaded.plugin.public_task(task),
                }
                for task in loaded.catalog.tasks
            ],
        }
        path = public / "tasks.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def _loaded_task(self, task_key: str | TaskKey) -> tuple[TaskKey, LoadedBenchmark, BenchmarkTask]:
        key = task_key if isinstance(task_key, TaskKey) else TaskKey.parse(task_key)
        try:
            loaded, task = self.tasks[key]
        except KeyError as error:
            raise KeyError(str(key)) from error
        return key, loaded, task

    @staticmethod
    def _profiles(loaded: LoadedBenchmark, task: BenchmarkTask) -> dict[str, EvaluationProfile]:
        profiles = loaded.plugin.evaluation_profiles(task)
        indexed = {profile.id: profile for profile in profiles}
        if len(indexed) != len(profiles) or not indexed:
            raise ValueError(f"plugin {loaded.plugin.id} returned invalid evaluation profiles")
        return indexed

    def _profile(
        self,
        loaded: LoadedBenchmark,
        task: BenchmarkTask,
        requested: str | None,
    ) -> EvaluationProfile:
        profiles = self._profiles(loaded, task)
        profile_id = requested or loaded.plugin.default_profile(task)
        try:
            return profiles[profile_id]
        except KeyError as error:
            choices = ", ".join(sorted(profiles))
            raise ValueError(
                f"unknown evaluation profile {profile_id!r}; choose one of: {choices}"
            ) from error

    def validate_task_profile(self, task_key: str, profile: str | None) -> str:
        """Validate a public task/profile request before scheduling asynchronous work."""
        _key, loaded, task = self._loaded_task(task_key)
        return self._profile(loaded, task, profile).id

    def health(self) -> dict[str, Any]:
        packs = self.list_packs()
        degraded_items = [
            {
                "kind": "runtime",
                "id": str(pack["key"]),
                "message": str(
                    pack["runtime"].get("error") or pack["runtime"].get("reason") or "runtime is unavailable"
                ),
            }
            for pack in packs
            if not bool(pack["runtime"].get("available", False))
        ]
        return {
            # Discovery and runtime failures are isolated; the Hub itself remains responsive.
            "ok": True,
            "degraded": bool(self.discovery_errors or degraded_items),
            "version": __version__,
            "pluginCount": len(self.plugins),
            "authProviderCount": len(self.auth_providers),
            "evaluationHostCount": len(self.evaluation_hosts),
            "packCount": len(self.benchmarks),
            "taskCount": len(self.tasks),
            "plugins": self.list_games(),
            "packs": packs,
            "degradedItems": degraded_items,
            "discoveryErrors": list(self.discovery_errors),
        }

    @staticmethod
    def _security_mode(value: str | EvaluationSecurityMode) -> EvaluationSecurityMode:
        try:
            return EvaluationSecurityMode(value)
        except ValueError as error:
            choices = ", ".join(item.value for item in EvaluationSecurityMode)
            raise ValueError(
                f"unknown evaluation security mode {value!r}; choose one of: {choices}"
            ) from error

    def list_evaluation_hosts(self) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for provider in sorted(self.evaluation_hosts.values(), key=lambda item: item.id):
            try:
                capability = provider.doctor().model_dump(mode="json")
            except Exception:
                capability = {
                    "available": False,
                    "disposable": False,
                    "platform": "unknown",
                    "reason": "evaluation host doctor failed",
                }
            values.append(
                {
                    **provider.descriptor.model_dump(mode="json"),
                    "capability": capability,
                }
            )
        return values

    def evaluation_host_doctor(self, provider_id: str) -> dict[str, Any]:
        try:
            provider = self.evaluation_hosts[provider_id]
        except KeyError as error:
            raise KeyError(f"evaluation host provider is not installed: {provider_id}") from error
        return {
            "provider": provider.descriptor.model_dump(mode="json"),
            "capability": provider.doctor().model_dump(mode="json"),
        }

    def list_games(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for plugin in sorted(self.plugins.values(), key=lambda item: item.game_id):
            packs = [loaded for key, loaded in self.benchmarks.items() if key.game_id == plugin.game_id]
            result.append(
                {
                    **plugin.descriptor.model_dump(mode="json"),
                    "packs": [str(loaded.key) for loaded in sorted(packs, key=lambda item: item.key)],
                    "taskCount": sum(len(loaded.catalog.tasks) for loaded in packs),
                }
            )
        return result

    def list_packs(self, game_id: str | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for key, loaded in sorted(self.benchmarks.items()):
            if game_id and key.game_id != game_id:
                continue
            if loaded.runtime_catalog is not None:
                runtime_ids = {spec.id for spec in loaded.runtime_catalog.runtimes}
                managed = [
                    item for item in self.runtime_manager.list(key.game_id) if item["id"] in runtime_ids
                ]
                required = {runtime_id for bindings in loaded.runtime_catalog.task_bindings.values()
                            for runtime_id in bindings} or runtime_ids
                ready = {item["id"] for item in managed if item["ready"]}
                available = bool(required) and required.issubset(ready)
                runtime = {
                    "id": "managed",
                    "available": available,
                    "runtimes": managed,
                    "reason": None
                    if available
                    else "one or more licensed runtimes require explicit preparation",
                }
            else:
                try:
                    runtime = loaded.evaluator.runtime_status()
                except Exception as error:
                    runtime = {"available": False, "error": str(error)}
            result.append(
                {
                    "key": str(key),
                    "gameId": key.game_id,
                    "packId": key.pack_id,
                    "pluginId": loaded.plugin.id,
                    "catalog": loaded.catalog.id,
                    "version": loaded.catalog.version,
                    "taskCount": len(loaded.catalog.tasks),
                    "runtime": runtime,
                    "manifest": str(loaded.context.state_dir / "public" / "tasks.json"),
                }
            )
        return result

    def list_tasks(
        self,
        language: str = "en",
        *,
        game_id: str | None = None,
        pack_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.database.session_factory() as session:
            result: list[dict[str, Any]] = []
            for key, (loaded, task) in sorted(self.tasks.items()):
                if game_id and key.game_id != game_id:
                    continue
                if pack_id and key.pack_id != pack_id:
                    continue
                latest = session.scalar(
                    select(Run).where(Run.task_key == str(key)).order_by(Run.created_at.desc()).limit(1)
                )
                profiles = self._profiles(loaded, task)
                result.append(
                    {
                        "key": str(key),
                        "gameId": key.game_id,
                        "packId": key.pack_id,
                        "taskId": key.task_id,
                        "difficulty": task.difficulty,
                        "title": localized(task.title, language),
                        "summary": localized(task.summary, language),
                        "brief": localized(task.brief, language),
                        "requirements": localized(task.requirements, language),
                        "apiUsage": localized(task.api_usage, language),
                        "acceptanceCriteria": localized(task.acceptance, language),
                        "domains": task.domains,
                        "estimatedMinutes": task.estimated_minutes,
                        "profiles": [value.model_dump(mode="json") for value in profiles.values()],
                        "defaultProfile": loaded.plugin.default_profile(task),
                        "latestRun": run_dict(latest) if latest else None,
                    }
                )
        return result

    def select_task_keys(self, selector: str) -> list[str]:
        """Return the canonical keys of one game, one game/pack, or one game/pack/task."""
        parts = selector.split("/")
        if not 1 <= len(parts) <= 3 or not all(parts):
            raise ValueError("select a game, a game/pack, or a game/pack/task")
        keys = [
            str(key)
            for key in sorted(self.tasks)
            if [key.game_id, key.pack_id, key.task_id][: len(parts)] == parts
        ]
        if not keys:
            raise ValueError(f"no task matches {selector}")
        return keys

    def prepare_attempt(
        self,
        task_key: str,
        path: Path,
        mode: str,
        score_command: Path | None,
    ) -> dict[str, Any]:
        """Materialize an anonymous attempt; without a scorer the platform scores it once."""
        key, loaded, task = self._loaded_task(task_key)
        if mode not in {"strict", "practice"}:
            raise ValueError("mode must be strict or practice")
        if score_command is None and mode != "strict":
            raise ValueError("an attempt scored by the platform must use strict mode")
        raw = path.expanduser()
        if raw.is_symlink():
            raise ValueError("attempt path must not be a symbolic link")
        parent = raw.parent.resolve(strict=True)
        if not parent.is_dir():
            raise ValueError("attempt parent must be a directory")
        destination = parent / raw.name
        resolved_destination = destination.resolve()
        private_roots = {
            self.settings.root.resolve(),
            *(item.context.pack_root for item in self.benchmarks.values()),
        }
        for private_root in private_roots:
            if resolved_destination == private_root or resolved_destination.is_relative_to(private_root):
                raise ValueError("attempt path must be outside benchmark code and pack directories")
            if private_root.is_relative_to(resolved_destination):
                raise ValueError("attempt path must not contain benchmark code or pack directories")
        if destination.exists():
            if not destination.is_dir():
                raise ValueError("attempt path is not a directory")
            if next(destination.iterdir(), None) is not None:
                raise ValueError("attempt directory is not empty")
        else:
            destination.mkdir()
        destination = destination.resolve(strict=True)

        loaded.plugin.materialize_attempt(task, destination, loaded.context)
        if score_command is None:
            prompt = (
                "# Rhenium agent task\n\n"
                "Solve the exam in `EXAM.md` from scratch.\n\n"
                f"- Mode: `{mode}`\n\n"
                "Follow `AGENTS.md` and `CLAUDE.md`. Work only in the current attempt directory. "
                "Do not inspect benchmark code, packs, evaluators, private assertions, or prior runs.\n\n"
                "Implement every required file and behavior. Review the full exam, remove placeholders, "
                "and perform any public checks available inside this directory.\n\n"
                f"{_PLATFORM_SCORING_RULE}\n\n"
                "Finish with a short summary of the files you created. Do not guess any hidden "
                "identifier or task number.\n"
            )
        else:
            scoring_rule = (
                "Run the scorer exactly once after the implementation is complete. Do not edit files "
                "after scoring."
                if mode == "strict"
                else "You may rerun the scorer and improve the submission from its report. Keep all "
                "benchmark internals private."
            )
            resolved_scorer = score_command.resolve()
            if resolved_scorer.suffix.casefold() == ".ps1":
                score_block = f'```powershell\n& "{resolved_scorer}" (Get-Location).Path\n```'
            else:
                score_block = f'```sh\n"{resolved_scorer}" "$PWD"\n```'
            prompt = (
                "# Rhenium agent task\n\n"
                "Solve the exam in `EXAM.md` from scratch.\n\n"
                f"- Mode: `{mode}`\n\n"
                "Follow `AGENTS.md` and `CLAUDE.md`. Work only in the current attempt directory. "
                "Do not inspect benchmark code, packs, evaluators, private assertions, or prior runs; "
                "the only permitted interaction is executing the approved scoring wrapper.\n\n"
                "Implement every required file and behavior. Review the full exam, remove placeholders, "
                "and perform any public checks available inside this directory before scoring.\n\n"
                f"{scoring_rule}\n\n"
                "Use this scoring command:\n\n"
                f"{score_block}\n\n"
                f"Finish by reporting the {loaded.plugin.completion_report_fields()}. Do not guess any "
                "hidden identifier or task number.\n"
            )
        (destination / "PROMPT.md").write_text(prompt, encoding="utf-8")
        forbidden = {str(key), key.task_id, str(loaded.key)}
        for public_file in destination.rglob("*"):
            relative = public_file.relative_to(destination).as_posix()
            if any(value in relative for value in forbidden):
                raise ValueError(f"attempt material contains an internal identifier: {relative}")
            if public_file.is_symlink():
                raise ValueError(f"attempt material must not contain symbolic links: {relative}")
            if not public_file.is_file():
                continue
            content = public_file.read_text(encoding="utf-8", errors="replace")
            if any(value in content for value in forbidden):
                raise ValueError(f"attempt material contains an internal identifier: {relative}")
        registration = self.register_attempt(str(key), destination, mode)
        return {
            "attemptId": registration["attemptId"],
            "path": registration["path"],
            "mode": registration["mode"],
        }

    def register_attempt(self, task_key: str, path: Path, mode: str) -> dict[str, Any]:
        key, _loaded, _task = self._loaded_task(task_key)
        if mode not in {"strict", "practice"}:
            raise ValueError("mode must be strict or practice")
        attempt_path = path.expanduser().resolve(strict=True)
        if not attempt_path.is_dir() or path.expanduser().is_symlink():
            raise ValueError("attempt path must be a real directory")
        private_roots = {
            self.settings.root.resolve(),
            *(item.context.pack_root for item in self.benchmarks.values()),
        }
        for private_root in private_roots:
            if attempt_path == private_root or attempt_path.is_relative_to(private_root):
                raise ValueError("attempt path must be outside benchmark code and pack directories")
            if private_root.is_relative_to(attempt_path):
                raise ValueError("attempt path must not contain benchmark code or pack directories")
        with self.database.session_factory() as session:
            existing = session.scalar(select(Attempt).where(Attempt.path == str(attempt_path)))
            if existing is not None:
                if existing.task_key != str(key) or existing.mode != mode:
                    raise ValueError("attempt path is already registered for another run")
                return {"attemptId": existing.id, "path": existing.path, "mode": existing.mode}
            attempt = Attempt(
                id=f"attempt-{uuid.uuid4().hex[:20]}",
                task_key=str(key),
                path=str(attempt_path),
                mode=mode,
            )
            session.add(attempt)
            session.commit()
            return {"attemptId": attempt.id, "path": attempt.path, "mode": attempt.mode}

    def _registered_attempt(self, submission: Path) -> tuple[Path, str]:
        raw = submission.expanduser()
        if raw.is_symlink():
            raise ValueError("registered attempt must not be a symbolic link")
        resolved = raw.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("registered attempt must be a directory")
        with self.database.session_factory() as session:
            attempt = session.scalar(select(Attempt).where(Attempt.path == str(resolved)))
            if attempt is None:
                raise ValueError("submission directory is not a registered anonymous attempt")
            task_key = attempt.task_key
        return resolved, task_key

    def evaluate_attempt(
        self,
        submission: Path,
        profile: str | None = None,
        *,
        security_mode: str | EvaluationSecurityMode = EvaluationSecurityMode.HONEST,
        host_provider: str | None = None,
        host_image: str | None = None,
    ) -> dict[str, Any]:
        resolved, task_key = self._registered_attempt(submission)
        key, loaded, _task = self._loaded_task(task_key)
        result = self.evaluate_task(
            task_key,
            resolved,
            profile=profile,
            security_mode=security_mode,
            host_provider=host_provider,
            host_image=host_image,
        )
        return self._redact_anonymous(result, key, loaded)

    def _redact_anonymous(
        self,
        value: Any,
        key: TaskKey,
        loaded: LoadedBenchmark,
    ) -> Any:
        value = loaded.plugin.sanitize_anonymous_result(value)
        omitted_keys = {
            "gameId",
            "hostAttestation",
            "logPath",
            "manifest",
            "packId",
            "taskId",
            "taskKey",
            "trajectoryPath",
            "workspacePath",
        }
        replacements = sorted(
            {
                str(loaded.context.pack_root),
                str(loaded.context.state_dir),
                str(loaded.context.cache_dir),
                str(key),
                str(loaded.key),
                key.task_id,
            },
            key=len,
            reverse=True,
        )

        def redact(item: Any) -> Any:
            if isinstance(item, dict):
                return {
                    field: redact(field_value)
                    for field, field_value in item.items()
                    if field not in omitted_keys
                }
            if isinstance(item, list):
                return [redact(entry) for entry in item]
            if isinstance(item, tuple):
                return tuple(redact(entry) for entry in item)
            if isinstance(item, str):
                for private in replacements:
                    item = item.replace(private, "[redacted]")
            return item

        return redact(value)

    def evaluate_task(
        self,
        task_key: str,
        submission: Path,
        profile: str | None = None,
        *,
        security_mode: str | EvaluationSecurityMode = EvaluationSecurityMode.HONEST,
        host_provider: str | None = None,
        host_image: str | None = None,
    ) -> dict[str, Any]:
        key, loaded, task = self._loaded_task(task_key)
        selected_profile = self._profile(loaded, task, profile)
        selected_security_mode = self._security_mode(security_mode)
        if selected_security_mode is EvaluationSecurityMode.HONEST and (
            host_provider is not None or host_image is not None
        ):
            raise ValueError("host provider options require --security-mode untrusted")
        submission = submission.expanduser().resolve()
        if not submission.is_dir():
            raise FileNotFoundError(submission)
        run_id = f"run-{uuid.uuid4().hex[:16]}"
        with self.database.session_factory() as session:
            run = Run(
                id=run_id,
                task_key=str(key),
                submission_path=str(submission),
                status="running",
                phase="evaluation",
                progress=20,
            )
            session.add(run)
            session.commit()
        try:
            if selected_security_mode is EvaluationSecurityMode.UNTRUSTED:
                if host_provider is None:
                    raw_result = fail_closed_untrusted_evaluation(None, "provider-not-selected")
                elif re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", host_provider) is None:
                    raw_result = fail_closed_untrusted_evaluation(None, "provider-id-invalid")
                elif host_image is None or not host_image.strip():
                    raw_result = fail_closed_untrusted_evaluation(
                        host_provider, "image-identity-not-selected"
                    )
                elif (
                    re.fullmatch(
                        r"[a-z0-9][a-z0-9+.-]*:[A-Za-z0-9][A-Za-z0-9._:/-]{6,}",
                        host_image,
                    )
                    is None
                ):
                    raw_result = fail_closed_untrusted_evaluation(host_provider, "image-identity-invalid")
                else:
                    provider = self.evaluation_hosts.get(host_provider)
                    policy = HostSecurityPolicy()
                    try:
                        submission_identity = hash_untrusted_submission(
                            submission,
                            maximum_files=policy.maximum_submission_files,
                            maximum_bytes=policy.maximum_submission_bytes,
                        )
                        request = HostEvaluationRequest(
                            run_id=run_id,
                            nonce=uuid.uuid4().hex,
                            task_key=str(key),
                            submission=submission,
                            submission_identity=submission_identity,
                            profile=selected_profile.id,
                            expected_image_identity=host_image,
                            policy=policy,
                        )
                    except (OSError, ValueError):
                        raw_result = fail_closed_untrusted_evaluation(
                            host_provider, "submission-input-invalid"
                        )
                    else:
                        raw_result = evaluate_on_disposable_host(provider, request)
            else:
                runtime_artifacts = self.runtime_manager.artifacts_for_task(
                    str(key), required=selected_profile.complete_eligible
                )
                if runtime_artifacts:
                    raw_result = loaded.evaluator.evaluate(
                        submission,
                        task,
                        profile=selected_profile.id,
                        runtimes=runtime_artifacts,
                    )
                else:
                    raw_result = loaded.evaluator.evaluate(submission, task, profile=selected_profile.id)
                raw_result = {
                    **raw_result,
                    "security": {
                        "mode": EvaluationSecurityMode.HONEST.value,
                        "attested": False,
                        "disposableHost": False,
                    },
                }
            if not selected_profile.complete_eligible:
                raw_result = {**raw_result, "complete": False, "passed": False}
            result = normalize_evaluation(raw_result)
            result["profile"] = selected_profile.id
            log_dir = self.settings.state_dir / "runs" / run_id
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "runtime.log"
            runtime_log = result.pop("runtime_log", "")
            log_path.write_text(str(runtime_log), encoding="utf-8")
            with self.database.session_factory() as session:
                current = session.get(Run, run_id)
                assert current
                current.status = "passed" if result["passed"] else "failed"
                current.phase = "complete"
                current.progress = 100
                current.score = float(result["score"])
                current.result_json = json_dumps(result)
                current.log_path = str(log_path)
                session.commit()
                return run_dict(current)
        except Exception as error:
            with self.database.session_factory() as session:
                current = session.get(Run, run_id)
                assert current
                current.status = "error"
                current.phase = "error"
                current.error = str(error)
                session.commit()
            raise

    def list_runs(self, task_key: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = select(Run).order_by(Run.created_at.desc()).limit(max(1, min(limit, 500)))
        if task_key:
            key, _loaded, _task = self._loaded_task(task_key)
            query = query.where(Run.task_key == str(key))
        else:
            query = query.where(Run.task_key.in_(self.task_keys))
        with self.database.session_factory() as session:
            return [run_dict(run) for run in session.scalars(query).all()]

    def evaluate_model(
        self,
        task_key: str,
        profile: str | None = None,
        progress: Callable[[int, str], None] | None = None,
        *,
        security_mode: str | EvaluationSecurityMode = EvaluationSecurityMode.HONEST,
        host_provider: str | None = None,
        host_image: str | None = None,
    ) -> dict[str, Any]:
        key, loaded, task = self._loaded_task(task_key)
        progress = progress or (lambda _value, _phase: None)
        configuration = self._configured_model()
        with self.database.session_factory() as session:
            row = session.get(Task, str(key))
            if row is None:
                raise KeyError(str(key))
            starter = Path(row.workspace_path)
            requirement = row.requirement
        if not starter.is_dir():
            raise FileNotFoundError(starter)

        model_run_id = f"model-{uuid.uuid4().hex[:16]}"
        run_root = self.settings.state_dir / "model-runs" / model_run_id
        workspace = run_root / "workspace"
        run_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(starter, workspace)
        model_metadata = self._run_model_in_workspace(
            loaded,
            task,
            workspace,
            requirement,
            configuration,
            model_run_id,
            progress,
        )
        progress(88, "running private evaluation")
        evaluation = self.evaluate_task(
            str(key),
            workspace,
            profile=profile,
            security_mode=security_mode,
            host_provider=host_provider,
            host_image=host_image,
        )
        evaluation = self._attach_model_metadata(evaluation, model_metadata)
        progress(100, "complete")
        return {**model_metadata, "taskKey": str(key), "evaluation": evaluation}

    def solve_attempt(
        self,
        submission: Path,
        profile: str | None = None,
        progress: Callable[[int, str], None] | None = None,
        *,
        security_mode: str | EvaluationSecurityMode = EvaluationSecurityMode.HONEST,
        host_provider: str | None = None,
        host_image: str | None = None,
    ) -> dict[str, Any]:
        workspace, task_key = self._registered_attempt(submission)
        key, loaded, task = self._loaded_task(task_key)
        progress = progress or (lambda _value, _phase: None)
        configuration = self._configured_model()
        model_run_id = f"model-{uuid.uuid4().hex[:16]}"
        system_prompt = f"{loaded.plugin.agent_system_prompt(task)} {_PLATFORM_SCORING_RULE}"
        model_metadata = self._run_model_in_workspace(
            loaded,
            task,
            workspace,
            loaded.plugin.task_prompt(task),
            configuration,
            model_run_id,
            progress,
            system_prompt=system_prompt,
        )
        progress(88, "running private evaluation")
        evaluation = self.evaluate_attempt(
            workspace,
            profile=profile,
            security_mode=security_mode,
            host_provider=host_provider,
            host_image=host_image,
        )
        evaluation = self._attach_model_metadata(evaluation, model_metadata, anonymous=True)
        progress(100, "complete")
        return self._redact_anonymous({**model_metadata, "evaluation": evaluation}, key, loaded)

    def run_agent_attempt(
        self,
        submission: Path,
        provider: str,
        profile: str | None = None,
        progress: Callable[[int, str], None] | None = None,
        *,
        security_mode: str | EvaluationSecurityMode = EvaluationSecurityMode.HONEST,
        host_provider: str | None = None,
        host_image: str | None = None,
    ) -> dict[str, Any]:
        """Let the chosen agent provider solve a registered attempt, then evaluate it once."""
        if provider == "api":
            return self.solve_attempt(
                submission,
                profile,
                progress,
                security_mode=security_mode,
                host_provider=host_provider,
                host_image=host_image,
            )
        if provider not in CLI_AGENT_PROVIDERS:
            raise ValueError("provider must be api, codex, or claude")
        workspace, task_key = self._registered_attempt(submission)
        key, loaded, task = self._loaded_task(task_key)
        progress = progress or (lambda _value, _phase: None)
        prompt_file = workspace / "PROMPT.md"
        prompt = (
            prompt_file.read_text(encoding="utf-8")
            if prompt_file.is_file()
            else loaded.plugin.task_prompt(task)
        ).rstrip()
        if _PLATFORM_SCORING_RULE not in prompt:
            prompt = f"{prompt}\n\n{_PLATFORM_SCORING_RULE}"
        model_run_id = f"model-{uuid.uuid4().hex[:16]}"
        run_root = self.settings.state_dir / "model-runs" / model_run_id
        run_root.mkdir(parents=True, exist_ok=True)
        trajectory_path = run_root / "trajectory.jsonl"
        agent_result = self.cli_agent_runner.run(
            provider,
            workspace,
            f"{prompt}\n",
            trajectory_path,
            progress=progress,
        )
        model_metadata = {
            "modelRunId": model_run_id,
            "model": cli_agent_model(provider, os.environ),
            **agent_result,
            "trajectoryPath": str(trajectory_path),
        }
        progress(88, "running private evaluation")
        evaluation = self.evaluate_attempt(
            workspace,
            profile=profile,
            security_mode=security_mode,
            host_provider=host_provider,
            host_image=host_image,
        )
        evaluation = self._attach_model_metadata(evaluation, model_metadata, anonymous=True)
        progress(100, "complete")
        return self._redact_anonymous({**model_metadata, "evaluation": evaluation}, key, loaded)

    def _configured_model(self) -> dict[str, Any]:
        configuration = self._model_configuration(include_secret=True)
        if not configuration["modelEnabled"]:
            raise ValueError("The model under test is disabled in settings")
        if not str(configuration["modelName"]).strip():
            raise ValueError("The model-under-test name is not configured")
        return configuration

    def _run_model_in_workspace(
        self,
        loaded: LoadedBenchmark,
        task: BenchmarkTask,
        workspace: Path,
        requirement: str,
        configuration: dict[str, Any],
        model_run_id: str,
        progress: Callable[[int, str], None],
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        run_root = self.settings.state_dir / "model-runs" / model_run_id
        run_root.mkdir(parents=True, exist_ok=True)
        progress(5, "preparing task workspace")
        model_result = self.model_runner.build(
            workspace,
            requirement,
            base_url=str(configuration["modelBaseUrl"]),
            model=str(configuration["modelName"]),
            api_key=str(configuration["modelApiKey"]),
            model_class=str(configuration["modelClass"]),
            max_steps=int(configuration["modelMaxSteps"]),
            request_timeout=int(configuration["modelRequestTimeout"]),
            progress=progress,
            system_prompt=system_prompt or loaded.plugin.agent_system_prompt(task),
            agent_environment=loaded.plugin.agent_environment(task),
        )
        trajectory = model_result.pop(
            "trajectory",
            {"messages": model_result.pop("transcript", []), "trajectory_format": "unknown"},
        )
        trajectory_path = run_root / "trajectory.json"
        trajectory_path.write_text(
            json.dumps(trajectory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return {
            "modelRunId": model_run_id,
            "model": configuration["modelName"],
            "framework": model_result.get(
                "framework", {"name": "unknown", "version": "", "trajectoryFormat": "unknown"}
            ),
            "steps": model_result["steps"],
            "exitStatus": model_result.get("exitStatus", "unknown"),
            "changedFiles": model_result["changedFiles"],
            "trajectoryPath": str(trajectory_path),
        }

    def _attach_model_metadata(
        self,
        evaluation: dict[str, Any],
        model_metadata: dict[str, Any],
        *,
        anonymous: bool = False,
    ) -> dict[str, Any]:
        with self.database.session_factory() as session:
            run = session.get(Run, str(evaluation["id"]))
            assert run
            result = json_loads(run.result_json, {})
            result["modelRun"] = model_metadata
            run.result_json = json_dumps(result)
            session.commit()
            return anonymous_run_dict(run) if anonymous else run_dict(run)

    def report(self, game_id: str | None = None, pack_id: str | None = None) -> dict[str, Any]:
        selected_keys = [
            str(key)
            for key in sorted(self.tasks)
            if (not game_id or key.game_id == game_id) and (not pack_id or key.pack_id == pack_id)
        ]
        with self.database.session_factory() as session:
            runs = list(
                session.scalars(
                    select(Run).where(Run.task_key.in_(selected_keys)).order_by(Run.created_at.desc())
                )
            )
        completed = [run for run in runs if run.status in {"passed", "failed"}]
        model_runs: dict[str, list[Run]] = {}
        for run in completed:
            model = json_loads(run.result_json, {}).get("modelRun", {}).get("model")
            if model:
                model_runs.setdefault(str(model), []).append(run)
        return {
            "gameId": game_id,
            "packId": pack_id,
            "tasks": len(selected_keys),
            "runs": len(runs),
            "completedRuns": len(completed),
            "passRate": round(sum(run.status == "passed" for run in completed) / len(completed) * 100, 2)
            if completed
            else 0.0,
            "averageScore": round(sum(run.score for run in completed) / len(completed), 2)
            if completed
            else 0.0,
            "byModel": {
                model: {
                    "runs": len(group),
                    "passRate": round(sum(run.status == "passed" for run in group) / len(group) * 100, 2),
                    "averageScore": round(sum(run.score for run in group) / len(group), 2),
                }
                for model, group in sorted(model_runs.items())
            },
        }

    def _model_configuration(self, include_secret: bool = False) -> dict[str, Any]:
        with self.database.session_factory() as session:
            stored = {
                row.key: json_loads(row.value_json, None) for row in session.scalars(select(Setting)).all()
            }
        stored_key = str(stored.pop("modelApiKey", "") or "")
        environment_key = os.environ.get("RHENIUM_MODEL_API_KEY", "")
        enabled_value = os.environ.get("RHENIUM_MODEL_ENABLED")
        environment_enabled = (
            enabled_value.strip().lower() in {"1", "true", "yes", "on"} if enabled_value is not None else None
        )
        max_steps_value = os.environ.get("RHENIUM_MODEL_MAX_STEPS")
        max_steps = int(max_steps_value) if max_steps_value else int(stored.get("modelMaxSteps", 100))
        timeout_value = os.environ.get("RHENIUM_MODEL_REQUEST_TIMEOUT")
        request_timeout = (
            int(timeout_value) if timeout_value else int(stored.get("modelRequestTimeout", 600))
        )
        configuration: dict[str, Any] = {
            "modelEnabled": (
                environment_enabled
                if environment_enabled is not None
                else bool(stored.get("modelEnabled", False))
            ),
            "modelBaseUrl": os.environ.get(
                "RHENIUM_MODEL_BASE_URL",
                str(stored.get("modelBaseUrl", "")),
            ),
            "modelName": os.environ.get(
                "RHENIUM_MODEL_NAME",
                os.environ.get("MSWEA_MODEL_NAME", str(stored.get("modelName", ""))),
            ),
            "modelClass": os.environ.get("RHENIUM_MODEL_CLASS", str(stored.get("modelClass", "litellm"))),
            "modelMaxSteps": max(8, min(max_steps, 1000)),
            "modelRequestTimeout": max(30, min(request_timeout, 3600)),
            "modelApiKeyConfigured": bool(stored_key or environment_key),
            "agentFramework": "mini-swe-agent",
        }
        if include_secret:
            configuration["modelApiKey"] = environment_key or stored_key
        return configuration

    def get_settings(self) -> dict[str, Any]:
        return {
            **self._model_configuration(),
            "authProviders": self.auth.provider_list(),
            "runtimes": self.runtime_manager.list(),
        }

    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "modelEnabled",
            "modelBaseUrl",
            "modelName",
            "modelClass",
            "modelMaxSteps",
            "modelApiKey",
        }
        with self.database.session_factory() as session:
            for key, value in values.items():
                if key not in allowed:
                    continue
                if key == "modelApiKey" and not str(value).strip():
                    continue
                if key == "modelMaxSteps":
                    value = max(8, min(int(value), 1000))
                row = session.get(Setting, key) or Setting(key=key, value_json="null")
                session.add(row)
                row.value_json = json_dumps(value)
            session.commit()
        return self.get_settings()


class JobManager:
    def __init__(self, hub: BenchmarkHub):
        self.hub = hub
        self._threads: dict[str, threading.Thread] = {}

    def start(self, kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        if kind not in {"evaluate", "model_evaluate"}:
            raise ValueError(f"Unsupported job kind: {kind}")
        task_key = str(payload.get("taskKey", ""))
        self.hub._loaded_task(task_key)
        if payload.get("profile") is not None:
            self.hub.validate_task_profile(task_key, str(payload["profile"]))
        self.hub._security_mode(str(payload.get("securityMode", "honest")))
        if kind == "evaluate" and not str(payload.get("submissionPath", "")):
            raise ValueError("evaluate jobs require submissionPath")
        if kind == "model_evaluate":
            with self.hub.database.session_factory() as session:
                active_jobs = session.scalars(
                    select(Job)
                    .where(
                        Job.kind == kind,
                        Job.task_key == task_key,
                        Job.status.in_(["queued", "running"]),
                    )
                    .order_by(Job.created_at.desc())
                ).all()
                for active in active_jobs:
                    active_payload = json_loads(active.payload_json, {})
                    if all(
                        active_payload.get(field) == payload.get(field)
                        for field in ("profile", "securityMode", "hostProvider", "hostImage")
                    ):
                        return job_dict(active)
        job = Job(
            id=f"job-{uuid.uuid4().hex[:16]}",
            task_key=task_key,
            kind=kind,
            payload_json=json_dumps(payload),
        )
        with self.hub.database.session_factory() as session:
            session.add(job)
            session.commit()
        thread = threading.Thread(target=self._run, args=(job.id,), daemon=True, name=f"rhenium-{kind}")
        self._threads[job.id] = thread
        thread.start()
        return job_dict(job)

    def _run(self, job_id: str) -> None:
        with self.hub.database.session_factory() as session:
            job = session.get(Job, job_id)
            assert job
            if job.cancel_requested or job.status == "canceled":
                job.status = "canceled"
                job.phase = "canceled"
                session.commit()
                return
            job.status = "running"
            job.phase = "starting"
            job.updated_at = utcnow()
            payload = json_loads(job.payload_json, {})
            session.commit()

        def progress(value: int, phase: str) -> None:
            with self.hub.database.session_factory() as session:
                current = session.get(Job, job_id)
                assert current
                if current.cancel_requested:
                    current.status = "canceled"
                    current.phase = "canceled"
                    session.commit()
                    raise JobCancelled
                current.progress = max(0, min(100, value))
                current.phase = phase
                current.updated_at = utcnow()
                session.commit()

        try:
            if job.kind == "evaluate":
                progress(10, "evaluating submission")
                result = self.hub.evaluate_task(
                    str(payload["taskKey"]),
                    Path(str(payload["submissionPath"])),
                    payload.get("profile"),
                    security_mode=str(payload.get("securityMode", "honest")),
                    host_provider=payload.get("hostProvider"),
                    host_image=payload.get("hostImage"),
                )
            else:
                result = self.hub.evaluate_model(
                    str(payload["taskKey"]),
                    payload.get("profile"),
                    progress,
                    security_mode=str(payload.get("securityMode", "honest")),
                    host_provider=payload.get("hostProvider"),
                    host_image=payload.get("hostImage"),
                )
            with self.hub.database.session_factory() as session:
                current = session.get(Job, job_id)
                assert current
                current.status = "completed"
                current.phase = "complete"
                current.progress = 100
                current.result_json = json_dumps(result)
                session.commit()
        except JobCancelled:
            with self.hub.database.session_factory() as session:
                current = session.get(Job, job_id)
                assert current
                current.status = "canceled"
                current.phase = "canceled"
                current.updated_at = utcnow()
                session.commit()
        except Exception as error:
            with self.hub.database.session_factory() as session:
                current = session.get(Job, job_id)
                assert current
                current.status = "failed"
                current.phase = "failed"
                current.error = str(error)
                session.commit()

    def list(self) -> list[dict[str, Any]]:
        with self.hub.database.session_factory() as session:
            jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()
            return [job_dict(job) for job in jobs]

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self.hub.database.session_factory() as session:
            job = session.get(Job, job_id)
            return job_dict(job) if job else None

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self.hub.database.session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status in {"completed", "failed", "canceled"}:
                return job_dict(job)
            job.cancel_requested = True
            if job.status == "queued":
                job.status = "canceled"
                job.phase = "canceled"
            session.commit()
            return job_dict(job)
