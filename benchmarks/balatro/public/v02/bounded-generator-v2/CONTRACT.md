# Configured Bounded Generator — public contract v2

Authored difficulty: medium. Calibration: unmeasured. Repair the ordinary single-use Tarot `c_bg2_generator`, mod `bounded_generator_v2`, prefix `bg2`.

## Behavior

Each physical Generator carries its own integer quantity `card.ability.extra.products`, in the inclusive range 1–3. The center default is 2. A supplied starting scene may configure individual instances differently; retain those values and never mutate the shared center default or another instance's configuration.

The player's normal Use in settled SELECTING_HAND creates exactly that instance's quantity of distinct ordinary Mercury Planets (`c_mercury`) in the consumable inventory. No playing-card selection is needed. The source is consumed once by the native lifecycle; the engine removes it from its inventory before calling the effect. Products remain normal usable Planets: using one consumes that particular object and raises Pair's level normally.

Admission is all or nothing. For current inventory size N including the source, ordinary capacity L, outstanding native reservation count B (`G.GAME.consumeable_buffer`), and this instance's quantity q, allow Use exactly when `N - 1 + B + q <= L`, subject to ordinary engine state/readiness rules. Consumption of the source releases its own slot. Capacity is checked before any use-side mutation. Can-use and display queries are pure: do not reserve, consume or create anything.

On insufficient capacity, refuse before consuming the source, adding products, recording successful use or changing reservations. Preserve all original physical objects and their properties, the quantity and the right to use that source later. After the player legitimately frees space, the same source can be used once if the formula permits.

On acceptance, read this instance's quantity for this job, reserve its promised slots with the native counter and queue generation through the real event manager. Release only this job's reservations as its products are added/completed. At completion the exact promised objects exist once, the original has finished normal removal and no reservation or unfinished job belonging to this use remains. Do not reserve or release a fixed default unrelated to the accepted job. Subsequent normal uses, including differently configured Generators, obey the same rules.

Keep unrelated consumables, identities and ordinary properties unchanged. Do not alter capacity, dollars, poker-hand levels or other game state except for the specified native consumption/usage and generated products. Later use of unrelated items keeps its normal behavior.

## Execution scope and interfaces

The fixed Windows/SMODS/Bot environment uses visible serial play, gamespeed=1, FAST=0 and HEADLESS=0. Initial scenes have zero outstanding reservations. Actions are separated by bounded observation of real event completion and controller readiness; an RPC reply alone does not imply deferred generation has completed.

Ordinary forbidden use has a verified JSON-RPC error code -32003 with `data.name=NOT_ALLOWED`. Only a correctly bound structured refusal in a case requiring refusal is acceptable. Rejecting a permitted use violates the contract. Arbitrary errors, timeout and unfinished work are not successful refusals; never retry an unconfirmed action.

No copy/retrigger, debuff, edition, special capacity modifier, competing producer, pack/shop use, source-retention mechanism or save/load behavior is in scope. All valid quantities and initial ordinary capacities permitted by the rule are in scope; internal storage/implementation is otherwise free. No target fields are injected during acceptance.

The editable files are `main.lua` and `lib/generation.lua`; `bounded_generator_v2.json` is immutable. The starter separates SMODS registration from admission and deferred-job behavior. These files need not retain their internal function structure. Do not alter evaluator/runtime/fixtures, fixed dependencies, original installation, personal data or external files. Public materials exclude reference solutions, private scenarios, exact scores, traces and saves.
