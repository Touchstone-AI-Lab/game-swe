# Construct: Deterministic per-room random streams

You are creating a new Lua mod for **The Binding of Isaac: Rebirth — Afterbirth+
v1.06.T1**. The starter contains only `mod/main.lua` and `mod/metadata.xml`.

## Task

Implement an isolated deterministic integer stream per `(run start seed, room
spawn seed)`. It must produce stable values for the same key, keep different
room states independent, and resume exactly after save/continue without
consuming or reseeding any game/global RNG.

## Required behavior

- Use Park–Miller with modulus `M=2147483647`. The initial room state is
  `((startSeed % (M-1))*65599 + (roomSpawnSeed % (M-1))) % (M-1)`; map zero to
  one. Each draw updates `state=(state*48271)%M` and returns `state%101`, an
  integer in [0,100]. The canonical key is
  `tostring(startSeed)..":"..tostring(roomSpawnSeed)`. Keep the current state
  and consumed-draw count for each `(startSeed, roomSpawnSeed)` key.
- `MC_POST_NEW_ROOM` selects or lazily initializes the room state. Repeated
  delivery for the same room is idempotent; revisiting a room restores the
  saved stream and does not reseed or draw. Different rooms never alias their
  state. When a run is already initialized, select the room in this callback.
- Afterbirth+ delivers the initial `MC_POST_NEW_ROOM` before
  `MC_POST_GAME_STARTED`. Cache that initial room spawn seed until `StartRun`
  has restored or reset the run state, then select it. After
  `MC_POST_GAME_END` or `MC_PRE_GAME_EXIT` has saved the run, mark the run
  uninitialized so the next startup room is likewise cached. `MC_POST_UPDATE`
  is a no-op until the run and active room are initialized; after startup it
  draws exactly once per callback.
- Each `MC_POST_UPDATE` consumes exactly one value from the active room stream
  and appends it to a mod-owned output sequence. No other callback consumes a
  value. Changing rooms or starting a new run does not mutate another room's
  saved entry.
- `MC_PRE_GAME_EXIT` and `MC_POST_GAME_END` write JSON schema version 1
  containing the run start seed and every room's key, state, and draw count.
  Saving consumes no random value; the constructrng save command uses the same
  save path. On a continued `MC_POST_GAME_STARTED`, restore only valid data
  whose run seed matches `Seeds:GetStartSeed()`. A room entry is valid only if its
  state is an integer in [1,M-1] and draw count is a non-negative integer; drop
  and reseed a bad entry without discarding valid peer entries. Missing,
  malformed, or wrong-seed data initializes lazily. A non-continued start
  clears all derived state. `outputSequence` is a test-observation trace for
  the current process only; it resets on every `StartRun` and is not persisted.
- Never call `math.random` or `math.randomseed`, mutate `Seeds`, alias an `RNG`
  object, or invoke an API that advances the game's RNG. In the acceptance
  fixtures, distinct room keys have distinct first eight outputs; identical
  keys always reproduce the same sequence.

Use only Afterbirth+ callbacks and public APIs (`Seeds:GetStartSeed`,
`Room:GetSpawnSeed`, mod save data, built-in JSON, MC_PRE_GAME_EXIT,
MC_POST_GAME_END, and MC_EXECUTE_CMD). Do not add third-party code or assets.

## Public observation and control API

Export IsaacConstructRoomRng with StartRun(continued, rawData, runSeed),
SelectRoom(startSeed, roomSpawnSeed), DrawCurrentRoom(), SaveNow(), and
Snapshot(). Engine callbacks and these methods use the same run-start, room
selection, draw, save, and load transitions. Snapshot returns fresh runSeed,
activeRoomKey, sorted rooms records (key, state, drawCount),
outputSequence, and lastSavedRaw. Tests may select deterministic run/room
keys and draw through this API but may not modify returned snapshots.

## Acceptance cases

same_run_room_same_sequence, different_room_distinct_stream,
different_run_distinct_stream, same_room_reload_same_stream,
save_resume_next_value, save_resume_consumed_count,
new_run_resets_derived_state, room_entry_reseeds_only_room_stream,
update_draw_order_stable, room_seed_not_global_rng, no_global_rng_reseed,
no_global_rng_consumption, game_rng_unchanged_by_first_draw,
repeated_update_advances_once, duplicate_room_callback_idempotent,
room_reentry_resumes_saved_stream, visited_room_state_isolated,
unvisited_room_state_deterministic, state_round_trip,
malformed_persisted_state_recovers, missing_persisted_state_initializes,
run_seed_is_part_of_key, room_spawn_seed_is_part_of_key,
value_range_is_inclusive, integer_generation_is_stable,
no_callback_order_drift, save_callback_does_not_advance,
game_start_callback_resets_once, room_change_does_not_reset_run,
save_after_n_draws_resumes_n_plus_one, invalid_room_entry_isolated,
stream_state_does_not_alias, no_math_random_dependency,
room_stream_cached_not_reinitialized, zero_seed_normalizes_to_one.
