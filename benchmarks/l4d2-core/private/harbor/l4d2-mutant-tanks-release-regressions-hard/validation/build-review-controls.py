"""Materialize the revised reference and deferred-spawn maintenance controls."""
import argparse
import shutil
from pathlib import Path

task = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("variant", choices=("nop", "gold", "deferred-half-second", "deferred-too-late"))
parser.add_argument("destination", type=Path)
args = parser.parse_args()
destination = args.destination.resolve()
if destination.exists() or destination.is_relative_to(task):
    parser.error("destination must be new and outside the task")
source = destination / "mutant-tanks"
shutil.copytree(task / "environment/mutant-tanks", source)
if args.variant == "nop":
    raise SystemExit(0)
shutil.copytree(task / "solution/after", source, dirs_exist_ok=True)

# Apply the two exact single-line changes in solution/cooldown.patch without
# depending on a platform-specific patch executable. Check its provenance too.
patch = (task / "solution/cooldown.patch").read_text(encoding="utf-8")
for ability in ("Acid", "Ammo"):
    path = source / f"addons/sourcemod/scripting/mutant_tanks/abilities/mt_{ability.lower()}.sp"
    old = (
        f"if ((flags & MT_ATTACK_RANGE) && g_es{ability}Player[tank].g_iRangeCooldown != -1 "
        f"&& g_es{ability}Player[tank].g_iRangeCooldown >= iTime)"
    )
    new = (
        f"if (((flags & MT_ATTACK_RANGE) && g_es{ability}Player[tank].g_iRangeCooldown != -1 "
        f"&& g_es{ability}Player[tank].g_iRangeCooldown >= iTime) || "
        f"(((flags & MT_ATTACK_CLAW) || (flags & MT_ATTACK_MELEE)) "
        f"&& g_es{ability}Player[tank].g_iCooldown != -1 && g_es{ability}Player[tank].g_iCooldown >= iTime))"
    )
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1 and "-\t" + old in patch and "+\t" + new in patch
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

if args.variant.startswith("deferred-"):
    path = source / "addons/sourcemod/scripting/mutant_tanks/abilities/mt_hypno.sp"
    text = path.read_text(encoding="utf-8")
    old = "{\n\tvHypno(tank);\n}\n\nvoid vHypno(int tank)"
    delay = "0.5" if args.variant == "deferred-half-second" else "2.0"
    new = """{
    CreateTimer(DELAY, tReviewDeferredHypno, GetClientUserId(tank), TIMER_FLAG_NO_MAPCHANGE);
}

Action tReviewDeferredHypno(Handle timer, any userid)
{
    int tank = GetClientOfUserId(userid);
    if (tank > 0 && IsClientInGame(tank) && IsPlayerAlive(tank)
        && MT_IsTankSupported(tank) && MT_IsCustomTankSupported(tank)) vHypno(tank);
    return Plugin_Stop;
}

void vHypno(int tank)""".replace("DELAY", delay)
    assert text.count(old) == 1
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
