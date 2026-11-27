# Mindustry Benchmark Plugin

Rhenium integration for two Mindustry benchmark packs. The plugin dispatches on the
catalog id:

- `rhenium-mindustry-v2` (`benchmarks/mindustry-core`, Hub key `mindustry/mindustry-core`):
  five repair tasks on the Mindustry game sources, evaluated by `evaluator.py` with the
  `mindustry/mindustry-159.7` runtime (`runtime_builder.py`, `container.py`).
- `rhenium-mindustry-v1` (`benchmarks/mindustry-construct`, Hub key `mindustry/construct`):
  ten construct tasks that ask for a server plugin written from an empty scaffold,
  evaluated by `construct_evaluator.py` with the `mindustry/mindustry` runtime
  (`construct_runtime_builder.py`). These modules are the pre-`9b038435` generation
  evaluator and runtime builder, restored with longer Docker bookkeeping timeouts.

The rest of this page describes the repair pack; the construct pack is described in
[the support matrix](../../docs/games/mindustry.md).

Every repair task is a repository-debugging task on the open-source Mindustry v159.7 game
sources: the plugin loads the `rhenium-mindustry-v2` catalog, materializes the vendored
`mindustry/` source tree with its upstream defects as the starter, builds the pinned
verifier images, and evaluates submissions through each task's private Harbor verifier.

The runtime catalog uses the official-download provider to download the pinned
Mindustry dedicated-server jar (`server-release.jar` of the v159.7 release), pinned by
URL, size and SHA-256; the builder verifies the SHA-256 again. The jar is not stored in
this repository. Prepare it explicitly with `rhenium auth login official-download`,
`rhenium runtime prepare mindustry/mindustry-159.7`, and
`rhenium runtime verify mindustry/mindustry-159.7`. Preparation builds the base image
(digest-pinned JDK 17, the trusted harness, one bootstrap boot of the real server) and
one verifier image per task; the image builds need network access for Debian packages.
Evaluation containers run without network access.

A full evaluation compiles the submitted `core/src` and `server/src` offline with `javac`
against the pinned jar and runs the hidden suite inside the real headless dedicated
server. It is complete only when the harness reports every frozen case exactly once
under the run's nonce; a core-profile run, a rejected submission, a build failure or a
server failure is incomplete and cannot pass. See
[the support matrix](../../docs/games/mindustry.md) for the download command, the
digests and the acceptance record.
