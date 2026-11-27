# Construct: Identity-keyed option palette rendering

You are creating a new Lua mod for **The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1**. The starter contains only `mod/main.lua` and `mod/metadata.xml`.

## Task

Add a runtime palette to a configuration-option renderer. Expose
`SetOptionColor(stableOptionId, rgb)` and
`ClearOptionColor(stableOptionId)`. A custom color is a three-number RGB table
with finite components in [0,1].

## Required behavior

- A valid custom color replaces only RGB. Obtain normal text alpha through the
  game's `KColor.Alpha` property, not by assuming the `Color.A` API. The normal
  KColor alpha is exactly 1.0 for a selectable option in the focused pane and
  0.4 otherwise; a disabled option uses 0.4 even if selected or focused.
  Preserve that exact alpha in the custom KColor and slider color. If a
  mock/non-game normal color has no finite `Alpha`, safely fall back to 1.0.
- For a custom-colored sliding option, apply the same RGB and computed alpha to
  its slider sprite's `Color` property, with offsets zeroed. Do not mutate the
  normal shared font or sprite colors. A non-slider must not mutate a sprite.
- Preserve the ordinary option's position, cursor position, and strikeout
  treatment. Apply the rules to selectable, disabled, selected, and unselected
  options in focused and unfocused panes. A custom color must never abort the
  render callback.
- Store a color by stable option identity, not its row index. It follows an
  option through row/category reordering and is removed when that option is
  removed. Color state is isolated per mod instance and never saved as
  configuration or allowed to modify the option value.
- A valid palette update is visible on the next render without reconstructing
  the font or sprite. Reject nil, partial, non-finite, or out-of-range RGB
  atomically and retain the last valid color. `rgb` is a dense three-element
  array `{red, green, blue}`; clearing restores the exact normal text and
  slider colors, including their alpha.

Use Afterbirth+ `KColor`, `Color`, `Sprite.Color`, and `Font:DrawString` APIs.
Do not add third-party code or assets.

## Public observation and control API

Export IsaacConstructPalette with UpsertOption(stableOptionId, kind, value,
renderState), RemoveOption(id), SetOptionOrder(ids),
SetOptionColor(stableOptionId, rgb), ClearOptionColor(stableOptionId),
SetRenderContext(context), RenderNow(), and Snapshot(). kind is boolean,
slider, or text. `stableOptionId` is a non-empty string. renderState contains
selectable, selected, focused, x, y, a KColor-like normalTextColor with
Red/Green/Blue/Alpha fields, and optional normalSliderColor carrying
R/G/B/A/RO/GO/BO fields. The render path uses KColor.Alpha for text alpha;
the supplied normal text color is the canonical baseline for the focused,
selectable, and disabled alpha rules. Snapshot normalizes colors to lowercase
red/green/blue/alpha fields and includes slider offsets.
SetRenderContext supplies the menu-level context used by the regular render
path. The real MC_POST_RENDER callback and RenderNow use the same renderer,
which calls Font:DrawString and updates slider Sprite.Color.
Snapshot returns fresh copies of `palette` (a map from stable option id to
`{red, green, blue}`), `lastRender` (the latest render's intents in draw order,
each `{id, x, y, cursorX, cursorY, strikeout, text = {red, green, blue, alpha},
slider = {red, green, blue, alpha, ro, go, bo} or nil for a non-slider, focused,
selected, disabled}`), and `renderErrorCount` (draw errors caught by the render
path). Tests read these fields and never write submission state.

## Acceptance cases

default_color_unchanged, valid_rgb_replaces_rgb, alpha_accessor_is_used,
focused_selectable_alpha, unfocused_pane_alpha, disabled_option_alpha,
selected_disabled_alpha, text_draw_no_error, slider_draw_no_error,
text_and_slider_share_custom_rgb, non_slider_has_no_sprite_mutation,
option_position_unchanged, cursor_position_unchanged, strikeout_unchanged,
color_follows_option_identity, row_reorder_keeps_color,
removed_option_drops_color, palette_update_visible_next_frame,
clear_restores_text_rgb, clear_restores_alpha, clear_restores_slider_color,
invalid_rgb_rejected_atomically, partial_rgb_rejected, nan_rgb_rejected,
infinity_rgb_rejected, last_valid_color_survives_rejection,
custom_color_not_saved, option_value_not_changed_by_color, color_state_not_shared,
between_categories, repeated_render_is_idempotent,
custom_color_does_not_abort_callback, normal_color_accessor_missing_fallback,
alpha_never_nil, inactive_slider_alpha.
