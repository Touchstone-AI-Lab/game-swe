# Construct: Fractional HUD notification compositor

You are creating a new Lua mod for **The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1**. The starter contains only `mod/main.lua` and `mod/metadata.xml`.

## Task

Implement two right-aligned HUD notifications from scratch: a startup hint and
a pending-restart warning. Use `MC_POST_RENDER` to draw. The hint text is
`Press F2 to open configuration`, rendered as `KColor(1,1,1,alpha)`. The
warning text is `Restart to apply settings`, rendered as
`KColor(1,0.35,0.25,1)`.

## Required behavior

- On every `MC_POST_GAME_STARTED`, start a 900-rendered-frame hint timer at
  elapsed frame 0. The hint is drawn through elapsed frame 899 and hidden at
  frame 900. Its alpha is `clamp((900-elapsedFrames)/61, 0, 1)`; it is 1.0
  through frame 839, then fades linearly. Floor and room transitions do not
  restart it.
- For the pinned Afterbirth+ runtime, derive the room bottom-right screen
  point with `Isaac.WorldToScreen(Game:GetRoom():GetBottomRightPos())`. Subtract
  the current HUD offset from both coordinates to obtain `(brX,brY)`. The
  offset is live and always in [0,10]. `constructoffset <number>` changes it to
  a finite parsed number clamped to that range; malformed input is ignored.
  The next render uses the new value and current room/render coordinates.
- Both notifications draw at X=0 and use the current integer width
  `truncTowardZero(brX)` as `Font:DrawString`'s box-width argument with
  `Center=false` (right aligned). Do not change their anchor or alignment when
  truncating. Integer `brX` must render identically; fractional `brX` must not
  raise a draw error.
- A visible warning occupies Y=`brY-28`. If both are visible, the hint is at
  Y=`brY-48`; with only the hint it is at Y=`brY-28`. Clearing the warning
  returns the hint to the lower slot on the same render. When the hint expires,
  a still-pending warning remains in the lower slot. Width, color, text, and
  alignment for each message are independent of draw order.
- Warning starts false. `MC_EXECUTE_CMD` command `constructwarn` sets it true;
  `constructreset` clears it; unknown commands do nothing. Room/floor changes
  preserve the warning; a non-continued `MC_POST_GAME_STARTED` clears it.
  Repeating either command is idempotent.

Keep the timer/compositor/render state separate from save-data persistence and
legacy HUD-effect ownership. Use only APIs available in Afterbirth+ v1.06.T1; do not
call newer `Isaac.GetScreenWidth/Height` methods. Do not add third-party code
or assets.

## Public observation and control API

Export IsaacConstructHUD with SetWarning(boolean), SetOffset(number),
RenderFrame(), and Snapshot(). The MC_POST_RENDER callback and RenderFrame()
must call the same compositor, including the actual Font:DrawString calls.
Snapshot returns fresh lastDraws in draw order; each record contains text, x,
y, integer boxWidth, center, and color red/green/blue/alpha, plus
elapsedFrames, warningPending, bottomRightX, bottomRightY, and hudOffset.
Setters use the production state transitions rather than verifier-only state.

## Acceptance cases

hint_frame_0, hint_frame_839, hint_frame_840, hint_frame_899,
hint_frame_900_hidden, game_start_restarts_hint, floor_change_keeps_hint_timer,
warning_hidden_initially, warning_visible_when_pending,
warning_survives_room_change, warning_survives_floor_change,
warning_cleared_by_reset, reset_is_idempotent, hint_only_bottom_slot,
warning_only_bottom_slot, both_messages_stack,
hint_returns_to_bottom_after_clear, warning_stays_bottom_when_hint_expires,
fractional_offset_0_5_width_floor, fractional_offset_9_5_width_floor,
integer_corner_width_unchanged, fractional_corner_no_render_error,
hint_y_bottom_slot, warning_y_bottom_slot, stacked_hint_y,
hint_text_unchanged, warning_text_unchanged, hint_color_and_alpha,
warning_color_constant, right_alignment_mode_preserved,
live_offset_applies_next_frame, screen_resize_recomputes_corner,
warning_reset_same_frame, offset_command_validates_and_unknown_is_noop,
new_run_clears_warning.
