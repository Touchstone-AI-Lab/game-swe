"""Build versioned maintenance controls outside the benchmark (never model inputs)."""
import argparse
import shutil
from pathlib import Path

VARIANTS = ("nop", "gold", "four-second-replacement")
STARTER = "l4d1_2_plugins"

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

if args.variant == "four-second-replacement":
    path = out / STARTER / "l4dinfectedbots/scripting/l4dinfectedbots.sp"
    text = path.read_text(encoding="utf-8-sig")
    old = "if(g_bInitialSpawn) SpawnTime = g_ePluginSettings.m_fInitialSpawnTime;"
    assert text.count(old) == 2
    # Add a competing four-second death timer in the player-controlled branch.
    # Merely changing SpawnTime has no effect: gold intentionally reuses the
    # initial wave and does not enqueue a death timer in this branch.
    replacement = """if(g_bInitialSpawn)
        {
            SpawnTime = g_ePluginSettings.m_fInitialSpawnTime;
            InfectedBotQueue++;
            for (int slot = 1; slot <= MaxClients; slot++)
            {
                if (SpawnInfectedBotTimer[slot] == null)
                {
                    SpawnInfectedBotTimer[slot] = CreateTimer(4.0, Timer_Spawn_InfectedBot, slot);
                    break;
                }
            }
        }"""
    text = text.replace(old, replacement, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
print(out)
