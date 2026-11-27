"""Build versioned maintenance controls outside the benchmark (never model inputs)."""
import argparse
import shutil
import subprocess
from pathlib import Path

VARIANTS = ("nop", "gold", "equivalent-long-docs")
STARTER = "left4dhooks"

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
    # solve.sh also applies three fixes outside solution/after.
    patch_tool = shutil.which("patch")
    if patch_tool is None:
        windows_patch = Path("C:/Program Files/Git/usr/bin/patch.exe")
        if windows_patch.is_file():
            patch_tool = str(windows_patch)
    if patch_tool is None:
        parser.error("GNU patch is required to reproduce the complete gold solution")
    for name in ("animhook.patch", "campaignscores.patch", "meleeinfo.patch"):
        with (TASK / "solution" / name).open("rb") as patch_input:
            subprocess.run([patch_tool, "--batch", "--forward", "--no-backup-if-mismatch",
                            "-d", str(out / STARTER), "-p1"], stdin=patch_input, check=True)


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8-sig")
    if text.count(old) != 1:
        raise ValueError(f"control anchor changed: {path}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

if args.variant == "equivalent-long-docs":
    path = out / STARTER / "sourcemod/scripting/include/left4dhooks.inc"
    text = path.read_text(encoding="utf-8-sig")
    declaration = "native float L4D2Direct_GetSpawnTimer(int client);"
    end = text.index(declaration)
    start = text.rfind("/**", 0, end)
    assert start >= 0
    docs = (
        "/**\n * Returns the engine timestamp stored in m_flBecomeGhostAt (seconds),\n"
        " * rather than the remaining duration; invalid client indices return -1.0.\n"
        " * @param client Client index.\n"
        + " * This read does not schedule a spawn or change player state.\n" * 24
        + " */\n"
    )
    assert "absolute" not in docs and len(docs) > 900
    path.write_text(text[:start] + docs + text[end:], encoding="utf-8", newline="\n")
print(out)
