# Physical Batch Removal — public contract v2

Authored difficulty: medium. Calibration: unmeasured. Repair the ordinary Tarot `c_dr2_clean_cut`, mod `deck_removal_consistency_v2` with prefix `dr2`.

## Public behavior

A normal successful Use in SELECTING_HAND consumes this Tarot once and permanently destroys exactly the **one to four selected physical playing-card objects**. Selection is the highlighted set at that use, not a prefix of the hand, mutable row positions, a matching rank/suit, or only the first two highlighted objects. Each selected object is destroyed once. The order of selections does not change the resulting target set.

Remove each selected object from the active card area, the persistent playing-card registry and the subsequent draw pool. The registered deck count and its ordinary deck-size bookkeeping decrease by the actual number of distinct selected physical objects. Mere visual disappearance or removing an object from the current hand is insufficient. Normal destruction completes through the native lifecycle; do not leave dangling live objects, duplicates, or pending work.

Every unselected physical card keeps its identity, rank, suit and ordinary base-card state. This includes an unselected card with the same rank and suit as a selected card. Do not replace survivors with newly created lookalikes or change their attributes. Other consumables, money, poker-hand levels and normal hand capacity stay unchanged apart from the specified Tarot's native consumption/usage.

After completion, normal play, refill, round completion and entry to a later blind still work. Permanently removed cards never return in later deals. A later independently owned Clean Cut follows the same rule against its own current selection; earlier target lists or destroyed-object references are not reused. Repeated operations keep the registry, areas, counts and remaining draw pool consistent.

An empty selection or selection above the maximum is rejected by the fixed normal interface before effect execution, without consuming the source or changing objects/resources. Only a verified structured business refusal with matching request identity counts as refusal. The fixed Bot's selection validation uses JSON-RPC code -32001 and `data.name=BAD_REQUEST`; ordinary can-use refusal is separately -32003 / NOT_ALLOWED. Arbitrary RPC/HTTP errors, timeouts and missing completion are incomplete, not successful rejection. Do not resend an unconfirmed Use.

## Scope and submission

Use the fixed serial visible native runtime, gamespeed=1, FAST=0 and HEADLESS=0. Scenes start from an independently seeded run. Initial fixture preparation may supply ordinary cards with different ranks/suits and multiple independent sources; it ends before tested actions. Observe actual engine-scheduled completion and readiness, not only the Use response. Native hand order is whatever the real engine presents; this contract does not assume changing rank causes an automatic reorder.

Only ordinary unenhanced, unsealed, uneditioned playing cards and ordinary consumables are required. No copy/retrigger, debuff, retained source, special destruction replacement, save/load or concurrent operations are in scope. Do not alter evaluator/observer/fixture/runtime, fixed components, original installation, personal data or external files.

Editable files: `main.lua` and `lib/lifecycle.lua`; immutable file: `deck_removal_consistency_v2.json`. The starter separates registration from target/lifecycle handling, but internal structure is not graded. Public materials contain the rules, generic submission instructions and starter only, without reference implementation, hidden scenarios, logs, saves or game source.
