# Validation: stardew-cjb-cheats-regressions

Private authoring record. It names the defects and the reference; never copy it into
an attempt workspace.

## Provenance

- Upstream: <https://github.com/CJBok/SDV-Mods> (MIT, `LICENSE` ships in the starter),
  mod **CJB Cheats Menu** (maintained by CJBok and Pathoschild).
- Reference: the unmodified `cheats-menu/1.42.0` release tree (commit
  `9bf8e959209eb19b047c6bfca81783408ade1db8`, released 19 April 2026 for SMAPI 4.1.10)
  trimmed to `CJBCheatsMenu/`, `Common/`, `Directory.Build.props`,
  `Directory.Packages.props`, `.editorconfig`, `LICENSE` and `README.md`.
- Starter: the same tree with five upstream fixes reverted. The cheat files moved to
  file-scoped namespaces after most of these fixes, so the reverse patches do not
  apply verbatim; each revert restores the pre-fix logic exactly. The release-note
  bullets that name the five fixes were removed from `CJBCheatsMenu/docs/release-notes.md`
  (nothing else in the notes changed). `solution/gold.patch` restores both.

  | commit | upstream release | fix | cheat |
  | --- | --- | --- | --- |
  | `7fcfe1d09883930274f95ba032c89694364811d8` | 1.38.0 | grubs no longer start turning into flies | One Hit Kill |
  | `ad97de5458b330d00ed7115172f3733e6c6ff8e7` | 1.37.0 | golden treasure chests can appear | Always Treasure |
  | `2c05d09d944175c1063695e96f00978a6f57fbef` | 1.36.2 | troughs filled when silos are empty | Auto-Feed Animals |
  | `40e1912d4493dfbc3385d1bff265e0ddc4b4f890` | 1.36.2 | only animals in buildable locations are petted | Auto-Pet Animals |
  | `3a9ba556ed23f434db89bb1388656dfc4dddd3c5` | 1.36.2 | only pets on the farm and in farmhouses are petted | Auto-Pet Pets |

  The one-hit-kill state is itself upstream history: 1.37.0 stopped setting every
  monster's maximum health to 1 (to keep vampiric healing) and thereby reintroduced
  the grub bug that 1.38.0 fixed. The starter's release notes still contain both
  earlier bullets, as the 1.37.x releases did.
- The tree uses C# 14 syntax, so the image uses the digest-pinned .NET 10 SDK that the
  Automate 2.6.1 tasks already use.

## Cases (11)

Suite: `tests/SuiteCjbCheatsRegressions.cs`; `tests/mod-config.json` switches on One
Hit Kill, Always Treasure, Auto-Feed Animals, Auto-Pet Animals and Auto-Pet Pets.

- Runtime sentinel (1): the mod is loaded and the world is ready.
- Targets (5): a grub stays a grub; troughs filled with an empty silo; a goat in town
  is not petted; a dog in town is not petted; golden chests appear with the fishing
  mastery (some but not all of 120 minigames).
- Preserved (5): a slime drops to 1 health and keeps its maximum health; troughs take
  hay from a silo that has some; coop animals are petted; the farm pet is petted;
  every minigame has a chest and none is golden without the mastery.

## Two-way validation (2026-09-23 UTC, this Linux x86_64 Docker host)

Through `rhenium run stardew-valley/core/stardew-cjb-cheats-regressions <submission>` with
the default `full` profile, against the runtime prepared with `rhenium runtime prepare
stardew-valley/stardew-1.6.15-smapi-4.1.10` (evaluator image `sha256:06f9deadb875...`):

| submission | run | score | complete | cases passed |
| --- | --- | ---: | --- | ---: |
| unchanged starter | `run-72670f62c548489f` | 10 | yes | 6/11 (exactly the 5 targets fail) |
| reference, run 1 | `run-e089ce3134304286` | 100 | yes | 11/11 |
| reference, run 2 | `run-cf39d4a5be814f80` | 100 | yes | 11/11 |
| reference, run 3 | `run-fb7775b93e0d43f3` | 100 | yes | 11/11 |

The three reference runs have identical case outcomes. Study controls and their outcomes
are in `private/study-controls/stardew-cjb-cheats-regressions/NOTES.md`.
