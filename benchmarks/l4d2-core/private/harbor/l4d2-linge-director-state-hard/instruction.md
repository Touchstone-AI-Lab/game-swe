# LinGe: configuration, event dispatch, and Director state

The MIT-licensed LinGe VScript project is at `/app/linge-hud`. Server operators
and addon authors report the following problems in its existing configuration,
event, and MoreSI APIs. Repair the complete batch without replacing the addon
with a separate implementation. These contracts describe the intended release;
they are not a request to reproduce an upstream patch.

## Configuration isolation

1. Loading a mixed-case configuration changes the input table itself. Arrays
   and newly retained nested tables can also remain shared with their input,
   so later edits to a caller's table silently alter the live configuration.
   `LinGe.Merge(dest, source, typeMatch=true, reserveKey=false)` must leave
   `source` unchanged and copy accepted table/array values recursively. Matching
   remains case-insensitive, with an exact existing key taking precedence.
   Preserve destination spelling and existing nested destination table identity.
   Unrecognised keys are ignored unless `reserveKey` is true. Keep integer-to-bool
   conversion and the existing `typeMatch=false` replacement behavior. Inputs are
   acyclic tables/arrays with ordinary scalar values; ambiguous case-only duplicate
   keys are outside this contract.

2. A restored array may arrive as a table keyed by nonnegative integers or their
   canonical decimal strings (`0`, `1`, ..., `10`). Its order now depends on table
   iteration, corrupting the SI preference list. When merging such a table into
   an array, reconstruct it in numeric index order only if the keys describe
   exactly `0..n-1`, without duplicate numeric indexes. Empty tables mean empty
   arrays. Sparse, negative, noncanonical, duplicate, or nonnumeric indexes must
   leave that destination array unchanged, without rejecting valid sibling fields.
   Reconstructed nested values must not alias the source.

3. Bulk configuration operations throw when the file is absent or malformed.
   `ConfigManager.LoadAll` and `SaveAll` must recover to the currently registered
   table values and write a valid file (recovery does not roll back edits to a
   registration-time snapshot). A syntactically valid non-table root is also
   malformed. Loading must update registered tables in place, obey `reserveKey`
   within each registered section, and never register an unknown file section.
   Saving either bulk or single sections must preserve unrelated sections of a
   valid file. Single-section Load/Save must have the same malformed-root recovery.

## Reentrant event dispatch

4. A callback that registers or unregisters another callback during dispatch can
   cause skipped, repeated, or out-of-range callbacks. Each `LinEventTrigger`
   invocation must run the ordered callback list captured when that dispatch
   begins. Changes affect subsequent invocations, including a nested invocation
   begun after the change, but not its already-running parent. Preserve duplicate
   registrations, prepend order, binding to `callOf`, forward/reverse unhooking,
   return values, and the public `LinEventHook/UnHook/Index/Trigger` APIs.

5. Changes to nested event parameters leak back to the caller, and
   `ACTION_RESETPARAMS` does not restore them for the next subscriber. Each dispatch
   must have its own deep copy of the caller's table/array payload. Subscribers in
   that invocation share edits until RESET; RESET restores the original payload
   for later subscribers. Nested dispatches must be isolated from their parent.
   `ACTION_STOP` still stops only its own invocation; null payloads remain valid.

6. Delayed events observe edits made to their payload after they were queued.
   Capture their payload when `LinEventTrigger(event, params, delay)` is called,
   but select subscribers when the delay expires. Two queued events remain
   independent. Events in this delayed-delivery contract are already registered
   when queued; preserve ignoring names that have never been registered.
   Preserve the actual VSLib timer path and ordinary immediate events.

## MoreSI Director controls

7. The SI whitelist skips consecutive invalid entries, throws on nonstrings, and
   counts duplicates as separate classes. Normalise string entries without regard
   to case; keep the first occurrence of each supported class in input order;
   discard invalid/nonstring entries. Nonarray input means no class restriction.
   Resolve the per-class ceiling using the number of distinct supported classes,
   including when quantity control is disabled (which retains the existing total
   of four). Do not mutate a caller's input array while normalising it.

8. A minimum higher than 31 can override the engine's intended 31-special ceiling.
   With quantity control enabled, the effective maximum is
   `min(31, max(simin, sibase + siauto * survivorCount))`; automatic additions apply
   only for positive `siauto`. Apply this consistently to total, dominator, and
   per-class limits. Disabling quantity control must still leave the independently
   configured whitelist, respawn interval, and initial delay working.

9. Runtime `sion`/`sioff` choices disappear on a subsequent round start without
   a cache restore. The latest command choice must remain the desired enabled
   state. A valid cache restore overrides it with the restored MoreSI enabled
   value; an invalid cache restore preserves the latest choice. Restore keeps
   live MoreSI disabled until round start. Starting disabled or disabling repeatedly
   must remove MoreSI's Director overrides and cleanup timer without an exception.
   A pending population-refresh timer must not re-enable a disabled controller.
   Keep existing command argument semantics (including `-2` meaning unchanged),
   public command registration, and independent option-disable behavior.

## Delivery and verification

Preserve the existing addon entrypoint, API names, licenses, normal HUD/damage,
hint, and reward behavior. Do not add polling as a substitute for event handling.
Keep source only: no binaries, archives, symlinks, or Git metadata. Do not modify
`/tests`. Run `python3 tools/smoke.py`; this checks packaging and source structure,
not private behavior.

The offline verifier boots the pinned real L4D2 dedicated server and exercises
the existing public APIs, registered commands, and event callbacks in its Squirrel
VM. Tests inspect copied values, callback effects/order, persisted config, and
Director option values. Delayed cases use VSLib's engine timer scheduling. Private
tests do not require a particular helper name, internal table layout, or reference
diff. Arbitrary cyclic payloads, concurrent external edits to Director overrides,
and unsupported configuration value types are outside this task.
