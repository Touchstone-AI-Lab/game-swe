# M2 v2 private rule / scene / expectation / defect matrix

Before candidate authoring. Native capability validation-deck-prerequisite-v2-dev1.json passed 13/13: four nonadjacent objects with mixed rank/suit, duplicate-face survivor, empty-selection structured refusal, global/area membership, native refill and a later blind/draw pool. Historical v1 already had one/two nonadjacent targets; v2 is not claiming that capability as new.

| Rule | Fixed scene | Expected | Defects distinguished |
|---|---|---|---|
| Ordinary singleton works | Single source, select initial index 0 | One object permanently removed, bookkeeping and subsequent native play/deal/pool correct | All controls must preserve this normal scene |
| Exact physical batch | Four targets at initial indices 0,2,5,7 | All four selected identities gone; selected D3 removed while another D3 survives | Prefix-target base/M01; maximum-two M03 |
| Persistent destruction | Same four-target scene | Registered list, ordinary deck limit and union of active areas all equal original minus targets | Batch area-only base/M02; visual disappearance is insufficient |
| Input refusal atomicity | Empty selection before first use in each scene | Exact structured BAD_REQUEST, unchanged source, inventory, cards/counts, money/levels; later valid action works | No arbitrary exception acceptance |
| Repeated fresh selection | Two sources; first selection 1,4,7; win, next blind; second selection index 3 | First three stay gone; second current physical object removed once; distinct source consumed each time | Reusing cached batch/state or incomplete prior removal |
| Survivor properties | Mixed ordinary H2/D3/S4/C5 including two D3 instances | Exact retained IDs/rank/suit/base center unchanged | Face-based removal/replacement or unintended mutation |
| Refill and later draw pool | Actual single-card play/refill, five H2 round win, next blind, fixed discard sequence | No removed identity returns; all surviving IDs become reachable and deck empties as specified | Registry/area divergence, delayed duplicate removal |

Three fresh processes per whole suite: singleton, four, repeat-three-then-one. Fixture has two declared initial phases (deck and first dealt hand), then seals permanently. No acceptance-time card removal, deck repair, capacity change or target-state injection. The repeated scene's next selection is the public action's current index 3; expectations derive its physical identity before that action, not an assumed historical row number. Correctness of the earlier batch remains separately required.

Native continuation always uses declared action rules. It does not branch on a failed assertion or rescue missing source objects. A missing prerequisite or unobservable action is incomplete. Drawing fewer than the normal hand size when the real deck is exhausted is ordinary native behavior, not a relaxed condition.

Planned controls: gold; base's multi-target path selects the hand prefix and only removes cards from the current area, while its singleton path remains correct; M01 only wrong batch target selection; M02 only current-area removal for batches; M03 truncates a batch to the first two selected objects. These are distinct target-set, lifecycle and cardinality defects. No syntactic/startup failure or equivalent variants count.
