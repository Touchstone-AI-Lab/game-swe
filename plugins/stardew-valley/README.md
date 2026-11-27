# rhenium-stardew-valley

In-development Stardew Valley engine plugin for the Rhenium 0.6 Hub. It owns the
C# starter materialization, Docker runtime probe, evaluator-image build, and
real-game result normalization for `stardew-valley/*` packs.

The plugin has no proprietary game dependency in its wheel. The independent Steam
provider acquires the fixed depot during `rhenium runtime prepare`; generated build
contexts and logs stay below `.rhenium/hub/`. Full evaluation containers always use
`--network=none`.

See `docs/games/stardew-valley.md` for the supported runtime matrix.
