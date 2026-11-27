# E0 notes: stardew-valley/core/stardew-cp-i18n-case

Private study material. It names the defect and the reference; never copy it into an attempt workspace.

## Sets

- Target (2 cases): `a translation reading "True" keeps its capital T`, `a translation reading "FALSE" keeps its upper case`.
- Preserved (1 case): `sentinel: the pack's patches apply and ordinary text is unchanged` (literal entry `constant`,
  ordinary translation `Howdy`). It passes in the unchanged starter. Publicly stated in the exam (Problem: "`"True
  enough"` comes through untouched, and so does every normal sentence") and discoverable in the supplied docs
  (`ContentPatcher/docs/author-guide/translations.md:17-18`).
- Static: `check:submission-shape`.

## Controls (all patches apply with `patch -p1` in `/app/StardewMods`)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| `target-negative-dotnet-bool-strings-only` | target-negative | reference | The provider keeps the case only for the .NET spellings `"True"`/`"False"`; every other translation goes back through the case-insensitive `InvariantSets.FromValue`. A fix narrowed to the first reported example. | `"True"` P, `"FALSE"` F, sentinel P | static P, sentinel P, `True` P, `FALSE` F. Admissible. |
| `compat-negative-lowercases-ordinary-text` | compat-negative | reference | Boolean-like text (`bool.TryParse`) keeps its case; every other translation is lowercased before interning, so `Howdy` becomes `howdy`. | sentinel F, both target P | static P, sentinel F, target P P. Admissible. |
| `alternative-bypass-interning` | alternative | starter | A single call-site change: `TranslationValueProvider.GetValues` wraps the exact translation text in a fresh `InvariantSet` instead of calling `InvariantSets.FromValue`. No new case-sensitive interning API in `InvariantSets`, and none of the reference's unrelated changes (gender-switch handling, token application through `Get(key, tokens)`). | all P | all P. Admissible. |

The unchanged starter is the first target-negative (both target F, sentinel P). The declared target-negative fails a
different subset (only the `FALSE` case), which shows the two target cases discriminate separately.

## Assertion-strength findings

- `Task-1` (exact text "including for translations whose entire text happens to match words Content Patcher treats
  specially elsewhere") is **weak**: only `True` and `FALSE` are probed. The starter also rewrites `Spring`, `Summer`,
  `Fall`, `Winter` and whitespace-padded booleans; a boolean-only fix passes 3/3.
- `Task-preserve-token-features` (defaults, placeholders, tokens inside translations) is **unasserted**: the probe pack
  uses none of them. Recommend excluding the clause. Consequence: this task's preserved set is one ordinary string, and a
  compat-negative had to be built on that string (it is contrived for that reason: there is no smaller realistic
  regression that the suite can see).
- The reference changes gender-switch and token-application behavior in the same file (upstream commit scope), i.e. it
  touches exactly the area the exam says must not change, unobserved by the suite. The alternative is closer to the
  public contract than the reference in that respect.
- No over-constraining assertion found.

## Harness note

All cases are synchronous; there is no wait predicate. The prepared evaluator image still contains the pre-fix runner.

## Not run

Each control was run once. The three cases read one asset in one boot, so there is no timing dependence to repeat for.

Starter, reference and the three declared controls were executed with the full profile in the real game container
(records under `e0/records/stardew-valley/core/stardew-cp-i18n-case/`); `rhenium-study e0 run` reported an empty `problems` list for all five.
