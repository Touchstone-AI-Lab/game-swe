# Confogl: transactional server ConVar profiles

The full Competitive Rework source is at `/app/l4d2-competitive`. Repair the
server ConVar profile lifecycle in Confogl without replacing the project or
altering unrelated gameplay modules. Existing easy release fixes and the score
lifecycle fixes are already present in this starter.

1. **Layered profiles lose their last assignment.** Before tracking starts,
   `confogl_addcvar <name> <value>` stages assignments without changing live
   ConVars. Names are case-insensitive and the last valid assignment wins,
   whether a ConVar already exists or is still pending creation. Duplicate
   assignments must not create duplicate hooks or reset records. Once tracking
   has started, further add commands remain ignored.
2. **Activation captures the wrong baseline.** On the first effective
   `confogl_setcvars`, capture every currently resolvable ConVar's actual string
   value immediately before the batch starts writing. Registration-time values
   are not restoration baselines. Snapshot the whole batch before any write:
   another plugin's change hook may change a second ConVar while the first is
   applied. Repeated activation/config callbacks must not replace a baseline
   with an already enforced value. Keep the existing match-enabled gate.
3. **Enforcement merely logs drift.** While active, an external change must be
   corrected to the staged desired value synchronously. Respect SourceMod's
   normal bound/coercion behavior (e.g. desired 20 with upper bound 10 enforces
   10). Do not recurse indefinitely, duplicate registrations, or globally skip
   enforcement on another tracked ConVar during a change-hook callback. A
   finite cross-ConVar callback must not leave drift after the correction.
   An in-range desired string retains its representation (for example `01`,
   not numeric-equivalent `1.0`), including after finite cross-ConVar writeback.
   Numeric bound equivalence applies when the desired value is actually clamped.
4. **Late-bound entries have a different lifecycle.** Unresolved names survive
   configuration callbacks. When they first resolve, capture their value at
   first activation and enforce them through the same rules as early entries.
   A callback while inactive only resolves/stages entries. Later repeated
   callbacks preserve the first baseline; resolution and duplicate staging must
   never produce two records for the same engine ConVar.
5. **Release overwrites server configuration.** `confogl_resetcvars`, while the
   match is disabled, and plugin unload must release the whole profile. Remove
   all its enforcement hooks before restoring any values, restore each activated
   entry's saved string exactly, and discard pending/staged records. An entry
   that was never activated must not write anything on release. A later profile
   cycle must capture a fresh baseline. A reset while a match is enabled remains
   rejected without changing state.
6. **Oversized arguments are silently truncated into valid assignments.** Keep
   the existing 63-byte maximum for ConVar names and desired values. Reject
   oversized command arguments in full, including an oversized duplicate; do
   not stage a truncated value/name or overwrite a previous valid assignment.
   Empty desired strings and quoted strings with spaces remain valid. The
   restoration baseline may be longer than a desired value: preserve engine
   strings up to 255 bytes without truncation.
7. **Diagnostic offsets can break a live profile.** Both `confogl_cvarsettings`
   and `confogl_cvardiff` must handle negative, end-of-list, and past-end offsets
   without an exception or mutation. Valid pages keep their existing behavior.

These are task-authored intended behaviors over the frozen source, not a request
for a specific upstream diff. Public commands, native declarations and other
modules must remain compatible. The private verifier compiles and loads the
complete submitted Confogl plugin in the actual pinned L4D2/SourceMod runtime,
uses public commands and configuration callbacks, and observes real ConVars and
change hooks. It does not inspect private helper names or array layouts.

Keep source only, preserve GPL notices, and do not modify `/tests` or add
compiled/archive artifacts or game files. Run `python3 tools/smoke.py` after
editing.
