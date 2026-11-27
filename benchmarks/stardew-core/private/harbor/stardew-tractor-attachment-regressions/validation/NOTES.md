# Validation: stardew-tractor-attachment-regressions

Private authoring record. It names the defects and the reference; never copy it into
an attempt workspace.

## Provenance

- Upstream: <https://github.com/Pathoschild/StardewMods> (MIT, `LICENSE` ships in the
  starter), mod **Tractor Mod**.
- Reference: the unmodified `tractor-mod/4.24.4` release tree (commit
  `b2d750f944dff2c0a540a02dd2af653b09e378c4`, released 14 March 2026 for SMAPI 4.1.10)
  trimmed to `TractorMod/`, `Common/`, `Directory.Build.props`,
  `Directory.Packages.props`, `.editorconfig`, `LICENSE` and `README.md`.
- Starter: the same tree with four upstream fixes reverted (each revert restores the
  pre-fix logic of its attachment exactly) and the release-note bullets naming them
  removed from `TractorMod/docs/release-notes.md`. `solution/gold.patch` restores both.

  | commit | upstream release | fix | attachment |
  | --- | --- | --- | --- |
  | `a92f4f9cd47adf5eee97eb5e2923baa4cee2a132` | 4.18.0 | fruit trees use fruit-tree growth stages | axe |
  | `f35bc8604385d63e62d82556c071ce771bf94139` | 4.19.2 | no seeds sown into a garden pot holding a bush | seeds |
  | `6ad0cb951396cd0956d5f143557723af9700afa8` | 4.20.0 | unplaceable custom-attachment items are not placed | custom |
  | `bd38fead316f0330e552a9447490c8ca375b8075` | 4.24.4 | the break-objects option skips breakable stones | pickaxe |

  The calico-egg-stone fix released in the same 4.24.4 (`43bc86106`) stays applied; it
  cannot be probed together with `bd38fead3` under one configuration.
- The tree uses C# 14 syntax, so the image uses the digest-pinned .NET 10 SDK that the
  Automate 2.6.1 tasks already use.

## Cases (9)

Suite: `tests/SuiteTractorAttachments.cs`; `tests/mod-config.json` sets distance 2,
sounds off, `CustomAttachments` = Parsnip and Torch, fruit-tree saplings on and grown
fruit trees off, Break Mine Stones off and Break Objects on.

- Setup (1): build the garage, let its stable spawn the tractor, walk up and mount it.
- Targets (4): a grown fruit tree is left alone; a pot holding a bush is not sown;
  parsnips are never placed; a field stone survives.
- Preserved (4): a sapling is cleared; an empty pot is sown; torches are placed; a
  placed torch is broken.

## Two-way validation (2026-09-23 UTC, this Linux x86_64 Docker host)

Through `rhenium run stardew-valley/core/stardew-tractor-attachment-regressions
<submission>` with the default `full` profile, against the runtime prepared with
`rhenium runtime prepare stardew-valley/stardew-1.6.15-smapi-4.1.10` (evaluator image
`sha256:05ddfc43e7d8...`):

| submission | run | score | complete | cases passed |
| --- | --- | ---: | --- | ---: |
| unchanged starter | `run-06b7a80c75fc4284` | 10 | yes | 5/9 (exactly the 4 targets fail) |
| reference, run 1 | `run-8578585b5c2d40bc` | 100 | yes | 9/9 |
| reference, run 2 | `run-0d8327bc877f47f3` | 100 | yes | 9/9 |
| reference, run 3 | `run-ac0494748ece42fd` | 100 | yes | 9/9 |

The three reference runs have identical case outcomes. Several earlier attempts on the
congested host never reached the game (Docker `create` timed out after the evaluator's
former 60-second limit); they are infrastructure failures, not task results, and were
rerun unchanged. Study controls and their outcomes are in
`private/study-controls/stardew-tractor-attachment-regressions/NOTES.md`.
