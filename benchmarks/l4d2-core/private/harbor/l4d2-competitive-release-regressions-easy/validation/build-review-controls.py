"""Build versioned maintenance controls outside the benchmark (never model inputs)."""
import argparse
import shutil
from pathlib import Path

VARIANTS = ("nop", "gold", "empty-timestamp-rewrite")
STARTER = "l4d2-competitive"

TASK = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("variant", choices=VARIANTS)
parser.add_argument("destination", type=Path)
args = parser.parse_args()
out = args.destination.resolve()
if out == TASK or TASK in out.parents:
    parser.error("destination must be outside the benchmark task")
if out.exists():
    parser.error("destination must not exist; controls never overwrite earlier evidence")
shutil.copytree(TASK / "environment" / STARTER, out / STARTER)
if args.variant != "nop":
    after = TASK / "solution/after"
    source = after / STARTER if (after / STARTER).is_dir() else after
    shutil.copytree(source, out / STARTER, dirs_exist_ok=True)

def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8-sig")
    if text.count(old) != 1:
        raise ValueError(f"control anchor changed: {path}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

if args.variant == "empty-timestamp-rewrite":
    path = out / STARTER / "addons/sourcemod/scripting/l4d2_incap_fire_fix.sp"
    replace_once(path,
        '\t\tif (wep != -1 && GetEntProp(wep, Prop_Send, "m_iClip1") > 0)',
        '\t\tif (wep != -1 && GetEntProp(wep, Prop_Send, "m_iClip1") == 0)\n'
        '\t\t\tSetEntPropFloat(wep, Prop_Send, "m_flNextSecondaryAttack", GetGameTime() - 5.0);\n'
        '\t\tif (wep != -1 && GetEntProp(wep, Prop_Send, "m_iClip1") > 0)')
print(out)
