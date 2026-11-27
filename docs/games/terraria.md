# Terraria

| Field | Current value |
| --- | --- |
| Maintainer | Zhuoran |
| Status | `In Development` |
| Plugin ID | `terraria` |
| Game/API family | Terraria `1.4.4.9`; tModLoader `1.4.4` stable API |
| Runner platforms | Docker on Linux x86_64 or macOS Docker VM |
| Submission language | C#/.NET |
| Evaluation boundary | Layered: .NET SDK `8.0.419` production-source projection plus tModLoader `2026.7.3.0` dedicated server against Terraria `1.4.4.9` |

This layered evaluation does not meet the repository's real-game requirement (AGENTS.md,
"Real game and automatic acquisition"): its exhaustive layer runs every contract case on a
source projection with doubled engine types, and the tModLoader server is an
operator-supplied local file rather than one acquired automatically.

Terraria tasks are authored and audited one at a time under the
[Terraria authoring requirements](terraria-authoring-requirements.md). Each task
freezes a real mod revision, retains its license, exercises affected production
files, and records broken/oracle and per-defect controls before another task is
started.

The exhaustive layer replaces only engine-owned Terraria/tModLoader types with
minimal doubles and runs every private contract case deterministically. The
integration layer compiles selected submitted production files into a real
`.tmod`, loads it in the pinned tModLoader dedicated server without network,
and runs three task-specific engine sentinels. A full result is fail-closed:
missing, malformed, partial, wrong-version, or non-server engine evidence makes
the run incomplete and unable to pass. When a layer ran its exact frozen case set,
its check lists every case's outcome under `details.cases`; a partial case set is
never reported case by case. Docker control operations wait up to 300 seconds for
a congested daemon; the verifier processes keep their own limits.

Dedicated servers do not execute every Terraria client path. Each task's
`engine-rubric.json` identifies any client-only rendering, input, map, or IL
behavior that remains in the source projection. Those exclusions are explicit;
a successful server boot is never counted as evidence that a client-only path
ran. The exact runtime inputs, hashes, isolation model, and build flow are
documented in the pack's `private/runtime/README.md`.
