"""Materialize maintainer controls outside the read-only benchmark tree."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def section(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


def replace(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"control anchor must occur exactly once: {old[:70]}")
    return text.replace(old, new)


def materialize(task: Path, candidate: str, destination: Path) -> None:
    if destination.exists():
        raise ValueError("control destination must be new")
    if destination.resolve().is_relative_to(task.resolve()):
        raise ValueError("generated controls must remain outside the task")
    source = task / "environment/linge-hud"
    shutil.copytree(source, destination)
    if candidate == "nop":
        return
    shutil.copytree(task / "solution/after", destination, dirs_exist_ok=True)
    base_path = destination / "vscripts/LinGe/Base.nut"
    si_path = destination / "vscripts/LinGe/MoreSI.nut"
    base = base_path.read_text(encoding="utf-8")
    si = si_path.read_text(encoding="utf-8")
    old_base = (source / "vscripts/LinGe/Base.nut").read_text(encoding="utf-8")
    old_si = (source / "vscripts/LinGe/MoreSI.nut").read_text(encoding="utf-8")
    whitelist_end = "// 输出当前设置信息"
    if candidate == "gold":
        return
    if candidate == "alternative":
        # Use sorted index validation rather than an indexed lookup table.
        start = '            local indexed = {}, valid = true;'
        end = '            if (valid) dest[target] = values;'
        old = section(base, start, end) + end
        new = '''            local entries = [], valid = true;
            foreach (key, value in val)
            {
                if (typeof key != "integer" && typeof key != "string") {valid=false;break;}
                local index = null;
                try {index=key.tointeger();} catch(e) {valid=false;break;}
                if (index<0 || (typeof key=="string" && index.tostring()!=key)) {valid=false;break;}
                entries.append({index=index,value=value});
            }
            entries.sort(@(a,b) a.index <=> b.index);
            local result=[];
            foreach (position, entry in entries)
            {
                if (position!=entry.index) {valid=false;break;}
                result.append(::LinGe.DeepClone(entry.value));
            }
            if (valid) dest[target]=result;'''
        base = replace(base, old, new)
        base = replace(base, "local snapshot = clone callback;",
                       "local snapshot = [];\n\tforeach (registration in callback) snapshot.append(registration);")
        base = base.replace("ReadFile", "ReadDocument")
        base = replace(base, '        SaveAll();\n    }\n    function SaveAll()',
                       '        foreach (name, value in table) if (value != null) Save(name);\n    }\n    function SaveAll()')
        si = replace(si, '    local result = [];', '    local result = [], seen = {};')
        si = replace(si, 'value.tolower() == valid.tolower() && result.find(valid) == null',
                     'value.tolower() == valid.tolower() && !seen.rawin(valid)')
        si = replace(si, '{ result.append(valid); break; }',
                     '{ seen.rawset(valid, true); result.append(valid); break; }')
    elif candidate == "minus-report-1":
        base = base.replace('::LinGe.DeepClone(val)', 'val')
        base = replace(base, '        local dt = typeof dest[target], st = typeof val;',
                       '        if (target != key) source.rawset(target, val);\n        local dt = typeof dest[target], st = typeof val;')
    elif candidate == "minus-report-2":
        old = section(base, '            local indexed = {}, valid = true;',
                      '            if (valid) dest[target] = values;') + '            if (valid) dest[target] = values;'
        base = replace(base, old, '            local values=[];\n            foreach(value in val) values.append(::LinGe.DeepClone(value));\n            dest[target]=values;')
    elif candidate == "minus-report-3":
        start, end = 'class ::LinGe.ConfigManager', 'local FILE_CONFIG'
        base = replace(base, section(base, start, end), section(old_base, start, end))
    elif candidate == "minus-report-4":
        base = replace(base, 'local snapshot = clone callback;', 'local snapshot = callback;')
    elif candidate == "minus-report-5":
        base = replace(base, 'local original = ::LinGe.DeepClone(params);', 'local original = params;')
        base = base.replace('::LinGe.DeepClone(original)', '(original == null ? null : clone original)')
    elif candidate == "minus-report-6":
        base = replace(base, '@(params) ::LinGe.Events.trigger[event][event](params), ::LinGe.DeepClone(params));',
                       '@(params) ::LinGe.Events.trigger[event][event](params), params);')
    elif candidate == "minus-report-7":
        start = '::LinGe.MoreSI.Checksionly <- function'
        si = replace(si, section(si, start, whitelist_end), section(old_si, start, whitelist_end))
    elif candidate == "minus-report-8":
        si = replace(si, 'if (simax > 31)', 'else if (simax > 31)')
    elif candidate == "minus-report-9":
        start = '::LinGe.MoreSI.Checksionly <- function'
        repaired_whitelist = section(si, start, whitelist_end)
        si = replace(old_si, section(old_si, start, whitelist_end), repaired_whitelist)
        si = replace(si, 'else if (simax > 31)', 'if (simax > 31)')
    else:
        raise ValueError(f"unknown control {candidate}")
    base_path.write_text(base, encoding="utf-8", newline="\n")
    si_path.write_text(si, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=["nop", "gold", "alternative"] + [f"minus-report-{i}" for i in range(1, 10)])
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    materialize(Path(__file__).resolve().parents[1], args.candidate, args.destination)
