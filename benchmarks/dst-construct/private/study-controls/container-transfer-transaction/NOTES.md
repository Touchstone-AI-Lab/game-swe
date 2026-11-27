# E0 notes: dst/core/container-transfer-transaction

Construction task from an empty starter (`task_version` 2.0.1). Sixteen evaluator
cases: 3 static gates, 6 hidden plain-Lua cases, 4 source-pattern checks and 3
dedicated-server cases.

## Preserved contracts

None. The starter workspace has no mod, every case fails (or is unobserved) in
`starter.execution.json`, and the exam states no behaviour that already holds.
No case is `preserved`, therefore there is no `compat-negative`; the task enters
general completion only.

## Controls

| control | kind | what it changes |
| --- | --- | --- |
| `target-negative-compensation-order` | target-negative | Reference plus a patch to `scripts/containertransfer/transaction.lua`: `_compensate` restores the source snapshot before the destination snapshot. Breaks exactly core-5a / accept-2; expected to fail only `hidden:add failure restores destination before source`. |
| `target-negative-destination-loss` | target-negative | Reference plus a patch to the component's adapter `add`: the stacks taken from the source are destroyed instead of being given to the destination container, while the transaction still reports `committed`. Breaks dst-3a (item conservation with real containers); the pure core is untouched, so only `server:real container stacks transfer without loss` should fail. |
| `alternative-a` | alternative | Full mod tree written from the public exam. Structural differences from the reference: the core is closure-based with private state (no metatable class); requests live in an ordered journal whose entries carry a phase history and an undo stack (pushed before each destructive call, popped top-down, which yields destination-then-source compensation) instead of a `phase` + `pending_restore` flag record; status names are `refused`/`aborted`; the rows given to `add` are the core's own slot-ordered selection rather than the value returned by `remove`. The engine adapter is a separate module (`scripts/containertransfer/chest_adapter.lua`) and is descriptor-based: `remove` describes and destroys what it takes, `add` spawns base-game items from descriptions, `restore` resizes stacks in place where possible; the reference instead carries live entities from source to destination. Capacity uses a short-lived probe prefab for the stack limit. The action is a two-step mark-source / choose-destination interaction. |
| `alternative-strict-reading` | alternative | `alternative-a` with one change in the core: the rows handed to `adapter:add` contain `prefab`, `count` and the metadata percentages but no source `slot`. Selection is still by ascending slot. Valid under the public exam, which never defines the row shape for `add`; rejected by `hidden/container-transfer-transaction.lua:73`, which reads `.slot` from what the fake adapter stored. It is kept to document the over-constraint and is expected to show problems. |

## Findings about the private suites

- Over-constraint (minor): slot order is observed through the `slot` field of the
  rows passed to `add` (hidden line 73 together with the verbatim store at line 52).
  See `alternative-strict-reading`. Recommendation: keep the task, note the
  assumption; a clarification of the `items` shape in the exam would be a
  benchmark-authoring change.
- Under-measurement: the pure `recover()` and `status()` are never called; no case
  saves or reloads a non-final phase; the fake adapter's `restore_fail` option
  (hidden line 57) is unused. Clauses core-4a, core-5b, dst-3b and
  api-1 are unasserted and listed in `excluded_clauses`; core-6 and
  accept-3 are weak (component `Recover()` is called once with nothing to recover).
- The exam's accept-5 promises server checks for capacity failure, compensation and
  event cleanup; the server suite has none of them.
- The server suite calls `service:OnSave()` with a receiver, so the receiver-less
  `OnSave` problem of the ledger and rescue tasks does not apply here.

## Not run / limits

- Engine evidence is the managed container runtime on this Linux x86_64 host only.
- The action, component action, stategraph handlers and RPC handler of the
  alternatives are loaded by the dedicated server but never invoked by any case;
  they are unexercised in both the reference and the alternatives.

## Catalog 2.1.0 update

The sections above describe catalog 2.0.1 (study snapshot 5929c99). The exam now states that the rows returned by `adapter:remove`, including the source slot, are passed to `adapter:add` unchanged in ascending slot order. The former `alternative-strict-reading` drops the slot and so violates a published rule; it is kept as `target-negative-drops-slot`. The acceptance bullet about the server suite (accept-5) was rewritten to what the suite checks, so the remark about it above no longer applies. Re-run on 2026-09-22: reference 100, alternative-a 100, the three negatives each fail exactly one case (compensation order, server item conservation, deterministic source slots).
