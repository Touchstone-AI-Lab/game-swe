# Maintainer notes

This task freezes GPL-3.0-or-later source from `SilvDev/Left4DHooks` at
`3d44e2207d8ec1218f46667e2c05e4f127a5fb74`. It contains twelve independent
behavior groups: ammo pointers, vomit-jar detours, spawn timers, float weapon
attributes, animation hooks, pipe-bomb detours, campaign scores, melee info,
stagger cleanup, gas-can detours, entity-address decoding, and lobby reservation
cookies. Nine regressions are seeded from real historical fixes and three are
preserved upstream defects repaired from later upstream revisions.

The frozen schema-1.4 contract has 72 cases. Seventy cases execute in thirteen
fresh L4D2 dedicated-server boots; two additional cases compile and inspect the
public SourcePawn ABI. The Molotov boot is a negative guard for the VomitJar
detour family, so the number of server boots is intentionally one greater than
the number of independent defect groups.

## Frozen behavior evidence

- Broken base and byte-identical nop: 30/72, reward 0. Two affected boots emit
  semantic fatal lines before `FINAL`; the verifier fails those boots closed.
- Oracle: 72/72, reward 1, in three independent full runs.
- Twelve single-group predicates: 33, 35, 36, 32, 31, 32, 35, 35, 32, 34,
  32, and 35 passes. Every newly passing case belongs to the intended group and
  guard regressions are zero.
- Two structurally different non-oracle alternatives: 72/72 each.
- Every full run contains exactly 72 unique case results. Healthy submissions
  produce thirteen unique `FINAL` sentinels; duplicate, missing, extra, or
  post-`FINAL` cases fail closed. Fatal-like lines are scanned through the
  matching `FINAL`; normal shutdown noise after it is ignored.

All fourteen candidate patches apply from the broken base with
`core.autocrlf=false`; independently rebuilt tree hashes match the frozen
manifest. Production sources, the oracle, and every rebuilt candidate use pure
LF with exactly one final newline. The public and private package scanners allow
either pure LF or pure CRLF per file, while mixed EOL and lone CR fail closed.

The package matrix has 22 rows: four expected accepts and eighteen expected
rejects. It covers the original tree, pure CRLF, mixed/lone-CR input, patch
residue, missing required files, removed licensing, compiled artifacts, reserved
markers, invalid UTF-8, and NUL bytes. Eight synthetic parser attacks separately
cover valid output, accepted post-`FINAL` shutdown noise, pre-`FINAL` fatal text,
duplicate/missing/extra cases, duplicate `FINAL`, and cases after `FINAL`.

## Frozen artifacts

- Evaluation contract: `43dd6fa0aade407ea7ac0d5c61eb6c97ce0874a57e667f888a95601be0dc995f`
- Verifier image: `sha256:ba3f759aad4e366983d1883779b95ecf24d594402a73429f3f22de6d194d0610`
- Agent image: `sha256:f309c97a8a5e2fbafeeac263ec4bd1bed32e44f2beb3bd7639d7a36ea6e1934a`
- Verifier payload: 20 host/image files, byte-exact.
- Agent artifact: 19 host/image files, byte-exact; every path has mtime epoch 0.
- Task hygiene: no committed `.smx`, logs, caches, `.orig`, or `.rej` files.

The public smoke command compiles `left4dhooks.sp` with SourceMod
1.12.0.7246. The verifier runs with no network.

No Valve game payloads or compiled SourceMod plugins are committed.
