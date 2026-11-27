# LinGe / VSLib: scheduler and persistence regressions

The complete LinGe VScripts source tree is at `/app/linge-hud`. Its vendored
VSLib services are used by the addon and by external scripts. Repair these eight
intended release contracts without replacing the addon or changing unrelated
HUD, event, Director, hint or reward behavior. Follow the effective runtime
definitions: LinGe also overrides some VSLib methods after library loading.

1. **Callbacks mutate their own scheduler.** At one scheduler update, only timers
   present at its start are eligible to run. A callback may remove itself, remove
   another due timer, or create/replace a named timer. Removed work must not run
   later in that update; newly created work must wait until a later update and its
   own delay. A named timer that replaces itself must survive cleanup of the old
   callback. Each due timer runs at most once per update, including after a late
   update; preserve the ordinary repeat and callback-returning-false behavior.
   No ordering between otherwise independent due timers is promised.

2. **Failure and retirement leave stale timer identities.** A throwing callback
   must be invoked only once, retired, and reported without stopping unrelated
   callbacks or clock updates. Never retry it merely to reproduce its exception.
   Completing, explicitly removing, failing, or round-ending a named timer must
   remove its stale name mapping from the exported `TimersID` table. Round end still preserves KEEPALIVE timers and
   their usable names. Removing an already retired timer remains harmless.

3. **Timer options leak between registrations.** Countdown/duration bookkeeping
   belongs to each timer; sharing an options table must not make timers consume
   each other's counts or modify that caller's table. COUNTDOWN uses a positive
   integer count and reports its remaining count through the established
   `TimerCount` callback parameter. DURATION runs `floor(duration / effective
   delay)` times; a nonnegative duration shorter than the delay runs zero times.
   DURATION_VARIANT keeps its existing elapsed-duration policy. Reject invalid
   counts, negative durations, nonnumeric delay/duration, nonfunction callbacks,
   or incompatible count/duration flags safely with `-1` from AddTimer. Keep the
   minimum delay of 0.1 seconds. An invalid AddTimerByName replacement returns
   `-1` and leaves the previous valid named timer intact; a valid replacement
   still returns its name. Callback parameter tables keep their existing shared
   identity; only scheduler-owned bookkeeping must be isolated. Preserve opaque
   non-null payloads for ordinary and DURATION_VARIANT callbacks, including
   integers and arrays used by MoreSI and delayed LinGe events; do not wrap,
   clone, or reject them. Null retains its existing empty-table convention.
   COUNTDOWN and DURATION require a table or null because they publish
   `TimerCount`; reject other payloads atomically with `-1`. Existing MoreSI
   team-change refresh and delayed LinGe event delivery must still work.

4. **Clock transitions mischarge elapsed time.** ManageTimer commands 0 (pause),
   1 (count up), and 2 (count down) must settle the old mode through the transition
   time before changing mode. Paused elapsed time must never count later. A
   non-null explicit value resets both value and time baseline. Countdowns that
   disallow negatives clamp at zero even across a long update; allowing negatives
   still permits crossing zero. ReadTimer must report the value at read time,
   consistently with subsequent updates. Preserve independent named clocks and
   the existing null result for an unknown name.

5. **Saved strings and keys do not round-trip.** New SaveTable/LoadTable files
   must preserve quotes, backslashes, tabs, carriage returns, newlines, and literal
   `{VSQUOTE}` / `{VSSLASH}` text. Tables support arbitrary string keys (including
   empty strings, punctuation and numeric-looking strings) and signed integer
   keys without key-type collisions. New serialization may use a version marker
   and a different data representation; internal formatting is not the contract.

6. **Nested values disappear or mutate callers.** New persistence must preserve
   nested tables and ordered arrays, empty containers, null, booleans, integers,
   and finite floats (within the VM's normal single-precision tolerance). Saving
   must not mutate its input or reject repeated noncyclic references merely
   because they share an object. Functions, classes/instances, unsupported key
   types and cyclic containers must be rejected safely: SaveTable returns false
   and leaves an existing file unchanged. Never partially overwrite a good file
   while discovering an unsupported value. Loading a fresh valid save returns
   independent containers; alias identity need not survive persistence.

7. **Existing files remain readable.** Continue reading legacy `.tbl` data written
   by this snapshot: brace tables with clean unquoted keys and `key = value`,
   bracket arrays, primitive values, and whitespace-separated entries. Recursively
   decode the old string markers and canonical `_vslInt_` nonnegative integer
   keys, including inside arrays and nested tables. Only an entire key matching
   `_vslInt_` followed by a canonical unsigned decimal integer is an encoded key;
   a similar substring elsewhere remains an ordinary string key. This legacy
   interpretation must not corrupt literal marker text or key names in new saves.

8. **Loading executes or crashes on malformed data.** LoadTable must parse data,
   not execute arbitrary Squirrel expressions. Missing, malformed, truncated,
   trailing-garbage, or executable-expression input returns null without an
   uncaught exception or script side effect. Valid table/array data still loads.
   SaveTableFileName/LoadTableFileName and normal LinGe configuration persistence
   must continue to work through the repaired public interfaces.

These are task-authored intended behaviors over the frozen existing source,
not a request for a particular upstream patch. Preserve the MIT notices and the
public VSLib entry points. Keep source only; do not add binary/archive artifacts,
symlinks, Git metadata or game files. Do not modify `/tests`.

Run `python3 tools/smoke.py` after editing. The private offline verifier loads the
actual addon in the pinned L4D2 Squirrel VM, observes callbacks across real engine
ticks, and reads/writes actual scriptdata files. A trusted independent driver
keeps the tests progressing even when the submitted timer scheduler is broken.
It does not compare patches or require a particular parser or private helper name.
