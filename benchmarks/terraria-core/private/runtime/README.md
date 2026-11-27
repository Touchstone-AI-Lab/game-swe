# Terraria native runtime

The `full` Terraria profile uses the official tModLoader `v2026.07.3.0`
GitHub release, which reports Terraria `v1.4.4.9`. The operator downloads
`tModLoader.zip` from the upstream release into the directory named by
`RHENIUM_TERRARIA_TML_DIR`; Rhenium verifies the complete archive SHA-256
before extracting it into a private Docker build context. The operator also
provides the MIT-licensed `Krafs.Publicizer` `2.2.1` NuGet package with its
pinned SHA-256; this is required to compile upstream mods that intentionally
publicize tModLoader internals.

The shared image contains the pinned .NET SDK and the verified tModLoader
installation. A task image adds only its private engine fixture. At evaluation
time the submitted source is copied into a fresh writable workspace, compiled
as part of a real `.tmod`, and loaded by the real tModLoader dedicated-server
process with networking disabled. The task's verifier mod writes a structured
report and terminates the process.

The source-projection verifier remains the exhaustive deterministic layer.
Engine cases are a smaller set of integration sentinels selected for behavior
that can be exercised reliably in the real server. Client-only map, rendering,
and input details remain source-projection assertions and are documented as
such; a server boot is never presented as evidence that those client paths ran.
