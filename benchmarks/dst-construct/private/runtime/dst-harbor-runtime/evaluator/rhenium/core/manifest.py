from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BenchmarkManifest(BaseModel):
    """Selects one plugin and catalog for a benchmark pack."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = 2
    pack_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    plugin: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    catalog: str
    runtime_catalog: str | None = None

    @field_validator("catalog", "runtime_catalog")
    @classmethod
    def catalog_path_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value != path.as_posix():
            raise ValueError("catalog must be a normalized relative POSIX path")
        return value

    @classmethod
    def load(cls, manifest_path: Path | str) -> Self:
        path = Path(manifest_path).resolve()
        manifest = cls.model_validate_json(path.read_text(encoding="utf-8"))
        root = path.parent
        catalog = (root / manifest.catalog).resolve()
        if not catalog.is_relative_to(root) or not catalog.is_file():
            raise ValueError(f"benchmark catalog is missing: {manifest.catalog}")
        if manifest.runtime_catalog is not None:
            runtime_catalog = (root / manifest.runtime_catalog).resolve()
            if not runtime_catalog.is_relative_to(root) or not runtime_catalog.is_file():
                raise ValueError(f"runtime catalog is missing: {manifest.runtime_catalog}")
        return manifest


def discover_manifest_paths(search_roots: tuple[Path, ...]) -> tuple[Path, ...]:
    discovered: dict[Path, Path] = {}
    for configured in search_roots:
        root = configured.expanduser().resolve()
        if not root.is_dir():
            continue
        for candidate in sorted(root.rglob("benchmark.json")):
            if candidate.is_symlink():
                continue
            resolved = candidate.resolve()
            if resolved.is_relative_to(root) and resolved.is_file():
                discovered.setdefault(resolved, candidate)
    return tuple(discovered[path] for path in sorted(discovered))
