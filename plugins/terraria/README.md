# Terraria benchmark plugin

Rhenium integration for independently authored Terraria/tModLoader
repository-debugging tasks.

Evaluation is layered and offline. A digest-pinned .NET SDK 8.0.419 source
projection compiles and executes selected real production mod files against
minimal doubles for engine-owned types. The full profile additionally compiles
the submitted production files into a real `.tmod` and loads it in pinned
tModLoader 2026.7.3.0 dedicated-server containers against Terraria 1.4.4.9.

Each public attempt receives one frozen mod snapshot plus its authored symptom
report. Private behavioral tests and reference repairs stay outside the attempt.
The plugin validates prompt/exam identity, source provenance metadata, exact
rubric-to-contract ordering, and both task-specific Docker image identities.
Dedicated-server engine sentinels cover integration behavior that is reliable
headlessly; each task records any client-only behavior retained in the exhaustive
source-projection layer.
