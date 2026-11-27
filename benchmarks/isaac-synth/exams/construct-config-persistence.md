# Construct: Versioned configuration persistence and recovery

You are creating a new Lua mod for **The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1**. The starter contains only `mod/main.lua` and `mod/metadata.xml`.

## Task

Implement a resilient configuration loader/saver invoked at
`MC_POST_GAME_STARTED`. It must normalize defaults, merge saved settings,
migrate the legacy format, and keep HUD offset state synchronized without ever
aborting the game's start callback on bad data.

Registered defaults are exactly:

```lua
menu = { dev = false, demo = false, open = false }
general = { hud = true, hud_offset = 0.0 }
controls = { menu_key = "F2", reset_key = "F3" }
```

## Required behavior

- Version 2 saves have exactly the top-level keys `schema_version`, `menu`,
  `general`, and `controls`, with `schema_version=2`. Merge each category by
  key. Ignore unknown keys; fall back to that key's default for invalid types
  or when `hud_offset` is not a finite number in [0,10]; preserve valid
  categories when another category is absent or malformed.
- Version 1 legacy data has exactly `schema_version=1` and flat `dev`, `demo`,
  `open` values. Migrate only those three fields into `menu`, retain defaults
  for `general` and `controls`, and write version 2 on the next save. Migration
  must be idempotent; a nested version-2 object must never be mistaken for v1.
- Handle these cases independently and without throwing: no data,
  `HasData()==false`, empty text, decode error, decoded boolean, decoded number,
  decoded string, non-table category, and unknown schema version. If a payload
  is rejected, rebuild safely from defaults plus the pre-load live
  configuration; do not index the rejected value.
- After every load invocation, including rejected or absent data, synchronize
  the live screen-offset helper exactly once to the normalized
  `general.hud_offset` (the default is 0.0). Repeating a load with the same
  payload yields identical normalized state.
- Emit a development success diagnostic only after a table payload was
  actually merged and only when `menu.dev` is true. Never emit it for rejected
  data or let the diagnostic alter production behavior.
- Both MC_PRE_GAME_EXIT and MC_POST_GAME_END use the same idempotent save
  routine. Duplicate lifecycle delivery does not change the serialized
  payload or live settings. The constructcfg save command invokes that same
  routine.

Use only Afterbirth+ APIs, including `Mod:HasData`, `Mod:LoadData`,
`Mod:SaveData`, `MC_PRE_GAME_EXIT`, `MC_POST_GAME_END`,
`MC_EXECUTE_CMD`, and the built-in `json` module. Do not add third-party code
or assets.

## Public observation and control API

Export IsaacConstructConfig with LoadRaw(hasData, rawData,
currentBeforeLoad), SaveNow(), and Snapshot(). The game-start callback passes
HasData() and LoadData() through LoadRaw. rawData is the exact LoadData()
string or nil. currentBeforeLoad is optional and, when supplied, becomes the
live pre-load configuration for the same safe merge path. LoadRaw owns decode,
normalization, offset synchronization, and diagnostics. SaveNow is the only
save path used by both exit callbacks and the constructcfg save command.
Snapshot returns fresh copies of config, screenOffset, offsetSyncCount,
successDiagnosticCount, and lastSavedRaw. Public methods never expose
mutable internal tables.

## Acceptance cases

defaults_without_data, hasdata_false, empty_payload, malformed_json,
decoded_boolean, decoded_number, decoded_string, v2_menu_override,
v2_general_override, v2_controls_override, missing_menu_keys_default,
missing_general_keys_default, missing_controls_keys_default,
unknown_keys_ignored, invalid_menu_type_default,
invalid_general_type_default, invalid_controls_type_default,
partial_section_merge, valid_section_survives_bad_section, full_round_trip,
unknown_schema_defaults, next_save_is_v2, flat_v1_dev_migrates,
flat_v1_demo_migrates, flat_v1_open_migrates,
nested_v2_not_misread_as_legacy, migration_is_idempotent,
offset_synced_after_valid_load, offset_synced_after_bad_json,
offset_synced_after_boolean, offset_synced_when_absent,
exactly_one_offset_sync_per_call, debug_only_after_valid_dev_load,
no_debug_after_rejected_load, repeated_load_has_same_normalized_state.
