# M4 v2 — sources and independence

Upgrade of authored isolated-card-wear-v1. v1 allowed fresh application only to ordinary cards; v2 adds reset of a still-worn enhancement and of a previously exhausted object, same-hand independent wear, and last rewards after these lifecycle transitions. The repair relates state ownership, replacement/reset and reward ordering; it is not another growth constant or persistence ledger task.

`validation-wear-prerequisite-v2-dev1.json` establishes the complete four-round native pathway: actual application to worn/depleted cards, cross-blind preservation, native discard, simultaneous scoring and final exhaustion. Fixed `Card:set_ability` / SMODS ability patches provide the source basis for replacement. The task uses no save/load or artificial callback execution and retains all v1 bytes.

The observer reads the public pure localization semantic count and physical identity/attributes, then actual score and native lifecycle. It does not prescribe an internal wear table. The fixture constructs initial objects only; every subsequent use, play, discard and blind change is real. A simple independent Python state model predicts remaining uses by physical ID from those declared actions. Designed medium, unmeasured by models.
