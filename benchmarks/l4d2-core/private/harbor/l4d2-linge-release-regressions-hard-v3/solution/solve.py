#!/usr/bin/env python3
from pathlib import Path


ROOT = Path("/app/linge-hud/vscripts/LinGe")


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise RuntimeError(f"oracle replacement did not match exactly once: {path.name}")
    path.write_text(source.replace(old, new), encoding="utf-8")


replace_once(ROOT / "Hint.nut", "\tDOMINATE = 0,", "\tDOMINATE,")
replace_once(
    ROOT / "RewardHP.nut",
    "\tif (Config.mode != 1 && reward_temp > 0 && hp + hpbuffer + reward_temp <= Config.limit)",
    """\tif (Config.mode == 2)
\t{
\t\tlocal remaining = Config.limit - hp - hpbuffer;
\t\tif (reward_temp > remaining)
\t\t\treward_temp = remaining;
\t\tif (reward_temp > 0)
\t\t\tattacker.SetHealthBuffer(hpbuffer + reward_temp);
\t}
\telse if (Config.mode == 3 && reward_temp > 0
\t&& hp + hpbuffer + reward_temp <= Config.limit)""",
)
