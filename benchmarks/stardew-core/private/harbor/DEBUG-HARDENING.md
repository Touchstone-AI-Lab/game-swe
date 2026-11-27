# Debugging-category hardening — design record

Started 2026-09-18 (PT). Trigger: the debugging tasks in `stardew-core` were
saturated and no longer discriminated, and the difficulty levers tried earlier
(NOTES.md) had not changed that. This file records the diagnosis, the proposed
levers, the external review, and the validation of each candidate. It is private
authoring material: it names defects and must never reach an attempt workspace.

## 0. Answer-key leak in the composite starters (found 2026-09-18)

The three composite tasks start from Automate 2.6.1 with upstream fixes reverted,
but their starter trees kept 2.6.1's own `Automate/docs/release-notes.md`. The
Hub's `materialize_starter` copies the whole `StardewMods/` tree into the attempt
workspace, so the model under test can read a changelog that names each reverted
fix, in some cases together with the repair:

> Fixed handling of machines with a zero-size output. Automate now discards the
> broken output, which matches what happens when you try to empty the machine
> manually.

| task | scored groups | groups named in the shipped release notes |
|---|---|---|
| `release-regressions` | 4 | 4 (mini-fridge, Junimo seed option, `GetMachineStates` initial scan, zero-size output) |
| `release-regressions-v2` | 5 (+1 unscored haystack) | 4, plus the haystack (incubated eggs) |
| `release-regressions-v3` | 3 (+1 reported but unasserted) | 2 (zero-size output, `GetMachineStates`), plus the unasserted chopped-bush report |

The only groups the notes do not name are the engineered location-key pair, which
exist in no upstream history. The five single-defect tasks start at the release
*before* their fix, so their notes do not mention the fix. There is no `.git` in
any starter. Other docs (`README.md`, `technical.md`) describe intended features
only, which is legitimate specification.

Consequence: every earlier difficulty judgement about the v1–v3 composites was
made with this leak present. Whether a given run read the file is visible only in
its trajectory, so those judgements are not evidence that the levers do not work.

Remediation on this branch: each composite starter loses exactly the release-note
entries for the fixes its own tree reverts (v1: 4 lines, v2: 5, v3: 3); nothing
else in the notes changes. The change is documentation-only and compiles
nothing, but it is a starter-snapshot change, so the three tasks still need
real-game base/reference controls and a catalog version bump before release.

Authoring rule, added to the checklist: **a starter built by reverting upstream
fixes must not ship a changelog, commit history, or doc entry that post-dates
the reverted fixes.** Grep the starter for each reverted fix's release-note text
before validation.

Separately, `release-regressions-v3/task.toml` has stale `base_ref`/`fix_commit`
strings copied from v2: v3 actually restores the mini-fridge and seed fixes and
reverts `001e64aa` (chopped bush) instead.

## 1. Author's diagnosis (written before external review)

Why the eight debugging tasks are easy, in order of how much each explains
(item 0 above was found after this list was written; §6 screens for its
effect):

1. **Localization is retrieval.** Every report carries a noun that greps straight
   to the defect site: mini-fridge → the chest-ID list, "seeds" → the Junimo hut
   config field, `GetMachineStates` → the API → `MachineManager`, "chopped the
   bush" → `BushMachine`, "two coops" → location identity. The v3 exam even names
   an API method, and every exam's Notes enumerate what the harness exercises
   ("machine setups, the mod API, farm buildings (including several of the same
   type), and terrain features"). The DarkRP pack's public policy forbids
   subsystem maps and internal identifiers; the Stardew exams do not follow it.
2. **Repair is restoration.** Once found, the correct code is implied by the code
   around it: `JunimoHutBehaviorForFertilizer` next to a `...ForSeeds` field,
   `NameOrUniqueName` on the same type, `disabled` computed beside `active`. Gold
   patches are reverted upstream fixes of 2–58 changed lines. No repair requires
   knowledge the repository does not already display.
3. **Tests check only the reported manifestation.** A patch that special-cases
   the reported object passes. No suite asserts a sibling manifestation of the
   same root cause.
4. **Composites are additive.** For a strong agent the per-group pass probability
   is ≈1, so the multiplicative compounding that v2/v3 relied on does not bite.
5. **Scaffold shape.** The Hub runs mini-swe-agent on the host: no build, no game,
   no decompiler. Diagnosis is pure static reading, and every defect is statically
   visible, so static reading is sufficient.

