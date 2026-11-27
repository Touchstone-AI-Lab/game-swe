# Import and reference provenance

- Repository base: `origin/main` at `a518348d92ec590d355d0c8e7b8bc351a2360f59`.
- Reviewed reference: `origin/feat/palworld` at `9f7edfc053f7628a33a9767d63b7b8afc169def7`; this commit was
  already an ancestor of that main revision when inspected.
- Reviewed Palworld surfaces: `benchmarks/palworld/README.md`,
  `validation/advanced-controls.md`, `benchmark.json`,
  `plugins/palworld/pyproject.toml`, and `docs/games/palworld.md`.
- Source release: Balatro-10 v0.2, authored in the separate local PoC.
- Exact original public archive SHA-256: `a26813f28ce72ed5bcc1f0f54f856f505d60f65092e7e19cf4a14976a4e3c854`.

All 68 archive entries were retained as source files under `public/v02/` with
identical bytes. Existing contracts and starter defects were not translated,
rewritten or weakened. Aggregate validation is a newly authored sanitized view;
it is not a replacement for the original completed local evidence or an
independent rerun. Original evidence files and the original runtime remain with
the operator and were not modified by this import.

The imported assets are project-authored text and Lua. Balatro, Steam, LÖVE,
Lovely, Steamodded and BalatroBot executables, libraries and source trees were
not imported. This change makes no new licensing grant for any third-party
game or runtime content and does not prescribe acquiring or installing them.

The Palworld reference informs documentation boundaries and the separation of
participant material from operator evidence. Its anonymous dedicated-server
provisioning, UE4SS integration, rolling-version policy, headless operation and
portable Harbor simulation are not adopted as Balatro capabilities.

## Byte-preserving format exceptions

The source `isolated-card-wear-v2/starter/lib/wear.lua` line 10 and
`live-joker-adjacency-v2/starter/lib/adjacency.lua` line 13 contain space-only
lines. Initial staged whitespace inspection reported both. They were retained
verbatim rather than editing validated snapshots or updating their checksums.
Only these two frozen files have a `blank-at-eol` attribute exception; other
whitespace checks remain enabled, and the explicit SHA-256 allowlist checks all
bytes, including those two lines. No repository-wide whitespace policy changed.
