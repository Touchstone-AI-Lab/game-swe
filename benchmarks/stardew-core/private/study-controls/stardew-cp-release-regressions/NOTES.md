# E0 notes: stardew-valley/core/stardew-cp-release-regressions

Private maintenance material. It names the defects and the reference; never copy it into
an attempt or a model workspace.

Layout: the workspace holds `StardewMods/`; every patch applies with `patch -p1` from
`/app/StardewMods` (`root` = `StardewMods`). Reference = starter + `solution/gold.patch`
(five upstream Content Patcher commits on the 2.6.1 release tree; see the task's
`validation/NOTES.md`).

## Case roles

17 entries in `clause-map.json`: 1 static, 1 runtime sentinel, 8 target, 7 preserved.

| report | target cases | defect (upstream fix) |
| --- | --- | --- |
| Path positions | `PathPart: a positive index ...`, `PathPart: a negative index ...` | fragment names tried before numbers, and segments taken from the index text (`f70cd17e4`) |
| Tokens in nested keys | `nested data: a tokenised nested key ...` | renaming a JSON property clones its value, so the value's token proxies write to a detached copy (`601912236`) |
| Positions in data models | `positions: the {X, Y} object form ... new entry`, `... field edit` | EditData converts without SMAPI's JSON settings (`4a12c9af7` entries, `56613e8a1` field edits) |
| Lists in new entries | `lists: a new entry's list field ...` | same root cause: the default Json.NET settings append to the model's default list |
| Text operations on missing targets | `text operations: removing from a missing entry ...`, `... missing map property ...` | a text operation's null result is written back as a value (`e451ffdcb`) |

Preserved (all pass in the unchanged starter): named `PathPart` fragments, a plain nested
key, the `"X, Y"` text form in an entry and in a field edit, removing a value from an
existing entry, and `Append` creating a missing entry and a missing map property.

## Controls (all run through `rhenium run`, full profile, in the real game)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| (starter) | — | starter | none | every target fails, every preserved passes | 8/16, the 8 targets fail (`run-ce03a91e8509419d`, 2026-09-23) |
| (reference) | — | reference | none | 16/16, three times | 16/16 in `run-6d729e0dd35f4804`, `run-2971368c666a47e5`, `run-edd0a2034e5f49ce` (identical outcomes) |
| `target-negative-field-edits-keep-local-serializer` | target-negative | reference | upstream intermediate state: `56613e8a1` reverted, so `Fields` edits still populate through the old local serializer | only `{X, Y} ... field edit` fails | 15/16, exactly that target fails (`run-73b38f0d728342ff`). Admissible. |
| `compat-negative-skip-text-operations-on-missing-entries` | compat-negative | reference | every text operation on a missing data entry is skipped | all targets pass; only `appending to a missing entry creates it` fails | 15/16, exactly that preserved case fails (`run-6e1f71547216473a`). Admissible. |
| `alternative-own-converters-and-detached-values` | alternative | starter | independent repair of every report (see manifest note) | 16/16 | 16/16 (`run-3f383d23ad2d499c`). Admissible. |

The alternative shows the reference's reflection into SMAPI internals (`SCore`'s toolkit)
and into Json.NET (`JProperty._name`) is not required by any case.

## Assertion-strength findings

- `Task-preserve-existing-text-ops` is **weak**: only an existing data entry is probed,
  not an existing map property.
- The position group probes `Vector2` only; `Point`, `Rectangle` and `Color` fields are not
  probed (an implementation that handles only `Vector2` passes).
- Only `RemoveDelimited` is probed for missing targets; `ReplaceDelimited` and data-model
  `Fields` targets are not.
- No over-constraining assertion found: the alternative, written only from the exam and
  the author guide, passes every case.

## Infrastructure note

The host's Docker daemon was congested during these runs. Evaluations whose container
could not be created within the plugin's 60-second limit (or whose Hub database was
locked by another command) never reached the game; they were rerun unchanged, and only
complete runs are recorded above.
