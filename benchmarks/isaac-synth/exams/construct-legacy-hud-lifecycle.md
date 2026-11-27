# Construct: Afterbirth+ configuration and HUD lifecycle

You are creating a new Lua mod for The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1. The starter contains only mod/main.lua and mod/metadata.xml.

## Task

Implement a configuration and HUD lifecycle mod for the pinned Afterbirth+
build. Configuration must survive across sessions, legacy menu settings must
migrate safely, and opening the configuration menu must hide the HUD without
claiming or removing an effect owned by another source.

## Configuration contract

The normalized version-2 object has exactly schema_version, menu, general,
and controls at the top level, with schema_version=2. Defaults are
menu={dev=false, demo=false, open=false}, general={hud=true,
hud_offset=<resolved offset>}, and controls={menu_key="F2", reset_key="F3"}.
Merge known keys by category; absent keys retain defaults, invalid value types
fall back to defaults, `general.hud_offset` must be finite and in [0,10], and
unknown keys are ignored.

Legacy version-1 data has exactly schema_version=1 and flat dev, demo, and
open fields. Migrate only those menu-owned values into menu; general and
controls use defaults. The next save always writes the version-2 object.
Missing data, HasData()==false, malformed JSON, and a decoded non-table value
are safe and do not abort the lifecycle callback.

## Required behavior

- Save the complete configuration table so settings from every category
  survive across sessions and save slots. Loading merges stored data over
  registered defaults and fills missing keys rather than rejecting partial
  data. Unknown keys are ignored; malformed JSON and non-table decoded values
  fall back safely. Saving serializes normalized settings without mutating the
  live configuration.
- Migrate legacy data whose top level holds the menu's own settings by moving
  them under the menu category. A continued game start loads and normalizes
  saved settings; a new run rebuilds the defaults before the menu opens.
- The normalized `menu.open` value is the desired menu state after load. Apply
  the same idempotent HUD-effect ownership transition used by `OpenMenu` and
  `CloseMenu`; opening updates `config.menu.open`, and closing clears it.
- HUD hiding uses only SeedEffect.SEED_NO_HUD and
  Seeds:HasSeedEffect/AddSeedEffect/RemoveSeedEffect. Record whether the effect
  was already present before opening. Closing removes it only if this mod
  added it. Repeated open/close transitions are idempotent. Room and floor
  changes do not alter menu state or effect ownership.
- Resolve the HUD-offset default to finite Options.HUDOffset when Options is a
  table with a finite numeric value; otherwise use 0. Clamp the result to
  [0,10].
- After every load, synchronize the live screen-offset helper exactly once to
  the normalized general.hud_offset, including after absent or rejected data.
  A valid saved offset overrides its resolved default; an absent or invalid
  value falls back to that default.
- This task targets Afterbirth+ only. Do not probe or call Game:GetHUD,
  Isaac.GetScreenWidth, or Isaac.GetScreenHeight, and do not branch on
  REPENTANCE. These APIs are outside the task's runtime contract. Loading,
  starting, rendering, opening, and closing remain error-free if any of them
  are absent.
- Save through one normalized serialization path. The constructlegacy save
  command and supported exit callbacks use the same routine.

## API surface

Use RegisterMod, Mod:AddCallback, MC_POST_GAME_STARTED, MC_POST_RENDER,
MC_PRE_GAME_EXIT, MC_POST_GAME_END, MC_EXECUTE_CMD, Game:GetSeeds,
Seeds:HasSeedEffect/AddSeedEffect/RemoveSeedEffect, SeedEffect.SEED_NO_HUD,
Options.HUDOffset, Mod:SaveData/LoadData/HasData, and built-in json encode
and decode.

## Public observation and control API

Export IsaacConstructLegacyHUD with OpenMenu(), CloseMenu(),
ResolveOffset(optionsValue), LoadRaw(hasData, rawData), SaveNow(), and
Snapshot(). The production callback passes the actual global Options through
ResolveOffset; tests may pass nil, booleans, and tables through the same
function. Production callbacks and public controls use the same transitions.
Snapshot returns fresh copies of config, hudOffset, menuOpen,
seedEffectInitiallyPresent, ownsSeedEffect, and lastSavedRaw. No public method
may expose a mutable internal table.

## Acceptance cases

version2_saves_all_categories, general_value_round_trip, partial_load_defaults,
legacy_flat_menu_migrates, legacy_migration_saves_v2,
missing_options_default_zero, offset_clamped_low, offset_clamped_high,
seed_absent_initially, menu_open_adds_seed_only_when_absent,
preexisting_seed_preserved, menu_close_removes_owned_seed,
menu_close_preserves_preexisting_seed, repeated_open_idempotent,
repeated_close_idempotent, hud_offset_nil_fallback,
hud_offset_non_numeric_fallback, hud_offset_finite_clamp,
options_root_absent_safe, unsupported_apis_never_used,
load_callback_does_not_throw, render_callback_does_not_throw,
load_decoded_table_merges, missing_fields_default, invalid_category_default,
unknown_keys_ignored, malformed_json_defaults, non_table_json_defaults,
hasdata_false_defaults, missing_data_defaults, save_after_load_is_v2,
save_does_not_mutate_live_config, continued_load_restores_config_and_open_effect,
new_run_uses_defaults, seed_restored_after_room_change.

Do not add third-party code or assets.
