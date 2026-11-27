# Reversible hand limit — private pre-implementation matrix v1

Status: frozen before candidates after probe v1 passed 9/9.

| Rule | Planned real scene | Expected behavior | Intended defect |
|---|---|---|---|
| Own contribution acquired/removed once | Buy one target, later sell, enter next blind/refill | +2 while held, own +2 removed, real draw follows current limit | double-add; no-remove |
| Preserve prior owners | Native Juggler acquired before target, target sold while Juggler remains | Only target contribution removed, other identity and +1 remain | base resets hard-coded default |
| Preserve later owners | Buy target then Juggler, remove target first | Later +1 survives; sale and refill complete | stale snapshot restoration |
| Independent physical instances | Buy two targets; sell one, play/refill; sell other | Only selected ID removed; remaining instance contributes exactly once | blanket reset/clearing all instances |
| Repeated legal operation | Another originally prepared shop target is bought/sold after first sale | No cumulative drift or stale ownership token | double-add, retained contribution |
| Read-only/normal transition | Observe over frames, real nonwinning hand and later deal | No incidental reapplication; native transaction and draw count advance | life-cycle effect in scoring/update |

Gold: compositional per-instance acquisition/removal. Base: adds correctly but resets limit to ordinary default on removal; a standalone ordinary scenario works.
Three planned mutations: double-add, no-remove, stale snapshot restore. Their complete behavioral rejection must be shown, not inferred from source. Candidate implementation follows this frozen matrix.

Fixture scope: explicit initial preparation may configure a legal initial deck/starting money, then furnish the first shop before any tested purchase. It is a declared two-stage preparation ending at the initial shop seal, not an outcome repair. After seal there are no fixture writes, card deletions, limit assignments, or inventory replenishment. Subsequent operations consume the originally prepared inventory or native draws. The final suite uses one continuous first-shop sequence per fresh process: target alone; target before native owner; target after native owner plus a second target; remove targets in acquisition order; leave shop and draw; sell native owner; play and refill. This exercises all boundaries without post-seal preparation. Three repetitions mean three independent processes, not these substeps.

## Pre-candidate scene refinement (2026-09-19)

The capability probe establishes that a normal sale can preserve another contributor and that the subsequent native draw uses the updated aggregate. Therefore all ownership-order and multi-instance boundaries are composed into one declared starting shop with four target objects and one native Juggler. The shop capacity is set only during initial preparation. No boundary is removed; the prior draft remains alongside this record. The initial target-alone phase verifies that base works in its ordinary success case. Later before/after/multi-owner phases identify compositional failures; final draw/refill validates the resulting aggregate in play. This does not reduce the required three independent gold/base repetitions.
