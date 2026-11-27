from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    state_dir: Path
    cache_dir: Path
    database_url: str
    benchmark_paths: tuple[Path, ...]
    web_dist: Path | None

    @classmethod
    def load(cls, root: Path | None = None) -> Settings:
        project_root = (root or Path(os.environ.get("RHENIUM_ROOT", Path.cwd()))).resolve()
        state_dir = Path(
            os.environ.get("RHENIUM_STATE_DIR", project_root / ".rhenium" / "hub")
        ).expanduser()
        cache_dir = Path(os.environ.get("RHENIUM_CACHE_DIR", state_dir / "cache")).expanduser()
        configured_benchmarks = os.environ.get("RHENIUM_BENCHMARK_PATH")
        benchmark_paths = (
            tuple(
                Path(value).expanduser()
                for value in configured_benchmarks.split(os.pathsep)
                if value.strip()
            )
            if configured_benchmarks is not None
            else (project_root / "benchmarks",)
        )
        web_value = os.environ.get("RHENIUM_WEB_DIST")
        local_web = project_root / "web/dist"
        packaged_web = Path(str(files("rhenium") / "web_dist"))
        web_dist = (
            Path(web_value).expanduser()
            if web_value
            else local_web
            if local_web.exists()
            else packaged_web
            if packaged_web.exists()
            else None
        )
        return cls(
            root=project_root,
            state_dir=state_dir,
            cache_dir=cache_dir,
            database_url=os.environ.get("RHENIUM_DATABASE_URL", f"sqlite:///{state_dir / 'state.sqlite'}"),
            benchmark_paths=benchmark_paths,
            web_dist=web_dist,
        )

    def ensure_directories(self) -> None:
        for path in (self.state_dir, self.cache_dir):
            path.mkdir(parents=True, exist_ok=True)
            with suppress(OSError):
                path.chmod(0o700)
