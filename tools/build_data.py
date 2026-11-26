#!/usr/bin/env python3
"""Build src/data.json for the GameSWE website from the paper checkout.

    python tools/build_data.py <paper_dir>

<paper_dir> is the Overleaf paper checkout (the folder holding `source/` and `analysis/`).
Reads only aggregate numbers:
  analysis/r30/data/e1-paper-stats.json   per-model and per-game resolution rates, funnel, stages
  source/table/main_results.tex           per-game repair / construction rates (Table 2)
  source/data/inventory_macros.tex        task totals
Every internal model id is replaced by a public slug, and the output is checked for leaks.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "data.json"

# Model name in the stats file -> public slug, display name (as in Table 2), icon file in public/icons.
# Keyed by display name so that no internal run id appears in this public script.
MODELS = {
    "Claude Opus 5.5": ("claude-opus-5-5", "Claude Opus 5.5", "claude-color.svg"),
    "GPT-6 Astra": ("gpt-6-astra", "GPT-6 Astra", "openai.svg"),
    "Kimi K3.1 Pro": ("kimi-k3-1-pro", "Kimi K3.1 Pro", "kimi-color.svg"),
    "DeepSeek Flash": ("deepseek-v4-1-flash", "DeepSeek-V4.1-Flash", "deepseek-color.svg"),
    "MiniMax M3.1 Flash": ("minimax-m3-1-flash", "MiniMax M3.1 Flash", "minimax-color.svg"),
    "GLM 5.3 Flash": ("glm-5-3-flash", "GLM 5.3 Flash", "zhipu-color.svg"),
    "Qwen 3.8 27B": ("qwen-3-8-27b", "Qwen 3.8 27B", "qwen-color.svg"),
}

# Internal game id -> public slug, short name, mod language, runtime (paper appendix, Table "Games in GameSWE").
GAMES = {
    "minecraft": ("minecraft", "Minecraft", "Java", "Paper server"),
    "stardew-valley": ("stardew-valley", "Stardew Valley", "C#", "Desktop game · SMAPI"),
    "garrys-mod": ("garrys-mod", "Garry's Mod", "GLua", "Dedicated server"),
    "dst": ("dont-starve-together", "Don't Starve Together", "Lua", "Dedicated server"),
    "terraria": ("terraria", "Terraria", "C#", "Dedicated server · tModLoader"),
    "rimworld": ("rimworld", "RimWorld", "C#", "Desktop game"),
    "mindustry": ("mindustry", "Mindustry", "Java", "Headless server"),
    "palworld": ("palworld", "Palworld", "Lua · UE4SS", "Dedicated server"),
    "isaac-rebirth": ("binding-of-isaac", "The Binding of Isaac", "Lua", "Desktop game"),
    "left-4-dead-2": ("left-4-dead-2", "Left 4 Dead 2", "SourcePawn · Squirrel", "Dedicated server"),
    "balatro": ("balatro", "Balatro", "Lua", "Desktop game"),
    "slay-the-spire": ("slay-the-spire", "Slay the Spire", "Java", "Desktop game · ModTheSpire"),
}

# Column headers of Table 2, flattened, mapped to internal game ids.
TABLE_HEADERS = {
    "Minecraft": "minecraft", "StardewValley": "stardew-valley", "Garry'sMod": "garrys-mod",
    "Don'tStarveTogether": "dst", "Terraria": "terraria", "RimWorld": "rimworld",
    "Mindustry": "mindustry", "Palworld": "palworld", "TheBindingofIsaac": "isaac-rebirth",
    "Left4Dead2": "left-4-dead-2", "Balatro": "balatro", "SlaytheSpire": "slay-the-spire", "Total": "total",
}

# Facts stated in the paper text (source/sections/benchmark.tex and protocol.tex), not in the stats file.
PAPER_FACTS = {
    "languages": 5,             # benchmark.tex: "span five programming languages"
    "candidates": 250,          # benchmark.tex: "We initially collect 250 candidate tasks"
    "thirdPartyTasks": 20,      # benchmark.tex: "the submission runs with them loaded (20 tasks)"
    "medianF2P": 11,            # benchmark.tex: "a median of 11 F2P and 4 P2P tests"
    "medianP2P": 4,
    "medianRepairLoc": 8918,    # benchmark.tex: "a median of 8,918 non-blank lines of mod source"
    "medianRepairPatch": 54,    # benchmark.tex: "its reference solution changes a median of 54 lines"
    "medianConstructAdded": 379.5,  # benchmark.tex: "its reference adds a median of 379.5 lines"
    "stepLimit": 100,           # results_macros_generated.tex: \EOneStepLimit
    "wallMinutes": 90,          # results_macros_generated.tex: \EOneWallMinutes
    "scaffold": "mini-swe-agent",
}

# The output holds numbers and public names only: no links, no paths. Internal run ids are added at runtime.
FORBIDDEN = ["http", "/home/", "\\", "isaac-rebirth\"", "\"dst\""]


def die(msg: str) -> None:
    sys.exit(f"build_data: {msg}")


def macro(tex: str, name: str) -> int:
    m = re.search(r"\\newcommand\{\\" + name + r"\}\{(\d+)\}", tex)
    if not m:
        die(f"macro \\{name} not found")
    return int(m.group(1))


def strip_tex(cell: str) -> str:
    cell = re.sub(r"\\cellcolor\[HTML\]\{[0-9A-Fa-f]+\}", "", cell)
    cell = re.sub(r"\\(textbf|underline)\{([^}]*)\}", r"\2", cell)
    cell = re.sub(r"\\textcolor\{gray\}\{--\}", "--", cell)
    return cell.strip()


def parse_table(tex: str) -> dict[str, dict[str, dict[str, float | None]]]:
    """Return {display name: {internal game id: {all, rep, con}}} from both panels of Table 2."""
    rows: dict[str, dict[str, dict[str, float | None]]] = {}
    headers: list[str] = []
    for line in tex.splitlines():
        if "\\multicolumn{3}{c}" in line:
            names = re.findall(r"@\{\}c@\{\}\}(.*?)\\end\{tabular\}", line)
            headers = [TABLE_HEADERS[re.sub(r"\\\\|\s", "", n)] for n in names]
            continue
        if not line.startswith("\\osmodelicon"):
            continue
        body = re.sub(r"^\\osmodelicon\{[^}]*\}", "", line).rstrip().removesuffix("\\\\")
        cells = [strip_tex(c) for c in body.split("&")]
        name, vals = cells[0], cells[1:]
        if len(vals) != 3 * len(headers):
            die(f"row {name!r} has {len(vals)} cells for {len(headers)} games")
        row = rows.setdefault(name, {})
        for i, g in enumerate(headers):
            a, r, c = (None if v == "--" else float(v) for v in vals[3 * i:3 * i + 3])
            row[g] = {"all": a, "rep": r, "con": c}
    return rows


def split_counts(n: int, cells: list[dict[str, float | None]]) -> tuple[int, int]:
    """Find the repair / construction split of an n-task game that reproduces every rounded rate."""
    def fits(rate: float | None, k: int) -> bool:
        if rate is None:
            return k == 0
        if k == 0:
            return False
        x = rate * k / 100
        return abs(x - round(x)) < 0.051 * k / 100 + 1e-9

    hits = []
    for r in range(n + 1):
        c = n - r
        ok = True
        for cell in cells:
            if not (fits(cell["rep"], r) and fits(cell["con"], c)):
                ok = False
                break
            solved = (round(cell["rep"] * r / 100) if r else 0) + (round(cell["con"] * c / 100) if c else 0)
            if abs(solved / n * 100 - cell["all"]) > 0.051:
                ok = False
                break
        if ok:
            hits.append((r, c))
    if len(hits) != 1:
        die(f"repair/construction split of a {n}-task game is not unique: {hits}")
    return hits[0]


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: -values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** 0.5
    vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb)


def r1(x: float) -> float:
    return round(x + 1e-9, 1)


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: python tools/build_data.py <paper_dir>")
    paper = Path(sys.argv[1])
    stats_path = paper / "analysis/r30/data/e1-paper-stats.json"
    stats = json.loads(stats_path.read_text())
    table = parse_table((paper / "source/table/main_results.tex").read_text())
    inv = (paper / "source/data/inventory_macros.tex").read_text()
    n_tasks, n_rep, n_con, n_games = (macro(inv, m) for m in ("ntasks", "nrepair", "nconstruct", "nhosts"))

    if sorted(stats["names"][m] for m in stats["order"]) != sorted(MODELS) or set(stats["games"]) != set(GAMES):
        die("model or game ids in the stats file do not match the mappings")
    M = {mid: MODELS[stats["names"][mid]] for mid in stats["order"]}
    by_name = {M[m][1]: m for m in M}
    if set(table) != set(by_name):
        die(f"Table 2 rows {sorted(table)} do not match the model names")

    models = []
    for mid in stats["order"]:
        slug, name, icon = M[mid]
        res = stats["res"][mid]
        f = stats["funnel"][mid]
        tot = table[name]["total"]
        if r1(res["macro"]) != tot["all"] or r1(res["repair"]) != tot["rep"] or r1(res["construct"]) != tot["con"]:
            die(f"{name}: stats file and Table 2 totals disagree")
        models.append({
            "slug": slug, "name": name, "icon": icon,
            "overall": r1(res["macro"]), "repair": r1(res["repair"]), "construct": r1(res["construct"]),
            "f2pOnly": r1(res["f2pOnlyMacro"]), "resolved": res["resolvedCount"],
            "funnel": {k: r1(f[k]) for k in ("changed", "reachedTests", "f2p", "f2pAndP2p", "resolved")},
        })
    models.sort(key=lambda m: -m["overall"])
    slug_of = {mid: M[mid][0] for mid in M}

    games = []
    rho = []
    for gid in stats["games"]:
        slug, name, lang, runtime = GAMES[gid]
        gs = stats["gameStats"][gid]
        n = gs["nTasks"]
        cells = [table[M[mid][1]][gid] for mid in stats["order"]]
        rep, con = split_counts(n, cells)
        scores = {}
        for mid in stats["order"]:
            cell = table[M[mid][1]][gid]
            if r1(stats["res"][mid]["perGame"][gid]) != cell["all"]:
                die(f"{name} / {M[mid][1]}: stats file and Table 2 disagree")
            scores[slug_of[mid]] = cell
        games.append({
            "slug": slug, "name": name, "language": lang, "runtime": runtime,
            "tasks": n, "repair": rep, "construct": con,
            "best": r1(gs["best"]), "bestModels": [slug_of[m] for m in gs["bestModels"]], "mean": r1(gs["mean"]),
            "scores": scores,
        })
        rho.append(spearman([stats["res"][m]["perGame"][gid] for m in stats["order"]],
                            [stats["res"][m]["macro"] for m in stats["order"]]))

    st = stats["stageAll"]
    unresolved = sum(st.values())
    own = stats["own"].values()
    submitted = sum(o["submitted"] for o in own)
    claims = sum(o["claims"] for o in stats["own"].values())
    attempts = n_tasks * len(models)
    findings = {
        "attempts": attempts, "unresolved": unresolved,
        "stages": [
            {"key": "unchanged", "label": "Left the code unchanged", "n": st["unchanged"]},
            {"key": "preTest", "label": "Failed to build or load", "n": st["preTest"]},
            {"key": "f2pFail", "label": "Failed fail-to-pass tests in the game", "n": st["f2pFail"]},
            {"key": "later", "label": "Passed F2P tests, still unresolved", "n": st["p2pOnly"] + st["other"]},
        ],
        "inGameFail": st["f2pFail"], "inGameFailShare": r1(st["f2pFail"] / attempts * 100),
        "submitted": submitted, "submittedShare": r1(submitted / unresolved * 100),
        "claims": claims, "claimsShare": r1(claims / unresolved * 100),
        "rho": round(sum(rho) / len(rho), 2),
    }

    totals = {
        "tasks": n_tasks, "repair": n_rep, "construct": n_con, "games": n_games, "models": len(models),
        "attempts": attempts, **PAPER_FACTS,
    }
    if (n_tasks, n_rep, n_con, n_games, len(models)) != (150, 100, 50, 12, 7):
        die("unexpected totals")
    if sum(g["tasks"] for g in games) != n_tasks or sum(g["repair"] for g in games) != n_rep \
            or sum(g["construct"] for g in games) != n_con:
        die("per-game task counts do not add up to the totals")
    if sum(m["resolved"] for m in models) != attempts - unresolved:
        die("resolved and unresolved attempts do not add up")

    data = {"asOf": "2026-11-21", "totals": totals, "models": models, "games": games, "findings": findings}
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    for bad in FORBIDDEN + [m for m in M if m != M[m][0]]:
        if bad in text:
            die(f"output contains forbidden string {bad!r}")
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(models)} models, {len(games)} games, rho={findings['rho']}")


if __name__ == "__main__":
    main()
