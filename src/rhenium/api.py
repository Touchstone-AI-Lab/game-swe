from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .config import Settings
from .core.identity import TaskKey
from .hub import BenchmarkHub, JobManager
from .operations import OperationManager


class SettingsRequest(BaseModel):
    values: dict[str, Any]


class AccountRequest(BaseModel):
    account: str = "default"


def create_app(
    settings: Settings | None = None,
    hub: BenchmarkHub | None = None,
    management_enabled: bool = True,
) -> FastAPI:
    resolved = settings or Settings.load()
    benchmark_hub = hub or BenchmarkHub(resolved)
    jobs = JobManager(benchmark_hub)
    operations = OperationManager(benchmark_hub)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(title="Rhenium", version=__version__, lifespan=lifespan)
    app.state.hub = benchmark_hub
    app.state.jobs = jobs
    app.state.operations = operations
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return benchmark_hub.health()

    @app.get("/api/games")
    def games() -> dict[str, Any]:
        return {"games": benchmark_hub.list_games()}

    @app.get("/api/games/{game_id}/packs")
    def packs(game_id: str) -> dict[str, Any]:
        return {"packs": benchmark_hub.list_packs(game_id=game_id)}

    @app.get("/api/packs")
    def all_packs() -> dict[str, Any]:
        return {"packs": benchmark_hub.list_packs()}

    @app.get("/api/tasks")
    def tasks(
        lang: Literal["en", "zh"] = "en",
        game: str | None = None,
        pack: str | None = None,
    ) -> dict[str, Any]:
        return {"tasks": benchmark_hub.list_tasks(language=lang, game_id=game, pack_id=pack)}

    @app.post("/api/games/{game_id}/packs/{pack_id}/tasks/{task_id}/runs")
    def run_model(
        game_id: str,
        pack_id: str,
        task_id: str,
        profile: str = "full",
        security_mode: Literal["honest", "untrusted"] = "honest",
        host_provider: str | None = None,
        host_image: str | None = None,
    ) -> dict[str, Any]:
        try:
            task_key = str(TaskKey(game_id, pack_id, task_id))
            selected_profile = benchmark_hub.validate_task_profile(task_key, profile)
        except KeyError as error:
            raise HTTPException(404, "Task not found") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        payload: dict[str, Any] = {"taskKey": task_key, "profile": selected_profile}
        if security_mode != "honest" or host_provider is not None or host_image is not None:
            payload.update(
                {
                    "securityMode": security_mode,
                    "hostProvider": host_provider,
                    "hostImage": host_image,
                }
            )
        return jobs.start("model_evaluate", payload)

    @app.get("/api/games/{game_id}/packs/{pack_id}/tasks/{task_id}/runs")
    def task_runs(
        game_id: str,
        pack_id: str,
        task_id: str,
        limit: int = Query(default=5, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            task_key = str(TaskKey(game_id, pack_id, task_id))
            return {"runs": benchmark_hub.list_runs(task_key=task_key, limit=limit)}
        except (KeyError, ValueError) as error:
            raise HTTPException(404, "Task not found") from error

    @app.get("/api/runs")
    def runs(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"runs": benchmark_hub.list_runs(limit=limit)}

    @app.get("/api/evaluation-hosts")
    def evaluation_hosts() -> dict[str, Any]:
        return {"providers": benchmark_hub.list_evaluation_hosts()}

    @app.get("/api/evaluation-hosts/{provider_id}/doctor")
    def evaluation_host_doctor(provider_id: str) -> dict[str, Any]:
        try:
            return benchmark_hub.evaluation_host_doctor(provider_id)
        except KeyError as error:
            raise HTTPException(404, "Evaluation host provider not found") from error

    @app.get("/api/jobs")
    def list_jobs() -> dict[str, Any]:
        return {"jobs": jobs.list()}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        result = jobs.get(job_id)
        if result is None:
            raise HTTPException(404, "Job not found")
        return result

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        try:
            return jobs.cancel(job_id)
        except KeyError as error:
            raise HTTPException(404, "Job not found") from error

    @app.get("/api/reports")
    def reports(game: str | None = None, pack: str | None = None) -> dict[str, Any]:
        return benchmark_hub.report(game_id=game, pack_id=pack)

    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        return benchmark_hub.get_settings()

    @app.patch("/api/settings")
    def patch_settings(request: SettingsRequest) -> dict[str, Any]:
        try:
            return benchmark_hub.update_settings(request.values)
        except (TypeError, ValueError) as error:
            raise HTTPException(400, f"Invalid settings value: {error}") from error

    def require_local(request: Request) -> None:
        host = request.client.host if request.client else ""
        if not management_enabled or host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(403, "auth and runtime management is available only on loopback")

    @app.get("/api/auth/providers")
    def auth_providers() -> dict[str, Any]:
        return {"providers": benchmark_hub.auth.provider_list()}

    @app.get("/api/auth/sessions")
    def auth_sessions() -> dict[str, Any]:
        return {"sessions": benchmark_hub.auth.list_sessions()}

    @app.post("/api/auth/providers/{provider_id}/login")
    def auth_login(provider_id: str, body: AccountRequest, request: Request) -> dict[str, Any]:
        require_local(request)
        try:
            return operations.start("auth_login", provider_id, {"account": body.account})
        except (KeyError, ValueError) as error:
            raise HTTPException(400, str(error)) from error

    @app.delete("/api/auth/providers/{provider_id}/sessions/{account_alias}")
    def auth_logout(provider_id: str, account_alias: str, request: Request) -> dict[str, Any]:
        require_local(request)
        return benchmark_hub.auth.logout(provider_id, account_alias)

    @app.get("/api/runtimes")
    def runtimes(game: str | None = None) -> dict[str, Any]:
        return {"runtimes": benchmark_hub.runtime_manager.list(game)}

    @app.get("/api/runtimes/{game_id}/{runtime_id}/doctor")
    def runtime_doctor(game_id: str, runtime_id: str) -> dict[str, Any]:
        try:
            return benchmark_hub.runtime_manager.doctor(f"{game_id}/{runtime_id}")
        except KeyError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/runtimes/{game_id}/{runtime_id}/prepare")
    def runtime_prepare(
        game_id: str,
        runtime_id: str,
        body: AccountRequest,
        request: Request,
    ) -> dict[str, Any]:
        require_local(request)
        try:
            return operations.start(
                "runtime_prepare",
                f"{game_id}/{runtime_id}",
                {"account": body.account},
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(400, str(error)) from error

    @app.post("/api/runtimes/{game_id}/{runtime_id}/verify")
    def runtime_verify(game_id: str, runtime_id: str, request: Request) -> dict[str, Any]:
        require_local(request)
        return operations.start("runtime_verify", f"{game_id}/{runtime_id}")

    @app.delete("/api/runtimes/{game_id}/{runtime_id}")
    def runtime_prune(game_id: str, runtime_id: str, request: Request) -> dict[str, Any]:
        require_local(request)
        return operations.start("runtime_prune", f"{game_id}/{runtime_id}")

    @app.get("/api/operations")
    def list_operations(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
        return {"operations": operations.list(limit)}

    @app.get("/api/operations/{operation_id}")
    def get_operation(operation_id: str) -> dict[str, Any]:
        result = operations.get(operation_id)
        if result is None:
            raise HTTPException(404, "Operation not found")
        return result

    @app.post("/api/operations/{operation_id}/cancel")
    def cancel_operation(operation_id: str, request: Request) -> dict[str, Any]:
        require_local(request)
        try:
            return operations.cancel(operation_id)
        except KeyError as error:
            raise HTTPException(404, "Operation not found") from error

    web_dist = resolved.web_dist
    if web_dist and (web_dist / "index.html").exists():
        assets = web_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def web_app(path: str) -> FileResponse:
            root = web_dist.resolve()
            requested = (root / path).resolve()
            if path and requested.is_relative_to(root) and requested.is_file():
                return FileResponse(requested)
            return FileResponse(root / "index.html")

    return app
