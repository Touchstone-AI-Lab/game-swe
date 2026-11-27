# RimWorld task-authoring candidate audit

This is an authoring research ledger, not a support matrix or validation report.
It records public source candidates for future `rimworld/core` tasks. A repository
appearing here does not authorize redistribution, does not make its runtime a
Rhenium dependency, and does not mean that its base or target has compiled or run
under Rhenium.

The snapshot date is 2026-09-09. The initial survey intentionally required GitHub's
MIT license classification, C# as a primary language, and either a RimWorld topic
or an explicit RimWorld 1.6 statement. Before a task copies any source, authoring
must re-read the license bytes at the exact selected commit, resolve all parent and
tag identities, inventory third-party notices, and copy only the minimum permitted
source plus the applicable license.

## Selection policy

High-priority candidates have all of the following:

- explicit RimWorld 1.6 metadata;
- an MIT code license at the source repository;
- substantial state, algorithm, scheduling, persistence, or cross-object logic;
- a bounded production entry point that can be observed deterministically;
- a real fix commit with a single-parent base and target, rather than an invented
  empty implementation;
- no required DLC and no required runtime Mod beyond Harmony, unless a later
  catalog/runtime decision explicitly expands the common dependency set;
- no requirement to redistribute textures, sound, compiled assemblies, Workshop
  payloads, saves, or proprietary game content.

## Catalog 0.3.0 authoring decision

The 2026-09-09 exact-source pass resolved every promoted pair through public,
credential-free GitHub objects. Every accepted historical target has exactly one
parent, the specified base; the applicable MIT license bytes cover the selected
source; and the audited 1.6 metadata has only Harmony as a hard Mod dependency.
Combat Readiness Check is the documented exception to byte-exact historical
source: its fix predates 1.6, so the task uses a faithful scoring-surface base
reconstruction and the exact retained target file from a proven 1.6 descendant.
Project RimFactory replaced Automatic Outfit Manager, and Combat Readiness Check
replaced Pick Up And Haul. The final nine additions are R4 ingredient consumption,
Project RimFactory, Adaptive Storage Framework, Combat Readiness Check, Customize
Weapon, Total Control, Bill Autopilot, Playwright, and Zombieland.

| Candidate | Decision | Exact-source note |
| --- | --- | --- |
| R4 ingredient consumption | accepted | `40daa82d0bcc65d6542a6acb81515e808f6d4184` -> `259c5d3992b2603b1a07e8d3db4b2446140874df`; one production file; MIT license SHA-256 `d94dffcf4684d8dc6f9a0f0b1c18696d8be625a21c0940c037d042daf2160f66` |
| Automatic Outfit Manager | rejected | The commits are a real single-parent production fix and declare Core + Harmony, but neither selected tree contains a LICENSE or NOTICE. The required compatible-license byte boundary therefore cannot be packaged. No source was copied. |
| Project RimFactory reserve | accepted as replacement | `6464e78a570914d0637157f3b55f48fa29f6b9d7` -> `4950a19d60cf8305ebad472b8ec256429cd18b45`; one cultivator source file; MIT license SHA-256 `6fd82a094b92b574ae9fba95ead292ba191b6ce0922da883cd07552fb9e5e5a0` |
| Adaptive Storage Framework | accepted with recorded 1.6 lineage | `2d0aef23f7b8592f9eedaaf8c8fc47b4dd1f0f5a` -> `6c403b09e22508fa929673caaec2877aa56ac9b5`; public 1.6 commit `31ee88b46651cfbe37da3f89620bc0b907165cc0` retains the relevant target transition unchanged |
| Pick Up And Haul | rejected | The target is a real single-parent production change, but `CountPastCapacity` returns the count *over* capacity and the target writes that number directly into `countQueue`; it neither computes the positive count that fits nor removes a zero-fit queue entry. It cannot prove the requested queue semantics, so no task source remains in the pack. |
| Customize Weapon | accepted | `47cf5e74ab3764242c1fbd833a97cba122c77f1e` -> `37c7140e2b7d6211f0cd6bfa6ed381705b090c81`; applicable `Source/LICENSE` preserved |
| Total Control | accepted | `cbaa04179a99e7020f592ab1d9f8cdf893960df6` -> `d58b2691233e4bcf5a803154f0e8ee1ca2558f8e`; symmetric apparel/weapon production files; scored fixtures remain Core-only |
| Bill Autopilot | accepted | `7c36614cb420b40068b67ea9b9b2225c01cdc06a` -> `61e6b2fe67dff6296de63383d8d92ad78077d5f5`; three production persistence/ownership files |
| Playwright | accepted | `11fa563967cf368e00f5011d79c9f9476019edb2` -> `f518aed8a2f2899c4e3c38a942685b7947eaeea7`; prefix state captures non-bulk goods before mutation |
| Zombieland | accepted | `6cbe9b443fdf72969f61b3f03adaaca13b15fa46` -> `f50cac11d97df1f8fc7f4aeada7e4c0842503c1b`; public REST commit object proves the sole parent; upstream bridge/test changes are excluded |
| Combat Readiness Check reserve | accepted as second replacement | `67f2446e4e6a3d38f7ac3b90c923f4967ee29f86` -> `f9b83ce14d9147510969878ff1bf96ed55d99544` is a single-parent wealth fix. Proven descendant `a3c1cd53260bbb74c8e3ce9e3cd012264c1758bb` declares 1.6 and retains the fix; the task-local provenance distinguishes its reconstructed 1.6 starter from the exact 1.6 oracle. MIT license SHA-256 `b93b4ab4758761c1f6c02e7bd2b6ef7b0ea8491a23c122040533a11de29e4023`. |

