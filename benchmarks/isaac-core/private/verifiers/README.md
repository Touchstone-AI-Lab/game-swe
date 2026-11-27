# Shared Exodus verifiers

A derived `isaac-core` task may name one of these directories in its catalog entry
(`"verifier": "<name>"`). The Isaac evaluator then bind-mounts the directory's `test.sh`,
`suite/`, `secret-suite/` and `james-suite/` read-only over the verifier image's copies;
the image, the runtime artifact and the task's own `tests/run-game.sh` are unchanged. The
task's `tests/test.sh` must be a byte copy of the shared `test.sh` (the catalog loader
rejects drift), because the declared case list is read from it. The frozen composite task
(`isaac-exodus-release-regressions`) and the clean-room synth tasks cannot name one.

## `exodus-v2` (catalog 5.0.0, 54 cases)

Used by all nine derived tasks. It keeps the frozen composite's `secret-suite/`,
`james-suite/` and `suite/metadata.xml` byte for byte and every frozen case of
`suite/main.lua`, and adds, in this order after `grid_worm_bounce`:

| Block | Cases | Report |
| --- | --- | --- |
| Grid Worm diagonal against the facing axis (inside the existing Grid Worm block) | `grid_worm_heading_cross_axis` | EX-226 |
| Hurdle Heels jump, mid-air hit, landing stomp | `hurdle_heels_landing_stomp`, `hurdle_heels_player_protected` | EX-447 |
| Ominous Lantern raised and lowered through forced item presses, then raised again and thrown | `ominous_lantern_put_away`, `ominous_lantern_throw_recharge` | EX-441 |
| Child's Leash with Sundial, Hungry Hippo and Robo-Baby 3.6.0 | `childs_leash_orbitals` | EX-436 |
| Algiz used while holding Lil Rune | `lil_rune_algiz_rune` | EX-427 |
| Big Scissors after a self-hit | `big_scissors_trail` | EX-461 |
| Unholy Mantle hit twice on one floor | `unholy_mantle_burst`, `unholy_mantle_once` | EX-463 |
| Birdbath used | `birdbath_use_spawns` | EX-465 |
| A card used while holding Paper Cut | `paper_cut_card_damage` | EX-467 |
| Baseball Mitt catching two shots | `baseball_mitt_return_flags` | EX-469 |
| Welcome Mat laid in a secret room, then a ball and a lantern tear killed there | `welcome_mat_poof_at_rest`, `welcome_mat_flame_at_rest`, `welcome_mat_bonus_kept` | EX-406 |
| Welcome Mat across a `stage` change and the next room | `welcome_mat_floor_start`, `welcome_mat_next_room` | EX-412 |
| A second run started with `restart 0` in the same process (last block) | `new_run_starts_with_base_stats` | EX-452 |

`test.sh` declares `expected=54` and expects the main process summary
`passed=49 failed=0 total=49`; the James and secret-room processes are unchanged (2 and 3
cases). The added blocks share the main process with the frozen ones, so the order
dependence noted in the clause maps applies to them too: a Lua error inside the suite
emits `GCB_FATAL` and leaves later cases unobserved. The Welcome Mat floor check and the
restart change the floor and the run, which is why they run last.

The Ominous Lantern block presses the item key through `MC_INPUT_ACTION`, which the engine
honours. The mod reads the throw direction itself with `Input.IsActionPressed`, which that
callback does not reach in Afterbirth+ (measured: with only the callback the reference tree
never threw), so for the throw the suite puts a proxy in the global `Input` that reports
`ACTION_SHOOTLEFT` as held, and restores the real one as soon as a lantern tear exists or
after 30 updates. A repair that reads the throw input some other way, or keeps its own
reference to `Input`, is not seen throwing and fails `ominous_lantern_throw_recharge`.
The first 5.0.0 build emptied the lantern from the suite with `DischargeActiveItem` instead of
throwing it, which skipped the mod's throw path and failed repairs that record the throw
there. Every 5.0.0 control in this repository was measured with the corrected build.

Every block was run in the real game against the composite reference tree and against
trees carrying each regression it observes; see
`../supplementary-regressions/README.md` and each derived task's `validation/`.

### Known limits

- `grid_worm_bounce` keeps the frozen check: on the first update on which the tear's
  velocity points away from the wall, the tear must be at least 35 units from the wall
  tile. One update later the tear is gone in every tree measured (the reference tree, the
  `isaac-exodus-tear-trajectory` starter, and a constructed one-reversal-per-impact
  debounce that does not move the tear), so such a debounce reads the same 30 units as
  the unrepaired starter and fails, although it never reverses twice in one contact. The
  four tasks that report EX-226 flag the case
  `over_constrained` in their clause maps (from the E0 `alternative-strict-reading`
  control): the study's audited outcome leaves it out, the Hub's native verdict does not.
- Frozen blocks read or set mod-internal `GetData()` fields: Ritual Candle (`IsLit`,
  `LitTimer`), Deja Vu (`ReturnChance`), Lovely Fly (`parentEnemy`) and Headcase
  (`IsExodusLobbed`). A repair that renames them fails those blocks' cases. The blocks added
  for 5.0.0 read only engine state.
- Blocks share one process, so state a repair leaves behind can fail a later block's case.
  Measured once: Big Scissors' creep changed to the enemy variant `EffectVariant.CREEP_RED`
  also fails `unholy_mantle_once` (`../supplementary-regressions/README.md`).
