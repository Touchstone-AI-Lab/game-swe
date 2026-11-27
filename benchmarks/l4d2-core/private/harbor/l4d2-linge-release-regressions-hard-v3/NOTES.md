# Maintainer notes: audited hard-v3

## Scope and provenance

This branch contains nine independently repairable defect groups across `HUD.nut`, `Hint.nut`, and
`RewardHP.nut`: terminal Survivor overflow, pre-incapacitation accounting,
exact-zero lethal classification, Tank transition filtering and terminal accounting,
stale special-infected damage, qualified flame damage, cache rollback baselines,
help-marker lifecycles, and temporary-only RewardHP limits.

Most repairs are composed from the upstream revisions named in `task.toml`. The
RewardHP mode-2 boundary is a task-local semantics repair derived from the module's
documented modes. The cache baseline is the behavior fixed by upstream `c27c22d`.
The exact-zero seed deliberately keeps the broken death-event fallback for negative
post-health while omitting the zero boundary. This makes the public delayed-output
report fail over a complete hurt/death/timer sequence; a solver may repair either the
hurt classification or the death fallback.

The delayed attacker/victim aggregation paragraph is a preservation requirement,
not a claim that the broken base has an additional pair-key defect.

The agent receives the complete broken project and `instruction.md`. Tests, this
file, validation tables, and the reference solution are absent from `/app/linge-hud`.
The submitted project includes `tools/smoke.py`, an answer-free source/entrypoint
check that the agent can run before submission.

## Runtime and scoring boundary

No Valve game files are stored in the repository. The image installs the anonymous
Left 4 Dead 2 dedicated-server app `222860` with SteamCMD. The verifier runs offline,
packages the submitted source as an addon, boots a fixed coop map, and executes 42
deterministic cases in the engine's Squirrel VM. Reward is binary: source/package
checks, all cases, and the final server marker must pass.

Terminal fixtures now drive the shipped `VSLib.EasyLogic.OnTakeDamage` chain and a
complete event transition. Survivor and Tank assertions check final counters and
delayed output, not which callback owns the repair. The timer fixture models named
timer replacement and executes the registered callback while capturing `ClientPrint`.
Hint checks dispatch the registered public game events and observe the resulting marker
entities rather than call lifecycle helpers, inspect timer names, or compare private enum
values. Cache checks likewise dispatch the registered transition, restore, and round-end
events, accepting a baseline advanced at transition or restore time.

`validation/case-contracts.tsv` maps every case to a public report or preservation
requirement. Fixtures still use the project's registered event owners, and the
pre-damage compatibility boundary is the callback chain already shipped in VSLib;
the verifier does not attempt to discover arbitrary new hook frameworks.

## Validation status

The audited hard-v3 contract is frozen. The final controls produced:

- broken base: 28/42, with all 14 failures confined to target cases across nine groups;
- complete oracle: 42/42;
- nine single-group predicates: every candidate retained all 28 base passing cases and
  unlocked only the case or cases in its named group;
- six behaviorally distinct complete alternatives: 42/42 each, covering VSLib
  pre-damage terminal accounting, death-event exact-zero fallback, map-transition
  baseline advancement, an independent revive lifecycle value, and complete repairs
  with every Hint or cache lifecycle helper renamed.

The exact recorded jobs and content hashes are in `validation/predicate-matrix.tsv`,
`validation/differential-matrix.tsv`, and `validation/contract-hashes.tsv`.
Frozen contract identifiers are:

- evaluation contract: `f666786544f5689c6c46a977b408f4017f52326a38558919ed210056a1fcca96`;
- public prompt: `654417cd28d4ee22d8f523f9ad77e198fc19f0aa075cb13efac671fc2f175682`;
- private tests tree: `e2892cc2b278ab7b51369217ad82500af4d870dbbd0b63b9d3b0b14b445aff9c`;
- task metadata: `cc029cbd293c914f21c7581a5f2ddde25df04bf3bf4483d94e9ad0d4030b046b`.

## Known limitation

`tools/smoke.py` checks UTF-8 source shape, delimiters, attribution, required files,
and addon includes. It is not a Squirrel compiler and does not expose target behavior.
The managed dedicated-server verifier remains authoritative for engine semantics.
