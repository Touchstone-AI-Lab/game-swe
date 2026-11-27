from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_palworld_harbor_tasks import HARBOR, PACK, _load_verifier

ADVANCED = {
    "base-containment-mincut": "containment",
    "guild-draft-canonical-order": "draft",
    "outbox-receipt-recovery": "outbox",
    "pal-workforce-optimal-matching": "workforce",
    "raid-event-watermark": "watermark",
    "guild-consistent-checkpoint": "checkpoint",
    "world-epoch-fenced-timers": "epoch",
}

# These controls break one real protocol rule while preserving valid Lua and
# all required files. An empty starter alone is not a discriminating control.
MUTATIONS = (
    ("containment", "local factor, bound = n+1, 0", "local factor, bound = 1, 0"),
    ("containment", "v.penalty*factor", "0"),
    ("containment", "if flow()~=optimum then fixed[i]=1 end", "fixed[i]=1"),
    ("containment", "previous[v.id] or 0", "0"),
    ("containment", "not same(result,data.result)", "false"),
    ("draft", "weights[index[v.from]]", "weights[index[v.to]]"),
    ("draft", "local low,high=0,math.max(0,n-1)", "local low,high=n,n"),
    ("draft", "other<second", "other>second"),
    ("draft", "for j=1,n do\n            local distance", "for j=n,1,-1 do\n            local distance"),
    ("draft", "not same(result,data.result)", "false"),
    ("outbox", 'if not ok or result ~= true then', 'if false then'),
    ("outbox", 'if receipt == "absent" then', 'if receipt ~= "rejected" then'),
    ("outbox", 'if not saved or result ~= true then', 'if false then'),
    ("workforce", 'a.priority > b.priority', 'a.priority < b.priority'),
    ("workforce", 'a.count > b.count', 'a.count < b.count'),
    ("workforce", 'a.key < b.key', 'a.key > b.key'),
    ("watermark", 'e.tick < self.watermark', 'e.tick <= self.watermark'),
    ("watermark", 'and not e.deleted', 'and true'),
    ("watermark", 'e.revision < old.revision', 'e.revision > old.revision'),
    ("checkpoint", 'while changed do', 'for _ = 1, 1 do'),
    ("checkpoint", 'for seq = 1, cut[shard] do', 'for seq = cut[shard], cut[shard] do'),
    ("checkpoint", 'cut[shard] = prefix', 'cut[shard] = 0'),
    ("epoch", 'or task.generation ~= token.generation', ''),
    ("epoch", 'token.epoch ~= self.epoch', 'false'),
    ("epoch", 'task.state ~= "leased"', 'false'),
)


@pytest.mark.parametrize(("module", "before", "after"), MUTATIONS)
def test_advanced_behavior_rejects_discriminating_mutations(
    module: str, before: str, after: str, tmp_path: Path
) -> None:
    task_id = next(key for key, value in ADVANCED.items() if value == module)
    task_root = HARBOR / task_id
    submission = tmp_path / "mutant"
    shutil.copytree(task_root / "solution" / "reference", submission)
    source = submission / "scripts" / module / "core.lua"
    text = source.read_text(encoding="utf-8")
    assert text.count(before) == 1, "mutation target changed: review the control"
    source.write_text(text.replace(before, after), encoding="utf-8")

    verifier = _load_verifier()
    result = verifier.run_behavior(submission, PACK / "hidden" / f"{task_id}.lua")
    assert result["status"] == "failed", result
    assert any(case["passed"] is False for case in result["cases"]), result


@pytest.mark.parametrize("task_id", ADVANCED)
@pytest.mark.parametrize("dedicated", [True, False])
def test_advanced_reference_mount_waits_for_world_and_releases_exact_hook(
    task_id: str, dedicated: bool
) -> None:
    from lupa.lua54 import LuaRuntime  # type: ignore[import-untyped]

    root = HARBOR / task_id / "solution" / "reference"
    runtime = LuaRuntime(encoding="utf-8", register_eval=False, register_builtins=False)
    module_cache: dict[str, Any] = {}

    def require_module(name: str) -> Any:
        if name == "UEHelpers":
            return runtime.globals().helpers
        if name not in module_cache:
            path = root / "scripts" / (name.replace(".", "/") + ".lua")
            module_cache[name] = runtime.execute(path.read_text(encoding="utf-8"))
        return module_cache[name]

    runtime.globals().require = require_module
    runtime.execute("""
        ready = false
        dedicated = true
        registrations = 0
        releases = 0
        prints = 0
        delayed = {}
        helpers = {
            GetWorld = function() return {IsValid=function() return ready end} end,
            GetKismetSystemLibrary = function()
                return {IsDedicatedServer=function() return dedicated end}
            end,
        }
        ExecuteInGameThread = function(callback) callback() end
        ExecuteWithDelay = function(_, callback) delayed[#delayed+1] = callback end
        RegisterHook = function(path, callback)
            assert(ready and dedicated)
            registrations = registrations + 1
            hook_path, hook_callback = path, callback
            return 37, 81
        end
        UnregisterHook = function(path, pre, post)
            assert(path == hook_path and pre == 37 and post == 81)
            releases = releases + 1
        end
        RegisterConsoleCommandGlobalHandler = function(_, callback)
            assert(ready and dedicated)
            console_callback = callback
        end
        print = function() prints = prints + 1 end
    """)
    runtime.globals().dedicated = dedicated
    # The exam forbids a top-level return in main.lua, so the reference must run to
    # its end, even before world readiness.
    main = (root / "scripts" / "main.lua").read_text(encoding="utf-8")
    runtime.execute(main + "\ninjection_reached = true\n")
    assert runtime.globals().injection_reached is True
    if not dedicated:
        runtime.execute("""
            ready = true
            delayed[1]()
            assert(RheniumService == nil and registrations == 0)
        """)
        return
    runtime.execute("""
        assert(RheniumService == nil and registrations == 0 and #delayed == 1)
        ready = true
        delayed[1]()
        delayed[1]()
        assert(RheniumService ~= nil and registrations == 1)
        console_callback()
        assert(prints == 1)
        RheniumService:Unmount()
        RheniumService:Unmount()
        assert(releases == 1)
        console_callback()
        hook_callback({get=function() error("old callback dereferenced an object") end})
        assert(prints == 1)
    """)
    runtime.execute("RheniumService:Unmount()")
    assert runtime.globals().releases == 1


def test_retained_eight_catalog_entries_are_unchanged() -> None:
    catalog = json.loads((PACK / "fixed-v1.json").read_text(encoding="utf-8"))
    canonical = json.dumps(
        [
            task
            for task in catalog["tasks"]
            if task["id"] not in {"base-containment-mincut", "guild-draft-canonical-order"}
        ],
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == (
        "2f72c8931601f125988cd474eeb81f86997bd869f0ac890f5b3bc4180bb4ae67"
    )
