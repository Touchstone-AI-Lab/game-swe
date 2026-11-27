from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from rhenium.core.catalog import (
    BenchmarkCatalog,
    BenchmarkTask,
    CatalogModel,
    LocalizedList,
    LocalizedText,
)

from .files import asset, digest, read_file, read_json, relative_path


class TaskSpec(CatalogModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: LocalizedText
    package: str
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class CatalogSpec(CatalogModel):
    schema_version: Literal[1]
    id: str
    version: str
    game: Literal["balatro"]
    tasks: tuple[TaskSpec, ...]


class BalatroTask(BenchmarkTask):
    package: str
    package_sha256: str
    editable_files: tuple[str, ...]
    immutable_files: tuple[str, ...]
    snapshot_files: dict[str, str]
    public_documents: tuple[str, ...]
    authored_prompt: str = Field(exclude=True)


def anonymous_document(text: str, task_id: str) -> str:
    """Only presentation identity changes. Authored behavior and APIs are preserved."""
    return text.replace(task_id, "this-exercise")


def load_catalog(root: Path, catalog_path: str) -> BenchmarkCatalog:
    spec = CatalogSpec.model_validate(read_json(root, catalog_path))
    tasks: list[BalatroTask] = []
    for item in spec.tasks:
        package_root = asset(root, item.package)
        raw = read_file(package_root, "package.json")
        if digest(raw) != item.package_sha256:
            raise ValueError("package identity mismatch")
        package = read_json(package_root, "package.json")
        if package.get("task") != item.id or package.get("protocol") != "v2":
            raise ValueError("incompatible candidate package")
        snapshot: dict[str, str] = {}
        for name, record in package["files"].items():
            data = read_file(package_root, name)
            if len(data) != record["size"] or digest(data) != record["sha256"]:
                raise ValueError("frozen public asset changed")
            snapshot[name] = record["sha256"]
        editable = tuple(package["editable_files"])
        immutable = tuple(package["immutable_files"])
        if (not editable or set(editable) & set(immutable)
                or len(set(editable + immutable)) != len(editable + immutable)
                or any(not name.startswith("starter/") for name in editable + immutable)
                or {name for name in snapshot if name.startswith("starter/")} != set(editable + immutable)):
            raise ValueError("invalid starter allowlist")
        for name in editable + immutable:
            relative_path(name)
        docs = tuple(name for name in ("CONTRACT.md", "API.md") if name in snapshot)
        if "CONTRACT.md" not in docs:
            raise ValueError("missing public contract")
        prompt = anonymous_document(read_file(package_root, "CONTRACT.md").decode("utf-8"), item.id)
        prompt += "\n\n## Submission\n\nRepair the supplied starter according to this contract.\n"
        prompt += "Editable files: " + ", ".join(f"`{name}`" for name in editable) + ".\n"
        prompt += "Keep immutable files byte-identical: " + ", ".join(f"`{name}`" for name in immutable)
        prompt += ". Use only the approved scorer command in PROMPT.md.\n"
        if "API.md" in docs:
            prompt += "The supplied API.md is part of this public specification.\n"
        difficulty = package["target_difficulty"]
        # Required Hub field: author planning estimate only, never measured solve time.
        estimates = {"easy": 30, "medium": 60, "hard": 90}
        brief = LocalizedText(en="Repair the supplied Lua mod using the frozen public contract.",
                              zh="按冻结的公开契约修复随附的 Lua 模组。")
        rules = LocalizedList(en=["Follow the supplied contract; preserve immutable starter files."],
                              zh=["遵循随附契约，保持不可编辑文件字节不变。"])
        tasks.append(BalatroTask(
            id=item.id, difficulty=difficulty, title=item.title, summary=brief, brief=brief,
            requirements=rules, api_usage=rules, acceptance=rules,
            domains=["lua", "game-lifecycle"], estimated_minutes=estimates[difficulty],
            required_files=list(editable + immutable), package=item.package,
            package_sha256=item.package_sha256, editable_files=editable,
            immutable_files=immutable, snapshot_files=snapshot, public_documents=docs,
            authored_prompt=prompt,
        ))
    return BenchmarkCatalog(
        id=spec.id, version=spec.version, game=spec.game,
        name=LocalizedText(en="Balatro authored candidate tasks", zh="Balatro 自编候选任务"),
        description=LocalizedText(en="Uncalibrated tasks; platform engine validation is separate.",
                                  zh="未校准候选任务；平台引擎验证单独记录。"), tasks=tasks,
    )
