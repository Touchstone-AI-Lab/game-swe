# L4D2Lib: live map data and Tank encounter state

Repair the complete L4D2Lib plugin inside `/app/l4d2-competitive`. Keep the
upstream public natives/forwards and unrelated gameplay behavior. The starter
already contains the accepted collection release fixes and score lifecycle
repairs. This task adds eight intended contracts:

1. **Live provider reload is not an atomic map update.** When the Confogl library
   is added/removed, reload the selected mapinfo file and immediately select the
   current map and update cached geometry. A failed import must retain the last
   successfully imported file and current map view. Missing files and syntactically
   malformed or truncated KeyValues documents are failed imports, even if the
   engine importer returns success after accepting partial data. Validate the
   entire document before committing; no particular parser is required. With no successful import,
   remain safely unavailable rather than keeping an invalid KeyValues handle.
   A successfully imported file without the current map deliberately replaces
   the old data; availability is false and getters use their supplied defaults.
2. **Lookups depend on a shared KeyValues cursor.** Every map-value lookup and
   subsection copy addresses the current map, independent of previous queries,
   reloads, failed subsection lookups, or slash-separated nested subsection paths (for example `outer/inner`). Copy a present
   subsection's children into the caller's current KeyValues node using the
   existing KeyValues copy semantics (replacement of that node's children);
   a missing subsection leaves the destination unchanged. Never fall back to
   similarly named keys at the file root or a different map. Keep the existing
   return signatures; a copy's result is observed in the destination, not a new
   return code.
3. **Output buffers and unavailable defaults are unsafe.** String getters honor
   the caller's declared capacity including the terminator; capacity zero writes
   nothing and capacity one writes only the terminator. Vector/float/int/string
   defaults work with absent map data and absent keys. Do not read past caller
   output arrays merely to fill them, or mutate a supplied default vector.
4. **Saferoom geometry accepts stale/invalid entities.** Invalid/free entity
   indices return Neither without throwing. Geometry supports valid positioned
   networked gameplay entities through their existing `m_vecOrigin` send property.
   Worldspawn, non-networked entities, and entities without that property return
   Neither. For supported entities,
   start membership uses max(start_dist,start_extra_dist), end membership uses
   end_dist, boundaries are inclusive, and overlapping rooms return both bits.
   A negative effective radius disables that room. Preserve the existing medkit
   heuristic when there is no map entry; no stale end geometry may survive a
   successful reload to missing-map data.
5. **Tank encounters accept unrelated or duplicate events.** A first tank_spawn
   requires a connected living team-3 class-8 client. Invalid userid, survivor,
   other infected class, and duplicate spawn events must not start a new encounter
   or emit a forward. While one encounter is active, a tank_claw pickup by a
   different valid living Tank is a handoff; repeated pickup by the current owner
   and unrelated item/client pickups do nothing. Preserve the published zero-based
   pass count: the first real handoff reports zero, then one, and so on.
6. **Pending death timers outlive their encounter.** A current owner's death
   schedules one notification 0.5 seconds later; repeated death events do not
   multiply or postpone it. A real handoff within that grace period cancels it;
   duplicate same-owner pickups do not. Round/map reset cancels pending work and
   resets pass numbering. No callback from an older encounter may report or reset
   a later encounter. A non-owner death must have no effect.
7. **Client slot reuse changes Tank ownership.** Associate ownership and pending
   work with the client connection, not only its reusable slot. Disconnecting
   the current owner retires that encounter silently and cancels pending death;
   a later occupant can start a fresh encounter. Unrelated disconnects do not
   erase the current owner. Do not pass a replacement connection as the dead Tank.
8. **Forward callbacks observe half-committed state.** Commit a handoff and advance
   its count before invoking observers; a nested valid handoff reports the next
   count and remains current. Retire a completed death and clear its timer before
   invoking L4D2_OnTankDeath: an observer may start a new Tank encounter there,
   and it must survive the old callback's return. Round resets made by an observer
   also remain effective. Each original transition emits only its own forward.

These contracts describe intended release behavior, not a prescribed patch.
Private tests load the complete compiled plugin in the real pinned L4D2 server,
use its public natives, engine events, SourceMod lifecycle callbacks and real
entity properties. A trusted Confogl provider supplies local test mapinfo paths.
No assertion depends on private helper names, arrays, or a particular diff.

Preserve GPL notices and source-only packaging. Do not modify `/tests` or add
game files/compiled archives. Run `python3 tools/smoke.py` after editing.
