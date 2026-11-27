# Validation candidates

These unified patches are evidence fixtures, not required solution shapes. Each
patch applies to `environment/mutant-tanks` and exactly reconstructs the tree
frozen in `manifest.tsv`. The nine `predicate-*` candidates repair one reported
behavior group each. The two `alternative-*` candidates repair all nine groups
with implementation strategies that differ from the oracle.

All candidates use the same 57-case contract. The external
`reward_stacking` group expands into independent A-then-B and B-then-A server
boots, so a complete verifier run has ten boots and ten FINAL markers.

For Reward stacking, alternative A uses field-local conditional accumulation,
while alternative B uses narrow
positive-reward merge helpers; neither copies the oracle's general stack helper.
The alternatives retain their distinct Boss boundary, Hypno lifecycle, Panic
fallback, Rainbow handoff, Warp eligibility, and cooldown strategies.

Rebuild and hash a candidate without network access:

```bash
python3 validation/candidates/rebuild.py predicate-reward /tmp/predicate-reward
```

`manifest.tsv` freezes each patch hash, changed-file set, and reconstructed tree
hash. Result matrices are recorded separately after real-server execution.
