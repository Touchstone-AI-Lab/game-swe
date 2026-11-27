# Historical manual native Linux validation runtime

This records the plugin 0.6.1 manual prototype. Plugin 0.7.0 uses the managed
`rhenium runtime prepare` workflow in `docs/games/palworld.md`; the prototype is
not a required input or fallback. This is an experimental, manually prepared Linux x86_64 runtime. It runs the
native Palworld server and a native UE4SS port. Wine and Windows executables are
not used. The current ten-task catalog has a separate real-engine control
record in `benchmarks/palworld/validation/linux-controls.md`.

This directory contains source instructions and hashes only. Do not redistribute
the server, Steam client state, loader binary, or the private local image.

## Recorded preparation

Preparation is an explicit operator step. Evaluation does not acquire, install,
update, compile, or authenticate anything.

1. Acquire Steam App 2394010 for Linux with anonymous SteamCMD into a disposable
   directory. The recorded build is **25247047**, game **v1.0.5.102999**,
   Unreal **5.1.1**. Preserve the installation as `/server` in the local image.
2. Build [BlackBookOfficial/ue4ss-linux-palworld](https://github.com/BlackBookOfficial/ue4ss-linux-palworld)
   at commit `2397c7b1ce2841fd6526b8d8110cd008c90a6316`.
   The source archive SHA-256 is
   `1e4fe405257d6c6ec2e63546feae35c47407d4528d0f4f83bd7d5b83975e5591`.
   The recorded build used GCC 13, Rust 1.90.0 and CMake configuration
   `Game__Dev__Linux64`, GUI enabled, input and profilers disabled. Install the
   resulting `libUE4SS.so` under `/server/ue4ss`.
3. Use the port's v1.0.2 Lua/configuration assets. That release archive has SHA-256
   `9c472b62a633877acddf2dcaf61826583f0d50b2c4e11723c71da5a4ea81abd9`.
   Disable console windows and hot reload. Remove empty numeric INI overrides.
   Set `FExecVTableOffsetInLocalPlayer = 40` in decimal. Keep EngineTick dispatch.
4. Apply `uehelpers-world.patch` to the runtime's shared `UEHelpers.lua`. The
   port's `GameInstance:GetWorld()` path crashed on this server. The patch waits
   for game-thread readiness, then returns a real reflected `World` object.
   `UKismetSystemLibrary:IsDedicatedServer` still runs in the real engine.
   No authority result or assertion is simulated.
5. Place the acquired Linux `steamclient.so` at
   `/server/runtime-home/.steam/sdk64/steamclient.so`. Install the checked-in
   `run-native` launcher as `/server/run-native` with executable permission.
6. Before sealing the image, verify every file against `pins.json`. Write those
   same entries as SHA-256 checksum lines to `/server/rhenium-runtime.sha256`.
   The launcher checks all seven entries before each server launch and exits on
   any mismatch. Its fixed `/server` paths are intentional.

The immutable local image ID tested on the controlled host is
`sha256:55acf9a22ae86cfc2a522e87f2d3e2a9330865fe04c44a23e783da094bcf30ba`.
It is local and non-redistributable. A rebuild can produce different bytes; do
not change the recorded pins to accept it without repeating the controls.

## Evaluation

Run the existing Rhenium evaluator inside that prepared Linux environment, with
the pack and original submission mounted read-only and writable state outside
the pack. The Python environment needs the core and Palworld plugin installed.
Set the plugin-owned variables before the ordinary scoring command:

```sh
export RHENIUM_PLUGIN_PALWORLD_ROOT=/server
export RHENIUM_PLUGIN_PALWORLD_SERVER_BIN=/server/run-native
```

Use the exact `scripts/score-exam` command printed in the prepared attempt's
`PROMPT.md` for an exam. The launcher must execute as an unprivileged user.
Use `--network none`, `--cap-drop ALL`, `--security-opt no-new-privileges`, and
separate writable container overlays for independent runs. The controlled runs
used 8 CPUs and 16 GiB per container. Never evaluate against a live game server.

The original plugin 0.6.1 inventory was manual and unregistered. Plugin 0.7.0
replaces that inventory with a managed runtime definition, registered through
`benchmark.json.runtime_catalog`. The managed builder does not use this local
prototype image. An operator must prepare and select
the runtime explicitly. This does not claim general Linux mod support, another
loader revision, another game build, or Windows validation of this launcher.

The prior release loader also had startup and Tick-dispatch defects. The retired
Palbox and damage tasks crashed on their specific engine hooks even with the
recorded native build. Their assertions were preserved; new task identities
replace them in catalog 2.0.0.

## Replay maintenance controls

`controls.py` is the maintenance harness used for the recorded runs. It runs
gold, empty NOP and service-absent controls through the full evaluator, checks
all expected engine case counts and checks registry/mod cleanup. Do not expose
this harness or its reference inputs to a model attempt.

From the repository root, set `CONTROL_OUTPUT` to a fresh absolute directory
writable by UID 1001, then run against the already prepared local image:

```sh
docker run --rm --network none --cpus 8 --memory 16g --cap-drop ALL \
  --security-opt no-new-privileges \
  -e PYTHONPATH=/workspace/src:/workspace/plugins/palworld/src \
  -v "$PWD:/workspace:ro" -v "$CONTROL_OUTPUT:/evidence" \
  sha256:55acf9a22ae86cfc2a522e87f2d3e2a9330865fe04c44a23e783da094bcf30ba \
  python /workspace/plugins/palworld/runtime/linux/controls.py
```

Use `CONTROL_SHARDS=3` and a distinct `CONTROL_SHARD=0`, `1`, or `2` plus a
fresh output directory/container for each shard to reproduce the recorded
parallel run. The harness fails rather than overwriting an existing submission.
Raw logs remain local; the committed record contains only control outcomes and
authored source hashes.
