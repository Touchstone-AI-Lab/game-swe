# E0 notes: balatro/core/shop-price-coherence-v2

Private maintenance material. Never copy into an attempt or a model workspace.

Anchor numbering: a paragraph number counts body paragraphs of the public file in order, skipping headings, list items and table rows; bullets count list items in order, and table rows count body rows below the header.

## Baseline

From the validation matrix's recorded engine results: the starter fails 18 of 80 cases (all `target`),
the reference and gold-ledger fail none. The starter has three defects: it rounds after each Ratio,
`remove` clears every owner, and `view` returns writable owner rows.

## Manifest controls

Controls differ from the reference by one defect.

| control | kind | change | outcome |
| --- | --- | --- | --- |
| M01-round-each | target-negative | Rounds after each Ratio. | Fails 4 target cases only. |
| M02-remove-all | target-negative | `remove` clears every owner. | Fails 11 target cases only. |
| M04-stale-accepted | compat-negative | Version check removed from `commit`. | Fails `core.stale`; every target case passes. |
| M06-view-alias | target-negative | `view` returns owner rows without copying. | Fails 3 target cases only. |
| M07-no-dedup | compat-negative | Transaction and offer guards removed from `commit`. | Fails `core.dedup`, `core.receipt_alias`; every target case passes. |
| gold-ledger | alternative | Validated event log with state rebuilt by replay, against the reference's mutable owner map. | Fails no case. |

M04 and M07 are valid compatibility negatives because the unchanged starter already has both guards
(`lib/ledger.lua:49-55`), so removing them breaks existing behavior while all three repairs hold.

## Preserved contracts

The `commit` pipeline in API.md bullets 1 to 7 and the table rows, Coupon consumption and category rules
(CONTRACT.md paragraphs 2, 3 and 5), native refusal atomicity (paragraph 7), and purchase, sale and later
play integrity (paragraphs 6, 8 and 9). The starter's formula also agrees with the contract for many
inputs, which is why several native purchases pass on it.

## Frozen controls left out of the manifest

Each fails both target and preserved cases, so it fits neither negative kind. They are the source of the
generated `overlap` flags.

- M03-query-consumes: `quote` spends every Coupon; fails 8 target and 14 preserved cases.
- M05-never-consume: a purchase never spends a Coupon; fails 14 target and 5 preserved cases.
- M08-wrong-category: category guard removed from pricing; fails 6 target and 18 preserved cases.

## Role and overlap changes

Three cases changed from `preserved` to `runtime-sentinel`: `normal.coupon.buy.quotes`,
`normal.post_remove.buy.quotes`, `normal.third.buy.quotes`. Each compares two empty lists on a sold-out
shop, so it only shows the snapshot settled. No control fails them and none is failed by a compat-negative
control.

Overlap flags are as generated.

## Coverage limits

- Unasserted: `native-price-other-goods`, `file-boundary`, `no-external-alteration`,
  `api-adapter-own-state`, `api-preserve-callbacks`.
- Weak: `reroll-fee-native`, `native-sale-value`, `core-api-integrated`, `api-core-isolated`,
  `api-quote-shape`, `api-commit-order`.
- The funds scene recovers with a different offer than the refused one; only the capacity scene retries
  the same offer.

CONTRACT.md paragraphs 1 and 9 otherwise identify the task and its scope, and API.md paragraphs 3 and 7
describe calling convention and evidence layers; these are not mapped as obligations.

## Not determined

Nothing open for the roles or clause statuses.
