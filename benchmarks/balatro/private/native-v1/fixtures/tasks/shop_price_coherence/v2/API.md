# Cooperative Checkout — public API version 2

`main.lua` must make `SPC2_MODEL` available, a table of functions below. The four editable sources are `main.lua`, `adapter.lua`, `lib/pricing.lua`, and `lib/ledger.lua`; their internal division is unrestricted. SMODS provides `SMODS.load_file(relative_path, mod_id)` returning a chunk; during the mod's initial loading the mod ID may be omitted. The immutable manifest selects `main.lua`. No external modules are required.

The core functions must operate on independent, opaque states without using engine globals, changing their inputs, or touching a real game. The adapter uses its own current-run state; calling `new()` for protocol tests must not reset that live state. All normal and rejected calls return values; malformed requests listed here are not exceptions. A valid state returned by `new()` is always supplied. Integers are finite exact integers; prices/available money are at most 1,000,000; IDs are nonempty strings at most 64 characters. There are at most eight active sources in scope. Order of source acquisition must not change the price.

Functions use dot calls, e.g. `SPC2_MODEL.add(state, 'owner-1', 'flat')`:

| Function | Result and semantics |
|---|---|
| `new()` | Independent state, version 0, no sources or receipts. |
| `view(state)` | Detached `{version=N, sources={...}}`. Sources sorted lexicographically by ID, each exactly `{id=string, kind='flat'/'ratio'/'coupon', available=boolean}`. Flat/Ratio availability is true; Coupon is true until consumed. |
| `add(state, owner_id, kind)` | Add one new source, Coupon initially available. Return `{ok=true,version=N}`. Increment version once. Existing ID: `OWNER_EXISTS`. Invalid ID/kind: `INVALID`. |
| `remove(state, owner_id)` | Remove only that owner and increment version once; return `{ok=true,version=N}`. Missing ID: `OWNER_MISSING`; invalid ID: `INVALID`. |
| `quote(state, offer_id, base, category)` | Pure query returning `{ok=true,quote=Q}`. Positive integer base. Category is `eligible_joker` or `other`; `other` price equals base and uses no rules. Invalid inputs: `INVALID`. |
| `commit(state, transaction_id, Q, available_money)` | Validate and record one successful modeled purchase; return detached `{ok=true,debit=Q.price,version=N}`. This function **does not debit engine money**. Its modeled resources are only owned rules, Coupon availability and receipts. |

Q has exactly six fields: `{offer_id, base, category, price, version, protocol=2}`. All returned views, quotes and receipts are detached: changing a returned table cannot change current state, future quotes or stored transaction identities. Input tables must not be retained as writable aliases. No snapshot/restore interface is required in this version.

All rejection results are exactly `{ok=false,code=CODE}` and leave every observable state, allowance and receipt unchanged. This includes failed requests that reuse an ID later for a legal request. `commit` validates in this order:

1. Valid transaction ID, nonnegative integer available money, and Q's exact shape/types/domains (including protocol 2 and nonnegative integer version); otherwise `INVALID`.
2. If this transaction ID has already succeeded, an exact replay of Q and available money returns its original success receipt without applying effects again, even if rules since changed. A different request for that ID returns `TRANSACTION_CONFLICT`.
3. A different transaction ID for an already committed physical offer ID returns `OFFER_COMMITTED`.
4. Q.version must match the current version, else `STALE_QUOTE`.
5. Q.price must equal a fresh computation from Q.base/category and current rules, else `QUOTE_MISMATCH`.
6. Available money must cover the quote, else `INSUFFICIENT_FUNDS`.
7. Record the successful transaction and physical offer. For an eligible purchase, consume all currently available Coupons. If any Coupon is consumed, increment version **once for that transaction**, not once per Coupon. Otherwise version does not change. Store an immutable receipt and request for replay comparison.

The adapter assigns source identity by physical owned object, not current row index; it records and consumes only real completed qualifying acquisitions. Native funds/capacity rejection occurs before acquisition and must not call a successful commit. Noneligible engine purchases need not be recorded in the core, but cannot spend allowances. Price calculation must start from the unmodified native price calculation; updating offers after commitment must not change the already acquired object's current debit. Preserve native callback call counts, arguments, all returns and error behavior when wrapping them.

The operator tests protocol invariants on independent core states and separately drives real native buy/sell/reroll/shop actions. These are complementary obligations. Passing core calls alone is not engine validation; visible descriptions alone are not evidence of correct transaction money or allowance consumption.
