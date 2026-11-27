from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Literal, Self, overload

from pydantic import Field, field_validator, model_validator

from rhenium.core.catalog import BenchmarkCatalog, BenchmarkTask, CatalogModel

from .construct_catalog import CONSTRUCT_CATALOG_FILE, DstConstructCatalog

CATALOG_ID = "dst-core"
# Every task ships the vendored mod below this workspace directory. The Hub
# workspace holds it as ``mod/`` and a Harbor or container verifier sees the
# same tree at ``/app/mod``.
STARTER_NAME = "mod"
CONTAINER_DESTINATION = "/app/mod"
# A mod configuration value as a dedicated-server operator writes it in
# modoverrides.lua. Nested tables are deliberately not supported.
ModOptionValue = bool | int | float | str


def _catalog_id(path: Path) -> str | None:
    """The ``id`` a catalog file declares, or None when it declares none."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    identifier = value.get("id") if isinstance(value, dict) else None
    return identifier if isinstance(identifier, str) else None


def _relative_posix(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ValueError("catalog paths must be normalized relative POSIX paths")
    return value


class UpstreamProvenance(CatalogModel):
    """Where the vendored mod tree comes from and which real fixes it lacks."""

    repository: str = Field(pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    license_spdx: Literal[
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "MPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "Unlicense",
    ]
    license_file: str
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    fix_commits: tuple[str, ...] = Field(min_length=1)

    @field_validator("license_file")
    @classmethod
    def license_file_is_relative(cls, value: str) -> str:
        return _relative_posix(value)

    @field_validator("fix_commits")
    @classmethod
    def fix_commits_are_full_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(
            len(item) != 40 or any(char not in "0123456789abcdef" for char in item) for item in value
        ):
            raise ValueError("fix_commits must be unique full lower-case commit hashes")
        return value


class DstTask(BenchmarkTask):
    """A repair task over a vendored, real Don't Starve Together mod.

    The starter is the upstream mod with real upstream fixes reverted. The
    hidden suite runs inside the pinned dedicated server with the submitted
    mod enabled and ``mod_options`` applied as the operator's configuration.
    """

    difficulty: Literal["medium", "hard"]
    task_kind: Literal["repository-debugging"] = "repository-debugging"
    source_mod: str = Field(min_length=1)
    upstream: UpstreamProvenance
    server_test: str
    server_cases: tuple[str, ...] = Field(min_length=3)
    mod_options: dict[str, ModOptionValue] = Field(default_factory=dict)
    authored_prompt: str = Field(default="", exclude=True, repr=False)

    @property
    def starter_name(self) -> str:
        return STARTER_NAME

    @property
    def container_destination(self) -> str:
        return CONTAINER_DESTINATION

    @field_validator("server_test")
    @classmethod
    def server_test_is_relative(cls, value: str) -> str:
        return _relative_posix(value)

    @field_validator("server_cases")
    @classmethod
    def case_names_are_unique_and_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not name.strip() or name != name.strip() for name in value):
            raise ValueError("declared case names must be non-blank and trimmed")
        if len(set(value)) != len(value):
            raise ValueError("declared case names must be unique")
        return value

    @field_validator("mod_options")
    @classmethod
    def option_names_are_identifiers(
        cls, value: dict[str, ModOptionValue]
    ) -> dict[str, ModOptionValue]:
        for key, item in value.items():
            if not key.isidentifier():
                raise ValueError("mod option names must be Lua identifiers")
            if isinstance(item, str) and any(char in item for char in "\"\\\n\r"):
                raise ValueError("mod option strings must not contain quotes or line breaks")
        return value

    @model_validator(mode="after")
    def required_files_live_in_the_mod_tree(self) -> Self:
        prefix = f"{STARTER_NAME}/"
        if any(not item.startswith(prefix) for item in self.required_files):
            raise ValueError(f"required_files must be below {prefix}")
        for required in ("modinfo.lua", "modmain.lua"):
            if f"{prefix}{required}" not in self.required_files:
                raise ValueError(f"required_files must include {prefix}{required}")
        return self


class DstCatalog(BenchmarkCatalog):
    id: Literal["dst-core"]
    game: Literal["dst"]
    tasks: list[DstTask]

    # The restored construct pack's Harbor verifier calls
    # ``DstCatalog.load(pack, "fixed-v1.json")``, so that file name is typed as
    # the construct catalog. The overlap with ``str`` is intentional.
    @overload
    @classmethod
    def load(  # type: ignore[overload-overlap]
        cls,
        pack_root: Path | str,
        catalog_path: Literal["fixed-v1.json"],
        *,
        verifier_pack: bool = False,
    ) -> DstConstructCatalog: ...

    @overload
    @classmethod
    def load(
        cls,
        pack_root: Path | str,
        catalog_path: str = "catalog.json",
        *,
        verifier_pack: bool = False,
    ) -> Self: ...

    @classmethod
    def load(
        cls,
        pack_root: Path | str,
        catalog_path: str = "catalog.json",
        *,
        verifier_pack: bool = False,
    ) -> Self | DstConstructCatalog:
        """Load and validate the catalog and its private assets.

        A Harbor verifier image carries a one-task pack with only the catalog
        and the hidden suite, so ``verifier_pack`` skips the public exam and
        the vendored starter, which that image deliberately does not contain.

        The plugin serves two catalog kinds and dispatches by catalog id: a
        catalog whose id is not ``dst-core`` (and ``fixed-v1.json``, the
        construct pack's file) is a construct catalog, loaded by the restored
        ``DstConstructCatalog`` model exactly as before the repair pack existed.
        """
        root = Path(pack_root).resolve()
        path = (root / catalog_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"DST catalog is missing: {catalog_path}")
        if catalog_path == CONSTRUCT_CATALOG_FILE or _catalog_id(path) not in {None, CATALOG_ID}:
            return DstConstructCatalog.load(root, catalog_path)
        catalog = cls.model_validate_json(path.read_text(encoding="utf-8"))
        loaded: list[DstTask] = []
        for task in catalog.tasks:
            suite = (root / task.server_test).resolve()
            if not suite.is_relative_to(root) or not suite.is_file():
                raise ValueError(f"server suite is missing for {task.id}: {task.server_test}")
            if verifier_pack:
                loaded.append(task)
                continue
            exam = (root / "exams" / f"{task.id}.md").resolve()
            task_root = root / "private" / "harbor" / task.id
            required = {
                "public exam": exam,
                "starter": task_root / "environment" / STARTER_NAME,
                "reference": task_root / "solution" / "after",
                "gold patch": task_root / "solution" / "gold.patch",
                "task metadata": task_root / "task.toml",
            }
            for label, candidate in required.items():
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():
                    raise ValueError(f"{label} is missing for {task.id}")
            starter = required["starter"]
            license_file = starter / task.upstream.license_file
            if not license_file.is_file():
                raise ValueError(f"upstream licence is missing from the starter of {task.id}")
            for relative in task.required_files:
                if not (task_root / "environment" / relative).is_file():
                    raise ValueError(f"required file is missing from the starter of {task.id}")
            loaded.append(task.model_copy(update={"authored_prompt": exam.read_text(encoding="utf-8")}))
        return catalog.model_copy(update={"tasks": loaded})
