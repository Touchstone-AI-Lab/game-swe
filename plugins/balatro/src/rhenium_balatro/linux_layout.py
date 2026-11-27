"""Select versioned operator state without touching the old halt or binding."""

from __future__ import annotations

import json

from rhenium.core.plugin import BenchmarkContext

from .container_host import RUNTIME_ID as CONTAINER
from .linux_managed import RUNTIME_ID as V1
from .linux_managed_v2 import RUNTIME_ID as V2


def pack_runtime(context: BenchmarkContext) -> str:
    path = context.pack_root / "runtimes.json"
    if not path.is_file():
        return V1  # Existing portable/unit catalogs have no managed binding.
    bindings = json.loads(path.read_text()).get("task_bindings", {})
    values = {tuple(value) for value in bindings.values()}
    if not values or values == {(V1,)}:
        return V1
    if values == {(V2,)}:
        return V2
    if values == {(CONTAINER,)}:
        return CONTAINER
    raise ValueError("Unsupported or mixed Linux runtime bindings")


def execution_context(context: BenchmarkContext) -> BenchmarkContext:
    if pack_runtime(context) == V1:
        return context
    return BenchmarkContext(
        project_root=context.project_root,
        pack_root=context.pack_root,
        state_dir=context.state_dir / "linux-controlled-v2-window-v2",
        cache_dir=context.cache_dir,
    )
