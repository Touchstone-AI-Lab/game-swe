# H2 implementation/control design

Supplement to the pre-candidate matrix, without changing its rules. Two correct implementations: gold uses a mutable owner map and copied receipts; gold-ledger stores validated immutable events and rebuilds its state by replay. Their adapters implement the same native acquisition/debit boundary. Same interface, files and tests; no grader branches on control role.

The loadable base combines three related repair obligations: intermediate rational rounding, removal of unrelated owners, and aliased public projections. Ordinary no-rule operations still work. No startup/RPC failure is intended.

Eight targeted single-family controls are justified by eight independent required invariants, not by difficulty count:

| Control | Single defect family | Planned distinguishing checks |
|---|---|---|
| M01-round-each | Intermediate rounding | Core formula matrix and real post-coupon $8 offer with Flat/two Ratios |
| M02-remove-all | Removal clears other owners | Core ownership and native sale followed by quotes/transactions |
| M03-query-consumes | Quote spends Coupon | Pure query/core allowances and real first eligible purchase |
| M04-stale-accepted | Missing version rejection | Core stale quote with otherwise unchanged price; native current quote cases still run |
| M05-never-consume | Successful eligible purchase leaves Coupons | Core versions/next quote and native later purchase |
| M06-view-alias | Returned projection aliases owners | Independent core state alias tests; native suite still runs |
| M07-no-dedup | No transaction/offer receipt guards | Core replay/conflict/offer identity; native suite still runs |
| M08-wrong-category | Discounts noneligible types | Core categories and real Planet/rule-Joker transaction prices |

Core-only error sequences are not described as native gameplay. All controls must complete the entire common suite with expected behavior failures; unexpected timeouts/crashes remain incomplete development evidence. A mutation that cannot finish must be revised with a new recorded control version before qualification, not counted as rejected.
