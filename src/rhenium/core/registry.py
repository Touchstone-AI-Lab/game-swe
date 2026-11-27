from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points
from typing import Any

from .auth import AuthProvider
from .evaluation_host import DisposableEvaluationHost
from .plugin import BenchmarkPlugin

ENTRY_POINT_GROUP = "rhenium.benchmarks"
AUTH_ENTRY_POINT_GROUP = "rhenium.auth_providers"
EVALUATION_HOST_ENTRY_POINT_GROUP = "rhenium.evaluation_hosts"


def _instantiate(value: Any) -> BenchmarkPlugin:
    plugin = value() if isinstance(value, type) else value
    if not isinstance(plugin, BenchmarkPlugin):
        raise TypeError("benchmark plugin must inherit BenchmarkPlugin")
    return plugin


def discover_plugins(
    candidates: tuple[EntryPoint, ...] | None = None,
) -> tuple[dict[str, BenchmarkPlugin], list[dict[str, str]]]:
    selected = candidates if candidates is not None else tuple(entry_points(group=ENTRY_POINT_GROUP))
    grouped: dict[str, list[EntryPoint]] = {}
    for entry_point in selected:
        grouped.setdefault(entry_point.name, []).append(entry_point)

    plugins: dict[str, BenchmarkPlugin] = {}
    errors: list[dict[str, str]] = []
    for name, matches in sorted(grouped.items()):
        if len(matches) != 1:
            errors.append(
                {
                    "kind": "plugin",
                    "id": name,
                    "message": f"duplicate plugin entry points: {len(matches)}",
                }
            )
            continue
        try:
            plugin = _instantiate(matches[0].load())
            if plugin.id != name:
                raise ValueError(f"entry point {name!r} loaded plugin {plugin.id!r}")
            if plugin.game_id in {item.game_id for item in plugins.values()}:
                raise ValueError(f"duplicate game plugin: {plugin.game_id}")
            plugins[name] = plugin
        except Exception as error:  # discovery must isolate a broken plugin
            errors.append({"kind": "plugin", "id": name, "message": str(error)})
    return plugins, errors


def discover_auth_providers(
    candidates: tuple[EntryPoint, ...] | None = None,
) -> tuple[dict[str, AuthProvider], list[dict[str, str]]]:
    selected = (
        candidates
        if candidates is not None
        else tuple(entry_points(group=AUTH_ENTRY_POINT_GROUP))
    )
    grouped: dict[str, list[EntryPoint]] = {}
    for entry_point in selected:
        grouped.setdefault(entry_point.name, []).append(entry_point)
    providers: dict[str, AuthProvider] = {}
    errors: list[dict[str, str]] = []
    for name, matches in sorted(grouped.items()):
        if len(matches) != 1:
            errors.append(
                {
                    "kind": "auth-provider",
                    "id": name,
                    "message": f"duplicate auth provider entry points: {len(matches)}",
                }
            )
            continue
        try:
            loaded = matches[0].load()
            provider = loaded() if isinstance(loaded, type) else loaded
            if not isinstance(provider, AuthProvider):
                raise TypeError("auth provider must inherit AuthProvider")
            if provider.id != name:
                raise ValueError(f"entry point {name!r} loaded provider {provider.id!r}")
            providers[name] = provider
        except Exception as error:
            errors.append({"kind": "auth-provider", "id": name, "message": str(error)})
    return providers, errors


def discover_evaluation_hosts(
    candidates: tuple[EntryPoint, ...] | None = None,
) -> tuple[dict[str, DisposableEvaluationHost], list[dict[str, str]]]:
    selected = (
        candidates
        if candidates is not None
        else tuple(entry_points(group=EVALUATION_HOST_ENTRY_POINT_GROUP))
    )
    grouped: dict[str, list[EntryPoint]] = {}
    for entry_point in selected:
        grouped.setdefault(entry_point.name, []).append(entry_point)
    providers: dict[str, DisposableEvaluationHost] = {}
    errors: list[dict[str, str]] = []
    for name, matches in sorted(grouped.items()):
        if len(matches) != 1:
            errors.append(
                {
                    "kind": "evaluation-host",
                    "id": name,
                    "message": f"duplicate evaluation host entry points: {len(matches)}",
                }
            )
            continue
        try:
            loaded = matches[0].load()
            provider = loaded() if isinstance(loaded, type) else loaded
            if not isinstance(provider, DisposableEvaluationHost):
                raise TypeError("evaluation host provider must inherit DisposableEvaluationHost")
            if provider.id != name:
                raise ValueError(f"entry point {name!r} loaded evaluation host {provider.id!r}")
            providers[name] = provider
        except Exception as error:
            errors.append({"kind": "evaluation-host", "id": name, "message": str(error)})
    return providers, errors
