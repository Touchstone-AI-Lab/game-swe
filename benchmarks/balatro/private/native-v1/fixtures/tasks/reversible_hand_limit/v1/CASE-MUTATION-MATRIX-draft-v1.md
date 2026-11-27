# Reversible hand limit — private pre-implementation matrix v1

Status: specification draft; capability unproven; no candidates written. Probe must precede candidate implementation.

| Rule | Planned real scene | Expected behavior | Intended defect |
|---|---|---|---|
| Own contribution acquired/removed once | Buy one target, later sell, enter next blind/refill | +2 while held, own +2 removed, real draw follows current limit | double-add; no-remove |
| Preserve prior owners | Native Juggler acquired before target, target sold while Juggler remains | Only target contribution removed, other identity and +1 remain | base resets hard-coded default |
| Preserve later owners | Buy target then Juggler, remove target first | Later +1 survives; sale and refill complete | stale snapshot restoration |
| Independent physical instances | Buy two targets; sell one, play/refill; sell other | Only selected ID removed; remaining instance contributes exactly once | blanket reset/clearing all instances |
| Repeated legal operation | Another originally prepared shop target is bought/sold after first sale | No cumulative drift or stale ownership token | double-add, retained contribution |
| Read-only/normal transition | Observe over frames, real nonwinning hand and later deal | No incidental reapplication; native transaction and draw count advance | life-cycle effect in scoring/update |

Gold: compositional per-instance acquisition/removal. Base: adds correctly but resets limit to ordinary default on removal; a standalone ordinary scenario works.
Three planned mutations: double-add, no-remove, stale snapshot restore. Their complete behavioral rejection must be shown, not inferred from source. Candidate code and final scene assertions are written only after the probe passes.

Fixture scope: explicit initial preparation may configure a legal initial deck/starting money, then furnish the first shop before any tested purchase. It is a declared two-stage preparation ending at the initial shop seal, not an outcome repair. After seal there are no fixture writes, card deletions, limit assignments, or inventory replenishment. Subsequent operations consume the originally prepared inventory or native draws. Independent boundary scenes restart a clean process.