The task-local provenance files contain exact source hashes and exclusions. No
reference compilation, Docker image, Steam acquisition, real RimWorld launch, or
oracle/base/no-op run was performed during this source-authoring pass.

Repository size, number of source files, and popularity are discovery signals only.
They are not substitutes for a narrow task seam or two-way control validation.

## Platform survey

### GitHub

The public repository search returned a large pool of MIT-classified C# projects.
The strongest candidates below were further checked through public commit lists,
recursive file trees, and `About.xml` metadata. The C# footprint is the sum of blob
sizes in the surveyed default-branch tree; it includes repository test/support code
where present and is therefore only a comparative measure.

### Modrinth

The public Modrinth search API query for `rimworld` returned only the unrelated
Minecraft projects MineFortress and RimCrafting. No RimWorld Mod was selected from
Modrinth in this snapshot. A name match must not be treated as a game match.

### CurseForge

The public [RimWorld category](https://www.curseforge.com/rimworld) exposed four
projects during this survey. They were content/art-oriented listings and did not
provide the license-plus-public-fix-history evidence required for a C# debugging
task. None was selected. CurseForge discovery can corroborate distribution, but
pack source must still come from a versioned, license-audited source repository.

## Priority A: natural fixes on the common Core + Harmony boundary

These candidates have explicit RimWorld 1.6 metadata and no observed hard runtime
dependency beyond Harmony. They should receive full exact-commit and file-level
license review before task files are authored.

| Source | C# footprint | Natural task seam | Candidate base -> target | Authoring assessment |
| --- | ---: | --- | --- | --- |
| [R4](https://github.com/CheaterEater-RM/RRRR) | 43 files / 284,882 bytes | Consume repair ingredients from vanilla-equivalent stack and radial cells without consuming unrelated items or granting free repairs | `40daa82d0bcc65d6542a6acb81515e808f6d4184` -> `259c5d3992b2603b1a07e8d3db4b2446140874df` | Strong second R4 task. Map/cell observation is more involved than the existing material-basis task but the changed production surface is bounded. |
| [Automatic Outfit Manager](https://github.com/tekmojo/AutomaticOutfitManager) | 141 files / 2,002,336 bytes | Recover interrupted locker returns and keep hauling in the same active outfit session without cancel/reselect loops or duplicate activity rows | `67d02b817e0d5d9a72490128d019f9c73119e4b9` -> `ba9725a72d5e9a97a5f69e91d6f084fbbaea8366` | Excellent hard state-machine task. Requires deterministic pawn, area, job, and tick fixtures; UI rows should be secondary observations, not the sole score. |
| [Adaptive Storage Framework](https://github.com/bbradson/Adaptive-Storage-Framework) | 171 files / 1,206,741 bytes | Restore a saved slot limit during post-initialization without losing the setter transition or exposing the temporary unlimited value | `2d0aef23f7b8592f9eedaaf8c8fc47b4dd1f0f5a` -> `6c403b09e22508fa929673caaec2877aa56ac9b5` | Very strong narrow regression: a one-line fix protects a larger persistence/cache invariant. Must prove the parent fails under 1.6, because the commit also shipped older-version binaries that will not be copied. |
| [Rimsential - Total Control: Continued](https://github.com/feldoh/TotalControl) | 171 files / 1,020,542 bytes | Preserve vanilla pawn-kind quality and health generation when no explicit loadout override exists, while honoring explicit overrides and royalty minimums | `cbaa04179a99e7020f592ab1d9f8cdf893960df6` -> `d58b2691233e4bcf5a803154f0e8ee1ca2558f8e` | Strong gear-generation task across two symmetric files. Fixed `Rand` state and no-DLC controls are required; royalty behavior must be optional unless the runtime scope changes. |
| [Pick Up And Haul](https://github.com/Mehni/PickUpAndHaul) | 14 files / 65,352 bytes | Stop queue construction immediately at pawn inventory capacity and correct the final queued count without reserving or searching for impossible extra stacks | `8e7544e8f3855f84aea093bc029aeea22b0da485` -> `34cf64db4007f954b3173acf91a80e42eb7f5e81` | Rejected on exact audit: the target writes the calculated over-capacity count into the queue rather than the count that fits and lacks a zero-fit removal transition. |
| [Customize Weapon](https://github.com/realloon/CustomizeWeapon) | 58 files / 172,980 bytes | Lazily create a missing pawn ability tracker and keep managed ability/state synchronization correct across equip, unequip, reload, and empty-management paths | `47cf5e74ab3764242c1fbd833a97cba122c77f1e` -> `37c7140e2b7d6211f0cd6bfa6ed381705b090c81` | Strong lifecycle/persistence task. The task must use benchmark-authored minimal Defs and must not pull textures or unrelated modules. |
| [Bill Autopilot](https://github.com/vbardales/Rimworld-Bill-Autopilot) | 15 files / 101,901 bytes | Never flatten a bill repeat mode the Mod does not own while still updating owned bill policies and surviving save/load | `7c36614cb420b40068b67ea9b9b2225c01cdc06a` -> `61e6b2fe67dff6296de63383d8d92ad78077d5f5` | Promising ownership/persistence task. `About.xml` declares only Harmony as a hard dependency; DLC package IDs are load-order hints, not hard dependencies. Exact diff still needs file-level review. |
| [Playwright](https://github.com/morerokk/Rimworld-Playwright) | 172 files / 558,300 bytes | Count non-bulk trade goods correctly for a sell-items win condition without double counting or null trade-session behavior | `11fa563967cf368e00f5011d79c9f9476019edb2` -> `f518aed8a2f2899c4e3c38a942685b7947eaeea7` | Rich scenario/state code with several natural fix commits. The sell-items seam is preferable to its Biotech/Royalty fixes because it can stay on Core + Harmony. Exact target files and source notices still need review. |
| [Zombieland](https://github.com/pardeike/Zombieland) | 208 files / 5,085,371 bytes | Clamp affected needs to half of their dynamic maximum and floor protected pawn capacities at one without discarding enhancements above one | `6cbe9b443fdf72969f61b3f03adaaca13b15fa46` -> `f50cac11d97df1f8fc7f4aeada7e4c0842503c1b` | Excellent high-complexity semantic task with variable-max and enhanced-capacity boundaries. The source tree is very large, so only the minimum patch and required types may enter a pack; upstream bridge/test tooling is evidence to audit, not content to copy. |
| [Project RimFactory Revived](https://github.com/zymex22/Project-RimFactory-Revived) | 237 files / 943,447 bytes | Plant only when local growth season, sowing, blocker, and vacuum rules all permit it instead of relying on global map temperature | `6464e78a570914d0637157f3b55f48fa29f6b9d7` -> `4950a19d60cf8305ebad472b8ec256429cd18b45` | Good map/environment behavior, but the repository also has 716 XML files. Authoring must prove a minimal compilable source slice and avoid packaging its content assets. |
| [Combat Readiness Check Continued](https://github.com/emipa606/CombatReadinessCheck) | 5 files / 25,302 bytes | Calculate colony wealth and derived raid points from the intended categories without the historical omission | `67f2446e4e6a3d38f7ac3b90c923f4967ee29f86` -> `f9b83ce14d9147510969878ff1bf96ed55d99544` | Semantically useful but smaller than the preferred pool. The fix predates the 1.6 port, so authoring must prove a faithful 1.6 base/target reconstruction rather than pretending the old commit itself was a 1.6 snapshot. |
| [Use This Instead](https://github.com/emipa606/UseThisInstead) | 10 files / 58,542 bytes | Replacement selection and substitution across matching defs | No natural fix pair selected | Supports 1.6 with Harmony only, but automated replacement updates dominate recent history. Keep in reserve until a bounded behavioral regression is located; do not synthesize an empty implementation merely to use the Mod. |

## Priority B: complex 1.6 sources needing deeper commit audit

These projects were discovered through the MIT + RimWorld 1.6 query and show
substantial behavior or content. They are not yet approved task sources because a
single-parent fix pair, exact dependency boundary, or minimal source slice remains
unresolved.

| Source | Observed scale | Behavior worth investigating | Open authoring question |
| --- | ---: | --- | --- |
| [Playable Recreation](https://github.com/tr8425/PlayableRecreation) | 146 C# files / 946,857 bytes | Multi-pawn recreation sessions, opponent selection, match beats, forfeits, relationship outcomes | Recent history is feature-heavy; locate a real bounded regression and confirm the unusual default branch identity. |
| [Search and Rescue](https://github.com/CH4ACKO3/SearchAndRescue) | 83 C# files / 1,159,571 bytes | Battlefield treatment, rescue/capture selection, medicine and hauling logistics | Supports 1.6 with Harmony. Commit query was rate-limited; identify a single-parent behavior fix before promotion. |
| [Soil Relocation](https://github.com/EscarvalOokt/SoilRelocation) | 74 C# files / 744,438 bytes | Terrain extraction, physical soil resources, placement/removal validation and extensibility | Supports 1.6 with Harmony and has dedicated test Mods. Need natural base/target selection and an asset-free task slice. |
| [Research: Organized](https://github.com/Cruesoe/ResearchOrganized) | 12 C# files / 121,677 bytes | Tech-level grouping and graph/tree layout | Supports 1.6 with Harmony. Prefer algorithmic graph layout assertions; avoid making screenshot geometry the primary oracle. |
| [RimExodus](https://github.com/Laurence-042/RimExodus) | repository size 102,373 KiB | Multi-map seams, river pinning, mover path costs, terrain references and cross-map transfers | Extremely rich but expands the fixture and compatibility surface. Candidate `83b0560ca9f8b9ff4367e56c9df108d64c4de404` -> `93426c08ce5c7702ce4d3bdb4ea60ccd97501c50` needs exact dependency and source-tree audit. |
| [SimLOD](https://github.com/traecneh/SimLOD) | repository size 8,588 KiB | Persistent abstract entities, ownership and recoverable native/abstract transitions | Strong conceptual fit, but the surveyed default branch is `codex/release-candidate`; source tree, license at commit, and natural fix history still need independent retrieval. |
| [Apparel Painter](https://github.com/beverage/apparel-painter) | repository size 15,905 KiB | Exact color/state changes across apparel, outfit stands, racks and shelves | README states 1.6, no DLC and no dependency. Recent sampled commits did not expose a natural bug-fix pair. |
| [Intercolony](https://github.com/miannoni/Intercolony) | repository size 7,422 KiB | Faction commerce, contracts, hiring and temporary worker state | Rich domain behavior; dependency, persistence, source footprint and fix history were not resolved before the GitHub secondary rate limit. |
| [Rimworld Playwright](https://github.com/morerokk/Rimworld-Playwright) | 172 C# files / 558,300 bytes | Scenario serialization, trade win conditions, permanent-condition uniqueness and pawn customization | One Core-compatible seam is promoted above; DLC-specific fixes remain out of the common runtime. |
| [Zoology Framework](https://github.com/AbobaShark/ZoologyMod-Framework-For-Rimworld) | repository size 249,224 KiB | Large animal-performance framework and biological stat mapping | Content and asset boundary is enormous. Use only if a small code-only invariant and exact license inventory can be isolated. |

## Priority C: dependency-expanded or unsuitable for the first common runtime

| Source | C# footprint | Reason to defer |
| --- | ---: | --- |
| [Shift Change](https://github.com/beverage/shift-change) | 36 files / 649,290 bytes | Complex and attractive, but Odyssey is a hard dependency. |
| [Rimworld Cosmere](https://github.com/RimworldCosmere/RimworldCosmere) | 190 files / 366,533 bytes | Requires Biotech plus multiple internal Cosmere Mods; large asset/content boundary. |
| [Mech Muster](https://github.com/coolnether123/MechMuster) | 16 files / 61,833 bytes | Requires Biotech and SpineLib. |
| [Caravan Readiness](https://github.com/coolnether123/CaravanReadiness) | 20 files / 128,274 bytes | Strong cargo/readiness aggregation, but requires SpineLib. |
| [Filter by Example](https://github.com/coolnether123/FilterByExample) | 19 files / 58,040 bytes | Requires SpineLib and recent history is dominated by support-cascade changes. |
| [Filter Signals](https://github.com/coolnether123/FilterSignals) | 28 files / 176,910 bytes | Requires SpineLib; several recent commits change developer fixture contracts rather than player behavior. |
| [Turn It On and Off - RePowered](https://github.com/emipa606/TurnOnOffRePowered) | 11 files / 63,426 bytes | Requires HugsLib in addition to Harmony. |
| [Yet Another Optimizer](https://github.com/szszss/YetAnotherOptimizer) | 326 files / 895,926 bytes | Rich concurrency and compatibility logic, but many fixes require other Mods and thread-sensitive evidence. Keep for a later dependency/host matrix. |
| [Kingfisher](https://github.com/realloon/Kingfisher) | 16 files / 60,661 bytes | Runtime optimization relies on patcher/tooling dependencies and the repository has a mixed MIT/MPL notice set. Exact file licensing and performance evidence need a separate design. |
| [Fermenter Continued](https://github.com/emipa606/Fermenter) | 20 files / 70,001 bytes plus 389 XML files | Most recent changes are XML compatibility patches; lower fit for a complex C# behavior benchmark. |

## Final ten-task catalog queue

This is a readable summary of the accepted `catalog.json` queue. The catalog is
authoritative. The queue keeps one shared RimWorld 1.6 Core + Harmony runtime
while emphasizing different kinds of complex behavior.

1. Existing R4 uncraftable material basis task.
2. R4 ingredient consumption around small benches.
3. Project RimFactory cell-local cultivator conditions (replaced Automatic Outfit Manager).
4. Adaptive Storage Framework loaded slot-limit restoration.
5. Combat Readiness Check raw colony wealth (replaced Pick Up And Haul).
6. Customize Weapon missing ability tracker and managed state lifecycle.
7. Total Control vanilla quality/health fallback generation.
8. Bill Autopilot repeat-mode ownership and persistence.
9. Playwright non-bulk trade win-condition accounting.
10. Zombieland dynamic-maximum need and enhanced-capacity preservation.

Project RimFactory was the first reserve and replaced Automatic Outfit Manager.
Combat Readiness Check was the second reserve and replaced Pick Up And Haul after
its faithful 1.6 base reconstruction and exact retained 1.6 target were proven.

## Promotion gate for an individual candidate

A candidate moves from this ledger into `catalog.json` only after all of the
following authoring work is complete:

1. Record the exact repository, single parent, target commit, relevant tag/release,
   and immutable hashes from fresh read-only evidence.
2. Read the license and every notice covering the selected files at both commits.
3. Inventory the full diff and select a non-overlapping scored production surface.
4. Define public behavior without revealing private fixture values.
5. Materialize an independent starter from the selected base; do not manufacture a
   no-op by deleting behavior unless that mutation is explicitly reviewed.
6. Create an oracle from the selected target files only.
7. Design one private assertion manifest for the task, including gates, expected
   observations, weights, and negative controls.
8. Document all DLC/Mod assumptions and keep any unrequired dependency out of the
   runtime and pack.
9. Leave compile, container, and real-engine results as `not-run` until the separate
   validation owner supplies evidence. Planned counts are never execution evidence.
