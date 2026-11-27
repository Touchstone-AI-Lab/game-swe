# Private Stream — seeded-effect-stream-v1

Repair the ordinary Private Stream Joker, `j_ses_private_stream`, in `joker.lua`. Keep the supplied mod identity and manifest. Difficulty: **uncalibrated**. This is an authored repair task, not a claimed historical upstream bug.

Each real, successful player discard operation grants one integer cash reward from 1 through 9. An operation discarding several cards still receives exactly one reward. Selecting cards, observing/displaying state, ordinary scoring, and other native effects grant no reward from this Joker and must not consume its reward sequence.

The public compatibility rule is a dedicated native seeded unit stream with the exact key `ses_private_v1`. On each qualifying operation, use its next unit draw `u` and award `1 + floor(9*u)` dollars. The native API form is `pseudorandom('ses_private_v1')` with no integer bounds. An equivalent implementation is allowed if it produces the same externally observable sequence. Do not reset the sequence between operations or consume extra draws. Same seeded runs and discard sequences must reproduce the same rewards despite unrelated native gameplay; a different run seed uses its own sequence. Do not share native Lucky or other effect streams.

The cash must actually be added once by the time that discard completes and the controller becomes ready. The Joker remains owned, adds no Chips or Mult, and does not alter cards, native discard counts, native Lucky effects, or other game rules. Native Lucky money, when applicable, remains separate from this Joker's reward. Preserve its ordinary Common identity and cost 4.

Version 1 covers one ordinary active instance in a seeded run, legal player discard operations at SELECTING_HAND, and normal play between operations. Copies, retriggers, debuffs, editions, automatic/boss discards, multiple instances, save restoration and other mods changing probabilities or rewards are out of scope. Only the candidate Lua is editable; the operator supplies preparation and read-only observation separately.
