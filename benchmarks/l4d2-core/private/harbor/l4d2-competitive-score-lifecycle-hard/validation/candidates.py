from pathlib import Path
import shutil

RELATIVE = Path("addons/sourcemod/scripting/l4d2_hybrid_scoremod_zone.sp")


def function(source: str, name: str) -> tuple[int, int]:
    """Locate a complete SourcePawn function, including nested blocks."""
    import re
    match = re.search(r"^.*\b" + re.escape(name) + r"\([^\n]*\)\s*\n\{", source, re.MULTILINE)
    if match is None:
        raise ValueError(name)
    opening = source.index("{", match.start())
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return match.start(), end


def materialize(task: Path, candidate: str, destination: Path) -> None:
    if candidate not in {"nop", "gold", "alternative", "minus-finalized-guards", *(f"minus-report-{i}" for i in range(1, 8))}:
        raise ValueError(candidate)
    shutil.copytree(task / "environment/l4d2-competitive", destination)
    if candidate == "nop":
        return
    shutil.copytree(task / "solution/after", destination, dirs_exist_ok=True)
    original = (task / "environment/l4d2-competitive" / RELATIVE).read_text(encoding="utf-8")
    path = destination / RELATIVE
    source = path.read_text(encoding="utf-8")
    if candidate == "alternative":
        # User IDs also identify one connection lifetime. An explicit minimum
        # computes the same bounded refund without gold's sequential clamps.
        source = source.replace("pending.WriteCell(GetClientSerial(client));", "pending.WriteCell(GetClientUserId(client));")
        source = source.replace("GetClientFromSerial(pending.ReadCell())", "GetClientOfUserId(pending.ReadCell())")
        source = source.replace("int refund = GetSurvivorTemporaryHealth(client);\n    if (refund > debit) refund = debit;\n    if (refund > iLostTempHealth[half]) refund = iLostTempHealth[half];", "int available = GetSurvivorTemporaryHealth(client);\n    int ceiling = debit < iLostTempHealth[half] ? debit : iLostTempHealth[half];\n    int refund = available < ceiling ? available : ceiling;")
        source = source.replace("if (oldHealth < 0) oldHealth = 0;\n    if (newHealth < 0) newHealth = 0;\n    int healthLost = oldHealth - newHealth;", "int healthLost = (oldHealth > 0 ? oldHealth : 0) - (newHealth > 0 ? newHealth : 0);")
        source = source.replace("int healthLost = (oldHealth", "int healthLost = (oldHealth")
        # Clamp the saved snapshot independently too.
        source = source.replace("iTempHealth[client] = newHealth;", "iTempHealth[client] = newHealth > 0 ? newHealth : 0;")
    elif candidate == "minus-finalized-guards":
        for name in ("OnTakeDamage", "OnTakeDamagePost", "OnPlayerHurt"):
            a, b = function(source, name)
            body = source[a:b].replace("bRoundOver || ", "")
            source = source[:a] + body + source[b:]
    elif candidate.startswith("minus-report-"):
        group = int(candidate.rsplit("-", 1)[1])
        functions = {
            1: ("GetAliveSurvivorCount", "GetSurvivorPillBonus"),
            2: (), 3: ("OnConfigsExecuted",),
            4: ("L4D2_ADM_OnTemporaryHealthSubtracted",),
            5: ("OnPlayerLedgeGrab", "OnPlayerRevived", "Revival"),
            6: ("RoundStartEvent",), 7: ("OnPluginEnd",),
        }[group]
        for name in functions:
            a, b = function(source, name)
            x, y = function(original, name)
            source = source[:a] + original[x:y] + source[b:]
        if group == 2:
            source = source.replace("    HookConVarChange(hCvarPillsHpFactor, CvarChanged);", "")
            source = source.replace("    HookConVarChange(hCvarPillsMaxBonus, CvarChanged);", "")
            source = source.replace('    HookConVarChange(FindConVar("survivor_limit"), CvarChanged);', "")
    path.write_text(source, encoding="utf-8", newline="\n")
