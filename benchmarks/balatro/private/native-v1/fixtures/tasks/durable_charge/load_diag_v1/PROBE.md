# load-diag-v1

Read-only instrumentation of the unchanged probe-save-v1, with the same six required cases and 25 second action timeout. One load per fresh second process. No candidate mod.

The inspected fixed dispatcher exposes `BB_DISPATCHER.endpoints.load.execute`. EventManager.add_event receives Event instances whose `func` source identifies the completion callback in endpoints/load.lua. Instrument those calls without scheduling them, changing their conditions, catching original exceptions, or changing argument/return arity (including trailing nil). Only diagnostic bookkeeping and the private diagnostic log are written.

Observe G.STATE/STAGE/STATE_COMPLETE, CONTROLLER.locked/locks, SETTINGS.paused, OVERLAY_MENU, screenwipe, hand presence, TIMERS.REAL/TOTAL, completion-event metadata and counts, response calls/returns. Values come from the pinned source. No save contents, complete game source, host environment, or object addresses are recorded. Heartbeats every second plus state transitions, capped at 512 rows / 192 KiB per process; final read-only RPC supplies counters even at the cap. Original exceptions propagate directly; an entered-but-not-returned callback is observable without swallowing or rethrowing the exception.

This version diagnoses; it does not repair lifecycle or award success from a reconciliation snapshot.
