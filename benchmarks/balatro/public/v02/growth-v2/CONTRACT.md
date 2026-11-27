# Round End Growth — public behavior for growth-v2

Difficulty: uncalibrated / 待校准. Repair the ordinary Joker registered by mod `round_end_growth`, prefix `poc`, center `j_poc_growth`. Preserve the mod manifest and registration identity. This public view preserves the existing growth contract.

- The Joker's `ability.extra.growth` starts at 0.
- Each successfully completed blind adds exactly 2, once per blind. The number of held cards and the engine's other end-of-round callbacks must not multiply that increment.
- Ordinary hands, discards, cash-out and shop observation do not add growth.
- Each main Joker scoring phase adds the current growth to Mult (additive Mult, not chips or X Mult).
- The hand that wins a blind uses the growth from before that blind ends. Only after the win does the increment become available to later scoring. This continues across consecutive successful blinds; there is no growth cap.
- Display the current growth consistently through the supplied localization interface.

Scope: ordinary seeded play with a single target Joker and ordinary playing cards, without debuffs, copying, editions or retriggers. Normal poker-hand types, different counts of played/held cards and multiple consecutive blinds follow the same rules. No save-restoration behavior is required.

Edit only the supplied candidate Lua file. Do not modify evaluator, fixture, observer, game, dependencies, runtime, environment or external files. Verification uses actual discard/play/blind completion/shop actions and native game results. Initialization can prepare an ordinary starting scene but cannot implement growth or set scores. Missing responses, crashes and incomplete flows cannot pass.

This package intentionally excludes private scenarios, exact scores and reference implementations. Its source is a self-authored controlled defect, not a claim of a historical upstream bug.
