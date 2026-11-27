# Construct: Config-menu input state machine

You are creating a new Lua mod for **The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1**. The starter contains only `mod/main.lua` and `mod/metadata.xml`.

## Task

Build a controller-, keyboard-, and analog-accessible configuration menu from
scratch. It has the ordered categories `menu`, `general`, `controls` and the
ordered subcategories `menu/main`, `menu/demo`, `general/hud`, and
`controls/keybinds`. It starts closed. Its configurable open_menu binding
defaults to F2 and its reset_config binding defaults to F3.

On the first open, the menu shows category `menu`, subcategory `menu/main`,
and that subcategory's first option. Closing and reopening preserves the last
selected category, subcategory, and option.

Each subcategory has exactly two ordered options:

- `menu/main`: boolean `open_at_start`, then slider `menu_scale`.
- `menu/demo`: boolean `demo_mode`, then slider `demo_rate`.
- `general/hud`: boolean `show_hud`, then slider `hud_offset`.
- `controls/keybinds`: keybind `open_menu`, then keybind `reset_config`.

All sliders start at 5.0 and range from 0 through 10 in 0.5 increments. The
default keybinds are F2 and F3.

## Required behavior

- Use `ButtonAction.ACTION_MENUUP`, `ACTION_MENUDOWN`, `ACTION_MENULEFT`, and
  `ACTION_MENURIGHT` for menu navigation. The category pane starts on `menu`;
  up/down wrap through the three categories and right enters the first
  subcategory belonging to the selected category. The subcategory pane has
  this fixed order: `menu/main`, `menu/demo`, `general/hud`,
  `controls/keybinds`. Up returns to the category pane, down enters that
  subcategory's options pane, and left/right move backward/forward in the
  fixed order with wraparound; the category index always follows the selected
  subcategory. Left in the category pane is a no-op. In the options pane,
  up/down wrap between its two options. Left returns to the subcategory pane
  for a boolean or keybind; on a slider, left/right change its value.
- In the options pane, up/down wrap between its two options. Left/right change
  a selected slider by exactly 0.5, clamped to [0,10]. They do not change a
  boolean or keybind; right on a non-slider option is a no-op.
  `ACTION_MENUCONFIRM` toggles a boolean or enters keybind capture.
  `ACTION_MENUBACK` backs out one pane, closes the menu from the category
  list, or cancels keybind capture.
- While capturing a keybind, the first menu-direction action or F1–F12 key is
  stored symbolically (`ACTION_MENU*` or `KEY_Fn`) and is consumed as the new
  binding, not as navigation. F2 menu-toggle handling is suspended until
  capture ends. Outside capture, direction input alone never confirms, backs
  out, or captures a key.
- Outside capture, the configured open_menu binding toggles the menu. The
  configured reset_config binding restores every option and both keybinds to
  their defaults while leaving the menu open in its current pane. If both
  bindings are identical, open_menu has priority and one physical press only
  toggles the menu. A press consumed by either binding does not also navigate
  the menu, even when the binding is one of the menu-direction actions.
- Keyboard arrows and controller d-pad use the same `ACTION_MENU*` semantics.
  Analog directions use `Input.GetActionValue` with those actions: values at or
  above 0.5 press/hold, values below 0.25 release, and values in [0.25,0.5)
  preserve the previous held state. Non-menu shoot actions never navigate the
  menu.
- A newly pressed direction acts on the same render frame. A held direction
  first repeats on its 12th consecutive held frame, then every 5 held frames.
  Release resets its timer. When several directions become actionable on one
  frame (new press or scheduled repeat), apply only one action in priority
  order up, down, left, right. Changing the selected held direction resets
  the repeat timer. These rules apply equally to keyboard, d-pad, and analog
  input.
- Keep category, subcategory, and option indices valid after every transition.
  Draw only the active pane in `MC_POST_RENDER`, without making rendering
  responsible for changing menu/config state or saving configuration data.
  The category pane draws the ordered category IDs; the subcategory pane draws
  the four ordered subcategory IDs; the options pane draws the two option IDs
  and their current values (`true`/`false`, one-decimal slider values, or the
  symbolic keybind). Mark exactly the currently selected row with the prefix
  `> ` and prefix other rows with two spaces. Draw at X=24 and
  Y=`24 + 16*(rowIndex-1)` using a mod-owned built-in Terminus `Font` and
  `Font:DrawString`; the category/subcategory row text is its ID and an option
  row is `optionId .. " = " .. valueText`. Rendering is hidden when the menu is
  closed.

Use only APIs present in Afterbirth+ v1.06.T1; in particular, poll menu actions
through `Input.IsActionTriggered` / `Input.IsActionPressed`, and keyboard
capture keys through `Input.IsButtonTriggered`. Use the built-in
`font/terminus.fnt`; do not add third-party code or assets.

## Public observation and control API

Export IsaacConstructNavigation with Step(frameInput) and Snapshot().
Step accepts one frame of input in the shape
{triggered={action=true}, held={action=true}, analog={action=number},
keys={KEY_F1=true}}; action names are up, down, left, right, confirm, and
back. `keys` contains newly pressed F1-F12 keys; configured bindings are
matched against these keys and against the symbolic menu-direction actions.
The real MC_POST_RENDER handler polls the Afterbirth+ input APIs, builds this
same shape, and calls Step exactly once per rendered frame.
Snapshot returns a fresh copy of open, pane, categoryIndex,
subcategoryIndex, optionIndex, capture, repeatDirection, repeatFrames, and
the complete current config, plus fresh `lastDraws` records (`pane`, `rowId`,
`text`, `selected`) and `renderErrorCount`. Indices are one-based; pane is
category, subcategory, or options. Tests may inject input through Step but may
not write state directly.

## Acceptance cases

initial_closed_state, first_open_state, category_up, category_down,
category_wrap_up, category_wrap_down,
category_right_enters_subcategories, reset_restores_defaults_and_keeps_menu_open,
subcategory_up_returns, subcategory_down_enters_options, subcategory_left,
subcategory_right, subcategory_wrap_left, subcategory_wrap_right,
render_tracks_current_pane_and_selection, options_down, option_wrap_up, option_wrap_down, slider_left_step,
slider_right_step, slider_lower_clamp, slider_upper_clamp,
keybind_left_returns, open_menu_rebind_takes_effect,
press_moves_immediately, repeat_starts_on_frame_12, repeat_every_5_frames,
release_resets_repeat, face_a_selects, face_b_backs_out, dpad_never_confirms,
analog_uses_same_navigation, keyboard_uses_same_navigation,
multi_direction_priority, keybind_capture_consumes_dpad_and_open_binding_wins
