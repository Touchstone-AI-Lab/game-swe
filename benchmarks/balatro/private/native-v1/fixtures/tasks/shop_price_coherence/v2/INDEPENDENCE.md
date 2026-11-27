# H2 upgrade rationale

v1 repaired one Boolean discount across existing/future stock. v2 requires multiple independently owned rule sources, an exact combined integer formula, pure versioned quotation, atomic/replay-safe transaction receipts and one-time allowances committed consistently with the native acquire-before-debit order. A single filter or API substitution cannot implement the full protocol and adapter obligations.

This differs from durable-charge (scoring/save persistence), bounded-generator (consumable capacity reservations), and pack commitment (preview selection). Native capacity here is only a transaction rejection precondition, not a generated-product lifecycle. Core exception/alias sequences are stated as protocol tests, not falsely claimed engine events. Hard is an authored design target, not a measured model difficulty.

Two planned correct implementations maintain the same public API with different state strategies: a mutable source/receipt map with defensive copies, and a replayed event ledger with detached projections. Source counts, module count and patch length are not grading criteria. New v2 assets preserve the complete v1 task and its evidence.
