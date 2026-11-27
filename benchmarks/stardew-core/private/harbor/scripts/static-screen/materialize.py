"""Build a Hub-equivalent Stardew attempt workspace for one task and variant."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]
PACK = REPO / "benchmarks/stardew-core"
NOTES = "StardewMods/Automate/docs/release-notes.md"


def public_instruction(text: str) -> str:
    return (
        text.replace("/app/StardewMods", "StardewMods")
        .replace("/app/mod", "mod")
        .replace("anything under `/tests`", "the private verifier")
    )


def main(task: str, variant: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    env = PACK / "private/harbor" / task / "environment"
    shutil.copytree(env / "StardewMods", dest / "StardewMods")
    # note (luojiaxuan): the "leaked" variant restores the release notes exactly as origin/main ships them.
    if variant == "leaked":
        rel = f"benchmarks/stardew-core/private/harbor/{task}/environment/{NOTES}"
        shipped = subprocess.run(
            ["git", "-C", str(REPO), "show", f"origin/main:{rel}"],
            check=True, capture_output=True,
        ).stdout
        (dest / NOTES).write_bytes(shipped)
    marker = {"difficulty": "hard", "submission": ".", "fromScratch": False, "language": "csharp"}
    (dest / "task.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    exam = public_instruction((PACK / "exams" / f"{task}.md").read_text(encoding="utf-8"))
    (dest / "EXAM.md").write_text(exam.rstrip() + "\n", encoding="utf-8")
    (dest / "AGENTS.md").write_text(
        "# Stardew Valley benchmark guidance\n\n"
        "Work only inside this attempt directory. Do not inspect the benchmark "
        "repository, plugin, tests, reference solution, prior runs, or state database. "
        "Implement the public contract in EXAM.md using the provided C# source tree. "
        "Do not use external implementations or network lookup. In strict mode, run the "
        "approved scorer exactly once after implementation and do not edit afterward.\n",
        encoding="utf-8",
    )
    (dest / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
