# Isaac Rebirth construct task drafts (8 public contracts)

**Status: authoring drafts. NOT ADMITTED. NOT ENGINE-VALIDATED.**

Each draft below is a complete public contract for one from-scratch Afterbirth+
Lua mod: the attempt starter contains only `mod/main.lua` and
`mod/metadata.xml`, and the contract is the only source of requirements. Every
requirement is derivable from the named public API surface — no private
assertion may carry a requirement that is not stated here. Final task prompts
must be produced from these contracts only after the authoring pipeline
generates a reference implementation and an independent verifier, and after
both pass two-way real-game validation (empty starter fails/incomplete;
reference scores 100/complete; an unrelated change fails).

All drafts use only Afterbirth+ v1.06.T1 APIs and target Steam App 250900 build
22878971.

---

## synth-01 — Config menu d-pad navigation

**Difficulty:** medium

**Contract.** Implement a mod-configuration menu whose controller navigation is
driven by the four d-pad directions. The menu has a category list, a subcategory
row, and an options pane. While the menu is open:

- `Controller.DPAD_UP` / `DPAD_DOWN` move the selection in the active list by one
  entry per trigger, and repeat while held, wrapping between the first and last
  entry.
- `Controller.DPAD_RIGHT` enters the options pane from the subcategory row or
  advances the subcategory selection; `DPAD_LEFT` leaves the options pane or
  moves the subcategory selection backward.
- D-pad left/right adjusts the value of a numeric or scroll option while the
  options pane is focused.
- D-pad directions must no longer be treated as reserved non-navigational
  buttons; only the face buttons (`Controller.BUTTON_A`, `Controller.BUTTON_B`)
  remain reserved, so a d-pad press alone never confirms or backs out.
- The analog stick, keyboard directional bindings, hold-to-repeat cadence,
  wrapping boundaries and face-button select/back behavior must be unchanged.

**API surface:** `RegisterMod`, `Mod:AddCallback`,
`ModCallbacks.MC_POST_RENDER`, `Input.IsButtonTriggered`,
`Controller.DPAD_{UP,DOWN,LEFT,RIGHT}`, `Controller.BUTTON_{A,B}`,
`ButtonAction.ACTION_SHOOT{DOWN,LEFT,RIGHT,UP}`, `Font:DrawString`, `KColor`.

**Derivable acceptance themes:** per-direction cursor movement and wrap;
pane enter/leave; left/right value adjustment; hold-repeat; face-button
select/back preserved; d-pad not in the reserved set. The verifier declares
exactly 35 unique cases over these themes.

---

## synth-02 — Save-data loader robustness and HUD-offset sync

**Difficulty:** medium

**Contract.** A configuration loader is invoked from
`MC_POST_GAME_STARTED`. It must:

- If the decoded payload is a table, merge saved section values over registered
  defaults and fill them into the live configuration.
- If the decoded payload is not a table (e.g. a boolean), must not index it and
  must not raise; merging is skipped and the configuration is rebuilt from
  defaults combined with the pre-load current configuration using `pcall`-safe
  access.
- Synchronize a screen-offset helper to the configuration's HUD-offset value
  after **every** load invocation, including a rejected payload, so the offset
  equals the default in that case.
- Saved values take precedence over defaults; keys absent from a table payload
  retain defaults.
- A development-only success diagnostic is emitted only when a table payload was
  actually merged, and must not affect production behavior.

**API surface:** `RegisterMod`, `Mod:AddCallback`,
`ModCallbacks.MC_POST_GAME_STARTED`, `Mod:SaveData`, `Mod:LoadData`,
`Mod:HasData`, `json.encode`, `json.decode`, `Isaac.DebugString`.

**Derivable acceptance themes:** non-table payload completes without error and
yields defaults+current; offset helper set after rejection; table merge
precedence and default fill; save→load round-trip; development diagnostic only
for merged table payloads.

---

## synth-03 — Fractional screen-coordinate truncation in rendering

**Difficulty:** easy

