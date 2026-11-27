# M1 v2 private rule / scene / expectation / defect matrix

Frozen before candidate authoring. Native capability prerequisite: validation-bounded-prerequisite-v2-dev1.json, 19/19 across four fresh processes. The v1 fixed-two task remains unchanged.

| Rule | Scene | Expected observation | Discriminator |
|---|---|---|---|
| Default quantity and ordinary behavior | Room: capacity 5, two quantity-2 sources and Hermit | Both uses succeed, four new Mercury identities, each source removed once; actually use two products and Hermit | All controls must preserve ordinary behavior |
| Configured admission with self slot | One: capacity 2, quantity 1 and Hermit, initially full | Source succeeds, one Mercury replaces it; Hermit subsequently works | base / M01 incorrectly require at least two product slots |
| Quantity and reservation ownership | Three: capacity 4, quantity 3 and Hermit | Exactly three products; effect returns with reservation 3, completion buffer 0; real Mercury use | base / M02 release default 2; M03 truncates production above 2 |
| Refusal and retained entitlement | Recover: capacity 3, quantity 3 and Hermit | First Use structured NOT_ALLOWED, all unchanged; real Hermit use then one newly legal Use of same source; product usable | No blanket exception acceptance; refuse/consume/usage/identity checked |
| Independent configuration and serial jobs | Mixed: capacity 5, quantities 1 and 3 plus Hermit | Two uses with distinct physical sources; reserve/release each accepted quantity independently; use a generated Mercury | Fixed release and output truncation; shared/default configuration mutation |
| Deferred completion and no duplicate | All successful jobs | One actual use-side callback, source leaves before it, scheduled delayed event finishes, exact products/identities, pending=0 | Wrong lifecycle, duplicate product/job, incomplete work |
| Pure admission and unaffected state | Pre-use repeated gamestate reads and all transitions | Buffer, usage, inventory, money and levels remain unchanged by queries; capacity constant | Query side effects; observation does not invoke callbacks |

Five independent scene processes per whole suite. Sources/quantities/capacities are written only in the one declared initial preparation; observers never generate products or clear buffer. Readiness deliberately does not require buffer=0 because the buffer itself is graded.

The One scene's later action uses its preexisting Hermit, so an incorrect legal-use refusal can still be fully observed without inventing a generated object. The Recover scene retains the source under all predeclared controls; the starter's admission bug is a minimum quantity of two, not an over-permissive three-product admission. An arbitrary candidate that destroys a prerequisite may be behaviorally wrong and still incomplete for later required actions; do not claim complete execution or rescue it.

Controls planned before implementation: gold; base combines minimum-two admission and fixed-two reservation release; M01 only minimum-two admission; M02 only fixed-two release; M03 only truncation of product creation to two while releasing the full accepted reservation. Three distinct defect surfaces suffice; no equivalent variants or hypothetical competing reservations are added.
