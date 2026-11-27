"""Maintainer controls; never distributed to an exam attempt."""
from pathlib import Path
import shutil


def replace_once(text: str, before: str, after: str) -> str:
    assert text.count(before) == 1, before
    return text.replace(before, after)


def materialize(task: Path, candidate: str, destination: Path) -> None:
    choices = {"nop", "gold", "alternative", "minus-death-postponed", "minus-syntax-validation"} | {f"minus-report-{i}" for i in range(1, 9)}
    if candidate not in choices:
        raise ValueError(candidate)
    shutil.copytree(task / "environment/l4d2-competitive", destination)
    if candidate == "nop":
        return
    shutil.copytree(task / "solution/after", destination, dirs_exist_ok=True)
    if candidate == "gold":
        return
    root = destination / "addons/sourcemod/scripting/l4d2lib"
    map_path, tank_path = root / "mapinfo.sp", root / "tanks.sp"
    mapping, tank = map_path.read_text(encoding="utf-8"), tank_path.read_text(encoding="utf-8")
    if candidate == "alternative":
        mapping = replace_once(mapping,
            "if ((GetVectorDistance(fOrigins, g_fStartPoint) <= (g_fStartExtraDist > g_fStartDist ? g_fStartExtraDist : g_fStartDist))) {",
            "float radius = g_fStartExtraDist > g_fStartDist ? g_fStartExtraDist : g_fStartDist;\n\tif (radius >= 0.0 && GetVectorDistance(fOrigins, g_fStartPoint, true) <= radius * radius) {")
        mapping = replace_once(mapping, "if (GetVectorDistance(fOrigins, g_fEndPoint) <= g_fEndDist) {",
            "if (g_fEndDist >= 0.0 && GetVectorDistance(fOrigins, g_fEndPoint, true) <= g_fEndDist * g_fEndDist) {")
        tank = replace_once(tank, "int previous = g_iTankClient, passes = g_iTankPassCount++;",
            "int previous = g_iTankClient, passes = g_iTankPassCount;\n    g_iTankPassCount += 1;")
    elif candidate == "minus-syntax-validation":
        mapping = replace_once(mapping, "parsed != SMCError_Okay || !incoming.ImportFromFile(sNameBuff)",
            "!incoming.ImportFromFile(sNameBuff)")
    elif candidate == "minus-report-1":
        mapping = replace_once(mapping, "void MapInfo_Reload()\n{\n\tMI_KV_Load();\n\tMI_KV_UpdateMapInfo();",
            "void MapInfo_Reload()\n{\n\tMI_KV_Load();")
    elif candidate == "minus-report-2":
        mapping = replace_once(mapping, "return MI_SelectMap() ? KvGetNum(g_hMIData, sKey, iDefVal) : iDefVal;",
            "return g_bMapDataAvailable ? KvGetNum(g_hMIData, sKey, iDefVal) : iDefVal;")
    elif candidate == "minus-report-3":
        mapping = replace_once(mapping, "iNewLen = iLen;\n\tchar[] sBuf", "iNewLen = iLen + 1;\n\tchar[] sBuf")
    elif candidate == "minus-report-4":
        mapping = mapping.replace("GetVectorDistance(fOrigins, g_fStartPoint) <=", "GetVectorDistance(fOrigins, g_fStartPoint) <")
        mapping = mapping.replace("GetVectorDistance(fOrigins, g_fEndPoint) <=", "GetVectorDistance(fOrigins, g_fEndPoint) <")
    elif candidate == "minus-report-5":
        tank = replace_once(tank, '&& GetClientTeam(client) == 3 && GetEntProp(client, Prop_Send, "m_zombieClass") == 8;', ';')
    elif candidate == "minus-report-6":
        tank = replace_once(tank, "delete g_hTankDeathTimer;\n    Call_StartForward(g_hFwdTankPassControl);",
            "Call_StartForward(g_hFwdTankPassControl);")
    elif candidate == "minus-report-7":
        tank = replace_once(tank, "g_bIsTankActive && GetClientFromSerial(g_TankSerial) == g_iTankClient",
            "g_bIsTankActive && IsClientInGame(g_iTankClient)")
        tank = replace_once(tank, "if (g_bIsTankActive && client == g_iTankClient) ResetStatus();", "// Slot-only ownership: disconnect retirement omitted.")
    elif candidate == "minus-death-postponed":
        tank = replace_once(tank, "\n        || g_hTankDeathTimer != null) return;", ") return;")
        tank = replace_once(tank, "    g_hTankDeathTimer = CreateTimer(0.5,", "    delete g_hTankDeathTimer;\n    g_hTankDeathTimer = CreateTimer(0.5,")
    elif candidate == "minus-report-8":
        tank = replace_once(tank, "int previous = g_iTankClient, passes = g_iTankPassCount++;",
            "int previous = g_iTankClient, passes = g_iTankPassCount;")
        tank = replace_once(tank, "Call_PushCell(previous);Call_PushCell(client);Call_PushCell(passes);\n    Call_Finish();",
            "Call_PushCell(previous);Call_PushCell(client);Call_PushCell(passes);\n    Call_Finish();\n    g_iTankPassCount++;")
    map_path.write_text(mapping, encoding="utf-8", newline="\n")
    tank_path.write_text(tank, encoding="utf-8", newline="\n")
