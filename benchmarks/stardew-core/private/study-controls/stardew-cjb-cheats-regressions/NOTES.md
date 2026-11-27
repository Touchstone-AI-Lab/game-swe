# E0 notes: stardew-valley/core/stardew-cjb-cheats-regressions

Private maintenance material. It names the defects and the reference; never copy it into
an attempt or a model workspace.

Layout: the workspace holds `StardewMods/`; every patch applies with `patch -p1` from
`/app/StardewMods` (`root` = `StardewMods`). Reference = starter + `solution/gold.patch`
(the unmodified CJB Cheats Menu 1.42.0 tree; see the task's `validation/NOTES.md`).

## Case roles

12 entries in `clause-map.json`: 1 static, 1 runtime sentinel, 5 target, 5 preserved.

| report | target case | defect (upstream fix reverted in the starter) |
| --- | --- | --- |
| One Hit Kill and grubs | `one-hit kill: a grub stays a grub ...` | grubs at 1 health with full maximum health start their metamorphosis (`7fcfe1d`) |
| Auto-Feed Animals with an empty silo | `auto-feed: troughs are filled even when no silo has hay left` | the cheat stops when no silo hay is left (`2c05d09`) |
| Auto-Pet Animals outside the farm | `auto-pet animals: an animal in town is left alone` | animals in non-buildable locations are petted (`40e1912`) |
| Auto-Pet Pets outside the farm | `auto-pet pets: a pet NPC in town is left alone` | every pet in every location is petted (`3a9ba55`) |
| Always Treasure and golden chests | `always treasure: with fishing mastery some chests are golden` | forcing treasure after the minigame opened skips the golden roll (`ad97de5`) |

Preserved (all pass in the unchanged starter): a slime drops to 1 health and keeps its
maximum health; troughs take hay from a silo that has some; coop animals are petted; the
farm pet is petted; every minigame has a chest and none is golden without the mastery.

## Controls (all run through `rhenium run`, full profile, in the real game)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| (starter) | — | starter | none | every target fails, every preserved passes | 6/11, the 5 targets fail (`run-72670f62c548489f`, 2026-09-23) |
| (reference) | — | reference | none | 11/11, three times | 11/11 in `run-e089ce3134304286`, `run-cf39d4a5be814f80`, `run-fb7775b93e0d43f3` (identical outcomes) |
| `target-negative-golden-whenever-mastered` | target-negative | reference | golden whenever the mastery is unlocked, no chance roll | only the golden-chest target fails | 10/11, exactly that target fails ("not every chest is golden") (`run-0c9721fb2ce44a15`). Admissible. |
| `compat-negative-max-health-one-for-all-monsters` | compat-negative | reference | the pre-1.37 upstream behavior: every monster's maximum health set to 1 | all targets pass; only the maximum-health preserved case fails | 10/11, exactly `one-hit kill: a monster drops to 1 health and keeps its maximum health` fails (`run-bedd04e477634ee1`). Admissible. |
| `alternative-metamorph-countdown-and-location-filters` | alternative | starter | independent repair (see manifest note) | 11/11 | 11/11 (`run-4af1a496117d4800`). Admissible. |

The compat-negative is real upstream history: CJB Cheats Menu 1.36.0 fixed the grub
problem by lowering every monster's maximum health, 1.37.0 undid that to keep vampiric
healing (reintroducing the grub bug), and 1.38.0 restricted it to grubs.

## Assertion-strength findings

- `Report-pet-pets-scope` is **weak**: only a pet on the farm is probed, not pets inside
  the farmhouse or a cabin.
- The golden-chest target is statistical (at least one golden and not all golden in 120
  minigames). At the game's rate for a player with the mastery (25% plus the day's
  average luck, so at least about 15%), a correct implementation fails with probability
  below 1e-8; the target-negative (always golden) fails it deterministically.
- Auto-feed is probed in a coop only; barns and slime-hutch water are not probed.
- No over-constraining assertion found: the alternative, written only from the exam,
  passes every case.

## Infrastructure note

The host's Docker daemon and the shared Hub database were congested during these runs.
Evaluations that never reached the game (container creation or the daemon probe timed
out, or the Hub database was locked) were rerun unchanged; only complete runs are
recorded above.