**Contract.** Two on-screen messages — the start-up "open the menu" hint and the
pending restart/new-run warning — right-align text by passing the screen's
bottom-right X coordinate as the `Font:DrawString` width argument. That
coordinate can be fractional because it derives from a configurable HUD offset.
The implementation must:

- Truncate the width argument toward zero to a whole number for both messages so
  neither draw raises on a fractional corner coordinate.
- Preserve bit-for-bit rendering when the corner coordinate is already an
  integer.
- Leave message text, colors, fade, the `bottom-right Y − 28` placement and the
  right-aligned draw mode unchanged.
- Keep drawing each message only under its existing condition (hint while its
  timer is active; warning while pending).

**API surface:** `Font:Load`, `Font:DrawString`,
`ModCallbacks.MC_POST_RENDER`, `KColor`.

**Derivable acceptance themes:** both draws complete on fractional X; width equals
`math.floor`-truncated corner X; integer case unchanged; Y/color/mode unchanged;
conditional draw preserved.

---

## synth-04 — Cross-build save migration and HUD visibility

**Difficulty:** hard

**Contract.** A configuration system must run on both newer Repentance and older
expansion builds:

- Saving encodes the entire configuration table so settings from every category
  survive across sessions and save slots.
- Loading merges stored data over registered defaults and fills missing keys
  rather than aborting on a fixed required-key set.
- Loading migrates legacy data whose top level holds the menu's own settings by
  moving them under the menu category.
- HUD hiding while the menu is open uses `SeedEffect.SEED_NO_HUD` +
  `Seeds:AddSeedEffect`/`RemoveSeedEffect` on older builds and
  `Game:GetHUD`/`HUD:SetVisible` on Repentance; both paths restore the HUD after
  the menu closes.
- The HUD-offset default resolves to `Options.HUDOffset` when that table exists
  and to `0` otherwise, without erroring.
- Screen size/center/corner coordinates are computed from native screen queries
  on Repentance and from room-render state on older builds.

**API surface:** `Isaac.GetScreenWidth`, `Isaac.GetScreenHeight`, `Game:GetRoom`,
`Game.ScreenShakeOffset`, `Room:WorldToScreenPosition`, `Room:GetRenderScrollOffset`,
`Game:GetSeeds`, `Seeds:HasSeedEffect`, `Seeds:AddSeedEffect`,
`Seeds:RemoveSeedEffect`, `SeedEffect.SEED_NO_HUD`, `Game:GetHUD`, `HUD:IsVisible`,
`HUD:SetVisible`, `Options.HUDOffset`, `REPENTANCE` build flag, `Mod:SaveData`,
`Mod:LoadData`, `Mod:HasData`.

**Derivable acceptance themes:** general-category persistence; encoded data
contains every category; legacy migration; missing keys default; per-build HUD
toggle and restore; options-table absence; screen rectangle computed per build.

---

## synth-05 — Custom option color alpha inheritance

**Difficulty:** medium

**Contract.** A menu option may carry a custom display color. Applying it must:

- Override only the text RGB; inherit the alpha from the font color that would
  otherwise be used for that option, read through the accessor the game's color
  type actually exposes, so `KColor` values interoperate.
- Follow pane state: full alpha while the options pane is focused, reduced alpha
  when inactive or when the option is not selectable.
- Never raise and never abort the render callback.
- Render structurally like a non-custom option (same position, cursor, strikeout)
  and apply the same rule to the slider sprite of custom-colored sliding options.

**API surface:** `KColor`, `Font:DrawString`, `ModCallbacks.MC_POST_RENDER`,
`RegisterMod`, `Mod:AddCallback`.

**Derivable acceptance themes:** focused/unfocused alpha inheritance; RGB
replacement; no-error render with a custom option; slider sprite color; removing
the custom color restores prior output.

---

## synth-06 — Deterministic per-room RNG without global-stream pollution

**Difficulty:** hard

