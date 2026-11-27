# E0 notes: balatro/core/deck-removal-consistency-v2

Private maintenance material. Never copy into an attempt or a model workspace.

Anchor numbering: a paragraph number counts body paragraphs of the public file in order, skipping headings, list items and table rows; bullets count list items in order, and table rows count body rows below the header.

## Baseline

From the validation matrix's recorded engine results: the starter fails 15 of 56 cases (all
`target`), the reference fails none. The starter's multi-target path takes a hand prefix and only
removes cards from the hand; its singleton path is correct.

## Manifest controls

| control | kind | change | outcome |
| --- | --- | --- | --- |
| M02-area-only | target-negative | Correct selection; batches are still only removed from the hand. | Fails 12 target cases only. |
| M03-first-two | target-negative | Native destruction, but a batch is truncated to the first two highlighted objects. | Fails 15 target cases only. |
| alternative-public | alternative | Snapshots the selection by identity and destroys each object through its own native call, against the reference's single batch call. | Passed every required case on the real engine. |

The task has no compatibility-specific negative: the manifest lists no `compat-negative`.

## Preserved contracts

All stated in CONTRACT.md and already true in the starter: the singleton path (paragraph 2, "one to
four"), source consumption and unchanged resources (paragraphs 2 and 4), survivor identity
(paragraph 4), continued play (paragraph 5) and refusal of invalid selections (paragraph 6).

## Frozen controls left out of the manifest

- M01-prefix-targets: destroys the hand prefix natively; fails 15 target cases and 3 preserved
  `.unchanged` cases (`four.first.unchanged`, `repeat.first.unchanged`, `repeat.second.unchanged`),
  so it fits neither negative kind. These three are the generated `overlap` cases.

## Role and overlap changes

None. `.sealed` is a genuine sentinel: it only checks the fixture's prepared flag.

## Coverage limits

- `selection-order-irrelevant` is unasserted: all selections are ascending.
- `destroyed-once` is weak: no destruction count is observed.
- `file-boundary` and `no-external-alteration` have no case; they are gated outside the case list.
- Batch size 2 is not exercised.

Paragraphs 1 and 7 identify the task and describe the environment. "Do not resend an unconfirmed
Use" in paragraph 6 is an operator rule. None of these is mapped as a separate obligation.

## Not determined

Nothing open for the roles or clause statuses. The fixed endpoint source was not read; the refusal
known issue relies on the frozen OBSERVATION-ADDENDUM-v1.md.