`stardew-auto-workshop` differs in kind: it requires reasoning about **engine
semantics that the repository does not show**: the game's own machine state
transitions (`heldObject`, `readyForHarvest`, `OutputMachine` triggers,
`AttemptAutoLoad`). Its reference does not hand-roll those transitions; it lets
the engine perform them.

## 2. Proposed levers

Ordered by expected yield. Each must survive the fairness rules in NOTES.md
(assertion discipline, two-way validation, no mechanism assertions).

- **P1 — engine-boundary defects.** Put the defect in the mod code that mirrors
  vanilla behaviour (`DataBasedObjectMachine.OnOutputCollected` mirrors
  `SObject.CheckForActionOnMachine`; also `AttemptAutoLoad`, `OutputMachine`
  trigger handling, `RecalculateOnCollect`, tapper product updates, `Chest.addItem`
  leftover handling, `Item.canStackWith`). Strip the explanatory comments that
  currently document the required ordering. The code then looks locally
  consistent; only knowledge of 1.6 machine semantics (which vanilla machines
  re-arm on `OutputCollected`, which recalculate on collect) exposes it.
  Open fairness question: the agent has no game DLL or decompiler, so P1 partly
  measures pretraining knowledge of Stardew internals. A mitigation is to ship a
  neutral, authored "vanilla machine rules" reference in the workspace that states
  general engine behaviour without pointing at the defect.
- **P2 — root-cause generalization cases.** The report shows one manifestation;
  the exam states the general contract; the suite also asserts two or three
  sibling manifestations of the same root cause reached through different entry
  points (another machine type on the same trigger path, another storage type, a
  building interior). A symptom-local patch fails. Every sibling case must trace
  to a sentence in the exam.
- **P3 — interacting-invariant repairs.** Defects whose obvious fix violates a
  second stated invariant, so the gold is a small redesign constrained by several
  cases rather than a one-line restoration. Example: output that does not fit in
  storage must stay in the machine (no loss), a partial push must keep the
  remainder, a zero-size output must still be discarded, and the machine must not
  restart until emptied. This transplants auto-workshop's interacting-invariant
  shape into the debugging category.
- **P4 — vocabulary decoupling and exam hygiene.** Reports in player vocabulary
  only (no class, API, or config-field names); no Notes line enumerating harness
  coverage; catalog summaries no richer than the exam.
- **P5 — model-in-the-loop screening.** Screen each candidate on the Hub scaffold
  with a weaker model and accept only candidates it fails in at least 2 of 3 runs,
  then measure stronger models for the ceiling. A fairness audit on every accepted
  candidate guards against selecting for trickiness.

Already tried (NOTES.md), not to be retried: defect count, defect subtlety,
engineered uncontaminated defects, unscored decoys, multi-step gameplay state,
per-group difficulty floor, out-of-repo compiled mod.

## 3. First-batch candidates (before review)

| id | levers | defect | reported manifestation | sibling cases |
|---|---|---|---|---|
| C1 | P1+P2 | `OnOutputCollected` applies the `OutputCollected` rule before resetting `heldObject`, so the re-armed output is wiped | crystalarium produces once, then sits empty | other `OutputCollected` machines; manual collection unaffected |
| C2 | P3 | push path loses the remainder of a partially stored output / restarts the machine | nearly full chest: some bars vanish | full chest holds, partial push keeps remainder, zero-size still discarded |
| C3 | P1 | stacking by item ID ignores flavour/quality identity | flavoured goods lose their names in the chest | quality split, preserve identity, unrelated stacks unchanged |
| C4 | P4 | cache not invalidated on a storage-option change | chest excluded from Automate keeps being used | — |

C1 is not engineered: Automate's own changelog records the upstream fix ("Fixed
some `Data/Machines` logic not being applied. This caused issues like
crystalariums and worm bins not resuming when their output was collected.").
Building C1 by reverting it would need the same changelog scrub, and it carries
the pretraining-contamination caveat of every upstream revert. An engineered
defect on the same engine boundary is preferred.

## 4. Revised order of work

1. **Measure the leak's effect before building anything new** (§6), including
   the scrubbed v1/v3 composites through the Hub scaffold.
2. Resolve the Z fairness question (§6) by adding a distinguishing observable to
   #241, then screen again.
3. Real-game base/reference controls for the three scrubbed composites, then a
   catalog version bump.
4. Only then build engineered P1–P3 candidates, screened per P5.

## 5. External review

Not run. The ChatGPT upload of the review package (this file, NOTES.md, public
exams, gold patches, private suites, the defect-bearing Automate source, Hub
scaffold code) was refused by the session's permission classifier as data
exfiltration, because it sends private assertions and reference solutions to a
model vendor whose models may be evaluated on this pack. The maintainer then
consented in chat, and navigation to chatgpt.com was refused again: the
classifier yields only to a permission rule in settings, not to chat consent.

