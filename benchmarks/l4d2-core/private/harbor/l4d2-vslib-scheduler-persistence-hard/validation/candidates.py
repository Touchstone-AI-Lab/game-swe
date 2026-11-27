from pathlib import Path
import shutil

def materialize(task: Path, candidate: str, destination: Path) -> None:
    if candidate not in {"nop", "gold", "alternative", "gold-timer", "gold-data", "reject-opaque-payloads", *{f"minus-report-{i}" for i in range(1, 9)}}:
        raise ValueError(candidate)
    shutil.copytree(task / "environment/linge-hud", destination)
    if candidate in {"gold", "alternative", "reject-opaque-payloads"} or candidate.startswith("minus-report-"):
        shutil.copytree(task / "solution/after", destination, dirs_exist_ok=True)
    elif candidate in {"gold-timer", "gold-data"}:
        names = ("VSLib/timer.nut", "VSLib/easylogic.nut") if candidate == "gold-timer" else ("VSLib/fileio.nut", "Base.nut")
        for name in names:
            relative = Path("vscripts/LinGe") / name
            shutil.copy2(task / "solution/after" / relative, destination / relative)
    root = destination / "vscripts/LinGe"
    def edit(name, old, new):
        path = root / name
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise ValueError(f"missing mutation anchor: {name}: {old}")
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    if candidate == "reject-opaque-payloads":
        # Recreate the old reference regression while retaining all other fixes.
        edit("VSLib/timer.nut", '(flags & (4 | 8)) && paramTable != null', 'paramTable != null')
    elif candidate == "alternative":
        # Deliberately different ordering and valid numeric/whitespace encoding.
        edit("VSLib/timer.nut", "foreach (entry in snapshot)", "snapshot.reverse();\n    foreach (entry in snapshot)")
        edit("VSLib/fileio.nut", 'format("%.9g", value)', 'format("%.9e", value)')
        edit("VSLib/fileio.nut", 'out += ::VSLib.FileIO._Encode(item, ancestors) + ",\\n";', 'out += ::VSLib.FileIO._Encode(item, ancestors) + " ";')
    elif candidate == "minus-report-1":
        edit("VSLib/timer.nut", "if (!(id in timers.TimersList) || timers.TimersList[id] != timer) continue;", "// omitted stale-entry check")
    elif candidate == "minus-report-2":
        edit("VSLib/timer.nut", "foreach (name in names) delete TimersID[name];", "// omitted exported identity retirement")
    elif candidate == "minus-report-3":
        edit("VSLib/timer.nut", "local options = clone value;", "local options = value;")
    elif candidate == "minus-report-4":
        edit("VSLib/timer.nut", "_SettleClock(ClockList[idx], now);", "// transition does not settle old clock mode")
        edit("VSLib/timer.nut", "_SettleClock(ClockList[idx], Time());", "// read returns stale value")
    elif candidate == "minus-report-5":
        edit("VSLib/fileio.nut", 'return modern ? result : ::VSLib.FileIO.DeserializeReviseTable(result);', 'return ::VSLib.FileIO.DeserializeReviseTable(result);')
    elif candidate == "minus-report-6":
        edit("VSLib/fileio.nut", 'ancestors.pop();', '// wrongly retain noncyclic siblings in ancestor set')
    elif candidate == "minus-report-7":
        edit("VSLib/fileio.nut", 'regexp("^_vslInt_(0|[1-9][0-9]*)$").match(key)', 'key.find("_vslInt_") != null')
    elif candidate == "minus-report-8":
        edit("VSLib/fileio.nut", 'local reader = ::VSLib.FileIO._DataReader(text);', 'if (!modern) return compilestring("return " + text)();\n        local reader = ::VSLib.FileIO._DataReader(text);')
