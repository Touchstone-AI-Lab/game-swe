# rhenium-palworld

Independent Palworld plugin for the Rhenium benchmark Hub.

The package owns the Palworld catalog models, Lua analyzer and sandbox,
evaluator, public checker, and UE4SS dedicated-server runtime integration. Its
game data remains in the repository's `benchmarks/palworld/` pack.

```sh
python -m rhenium_palworld.public_check /path/to/submission
```

Submissions are UE4SS Lua mods packaged with a Palworld `Info.json` manifest and
a `scripts/main.lua` entry point.

Runtime paths use `RHENIUM_PLUGIN_PALWORLD_ROOT` and
`RHENIUM_PLUGIN_PALWORLD_SERVER_BIN`. Core Rhenium does not read these
variables. Discovery prefers
`Pal/Binaries/Win64/PalServer-Win64-Shipping.exe`: `PalServer.exe` is only a
launcher, and terminating it would orphan the server it spawned.

Catalog 2.0.0 has ten construct tasks. Eight retain their original contracts.
Two replacements use exact constrained graph/order optimization and a native
PlayerController hook. Plugin 0.7.0 registers a native Linux x86_64 managed
runtime, with pinned depot acquisition through the existing Steam provider and plugin-owned
UE4SS compilation. The normal Hub evaluator consumes only the ready artifact
passed by core, using its immutable local image ID. Environment variables do
not select a fallback for managed evaluation.

```sh
rhenium auth login steam
rhenium runtime prepare palworld/palworld-linux-25247047-native-2397c7b
rhenium runtime verify palworld/palworld-linux-25247047-native-2397c7b
```

The existing Steam provider uses a QR-authenticated account session and never
requests or accepts a Steam password.
Preparation uses the network; evaluation runs a fresh network-disabled native
Linux container and never acquires, installs or rebuilds a runtime. Docker must
already be available. Runtime assets are source-only package data under
`src/rhenium_palworld/native/`; no game or loader binary ships in the wheel.
See [Palworld support](../../docs/games/palworld.md) for the operator workflow
and measured validation boundary. The previous manually prepared image and its
controls remain historical evidence in
[`runtime/linux/README.md`](runtime/linux/README.md).

Two API details matter when reading this code. Palworld's shipping build does
not export `UGameplayStatics::IsDedicatedServer`, so authority comes from
`UKismetSystemLibrary::IsDedicatedServer`, and `NotifyOnNewObject` needs a full
class path such as `/Script/Pal.PalPlayerController`. UE4SS also starts Lua
mods before the server owns a valid `UWorld`, which is why the injected
assertion suite polls for world readiness instead of firing after a fixed
delay. See [Palworld benchmark support](../../docs/games/palworld.md).