## 6. Static screen: leaked vs scrubbed composites (2026-09-18 PT)

Question: does the release-notes leak change which groups an agent repairs?

Method (`scripts/static-screen/`):

- `materialize.py` builds the attempt exactly as the Stardew plugin's
  `materialize_attempt` does (starter tree, public exam with the same path
  rewrites, the same `AGENTS.md`/`CLAUDE.md`). Variant `leaked` restores
  `release-notes.md` from `origin/main`; `scrubbed` is this branch.
- `run_attempt.sh` runs Claude Code headless with `--restricted
  --strict-mcp-config --tools Read,Glob,Grep,Edit,Write`: no shell, no web, file
  tools confined to the attempt directory, user and project settings ignored. A
  probe confirmed that reads of the benchmark repository are refused and that
  none of the operator's global instructions reach the model. The system prompt
  appends the plugin's `agent_system_prompt`.
- Grading is **static**, because no licensed runtime was reachable (§8).
  `grade.py` gives a first pass per scored group; it fails every group on each
  base tree and passes every group on each gold tree. Every run's diff was then
  read by hand, and the manual verdict is final.
- One run per cell. Trajectories and diffs are kept outside Git at
  `~/gcb-static-screen/2026-09-18-stardew-leak/` on the maintainer's Mac.
- The scaffold (restricted Claude Code without a shell) differs from the Hub's
  mini-swe-agent.

Groups: v1 = mini-fridge (F), Junimo seed option (S), API initial scan (A),
zero-size output (Z); v3 = Z, A, location-key pair (L). A task passes only if
every scored group is fixed.

**Fairness question on Z.** Report #241's "just discards a
broken item" also admits a second reading: an item whose data is missing, repaired
by `KeyNotFoundException` handling. The codebase invites that reading:
`ChestContainer` already has `catch (KeyNotFoundException) // invalid/broken item`.
The report never says the stuck output has an empty stack, while the assertion
zeroes the stack. A reviewer can argue that the report underdetermines the defect
and that such fixes answer the report as written. Proposed repair: add one
player-visible observable to #241 that distinguishes the two readings (for example,
that the ready machine's output shows no quantity, or that the stuck item is an
ordinary vanilla item), then screen again. Z should become harder to miss for the
right reason, not easier to guess.

## 7. Two added debugging tasks (catalog 1.1.0, 2026-09-18 PT)

Requirement from the team: every game needs ten debugging tasks; this pack had
eight. Both new tasks start from upstream Automate 2.6.1 (verified byte-identical
to the `automate/2.6.1` tag, changelog included) with one engineered defect, so no
changelog, commit, or pretraining source names the fix. Suites use only the
chest-and-furnace primitives that existing suites already exercised in game.

| task | defect | reports → assertions | base / reference (expected) |
|---|---|---|---|
| `stardew-automate-output-count-drift` | `ChestContainer.Store` reads `Item.addToStack`'s return (the leftover) as the amount added | #262 duplication on top-up; #263 full chest never takes a bar that fits; #265 bar lost when the stack is maxed | 3/6 / 6/6 |
| `stardew-automate-setup-extension` | `MachineGroupBuilder.Add(IContainer)` keeps container tiles out of the group footprint (flood fill still follows them) | #273 furnace on the far side of a chest ignored; #276 new chest beside a chest ignored | 3/5 / 5/5 |

Base/reference counts are what the suites were designed to produce and what I
traced by hand through Automate's code on both trees. They were not measured when
this section was written (§8). **Measured on 2026-09-23 UTC** through `rhenium run`
on catalog 1.2.0 images: output-count-drift 3/6 starter and 6/6 reference,
setup-extension 3/5 and 5/5, exactly as traced.

Catalog difficulty labels: output-count-drift `easy`, setup-extension `medium`.

Pending before release: real-game base/reference controls for both tasks and for
the three scrubbed composites (the Lab Linux host that ran the 2026-09-17 controls
can do this through `rhenium run`), then a note of the measured counts here.

## 8. Blocked infrastructure (2026-09-18)

- hyper00 and hyper01 reject the operator's SSH key (`publickey` offered and
  refused), so the prepared Stardew images and game files there are unreachable.
- moss is reachable but has no licensed game files; acquiring them needs the
  maintainer's interactive `rhenium auth login steam`.
- No real-game control has been run for any change on this branch.
