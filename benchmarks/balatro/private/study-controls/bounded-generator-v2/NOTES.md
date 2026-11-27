# E0 notes: balatro/core/bounded-generator-v2

Private maintenance material. Never copy into an attempt or a model workspace.

Anchor numbering: a paragraph number counts body paragraphs of the public file in order, skipping headings, list items and table rows; bullets count list items in order, and table rows count body rows below the header.

## Baseline

From the validation matrix's recorded engine results: the starter fails 8 of 75 cases (all
`target`), the reference fails none. The starter has two linked defects: admission uses
`math.max(2,q)` and the job releases a fixed 2.

## Manifest controls

| control | kind | change | outcome |
| --- | --- | --- | --- |
| M01-min-two-admission | target-negative | Release fixed per product; admission keeps the minimum of two. | Fails 4 `one.generate0.*` target cases only. |
| M02-fixed-release | target-negative | Admission fixed; release stays a fixed 2. | Fails 5 `.lifecycle` target cases only. |
| M03-truncate-products | compat-negative | Admission and release fixed; product loop stops at 2 while the full reservation is released. | Fails 3 preserved `.inventory` cases; every target case passes. |
| alternative-public | alternative | One queued event per promised product, each releasing one slot, against the reference's single event. | Passed every required case on the real engine. |

M03 is a valid compatibility negative because the unchanged starter already creates q products
(`lib/generation.lua:12-14`), so losing the third product breaks existing behavior while both
requested repairs hold.

## Preserved contracts

All stated in CONTRACT.md and already true in the starter: creation of exactly q products
(paragraph 3), default-quantity use (paragraphs 2 and 3), refusal atomicity and later retry
(paragraph 5), unrelated objects and state unchanged (paragraph 7), usable products and normal
Hermit use (paragraphs 3 and 7).

## Frozen controls left out of the manifest

None. Every frozen control other than base and gold is listed.

## Role and overlap changes

- No role changed.
- `recover.refusal.response` set to `overlap: true`. It stays `preserved` because it passes on the
  starter, but it is the only case that grades the refuse branch of the admission expression the
  requested change rewrites: an over-correction that admits one slot too many passes every target
  case and fails here.
- `.sealed` keeps its generated `runtime-sentinel` role although it also carries the only evidence
  for `config-immutable`.

## Coverage limits

- `admission-reservation-term` is unasserted: B is 0 at every Use.
- `display-query-pure` and `queued-event` are weak; see their clause notes.
- `file-boundary` and `no-external-alteration` have no case; they are gated outside the case list.
- Refusal is exercised only for q=3.

Paragraphs 8 and 10 otherwise describe the environment and scope, and paragraph 1 identifies the
task; they are not mapped as separate obligations.

## Not determined

No engine source or event trace was read, so it is unknown whether the native use path alone
produces a finished tracked event with delay>0. If it does, a synchronous generator could satisfy
the `deferred` field and only `reserved` constrains it; if it does not, a zero-delay queued job
would fail that field. No role change depends on this.