**Contract.** Implement a randomizer whose outcomes are deterministic for a given
run seed and room and reproducible across a save/quit/reload, without consuming
from or reseeding the game's global random state. `MC_POST_NEW_ROOM` establishes
the per-room stream; `MC_POST_UPDATE` must draw values in a stable order;
persisted state on `MC_POST_GAME_SAVED` must reproduce the same next value after
reload. Reset on new run (`MC_POST_GAME_STARTED`) must clear derived state.

**API surface:** `RegisterMod`, `Mod:AddCallback`,
`ModCallbacks.MC_POST_NEW_ROOM`, `ModCallbacks.MC_POST_UPDATE`,
`ModCallbacks.MC_POST_GAME_STARTED`, `ModCallbacks.MC_POST_GAME_SAVED`,
`Game:GetSeeds`, `Seeds:GetSeed`, `Mod:SaveData`, `Mod:LoadData`.

**Derivable acceptance themes:** same seed+room → same sequence; no global
consumption; reload continuation; run reset; update-order stability; distinct
rooms differ.

---

## synth-07 — Orphaned effect cleanup across room transitions

**Difficulty:** hard

**Contract.** Track entities created by the mod and remove or repair references
when their owner is gone (killed, removed, or room change), so no orphaned
effect, dangling table reference, or double-free remains. Cleanup must be
idempotent across repeated callbacks and must not touch non-mod entities.
Re-entering the room must not resurrect stale owners.

**API surface:** `RegisterMod`, `Mod:AddCallback`,
`ModCallbacks.MC_POST_UPDATE`, `ModCallbacks.MC_POST_NEW_ROOM`,
`ModCallbacks.MC_POST_NPC_INIT`, `ModCallbacks.MC_ENTITY_REMOVED`,
`Entity:Exists`, `Entity:Remove`, `Isaac.GetRoomEntities`, `Game:GetRoom`.

**Derivable acceptance themes:** orphan removed on transition; dangling
reference cleared; idempotent double callback; foreign entities untouched;
re-entry does not restore stale owner; no error on already-removed entity.

---

## synth-08 — Cross-callback state machine idempotency and rollback

**Difficulty:** hard

**Contract.** Implement a multi-phase effect whose phases advance on distinct
callbacks (`MC_USE_ITEM`, `MC_POST_UPDATE`, `MC_POST_NEW_ROOM`,
`MC_POST_GAME_SAVED`) with an explicit state machine. Each phase transition must
be idempotent (a callback re-entered before the previous phase commits must not
double-apply), and an aborted phase must roll back partial effects before the
state advances. Saved state must reproduce the same phase after reload.
`MC_POST_GAME_STARTED` resets all phase state.

**API surface:** `RegisterMod`, `Mod:AddCallback`,
`ModCallbacks.MC_USE_ITEM`, `ModCallbacks.MC_POST_UPDATE`,
`ModCallbacks.MC_POST_NEW_ROOM`, `ModCallbacks.MC_POST_GAME_SAVED`,
`ModCallbacks.MC_POST_GAME_STARTED`, `Mod:SaveData`, `Mod:LoadData`,
`Isaac.GetPlayer`, `Game:GetRoom`.

**Derivable acceptance themes:** phase advance ordering; re-entrant idempotency;
abort rollback; reload reproduces phase; reset clears; no double-apply across
room change.

---

## Admission checklist (per task, required before `benchmark.json` exists)

1. Reference solution from the authoring `fixed` checkpoint scores 100 and
   `complete` on the `full` profile of the licensed runtime.
2. The empty `mod/` starter fails with an incomplete result.
3. An unrelated-but-valid change does not pass.
4. Every one of the 35 verifier cases maps to a requirement stated in the public
   prompt, and no requirement exists only in the private suite.
5. `rhenium runtime prepare isaac-rebirth/afterbirth-plus-1.06.t1-synth`
   succeeds against a staged validation pack, and the artifact identity is an
   immutable image id.
6. One-shot strict calibration against the selected model is recorded with the
   run id and failing cases.
