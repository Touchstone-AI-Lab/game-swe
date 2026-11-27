# Pack Choice Commit v2

Repair the supplied multi-file mod. Target difficulty: **Hard, unmeasured**. Preserve the public centers and API. This is an authored repair, not a claimed upstream historical bug.

The ordinary `p_pc2_choices` Booster costs $4 and presents three physical Common Jokers, in order: `j_pc2_copper`, `j_pc2_silver`, `j_pc2_gold`. Choose at most two through normal game actions. Their signing rewards are respectively $3, $5 and $7. They have no recurring scoring or money effect; their ordinary cost is $4 and native resale rules apply. Capacity is sufficient throughout the supported task.

Opening, creating, displaying or destroying an unchosen preview gives no reward. Each actual selected-and-acquired physical object commits its own reward exactly once. Pay that reward in a normally scheduled deferred game event; after the action has settled, no unpaid work remains. If the player selects one and skips the rest, retain the selected reward and grant nothing for unselected items. Skipping all grants zero. Choosing two grants the sum of those two objects' rewards, regardless of shifted preview positions.

Each opened pack has a separate session and new preview identities. The next pack cannot inherit a prior choice or paid marker. Closing a session prevents new commits but does not cancel already committed pending rewards. Repeated normal operations remain usable. Later play does not pay again; sale gives only native resale income, neither refunding nor revoking the signing reward.

Use `PC2_MODEL` for the preview/commit/pending/settled ledger and `PC2_STATUS()` as a pure detached view of the live ledger, as specified in `API.md`. The real adapter must route preview creation, acquisition, closure and delayed payout through this ledger. Do not use a separate display-only ledger. Private protocol tests call fresh isolated core states; their duplicate/conflict/invalid sequences are not claimed as native player actions.

Scope excludes capacity shortages, extra choices, altered pack size, copy/retrigger, debuffs, editions, save/load, crashes during payout, arbitrary external producers and concurrency between open packs. A complete native action response still requires bounded observation until deferred work and controller readiness settle. Do not manually execute callbacks, change fixed components, overwrite money after observing expected values, or suppress native business behavior.
