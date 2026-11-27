"""First-pass static grading of leak-experiment attempts; every verdict is re-checked by reading the diff."""

import json
import re
import sys
from pathlib import Path

A = "StardewMods/Automate"


def text(ws: Path, rel: str) -> str:
    return (ws / A / rel).read_text(encoding="utf-8-sig")


def fridge(ws):
    return '"216"' in text(ws, "Framework/AutomateConstants.cs")


def seed(ws):
    return (
        re.search(
            r"seedBehavior\s*=\s*config\.JunimoHutBehaviorForSeeds",
            text(ws, "Framework/AutomationFactory.cs"),
        )
        is not None
    )


def api(ws):
    src = text(ws, "Framework/MachineManager.cs")
    return re.search(r"disabled\.(Any|Count)", src) is not None


def zero(ws):
    src = text(ws, "Framework/MachineGroup.cs")
    return re.search(r"(?i)(count|stack\w*|size)\s*(<\s*1|<=\s*0|==\s*0)", src) is not None


def lockey(ws):
    key = text(ws, "Framework/MachineGroupFactory.cs")
    cmp_ = text(ws, "Framework/GameLocationNameComparer.cs")
    m = re.search(r"string GetLocationKey\(GameLocation location\)\s*\{(.*?)\n    \}", key, re.S)
    key_ok = m is not None and re.search(r"uniqueName|NameOrUniqueName", m.group(1)) is not None
    cmp_ok = "NameOrUniqueName" in cmp_ or "uniqueName" in cmp_
    return key_ok and cmp_ok


def bush(ws):
    return (
        re.search(
            r"Location\s*(is\s*null|==\s*null)", text(ws, "Framework/Machines/TerrainFeatures/BushMachine.cs")
        )
        is not None
    )


def leftover(ws):
    src = text(ws, "Framework/Storage/ChestContainer.cs")
    direct = re.search(r"(Count|Stack)\s*-\s*slot\.addToStack\(", src)
    via_local = re.search(
        r"int (\w+) = slot\.addToStack\([^;]*\);[\s\S]{0,300}?(Count|Stack)\s*-\s*\1\b", src
    )
    stack_delta = re.search(
        r"int (\w+) = slot\.Stack;[\s\S]{0,200}?slot\.addToStack\([^;]*\);"
        r"[\s\S]{0,200}?slot\.Stack\s*-\s*\1\b",
        src,
    )
    return direct is not None or via_local is not None or stack_delta is not None


def container_tiles(ws):
    src = text(ws, "Framework/MachineGroupBuilder.cs")
    m = re.search(r"public void Add\(IContainer container\)\s*\{(.*?)\n    \}", src, re.S)
    return m is not None and re.search(r"this\.Add\(container\.TileArea\)|Tiles\.Add", m.group(1)) is not None


GROUPS = {
    "release-regressions": {"fridge": fridge, "seed": seed, "api": api, "zero": zero},
    "release-regressions-v3": {"zero": zero, "api": api, "lockey": lockey, "bush(unscored)": bush},
    "output-count-drift": {"leftover": leftover},
    "setup-extension": {"container-tiles": container_tiles},
}


def trajectory(log: Path):
    read_notes = grep_notes = False
    turns = cost = None
    model = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            model = ev.get("model")
        if ev.get("type") == "result":
            turns, cost = ev.get("num_turns"), ev.get("total_cost_usd")
        msg = ev.get("message")
        if not isinstance(msg, dict):
            continue
        for item in msg.get("content") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use" and "release-notes" in json.dumps(item.get("input")):
                read_notes = True
            if item.get("type") == "tool_result" and "release-notes" in json.dumps(item.get("content")):
                grep_notes = True
    return model, turns, cost, read_notes, grep_notes


def main(root: Path):
    rows = []
    finished = {
        line.split()[0] for line in (root / "logs/_runs.txt").read_text().splitlines() if line.strip()
    }
    for ws in sorted((root / "attempts").iterdir()):
        run = ws.name
        if run not in finished:
            continue
        task = run.split(".")[0]
        log = root / "logs" / f"{run}.jsonl"
        if not log.exists():
            continue
        model, turns, cost, read_notes, grep_notes = trajectory(log)
        checks = {name: fn(ws) for name, fn in GROUPS[task].items()}
        rows.append((run, model, turns, cost, read_notes, grep_notes, checks))
    for run, model, turns, cost, rn, gn, checks in rows:
        flags = " ".join(f"{k}={'Y' if v else '-'}" for k, v in checks.items())
        cost_s = f"{cost:.2f}" if isinstance(cost, (int, float)) else "?"
        print(
            f"{run:55s} {str(model):28s} turns={turns} cost=${cost_s} "
            f"openedNotes={rn} notesInResults={gn} | {flags}"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
