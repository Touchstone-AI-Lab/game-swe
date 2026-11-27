# Visible Linux completion diagnosis after the transport repair

These are diagnostic workflows, not final task validation. Original and new
halts, component pins and frozen tasks are retained. No action is resent.

## Observations

The controlled-v2 smoke passed. The first deck gold then stopped on a second
`play` completion timeout, not the previous truncated JSON failure. Read-only
HTTP observers found no short reads in the new diagnostic workflows.

| Independent diagnostic | Observation | Exit / status |
| --- | --- | --- |
| play v1, `20261031-172920-b2617404` | Completion callback repeatedly ran and returned; ROUND_EVAL, STATE_COMPLETE true, unlocked, unpaused; blind row and cash-out UI absent. No second response was attempted. | Normal; incomplete |
| play v2, `20261031-173422-808b04da` | 1,670 frames over 59.02 seconds; final 31 FPS. Draw consumed 28.21 seconds, present 23.79, game update 5.08, sound 0.34. Event timers advanced and the round-evaluation UI was only beginning near the deadline. | Normal; incomplete |
| render v1, `20261031-173823` | Mesa llvmpipe, fullscreen 1920×1080, vsync 0, 35 FPS in MENU. | Harness error: driver called nonexistent `stop` instead of `close`. Parent-death protection terminated the owned child; not a normal exit or accepted run. |
| render v2, `20261031-174126` | Own video settings selected a visible 1280×720 window; same renderer, vsync 0; MENU reached 56 FPS. | Normal; diagnostic only |
| play v3, `20261031-174257-ca347e37` | At 1280×720, first process completed its winning play in 23.812 seconds and continued through cash-out, next round and another play. Second process still timed out on its winning play at 25.026 seconds. | Both normal; incomplete; profile not adopted |

The fixed Bot `settings.lua:69-76` supplies 1/60 second to the original update
per frame in visible mode. At approximately 30 rendered frames per wall second,
game animation advances at approximately half wall-clock speed. This is an
observed environment timing limitation, not evidence that a candidate is wrong.
The second complete-callback response cannot be sent before the engine's UI
completion conditions are satisfied.

## Bounded control under investigation

`window_profile_v2` selects an ordinary visible **800×600** window only in the
fresh owned process, using the game's existing `apply_window_changes` path.
It changes isolated video settings, invokes normal resize/save-settings behavior,
and records actual dimensions, visibility and renderer. It does not modify
simulation delta, speed, game state, locks, completion flags, action response
conditions, candidate state or frozen checks. FAST and HEADLESS remain zero.
No installed game, Bot, loader, host setting or daily profile is edited.

The window hook forwards original update arguments, all return values and
exceptions; it configures once after MENU is reached. A unit-only LuaJIT test
checks deferred/one-time application, original return/exception behavior and
unchanged game state/speed. This is not engine evidence.

Independent full deck diagnostic `play-diagnosis-v4/20261031-174634-b7ae4132`
completed all three processes with normal exits and no short reads or errors.
Winning-play durations in its first two processes were 19.593 and 19.239 seconds.
This supports adopting the owned video configuration, while the 1280×720 pilot
remains incomplete. The diagnostic is not promoted to final task evidence.

The production profile now uses `linux_window_v2`, an exact copy of the inspected
800×600 hook. Its bytes are included in environment/harness fingerprints, checked
before launch and during cleanup; actual visible dimensions are required before
task actions. A fresh `linux-controlled-v2-window-v2` operator state preserves
both older halts. Final smoke and controls must be rerun without diagnostics.

This is a measured configuration remedy on the controlled host, not a claim of
a Mesa or WSLg driver defect. The first video control changed fullscreen mode,
display selection and dimensions; the later 1280×720 versus 800×600 controls kept
the ordinary windowed path. Actual FPS is measured rather than promised to be 60.
The final controls omit the temporary profiling modules, while retaining every
frozen task observer (including durable-charge's original load observer).
