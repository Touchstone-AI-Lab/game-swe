# Slay the Spire benchmark pack

Multi-defect regression tasks built from
[ModTheSpire](https://github.com/kiooeht/ModTheSpire) (MIT), the loader and bytecode
patching engine that every Slay the Spire mod is loaded through. It is a Java 8 project
built with Maven.

| task | assertions |
|---|---|
| `mts-load-order-regressions` | 9 |
| `mts-mod-identity-regressions` | 7 |
| `mts-loader-internals-regressions` | 16 |

Eight tasks were built during this work; five were not kept. What they taught is in
`validation/`, including the two cases where the task was destroyed by the wording of its
own bug report.

```text
benchmarks/slay-the-spire-core/
├── catalog.json              bilingual task metadata
├── exams/                    the public problem statement for each task
├── private/harbor/           the Harbor task packages (environment, tests, solution)
└── validation/               how each task was validated
```

## The pack runs without the paid base game

This is the point of building on ModTheSpire rather than on a mod. Slay the Spire is a
paid game and its `desktop-1.0.jar` cannot be redistributed, so anything that links
against it is undistributable. ModTheSpire is different: the parts these tasks exercise —
dependency resolution, mod descriptors, patch generation, parameter binding, enum
injection — all compile and run against nothing but the JDK and Javassist.

Concretely, each task's image strips the `systemPath` dependency on the game jar and
excludes the two source trees that genuinely need it (`patches/**` and `PackageJar.java`).
Everything the tasks touch builds and is graded without a game install, without a display
and without network access.

**JDK 8 is required, not incidental.** `MTSClassLoader` and `EnumBusterReflect` use
`sun.misc` and `sun.reflect` internals, and `ReflectionHelper` rewrites `Field.modifiers`
— all removed or blocked from Java 9 onwards. On a newer JDK the build fails in a way that
looks like a missing game dependency and is not.

## The pack ships without `benchmark.json`, deliberately

There is no `rhenium-slay-the-spire` plugin, and the Hub discovers packs by finding a
`benchmark.json`. Shipping one that names a plugin which does not exist would make the
pack discoverable and then unrunnable, so it is omitted and the pack stays inert until a
plugin exists. `runtimes.json` is omitted for the same reason and because there is no
external runtime to pin: each task builds its own image from `environment/Dockerfile`.

This mirrors how the DarkRP pack was first landed.

## Evaluation contract

Each task is a plain Harbor package: the verifier stages a private JUnit suite over the
submission, runs `mvn -o -B clean test`, and writes `1` to `/logs/verifier/reward.txt`
only when the exact expected number of assertions passes with no failures and no errors.
`clean` is load-bearing — a submission copied in with older timestamps would otherwise be
judged up to date against the image's compiled classes and the verifier would grade stale
bytecode.

The Maven repository is warmed at image build time by running the exact goals the verifier
runs, and the warm-up is then repeated with `-o` as a build-time assertion, so an
incomplete cache fails the image build rather than a scored run.

## Tasks and public metadata

Public exams and catalog summaries describe only what a mod author observed. They
intentionally omit defect counts, subsystem maps, diagnoses, internal identifiers and private
case counts. The construction history and validation matrices stay in the private Harbor
metadata available to maintainers.

## What makes these tasks hard, and what does not

On this codebase the lessons run opposite to the sibling DarkRP pack's:

- **Spreading defects across subsystems does not work here.** ModTheSpire is a few dozen
  small files, so a single `find … | xargs grep -l` retrieves the whole subsystem map.
  With no localisation cost there is no budget pressure, so each extra report is simply
  another pointer.
- **Raising the cost of *finding* the defect does not work here either.** Spread, defect
  count, intricate index arithmetic and generated-code conventions were each tried. On an
  engine this size any symptom names a feature and a feature name is a region name.
- **What remains is tasks where knowing which lines are wrong does not tell you what the
  right lines are.** The three tasks in this pack are all of that kind: correctness is
  fixed by a global property (a topological order over the whole dependency graph) or by a
  semantic decision the code never records (which field identifies a mod across a rename;
  which parser must read a stored version back).
- **A corollary about supply.** Count the axes in a codebase where correctness is globally
  determined rather than locally checkable. This engine has about three, and it produced
  about three tasks. Eight were built.

See `validation/` for the per-task matrices.

## A note for anyone training on this pack

Several tasks touch the same files — `ParameterPatchInfo.java` in particular, because it
is where the source for every parameterised patch is assembled. The *defects* are in
disjoint lines and each task's gold patch only restores its own, but a gold patch for one
task does show the correct text of lines that another task leaves alone in the same file.

That is fine for evaluation, where solutions are never shown to the model. It matters if
you train on one task's patch and evaluate on another: hold out by file, not only by task.

## Provenance of the vendored snapshot

Each task's `environment/modthespire/` is a verbatim snapshot of the upstream ModTheSpire
tree — nothing added, nothing removed — apart from the defects the task is about and the
three build-level adjustments described above (the `systemPath` dependency on the game jar
stripped, `patches/**` and `PackageJar.java` excluded from compilation, and a dead
`javafx.util.Pair` import removed from `ui/UpdateWindow.java`).

Upstream's `LICENSE` (MIT, © 2018 Anthony Moore) travels with the snapshot. Two things a
reviewer will notice and should not be surprised by:

- the tree contains a vendored copy of `org.clapper.util`, which upstream ships **without
  per-file licence headers** and does not mention in its `pom.xml` or `README`. That is
  how ModTheSpire ships it; we have neither added headers it does not have nor removed
  files it does. The library itself is BSD-licensed.
- `.mvn/wrapper/maven-wrapper.jar` is checked in. The tasks do not use it — the image
  invokes `mvn` directly — but it is part of the upstream tree and removing files from a
  snapshot is its own kind of infidelity.

Each task carries its own full copy of the tree, which is what makes a task a
self-contained Harbor package. That is the same layout the DarkRP pack uses.
