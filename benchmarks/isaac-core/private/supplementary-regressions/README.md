# Supplementary Exodus regressions

Private maintenance material for catalog 5.0.0. The frozen composite's twenty reports are
local repairs next to code the report names, so each derived task now also carries three of
the regressions below, whose diagnosis depends on how Afterbirth+ itself behaves. They are
not upstream bugs: each one is a plausible maintenance edit injected into the composite
reference tree (`main.lua`, sha256 `ee5753ae…`), and its reference repair is the reverse of
its patch, so every derived task's gold is still that unchanged tree.

- `<id>.patch` is a unified diff from the reference tree to the regressed tree.
- `reports.md` holds the player report for each patch; a derived exam quotes it verbatim.
- The cases that observe each regression live in the shared verifier
  (`../verifiers/exodus-v2/`, see its README).

| Report | Change | Cases (starter fails) | Guard (starter passes) |
| --- | --- | --- | --- |
| EX-406 | Welcome Mat copies its position into its stored vector, which is the mod's shared `NullVector` | `welcome_mat_poof_at_rest`, `welcome_mat_flame_at_rest` | `welcome_mat_bonus_kept` |
| EX-412 | Welcome Mat's floor-start flag assumes MC_POST_NEW_LEVEL fires before MC_POST_NEW_ROOM | `welcome_mat_floor_start`, `welcome_mat_next_room`, `welcome_mat_bonus_kept` | - |
| EX-427 | Lil Rune's MC_USE_CARD callback reads a player argument that Afterbirth+ does not pass | `lil_rune_algiz_rune`, `lil_rune_jera_health` | - |
| EX-436 | Child's Leash is applied through a copy of `OrbitDistance` | `childs_leash_orbitals` | - |
| EX-441 | Ominous Lantern refills its charge inside MC_USE_ITEM, before the engine discharges it | `ominous_lantern_put_away` | `ominous_lantern_throw_recharge` |
| EX-447 | Hurdle Heels' jump protection lost its `ENTITY_PLAYER` callback filter | `hurdle_heels_landing_stomp` | `hurdle_heels_player_protected` |
| EX-452 | `newGame` no longer re-evaluates the cache after resetting run state | `new_run_starts_with_base_stats` | - |
| EX-461 | Big Scissors spawns its creep with `Vector.Zero`, which Afterbirth+ does not define | `big_scissors_trail` | - |
| EX-463 | Unholy Mantle's damage uses `math.pow`, absent from Afterbirth+'s Lua 5.3 | `unholy_mantle_burst` | `unholy_mantle_once` |
| EX-465 | Birdbath's MC_USE_ITEM callback takes the player from a Repentance-style third argument | `birdbath_use_spawns` | - |
| EX-467 | Paper Cut's card callback calls `Isaac.GetPlayer()` without an index | `paper_cut_card_damage` | - |
| EX-469 | Baseball Mitt's returned balls use `EntityTear:AddTearFlags`, which Afterbirth+ does not have | `baseball_mitt_return_flags` | - |

`lil_rune_jera_health` and `welcome_mat_bonus_kept` are frozen or neighbouring cases that
the regression also breaks; the table lists every case the regressed starter fails.

All real-game evidence comes from the second controlled host (NixOS x86_64, prepared
`afterbirth-plus-1.06.t1` runtime, verifier image `sha256:c0560b37db5a…`), 2026-10-22
(UTC). Each regression was first run on its own against experimental verifiers holding only
its cases: the reference tree passed, and the reference tree plus that one patch failed
exactly the listed cases (EX-412 also `welcome_mat_bonus_kept`). In the final shared
verifier the reference tree passed 54/54 under every derived task, and every derived
starter failed exactly its composite reports' cases plus the listed cases of its three
regressions (`welcome_mat_poof_at_rest` also fails wherever EX-327 is reported, because the
poof is Baseball Mitt's impact effect); see each task's `validation/`. Two guard checks:
the reference tree refilling the lantern whenever it is lowered, so that a throw is refilled
at once, fails exactly `ominous_lantern_throw_recharge`; and the reference tree with Big
Scissors' creep changed to the enemy variant `EffectVariant.CREEP_RED` fails
`big_scissors_trail` and also `unholy_mantle_once`: Isaac reaches the Unholy Mantle block
with 2 red hearts instead of 5, and the second hit does not lower them. The table's engine
facts were measured on the same runtime: Afterbirth+ embeds Lua 5.3 without the 5.1
compatibility functions, does not define `Vector.Zero`, `EntityTear:AddTearFlags` or
`EntityPlayer.TearRange`, raises on `Isaac.GetPlayer()` without an index, passes two
arguments to MC_USE_ITEM and one to MC_USE_CARD, fires MC_POST_NEW_ROOM before
MC_POST_NEW_LEVEL on a new floor, and returns copies from entity vector fields while
Lua-held vectors are shared references.
