# Validation: stardew-cp-release-regressions

Private authoring record. It names the defects and the reference; never copy it into
an attempt workspace.

## Provenance

- Upstream: <https://github.com/Pathoschild/StardewMods> (MIT, `LICENSE` ships in the
  starter), mod **Content Patcher**.
- Starter: the `content-patcher/2.6.1` release tree (commit
  `2e40a38874c3d7f5f19d409f342244fcaf3d28bb`, released 27 March 2025 for SMAPI 4.1.10)
  trimmed to `ContentPatcher/`, `Common/`, `Directory.Build.props`,
  `Directory.Packages.props`, `.editorconfig`, `LICENSE` and `README.md`. Nothing was
  reverted or injected: every defect is genuine in that release, and its release notes
  predate every fix.
- Reference (`solution/gold.patch`): five upstream commits applied in order, with only
  line offsets differing from upstream:

  | commit | upstream release | fix |
  | --- | --- | --- |
  | `4a12c9af7f024f775efac4adb3dc11f5c154b15a` | 2.7.0 | `EditData` entries converted through SMAPI's JSON serializer |
  | `56613e8a1176805a65a0dfc455bf4c087934466d` | 2.7.0 | `EditData` field edits use the same serializer |
  | `601912236e440ebd83e4f307d2293e2ff044209b` | 2.7.0 | tokenised JSON property names keep their tokenised values |
  | `e451ffdcb96a238c0606c5a40f34e9cedac54c3b` | 2.9.0 | text operations that produce no value don't create one |
  | `f70cd17e44e033c0ae9ae318d7f28b444cf9a231` | after 2.9.1 | numeric `PathPart` positions |

  CP 2.9.x requires SMAPI 4.4.0, so the task is pinned to the 2.6.1 tree, which builds
  against the pinned SMAPI 4.1.10; all five commits apply to it unchanged.

## Cases (16)

Suite: `tests/SuiteCpReleaseRegressions.cs`, fixture pack `tests/probe-pack/`
(one independent patch per behavior, so a failing group cannot stop another from
applying). Roles are recorded in
`private/study-controls/stardew-cp-release-regressions/clause-map.json`.

- Runtime sentinel (1): the pack loads and plain entries apply.
- Targets (8): `PathPart` positive index; `PathPart` negative index; tokenised nested
  key; `{X, Y}` position in a new entry; `{X, Y}` position in a field edit; a new
  entry's list field; `RemoveDelimited` on a missing entry; `RemoveDelimited` on a
  missing map property.
- Preserved (7): `PathPart` fragment names; plain nested key; `"X, Y"` text position in
  an entry and in a field edit; `RemoveDelimited` on an existing entry; `Append`
  creating a missing entry; `Append` creating a missing map property.

Measured fact that shaped the position group: on the pinned Linux game build the
default Json.NET conversion accepts `Vector2` only in the `"X, Y"` text form, so the
starter rejects the object form that the author guide uses. SMAPI's own serializer
reads both.

## Two-way validation (2026-09-23 UTC, this Linux x86_64 Docker host)

Through `rhenium run stardew-valley/core/stardew-cp-release-regressions <submission>` with
the default `full` profile, against the runtime prepared with `rhenium runtime prepare
stardew-valley/stardew-1.6.15-smapi-4.1.10` (evaluator image `sha256:1c187ab11538...`):

| submission | run | score | complete | cases passed |
| --- | --- | ---: | --- | ---: |
| unchanged starter | `run-ce03a91e8509419d` | 10 | yes | 8/16 (exactly the 8 targets fail) |
| reference, run 1 | `run-6d729e0dd35f4804` | 100 | yes | 16/16 |
| reference, run 2 | `run-2971368c666a47e5` | 100 | yes | 16/16 |
| reference, run 3 | `run-edd0a2034e5f49ce` | 100 | yes | 16/16 |

The three reference runs have identical case outcomes. Study controls and their outcomes
are in `private/study-controls/stardew-cp-release-regressions/NOTES.md`.
