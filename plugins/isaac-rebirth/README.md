# rhenium-isaac-rebirth

Independent Rhenium plugin for The Binding of Isaac: Rebirth with Afterbirth and
Afterbirth+. It loads `isaac-rebirth` packs, materializes anonymous Exodus Lua
workspaces, and evaluates them against the fixed private native-game image.

The plugin wheel contains no installed game runtime or Steam state. Use
`rhenium auth login steam` followed by `rhenium runtime prepare
isaac-rebirth/afterbirth-plus-1.06.t1`. The managed artifact is proprietary and must
not be published or shared.

See `docs/games/isaac-rebirth.md` and `benchmarks/isaac-core/README.md`.
