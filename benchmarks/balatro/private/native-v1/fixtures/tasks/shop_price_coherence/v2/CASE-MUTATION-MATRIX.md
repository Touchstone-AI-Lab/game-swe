# H2 private rule / scenario / expectation / defect matrix — design v1

Frozen before any pricing candidate is authored. Capability prerequisite: validation-price-prerequisite-v2-dev2.json, 26/26, three fresh processes. Core protocol checks are separate from native engine cases. Exact scene vectors and oracle are private assets.

| Public obligation | Planned scenario | Expected observation | Distinguishing defect |
|---|---|---|---|
| Fixed reductions then rational product, one floor | Core cartesian base/rule combinations; native Flat + two Ratios, $8 offer after allowance consumption | Independent integer oracle; real quote/debit agree | Early intermediate rounding |
| Physical source ownership | Add multiple source kinds, sell one Ratio, later acquire/remove another source | Only sold contribution disappears | Remove clears unrelated rules |
| Pure quote and original base | Repeat core quotes/views; native stable polling and repricing after unrelated acquisition/reroll | No version/allowance change, no compounded quote | Reuse discounted base / query consumes quota |
| One-time coupon transaction | Real Coupon purchase, eligible purchase, later second eligible purchase; core duplicate commit | First transaction uses allowance, next does not; exact replay unchanged | Never consume / repeated consumption |
| Category boundaries | Non-rule Jokers, rule Jokers and ordinary Planet; reroll | Only eligible Joker discounted; other purchases retain allowance | Coupon consumed by noneligible purchase |
| Stale quote/version | Core quote then source add/remove/consume; real changed offers and later shop | Reject stale core quote atomically; real current offer updates | Stale cache/version acceptance |
| Failed purchase has no side effects | Native funds and full-capacity refusal followed by real sale and success; core insufficient funds then legal commit | Same offer/source/allowance remains and later use succeeds | Failed purchase consumes quota/receipt |
| Detached state and request/receipt data | Mutate returned view, quote and receipt; mutate committed input; query/replay afterwards | Ledger and original receipt unaffected | Shallow aliases |
| Idempotent identity and conflict | Duplicate identical commit, conflicting transaction ID, second transaction for same offer | Original receipt / CONFLICT / OFFER_COMMITTED; no new consumption | Missing transaction or offer deduplication |
| Native transaction integrity | Actual debit and owned identity; remaining offers; real sale and later play | Full original RPC completion, normal sale credit, continued gameplay | Reprice purchased card before native debit |

Controls planned before implementation: loadable base combining early rounding, unrelated-rule removal and returned-view alias errors; two correct implementations (owned map with detached receipts; independent event-ledger replay model). Targeted controls cover each independent invariant family, with combined assertions where one control distinguishes related subcases. Hard control count is intentionally not fixed at 2–4: the relevant invariant families above determine the necessary small set. Every control runs the same complete suite; no role/path/source-layout checks decide business outcome.

No timeout or native response failure is a valid negative control. In-flight repricing is an integration risk to detect during development; do not ship a crashing/hanging mutation for that row. If a control cannot finish the native suite, retain incomplete and revise the control before freezing, with the original development evidence retained. Contracts and expectations cannot be changed merely to make a candidate pass.
