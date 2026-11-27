# The Binding of Isaac core pack

This read-only pack contains one composite Exodus debugging task contributed and
maintained by Xuesong Ye, plus nine tasks derived from it (catalog 5.0.0). The public
task contracts live in `exams/`; the source snapshots, private assertions, reference
solutions, Harbor metadata, and validation history live below `private/` and are never
copied into anonymous attempts.

In catalog 5.0.0 each derived task also carries three supplementary regressions
(`private/supplementary-regressions/`): maintenance edits injected into the reference tree
whose diagnosis depends on Afterbirth+ runtime behaviour, reported in the exam verbatim and
repaired by the reverse of the injected edit, so every derived gold is still the unchanged
reference tree. The nine derived tasks run the shared 54-case verifier
`private/verifiers/exodus-v2/` (named by each catalog entry's `verifier` field and mounted
over the image's `test.sh` and suites); the frozen composite task, its exam, its 35-case
verifier and its checksum are unchanged. The next paragraph describes catalog 4.3.0, the
revision before.

In catalog 4.3.0, each derived task adds one independently testable regression to its
earlier report set, and all ten tasks are labeled hard. The added defects are reverted in
their starters and repaired in the matching gold patches. All ten tasks share the frozen
35-case verifier and the
`afterbirth-plus-1.06.t1` runtime binding. The derived tasks add one file of their own,
`tests/run-game.sh`, a launch script the Hub mounts over the image's copy: it waits for the
offline Steam client to finish starting before requesting the game launch and allows
longer wall-clock budgets, and decides no case (see any derived task's
`tests/README.md`). Each derived task's expanded base and reference were measured in the
real game on 2026-09-26 (UTC): every base fails exactly its previous measured set plus the
added report's case(s) with reward 0, and every reference passes 35/35 with reward 1, all
three processes complete and without a fatal marker (each task's `validation/controls.tsv`
and `validation/README.md`). The frozen composite task, its exam and its checksum are
unchanged in this revision.

The canonical baseline task key is
`isaac-rebirth/core/isaac-exodus-release-regressions`. The `core` profile checks
the submitted mod layout but is always incomplete. The `full` profile uses a
private local Docker image containing an operator-owned native Linux installation
of The Binding of Isaac: Rebirth with Afterbirth and Afterbirth+, disables
container networking, boots three game processes, and requires every declared real-game
assertion to finish (35 for the composite, 54 for a derived task).

See [Isaac support](../../docs/games/isaac-rebirth.md) for runtime setup and
support status.
